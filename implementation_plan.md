# Implementation Plan — Sửa 4 Lệch M1 (BIGINT + Bloom + Giáo án + Endpoint)

## [Overview]

Sửa 4 điểm lệch giữa code hiện tại và plan `docs_vsf/plan_exam_learning_analytics.md` M1, đồng thời tận dụng 8 bảng `s360.cm_*` (hệ thống soạn giáo án) vừa được tích hợp. Mục tiêu: (1) đồng bộ ORM `ExamPaper`/`CurriculumUnit`/`ExamCompetency` từ UUID sang BIGINT/INTEGER khớp với `score_focused_schema.sql`, (2) sửa Bloom mapping sai ngữ nghĩa, (3) ingest giáo án từ `cm_*` vào Qdrant để RAG có thể đối chiếu cả SGK lẫn giáo án, (4) bổ sung endpoint `/exam-papers/{id}/content-analysis`.

Phạm vi: **chỉ phần M1-M4 analytics** (ExamPaper, CurriculumUnit, ExamCompetency). Không đụng `ai_sessions.id` (UUID giữ nguyên). Schema mới không có bảng `schools` — toàn bộ tenant isolation dùng `so_school_id INTEGER` trực tiếp.

**3 điểm bổ sung từ Gemini (đã xác thực code thật):**
1. `ExamPaper.school_id` (UUID FK `schools.id`) → `so_school_id INTEGER NOT NULL` — đổi cả tên cột ORM + tất cả query trong `exam_papers.py`
2. Qdrant filter tương thích ngược: khi `include_lesson_plans=False`, filter `source != "giao_an"` để không làm mất kết quả SGK cũ
3. View `v_exam_validity` cần được định nghĩa trong SQL + đổi `school_id` → `so_school_id`

## [Types]

### 1. ORM type changes (`src/models/tables.py`)

**ExamPaper** — đổi từ UUID sang BIGINT/INTEGER:
| Cột | Type cũ | Type mới |
|-----|---------|----------|
| `id` | `UUID` + `uuid_generate_v4()` | `BigInteger` + `autoincrement=True` |
| `school_id` | `UUID` FK `schools.id` | Đổi thành `so_school_id INTEGER NOT NULL` (schema mới không có bảng `schools`) |
| `subject_id` | `UUID` FK `subjects.id` | `Integer` (khớp `s360.dim_subject.id`) |
| `semester_id` | `UUID` FK `semesters.id` | `Integer` |
| `grade_id` | `UUID` FK `grades.id` | `Integer` |
| `uploaded_by` | `BigInteger` FK `users.id` | Giữ nguyên `BigInteger` |

**CurriculumUnit** — đổi từ UUID sang BIGINT:
| Cột | Type cũ | Type mới |
|-----|---------|----------|
| `id` | `UUID` + `uuid_generate_v4()` | `BigInteger` + `autoincrement=True` |
| `subject_id` | `UUID` FK `subjects.id` | `Integer` |
| `parent_id` | `UUID` FK self | `BigInteger` |

**ExamCompetency** — composite PK đổi sang BIGINT:
| Cột | Type cũ | Type mới |
|-----|---------|----------|
| `exam_paper_id` | `UUID` FK | `BigInteger` |
| `unit_id` | `UUID` FK | `BigInteger` |

### 2. SQL schema additions (`score_focused_schema.sql`)

Thêm các cột còn thiếu vào `public.exam_papers` (ORM có nhưng SQL chưa có):
```sql
ALTER TABLE public.exam_papers
  ADD COLUMN IF NOT EXISTS file_type public.file_type_enum,
  ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT,
  ADD COLUMN IF NOT EXISTS ai_analysis JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS content_difficulty NUMERIC(4,3),
  ADD COLUMN IF NOT EXISTS content_analyzed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS content_source public.file_type_enum,
  ADD COLUMN IF NOT EXISTS topics TEXT[],
  ADD COLUMN IF NOT EXISTS meta JSONB NOT NULL DEFAULT '{}'::jsonb;
```

Thêm View `v_exam_validity` (service `exam_validity.py` dùng SQL raw `FROM v_exam_validity`):
```sql
CREATE OR REPLACE VIEW v_exam_validity AS
SELECT
    ep.id AS exam_paper_id,
    ep.so_school_id,
    ep.subject_id,
    ep.semester_id,
    ep.grade_id,
    ep.score_category,
    ep.title,
    ep.content_difficulty AS cdi,
    ...
FROM public.exam_papers ep
LEFT JOIN s360.fact_gradebooks fg ON ...;
```
> **Lưu ý:** View này cần được định nghĩa đầy đủ dựa trên logic `exam_validity.py` hiện tại. Gemini cần đọc `exam_validity.py` để xây dựng SELECT chính xác, đảm bảo cột `so_school_id` (không phải `school_id`).

### 3. Pydantic schema changes

Tất cả DTO dùng `UUID` cho exam_paper_id, subject_id, unit_id, semester_id, grade_id → đổi sang `int`. `school_id` → `so_school_id: int` (schema mới không có bảng `schools`).

