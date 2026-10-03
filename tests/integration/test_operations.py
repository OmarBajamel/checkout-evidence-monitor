"""Durability/review/API tests authored without execution for this new source."""

import time
import pytest
from cem.errors import CEMError
from cem.operations import Operations, ReviewDecision
from cem.storage import Store
from tests.helpers import run, script
from tests.pilot_helpers import pilot
from tests.integration.test_store_api import client


def prepared(tmp_path):
    ops = Operations(Store(tmp_path / "data"))
    config = pilot()
    ops.save_target(config)
    ops.acquire("worker-a")
    ops.heartbeat("worker-a")
    return ops, config


def test_target_save_is_paused_and_reading_never_queues(tmp_path):
    ops = Operations(Store(tmp_path / "data"))
    ops.save_target(pilot())
    for _ in range(3):
        state = ops.snapshot()
        assert state["targets"][0]["state"] == "PAUSED"
        assert state["jobs"] == []
    with pytest.raises(CEMError, match="runner"):
        ops.action("offline-pilot", "RUN_ONCE")


def test_run_once_is_deduplicated_and_cross_worker_lease_is_exclusive(tmp_path):
    ops, config = prepared(tmp_path)
    ops.action(config.target_id, "RUN_ONCE")
    ops.action(config.target_id, "RUN_ONCE")
    assert len(ops.snapshot()["jobs"]) == 1
    with pytest.raises(CEMError, match="Another"):
        Operations(ops.store).acquire("worker-b")
    job = ops.next_job("worker-a")
    assert job and ops.next_job("worker-a") is None
    ops.action(config.target_id, "PAUSE")
    assert ops.cancelled(job["id"])
    with pytest.raises(CEMError):
        ops.save_target(config)


def test_missed_cadence_is_coalesced_and_disclosed(tmp_path):
    ops, config = prepared(tmp_path)
    ops.action(config.target_id, "START")
    with ops.store.connect() as db:
        db.execute("UPDATE monitor_targets SET next_at=?", (time.time() - 4 * 3600,))
    assert ops.next_job("worker-a")
    state = ops.snapshot()
    assert len(state["jobs"]) == 1
    assert any(n["kind"] == "MISSED_CADENCE" for n in state["notices"])
    assert state["targets"][0]["next_at"] > time.time()


def test_restart_keeps_interruption_and_recovers_no_fake_success(tmp_path):
    ops, config = prepared(tmp_path)
    ops.action(config.target_id, "RUN_ONCE")
    job = ops.next_job("worker-a")
    assert len(Operations(ops.store).abandoned()) == 1
    # Cleanup is tested separately with a mocked Docker boundary; no container is launched here.
    ops.interrupted(job["id"])
    state = Operations(ops.store).snapshot()
    assert state["jobs"][0]["status"] == "INTERRUPTED"
    assert ops.store.list_runs()["total"] == 0


def test_cleanup_failure_pauses_target_and_remains_recoverable(tmp_path):
    ops, config = prepared(tmp_path)
    ops.action(config.target_id, "START")
    job = ops.next_job("worker-a")
    ops.finish(job, code="CLEANUP_UNCONFIRMED")
    assert ops.snapshot()["targets"][0]["state"] == "PAUSED"
    assert ops.abandoned()[0]["id"] == job["id"]


def test_review_annotations_preserve_evidence_and_protect_retention(tmp_path):
    ops, _ = prepared(tmp_path)
    a = ops.store.save(run(script()))
    b = ops.store.save(run(script(body=b"changed")))
    old = ops.store.artifact_path(b.id).read_bytes()
    first = ops.review(
        ReviewDecision(
            baseline_id=a.id, candidate_id=b.id, decision="INVESTIGATE", reason="Inspect this difference"
        )
    )
    ops.review(
        ReviewDecision(
            baseline_id=a.id, candidate_id=b.id, decision="EXPECTED", reason="Release owner confirmed context"
        )
    )
    assert ops.store.artifact_path(b.id).read_bytes() == old
    assert ops.reviews(a.id, b.id)["total"] == 2
    assert first["id"] in {r["id"] for r in ops.export_reviews(a.id, b.id)["reviews"]}
    with pytest.raises(CEMError, match="review"):
        ops.store.retention_preview([b.id])


