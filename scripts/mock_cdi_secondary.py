"""Mock CDI cho khối THCS (cấp 2) đã có điểm thật.

CDI được random cho từng đề (TX/GK/CK), nhưng với GK/CK (đề có trong `v_exam_validity`) thì
KHÔNG còn random độc lập hoàn toàn trên 1 dải rộng — sẽ NEO quanh EDI thật của đúng tổ hợp
(subject, semester, score_category, grade) đó (± `_CDI_NOISE`). Lý do: nếu CDI random độc lập
trên dải [0.15, 0.85] trong khi EDI thật của trường thường chỉ rơi trong dải hẹp hơn (~0.25-0.55,
vì điểm trung bình thường quanh 5-7/10), thì PHẦN LỚN các lần random sẽ lệch khỏi EDI quá 0.25 chỉ
do may rủi — khiến gần như toàn trường bị gắn cờ INFLATION_OR_LEAK/LEARNING_GAP một cách giả tạo
(noise của bộ random, không phải tín hiệu thật). Neo quanh EDI giữ phần lớn các dòng ở vùng VALID,
chỉ còn 1 thiểu số lệch đủ lớn do nhiễu — giống phân phối thật hơn nhiều.

TX không có trong `mv_exam_difficulty` (chỉ tính cho MIDTERM/FINAL, xem docs/schema.sql:616) ->
không có EDI để neo -> vẫn random tự do trong `_CDI_FALLBACK_RANGE` (không ảnh hưởng bảng "Tin cậy
điểm số", chỉ phục vụ các màn khác: xem/map đề, cảnh báo công bằng đánh giá).

3 việc script làm (đều SQL hàng loạt — INSERT...SELECT / UPDATE...FROM, KHÔNG loop Python, vì dữ
liệu thử nghiệm có thể có hàng nghìn tổ hợp):
1. Tạo đề mock GK/CK cho các tổ hợp (subject, semester, grade) cấp 2 đã có điểm thật, chưa map.
2. Tạo đề mock TX cho các tổ hợp (subject, semester, class, column_index) cấp 2 đã có điểm TX
   thật, chưa map.
3. RANDOM LẠI content_difficulty cho đề mock đã tồn tại (title bắt đầu '[MOCK]' — CHỈ mock, KHÔNG
   đụng đề thật dù content_difficulty đang NULL vì đang chờ pipeline AI phân tích thật, tránh ghi
   đè giả lên kết quả thật sắp có): GK/CK neo theo EDI thật ± nhiễu nhỏ, TX vẫn random tự do.

Idempotent về việc TẠO mapping (không tạo trùng đề/mapping); CDI thì luôn random lại mỗi lần chạy.
Các case demo INFLATION_OR_LEAK/LEARNING_GAP có chủ đích vẫn nằm riêng ở
scripts/seed_exam_validity_demo.py (không bị script này ghi đè vì không có title '[MOCK]').
Chạy: python scripts/mock_cdi_secondary.py
"""

from sqlalchemy import text

from src.db.session import SessionLocal

_CDI_FALLBACK_RANGE = (0.3, 0.6)  # cho TX (không có EDI để neo) — dải hẹp hơn bản cũ, đỡ cực trị.
_CDI_NOISE = 0.12  # bán biên dao động quanh EDI thật cho GK/CK — phần lớn giữ trong vùng VALID (|D|<0.25).

_INSERT_PERIODIC = """
WITH cand AS (
    SELECT uuid_generate_v4() AS paper_id,
           d.subject_id, d.semester_id, d.score_category, d.grade_id, s.school_id, d.facility_index,
           (SELECT u.id FROM users u WHERE u.school_id = s.school_id
              AND u.role IN ('ADMIN', 'PRINCIPAL') LIMIT 1) AS uploader_id
    FROM mv_exam_difficulty d
    JOIN grades g ON g.id = d.grade_id
    JOIN subjects s ON s.id = d.subject_id
    WHERE g.school_level = 'SECONDARY'
      AND NOT EXISTS (
          SELECT 1 FROM exam_column_mappings m
          WHERE m.subject_id = d.subject_id AND m.semester_id = d.semester_id
            AND m.score_category = d.score_category AND m.grade_id = d.grade_id
      )
      AND EXISTS (SELECT 1 FROM users u WHERE u.school_id = s.school_id AND u.role IN ('ADMIN', 'PRINCIPAL'))
),
ins_papers AS (
    INSERT INTO exam_papers
        (id, school_id, subject_id, semester_id, grade_id, title, difficulty,
         uploaded_by, content_difficulty, content_analyzed_at, content_source)
    -- Neo CDI quanh EDI thật (1 - facility_index) ± nhiễu nhỏ, KHÔNG random độc lập trên dải rộng
    -- (xem giải thích đầu file) -> phần lớn rơi vào vùng VALID, chỉ thiểu số lệch đủ để bị gắn cờ.
    SELECT paper_id, school_id, subject_id, semester_id, grade_id,
           '[MOCK] ' || score_category || ' - chua upload file that',
           'MEDIUM', uploader_id,
           LEAST(0.95, GREATEST(0.05,
               round(((1 - facility_index) + (random() * 2 - 1) * :noise)::numeric, 3))),
           now(), 'OTHER'
    FROM cand
    RETURNING id
)
INSERT INTO exam_column_mappings (subject_id, semester_id, score_category, column_index, grade_id, exam_paper_id, mapped_by)
SELECT c.subject_id, c.semester_id, c.score_category, 1, c.grade_id, c.paper_id, c.uploader_id
FROM cand c
WHERE c.paper_id IN (SELECT id FROM ins_papers)
RETURNING id;
"""

