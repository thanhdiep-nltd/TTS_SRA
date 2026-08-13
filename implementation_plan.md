# Implementation Plan

[Overview]
Sửa thẳng Report Agent hiện tại (`src/agents/report_agent/`) để hoạt động hoàn toàn trên schema mới (`s360` + `public` merged schema), giữ nguyên 4 loại báo cáo (academic_conduct, subject_quality, at_risk, subject_report) + báo cáo custom, render DOCX/HTML/PDF như hiện tại, không tạo V2, không tạo thêm bản sao.

Report Agent hiện tại đang query trực tiếp các bảng cũ trong `public` schema với PK dạng UUID (`schools`, `academic_years`, `semesters`, `grades`, `classes`, `subjects`, `students`, `enrollments`, `scores`, `student_term_reports`, `teacher_assignments`). Schema mới (`score_focused_schema.sql`) đã merge App Core (10 bảng `public`) + School Online DWH (14 bảng `s360`), tất cả PK chuyển sang BIGINT/INTEGER, không còn UUID. Các bảng điểm được tổ chức lại thành fact tables trong `s360` schema (`fact_gradebooks`, `fact_gradebooks_moet`, `fact_so_assignment_grade`, `fact_subject_academic_records`, `fact_overall_academic_records`). Dữ liệu s360 đã có seed data từ `data_mock/mock_full_data/generate_full_system_mock_v4.py`. Mục tiêu: sửa thẳng `report_agent/tools.py` để query đúng schema mới, giữ nguyên toàn bộ logic render DOCX/HTML và 4 loại báo cáo. Các phần khác của hệ thống (dashboard, data_service_agent, ews, repositories) vẫn dùng schema cũ — giữ nguyên, không đụng tới.

[Types]
Tạo ORM models mới cho schema `s360` và tạo schema mới `ReportExportRequestS360` (không sửa schema `ReportExportRequest` cũ).

### New ORM Models (`src/models/s360_tables.py`)

