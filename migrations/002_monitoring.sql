-- Static readable copy of operations.SCHEMA; not executed by this authoring step.

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
