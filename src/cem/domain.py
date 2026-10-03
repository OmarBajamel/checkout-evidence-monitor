"""Strict, bounded evidence contracts. Raw bodies and cookie values have no field."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"
COLLECTOR_VERSION = "cem-cdp-1"
RULE_VERSION = "obs-1"
MAX_IMPORT = 50 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid4().hex


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    @field_validator("started_at", "ended_at", "observed_at", check_fields=False)
    @classmethod
    def timestamp(cls, value):
        if value is not None:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                raise ValueError("Timestamp requires a timezone")
            return parsed.astimezone(timezone.utc).isoformat()
        return value

    @field_validator("limitation_codes", check_fields=False)
    @classmethod
    def bounded_codes(cls, value):
        import re

        if any(not re.fullmatch(r"[A-Z0-9_]{1,80}", code) for code in value):
            raise ValueError("Limitation codes must be bounded identifiers")
        return value


class RunStatus(StrEnum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class Budgets(StrictModel):
    steps: int = Field(default=20, ge=1, le=40)
    redirects: int = Field(default=5, ge=0, le=10)
    step_seconds: int = Field(default=30, ge=1, le=60)
    run_seconds: int = Field(default=180, ge=1, le=300)
    events: int = Field(default=500, ge=1, le=2000)
    body_bytes: Literal[2097152] = 2097152
    output_bytes: Literal[52428800] = 52428800
    cdp_sessions: int = Field(default=8, ge=1, le=8)


class Profile(StrictModel):
    target_id: str = Field(default="synthetic-storefront", pattern=r"^[a-z0-9-]{1,64}$")
    fixture_version: str = "fixture-1"
    journey_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    browser_version: str = "153.0.8010.12"
    browser_revision: str = "1243"
    viewport: tuple[int, int] = (1440, 900)
    locale: Literal["en-US"] = "en-US"
    consent: Literal["DECLINED", "ACCEPTED", "UNSET"] = "DECLINED"
    authentication: Literal["SYNTHETIC_GUEST", "PUBLIC_GUEST"] = "SYNTHETIC_GUEST"
    service_workers: Literal["block", "allow"] = "block"
    cache: Literal["disabled-fresh"] = "disabled-fresh"
    collector_version: str = COLLECTOR_VERSION
    rule_version: str = RULE_VERSION
    identity_key_id: str = Field(pattern=r"^[a-f0-9]{16}$")
    mode: Literal["HTTP", "PAGE", "JOURNEY"] = "JOURNEY"
    budgets: Budgets = Field(default_factory=Budgets)


class Grant(StrictModel):
    owner: str = Field(min_length=1, max_length=120)
    assessor: str = Field(min_length=1, max_length=120)
    profile: Literal["LAB"] = "LAB"
    fixture_id: str = Field(pattern=r"^T(0[1-9]|1[0-9]|2[0-4])$")
    origins: list[str] = Field(min_length=1, max_length=4)
    actions: list[Literal["goto", "click", "fill", "select", "wait", "assert", "stop"]] = Field(
        min_length=1, max_length=7
    )
    expires_at: datetime
    issued_at: datetime
    purpose: Literal["SYNTHETIC_LOCAL_EVALUATION"] = "SYNTHETIC_LOCAL_EVALUATION"

    @field_validator("expires_at", "issued_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Grant dates need a timezone")
        return value


class Step(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9-]{1,40}$")
    action: Literal["goto", "click", "fill", "select", "wait", "assert", "stop"]
    selector: str | None = Field(default=None, max_length=160)
    path: str | None = Field(default=None, max_length=160)
    value: str | None = Field(default=None, max_length=100)
    expected_state: Literal["catalog", "cart", "checkout", "stopped"] | None = None


class Job(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    profile: Literal["LAB"] = "LAB"
    grant: Grant
    steps: list[Step] = Field(min_length=1, max_length=40)
    budgets: Budgets = Field(default_factory=Budgets)
    consent: Literal["DECLINED", "ACCEPTED", "UNSET"] = "DECLINED"
    service_workers: Literal["block", "allow"] = "block"
    arm: Literal["HTTP", "PAGE", "JOURNEY"] = "JOURNEY"


class StepResult(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9-]{1,40}$")
    state: str = Field(max_length=40)
    status: Literal["REACHED", "BLOCKED", "NOT_RUN"]
    reason: str | None = Field(default=None, max_length=80)
    started_at: str
    ended_at: str


class FrameRecord(StrictModel):
    id: str = Field(max_length=80)
    origin: str = Field(max_length=250)
    parent_id: str | None = Field(default=None, max_length=80)
    visibility: Literal["METADATA", "NETWORK", "PARTIAL"] = "METADATA"


class CookieRecord(StrictModel):
    name: str = Field(max_length=80)
    domain: str = Field(max_length=250)
    path: str = Field(max_length=250)
    secure: bool
    http_only: bool
    same_site: str = Field(max_length=20)
    role: Literal["CONFIGURED_SESSION", "UNKNOWN"] = "UNKNOWN"


class Evidence(StrictModel):
    id: str = Field(default_factory=new_id, pattern=r"^[a-f0-9]{32}$")
    kind: Literal["DOCUMENT", "SCRIPT", "REQUEST", "INLINE_METADATA", "LIMITATION"]
    observed_at: str = Field(default_factory=utc_now)
    step_id: str = Field(max_length=40)
    state: str = Field(max_length=40)
    frame_id: str = Field(default="main", max_length=80)
    origin: str = Field(default="", max_length=250)
    url_display: str = Field(default="", max_length=2048)
    identity: str = Field(default="", pattern=r"^(?:[a-f0-9]{64})?$")
    reference_observed: bool = False
    request_observed: bool = False
    response_observed: bool = False
    execution_evidence: Literal["NOT_OBSERVED"] = "NOT_OBSERVED"
    http_status: int | None = Field(default=None, ge=100, le=599)
    method: str = Field(default="GET", max_length=12)
    headers: dict[str, str] = Field(default_factory=dict, max_length=20)
    csp: list[dict] = Field(default_factory=list, max_length=20)
    tls_validation: Literal["VALIDATED", "FAILED", "NOT_APPLICABLE", "UNKNOWN"] = "UNKNOWN"
    redirected_from: str | None = Field(default=None, max_length=2048)
    from_cache: bool = False
    from_service_worker: bool = False
    body_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    body_representation: Literal["CDP_BASE64_DECODED", "CDP_TEXT_UTF8_REENCODED"] | None = None
    body_size: int | None = Field(default=None, ge=0, le=2097152)
    body_reason: str | None = Field(default="NOT_CAPTURED", max_length=80)
    content_type: str = Field(default="", max_length=120)
    content_encoding: str = Field(default="", max_length=80)
    integrity_metadata: str | None = Field(default=None, max_length=512)
    relation: Literal["SAME_ORIGIN", "CROSS_ORIGIN", "UNKNOWN"] = "UNKNOWN"
    delivery: Literal["ATTEMPTED", "RESPONSE_OBSERVED", "FAILED", "UNKNOWN"] = "UNKNOWN"
    limitation_codes: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def hash_needs_representation(self):
        if self.body_sha256 and (self.body_representation is None or self.body_size is None):
            raise ValueError("Body hash requires representation and byte count")
        return self


class Run(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    id: str = Field(default_factory=new_id, pattern=r"^[a-f0-9]{32}$")
    label: str = Field(max_length=100)
    fixture_id: str = Field(pattern=r"^(T(0[1-9]|1[0-9]|2[0-4])|PILOT)$")
    profile: Profile
    grant: Grant | None = None
    journey: list[Step] = Field(default_factory=list, max_length=40)
    started_at: str = Field(default_factory=utc_now)
    ended_at: str | None = None
    status: RunStatus = RunStatus.PARTIAL
    provenance: Literal["COLLECTED_LAB", "COLLECTED_PILOT", "DECLARED_IMPORT", "SYNTHETIC_DEMO"] = (
        "DECLARED_IMPORT"
    )
    steps: list[StepResult] = Field(default_factory=list, max_length=40)
    frames: list[FrameRecord] = Field(default_factory=list, max_length=100)
    cookies: list[CookieRecord] = Field(default_factory=list, max_length=100)
    evidence: list[Evidence] = Field(default_factory=list, max_length=2000)
    limitation_codes: list[str] = Field(default_factory=list, max_length=50)
    complete_states: list[str] = Field(default_factory=list, max_length=40)
    event_count: int = Field(default=0, ge=0)
    elapsed_ms: int = Field(default=0, ge=0)
    sanitized_artifact_sha256: str | None = None


class Finding(StrictModel):
    rule_version: Literal["obs-1"] = RULE_VERSION
    id: str = Field(default_factory=new_id)
    rule_ids: list[str]
    title: str
    condition: Literal["MATCH", "NO_MATCH", "NOT_RUN", "INCONCLUSIVE"]
    applicability: Literal["APPLICABLE", "NOT_APPLICABLE", "UNKNOWN"]
    evidence_sufficiency: Literal["SUFFICIENT", "PARTIAL", "MISSING"]
    confidence: Literal["HIGH", "LIMITED", "UNKNOWN"]
    severity: Literal["INFO", "REVIEW_NEEDED", "ERROR"]
    reason_codes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    interpretation: str
    suggested_owner: str = "Security reviewer"
    mappings: list[dict[str, str]] = Field(default_factory=list)


class Change(StrictModel):
    category: Literal["SCRIPT", "HEADERS", "COOKIE"] = "SCRIPT"
    kind: Literal["ADDED", "CHANGED", "NOT_OBSERVED", "AMBIGUOUS", "UNOBSERVABLE"]
    identity: str
    url_display: str
    state: str
    baseline_evidence_id: str | None = None
    candidate_evidence_id: str | None = None
    reason: str
    new_origin: bool = False


class Comparison(StrictModel):
    baseline_id: str
    candidate_id: str
    eligibility: Literal["COMPARABLE", "INCOMPATIBLE_PROFILE"]
    mismatch_fields: list[str] = Field(default_factory=list)
    changes: list[Change] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