```python
from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy import Enum as SAEnum
from src.db.base import Base
from src.models import enums

_NOW = text("now()")

def pg_enum(py_enum, name: str) -> SAEnum:
    return SAEnum(
        py_enum,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        create_type=False,
    )

class DimSchoolYear(Base):
    __tablename__ = "dim_school_year"
    __table_args__ = {"schema": "s360"}
    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=False)
    fullname = Column(String(100), nullable=False)
    start_date = Column(Date)
    end_date = Column(Date)
    is_current = Column(Integer, default=0)
    is_locked = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)
    source_system = Column(String(50), default='SCHOOL_ONLINE')

class DimHomeroomClass(Base):
    __tablename__ = "dim_homeroom_class"
    __table_args__ = {"schema": "s360"}
    id = Column(BigInteger, primary_key=True)
    so_school_id = Column(Integer, nullable=False)
    school_year_id = Column(Integer, ForeignKey("s360.dim_school_year.id"), nullable=False)
    grade_id = Column(Integer, nullable=False)
    code = Column(String(50), nullable=False)
    fullname = Column(String(100), nullable=False)
    homeroom_teacher_id = Column(BigInteger)
    teacher_code = Column(String(50))
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)
    source_system = Column(String(50), default='SCHOOL_ONLINE')

class DimHomeroomClassStudent(Base):
    __tablename__ = "dim_homeroom_class_student"
    __table_args__ = {"schema": "s360"}
    id = Column(BigInteger, primary_key=True)
    so_student_id = Column(BigInteger, nullable=False)
    student_code = Column(String(50), nullable=False)
    student_name = Column(String(255), nullable=False)
    homeroom_class_id = Column(Integer, nullable=False)
    class_code = Column(String(50))
    class_name = Column(String(100))
    so_school_id = Column(Integer, nullable=False)
    school_year_id = Column(Integer, nullable=False)
    school_name = Column(String(255))
    teacher_code = Column(String(50))
    grade_id = Column(Integer, nullable=False)
    grade_name = Column(String(50))
    moet_code = Column(String(50))
    join_date = Column(Date)
    is_graduated = Column(Integer, default=0)
    status = Column(Integer, default=1)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)
    source_system = Column(String(50), default='SCHOOL_ONLINE')

class DimSubject(Base):
    __tablename__ = "dim_subject"
    __table_args__ = {"schema": "s360"}
    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    name_en = Column(String(255))
    subject_type = Column(String(50), default='CORE')
    subject_category = Column(String(50), default='MATH_SCIENCE')
    assessment_type = Column(pg_enum(enums.AssessmentType, "assessment_type_enum"), nullable=False, server_default=text("'SCORED'"))
    default_scale_name = Column(String(50), nullable=False, server_default=text("'SCALE_10'"))
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)
    source_system = Column(String(50), default='SCHOOL_ONLINE')

class DimExam(Base):
    __tablename__ = "dim_exam"
    __table_args__ = {"schema": "s360"}
    id = Column(BigInteger, primary_key=True)
    so_exam_id = Column(BigInteger)
    school_year_id = Column(Integer, nullable=False)
    subject_id = Column(Integer, ForeignKey("s360.dim_subject.id"), nullable=False)
    grade_id = Column(Integer, nullable=False)
    exam_code = Column(String(50))
    exam_name = Column(String(255), nullable=False)
    coefficient = Column(Numeric(10, 1), default=1.0)
    moet_semester_index = Column(Integer)
    max_grade = Column(Numeric(10, 1), default=10.0)
    is_periodic_exam = Column(Integer, default=0)
    is_moet = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)

class FactGradebooks(Base):
    __tablename__ = "fact_gradebooks"
    __table_args__ = {"schema": "s360"}
    id = Column(BigInteger, primary_key=True)
    so_school_id = Column(Integer, nullable=False)
    school_year_id = Column(Integer, ForeignKey("s360.dim_school_year.id"), nullable=False)
    semester_index = Column(Integer, nullable=False)
    student_code = Column(String(50), nullable=False)
    homeroom_class_id = Column(Integer, nullable=False)
    subject_id = Column(Integer, ForeignKey("s360.dim_subject.id"), nullable=False)
    so_exam_id = Column(BigInteger, ForeignKey("s360.dim_exam.id"))
    final_grade = Column(Numeric(10, 2))
    final_grade_percent = Column(Numeric(5, 2))
    final_grade_letter = Column(String(10))
    pass_fail_status = Column(pg_enum(enums.PassFail, "pass_fail_enum"))
    scale_name_used = Column(String(50), default='SCALE_10')
    max_grade = Column(Numeric(10, 1), default=10.0)
    is_locked = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)
    source_system = Column(String(50), default='SCHOOL_ONLINE')

class FactOverallAcademicRecords(Base):
    __tablename__ = "fact_overall_academic_records"
    __table_args__ = {"schema": "s360"}
    id = Column(BigInteger, primary_key=True)
    so_school_id = Column(Integer, nullable=False)
    school_year_id = Column(Integer, ForeignKey("s360.dim_school_year.id"), nullable=False)
    grade_id = Column(Integer, nullable=False)
    homeroom_class_id = Column(Integer, nullable=False)
    student_id = Column(BigInteger, nullable=False)
    student_code = Column(String(50), nullable=False)
    final_grade = Column(Numeric(10, 1))
    s1_final_grade = Column(Numeric(10, 1))
    s2_final_grade = Column(Numeric(10, 1))
    conduct = Column(pg_enum(enums.Conduct, "conduct_enum"))
    s1_conduct = Column(pg_enum(enums.Conduct, "conduct_enum"))
    s2_conduct = Column(pg_enum(enums.Conduct, "conduct_enum"))
    learning_capacity = Column(String(50))
    s1_learning_capacity = Column(String(50))
    s2_learning_capacity = Column(String(50))
    final_behavior_point = Column(Integer)
    day_of_absent = Column(Integer, default=0)
    s1_day_of_absent = Column(Integer, default=0)
    s2_day_of_absent = Column(Integer, default=0)
    homeroom_teacher_comment = Column(Text)
    principal_comment = Column(Text)
    is_passed_no_conditional = Column(Integer, default=1)
    is_graduated = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)

class FactSubjectAcademicRecords(Base):
    __tablename__ = "fact_subject_academic_records"
    __table_args__ = {"schema": "s360"}
    id = Column(BigInteger, primary_key=True)
    overall_record_id = Column(BigInteger)
    subject_id = Column(Integer, ForeignKey("s360.dim_subject.id"), nullable=False)
    student_code = Column(String(50), nullable=False)
    final_grade = Column(Numeric(10, 1))
    s1_final_grade = Column(Numeric(10, 1))
    s2_final_grade = Column(Numeric(10, 1))
    final_grade_after_summer = Column(Numeric(10, 1))
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)
```

