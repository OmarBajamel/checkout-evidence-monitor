"""One transactional persistence service shared by CLI and API."""

from contextlib import contextmanager
from pathlib import Path
from threading import RLock
import hashlib
import json
import os
import secrets
import sqlite3
import re
from pydantic import ValidationError
from .config import parse_json
from .domain import Run, MAX_IMPORT, utc_now, new_id
from .privacy import sanitize_run, safe_text
from .errors import CEMError

ID = re.compile(r"^[a-f0-9]{32}$")
MIGRATION = """
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES(1);
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, target_id TEXT NOT NULL, started_at TEXT NOT NULL,
 label TEXT NOT NULL, status TEXT NOT NULL, profile_json TEXT NOT NULL, payload_json TEXT NOT NULL,
 artifact_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, state TEXT NOT NULL, payload_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS evidence_run ON evidence(run_id);
CREATE TABLE IF NOT EXISTS steps(run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
 step_id TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(run_id,step_id));
CREATE TABLE IF NOT EXISTS frames(run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
 frame_id TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(run_id,frame_id));
CREATE TABLE IF NOT EXISTS cookies(run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(run_id,ordinal));
CREATE TABLE IF NOT EXISTS baselines(target_id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(id),
 reason TEXT NOT NULL,selected_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY,at TEXT NOT NULL,action TEXT NOT NULL,
 subject TEXT NOT NULL,reason TEXT NOT NULL);
"""


def validate_id(value: str) -> str:
    if not ID.fullmatch(value):
        raise CEMError("INVALID_INPUT", "A valid opaque record ID is required.")
    return value


def reject_symlink_chain(path: Path):
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise CEMError("PATH_DENIED", "Symlinks and junctions are not supported.")


