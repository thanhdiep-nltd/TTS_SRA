"""Test offline cho seed catalog chuẩn chương trình (không chạm Neon, không gọi LLM)."""

import re
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from scripts.seed_curriculum_nodes import (
    build_unit_specs,
    deactivate_placeholder_units,
    load_catalog,
    resolve_subject_ids,
    upsert_units,
)
from src.models.tables import CurriculumUnit

SUBJECT_IDS = {6: 106, 7: 107, 8: 108, 9: 109}  # s360.dim_subject: TOAN_6..TOAN_9


def test_catalog_file_has_expected_structure():
    data = load_catalog()
    assert data["subject_code"] == "TOAN"
    assert [grade["grade"] for grade in data["grades"]] == [6, 7, 8, 9]
    total = sum(len(grade["chapters"]) for grade in data["grades"])
    assert total == 31  # 6 + 7 + 8 + 10 chương
    for grade in data["grades"]:
        codes = [chapter["code"] for chapter in grade["chapters"]]
        assert len(codes) == len(set(codes)), "code trùng trong cùng khối"
        for chapter in grade["chapters"]:
            assert re.fullmatch(r"TOAN\d+_C\d+", chapter["code"]), chapter["code"]
            assert chapter["semester"] in (1, 2)
            assert chapter["name"].strip()
            assert chapter["description"].strip()


def test_build_unit_specs_skips_grade_without_subject():
    data = load_catalog()
    specs = build_unit_specs(data, SUBJECT_IDS)
    assert len(specs) == 31
    assert all(spec["parent_id"] is None for spec in specs)
    for spec in specs:
        assert spec["subject_id"] == SUBJECT_IDS[spec["grade_number"]]
        assert spec["semester_number"] in (1, 2)

    partial = build_unit_specs(data, {6: 106})
    assert len(partial) == 6
    assert {spec["grade_number"] for spec in partial} == {6}


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE curriculum_units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id INTEGER NOT NULL,
                    grade_number INTEGER NOT NULL,
                    parent_id INTEGER,
                    code VARCHAR(50) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    semester_number INTEGER,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    with Session(engine) as session:
        yield session


def test_upsert_is_idempotent_and_updates(db_session):
    data = load_catalog()
    specs = build_unit_specs(data, SUBJECT_IDS)

    inserted, updated = upsert_units(db_session, specs)
    assert (inserted, updated) == (31, 0)
    assert db_session.query(CurriculumUnit).count() == 31

    inserted2, updated2 = upsert_units(db_session, specs)
    assert (inserted2, updated2) == (0, 31)
    assert db_session.query(CurriculumUnit).count() == 31

    renamed = dict(specs[0], name="Số tự nhiên (đã sửa)")
    _, updated3 = upsert_units(db_session, [renamed])
    assert updated3 == 1
    row = db_session.query(CurriculumUnit).filter_by(subject_id=106, grade_number=6, code="TOAN6_C1").one()
    assert row.name == "Số tự nhiên (đã sửa)"
    assert row.parent_id is None
    assert row.semester_number == 1


def test_deactivate_placeholder_units(db_session):
    db_session.add(
        CurriculumUnit(subject_id=106, grade_number=6, code="UNIT_TOAN_6_G6", name="Chương trình Toán 6 Khối 6")
    )
    db_session.commit()

    hidden = deactivate_placeholder_units(db_session)

    assert hidden == 1
    row = db_session.query(CurriculumUnit).filter_by(code="UNIT_TOAN_6_G6").one()
    assert row.is_active is False


def test_resolve_subject_ids():
    fake = MagicMock()
    fake.execute.return_value.first.return_value = (106,)
    assert resolve_subject_ids(fake, "TOAN", [6]) == {6: 106}
    fake.execute.return_value.first.return_value = None
    assert resolve_subject_ids(fake, "TOAN", [6, 7]) == {}