### New Schema (`src/schemas/analytics.py`)

Tạo `ReportExportRequestS360` — **không sửa** `ReportExportRequest` cũ:

```python
class ReportExportRequestS360(BaseModel):
    report_type: Literal["academic_conduct", "subject_quality", "at_risk", "subject_report"]
    format: Literal["docx", "pdf", "html"]
    grade_level: str = "all"
    class_id: Optional[int] = None          # BIGINT — s360.dim_homeroom_class.id
    semester_index: Optional[int] = None    # 1 hoặc 2
    subject_id: Optional[int] = None        # INTEGER — s360.dim_subject.id
    school_year_id: Optional[int] = None    # INTEGER — s360.dim_school_year.id
    include_charts: bool = True
    include_tables: bool = True
    include_ai_insights: bool = True
    include_signature: bool = True
```

[Files]
Sửa thẳng `src/agents/report_agent/` để dùng schema mới, thêm models mới, giữ nguyên các file khác. **Không tạo bất kỳ file/package tên V2.**

### New Files

| File | Purpose |
|------|---------|
| `src/models/s360_tables.py` | ORM models cho schema `s360` (8 models: DimSchoolYear, DimHomeroomClass, DimHomeroomClassStudent, DimSubject, DimExam, FactGradebooks, FactOverallAcademicRecords, FactSubjectAcademicRecords) |

### Modified Files

| File | Changes |
|------|---------|
| `src/agents/report_agent/tools.py` | **Sửa thẳng** — bỏ import từ `src.models.tables` (các bảng cũ), import từ `src.models.s360_tables` (schema mới). **Giữ nguyên tên hàm gốc** (`compute_report_data`, `get_report_data_summary`, `generate_report_download_link`, `generate_custom_report_docx`), chỉ thay đổi logic bên trong. Giữ nguyên `render_markdown_to_docx`, `render_markdown_to_html`. Viết mới `is_valid_int`, `resolve_parameters` |
| `src/agents/report_agent/node.py` | Giữ nguyên cấu trúc, chỉ đổi import tools (nếu tên hàm đổi) |
| `src/schemas/analytics.py` | Thêm `ReportExportRequestS360` (giữ nguyên `ReportExportRequest` cũ) |
| `src/api/v1/analytics.py` | Thêm `_average_gpa_s360`, `_at_risk_classes_s360`, `_grade_distribution_s360` (giữ nguyên hàm cũ) |
| `src/api/v1/report_renderer.py` | Thêm `prepare_data_s360`, `generate_docx_report_s360`, `generate_html_report_s360` (giữ nguyên hàm cũ) |
| `src/api/v1/reports.py` | Thêm `export_analytics_report_s360` (giữ nguyên `export_analytics_report` cũ) |

### Unchanged Files (không đụng tới)

