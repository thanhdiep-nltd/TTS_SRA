-- ============================================================
--  AI20K-075 — AI Trợ Lý Phân Tích Kết Quả Học Tập Toàn Trường
--  Database Schema v2.0
--  PostgreSQL 16
--
--  Phase 1 (hiện tại): Đo lường năng lực đa chiều trên dữ liệu
--    điểm TỔNG HỢP mỗi môn (chuẩn hóa theo độ khó + ánh xạ chương trình).
--  Phase 2 (sau): item-level (questions/student_responses) + RAG
--    (exam_chunks + pgvector). Schema này đã chừa chỗ để mở rộng.
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- Hỗ trợ tìm kiếm tên gần đúng
-- NOTE: extension "vector" (pgvector) để dành cho Phase 2 (RAG).

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE school_level_enum AS ENUM ('PRIMARY', 'SECONDARY', 'HIGH', 'ALL');

CREATE TYPE user_role_enum AS ENUM (
    'ADMIN',
    'PRINCIPAL',
    'GRADE_HEAD_PRIMARY',
    'HOMEROOM_TEACHER_PRIMARY',
    'SUBJECT_TEACHER',
    'HOMEROOM_TEACHER_SECONDARY',
    'SUBJECT_HEAD'
);

CREATE TYPE role_context_enum AS ENUM (
    'HOMEROOM_PRIMARY',
    'HOMEROOM_SECONDARY',
    'SUBJECT_TEACHER',
    'GRADE_HEAD',
    'SUBJECT_HEAD'
);

-- (Legacy) còn dùng cho exam_papers.score_type. scores đã chuyển sang score_category + column_index.
CREATE TYPE score_type_enum AS ENUM ('TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK');

-- Nhóm đầu điểm (số cột mỗi nhóm do column_index quyết định): Miệng×3, TX×4, GK×2, CK×1
CREATE TYPE score_category_enum AS ENUM (
    'ORAL',     -- Kiểm tra miệng — hệ số 1 (không map đề)
    'REGULAR',  -- Kiểm tra thường xuyên — hệ số 1
    'MIDTERM',  -- Giữa kỳ — hệ số 2
    'FINAL'     -- Cuối kỳ — hệ số 3
);

CREATE TYPE score_status_enum AS ENUM ('DRAFT', 'SUBMITTED', 'APPROVED');

-- Cách đánh giá môn: SCORED = cho điểm 0–10 (tính ĐTB); REMARK = Đạt/Chưa đạt (không tính ĐTB)
CREATE TYPE assessment_type_enum AS ENUM ('SCORED', 'REMARK');

-- Kết quả môn đánh giá bằng nhận xét
CREATE TYPE pass_fail_enum AS ENUM ('DAT', 'CHUA_DAT');

-- Hạnh kiểm (GV chủ nhiệm đánh giá)
CREATE TYPE conduct_enum AS ENUM ('TOT', 'KHA', 'TRUNG_BINH', 'YEU');

CREATE TYPE file_type_enum AS ENUM ('PDF', 'WORD', 'IMAGE', 'OTHER');

CREATE TYPE difficulty_enum AS ENUM ('EASY', 'MEDIUM', 'HARD');

CREATE TYPE ai_session_role_enum AS ENUM ('user', 'assistant', 'system');

-- Trạng thái guardrail cho mỗi lượt Text-to-SQL (PRD §6.6 / §8)
CREATE TYPE guardrail_status_enum AS ENUM (
    'PASSED',
    'BLOCKED_INJECTION',   -- Input guardrail: phát hiện prompt injection / jailbreak
    'BLOCKED_SQL',         -- Execution guardrail: SQL không phải SELECT / có từ khóa cấm
    'BLOCKED_PII',         -- Output guardrail: chặn rò rỉ thông tin cá nhân
    'BLOCKED_SENSITIVE'
);

-- ============================================================
-- SCHOOLS
-- ============================================================

