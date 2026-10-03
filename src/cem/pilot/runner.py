"""Host-controlled pilot containers. No network fallback, no scan on import."""

from pathlib import Path
import hashlib
import json
import os
import secrets
import subprocess
import time
from .policy import PilotConfig, require_grant
from ..domain import Run, MAX_IMPORT
from ..errors import CEMError
from ..phase import require_runtime, source_snapshot
from ..storage import Store, reject_symlink_chain, validate_id

LABEL = "org.checkout-evidence-monitor.pilot"
TEMP_FS = "rw,nosuid,nodev,size=268435456"
OUTPUT_FS = "rw,nosuid,nodev,noexec,size=52428800,mode=1777"
OUTPUT_READY = (
    "import os,stat,sys; "
    "ready=os.path.exists('/output/status.json') and os.path.exists('/output/run.json'); "
    "sys.exit(1) if not ready else None; "
    "s=os.lstat('/output/run.json'); "
    "sys.exit(2) if not stat.S_ISREG(s.st_mode) or s.st_size>52428800 else None; "
    "print(s.st_size)"
)


def docker(*args, check=True):
    try:
        result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        raise CEMError("ISOLATION_UNAVAILABLE", "Docker is unavailable or unresponsive.") from None
    if check and result.returncode:
        raise CEMError(
            "ISOLATION_UNAVAILABLE", "Pilot isolation could not be established; no fallback was used."
        )
    return result


def inspection(name):
    return json.loads(docker("inspect", name).stdout)[0]


def require_local_engine():
    override = os.environ.get("DOCKER_HOST", "")
    if override:
        endpoint = override
    else:
        context = docker("context", "show").stdout.strip()
        endpoint = json.loads(docker("context", "inspect", context).stdout)[0]["Endpoints"]["docker"]["Host"]
    if not endpoint.startswith(("npipe://", "unix://")):
        raise CEMError(
            "REMOTE_ENGINE_DENIED", "Pilot isolation requires a local Docker socket, not a remote context."
        )


def verify(info, *, image, job_id, mounts, networks, role):
    h, c = info["HostConfig"], info["Config"]
    actual = {
        (os.path.normcase(str(Path(m["Source"]).resolve())), m["Destination"], m["RW"])
        for m in info.get("Mounts", [])
        if m["Type"] == "bind"
    }
    expected = {(os.path.normcase(str(p.resolve())), dest, rw) for p, dest, rw in mounts}
    checks = [
        info["Image"] == image,
        c.get("User") == "1000:1000",
        c.get("Labels", {}).get(LABEL) == job_id,
        c.get("Entrypoint") == ["python", "-m", "cem.pilot.entry"],
        c.get("Cmd") == [role],
        h.get("ReadonlyRootfs") is True,
        not h.get("Privileged"),
        not h.get("CapAdd"),
        "ALL" in h.get("CapDrop", []),
        not h.get("PortBindings"),
        not h.get("PublishAllPorts"),
        not h.get("Devices"),
        not h.get("Links"),
        not h.get("ExtraHosts"),
        h.get("PidMode", "") == "",
        h.get("IpcMode") == "private",
        h.get("PidsLimit") == 256,
        h.get("ShmSize") == 268435456,
        h.get("LogConfig", {}).get("Type") == "none",
        0 < h.get("Memory", 0) <= 1073741824,
        h.get("NanoCpus") == 2000000000,
        any(v.startswith("no-new-privileges") for v in h.get("SecurityOpt", [])),
        any(v.startswith("seccomp=") and "unconfined" not in v for v in h.get("SecurityOpt", [])),
        actual == expected,
        all(m["Type"] in ("bind", "tmpfs") for m in info.get("Mounts", [])),
        set(info["NetworkSettings"]["Networks"]) == set(networks),
        h.get("Dns") == ["127.0.0.1"] if role == "browser" else True,
        h.get("NetworkMode") not in ("host", "none", "default"),
        not h.get("VolumesFrom"),
        not h.get("DeviceRequests"),
        h.get("Tmpfs")
        == ({"/tmp": TEMP_FS, "/output": OUTPUT_FS} if role == "browser" else {"/tmp": TEMP_FS}),
    ]
    if not all(checks):
        raise CEMError("ISOLATION_MISMATCH", "Inspected pilot controls differ from the declared profile.")


def names(job_id):
    validate_id(job_id)
    prefix = "cem-pilot-" + job_id
    return prefix + "-browser", prefix + "-proxy", prefix + "-inside", prefix + "-outside"