def test_notification_dedup_does_not_reopen_acknowledged_identical_difference(tmp_path):
    ops, config = prepared(tmp_path)
    a = run(script())
    a.profile.target_id = config.target_id
    a = ops.store.save(a)
    ops.store.baseline(a.id, "Synthetic comparison reference")
    for _ in range(2):
        ops.action(config.target_id, "RUN_ONCE")
        job = ops.next_job("worker-a")
        b = run(script(body=b"changed"))
        b.profile.target_id = config.target_id
        b.id = job["run_id"]
        b = ops.store.save(b)
        ops.finish(job, b)
        notice = ops.snapshot()["notices"][0]
        ops.acknowledge(notice["id"])
    state = ops.snapshot()
    assert len(state["notices"]) == 1 and state["notices"][0]["repeats"] == 2
    assert state["unread"] == 0


def test_retention_refuses_stale_preview_and_never_deletes_unread(tmp_path):
    ops, config = prepared(tmp_path)
    ops.action(config.target_id, "RUN_ONCE")
    job = ops.next_job("worker-a")
    ops.finish(job, code="COLLECTOR_FAILED")
    with ops.store.connect() as db:
        db.execute("UPDATE monitor_jobs SET ended_at=?", (time.time() - 40 * 86400,))
        db.execute("UPDATE monitor_notices SET last_at=?", (time.time() - 40 * 86400,))
    preview = ops.retention_preview()
    assert preview["notices"] == [] and len(preview["jobs"]) == 1
    ops.acknowledge(ops.snapshot()["notices"][0]["id"])
    with pytest.raises(CEMError, match="fresh"):
        ops.retention_apply(preview["confirmation"])
    fresh = ops.retention_preview()
    assert ops.retention_apply(fresh["confirmation"]) == {"jobs": 1, "notices": 1}


def test_new_api_writes_require_origin_and_cannot_run_without_worker(tmp_path):
    store, c = client(tmp_path)
    payload = pilot().model_dump(mode="json")
    assert c.post("/api/v1/targets", json=payload).status_code == 403
    r = c.post("/api/v1/targets", json=payload, headers={"Origin": "http://127.0.0.1:8760"})
    assert r.status_code == 200 and r.json()["state"] == "PAUSED"
    assert c.get("/api/v1/operations").json()["jobs"] == []
    r = c.post(
        "/api/v1/targets/offline-pilot/actions",
        json={"action": "RUN_ONCE"},
        headers={"Origin": "http://127.0.0.1:8760"},
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "RUNNER_OFFLINE"
    assert store.list_runs()["total"] == 0


def test_pilot_scope_context_survives_operational_retention(tmp_path):
    from cem.pilot.collector import make_run

    ops, config = prepared(tmp_path)
    ops.action(config.target_id, "RUN_ONCE")
    job = ops.next_job("worker-a")
    observed = make_run(config, ops.store.key(), job["run_id"])
    observed.status = "PARTIAL"
    observed = ops.store.save(observed, pilot_origins=config.grant.origins)
    ops.finish(job, observed)
    before = ops.run_context(observed.id)
    assert before["approved_origins"] == config.grant.origins
    assert "owner" not in before and "assessor" not in before
    with ops.store.connect() as db:
        db.execute("UPDATE monitor_jobs SET ended_at=?", (time.time() - 40 * 86400,))
    preview = ops.retention_preview()
    assert ops.retention_apply(preview["confirmation"])["jobs"] == 1
    assert ops.run_context(observed.id) == before
    assert ops.store.verified_get(observed.id).id == observed.id
