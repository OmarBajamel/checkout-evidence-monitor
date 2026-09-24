import pytest
from cem.phase import require_runtime
from cem.storage import Store
from cem.lab_wrapper import run_lab
from cem.comparison import compare
from benchmarks.run import make_job


@pytest.mark.parametrize(
    "scenario",
    [
        "T01",
        "T02",
        "T03",
        "T04",
        "T05",
        "T06",
        "T07",
        "T08",
        "T09",
        "T10",
        "T11",
        "T12",
        "T13",
        "T14",
        "T15",
        "T16",
        "T17",
        "T18",
        "T19",
        "T20",
    ],
)
def test_actual_isolated_fixture(scenario, root, tmp_path):
    require_runtime(root, profile="LAB")
    store = Store(tmp_path / "lab-records")
    baseline = run_lab(make_job(root, "T01", "JOURNEY"), store, root)
    assert baseline.status == "COMPLETED", baseline.limitation_codes
    job = make_job(root, scenario, "JOURNEY")
    if scenario == "T20":
        job.budgets.events = 12
    current = run_lab(job, store, root)
    diff = compare(baseline, current)
    assert (
        current.provenance == "COLLECTED_LAB"
        and store.integrity(current.id)["state"] == "VERIFIED_SANITIZED_BYTES"
    )
    assert all(e.execution_evidence == "NOT_OBSERVED" for e in current.evidence)
    if scenario == "T01":
        assert not any(c.kind in ("ADDED", "CHANGED", "NOT_OBSERVED") for c in diff.changes)
    if scenario in ("T02", "T03"):
        assert any(c.kind == "ADDED" for c in diff.changes)
    if scenario in ("T04", "T08"):
        assert any(c.kind in ("ADDED", "CHANGED") for c in diff.changes)
    if scenario == "T05":
        assert any(c.kind == "NOT_OBSERVED" for c in diff.changes)
    if scenario in ("T06", "T17", "T18"):
        assert current.status in ("PARTIAL", "FAILED") and not any(
            c.kind == "NOT_OBSERVED" for c in diff.changes
        )
    if scenario == "T07":
        assert any("/delayed.js" in e.url_display and e.response_observed for e in current.evidence)
    if scenario in ("T09", "T19"):
        assert diff.eligibility == "INCOMPATIBLE_PROFILE"
    if scenario == "T10":
        assert any(e.body_reason == "BODY_OVERSIZED" for e in current.evidence)
    if scenario == "T11":
        assert any(f.visibility == "PARTIAL" for f in current.frames)
    if scenario == "T12":
        assert any("pay.cem.test" in e.origin for e in current.evidence)
    if scenario == "T13":
        assert any("content-security-policy-report-only" in e.headers for e in current.evidence)
    if scenario == "T14":
        assert any(not c.http_only for c in current.cookies)
    if scenario == "T15":
        assert any(e.delivery == "FAILED" and e.url_display.startswith("http:") for e in current.evidence)
    if scenario == "T16":
        assert "synthetic-secret" not in current.model_dump_json()
    if scenario == "T20":
        assert "EVENT_CAP" in current.limitation_codes and current.status == "PARTIAL"
