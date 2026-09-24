import pytest
from fastapi.testclient import TestClient
from cem.api import create_app, Session
from cem.errors import CEMError
from cem.storage import Store
from tests.helpers import run, script


def client(tmp_path):
    store = Store(tmp_path / "data")
    session = Session()
    c = TestClient(create_app(store, session), base_url="http://127.0.0.1:8760")
    r = c.post(
        "/api/v1/session/bootstrap",
        json={"secret": session.bootstrap},
        headers={"Origin": "http://127.0.0.1:8760"},
    )
    assert r.status_code == 200
    c.headers["Authorization"] = "Bearer " + r.json()["bearer"]
    return store, c


def test_T22_integrity_orphan_and_retention(tmp_path):
    s = Store(tmp_path / "data")
    b = s.save(run(script()))
    assert s.integrity(b.id)["state"] == "VERIFIED_SANITIZED_BYTES"
    s.artifact_path(b.id).write_text("altered")
    assert s.integrity(b.id)["state"] == "MISMATCH"
    with pytest.raises(CEMError):
        s.baseline(b.id, "Must refuse corrupted record")
    (s.records / "interrupted.pending").write_text("partial")
    assert s.recovery_status()["pending_count"] == 1
    preview = s.retention_preview([b.id])
    s.retention_apply([b.id], preview["confirmation"])
    assert s.list_runs()["total"] == 0


def test_T25_token_host_origin_and_single_use(tmp_path):
    s, c = client(tmp_path)
    assert c.get("/api/v1/runs").status_code == 200
    for headers in (
        {"Authorization": "Bearer invalid"},
        {"Host": "evil.test"},
        {"Origin": "null"},
        {"Origin": "https://evil.test"},
        {"X-Forwarded-Host": "localhost"},
    ):
        assert c.get("/api/v1/runs", headers=headers).status_code in (401, 403)
    assert c.options("/api/v1/runs").status_code == 405
    assert "access-control-allow-origin" not in c.get("/api/v1/runs").headers


def test_T26_paths_unknown_routes_and_bounded_errors(tmp_path):
    s, c = client(tmp_path)
    assert c.get("/api/v1/evidence/../../private").status_code == 404
    assert c.get("/api/v1/runs?limit=101").status_code == 400
    r = c.post(
        "/api/v1/baselines",
        content="x" * 9000,
        headers={"Origin": "http://127.0.0.1:8760", "Content-Type": "application/json"},
    )
    assert r.status_code == 413 and len(r.content) < 1024
    assert c.get("/api/v1/proxy?url=http://example.com").status_code == 404


def test_T27_loading_workbench_never_creates_run(tmp_path):
    s, c = client(tmp_path)
    c.get("/")
    c.get("/api/v1/runs")
    assert s.list_runs()["total"] == 0
    assert c.post("/api/v1/collect", json={}, headers={"Origin": "http://127.0.0.1:8760"}).status_code in (
        404,
        405,
    )


def test_T28_real_store_journey_evidence_export(tmp_path):
    s, c = client(tmp_path)
    b = s.save(run(script()))
    assert c.get("/api/v1/runs").json()["items"][0]["id"] == b.id
    assert c.get(f"/api/v1/runs/{b.id}/journey").json()["steps"][2]["state"] == "checkout"
    e = c.get("/api/v1/evidence/" + b.evidence[0].id).json()
    assert e["record"]["body_sha256"] == b.evidence[0].body_sha256
    assert e["provenance"] == "DECLARED_IMPORT"
    for fmt in ("html", "json", "csv"):
        result = c.get(f"/api/v1/runs/{b.id}/export?format={fmt}")
        assert result.status_code == 200 and "attachment;" in result.headers["content-disposition"]


def test_T32_baseline_is_explicit_audited_and_profiles_refused(tmp_path):
    s, c = client(tmp_path)
    a = s.save(run(script()))
    b = run(script())
    b.profile.consent = "ACCEPTED"
    b = s.save(b)
    assert not c.get("/api/v1/runs").json()["items"][0]["is_baseline"]
    r = c.post(
        "/api/v1/baselines",
        json={"run_id": a.id, "reason": "Synthetic reviewed window"},
        headers={"Origin": "http://127.0.0.1:8760"},
    )
    assert r.status_code == 200
    with s.connect() as db:
        assert db.execute("SELECT count(*) FROM audit WHERE action='BASELINE_SELECTED'").fetchone()[0] == 1
    result = c.get("/api/v1/comparisons", params={"baseline": a.id, "candidate": b.id}).json()
    assert result["eligibility"] == "INCOMPATIBLE_PROFILE" and result["changes"] == []