CREATE TABLE schools (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    code            VARCHAR(50) UNIQUE NOT NULL,       -- Mã trường: THCS-XYZ
    address         TEXT,
    phone           VARCHAR(20),
    logo_url        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- USERS & AUTHENTICATION
-- (Đặt TRƯỚC subjects vì subjects.subject_head_id tham chiếu users)
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id       UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,             -- bcrypt
    full_name       VARCHAR(255) NOT NULL,
    phone           VARCHAR(20),
    avatar_url      TEXT,
    role            user_role_enum NOT NULL,
    school_level    school_level_enum NOT NULL DEFAULT 'ALL',
    subject_id      UUID,  -- môn phụ trách (chuyên môn của GV); FK thêm sau subjects (vòng phụ thuộc)
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL UNIQUE,      -- SHA-256 của token thật
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- CORE SCHOOL STRUCTURE
-- ============================================================

-- Năm học: 2024-2025, 2025-2026
CREATE TABLE academic_years (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id       UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name            VARCHAR(20) NOT NULL,              -- "2025-2026"
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    is_current      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (school_id, name)
);

-- Học kỳ: HK1, HK2
CREATE TABLE semesters (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    academic_year_id UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    name            VARCHAR(10) NOT NULL,              -- "HK1", "HK2"
    number          SMALLINT NOT NULL CHECK (number IN (1, 2)),
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    is_current      BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (academic_year_id, number)
);

-- Khối lớp: 1→5 (Cấp 1), 6→9 (Cấp 2), 10→12 (Cấp 3)
CREATE TABLE grades (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id       UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name            VARCHAR(20) NOT NULL,              -- "Khối 1", "Khối 8"
    grade_number    SMALLINT NOT NULL CHECK (grade_number BETWEEN 1 AND 12),
    school_level    school_level_enum NOT NULL,        -- Tự suy ra từ grade_number
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (school_id, grade_number)
);

-- Lớp học: 1A, 6B, 10C
CREATE TABLE classes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    grade_id        UUID NOT NULL REFERENCES grades(id) ON DELETE CASCADE,
    name            VARCHAR(20) NOT NULL,              -- "6A", "10B"
    academic_year_id UUID NOT NULL REFERENCES academic_years(id),
    student_count   SMALLINT DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (grade_id, name, academic_year_id)
);

-- Môn học
CREATE TABLE subjects (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id       UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,             -- "Toán", "Ngữ Văn", "Tiếng Anh"
    code            VARCHAR(20) NOT NULL,              -- "TOAN", "VAN", "ANH"
    applicable_level school_level_enum NOT NULL DEFAULT 'ALL',  -- cấp áp dụng (THCS/THPT/...)
    assessment_type assessment_type_enum NOT NULL DEFAULT 'SCORED',  -- SCORED (điểm) | REMARK (Đạt/CĐ, không tính ĐTB)
    subject_head_id UUID REFERENCES users(id) ON DELETE SET NULL,  -- Trưởng bộ môn (Cấp 2/3)
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (school_id, code)
);

-- FK vòng: users.subject_id -> subjects (môn phụ trách của GV), thêm sau khi subjects tồn tại.
ALTER TABLE users ADD CONSTRAINT fk_users_subject_id_subjects
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL;

-- ============================================================
-- TEACHER ASSIGNMENTS (Phân công giảng dạy)
-- ============================================================
-- Logic:
--   Cấp 1 HOMEROOM_PRIMARY: class_id = lớp chủ nhiệm, subject_id = NULL, grade_id = NULL
--   Cấp 1 GRADE_HEAD:       grade_id = khối quản lý, class_id = NULL, subject_id = NULL
--   Cấp 2/3 SUBJECT_TEACHER: class_id = lớp dạy, subject_id = môn dạy, grade_id = NULL
--   Cấp 2/3 HOMEROOM_SECONDARY: class_id = lớp chủ nhiệm, subject_id = NULL (chỉ xem bảng tổng hợp)
--   Cấp 2/3 SUBJECT_HEAD:   subject_id = môn quản lý, class_id = NULL, grade_id = NULL
-- Quy tắc nghiệp vụ (enforce ở src/services/assignments.py, không ở DB):
--   • Mỗi GV chỉ chủ nhiệm TỐI ĐA 1 lớp / năm học.
--   • Khi nhận chủ nhiệm, tự sinh phân công SUBJECT_TEACHER cho môn phụ trách (users.subject_id) tại lớp đó.

