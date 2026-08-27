"""Các helper thống kê s360 (score_focused_schema.sql) — tách khỏi src.api.v1.analytics.

Lý do tách: tránh circular import. `src.agents.report_agent.queries` (tầng agent) cần
`_average_gpa_s360` / `_at_risk_classes_s360`, nhưng import từ `src.api.v1.analytics`
kéo theo chuỗi `api.v1.__init__` → chat → graph → agents → report_agent → queries → circular.

Đặt ở `src/services/` (tầng service, không phụ thuộc API/agents) để cả `analytics.py`,
`reports.py` và `queries.py` đều import an toàn mà không gây vòng lặp.
"""

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.models.s360_tables import DimHomeroomClass, FactGradebooks
from src.schemas.analytics import GradeDistributionRow

# Bucket cho schema s360 (dựa trên fact_gradebooks.final_grade)
_BUCKET_S360 = case(
    (FactGradebooks.final_grade >= 8, "gioi"),
    (FactGradebooks.final_grade >= 6.5, "kha"),
    (FactGradebooks.final_grade >= 5, "trung_binh"),
    else_="yeu",
)


def _average_gpa_s360(db: Session, scope) -> float | None:
    """GPA trung bình từ schema s360 (fact_gradebooks.final_grade)."""
    stmt = select(func.avg(FactGradebooks.final_grade)).where(FactGradebooks.final_grade.isnot(None))
    if scope is not None:
        stmt = stmt.where(scope)
    val = db.scalar(stmt)
    return round(float(val), 2) if val is not None else None


def _at_risk_classes_s360(db: Session, scope) -> int:
    """Số lớp có ĐTB < 5.0 từ schema s360 (fact_gradebooks)."""
    sub = select(FactGradebooks.homeroom_class_id).where(FactGradebooks.final_grade.isnot(None))
    if scope is not None:
        sub = sub.where(scope)
    sub = sub.group_by(FactGradebooks.homeroom_class_id).having(func.avg(FactGradebooks.final_grade) < 5.0)
    return db.scalar(select(func.count()).select_from(sub.subquery("at_risk"))) or 0


def _grade_distribution_s360(db: Session, scope) -> list[GradeDistributionRow]:
    """Phân bố điểm theo khối từ schema s360 (fact_gradebooks JOIN dim_homeroom_class)."""
    stmt = (
        select(DimHomeroomClass.grade_id, _BUCKET_S360.label("bucket"), func.count())
        .select_from(FactGradebooks)
        .join(DimHomeroomClass, DimHomeroomClass.id == FactGradebooks.homeroom_class_id)
        .where(FactGradebooks.final_grade.isnot(None))
    )
    if scope is not None:
        stmt = stmt.where(scope)
    rows: dict[int, GradeDistributionRow] = {}
    for grade_id, bucket, count in db.execute(stmt.group_by(DimHomeroomClass.grade_id, _BUCKET_S360)).all():
        name = f"Khối {grade_id}"
        row = rows.setdefault(grade_id, GradeDistributionRow(name=name, gioi=0, kha=0, trung_binh=0, yeu=0))
        setattr(row, bucket, count)
    return list(rows.values())


__all__ = ["_average_gpa_s360", "_at_risk_classes_s360", "_grade_distribution_s360", "_BUCKET_S360"]