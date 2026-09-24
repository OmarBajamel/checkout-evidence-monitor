import asyncio
import copy
import pytest
from cem.comparison import compare
from cem.rules import evaluate
from cem.domain import Evidence, CookieRecord, FrameRecord
from cem.privacy import sanitize_run
from cem.collector.cdp import Capture
from tests.helpers import run, script, KEY


def test_T01_identical_bodies_are_not_changes():
    a, b = run(script()), run(script())
    assert compare(a, b).eligibility == "COMPARABLE"
    assert compare(a, b).changes == []


def test_T02_added_script_needs_complete_window():
    result = compare(run(script()), run(script(), script("extra")))
    assert [(c.kind, c.state) for c in result.changes] == [("ADDED", "checkout")]
    assert result.changes[0].reason == "NEWLY_OBSERVED_NOT_MALICIOUS"


def test_T03_origin_and_resource_are_grouped():
    a, b = run(script()), run(script(), script("provider", origin="https://pay.cem.test:8766"))
    result = compare(a, b)
    findings = evaluate(b, result)
    assert result.changes[0].new_origin
    assert any(set(f.rule_ids) == {"OBS-005", "OBS-007", "OBS-008"} for f in findings)


def test_T04_changed_bytes_keep_representation():
    result = compare(run(script()), run(script(body=b"changed")))
    assert result.changes[0].kind == "CHANGED"
    assert result.changes[0].reason == "CONTENT_DIFFERS_INTENT_UNKNOWN"


def test_T05_absence_requires_complete_candidate_window():
    assert compare(run(script()), run()).changes[0].kind == "NOT_OBSERVED"


def test_T06_unreached_checkout_never_means_removal():
    a, b = run(script()), run()
    b.complete_states = ["catalog"]
    b.status = "PARTIAL"
    b.limitation_codes = ["STEP_TIMEOUT"]
    result = compare(a, b)
    assert result.changes[0].kind == "UNOBSERVABLE"
    assert any(f.condition == "INCONCLUSIVE" and "OBS-005" in f.rule_ids for f in evaluate(b, result))


@pytest.mark.asyncio
async def test_T07_delayed_same_session_body_and_unavailable_reason():
    record = run()
    capture = Capture(record, KEY)

    class Session:
        calls = []

        async def send(self, method, args):
            self.calls.append(method)
            await asyncio.sleep(0.01)
            return {"body": "synthetic", "base64Encoded": False}

    capture.session = Session()
    capture.main_frame = "f"
    capture.request(
        {
            "requestId": "1",
            "type": "Script",
            "frameId": "f",
            "request": {"url": "https://shop.cem.test:8765/scripts/base.js"},
        }
    )
    capture.data({"requestId": "1", "dataLength": 9})
    capture.finished({"requestId": "1"})
    worker = asyncio.create_task(capture.capture_bodies())
    await asyncio.wait_for(capture.queue.join(), 1)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker
    assert capture.session.calls == ["Network.getResponseBody"]
    assert record.evidence[0].body_sha256 and record.evidence[0].body_size == 9


def test_T08_dynamic_change_does_not_classify_intent():
    a, b = run(script("dynamic", b"1")), run(script("dynamic", b"2"))
    f = next(f for f in evaluate(b, compare(a, b)) if "OBS-006" in f.rule_ids)
    assert f.severity == "REVIEW_NEEDED" and "intent is unknown" in f.interpretation


def test_T09_consent_mismatch_refuses_diff():
    a, b = run(script()), run(script("extra"))
    b.profile.consent = "ACCEPTED"
    result = compare(a, b)
    assert result.eligibility == "INCOMPATIBLE_PROFILE" and result.changes == []
    assert result.mismatch_fields == ["consent"]


def test_T10_missing_body_is_unknown():
    e = script()
    e.body_sha256 = None
    e.body_reason = "BODY_OVERSIZED"
    assert compare(run(script()), run(e)).changes[0].kind == "UNOBSERVABLE"


def test_T11_frames_remain_distinct_and_partial():
    e = script()
    e.frame_id = "unresolved-frame"
    e.identity = ""
    b = run(e)
    b.frames = [
        FrameRecord(id="frame-1", origin="https://pay.cem.test:8766", parent_id="main", visibility="PARTIAL")
    ]
    assert compare(run(script()), b).changes
    assert any(c.kind == "AMBIGUOUS" for c in compare(run(script()), b).changes)
    assert sanitize_run(b).frames[0].origin == "https://pay.cem.test:8766"


def test_T13_report_only_is_not_enforced():
    doc = Evidence(
        kind="DOCUMENT",
        step_id="checkout",
        state="checkout",
        response_observed=True,
        url_display="https://shop.cem.test:8765/checkout",
        headers={"content-security-policy-report-only": "default-src 'self'; script-src 'self'"},
    )
    b = sanitize_run(run(doc))
    f = next(f for f in evaluate(b) if "OBS-002" in f.rule_ids)
    assert f.reason_codes == ["REPORT_ONLY"] and b.evidence[0].csp[0]["mode"] == "REPORT_ONLY"
    assert "script-src" in b.evidence[0].csp[0]["directives"]


def test_T14_cookie_attribute_change_has_no_value():
    a, b = run(), run()
    c = CookieRecord(
        name="cem-session",
        domain="shop.cem.test",
        path="/",
        secure=True,
        http_only=True,
        same_site="Lax",
        role="CONFIGURED_SESSION",
    )
    a.cookies = [c]
    b.cookies = [copy.deepcopy(c)]
    b.cookies[0].http_only = False
    assert compare(a, b).changes[0].category == "COOKIE"
    assert "value" not in b.cookies[0].model_dump()
    assert any(f.condition == "MATCH" and f.rule_ids == ["OBS-003"] for f in evaluate(b))


def test_T15_attempt_is_not_delivery():
    doc = Evidence(
        kind="DOCUMENT",
        state="checkout",
        step_id="checkout",
        url_display="https://shop.cem.test:8765/checkout",
        response_observed=True,
    )
    e = script(origin="http://pay.cem.test:8766")
    e.response_observed = False
    e.delivery = "FAILED"
    b = run(doc, e)
    f = next(f for f in evaluate(b) if "OBS-004" in f.rule_ids)
    assert f.condition == "MATCH" and b.evidence[1].delivery == "FAILED"


def test_T19_service_worker_policy_refuses_equivalence():
    a, b = run(script()), run(script())
    b.profile.service_workers = "allow"
    assert compare(a, b).mismatch_fields == ["service_workers"]


def test_T20_caps_retain_records_and_qualify_absence():
    b = run(script())
    capture = Capture(b, KEY)
    capture.main_frame = "f"
    b.profile.budgets.events = 1
    capture.request(
        {
            "requestId": "2",
            "frameId": "f",
            "type": "Script",
            "request": {"url": "https://shop.cem.test:8765/scripts/extra.js"},
        }
    )
    assert len(b.evidence) == 1 and "EVENT_CAP" in b.limitation_codes
    assert next(f for f in evaluate(b) if f.rule_ids == ["OBS-011"]).condition == "MATCH"