CREATE TABLE teacher_assignments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    academic_year_id UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    role_context    role_context_enum NOT NULL,
    class_id        UUID REFERENCES classes(id) ON DELETE CASCADE,     -- nullable
    grade_id        UUID REFERENCES grades(id) ON DELETE CASCADE,      -- nullable (Grade Head)
    subject_id      UUID REFERENCES subjects(id) ON DELETE CASCADE,    -- nullable (Cấp 1 / homeroom)
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_assignment_consistency CHECK (
        (role_context = 'HOMEROOM_PRIMARY'   AND class_id IS NOT NULL AND subject_id IS NULL     AND grade_id IS NULL) OR
        (role_context = 'GRADE_HEAD'         AND grade_id IS NOT NULL AND class_id IS NULL       AND subject_id IS NULL) OR
        (role_context = 'SUBJECT_TEACHER'    AND class_id IS NOT NULL AND subject_id IS NOT NULL AND grade_id IS NULL) OR
        (role_context = 'HOMEROOM_SECONDARY' AND class_id IS NOT NULL AND subject_id IS NULL     AND grade_id IS NULL) OR
        (role_context = 'SUBJECT_HEAD'       AND subject_id IS NOT NULL AND class_id IS NULL     AND grade_id IS NULL)
    ),
    -- NULLS NOT DISTINCT: chặn phân công trùng kể cả khi có cột NULL (PG15+)
    UNIQUE NULLS NOT DISTINCT (user_id, role_context, class_id, grade_id, subject_id, academic_year_id)
);

-- ============================================================
-- STUDENTS (Học sinh)
-- ============================================================

CREATE TABLE students (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id       UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    student_code    VARCHAR(20) NOT NULL,              -- Mã học sinh
    full_name       VARCHAR(255) NOT NULL,
    date_of_birth   DATE,
    gender          VARCHAR(10) CHECK (gender IN ('MALE', 'FEMALE', 'OTHER')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (school_id, student_code)
);

-- Enrollment: học sinh thuộc lớp nào trong năm học nào
CREATE TABLE enrollments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    class_id        UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    academic_year_id UUID NOT NULL REFERENCES academic_years(id),
    enrolled_at     DATE NOT NULL DEFAULT CURRENT_DATE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (student_id, academic_year_id)                -- 1 HS chỉ ở 1 lớp / năm học
);

-- ============================================================
-- EXAM PAPERS (Metadata độ khó + chương trình của đề kiểm tra)
-- Phase 1: chỉ lưu metadata. RAG (exam_chunks + embedding) để Phase 2.
-- ============================================================

CREATE TABLE exam_papers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id       UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    subject_id      UUID NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
    semester_id     UUID NOT NULL REFERENCES semesters(id) ON DELETE RESTRICT,
    grade_id        UUID REFERENCES grades(id),         -- đề cho cả khối hoặc một lớp
    score_type      score_type_enum,                    -- (legacy, nullable) — binding thật ở exam_column_mappings
    title           VARCHAR(500) NOT NULL,              -- "Đề thi GK Toán Khối 8 HK1 2025-2026"
    description     TEXT,
    file_url        TEXT,                               -- URL file gốc (nullable; có thể chưa upload)
    file_type       file_type_enum DEFAULT 'PDF',
    file_size_bytes BIGINT,
    -- Độ khó KHAI BÁO (prior từ GV + AI). Hiệu chỉnh/đối chiếu bằng mv_exam_difficulty.
    difficulty      difficulty_enum,
    difficulty_coefficient NUMERIC(3,2) NOT NULL DEFAULT 1.00
                        CHECK (difficulty_coefficient BETWEEN 0.50 AND 1.50),
    num_questions   SMALLINT,
    total_points    NUMERIC(5,2),
    topics          TEXT[],                             -- ["Hình học", "Đại số"]
    ai_analysis     JSONB NOT NULL DEFAULT '{}',        -- LLM enrichment: phân bố Bloom, ước lượng độ khó, coverage
    metadata        JSONB NOT NULL DEFAULT '{}',
    uploaded_by     UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- CURRICULUM MAP (Chuẩn đầu ra / đơn vị chương trình)
-- ============================================================

