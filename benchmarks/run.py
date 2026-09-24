"""Manual future LAB experiment. No network outside each inspected network-none job."""

import json
import random
import hashlib
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from cem.phase import require_runtime, source_snapshot
from cem.config import parse_json
from cem.domain import Job
from cem.lab_wrapper import run_lab
from cem.storage import Store
from cem.comparison import compare
from cem.rules import evaluate
from benchmarks.metrics import scores, change_scores, timing


def make_job(root, scenario, arm):
    data = parse_json((root / "examples/synthetic-lab-job.json").read_bytes())
    now = datetime.now(timezone.utc)
    data["grant"].update(
        fixture_id=scenario, issued_at=now.isoformat(), expires_at=(now + timedelta(hours=1)).isoformat()
    )
    data["arm"] = arm
    if scenario == "T09":
        data["consent"] = "ACCEPTED"
    if scenario == "T19":
        data["service_workers"] = "allow"
    if scenario == "T15":
        data["grant"]["origins"].append("http://pay.cem.test:8766")
    return Job.model_validate(data)


def main():
    root = Path.cwd()
    require_runtime(root, profile="LAB")
    snapshot = source_snapshot(root)
    output = root / "reports/benchmark-runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output.mkdir(parents=True, exist_ok=False)
    store = Store(output / "records")
    truth = json.loads((root / "lab/ground-truth.json").read_text(encoding="utf-8"))["scenarios"]
    chosen = [t for t in truth if t["benchmark_applicability"].startswith("THREE")]
    attempts = []
    seed = 20260924
    for repetition in range(3):
        arms = ["HTTP", "PAGE", "JOURNEY"]
        arms = arms[repetition:] + arms[:repetition]
        ordered = chosen[:]
        random.Random(seed + repetition).shuffle(ordered)
        for arm in arms:
            baseline = None
            started = time.monotonic()
            baseline_item = {"scenario": "T01", "arm": arm, "role": "BASELINE", "repetition": repetition}
            try:
                baseline = run_lab(make_job(root, "T01", arm), store, root)
                baseline_item.update(
                    {
                        "scenario": "T01",
                        "arm": arm,
                        "role": "BASELINE",
                        "repetition": repetition,
                        "run_id": baseline.id,
                        **scores(baseline, truth[0], arm),
                    }
                )
            except Exception as exc:
                baseline_item.update(
                    status="FAILED",
                    reason=getattr(exc, "code", "BASELINE_FAILED"),
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                )
            attempts.append(baseline_item)
            with (output / "attempts.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(baseline_item) + "\n")
            for scenario in ordered:
                item = {"scenario": scenario["id"], "arm": arm, "role": "CANDIDATE", "repetition": repetition}
                started = time.monotonic()
                try:
                    if baseline is None:
                        item.update(status="NOT_RUN", reason="BASELINE_UNAVAILABLE", elapsed_ms=None)
                        attempts.append(item)
                        with (output / "attempts.jsonl").open("a", encoding="utf-8") as f:
                            f.write(json.dumps(item) + "\n")
                        continue
                    current = run_lab(make_job(root, scenario["id"], arm), store, root)
                    comparison = compare(baseline, current)
                    findings = evaluate(current, comparison)
                    unsupported = sum(
                        1
                        for f in findings
                        if f.condition == "MATCH"
                        and any(
                            term in f.title.lower()
                            for term in ("compliant", "malicious", "executed successfully")
                        )
                    )
                    item.update(
                        run_id=current.id,
                        **scores(current, scenario, arm),
                        changes=change_scores(comparison, scenario, arm),
                        comparison=comparison.eligibility,
                        unsupported_conclusions={
                            "automated_count": unsupported,
                            "manual_review": "REQUIRED_NOT_INFERRED_FROM_KEYWORDS",
                        },
                        artifact_bytes=store.artifact_path(current.id).stat().st_size,
                        artifact_sha256=current.sanitized_artifact_sha256,
                    )
                except Exception as exc:
                    item.update(
                        status="FAILED",
                        reason=getattr(exc, "code", "EXPERIMENT_ATTEMPT_FAILED"),
                        elapsed_ms=int((time.monotonic() - started) * 1000),
                    )
                attempts.append(item)
                with (output / "attempts.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(item) + "\n")
    report = {
        "source_snapshot": snapshot,
        "seed": seed,
        "repetitions": 3,
        "ground_truth_sha256": hashlib.sha256((root / "lab/ground-truth.json").read_bytes()).hexdigest(),
        "timing": timing(attempts),
        "attempts": attempts,
        "notice": "Purposive local synthetic evaluation. Failed attempts retained. No population or compliance claim.",
    }
    (output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Recorded local experiment:", output)


if __name__ == "__main__":
    main()
