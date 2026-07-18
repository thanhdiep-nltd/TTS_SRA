import unicodedata
from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.models.enums import AssessmentType, ScoreCategory
from src.models.tables import (
    Class,
    Enrollment,
    ExamColumnMapping,
    ExamPaper,
    Grade,
    Score,
    Semester,
    Student,
    StudentTermReport,
    Subject,
    SubjectEvaluation,
)
from src.schemas.gradebook import (
    ClassSummaryResponse,
    ExamRef,
    GradebookColumn,
    GradebookResponse,
    GradebookRow,
    GradeCell,
    HocLucStat,
    SubjectEvalUpsert,
    SubjectInfo,
    SummaryRow,
    TermReportUpsert,
)
from src.services import rbac, scoring

router = APIRouter(prefix="/scores", tags=["Gradebook"])

_HL_LABELS = ["Giỏi", "Khá", "Trung bình", "Yếu", "Kém"]

COLUMNS = [
    GradebookColumn(
        key=scoring.column_key(cat, idx),
        category=cat.value,
        index=idx,
        label=scoring.column_label(cat, idx),
        mappable=cat in scoring.MAPPABLE,
    )
    for cat, idx in scoring.SCORE_COLUMNS
]


def compute_stats(values: list[float | None]) -> list[HocLucStat]:
    graded = [scoring.hoc_luc(v) for v in values if v is not None]
    total = len(graded) or 1
    return [
        HocLucStat(label=lbl, count=graded.count(lbl), ratio=round(graded.count(lbl) / total * 100, 1))
        for lbl in _HL_LABELS
    ]


def _by_category(scores: list[Score]) -> dict[ScoreCategory, list[float]]:
    out: dict[ScoreCategory, list[float]] = defaultdict(list)
    for sc in scores:
        out[sc.score_category].append(float(sc.value))
    return out


def _vn_name_key(full_name: str) -> tuple[str, str]:
    """Khóa sắp xếp theo TÊN (từ cuối) như danh sách lớp VN; bỏ dấu để xếp đúng alphabet."""

    def strip(s: str) -> str:
        s = s.replace("đ", "d").replace("Đ", "D")
        return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()

    parts = full_name.split()
    given = parts[-1] if parts else full_name
    return (strip(given), strip(full_name))


def _students_of_class(db: Session, class_id: UUID) -> list[Student]:
    stmt = (
        select(Student)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(Enrollment.class_id == class_id, Enrollment.is_active.is_(True))
    )
    students = list(db.execute(stmt).scalars().all())
    return sorted(students, key=lambda s: _vn_name_key(s.full_name))


