"""Ma trận đề + ráp đề chính thức từ ngân hàng câu hỏi.

RBAC: GV bộ môn/Trưởng bộ môn của môn được tạo ma trận + ráp đề; chỉ Trưởng bộ môn/ADMIN
được CHỐT đề (finalize → sinh exam_papers + exam_competencies, nối vào luồng chấm).
Xem docs/exam_generation_design.md §6.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.models import enums
from src.models.tables import ExamBlueprint, GeneratedExam, GeneratedExamItem, QuestionItem
from src.schemas.exam_generation import (
    AnswerKeyItemRead,
    AssembledItemRead,
    AssembleRequest,
    BlueprintCreate,
    BlueprintDraft,
    BlueprintRead,
    BlueprintUpdate,
    CoverageCellResult,
    CoverageRequest,
    GeneratedExamDetail,
    GeneratedExamRead,
    RecommendBlueprintRequest,
    VariantAnswerRead,
    VariantRead,
)
from src.services import blueprint_recommendation, exam_assembly, rbac

router = APIRouter(tags=["Exam Generation"])

_GRADE_CATEGORIES = {enums.ScoreCategory.MIDTERM, enums.ScoreCategory.FINAL}


def _validate_cells_sum(cells: list[dict], total_points: float) -> None:
    """Σ(số câu × điểm mỗi câu) phải bằng tổng điểm đề (sai lệch ≤ 0.01)."""
    summed = sum(c["num_questions"] * c["points_each"] for c in cells)
    if abs(summed - total_points) > 0.01:
        raise HTTPException(
            status_code=422,
            detail=f"Tổng điểm các ô ({summed}) khác tổng điểm đề ({total_points})",
        )


def _validate_blueprint_total(payload: BlueprintCreate) -> None:
    cells = [c.model_dump(mode="json") for c in payload.cells]
    _validate_cells_sum(cells, payload.total_points)


def _get_blueprint_in_school(db: Session, blueprint_id: UUID, school_id: UUID) -> ExamBlueprint:
    blueprint = db.get(ExamBlueprint, blueprint_id)
    if blueprint is None or blueprint.school_id != school_id:
        raise HTTPException(status_code=404, detail="Ma trận đề không tồn tại")
    return blueprint


def _can_edit_blueprint(db: Session, user, blueprint: ExamBlueprint) -> bool:
    """Tác giả ma trận, hoặc Trưởng bộ môn/ADMIN của môn đó, được sửa/xóa."""
    return user.id == blueprint.created_by or rbac.can_review_question(db, user, blueprint.subject_id)


def _get_generated_exam_in_school(db: Session, exam_id: UUID, school_id: UUID) -> GeneratedExam:
    gen = db.get(GeneratedExam, exam_id)
    if gen is None or gen.school_id != school_id:
        raise HTTPException(status_code=404, detail="Đề ráp không tồn tại")
    return gen


@router.post("/exam-blueprints", response_model=BlueprintRead, status_code=201)
def create_blueprint(payload: BlueprintCreate, user: CurrentUser, db: Session = Depends(get_db)):
    if payload.score_category not in _GRADE_CATEGORIES:
        raise HTTPException(status_code=422, detail="Chỉ tạo ma trận cho đề chính thức (MIDTERM/FINAL)")
    if not rbac.can_manage_question_bank(db, user, payload.subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    _validate_blueprint_total(payload)
    data = payload.model_dump(mode="json")
    blueprint = ExamBlueprint(
        **data,
        school_id=user.school_id,
        created_by=user.id,
        exam_format=blueprint_recommendation.derive_exam_format(data["cells"]),
    )
    db.add(blueprint)
    db.commit()
    db.refresh(blueprint)
    return blueprint


@router.get("/exam-blueprints", response_model=list[BlueprintRead])
def list_blueprints(subject_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    if not rbac.can_manage_question_bank(db, user, subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    stmt = select(ExamBlueprint).where(
        ExamBlueprint.school_id == user.school_id, ExamBlueprint.subject_id == subject_id
    )
    return list(db.execute(stmt.order_by(ExamBlueprint.created_at.desc())).scalars().all())


@router.post("/exam-blueprints/recommend", response_model=BlueprintDraft)
def recommend_blueprint(payload: RecommendBlueprintRequest, user: CurrentUser, db: Session = Depends(get_db)):
    """Gợi ý ma trận từ năng lực thực tế của trường — CHỈ đề xuất, không lưu (GV tự POST
    /exam-blueprints sau khi xem/chỉnh)."""
    if payload.score_category not in _GRADE_CATEGORIES:
        raise HTTPException(status_code=422, detail="Chỉ gợi ý ma trận cho đề chính thức (MIDTERM/FINAL)")
    if not rbac.can_manage_question_bank(db, user, payload.subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    try:
        return blueprint_recommendation.recommend(db, user.school_id, payload)
    except blueprint_recommendation.RecommendationInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/exam-blueprints/coverage", response_model=list[CoverageCellResult])
def check_coverage(payload: CoverageRequest, user: CurrentUser, db: Session = Depends(get_db)):
    """Đếm câu APPROVED có sẵn cho từng ô — cho GV biết thiếu câu TRƯỚC khi ráp đề (tránh 409)."""
    if not rbac.can_manage_question_bank(db, user, payload.subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    results = []
    for cell in payload.cells:
        cell_dict = cell.model_dump(mode="json")
        available = exam_assembly.count_candidates_for_cell(
            db, user.school_id, payload.subject_id, payload.grade_number, cell_dict
        )
        results.append(
            CoverageCellResult(
                unit_id=cell.unit_id,
                bloom_level=cell.bloom_level,
                question_type=cell.question_type,
                needed=cell.num_questions,
                available=available,
                shortfall=max(0, cell.num_questions - available),
            )
        )
    return results


@router.get("/exam-blueprints/{blueprint_id}", response_model=BlueprintRead)
def get_blueprint(blueprint_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    blueprint = _get_blueprint_in_school(db, blueprint_id, user.school_id)
    if not rbac.can_manage_question_bank(db, user, blueprint.subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    return blueprint


@router.patch("/exam-blueprints/{blueprint_id}", response_model=BlueprintRead)
def update_blueprint(blueprint_id: UUID, payload: BlueprintUpdate, user: CurrentUser, db: Session = Depends(get_db)):
    """Tinh chỉnh ma trận (tác giả hoặc Trưởng bộ môn/ADMIN). Re-validate Σ điểm sau khi merge."""
    blueprint = _get_blueprint_in_school(db, blueprint_id, user.school_id)
    if not _can_edit_blueprint(db, user, blueprint):
        raise HTTPException(status_code=403, detail="Không có quyền sửa ma trận này")
    data = payload.model_dump(exclude_unset=True, mode="json")
    for field, value in data.items():
        setattr(blueprint, field, value)
    _validate_cells_sum(blueprint.cells, float(blueprint.total_points))
    blueprint.exam_format = blueprint_recommendation.derive_exam_format(blueprint.cells)
    db.commit()
    db.refresh(blueprint)
    return blueprint


@router.delete("/exam-blueprints/{blueprint_id}", status_code=204)
def delete_blueprint(blueprint_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Xóa ma trận chưa từng được dùng để ráp đề (còn tham chiếu generated_exams → 409)."""
    blueprint = _get_blueprint_in_school(db, blueprint_id, user.school_id)
    if not _can_edit_blueprint(db, user, blueprint):
        raise HTTPException(status_code=403, detail="Không có quyền xóa ma trận này")
    used = db.execute(select(GeneratedExam.id).where(GeneratedExam.blueprint_id == blueprint_id).limit(1)).first()
    if used is not None:
        raise HTTPException(status_code=409, detail="Ma trận đã được dùng để ráp đề, không thể xóa")
    db.delete(blueprint)
    db.commit()


