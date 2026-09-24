"""Explicit synthetic examples, never a fallback for failed real data."""

from pathlib import Path
from .storage import Store
from .domain import Run, Profile, Evidence, StepResult, utc_now


def demo_store(root: Path) -> Store:
    # Separate durable namespace; no real baseline mutation allowed by the returned store.
    s = Store(root)
    if s.list_runs(limit=1)["total"] == 0:
        for variant in (0, 1):
            e = Evidence(
                kind="SCRIPT",
                step_id="checkout",
                state="checkout",
                url_display="https://shop.cem.test:8765/scripts/checkout.js",
                origin="https://shop.cem.test:8765",
                identity="a" * 64,
                reference_observed=True,
                request_observed=True,
                response_observed=True,
                body_sha256=("b" if variant else "c") * 64,
                body_size=42,
                body_representation="CDP_TEXT_UTF8_REENCODED",
                body_reason=None,
                relation="SAME_ORIGIN",
                delivery="RESPONSE_OBSERVED",
            )
            r = Run(
                label="Synthetic example " + ("candidate" if variant else "baseline"),
                fixture_id="T04" if variant else "T01",
                profile=Profile(journey_hash="0" * 64, identity_key_id="0" * 16),
                status="COMPLETED",
                ended_at=utc_now(),
                provenance="SYNTHETIC_DEMO",
                evidence=[e],
                steps=[
                    StepResult(
                        id="checkout",
                        state="checkout",
                        status="REACHED",
                        started_at=utc_now(),
                        ended_at=utc_now(),
                    )
                ],
                complete_states=["checkout"],
                limitation_codes=["AUTHORED_EXAMPLE_NOT_MEASURED"],
            )
            s.save(r, demo=True)
    return Store(root, read_only=True)
