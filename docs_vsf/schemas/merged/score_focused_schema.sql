-- ============================================================
-- VSF Student Risk Alert (VSF SRA) - Score-Focused Database Schema DDL
-- Focused on Student Academic Performance & Scores for Text-to-SQL Agent Testing
-- Combines App Core (Public Schema - 10 Tables) + School Online DWH (s360 Schema - 14 Tables)
-- Total Tables: 24 Tables
-- 100% Primary Keys & Foreign Keys use BIGINT / INTEGER (No UUID)
-- Supports 6 Grading Scales & Multi-Scale per Subject
-- Includes Data Provenance (source_system) & Partitioned Score Types (Classroom, Exam, LMS Assignment)
-- DBMS: PostgreSQL 16+
-- ============================================================

-- Create Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create Schemas
CREATE SCHEMA IF NOT EXISTS public;
CREATE SCHEMA IF NOT EXISTS s360;

-- Drop Old Tables (if exists)
DROP TABLE IF EXISTS alembic_version CASCADE;
DROP TABLE IF EXISTS s360.train_student_subject_risk_dataset CASCADE;
DROP TABLE IF EXISTS s360.fact_student_subject_risk_predictions CASCADE;
DROP TABLE IF EXISTS s360.fact_student_risk_predictions CASCADE;
DROP TABLE IF EXISTS public.ai_observability_snapshots CASCADE;
DROP TABLE IF EXISTS public.ai_session_attachments CASCADE;
DROP TABLE IF EXISTS public.ai_messages CASCADE;
DROP TABLE IF EXISTS public.ai_sessions CASCADE;
DROP TABLE IF EXISTS public.classroom_recordings CASCADE;
DROP TABLE IF EXISTS public.report_schedules CASCADE;
DROP TABLE IF EXISTS public.audit_logs CASCADE;
DROP TABLE IF EXISTS public.exam_competencies CASCADE;
DROP TABLE IF EXISTS public.curriculum_units CASCADE;
DROP TABLE IF EXISTS public.exam_papers CASCADE;
DROP TABLE IF EXISTS public.refresh_tokens CASCADE;
DROP TABLE IF EXISTS public.users CASCADE;

DROP TABLE IF EXISTS s360.fact_swb_support CASCADE;
DROP TABLE IF EXISTS s360.fact_swb_survey CASCADE;
DROP TABLE IF EXISTS s360.fact_student_medical_history CASCADE;
DROP TABLE IF EXISTS s360.fact_student_life_events CASCADE;
DROP TABLE IF EXISTS s360.fact_course_attendences CASCADE;
DROP TABLE IF EXISTS s360.fact_so_class_attendance_statistics CASCADE;
DROP TABLE IF EXISTS s360.fact_so_homeroom_class_late_attendances CASCADE;
DROP TABLE IF EXISTS s360.fact_so_homeroom_class_attendances CASCADE;
DROP TABLE IF EXISTS s360.fact_so_daily_attendance CASCADE;
DROP TABLE IF EXISTS s360.fact_absent_logs CASCADE;
DROP TABLE IF EXISTS s360.fact_behavior_logs CASCADE;
DROP TABLE IF EXISTS s360.dim_course CASCADE;
DROP TABLE IF EXISTS s360.dim_behavior CASCADE;
DROP TABLE IF EXISTS s360.fact_course_enrolls CASCADE;
DROP TABLE IF EXISTS s360.fact_so_evaluate_process_subjects CASCADE;
DROP TABLE IF EXISTS s360.fact_overall_academic_records CASCADE;
DROP TABLE IF EXISTS s360.fact_subject_academic_records CASCADE;
DROP TABLE IF EXISTS s360.fact_so_assignment_grade CASCADE;
DROP TABLE IF EXISTS s360.fact_gradebooks_moet CASCADE;
DROP TABLE IF EXISTS s360.fact_gradebooks CASCADE;
DROP TABLE IF EXISTS s360.dim_grade_scale_detail CASCADE;
DROP TABLE IF EXISTS s360.dim_so_assignment CASCADE;
DROP TABLE IF EXISTS s360.dim_exam_moet CASCADE;
DROP TABLE IF EXISTS s360.dim_exam CASCADE;
DROP TABLE IF EXISTS s360.dim_subject CASCADE;
DROP TABLE IF EXISTS s360.dim_homeroom_class_student CASCADE;
DROP TABLE IF EXISTS s360.dim_homeroom_class CASCADE;
DROP TABLE IF EXISTS s360.dim_school_year CASCADE;

-- ============================================================
-- ENUMS & TYPES (Schema: public)
-- ============================================================

DROP TYPE IF EXISTS public.school_level_enum CASCADE;
DROP TYPE IF EXISTS public.user_role_enum CASCADE;
DROP TYPE IF EXISTS public.role_context_enum CASCADE;
DROP TYPE IF EXISTS public.score_category_enum CASCADE;
DROP TYPE IF EXISTS public.score_status_enum CASCADE;
DROP TYPE IF EXISTS public.assessment_type_enum CASCADE;
DROP TYPE IF EXISTS public.pass_fail_enum CASCADE;
DROP TYPE IF EXISTS public.conduct_enum CASCADE;
DROP TYPE IF EXISTS public.difficulty_enum CASCADE;
DROP TYPE IF EXISTS public.ai_session_role_enum CASCADE;
DROP TYPE IF EXISTS public.guardrail_status_enum CASCADE;
DROP TYPE IF EXISTS public.recording_rank_enum CASCADE;
DROP TYPE IF EXISTS public.file_type_enum CASCADE;

CREATE TYPE public.file_type_enum AS ENUM ('PDF', 'WORD', 'IMAGE', 'OTHER');

CREATE TYPE public.school_level_enum AS ENUM ('PRIMARY', 'SECONDARY', 'HIGH', 'ALL');

CREATE TYPE public.user_role_enum AS ENUM (
    'ADMIN',
    'PRINCIPAL',
    'GRADE_HEAD_PRIMARY',
    'HOMEROOM_TEACHER_PRIMARY',
    'SUBJECT_TEACHER',
    'HOMEROOM_TEACHER_SECONDARY',
    'SUBJECT_HEAD',
    'STUDENT',
    'PARENT'
);

CREATE TYPE public.role_context_enum AS ENUM (
    'HOMEROOM_PRIMARY',
    'HOMEROOM_SECONDARY',
    'SUBJECT_TEACHER',
    'GRADE_HEAD',
    'SUBJECT_HEAD'
);

CREATE TYPE public.score_category_enum AS ENUM ('ORAL', 'REGULAR', 'MIDTERM', 'FINAL');

CREATE TYPE public.score_status_enum AS ENUM ('DRAFT', 'SUBMITTED', 'APPROVED');

CREATE TYPE public.assessment_type_enum AS ENUM ('SCORED', 'REMARK');

CREATE TYPE public.pass_fail_enum AS ENUM ('DAT', 'CHUA_DAT');

CREATE TYPE public.conduct_enum AS ENUM ('TOT', 'KHA', 'TRUNG_BINH', 'YEU');

CREATE TYPE public.difficulty_enum AS ENUM ('EASY', 'MEDIUM', 'HARD');

CREATE TYPE public.ai_session_role_enum AS ENUM ('user', 'assistant', 'system');

CREATE TYPE public.guardrail_status_enum AS ENUM (
    'PASSED',
    'BLOCKED_INJECTION',
    'BLOCKED_SQL',
    'BLOCKED_PII',
    'BLOCKED_SENSITIVE'
);

CREATE TYPE public.recording_rank_enum AS ENUM ('EXCELLENT', 'SATISFACTORY', 'NEEDS_IMPROVEMENT');

-- ============================================================
-- SCHEMA: public (APP CORE, AUTH & EXTENDED OPERATIONS - 10 TABLES)
-- ============================================================

