"""Manual local test-session authoring; never invoked by install/build.
Run only following a direct TEST APPROVED instruction. This editable record is not identity proof.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import argparse
import hashlib
import json
import os


def snapshot(root):
    h = hashlib.sha256()
    for folder in (
        "src",
        "frontend/src",
        "lab",
        "tests",
        "benchmarks",
        "tools",
        "schemas",
        "migrations",
        "frontend/public",
        "frontend/.storybook",
    ):
        for p in sorted((root / folder).rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
            if p.is_file() and "__pycache__" not in p.parts:
                h.update(
                    p.relative_to(root).as_posix().encode() + b"\0" + hashlib.sha256(p.read_bytes()).digest()
                )
    for name in (
        "pyproject.toml",
        "requirements-win.lock",
        "requirements-linux.lock",
        "requirements-dev-win.lock",
        "requirements-dev-linux.lock",
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/tsconfig.json",
        "frontend/vite.config.ts",
        "frontend/index.html",
        "frontend/.npmrc",
    ):
        p = root / name
        if p.is_file():
            h.update(name.encode() + b"\0" + hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--instruction", required=True, choices=["TEST APPROVED"])
    a.add_argument("--profile", choices=["OFFLINE", "LAB", "OFFLINE_AND_LAB"], default="OFFLINE_AND_LAB")
    opts = a.parse_args()
    r = Path.cwd()
    original = r / "state/APPROVAL_RECORD.json"
    if (
        original.exists()
        and not json.loads(original.read_text(encoding="utf-8-sig"))["testing"]["authorized"]
    ):
        raise SystemExit("Record the actual direct testing grant in the private workflow first.")
    out = r / ".cem-private/test-session.json"
    out.parent.mkdir(exist_ok=True, mode=0o700)
    data = {
        "instruction": opts.instruction,
        "profile": opts.profile,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
        "source_snapshot": snapshot(r),
    }
    fd = os.open(out, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Set CEM_TEST_SESSION to", out)


if __name__ == "__main__":
    main()
