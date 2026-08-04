# -*- coding: utf-8 -*-
"""Tái hiện lỗi 500 của endpoint /ews/golden-set: chạy run_golden_set rồi serialize JSON."""
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.ews.golden_set import run_golden_set  # noqa: E402

print(">>> Calling run_golden_set() ...")
res = run_golden_set()
print(">>> run_golden_set() OK. total =", res.get("total"), "passed =", res.get("passed"))

print(">>> Serializing to JSON with allow_nan=False (giống FastAPI) ...")
try:
    s = json.dumps(res, ensure_ascii=False, allow_nan=False)
    print(">>> JSON OK, length =", len(s))
    # Kiểm tra case đầu tiên có features không
    cases = res.get("cases", [])
    if cases:
        c0 = cases[0]
        feats = c0.get("features", {})
        print(">>> Case[0] id =", c0.get("id"), "| #features =", len(feats))
        for k, v in list(feats.items())[:5]:
            print("    ", k, "=", repr(v), type(v).__name__)
except (TypeError, ValueError) as e:
    print(">>> JSON SERIALIZATION FAILED:", type(e).__name__, e)
    # Tìm field gây lỗi
    def find_bad(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                find_bad(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                find_bad(v, f"{path}[{i}]")
        elif isinstance(obj, float):
            import math
            if math.isnan(obj) or math.isinf(obj):
                print(">>> BAD FLOAT at", path, "=", repr(obj))
        elif obj is None:
            pass
    find_bad(res)
    raise
