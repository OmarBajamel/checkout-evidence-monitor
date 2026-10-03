"""Authored for the next OFFLINE verification. No remote connections or Docker launches."""

import asyncio
from datetime import timedelta
import json
import socket
import pytest
from pydantic import ValidationError
from cem.errors import CEMError
from cem.pilot.policy import PilotConfig, allow_request, origin, public_address, require_grant
from cem.pilot.proxy import resolve_public, Relay
from cem.phase import require_runtime, source_snapshot
from cem.privacy import sanitize_run
from cem.storage import Store
from tests.helpers import run, script
from tests.pilot_helpers import pilot


@pytest.mark.parametrize(
    "url",
    [
        "http://store.example.com",
        "https://127.0.0.1",
        "https://[::1]",
        "https://localhost",
        "https://store.example.com:444",
        "https://user:password@store.example.com",
        "https://store.example.com/checkout",
        "https://store.example.com?x=1",
        "https://store.example.com.",
        "https://host.internal",
    ],
)
def test_pilot_origin_rejects_ambiguous_or_nonpublic_configuration(url):
    with pytest.raises(ValueError):
        origin(url)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "169.254.169.254",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.0.1",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:8.8.8.8",
        "64:ff9b::808:808",
        "2002:0808:0808::1",
    ],
)
def test_pilot_egress_address_rejection(address):
    assert not public_address(address)


def test_pilot_public_addresses_are_eligible_but_never_dialed():
    assert public_address("8.8.8.8")
    assert public_address("2606:4700:4700::1111")


@pytest.mark.parametrize(
    "url,method,navigation",
    [
        ("https://store.example.com/checkout", "POST", True),
        ("https://store.example.com/orders", "GET", False),
        ("https://store.example.com/%6f%72ders", "GET", False),
        ("https://store.example.com/checkout?customer=1", "GET", True),
        ("https://cdn.example.com/frame", "GET", True),
        ("https://unlisted.example.com/a.js", "GET", False),
        ("file:///etc/passwd", "GET", False),
    ],
)
def test_pilot_request_scope_is_fail_closed(url, method, navigation):
    with pytest.raises(CEMError):
        allow_request(pilot(), url, method, navigation=navigation)


def test_pilot_navigation_and_approved_resource_queries_are_distinct():
    config = pilot()
    allow_request(config, config.origin + "/checkout", "GET", navigation=True)
    allow_request(config, "https://cdn.example.com/bundle.js?v=build", "GET")
    with pytest.raises(CEMError):
        require_grant(config, config.grant.expires_at)


def test_pilot_renewal_preserves_comparability_but_scope_change_does_not():
    config = pilot()
    raw = config.model_dump()
    raw["grant"]["issued_at"] += timedelta(seconds=10)
    raw["grant"]["expires_at"] += timedelta(seconds=10)
    raw["cadence_minutes"] = 120
    assert PilotConfig.model_validate(raw).fingerprint() == config.fingerprint()
    raw["steps"][1]["selector"] = "#different-state"
    assert PilotConfig.model_validate(raw).fingerprint() != config.fingerprint()


def test_pilot_forbids_input_actions_and_unconfirmed_state():
    raw = pilot().model_dump()
    raw["steps"][1]["action"] = "fill"
    raw["steps"][1]["value"] = "secret"
    with pytest.raises(ValidationError):
        PilotConfig.model_validate(raw)
    raw = pilot().model_dump()
    raw["steps"][0]["selector"] = None
    with pytest.raises(ValidationError):
        PilotConfig.model_validate(raw)


@pytest.mark.asyncio
async def test_dns_rebinding_mixed_answers_rejected_before_socket(monkeypatch):
    loop = asyncio.get_running_loop()

    async def answers(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]

    monkeypatch.setattr(loop, "getaddrinfo", answers)
    with pytest.raises(CEMError, match="exclusively"):
        await resolve_public("store.example.com")


class Writer:
    def __init__(self):
        self.output = b""
        self.closed = False

    def write(self, value):
        self.output += value

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


@pytest.mark.asyncio
async def test_proxy_needs_auth_and_refuses_unlisted_authority_before_dns(monkeypatch):
    async def forbidden(*a, **k):
        pytest.fail("No socket or DNS work may follow a rejected CONNECT")

    monkeypatch.setattr("cem.pilot.proxy.resolve_public", forbidden)
    for request in (
        b"CONNECT store.example.com:443 HTTP/1.1\r\nHost: store.example.com\r\n\r\n",
        b"CONNECT evil.example.com:443 HTTP/1.1\r\n\r\n",
    ):
        reader = asyncio.StreamReader()
        reader.feed_data(request)
        reader.feed_eof()
        writer = Writer()
        relay = Relay(pilot(), "a" * 64)
        await relay.handle(reader, writer)
        assert writer.closed and relay.active == 0


def test_pilot_runtime_cannot_reuse_offline_lab_session(tmp_path, monkeypatch):
    session = tmp_path / "session.json"
    session.write_text(
        json.dumps(
            {
                "instruction": "TEST APPROVED",
                "profile": "OFFLINE_AND_LAB",
                "expires_at": pilot().grant.expires_at.isoformat(),
                "source_snapshot": source_snapshot(tmp_path),
            }
        )
    )
    monkeypatch.setenv("CEM_TEST_SESSION", str(session))
    require_runtime(tmp_path, profile="OFFLINE")
    with pytest.raises(CEMError):
        require_runtime(tmp_path, profile="PILOT")


def test_pilot_import_cannot_claim_collected_provenance(tmp_path):
    record = run(script())
    record.fixture_id = "PILOT"
    record.provenance = "COLLECTED_PILOT"
    record.evidence[0].url_display = "https://store.example.com/customer/123?token=secret"
    record.evidence[0].origin = "https://store.example.com"
    stored = Store(tmp_path / "data").save(record)
    assert stored.provenance == "DECLARED_IMPORT"
    assert "store.example.com" not in stored.evidence[0].url_display


def test_pilot_sanitization_masks_paths_nonces_and_arbitrary_integrity():
    record = run(script())
    record.fixture_id = "PILOT"
    e = record.evidence[0]
    e.url_display = "https://store.example.com/customer/123?private=secret"
    e.headers = {
        "content-security-policy": "script-src 'self' 'nonce-secret-value' * https://store.example.com/private/path?x=secret"
    }
    e.integrity_metadata = "private-value"
    sanitized = sanitize_run(record, pilot_origins=["https://store.example.com"])
    raw = sanitized.model_dump_json()
    assert "secret-value" not in raw and "customer/123" not in raw and "private/path" not in raw
    assert (
        sanitized.evidence[0]
        .headers["content-security-policy"]
        .startswith("script-src 'self' 'nonce-[redacted]' *")
    )
    assert (
        sanitize_run(sanitized, pilot_origins=["https://store.example.com"]).model_dump()
        == sanitized.model_dump()
    )
