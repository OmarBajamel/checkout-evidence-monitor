"""Pure count definitions. Zero denominators are null, never perfect scores."""

from pathlib import PurePosixPath
from urllib.parse import urlsplit
from statistics import median


def ratio(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def inventory(run):
    return {PurePosixPath(urlsplit(e.url_display).path).stem for e in run.evidence if e.kind == "SCRIPT"}


def scores(run, truth, arm):
    expected = set(truth["script_names"])
    eligible = expected if arm == "JOURNEY" else {"base"}
    predicted = inventory(run)
    states = {s.state for s in run.steps if s.status == "REACHED" and s.state != "stopped"}
    fields = (
        ["reference_observed", "request_observed", "response_observed", "body_sha256"]
        if arm != "HTTP"
        else ["reference_observed"]
    )
    scripts = [e for e in run.evidence if e.kind == "SCRIPT"]
    present = {
        (PurePosixPath(urlsplit(e.url_display).path).stem, field)
        for e in scripts
        for field in fields
        if bool(getattr(e, field))
    }
    return {
        "inventory_identity_policy": "unique fixture resource basename; per-state evidence kept in raw run",
        "journey_coverage": ratio(
            len(states & set(truth["expected_journey_states"])), len(truth["expected_journey_states"])
        ),
        "inventory_precision": ratio(len(predicted & expected), len(predicted)),
        "inventory_recall_arm": ratio(len(predicted & eligible), len(eligible)),
        "inventory_recall_scenario": ratio(len(predicted & expected), len(expected)),
        "field_completeness": ratio(
            sum((name, field) in present for name in eligible for field in fields),
            len(eligible) * len(fields),
        ),
        "elapsed_ms": run.elapsed_ms,
        "retained_events": run.event_count,
        "status": run.status,
        "limitations": run.limitation_codes,
    }


def change_scores(comparison, truth, arm):
    names = {
        "added": {("ADDED", "extra")},
        "added_origin": {("ADDED", "provider")},
        "changed": {("CHANGED", "base")},
        "not_observed": {("NOT_OBSERVED", "checkout")},
    }
    expected = names.get(truth["expected_observation"])
    if arm != "JOURNEY" or expected is None or comparison.eligibility != "COMPARABLE":
        return {
            "applicability": "NOT_APPLICABLE_OR_INCOMPARABLE",
            "precision": ratio(0, 0),
            "recall": ratio(0, 0),
        }
    predicted = {
        (c.kind, PurePosixPath(urlsplit(c.url_display).path).stem)
        for c in comparison.changes
        if c.category == "SCRIPT" and c.kind in ("ADDED", "CHANGED", "NOT_OBSERVED")
    }
    return {
        "applicability": "ELIGIBLE",
        "precision": ratio(len(predicted & expected), len(predicted)),
        "recall": ratio(len(predicted & expected), len(expected)),
        "expected": sorted(expected),
        "predicted": sorted(predicted),
    }


def timing(rows):
    successful = [r["elapsed_ms"] for r in rows if r.get("status") == "COMPLETED"]
    return {
        "attempts": len(rows),
        "completed": len(successful),
        "failed_or_partial": len(rows) - len(successful),
        "completed_median_ms": median(successful) if successful else None,
        "completed_range_ms": [min(successful), max(successful)] if successful else None,
    }
