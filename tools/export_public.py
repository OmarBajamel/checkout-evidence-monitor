"""Audited static packaging only. Explicit file manifest, no recursive workspace copy."""

from pathlib import Path
import argparse
import hashlib
import json
from publication_guard import check_content


def export(root: Path, manifest: dict, destination: Path):
    root = root.resolve()
    if ".." in destination.parts:
        raise ValueError("Traversal export destination is forbidden")
    destination = destination.absolute()
    if not destination.is_relative_to(root / "publication/export"):
        raise ValueError("Export must use a fresh owned publication/export directory")
    for part in (destination, *destination.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Linked export path forbidden")
    if destination.exists():
        raise ValueError("Existing export preserved; choose a fresh directory")
    reviewed = []
    seen = set()
    for item in manifest["files"]:
        if item["destination"] in seen:
            raise ValueError("Duplicate export destination")
        seen.add(item["destination"])
        source = root / item["source"]
        if not source.resolve().is_relative_to(root):
            raise ValueError("Source escaped workspace")
        for part in (source, *source.parents):
            if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
                raise ValueError("Linked source forbidden")
        data = source.read_bytes()
        check_content(item["destination"], data)
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Source changed after review: " + item["source"])
        reviewed.append((item, data))
    destination.mkdir(parents=True, exist_ok=False)
    for item, data in reviewed:
        target = destination / item["destination"]
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as f:
            f.write(data)
    print(
        json.dumps(
            {"files": len(reviewed), "export": str(destination), "remote_writes": 0, "runtime": "NOT_RUN"}
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", default="publication/PUBLICATION_MANIFEST.json")
    p.add_argument("--destination", required=True)
    a = p.parse_args()
    export(Path.cwd(), json.loads(Path(a.manifest).read_text(encoding="utf-8")), Path(a.destination))
