"""Pure, strict pilot scope validation; DNS checks live at the egress boundary."""

from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import re
from typing import Literal
from urllib.parse import urlsplit, unquote
from pydantic import Field, field_validator, model_validator
from ..domain import StrictModel, Budgets, Step
from ..errors import CEMError

FORBIDDEN = re.compile(
    r"(?i)(?:order|purchase|payment|pay-now|logout|login|register|account|delete|remove|add-to-cart|submit|confirm|send-mail)"
)
HOST = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
PATH = re.compile(r"^/[A-Za-z0-9/_-]{0,159}$")


def origin(value: str) -> str:
    try:
        p = urlsplit(value)
        host = p.hostname or ""
        if (
            p.scheme != "https"
            or p.username
            or p.password
            or p.port not in (None, 443)
            or p.path not in ("", "/")
            or p.query
            or p.fragment
            or not HOST.fullmatch(host)
            or host.endswith((".local", ".localhost", ".test", ".invalid", ".internal", ".example"))
            or host in ("localhost",)
            or host.startswith("xn--")
            or ".xn--" in host
        ):
            raise ValueError()
        return "https://" + host
    except (ValueError, UnicodeError):
        raise ValueError("Use a public ASCII HTTPS hostname on port 443 without a path") from None


def public_address(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
        # Reject translation/transition ranges in addition to private and special-use destinations.
        if not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return False
        if isinstance(ip, ipaddress.IPv6Address):
            if ip.ipv4_mapped or ip.sixtofour or ip.teredo:
                return False
            if ip in ipaddress.ip_network("64:ff9b::/96") or ip in ipaddress.ip_network("64:ff9b:1::/48"):
                return False
        return True
    except ValueError:
        return False


class PilotGrant(StrictModel):
    owner: str = Field(min_length=1, max_length=120)
    assessor: str = Field(min_length=1, max_length=120)
    origins: list[str] = Field(min_length=1, max_length=8)
    issued_at: datetime
    expires_at: datetime
    purpose: Literal["AUTHORIZED_PUBLIC_STORE_OBSERVATION"] = "AUTHORIZED_PUBLIC_STORE_OBSERVATION"
    authority_confirmed: Literal[True]
    no_payment_or_account_actions: Literal[True]

    @field_validator("origins")
    @classmethod
    def origins_valid(cls, values):
        normalized = [origin(v) for v in values]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Origins must be unique")
        return normalized

    @field_validator("issued_at", "expires_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Grant timestamps require timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def bounded(self):
        seconds = (self.expires_at - self.issued_at).total_seconds()
        if not 60 <= seconds <= 8 * 3600:
            raise ValueError("Grant must last 1 minute to 8 hours")
        return self


class PilotConfig(StrictModel):
    target_id: str = Field(pattern=r"^[a-z0-9-]{1,64}$")
    label: str = Field(min_length=1, max_length=80)
    origin: str
    grant: PilotGrant
    steps: list[Step] = Field(min_length=1, max_length=12)
    cadence_minutes: int = Field(default=60, ge=15, le=1440)
    budgets: Budgets = Field(default_factory=lambda: Budgets(steps=12, run_seconds=120))
    consent: Literal["UNSET"] = "UNSET"

    @field_validator("origin")
    @classmethod
    def origin_valid(cls, value):
        return origin(value)

    @model_validator(mode="after")
    def journey_valid(self):
        if self.origin not in self.grant.origins or len(self.steps) > self.budgets.steps:
            raise ValueError("Primary origin and step budget must be authorized")
        if self.steps[0].action != "goto" or len({s.id for s in self.steps}) != len(self.steps):
            raise ValueError("Journey must start with navigation and have unique step IDs")
        stopped = False
        for step in self.steps:
            if stopped or step.action not in ("goto", "wait", "assert", "stop") or step.value is not None:
                raise ValueError("Pilot permits navigation and observation only")
            if step.action == "goto":
                if (
                    not step.path
                    or not PATH.fullmatch(step.path)
                    or "//" in step.path
                    or FORBIDDEN.search(step.path)
                ):
                    raise ValueError("Only explicit read-only paths without queries are supported")
            elif step.path is not None:
                raise ValueError("Only navigation can have a path")
            if step.action in ("goto", "wait", "assert") and not step.selector:
                raise ValueError("Observation requires a visible selector")
            if step.selector and (
                len(step.selector) > 160
                or not re.fullmatch(r"[a-zA-Z0-9_\-#\.\[\]='\" >:()]+", step.selector)
            ):
                raise ValueError("Use a bounded CSS selector without executable expressions")
            if step.expected_state not in ("catalog", "cart", "checkout", "stopped"):
                raise ValueError("Every step needs an explicit observation state")
            if (step.action == "stop") != (step.expected_state == "stopped") or (
                step.action == "stop" and step.selector
            ):
                raise ValueError(
                    "Only a stop step can have the stopped state and it cannot wait on a selector"
                )
            stopped = step.action == "stop"
        return self

    def fingerprint(self) -> str:
        # Identity excludes grant timestamps and cadence; renewal does not silently change the profile.
        values = {
            "origin": self.origin,
            "origins": sorted(self.grant.origins),
            "steps": [s.model_dump() for s in self.steps],
            "budgets": self.budgets.model_dump(),
            "consent": self.consent,
            "policy": "pilot-navigation-1",
        }
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def require_grant(config: PilotConfig, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    if not config.grant.issued_at <= now < config.grant.expires_at:
        raise CEMError("GRANT_EXPIRED", "An active time-bounded store authorization is required.", 403)


def allow_request(config: PilotConfig, url: str, method: str, *, navigation=False):
    require_grant(config)
    try:
        p = urlsplit(url)
        approved = origin(f"{p.scheme}://{p.netloc}")
        if approved not in config.grant.origins or p.username or p.password or method not in ("GET", "HEAD"):
            raise ValueError()
        if len(url) > 8192 or p.fragment or FORBIDDEN.search(unquote(p.path)):
            raise ValueError()
        if navigation and (
            approved != config.origin
            or p.query
            or p.path not in {s.path for s in config.steps if s.action == "goto"}
        ):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise CEMError(
            "PILOT_SCOPE_DENIED", "A request left the declared read-only pilot scope.", 403
        ) from None


def display_url(url: str, origins: list[str]) -> tuple[str, str]:
    try:
        p = urlsplit(url)
        approved = origin(f"{p.scheme}://{p.netloc}")
        if approved not in origins:
            return "[redacted external URL]", ""
        return approved + "/[redacted-path]" + ("?[redacted]" if p.query else ""), approved
    except (ValueError, UnicodeError):
        return "[redacted external URL]", ""
