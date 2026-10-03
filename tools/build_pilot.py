"""Opt-in source-bound image preparation. Requires a future PILOT runtime session."""

from pathlib import Path
from datetime import datetime, timezone
import json
import shutil
import subprocess
import sys
from cem.phase import require_runtime, source_snapshot
from cem.errors import CEMError
from cem.pilot.runner import require_local_engine


def main():
    root = Path.cwd().resolve()
    require_runtime(root, profile="PILOT")
    require_local_engine()
    snapshot = source_snapshot(root)
    context = (
        root / ".cem-private" / ("pilot-build-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    )
    context.mkdir(parents=True, exist_ok=False)
    shutil.copytree(root / "src", context / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(root / "requirements-linux.lock", context / "requirements-linux.lock")
    shutil.copyfile(root / "lab/container/Dockerfile.pilot", context / "Dockerfile")
    wheels = context / "wheelhouse"
    wheels.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
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
            "--tag=cem-pilot:0.2.0",
            str(context),
        ],
        check=True,
    )
    image = subprocess.run(
        ["docker", "image", "inspect", "cem-pilot:0.2.0"], capture_output=True, text=True, check=True
    )
    image_id = json.loads(image.stdout)[0]["Id"]
    if source_snapshot(root) != snapshot or not image_id.startswith("sha256:"):
        raise CEMError("SOURCE_CHANGED", "Source changed during preparation; rebuild before running.")
    (root / ".cem-private/pilot-image.json").write_text(
        json.dumps(
            {
                "image_id": image_id,
                "source_snapshot": snapshot,
                "built_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Source-bound pilot image prepared. No container was started.")


if __name__ == "__main__":
    main()
