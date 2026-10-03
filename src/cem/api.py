"""Protected same-origin local workbench and explicit bounded monitoring controls."""

from pathlib import Path
from dataclasses import dataclass, field
from threading import Lock
from contextlib import asynccontextmanager
import secrets
import time
import mimetypes
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.exceptions import RequestValidationError
from .domain import StrictModel
from pydantic import Field
from .errors import CEMError
from .storage import Store, reject_symlink_chain
from .comparison import compare
from .rules import evaluate
from .reports import render
from .operations import Operations, TargetAction, ReviewDecision
from .pilot.policy import PilotConfig

CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"


@dataclass
class Session:
    bootstrap: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    created: float = field(default_factory=time.monotonic)
    bearer: str | None = None
    active_since: float = 0
    last_seen: float = 0
    lock: Lock = field(default_factory=Lock)

    def exchange(self, secret: str) -> str:
        with self.lock:
            if (
                self.bearer
                or time.monotonic() - self.created > 60
                or not secrets.compare_digest(secret, self.bootstrap)
            ):
                raise CEMError("AUTH_REQUIRED", "The bootstrap link expired or was already used.", 401)
            self.bearer = secrets.token_urlsafe(32)
            self.bootstrap = ""
            self.active_since = self.last_seen = time.monotonic()
            return self.bearer

    def authorize(self, authorization: str):
        token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
        with self.lock:
            now = time.monotonic()
            if (
                not self.bearer
                or now - self.last_seen > 1800
                or now - self.active_since > 28800
                or not secrets.compare_digest(token, self.bearer)
            ):
                raise CEMError(
                    "AUTH_REQUIRED",
                    "Local session expired. Obtain a new bootstrap from the local terminal.",
                    401,
                )
            self.last_seen = now


class Bootstrap(StrictModel):
    secret: str = Field(min_length=40, max_length=100)


class BaselineSelection(StrictModel):
    run_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    reason: str = Field(min_length=3, max_length=500)


class RetentionConfirmation(StrictModel):
    confirmation: str = Field(pattern=r"^[a-f0-9]{64}$")


