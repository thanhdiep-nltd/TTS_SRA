"""Test offline cho src/services/curriculum_catalog.py — parser markdown mục lục + upload (không RAG)."""

import json

import pytest

from src.services.curriculum_catalog import parse_catalog_upload, parse_markdown_catalog

_MD_SAMPLE = """# Mục lục
## 📘 LỚP 6
### Tập 1
* **Chương I: Số tự nhiên**
  * Tập hợp, các phép tính số tự nhiên, lũy thừa.
* **Chương II: Số nguyên**
  * Số nguyên âm, các phép tính cộng trừ nhân chia.
### Tập 2
* **Chương III: Phân số và số thập phân**
  * Khái niệm, so sánh và các phép tính với phân số.
## 📘 LỚP 7
### Tập 1
* **Chương I: Số hữu tỉ**
  * Tập hợp số hữu tỉ, các phép tính.
### Tập 2
* **Chương II: Biểu thức đại số**
  * Đa thức một biến, nghiệm của đa thức.
"""


def test_parse_markdown_catalog_structure():
    data = parse_markdown_catalog(_MD_SAMPLE, "toan")
    assert data["subject_code"] == "TOAN"
    assert [g["grade"] for g in data["grades"]] == [6, 7]

    g6 = data["grades"][0]
    chapters = g6["chapters"]
    assert [c["code"] for c in chapters] == ["TOAN6_C1", "TOAN6_C2", "TOAN6_C3"]  # đánh số liên tục qua 2 tập
    assert chapters[0]["name"] == "Số tự nhiên"
    assert chapters[0]["semester"] == 1
    assert chapters[2]["semester"] == 2
    assert chapters[2]["name"] == "Phân số và số thập phân"
    assert chapters[0]["description"] == "Tập hợp, các phép tính số tự nhiên, lũy thừa."

    g7 = data["grades"][1]
    assert [c["code"] for c in g7["chapters"]] == ["TOAN7_C1", "TOAN7_C2"]


def test_parse_catalog_upload_json():
    data, source = parse_catalog_upload(
        "catalog.json",
        json.dumps({"grades": [{"grade": 6, "chapters": [{"code": "TOAN6_C1", "name": "Số tự nhiên", "semester": 1}]}]}),
        "toan",
    )
    assert source == "json"
    assert data["subject_code"] == "TOAN"
    assert len(data["grades"]) == 1


def test_parse_catalog_upload_markdown():
    data, source = parse_catalog_upload("mucluc.md", _MD_SAMPLE, "toan")
    assert source == "markdown"
    assert len(data["grades"]) == 2


def test_parse_catalog_upload_markdown_invalid():
    with pytest.raises(ValueError):
        parse_catalog_upload("noise.md", "không phải mục lục", "toan")