-- Bản đồ chương trình, phân cấp: chương → bài → chuẩn đầu ra
CREATE TABLE curriculum_units (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_id      UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    grade_number    SMALLINT NOT NULL CHECK (grade_number BETWEEN 1 AND 12),
    parent_id       UUID REFERENCES curriculum_units(id) ON DELETE CASCADE,
    code            VARCHAR(50) NOT NULL,               -- "TOAN8.DS.PT_BAC1"
    name            VARCHAR(255) NOT NULL,              -- "Phương trình bậc nhất một ẩn"
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (subject_id, grade_number, code)
);

-- Đề kiểm tra phủ những chuẩn nào, trọng số bao nhiêu.
-- Ánh xạ ở mức ĐỀ (vì dữ liệu điểm là tổng hợp, chưa có item-level).
CREATE TABLE exam_competencies (
    exam_paper_id   UUID NOT NULL REFERENCES exam_papers(id) ON DELETE CASCADE,
    unit_id         UUID NOT NULL REFERENCES curriculum_units(id) ON DELETE RESTRICT,
    weight          NUMERIC(4,3) NOT NULL DEFAULT 0 CHECK (weight BETWEEN 0 AND 1),  -- tỉ trọng điểm
    bloom_level     SMALLINT CHECK (bloom_level BETWEEN 1 AND 6),  -- 1=Nhớ ... 6=Sáng tạo
    PRIMARY KEY (exam_paper_id, unit_id)
);

-- Liên kết đề thi vào CỘT điểm (Pha 2). REGULAR(TX): theo lớp. MIDTERM/FINAL: theo khối.
CREATE TABLE exam_column_mappings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_id      UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    semester_id     UUID NOT NULL REFERENCES semesters(id) ON DELETE CASCADE,
    score_category  score_category_enum NOT NULL,
    column_index    SMALLINT NOT NULL,
    class_id        UUID REFERENCES classes(id) ON DELETE CASCADE,   -- cho REGULAR (TX)
    grade_id        UUID REFERENCES grades(id) ON DELETE CASCADE,    -- cho MIDTERM/FINAL
    exam_paper_id   UUID NOT NULL REFERENCES exam_papers(id) ON DELETE CASCADE,
    mapped_by       UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ( (score_category = 'REGULAR' AND class_id IS NOT NULL AND grade_id IS NULL)
         OR (score_category IN ('MIDTERM','FINAL') AND grade_id IS NOT NULL AND class_id IS NULL) ),
    UNIQUE NULLS NOT DISTINCT (subject_id, semester_id, score_category, column_index, class_id, grade_id)
);

-- ============================================================
-- SCORES (Điểm số — dữ liệu tổng hợp mỗi môn)
-- ============================================================

CREATE TABLE scores (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
    subject_id      UUID NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
    class_id        UUID NOT NULL REFERENCES classes(id) ON DELETE RESTRICT,  -- denormalize: giữ lớp tại thời điểm chấm
    semester_id     UUID NOT NULL REFERENCES semesters(id) ON DELETE RESTRICT,
    score_category  score_category_enum NOT NULL,                            -- ORAL/REGULAR/MIDTERM/FINAL
    column_index    SMALLINT NOT NULL CHECK (column_index >= 1),             -- cột thứ mấy trong nhóm
    value           NUMERIC(4,2) NOT NULL CHECK (value >= 0 AND value <= 10),
    exam_paper_id   UUID REFERENCES exam_papers(id) ON DELETE SET NULL,       -- nên gán cho TX/GK/CK
    status          score_status_enum NOT NULL DEFAULT 'DRAFT',
    note            TEXT,
    entered_by      UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    approved_by     UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (student_id, subject_id, semester_id, score_category, column_index)
);

-- ============================================================
-- ĐÁNH GIÁ HỌC TẬP THEO MÔN (GV bộ môn nhập)
--   Môn SCORED: comment = nhận xét học tập của HS.
--   Môn REMARK: result = Đạt/Chưa đạt (thay cho điểm số, không tính ĐTB).
-- ============================================================

CREATE TABLE subject_evaluations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id      UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    class_id        UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    semester_id     UUID NOT NULL REFERENCES semesters(id) ON DELETE CASCADE,
    result          pass_fail_enum,                    -- cho môn REMARK
    comment         TEXT,                              -- đánh giá học tập (môn SCORED)
    evaluated_by    UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (student_id, subject_id, semester_id)
);

-- ============================================================
-- PHIẾU TỔNG KẾT HỌC KỲ (GV chủ nhiệm nhập): hạnh kiểm + đánh giá chung
-- ============================================================

