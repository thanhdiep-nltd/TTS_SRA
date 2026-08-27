"""Đánh giá độ chính xác map câu hỏi → node (G3 — docs_vsf/plan_cdi_kg_anchored.md).

Chạy: python scripts/eval_exam_mapping.py [--limit N] [--labeled path]
Cần DB (shortlist) + LLM (map_items). In metric tổng + theo môn/khối.
Hàm metric thuần (compute_metrics) được test trong tests/test_exam_eval.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

if __name__ == "__main__" and __package__ is None:
    # Chạy trực tiếp → thêm repo root vào sys.path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.session import SessionLocal  # noqa: E402
from src.services.content_difficulty import build_shortlist, map_items  # noqa: E402

_DEFAULT_LABELED = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "exam_labeled.jsonl"


def load_labeled(path: Path | None = None) -> list[dict[str, Any]]:
    """Đọc bộ nhãn vàng (jsonl): id, subject_code, grade, semester, text, expected_codes, off_curriculum."""
    p = path or _DEFAULT_LABELED
    cases: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        case = json.loads(line)
        case.setdefault("off_curriculum", not case.get("expected_codes"))
        cases.append(case)
    return cases


def _subject_id(db, subject_code: str, grade: int) -> int | None:
    row = db.execute(
        text("SELECT id FROM s360.dim_subject WHERE code = :code"), {"code": f"{subject_code}_{grade}"}
    ).first()
    return int(row[0]) if row else None


def run_eval(db, labeled: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    """Chạy pipeline map_items cho từng câu nhãn vàng; trả case kết quả (code thay vì id)."""
    results: list[dict[str, Any]] = []
    for case in labeled[:limit] if limit else labeled:
        grade = int(case["grade"])
        subject_id = _subject_id(db, case["subject_code"], grade)
        shortlist = build_shortlist(db, subject_id, grade, case.get("semester")) if subject_id else []
        code_by_id = {unit.id: unit.code for unit in shortlist}
        items = map_items(case["text"], shortlist) if shortlist else []
        item = items[0] if items else None
        pred_codes = [code_by_id[n.node_id] for n in sorted(item.nodes, key=lambda n: -n.weight)] if item else []
        results.append(
            {
                "id": case["id"],
                "subject_code": case["subject_code"],
                "grade": grade,
                "expected_codes": list(case["expected_codes"]),
                "predicted_codes": pred_codes,
                "null": not pred_codes,
                "true_off": bool(case["off_curriculum"]),
            }
        )
    return results


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def compute_metrics(cases: list[dict[str, Any]]) -> dict[str, float | None]:
    """Metric theo G3: exact match, top-1, overlap recall, null-rate, off precision/recall."""
    on_curriculum = [c for c in cases if not c["true_off"]]
    exact = _mean([set(c["predicted_codes"]) == set(c["expected_codes"]) for c in on_curriculum])
    top1 = _mean(
        [bool(c["predicted_codes"]) and c["predicted_codes"][0] in set(c["expected_codes"]) for c in on_curriculum]
    )
    overlap = _mean(
        [
            len(set(c["predicted_codes"]) & set(c["expected_codes"])) / len(c["expected_codes"])
            for c in on_curriculum
            if c["expected_codes"]
        ]
    )
    null_rate = _mean([c["null"] for c in cases])
    tp = sum(1 for c in cases if c["true_off"] and c["null"])
    fp = sum(1 for c in cases if not c["true_off"] and c["null"])
    fn = sum(1 for c in cases if c["true_off"] and not c["null"])
    precision = round(tp / (tp + fp), 3) if tp + fp else None
    recall = round(tp / (tp + fn), 3) if tp + fn else None
    return {
        "n": len(cases),
        "exact_match_rate": exact,
        "top1_hit_rate": top1,
        "overlap_recall": overlap,
        "null_rate": null_rate,
        "off_precision": precision,
        "off_recall": recall,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Eval độ chính xác map câu hỏi → node (G3)")
    parser.add_argument("--labeled", type=Path, default=_DEFAULT_LABELED)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    labeled = load_labeled(args.labeled)
    db = SessionLocal()
    try:
        cases = run_eval(db, labeled, args.limit)
    finally:
        db.close()

    metrics = compute_metrics(cases)
    print("== Metric tổng ==")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    print("== Theo môn/khối ==")
    by_key: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for case in cases:
        by_key.setdefault((case["subject_code"], case["grade"]), []).append(case)
    for (subj, grade), group in sorted(by_key.items()):
        m = compute_metrics(group)
        print(f"  {subj} {grade}: exact={m['exact_match_rate']} top1={m['top1_hit_rate']} null={m['null_rate']} (n={len(group)})")


if __name__ == "__main__":
    main()
