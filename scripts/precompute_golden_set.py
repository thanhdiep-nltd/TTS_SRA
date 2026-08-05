#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/precompute_golden_set.py — Sinh file cache tĩnh cho Golden Set API.

Chạy golden set qua pipeline thật (cần model .cbm + catboost), validate JSON
(allow_nan=False) + validate schema, rồi ghi ra src/ews/golden_set_data.json.

Dùng khi:
  - Retrain model mới -> chạy lại script này để cập nhật file cache.
  - File cache bị thiếu/hỏng -> tái sinh.

Chạy:
    .venv\\Scripts\\python.exe scripts\\precompute_golden_set.py
"""
from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Đảm bảo import được package src/ khi chạy từ bất kỳ CWD nào.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Console Windows (cp1252) không in được tiếng Việt -> ép UTF-8.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.ews.golden_set import run_golden_set  # noqa: E402
from src.schemas.ews import EwsGoldenSetResult  # noqa: E402

# Đường dẫn file cache — đặt cạnh golden_set.py (src/ews/golden_set_data.json).
OUT_PATH = Path(__file__).resolve().parents[1] / "src" / "ews" / "golden_set_data.json"


def _find_bad_float(obj, path: str = "") -> list[str]:
    """Tìm mọi float NaN/Inf trong cấu trúc lồng nhau (để báo lỗi rõ ràng)."""
    bad: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            bad += _find_bad_float(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += _find_bad_float(v, f"{path}[{i}]")
    elif isinstance(obj, float):
        import math

        if math.isnan(obj) or math.isinf(obj):
            bad.append(f"{path}={obj!r}")
    return bad


def main() -> None:
    print(">>> Calling run_golden_set() ...")
    res = run_golden_set()
    print(f">>> run_golden_set() OK. total={res.get('total')} passed={res.get('passed')}")

    # Gắn metadata (non-breaking) để dashboard hiển thị phiên bản model & thời điểm sinh cache.
    res["model_version"] = "v2_ensemble"
    res["generated_at"] = datetime.now(timezone.utc).isoformat()

    # 1) Validate JSON serializable (giống FastAPI: allow_nan=False).
    try:
        json.dumps(res, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as e:
        bad = _find_bad_float(res)
        print(">>> JSON SERIALIZATION FAILED:", type(e).__name__, e)
        if bad:
            print(">>> BAD FLOAT at:", *bad, sep="\n    ")
        raise

    # 2) Validate schema (chặn commit file hỏng/stale).
    try:
        EwsGoldenSetResult.model_validate(res)
    except Exception as e:  # noqa: BLE001 - báo lỗi validate rõ ràng
        print(">>> SCHEMA VALIDATION FAILED:", e)
        raise

    # 3) Ghi file cache.
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f">>> Wrote cache to {OUT_PATH}")

    # 4) In summary.
    print("=" * 60)
    print(f"Accuracy: {res['passed']}/{res['total']} ({res['accuracy'] * 100:.1f}%)")
    for c in res["cases"]:
        print(f"  {c['id']:<7}{c['description']:<36}{c['predicted']:<10}"
              f"{'PASS' if c['passed'] else 'FAIL'}")
    print("=" * 60)
    print("Done. Commit file golden_set_data.json vào git để runtime không cần model.")


if __name__ == "__main__":
    main()