| File | Status |
|------|--------|
| `src/agents/graph.py` | Giữ nguyên — node `"report_agent"` không đổi |
| `src/agents/supervisor/node.py` | Giữ nguyên — không đổi |
| `src/agents/trace_adapter.py` | Giữ nguyên — không đổi |
| `src/models/tables.py` | Giữ nguyên — các agent khác (data_service_agent, ews, repositories) vẫn dùng |
| `src/api/v1/reports.py` (phần cũ) | Giữ nguyên `export_analytics_report()` |
| `src/api/v1/report_renderer.py` (phần cũ) | Giữ nguyên `prepare_data()`, `generate_docx_report()`, `generate_html_report()` |

[Functions]
Sửa thẳng logic query trong `report_agent/tools.py` (giữ tên hàm gốc) và thêm hàm `_s360` trong shared API files.

### Modified Functions in `src/agents/report_agent/tools.py` (giữ tên gốc, đổi logic bên trong)

| Function | Thay đổi |
|----------|-----------|
| `is_valid_uuid` → `is_valid_int` | Thay kiểm tra UUID → kiểm tra integer hợp lệ |
| `resolve_uuid_parameters` → `resolve_parameters` | Resolve text→BIGINT/INTEGER ID từ schema mới (class_id, semester_index, subject_id, school_year_id) |
| `compute_report_data` | Đổi logic query sang `s360.fact_gradebooks`, `s360.fact_overall_academic_records`, `s360.dim_homeroom_class_student`, `s360.dim_homeroom_class`, `s360.dim_subject`, `public.teacher_assignments` |
| `get_report_data_summary` | Gọi `compute_report_data` (đã sửa) |
| `generate_report_download_link` | Gọi `export_analytics_report_s360`. **Hỗ trợ cả 3 format (docx, html, pdf) cùng lúc** như hiện tại |
| `generate_custom_report_docx` | Giữ nguyên (không phụ thuộc schema) |

### Copied Functions (giữ nguyên, không thay đổi)

| Function | Source | Reason |
|----------|--------|--------|
| `render_markdown_to_docx` | `tools.py` (hiện tại) | Pure render, không phụ thuộc schema |
| `render_markdown_to_html` | `tools.py` (hiện tại) | Pure render, không phụ thuộc schema |

### New Functions in `src/api/v1/report_renderer.py`

| Function | Purpose |
|----------|---------|
| `prepare_data_s360` | Query students, scores, conduct từ `s360.fact_overall_academic_records`, `s360.dim_homeroom_class_student`, `s360.fact_gradebooks` |
| `generate_docx_report_s360` | Render DOCX từ data s360 |
| `generate_html_report_s360` | Render HTML từ data s360 |

### New Functions in `src/api/v1/analytics.py`

| Function | Purpose |
|----------|---------|
| `_average_gpa_s360` | Query `AVG(s360.fact_gradebooks.final_grade)` thay vì `AVG(scores.value)` |
| `_at_risk_classes_s360` | Query `s360.fact_gradebooks` GROUP BY `homeroom_class_id` HAVING AVG < 5.0 |
| `_grade_distribution_s360` | Query `s360.fact_gradebooks` JOIN `s360.dim_homeroom_class` |

### New Functions in `src/api/v1/reports.py`

| Function | Purpose |
|----------|---------|
| `export_analytics_report_s360` | Endpoint xuất báo cáo từ schema mới, nhận `ReportExportRequestS360`, gọi `prepare_data_s360` + `generate_*_report_s360` |

[Classes]
Tạo ORM models mới và schema classes mới.

### New Classes in `src/models/s360_tables.py`

| Class | Table | Schema |
|-------|-------|--------|
| `DimSchoolYear` | `dim_school_year` | `s360` |
| `DimHomeroomClass` | `dim_homeroom_class` | `s360` |
| `DimHomeroomClassStudent` | `dim_homeroom_class_student` | `s360` |
| `DimSubject` | `dim_subject` | `s360` |
| `DimExam` | `dim_exam` | `s360` |
| `FactGradebooks` | `fact_gradebooks` | `s360` |
| `FactOverallAcademicRecords` | `fact_overall_academic_records` | `s360` |
| `FactSubjectAcademicRecords` | `fact_subject_academic_records` | `s360` |