CREATE TABLE student_term_reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    class_id        UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    semester_id     UUID NOT NULL REFERENCES semesters(id) ON DELETE CASCADE,
    conduct         conduct_enum,                      -- hạnh kiểm
    general_comment TEXT,                              -- đánh giá chung của chủ nhiệm
    evaluated_by    UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (student_id, class_id, semester_id)
);

-- ============================================================
-- AUDIT LOG (Lịch sử thay đổi)
-- ============================================================

CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name      VARCHAR(100) NOT NULL,
    record_id       UUID NOT NULL,
    action          VARCHAR(10) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    old_values      JSONB,
    new_values      JSONB,
    ip_address      INET,
    user_agent      TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- AI CHAT SESSIONS (Lịch sử hội thoại + nhật ký Text-to-SQL)
-- ============================================================

CREATE TABLE ai_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(500),
    context_filter  JSONB NOT NULL DEFAULT '{}',        -- {"grade_id":..., "subject_id":..., "semester_id":...}
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE ai_messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID NOT NULL REFERENCES ai_sessions(id) ON DELETE CASCADE,
    role            ai_session_role_enum NOT NULL,
    content         TEXT NOT NULL,
    -- Nhật ký an ninh Text-to-SQL (PRD §6.6 / §8) — bắt buộc cho audit guardrail
    generated_sql   TEXT,                               -- câu SQL do AI sinh (nếu có)
    guardrail_status guardrail_status_enum,             -- kết quả qua 3 lớp rào chắn
    token_count     INTEGER,
    sources         JSONB,                              -- [{exam_paper_id, score}] (dùng khi có RAG)
    model_used      VARCHAR(100),                       -- "gpt-4o-mini", "claude-3-5-sonnet"
    latency_ms      INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- SCHEDULED REPORTS (Báo cáo định kỳ)
-- ============================================================

