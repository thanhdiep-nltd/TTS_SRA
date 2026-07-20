-- ============================================================
-- VSF Student Risk Alert (VSF SRA) - Consolidated Database Schema DDL
-- Combination of App Core/AI Engine (Public) and School Online DWH (s360, t360, default)
-- Total Tables: 54 Tables
-- DBMS: PostgreSQL 16+
-- ============================================================

-- Create Extensions
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create Schemas
CREATE SCHEMA IF NOT EXISTS public;
CREATE SCHEMA IF NOT EXISTS s360;
CREATE SCHEMA IF NOT EXISTS t360;
CREATE SCHEMA IF NOT EXISTS default;

-- ============================================================
-- ENUMS & TYPES (Schema: public)
-- ============================================================

CREATE TYPE public.school_level_enum AS ENUM ('PRIMARY', 'SECONDARY', 'HIGH', 'ALL');

CREATE TYPE public.user_role_enum AS ENUM (
    'ADMIN',
    'PRINCIPAL',
    'GRADE_HEAD_PRIMARY',
    'HOMEROOM_TEACHER_PRIMARY',
    'SUBJECT_TEACHER',
    'HOMEROOM_TEACHER_SECONDARY',
    'SUBJECT_HEAD'
);

CREATE TYPE public.role_context_enum AS ENUM (
    'HOMEROOM_PRIMARY',
    'HOMEROOM_SECONDARY',
    'SUBJECT_TEACHER',
    'GRADE_HEAD',
    'SUBJECT_HEAD'
);

CREATE TYPE public.score_type_enum AS ENUM ('TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK');

CREATE TYPE public.score_category_enum AS ENUM ('ORAL', 'REGULAR', 'MIDTERM', 'FINAL');

CREATE TYPE public.score_status_enum AS ENUM ('DRAFT', 'SUBMITTED', 'APPROVED');

CREATE TYPE public.assessment_type_enum AS ENUM ('SCORED', 'REMARK');

CREATE TYPE public.pass_fail_enum AS ENUM ('DAT', 'CHUA_DAT');

CREATE TYPE public.conduct_enum AS ENUM ('TOT', 'KHA', 'TRUNG_BINH', 'YEU');

CREATE TYPE public.file_type_enum AS ENUM ('PDF', 'WORD', 'IMAGE', 'OTHER');

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

CREATE TYPE public.question_type_enum AS ENUM ('MCQ', 'TRUE_FALSE', 'SHORT_ANSWER', 'ESSAY');

CREATE TYPE public.exam_format_enum AS ENUM ('MCQ_ONLY', 'ESSAY_ONLY', 'MIXED');

CREATE TYPE public.item_status_enum AS ENUM ('DRAFT', 'REVIEW', 'APPROVED', 'REJECTED', 'RETIRED');

CREATE TYPE public.item_source_enum AS ENUM ('AI_GENERATED', 'MANUAL', 'IMPORTED');

CREATE TYPE public.gen_exam_status_enum AS ENUM ('DRAFT', 'FINALIZED', 'PUBLISHED');

CREATE TYPE public.notification_type_enum AS ENUM (
    'QUESTION_SUBMITTED',
    'ITEM_REVIEWED',
    'EXAM_FINALIZED',
    'ANNOUNCEMENT',
    'GENERATION_FAILED'
);

-- ============================================================
-- SCHEMA: public (APP CORE & AI ENGINE - 18 TABLES)
-- ============================================================