def cleanup(job_id):
    """Only remove exact job-owned names after checking their ownership label."""
    require_local_engine()
    browser, proxy, internal, external = names(job_id)
    ok = True
    for name in (browser, proxy):
        result = docker("container", "inspect", name, check=False)
        if result.returncode:
            # Confirm a responsive engine before treating a missing resource as absent.
            absent = docker(
                "container",
                "ls",
                "-a",
                "--filter",
                "name=^/" + name + "$",
                "--format",
                "{{.Names}}",
                check=False,
            )
            if absent.returncode or absent.stdout.strip():
                ok = False
            continue
        info = json.loads(result.stdout)[0]
        if info.get("Config", {}).get("Labels", {}).get(LABEL) != job_id:
            ok = False
            continue
        if docker("rm", "-f", name, check=False).returncode:
            ok = False
    for name in (internal, external):
        result = docker("network", "inspect", name, check=False)
        if result.returncode:
            absent = docker(
                "network", "ls", "--filter", "name=^" + name + "$", "--format", "{{.Name}}", check=False
            )
            if absent.returncode or absent.stdout.strip():
                ok = False
            continue
        info = json.loads(result.stdout)[0]
        if info.get("Labels", {}).get(LABEL) != job_id or info.get("Containers"):
            ok = False
            continue
        if docker("network", "rm", name, check=False).returncode:
            ok = False
    return ok


