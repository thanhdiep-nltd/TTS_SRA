"""src/api/v1/knowledge_gap.py — API lỗ hổng kiến thức (M2).

Đọc exam_competencies (đề → unit + weight + bloom) + điểm tổng của học sinh từ
fact_gradebooks để ước lượng mastery từng unit (dùng service knowledge_gap thuần).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.schemas.knowledge_gap import ClassKnowledgeGaps, KnowledgeGapItem, StudentKnowledgeGaps
from src.services.knowledge_gap import UnitWeight, compute_unit_mastery

router = APIRouter(prefix="/knowledge-gaps", tags=["Knowledge Gaps"])


def _resolve_school_year(db: Session, school_year_id: int | None) -> int:
    """Lấy năm học hiện hành nếu không truyền."""
    if school_year_id and school_year_id > 0:
        return school_year_id
    row = db.execute(text("SELECT id FROM s360.dim_school_year WHERE is_current = 1 LIMIT 1")).fetchone()
    return int(row.id) if row and row.id is not None else 2025


def _load_exam_units(
    db: Session, subject_id: int, semester_index: int, school_id: int | None = None
) -> list[UnitWeight]:
    """Load danh sách unit của đề (từ exam_competencies) cho môn + học kỳ.

    Ưu tiên đề CK (FINAL) nếu có, ngược lại MIDTERM. Có Tenant isolation theo trường.
    """
    school_filter = "AND (ep.so_school_id IS NULL OR ep.so_school_id = :school_id)" if school_id else ""
    params = {"sid": subject_id, "sem": semester_index}
    if school_id:
        params["school_id"] = school_id

    rows = db.execute(
        text(f"""
            SELECT ec.unit_id, ec.weight, ec.bloom_level
            FROM public.exam_competencies ec
            JOIN public.exam_papers ep ON ep.id = ec.exam_paper_id
            WHERE ep.subject_id = :sid
              AND ep.semester_id = :sem
              {school_filter}
            ORDER BY CASE ep.score_category WHEN 'FINAL' THEN 0 WHEN 'MIDTERM' THEN 1 ELSE 2 END
            LIMIT 100
        """),
        params,
    ).fetchall()
    return [
        UnitWeight(
            unit_id=r.unit_id,
            weight=float(r.weight) if r.weight is not None else 0.0,
            bloom_level=r.bloom_level or 3,
        )
        for r in rows
    ]


def _unit_meta(
    db: Session, unit_ids: list[int]
) -> dict[int, tuple[str | None, str | None, str | None, str | None, list[str] | None]]:
    """Map unit_id → (name, chapter, lesson, summary, keywords).

    chapter = tên node cha (parent_id) nếu unit là bài con, ngược lại chính tên unit (node chương);
    lesson = tên unit nếu là bài con, None nếu là chương. summary/keywords là nội dung làm giàu
    khi nạp sách — giúp giải thích "hổng khái niệm/mục nào".
    """
    if not unit_ids:
        return {}
    rows = db.execute(
        text(
            """
            SELECT cu.id, cu.name, cu.parent_id, cu.summary, cu.keywords, p.name AS chapter_name
            FROM public.curriculum_units cu
            LEFT JOIN public.curriculum_units p ON p.id = cu.parent_id
            WHERE cu.id = ANY(:ids)
            """
        ),
        {"ids": unit_ids},
    ).fetchall()
    return {
        r.id: (
            r.name,
            (r.chapter_name if r.chapter_name else r.name) if r.parent_id else r.name,
            r.name if r.parent_id else None,
            r.summary,
            list(r.keywords) if r.keywords else None,
        )
        for r in rows
    }


@router.get("/students/{student_code}", response_model=StudentKnowledgeGaps)
def get_student_knowledge_gaps(
    student_code: str,
    subject_id: int = Query(..., description="ID môn học (s360.dim_subject.id)"),
    school_year_id: int | None = Query(None, description="Năm học (để trống để lấy năm hiện tại)"),
    semester_index: int = Query(1),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Liệt kê các unit hổng kiến thức của 1 học sinh theo môn + học kỳ."""
    sy_id = _resolve_school_year(db, school_year_id)
    school_id = getattr(current_user, "so_school_id", None)

    units = _load_exam_units(db, subject_id, semester_index, school_id)
    if not units:
        return StudentKnowledgeGaps(
            student_code=student_code,
            subject_id=subject_id,
            school_year_id=sy_id,
            semester_index=semester_index,
            gaps=[],
        )

    # Điểm tổng gần nhất của học sinh trên đề (fact_gradebooks, đã khoá) kèm Tenant Isolation.
    school_cond = "AND fg.so_school_id = :school_id" if school_id else ""
    params = {"sc": student_code, "sid": subject_id, "sy": sy_id, "sem": semester_index}
    if school_id:
        params["school_id"] = school_id

    score_row = db.execute(
        text(f"""
            SELECT fg.final_grade, fg.max_grade
            FROM s360.fact_gradebooks fg
            WHERE fg.student_code = :sc AND fg.subject_id = :sid
              AND fg.school_year_id = :sy AND fg.semester_index = :sem
              AND fg.is_locked = 1
              {school_cond}
            ORDER BY fg.created_at DESC
            LIMIT 1
        """),
        params,
    ).fetchone()

    if score_row is None or score_row.final_grade is None:
        return StudentKnowledgeGaps(
            student_code=student_code,
            subject_id=subject_id,
            school_year_id=sy_id,
            semester_index=semester_index,
            gaps=[],
        )

    total_score = float(score_row.final_grade)
    max_score = float(score_row.max_grade) if score_row.max_grade else 10.0
    mastery = compute_unit_mastery(total_score, max_score, units)

    meta = _unit_meta(db, [m.unit_id for m in mastery])
    gaps = [
        KnowledgeGapItem(
            unit_id=m.unit_id,
            unit_name=meta.get(m.unit_id, (None, None, None, None, None))[0],
            chapter=meta.get(m.unit_id, (None, None, None, None, None))[1],
            lesson=meta.get(m.unit_id, (None, None, None, None, None))[2],
            summary=meta.get(m.unit_id, (None, None, None, None, None))[3],
            keywords=meta.get(m.unit_id, (None, None, None, None, None))[4],
            gap_score=m.gap_score,
            mastery=m.mastery,
            evidence_source="EXAM",
        )
        for m in mastery
        if m.is_gap
    ]
    return StudentKnowledgeGaps(
        student_code=student_code,
        subject_id=subject_id,
        school_year_id=sy_id,
        semester_index=semester_index,
        gaps=gaps,
    )