@router.post("/exams/assemble", response_model=GeneratedExamRead, status_code=201)
def assemble_exam(payload: AssembleRequest, user: CurrentUser, db: Session = Depends(get_db)):
    """Ráp đề từ ma trận: chọn câu APPROVED + sinh mã đề. Thiếu câu trong kho → 409."""
    blueprint = _get_blueprint_in_school(db, payload.blueprint_id, user.school_id)
    if not rbac.can_manage_question_bank(db, user, blueprint.subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    try:
        return exam_assembly.assemble(db, user, payload)
    except exam_assembly.InsufficientItemsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/exams", response_model=list[GeneratedExamRead])
def list_exams(
    subject_id: UUID,
    user: CurrentUser,
    status: enums.GenExamStatus | None = None,
    db: Session = Depends(get_db),
):
    """Danh sách đề đã ráp của một môn (mới nhất trước)."""
    if not rbac.can_manage_question_bank(db, user, subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    stmt = (
        select(GeneratedExam)
        .join(ExamBlueprint, ExamBlueprint.id == GeneratedExam.blueprint_id)
        .where(GeneratedExam.school_id == user.school_id, ExamBlueprint.subject_id == subject_id)
    )
    if status is not None:
        stmt = stmt.where(GeneratedExam.status == status)
    return list(db.execute(stmt.order_by(GeneratedExam.created_at.desc())).scalars().all())


@router.post("/exams/{exam_id}/finalize", response_model=GeneratedExamRead)
def finalize_exam(exam_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Chốt đề (Trưởng bộ môn/ADMIN): sinh exam_papers + exam_competencies (TEVI-ready)."""
    gen = _get_generated_exam_in_school(db, exam_id, user.school_id)
    blueprint = db.get(ExamBlueprint, gen.blueprint_id)
    if not rbac.can_review_question(db, user, blueprint.subject_id):
        raise HTTPException(status_code=403, detail="Chỉ Trưởng bộ môn được chốt đề chính thức")
    try:
        return exam_assembly.finalize(db, user, exam_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/exams/{exam_id}", response_model=GeneratedExamDetail)
def get_exam(exam_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Chi tiết đề ráp gồm các mã đề (đáp án ẩn — chỉ phục vụ in đề/đối soát)."""
    gen = _get_generated_exam_in_school(db, exam_id, user.school_id)
    blueprint = db.get(ExamBlueprint, gen.blueprint_id)
    if not rbac.can_manage_question_bank(db, user, blueprint.subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    return GeneratedExamDetail(**GeneratedExamRead.model_validate(gen).model_dump(), variants=_build_variants(db, gen))


@router.get("/exams/{exam_id}/answer-key", response_model=list[VariantAnswerRead])
def get_exam_answer_key(exam_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Đáp án + lời giải theo mã đề — chỉ người ráp đề hoặc Trưởng bộ môn/ADMIN (in phiếu đáp án)."""
    gen = _get_generated_exam_in_school(db, exam_id, user.school_id)
    blueprint = db.get(ExamBlueprint, gen.blueprint_id)
    if not (user.id == gen.created_by or rbac.can_review_question(db, user, blueprint.subject_id)):
        raise HTTPException(status_code=403, detail="Chỉ người ra đề hoặc Trưởng bộ môn được xem đáp án")
    return _build_answer_keys(db, gen)


def _variant_rows_with_items(
    db: Session, gen: GeneratedExam
) -> tuple[list[GeneratedExamItem], dict[UUID, QuestionItem]]:
    """Câu của mọi mã đề (tất cả biến thể) + map item_id -> QuestionItem, dùng chung cho
    hiển thị đề (ẩn đáp án) và tra đáp án (lộ đáp án, RBAC chặt hơn)."""
    rows = list(
        db.execute(
            select(GeneratedExamItem)
            .where(GeneratedExamItem.generated_exam_id == gen.id)
            .order_by(GeneratedExamItem.variant_code, GeneratedExamItem.position)
        )
        .scalars()
        .all()
    )
    item_map = {
        qi.id: qi
        for qi in db.execute(select(QuestionItem).where(QuestionItem.id.in_([r.item_id for r in rows]))).scalars().all()
    }
    return rows, item_map


def _build_variants(db: Session, gen: GeneratedExam) -> list[VariantRead]:
    """Dựng các mã đề: áp option_order để hiển thị đáp án đã xáo, ẩn answer_key."""
    rows, item_map = _variant_rows_with_items(db, gen)
    variants: dict[str, list[AssembledItemRead]] = {}
    for row in rows:
        qi = item_map[row.item_id]
        variants.setdefault(row.variant_code, []).append(
            AssembledItemRead(
                position=row.position,
                item_id=row.item_id,
                points=float(row.points),
                stem=qi.stem,
                question_type=qi.question_type,
                options=_apply_order(qi.options, row.option_order),
            )
        )
    return [VariantRead(variant_code=code, items=items) for code, items in variants.items()]


def _build_answer_keys(db: Session, gen: GeneratedExam) -> list[VariantAnswerRead]:
    """Đáp án + lời giải theo từng mã đề — KHÔNG ẩn answer_key (endpoint riêng, RBAC chặt hơn)."""
    rows, item_map = _variant_rows_with_items(db, gen)
    variants: dict[str, list[AnswerKeyItemRead]] = {}
    for row in rows:
        qi = item_map[row.item_id]
        variants.setdefault(row.variant_code, []).append(
            AnswerKeyItemRead(
                position=row.position,
                item_id=row.item_id,
                points=float(row.points),
                answer_key=qi.answer_key,
                solution=qi.solution,
            )
        )
    return [VariantAnswerRead(variant_code=code, items=items) for code, items in variants.items()]


def _apply_order(options: list[dict] | None, order: list | None) -> list[dict] | None:
    """Sắp lại options theo thứ tự key đã xáo (option_order) và CHỈ giữ key/text — không lộ
    misconception (chỉ đáp án đúng có misconception=null, lộ ra sẽ tiết lộ đáp án đúng)."""
    if not options:
        return None
    public = [{"key": o.get("key"), "text": o.get("text")} for o in options]
    if not order:
        return public
    by_key = {o["key"]: o for o in public}
    return [by_key[k] for k in order if k in by_key]