### New Classes in `src/schemas/analytics.py`

| Class | Changes |
|-------|---------|
| `ReportExportRequestS360` | Mới — `semester_index: Optional[int]`, `class_id: Optional[int]`, `subject_id: Optional[int]`, `school_year_id: Optional[int]` |

### Unchanged Classes

| Class | Status |
|-------|--------|
| `ReportExportRequest` | Giữ nguyên (dashboard vẫn dùng) |
| Tất cả models cũ trong `src/models/tables.py` | Giữ nguyên (data_service_agent, ews, repositories vẫn dùng) |

[Dependencies]
Không cần thêm package mới. Tất cả dependencies đã có sẵn:
- `sqlalchemy` — ORM queries
- `docx` — DOCX generation
- `langchain_core.tools` — `@tool` decorator
- `langgraph.prebuilt` — `create_react_agent`
- `fastapi` — API endpoints

[Testing]
Tạo test file mới và cập nhật test hiện có.

### New Test Files

| File | Purpose |
|------|---------|
| `tests/test_agents/test_report_agent_s360.py` | Test `resolve_parameters`, `compute_report_data`, `get_report_data_summary` với mock data từ schema mới |

### Modified Test Files

| File | Changes |
|------|---------|
| `tests/test_report_renderer.py` | Thêm test cases cho `prepare_data_s360`, `generate_docx_report_s360`, `generate_html_report_s360` |

### Test Strategy

1. **Unit test `resolve_parameters`**: Test resolve text→ID với mock `SessionLocal`
2. **Unit test `compute_report_data`**: Test query logic với mock data `s360` schema
3. **Integration test `get_report_data_summary`**: Test full flow từ tool call → response
4. **Integration test `generate_report_download_link`**: Test tạo file DOCX/HTML/PDF (cả 3 format)
5. **Regression test dashboard**: Đảm bảo dashboard vẫn hoạt động với schema cũ (hàm cũ không bị break)
6. **Verify `report_agent/tools.py` không còn import từ `src.models.tables`**: `grep -r "from src.models.tables" src/agents/report_agent/` phải trả về 0 kết quả

[Implementation Order]
Thứ tự triển khai để giảm thiểu xung đột và đảm bảo tích hợp thành công.

1. **Tạo `src/models/s360_tables.py`** — ORM models cho schema `s360` (8 models, không phụ thuộc gì khác)
2. **Thêm `ReportExportRequestS360` vào `src/schemas/analytics.py`** — Không sửa `ReportExportRequest` cũ
3. **Cập nhật `src/api/v1/analytics.py`** — Thêm `_average_gpa_s360`, `_at_risk_classes_s360`, `_grade_distribution_s360`
4. **Cập nhật `src/api/v1/report_renderer.py`** — Thêm `prepare_data_s360`, `generate_docx_report_s360`, `generate_html_report_s360`
5. **Cập nhật `src/api/v1/reports.py`** — Thêm `export_analytics_report_s360`
6. **Sửa thẳng `src/agents/report_agent/tools.py`** — Bỏ import từ `src.models.tables`, import từ `src.models.s360_tables`. Đổi logic bên trong `compute_report_data`, `get_report_data_summary`, `generate_report_download_link`. Viết mới `is_valid_int`, `resolve_parameters`. Giữ nguyên `render_markdown_to_docx`, `render_markdown_to_html`, `generate_custom_report_docx`
7. **Cập nhật `src/agents/report_agent/node.py`** — Đổi import tools (nếu tên hàm đổi)
8. **Tạo `tests/test_agents/test_report_agent_s360.py`** — Unit + integration tests
9. **Cập nhật `tests/test_report_renderer.py`** — Thêm test s360
10. **Verify `report_agent/tools.py` không còn import từ `src.models.tables`** — `grep -r "from src.models.tables" src/agents/report_agent/` = 0 kết quả
11. **Chạy toàn bộ tests** — Đảm bảo không break dashboard và các agent khác