## [Files]

### File sửa (14 files):

**ORM:**
- `src/models/tables.py` — đổi ExamPaper, CurriculumUnit, ExamCompetency từ UUID → BIGINT/INTEGER; đổi `ExamPaper.school_id` → `ExamPaper.so_school_id`

**Service:**
- `src/services/content_difficulty.py` — bỏ `from uuid import UUID`, đổi tất cả type hint `UUID` → `int`, sửa `_bloom_distribution_and_alignment` mapping
- `src/services/exam_validity.py` — đổi `school_id: UUID` → `so_school_id: int`, đổi `semester_id`, `subject_id`, `grade_id`, `exam_paper_id` → `int`; sửa SQL raw `FROM v_exam_validity WHERE school_id` → `WHERE so_school_id`

**Schemas:**
- `src/schemas/exam_analysis.py` — `unit_id: UUID` → `int`
- `src/schemas/exam_validity.py` — `exam_paper_id`, `subject_id`, `semester_id`, `grade_id`, `class_id` → `int`; `school_id` → `so_school_id: int`

**API:**
- `src/api/v1/exam_validity.py` — đổi param `semester_id: UUID`, `subject_id: UUID`, `grade_id: UUID` → `int`; `user.school_id` → `user.so_school_id`
- `src/api/v1/exam_papers.py` — sửa `ExamPaper.school_id` → `ExamPaper.so_school_id` trong tất cả query; thêm endpoint `GET /exam-papers/{id}/content-analysis` (file đã tồn tại, chỉ bổ sung sub-route)
- `src/api/v1/knowledge_gap.py` — đã dùng int, nhưng cần verify JOIN `public.exam_papers` dùng `subject_id` INTEGER (hiện đang JOIN với UUID → lỗi)
- `src/api/v1/pass_fail_forecast.py` — tương tự, verify type

**RAG/Retrieval:**
- `src/services/retrieval.py` — thêm hàm `search_lesson_plan(query, mon, lop)` hoặc mở rộng `search_textbook` để search cả SGK + giáo án. **Tương thích ngược Qdrant:** Khi `include_lesson_plans=False`, filter `source != "giao_an"` (hoặc `source` không tồn tại) để không làm mất kết quả SGK cũ chưa có trường `source`

**SQL:**
- `docs_vsf/schemas/merged/score_focused_schema.sql` — thêm cột thiếu cho `exam_papers` + thêm View `v_exam_validity`

**Tests:**
- `tests/test_content_difficulty.py` — sửa mock data UUID → int, sửa test bloom mapping
- `tests/test_exam_validity_service.py` — sửa mock data UUID → int

### File tạo mới (1 file):
- `scripts/ingest_lesson_plans.py` — script ingest `cm_lessonplan` + `cm_lesson` + `cm_unit` + `cm_course` vào Qdrant collection `edu_knowledge` với metadata `source=giao_an`, `subject_id`, `grade_id`, `unit_name`, `lesson_name`

## [Functions]

### Hàm sửa:

1. **`src/services/content_difficulty.py`**:
   - `_get_or_create_unit(db, subject_id: int, ...)` — đổi UUID → int
   - `_load_catalog(db, subject_id: int, ...)` — đổi UUID → int
   - `merge_by_unit(items) -> dict[int, tuple[int, float]]` — đổi UUID → int
   - `_persist_competencies(db, paper_id: int, merged)` — đổi UUID → int
   - `analyze_exam_paper(exam_paper_id: int)` — đổi UUID → int
   - `_bloom_distribution_and_alignment(items)` — sửa mapping: `rem=1, und=2, app=3, anz=4-6`
   - `_resolve_units` — `unit_id` type int
   - `ResolvedCompetency.unit_id` — `int | None`
   - `AnalysisContext.subject_id` — `int`

2. **`src/services/exam_validity.py`**:
   - `compute_validity(db, so_school_id: int, semester_id: int, ...)` — đổi UUID → int (schema mới dùng `so_school_id INTEGER`)
   - `school_overview(db, so_school_id: int, semester_id: int)` — đổi UUID → int
   - `content_adjusted_ranking(db, so_school_id: int, grade_id: int, semester_id: int, subject_id: int, ...)` — đổi UUID → int
   - Sửa SQL raw: `WHERE v.school_id = :school_id` → `WHERE v.so_school_id = :so_school_id`

3. **`src/services/retrieval.py`**:
   - `search_textbook(query, mon, lop)` — mở rộng thêm param `include_lesson_plans: bool = False` để search cả 2 nguồn
   - **Tương thích ngược Qdrant:** Khi `include_lesson_plans=False`, filter `source != "giao_an"` (hoặc `source` không tồn tại) để không làm mất kết quả SGK cũ

