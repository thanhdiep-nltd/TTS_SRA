#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Golden Set — Kiểm tra độ chính xác EWS v2_ensemble (CLI).

Chạy:
    .venv\\Scripts\\python.exe scripts\\ews_golden_set.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ews.golden_set import run_golden_set  # noqa: E402


def main() -> None:
    res = run_golden_set()

    print("=" * 120)
    print(f"{'ID':<7}{'Tình huống':<36}{'Dự đoán':<10}{'Kỳ vọng':<10}{'KQ':<6}"
          f"{'risk':<7}{'s_score':<8}{'lms':<7}{'att':<7}{'beh':<7}{'w_att':<7}{'w_beh':<7}")
    print("=" * 120)

    for c in res["cases"]:
        fmt = lambda v: "NaN" if v is None else f"{v:.1f}"
        print(f"{c['id']:<7}{c['description']:<36}{c['predicted']:<10}{c['expected']:<10}"
              f"{'PASS' if c['passed'] else 'FAIL':<6}{c['risk_score']:<7.1f}"
              f"{fmt(c['score_risk']):<8}{fmt(c['lms_risk']):<7}{fmt(c['attendance_risk']):<7}"
              f"{fmt(c['behavior_risk']):<7}{c['weight_attendance']:<7.3f}{c['weight_behavior']:<7.3f}")

    print("=" * 120)
    print(f"Accuracy: {res['passed']}/{res['total']} ({res['accuracy'] * 100:.1f}%)")

    # Minh chứng case GS-02 (học giỏi + nghỉ nhiều)
    gs02 = next(c for c in res["cases"] if c["id"] == "GS-02")
    print("\n--- Minh chứng GS-02 (Học giỏi + NGHỈ NHIỀU) ---")
    print(f"  score_risk={gs02['score_risk']:.1f}  attendance_risk={gs02['attendance_risk']:.1f}")
    print(f"  weight_attendance={gs02['weight_attendance']:.3f}")
    print(f"  final risk_score={gs02['risk_score']:.2f}  ->  {gs02['predicted']}")
    print("  => Học giỏi (score_risk thấp) nhưng nghỉ nhiều (attendance_risk cao) vẫn bị đánh HIGH.")


if __name__ == "__main__":
    main()
