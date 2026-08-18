"""Nạp catalog chuẩn chương trình (bảng phẳng curriculum_units) — KHÔNG RAG.

Dùng chung cho scripts/seed_curriculum_nodes.py (CLI) và API admin
(src/api/v1/curriculum.py). M0/M5 trong docs_vsf/plan_cdi_kg_anchored.md:
bảng phẳng = bộ xương chương trình (chương/bài) — LLM map câu hỏi đề thi vào đây;
KHÔNG đi qua Qdrant/Airflow (RAG chỉ dành cho chat hỏi đáp SGK).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.models.tables import CurriculumUnit

DEFAULT_DATA_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed_data" / "toan_canh_dieu_6_9.json"

_GRADE_RE = re.compile(r"^##\s*.*?LỚP\s*(\d+)")
_SEMESTER_RE = re.compile(r"^###\s*.*?Tập\s*(\d+)")
_CHAPTER_RE = re.compile(r"^\*\s*\*\*Chương\s+[IVXLCDM]+\s*:\s*(.+?)\*\*\s*$")
_DESC_RE = re.compile(r"^\s{2,}\*\s*(.+)$")


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    """Đọc JSON catalog chuẩn chương trình và validate cấu trúc cơ bản."""
    p = path or DEFAULT_DATA_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    if not data.get("subject_code") or not data.get("grades"):
        raise ValueError(f"Catalog không hợp lệ: {p}")
    for grade in data["grades"]:
        for chapter in grade["chapters"]:
            if not all(key in chapter for key in ("code", "name", "semester")):
                raise ValueError(f"Chương thiếu trường bắt buộc trong {p}")
    return data


def parse_markdown_catalog(text_content: str, subject_code: str) -> dict[str, Any]:
    """Parse mục lục SGK dạng markdown → catalog dict.

    Format (vd docs/Chuong_Trinh_Toan_Canh_Dieu_6_9.md):
      "## ... LỚP 6" → khối; "### Tập 1" → học kỳ;
      "* **Chương I: Tên**" → chương; "  * Mô tả..." → mô tả.
    Code sinh theo THỨ TỰ chương trong khối (C1, C2, ...) — không phụ thuộc số La Mã.
    """
    grades: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    pending: dict[str, Any] | None = None
    semester = 1
    chapter_index = 0
    for line in text_content.splitlines():
        match = _GRADE_RE.match(line)
        if match:
            if pending is not None and current is not None:
                current["chapters"].append(pending)  # flush chương cuối của khối trước
                pending = None
            if current:
                grades.append(current)
            current = {"grade": int(match.group(1)), "chapters": []}
            semester = 1
            chapter_index = 0
            continue
        if current is None:
            continue
        match = _SEMESTER_RE.match(line)
        if match:
            semester = int(match.group(1))
            continue
        match = _CHAPTER_RE.match(line)
        if match:
            if pending:
                current["chapters"].append(pending)
            chapter_index += 1
            pending = {
                "code": f"{subject_code.upper()}{current['grade']}_C{chapter_index}",
                "name": match.group(1).strip(),
                "semester": semester,
                "description": None,
            }
            continue
        match = _DESC_RE.match(line)
        if match and pending is not None and not pending.get("description"):
            pending["description"] = match.group(1).strip()
    if pending:
        current["chapters"].append(pending)
    if current:
        grades.append(current)
    return {"subject_code": subject_code.upper(), "grades": grades}


def parse_catalog_upload(filename: str, content: str, subject_code: str) -> tuple[dict[str, Any], str]:
    """Phân tích file upload mục lục → (catalog, source). JSON hoặc markdown. KHÔNG RAG."""
    ext = Path(filename).suffix.lower()
    if ext == ".json":
        data = json.loads(content)
        if not data.get("grades"):
            raise ValueError("JSON catalog không có mục 'grades'.")
        data["subject_code"] = subject_code.upper()
        return data, "json"
    data = parse_markdown_catalog(content, subject_code)
    if not data["grades"]:
        raise ValueError("Không tìm thấy cấu trúc '## ... LỚP ...' — định dạng markdown mục lục không hợp lệ.")
    return data, "markdown"


def build_unit_specs(data: dict[str, Any], subject_id_by_grade: dict[int, int]) -> list[dict[str, Any]]:
    """Chuyển catalog thành spec dòng CurriculumUnit; bỏ khối chưa có subject_id."""
    specs: list[dict[str, Any]] = []
    for grade in data["grades"]:
        grade_number = int(grade["grade"])
        subject_id = subject_id_by_grade.get(grade_number)
        if subject_id is None:
            continue
        for chapter in grade["chapters"]:
            specs.append(
                {
                    "subject_id": subject_id,
                    "grade_number": grade_number,
                    "code": chapter["code"],
                    "name": chapter["name"],
                    "description": chapter.get("description"),
                    "semester_number": int(chapter["semester"]),
                    "parent_id": None,
                }
            )
    return specs


def resolve_subject_ids(db: Session, subject_code: str, grades: list[int]) -> dict[int, int]:
    """Tra s360.dim_subject theo code f"{subject_code}_{grade}" → {grade: subject_id}."""
    result: dict[int, int] = {}
    for grade in grades:
        row = db.execute(
            text("SELECT id FROM s360.dim_subject WHERE code = :code"), {"code": f"{subject_code}_{grade}"}
        ).first()
        if row is not None:
            result[grade] = int(row[0])
    return result


def upsert_units(db: Session, specs: list[dict[str, Any]]) -> tuple[int, int]:
    """Upsert curriculum_units theo (subject_id, grade_number, code); trả (inserted, updated)."""
    inserted = updated = 0
    for spec in specs:
        unit = db.execute(
            select(CurriculumUnit).where(
                CurriculumUnit.subject_id == spec["subject_id"],
                CurriculumUnit.grade_number == spec["grade_number"],
                CurriculumUnit.code == spec["code"],
            )
        ).scalars().first()
        if unit is None:
            db.add(CurriculumUnit(**spec))
            inserted += 1
        else:
            unit.name = spec["name"]
            unit.description = spec["description"]
            unit.semester_number = spec["semester_number"]
            unit.parent_id = None
            unit.is_active = True
            updated += 1
    db.commit()
    return inserted, updated


def deactivate_placeholder_units(db: Session) -> int:
    """Ẩn unit placeholder cũ (code UNIT_% từ mock generator) khỏi picker/shortlist — G6.3."""
    rows = db.execute(
        select(CurriculumUnit).where(CurriculumUnit.code.like("UNIT_%"), CurriculumUnit.is_active.is_(True))
    ).scalars().all()
    for unit in rows:
        unit.is_active = False
    db.commit()
    return len(rows)
