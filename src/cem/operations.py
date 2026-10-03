"""Durable local monitoring and reviewer annotations, separate from immutable observations."""

import hashlib
import json
import time
from typing import Literal
from pydantic import Field
from .domain import StrictModel, new_id
from .errors import CEMError
from .storage import Store, validate_id
from .privacy import safe_text
from .pilot.policy import PilotConfig, require_grant
from .comparison import compare

SCHEMA = """
CREATE TABLE IF NOT EXISTS monitor_targets(
 id TEXT PRIMARY KEY, label TEXT NOT NULL, config_json TEXT NOT NULL, version INTEGER NOT NULL,
 state TEXT NOT NULL, next_at REAL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS monitor_config_history(
 target_id TEXT NOT NULL, version INTEGER NOT NULL, config_json TEXT NOT NULL, at REAL NOT NULL,
 PRIMARY KEY(target_id,version));
CREATE TABLE IF NOT EXISTS monitor_jobs(
 id TEXT PRIMARY KEY, target_id TEXT NOT NULL REFERENCES monitor_targets(id), config_json TEXT NOT NULL,
 version INTEGER NOT NULL, status TEXT NOT NULL, queued_at REAL NOT NULL, started_at REAL, ended_at REAL,
 run_id TEXT NOT NULL, code TEXT, cancel INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX IF NOT EXISTS monitor_no_overlap ON monitor_jobs(target_id)
 WHERE status IN ('QUEUED','RUNNING');
CREATE TABLE IF NOT EXISTS monitor_notices(
 id TEXT PRIMARY KEY, target_id TEXT NOT NULL REFERENCES monitor_targets(id), dedupe TEXT NOT NULL,
 kind TEXT NOT NULL, message TEXT NOT NULL, baseline_id TEXT, candidate_id TEXT,
 created_at REAL NOT NULL, last_at REAL NOT NULL, repeats INTEGER NOT NULL DEFAULT 1,
 read_at REAL, UNIQUE(target_id,dedupe));
CREATE TABLE IF NOT EXISTS monitor_reviews(
 id TEXT PRIMARY KEY, baseline_id TEXT NOT NULL REFERENCES runs(id), candidate_id TEXT NOT NULL REFERENCES runs(id),
 decision TEXT NOT NULL, reason TEXT NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS monitor_worker(
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), token TEXT NOT NULL, heartbeat REAL NOT NULL,
 expires REAL NOT NULL, status TEXT NOT NULL, code TEXT);
CREATE TABLE IF NOT EXISTS monitor_run_context(
 run_id TEXT PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
 target_id TEXT NOT NULL, version INTEGER NOT NULL, config_sha256 TEXT NOT NULL,
 FOREIGN KEY(target_id,version) REFERENCES monitor_config_history(target_id,version));
"""


class TargetAction(StrictModel):
    action: Literal["START", "PAUSE", "RUN_ONCE", "CANCEL"]


class ReviewDecision(StrictModel):
    baseline_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    candidate_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    decision: Literal["EXPECTED", "INVESTIGATE", "DEFERRED", "REVIEWED"]
    reason: str = Field(min_length=3, max_length=500)