_INSERT_REGULAR = """
WITH cand AS (
    SELECT uuid_generate_v4() AS paper_id,
           sc.subject_id, sc.semester_id, sc.column_index, sc.class_id, sub.school_id,
           (SELECT u.id FROM users u WHERE u.school_id = sub.school_id
              AND u.role IN ('ADMIN', 'PRINCIPAL') LIMIT 1) AS uploader_id
    FROM (SELECT DISTINCT subject_id, semester_id, column_index, class_id FROM scores
          WHERE score_category = 'REGULAR' AND status = 'APPROVED') sc
    JOIN classes c ON c.id = sc.class_id
    JOIN grades g ON g.id = c.grade_id
    JOIN subjects sub ON sub.id = sc.subject_id
    WHERE g.school_level = 'SECONDARY'
      AND NOT EXISTS (
          SELECT 1 FROM exam_column_mappings m
          WHERE m.subject_id = sc.subject_id AND m.semester_id = sc.semester_id
            AND m.score_category = 'REGULAR' AND m.column_index = sc.column_index AND m.class_id = sc.class_id
      )
      AND EXISTS (SELECT 1 FROM users u WHERE u.school_id = sub.school_id AND u.role IN ('ADMIN', 'PRINCIPAL'))
),
ins_papers AS (
    INSERT INTO exam_papers
        (id, school_id, subject_id, semester_id, grade_id, title, difficulty,
         uploaded_by, content_difficulty, content_analyzed_at, content_source)
    SELECT paper_id, school_id, subject_id, semester_id, NULL,
           '[MOCK] TX' || column_index || ' - chua upload file that',
           'MEDIUM', uploader_id,
           round((:lo + random() * (:hi - :lo))::numeric, 3),
           now(), 'OTHER'
    FROM cand
    RETURNING id
)
INSERT INTO exam_column_mappings (subject_id, semester_id, score_category, column_index, class_id, exam_paper_id, mapped_by)
SELECT c.subject_id, c.semester_id, 'REGULAR', c.column_index, c.class_id, c.paper_id, c.uploader_id
FROM cand c
WHERE c.paper_id IN (SELECT id FROM ins_papers)
RETURNING id;
"""

_REGENERATE_EXISTING = """
WITH calc AS (
    SELECT DISTINCT ON (ep.id) ep.id,
           CASE WHEN d.facility_index IS NOT NULL THEN
               LEAST(0.95, GREATEST(0.05,
                   round(((1 - d.facility_index) + (random() * 2 - 1) * :noise)::numeric, 3)))
           ELSE
               round((:lo + random() * (:hi - :lo))::numeric, 3)
           END AS new_cdi
    FROM exam_papers ep
    LEFT JOIN exam_column_mappings m ON m.exam_paper_id = ep.id
    LEFT JOIN mv_exam_difficulty d
      ON d.subject_id = m.subject_id AND d.semester_id = m.semester_id
     AND d.score_category = m.score_category AND d.grade_id = m.grade_id
    WHERE ep.title LIKE '[MOCK]%'
    ORDER BY ep.id
)
UPDATE exam_papers ep
SET content_difficulty = calc.new_cdi,
    content_analyzed_at = now(),
    content_source = 'OTHER'
FROM calc
WHERE ep.id = calc.id
RETURNING ep.id;
"""


def main() -> None:
    db = SessionLocal()
    try:
        params = {"lo": _CDI_FALLBACK_RANGE[0], "hi": _CDI_FALLBACK_RANGE[1], "noise": _CDI_NOISE}
        periodic_ids = db.execute(text(_INSERT_PERIODIC), params).all()
        regular_ids = db.execute(text(_INSERT_REGULAR), params).all()
        regenerated_ids = db.execute(text(_REGENERATE_EXISTING), params).all()
        db.commit()
        print(
            f"Done. GK/CK moi: {len(periodic_ids)}, TX moi: {len(regular_ids)}, "
            f"da neo lai CDI cho: {len(regenerated_ids)} de [MOCK] cu."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
