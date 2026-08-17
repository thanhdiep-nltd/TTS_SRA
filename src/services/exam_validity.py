"""Tam giác hóa độ khó đề thi (TEVI): đối chiếu EDI (thực nghiệm, từ điểm số thật) vs
CDI (nội dung, Bloom/chuẩn CT) để đánh giá độ tin cậy của điểm số và phát hiện phân kỳ
bất thường (lạm phát điểm, nghi lộ đề, lỗ hổng dạy-học). Không dùng độ khó GV tự khai báo
khi tạo đề vì mang tính chủ quan, không phải nguồn đối chiếu độc lập.

Xem docs/exam_triangulation_design.md cho mô hình toán đầy đủ.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.models import enums
from src.schemas.exam_validity import ContentAdjustedRankRow, ExamValidityRead, SchoolValidityOverview

# Ngưỡng tin cậy: dưới ngưỡng này, view đã tự gắn cờ LOW_SAMPLE/NO_CONTENT (xem migration).
_MIN_SAMPLE = 30
# Hệ số hiệu chỉnh thực lực theo độ khó nội dung (§2.5 design doc).
_ABILITY_K = 3.0

_BASE_SELECT = """
SELECT v.exam_paper_id, v.subject_id, v.subject_name, v.semester_id, v.score_category,
       v.grade_id, v.grade_name, v.n, v.mean_score, v.edi, v.cdi, v.divergence, v.flag,
       NULL AS column_index
FROM v_exam_validity v
WHERE v.so_school_id = :so_school_id
"""


def _confidence(n: int, cdi: float | None) -> str:
    """Mức tin cậy của nhận định: thấp nếu mẫu nhỏ hoặc chưa có CDI (nội dung chưa phân tích)."""
    return "HIGH" if n >= _MIN_SAMPLE and cdi is not None else "LOW"


def _row_to_read(row) -> ExamValidityRead:
    return ExamValidityRead(
        exam_paper_id=row.exam_paper_id,
        subject_id=row.subject_id,
        subject_name=row.subject_name,
        semester_id=row.semester_id,
        score_category=row.score_category,
        grade_id=row.grade_id,
        grade_name=row.grade_name,
        n=row.n,
        mean_score=float(row.mean_score),
        edi=float(row.edi),
        cdi=float(row.cdi) if row.cdi is not None else None,
        divergence=float(row.divergence) if row.divergence is not None else None,
        flag=row.flag,
        confidence=_confidence(row.n, row.cdi),
        column_index=row.column_index if hasattr(row, "column_index") else None,
    )


def compute_validity(
    db: Session,
    so_school_id: int,
    semester_id: int,
    subject_id: int | None = None,
    score_category: enums.ScoreCategory | None = None,
    grade_id: int | None = None,
    flagged_only: bool = False,
) -> list[ExamValidityRead]:
    """Trả các dòng tam giác hóa khớp bộ lọc.

    `subject_id`/`score_category` để trống -> quét TOÀN TRƯỜNG (mọi môn/loại điểm), không cần
    dò tay từng môn. `flagged_only=True` -> chỉ trả các dòng có cờ bất thường (bỏ VALID/NO_CONTENT),
    sắp xếp theo môn rồi khối — dùng cho màn cảnh báo mặc định.
    """
    sql = (
        _BASE_SELECT
        + " AND v.semester_id = :semester_id"
        + " AND (:subject_id IS NULL OR v.subject_id = :subject_id)"
        + " AND (:cat IS NULL OR v.score_category::text = :cat)"
        + " AND (:grade_id IS NULL OR v.grade_id = :grade_id)"
    )
    if flagged_only:
        sql += " AND v.flag NOT IN ('VALID', 'NO_CONTENT')"
    sql += " ORDER BY v.subject_name, v.grade_name"
    params = {
        "so_school_id": so_school_id,
        "semester_id": semester_id,
        "subject_id": subject_id,
        "cat": score_category.value if score_category is not None else None,
        "grade_id": grade_id,
    }
    rows = db.execute(text(sql), params).all()
    return [_row_to_read(r) for r in rows]


def school_overview(db: Session, so_school_id: int, semester_id: int) -> SchoolValidityOverview:
    """Tổng hợp toàn trường: đếm cờ theo loại + xếp các đề đáng rà soát nhất lên đầu."""
    sql = _BASE_SELECT + " AND v.semester_id = :semester_id"
    rows = db.execute(text(sql), {"so_school_id": so_school_id, "semester_id": semester_id}).all()
    items = [_row_to_read(r) for r in rows]

    flags_count: dict[str, int] = {}
    for item in items:
        flags_count[item.flag] = flags_count.get(item.flag, 0) + 1

    def _severity(item: ExamValidityRead) -> float:
        conf_weight = 1.0 if item.confidence == "HIGH" else 0.3
        return abs(item.divergence or 0) * conf_weight

    flagged_items = sorted(
        (i for i in items if i.flag not in ("VALID", "NO_CONTENT")),
        key=_severity,
        reverse=True,
    )

    return SchoolValidityOverview(
        total_checked=len(items),
        flags_count=flags_count,
        flagged_items=flagged_items,
    )


def content_adjusted_ranking(
    db: Session,
    so_school_id: int,
    grade_id: int,
    semester_id: int,
    subject_id: int,
    score_category: enums.ScoreCategory = enums.ScoreCategory.FINAL,
) -> list[ContentAdjustedRankRow]:
    """Xếp hạng các lớp trong khối theo thực lực neo-nội-dung (độc lập TB cohort).

    ability = clamp(0..10, raw_average + k * (cdi - 0.5)); k=0 (raw) nếu chưa có CDI.
    """
    cdi_row = db.execute(
        text(
            _BASE_SELECT + " AND v.subject_id = :subject_id AND v.semester_id = :semester_id"
            " AND v.score_category = :cat AND v.grade_id = :grade_id"
        ),
        {
            "so_school_id": so_school_id,
            "subject_id": subject_id,
            "semester_id": semester_id,
            "cat": score_category.value,
            "grade_id": grade_id,
        },
    ).first()
    cdi = float(cdi_row.cdi) if cdi_row is not None and cdi_row.cdi is not None else None

    sql = """
    SELECT c.id AS class_id, c.name AS class_name, AVG(s.value) AS raw_average
    FROM scores s
    JOIN classes c ON c.id = s.class_id
    WHERE c.grade_id = :grade_id AND s.subject_id = :subject_id AND s.semester_id = :semester_id
      AND s.score_category = :cat AND s.status = 'APPROVED'
    GROUP BY c.id, c.name
    ORDER BY c.name
    """
    rows = db.execute(
        text(sql),
        {"grade_id": grade_id, "subject_id": subject_id, "semester_id": semester_id, "cat": score_category.value},
    ).all()

    results = []
    for row in rows:
        raw = float(row.raw_average)
        ability = raw if cdi is None else max(0.0, min(10.0, raw + _ABILITY_K * (cdi - 0.5)))
        results.append(
            ContentAdjustedRankRow(
                class_id=row.class_id,
                class_name=row.class_name,
                raw_average=round(raw, 2),
                content_adjusted_ability=round(ability, 2),
                cdi=cdi if cdi is not None else 0.5,
            )
        )
    return sorted(results, key=lambda r: r.content_adjusted_ability, reverse=True)