def _is_enrolled(db: Session, student_id: UUID, class_id: UUID) -> bool:
    stmt = select(Enrollment.id).where(
        Enrollment.student_id == student_id, Enrollment.class_id == class_id, Enrollment.is_active.is_(True)
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def _scoped_scores(db: Session, user, *conditions):
    stmt = select(Score).where(*conditions)
    scope = rbac.accessible_score_filter(db, user)
    if scope is not None:
        stmt = stmt.where(scope)
    return db.execute(stmt).scalars().all()


def _resolve_mappings(
    db: Session, subject_id: UUID, semester_id: UUID, class_id: UUID, grade_id: UUID
) -> dict[str, ExamRef]:
    """Đề đã map cho lớp: TX theo class_id + GK/CK theo grade_id (đồng bộ toàn khối)."""
    rows = db.execute(
        select(ExamColumnMapping, ExamPaper)
        .join(ExamPaper, ExamPaper.id == ExamColumnMapping.exam_paper_id)
        .where(
            ExamColumnMapping.subject_id == subject_id,
            ExamColumnMapping.semester_id == semester_id,
            or_(
                and_(ExamColumnMapping.score_category == ScoreCategory.REGULAR, ExamColumnMapping.class_id == class_id),
                and_(
                    ExamColumnMapping.score_category.in_([ScoreCategory.MIDTERM, ScoreCategory.FINAL]),
                    ExamColumnMapping.grade_id == grade_id,
                ),
            ),
        )
    ).all()
    return {
        scoring.column_key(m.score_category, m.column_index): ExamRef(
            mapping_id=m.id,
            exam_paper_id=p.id,
            title=p.title,
            file_type=p.file_type.value if p.file_type else None,
            content_difficulty=float(p.content_difficulty) if p.content_difficulty is not None else None,
            content_analyzed_at=p.content_analyzed_at,
        )
        for m, p in rows
    }


def _subject_evals(db: Session, *conditions) -> dict:
    """Map đánh giá học tập theo (student_id[, subject_id]) tùy điều kiện truyền vào."""
    return {
        (e.student_id, e.subject_id): e
        for e in db.execute(select(SubjectEvaluation).where(*conditions)).scalars().all()
    }


def _detail_row(st: Student, subj: Subject, ev, bucket: dict, sem_ids: tuple) -> GradebookRow:
    """Một dòng bảng điểm chi tiết — môn SCORED có điểm/ĐTB, môn REMARK có Đạt/CĐ."""
    base = dict(
        student_id=st.id, student_code=st.student_code, full_name=st.full_name, evaluation=ev.comment if ev else None
    )
    if subj.assessment_type == AssessmentType.REMARK:
        return GradebookRow(**base, cells={}, result=ev.result.value if ev and ev.result else None)
    semester_id, hk1_id, hk2_id = sem_ids

    def dtb(sem_id):
        return scoring.dtb_semester(_by_category(bucket.get((st.id, sem_id), []))) if sem_id else None

    hk1, hk2 = dtb(hk1_id), dtb(hk2_id)
    dtb_hk = dtb(semester_id)
    cells = {
        scoring.column_key(s.score_category, s.column_index): GradeCell(id=s.id, value=float(s.value))
        for s in bucket.get((st.id, semester_id), [])
    }
    return GradebookRow(
        **base,
        cells=cells,
        dtb_hk=dtb_hk,
        dtb_hk1=hk1,
        dtb_hk2=hk2,
        dtb_cn=scoring.dtb_year(hk1, hk2),
        hoc_luc=scoring.hoc_luc(dtb_hk),
    )


def _check_class_access(db: Session, user, cls: Class | None) -> None:
    """Đảm bảo lớp thuộc trường user VÀ (nếu quyền bị giới hạn) user có phân công cho lớp này."""
    if cls is None:
        raise HTTPException(status_code=404, detail="Lớp không tồn tại")
    grade = db.get(Grade, cls.grade_id)
    if grade is None or grade.school_id != user.school_id:
        raise HTTPException(status_code=404, detail="Lớp không tồn tại")
    class_ids = rbac.accessible_class_ids(db, user)
    if class_ids is not None and cls.id not in class_ids:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem lớp này")


@router.get("/gradebook", response_model=GradebookResponse)
def gradebook(class_id: UUID, subject_id: UUID, semester_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Bảng điểm chi tiết một môn của lớp (Miệng/TX/GK/CK + ĐTB, hoặc Đạt/CĐ cho môn nhận xét)."""
    cls = db.get(Class, class_id)
    subj = db.get(Subject, subject_id)
    _check_class_access(db, user, cls)
    if subj is None:
        raise HTTPException(status_code=404, detail="Lớp hoặc môn không tồn tại")
    sem_by_num = {
        s.number: s.id
        for s in db.execute(select(Semester).where(Semester.academic_year_id == cls.academic_year_id)).scalars()
    }
    hk1_id, hk2_id = sem_by_num.get(1), sem_by_num.get(2)
    sem_ids = [s for s in {semester_id, hk1_id, hk2_id} if s]

    scores = _scoped_scores(
        db, user, Score.class_id == class_id, Score.subject_id == subject_id, Score.semester_id.in_(sem_ids)
    )
    bucket: dict[tuple, list[Score]] = defaultdict(list)
    for sc in scores:
        bucket[(sc.student_id, sc.semester_id)].append(sc)
    evals = _subject_evals(
        db,
        SubjectEvaluation.subject_id == subject_id,
        SubjectEvaluation.semester_id == semester_id,
        SubjectEvaluation.class_id == class_id,
    )

    rows = [
        _detail_row(st, subj, evals.get((st.id, subject_id)), bucket, (semester_id, hk1_id, hk2_id))
        for st in _students_of_class(db, class_id)
    ]
    return GradebookResponse(
        class_id=class_id,
        subject_id=subject_id,
        semester_id=semester_id,
        assessment_type=subj.assessment_type.value,
        columns=COLUMNS,
        rows=rows,
        mappings=_resolve_mappings(db, subject_id, semester_id, class_id, cls.grade_id),
        total_students=len(rows),
        stats=compute_stats([r.dtb_hk for r in rows]),
    )


def _summary_row(st: Student, subjects: list[Subject], bucket: dict, evals: dict, report) -> SummaryRow:
    """Một dòng tổng hợp lớp: ĐTB môn SCORED, Đạt/CĐ môn REMARK, hạnh kiểm + đánh giá chung."""
    averages, remarks = {}, {}
    for subj in subjects:
        if subj.assessment_type == AssessmentType.REMARK:
            ev = evals.get((st.id, subj.id))
            remarks[str(subj.id)] = ev.result.value if ev and ev.result else ""
        else:
            averages[str(subj.id)] = scoring.dtb_semester(_by_category(bucket.get((st.id, subj.id), [])))
    graded = [a for a in averages.values() if a is not None]
    overall = round(sum(graded) / len(graded), 2) if graded else None
    return SummaryRow(
        student_id=st.id,
        student_code=st.student_code,
        full_name=st.full_name,
        averages=averages,
        remarks=remarks,
        overall=overall,
        hoc_luc=scoring.hoc_luc(overall),
        conduct=report.conduct.value if report and report.conduct else None,
        general_comment=report.general_comment if report else None,
        absent_days=getattr(report, "absent_days", 0) if report else 0,
    )


@router.get("/class-summary", response_model=ClassSummaryResponse)
def class_summary(class_id: UUID, semester_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Bảng tổng hợp lớp (cho GV chủ nhiệm): ĐTB môn + ĐTB chung + học lực + hạnh kiểm + đánh giá chung."""
    cls = db.get(Class, class_id)
    _check_class_access(db, user, cls)
    grade = db.get(Grade, cls.grade_id)
    subjects = list(
        db.execute(
            select(Subject)
            .where(Subject.school_id == grade.school_id, Subject.is_active.is_(True))
            .order_by(Subject.name)
        ).scalars()
    )

    scores = _scoped_scores(db, user, Score.class_id == class_id, Score.semester_id == semester_id)
    bucket: dict[tuple, list[Score]] = defaultdict(list)
    for sc in scores:
        bucket[(sc.student_id, sc.subject_id)].append(sc)
    evals = _subject_evals(db, SubjectEvaluation.class_id == class_id, SubjectEvaluation.semester_id == semester_id)
    reports = {
        r.student_id: r
        for r in db.execute(
            select(StudentTermReport).where(
                StudentTermReport.class_id == class_id, StudentTermReport.semester_id == semester_id
            )
        )
        .scalars()
        .all()
    }

    rows = [_summary_row(st, subjects, bucket, evals, reports.get(st.id)) for st in _students_of_class(db, class_id)]
    return ClassSummaryResponse(
        class_id=class_id,
        semester_id=semester_id,
        subjects=[
            SubjectInfo(id=s.id, name=s.name, code=s.code, assessment_type=s.assessment_type.value) for s in subjects
        ],
        rows=rows,
        total_students=len(rows),
        stats=compute_stats([r.overall for r in rows]),
        can_edit_report=rbac.can_edit_term_report(db, user, class_id),
    )


@router.put("/subject-eval", status_code=204)
def upsert_subject_eval(payload: SubjectEvalUpsert, user: CurrentUser, db: Session = Depends(get_db)):
    """GV bộ môn nhập/sửa đánh giá học tập (nhận xét hoặc Đạt/CĐ) cho 1 HS ở 1 môn."""
    if not rbac.can_edit_subject_eval(db, user, payload.subject_id, payload.class_id):
        raise HTTPException(status_code=403, detail="Bạn không có quyền đánh giá môn này ở lớp này")
    if not _is_enrolled(db, payload.student_id, payload.class_id):
        raise HTTPException(status_code=400, detail="Học sinh không thuộc lớp này")
    row = (
        db.execute(
            select(SubjectEvaluation).where(
                SubjectEvaluation.student_id == payload.student_id,
                SubjectEvaluation.subject_id == payload.subject_id,
                SubjectEvaluation.semester_id == payload.semester_id,
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        row = SubjectEvaluation(
            student_id=payload.student_id,
            subject_id=payload.subject_id,
            class_id=payload.class_id,
            semester_id=payload.semester_id,
        )
        db.add(row)
    row.result, row.comment, row.evaluated_by = payload.result, payload.comment, user.id
    db.commit()


@router.put("/term-report", status_code=204)
def upsert_term_report(payload: TermReportUpsert, user: CurrentUser, db: Session = Depends(get_db)):
    """GV chủ nhiệm nhập/sửa hạnh kiểm + đánh giá chung cho 1 HS ở 1 học kỳ."""
    if not rbac.can_edit_term_report(db, user, payload.class_id):
        raise HTTPException(status_code=403, detail="Chỉ GV chủ nhiệm lớp được nhập hạnh kiểm/đánh giá")
    if not _is_enrolled(db, payload.student_id, payload.class_id):
        raise HTTPException(status_code=400, detail="Học sinh không thuộc lớp này")
    row = (
        db.execute(
            select(StudentTermReport).where(
                StudentTermReport.student_id == payload.student_id,
                StudentTermReport.class_id == payload.class_id,
                StudentTermReport.semester_id == payload.semester_id,
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        row = StudentTermReport(
            student_id=payload.student_id, class_id=payload.class_id, semester_id=payload.semester_id
        )
        db.add(row)

    fields = payload.model_dump(exclude_unset=True)
    if "conduct" in fields:
        row.conduct = payload.conduct
    if "general_comment" in fields:
        row.general_comment = payload.general_comment
    if "absent_days" in fields:
        row.absent_days = payload.absent_days
    row.evaluated_by = user.id
    db.commit()
