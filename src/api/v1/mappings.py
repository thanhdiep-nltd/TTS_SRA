from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.models import enums
from src.models.tables import Class, ExamColumnMapping
from src.schemas.exam import MappingCreate, MappingRead
from src.services import rbac

# prefix /scores: route tĩnh /scores/mappings phải đăng ký TRƯỚC scores.router (/scores/{id}).
router = APIRouter(prefix="/scores", tags=["Exam Mapping"])

_GRADE_LEVEL = {enums.ScoreCategory.MIDTERM, enums.ScoreCategory.FINAL}


@router.post("/mappings", response_model=MappingRead, status_code=201)
def create_mapping(payload: MappingCreate, user: CurrentUser, db: Session = Depends(get_db)):
    if not rbac.can_map(db, user, payload.score_category, payload.subject_id, payload.class_id, payload.grade_id):
        raise HTTPException(status_code=403, detail="Bạn không có quyền map đề cho cột này")
    mapping = ExamColumnMapping(**payload.model_dump(), mapped_by=user.id)
    db.add(mapping)
    db.commit()  # vi phạm CHECK/UNIQUE -> IntegrityError -> 409 (handler ở main)
    db.refresh(mapping)
    return mapping


@router.get("/mappings", response_model=list[MappingRead])
def list_mappings(
    user: CurrentUser,
    subject_id: UUID,
    semester_id: UUID,
    db: Session = Depends(get_db),
    class_id: UUID | None = None,
):
    """Map của (môn, học kỳ). Nếu truyền class_id: gồm TX của lớp + GK/CK của khối lớp đó."""
    stmt = select(ExamColumnMapping).where(
        ExamColumnMapping.subject_id == subject_id, ExamColumnMapping.semester_id == semester_id
    )
    if class_id is not None:
        cls = db.get(Class, class_id)
        grade_id = cls.grade_id if cls else None
        stmt = stmt.where(
            or_(
                and_(
                    ExamColumnMapping.score_category == enums.ScoreCategory.REGULAR,
                    ExamColumnMapping.class_id == class_id,
                ),
                and_(ExamColumnMapping.score_category.in_(_GRADE_LEVEL), ExamColumnMapping.grade_id == grade_id),
            )
        )
    return list(db.execute(stmt).scalars().all())


@router.delete("/mappings/{mapping_id}", status_code=204)
def delete_mapping(mapping_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    mapping = db.get(ExamColumnMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="Liên kết đề không tồn tại")
    if not rbac.can_map(db, user, mapping.score_category, mapping.subject_id, mapping.class_id, mapping.grade_id):
        raise HTTPException(status_code=403, detail="Bạn không có quyền gỡ liên kết này")
    db.delete(mapping)
    db.commit()
