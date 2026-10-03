"""Synthetic pilot configuration for OFFLINE mocks only. Never grants a real assessment."""

from datetime import datetime, timedelta, timezone
from cem.pilot.policy import PilotConfig
from cem.domain import Step


def pilot():
    now = datetime.now(timezone.utc)
    return PilotConfig(
        target_id="offline-pilot",
        label="Offline pilot fixture",
        origin="https://store.example.com",
        grant={
            "owner": "Synthetic operator",
            "assessor": "Synthetic operator",
            "origins": ["https://store.example.com", "https://cdn.example.com"],
            "issued_at": now - timedelta(seconds=1),
            "expires_at": now + timedelta(hours=1),
            "authority_confirmed": True,
            "no_payment_or_account_actions": True,
        },
        steps=[
            Step(id="catalog", action="goto", path="/", selector="main", expected_state="catalog"),
            Step(
                id="checkout",
                action="goto",
                path="/checkout",
                selector="#checkout",
                expected_state="checkout",
            ),
            Step(id="stop", action="stop", expected_state="stopped"),
        ],
    )
