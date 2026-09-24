"""Future opt-in image build, bound to the current source; never runs the image."""

import json
import hashlib
from urllib.request import urlopen
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from cem.phase import require_runtime, source_snapshot
from cem.errors import CEMError


def main():
    root = Path.cwd()
    require_runtime(root, profile="LAB")
    initial_snapshot = source_snapshot(root)
    engine = subprocess.run(
        ["docker", "info", "--format", "{{.OSType}}/{{.Architecture}}"],
        capture_output=True,
        text=True,
        check=True,
    )
    if engine.stdout.strip() not in ("linux/x86_64", "linux/amd64"):
        raise CEMError("ISOLATION_UNAVAILABLE", "The LAB build requires a local Linux x64 Docker engine.")
    context = root / (".cem-private/lab-build-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    context.mkdir(parents=True, exist_ok=False)
    for name in ("src", "lab"):
        shutil.copytree(root / name, context / name, ignore=shutil.ignore_patterns("__pycache__", "certs"))
    shutil.copyfile(root / "requirements-linux.lock", context / "requirements-linux.lock")
    wheels = context / "wheelhouse"
    wheels.mkdir()
    system = context / "system-debs"
    system.mkdir()
    lock = json.loads((root / "lab/container/system-lock.json").read_text(encoding="utf-8"))
    for package in lock["packages"]:
        with urlopen(package["url"], timeout=60) as response:
            data = response.read(2097153)
        if len(data) > 2097152 or hashlib.sha256(data).hexdigest() != package["sha256"]:
            raise CEMError("DEPENDENCY_MISMATCH", "Pinned certificate utility bytes differ.")
        (system / package["filename"]).write_bytes(data)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            # Complete transitive Linux lock: avoid evaluating dependency OS markers on the Windows host.
            "--no-deps",
            "--platform",
            "manylinux_2_28_x86_64",
            "--platform",
            "manylinux_2_17_x86_64",
            "--platform",
            "manylinux2014_x86_64",
            "--platform",
            "manylinux1_x86_64",
            "--python-version",
            "3.12",
            "--implementation",
            "cp",
            "--abi",
            "cp312",
            "--only-binary=:all:",
            "--require-hashes",
            "-r",
            str(root / "requirements-linux.lock"),
            "--dest",
            str(wheels),
        ],
        check=True,
    )
    subprocess.run(
        [
            "docker",
            "build",
            "--platform=linux/amd64",
            "--network=none",
            "--file",
            str(context / "lab/container/Dockerfile"),
            "--tag",
            "cem-lab:0.1.0",
            str(context),
        ],
        check=True,
    )
    result = subprocess.run(
        ["docker", "image", "inspect", "cem-lab:0.1.0"], capture_output=True, text=True, check=True
    )
    info = json.loads(result.stdout)[0]
    if not info["Id"].startswith("sha256:"):
        raise CEMError("ISOLATION_UNAVAILABLE", "Image digest unavailable")
    if source_snapshot(root) != initial_snapshot:
        raise CEMError(
            "ISOLATION_UNAVAILABLE", "Source changed during image preparation; rebuild before LAB execution."
        )
    (root / ".cem-private/lab-image.json").write_text(
        json.dumps(
            {
                "image_id": info["Id"],
                "source_snapshot": initial_snapshot,
                "base": "lab/container/image-lock.json",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Built source-bound LAB image. No container was started.")


if __name__ == "__main__":
    main()
