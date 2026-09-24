import hashlib
from datetime import datetime, timedelta, timezone
from cem.domain import Run, Profile, Evidence, Job, Grant, Step, StepResult, utc_now
from cem.privacy import identity

KEY = b"synthetic-test-identity-key-only!!"


def script(
    name="checkout", body=b"window.synthetic=true;", state="checkout", origin="https://shop.cem.test:8765"
):
    url = origin + "/scripts/" + name + ".js"
    return Evidence(
        kind="SCRIPT",
        step_id=state,
        state=state,
        url_display=url,
        origin=origin,
        identity=identity(url, "main", state, KEY),
        request_observed=True,
        response_observed=True,
        reference_observed=True,
        body_sha256=hashlib.sha256(body).hexdigest(),
        body_size=len(body),
        body_representation="CDP_TEXT_UTF8_REENCODED",
        body_reason=None,
        delivery="RESPONSE_OBSERVED",
    )


def run(*evidence):
    return Run(
        label="Synthetic unit record",
        fixture_id="T01",
        profile=Profile(journey_hash="a" * 64, identity_key_id="b" * 16),
        status="COMPLETED",
        complete_states=["catalog", "cart", "checkout"],
        evidence=list(evidence),
        steps=[
            StepResult(id=s, state=s, status="REACHED", started_at=utc_now(), ended_at=utc_now())
            for s in ("catalog", "cart", "checkout")
        ],
    )


def job(scenario="T01", arm="JOURNEY"):
    now = datetime.now(timezone.utc)
    return Job(
        grant=Grant(
            owner="Synthetic operator",
            assessor="Synthetic operator",
            fixture_id=scenario,
            origins=["https://shop.cem.test:8765", "https://pay.cem.test:8766"],
            actions=["goto", "click", "fill", "select", "wait", "assert", "stop"],
            issued_at=now - timedelta(seconds=5),
            expires_at=now + timedelta(hours=1),
        ),
        steps=[
            Step(id="catalog", action="goto", path="/", expected_state="catalog"),
            Step(id="cart", action="click", selector="[data-cem='cart']", expected_state="cart"),
            Step(id="checkout", action="click", selector="[data-cem='checkout']", expected_state="checkout"),
            Step(id="stop", action="stop", expected_state="stopped"),
        ],
        arm=arm,
    )
