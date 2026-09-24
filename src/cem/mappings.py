"""Narrow, attributed relationships. None is a standard compliance verdict."""

from importlib.resources import files
import json


def relationships(rule: str) -> list[dict[str, str]]:
    data = json.loads(files("cem").joinpath("data/asvs-subset.json").read_text(encoding="utf-8"))
    return [
        {k: str(v) for k, v in row.items() if k != "rules"}
        for row in data["relationships"]
        if rule in row["rules"]
    ]
