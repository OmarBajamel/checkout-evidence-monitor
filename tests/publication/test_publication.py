import json
import pytest
from tools.publication_guard import (
    public_path,
    check_content,
    preflight,
    canonical_hash,
    publish_with_adapter,
)
from cem.phase import source_snapshot, require_runtime


def test_T35_public_path_secrets_and_concept_provenance(root):
    for path in (
        "state/approval.json",
        "STATE/approval.json",
        "assets/../../private.json",
        ".env",
        "data/evidence.sqlite3",
        "assets/font.ttf",
        "node_modules/x.js",
    ):
        with pytest.raises(ValueError):
            public_path(path)
    with pytest.raises(ValueError):
        check_content("docs/key.txt", b"-----BEGIN " + b"PRIVATE KEY-----")
    with pytest.raises(ValueError):
        check_content("assets/concept.svg", b"<svg><script>alert(1)</script></svg>")
    concept = (
        (root / "content/linkedin/03_review_experience/visual-landscape.svg")
        if (root / "content/linkedin").exists()
        else (root / "assets/concepts/changes-landscape.svg")
    ).read_text(encoding="utf-8")
    assert "DESIGN CONCEPT" in concept and "NOT A RUNTIME SCREENSHOT" in concept


def test_T36_mock_publication_requires_every_binding():
    plan = {
        "status": "READY_FOR_OWNER_REVIEW_NOT_AUTHORIZED",
        "owner_selector": "AUTHENTICATED_PERSONAL_ACCOUNT",
        "visibility": "public",
        "allowed_repository_names": ["checkout-evidence-monitor"],
        "runtime_status": "NOT_RUN_BY_USER_CHOICE",
    }
    manifest = {
        "source_snapshot": "synthetic",
        "runtime_status": "NOT_RUN_BY_USER_CHOICE",
        "files": [{"destination": "README.md"}],
    }
    owner = {"type": "User", "login": "synthetic-owner"}
    grant = {
        "authorized": True,
        "instruction": "APPROVED PUBLISH",
        "plan_sha256": canonical_hash(plan),
        "export_sha256": canonical_hash(manifest),
        "source_snapshot": "synthetic",
        "resolved_owner": "synthetic-owner",
    }

    class Mock:
        writes = []

        def create_new_public_repository(self, intent, files):
            self.writes.append(intent)
            return intent

    mock = Mock()
    for change in (
        {"authorized": False},
        {"plan_sha256": "wrong"},
        {"export_sha256": "wrong"},
        {"resolved_owner": "other"},
    ):
        with pytest.raises(ValueError):
            publish_with_adapter(
                mock, {**grant, **change}, plan, manifest, owner, "checkout-evidence-monitor"
            )
    assert mock.writes == []
    with pytest.raises(ValueError):
        preflight(grant, plan, manifest, owner, "unrelated-repo")
    result = publish_with_adapter(mock, grant, plan, manifest, owner, "checkout-evidence-monitor")
    assert result["remote_ci"] is False and result["hosting"] is False and len(mock.writes) == 1


@pytest.mark.parametrize(
    "status", ["NOT_RUN_BY_USER_CHOICE", "TESTED_PASS_LOCAL", "TESTED_WITH_FAILURES", "TESTING_BLOCKED"]
)
def test_T36_test_outcome_must_match_explicit_publication_plan(status):
    plan = {
        "status": "READY_FOR_OWNER_REVIEW_NOT_AUTHORIZED",
        "owner_selector": "AUTHENTICATED_PERSONAL_ACCOUNT",
        "visibility": "public",
        "allowed_repository_names": ["synthetic"],
        "runtime_status": status,
    }
    manifest = {
        "source_snapshot": "synthetic",
        "runtime_status": status,
        "files": [{"destination": "README.md"}],
    }
    owner = {"type": "User", "login": "synthetic-owner"}

    def grant():
        return {
            "authorized": True,
            "instruction": "APPROVED PUBLISH",
            "source_snapshot": "synthetic",
            "resolved_owner": owner["login"],
            "plan_sha256": canonical_hash(plan),
            "export_sha256": canonical_hash(manifest),
        }

    assert preflight(grant(), plan, manifest, owner, "synthetic")["runtime_status"] == status
    plan["status"] = "STALE_REVIEW_REQUIRED"
    with pytest.raises(ValueError, match="not ready"):
        preflight(grant(), plan, manifest, owner, "synthetic")
    plan["status"] = "READY_FOR_OWNER_REVIEW_NOT_AUTHORIZED"
    manifest["runtime_status"] = "TESTED_PASS_LOCAL" if status != "TESTED_PASS_LOCAL" else "TESTING_BLOCKED"
    with pytest.raises(ValueError, match="verification status"):
        preflight(grant(), plan, manifest, owner, "synthetic")
    plan["runtime_status"] = manifest["runtime_status"] = "INVENTED_SUCCESS"
    with pytest.raises(ValueError, match="verification status"):
        preflight(grant(), plan, manifest, owner, "synthetic")


def test_T37_finished_content_has_truthful_readiness(root):
    folders = sorted((root / "content/linkedin").glob("[0-9][0-9]_*"))
    if not (root / "content/linkedin").exists():
        status = (root / "docs/TESTING_STATUS.md").read_text(encoding="utf-8")
        declared = status.split("Overall outcome:", 1)[1].splitlines()[0]
        assert any(
            f"**{outcome}**" in declared
            for outcome in (
                "NOT_RUN_BY_USER_CHOICE",
                "TESTING_BLOCKED",
                "TESTED_PASS_LOCAL",
                "TESTED_WITH_FAILURES",
            )
        )
        assert "LAB" in status and "Source snapshot:" in status
        return  # Private editorial package is outside the public source export.
    assert len(folders) == 6
    for folder in folders:
        evidence = json.loads((folder / "EVIDENCE.json").read_text(encoding="utf-8"))
        assert evidence["publish_authorized"] is False
        assert len((folder / "POST_EN.md").read_text(encoding="utf-8").split()) >= 140
        assert (folder / "POST_AR.md").stat().st_size > 300
        for orientation in ("landscape", "portrait"):
            assert (folder / ("visual-" + orientation + ".png")).read_bytes().startswith(b"\x89PNG")
    sixth = folders[-1]
    assert "[REPOSITORY_URL_PENDING]" in (sixth / "POST_EN.md").read_text(encoding="utf-8")
    assert (
        json.loads((sixth / "EVIDENCE.json").read_text(encoding="utf-8"))["readiness"]
        == "WAITING_FOR_PUBLICATION"
    )


def test_T38_source_changes_invalidate_tests_without_publishing(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    file = tmp_path / "src/version.txt"
    file.write_text("one")
    old = source_snapshot(tmp_path)
    file.write_text("two")
    assert old != source_snapshot(tmp_path)
    before_lock = source_snapshot(tmp_path)
    (tmp_path / "requirements-win.lock").write_text("synthetic dependency change")
    assert before_lock != source_snapshot(tmp_path)
    session = tmp_path / "session.json"
    session.write_text(
        json.dumps(
            {
                "instruction": "TEST APPROVED",
                "profile": "OFFLINE",
                "source_snapshot": old,
                "expires_at": "2999-01-01T00:00:00+00:00",
            }
        )
    )
    monkeypatch.setenv("CEM_TEST_SESSION", str(session))
    with pytest.raises(Exception):
        require_runtime(tmp_path)
    assert not (tmp_path / ".git").exists()
