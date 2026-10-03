"""Host-owned Docker lifecycle. Inspect the stopped container BEFORE any application starts."""

from pathlib import Path
import hashlib
import json
import os
import subprocess
import time
from .domain import Job, Run, MAX_IMPORT, new_id, utc_now, RunStatus
from .authorization import validate_job
from .errors import CEMError
from .phase import require_runtime, source_snapshot
from .storage import Store, reject_symlink_chain
from .collector.journey import make_run

LABEL = "org.checkout-evidence-monitor"


def docker(args, timeout=30, check=True):
    try:
        result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
        if check and result.returncode:
            raise CEMError(
                "ISOLATION_UNAVAILABLE", "Docker operation failed; no safeguard fallback is available."
            )
        return result
    except (OSError, subprocess.TimeoutExpired):
        raise CEMError(
            "ISOLATION_UNAVAILABLE", "The required Docker engine is unavailable or unresponsive."
        ) from None


def verify_inspection(info, input_dir: Path, output_dir: Path, uid: str):
    host = info["HostConfig"]
    config = info["Config"]
    allowed = {(str(input_dir.resolve()), "/job", False), (str(output_dir.resolve()), "/output", True)}
    mounts = {
        (str(Path(m["Source"]).resolve()), m["Destination"], m["RW"])
        for m in info.get("Mounts", [])
        if m.get("Type") == "bind"
    }
    required = (
        host.get("NetworkMode") == "none",
        host.get("ReadonlyRootfs") is True,
        not host.get("Privileged"),
        not host.get("PortBindings"),
        not host.get("Devices"),
        host.get("PidMode", "") == "",
        host.get("IpcMode") == "private",
        "ALL" in host.get("CapDrop", []),
        not host.get("CapAdd"),
        config.get("User") == uid,
        any(x.startswith("no-new-privileges") for x in host.get("SecurityOpt", [])),
        any(x.startswith("seccomp=") and "unconfined" not in x for x in host.get("SecurityOpt", [])),
        0 < host.get("Memory", 0) <= 1073741824,
        host.get("PidsLimit") == 256,
        host.get("NanoCpus") == 2000000000,
        host.get("ShmSize") == 268435456,
        mounts == allowed,
        len([m for m in info.get("Mounts", []) if m.get("Type") not in ("bind", "tmpfs")]) == 0,
        config.get("Labels", {}).get(LABEL) == "synthetic-lab",
        config.get("Entrypoint") == ["python", "/opt/cem/lab/entry.py"],
        not host.get("PublishAllPorts"),
        not host.get("Links"),
    )
    if not all(required):
        raise CEMError(
            "ISOLATION_UNAVAILABLE", "Container inspection does not match the required isolation contract."
        )