-- 1. Quản lý Tài khoản Người dùng & Đồng bộ Auth (App Core + DWH Link)
CREATE TABLE public.users (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    phone           VARCHAR(20),
    avatar_url      TEXT,
    role            public.user_role_enum NOT NULL,
    school_level    public.school_level_enum NOT NULL DEFAULT 'ALL',
    subject_id      INTEGER,
    teacher_code    VARCHAR(50), -- Mã giáo viên liên kết DWH
    student_code    VARCHAR(50), -- Mã học sinh liên kết DWH (nếu là HS/PH)
    so_student_id   BIGINT,      -- ID học sinh trong s360.dim_homeroom_class_student
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_school ON public.users(so_school_id);
CREATE INDEX idx_users_role   ON public.users(role);
CREATE INDEX idx_users_email  ON public.users(email);
CREATE INDEX idx_users_tcode  ON public.users(teacher_code);
CREATE INDEX idx_users_scode  ON public.users(student_code);

-- 2. Quản lý Refresh Token Đăng nhập JWT
CREATE TABLE public.refresh_tokens (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL UNIQUE,
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Phân công Giáo viên (RBAC scope cho chatbot & EWS — get_user_assignment_constraints)
CREATE TABLE public.teacher_assignments (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id          BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    academic_year_id BIGINT NOT NULL DEFAULT 2025,
    role_context     public.role_context_enum NOT NULL,
    class_id         BIGINT,
    grade_id         BIGINT,
    subject_id       BIGINT,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT assignment_consistency CHECK (
        (role_context = 'HOMEROOM_PRIMARY'   AND class_id IS NOT NULL AND subject_id IS NULL     AND grade_id IS NULL) OR
        (role_context = 'GRADE_HEAD'         AND grade_id IS NOT NULL AND class_id IS NULL       AND subject_id IS NULL) OR
        (role_context = 'SUBJECT_TEACHER'    AND class_id IS NOT NULL AND subject_id IS NOT NULL AND grade_id IS NULL) OR
        (role_context = 'HOMEROOM_SECONDARY' AND class_id IS NOT NULL AND subject_id IS NULL     AND grade_id IS NULL) OR
        (role_context = 'SUBJECT_HEAD'       AND subject_id IS NOT NULL AND class_id IS NULL     AND grade_id IS NULL)
    ),
    CONSTRAINT uq_teacher_assignment UNIQUE NULLS NOT DISTINCT (user_id, role_context, class_id, grade_id, subject_id, academic_year_id)
);
CREATE INDEX idx_ta_user    ON public.teacher_assignments(user_id);
CREATE INDEX idx_ta_class   ON public.teacher_assignments(class_id);
CREATE INDEX idx_ta_grade   ON public.teacher_assignments(grade_id);
CREATE INDEX idx_ta_subject ON public.teacher_assignments(subject_id);
CREATE INDEX idx_ta_year    ON public.teacher_assignments(academic_year_id);

-- 3. Bài kiểm tra / Đề thi Upload & Metadata AI (ĐIỂM BÀI THI CHI TIẾT)
CREATE TABLE public.exam_papers (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    subject_id      INTEGER NOT NULL,
    semester_id     INTEGER NOT NULL,
    grade_id        INTEGER,
    score_category  public.score_category_enum,
    title           VARCHAR(500) NOT NULL,
    description     TEXT,
    file_url        TEXT,
    difficulty      public.difficulty_enum,
    difficulty_coefficient NUMERIC(3,2) NOT NULL DEFAULT 1.00 CHECK (difficulty_coefficient BETWEEN 0.50 AND 1.50),
    num_questions   SMALLINT,
    total_points    NUMERIC(5,2),
    uploaded_by     BIGINT NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Phân cấp Chương trình Môn học (Curriculum Units)
CREATE TABLE public.curriculum_units (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id      INTEGER NOT NULL,
    grade_number    SMALLINT NOT NULL CHECK (grade_number BETWEEN 1 AND 12),
    parent_id       BIGINT REFERENCES public.curriculum_units(id) ON DELETE CASCADE,
    code            VARCHAR(50) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_curri_subject ON public.curriculum_units(subject_id, grade_number);

-- 5. Ánh xạ Trọng số Chuẩn đầu ra Bloom với Đề thi (Exam Competencies)
CREATE TABLE public.exam_competencies (
    exam_paper_id   BIGINT NOT NULL REFERENCES public.exam_papers(id) ON DELETE CASCADE,
    unit_id         BIGINT NOT NULL REFERENCES public.curriculum_units(id) ON DELETE RESTRICT,
    weight          NUMERIC(4,3) NOT NULL DEFAULT 0 CHECK (weight BETWEEN 0 AND 1),
    bloom_level     SMALLINT CHECK (bloom_level BETWEEN 1 AND 6),
    PRIMARY KEY (exam_paper_id, unit_id)
);

-- 6. Nhật ký Lịch sử Thay đổi (Audit Logs)
CREATE TABLE public.audit_logs (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name      VARCHAR(100) NOT NULL,
    record_id       BIGINT NOT NULL,
    action          VARCHAR(10) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by      BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
    old_values      JSONB,
    new_values      JSONB,
    ip_address      INET,
    user_agent      TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_table ON public.audit_logs(table_name, record_id);
CREATE INDEX idx_audit_time  ON public.audit_logs(changed_at DESC);

-- 7. Lịch Gửi Báo cáo Định kỳ (Report Schedules)
CREATE TABLE public.report_schedules (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_by      BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    report_type     VARCHAR(50) NOT NULL CHECK (report_type IN ('school_overview','grade','subject','class','at_risk')),
    filter_params   JSONB NOT NULL DEFAULT '{}',
    cron_expr       VARCHAR(100) NOT NULL,
    recipients      TEXT[] NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at     TIMESTAMPTZ,
    next_run_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Ghi âm Bài giảng & Đánh giá AI (Classroom Recordings)
CREATE TABLE public.classroom_recordings (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    teacher_id      BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    subject_id      INTEGER NOT NULL,
    class_id        INTEGER NOT NULL,
    semester_id     INTEGER NOT NULL,
    lesson_name     VARCHAR(255) NOT NULL,
    period          INTEGER NOT NULL,
    date            DATE NOT NULL,
    week            INTEGER NOT NULL,
    audio_file_url  TEXT NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
    progress        INTEGER NOT NULL DEFAULT 0,
    score           NUMERIC(3, 1),
    engagement      VARCHAR(20),
    rank            public.recording_rank_enum,
    ai_report       TEXT,
    transcript      JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_recordings_teacher ON public.classroom_recordings(teacher_id);
CREATE INDEX idx_recordings_class   ON public.classroom_recordings(class_id);

-- 9. Phiên Hội thoại AI Chat Text-to-SQL Agent
CREATE TABLE public.ai_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title           VARCHAR(500),
    context_filter  JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_session_user ON public.ai_sessions(user_id);

-- 10. Nhật ký Tin nhắn AI Chat & Guardrails Telemetry
CREATE TABLE public.ai_messages (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES public.ai_sessions(id) ON DELETE CASCADE,
    role            public.ai_session_role_enum NOT NULL,
    content         TEXT NOT NULL,
    generated_sql   TEXT,
    guardrail_status public.guardrail_status_enum,
    token_count     INTEGER,
    sources         JSONB,
    model_used      VARCHAR(100),
    latency_ms      INTEGER,
    rating          SMALLINT CHECK (rating IN (1, -1)),
    feedback_tag    VARCHAR(100),
    feedback_text   TEXT,
    feedback_at     TIMESTAMPTZ,
    thought_trace   JSONB,
    step_trace      JSONB,
    input_token_count INTEGER,
    output_token_count INTEGER,
    cost            NUMERIC(10, 6),
    llm_provider    VARCHAR(50),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_message_session ON public.ai_messages(session_id);

-- 10b. Tệp Đính kèm Phiên Hội thoại AI (Attachments)
CREATE TABLE public.ai_session_attachments (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES public.ai_sessions(id) ON DELETE CASCADE,
    uploaded_by     BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
    file_name       VARCHAR(255) NOT NULL,
    stored_name     VARCHAR(255) NOT NULL,
    file_type       public.file_type_enum NOT NULL,
    extracted_text  TEXT,
    char_count      INTEGER NOT NULL DEFAULT 0,
    truncated       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_attachment_session ON public.ai_session_attachments(session_id);

-- 10c. AgentOps Observability Snapshots (Dashboard Giám sát AI Agent)
CREATE TABLE public.ai_observability_snapshots (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    daily_cost_usd  NUMERIC(10, 6) NOT NULL DEFAULT 0,
    daily_budget_usd NUMERIC(10, 2) NOT NULL,
    latency_p95_ms  INTEGER,
    ttft_p95_ms     INTEGER,
    faithfulness_avg NUMERIC(4, 3),
    groundedness_avg NUMERIC(4, 3),
    tool_success_rate NUMERIC(4, 3),
    total_requests  INTEGER NOT NULL DEFAULT 0,
    total_tokens_in BIGINT NOT NULL DEFAULT 0,
    total_tokens_out BIGINT NOT NULL DEFAULT 0,
    agent_routes    JSONB NOT NULL DEFAULT '{}',
    agent_step_p95_ms JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_observability_captured_at ON public.ai_observability_snapshots(captured_at);



-- ============================================================
-- SCHEMA: s360 (STUDENT 360 DWH SCORE-FOCUSED - 14 TABLES)
-- ============================================================

-- 11. Danh mục Năm học
CREATE TABLE s360.dim_school_year (
    id              INTEGER PRIMARY KEY,
    code            VARCHAR(50) NOT NULL,
    fullname        VARCHAR(100) NOT NULL,
    start_date      DATE,
    end_date        DATE,
    is_current      INTEGER DEFAULT 0,
    is_locked       INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    source_system   VARCHAR(50) DEFAULT 'SCHOOL_ONLINE'
);
COMMENT ON TABLE s360.dim_school_year IS 'Danh mục năm học học đường';

-- 12. Danh mục Lớp Chủ nhiệm
CREATE TABLE s360.dim_homeroom_class (
    id                  BIGINT PRIMARY KEY,
    so_school_id        INTEGER NOT NULL,
    school_year_id      INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    grade_id            INTEGER NOT NULL,
    code                VARCHAR(50) NOT NULL,
    fullname            VARCHAR(100) NOT NULL,
    homeroom_teacher_id BIGINT,
    teacher_code        VARCHAR(50),
    is_active           INTEGER DEFAULT 1,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    source_system       VARCHAR(50) DEFAULT 'SCHOOL_ONLINE'
);
COMMENT ON TABLE s360.dim_homeroom_class IS 'Danh mục các lớp chủ nhiệm của trường học';

-- 13. Danh sách Học sinh & Liên kết Lớp Chủ nhiệm
CREATE TABLE s360.dim_homeroom_class_student (
    id                  BIGINT PRIMARY KEY,
    so_student_id       BIGINT NOT NULL,
    student_code        VARCHAR(50) NOT NULL,
    student_name        VARCHAR(255) NOT NULL,
    homeroom_class_id   INTEGER NOT NULL,
    class_code          VARCHAR(50),
    class_name          VARCHAR(100),
    so_school_id        INTEGER NOT NULL,
    school_year_id      INTEGER NOT NULL,
    school_name         VARCHAR(255),
    teacher_code        VARCHAR(50),
    grade_id            INTEGER NOT NULL,
    grade_name          VARCHAR(50),
    moet_code           VARCHAR(50),
    join_date           DATE,
    is_graduated        INTEGER DEFAULT 0,
    status              INTEGER DEFAULT 1,
    is_active           INTEGER DEFAULT 1,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    source_system       VARCHAR(50) DEFAULT 'SCHOOL_ONLINE'
);
CREATE INDEX idx_student_code ON s360.dim_homeroom_class_student(student_code);
CREATE INDEX idx_student_class ON s360.dim_homeroom_class_student(homeroom_class_id);
COMMENT ON TABLE s360.dim_homeroom_class_student IS 'Danh sách học sinh thuộc lớp chủ nhiệm của từng niên khóa';

-- 14. Danh mục Môn học Chính thức & Cấu hình Thang Điểm Môn
CREATE TABLE s360.dim_subject (
    id                  INTEGER PRIMARY KEY,
    code                VARCHAR(50) NOT NULL,
    name                VARCHAR(255) NOT NULL,
    name_en             VARCHAR(255),
    subject_type        VARCHAR(50) DEFAULT 'CORE',
    subject_category    VARCHAR(50) DEFAULT 'MATH_SCIENCE', -- MATH_SCIENCE | HUMANITIES | TECHNOLOGY | ARTS_PE
    assessment_type     public.assessment_type_enum NOT NULL DEFAULT 'SCORED', -- SCORED (cho điểm) | REMARK (Đạt/Chưa đạt)
    default_scale_name  VARCHAR(50) NOT NULL DEFAULT 'SCALE_10', -- Cấu hình thang điểm mặc định cho môn
    is_active           INTEGER DEFAULT 1,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    source_system       VARCHAR(50) DEFAULT 'SCHOOL_ONLINE'
);
COMMENT ON TABLE s360.dim_subject IS 'Danh mục môn học chính thức và cấu hình loại thang điểm theo môn';

-- 15. [PHÂN HỆ 1: ĐIỂM BÀI THI / KIỂM TRA ĐỊNH KỲ] Danh mục Kỳ thi & Đầu điểm LMS
CREATE TABLE s360.dim_exam (
    id                  BIGINT PRIMARY KEY,
    so_exam_id          BIGINT,
    school_year_id      INTEGER NOT NULL,
    subject_id          INTEGER NOT NULL REFERENCES s360.dim_subject(id),
    grade_id            INTEGER NOT NULL,
    exam_code           VARCHAR(50),
    exam_name           VARCHAR(255) NOT NULL,
    coefficient         DECIMAL(10,1) DEFAULT 1.0,
    moet_semester_index INTEGER CHECK (moet_semester_index IN (1, 2)),
    max_grade           DECIMAL(10,1) DEFAULT 10.0,
    is_periodic_exam    INTEGER DEFAULT 0,
    is_moet             INTEGER DEFAULT 1,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE s360.dim_exam IS 'Danh mục các kỳ thi và đầu điểm kiểm tra (Regular, Midterm, Final)';

-- 16. [PHÂN HỆ 1: ĐIỂM BÀI THI BỘ GD] Danh mục Đầu điểm Chuẩn Bộ Giáo dục (MOET)
CREATE TABLE s360.dim_exam_moet (
    gradebook_type_item_id    BIGINT PRIMARY KEY,
    gradebook_types_code      VARCHAR(50),
    gradebook_types_fullname  VARCHAR(255),
    gradebook_type_items_code VARCHAR(50),
    gradebook_type_items_fullname VARCHAR(255) NOT NULL,
    parent_id                 BIGINT,
    moet_semester_index       INTEGER CHECK (moet_semester_index IN (1, 2)),
    coefficient               DECIMAL(10,1) DEFAULT 1.0,
    max_grade                 DECIMAL(10,1) DEFAULT 10.0,
    is_active                 INTEGER DEFAULT 1,
    created_at                TIMESTAMPTZ DEFAULT NOW(),
    updated_at                TIMESTAMPTZ DEFAULT NOW(),
    source_system             VARCHAR(50) DEFAULT 'SCHOOL_ONLINE'
);
COMMENT ON TABLE s360.dim_exam_moet IS 'Danh mục chi tiết các đầu điểm chuẩn hóa theo quy định của Bộ Giáo dục (MOET)';

-- 17. [PHÂN HỆ 2: ĐIỂM BÀI TẬP LMS] Danh mục Bài tập / Nhiệm vụ Học tập LMS
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
    gradebook_type_item_id BIGINT REFERENCES s360.dim_exam_moet(gradebook_type_item_id),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    source_system       VARCHAR(50) DEFAULT 'LMS'
);
COMMENT ON TABLE s360.dim_so_assignment IS 'Danh mục bài tập / nhiệm vụ học tập trên hệ thống LMS';

-- 18. [MA TRẬN 6 THANG ĐIỂM] Ma trận Quy đổi Dải điểm & Tỷ lệ Universal Percent Bridge
CREATE TABLE s360.dim_grade_scale_detail (
    id                      BIGINT PRIMARY KEY,
    so_school_id            INTEGER NOT NULL DEFAULT 1,
    scale_name              VARCHAR(100) NOT NULL, -- 'SCALE_10', 'SCALE_100', 'SCALE_4', 'SCALE_6', 'LETTER_AF', 'PASS_FAIL'
    max_score               NUMERIC(5,2) NOT NULL DEFAULT 10.00,
    min_score_range         NUMERIC(5,2),
    max_score_range         NUMERIC(5,2),
    min_percent             NUMERIC(5,2) NOT NULL,
    max_percent             NUMERIC(5,2) NOT NULL,
    representative_percent  NUMERIC(5,2) NOT NULL,
    grade_letter            VARCHAR(10),  -- 'A+', 'A', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F'
    grade_label             VARCHAR(100), -- 'Xuất sắc', 'Giỏi', 'Khá', 'Trung bình', 'Yếu'
    gpa_scale_4             NUMERIC(3,2), -- 4.0, 3.5, 3.0, 2.5, 2.0, 1.0, 0.0
    scale_6_value           SMALLINT,     -- 1, 2, 3, 4, 5, 6
    pass_fail_status        public.pass_fail_enum, -- 'DAT', 'CHUA_DAT'
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE s360.dim_grade_scale_detail IS 'Bảng ma trận cấu hình quy đổi giữa 6 thang điểm làm cầu nối chuẩn hóa cho Text-to-SQL Agent';

-- 19. [PHÂN HỆ 3: ĐIỂM TRÊN LỚP / SỔ ĐIỂM HỌC BẠ LMS] Sổ điểm Học phần / môn học tổng hợp
CREATE TABLE s360.fact_gradebooks (
    id                  BIGINT PRIMARY KEY,
    so_school_id        INTEGER NOT NULL,
    school_year_id      INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    semester_index      INTEGER NOT NULL CHECK (semester_index IN (1, 2)),
    student_code        VARCHAR(50) NOT NULL,
    homeroom_class_id   INTEGER NOT NULL,
    subject_id          INTEGER NOT NULL REFERENCES s360.dim_subject(id),
    so_exam_id          BIGINT REFERENCES s360.dim_exam(id),
    
    -- Các giá trị biểu diễn điểm số trên lớp & tổng kết học bạ tùy theo thang điểm môn
    final_grade         DECIMAL(10,2),    -- Điểm số trên lớp / tổng kết (Thang 10, 100, 4, 6)
    final_grade_percent NUMERIC(5,2),     -- Tỷ lệ % đại diện quy đổi
    final_grade_letter  VARCHAR(10),      -- Điểm chữ ('A+', 'A', 'B'...)
    pass_fail_status    public.pass_fail_enum, -- Đạt / Chưa đạt
    scale_name_used     VARCHAR(50) DEFAULT 'SCALE_10', -- Thang điểm thực tế được dùng
    max_grade           DECIMAL(10,1) DEFAULT 10.0,
    
    is_locked           INTEGER DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    source_system       VARCHAR(50) DEFAULT 'SCHOOL_ONLINE'
);
CREATE INDEX idx_fg_student ON s360.fact_gradebooks(student_code);
CREATE INDEX idx_fg_subject ON s360.fact_gradebooks(subject_id);
CREATE INDEX idx_fg_exam    ON s360.fact_gradebooks(so_exam_id);
COMMENT ON TABLE s360.fact_gradebooks IS 'Sổ điểm học bạ trên lớp tổng hợp của học sinh (Tổng hợp điểm miệng, thường xuyên, kiểm tra định kỳ)';

-- 20. [PHÂN HỆ 3: ĐIỂM TRÊN LỚP CHUẨN BỘ] Sổ điểm Chuẩn Bộ Giáo dục (MOET)
CREATE TABLE s360.fact_gradebooks_moet (
    id                      BIGINT PRIMARY KEY,
    so_school_id            INTEGER NOT NULL,
    school_year_id          INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    semester_index          INTEGER NOT NULL CHECK (semester_index IN (1, 2)),
    grade_id                INTEGER NOT NULL,
    subject_id              INTEGER NOT NULL REFERENCES s360.dim_subject(id),
    student_code            VARCHAR(50) NOT NULL,
    homeroom_class_id       INTEGER NOT NULL,
    gradebook_type_item_id  BIGINT REFERENCES s360.dim_exam_moet(gradebook_type_item_id),
    final_grade             DECIMAL(10,1),
    comment                 VARCHAR(500),
    is_locked               INTEGER DEFAULT 0,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    source_system           VARCHAR(50) DEFAULT 'MOET_APP'
);
CREATE INDEX idx_fgm_student ON s360.fact_gradebooks_moet(student_code);
CREATE INDEX idx_fgm_item    ON s360.fact_gradebooks_moet(gradebook_type_item_id);
COMMENT ON TABLE s360.fact_gradebooks_moet IS 'Sổ điểm trên lớp chuẩn hóa theo quy định của Bộ Giáo dục (MOET)';

-- 21. [PHÂN HỆ 2: ĐIỂM BÀI TẬP LMS CHI TIẾT] Điểm Bài tập LMS (Assignments)
CREATE TABLE s360.fact_so_assignment_grade (
    id                  BIGINT PRIMARY KEY,
    so_school_id        INTEGER NOT NULL,
    assignment_id       BIGINT NOT NULL REFERENCES s360.dim_so_assignment(assignment_id),
    user_id             BIGINT,
    student_code        VARCHAR(50) NOT NULL,
    final_grade         DECIMAL(10,1), -- Điểm bài tập được giao trên LMS
    comment             TEXT,
    is_locked           INTEGER DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    source_system       VARCHAR(50) DEFAULT 'LMS'
);
CREATE INDEX idx_fag_assignment ON s360.fact_so_assignment_grade(assignment_id);
CREATE INDEX idx_fag_student    ON s360.fact_so_assignment_grade(student_code);
COMMENT ON TABLE s360.fact_so_assignment_grade IS 'Bảng ghi nhận kết quả điểm số bài tập (Assignment) trên LMS';

-- 22. Học bạ Môn học Chi tiết Cả năm
CREATE TABLE s360.fact_subject_academic_records (
    id                       BIGINT PRIMARY KEY,
    overall_record_id        BIGINT,
    subject_id               INTEGER NOT NULL REFERENCES s360.dim_subject(id),
    student_code             VARCHAR(50) NOT NULL,
    final_grade              DECIMAL(10,1), -- Điểm trung bình môn cả năm
    s1_final_grade           DECIMAL(10,1), -- Điểm HK1
    s2_final_grade           DECIMAL(10,1), -- Điểm HK2
    final_grade_after_summer DECIMAL(10,1),
    created_at               TIMESTAMPTZ DEFAULT NOW(),
    updated_at               TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE s360.fact_subject_academic_records IS 'Kết quả học tập tổng kết chi tiết theo môn học cả năm';

-- 23. Học bạ Tổng kết Cả năm Toàn diện (GPA, Học lực, Hạnh kiểm)
CREATE TABLE s360.fact_overall_academic_records (
    id                          BIGINT PRIMARY KEY,
    so_school_id                INTEGER NOT NULL,
    school_year_id              INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    grade_id                    INTEGER NOT NULL,
    homeroom_class_id           INTEGER NOT NULL,
    student_id                  BIGINT NOT NULL,
    student_code                VARCHAR(50) NOT NULL,
    
    final_grade                 DECIMAL(10,1), -- ĐTB cả năm
    s1_final_grade              DECIMAL(10,1), -- ĐTB HK1
    s2_final_grade              DECIMAL(10,1), -- ĐTB HK2
    
    conduct                     public.conduct_enum, -- Hạnh kiểm cả năm
    s1_conduct                  public.conduct_enum, -- Hạnh kiểm HK1
    s2_conduct                  public.conduct_enum, -- Hạnh kiểm HK2
    
    learning_capacity          VARCHAR(50), -- Học lực cả năm ('Giỏi', 'Khá', 'Trung bình', 'Yếu')
    s1_learning_capacity       VARCHAR(50),
    s2_learning_capacity       VARCHAR(50),
    
    final_behavior_point        INTEGER,    -- Điểm rèn luyện tổng kết
    day_of_absent               INTEGER DEFAULT 0, -- Tổng số ngày nghỉ cả năm
    s1_day_of_absent            INTEGER DEFAULT 0,
    s2_day_of_absent            INTEGER DEFAULT 0,
    
    homeroom_teacher_comment    TEXT,
    principal_comment           TEXT,
    is_passed_no_conditional    INTEGER DEFAULT 1,
    is_graduated                INTEGER DEFAULT 0,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_foar_student ON s360.fact_overall_academic_records(student_code);
CREATE INDEX idx_foar_year    ON s360.fact_overall_academic_records(school_year_id);
COMMENT ON TABLE s360.fact_overall_academic_records IS 'Học bạ tổng kết kết quả học tập và rèn luyện toàn diện của học sinh theo năm học';

-- 24. Đánh giá Tiến trình Học tập Môn học Định kỳ
CREATE TABLE s360.fact_so_evaluate_process_subjects (
    id                      BIGINT PRIMARY KEY,
    evaluate_progress_id    BIGINT,
    subject_id              INTEGER NOT NULL REFERENCES s360.dim_subject(id),
    student_code            VARCHAR(50) NOT NULL,
    school_year_id          INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    semester_index          INTEGER NOT NULL CHECK (semester_index IN (1, 2)),
    final_grade_level       VARCHAR(50),
    student_level           VARCHAR(50),
    comment                 TEXT,
    teacher_fullname        VARCHAR(255),
    is_approved             INTEGER DEFAULT 1,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    source_system           VARCHAR(50) DEFAULT 'SCHOOL_ONLINE'
);
COMMENT ON TABLE s360.fact_so_evaluate_process_subjects IS 'Báo cáo đánh giá nhận xét tiến trình học tập môn học định kỳ';

-- 25. [NHẬT KÝ ĐĂNG KÝ HỌC PHẦN] Nhật ký ghi nhận học sinh đăng ký / hủy môn học phần tự chọn
CREATE TABLE s360.fact_course_enrolls (
    id                      BIGINT PRIMARY KEY,
    so_school_id            INTEGER NOT NULL DEFAULT 1,
    student_code            VARCHAR(50) NOT NULL,
    subject_id              INTEGER NOT NULL REFERENCES s360.dim_subject(id),
    grade_id                INTEGER NOT NULL,
    is_moved_out            INTEGER DEFAULT 0, -- 1: Đã rút môn/chuyển lớp học phần, 0: Đang học
    moved_out_at            TIMESTAMPTZ,
    is_student              INTEGER DEFAULT 1,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    source_system           VARCHAR(50) DEFAULT 'LMS'
);
CREATE INDEX idx_fce_student ON s360.fact_course_enrolls(student_code);
CREATE INDEX idx_fce_subject ON s360.fact_course_enrolls(subject_id);
COMMENT ON TABLE s360.fact_course_enrolls IS 'Nhật ký ghi nhận lịch sử học sinh đăng ký và rút môn học phần tự chọn';

-- ============================================================
-- SCHEMAS: Attendance, Absences & Discipline/Behavior (Group 1 & 2)
-- ============================================================

-- 26. [DANH MỤC HÀNH VI KỶ LUẬT] Danh mục tiêu chí khen thưởng & vi phạm nếp sống
CREATE TABLE s360.dim_behavior (
    id                          BIGINT PRIMARY KEY,
    code                        VARCHAR(100) NOT NULL,
    name                        VARCHAR(255) NOT NULL,
    group_code                  VARCHAR(100),
    group_name                  VARCHAR(255),
    point                       DOUBLE PRECISION DEFAULT 0.0,
    point_min                   INTEGER,
    point_max                   INTEGER,
    is_duplicate_behavior       INTEGER DEFAULT 0,
    count_duplicate_behavior    INTEGER DEFAULT 0,
    scope_duplicate_behavior    INTEGER DEFAULT 0,
    point_duplicate_behavior    DOUBLE PRECISION DEFAULT 0.0,
    is_behavior_solve           INTEGER DEFAULT 0,
    is_apply_student            INTEGER DEFAULT 1,
    is_apply_teacher            INTEGER DEFAULT 0,
    is_apply_homeroom_class     INTEGER DEFAULT 0,
    convert_behavior_id         INTEGER,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE s360.dim_behavior IS 'Danh mục tiêu chí khen thưởng, kỷ luật và hành vi vi phạm rèn luyện';

-- 27. [DANH MỤC LỚP HỌC PHẦN] Danh mục khóa học / lớp môn tự chọn
CREATE TABLE s360.dim_course (
    id                          BIGINT PRIMARY KEY,
    so_school_id                INTEGER NOT NULL DEFAULT 1,
    school_year_id              INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    grade_id                    INTEGER NOT NULL,
    subject_id                  INTEGER REFERENCES s360.dim_subject(id),
    homeroom_class_id          INTEGER REFERENCES s360.dim_homeroom_class(id),
    code                        VARCHAR(100) NOT NULL,
    name                        VARCHAR(255) NOT NULL,
    type                        VARCHAR(100),
    max_student                 INTEGER DEFAULT 40,
    start_date                  DATE,
    end_date                    DATE,
    description                 TEXT,
    status                      VARCHAR(50) DEFAULT 'ACTIVE',
    is_online_training          INTEGER DEFAULT 0,
    is_locked                   INTEGER DEFAULT 0,
    is_extracurricular_activity INTEGER DEFAULT 0,
    extracurricular_activity_id INTEGER,
    el_course_id                BIGINT,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_dc_school_year ON s360.dim_course(so_school_id, school_year_id);
COMMENT ON TABLE s360.dim_course IS 'Danh mục lớp học phần / khóa học môn tự chọn';

-- 28. [NHẬT KÝ KỶ LUẬT & KHEN THƯỞNG] Nhật ký vi phạm nếp sống rèn luyện
CREATE TABLE s360.fact_behavior_logs (
    id                          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    so_school_id                INTEGER NOT NULL DEFAULT 1,
    school_year_id              INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    student_code                VARCHAR(50) NOT NULL,
    behavior_id                 BIGINT REFERENCES s360.dim_behavior(id),
    behavior_before_id          BIGINT,
    object_type                 VARCHAR(50),
    object_id                   BIGINT,
    behavior_code               VARCHAR(100),
    behavior_fullname           VARCHAR(255),
    behavior_fullname_clean     VARCHAR(255),
    behavior_level              VARCHAR(50),
    behavior_point              DOUBLE PRECISION DEFAULT 0.0,
    behavior_comment            TEXT,
    comment_date                DATE DEFAULT CURRENT_DATE,
    sanction_code               VARCHAR(100),
    sanction_name               VARCHAR(255),
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    source_system               VARCHAR(50) DEFAULT 'SCHOOL_ONLINE'
);
CREATE INDEX idx_fbl_student ON s360.fact_behavior_logs(student_code);
CREATE INDEX idx_fbl_date ON s360.fact_behavior_logs(comment_date);
COMMENT ON TABLE s360.fact_behavior_logs IS 'Nhật ký ghi nhận khen thưởng rèn luyện & vi phạm kỷ luật của học sinh';

-- 29. [NHẬT KÝ XIN NGHỈ HỌC] Nhật ký học sinh xin nghỉ học có phép / không phép
CREATE TABLE s360.fact_absent_logs (
    id                          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    absent_period_id            BIGINT,
    so_school_id                INTEGER NOT NULL DEFAULT 1,
    school_year_id              INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    homeroom_class_id          INTEGER NOT NULL REFERENCES s360.dim_homeroom_class(id),
    student_code                VARCHAR(50) NOT NULL,
    reason                      TEXT,
    reason_norm                 TEXT,
    reason_category             VARCHAR(100),
    from_date                   DATE NOT NULL,
    to_date                     DATE NOT NULL,
    is_approved                 INTEGER DEFAULT 1,
    approval_status             VARCHAR(50) DEFAULT 'APPROVED',
    approved_at                 TIMESTAMPTZ,
    is_auto_approved            INTEGER DEFAULT 0,
    is_full_day                 INTEGER DEFAULT 1,
    absent_date                 DATE NOT NULL,
    timetable_period_code       VARCHAR(50),
    timetable_period_name       VARCHAR(100),
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_fal_student ON s360.fact_absent_logs(student_code);
CREATE INDEX idx_fal_class ON s360.fact_absent_logs(homeroom_class_id);
CREATE INDEX idx_fal_date ON s360.fact_absent_logs(absent_date);
COMMENT ON TABLE s360.fact_absent_logs IS 'Nhật ký xin nghỉ học chi tiết của học sinh (nghỉ có phép / không phép)';

-- 30. [ĐIỂM DANH HÀNG NGÀY] Thống kê tình hình điểm danh theo buổi
CREATE TABLE s360.fact_so_daily_attendance (
    id                          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    _date                       DATE NOT NULL,
    week_start                  DATE,
    month_start                 DATE,
    school_year_id              INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    school_id                   INTEGER NOT NULL DEFAULT 1,
    school_year                 VARCHAR(50),
    school_year_start_date      DATE,
    school_year_end_date        DATE,
    student_code                VARCHAR(50) NOT NULL,
    course_id                   BIGINT REFERENCES s360.dim_course(id),
    subject_id                  INTEGER REFERENCES s360.dim_subject(id),
    school_code                 VARCHAR(50),
    homeroom_class_id          INTEGER NOT NULL REFERENCES s360.dim_homeroom_class(id),
    class_code                  VARCHAR(50),
    class_name                  VARCHAR(100),
    grade_id                    INTEGER NOT NULL,
    grade_name                  VARCHAR(50),
    total_periods               INTEGER DEFAULT 0,
    absent_periods              INTEGER DEFAULT 0,
    absent_no_permission        INTEGER DEFAULT 0,
    absent_with_permission      INTEGER DEFAULT 0,
    any_absence_flag            INTEGER DEFAULT 0,
    full_subject_absence_flag   INTEGER DEFAULT 0,
    first_created_at            TIMESTAMPTZ DEFAULT NOW(),
    last_updated_at             TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_fda_student ON s360.fact_so_daily_attendance(student_code);
CREATE INDEX idx_fda_class ON s360.fact_so_daily_attendance(homeroom_class_id);
CREATE INDEX idx_fda_date ON s360.fact_so_daily_attendance(_date);
COMMENT ON TABLE s360.fact_so_daily_attendance IS 'Thống kê tình hình điểm danh theo ngày của học sinh';

-- 31. [ĐIỂM DANH LỚP CHỦ NHIỆM] Nhật ký điểm danh đầu giờ của giáo viên chủ nhiệm
CREATE TABLE s360.fact_so_homeroom_class_attendances (
    id                          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    tenant_id                   INTEGER DEFAULT 1,
    so_school_id                INTEGER NOT NULL DEFAULT 1,
    campus_id                   INTEGER DEFAULT 1,
    school_year_id              INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    homeroom_class_id          INTEGER NOT NULL REFERENCES s360.dim_homeroom_class(id),
    attendance_date             DATE NOT NULL,
    so_user_id                  BIGINT,
    student_code                VARCHAR(50) NOT NULL,
    status                      INTEGER DEFAULT 1,
    comment                     TEXT,
    comment_meal                TEXT,
    is_push_to_app              INTEGER DEFAULT 1,
    is_push_notification        INTEGER DEFAULT 1,
    is_locked                   INTEGER DEFAULT 0,
    last_attendance_update_at   TIMESTAMPTZ,
    is_deleted                  INTEGER DEFAULT 0,
    created_by                  BIGINT,
    updated_by                  BIGINT,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    source_system               VARCHAR(50) DEFAULT 'SCHOOL_ONLINE'
);
CREATE INDEX idx_fhca_student ON s360.fact_so_homeroom_class_attendances(student_code);
CREATE INDEX idx_fhca_class_date ON s360.fact_so_homeroom_class_attendances(homeroom_class_id, attendance_date);
COMMENT ON TABLE s360.fact_so_homeroom_class_attendances IS 'Nhật ký điểm danh lớp chủ nhiệm hàng ngày vào đầu giờ';

-- 32. [NHẬT KÝ ĐI MUỘN] Nhật ký học sinh đi học muộn & về sớm
CREATE TABLE s360.fact_so_homeroom_class_late_attendances (
    id                          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    tenant_id                   INTEGER DEFAULT 1,
    campus_id                   INTEGER DEFAULT 1,
    so_school_name              VARCHAR(255),
    so_school_id                INTEGER NOT NULL DEFAULT 1,
    school_year_id              INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    grade_id                    INTEGER NOT NULL,
    homeroom_class_id          INTEGER NOT NULL REFERENCES s360.dim_homeroom_class(id),
    homeroom_class_name         VARCHAR(100),
    attendance_date             DATE NOT NULL,
    so_user_id                  BIGINT,
    student_code                VARCHAR(50) NOT NULL,
    user_name                   VARCHAR(100),
    user_fullname               VARCHAR(255),
    user_mail                   VARCHAR(100),
    attendance_time             TIMESTAMPTZ,
    is_late                     INTEGER DEFAULT 1,
    status_name                 VARCHAR(50) DEFAULT 'DI_MUON',
    ignore_late                 INTEGER DEFAULT 0,
    reason_ignore               TEXT,
    image_path                  VARCHAR(500),
    time_late                   INTEGER DEFAULT 0,
    process_status              VARCHAR(50) DEFAULT 'PROCESSED',
    is_deleted                  INTEGER DEFAULT 0,
    created_by                  BIGINT,
    updated_by                  BIGINT,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    source_system               VARCHAR(50) DEFAULT 'SCHOOL_ONLINE'
);
CREATE INDEX idx_fhcla_student ON s360.fact_so_homeroom_class_late_attendances(student_code);
CREATE INDEX idx_fhcla_class ON s360.fact_so_homeroom_class_late_attendances(homeroom_class_id);
CREATE INDEX idx_fhcla_date ON s360.fact_so_homeroom_class_late_attendances(attendance_date);
COMMENT ON TABLE s360.fact_so_homeroom_class_late_attendances IS 'Nhật ký ghi nhận học sinh đi học muộn / về sớm';

-- 33. [THỐNG KÊ CHUYÊN CẦN LỚP] Báo cáo thống kê tổng hợp tỷ lệ tham gia lớp
CREATE TABLE s360.fact_so_class_attendance_statistics (
    id                          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    so_user_id                  BIGINT,
    student_code                VARCHAR(50) NOT NULL,
    date                        DATE NOT NULL,
    status                      VARCHAR(50),
    total_lesson                INTEGER DEFAULT 0,
    lesson_attend               INTEGER DEFAULT 0,
    lesson_not_attend           INTEGER DEFAULT 0,
    tenant_id                   INTEGER DEFAULT 1,
    so_school_id                INTEGER NOT NULL DEFAULT 1,
    school_year_id              INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    campus_id                   INTEGER DEFAULT 1,
    grade_id                    INTEGER NOT NULL,
    homeroom_class_id          INTEGER NOT NULL REFERENCES s360.dim_homeroom_class(id),
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    source_system               VARCHAR(50) DEFAULT 'SCHOOL_ONLINE'
);
CREATE INDEX idx_fcas_class_date ON s360.fact_so_class_attendance_statistics(homeroom_class_id, date);
COMMENT ON TABLE s360.fact_so_class_attendance_statistics IS 'Thống kê tổng hợp số tiết tham gia & nghỉ học của lớp';

-- 34. [ĐIỂM DANH THEO TIẾT HỌC] Điểm danh môn học phần / tiết học chi tiết
CREATE TABLE s360.fact_course_attendences (
    id                          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    so_school_id                INTEGER NOT NULL DEFAULT 1,
    school_year_id              INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    course_id                   BIGINT REFERENCES s360.dim_course(id),
    timetable_period_code       VARCHAR(50),
    timetable_period_name       VARCHAR(100),
    _date                       DATE NOT NULL,
    student_code                VARCHAR(50) NOT NULL,
    status                      VARCHAR(50) DEFAULT 'PRESENT',
    status_name                 VARCHAR(100) DEFAULT 'Có mặt',
    comment                     TEXT,
    is_push_to_app              INTEGER DEFAULT 1,
    is_push_notification        INTEGER DEFAULT 1,
    is_locked                   INTEGER DEFAULT 0,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    source_system               VARCHAR(50) DEFAULT 'LMS'
);
CREATE INDEX idx_fca_student ON s360.fact_course_attendences(student_code);
CREATE INDEX idx_fca_course ON s360.fact_course_attendences(course_id);
CREATE INDEX idx_fca_date ON s360.fact_course_attendences(_date);
COMMENT ON TABLE s360.fact_course_attendences IS 'Nhật ký điểm danh chi tiết theo từng tiết học / môn học phần';

-- ============================================================
-- SCHEMAS: SWB & Mental Health Survey (Khảo sát SWB & Hồ sơ Can thiệp Tâm lý)
-- ============================================================

-- 35. [KHẢO SÁT CHỈ SỐ HẠNH PHÚC & SỨC KHỎE TÂM THẦN] Kết quả khảo sát SWB Survey định kỳ
CREATE TABLE s360.fact_swb_survey (
    id                          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    survey_date                 DATE NOT NULL,
    week_start                  DATE,
    month_start                 DATE,
    school_year_id              INTEGER REFERENCES s360.dim_school_year(id),
    school_year                 VARCHAR(50),
    student_code                VARCHAR(50) NOT NULL,
    school_code                 VARCHAR(50),
    school_name                 VARCHAR(255),
    homeroom_class_id          INTEGER REFERENCES s360.dim_homeroom_class(id),
    class_code                  VARCHAR(50),
    class_name                  VARCHAR(100),
    grade_id                    INTEGER,
    grade_name                  VARCHAR(50),
    question_set_id             BIGINT,
    question_group_id           BIGINT,
    question_group_name         VARCHAR(255),
    question_group_name_en      VARCHAR(255),
    question_id                 BIGINT,
    converted_score             DOUBLE PRECISION,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_fssur_student ON s360.fact_swb_survey(student_code);
CREATE INDEX idx_fssur_class   ON s360.fact_swb_survey(homeroom_class_id);
CREATE INDEX idx_fssur_date    ON s360.fact_swb_survey(survey_date);
COMMENT ON TABLE s360.fact_swb_survey IS 'Nhật ký kết quả khảo sát độ hài lòng & chỉ số sức khỏe tâm thần (SWB Survey) định kỳ của học sinh';

-- 36. [HỒ SƠ HỖ TRỢ CAN THIỆP TÂM LÝ & IEP] Nhật ký ca hỗ trợ tâm lý & kế hoạch giáo dục cá nhân
CREATE TABLE s360.fact_swb_support (
    id                          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    student_code                VARCHAR(50) NOT NULL,
    loai_can_thiep              VARCHAR(100),
    ten_ho_tro                  VARCHAR(255),
    trang_thai_ho_tro           VARCHAR(100),
    ngay_bat_dau                DATE,
    school_year_id              INTEGER REFERENCES s360.dim_school_year(id),
    school_year                 VARCHAR(50),
    school_code                 VARCHAR(50),
    school_name                 VARCHAR(255),
    grade_id                    INTEGER,
    grade_name                  VARCHAR(50),
    homeroom_class_id          INTEGER REFERENCES s360.dim_homeroom_class(id),
    class_code                  VARCHAR(50),
    class_name                  VARCHAR(100),
    iep_muc_tieu                TEXT,
    iep_tiep_can                TEXT,
    iep_can_thiep_cu_the        TEXT,
    iep_ke_hoach_trien_khai    TEXT,
    iep_thu_thap_thong_tin      TEXT,
    iep_nhat_ky_tro_giup        TEXT,
    ngay_cap_nhat_iep           DATE,
    iep_actions_can_lam         TEXT,
    ten_chuong_trinh_nhom       VARCHAR(255),
    muc_tieu_chuong_trinh_nhom TEXT,
    ngay_ho_tro_gan_nhat        DATE,
    ma_van_de_dang_can_thiep    VARCHAR(100),
    reference_id                BIGINT,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_fssup_student ON s360.fact_swb_support(student_code);
CREATE INDEX idx_fssup_class   ON s360.fact_swb_support(homeroom_class_id);
COMMENT ON TABLE s360.fact_swb_support IS 'Nhật ký hồ sơ hỗ trợ tâm lý & can thiệp chăm sóc đặc biệt (IEP) của học sinh';

-- ============================================================
-- 37. [BIẾN CỐ CUỘC SỐNG HỌC SINH] Nhật ký biến cố gia đình / tâm lý xã hội
--     Lưu mọi biến cố (phạm vi LOW → CRITICAL): ly hôn, người thân qua đời,
--     tai nạn gia đình, mâu thuẫn, áp lực học tập...
-- ============================================================
CREATE TABLE s360.fact_student_life_events (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_code    VARCHAR(50) NOT NULL,
    event_type      VARCHAR(50) NOT NULL,  -- 'FAMILY_DIVORCE' | 'BEREAVEMENT' | 'FAMILY_ACCIDENT' | 'FAMILY_CONFLICT' | 'ACADEMIC_PRESSURE' | 'MENTAL_CRISIS'
    event_name      VARCHAR(255) NOT NULL, -- 'Bố mẹ ly hôn', 'Người thân qua đời', 'Tai nạn gia đình'...
    event_date      DATE NOT NULL,
    severity        VARCHAR(20) NOT NULL DEFAULT 'MODERATE'
                    CHECK (severity IN ('LOW', 'MODERATE', 'HIGH', 'CRITICAL')),
    description     TEXT,
    school_year_id  INTEGER REFERENCES s360.dim_school_year(id),
    so_school_id    INTEGER NOT NULL DEFAULT 1,
    -- === MÔ HÌNH THỜI GIAN (Temporal Status) — phân biệt biến cố mới/cũ, đang diễn ra/đã kết thúc ===
    time_quantity   INT,          -- Đã diễn ra X đơn vị (vd 3, 5, 10)
    time_unit       VARCHAR(20),  -- DAY/WEEK/MONTH/YEAR
    status          VARCHAR(20) DEFAULT 'UNKNOWN',  -- ONGOING / RESOLVED / UNKNOWN
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_fsle_student ON s360.fact_student_life_events(student_code);
CREATE INDEX idx_fsle_date    ON s360.fact_student_life_events(event_date);
COMMENT ON TABLE s360.fact_student_life_events IS 'Nhật ký biến cố cuộc sống (ly hôn, qua đời, tai nạn, áp lực...) — nguồn gốc crisis tâm lý cho EWS/At-Risk';

-- ============================================================
-- 38. [TIỀN SỬ Y TẾ / BỆNH LÝ MÃN TÍNH HỌC SINH] Hồ sơ y tế
--     Chỉ lưu cho học sinh CÓ BỆNH: tiểu đường, tim mạch, hen suyễn...
-- ============================================================
CREATE TABLE s360.fact_student_medical_history (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_code    VARCHAR(50) NOT NULL,
    condition_type  VARCHAR(50) NOT NULL,  -- 'DIABETES' | 'CARDIOVASCULAR' | 'ASTHMA' | 'ALLERGY' | 'MENTAL_HEALTH'
    condition_name  VARCHAR(255) NOT NULL, -- 'Tiểu đường type 1', 'Hen suyễn', 'Bệnh tim bẩm sinh'...
    diagnosed_date  DATE,
    severity        VARCHAR(20) NOT NULL DEFAULT 'MODERATE'
                    CHECK (severity IN ('LOW', 'MODERATE', 'HIGH')),
    is_chronic      BOOLEAN DEFAULT TRUE,
    notes           TEXT,
    school_year_id  INTEGER REFERENCES s360.dim_school_year(id),
    so_school_id    INTEGER NOT NULL DEFAULT 1,
    -- === MÔ HÌNH THỜI GIAN (Temporal Status) — phân biệt bệnh ngắn hạn/mãn tính, đang điều trị/đã hồi phục ===
    time_quantity   INT,          -- Đã X đơn vị (vd gãy tay 3 tháng = 3 MONTH)
    time_unit       VARCHAR(20),  -- DAY/WEEK/MONTH/YEAR
    status          VARCHAR(20) DEFAULT 'UNKNOWN',  -- ONGOING / RESOLVED / UNKNOWN
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_fsmh_student ON s360.fact_student_medical_history(student_code);
CREATE INDEX idx_fsmh_type    ON s360.fact_student_medical_history(condition_type);
COMMENT ON TABLE s360.fact_student_medical_history IS 'Hồ sơ tiền sử y tế / bệnh lý mãn tính (tiểu đường, tim mạch, hen suyễn...) — chỉ lưu học sinh có bệnh';

-- ============================================================
-- SEED DATA: Cấu hình Ma trận Quy đổi 6 Thang Điểm
-- ============================================================

INSERT INTO s360.dim_grade_scale_detail 
(id, scale_name, min_score_range, max_score_range, min_percent, max_percent, representative_percent, grade_letter, grade_label, gpa_scale_4, scale_6_value, pass_fail_status)
VALUES
-- Thang Điểm Chữ A...F & GPA 4.0 & Thang 6
(1, 'SCALE_ALL_EXCELLENT', 9.00, 10.00, 90.00, 100.00, 95.00, 'A+', 'Xuất sắc', 4.00, 6, 'DAT'),
(2, 'SCALE_ALL_GOOD_HIGH',  8.50,  8.99, 85.00,  89.99, 87.50, 'A',  'Giỏi xuất sắc', 3.75, 6, 'DAT'),
(3, 'SCALE_ALL_GOOD',       8.00,  8.49, 80.00,  84.99, 82.50, 'B+', 'Giỏi',         3.50, 5, 'DAT'),
(4, 'SCALE_ALL_ABOVE_AVG',  7.00,  7.99, 70.00,  79.99, 75.00, 'B',  'Khá',         3.00, 4, 'DAT'),
(5, 'SCALE_ALL_AVERAGE',    6.50,  6.99, 65.00,  69.99, 67.50, 'C+', 'Trung bình khá',2.50, 3, 'DAT'),
(6, 'SCALE_ALL_BELOW_AVG',  5.00,  6.49, 50.00,  64.99, 57.50, 'C',  'Trung bình',  2.00, 3, 'DAT'),
(7, 'SCALE_ALL_POOR',       4.00,  4.99, 40.00,  49.99, 45.00, 'D',  'Yếu',         1.00, 2, 'CHUA_DAT'),
(8, 'SCALE_ALL_FAIL',       0.00,  3.99,  0.00,  39.99, 20.00, 'F',  'Kém',         0.00, 1, 'CHUA_DAT');

-- Triggers auto-update updated_at
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
CREATE TRIGGER trg_ai_sessions_updated BEFORE UPDATE ON public.ai_sessions FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

-- ============================================================
-- METADATA INDEX: Bảng Index Danh Mục Chuẩn Hóa Cho Dynamic Entity Resolution (Hybrid Search)
-- ============================================================

CREATE TABLE IF NOT EXISTS s360.metadata_index (
    id              BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    so_school_id    INTEGER NOT NULL,
    entity_type     VARCHAR(50) NOT NULL, -- 'SCHOOL_YEAR', 'CLASS', 'SUBJECT', 'EXAM', 'ASSIGNMENT', 'GRADE_SCALE'
    entity_name     VARCHAR(255) NOT NULL, -- '7A1', 'Năm học 2025 - 2026', 'Kiểm tra giữa kỳ 1', 'Toán học'
    exact_code      VARCHAR(100),          -- '2025_2026', 'TOAN_7', 'GK1_TOAN_7', '7A1'
    exact_id        BIGINT NOT NULL,       -- 2025, 1, 16, 29
    extra_metadata  JSONB,                 -- {"grade_number": 7, "semester_index": 1}
    embedding       vector(1536),          -- Vector Embedding (OpenAI text-embedding-3-large 1536 dim / Gemini 1536 dim)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_meta_trgm ON s360.metadata_index USING gin (entity_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_meta_school ON s360.metadata_index(so_school_id, entity_type);

-- ============================================================
-- EWS OUTPUT & TRAINING STORE: Bảng Dự báo Runtime & Dataset Huấn luyện MLOps
-- ============================================================

-- 1. Bảng lưu Kết quả Dự Báo Rủi Ro Runtime (Dùng cho Text-to-SQL Agent)
CREATE TABLE IF NOT EXISTS s360.fact_student_subject_risk_predictions (
    id                      BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    student_code            VARCHAR(50) NOT NULL,
    so_school_id            INTEGER NOT NULL,                     -- Trường sở hữu dự báo (Multi-Tenant Isolation)
    subject_id              INTEGER NOT NULL REFERENCES s360.dim_subject(id),
    school_year_id          INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    semester_index          INTEGER NOT NULL CHECK (semester_index IN (1, 2)),
    
    -- === KHÓA ĐỊNH VỊ THỜI GIAN DỰ BÁO ===
    evaluated_at_week       INTEGER NOT NULL,                     -- Mốc tuần học (5, 8, 11, 14, 16)
    model_version           VARCHAR(20) DEFAULT 'v1_single',     -- 'v1_single' | 'v2_ensemble' (2 phiên bản song song)
    evaluated_at_date       DATE NOT NULL DEFAULT CURRENT_DATE,   -- Ngày chạy dự báo thực tế (Audit Trail)
    cutoff_date             DATE,                                 -- Ngày cutoff dữ liệu dùng để trích xuất feature (khớp feature_extractor)
    target_scope            VARCHAR(20) DEFAULT 'SEMESTER',       -- 'SEMESTER' (Học kỳ) hoặc 'FULL_YEAR' (Cả năm)
    join_date               DATE,                                 -- Ngày chuyển tới / nhập học vào lớp (NULL = có mặt từ đầu) — M2-PIVOT

    -- === TEMPORAL SCORES (coefficient-weighted avg + OLS slope) — 9 Features ===
    weighted_early_avg      DECIMAL(10,2),  -- Σ(score×coeff)/Σ(coeff) nửa đầu
    weighted_late_avg       DECIMAL(10,2),  -- Σ(score×coeff)/Σ(coeff) nửa sau
    weighted_late_avg_imputed BOOLEAN DEFAULT FALSE,  -- Cờ: ĐTB nửa sau kỳ bị impute (chưa có điểm thật)
    score_slope             DECIMAL(10,4),  -- OLS slope (KHÔNG weight)
    score_volatility        DECIMAL(10,4),  -- raw std dev (KHÔNG weight)
    max_drop                DECIMAL(10,2),  -- raw max(LAG-score) (KHÔNG weight)
    last_score              DECIMAL(10,2),  -- điểm kiểm tra mới nhất
    max_coefficient_so_far  DECIMAL(5,2),   -- hệ số lớn nhất đã ghi nhận đến mốc dự báo
    high_weight_score_count INTEGER DEFAULT 0, -- số lượng bài kiểm tra trọng số cao (hệ số >= 2.0)
    last_high_weight_score  DECIMAL(10,2),  -- điểm số của bài thi hệ số cao gần nhất

    -- === LMS CỤM TIẾN TRÌNH TỰ HỌC (từ fact_so_assignment_grade) — 5 Features ===
    lms_avg_score           DECIMAL(10,2),  -- Điểm TB LMS toàn kỳ
    lms_recent_drop         DECIMAL(10,2),  -- Mức rớt điểm LMS 4 tuần gần nhất (lms_avg_score - lms_recent_avg)
    lms_submission_rate     DECIMAL(5,4),   -- Tỷ lệ nộp bài LMS toàn kỳ
    lms_recent_submission_rate DECIMAL(5,4),-- Tỷ lệ nộp bài LMS 4 tuần gần nhất
    lms_gradebook_gap       DECIMAL(10,2),  -- Độ lệch năng lực vs thái độ (lms_avg_score - last_score)

    -- === ATTENDANCE (4 features — 0 multicollinearity) ===
    daily_absence_rate          DECIMAL(5,4),  -- % tổng tiết vắng (fact_so_daily_attendance)
    unexcused_absent_rate       DECIMAL(5,4),  -- % vắng không phép (fact_so_daily_attendance)
    excused_absent_days         INTEGER DEFAULT 0,  -- Tổng ngày nghỉ có phép (fact_absent_logs)
    total_late_count            INTEGER DEFAULT 0,  -- Tổng số lần đi muộn (fact_so_homeroom_class_late_attendances)

    -- === BEHAVIOR (3 features — focus rủi ro kỷ luật & tái phạm) ===
    total_demerit_points        DECIMAL(10,2) DEFAULT 0.0, -- Tổng điểm rèn luyện bị trừ (đã gồm phạt tái diễn)
    repeat_offense_count        INTEGER DEFAULT 0,         -- Số lần vi phạm lặp đi lặp lại (tái phạm)
    severe_sanction_count       INTEGER DEFAULT 0,         -- Số lần có hình thức xử lý kỷ luật chính thức

    -- === SUB-SCORES & TRỌNG SỐ (chỉ dùng cho v2_ensemble) ===
    score_risk              DECIMAL(5,2),  -- risk score riêng yếu tố Điểm (0-100)
    lms_risk                DECIMAL(5,2),  -- risk score riêng yếu tố LMS (0-100)
    attendance_risk         DECIMAL(5,2),  -- risk score riêng yếu tố Chuyên cần (0-100)
    behavior_risk           DECIMAL(5,2),  -- risk score riêng yếu tố Hạnh kiểm (0-100)
    weight_score            DECIMAL(5,4),  -- trọng số động đã dùng cho Điểm
    weight_lms              DECIMAL(5,4),  -- trọng số động đã dùng cho LMS
    weight_attendance       DECIMAL(5,4),  -- trọng số động đã dùng cho Chuyên cần
    weight_behavior         DECIMAL(5,4),  -- trọng số động đã dùng cho Hạnh kiểm

    -- === KẾT QUẢ DỰ BÁO EWS RUNTIME (Thang 0-100 & 4 Mức Rủi Ro) ===
    risk_score              DECIMAL(5,2),         -- Thang điểm rủi ro 0.00 -> 100.00 (0: Safe, 100: Critical)
    risk_level              VARCHAR(15) NOT NULL, -- 'LOW', 'MODERATE', 'HIGH', 'CRITICAL'
    risk_probability        DECIMAL(5,4),         -- Xác suất rủi ro (0.0000 -> 1.0000)
    shap_drivers            JSONB,                -- Top 5 nhân tố tác động SHAP (rank, feature, shap_value, value)

    -- === LLM-BASED FORECASTING (M5) — kết quả phân tích định tính + score điều chỉnh ===
    llm_risk_score          DECIMAL(5,2),         -- Điểm rủi ro 0-100 do LLM đánh giá (điều chỉnh định tính)
    llm_risk_level          VARCHAR(15),          -- LOW/MODERATE/HIGH/CRITICAL do LLM
    llm_narrative_summary   TEXT,                 -- Phân tích nguyên nhân gốc rễ (biến cố + bệnh)
    llm_forecast_trend      TEXT,                 -- Dự báo xu hướng 3-4 tuần tới
    llm_recommended_actions JSONB,                -- 2-3 hành động can thiệp khuyến nghị
    llm_evaluated_at        TIMESTAMPTZ,          -- Thời điểm LLM đánh giá (NULL = chưa phân tích)
    llm_previous_score       DECIMAL(5,2),         -- Điểm LLM trước đó (trước lần re-run "Chạy Lại Phân Tích")
    llm_score_change_reason  TEXT,                 -- Lý do thay đổi điểm LLM khi re-run (NULL = giữ nguyên điểm cũ)

    created_at              TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_fssrp_checkpoint UNIQUE (so_school_id, student_code, subject_id, school_year_id, semester_index, evaluated_at_week, model_version)
);

CREATE INDEX IF NOT EXISTS idx_fssrp_school
    ON s360.fact_student_subject_risk_predictions(so_school_id);

-- M2-PIVOT: migration cho DB đã tồn tại — thêm cột join_date (idempotent)
ALTER TABLE s360.fact_student_subject_risk_predictions
    ADD COLUMN IF NOT EXISTS join_date DATE;

-- M2-CUTOFF: migration cho DB đã tồn tại — thêm cột cutoff_date (idempotent)
ALTER TABLE s360.fact_student_subject_risk_predictions
    ADD COLUMN IF NOT EXISTS cutoff_date DATE;

-- M2-ENSEMBLE: migration cho DB đã tồn tại — thêm model_version + sub-scores/weights (idempotent)
ALTER TABLE s360.fact_student_subject_risk_predictions
    ADD COLUMN IF NOT EXISTS model_version VARCHAR(20) DEFAULT 'v1_single',
    ADD COLUMN IF NOT EXISTS score_risk DECIMAL(5,2),
    ADD COLUMN IF NOT EXISTS lms_risk DECIMAL(5,2),
    ADD COLUMN IF NOT EXISTS attendance_risk DECIMAL(5,2),
    ADD COLUMN IF NOT EXISTS behavior_risk DECIMAL(5,2),
    ADD COLUMN IF NOT EXISTS weight_score DECIMAL(5,4),
    ADD COLUMN IF NOT EXISTS weight_lms DECIMAL(5,4),
    ADD COLUMN IF NOT EXISTS weight_attendance DECIMAL(5,4),
    ADD COLUMN IF NOT EXISTS weight_behavior DECIMAL(5,4);

-- M4-SHAP: migration cho DB đã tồn tại — thêm cột shap_drivers (idempotent)
ALTER TABLE s360.fact_student_subject_risk_predictions
    ADD COLUMN IF NOT EXISTS shap_drivers JSONB;

-- M5-LLM-RERUN-AUDIT: migration cho DB đã tồn tại — thêm cột re-run audit (idempotent)
ALTER TABLE s360.fact_student_subject_risk_predictions
    ADD COLUMN IF NOT EXISTS llm_previous_score DECIMAL(5,2),
    ADD COLUMN IF NOT EXISTS llm_score_change_reason TEXT;

-- M2-ENSEMBLE: backfill model_version cho dữ liệu cũ (idempotent)
UPDATE s360.fact_student_subject_risk_predictions
    SET model_version = 'v1_single'
    WHERE model_version IS NULL;

-- M2-ENSEMBLE: sửa UNIQUE constraint để cho phép 2 phiên bản song song (idempotent)
-- M3-MULTI-TENANT: bao gồm so_school_id để phân tách dữ liệu giữa các trường
ALTER TABLE s360.fact_student_subject_risk_predictions
    DROP CONSTRAINT IF EXISTS uq_fssrp_checkpoint;
ALTER TABLE s360.fact_student_subject_risk_predictions
    ADD CONSTRAINT uq_fssrp_checkpoint
        UNIQUE (so_school_id, student_code, subject_id, school_year_id, semester_index, evaluated_at_week, model_version);

CREATE INDEX IF NOT EXISTS idx_fssrp_v3_student_subject
    ON s360.fact_student_subject_risk_predictions(student_code, subject_id);

CREATE INDEX IF NOT EXISTS idx_fssrp_v3_risk
    ON s360.fact_student_subject_risk_predictions(risk_level);

COMMENT ON TABLE s360.fact_student_subject_risk_predictions IS 'Bảng lưu kết quả dự báo rủi ro học tập chi tiết theo môn học do EWS Model xuất ra';


-- =====================================================================
-- EWS CONTROL PANEL (BGH) — quản lý job dự đoán + override trọng số
-- Chèn tay theo yêu cầu BGH (không chạy lại apply_merged_schema.py)
-- =====================================================================

-- 1) Bảng job dự đoán theo yêu cầu của BGH (hàng đợi DB-backed FIFO)
CREATE TABLE IF NOT EXISTS public.ews_pipeline_jobs (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id      INTEGER NOT NULL,
    requested_by      BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    school_year_id    INTEGER NOT NULL,
    semester_index    INTEGER NOT NULL CHECK (semester_index IN (1, 2)),
    evaluated_at_week INTEGER NOT NULL,
    cutoff_date       DATE,
    model_version     VARCHAR(20) NOT NULL DEFAULT 'v2_ensemble',
    status            VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    progress          INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    rows_processed    INTEGER,
    error_message     TEXT,
    started_at        TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ews_jobs_school_created
    ON public.ews_pipeline_jobs(so_school_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ews_jobs_status
    ON public.ews_pipeline_jobs(status);

COMMENT ON TABLE public.ews_pipeline_jobs IS
    'Lịch chạy dự đoán EWS do BGH yêu cầu, theo từng trường (so_school_id).';

-- 2) Bảng override trọng số EWS theo trường (BGH tinh chỉnh)
CREATE TABLE IF NOT EXISTS public.ews_weight_overrides (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id       INTEGER NOT NULL UNIQUE,
    weight_score       DOUBLE PRECISION,
    weight_lms         DOUBLE PRECISION,
    weight_attendance  DOUBLE PRECISION,
    weight_behavior    DOUBLE PRECISION,
    alpha_score        DOUBLE PRECISION,
    alpha_lms          DOUBLE PRECISION,
    alpha_attendance   DOUBLE PRECISION,
    alpha_behavior     DOUBLE PRECISION,
    weight_floor       DOUBLE PRECISION,
    worst_factor_beta  DOUBLE PRECISION,
    threshold_low      DOUBLE PRECISION,
    threshold_moderate DOUBLE PRECISION,
    threshold_high     DOUBLE PRECISION,
    threshold_critical DOUBLE PRECISION,
    updated_by         BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.ews_weight_overrides IS
    'Override trọng số/phân loại rủi ro EWS theo từng trường; NULL = dùng baseline YAML.';


-- 2. Bảng lưu Dữ liệu Train Mô hình (Training Dataset Store & Mock Data Ground Truth)
CREATE TABLE IF NOT EXISTS s360.train_student_subject_risk_dataset (
    id                      BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    student_code            VARCHAR(50) NOT NULL,
    so_school_id            INTEGER NOT NULL,                     -- Trường sở hữu dữ liệu train (Multi-Tenant Isolation)
    subject_id              INTEGER NOT NULL REFERENCES s360.dim_subject(id),
    school_year_id          INTEGER NOT NULL REFERENCES s360.dim_school_year(id),
    semester_index          INTEGER NOT NULL CHECK (semester_index IN (1, 2)),
    evaluated_at_week       INTEGER NOT NULL,                     -- Mốc tuần cắt dữ liệu (Feature Cutoff)

    -- === 1. TEMPORAL SCORES (9 Features) ===
    weighted_early_avg      DECIMAL(10,2),
    weighted_late_avg       DECIMAL(10,2),
    score_slope             DECIMAL(10,4),
    score_volatility        DECIMAL(10,4),
    max_drop                DECIMAL(10,2),
    last_score              DECIMAL(10,2),
    max_coefficient_so_far  DECIMAL(5,2),
    high_weight_score_count INTEGER DEFAULT 0,
    last_high_weight_score  DECIMAL(10,2),

    -- === 2. LMS (5 Features) ===
    lms_avg_score           DECIMAL(10,2),
    lms_recent_drop         DECIMAL(10,2),
    lms_submission_rate     DECIMAL(5,4),
    lms_recent_submission_rate DECIMAL(5,4),
    lms_gradebook_gap       DECIMAL(10,2),

    -- === 3. ATTENDANCE (4 Features) ===
    daily_absence_rate          DECIMAL(5,4),
    unexcused_absent_rate       DECIMAL(5,4),
    excused_absent_days         INTEGER DEFAULT 0,
    total_late_count            INTEGER DEFAULT 0,

    -- === 4. BEHAVIOR (3 Features) ===
    total_demerit_points        DECIMAL(10,2) DEFAULT 0.0,
    repeat_offense_count        INTEGER DEFAULT 0,            -- Tái phạm vi phạm
    severe_sanction_count       INTEGER DEFAULT 0,

    -- === GROUND TRUTH LABELS (y) — DÙNG ĐỂ TRAIN MÔ HÌNH ===
    actual_final_grade      DECIMAL(10,2),              -- Điểm tổng kết thực tế cuối kỳ (nếu có)
    actual_risk_level       VARCHAR(15) NOT NULL,       -- NHÃN THẬT: 'LOW', 'MODERATE', 'HIGH', 'CRITICAL'
    is_at_risk              INTEGER NOT NULL DEFAULT 0,  -- NHÃN BINARY: 1 (Rủi ro trượt/sụt giảm), 0 (An toàn)
    
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tssrd_student_subject
    ON s360.train_student_subject_risk_dataset(student_code, subject_id);

CREATE INDEX IF NOT EXISTS idx_tssrd_school
    ON s360.train_student_subject_risk_dataset(so_school_id);

CREATE INDEX IF NOT EXISTS idx_tssrd_risk_label
    ON s360.train_student_subject_risk_dataset(actual_risk_level);

COMMENT ON TABLE s360.train_student_subject_risk_dataset IS 'Bảng chứa Dữ liệu Mock / Lịch sử có Nhãn (Ground Truth Labels) phục vụ Huấn luyện Mô hình EWS';

-- End of score_focused_schema.sql DDL
