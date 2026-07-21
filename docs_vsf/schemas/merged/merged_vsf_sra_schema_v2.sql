-- ============================================================
-- VSF Student Risk Alert (VSF SRA) - Consolidated Database Schema DDL V2 (Streamlined & Merged)
-- Combination of App Core/AI Engine (Public) and School Online DWH (s360, t360, default)
-- Total Tables: 55 Tables
-- DBMS: PostgreSQL 16+
-- ============================================================

-- Create Extensions
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create Schemas
CREATE SCHEMA IF NOT EXISTS public;
CREATE SCHEMA IF NOT EXISTS s360;
CREATE SCHEMA IF NOT EXISTS t360;
CREATE SCHEMA IF NOT EXISTS "default";

-- ============================================================
-- ENUMS & TYPES (Schema: public)
-- ============================================================

DROP TYPE IF EXISTS public.school_level_enum CASCADE;
DROP TYPE IF EXISTS public.user_role_enum CASCADE;
DROP TYPE IF EXISTS public.role_context_enum CASCADE;
DROP TYPE IF EXISTS public.score_type_enum CASCADE;
DROP TYPE IF EXISTS public.score_category_enum CASCADE;
DROP TYPE IF EXISTS public.score_status_enum CASCADE;
DROP TYPE IF EXISTS public.assessment_type_enum CASCADE;
DROP TYPE IF EXISTS public.pass_fail_enum CASCADE;
DROP TYPE IF EXISTS public.conduct_enum CASCADE;
DROP TYPE IF EXISTS public.file_type_enum CASCADE;
DROP TYPE IF EXISTS public.difficulty_enum CASCADE;
DROP TYPE IF EXISTS public.ai_session_role_enum CASCADE;
DROP TYPE IF EXISTS public.guardrail_status_enum CASCADE;
DROP TYPE IF EXISTS public.recording_rank_enum CASCADE;
DROP TYPE IF EXISTS public.question_type_enum CASCADE;
DROP TYPE IF EXISTS public.exam_format_enum CASCADE;
DROP TYPE IF EXISTS public.item_status_enum CASCADE;
DROP TYPE IF EXISTS public.item_source_enum CASCADE;
DROP TYPE IF EXISTS public.gen_exam_status_enum CASCADE;
DROP TYPE IF EXISTS public.notification_type_enum CASCADE;
DROP TYPE IF EXISTS public.grade_scale_type_enum CASCADE;

CREATE TYPE public.grade_scale_type_enum AS ENUM (
    'SCALE_10',       -- Thang điểm 10.0 (MOET 0.0 - 10.0)
    'SCALE_100',      -- Thang điểm 100 (%)
    'SCALE_4',        -- Thang điểm GPA 4.0
    'SCALE_6',        -- Thang điểm 6.0 (Cambridge Primary)
    'SCALE_LETTER',   -- Thang điểm chữ (A, B, C, D, E, F)
    'SCALE_PASS_FAIL' -- Thang điểm nhận xét (DAT, CHUA_DAT)
);

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
CREATE TYPE public.guardrail_status_enum AS ENUM ('PASSED', 'BLOCKED_INJECTION', 'BLOCKED_SQL', 'BLOCKED_PII', 'BLOCKED_SENSITIVE');
CREATE TYPE public.recording_rank_enum AS ENUM ('EXCELLENT', 'SATISFACTORY', 'NEEDS_IMPROVEMENT');
CREATE TYPE public.question_type_enum AS ENUM ('MCQ', 'TRUE_FALSE', 'SHORT_ANSWER', 'ESSAY');
CREATE TYPE public.exam_format_enum AS ENUM ('MCQ_ONLY', 'ESSAY_ONLY', 'MIXED');
CREATE TYPE public.item_status_enum AS ENUM ('DRAFT', 'REVIEW', 'APPROVED', 'REJECTED', 'RETIRED');
CREATE TYPE public.item_source_enum AS ENUM ('AI_GENERATED', 'MANUAL', 'IMPORTED');
CREATE TYPE public.gen_exam_status_enum AS ENUM ('DRAFT', 'FINALIZED', 'PUBLISHED');
CREATE TYPE public.notification_type_enum AS ENUM ('QUESTION_SUBMITTED', 'ITEM_REVIEWED', 'EXAM_FINALIZED', 'ANNOUNCEMENT', 'GENERATION_FAILED');

