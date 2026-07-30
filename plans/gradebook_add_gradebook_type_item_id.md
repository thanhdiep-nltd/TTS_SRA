# Kế hoạch: Bổ sung `gradebook_type_item_id` vào `dim_so_assignment`

## 1. Lý do

Hiện tại [`score_focused_schema.sql`](../docs_vsf/schemas/merged/score_focused_schema.sql) thiếu cột `gradebook_type_item_id` trong bảng [`dim_so_assignment`](../docs_vsf/schemas/merged/score_focused_schema.sql:457) so với CSV gốc [`School Online Schema.csv`](../docs/School%20Online%20Schema.csv:227).

**Hậu quả:** Không thể map bài tập LMS vào đầu điểm MOET cụ thể trong Gradebook.

## 2. Các file cần sửa

| File | Thao tác | Mức độ |
|------|---------|--------|
| `docs_vsf/schemas/merged/score_focused_schema.sql` | Thêm cột `gradebook_type_item_id` vào DDL của `dim_so_assignment` | ⭐ Critical |
| `data_mock/generate_full_system_mock.py` | Thêm `gradebook_type_item_id` vào seed data của `dim_so_assignment` | ⭐ Critical |

## 3. Chi tiết sửa

### 3.1. Sửa `docs_vsf/schemas/merged/score_focused_schema.sql`

Tại dòng 457-471, thêm dòng `gradebook_type_item_id` sau `date_assigned`:

```sql
CREATE TABLE s360.dim_so_assignment (
    assignment_id       BIGINT PRIMARY KEY,
    so_school_id        INTEGER NOT NULL,
    grade_id            INTEGER NOT NULL,
    semester_index      INTEGER CHECK (semester_index IN (1, 2)),
    subject_id          INTEGER NOT NULL REFERENCES s360.dim_subject(id),
    code                VARCHAR(50),
    fullname            VARCHAR(255) NOT NULL,
    max_grade           DECIMAL(10,1) DEFAULT 10.0,
    due_date            DATE,
    date_assigned       DATE,
    gradebook_type_item_id BIGINT REFERENCES s360.dim_exam_moet(gradebook_type_item_id),  -- THÊM
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    source_system       VARCHAR(50) DEFAULT 'LMS'
);
```

### 3.2. Sửa `data_mock/generate_full_system_mock.py`

Tại dòng 204-216, sửa seed data:

```python
# SỬA: thêm gradebook_type_item_id vào tuple
lms_assignments = [
    (1, 1, 7, 5, "ASS_TOAN7_W1", "Bài tập Tuần 1: Đại số Khối 7", 1),  # Map vào Midterm S1 (gradebook_type_item_id=1)
    (2, 1, 7, 5, "ASS_TOAN7_W2", "Bài tập Tuần 2: Hình học Khối 7", 1),
    (3, 1, 7, 7, "ASS_ANH7_W1", "Vocabulary & Grammar Unit 1", 1),
    (4, 1, 7, 8, "ASS_TOAN_ENG7_W1", "English Math Problem Set 1", 1),
]

# SỬA: INSERT thêm gradebook_type_item_id
for la in lms_assignments:
    session.execute(text("""
        INSERT INTO s360.dim_so_assignment 
        (assignment_id, so_school_id, grade_id, subject_id, code, fullname, gradebook_type_item_id)
        VALUES (:aid, :sid, :gid, :subid, :code, :fname, :gtii)
        ON CONFLICT (assignment_id) DO NOTHING;
    """), {"aid": la[0], "sid": la[1], "gid": la[2], "subid": la[3], 
           "code": la[4], "fname": la[5], "gtii": la[6]})
```

> **Lưu ý:** 4 assignment hiện tại đều map vào `gradebook_type_item_id=1` (Midterm S1). Có thể mở rộng sau nếu cần map vào các đầu điểm khác như Final S1 (id=2), Mid S2 (id=3), Final S2 (id=4).

## 4. Luồng dữ liệu sau khi sửa

```
LMS Assignment                    dim_exam_moet (MOET gradebook columns)
┌────────────────────┐           ┌──────────────────────────────┐
│ dim_so_assignment  │           │ gradebook_type_item_id = 1   │
│ assignment_id = 1  │──────────▶│ code = "EXAM_MID_S1"         │
│ gradebook_type_    │           │ coefficient = 1.0            │
│   item_id = 1      │           │ moet_semester_index = 1      │
└────────────────────┘           └──────────┬───────────────────┘
                                            │
                              ┌─────────────┴─────────────┐
                              │ fact_gradebooks_moet      │
                              │ gradebook_type_item_id = 1│
                              │ student_code = "..."      │
                              │ final_grade = 8.5         │
                              └───────────────────────────┘
```

## 5. Câu lệnh kiểm tra sau khi chạy

```sql
-- Kiểm tra map được không
SELECT 
    da.assignment_id,
    da.code AS assignment_code,
    da.fullname AS assignment_name,
    dem.gradebook_type_item_id,
    dem.gradebook_type_items_fullname AS moet_column_name,
    dem.coefficient
FROM s360.dim_so_assignment da
LEFT JOIN s360.dim_exam_moet dem 
    ON da.gradebook_type_item_id = dem.gradebook_type_item_id;

-- Xem assignment nào chưa được map (gradebook_type_item_id IS NULL)
SELECT assignment_id, code, fullname
FROM s360.dim_so_assignment
WHERE gradebook_type_item_id IS NULL;
```

## 6. Các bước thực hiện

1. Sửa `docs_vsf/schemas/merged/score_focused_schema.sql` — thêm cột `gradebook_type_item_id`
2. Sửa `data_mock/generate_full_system_mock.py` — thêm `gradebook_type_item_id` vào seed
3. Chạy lại `score_focused_schema.sql` để recreate schema
4. Chạy `generate_full_system_mock.py` để seed lại dữ liệu
5. Kiểm tra bằng câu lệnh SELECT ở mục 5
