"""HTTP baseline follows declared redirects only and never executes JavaScript."""

from html.parser import HTMLParser
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, HTTPSHandler, Request
from urllib.parse import urljoin
from urllib.error import HTTPError
import ssl
import time
from ..authorization import validate_job, allow_request
from ..domain import Evidence, StepResult, RunStatus, utc_now
from ..privacy import safe_url, headers, identity
from .journey import make_run


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and len(self.refs) < 2000:
            a = dict(attrs)
            self.refs.append((a.get("src"), a.get("integrity")))


def collect_http(job, key, ca_path):
    validate_job(job)
    run = make_run(job, key)
    start = time.monotonic()
    base = next(x for x in job.grant.origins if "shop.cem.test" in x)
    url = base + job.steps[0].path + f"?scenario={job.grant.fixture_id}"
    opener = build_opener(
        NoRedirect(), ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context(cafile=str(ca_path)))
    )
    try:
        for _ in range(job.budgets.redirects + 1):
            validate_job(job)
            allow_request(url, "GET", job.grant.origins)
            remaining = job.budgets.run_seconds - (time.monotonic() - start)
            if remaining <= 0:
                raise TimeoutError()
            try:
                response = opener.open(
                    Request(url, method="GET"), timeout=min(job.budgets.step_seconds, remaining)
                )
            except HTTPError as error:
                if error.code in (301, 302, 303, 307, 308):
                    url = urljoin(url, error.headers.get("Location", ""))
                    error.close()
                    continue
                raise
            with response:
                raw = response.read(2097153)
                display, origin = safe_url(url)
                if len(raw) > 2097152:
                    run.limitation_codes.append("DOCUMENT_CAP")
                    raw = b""
                doc = Evidence(
                    kind="DOCUMENT",
                    step_id=job.steps[0].id,
                    state="catalog",
                    url_display=display,
                    origin=origin,
                    identity=identity(url, "main", "catalog", key),
                    request_observed=True,
                    response_observed=True,
                    http_status=response.status,
                    headers=headers({k: "\n".join(response.headers.get_all(k)) for k in response.headers}),
                    delivery="RESPONSE_OBSERVED",
                    tls_validation="VALIDATED" if url.startswith("https://") else "NOT_APPLICABLE",
                )
                run.evidence.append(doc)
                p = Scripts()
                p.feed(raw.decode("utf-8", "replace"))
                for src, sri in p.refs[: job.budgets.events - 1]:
                    absolute = urljoin(url, src) if src else ""
                    display, origin = safe_url(absolute) if src else ("", "")
                    run.evidence.append(
                        Evidence(
                            kind="SCRIPT" if src else "INLINE_METADATA",
                            step_id=job.steps[0].id,
                            state="catalog",
                            origin=origin,
                            url_display=display,
                            identity=identity(absolute, "main", "catalog", key) if src else "",
                            reference_observed=True,
                            integrity_metadata=sri,
                            body_reason="HTTP_ARM_REFERENCE_ONLY",
                        )
                    )
                run.steps.append(
                    StepResult(
                        id=job.steps[0].id,
                        state="catalog",
                        status="REACHED",
                        started_at=run.started_at,
                        ended_at=utc_now(),
                    )
                )
                run.complete_states = ["catalog"] if not run.limitation_codes else []
                break
        else:
            run.limitation_codes.append("REDIRECT_CAP")
        run.status = RunStatus.PARTIAL if run.limitation_codes else RunStatus.COMPLETED
    except Exception:
        run.status = RunStatus.FAILED
        run.limitation_codes.append("HTTP_COLLECTION_FAILED")
    for s in job.steps[1:]:
        run.steps.append(
            StepResult(
                id=s.id,
                state=s.expected_state or "unknown",
                status="NOT_RUN",
                reason="HTTP_ARM_NO_JAVASCRIPT",
                started_at=utc_now(),
                ended_at=utc_now(),
            )
        )
    run.event_count = 1
    run.elapsed_ms = int((time.monotonic() - start) * 1000)
    run.ended_at = utc_now()
    return run
