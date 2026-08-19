from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from src.models.tables import (
    AssignmentCompetency,
    CurriculumBook,
    CurriculumUnit,
    ExamCompetency,
    Misconception,
    QuestionItem,
    StudentKnowledgeGap,
)
from src.services.curriculum_catalog import delete_book_and_units


@pytest.fixture
def db_session():
    # Dùng in-memory SQLite cho test nhanh và độc lập
    engine = create_engine("sqlite:///:memory:", echo=False)
    ddl_statements = [
        """CREATE TABLE curriculum_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(255) NOT NULL,
            subject_code VARCHAR(10) NOT NULL,
            subject_id INTEGER NOT NULL,
            grade_number SMALLINT NOT NULL,
            semester_number SMALLINT,
            filename VARCHAR(255),
            source VARCHAR(30),
            created_by BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE curriculum_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            grade_number SMALLINT NOT NULL,
            parent_id BIGINT,
            code VARCHAR(50) NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            semester_number SMALLINT,
            is_active BOOLEAN DEFAULT 1 NOT NULL,
            is_phu BOOLEAN DEFAULT 0 NOT NULL,
            book_id BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE exam_competencies (
            exam_paper_id BIGINT NOT NULL,
            unit_id BIGINT NOT NULL,
            weight NUMERIC(4, 3) DEFAULT 0 NOT NULL,
            bloom_level SMALLINT,
            PRIMARY KEY (exam_paper_id, unit_id)
        )""",
        """CREATE TABLE assignment_competencies (
            assignment_id BIGINT NOT NULL,
            unit_id BIGINT NOT NULL,
            weight NUMERIC(4, 3) DEFAULT 0 NOT NULL,
            bloom_level SMALLINT,
            PRIMARY KEY (assignment_id, unit_id)
        )""",
        """CREATE TABLE student_knowledge_gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            so_school_id INTEGER NOT NULL,
            student_code VARCHAR(50) NOT NULL,
            subject_id INTEGER NOT NULL,
            school_year_id INTEGER NOT NULL,
            semester_index INTEGER NOT NULL,
            unit_id BIGINT NOT NULL,
            gap_score NUMERIC(5, 2),
            evidence_source VARCHAR(20),
            evidence_detail TEXT,
            status VARCHAR(20) DEFAULT 'active',
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE question_items (
            id TEXT PRIMARY KEY,
            school_id TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            grade_number SMALLINT NOT NULL,
            unit_id BIGINT NOT NULL,
            bloom_level SMALLINT NOT NULL,
            question_type VARCHAR(12) NOT NULL,
            stem TEXT NOT NULL,
            options TEXT,
            answer_key TEXT NOT NULL,
            solution TEXT,
            default_points NUMERIC(4, 2) DEFAULT 1.0,
            status VARCHAR(8) DEFAULT 'DRAFT',
            source VARCHAR(12) DEFAULT 'AI_GENERATED',
            provenance TEXT,
            times_used INTEGER DEFAULT 0,
            p_value NUMERIC(4, 3),
            discrimination NUMERIC(4, 3),
            exposure_at TIMESTAMP,
            created_by BIGINT NOT NULL,
            reviewed_by BIGINT,
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE misconceptions (
            id TEXT PRIMARY KEY,
            school_id TEXT,
            subject_id TEXT NOT NULL,
            unit_id BIGINT NOT NULL,
            grade_number SMALLINT NOT NULL,
            description TEXT NOT NULL,
            example_wrong TEXT,
            evidence_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
    ]

    with engine.begin() as conn:
        for stmt in ddl_statements:
            conn.execute(text(stmt))

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()



def test_delete_book_and_all_units_success(db_session: Session):
    # 1. Tạo 2 cuốn sách: Book 1 (cần xóa) và Book 2 (giữ lại)
    book1 = CurriculumBook(
        id=1,
        title="Toán 6 Cánh Diều Tập 1",
        subject_code="TOAN_6",
        subject_id=106,
        grade_number=6,
        semester_number=1,
    )
    book2 = CurriculumBook(
        id=2,
        title="Toán 6 Cánh Diều Tập 2",
        subject_code="TOAN_6",
        subject_id=106,
        grade_number=6,
        semester_number=2,
    )
    db_session.add_all([book1, book2])
    db_session.flush()

    # 2. Tạo các node cho Book 1 (1 chương cha + 2 bài con)
    c1 = CurriculumUnit(
        id=101,
        subject_id=106,
        grade_number=6,
        code="TOAN6_C1",
        name="Số tự nhiên",
        book_id=1,
    )
    db_session.add(c1)
    db_session.flush()

    b1 = CurriculumUnit(
        id=102,
        subject_id=106,
        grade_number=6,
        code="TOAN6_C1_B1",
        name="Tập hợp",
        parent_id=101,
        book_id=1,
    )
    b2 = CurriculumUnit(
        id=103,
        subject_id=106,
        grade_number=6,
        code="TOAN6_C1_B2",
        name="Tập hợp số tự nhiên",
        parent_id=101,
        book_id=1,
    )

    # Node cho Book 2
    c2 = CurriculumUnit(
        id=201,
        subject_id=106,
        grade_number=6,
        code="TOAN6_C2",
        name="Số nguyên",
        book_id=2,
    )

    # Node không thuộc sách nào (legacy node)
    c_legacy = CurriculumUnit(
        id=301,
        subject_id=106,
        grade_number=6,
        code="TOAN6_LEGACY",
        name="Ôn tập chung",
        book_id=None,
    )

    db_session.add_all([b1, b2, c2, c_legacy])
    db_session.flush()

    # 3. Tạo các bản ghi phụ thuộc trỏ tới node của Book 1
    db_session.add(ExamCompetency(exam_paper_id=1, unit_id=101, weight=0.5))
    db_session.add(AssignmentCompetency(assignment_id=10, unit_id=102, weight=0.3))
    db_session.commit()

    # 4. Thực hiện xóa Book 1
    result = delete_book_and_units(db_session, book_id=1)

    assert result["book_id"] == 1
    assert result["title"] == "Toán 6 Cánh Diều Tập 1"
    assert result["deleted_units_count"] == 3

    # 5. Kiểm tra Book 1 và toàn bộ 3 node của Book 1 đã bị xóa
    assert db_session.get(CurriculumBook, 1) is None
    units_book1 = db_session.execute(
        select(CurriculumUnit).where(CurriculumUnit.book_id == 1)
    ).scalars().all()
    assert len(units_book1) == 0

    assert db_session.get(CurriculumUnit, 101) is None
    assert db_session.get(CurriculumUnit, 102) is None
    assert db_session.get(CurriculumUnit, 103) is None

    # 6. Kiểm tra các bản ghi phụ thuộc đã được dọn sạch
    ex_comp = db_session.execute(
        select(ExamCompetency).where(ExamCompetency.unit_id.in_([101, 102, 103]))
    ).scalars().all()
    assert len(ex_comp) == 0

    as_comp = db_session.execute(
        select(AssignmentCompetency).where(AssignmentCompetency.unit_id.in_([101, 102, 103]))
    ).scalars().all()
    assert len(as_comp) == 0

    # 7. Kiểm tra Book 2 và node của Book 2 cùng legacy node vẫn còn nguyên
    assert db_session.get(CurriculumBook, 2) is not None
    assert db_session.get(CurriculumUnit, 201) is not None
    assert db_session.get(CurriculumUnit, 301) is not None


def test_delete_non_existent_book_raises(db_session: Session):
    with pytest.raises(ValueError, match="không tồn tại"):
        delete_book_and_units(db_session, book_id=99999)
