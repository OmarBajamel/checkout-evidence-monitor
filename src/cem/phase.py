"""Accidental-execution guard; local files do not authenticate a human."""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
from .errors import CEMError


def source_snapshot(root: Path) -> str:
    digest = hashlib.sha256()
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
        base = root / folder
        if base.exists():
            for p in sorted(base.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
                if p.is_file() and "__pycache__" not in p.parts:
                    digest.update(
                        p.relative_to(root).as_posix().encode()
                        + b"\0"
                        + hashlib.sha256(p.read_bytes()).digest()
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
            digest.update(name.encode() + b"\0" + hashlib.sha256(p.read_bytes()).digest())
    return digest.hexdigest()


def require_runtime(root: Path | None = None, *, profile="OFFLINE"):
    root = (root or Path.cwd()).resolve()
    p = Path(os.environ.get("CEM_TEST_SESSION", ""))
    try:
        if not p.is_file() or p.is_symlink() or p.stat().st_size > 8192:
            raise ValueError()
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("instruction", "").upper() != "TEST APPROVED" or d.get("profile") not in (
            profile,
            "OFFLINE_AND_LAB",
        ):
            raise ValueError()
        if datetime.fromisoformat(d["expires_at"]) <= datetime.now(timezone.utc):
            raise ValueError()
        if d["source_snapshot"] != source_snapshot(root):
            raise ValueError()
        a = root / "state/APPROVAL_RECORD.json"
        if a.exists() and not json.loads(a.read_text(encoding="utf-8-sig"))["testing"]["authorized"]:
            raise ValueError()
        return d
    except (ValueError, KeyError, OSError, TypeError):
        raise CEMError(
            "TEST_APPROVAL_REQUIRED",
            "Runtime/preview execution needs an unexpired TEST APPROVED session for this source snapshot.",
            403,
        ) from None
