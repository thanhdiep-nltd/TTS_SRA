# Implementation Plan — Tích hợp Bảng Hệ thống Soạn Giáo Án vào score_focused_schema.sql

## [Overview]

Tích hợp 8 bảng của hệ thống soạn giáo án (nguồn `docs_vsf/schemas/new/Schema Hệ thống Soạn Giáo Án.csv`) vào `docs_vsf/schemas/merged/score_focused_schema.sql` để hệ thống SRA có dữ liệu giáo án (khóa học, chương/bài, bài học, giáo án, mục tiêu, đánh giá) phục vụ M1 (Curriculum Blueprint Alignment / blind-spot detection) và M2 (knowledge gap theo unit).

Hiện tại `score_focused_schema.sql` (1417 dòng) chứa 24+ bảng public + s360 nhưng **chưa có bảng giáo án**. Hệ thống soạn giáo án cung cấp cấu trúc phân cấp: `cm_course` (khóa học) → `cm_unit` (chương/bài) → `cm_lesson` (bài học) → `cm_lessonplan` (giáo án) + `cm_lessontarget` (mục tiêu) + `cm_courseassessment`/`cm_courseassessmentunit` (đánh giá). Đây là nguồn "chuẩn chương trình" chi tiết hơn `curriculum_units` hiện có, giúp đối soát đề thi với giáo án (blind-spot) và map LMS/đề vào unit.

**Quyết định thiết kế (đã chốt với user):** đặt vào schema `s360`, PK chuyển sang `BIGINT`, chuẩn hóa tên cột sang `snake_case`, bỏ cột trùng `schoolyearid1`, **chỉ sửa DDL SQL** (không sửa ORM/seed trong plan này). Toàn bộ là data mock nên sửa trực tiếp vào SQL.

## [Types]

8 bảng mới trong schema `s360`, tất cả PK `BIGINT`, tên cột `snake_case`. Giữ tiền tố `cm_` để tránh xung đột với `s360.dim_course` (lớp học phần tự chọn) đã tồn tại.

### 1. `s360.cm_course` — Khóa học / môn học trong hệ soạn giáo án
| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| `id` | `BIGINT PRIMARY KEY` | |
| `content1` | `VARCHAR` | |
| `content2` | `VARCHAR` | |
| `subject_id` | `INTEGER REFERENCES s360.dim_subject(id)` | Môn học |
| `grade_id` | `INTEGER` | Khối |
| `period` | `DOUBLE PRECISION` | Số tiết |
| `is_subcourse` | `BOOLEAN DEFAULT FALSE` | Có phải khóa con |
| `subcode` | `VARCHAR(50)` | |
| `subname` | `VARCHAR(255)` | |
| `main_course_id` | `BIGINT REFERENCES s360.cm_course(id)` | Khóa cha (self-FK) |
| `code` | `VARCHAR(50)` | |
| `name` | `VARCHAR(255)` | |
| `description` | `TEXT` | |
| `order_number` | `INTEGER` | |
| `status` | `INTEGER DEFAULT 1` | |
| `created_by_id` | `VARCHAR(50)` | |
| `created_at` | `TIMESTAMPTZ DEFAULT NOW()` | |
| `modified_by_id` | `VARCHAR(50)` | |
| `modified_at` | `TIMESTAMPTZ` | |
| `is_deleted` | `BOOLEAN DEFAULT FALSE` | |
| `school_year_id` | `VARCHAR(50)` | Nguồn dùng string |
| `_processed_at` | `INTEGER` | Metadata ingest |
| `ingest_date` | `INTEGER` | Metadata ingest |

### 2. `s360.cm_unit` — Chương / bài trong khóa học
| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| `id` | `BIGINT PRIMARY KEY` | |
| `start_date` | `DATE` | |
| `end_date` | `DATE` | |
| `color` | `VARCHAR(20)` | |
| `content1` | `VARCHAR` | |
| `content2` | `VARCHAR` | |
| `course_id` | `BIGINT REFERENCES s360.cm_course(id)` | |
| `code` | `VARCHAR(50)` | |
| `name` | `VARCHAR(255)` | |
| `description` | `TEXT` | |
| `order_number` | `INTEGER` | |
| `period` | `DOUBLE PRECISION` | |
| `status` | `INTEGER DEFAULT 1` | |
| `created_by_id` | `VARCHAR(50)` | |
| `created_at` | `TIMESTAMPTZ DEFAULT NOW()` | |
| `modified_by_id` | `VARCHAR(50)` | |
| `modified_at` | `TIMESTAMPTZ` | |
| `is_deleted` | `BOOLEAN DEFAULT FALSE` | |
| `school_year_id` | `VARCHAR(50)` | |
| `_processed_at` | `INTEGER` | |
| `ingest_date` | `INTEGER` | |

