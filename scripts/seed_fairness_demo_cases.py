"""Cấy lại 1 vài trường hợp RÕ RÀNG cho demo tính năng cảnh báo công bằng đánh giá
(`src/services/student_fairness.py`), sau khi đã chạy `correlate_secondary_scores.py` (đồng bộ
điểm mọi học sinh quanh mặt bằng năng lực ổn định -> không còn nhiễu ngẫu nhiên gây flag tràn lan).

- 4 ca SUSPECT_FAVORITISM: chọn 4 (subject, semester, class) đã có CDI thật cho TX (>=0.6, "khó")
  và GK/CK theo khối (<=0.5, "dễ") — ghi đè điểm 1 học sinh trong lớp đó: TX cao (8.5-9.5),
  GK/CK thấp (3.0-4.5).
- 4 ca SUSPECT_SUPPRESSION: chọn 4 học sinh bất kỳ đã có đủ điểm TX+GK/CK — ghi đè: TX thấp
  (3.5-4.8), GK/CK cao (8.3-9.5).

Idempotent về việc CHỌN học sinh (ORDER BY cố định theo id) nhưng giá trị điểm random lại mỗi
lần chạy — chạy lại vẫn ra rõ 8 ca, chỉ số liệu cụ thể đổi nhẹ.
Chạy: python scripts/seed_fairness_demo_cases.py (sau correlate_secondary_scores.py)
"""

import random

from sqlalchemy import text

from src.db.session import SessionLocal

_RNG = random.Random(7)
_N_CASES = 4

_FAVORITISM_COMBOS = """
WITH tx_cdi AS (
    SELECT m.subject_id, m.semester_id, m.class_id, AVG(ep.content_difficulty) AS cdi
    FROM exam_column_mappings m JOIN exam_papers ep ON ep.id = m.exam_paper_id
    WHERE m.score_category = 'REGULAR' AND ep.content_difficulty IS NOT NULL
    GROUP BY m.subject_id, m.semester_id, m.class_id
    HAVING AVG(ep.content_difficulty) >= 0.6
),
periodic_cdi AS (
    SELECT m.subject_id, m.semester_id, m.grade_id,
           SUM(ep.content_difficulty * CASE m.score_category WHEN 'MIDTERM' THEN 2 WHEN 'FINAL' THEN 3 END)
             / SUM(CASE m.score_category WHEN 'MIDTERM' THEN 2 WHEN 'FINAL' THEN 3 END) AS cdi
    FROM exam_column_mappings m JOIN exam_papers ep ON ep.id = m.exam_paper_id
    WHERE m.score_category IN ('MIDTERM', 'FINAL') AND ep.content_difficulty IS NOT NULL
    GROUP BY m.subject_id, m.semester_id, m.grade_id
    HAVING SUM(ep.content_difficulty * CASE m.score_category WHEN 'MIDTERM' THEN 2 WHEN 'FINAL' THEN 3 END)
         / SUM(CASE m.score_category WHEN 'MIDTERM' THEN 2 WHEN 'FINAL' THEN 3 END) <= 0.5
)
SELECT tc.subject_id, tc.semester_id, tc.class_id
FROM tx_cdi tc
JOIN classes c ON c.id = tc.class_id
JOIN periodic_cdi pc ON pc.subject_id = tc.subject_id AND pc.semester_id = tc.semester_id AND pc.grade_id = c.grade_id
ORDER BY tc.subject_id, tc.class_id
LIMIT :n;
"""

_PICK_STUDENT_IN_CLASS = """
SELECT student_id FROM scores
WHERE subject_id = :subject_id AND semester_id = :semester_id AND class_id = :class_id AND status = 'APPROVED'
ORDER BY student_id LIMIT 1;
"""

_PICK_ANY_STUDENT_WITH_FULL_SCORES = """
SELECT sc.student_id, sc.subject_id, sc.semester_id
FROM scores sc
WHERE sc.status = 'APPROVED'
  AND EXISTS (SELECT 1 FROM scores x WHERE x.student_id = sc.student_id AND x.subject_id = sc.subject_id
              AND x.semester_id = sc.semester_id AND x.score_category = 'REGULAR' AND x.status = 'APPROVED')
  AND EXISTS (SELECT 1 FROM scores x WHERE x.student_id = sc.student_id AND x.subject_id = sc.subject_id
              AND x.semester_id = sc.semester_id AND x.score_category IN ('MIDTERM', 'FINAL') AND x.status = 'APPROVED')
GROUP BY sc.student_id, sc.subject_id, sc.semester_id
ORDER BY sc.student_id
OFFSET :offset LIMIT 1;
"""


def _set_scores(db, student_id, subject_id, semester_id, categories: list[str], lo: float, hi: float) -> int:
    result = db.execute(
        text(
            "UPDATE scores SET value = ROUND(CAST(:v AS numeric), 2) "
            "WHERE student_id = :sid AND subject_id = :subj AND semester_id = :sem "
            "AND score_category = ANY(:cats) AND status = 'APPROVED'"
        ),
        {
            "v": round(_RNG.uniform(lo, hi), 2),
            "sid": student_id,
            "subj": subject_id,
            "sem": semester_id,
            "cats": categories,
        },
    )
    return result.rowcount


def main() -> None:
    db = SessionLocal()
    try:
        seeded = []

        combos = db.execute(text(_FAVORITISM_COMBOS), {"n": _N_CASES}).all()
        for combo in combos:
            student = db.execute(
                text(_PICK_STUDENT_IN_CLASS),
                {"subject_id": combo.subject_id, "semester_id": combo.semester_id, "class_id": combo.class_id},
            ).first()
            if student is None:
                continue
            _set_scores(db, student.student_id, combo.subject_id, combo.semester_id, ["REGULAR"], 8.5, 9.5)
            _set_scores(db, student.student_id, combo.subject_id, combo.semester_id, ["MIDTERM", "FINAL"], 3.0, 4.5)
            seeded.append(("SUSPECT_FAVORITISM", student.student_id))

        for i in range(_N_CASES):
            row = db.execute(text(_PICK_ANY_STUDENT_WITH_FULL_SCORES), {"offset": i * 37}).first()
            if row is None:
                continue
            _set_scores(db, row.student_id, row.subject_id, row.semester_id, ["REGULAR"], 3.5, 4.8)
            _set_scores(db, row.student_id, row.subject_id, row.semester_id, ["MIDTERM", "FINAL"], 8.3, 9.5)
            seeded.append(("SUSPECT_SUPPRESSION", row.student_id))

        db.commit()
        print(f"Done. Da cay {len(seeded)} ca demo:")
        for flag, student_id in seeded:
            print(f"  {flag}: student_id={student_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
