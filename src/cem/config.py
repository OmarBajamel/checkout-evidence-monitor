"""Parse declarative configuration; aliases, tags and executable objects are forbidden."""

import json
from pathlib import Path
import yaml
from yaml.tokens import AliasToken, AnchorToken, TagToken
from pydantic import ValidationError
from .domain import Job, MAX_IMPORT
from .errors import CEMError


def bounded_tree(value, depth=0):
    if depth > 16:
        raise CEMError("ARTIFACT_LIMIT", "Document nesting exceeds the limit.")
    if isinstance(value, str) and len(value) > 16384:
        raise CEMError("ARTIFACT_LIMIT", "A document string exceeds the limit.")
    if isinstance(value, dict):
        if len(value) > 2000 or any(not isinstance(k, str) for k in value):
            raise CEMError("INVALID_INPUT", "Document keys are invalid.")
        for k, v in value.items():
            bounded_tree(k, depth + 1)
            bounded_tree(v, depth + 1)
    elif isinstance(value, list):
        if len(value) > 2000:
            raise CEMError("ARTIFACT_LIMIT", "A document list exceeds the limit.")
        for v in value:
            bounded_tree(v, depth + 1)
    elif not isinstance(value, (str, bool, int, float, type(None))):
        raise CEMError("INVALID_INPUT", "Document contains an unsupported value.")


def duplicate_safe(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CEMError("INVALID_INPUT", "Duplicate document keys are not allowed.")
        result[key] = value
    return result


def parse_json(raw: bytes):
    if len(raw) > MAX_IMPORT:
        raise CEMError("ARTIFACT_LIMIT", "The input exceeds 50 MiB.")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=duplicate_safe,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        bounded_tree(value)
        return value
    except (ValueError, RecursionError, UnicodeError):
        raise CEMError("INVALID_INPUT", "The JSON document is malformed.") from None


class UniqueSafeLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    return duplicate_safe(
        (loader.construct_object(k, deep=deep), loader.construct_object(v, deep=deep)) for k, v in node.value
    )


UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load_job(path: Path) -> Job:
    if ".." in path.parts or any(
        p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in (path, *path.parents)
    ):
        raise CEMError("PATH_DENIED", "Linked or traversal job paths are forbidden.")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise CEMError("INVALID_INPUT", "Provide a regular job file no larger than 64 KiB.")
    raw = path.read_bytes()
    try:
        if path.suffix.lower() in (".yaml", ".yml"):
            text = raw.decode("utf-8")
            if any(isinstance(t, (AliasToken, AnchorToken, TagToken)) for t in yaml.scan(text)):
                raise ValueError()
            data = yaml.load(text, Loader=UniqueSafeLoader)
            bounded_tree(data)
        else:
            data = parse_json(raw)
        if not isinstance(data, dict):
            raise ValueError()
        if data.get("profile") != "LAB":
            raise CEMError(
                "PUBLIC_PROFILE_NOT_SUPPORTED", "Only the isolated synthetic LAB profile is supported."
            )
        return Job.model_validate(data)
    except (yaml.YAMLError, ValueError, TypeError, ValidationError, RecursionError):
        raise CEMError("INVALID_INPUT", "The job violates its typed configuration contract.") from None