-- 1. Bảng quản lý Tài khoản Người dùng & Xác thực Auth (SRA Core)
CREATE TABLE public.users (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    tenant_id       INTEGER,
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    phone           VARCHAR(20),
    avatar_url      TEXT,
    role            public.user_role_enum NOT NULL,
    school_level    public.school_level_enum NOT NULL DEFAULT 'ALL',
    subject_id      INTEGER,
    teacher_code    VARCHAR(50), -- Mã giáo viên liên kết DWH (Teacher 360)
    student_code    VARCHAR(50), -- Mã học sinh liên kết DWH (nếu là tài khoản HS/PH)
    so_student_id   BIGINT,      -- ID học sinh liên kết DWH (dim_homeroom_class_student)
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_school ON public.users(so_school_id);
CREATE INDEX idx_users_role   ON public.users(role);
CREATE INDEX idx_users_email  ON public.users(email);
CREATE INDEX idx_users_tcode  ON public.users(teacher_code);

-- 2. Quản lý Refresh Token Đăng nhập JWT
CREATE TABLE public.refresh_tokens (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL UNIQUE,
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Audit Log Lịch sử Thay đổi Ứng dụng
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

-- 4. Phiên Hội thoại AI Assistant
CREATE TABLE public.ai_sessions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title           VARCHAR(500),
    context_filter  JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_session_user ON public.ai_sessions(user_id);

-- 5. Nhật ký Tin nhắn AI Chat & Guardrails Telemetry
CREATE TABLE public.ai_messages (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id      BIGINT NOT NULL REFERENCES public.ai_sessions(id) ON DELETE CASCADE,
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

-- 6. File Đính kèm trong AI Chat
CREATE TABLE public.ai_session_attachments (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id      BIGINT NOT NULL REFERENCES public.ai_sessions(id) ON DELETE CASCADE,
    uploaded_by     BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
    file_name       VARCHAR(255) NOT NULL,
    stored_name     VARCHAR(255) NOT NULL,
    file_type       public.file_type_enum NOT NULL,
    extracted_text  TEXT,
    char_count      INTEGER NOT NULL DEFAULT 0,
    truncated       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Lịch Gửi Báo cáo Định kỳ
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

-- 8. Ghi âm Bài giảng & Đánh giá AI
CREATE TABLE public.classroom_recordings (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    teacher_id      BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    subject_id      INTEGER NOT NULL,
    class_id        INTEGER NOT NULL,
    course_id       BIGINT, -- ID khóa học LMS liên kết (dim_course)
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

-- 9. Đề thi Metadata & Phân tích Độ khó AI (TEVI)
CREATE TABLE public.exam_papers (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    subject_id      INTEGER NOT NULL,
    semester_id     INTEGER NOT NULL,
    grade_id        INTEGER,
    score_type      VARCHAR(100), -- Tự do nhập loại đầu điểm (ví dụ 'TX1', 'GK', 'Checkpoint 1')
    so_exam_id      BIGINT,       -- Liên kết trực tiếp dim_exam của School Online
    gradebook_type_item_id BIGINT,-- Liên kết trực tiếp dim_exam_moet chuẩn Bộ
    title           VARCHAR(500) NOT NULL,
    description     TEXT,
    file_url        TEXT,
    file_type       public.file_type_enum DEFAULT 'PDF',
    file_size_bytes BIGINT,
    difficulty      public.difficulty_enum,
    difficulty_coefficient NUMERIC(3,2) NOT NULL DEFAULT 1.00 CHECK (difficulty_coefficient BETWEEN 0.50 AND 1.50),
    num_questions   SMALLINT,
    total_points    NUMERIC(5,2),
    topics          TEXT[],
    ai_analysis     JSONB NOT NULL DEFAULT '{}',
    metadata        JSONB NOT NULL DEFAULT '{}',
    uploaded_by     BIGINT NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    content_difficulty NUMERIC(4, 3),
    content_analyzed_at TIMESTAMPTZ,
    content_source  public.file_type_enum,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. Ma trận Chuẩn đầu ra Bloom với Đề thi
CREATE TABLE public.exam_competencies (
    exam_paper_id   BIGINT NOT NULL REFERENCES public.exam_papers(id) ON DELETE CASCADE,
    strand_id       BIGINT NOT NULL, -- Liên kết trực tiếp stg_so_strand_path của DWH
    weight          NUMERIC(4,3) NOT NULL DEFAULT 0 CHECK (weight BETWEEN 0 AND 1),
    bloom_level     SMALLINT CHECK (bloom_level BETWEEN 1 AND 6),
    PRIMARY KEY (exam_paper_id, strand_id)
);

-- 11. Ánh xạ Đề thi vào Cột điểm DWH
CREATE TABLE public.exam_column_mappings (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id      INTEGER NOT NULL,
    semester_id     INTEGER NOT NULL,
    score_category  public.score_category_enum NOT NULL,
    column_index    SMALLINT NOT NULL,
    class_id        INTEGER,
    grade_id        INTEGER,
    exam_paper_id   BIGINT NOT NULL REFERENCES public.exam_papers(id) ON DELETE CASCADE,
    mapped_by       BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. Ngân hàng Câu hỏi Trắc nghiệm & Tự luận AI
CREATE TABLE public.question_items (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    subject_id      INTEGER NOT NULL,
    grade_number    SMALLINT NOT NULL CHECK (grade_number BETWEEN 1 AND 12),
    strand_id       BIGINT, -- Liên kết trực tiếp stg_so_strand_path của DWH
    bloom_level     SMALLINT NOT NULL CHECK (bloom_level BETWEEN 1 AND 6),
    question_type   public.question_type_enum NOT NULL,
    stem            TEXT NOT NULL,
    options         JSONB,
    answer_key      JSONB NOT NULL,
    solution        TEXT,
    default_points  NUMERIC(4, 2) NOT NULL DEFAULT 1.0 CHECK (default_points > 0),
    status          public.item_status_enum NOT NULL DEFAULT 'DRAFT',
    source          public.item_source_enum NOT NULL DEFAULT 'AI_GENERATED',
    provenance      JSONB NOT NULL DEFAULT '{}',
    times_used      INTEGER NOT NULL DEFAULT 0,
    p_value         NUMERIC(4, 3),
    discrimination  NUMERIC(4, 3),
    exposure_at     TIMESTAMPTZ,
    created_by      BIGINT NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    reviewed_by     BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
    reviewed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 13. Ngân hàng Lỗi sai Học sinh Theo chủ đề (Misconceptions)
CREATE TABLE public.misconceptions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER,
    subject_id      INTEGER NOT NULL,
    strand_id       BIGINT, -- Liên kết trực tiếp stg_so_strand_path của DWH
    grade_number    SMALLINT NOT NULL CHECK (grade_number BETWEEN 1 AND 12),
    description     TEXT NOT NULL,
    example_wrong   TEXT,
    evidence_count  INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 14. Ma trận Thiết kế Cấu trúc Đề thi AI (Blueprint)
CREATE TABLE public.exam_blueprints (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    subject_id      INTEGER NOT NULL,
    grade_number    SMALLINT NOT NULL CHECK (grade_number BETWEEN 1 AND 12),
    score_category  public.score_category_enum NOT NULL,
    title           VARCHAR(255) NOT NULL,
    total_points    NUMERIC(5, 2) NOT NULL DEFAULT 10.0 CHECK (total_points > 0),
    duration_min    SMALLINT,
    target_difficulty NUMERIC(4, 3),
    cells           JSONB NOT NULL,
    exam_format     public.exam_format_enum,
    created_by      BIGINT NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 15. Lịch sử Ráp đề Thi AI
CREATE TABLE public.generated_exams (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    blueprint_id    BIGINT NOT NULL REFERENCES public.exam_blueprints(id) ON DELETE RESTRICT,
    semester_id     INTEGER NOT NULL,
    grade_id        INTEGER,
    num_variants    SMALLINT NOT NULL DEFAULT 1 CHECK (num_variants BETWEEN 1 AND 20),
    status          public.gen_exam_status_enum NOT NULL DEFAULT 'DRAFT',
    exam_paper_id   BIGINT REFERENCES public.exam_papers(id) ON DELETE SET NULL,
    created_by      BIGINT NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 16. Chi tiết Câu hỏi trong Mã đề Thi Ráp
CREATE TABLE public.generated_exam_items (
    generated_exam_id BIGINT NOT NULL REFERENCES public.generated_exams(id) ON DELETE CASCADE,
    variant_code      VARCHAR(8) NOT NULL,
    position          SMALLINT NOT NULL CHECK (position >= 1),
    item_id           BIGINT NOT NULL REFERENCES public.question_items(id) ON DELETE RESTRICT,
    points            NUMERIC(4, 2) NOT NULL,
    option_order      JSONB,
    PRIMARY KEY (generated_exam_id, variant_code, position)
);

-- 17. Thông báo Người dùng & Hệ thống
CREATE TABLE public.notifications (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    recipient_id    BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    sender_id       BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
    type            public.notification_type_enum NOT NULL,
    title           VARCHAR(255) NOT NULL,
    message         TEXT NOT NULL,
    entity_type     VARCHAR(50),
    entity_id       BIGINT,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 18. Giám sát Hiệu năng & Chi phí AI Telemetry (AgentOps)
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

-- ============================================================
-- SCHEMA: default (STAGING TABLES - 3 TABLES)
-- ============================================================

-- 19. Staging Đường dẫn Phân cấp Cột điểm MOET
CREATE TABLE default.stg_so_exam_moet_path (
    gradebook_type_item_id bigint,
    parent_id bigint,
    gradebook_type_items_fullname varchar,
    level integer,
    path varchar,
    id_path varchar
);
COMMENT ON TABLE default.stg_so_exam_moet_path IS 'Lưu trữ thông tin phân cấp (cây danh mục) của các mục trong loại sổ điểm MOET';

-- 20. Staging Phân cấp Chương trình Môn học
CREATE TABLE default.stg_so_strand_path (
    strand_id bigint,
    parent_id integer,
    strand_name varchar,
    level integer,
    path varchar,
    id_path varchar,
    subject_id integer,
    subject_name varchar
);
COMMENT ON TABLE default.stg_so_strand_path IS 'Lưu cấu trúc phân cấp chương trình học tập (Môn học -> Chủ đề kiến thức/Strand)';

-- 21. Staging Học sinh Sơ bộ
CREATE TABLE default.stg_so_students (
    id decimal(20,0),
    code varchar
);
COMMENT ON TABLE default.stg_so_students IS 'Bảng staging lưu giữ thông tin sơ bộ của học sinh phục vụ đối chiếu dữ liệu';

-- ============================================================
-- SCHEMA: s360 (STUDENT 360 DWH - 33 TABLES)
-- ============================================================

-- 22. Danh mục Ma trận Dải điểm Quy đổi (% Universal Bridge)
CREATE TABLE s360.dim_grade_scale_detail (
    id              BIGINT PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    scale_name      VARCHAR(100) NOT NULL,
    max_score       NUMERIC(5,2) NOT NULL DEFAULT 10.00,
    min_score_range NUMERIC(5,2),
    max_score_range NUMERIC(5,2),
    min_percent     NUMERIC(5,2) NOT NULL,
    max_percent     NUMERIC(5,2) NOT NULL,
    representative_percent NUMERIC(5,2) NOT NULL,
    grade_letter    VARCHAR(10),
    grade_label     VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE s360.dim_grade_scale_detail IS 'Bảng ma trận cấu hình quy đổi từ Điểm chữ (A, B, C, Đạt) hoặc dải điểm sang Tỷ lệ % đại diện làm cầu nối chuẩn hóa';

-- 23. Danh mục Tiêu chí Hành vi Rèn luyện
CREATE TABLE s360.dim_behavior (
    id bigint,
    code varchar,
    name varchar,
    group_code varchar,
    group_name varchar,
    point double precision,
    point_min integer,
    point_max integer,
    is_duplicate_behavior integer,
    count_duplicate_behavior integer,
    scope_duplicate_behavior integer,
    point_duplicate_behavior double precision,
    is_behavior_solve integer,
    is_apply_student integer,
    is_apply_teacher integer,
    is_apply_homeroom_class integer,
    convert_behavior_id integer,
    created_at varchar,
    updated_at varchar
);
COMMENT ON TABLE s360.dim_behavior IS 'Danh mục các hành vi rèn luyện (tiêu chí cộng/trừ điểm) của học sinh';

-- 23. Danh mục Khóa học / Lớp học phần LMS
CREATE TABLE s360.dim_course (
    id bigint,
    so_school_id integer,
    school_year_id integer,
    grade_id integer,
    subject_id integer,
    homeroom_class_id integer,
    code varchar,
    name varchar,
    type varchar,
    max_student integer,
    start_date date,
    end_date date,
    description varchar,
    status varchar,
    is_online_training integer,
    is_locked integer,
    is_extracurricular_activity integer,
    extracurricular_activity_id integer,
    el_course_id bigint,
    created_at varchar,
    updated_at varchar
);
COMMENT ON TABLE s360.dim_course IS 'Danh mục khóa học / lớp học phần của trường học';

-- 24. Danh mục Kỳ thi & Đầu điểm LMS
CREATE TABLE s360.dim_exam (
    id bigint,
    so_exam_id bigint,
    school_year_id integer,
    subject_id integer,
    grade_id integer,
    grade_code varchar,
    grade_name varchar,
    exam_code varchar,
    exam_name varchar,
    so_parent_exam_id bigint,
    report_type_id integer,
    report_type_code varchar,
    report_type_name varchar,
    report_type_description varchar,
    is_moet integer,
    is_upgrade integer,
    is_attainment integer,
    coefficient decimal(10,1),
    moet_semester_index integer,
    max_grade decimal(10,1),
    is_periodic_exam integer,
    convert_to_10 integer,
    is_display_grade_book integer,
    created_at varchar,
    updated_at varchar,
    is_deleted integer
);
COMMENT ON TABLE s360.dim_exam IS 'Danh mục các kỳ thi và đầu điểm (Regular, Midterm, Final)';

-- 25. Danh mục Đầu điểm Chuẩn Bộ Giáo dục (MOET)
CREATE TABLE s360.dim_exam_moet (
    gradebook_type_item_id bigint,
    tenant_id integer,
    gradebook_type_id integer,
    gradebook_types_code varchar,
    gradebook_types_fullname varchar,
    gradebook_types_description varchar,
    gradebook_type_items_code varchar,
    gradebook_type_items_fullname varchar,
    parent_id bigint,
    moet_semester_index integer,
    semester_stages integer,
    process_type_default integer,
    coefficient decimal(10,1),
    max_grade decimal(10,1),
    round_type integer,
    index_order integer,
    is_allow_input integer,
    is_allow_mapping integer,
    is_active integer,
    is_category integer,
    is_deleted integer,
    created_by bigint,
    updated_by bigint,
    created_at varchar,
    updated_at varchar,
    gradebook_type_items_path varchar,
    gradebook_type_items_id_path varchar,
    source_system varchar
);
COMMENT ON TABLE s360.dim_exam_moet IS 'Danh mục chi tiết các đầu điểm chuẩn hóa theo quy định của Bộ Giáo dục (MOET)';

-- 26. Danh mục Hoạt động Ngoại khóa
CREATE TABLE s360.dim_extracurricular_activity (
    id integer,
    so_school_id integer,
    school_year varchar,
    code varchar,
    name varchar,
    category_code varchar,
    category_name varchar,
    category_name_en varchar,
    scope_type integer,
    scope_name varchar,
    target_type integer,
    target_name varchar,
    cost decimal(10,1),
    unit_cost varchar,
    start_date date,
    end_date date,
    is_allow_register integer,
    register_open_date timestamp(6) with time zone,
    register_close_date timestamp(6) with time zone,
    number_of_user integer,
    number_of_registers integer,
    status varchar,
    is_duplicate_semester2 integer,
    duplicate_semester2_id bigint,
    duplicate_semester2_at timestamp(6) with time zone,
    semester_1 integer,
    semester_2 integer,
    semester_all integer,
    code_1 varchar,
    code_2 varchar,
    code_all varchar,
    cost_all integer,
    cost_2 integer,
    cost_1 integer,
    start_date_1 date,
    start_date_2 date,
    start_date_all date,
    end_date_1 date,
    end_date_2 date,
    end_date_all date,
    status_semester_1 integer,
    status_semester_2 integer,
    status_semester_all integer,
    number_of_user_1 integer,
    number_of_user_2 integer,
    number_of_user_all integer,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.dim_extracurricular_activity IS 'Danh mục các hoạt động ngoại khóa của trường';

-- 27. Danh mục Lớp Chủ nhiệm
CREATE TABLE s360.dim_homeroom_class (
    id bigint,
    so_school_id integer,
    school_year_id integer,
    grade_id integer,
    code varchar,
    fullname varchar,
    homeroom_teacher_id bigint,
    teacher_code varchar,
    class_leader_id bigint,
    parent_leader_id bigint,
    is_active integer,
    is_bilingual integer,
    is_bilingual_prep integer,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.dim_homeroom_class IS 'Danh mục các lớp chủ nhiệm của trường học';

-- 28. Danh sách Học sinh thuộc Lớp Chủ nhiệm
CREATE TABLE s360.dim_homeroom_class_student (
    id bigint,
    tenant_id integer,
    so_student_id bigint,
    student_code varchar,
    student_name bytea,
    homeroom_class_id integer,
    class_code varchar,
    class_name varchar,
    so_school_id integer,
    school_year_id integer,
    school_name varchar,
    school_code varchar,
    teacher_code varchar,
    campus_name varchar,
    grade_id integer,
    grade_name varchar,
    moet_code varchar,
    join_date date,
    is_graduated integer,
    status integer,
    special_note varchar,
    is_deleted integer,
    is_active integer,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.dim_homeroom_class_student IS 'Danh sách liên kết học sinh với lớp chủ nhiệm của từng niên khóa';

-- 29. Danh mục Năm học
CREATE TABLE s360.dim_school_year (
    id integer,
    code varchar,
    fullname varchar,
    start_date date,
    end_date date,
    calculator_type integer,
    calculator_name varchar,
    is_locked integer,
    is_gradebook_locked integer,
    is_current integer,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.dim_school_year IS 'Danh mục năm học học đường';

-- 30. Danh mục Bài tập Giao trên LMS
CREATE TABLE s360.dim_so_assignment (
    assignment_id bigint,
    so_school_id integer,
    grade_id integer,
    grade_code varchar,
    grade_name varchar,
    semester_index integer,
    subject_id integer,
    course_id bigint,
    code varchar,
    fullname varchar,
    course_lesson_id bigint,
    gradebook_type_item_id integer,
    gradebook_type_item_name varchar,
    report_type_item_id integer,
    report_type_item_name varchar,
    el_assignment_id bigint,
    max_grade decimal(10,0),
    description varchar,
    due_date date,
    locked_at timestamp(6) with time zone,
    is_locked integer,
    is_mapping_locked integer,
    type integer,
    is_homework_calendar integer,
    date_assigned date,
    is_deleted integer,
    source_system varchar
);
COMMENT ON TABLE s360.dim_so_assignment IS 'Danh mục bài tập / nhiệm vụ học tập được giao cho học sinh';

-- 31. Đánh giá Tiến độ Học tập Tổng hợp
CREATE TABLE s360.dim_so_evaluate_progress (
    id bigint,
    tenant_id integer,
    so_school_id integer,
    school_name varchar,
    school_code varchar,
    campus_id integer,
    school_year_id integer,
    grade_id integer,
    grade_code varchar,
    grade_name varchar,
    class_code varchar,
    class_name varchar,
    semester_index integer,
    semester_stages integer,
    homeroom_class_id integer,
    user_id bigint,
    student_code varchar,
    is_attach_report_moet integer,
    is_attach_report_cam integer,
    file_attach_report_moet varchar,
    file_attach_report_cam varchar,
    final_behavior_point integer,
    learning_capacity integer,
    conduct_type integer,
    comment varchar,
    comment_21 varchar,
    comment_reply varchar,
    comment_reply_by bigint,
    homeroom_teacher_fullname varchar,
    is_bilingual integer,
    is_locked integer,
    is_deleted integer,
    created_by bigint,
    created_at timestamp(6) with time zone,
    updated_by bigint,
    updated_at timestamp(6) with time zone,
    source_system varchar
);
COMMENT ON TABLE s360.dim_so_evaluate_progress IS 'Thông tin đánh giá tổng kết tiến độ học tập của học sinh';

-- 32. Ánh xạ Môn học từng Trường
CREATE TABLE s360.dim_so_school_mapping_subject (
    so_school_id integer,
    school_name varchar,
    subject_id integer,
    subject_name varchar,
    school_year_id integer,
    grade_id integer,
    homeroom_class_id bigint
);
COMMENT ON TABLE s360.dim_so_school_mapping_subject IS 'Bảng ánh xạ cấu trúc môn học của từng trường theo khối lớp, lớp chủ nhiệm và năm học';

-- 33. Danh mục Môn học Chính thức
CREATE TABLE s360.dim_subject (
    id integer,
    code varchar,
    name varchar,
    name_en varchar,
    education_stages integer,
    subject_type varchar,
    is_credit integer,
    is_level_esl integer,
    is_cambridge_k11 integer,
    is_active integer,
    is_sync_lms integer,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.dim_subject IS 'Danh mục môn học chính thức của trường';

-- 34. Nhật ký Đơn xin Nghỉ học & Vắng mặt
CREATE TABLE s360.fact_absent_logs (
    id bigint,
    absent_period_id bigint,
    so_school_id integer,
    school_year_id integer,
    homeroom_class_id integer,
    student_code varchar,
    reason bytea,
    reason_norm varchar,
    reason_category varchar,
    from_date date,
    to_date date,
    is_approved integer,
    approval_status varchar,
    approved_at timestamp(6) with time zone,
    is_auto_approved integer,
    is_full_day integer,
    absent_date date,
    timetable_period_code varchar,
    timetable_period_name varchar,
    created_at varchar,
    updated_at varchar
);
COMMENT ON TABLE s360.fact_absent_logs IS 'Nhật ký chi tiết đơn xin nghỉ học của học sinh';

-- 35. Nhật ký Điểm cộng/trừ Rèn luyện Hành vi
CREATE TABLE s360.fact_behavior_logs (
    id bigint,
    so_school_id integer,
    school_year_id integer,
    student_code varchar,
    behavior_id integer,
    behavior_before_id bigint,
    object_type integer,
    object_id integer,
    behavior_code varchar,
    behavior_fullname varchar,
    behavior_fullname_clean varchar,
    behavior_level varchar,
    behavior_point varchar,
    behavior_comment varchar,
    comment_date date,
    sanction_code varchar,
    sanction_name varchar,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.fact_behavior_logs IS 'Nhật ký ghi nhận các hành vi rèn luyện của học sinh';

-- 36. Điểm danh Chuyên cần Tiết học
CREATE TABLE s360.fact_course_attendences (
    id bigint,
    so_school_id integer,
    school_year_id integer,
    course_id integer,
    timetable_period_code varchar,
    timetable_period_name varchar,
    _date date,
    student_code varchar,
    status integer,
    status_name varchar,
    comment varchar,
    is_push_to_app integer,
    is_push_notification integer,
    is_locked integer,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.fact_course_attendences IS 'Nhật ký điểm danh chuyên cần theo từng tiết học của các lớp học phần';

-- 37. Đăng ký Học phần / Khóa học
CREATE TABLE s360.fact_course_enrolls (
    id bigint,
    student_code varchar,
    course_id bigint,
    is_moved_out integer,
    moved_out_at timestamp(6) with time zone,
    is_student integer,
    is_teaching_assistant integer,
    created_at varchar,
    updated_at varchar
);
COMMENT ON TABLE s360.fact_course_enrolls IS 'Nhật ký ghi nhận học sinh đăng ký học phần (Course)';

-- 38. Đóng Học phí Ngoại khóa
CREATE TABLE s360.fact_extracurricular_activity_payments (
    id bigint,
    so_school_id integer,
    school_year_id integer,
    homeroom_class varchar,
    student_id integer,
    student_code varchar,
    vinclub_membership_rank varchar,
    vinclub_discount_percent double precision,
    original_price integer,
    discount_price integer,
    final_price integer,
    price integer,
    status integer,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.fact_extracurricular_activity_payments IS 'Dữ liệu giao dịch đóng tiền hoạt động ngoại khóa';

-- 39. Đăng ký Tham gia Ngoại khóa
CREATE TABLE s360.fact_extracurricular_activity_registers (
    id bigint,
    so_school_id integer,
    school_year_id integer,
    student_id bigint,
    student_code varchar,
    extracurricular_activity_id bigint,
    object_type integer,
    object_id varchar,
    status integer,
    status_description varchar,
    cost integer,
    paid_price integer,
    note varchar,
    is_upgrade_to_register integer,
    is_refund integer,
    change_status_at timestamp(6) with time zone,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.fact_extracurricular_activity_registers IS 'Danh sách đăng ký tham gia ngoại khóa của học sinh';

-- 40. Sổ điểm Học phần / LMS
CREATE TABLE s360.fact_gradebooks (
    id bigint,
    so_school_id integer,
    school_year_id integer,
    semester_index integer,
    semester_stages integer,
    student_code varchar,
    homeroom_class varchar,
    homeroom_teacher_id bigint,
    subject_id integer,
    course_id bigint,
    homeroom_class_id integer,
    so_exam_id bigint,
    final_grade decimal(10,2),
    final_grade_convert varchar,
    max_grade decimal(10,1),
    is_grade_letter integer,
    is_locked integer,
    is_move_in_grade integer,
    is_semester_locked integer,
    is_input_grade integer,
    is_input_after_summer integer,
    grade_id integer,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.fact_gradebooks IS 'Bảng điểm tổng hợp (Sổ điểm học bạ) của học sinh theo từng môn học và kỳ học';

-- 41. Sổ điểm Chuẩn Bộ Giáo dục (MOET)
CREATE TABLE s360.fact_gradebooks_moet (
    id bigint,
    tenant_id integer,
    so_school_id integer,
    school_code varchar,
    school_name varchar,
    campus_id integer,
    grade_id integer,
    grade_code varchar,
    grade_name varchar,
    subject_id integer,
    school_year_id integer,
    semester_index integer,
    semester_stages integer,
    so_user_id bigint,
    student_code varchar,
    course_id bigint,
    homeroom_class_id integer,
    gradebook_type_item_id bigint,
    final_grade decimal(10,1),
    comment varchar,
    is_semester_locked integer,
    is_grade_letter integer,
    is_move_in_grade integer,
    is_input_grade integer,
    is_input_after_summer integer,
    is_locked integer,
    is_deleted integer,
    created_by bigint,
    updated_by bigint,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.fact_gradebooks_moet IS 'Sổ điểm chuẩn hóa theo quy định của Bộ Giáo dục (MOET) dành cho học sinh';

-- 42. Học bạ Tổng kết Cả năm
CREATE TABLE s360.fact_overall_academic_records (
    id bigint,
    so_school_id integer,
    school_year_id bigint,
    grade_id bigint,
    homeroom_class_id bigint,
    student_id bigint,
    student_code varchar,
    join_date date,
    final_grade decimal(10,1),
    s1_final_grade decimal(10,1),
    s2_final_grade decimal(10,1),
    final_grade_after_summer decimal(10,1),
    conduct varchar,
    s1_conduct varchar,
    s2_conduct varchar,
    conduct_after_summer varchar,
    learning_capacity varchar,
    s1_learning_capacity varchar,
    s2_learning_capacity varchar,
    learning_capacity_after_summer varchar,
    final_behavior_point integer,
    s1_final_behavior_point integer,
    s2_final_behavior_point integer,
    day_of_absent integer,
    s1_day_of_absent integer,
    s2_day_of_absent integer,
    homeroom_teacher_comment varchar,
    s1_homeroom_teacher_comment varchar,
    s2_homeroom_teacher_comment varchar,
    comment_after_summer varchar,
    principal_comment varchar,
    change_final_conduct_s1 integer,
    change_final_conduct_s1_by bigint,
    change_final_conduct_s1_at timestamp(6) with time zone,
    change_final_conduct_s1_reason varchar,
    change_final_conduct_s2 integer,
    change_final_conduct_s2_by bigint,
    change_final_conduct_s2_at timestamp(6) with time zone,
    change_final_conduct_s2_reason varchar,
    change_final_conduct integer,
    change_final_conduct_by bigint,
    change_final_conduct_at timestamp(6) with time zone,
    change_final_conduct_reason varchar,
    homeroom_teacher_fullname varchar,
    is_homeroom_teacher_approved integer,
    homeroom_teacher_approved_at timestamp(6) with time zone,
    is_principal_approved integer,
    principal_approved_at timestamp(6) with time zone,
    vocational_certificate varchar,
    vocational_certificate_type varchar,
    reward varchar,
    special_reward varchar,
    status integer,
    is_locked integer,
    is_s1_locked integer,
    is_s2_locked integer,
    is_after_summer integer,
    is_passed_no_conditional integer,
    is_graduated integer,
    title varchar,
    s1_title varchar,
    s2_title varchar,
    created_at varchar,
    updated_at varchar
);
COMMENT ON TABLE s360.fact_overall_academic_records IS 'Học bạ tổng kết kết quả học tập toàn diện của học sinh theo từng năm học';

-- 43. Thống kê Chuyên cần Vắng/Trễ Theo Chu kỳ
CREATE TABLE s360.fact_so_absent_extract_late (
    student_code varchar,
    school_year_id integer,
    so_school_id integer,
    homeroom_class_id integer,
    absent_date date,
    original_reason_category varchar,
    reason_norm varchar,
    reason varchar,
    school_year varchar,
    school_year_start_date date,
    school_year_end_date date,
    reason_category varchar,
    school_code varchar,
    class_code varchar,
    class_name varchar,
    school_name varchar,
    grade_id integer,
    grade_name varchar,
    week_start date,
    month_start date
);
COMMENT ON TABLE s360.fact_so_absent_extract_late IS 'Bảng tổng hợp thống kê dữ liệu nghỉ học và đi muộn của học sinh theo chu kỳ tuần/tháng/kỳ học';

-- 44. Điểm Bài tập LMS
CREATE TABLE s360.fact_so_assignment_grade (
    id bigint,
    tenant_id bigint,
    school_id bigint,
    assignment_id bigint,
    is_sync_from_exam integer,
    user_id bigint,
    student_code varchar,
    final_grade decimal(10,1),
    comment varchar,
    is_locked integer,
    is_push_notification integer,
    is_deleted integer,
    created_by bigint,
    updated_by bigint,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.fact_so_assignment_grade IS 'Bảng ghi nhận kết quả điểm số bài tập (Assignment) được giáo viên chấm';

-- 45. Thống kê Điểm danh Ngày
CREATE TABLE s360.fact_so_class_attendance_statistics (
    id bigint,
    so_user_id bigint,
    student_code varchar,
    date date,
    status integer,
    total_lesson integer,
    lesson_attend integer,
    lesson_not_attend integer,
    tenant_id integer,
    so_school_id integer,
    school_year_id integer,
    campus_id integer,
    grade_id integer,
    homeroom_class_id integer,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.fact_so_class_attendance_statistics IS 'Bảng thống kê điểm danh chuyên cần của học sinh theo ngày';

-- 46. Nhật ký Chuyên cần Ngày theo Môn
CREATE TABLE s360.fact_so_daily_attendance (
    _date date,
    week_start date,
    month_start date,
    school_year_id integer,
    school_id integer,
    school_year varchar,
    school_year_start_date date,
    school_year_end_date date,
    student_code varchar,
    course_id integer,
    subject_id integer,
    school_code varchar,
    homeroom_class_id integer,
    class_code varchar,
    class_name varchar,
    grade_id integer,
    grade_name varchar,
    total_periods bigint,
    absent_periods bigint,
    absent_no_permission bigint,
    absent_with_permission bigint,
    any_absence_flag integer,
    full_subject_absence_flag integer,
    first_created_at varchar,
    last_updated_at varchar
);
COMMENT ON TABLE s360.fact_so_daily_attendance IS 'Bảng thống kê điểm danh môn học theo ngày của học sinh';

-- 47. Đánh giá Tiêu chí Năng lực Môn học
CREATE TABLE s360.fact_so_evaluate_process_subject_criterion (
    report_type_item_id integer,
    criterion_evaluate_id integer,
    id bigint,
    evaluate_progress_subject_id bigint,
    evaluate_progress_id bigint,
    so_school_id integer,
    grade_id integer,
    homeroom_class_id integer,
    subject_id integer,
    course_id bigint,
    user_id bigint,
    student_code varchar,
    school_year_id integer,
    semester_index integer,
    semester_stages integer,
    final_grade varchar,
    final_grade_level varchar,
    criterion_code varchar,
    criterion_name varchar,
    source_system varchar
);
COMMENT ON TABLE s360.fact_so_evaluate_process_subject_criterion IS 'Kết quả đánh giá chi tiết của học sinh theo từng tiêu chí cụ thể của môn học';

-- 48. Báo cáo Tiến trình Môn học
CREATE TABLE s360.fact_so_evaluate_process_subjects (
    id bigint,
    evaluate_progress_id bigint,
    subject_id integer,
    course_id bigint,
    final_grade_level varchar,
    end_of_year_final_grade_level varchar,
    student_level varchar,
    student_level_expected varchar,
    comment varchar,
    comment_next_term varchar,
    comment2 varchar,
    comment3 varchar,
    general_comment varchar,
    action_for_improvement_student varchar,
    action_for_improvement_teacher varchar,
    reward varchar,
    teacher_fullname varchar,
    teacher2_fullname varchar,
    is_approved integer,
    approved_by bigint,
    approved_at timestamp(6) with time zone,
    is_changed_final_grade_level integer,
    is_locked integer,
    so_school_id integer,
    grade_id integer,
    homeroom_class_id integer,
    user_id bigint,
    student_code varchar,
    school_year_id integer,
    semester_index integer,
    semester_stages integer,
    source_system varchar
);
COMMENT ON TABLE s360.fact_so_evaluate_process_subjects IS 'Báo cáo đánh giá tiến trình học tập môn học định kỳ';

-- 49. Điểm danh Lớp Chủ nhiệm Đầu giờ
CREATE TABLE s360.fact_so_homeroom_class_attendances (
    id bigint,
    tenant_id integer,
    so_school_id integer,
    campus_id integer,
    school_year_id integer,
    homeroom_class_id integer,
    attendance_date date,
    so_user_id bigint,
    student_code varchar,
    status integer,
    comment varchar,
    comment_meal varchar,
    is_push_to_app integer,
    is_push_notification integer,
    is_locked integer,
    last_attendance_update_at timestamp(6) with time zone,
    is_deleted integer,
    created_by bigint,
    updated_by bigint,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.fact_so_homeroom_class_attendances IS 'Nhật ký điểm danh lớp chủ nhiệm hàng ngày vào đầu giờ';

-- 50. Nhật ký Ca đi Muộn Lớp Chủ nhiệm
CREATE TABLE s360.fact_so_homeroom_class_late_attendances (
    id bigint,
    tenant_id integer,
    campus_id integer,
    so_school_name varchar,
    so_school_id integer,
    school_year_id integer,
    grade_id integer,
    homeroom_class_id integer,
    homeroom_class_name varchar,
    attendance_date date,
    so_user_id integer,
    student_code varchar,
    user_name varchar,
    user_fullname bytea,
    user_mail bytea,
    attendance_time timestamp(6) with time zone,
    is_late integer,
    status_name varchar,
    ignore_late integer,
    reason_ignore varchar,
    image_path varchar,
    time_late integer,
    process_status bigint,
    is_deleted integer,
    created_by bigint,
    updated_by bigint,
    created_at varchar,
    updated_at varchar,
    source_system varchar
);
COMMENT ON TABLE s360.fact_so_homeroom_class_late_attendances IS 'Nhật ký chi tiết các ca đi muộn lớp chủ nhiệm';

-- 51. Thống kê Đạt chuẩn Môn học
CREATE TABLE s360.fact_so_subject_mastery (
    so_school_id bigint,
    so_school_year_id bigint,
    semester_index integer,
    semester_stages integer,
    grade_id bigint,
    homeroom_class_name varchar,
    homeroom_class_id bigint,
    subject_id integer,
    student_code varchar,
    score_type varchar,
    final_grade double precision,
    final_grade_level varchar,
    percent_target_min double precision,
    percent_target_max double precision,
    percent_target_normal double precision,
    percent_target_exceed double precision
);
COMMENT ON TABLE s360.fact_so_subject_mastery IS 'Thống kê mức độ hoàn thành chuẩn đầu ra môn học của học sinh';

-- 52. Học bạ Môn học Chi tiết
CREATE TABLE s360.fact_subject_academic_records (
    id bigint,
    overall_record_id bigint,
    subject_id bigint,
    final_grade decimal(10,1),
    s1_final_grade decimal(10,1),
    s2_final_grade decimal(10,1),
    final_grade_after_summer decimal(10,1),
    is_teacher_approved integer,
    is_after_summer integer,
    is_input_final_grade_s1 integer,
    is_input_final_grade_s2 integer,
    is_input_final_grade_cn integer,
    is_locked integer,
    is_deleted integer,
    created_at varchar,
    updated_at varchar
);
COMMENT ON TABLE s360.fact_subject_academic_records IS 'Kết quả học tập tổng kết của học sinh chi tiết theo từng môn học';

-- 53. Liên kết Đăng ký & Thanh toán Ngoại khóa
CREATE TABLE s360.link_register_payment (
    id bigint,
    payment_id integer,
    register_id integer,
    created_at varchar,
    updated_at varchar
);
COMMENT ON TABLE s360.link_register_payment IS 'Bảng trung gian liên kết giữa thông tin đăng ký ngoại khóa và thông tin thanh toán';

-- ============================================================
-- SCHEMA: t360 (TEACHER 360 DWH - 1 TABLE)
-- ============================================================

-- 54. Phân công Giáo viên Chủ nhiệm & Bộ môn
CREATE TABLE t360.dim_t360_homeroom_class_teacher (
    id bigint,
    tenant_id bigint,
    homeroom_teacher_id decimal(20,0),
    teacher_code varchar,
    teacher_name bytea,
    homeroom_class_id bigint,
    class_code varchar,
    class_name varchar,
    so_school_id integer,
    school_name varchar,
    school_code varchar,
    so_campus_name varchar,
    school_year_id integer,
    school_year_code varchar,
    grade_name varchar,
    is_moved_out integer,
    teacher_type varchar,
    is_deleted integer,
    created_at timestamp(6) with time zone,
    updated_at timestamp(6) with time zone
);
COMMENT ON TABLE t360.dim_t360_homeroom_class_teacher IS 'Danh mục phân công giáo viên chủ nhiệm hoặc giáo viên giảng dạy chính theo lớp, năm học và cơ sở trường';

-- ============================================================
-- TRIGGERS: Tự động cập nhật updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
CREATE TRIGGER trg_ai_sessions_updated BEFORE UPDATE ON public.ai_sessions FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
CREATE TRIGGER trg_exam_papers_updated BEFORE UPDATE ON public.exam_papers FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
CREATE TRIGGER trg_classroom_recordings_updated BEFORE UPDATE ON public.classroom_recordings FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
CREATE TRIGGER trg_question_items_updated BEFORE UPDATE ON public.question_items FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

-- End of Consolidated DDL