### 3. `s360.cm_lesson` — Bài học
| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| `id` | `BIGINT PRIMARY KEY` | |
| `start_date` | `DATE` | |
| `end_date` | `DATE` | |
| `color` | `VARCHAR(20)` | |
| `content1` | `VARCHAR` | |
| `unit_id` | `BIGINT REFERENCES s360.cm_unit(id)` | |
| `code` | `VARCHAR(50)` | |
| `name` | `VARCHAR(255)` | |
| `description` | `TEXT` | |
| `order_number` | `INTEGER` | |
| `period` | `DOUBLE PRECISION` | |
| `status` | `INTEGER DEFAULT 1` | |
| `created_by_id` | `VARCHAR(50)` | |
| `created_at` | `TIMESTAMPTZ DEFAULT NOW()` | |
| `modified_by_id` | `VARCHAR(50)` | |
| `modified_at` | `TIMESTAMPTZ` | |
| `is_deleted` | `BOOLEAN DEFAULT FALSE` | |
| `school_year_id` | `VARCHAR(50)` | |
| `_processed_at` | `INTEGER` | |
| `ingest_date` | `INTEGER` | |

### 4. `s360.cm_lessonplan` — Giáo án (bỏ `schoolyearid1`)
| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| `id` | `BIGINT PRIMARY KEY` | |
| `lesson_id` | `BIGINT REFERENCES s360.cm_lesson(id)` | |
| `school_id` | `INTEGER` | |
| `school_year_id` | `VARCHAR(50)` | |
| `lesson_plan_activity_types` | `VARCHAR(255)` | |
| `start_date` | `DATE` | |
| `end_date` | `DATE` | |
| `has_custom_date_range` | `BOOLEAN DEFAULT FALSE` | |
| `approved_by_id` | `VARCHAR(50)` | |
| `approved_at` | `TIMESTAMPTZ` | |
| `code` | `VARCHAR(50)` | |
| `name` | `VARCHAR(255)` | |
| `description` | `TEXT` | |
| `order_number` | `INTEGER` | |
| `status` | `INTEGER DEFAULT 1` | |
| `created_by_id` | `VARCHAR(50)` | |
| `created_at` | `TIMESTAMPTZ DEFAULT NOW()` | |
| `reject_by_id` | `VARCHAR(50)` | |
| `reject_at` | `TIMESTAMPTZ` | |
| `modified_by_id` | `VARCHAR(50)` | |
| `modified_at` | `TIMESTAMPTZ` | |
| `is_deleted` | `BOOLEAN DEFAULT FALSE` | |
| `content_own` | `TEXT` | |
| `period` | `DOUBLE PRECISION` | |
| `period_lesson` | `DOUBLE PRECISION` | |
| `_processed_at` | `INTEGER` | |
| `ingest_date` | `INTEGER` | |

### 5. `s360.cm_lessontarget` — Mục tiêu bài học
| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| `id` | `BIGINT PRIMARY KEY` | |
| `lesson_id` | `BIGINT REFERENCES s360.cm_lesson(id)` | |
| `code` | `VARCHAR(50)` | |
| `name` | `VARCHAR(255)` | |
| `description` | `TEXT` | |
| `order_number` | `INTEGER` | |
| `status` | `INTEGER DEFAULT 1` | |
| `created_by_id` | `VARCHAR(50)` | |
| `created_at` | `TIMESTAMPTZ DEFAULT NOW()` | |
| `modified_by_id` | `VARCHAR(50)` | |
| `modified_at` | `TIMESTAMPTZ` | |
| `is_deleted` | `BOOLEAN DEFAULT FALSE` | |
| `school_year_id` | `VARCHAR(50)` | |
| `_processed_at` | `INTEGER` | |
| `ingest_date` | `INTEGER` | |

