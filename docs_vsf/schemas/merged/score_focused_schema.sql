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

-- Create Schemas
CREATE SCHEMA IF NOT EXISTS public;
CREATE SCHEMA IF NOT EXISTS s360;

-- Drop Old Tables (if exists)
DROP TABLE IF EXISTS alembic_version CASCADE;
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

-- End of score_focused_schema.sql DDL