class Operations:
    def __init__(self, store: Store):
        self.store = store
        if not store.read_only:
            with store.connect() as db:
                db.executescript(SCHEMA)

    @staticmethod
    def notice(db, target, key, kind, message, baseline=None, candidate=None):
        now = time.time()
        # Inbox cap never silently drops a new actionable item; scheduler backpressure checks below.
        db.execute(
            """INSERT INTO monitor_notices VALUES(?,?,?,?,?,?,?,?,?,1,NULL)
            ON CONFLICT(target_id,dedupe) DO UPDATE SET
            last_at=excluded.last_at,repeats=monitor_notices.repeats+1,
            candidate_id=excluded.candidate_id,baseline_id=excluded.baseline_id""",
            (new_id(), target, key, kind, message, baseline, candidate, now, now),
        )

    def save_target(self, config: PilotConfig):
        self.store.writable()
        require_grant(config)
        if len(config.model_dump_json().encode()) > 7800:
            raise CEMError("ARTIFACT_LIMIT", "Target configuration exceeds the local request budget.")
        config = config.model_copy(update={"label": safe_text(config.label, 80)})
        now = time.time()
        with self.store.lock, self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM monitor_targets WHERE id=?", (config.target_id,)).fetchone()
            if existing:
                pending = db.execute(
                    "SELECT 1 FROM monitor_jobs WHERE target_id=? AND status IN ('QUEUED','RUNNING')",
                    (config.target_id,),
                ).fetchone()
                if existing["state"] != "PAUSED" or pending:
                    raise CEMError(
                        "TARGET_BUSY",
                        "Pause and finish cancelling active work before editing this target.",
                        409,
                    )
                if existing["version"] >= 100:
                    raise CEMError(
                        "HISTORY_CAP",
                        "Target revision limit reached; retain the history and create a new target.",
                    )
            elif db.execute("SELECT count(*) FROM monitor_targets").fetchone()[0] >= 10:
                raise CEMError("TARGET_CAP", "This local pilot supports at most 10 targets.")
            version = existing["version"] + 1 if existing else 1
            db.execute(
                """INSERT INTO monitor_targets VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET label=excluded.label,config_json=excluded.config_json,
                version=excluded.version,state='PAUSED',next_at=NULL,updated_at=excluded.updated_at""",
                (config.target_id, config.label, config.model_dump_json(), version, "PAUSED", None, now, now),
            )
            db.execute(
                "INSERT INTO monitor_config_history VALUES(?,?,?,?)",
                (config.target_id, version, config.model_dump_json(), now),
            )
            self.store.audit(db, "TARGET_CONFIGURED", config.target_id, f"Version {version}; saved paused")
        return {"target_id": config.target_id, "version": version, "state": "PAUSED"}

    @staticmethod
    def target(db, target_id):
        row = db.execute("SELECT * FROM monitor_targets WHERE id=?", (target_id,)).fetchone()
        if not row:
            raise CEMError("NOT_FOUND", "Target not found.", 404)
        return row

    @staticmethod
    def capacity(db, target_id):
        jobs = db.execute("SELECT count(*) FROM monitor_jobs WHERE target_id=?", (target_id,)).fetchone()[0]
        notices = db.execute(
            "SELECT count(*) FROM monitor_notices WHERE target_id=?", (target_id,)
        ).fetchone()[0]
        if jobs >= 1000 or notices >= 1000:
            raise CEMError(
                "MONITOR_CAP", "Operational history is full. Review retention before collecting more.", 409
            )

    @staticmethod
    def queue(db, row):
        pending = db.execute(
            "SELECT id FROM monitor_jobs WHERE target_id=? AND status IN ('QUEUED','RUNNING')", (row["id"],)
        ).fetchone()
        if pending:
            return pending[0]
        Operations.capacity(db, row["id"])
        job_id = new_id()
        db.execute(
            "INSERT INTO monitor_jobs VALUES(?,?,?,?,? ,?,NULL,NULL,?,NULL,0)",
            (job_id, row["id"], row["config_json"], row["version"], "QUEUED", time.time(), new_id()),
        )
        return job_id

    def action(self, target_id, action):
        self.store.writable()
        with self.store.lock, self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.target(db, target_id)
            config = PilotConfig.model_validate_json(row["config_json"])
            if action in ("START", "RUN_ONCE"):
                require_grant(config)
                worker = db.execute("SELECT * FROM monitor_worker WHERE singleton=1").fetchone()
                if not worker or worker["expires"] <= time.time() or worker["status"] != "READY":
                    raise CEMError(
                        "RUNNER_OFFLINE",
                        "Start the explicitly authorized pilot runner before queuing work.",
                        409,
                    )
                self.capacity(db, target_id)
                if action == "START":
                    db.execute(
                        "UPDATE monitor_targets SET state='ACTIVE',next_at=?,updated_at=? WHERE id=?",
                        (time.time(), time.time(), target_id),
                    )
                else:
                    self.queue(db, row)
            else:
                if action == "PAUSE":
                    db.execute(
                        "UPDATE monitor_targets SET state='PAUSED',next_at=NULL,updated_at=? WHERE id=?",
                        (time.time(), target_id),
                    )
                db.execute(
                    "UPDATE monitor_jobs SET status='CANCELLED',code='CANCELLED',ended_at=? WHERE target_id=? AND status='QUEUED'",
                    (time.time(), target_id),
                )
                db.execute(
                    "UPDATE monitor_jobs SET cancel=1 WHERE target_id=? AND status='RUNNING'", (target_id,)
                )
            self.store.audit(db, "MONITOR_" + action, target_id, "Explicit local operator action")
        return {"target_id": target_id, "action": action}

    def snapshot(self):
        if self.store.read_only:
            return {
                "targets": [],
                "jobs": [],
                "notices": [],
                "unread": 0,
                "worker": {"status": "DEMO"},
                "demo": True,
            }
        with self.store.connect() as db:
            rows = db.execute("SELECT * FROM monitor_targets ORDER BY created_at").fetchall()
            targets = []
            for row in rows:
                config = PilotConfig.model_validate_json(row["config_json"])
                last = db.execute(
                    "SELECT id,status,run_id,code,queued_at,ended_at FROM monitor_jobs WHERE target_id=? ORDER BY queued_at DESC LIMIT 1",
                    (row["id"],),
                ).fetchone()
                baseline = db.execute(
                    "SELECT run_id FROM baselines WHERE target_id=?", (row["id"],)
                ).fetchone()
                targets.append(
                    {
                        "id": row["id"],
                        "label": row["label"],
                        "state": row["state"],
                        "version": row["version"],
                        "next_at": row["next_at"],
                        "origin": config.origin,
                        "cadence_minutes": config.cadence_minutes,
                        "grant_expires_at": config.grant.expires_at.isoformat(),
                        "steps": len(config.steps),
                        "last_job": dict(last) if last else None,
                        "baseline_id": baseline[0] if baseline else None,
                    }
                )
            worker = db.execute(
                "SELECT heartbeat,expires,status,code FROM monitor_worker WHERE singleton=1"
            ).fetchone()
            w = dict(worker) if worker else {"status": "OFFLINE", "heartbeat": None, "code": None}
            if worker and worker["expires"] <= time.time():
                w["status"] = "OFFLINE"
            jobs = [
                dict(r)
                for r in db.execute(
                    "SELECT id,target_id,status,queued_at,started_at,ended_at,run_id,code,cancel FROM monitor_jobs ORDER BY queued_at DESC LIMIT 50"
                )
            ]
            # Unread first so completed read history never hides an actionable notice.
            notices = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM monitor_notices ORDER BY (read_at IS NULL) DESC,last_at DESC LIMIT 100"
                )
            ]
            unread = db.execute("SELECT count(*) FROM monitor_notices WHERE read_at IS NULL").fetchone()[0]
        return {
            "targets": targets,
            "jobs": jobs,
            "notices": notices,
            "unread": unread,
            "worker": w,
            "demo": False,
        }

    def config(self, target_id):
        self.store.writable()
        with self.store.connect() as db:
            return PilotConfig.model_validate_json(self.target(db, target_id)["config_json"]).model_dump(
                mode="json"
            )

    def acknowledge(self, notice_id):
        self.store.writable()
        validate_id(notice_id)
        with self.store.connect() as db:
            result = db.execute("UPDATE monitor_notices SET read_at=? WHERE id=?", (time.time(), notice_id))
            if not result.rowcount:
                raise CEMError("NOT_FOUND", "Notification not found.", 404)
        return {"id": notice_id, "read": True}

    def review(self, body: ReviewDecision):
        self.store.writable()
        a, b = self.store.verified_get(body.baseline_id), self.store.verified_get(body.candidate_id)
        if a.id == b.id or a.profile.target_id != b.profile.target_id:
            raise CEMError("INVALID_REVIEW_PAIR", "Review requires different runs of the same target.")
        reason = safe_text(body.reason, 500).strip()
        if len(reason) < 3:
            raise CEMError("INVALID_INPUT", "Provide a review reason with at least three characters.")
        identifier = new_id()
        with self.store.lock, self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT count(*) FROM monitor_reviews").fetchone()[0] >= 10000:
                raise CEMError(
                    "HISTORY_CAP", "Review history is full; archive this evidence store before continuing."
                )
            db.execute(
                "INSERT INTO monitor_reviews VALUES(?,?,?,?,?,?)",
                (identifier, a.id, b.id, body.decision, reason, time.time()),
            )
            self.store.audit(db, "REVIEW_RECORDED", identifier, body.decision)
        return {"id": identifier, "decision": body.decision, "reason": reason}

    def reviews(self, baseline, candidate):
        validate_id(baseline)
        validate_id(candidate)
        if self.store.read_only:
            return {"items": [], "total": 0, "demo": True}
        with self.store.connect() as db:
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM monitor_reviews WHERE baseline_id=? AND candidate_id=? ORDER BY at DESC LIMIT 100",
                    (baseline, candidate),
                )
            ]
            total = db.execute(
                "SELECT count(*) FROM monitor_reviews WHERE baseline_id=? AND candidate_id=?",
                (baseline, candidate),
            ).fetchone()[0]
        return {
            "items": rows,
            "total": total,
            "demo": False,
            "notice": "Annotations are local operator decisions, not security verdicts.",
        }

    def acquire(self, token):
        self.store.writable()
        now = time.time()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM monitor_worker WHERE singleton=1").fetchone()
            if row and row["expires"] > now and row["token"] != token:
                raise CEMError("WORKER_BUSY", "Another local pilot runner owns this store.", 409)
            db.execute(
                "INSERT INTO monitor_worker VALUES(1,?,?,?,'RECOVERING',NULL) ON CONFLICT(singleton) DO UPDATE SET token=excluded.token,heartbeat=excluded.heartbeat,expires=excluded.expires,status=excluded.status,code=NULL",
                (token, now, now + 60),
            )

    def export_reviews(self, baseline, candidate):
        a, b = self.store.verified_get(baseline), self.store.verified_get(candidate)
        comparison = compare(a, b)
        rows = []
        if not self.store.read_only:
            with self.store.connect() as db:
                rows = [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM monitor_reviews WHERE baseline_id=? AND candidate_id=? ORDER BY at,id",
                        (a.id, b.id),
                    )
                ]
        return {
            "schema_version": "review-1",
            "baseline": {
                "id": a.id,
                "provenance": a.provenance,
                "profile": a.profile.model_dump(mode="json"),
                "integrity": self.store.integrity(a.id),
            },
            "candidate": {
                "id": b.id,
                "provenance": b.provenance,
                "profile": b.profile.model_dump(mode="json"),
                "integrity": self.store.integrity(b.id),
                "limitations": b.limitation_codes,
            },
            "comparison": comparison.model_dump(mode="json"),
            "reviews": rows,
            "baseline_pilot_context": self.run_context(a.id),
            "candidate_pilot_context": self.run_context(b.id),
            "notice": "Sanitized comparison and local operator annotations; not a security or compliance verdict.",
        }

    @staticmethod
    def retain_context(db, job):
        stored = db.execute("SELECT payload_json FROM runs WHERE id=?", (job["run_id"],)).fetchone()
        if not stored or json.loads(stored[0]).get("provenance") != "COLLECTED_PILOT":
            return
        db.execute(
            "INSERT OR IGNORE INTO monitor_run_context VALUES(?,?,?,?)",
            (
                job["run_id"],
                job["target_id"],
                job["version"],
                hashlib.sha256(job["config_json"].encode()).hexdigest(),
            ),
        )

    def run_context(self, run_id):
        validate_id(run_id)
        if self.store.read_only:
            return None
        with self.store.connect() as db:
            row = db.execute(
                """SELECT c.version,c.config_sha256,h.config_json
                FROM monitor_run_context c JOIN monitor_config_history h
                ON h.target_id=c.target_id AND h.version=c.version WHERE c.run_id=?""",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        config = PilotConfig.model_validate_json(row["config_json"])
        return {
            "target_id": config.target_id,
            "configuration_version": row["version"],
            "configuration_sha256": row["config_sha256"],
            "approved_origins": config.grant.origins,
            "issued_at": config.grant.issued_at.isoformat(),
            "expires_at": config.grant.expires_at.isoformat(),
            "purpose": config.grant.purpose,
            "actions": sorted({s.action for s in config.steps}),
            "notice": "Local operator attestation retained with the run; not authenticated legal proof.",
        }

    def heartbeat(self, token, status="READY", code=None):
        with self.store.connect() as db:
            result = db.execute(
                "UPDATE monitor_worker SET heartbeat=?,expires=?,status=?,code=? WHERE singleton=1 AND token=?",
                (time.time(), time.time() + 60, status, code, token),
            )
            if not result.rowcount:
                raise CEMError("WORKER_LEASE_LOST", "The worker lease changed.")

    def release(self, token):
        with self.store.connect() as db:
            db.execute(
                "UPDATE monitor_worker SET expires=0,status='OFFLINE' WHERE singleton=1 AND token=?", (token,)
            )

    def abandoned(self):
        with self.store.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM monitor_jobs WHERE status='RUNNING' OR code='CLEANUP_UNCONFIRMED'"
                )
            ]

    def interrupted(self, job_id):
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM monitor_jobs WHERE id=?", (job_id,)).fetchone()
            if row:
                if db.execute("SELECT 1 FROM runs WHERE id=?", (row["run_id"],)).fetchone():
                    self.retain_context(db, row)
                db.execute(
                    "UPDATE monitor_jobs SET status='INTERRUPTED',ended_at=?,code='RUNNER_RESTARTED' WHERE id=?",
                    (time.time(), job_id),
                )
                self.notice(
                    db,
                    row["target_id"],
                    "runner-restarted",
                    "INTERRUPTED",
                    "A prior observation was interrupted. Its coverage is unknown.",
                    candidate=row["run_id"],
                )
                self.store.audit(
                    db, "MONITOR_RECOVERY", job_id, "Owned isolation cleanup confirmed; prior job interrupted"
                )

    def next_job(self, token):
        now = time.time()
        with self.store.lock, self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            lease = db.execute(
                "SELECT * FROM monitor_worker WHERE singleton=1 AND token=? AND expires>?", (token, now)
            ).fetchone()
            if not lease or lease["status"] != "READY":
                raise CEMError("WORKER_LEASE_LOST", "This worker does not own a ready lease.")
            for row in db.execute(
                "SELECT * FROM monitor_targets WHERE state='ACTIVE' AND next_at<=? ORDER BY next_at", (now,)
            ).fetchall():
                config = PilotConfig.model_validate_json(row["config_json"])
                try:
                    require_grant(config)
                    self.capacity(db, row["id"])
                except CEMError as exc:
                    db.execute(
                        "UPDATE monitor_targets SET state='PAUSED',next_at=NULL WHERE id=?", (row["id"],)
                    )
                    self.notice(
                        db,
                        row["id"],
                        exc.code,
                        exc.code,
                        "Monitoring paused: renew authorization or review operational capacity.",
                    )
                    continue
                if now - row["next_at"] >= config.cadence_minutes * 60:
                    self.notice(
                        db,
                        row["id"],
                        "missed-cadence",
                        "MISSED_CADENCE",
                        "One or more scheduled windows were missed. No observations were backfilled.",
                    )
                self.queue(db, row)
                # Coalesce missed windows; never create an unbounded catch-up burst.
                db.execute(
                    "UPDATE monitor_targets SET next_at=? WHERE id=?",
                    (now + config.cadence_minutes * 60, row["id"]),
                )
            row = db.execute(
                "SELECT * FROM monitor_jobs WHERE status='QUEUED' ORDER BY queued_at LIMIT 1"
            ).fetchone()
            if row:
                db.execute(
                    "UPDATE monitor_jobs SET status='RUNNING',started_at=? WHERE id=?", (now, row["id"])
                )
                return dict(row)
        return None

    def cancelled(self, job_id):
        with self.store.connect() as db:
            row = db.execute("SELECT cancel FROM monitor_jobs WHERE id=?", (job_id,)).fetchone()
            return not row or bool(row[0])

    def finish(self, job, run=None, code=None):
        baseline = None
        comparison = None
        if run:
            with self.store.connect() as db:
                row = db.execute(
                    "SELECT run_id FROM baselines WHERE target_id=?", (job["target_id"],)
                ).fetchone()
                baseline = row[0] if row else None
            if baseline and baseline != run.id:
                try:
                    comparison = compare(self.store.verified_get(baseline), self.store.verified_get(run.id))
                except CEMError:
                    code = "INTEGRITY_FAILED"
        with self.store.lock, self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if run:
                self.retain_context(db, job)
            status = (
                "CANCELLED"
                if code == "CANCELLED"
                else "FAILED"
                if code
                else str(run.status)
                if run
                else "FAILED"
            )
            db.execute(
                "UPDATE monitor_jobs SET status=?,ended_at=?,code=? WHERE id=?",
                (status, time.time(), code, job["id"]),
            )
            if code:
                self.notice(
                    db,
                    job["target_id"],
                    "failure-" + code,
                    "RUN_FAILED",
                    "Observation failed: " + code.replace("_", " ").lower() + ".",
                    candidate=run.id if run else None,
                )
                if code in (
                    "GRANT_EXPIRED",
                    "TEST_APPROVAL_REQUIRED",
                    "PILOT_IMAGE_REQUIRED",
                    "CLEANUP_UNCONFIRMED",
                ):
                    db.execute(
                        "UPDATE monitor_targets SET state='PAUSED',next_at=NULL WHERE id=?",
                        (job["target_id"],),
                    )
            elif run:
                if run.status != "COMPLETED":
                    self.notice(
                        db,
                        job["target_id"],
                        "partial-" + "-".join(sorted(run.limitation_codes)),
                        "PARTIAL",
                        "Observation coverage is incomplete. Inspect its limits.",
                        baseline,
                        run.id,
                    )
                if not baseline:
                    self.notice(
                        db,
                        job["target_id"],
                        "baseline-needed",
                        "BASELINE_NEEDED",
                        "An observation is ready. Review its coverage and choose a baseline with a reason.",
                        candidate=run.id,
                    )
                elif comparison and comparison.eligibility != "COMPARABLE":
                    self.notice(
                        db,
                        job["target_id"],
                        "profile-" + run.profile.journey_hash,
                        "INCOMPATIBLE_PROFILE",
                        "Observation profile changed. Review and select a suitable comparison reference.",
                        baseline,
                        run.id,
                    )
                elif comparison and comparison.changes:
                    significant = [
                        c for c in comparison.changes if c.kind in ("ADDED", "CHANGED", "NOT_OBSERVED")
                    ]
                    if significant:
                        evidence = {e.id: e for e in run.evidence}
                        signature = []
                        for change in significant:
                            e = evidence.get(change.candidate_evidence_id)
                            signature.append(
                                [
                                    change.kind,
                                    change.category,
                                    change.identity,
                                    change.state,
                                    e.body_sha256 if e else None,
                                    e.headers if e else None,
                                ]
                            )
                        # Cookie values never participate; attribute metadata is already sanitized.
                        signature.append([c.model_dump() for c in run.cookies])
                        key = hashlib.sha256(
                            json.dumps([baseline, signature], sort_keys=True).encode()
                        ).hexdigest()
                        self.notice(
                            db,
                            job["target_id"],
                            key,
                            "REVIEW_CHANGES",
                            f"{len(significant)} differences need context. A difference does not establish maliciousness.",
                            baseline,
                            run.id,
                        )
                    elif any(c.kind in ("AMBIGUOUS", "UNOBSERVABLE") for c in comparison.changes):
                        self.notice(
                            db,
                            job["target_id"],
                            "uncertain-" + run.profile.journey_hash,
                            "UNCERTAIN",
                            "Some resources could not be compared reliably.",
                            baseline,
                            run.id,
                        )
            self.store.audit(db, "MONITOR_JOB_FINISHED", job["id"], status + (" " + code if code else ""))

    @staticmethod
    def retention_set(db):
        cutoff = time.time() - 30 * 86400
        jobs = [
            r[0]
            for r in db.execute(
                "SELECT id FROM monitor_jobs WHERE ended_at<? AND status NOT IN ('QUEUED','RUNNING') AND (code IS NULL OR code!='CLEANUP_UNCONFIRMED')",
                (cutoff,),
            )
        ]
        notices = [
            r[0]
            for r in db.execute(
                "SELECT id FROM monitor_notices WHERE read_at IS NOT NULL AND last_at<?", (cutoff,)
            )
        ]
        values = {"jobs": sorted(jobs), "notices": sorted(notices)}
        return {
            **values,
            "confirmation": hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest(),
            "notice": "Only completed operational metadata and read inbox items older than 30 days. Evidence, grants, and review decisions remain.",
        }

    def retention_preview(self):
        self.store.writable()
        with self.store.connect() as db:
            return self.retention_set(db)

    def retention_apply(self, confirmation):
        self.store.writable()
        with self.store.lock, self.store.connect() as db:
            # Re-read and compare under a cross-process write reservation, not only a process-local lock.
            db.execute("BEGIN IMMEDIATE")
            preview = self.retention_set(db)
            if confirmation != preview["confirmation"]:
                raise CEMError(
                    "RETENTION_CHANGED", "Review a fresh retention preview before confirming.", 409
                )
            for identifier in preview["jobs"]:
                db.execute("DELETE FROM monitor_jobs WHERE id=?", (identifier,))
            for identifier in preview["notices"]:
                db.execute("DELETE FROM monitor_notices WHERE id=?", (identifier,))
            self.store.audit(
                db,
                "MONITOR_RETENTION",
                "local-history",
                f"{len(preview['jobs'])} jobs; {len(preview['notices'])} notices",
            )
        return {"jobs": len(preview["jobs"]), "notices": len(preview["notices"])}
