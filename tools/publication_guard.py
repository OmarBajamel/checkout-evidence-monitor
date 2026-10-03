"""Pure local publication preflight. No credentials, provider client or network calls."""

import hashlib
import json
import re
from pathlib import PurePosixPath

PRIVATE = {
    "state",
    "research",
    ".research-cache",
    ".agents",
    ".codex",
    ".cem-private",
    ".cem-data",
    ".cem-demo",
    ".build-tools",
    ".venv",
    "node_modules",
    ".git",
    "content",
    "reports",
    "publication",
}
SECRET_PATTERNS = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(rb"AKIA[A-Z0-9]{16}"),
]


def public_path(path):
    p = PurePosixPath(path)
    if (
        p.is_absolute()
        or not p.parts
        or p.parts[0].casefold() in PRIVATE
        or any(
            x.casefold() in ("..", ".", ".git", "node_modules", "__pycache__")
            or x.casefold().startswith((".env", ".cem-"))
            for x in p.parts
        )
        or "\\" in path
        or ":" in path
    ):
        raise ValueError("Unsafe export path")
    if p.suffix.lower() in (
        ".db",
        ".sqlite",
        ".sqlite3",
        ".har",
        ".zip",
        ".tar",
        ".gz",
        ".whl",
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".pem",
        ".key",
        ".log",
    ):
        raise ValueError("Unreviewed private, archive or binary format")
    return p


def check_content(path, data):
    public_path(path)
    if any(pattern.search(data) for pattern in SECRET_PATTERNS):
        raise ValueError("Potential credential material")
    if path.endswith(".svg") and re.search(
        rb"<(?:script|foreignObject|image)\b|(?:href|src)=|@import|url\(", data, re.I
    ):
        raise ValueError("External or active SVG content")


def canonical_hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def preflight(grant, plan, manifest, owner, repo):
    if not grant.get("authorized") or grant.get("instruction", "").upper() != "APPROVED PUBLISH":
        raise ValueError("Publication approval missing")
    if plan.get("status") != "READY_FOR_OWNER_REVIEW_NOT_AUTHORIZED":
        raise ValueError("Publication plan is not ready; refresh and review its exact export first")
    if grant.get("plan_sha256") != canonical_hash(plan) or grant.get("export_sha256") != canonical_hash(
        manifest
    ):
        raise ValueError("Publication binding differs")
    if not owner or owner.get("type") != "User" or not owner.get("login"):
        raise ValueError("Authenticated personal account required")
    if plan.get("owner_selector") != "AUTHENTICATED_PERSONAL_ACCOUNT" or plan.get("visibility") != "public":
        raise ValueError("Owner or visibility outside plan")
    if grant.get("resolved_owner") != owner["login"]:
        raise ValueError("Resolved owner differs")
    if repo not in plan.get("allowed_repository_names", []):
        raise ValueError("Repository outside plan")
    supported_statuses = {
        "NOT_RUN_BY_USER_CHOICE",
        "TESTED_PASS_LOCAL",
        "TESTED_WITH_FAILURES",
        "TESTING_BLOCKED",
    }
    runtime_status = manifest.get("runtime_status")
    if (
        manifest.get("source_snapshot") != grant.get("source_snapshot")
        or runtime_status not in supported_statuses
        or runtime_status != plan.get("runtime_status")
    ):
        raise ValueError("Source snapshot or explicitly bound verification status differs")
    for item in manifest["files"]:
        public_path(item["destination"])
    if not manifest["files"]:
        raise ValueError("Empty export")
    return {
        "owner": owner["login"],
        "repo": repo,
        "visibility": "public",
        "remote_ci": False,
        "hosting": False,
        "linkedin": False,
        "runtime_status": runtime_status,
        "status": "AUTHORIZED_BOUNDED_PUBLICATION",
    }


def publish_with_adapter(adapter, grant, plan, manifest, owner, repo):
    intent = preflight(grant, plan, manifest, owner, repo)
    # Adapter must reject unrelated existing repositories and avoid force push.
    return adapter.create_new_public_repository(intent, manifest)