4. **`src/api/v1/exam_validity.py`**:
   - `get_exam_validity(semester_id: int, ...)` — đổi UUID → int; `user.school_id` → `user.so_school_id`
   - `get_exam_validity_overview(semester_id: int, ...)` — đổi UUID → int; `user.school_id` → `user.so_school_id`
   - `get_content_adjusted_ranking(grade_id: int, semester_id: int, subject_id: int, ...)` — đổi UUID → int

5. **`src/api/v1/exam_papers.py`**:
   - Tất cả query `ExamPaper.school_id == user.school_id` → `ExamPaper.so_school_id == user.so_school_id`
   - Thêm `GET /exam-papers/{exam_paper_id}/content-analysis` → response_model `ExamContentAnalysis`

6. **`tests/test_content_difficulty.py`**:
   - `test_bloom_distribution_and_alignment` (dòng 460-481) — sửa expected values cho mapping mới

### Hàm mới:

7. **`scripts/ingest_lesson_plans.py`** — `ingest_lesson_plans()`: đọc `s360.cm_lessonplan` JOIN `cm_lesson` JOIN `cm_unit` JOIN `cm_course` → embed `content_own` + `name` + `description` → upsert vào Qdrant `edu_knowledge` với metadata `source=giao_an`, `subject_id`, `grade_id`, `unit_name`, `lesson_name`.

## [Classes]

### Sửa:
- `ExamPaper` (tables.py) — đổi column types UUID → BIGINT/INTEGER; `school_id` → `so_school_id`
- `CurriculumUnit` (tables.py) — đổi column types UUID → BIGINT/INTEGER
- `ExamCompetency` (tables.py) — đổi column types UUID → BIGINT
- `ResolvedCompetency` (content_difficulty.py) — `unit_id: int | None`
- `AnalysisContext` (content_difficulty.py) — `subject_id: int`
- `ExamValidityRead` (exam_validity.py) — `exam_paper_id: int`, `subject_id: int`, `semester_id: int`, `grade_id: int | None`
- `SchoolValidityOverview` (exam_validity.py) — giữ nguyên (không có UUID fields)
- `ExamContentAnalysis` (exam_analysis.py) — các field `unit_id` → int

## [Dependencies]

Không dependency mới. Dùng thư viện hiện có: `qdrant-client` (đã có), `sqlalchemy`, `pydantic`. Không đổi `requirements.txt`.

## [Testing]

1. **`tests/test_content_difficulty.py`**:
   - Sửa tất cả mock `ExamPaper`/`CurriculumUnit`/`ExamCompetency` từ UUID → int
   - Sửa `test_bloom_distribution_and_alignment` (dòng 460-481): expected values cho mapping mới `rem=1, und=2, app=3, anz=4-6`
   - Thêm test `test_bloom_mapping_correctness`: verify `bloom_level=1` → `remember`, `bloom_level=2` → `understand`, `bloom_level=3` → `apply`, `bloom_level=4` → `analyze`

2. **`tests/test_exam_validity_service.py`**:
   - Sửa mock data UUID → int cho exam_paper_id, subject_id, semester_id, grade_id

3. **`tests/test_knowledge_gap.py`** + **`tests/test_pass_fail_forecast.py`**:
   - Verify không bị lỗi type mismatch sau khi ORM đổi sang BIGINT

4. **Verify tổng**:
   - `ruff check` sạch
   - `pytest tests/test_content_difficulty.py tests/test_exam_validity_service.py tests/test_knowledge_gap.py tests/test_pass_fail_forecast.py` xanh
   - Chạy `scripts/apply_merged_schema.py` + `generate_full_system_mock_v4.py` để verify DDL + seed

## [Implementation Order]

1. **SQL**: Thêm cột thiếu vào `exam_papers` + View `v_exam_validity` trong `score_focused_schema.sql` + chạy `apply_merged_schema.py`
2. **ORM**: Sửa `tables.py` — ExamPaper (gồm `school_id`→`so_school_id`), CurriculumUnit, ExamCompetency UUID → BIGINT/INTEGER
3. **Service**: Sửa `content_difficulty.py` (type hints + bloom mapping) + `exam_validity.py` (type hints + SQL raw `so_school_id`)
4. **Schemas**: Sửa `exam_analysis.py`, `exam_validity.py` — UUID → int
5. **APIs**: Sửa `exam_validity.py` router params UUID → int + `user.so_school_id`; sửa `exam_papers.py` query `so_school_id`; verify `knowledge_gap.py`, `pass_fail_forecast.py` JOIN đúng type
6. **RAG**: Thêm `search_lesson_plan` vào `retrieval.py` (có filter tương thích ngược); cập nhật `_best_evidence` trong `content_difficulty.py` để dùng cả 2 nguồn
7. **Script ingest giáo án**: Tạo `scripts/ingest_lesson_plans.py`
8. **Endpoint**: Thêm `GET /exam-papers/{id}/content-analysis` vào `exam_papers.py` (file đã tồn tại)
9. **Tests**: Sửa tất cả test files UUID → int + bloom mapping
10. **Verify**: `ruff check` + `pytest` + `apply_merged_schema.py` + `mock_v4`