def run_pilot(
    config: PilotConfig, store: Store, root: Path, job_id: str, run_id: str, cancelled=lambda: False
) -> Run:
    require_runtime(root, profile="PILOT")
    require_local_engine()
    if os.name != "nt" and os.geteuid() == 0:
        raise CEMError("ISOLATION_UNAVAILABLE", "Run the pilot wrapper as a non-root local operator.")
    require_grant(config)
    store.writable()
    validate_id(job_id)
    validate_id(run_id)
    record = root / ".cem-private/pilot-image.json"
    reject_symlink_chain(record)
    try:
        image_record = json.loads(record.read_text(encoding="utf-8"))
        image = image_record["image_id"]
        if image_record["source_snapshot"] != source_snapshot(root) or not image.startswith("sha256:"):
            raise ValueError()
        lock = json.loads((root / "lab/container/image-lock.json").read_text(encoding="utf-8"))
        seccomp = root / "lab/container/seccomp_profile.json"
        if hashlib.sha256(seccomp.read_bytes()).hexdigest() != lock["seccomp_sha256"]:
            raise ValueError()
        if inspection(image)["Id"] != image:
            raise ValueError()
    except (OSError, ValueError, KeyError):
        raise CEMError(
            "PILOT_IMAGE_REQUIRED", "Build the source-bound pilot image in the approved testing phase."
        ) from None
    workspace = store.root / "pilot-jobs" / job_id
    reject_symlink_chain(workspace)
    incoming, outgoing, relay_input = workspace / "input", workspace / "output", workspace / "proxy-input"
    browser, proxy, internal, external = names(job_id)
    result = None
    cleanup_ok = False
    attempted_resources = False
    try:
        incoming.mkdir(parents=True, exist_ok=False)
        relay_input.mkdir()
        outgoing.mkdir(mode=0o700)
        token = secrets.token_hex(32)
        (incoming / "config.json").write_text(config.model_dump_json(), encoding="utf-8")
        (incoming / "identity-key").write_bytes(store.key())
        (incoming / "proxy-token").write_text(token, encoding="ascii")
        (relay_input / "config.json").write_text(config.model_dump_json(), encoding="utf-8")
        (relay_input / "proxy-token").write_text(token, encoding="ascii")
        for path in [*incoming.iterdir(), *relay_input.iterdir()]:
            os.chmod(path, 0o644)
        # Mount readability is required for container UID 1000; enclosing private data directory limits access.
        if cancelled():
            raise CEMError("CANCELLED", "The pilot job was cancelled.")
        require_grant(config)
        engine = docker("info", "--format", "{{.OSType}}/{{.Architecture}}").stdout.strip()
        if engine not in ("linux/x86_64", "linux/amd64"):
            raise CEMError("ISOLATION_UNAVAILABLE", "Pilot requires a local Linux x64 Docker engine.")
        attempted_resources = True
        docker(
            "network",
            "create",
            "--internal",
            "--ipv6=false",
            "--driver",
            "bridge",
            "--opt",
            "com.docker.network.bridge.gateway_mode_ipv4=isolated",
            "--label",
            f"{LABEL}={job_id}",
            internal,
        )
        docker("network", "create", "--driver", "bridge", "--label", f"{LABEL}={job_id}", external)
        for name, isolated in ((internal, True), (external, False)):
            n = json.loads(docker("network", "inspect", name).stdout)[0]
            if (
                n.get("Internal") != isolated
                or n.get("Driver") != "bridge"
                or n.get("Labels", {}).get(LABEL) != job_id
                or (
                    isolated
                    and (
                        n.get("EnableIPv6")
                        or n.get("Options", {}).get("com.docker.network.bridge.gateway_mode_ipv4")
                        != "isolated"
                    )
                )
            ):
                raise CEMError("ISOLATION_MISMATCH", "Pilot bridge configuration differs.")
        common = [
            "--read-only",
            "--user",
            "1000:1000",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--security-opt=seccomp=" + str(seccomp.resolve()),
            "--pids-limit=256",
            "--memory=1g",
            "--cpus=2",
            "--ipc=private",
            "--shm-size=256m",
            "--tmpfs=/tmp:" + TEMP_FS,
            "--log-driver=none",
            "--label",
            f"{LABEL}={job_id}",
            "--env=CEM_PILOT_CONTAINER=1",
            "--env=HTTP_PROXY=",
            "--env=HTTPS_PROXY=",
            "--env=ALL_PROXY=",
            "--env=http_proxy=",
            "--env=https_proxy=",
            "--env=all_proxy=",
        ]
        docker(
            "create",
            "--name",
            proxy,
            "--network",
            internal,
            *common,
            "--mount",
            f"type=bind,source={relay_input.resolve()},target=/job,readonly",
            image,
            "proxy",
        )
        docker("network", "connect", external, proxy)
        verify(
            inspection(proxy),
            image=image,
            job_id=job_id,
            mounts=[(relay_input, "/job", False)],
            networks=[internal, external],
            role="proxy",
        )
        docker("start", proxy)
        ready_by = time.monotonic() + 10
        while True:
            require_grant(config)
            if cancelled():
                raise CEMError("CANCELLED", "The pilot job was cancelled.")
            ready = docker(
                "exec",
                proxy,
                "python",
                "-c",
                "import socket; socket.create_connection(('127.0.0.1',8888),timeout=1).close()",
                check=False,
            )
            if ready.returncode == 0:
                break
            if time.monotonic() >= ready_by:
                raise CEMError("PROXY_UNAVAILABLE", "The isolated proxy did not become ready.")
            time.sleep(0.25)
        proxy_ip = inspection(proxy)["NetworkSettings"]["Networks"][internal]["IPAddress"]
        import ipaddress

        ipaddress.IPv4Address(proxy_ip)
        docker(
            "create",
            "--name",
            browser,
            "--network",
            internal,
            "--dns=127.0.0.1",
            *common,
            "--env=CEM_PROXY_IP=" + proxy_ip,
            "--env=CEM_RUN_ID=" + run_id,
            "--mount",
            f"type=bind,source={incoming.resolve()},target=/job,readonly",
            "--tmpfs=/output:" + OUTPUT_FS,
            image,
            "browser",
        )
        verify(
            inspection(browser),
            image=image,
            job_id=job_id,
            mounts=[(incoming, "/job", False)],
            networks=[internal],
            role="browser",
        )
        require_grant(config)
        docker("start", browser)
        deadline = time.monotonic() + config.budgets.run_seconds + 25
        while True:
            require_grant(config)
            if cancelled():
                raise CEMError("CANCELLED", "The pilot job was cancelled.")
            if time.monotonic() >= deadline:
                raise CEMError("RUN_TIMEOUT", "Pilot collection exceeded its hard deadline.")
            info = inspection(browser)
            if not info["State"]["Running"]:
                raise CEMError("COLLECTOR_FAILED", "Pilot browser stopped before its result was transferred.")
            ready = docker("exec", browser, "python", "-c", OUTPUT_READY, check=False)
            if ready.returncode == 0:
                if not ready.stdout.strip().isdigit() or int(ready.stdout.strip()) > MAX_IMPORT:
                    raise CEMError("ARTIFACT_LIMIT", "Pilot output exceeded the retained-byte limit.")
                # No writable host mount. Copy one bounded tmpfs file without following symlinks.
                docker("cp", browser + ":/output/run.json", str(outgoing / "run.json"))
                require_grant(config)
                if cancelled():
                    raise CEMError("CANCELLED", "The pilot job was cancelled.")
                break
            if ready.returncode != 1:
                raise CEMError(
                    "ARTIFACT_LIMIT", "Pilot output is unavailable or is not a bounded regular file."
                )
            time.sleep(0.5)
        path = outgoing / "run.json"
        reject_symlink_chain(path)
        if not path.is_file() or path.stat().st_size > MAX_IMPORT:
            raise CEMError("ARTIFACT_LIMIT", "Pilot result is unavailable or oversized.")
        result = Run.model_validate_json(path.read_bytes())
        from .collector import make_run

        expected = make_run(config, store.key(), run_id)
        if (
            result.id != run_id
            or result.profile.target_id != config.target_id
            or result.profile.journey_hash != config.fingerprint()
            or result.profile != expected.profile
            or result.fixture_id != "PILOT"
        ):
            raise CEMError("RESULT_MISMATCH", "Pilot output did not match the scheduled job.")
    finally:
        try:
            cleanup_ok = cleanup(job_id) if attempted_resources else True
        except Exception:
            cleanup_ok = False
        for path in [
            *(incoming / name for name in ("config.json", "identity-key", "proxy-token")),
            *(relay_input / name for name in ("config.json", "proxy-token")),
            outgoing / "run.json",
        ]:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                cleanup_ok = False
        if not cleanup_ok:
            raise CEMError(
                "CLEANUP_UNCONFIRMED", "Pilot isolation cleanup is unconfirmed. Resolve it before resuming."
            )
    return store.save(result, pilot_origins=config.grant.origins)
