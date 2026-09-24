from datetime import datetime, timedelta, timezone
import json
import pytest
from cem.authorization import allow_request, canonical_origin, validate_job
from cem.config import parse_json, load_job
from cem.domain import Step
from cem.errors import CEMError
from cem.phase import require_runtime
from cem.reports import render, cell
from cem.storage import Store
from tests.helpers import run, script, job


def test_T12_redirect_needs_destination_grant():
    with pytest.raises(CEMError):
        allow_request("https://pay.cem.test:8766/frame", "GET", ["https://shop.cem.test:8765"])
    allow_request("https://pay.cem.test:8766/frame", "GET", ["https://pay.cem.test:8766"])


def test_T16_redaction_precedes_every_artifact(tmp_path):
    e = script()
    e.url_display += "?token=synthetic-secret"
    e.headers = {
        "authorization": "Bearer dummy-secret",
        "set-cookie": "private=value",
        "content-security-policy": "script-src https://example.test/?token=dummy",
    }
    record = run(e)
    record.journey = [
        Step(id="fill", action="fill", selector="[data-cem='email']", value="person@example.com")
    ]
    stored = Store(tmp_path / "data").save(record)
    for format in ("json", "html", "csv"):
        raw = render(stored, format)[0]
        assert (
            b"synthetic-secret" not in raw and b"dummy-secret" not in raw and b"person@example.com" not in raw
        )
    assert b"person@example.com" not in next((tmp_path / "data/records").glob("*.json")).read_bytes()


@pytest.mark.parametrize(
    "url", ["http://169.254.169.254/latest/meta-data", "http://127.0.0.1:8765/", "http://10.0.0.1/"]
)
def test_T17_private_redirect_denied_without_network(url, monkeypatch):
    import socket

    monkeypatch.setattr(socket, "getaddrinfo", lambda *a: pytest.fail("DNS must not run"))
    with pytest.raises(CEMError):
        canonical_origin(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://[::1]:8765/",
        "https://SHOP.cem.test:8765/",
        "https://shop.cem.test.:8765/",
        "https://shop.cem.test:8765@evil.test/",
        "https://shop.cem.test:8765\\@evil.test/",
    ],
)
def test_T18_ambiguous_authorities_refused(url):
    with pytest.raises(CEMError):
        canonical_origin(url)


def test_T21_html_and_csv_injection_are_inert():
    b = run(script())
    b.label = "<img src=x onerror=alert(1)>"
    html = render(b, "html")[0].decode()
    assert "<img src=x" not in html and "&lt;img" in html
    for value in ("=1+1", "+cmd", "-cmd", "@SUM(A1)", "\t=1"):
        assert cell(value).startswith("'")


def test_T23_order_selector_and_post_denied():
    j = job()
    j.steps[1].selector = "[data-cem='forbidden-order']"
    with pytest.raises(CEMError):
        validate_job(j)
    with pytest.raises(CEMError):
        allow_request("https://shop.cem.test:8765/checkout", "POST", j.grant.origins)


def test_T24_expired_public_json_and_phase_refusals(tmp_path, monkeypatch):
    j = job()
    j.grant.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(CEMError):
        validate_job(j)
    p = tmp_path / "job.json"
    p.write_text(json.dumps({"profile": "AUTHORIZED_PUBLIC"}))
    with pytest.raises(CEMError):
        load_job(p)
    with pytest.raises(CEMError):
        parse_json(b'{"a":1,"a":2}')
    monkeypatch.delenv("CEM_TEST_SESSION", raising=False)
    with pytest.raises(CEMError):
        require_runtime(tmp_path)


def test_T34_changed_snapshot_and_absent_permission_deny(tmp_path, monkeypatch):
    p = tmp_path / "grant.json"
    p.write_text(
        json.dumps(
            {
                "instruction": "TEST APPROVED",
                "profile": "OFFLINE",
                "source_snapshot": "0" * 64,
                "expires_at": "2999-01-01T00:00:00+00:00",
            }
        )
    )
    monkeypatch.setenv("CEM_TEST_SESSION", str(p))
    with pytest.raises(CEMError):
        require_runtime(tmp_path)
