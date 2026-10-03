"""Source-bound isolation policy mocks; these tests never invoke Docker."""

import copy
import pytest
from cem.errors import CEMError
from cem.pilot.runner import verify, require_local_engine, LABEL, TEMP_FS, OUTPUT_FS
from tests.pilot_helpers import pilot


def inspection(tmp_path):
    return {
        "Image": "sha256:" + "a" * 64,
        "Config": {
            "User": "1000:1000",
            "Labels": {LABEL: "b" * 32},
            "Entrypoint": ["python", "-m", "cem.pilot.entry"],
            "Cmd": ["browser"],
        },
        "HostConfig": {
            "ReadonlyRootfs": True,
            "Privileged": False,
            "CapDrop": ["ALL"],
            "CapAdd": [],
            "PidMode": "",
            "IpcMode": "private",
            "PidsLimit": 256,
            "Memory": 1073741824,
            "ShmSize": 268435456,
            "LogConfig": {"Type": "none"},
            "NanoCpus": 2000000000,
            "SecurityOpt": ["no-new-privileges", "seccomp=reviewed-profile"],
            "Dns": ["127.0.0.1"],
            "NetworkMode": "inside",
            "Tmpfs": {"/tmp": TEMP_FS, "/output": OUTPUT_FS},
        },
        "Mounts": [{"Source": str(tmp_path), "Destination": "/job", "RW": False, "Type": "bind"}],
        "NetworkSettings": {"Networks": {"inside": {}}},
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "internet",
        "root",
        "capability",
        "writable",
        "host",
        "dns",
        "mount",
        "sandbox",
        "output",
        "extra_tmpfs",
    ],
)
def test_pilot_inspection_refuses_each_weakened_boundary(tmp_path, mutation):
    info = inspection(tmp_path)
    kwargs = {
        "image": info["Image"],
        "job_id": "b" * 32,
        "mounts": [(tmp_path, "/job", False)],
        "networks": ["inside"],
        "role": "browser",
    }
    verify(info, **kwargs)
    bad = copy.deepcopy(info)
    if mutation == "internet":
        bad["NetworkSettings"]["Networks"]["outside"] = {}
    elif mutation == "root":
        bad["Config"]["User"] = "0:0"
    elif mutation == "capability":
        bad["HostConfig"]["CapAdd"] = ["NET_ADMIN"]
    elif mutation == "writable":
        bad["HostConfig"]["ReadonlyRootfs"] = False
    elif mutation == "host":
        bad["HostConfig"]["NetworkMode"] = "host"
    elif mutation == "dns":
        bad["HostConfig"]["Dns"] = ["8.8.8.8"]
    elif mutation == "mount":
        bad["Mounts"].append(
            {"Source": "/var/run/docker.sock", "Destination": "/socket", "RW": True, "Type": "bind"}
        )
    elif mutation == "sandbox":
        bad["HostConfig"]["SecurityOpt"] = ["seccomp=unconfined"]
    elif mutation == "output":
        bad["HostConfig"]["Tmpfs"]["/output"] = "rw,size=1g"
    elif mutation == "extra_tmpfs":
        bad["HostConfig"]["Tmpfs"]["/job"] = "rw,size=1g"
    with pytest.raises(CEMError):
        verify(bad, **kwargs)


def test_remote_engine_override_is_refused_before_docker(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.example.com:2375")
    monkeypatch.setattr(
        "cem.pilot.runner.docker", lambda *a, **k: pytest.fail("Remote Docker must not be contacted")
    )
    with pytest.raises(CEMError, match="local"):
        require_local_engine()


def test_scope_fingerprint_is_independent_of_operator_label():
    a, b = pilot(), pilot()
    b.label = "Another human-readable label"
    b.grant.owner = "Another authorized operator"
    assert a.fingerprint() == b.fingerprint()
