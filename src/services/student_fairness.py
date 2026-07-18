"""Cảnh báo công bằng đánh giá cấp học sinh: đối chiếu điểm Thường xuyên (TX, GV bộ môn ra đề
cho lớp mình) với điểm Giữa kỳ/Cuối kỳ (GK/CK, đề chung toàn khối do Trưởng bộ môn ra) — neo theo
CDI (độ khó nội dung) của từng loại đề — để phát hiện 2 dạng tiêu cực:

- SUSPECT_FAVORITISM (nghi "tủ đề"/ưu ái ở TX): TX khó (CDI cao) nhưng học sinh làm rất tốt, còn
  GK/CK (không được biết trước, không khó hơn TX) lại điểm thấp hẳn.
- SUSPECT_SUPPRESSION (nghi bị "chèn ép" ở TX): TX điểm thấp bất thường, nhưng GK/CK (đề chung,
  không ai ưu ái) lại điểm cao.

QUAN TRỌNG: đây là TÍN HIỆU CẢNH BÁO để BGH rà soát thêm, KHÔNG phải kết luận tiêu cực đã xác nhận
— chênh lệch có thể do nhiều nguyên nhân khác (học sinh ôn tập lệch, ốm vào ngày thi, v.v.).

`subject_id=None` -> quét TOÀN TRƯỜNG (mọi môn trong học kỳ) để BGH không phải dò tay từng môn.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.schemas.student_fairness import StudentFairnessRow

# Ngưỡng (xem docs/exam_triangulation_design.md cho tinh thần thiết kế; ngưỡng cụ thể ở đây mới,
# theo phong cách 0.25 divergence + 8.0/5.0 học lực đã dùng trong TEVI/scoring.py).
_TX_HARD_CDI = 0.6
_PERIODIC_NOT_HARDER_CDI = 0.5
_HIGH_SCORE = 8.0
_LOW_SCORE = 5.0
_MIN_GAP = 3.0
_MIN_COLUMNS = 2

_QUERY = """
WITH tx_cdi_by_class AS (
    SELECT m.subject_id, m.class_id, AVG(ep.content_difficulty) AS tx_cdi
    FROM exam_column_mappings m
    JOIN exam_papers ep ON ep.id = m.exam_paper_id
    WHERE m.semester_id = :semester_id AND m.score_category = 'REGULAR'
      AND ep.content_difficulty IS NOT NULL
      AND (CAST(:subject_id AS uuid) IS NULL OR m.subject_id = CAST(:subject_id AS uuid))
    GROUP BY m.subject_id, m.class_id
),
periodic_cdi_by_grade AS (
    SELECT m.subject_id, m.grade_id,
           SUM(ep.content_difficulty * CASE m.score_category WHEN 'MIDTERM' THEN 2 WHEN 'FINAL' THEN 3 END)
             / SUM(CASE m.score_category WHEN 'MIDTERM' THEN 2 WHEN 'FINAL' THEN 3 END) AS periodic_cdi
    FROM exam_column_mappings m
    JOIN exam_papers ep ON ep.id = m.exam_paper_id
    WHERE m.semester_id = :semester_id AND m.score_category IN ('MIDTERM', 'FINAL')
      AND ep.content_difficulty IS NOT NULL
      AND (CAST(:subject_id AS uuid) IS NULL OR m.subject_id = CAST(:subject_id AS uuid))
    GROUP BY m.subject_id, m.grade_id
),
tx_by_student AS (
    SELECT sc.student_id, sc.subject_id, sc.class_id, AVG(sc.value) AS tx_avg, COUNT(*) AS tx_n
    FROM scores sc
    WHERE sc.semester_id = :semester_id AND sc.score_category = 'REGULAR' AND sc.status = 'APPROVED'
      AND (CAST(:subject_id AS uuid) IS NULL OR sc.subject_id = CAST(:subject_id AS uuid))
    GROUP BY sc.student_id, sc.subject_id, sc.class_id
),
periodic_by_student AS (
    SELECT sc.student_id, sc.subject_id,
           SUM(sc.value * CASE sc.score_category WHEN 'MIDTERM' THEN 2 WHEN 'FINAL' THEN 3 END)
             / SUM(CASE sc.score_category WHEN 'MIDTERM' THEN 2 WHEN 'FINAL' THEN 3 END) AS periodic_avg,
           COUNT(*) AS periodic_n
    FROM scores sc
    WHERE sc.semester_id = :semester_id AND sc.score_category IN ('MIDTERM', 'FINAL') AND sc.status = 'APPROVED'
      AND (CAST(:subject_id AS uuid) IS NULL OR sc.subject_id = CAST(:subject_id AS uuid))
    GROUP BY sc.student_id, sc.subject_id
)
SELECT st.id AS student_id, st.student_code, st.full_name,
       c.id AS class_id, c.name AS class_name,
       tx.subject_id, sub.name AS subject_name,
       tx.tx_avg, tcdi.tx_cdi, tx.tx_n,
       pe.periodic_avg, pcdi.periodic_cdi, pe.periodic_n