CREATE TABLE report_schedules (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_by      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    report_type     VARCHAR(50) NOT NULL
                        CHECK (report_type IN ('school_overview','grade','subject','class','at_risk')),
    filter_params   JSONB NOT NULL DEFAULT '{}',
    cron_expr       VARCHAR(100) NOT NULL,              -- "0 8 * * 1" = 8h sáng thứ Hai
    recipients      TEXT[] NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at     TIMESTAMPTZ,
    next_run_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================

-- Users
CREATE INDEX idx_users_school     ON users(school_id);
CREATE INDEX idx_users_role       ON users(role);
CREATE INDEX idx_users_email      ON users(email);

-- Classes & Grades
CREATE INDEX idx_classes_grade    ON classes(grade_id);
CREATE INDEX idx_classes_year     ON classes(academic_year_id);

-- Teacher Assignments
CREATE INDEX idx_ta_user          ON teacher_assignments(user_id);
CREATE INDEX idx_ta_class         ON teacher_assignments(class_id);
CREATE INDEX idx_ta_grade         ON teacher_assignments(grade_id);
CREATE INDEX idx_ta_subject       ON teacher_assignments(subject_id);
CREATE INDEX idx_ta_year          ON teacher_assignments(academic_year_id);

-- Students / Enrollments
CREATE INDEX idx_students_name    ON students USING gin (full_name gin_trgm_ops);  -- tìm tên gần đúng
CREATE INDEX idx_enroll_student   ON enrollments(student_id);
CREATE INDEX idx_enroll_class     ON enrollments(class_id);
CREATE INDEX idx_enroll_year      ON enrollments(academic_year_id);

-- Scores (query chính của analytics)
CREATE INDEX idx_scores_student   ON scores(student_id);
CREATE INDEX idx_scores_subject   ON scores(subject_id);
CREATE INDEX idx_scores_semester  ON scores(semester_id);
CREATE INDEX idx_scores_class     ON scores(class_id);
CREATE INDEX idx_scores_category  ON scores(score_category);
CREATE INDEX idx_scores_status    ON scores(status);
CREATE INDEX idx_scores_exam      ON scores(exam_paper_id);
CREATE INDEX idx_scores_compound  ON scores(subject_id, semester_id, score_category, column_index);

-- Đánh giá học tập theo môn / Phiếu tổng kết học kỳ
CREATE INDEX idx_subjeval_class_sem   ON subject_evaluations(class_id, semester_id);
CREATE INDEX idx_subjeval_subject     ON subject_evaluations(subject_id);
CREATE INDEX idx_termreport_class_sem ON student_term_reports(class_id, semester_id);

-- Exam Papers
CREATE INDEX idx_exam_subject     ON exam_papers(subject_id);
CREATE INDEX idx_exam_semester    ON exam_papers(semester_id);
CREATE INDEX idx_exam_grade       ON exam_papers(grade_id);
CREATE INDEX idx_exam_type        ON exam_papers(score_type);

-- Curriculum
CREATE INDEX idx_curri_subject    ON curriculum_units(subject_id, grade_number);
CREATE INDEX idx_curri_parent     ON curriculum_units(parent_id);
CREATE INDEX idx_examcomp_unit    ON exam_competencies(unit_id);

-- Audit Logs
CREATE INDEX idx_audit_table      ON audit_logs(table_name, record_id);
CREATE INDEX idx_audit_time       ON audit_logs(changed_at DESC);
CREATE INDEX idx_audit_user       ON audit_logs(changed_by);

-- AI Sessions
CREATE INDEX idx_session_user     ON ai_sessions(user_id);
CREATE INDEX idx_message_session  ON ai_messages(session_id);

-- ============================================================
-- TRIGGER: updated_at auto-update
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated       BEFORE UPDATE ON users       FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_schools_updated     BEFORE UPDATE ON schools     FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_students_updated    BEFORE UPDATE ON students    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_scores_updated      BEFORE UPDATE ON scores      FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_exam_papers_updated BEFORE UPDATE ON exam_papers FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_ai_sessions_updated BEFORE UPDATE ON ai_sessions FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- TRIGGER: Auto audit log cho bảng scores
-- App layer phải đặt: SET LOCAL app.current_user_id = '<uuid>'; trong transaction.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_scores_change()
RETURNS TRIGGER AS $$
DECLARE
    v_user UUID := NULLIF(current_setting('app.current_user_id', true), '')::uuid;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_logs(table_name, record_id, action, changed_by, old_values, new_values)
        VALUES ('scores', OLD.id, 'UPDATE', v_user, to_jsonb(OLD), to_jsonb(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_logs(table_name, record_id, action, changed_by, old_values)
        VALUES ('scores', OLD.id, 'DELETE', v_user, to_jsonb(OLD));
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_scores
    AFTER UPDATE OR DELETE ON scores
    FOR EACH ROW EXECUTE FUNCTION audit_scores_change();

-- ============================================================
-- FUNCTION: ĐTB môn học kỳ (theo private_docs/detail_table_score.md)
--   ĐTBmhk = Σ(hệ_số × điểm) / Σ(hệ_số) trên các đầu điểm HIỆN CÓ.
--   Hệ số: ORAL/REGULAR = 1, MIDTERM = 2, FINAL = 3. Trả NULL nếu chưa có điểm.
--   ĐTB cả năm tính ở tầng ứng dụng: (ĐTB HK1 + 2·ĐTB HK2) / 3.
-- ============================================================

CREATE OR REPLACE FUNCTION calc_subject_average(
    p_student_id UUID,
    p_subject_id UUID,
    p_semester_id UUID
)
RETURNS NUMERIC(4,2) AS $$
DECLARE
    v_num NUMERIC := 0;
    v_den INT     := 0;
BEGIN
    SELECT
        COALESCE(SUM(CASE score_category
            WHEN 'ORAL' THEN value WHEN 'REGULAR' THEN value
            WHEN 'MIDTERM' THEN 2*value WHEN 'FINAL' THEN 3*value END), 0),
        COALESCE(SUM(CASE score_category
            WHEN 'ORAL' THEN 1 WHEN 'REGULAR' THEN 1
            WHEN 'MIDTERM' THEN 2 WHEN 'FINAL' THEN 3 END), 0)
      INTO v_num, v_den
      FROM scores
     WHERE student_id = p_student_id AND subject_id = p_subject_id
       AND semester_id = p_semester_id AND status = 'APPROVED';

    IF v_den = 0 THEN RETURN NULL; END IF;
    RETURN ROUND(v_num / v_den, 2);
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- MEASUREMENT LAYER — Đánh giá năng lực điều chỉnh theo độ khó
-- Cohort so sánh = (môn × học kỳ × loại điểm × khối).
-- Chạy được ngay với dữ liệu điểm hiện có, không cần file đề.
-- ============================================================

-- Độ khó THỰC NGHIỆM (suy ra từ phân phối điểm giữa kỳ + cuối kỳ)
CREATE MATERIALIZED VIEW mv_exam_difficulty AS
SELECT s.subject_id,
       s.semester_id,
       s.score_category,
       c.grade_id,
       COUNT(*)                                       AS n,
       ROUND(AVG(s.value), 2)                         AS mean_score,
       ROUND(COALESCE(STDDEV_SAMP(s.value), 0), 2)    AS stddev_score,
       ROUND(AVG((s.value < 5.0)::int)::numeric, 4)   AS pct_below_5,
       ROUND(AVG(s.value) / 10.0, 4)                  AS facility_index  -- cao = đề dễ; độ khó = 1 - facility
FROM scores s
JOIN classes c ON c.id = s.class_id
WHERE s.status = 'APPROVED' AND s.score_category IN ('MIDTERM', 'FINAL')
GROUP BY s.subject_id, s.semester_id, s.score_category, c.grade_id;

CREATE UNIQUE INDEX idx_mv_diff
    ON mv_exam_difficulty(subject_id, semester_id, score_category, grade_id);
-- Làm mới sau khi nhập/duyệt điểm: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_exam_difficulty;

-- Điểm CHUẨN HÓA theo ngữ cảnh độ khó
CREATE VIEW v_normalized_scores AS
SELECT s.id          AS score_id,
       s.student_id,
       s.subject_id,
       s.semester_id,
       s.class_id,
       c.grade_id,
       s.score_category,
       s.column_index,
       s.value        AS raw_value,
       d.mean_score,
       d.stddev_score,
       d.facility_index,
       -- Vị trí tương đối trong khối (z-score)
       CASE WHEN d.stddev_score > 0
            THEN ROUND((s.value - d.mean_score) / d.stddev_score, 2)
            ELSE 0 END AS z_score,
       -- Điểm điều chỉnh theo ngữ cảnh: neo TB khối = 7.0, mỗi 1 SD = 1.5 điểm
       CASE WHEN d.stddev_score > 0
            THEN GREATEST(0, LEAST(10,
                 ROUND(7.0 + (s.value - d.mean_score) / d.stddev_score * 1.5, 2)))
            ELSE s.value END AS context_adjusted_value
FROM scores s
JOIN classes c ON c.id = s.class_id
JOIN mv_exam_difficulty d
  ON d.subject_id = s.subject_id AND d.semester_id = s.semester_id
 AND d.score_category = s.score_category AND d.grade_id = c.grade_id
WHERE s.status = 'APPROVED' AND s.score_category IN ('MIDTERM', 'FINAL');

-- ============================================================
-- CLASSROOM RECORDINGS (Ghi âm bài giảng và đánh giá AI)
-- ============================================================

CREATE TYPE recording_rank_enum AS ENUM ('EXCELLENT', 'SATISFACTORY', 'NEEDS_IMPROVEMENT');

CREATE TABLE classroom_recordings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    semester_id UUID NOT NULL REFERENCES semesters(id) ON DELETE CASCADE,
    lesson_name VARCHAR(255) NOT NULL,
    period INTEGER NOT NULL,
    date DATE NOT NULL,
    week INTEGER NOT NULL,
    audio_file_url TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    progress INTEGER NOT NULL DEFAULT 0,
    score NUMERIC(3, 1),
    engagement VARCHAR(20),
    rank recording_rank_enum,
    ai_report TEXT,
    transcript JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_recordings_school ON classroom_recordings(school_id);
CREATE INDEX idx_recordings_teacher ON classroom_recordings(teacher_id);
CREATE INDEX idx_recordings_class ON classroom_recordings(class_id);
CREATE INDEX idx_recordings_subject ON classroom_recordings(subject_id);

-- ============================================================
-- SEED: Dữ liệu mặc định
-- ============================================================

INSERT INTO schools (id, name, code, address)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Trường THCS Mẫu',
    'THCS-MAU',
    '123 Đường ABC, Quận 1, TP.HCM'
);
