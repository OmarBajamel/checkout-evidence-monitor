from benchmarks.metrics import ratio, scores, timing
from tests.helpers import run, script


def test_zero_denominator_is_not_perfect():
    assert ratio(0, 0) == {"numerator": 0, "denominator": 0, "value": None}


def test_absent_script_reduces_field_completeness():
    result = scores(
        run(script("base")),
        {"script_names": ["base", "checkout"], "expected_journey_states": ["catalog", "cart", "checkout"]},
        "JOURNEY",
    )
    assert result["field_completeness"]["denominator"] == 8
    assert result["field_completeness"]["numerator"] == 4


def test_failed_attempts_remain_in_reliability():
    result = timing(
        [
            {"status": "COMPLETED", "elapsed_ms": 100},
            {"status": "FAILED", "elapsed_ms": 120},
            {"status": "NOT_RUN", "elapsed_ms": None},
        ]
    )
    assert (
        result["attempts"] == 3 and result["failed_or_partial"] == 2 and result["completed_median_ms"] == 100
    )
