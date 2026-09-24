"""LAB is exact synthetic scope, never a public scanner."""

from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
import re
from .domain import Job
from .errors import CEMError

HOSTS = frozenset({"shop.cem.test", "pay.cem.test"})
ORIGINS = frozenset(
    {
        f"{scheme}://{host}:{port}"
        for scheme in ("http", "https")
        for host, port in (("shop.cem.test", 8765), ("pay.cem.test", 8766))
    }
)
PATHS = frozenset(
    {
        "/",
        "/cart",
        "/checkout",
        "/catalog",
        "/scripts/base.js",
        "/scripts/checkout.js",
        "/scripts/extra.js",
        "/scripts/dynamic.js",
        "/scripts/large.js",
        "/scripts/delayed.js",
        "/frame",
        "/scripts/provider.js",
        "/redirect",
        "/sw.js",
        "/scripts/sw-only.js",
        "/canary",
        "/favicon.ico",
        "/secret-path/[redacted]",
    }
)
SELECTORS = frozenset(
    {
        "[data-cem='cart']",
        "[data-cem='checkout']",
        "[data-cem='email']",
        "[data-cem='country']",
        "[data-cem='consent']",
        "[data-state='checkout']",
        "[data-state='cart']",
        "[data-state='catalog']",
    }
)
VALUES = frozenset({"synthetic@example.test", "DE", "DECLINED", "ACCEPTED"})
FORBIDDEN = re.compile(r"(order|submit|purchase|pay-now|account|send-mail)", re.I)


def canonical_origin(url: str) -> str:
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url) or "\\" in url:
        raise CEMError("SCOPE_DENIED", "The URL is outside the synthetic scope.")
    try:
        p = urlsplit(url)
        if (
            p.scheme not in ("http", "https")
            or p.username
            or p.password
            or p.fragment
            or p.hostname not in HOSTS
        ):
            raise ValueError()
        # Exact authority spelling blocks numeric aliases, IPv6, trailing dots and encoded host ambiguity.
        origin = f"{p.scheme}://{p.hostname}:{p.port}"
        if p.netloc != f"{p.hostname}:{p.port}" or origin not in ORIGINS:
            raise ValueError()
        return origin
    except ValueError:
        raise CEMError("SCOPE_DENIED", "The URL is outside the synthetic scope.") from None


def allow_request(url: str, method: str, granted_origins: list[str]):
    origin = canonical_origin(url)
    p = urlsplit(url)
    if origin not in granted_origins or method != "GET" or p.path not in PATHS or FORBIDDEN.search(p.path):
        raise CEMError("ACTION_DENIED", "The request is not an approved synthetic action.")
    # Query values never choose a destination or executable code.
    if p.query and not re.fullmatch(r"(scenario=T(?:0[1-9]|1[0-9]|2[0-4])|dummy=synthetic-secret)", p.query):
        raise CEMError("ACTION_DENIED", "Only fixture query values are allowed.")


def validate_job(job: Job, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    g = job.grant
    if g.issued_at > now or g.expires_at <= now or g.expires_at - g.issued_at > timedelta(hours=8):
        raise CEMError("AUTH_SCOPE_EXPIRED", "The LAB grant is missing, future-dated or expired.")
    if not set(g.origins).issubset(ORIGINS) or not g.origins:
        raise CEMError("SCOPE_DENIED", "Grant origins must exactly name shipped fixtures.")
    if len(job.steps) > job.budgets.steps:
        raise CEMError("ARTIFACT_LIMIT", "Journey exceeds the step budget.")
    if len({s.id for s in job.steps}) != len(job.steps):
        raise CEMError("INVALID_INPUT", "Journey step IDs must be unique.")
    for s in job.steps:
        if s.action not in g.actions or s.selector and s.selector not in SELECTORS:
            raise CEMError("ACTION_DENIED", "Journey contains an unapproved selector or action.")
        if s.action == "goto":
            if s.path not in ("/", "/cart", "/checkout", "/redirect"):
                raise CEMError("ACTION_DENIED", "Navigation path is not allowed.")
        elif s.action in ("click", "fill", "select", "wait", "assert") and not s.selector:
            raise CEMError("INVALID_INPUT", "This action requires a declared selector.")
        if s.action in ("fill", "select") and s.value not in VALUES:
            raise CEMError("ACTION_DENIED", "Only declared synthetic values are allowed.")
