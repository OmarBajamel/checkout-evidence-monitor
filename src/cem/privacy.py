"""Sanitize at the capture/import boundary before logging or persistence."""

import hashlib
import hmac
import json
import re
from urllib.parse import urlsplit
from .authorization import HOSTS, ORIGINS, SELECTORS, PATHS
from .domain import Run, Evidence

HEADERS = frozenset(
    {
        "content-security-policy",
        "content-security-policy-report-only",
        "strict-transport-security",
        "x-content-type-options",
        "referrer-policy",
        "content-type",
        "content-encoding",
        "x-frame-options",
    }
)
SECRET = re.compile(
    r"(?i)(bearer\s+\S+|(?:token|secret|password|session|key)\s*[:=]\s*[^;\s&]+|[\w.+-]+@[\w.-]+\.[a-z]{2,})"
)
SAFE_PATH = re.compile(
    r"^/(?:scripts/[a-z-]+\.js|sw\.js|cart|checkout|catalog|frame|redirect|canary|favicon\.ico)?$"
)


def safe_text(value: str, limit=512) -> str:
    return SECRET.sub("[redacted]", re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", str(value)))[:limit]


def safe_url(url: str) -> tuple[str, str]:
    try:
        p = urlsplit(url)
        host = p.hostname or ""
        port = f":{p.port}" if p.port else ""
        # Arbitrary imported host/path content is not trusted as safe context.
        if p.scheme not in ("http", "https") or host not in HOSTS:
            return "[redacted external URL]", ""
        origin = f"{p.scheme}://{host}{port}"
        path = p.path if SAFE_PATH.fullmatch(p.path) else "/[redacted-path]"
        return origin + path + ("?[redacted]" if p.query else ""), origin
    except ValueError:
        return "[invalid URL]", ""


def identity(url: str, frame: str, state: str, key: bytes) -> str:
    # Include exact sensitive representation in a keyed digest, never on disk.
    return hmac.new(
        key, json.dumps([url, frame, state], ensure_ascii=True).encode(), hashlib.sha256
    ).hexdigest()


def headers(values: dict) -> dict[str, str]:
    return {k.lower(): safe_text(v, 2048) for k, v in values.items() if k.lower() in HEADERS}


def csp_inventory(values: dict) -> list[dict]:
    policies = []
    for key in ("content-security-policy", "content-security-policy-report-only"):
        for raw in values.get(key, "").splitlines():
            directives = {}
            unsupported = False
            duplicates = []
            for part in raw.split(";")[:40]:
                tokens = part.strip().split()
                if not tokens:
                    continue
                name = tokens[0].lower()
                if not re.fullmatch(r"[a-z][a-z0-9-]*", name) or "," in part:
                    unsupported = True
                    continue
                if name in directives:
                    duplicates.append(name)
                else:
                    directives[name] = tokens[1:40]
            policies.append(
                {
                    "mode": "REPORT_ONLY" if key.endswith("report-only") else "ENFORCED_HEADER",
                    "directives": directives,
                    "duplicate_directives": duplicates,
                    "parse_status": "UNSUPPORTED_OR_MALFORMED" if unsupported else "TOKENIZED_NOT_VALIDATED",
                    "field_boundary": "CDP_OR_HTTP_HEADER_REPRESENTATION",
                }
            )
    return policies[:20]


def sanitize_evidence(e: Evidence) -> Evidence:
    d = e.model_dump()
    d["url_display"], d["origin"] = safe_url(e.url_display)
    if e.redirected_from:
        d["redirected_from"] = safe_url(e.redirected_from)[0]
    d["headers"] = headers(e.headers)
    d["csp"] = csp_inventory(d["headers"])
    d["content_type"] = safe_text(e.content_type, 120)
    d["content_encoding"] = safe_text(e.content_encoding, 80)
    d["integrity_metadata"] = safe_text(e.integrity_metadata, 512) if e.integrity_metadata else None
    d["body_reason"] = safe_text(e.body_reason, 80) if e.body_reason else None
    d["method"] = e.method if e.method in ("GET", "HEAD", "POST", "OPTIONS") else "OTHER"
    for f in ("state", "step_id", "frame_id"):
        d[f] = safe_text(d[f], 40 if f != "frame_id" else 80)
    return Evidence.model_validate(d)


def sanitize_run(run: Run) -> Run:
    d = run.model_dump(mode="json")
    d["label"] = safe_text(run.label, 100)
    d["evidence"] = [sanitize_evidence(e).model_dump(mode="json") for e in run.evidence]
    for step in d["journey"]:
        step["value"] = "[redacted]" if step["value"] is not None else None
        step["selector"] = step["selector"] if step["selector"] in SELECTORS else None
        step["path"] = step["path"] if step["path"] in PATHS else None
    for step in d["steps"]:
        step["state"] = safe_text(step["state"], 40)
        step["reason"] = safe_text(step["reason"], 80) if step["reason"] else None
    d["complete_states"] = [
        s for s in d["complete_states"] if s in ("catalog", "cart", "checkout", "stopped")
    ]
    if run.status != "COMPLETED" or run.limitation_codes:
        d["complete_states"] = []
    for field in (
        "fixture_version",
        "browser_version",
        "browser_revision",
        "collector_version",
        "rule_version",
    ):
        d["profile"][field] = safe_text(d["profile"][field], 80)
    for c in d["cookies"]:
        c["name"] = safe_text(c["name"], 80)
        c["domain"] = c["domain"] if c["domain"].lstrip(".") in HOSTS else "[redacted]"
        c["path"] = c["path"] if SAFE_PATH.fullmatch(c["path"]) else "/[redacted-path]"
    for f in d["frames"]:
        f["origin"] = safe_url(f["origin"] + "/")[1] if f["origin"] else ""
        f["id"] = safe_text(f["id"], 80)
        f["parent_id"] = safe_text(f["parent_id"], 80) if f["parent_id"] else None
    if d["grant"]:
        d["grant"]["owner"] = "Local operator"
        d["grant"]["assessor"] = "Local operator"
        if not set(d["grant"]["origins"]).issubset(ORIGINS):
            d["grant"] = None
    return Run.model_validate(d)