def canonical_bytes(run: Run) -> bytes:
    d = run.model_dump(mode="json")
    d["sanitized_artifact_sha256"] = None
    return json.dumps(d, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


class Store:
    def __init__(self, root: Path, *, read_only=False):
        reject_symlink_chain(root)
        self.root = root.resolve()
        self.read_only = read_only
        self.lock = RLock()
        if not read_only:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            (self.root / "records").mkdir(exist_ok=True, mode=0o700)
        self.records = self.root / "records"
        self.db = self.root / "evidence.sqlite3"
        reject_symlink_chain(self.db)
        if not read_only:
            with self.connect() as db:
                db.executescript(MIGRATION)
        if not self.db.exists():
            raise CEMError("NOT_FOUND", "The requested evidence store does not exist.", 404)

    @contextmanager
    def connect(self):
        mode = "ro" if self.read_only else "rwc"
        db = sqlite3.connect(self.db.as_uri() + f"?mode={mode}", uri=True, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        try:
            yield db
            if not self.read_only:
                db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def writable(self):
        if self.read_only:
            raise CEMError("READ_ONLY_DEMO", "This dataset is read-only.", 403)

    def artifact_path(self, run_id):
        p = self.records / (validate_id(run_id) + ".json")
        reject_symlink_chain(p)
        return p

    def key(self) -> bytes:
        self.writable()
        p = self.root / ".identity-key"
        reject_symlink_chain(p)
        with self.lock:
            if not p.exists():
                fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(secrets.token_bytes(32))
            value = p.read_bytes()
        if len(value) != 32:
            raise CEMError("KEY_INVALID", "Identity key has an invalid length.")
        return value

    @staticmethod
    def audit(db, action, subject, reason):
        db.execute(
            "INSERT INTO audit VALUES(?,?,?,?,?)",
            (new_id(), utc_now(), action, subject, safe_text(reason, 500)),
        )

    def save(self, run: Run, *, trusted_lab=False, demo=False) -> Run:
        self.writable()
        run = sanitize_run(run.model_copy(deep=True))
        run.provenance = "SYNTHETIC_DEMO" if demo else ("COLLECTED_LAB" if trusted_lab else "DECLARED_IMPORT")
        if len({e.id for e in run.evidence}) != len(run.evidence):
            raise CEMError("INVALID_INPUT", "Evidence IDs must be unique.")
        raw = canonical_bytes(run)
        if len(raw) > MAX_IMPORT:
            raise CEMError("ARTIFACT_LIMIT", "Sanitized record exceeds 50 MiB.")
        digest = hashlib.sha256(raw).hexdigest()
        path = self.artifact_path(run.id)
        temp = self.records / (run.id + "." + new_id() + ".pending")
        with self.lock, self.connect() as db:
            if db.execute("SELECT 1 FROM runs WHERE id=?", (run.id,)).fetchone() or path.exists():
                raise CEMError("DUPLICATE_RUN", "This run already exists.", 409)
            # File first + transaction: interruptions leave an identifiable orphan, never a successful DB row.
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, path)
            payload = run.model_dump(mode="json")
            payload["evidence"] = []
            payload["sanitized_artifact_sha256"] = digest
            try:
                db.execute(
                    "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)",
                    (
                        run.id,
                        run.profile.target_id,
                        run.started_at,
                        run.label,
                        run.status,
                        run.profile.model_dump_json(),
                        json.dumps(payload),
                        digest,
                    ),
                )
                db.executemany(
                    "INSERT INTO evidence VALUES(?,?,?,?,?)",
                    [(e.id, run.id, e.kind, e.state, e.model_dump_json()) for e in run.evidence],
                )
                db.executemany(
                    "INSERT INTO steps VALUES(?,?,?)",
                    [(run.id, s.id, s.model_dump_json()) for s in run.steps],
                )
                db.executemany(
                    "INSERT INTO frames VALUES(?,?,?)",
                    [(run.id, f.id, f.model_dump_json()) for f in run.frames],
                )
                db.executemany(
                    "INSERT INTO cookies VALUES(?,?,?)",
                    [(run.id, i, c.model_dump_json()) for i, c in enumerate(run.cookies)],
                )
                self.audit(db, "IMPORT" if not trusted_lab else "COLLECT_LAB", run.id, run.provenance)
            except sqlite3.IntegrityError:
                raise CEMError(
                    "RECORD_CONFLICT", "A record ID conflicts with existing evidence.", 409
                ) from None
        run.sanitized_artifact_sha256 = digest
        return run

    def import_file(self, path: Path) -> Run:
        if ".." in path.parts:
            raise CEMError("PATH_DENIED", "Traversal components are forbidden in import paths.")
        reject_symlink_chain(path)
        if not path.is_file() or path.suffix.lower() != ".json" or path.stat().st_size > MAX_IMPORT:
            raise CEMError("INVALID_INPUT", "Only bounded regular CEM JSON files can be imported.")
        try:
            run = Run.model_validate(parse_json(path.read_bytes()))
        except ValidationError:
            raise CEMError("INVALID_INPUT", "Import does not match the CEM evidence schema.") from None
        return self.save(run)

    def get(self, run_id: str) -> Run:
        validate_id(run_id)
        with self.lock, self.connect() as db:
            row = db.execute("SELECT payload_json FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise CEMError("NOT_FOUND", "Run not found.", 404)
            d = json.loads(row[0])
            d["evidence"] = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload_json FROM evidence WHERE run_id=? ORDER BY rowid", (run_id,)
                )
            ]
        return Run.model_validate(d)

    def list_runs(self, limit=50, offset=0, q=""):
        if not 1 <= limit <= 100 or not 0 <= offset <= 1000000 or len(q) > 200:
            raise CEMError("INVALID_INPUT", "Pagination or search exceeds its limit.")
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self.lock, self.connect() as db:
            where = " WHERE label LIKE ? ESCAPE '\\' OR target_id LIKE ? ESCAPE '\\'"
            args = ("%" + escaped + "%", "%" + escaped + "%")
            total = db.execute("SELECT COUNT(*) FROM runs" + where, args).fetchone()[0]
            rows = db.execute(
                "SELECT payload_json FROM runs"
                + where
                + " ORDER BY started_at DESC,id DESC LIMIT ? OFFSET ?",
                (*args, limit, offset),
            ).fetchall()
            baselines = {r[0]: r[1] for r in db.execute("SELECT target_id,run_id FROM baselines")}
        return {
            "items": [
                {
                    **json.loads(r[0]),
                    "is_baseline": baselines.get(json.loads(r[0])["profile"]["target_id"])
                    == json.loads(r[0])["id"],
                }
                for r in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "demo": self.read_only,
        }

    def evidence(self, evidence_id: str):
        validate_id(evidence_id)
        with self.lock, self.connect() as db:
            row = db.execute("SELECT run_id,payload_json FROM evidence WHERE id=?", (evidence_id,)).fetchone()
        if not row:
            raise CEMError("EVIDENCE_UNAVAILABLE", "Evidence record not found.", 404)
        run = self.get(row[0])
        data = json.loads(row[1])
        preview = json.dumps(data, ensure_ascii=False, indent=2)
        raw = preview.encode("utf-8")
        return {
            "schema_version": "1.0",
            "run_id": run.id,
            "profile": run.profile.model_dump(),
            "provenance": run.provenance,
            "run_status": run.status,
            "integrity": self.integrity(run.id),
            "record": data,
            "preview": raw[:16384].decode("utf-8", "ignore"),
            "preview_truncated": len(raw) > 16384,
            "preview_total_bytes": len(raw),
        }

    def integrity(self, run_id: str):
        path = self.artifact_path(run_id)
        with self.connect() as db:
            row = db.execute("SELECT artifact_hash FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise CEMError("NOT_FOUND", "Run not found.", 404)
        if not path.exists():
            return {"state": "MISSING", "expected_sha256": row[0], "actual_sha256": None}
        if path.stat().st_size > MAX_IMPORT:
            return {"state": "MISMATCH", "expected_sha256": row[0], "actual_sha256": None}
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        database_hash = hashlib.sha256(canonical_bytes(self.get(run_id))).hexdigest()
        return {
            "state": "VERIFIED_SANITIZED_BYTES" if actual == row[0] == database_hash else "MISMATCH",
            "expected_sha256": row[0],
            "actual_sha256": actual,
        }

    def verified_get(self, run_id: str) -> Run:
        if self.integrity(run_id)["state"] != "VERIFIED_SANITIZED_BYTES":
            raise CEMError(
                "INTEGRITY_FAILED",
                "Stored evidence integrity is unresolved; comparison and export are blocked.",
                409,
            )
        return self.get(run_id)

    def baseline(self, run_id: str, reason: str):
        self.writable()
        reason = safe_text(reason, 500).strip()
        if not 3 <= len(reason) <= 500:
            raise CEMError("INVALID_INPUT", "Provide a baseline selection reason (3–500 characters).")
        run = self.get(run_id)
        if run.provenance == "SYNTHETIC_DEMO":
            raise CEMError("READ_ONLY_DEMO", "Demo records cannot become baselines.", 403)
        if self.integrity(run_id)["state"] != "VERIFIED_SANITIZED_BYTES":
            raise CEMError("INTEGRITY_FAILED", "Resolve artifact integrity before choosing a baseline.", 409)
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT INTO baselines VALUES(?,?,?,?) ON CONFLICT(target_id) DO UPDATE SET run_id=excluded.run_id,reason=excluded.reason,selected_at=excluded.selected_at",
                (run.profile.target_id, run.id, reason, utc_now()),
            )
            self.audit(db, "BASELINE_SELECTED", run.id, reason)
        return {"run_id": run.id, "reason": reason, "notice": "Selection does not certify safety."}

    def retention_preview(self, run_ids: list[str]):
        if len(run_ids) > 100:
            raise CEMError("ARTIFACT_LIMIT", "Select at most 100 runs.")
        ids = sorted(set(validate_id(x) for x in run_ids))
        with self.connect() as db:
            baselines = {r[0] for r in db.execute("SELECT run_id FROM baselines")}
        if baselines.intersection(ids):
            raise CEMError("BASELINE_PROTECTED", "Select a replacement baseline first.", 409)
        for id in ids:
            self.get(id)
        token = hashlib.sha256(json.dumps(ids).encode()).hexdigest()
        return {
            "run_ids": ids,
            "confirmation": token,
            "notice": "Only these app-owned records will be removed.",
        }

    def retention_apply(self, ids, confirmation):
        self.writable()
        preview = self.retention_preview(ids)
        if not secrets.compare_digest(preview["confirmation"], confirmation):
            raise CEMError("CONFIRMATION_REQUIRED", "Review the current retention preview first.")
        with self.lock, self.connect() as db:
            for id in preview["run_ids"]:
                path = self.artifact_path(id)
                self.audit(db, "RETENTION_DELETE", id, "Explicit operator selection")
                db.execute("DELETE FROM runs WHERE id=?", (id,))
                # Validated app-owned filename only. No recursive deletion.
                path.unlink(missing_ok=True)
        return {"deleted": preview["run_ids"]}

    def recovery_status(self):
        with self.connect() as db:
            known = {r[0] + ".json" for r in db.execute("SELECT id FROM runs")}
        files = list(self.records.iterdir())
        return {
            "orphan_count": sum(p.name not in known for p in files),
            "pending_count": sum(p.suffix == ".pending" for p in files),
            "notice": "Uncommitted files are not successful runs. No cleanup was executed.",
        }
