"""Explicit local worker. No thread, timer, or collection starts on import."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Thread
import secrets
import time
from .errors import CEMError
from .operations import Operations
from .pilot.policy import PilotConfig
from .pilot.runner import run_pilot, cleanup
from .phase import require_runtime


class Worker:
    def __init__(self, operations: Operations, root: Path):
        self.ops, self.root = operations, root
        self.stop_event = Event()
        self.thread = None
        self.token = secrets.token_hex(16)

    def start(self):
        require_runtime(self.root, profile="PILOT")
        self.ops.acquire(self.token)
        self.thread = Thread(target=self.run, name="cem-pilot-worker", daemon=False)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=120)
        if self.thread and self.thread.is_alive():
            self.ops.heartbeat(self.token, "BLOCKED", "CLEANUP_UNCONFIRMED")

    def run(self):
        blocked = False
        try:
            for old in self.ops.abandoned():
                self.ops.heartbeat(self.token, "RECOVERING")
                if not cleanup(old["id"]):
                    raise CEMError("CLEANUP_UNCONFIRMED", "Prior pilot resources require recovery.")
                self.ops.interrupted(old["id"])
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="cem-pilot-job") as pool:
                while not self.stop_event.is_set():
                    require_runtime(self.root, profile="PILOT")
                    self.ops.heartbeat(self.token)
                    job = self.ops.next_job(self.token)
                    if not job:
                        self.stop_event.wait(1)
                        continue
                    cancelled = Event()
                    future = pool.submit(
                        run_pilot,
                        PilotConfig.model_validate_json(job["config_json"]),
                        self.ops.store,
                        self.root,
                        job["id"],
                        job["run_id"],
                        lambda: cancelled.is_set() or self.stop_event.is_set(),
                    )
                    lease_error = None
                    while not future.done():
                        try:
                            require_runtime(self.root, profile="PILOT")
                            self.ops.heartbeat(self.token)
                            if self.ops.cancelled(job["id"]):
                                cancelled.set()
                        except Exception as exc:
                            cancelled.set()
                            lease_error = exc
                        time.sleep(0.5)
                    try:
                        run = future.result()
                        self.ops.finish(job, run=run)
                    except CEMError as exc:
                        self.ops.finish(job, code=exc.code)
                        if exc.code == "CLEANUP_UNCONFIRMED":
                            raise
                    except Exception:
                        self.ops.finish(job, code="WORKER_ERROR")
                    if lease_error:
                        raise lease_error
        except CEMError as exc:
            blocked = True
            try:
                self.ops.heartbeat(self.token, "BLOCKED", exc.code)
            except Exception:
                pass
        except Exception:
            blocked = True
            try:
                self.ops.heartbeat(self.token, "BLOCKED", "WORKER_ERROR")
            except Exception:
                pass
        finally:
            if not blocked:
                try:
                    self.ops.release(self.token)
                except Exception:
                    # No further work is dispatched; an unwritable database's lease expires.
                    pass