def create_app(
    store: Store, session: Session, port=8760, assets: Path | None = None, *, monitor_root: Path | None = None
) -> FastAPI:
    if not 1024 <= port <= 65535:
        raise CEMError("INVALID_INPUT", "Choose an unprivileged local port.")
    origin = f"http://127.0.0.1:{port}"
    expected_host = f"127.0.0.1:{port}"
    assets = assets or Path(__file__).parent / "web"
    operations = Operations(store)

    @asynccontextmanager
    async def lifespan(_app):
        worker = None
        if monitor_root is not None:
            from .monitor import Worker

            if store.read_only:
                raise CEMError("READ_ONLY_DEMO", "Demo cannot start a pilot runner.", 403)
            worker = Worker(operations, monitor_root)
            worker.start()
        try:
            yield
        finally:
            if worker:
                worker.stop()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    def error(code, message, status):
        return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)

    @app.exception_handler(CEMError)
    async def cem_error(_request, exc):
        return error(exc.code, exc.message, exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _exc):
        return error("INVALID_INPUT", "Request violates the typed API contract.", 422)

    @app.exception_handler(Exception)
    async def internal_error(_request, _exc):
        return error("INTERNAL_ERROR", "The local operation failed. No successful result was recorded.", 500)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        try:
            # Inspect duplicate security headers before a convenience accessor folds them.
            pairs = request.scope["headers"]
            for key in (b"host", b"origin", b"authorization", b"content-type", b"content-length"):
                if sum(k.lower() == key for k, v in pairs) > 1:
                    raise CEMError("INVALID_INPUT", "Duplicate security headers are forbidden.", 400)
            if request.headers.get("host") != expected_host:
                raise CEMError("HOST_DENIED", "Host is outside the local session.", 403)
            if any(
                k.lower() in (b"forwarded", b"x-forwarded-host", b"x-forwarded-proto", b"x-forwarded-for")
                for k, v in pairs
            ):
                raise CEMError("HOST_DENIED", "Forwarded requests are not supported.", 403)
            request_origin = request.headers.get("origin")
            fetch_site = request.headers.get("sec-fetch-site")
            if (
                request_origin is not None
                and request_origin != origin
                or fetch_site in ("cross-site", "same-site")
            ):
                raise CEMError("ORIGIN_DENIED", "Cross-origin local access is forbidden.", 403)
            if request.method not in ("GET", "POST"):
                raise CEMError("METHOD_DENIED", "This method is not supported.", 405)
            api = request.url.path.startswith("/api/")
            if api:
                if request.method == "POST":
                    if (
                        request_origin != origin
                        or request.headers.get("content-type", "").split(";")[0].strip() != "application/json"
                    ):
                        raise CEMError("ORIGIN_DENIED", "Writes require same-origin JSON.", 403)
                    raw = bytearray()
                    async for chunk in request.stream():
                        raw.extend(chunk)
                        if len(raw) > 8192:
                            raise CEMError("ARTIFACT_LIMIT", "Request body exceeds 8 KiB.", 413)
                    request._body = bytes(raw)
                elif request.headers.get("content-length", "0") != "0":
                    raise CEMError("INVALID_INPUT", "GET request bodies are not supported.")
                if fetch_site is not None and fetch_site != "same-origin":
                    raise CEMError("ORIGIN_DENIED", "API requests must use the same origin.", 403)
                if request.url.path != "/api/v1/session/bootstrap":
                    session.authorize(request.headers.get("authorization", ""))
            response = await call_next(request)
        except CEMError as exc:
            response = error(exc.code, exc.message, exc.status)
        response.headers.update(
            {
                "Content-Security-Policy": CSP,
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Cache-Control": "no-store",
                "Cross-Origin-Resource-Policy": "same-origin",
                "X-Frame-Options": "DENY",
            }
        )
        return response

    @app.post("/api/v1/session/bootstrap")
    def bootstrap(body: Bootstrap):
        return {
            "bearer": session.exchange(body.secret),
            "expires_in_idle_seconds": 1800,
            "absolute_seconds": 28800,
            "demo": store.read_only,
        }

    @app.get("/api/v1/runs")
    def runs(limit: int = 50, offset: int = 0, q: str = ""):
        return store.list_runs(limit, offset, q)

    @app.get("/api/v1/runs/{run_id}")
    def run_detail(run_id: str):
        run = store.get(run_id)
        return {
            "run": run.model_dump(mode="json"),
            "integrity": store.integrity(run_id),
            "findings": [f.model_dump() for f in evaluate(run)],
            "demo": store.read_only,
        }

    @app.get("/api/v1/runs/{run_id}/journey")
    def journey(run_id: str):
        run = store.get(run_id)
        return {
            "run_id": run.id,
            "profile": run.profile.model_dump(mode="json"),
            "steps": [s.model_dump() for s in run.steps],
            "frames": [f.model_dump() for f in run.frames],
            "evidence": [e.model_dump() for e in run.evidence],
            "complete_states": run.complete_states,
            "limitation_codes": run.limitation_codes,
            "provenance": run.provenance,
            "pilot_context": operations.run_context(run_id),
        }

    @app.get("/api/v1/comparisons")
    def comparison(baseline: str, candidate: str):
        a, b = store.verified_get(baseline), store.verified_get(candidate)
        result = compare(a, b)
        result.findings = evaluate(b, result)
        return result.model_dump(mode="json")

    @app.get("/api/v1/evidence/{evidence_id}")
    def evidence(evidence_id: str):
        result = store.evidence(evidence_id)
        result["findings"] = [
            f.model_dump() for f in evaluate(store.get(result["run_id"])) if evidence_id in f.evidence_ids
        ]
        return result

    @app.post("/api/v1/baselines")
    def baseline(body: BaselineSelection):
        return store.baseline(body.run_id, body.reason)

    @app.get("/api/v1/runs/{run_id}/export")
    def export(run_id: str, format: str = "html"):
        raw, mime, filename = render(store.verified_get(run_id), format)
        return Response(
            raw, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    @app.get("/api/v1/operations")
    def operation_status():
        return operations.snapshot()

    @app.post("/api/v1/targets")
    def save_target(body: PilotConfig):
        return operations.save_target(body)

    @app.get("/api/v1/targets/{target_id}")
    def target_config(target_id: str):
        return operations.config(target_id)

    @app.post("/api/v1/targets/{target_id}/actions")
    def target_action(target_id: str, body: TargetAction):
        return operations.action(target_id, body.action)

    @app.post("/api/v1/notifications/{notice_id}/read")
    def read_notice(notice_id: str):
        return operations.acknowledge(notice_id)

    @app.get("/api/v1/reviews")
    def review_history(baseline: str, candidate: str):
        return operations.reviews(baseline, candidate)

    @app.post("/api/v1/reviews")
    def record_review(body: ReviewDecision):
        return operations.review(body)

    @app.get("/api/v1/reviews/export")
    def export_reviews(baseline: str, candidate: str):
        return operations.export_reviews(baseline, candidate)

    @app.get("/api/v1/operations/retention")
    def monitor_retention():
        return operations.retention_preview()

    @app.post("/api/v1/operations/retention")
    def monitor_retention_apply(body: RetentionConfirmation):
        return operations.retention_apply(body.confirmation)

    @app.get("/{path:path}")
    def static(path: str):
        if path.startswith("api/"):
            raise CEMError("NOT_FOUND", "API route not found.", 404)
        if "\\" in path or any(part in ("..", ".") for part in path.split("/")):
            raise CEMError("PATH_DENIED", "Invalid asset path.", 400)
        candidate = assets / path if path else assets / "index.html"
        if not candidate.resolve().is_relative_to(assets.resolve()):
            raise CEMError("PATH_DENIED", "Invalid asset path.", 400)
        reject_symlink_chain(candidate)
        if not candidate.is_file():
            if "." in path:
                raise CEMError("NOT_FOUND", "Asset not found.", 404)
            candidate = assets / "index.html"
        if not candidate.is_file():
            raise CEMError(
                "ASSETS_NOT_BUILT", "Compile the local frontend before starting the workbench.", 503
            )
        return FileResponse(candidate, media_type=mimetypes.guess_type(candidate.name)[0])

    return app