### 6. `s360.cm_courseassessment` — Đánh giá khóa học
| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| `id` | `BIGINT PRIMARY KEY` | |
| `course_id` | `BIGINT REFERENCES s360.cm_course(id)` | |
| `period` | `DOUBLE PRECISION` | |
| `start_date` | `DATE` | |
| `end_date` | `DATE` | |
| `content1` | `VARCHAR` | |
| `organization_method` | `VARCHAR(255)` | |
| `evaluate_method` | `VARCHAR(255)` | |
| `scale` | `VARCHAR(50)` | |
| `objective_subjective` | `DECIMAL(5,4)` | |
| `personal_group` | `DECIMAL(5,4)` | |
| `code` | `VARCHAR(50)` | |
| `name` | `VARCHAR(255)` | |
| `description` | `TEXT` | |
| `order_number` | `INTEGER` | |
| `status` | `INTEGER DEFAULT 1` | |
| `created_by_id` | `VARCHAR(50)` | |
| `created_at` | `TIMESTAMPTZ DEFAULT NOW()` | |
| `modified_by_id` | `VARCHAR(50)` | |
| `modified_at` | `TIMESTAMPTZ` | |
| `is_deleted` | `BOOLEAN DEFAULT FALSE` | |
| `school_year_id` | `VARCHAR(50)` | |
| `upload_time` | `TIMESTAMPTZ` | |
| `publish_time` | `TIMESTAMPTZ` | |
| `phase` | `VARCHAR(50)` | |
| `testspecs_filename` | `VARCHAR(255)` | |
| `testspecs_url` | `TEXT` | |
| `_processed_at` | `INTEGER` | |
| `ingest_date` | `INTEGER` | |

### 7. `s360.cm_courseassessmentunit` — Liên kết đánh giá ↔ unit (composite PK)
| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| `course_assessment_id` | `BIGINT REFERENCES s360.cm_courseassessment(id)` | |
| `unit_id` | `BIGINT REFERENCES s360.cm_unit(id)` | |
| `_processed_at` | `INTEGER` | |
| `ingest_date` | `INTEGER` | |
| | | `PRIMARY KEY (course_assessment_id, unit_id)` |

## [Files]

**File sửa (1 file):**
- `docs_vsf/schemas/merged/score_focused_schema.sql` — thêm 8 bảng `s360.cm_*` vào cuối file (sau bảng `student_knowledge_gaps`, trước dòng `-- End of score_focused_schema.sql DDL`), kèm `DROP TABLE IF EXISTS` cho từng bảng trong khối drop đầu file (để idempotent khi chạy lại `apply_merged_schema.py`).

**File tạo mới (1 file):**
- `docs_vsf/plan_lesson_plan_integration.md` — chính là file plan này.

**Không sửa:** `src/models/*.py`, `data_mock/*`, `scripts/apply_merged_schema.py` (theo quyết định "chỉ SQL DDL").

## [Functions]

Không thêm/sửa hàm Python trong plan này (chỉ DDL SQL). Các bảng `cm_*` sẽ được ORM/seed tích hợp ở giai đoạn sau (ngoài phạm vi).

## [Classes]

Không thêm/sửa class Python trong plan này.

## [Dependencies]

Không dependency mới. Chỉ thêm DDL SQL thuần (PostgreSQL 16+). Không đổi `requirements.txt`/`package.json`.

## [Testing]

- Chạy lại `scripts/apply_merged_schema.py` (hoặc `psql -f docs_vsf/schemas/merged/score_focused_schema.sql`) trên Neon để xác nhận DDL chạy sạch, không lỗi FK/type.
- Kiểm tra idempotency: chạy lại lần 2 → không lỗi (nhờ `DROP TABLE IF EXISTS` + `CREATE TABLE`).
- Xác nhận 8 bảng `s360.cm_*` tồn tại: `\dt s360.cm_*`.
- Xác nhận không xung đột tên với `s360.dim_course` (đã tồn tại).

## [Implementation Order]

1. Thêm 8 khối `DROP TABLE IF EXISTS s360.cm_* CASCADE;` vào phần drop đầu file (sau dòng 66, trước `-- ENUMS`).
2. Thêm 8 bảng `CREATE TABLE s360.cm_*` vào cuối file (sau `student_knowledge_gaps`, trước `-- End of score_focused_schema.sql DDL`), theo thứ tự FK: `cm_course` → `cm_unit` → `cm_lesson` → `cm_lessonplan` + `cm_lessontarget` → `cm_courseassessment` → `cm_courseassessmentunit`.
3. Thêm `CREATE INDEX` cho các cột FK thường query (`cm_unit.course_id`, `cm_lesson.unit_id`, `cm_lessonplan.lesson_id`, `cm_lessontarget.lesson_id`, `cm_courseassessment.course_id`).
4. Chạy `scripts/apply_merged_schema.py` để verify DDL sạch + idempotent.
5. Xác nhận 8 bảng tồn tại + không xung đột `dim_course`.