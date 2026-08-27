"""Test metric eval map câu → node (G3) — hàm thuần, không DB/LLM."""

import re

import pytest

from scripts.eval_exam_mapping import compute_metrics, load_labeled


def _case(pred, exp, true_off=None):
    return {
        "id": "x",
        "subject_code": "TOAN",
        "grade": 6,
        "expected_codes": list(exp),
        "predicted_codes": list(pred),
        "null": not pred,
        "true_off": (not exp) if true_off is None else true_off,
    }


def test_exact_and_top1_ignore_order():
    cases = [
        _case(["TOAN6_C1"], ["TOAN6_C1"]),
        _case(["TOAN6_C2"], ["TOAN6_C1"]),  # sai node
        _case(["TOAN6_C4", "TOAN6_C5"], ["TOAN6_C5", "TOAN6_C4"]),  # khớp bất kể thứ tự
    ]
    m = compute_metrics(cases)
    assert m["exact_match_rate"] == pytest.approx(2 / 3, abs=0.001)
    assert m["top1_hit_rate"] == pytest.approx(2 / 3, abs=0.001)


def test_top1_uses_highest_weight_node():
    cases = [_case(["TOAN6_C1", "TOAN6_C2"], ["TOAN6_C1"])]
    m = compute_metrics(cases)
    assert m["top1_hit_rate"] == 1.0
    assert m["overlap_recall"] == 1.0


def test_null_and_off_metrics():
    cases = [
        _case([], [], true_off=True),  # TP
        _case(["TOAN6_C1"], [], true_off=True),  # FN: lẽ ra off nhưng map được
        _case([], ["TOAN6_C1"]),  # FP: báo nhầm off
        _case(["TOAN6_C1"], ["TOAN6_C1"]),  # TN
    ]
    m = compute_metrics(cases)
    assert m["n"] == 4
    assert m["null_rate"] == 0.5
    assert m["off_precision"] == 0.5
    assert m["off_recall"] == 0.5


def test_compute_metrics_empty():
    m = compute_metrics([])
    assert m["n"] == 0
    assert m["exact_match_rate"] is None
    assert m["null_rate"] is None


def test_labeled_set_is_valid():
    labeled = load_labeled()
    assert len(labeled) >= 30
    ids = [c["id"] for c in labeled]
    assert len(ids) == len(set(ids)), "id trùng"
    for case in labeled:
        assert case["grade"] in (6, 7, 8, 9)
        assert case["text"].strip()
        for code in case["expected_codes"]:
            assert re.fullmatch(r"TOAN\d+_C\d+", code), code
        assert case["off_curriculum"] == (not case["expected_codes"])