def run_lab(job: Job, store: Store, root: Path, image="cem-lab:0.1.0") -> Run:
    require_runtime(root, profile="LAB")
    validate_job(job)
    if os.name != "nt" and os.getuid() == 0:
        raise CEMError("ISOLATION_UNAVAILABLE", "Run the LAB wrapper as a non-root local user.")
    if image != "cem-lab:0.1.0":
        raise CEMError("INVALID_INPUT", "Only the reviewed local LAB image tag is accepted.")
    image_record = root / ".cem-private/lab-image.json"
    reject_symlink_chain(image_record)
    if not image_record.is_file():
        raise CEMError("ISOLATION_UNAVAILABLE", "Build and record the source-bound LAB image first.")
    image_data = json.loads(image_record.read_text(encoding="utf-8"))
    if image_data.get("source_snapshot") != source_snapshot(root):
        raise CEMError("ISOLATION_UNAVAILABLE", "LAB image source snapshot is stale.")
    image = image_data.get("image_id", "")
    if (
        not image.startswith("sha256:")
        or len(image) != 71
        or any(c not in "0123456789abcdef" for c in image[7:])
    ):
        raise CEMError("ISOLATION_UNAVAILABLE", "LAB image identity is invalid.")
    seccomp = root / "lab/container/seccomp_profile.json"
    reject_symlink_chain(seccomp)
    lock = json.loads((root / "lab/container/image-lock.json").read_text(encoding="utf-8-sig"))
    if hashlib.sha256(seccomp.read_bytes()).hexdigest() != lock["seccomp_sha256"]:
        raise CEMError("ISOLATION_UNAVAILABLE", "The reviewed seccomp profile was modified.")
    key = store.key()
    job_root = store.root / "jobs" / new_id()
    reject_symlink_chain(job_root)
    inp = job_root / "input"
    out = job_root / "output"
    inp.mkdir(parents=True, mode=0o700)
    out.mkdir(mode=0o700)
    (inp / "job.json").write_text(job.model_dump_json(), encoding="utf-8")
    fd = os.open(inp / "identity-key", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    uid = f"{os.getuid()}:{os.getgid()}" if os.name != "nt" else "1000:1000"
    args = [
        "create",
        "--network",
        "none",
        "--read-only",
        "--user",
        uid,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--security-opt",
        "seccomp=" + str(seccomp),
        "--pids-limit",
        "256",
        "--memory",
        "1g",
        "--cpus",
        "2",
        "--ipc",
        "private",
        "--shm-size",
        "256m",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=268435456,mode=1777",
        "--label",
        LABEL + "=synthetic-lab",
        "--add-host",
        "shop.cem.test:127.0.0.1",
        "--add-host",
        "pay.cem.test:127.0.0.1",
        "--env",
        "CEM_ISOLATED_JOB=1",
        "--env",
        "HTTP_PROXY=",
        "--env",
        "HTTPS_PROXY=",
        "--env",
        "ALL_PROXY=",
        "--env",
        "http_proxy=",
        "--env",
        "https_proxy=",
        "--env",
        "all_proxy=",
        "--mount",
        f"type=bind,src={inp.resolve()},dst=/job,readonly",
        "--mount",
        f"type=bind,src={out.resolve()},dst=/output",
        image,
    ]
    cid = None
    reason = None
    cleanup_unconfirmed = False
    try:
        cid = docker(args).stdout.strip()
        if not cid or any(c not in "0123456789abcdef" for c in cid):
            raise CEMError("ISOLATION_UNAVAILABLE", "Docker returned an invalid container identifier.")
        info = json.loads(docker(["inspect", cid]).stdout)[0]
        verify_inspection(info, inp, out, uid)
        # Stopped image inspection cannot run code. No process starts before this succeeds.
        docker(["start", cid])
        deadline = time.monotonic() + job.budgets.run_seconds + 30
        while time.monotonic() < deadline:
            status = json.loads(docker(["inspect", cid]).stdout)[0]["State"]
            if not status["Running"]:
                if status["ExitCode"] != 0:
                    reason = "LAB_PROCESS_FAILED"
                break
            if (
                sum(p.stat().st_size for p in out.iterdir() if p.is_file() and not p.is_symlink())
                > MAX_IMPORT
            ):
                reason = "OUTPUT_CAP"
                break
            time.sleep(0.25)
        else:
            reason = "LAB_TIMEOUT"
    except KeyboardInterrupt:
        reason = "CANCELLED"
    finally:
        if cid:
            for operation in (["stop", "--time", "10", cid], ["rm", cid]):
                try:
                    if docker(operation, check=False).returncode:
                        cleanup_unconfirmed = True
                except CEMError:
                    cleanup_unconfirmed = True
        # Only the two known input files are removed; owned job directory retained for recovery.
        for name in ("identity-key", "job.json"):
            p = inp / name
            reject_symlink_chain(p)
            p.unlink(missing_ok=True)
    record = out / "run.json"
    reject_symlink_chain(record)
    if not record.exists():
        run = make_run(job, key)
        run.status = RunStatus.CANCELLED if reason == "CANCELLED" else RunStatus.FAILED
        run.limitation_codes = [reason or "LAB_OUTPUT_MISSING"]
        if cleanup_unconfirmed:
            run.limitation_codes.append("CLEANUP_UNCONFIRMED")
        run.ended_at = utc_now()
        return store.save(run, trusted_lab=True)
    if record.stat().st_size > MAX_IMPORT:
        raise CEMError("ARTIFACT_LIMIT", "LAB output exceeds its bound.")
    from .config import parse_json
    from pydantic import ValidationError

    try:
        run = Run.model_validate(parse_json(record.read_bytes()))
    except ValidationError:
        raise CEMError("INVALID_INPUT", "LAB output violates its evidence contract.") from None
    if reason:
        run.status = RunStatus.CANCELLED if reason == "CANCELLED" else RunStatus.PARTIAL
        run.limitation_codes = list(dict.fromkeys([*run.limitation_codes, reason]))
        run.complete_states = []
    if cleanup_unconfirmed:
        run.limitation_codes = list(dict.fromkeys([*run.limitation_codes, "CLEANUP_UNCONFIRMED"]))
        run.complete_states = []
        if run.status == RunStatus.COMPLETED:
            run.status = RunStatus.PARTIAL
    return store.save(run, trusted_lab=True)
