"""src/api/v1/knowledge_gap.py — API lỗ hổng kiến thức (M2).

Đọc exam_competencies (đề → unit + weight + bloom) + điểm tổng của học sinh từ
fact_gradebooks để ước lượng mastery từng unit (dùng service knowledge_gap thuần).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.schemas.knowledge_gap import (
    ClassKnowledgeGaps,
    ClassOption,
    KnowledgeGapItem,
    StudentKnowledgeGaps,
    StudentOption,
)
from src.services.knowledge_gap import UnitWeight, compute_unit_mastery

router = APIRouter(prefix="/knowledge-gaps", tags=["Knowledge Gaps"])


@router.get("/subject-options", response_model=list[dict])
def list_s360_subjects(db: Session = Depends(get_db)):
    """Danh sách môn học từ s360.dim_subject (danh mục dùng chung, 24 môn).

    KHÔNG dùng /ews/meta (chỉ trả môn có trong dự báo EWS — bảng risk_predictions
    có thể rỗng) hay /subjects public (model User thiếu school_id). Trả subject_id
    Integer đúng dạng API knowledge-gaps.
    """
    rows = db.execute(
        text("""
            SELECT id, code, name
            FROM s360.dim_subject
            WHERE is_active = 1
            ORDER BY id
        """)
    ).fetchall()
    return [{"id": r.id, "code": r.code, "name": r.name} for r in rows]


@router.get("/class-options", response_model=list[ClassOption])
def list_s360_classes(
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Danh sách lớp từ s360.dim_homeroom_class (dữ liệu thật của học sinh/điểm).

    KHÔNG dùng /classes (public CRUD) vì DB dev dữ liệu thật nằm ở schema s360
    (public.classes rỗng) và model User không có school_id UUID. Lọc theo so_school_id.
    """
    school_id = getattr(current_user, "so_school_id", None)
    params: dict = {}
    cond = ""
    if school_id is not None:
        cond = "WHERE so_school_id = :sid"
        params["sid"] = school_id
    rows = db.execute(
        text(f"""
            SELECT id, code, fullname, grade_id
            FROM s360.dim_homeroom_class
            {cond}
            ORDER BY grade_id, id
        """),
        params,
    ).fetchall()
    return [
        ClassOption(
            class_id=int(r.id),
            class_name=r.fullname,
            grade_id=int(r.grade_id) if r.grade_id is not None else None,
            code=r.code,
        )
        for r in rows
    ]


@router.get("/classes/{class_id}/students", response_model=list[StudentOption])
def list_s360_students(
    class_id: int,
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Học sinh của 1 lớp từ s360.dim_homeroom_class_student (lọc đúng lớp + trường)."""
    school_id = getattr(current_user, "so_school_id", None)
    params: dict = {"cid": class_id}
    cond = "homeroom_class_id = :cid"
    if school_id is not None:
        cond += " AND so_school_id = :sid"
        params["sid"] = school_id
    rows = db.execute(
        text(f"""
            SELECT student_code, student_name
            FROM s360.dim_homeroom_class_student
            WHERE {cond}
            ORDER BY student_name
        """),
        params,
    ).fetchall()
    return [
        StudentOption(student_code=r.student_code, student_name=r.student_name)
        for r in rows
        if r.student_name
    ]


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
    """Liệt kê các unit hổng kiến thức của 1 học sinh theo môn + học kỳ.

    Nguồn 1: student_unit_mastery (mastery theo chương từ LMS item-level + đối soát) — ưu tiên.
    Nguồn 2 (fallback): điểm tổng + exam_competencies (hành vi cũ, ill-posed) khi chưa có LMS.
    """
    sy_id = _resolve_school_year(db, school_year_id)
    school_id = getattr(current_user, "so_school_id", None)

    # === Nguồn 1: student_unit_mastery (LMS item-level, đối soát) — ưu tiên nếu có. ===
    # Lưu ý: bảng student_unit_mastery không có school_year_id; lọc theo semester_index + tenant.
    sum_cond = "AND sum.so_school_id = :school_id" if school_id else ""
    sum_params = {"sc": student_code, "sid": subject_id, "sem": semester_index}
    if school_id:
        sum_params["school_id"] = school_id
    sum_rows = db.execute(
        text(f"""
            SELECT sum.unit_id, sum.raw_mastery, sum.adjusted_mastery, sum.n_items,
                   sum.coverage, sum.confidence, sum.evidence_source, sum.integrity_status,
                   sum.evidence_detail
            FROM public.student_unit_mastery sum
            WHERE sum.student_code = :sc AND sum.subject_id = :sid
              AND sum.semester_index = :sem
              {sum_cond}
        """),
        sum_params,
    ).fetchall()

    mastery_units = [r for r in sum_rows if r.adjusted_mastery is not None]
    if mastery_units:
        meta = _unit_meta(db, [r.unit_id for r in mastery_units])
        gaps = [
            KnowledgeGapItem(
                unit_id=r.unit_id,
                unit_name=meta.get(r.unit_id, (None, None, None, None, None))[0],
                chapter=meta.get(r.unit_id, (None, None, None, None, None))[1],
                lesson=meta.get(r.unit_id, (None, None, None, None, None))[2],
                gap_score=round(1.0 - float(r.adjusted_mastery), 3),
                mastery=round(float(r.adjusted_mastery), 3),
                confidence=r.confidence or "LOW",
                coverage=float(r.coverage) if r.coverage is not None else None,
                integrity_status=r.integrity_status,
                evidence_source=(r.evidence_source or "LMS"),
                evidence_detail=dict(r.evidence_detail) if r.evidence_detail else None,
            )
            for r in mastery_units
        ]
        return StudentKnowledgeGaps(
            student_code=student_code,
            subject_id=subject_id,
            school_year_id=sy_id,
            semester_index=semester_index,
            gaps=gaps,
        )

    # === Nguồn 2 (fallback): điểm tổng + exam_competencies — chỉ khi chưa có LMS mastery. ===
    units = _load_exam_units(db, subject_id, semester_index, school_id)
    score_row = _latest_locked_score(db, student_code, subject_id, sy_id, semester_index, school_id)
    if not units or score_row is None or score_row.final_grade is None:
        # Chưa đủ dữ liệu: không có LMS, không có điểm thi → không đánh giá được học sinh.
        return StudentKnowledgeGaps(
            student_code=student_code,
            subject_id=subject_id,
            school_year_id=sy_id,
            semester_index=semester_index,
            gaps=[],
        )

    total_score = float(score_row.final_grade)
    max_score = float(score_row.max_grade) if score_row.max_grade else 10.0
    mastery_list = compute_unit_mastery(total_score, max_score, units)
    meta = _unit_meta(db, [m.unit_id for m in mastery_list])
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
            confidence="LOW",
            evidence_source="EXAM",
        )
        for m in mastery_list
        if m.is_gap
    ]
    return StudentKnowledgeGaps(
        student_code=student_code,
        subject_id=subject_id,
        school_year_id=sy_id,
        semester_index=semester_index,
        gaps=gaps,
    )


def _latest_locked_score(db: Session, student_code: str, subject_id: int, sy: int, sem: int, school_id: int | None):
    """Điểm tổng khóa gần nhất của học sinh (fallback EXAM khi chưa có item-level)."""
    school_cond = "AND fg.so_school_id = :school_id" if school_id else ""
    params = {"sc": student_code, "sid": subject_id, "sy": sy, "sem": sem}
    if school_id:
        params["school_id"] = school_id
    return db.execute(
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