FROM tx_by_student tx
JOIN periodic_by_student pe ON pe.student_id = tx.student_id AND pe.subject_id = tx.subject_id
JOIN students st ON st.id = tx.student_id
JOIN classes c ON c.id = tx.class_id
JOIN subjects sub ON sub.id = tx.subject_id
LEFT JOIN tx_cdi_by_class tcdi ON tcdi.class_id = tx.class_id AND tcdi.subject_id = tx.subject_id
LEFT JOIN periodic_cdi_by_grade pcdi ON pcdi.grade_id = c.grade_id AND pcdi.subject_id = tx.subject_id
WHERE sub.school_id = :school_id
  AND tx.tx_n >= :min_columns AND pe.periodic_n >= :min_columns
  AND (CAST(:class_id AS uuid) IS NULL OR c.id = CAST(:class_id AS uuid))
"""


def _format_cdi(cdi: float | None) -> str:
    return f"{cdi:.2f}" if cdi is not None else "chưa rõ (chưa phân tích nội dung đề)"


def _classify(
    tx_avg: float, tx_cdi: float | None, periodic_avg: float, periodic_cdi: float | None
) -> tuple[str, float, str] | None:
    """Trả (flag, gap, evidence) nếu nghi vấn, None nếu NORMAL (không trả về)."""
    gap_favoritism = tx_avg - periodic_avg
    gap_suppression = periodic_avg - tx_avg

    is_favoritism = (
        (tx_cdi is None or tx_cdi >= _TX_HARD_CDI)
        and tx_avg >= _HIGH_SCORE
        and (periodic_cdi is None or periodic_cdi <= _PERIODIC_NOT_HARDER_CDI)
        and periodic_avg <= _LOW_SCORE
        and gap_favoritism >= _MIN_GAP
    )
    if is_favoritism:
        evidence = (
            f"TX trung bình {tx_avg:.1f}/10 trên đề có độ khó nội dung (CDI) {_format_cdi(tx_cdi)} (khó), "
            f"nhưng Giữa kỳ/Cuối kỳ (đề chung toàn khối, GV không biết trước) chỉ đạt {periodic_avg:.1f}/10 "
            f"trên đề CDI {_format_cdi(periodic_cdi)} (không khó hơn TX) — chênh {gap_favoritism:.1f} điểm. "
            "Gợi ý: có thể GV bộ môn đã cho biết trước nội dung/đề TX."
        )
        return "SUSPECT_FAVORITISM", round(gap_favoritism, 2), evidence

    is_suppression = tx_avg <= _LOW_SCORE and periodic_avg >= _HIGH_SCORE and gap_suppression >= _MIN_GAP
    if is_suppression:
        evidence = (
            f"TX trung bình chỉ {tx_avg:.1f}/10, nhưng Giữa kỳ/Cuối kỳ (đề chung toàn khối, không ai ưu ái) "
            f"lại đạt {periodic_avg:.1f}/10 — chênh {gap_suppression:.1f} điểm. "
            "Gợi ý: học sinh có năng lực thật nhưng có thể bị đánh giá không công bằng ở TX."
        )
        return "SUSPECT_SUPPRESSION", round(gap_suppression, 2), evidence

    return None


def compute_fairness_signals(
    db: Session,
    school_id: UUID,
    semester_id: UUID,
    subject_id: UUID | None = None,
    class_id: UUID | None = None,
) -> list[StudentFairnessRow]:
    """Rà các học sinh có TX vs GK/CK lệch bất thường so với CDI. `subject_id=None` quét toàn trường.

    Chỉ trả về dòng bị nghi vấn (bỏ NORMAL).
    """
    rows = db.execute(
        text(_QUERY),
        {
            "school_id": school_id,
            "subject_id": subject_id,
            "semester_id": semester_id,
            "class_id": class_id,
            "min_columns": _MIN_COLUMNS,
        },
    ).all()

    results: list[StudentFairnessRow] = []
    for row in rows:
        tx_avg = float(row.tx_avg)
        periodic_avg = float(row.periodic_avg)
        tx_cdi = float(row.tx_cdi) if row.tx_cdi is not None else None
        periodic_cdi = float(row.periodic_cdi) if row.periodic_cdi is not None else None

        classification = _classify(tx_avg, tx_cdi, periodic_avg, periodic_cdi)
        if classification is None:
            continue
        flag, gap, evidence = classification
        confidence = "LOW" if tx_cdi is None or periodic_cdi is None else "HIGH"

        results.append(
            StudentFairnessRow(
                student_id=row.student_id,
                student_code=row.student_code,
                full_name=row.full_name,
                class_id=row.class_id,
                class_name=row.class_name,
                subject_id=row.subject_id,
                subject_name=row.subject_name,
                semester_id=semester_id,
                tx_avg=round(tx_avg, 2),
                tx_cdi=tx_cdi,
                periodic_avg=round(periodic_avg, 2),
                periodic_cdi=periodic_cdi,
                gap=gap,
                flag=flag,
                confidence=confidence,
                evidence=evidence,
            )
        )

    return sorted(results, key=lambda r: r.gap or 0, reverse=True)