-- ============================================================
-- SCHEMA: public (APP CORE & AI ENGINE - 18 TABLES)
-- ============================================================

-- 1. Users
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
    teacher_code    VARCHAR(50),
    student_code    VARCHAR(50),
    so_student_id   BIGINT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_school ON public.users(so_school_id);
CREATE INDEX idx_users_role   ON public.users(role);
CREATE INDEX idx_users_email  ON public.users(email);
CREATE INDEX idx_users_tcode  ON public.users(teacher_code);

-- 2. Refresh Tokens
CREATE TABLE public.refresh_tokens (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL UNIQUE,
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Audit Logs
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

-- 4. AI Sessions
CREATE TABLE public.ai_sessions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title           VARCHAR(500),
    context_filter  JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. AI Messages
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

-- 6. AI Attachments
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

-- 7. Report Schedules
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

-- 8. Classroom Recordings
CREATE TABLE public.classroom_recordings (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    teacher_id      BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    subject_id      INTEGER NOT NULL,
    class_id        INTEGER NOT NULL,
    course_id       BIGINT,
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

-- 9. Exam Papers
CREATE TABLE public.exam_papers (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    subject_id      INTEGER NOT NULL,
    semester_id     INTEGER NOT NULL,
    grade_id        INTEGER,
    score_type      VARCHAR(100),
    so_exam_id      BIGINT,
    gradebook_type_item_id BIGINT,
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

-- 10. Exam Competencies
CREATE TABLE public.exam_competencies (
    exam_paper_id   BIGINT NOT NULL REFERENCES public.exam_papers(id) ON DELETE CASCADE,
    strand_id       BIGINT NOT NULL,
    weight          NUMERIC(4,3) NOT NULL DEFAULT 0 CHECK (weight BETWEEN 0 AND 1),
    bloom_level     SMALLINT CHECK (bloom_level BETWEEN 1 AND 6),
    PRIMARY KEY (exam_paper_id, strand_id)
);

-- 11. Exam Column Mappings
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

-- 12. Question Items
CREATE TABLE public.question_items (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    subject_id      INTEGER NOT NULL,
    grade_number    SMALLINT NOT NULL CHECK (grade_number BETWEEN 1 AND 12),
    strand_id       BIGINT,
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

-- 13. Misconceptions
CREATE TABLE public.misconceptions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id    INTEGER,
    subject_id      INTEGER NOT NULL,
    strand_id       BIGINT,
    grade_number    SMALLINT NOT NULL CHECK (grade_number BETWEEN 1 AND 12),
    description     TEXT NOT NULL,
    example_wrong   TEXT,
    evidence_count  INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 14. Exam Blueprints
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

-- 15. Generated Exams
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

-- 16. Generated Exam Items
CREATE TABLE public.generated_exam_items (
    generated_exam_id BIGINT NOT NULL REFERENCES public.generated_exams(id) ON DELETE CASCADE,
    variant_code      VARCHAR(8) NOT NULL,
    position          SMALLINT NOT NULL CHECK (position >= 1),
    item_id           BIGINT NOT NULL REFERENCES public.question_items(id) ON DELETE RESTRICT,
    points            NUMERIC(4, 2) NOT NULL,
    option_order      JSONB,
    PRIMARY KEY (generated_exam_id, variant_code, position)
);

-- 17. Notifications
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

-- 18. AI Observability Snapshots
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
-- SCHEMA: s360 (STUDENT 360 DWH - 33 TABLES STREAMLINED V2)
-- ============================================================

-- 19. Grade Scale Detail (Universal % Bridge Matrix for 6 Scales)
CREATE TABLE s360.dim_grade_scale_detail (
    id              BIGINT PRIMARY KEY,
    so_school_id    INTEGER NOT NULL,
    scale_type      public.grade_scale_type_enum NOT NULL DEFAULT 'SCALE_10',
    scale_name      VARCHAR(100) NOT NULL,
    max_score       NUMERIC(5,2) NOT NULL DEFAULT 10.00,
    min_score_range NUMERIC(5,2),
    max_score_range NUMERIC(5,2),
    min_percent     NUMERIC(5,2) NOT NULL,
    max_percent     NUMERIC(5,2) NOT NULL,
    representative_percent NUMERIC(5,2) NOT NULL,
    grade_letter    VARCHAR(10),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 20. Behavior Criteria
CREATE TABLE s360.dim_behavior (
    id integer PRIMARY KEY,
    code varchar,
    name varchar,
    group_code varchar,
    group_name varchar,
    point double precision,
    point_min integer,
    point_max integer,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 21. Course / LMS Section
CREATE TABLE s360.dim_course (
    id bigint PRIMARY KEY,
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
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 22. Exam Types
CREATE TABLE s360.dim_exam (
    id bigint PRIMARY KEY,
    so_exam_id bigint,
    school_year_id integer,
    subject_id integer,
    grade_id integer,
    grade_code varchar,
    grade_name varchar,
    exam_code varchar,
    exam_name varchar,
    so_parent_exam_id bigint,
    coefficient decimal(10,1),
    moet_semester_index integer,
    max_grade decimal(10,1),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 23. Exam MOET Types
CREATE TABLE s360.dim_exam_moet (
    gradebook_type_item_id bigint PRIMARY KEY,
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
    coefficient decimal(10,1),
    max_grade decimal(10,1),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 24. Extracurricular Activity
CREATE TABLE s360.dim_extracurricular_activity (
    id integer PRIMARY KEY,
    so_school_id integer,
    school_year varchar,
    code varchar,
    name varchar,
    category_code varchar,
    category_name varchar,
    cost decimal(10,1),
    start_date date,
    end_date date,
    status varchar,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 25. Homeroom Class
CREATE TABLE s360.dim_homeroom_class (
    id bigint PRIMARY KEY,
    so_school_id integer,
    school_year_id integer,
    grade_id integer,
    code varchar,
    fullname varchar,
    homeroom_teacher_id bigint,
    teacher_code varchar,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 26. Homeroom Class Student (Danh sách Học sinh DWH)
CREATE TABLE s360.dim_homeroom_class_student (
    id bigint PRIMARY KEY,
    tenant_id integer,
    so_student_id bigint,
    student_code varchar,
    student_fullname varchar, -- Đã chuyển từ bytea rác sang varchar chuẩn
    gender_name varchar,
    homeroom_class_id integer,
    class_code varchar,
    class_name varchar,
    so_school_id integer,
    school_year_id integer,
    school_name varchar,
    school_code varchar,
    teacher_code varchar,
    grade_id integer,
    grade_name varchar,
    join_date date,
    status integer,
    is_active integer,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 27. School Year
CREATE TABLE s360.dim_school_year (
    id integer PRIMARY KEY,
    code varchar,
    fullname varchar,
    start_date date,
    end_date date,
    is_current integer,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 28. Assignment LMS
CREATE TABLE s360.dim_so_assignment (
    assignment_id bigint PRIMARY KEY,
    so_school_id integer,
    grade_id integer,
    subject_id integer,
    course_id bigint,
    code varchar,
    fullname varchar,
    max_grade decimal(10,0),
    description varchar,
    due_date date,
    date_assigned date,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 29. Evaluate Progress (Đã lược bỏ các cột file PDF đính kèm & comment rác)
CREATE TABLE s360.dim_so_evaluate_progress (
    id bigint PRIMARY KEY,
    tenant_id integer,
    so_school_id integer,
    school_name varchar,
    school_code varchar,
    school_year_id integer,
    grade_id integer,
    grade_code varchar,
    grade_name varchar,
    class_code varchar,
    class_name varchar,
    semester_index integer,
    semester_stages integer,
    homeroom_class_id integer,
    so_student_id bigint,
    student_code varchar,
    is_attach_report_moet integer,
    is_attach_report_cam integer,
    final_behavior_point integer,
    learning_capacity integer,
    conduct_type integer,
    comment varchar,
    homeroom_teacher_fullname varchar,
    is_bilingual integer,
    is_locked integer,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 30. School Mapping Subject
CREATE TABLE s360.dim_so_school_mapping_subject (
    so_school_id integer,
    school_name varchar,
    subject_id integer,
    subject_name varchar,
    school_year_id integer,
    grade_id integer,
    homeroom_class_id bigint
);

-- 31. Subject Catalog
CREATE TABLE s360.dim_subject (
    id integer PRIMARY KEY,
    code varchar,
    name varchar,
    name_en varchar,
    is_active integer,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 32. Absent Logs (Đã chuyển reason sang VARCHAR)
CREATE TABLE s360.fact_absent_logs (
    id bigint PRIMARY KEY,
    absent_period_id bigint,
    so_school_id integer,
    school_year_id integer,
    homeroom_class_id integer,
    student_code varchar,
    reason_norm varchar,
    reason_category varchar,
    from_date date,
    to_date date,
    is_approved integer,
    approval_status varchar,
    approved_at TIMESTAMPTZ,
    absent_date date,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 33. Behavior Logs
CREATE TABLE s360.fact_behavior_logs (
    id bigint PRIMARY KEY,
    so_school_id integer,
    school_year_id integer,
    student_code varchar,
    behavior_id integer,
    behavior_code varchar,
    behavior_fullname varchar,
    behavior_point varchar,
    behavior_comment varchar,
    comment_date date,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 34. Course Attendances
CREATE TABLE s360.fact_course_attendences (
    id bigint PRIMARY KEY,
    so_school_id integer,
    school_year_id integer,
    course_id integer,
    _date date,
    student_code varchar,
    status integer,
    status_name varchar,
    comment varchar,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 35. Course Enrolls
CREATE TABLE s360.fact_course_enrolls (
    id bigint PRIMARY KEY,
    so_school_id integer,
    school_year_id integer,
    course_id integer,
    student_code varchar,
    status integer,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 36. Extracurricular Payments
CREATE TABLE s360.fact_extracurricular_activity_payments (
    id bigint PRIMARY KEY,
    so_school_id integer,
    student_code varchar,
    activity_id integer,
    amount decimal(10,1),
    payment_status varchar,
    payment_date TIMESTAMPTZ
);

-- 37. Extracurricular Registers
CREATE TABLE s360.fact_extracurricular_activity_registers (
    id bigint PRIMARY KEY,
    so_school_id integer,
    student_code varchar,
    activity_id integer,
    register_date TIMESTAMPTZ,
    status varchar
);

-- 38. Gradebooks LMS
CREATE TABLE s360.fact_gradebooks (
    id bigint PRIMARY KEY,
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
    grade_id integer,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 39. Gradebooks MOET
CREATE TABLE s360.fact_gradebooks_moet (
    id bigint PRIMARY KEY,
    tenant_id integer,
    so_school_id integer,
    school_code varchar,
    school_name varchar,
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
    is_locked integer,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 40. Overall Academic Records
CREATE TABLE s360.fact_overall_academic_records (
    id bigint PRIMARY KEY,
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
    conduct varchar,
    learning_capacity varchar,
    final_behavior_point integer,
    day_of_absent integer,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 41. Absent Extract Late
CREATE TABLE s360.fact_so_absent_extract_late (
    student_code varchar,
    school_year_id integer,
    so_school_id integer,
    homeroom_class_id integer,
    absent_date date,
    reason_norm varchar,
    school_code varchar,
    class_code varchar,
    class_name varchar,
    grade_id integer,
    week_start date,
    month_start date
);

-- 42. Assignment Grade LMS
CREATE TABLE s360.fact_so_assignment_grade (
    id bigint PRIMARY KEY,
    tenant_id bigint,
    school_id bigint,
    assignment_id bigint,
    user_id bigint,
    student_code varchar,
    final_grade decimal(10,1),
    comment varchar,
    is_locked integer,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 43. Class Attendance Statistics
CREATE TABLE s360.fact_so_class_attendance_statistics (
    id bigint PRIMARY KEY,
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
    grade_id integer,
    homeroom_class_id integer,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 44. Daily Attendance
CREATE TABLE s360.fact_so_daily_attendance (
    _date date,
    week_start date,
    month_start date,
    school_year_id integer,
    school_id integer,
    student_code varchar,
    course_id integer,
    subject_id integer,
    homeroom_class_id integer,
    grade_id integer,
    total_periods bigint,
    absent_periods bigint,
    absent_no_permission bigint,
    absent_with_permission bigint,
    any_absence_flag integer,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 45. Evaluate Process Subject Criterion
CREATE TABLE s360.fact_so_evaluate_process_subject_criterion (
    id bigint PRIMARY KEY,
    report_type_item_id integer,
    criterion_evaluate_id integer,
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
    criterion_name varchar
);

-- 46. Evaluate Process Subjects
CREATE TABLE s360.fact_so_evaluate_process_subjects (
    id bigint PRIMARY KEY,
    evaluate_progress_id bigint,
    so_school_id integer,
    school_year_id integer,
    grade_id integer,
    homeroom_class_id integer,
    subject_id integer,
    user_id bigint,
    student_code varchar,
    semester_index integer,
    final_grade decimal(10,1),
    comment varchar
);

-- 47. Homeroom Class Attendances
CREATE TABLE s360.fact_so_homeroom_class_attendances (
    id bigint PRIMARY KEY,
    so_school_id integer,
    school_year_id integer,
    homeroom_class_id integer,
    student_code varchar,
    date date,
    status integer,
    comment varchar
);

-- 48. Homeroom Class Late Attendances
CREATE TABLE s360.fact_so_homeroom_class_late_attendances (
    id bigint PRIMARY KEY,
    so_school_id integer,
    student_code varchar,
    date date,
    late_minutes integer,
    reason varchar
);

-- 49. Subject Mastery
CREATE TABLE s360.fact_so_subject_mastery (
    id bigint PRIMARY KEY,
    so_school_id integer,
    school_year_id integer,
    grade_id integer,
    subject_id integer,
    student_code varchar,
    score_type varchar,
    mastery_percent decimal(5,2),
    mastery_status varchar
);

-- 50. Subject Academic Records
CREATE TABLE s360.fact_subject_academic_records (
    id bigint PRIMARY KEY,
    so_school_id integer,
    school_year_id integer,
    grade_id integer,
    subject_id integer,
    student_code varchar,
    final_grade decimal(10,1),
    s1_final_grade decimal(10,1),
    s2_final_grade decimal(10,1)
);

-- 51. Link Register Payment
CREATE TABLE s360.link_register_payment (
    id bigint PRIMARY KEY,
    register_id bigint,
    payment_id bigint
);

-- ============================================================
-- SCHEMA: t360 (TEACHER 360 DWH - 1 TABLE)
-- ============================================================

-- 52. Teacher Homeroom Class Assignment
CREATE TABLE t360.dim_t360_homeroom_class_teacher (
    id bigint PRIMARY KEY,
    so_school_id integer,
    school_year_id integer,
    homeroom_class_id integer,
    teacher_code varchar,
    teacher_name varchar,
    is_homeroom integer
);

-- ============================================================
-- SCHEMA: "default" (STAGING TABLES - 3 TABLES)
-- ============================================================

-- 53. Staging MOET Path
CREATE TABLE "default".stg_so_exam_moet_path (
    gradebook_type_item_id bigint,
    parent_id bigint,
    gradebook_type_items_fullname varchar,
    level integer,
    path varchar,
    id_path varchar
);

-- 54. Staging Strand Path
CREATE TABLE "default".stg_so_strand_path (
    strand_id bigint,
    parent_id integer,
    strand_name varchar,
    level integer,
    path varchar,
    id_path varchar,
    subject_id integer,
    subject_name varchar
);

-- 55. Staging Students
CREATE TABLE "default".stg_so_students (
    id decimal(20,0),
    code varchar
);