@router.get("/classes/{class_id}", response_model=ClassKnowledgeGaps)
def get_class_knowledge_gaps(
    class_id: int,
    subject_id: int = Query(..., description="ID môn học (s360.dim_subject.id)"),
    school_year_id: int | None = Query(None, description="Năm học (để trống để lấy năm hiện tại)"),
    semester_index: int = Query(1),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Unit hổng phổ biến của cả lớp (trung bình gap_score các học sinh)."""
    sy_id = _resolve_school_year(db, school_year_id)
    school_id = getattr(current_user, "so_school_id", None)

    units = _load_exam_units(db, subject_id, semester_index, school_id)
    if not units:
        return ClassKnowledgeGaps(
            class_id=class_id,
            subject_id=subject_id,
            school_year_id=sy_id,
            semester_index=semester_index,
            gaps=[],
        )

    # Điểm tổng của mọi học sinh trong lớp (fact_gradebooks) kèm Tenant isolation.
    school_cond = "AND fg.so_school_id = :school_id" if school_id else ""
    params = {"sid": subject_id, "sy": sy_id, "sem": semester_index, "cid": class_id}
    if school_id:
        params["school_id"] = school_id

    rows = db.execute(
        text(f"""
            SELECT fg.student_code, fg.final_grade, fg.max_grade
            FROM s360.fact_gradebooks fg
            WHERE fg.subject_id = :sid
              AND fg.school_year_id = :sy AND fg.semester_index = :sem
              AND fg.homeroom_class_id = :cid
              AND fg.is_locked = 1
              {school_cond}
        """),
        params,
    ).fetchall()

    if not rows:
        return ClassKnowledgeGaps(
            class_id=class_id,
            subject_id=subject_id,
            school_year_id=sy_id,
            semester_index=semester_index,
            gaps=[],
        )

    # Gộp gap_score theo unit.
    acc: dict[int, list[float]] = {}
    for r in rows:
        total = float(r.final_grade) if r.final_grade is not None else 0.0
        max_score = float(r.max_grade) if r.max_grade else 10.0
        for m in compute_unit_mastery(total, max_score, units):
            if m.gap_score > 0:
                acc.setdefault(m.unit_id, []).append(m.gap_score)

    meta = _unit_meta(db, list(acc.keys()))
    gaps = [
        KnowledgeGapItem(
            unit_id=uid,
            unit_name=meta.get(uid, (None, None, None, None, None))[0],
            chapter=meta.get(uid, (None, None, None, None, None))[1],
            lesson=meta.get(uid, (None, None, None, None, None))[2],
            summary=meta.get(uid, (None, None, None, None, None))[3],
            keywords=meta.get(uid, (None, None, None, None, None))[4],
            gap_score=round(sum(v) / len(v), 3),
            mastery=round(1.0 - sum(v) / len(v), 3),
            evidence_source="EXAM",
        )
        for uid, v in sorted(acc.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))
    ]
    return ClassKnowledgeGaps(
        class_id=class_id,
        subject_id=subject_id,
        school_year_id=school_year_id,
        semester_index=semester_index,
        gaps=gaps,
    )
