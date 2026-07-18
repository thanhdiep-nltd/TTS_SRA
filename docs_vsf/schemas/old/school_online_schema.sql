-- ============================================================
-- School Online Database Schema DDL with Table & Column Comments
-- Generated from CSV metadata analysis
-- ============================================================

CREATE SCHEMA IF NOT EXISTS s360;
CREATE SCHEMA IF NOT EXISTS t360;

-- ============================================================
-- SCHEMA: default
-- ============================================================

-- MỤC ĐÍCH: Lưu trữ thông tin phân cấp (cây danh mục) của các mục trong loại sổ điểm MOET.
-- Staging School Online Exam Ministry of Education and Training Path
CREATE TABLE default.stg_so_exam_moet_path (
    gradebook_type_item_id bigint,          -- ID danh mục cột điểm trong sổ điểm MOET
    parent_id bigint,                       -- ID phần tử cha (Phục vụ phân cấp)
    gradebook_type_items_fullname varchar,  -- Tên đầy đủ mục/cột điểm trong sổ điểm MOET
    level integer,                          -- Cấp độ phân cấp (Ví dụ: 1, 2, 3)
    path varchar,                           -- Đường dẫn phân cấp đầy đủ (Dạng text)
    id_path varchar                         -- Đường dẫn phân cấp ID đầy đủ
);

-- MỤC ĐÍCH: Lưu cấu trúc phân cấp chương trình học tập (Môn học -> Chủ đề kiến thức/Strand).
-- Staging School Online Strand Path
CREATE TABLE default.stg_so_strand_path (
    strand_id bigint,
    parent_id integer,      -- ID phần tử cha (Phục vụ phân cấp)
    strand_name varchar,
    level integer,          -- Cấp độ phân cấp (Ví dụ: 1, 2, 3)
    path varchar,           -- Đường dẫn phân cấp đầy đủ (Dạng text)
    id_path varchar,        -- Đường dẫn phân cấp ID đầy đủ
    subject_id integer,     -- ID môn học
    subject_name varchar    -- Tên môn học
);

-- MỤC ĐÍCH: Bảng staging lưu giữ thông tin sơ bộ của học sinh phục vụ đối chiếu dữ liệu.
-- Staging School Online Students
CREATE TABLE default.stg_so_students (
    id decimal(20,0),   -- ID định danh duy nhất (Khóa chính)
    code varchar        -- Mã định danh danh mục
);

-- ============================================================
-- SCHEMA: s360
-- ============================================================

-- MỤC ĐÍCH: Danh mục các hành vi rèn luyện (tiêu chí cộng/trừ điểm) của học sinh.
-- Student 360 - Dimension Behavior
CREATE TABLE s360.dim_behavior (
    id bigint,                          -- ID định danh duy nhất (Khóa chính)
    code varchar,                       -- Mã định danh danh mục
    name varchar,                       -- Tên gọi danh mục
    group_code varchar,
    group_name varchar,
    point double,                       -- Điểm số thiết lập
    point_min integer,                  -- Điểm tối thiểu
    point_max integer,                  -- Điểm tối đa
    is_duplicate_behavior integer,      -- Cờ trùng lặp hành vi
    count_duplicate_behavior integer,   -- Số lần lặp hành vi
    scope_duplicate_behavior integer,   -- Phạm vi lặp hành vi
    point_duplicate_behavior double,    -- Điểm phạt/thưởng khi lặp hành vi
    is_behavior_solve integer,          -- Cờ hành vi đã được giải quyết
    is_apply_student integer,           -- Cờ áp dụng cho học sinh
    is_apply_teacher integer,           -- Cờ áp dụng cho giáo viên
    is_apply_homeroom_class integer,    -- Cờ áp dụng cho lớp chủ nhiệm
    convert_behavior_id integer,        -- ID quy đổi hành vi
    created_at varchar,                 -- Thời gian tạo bản ghi
    updated_at varchar                  -- Thời gian cập nhật bản ghi
);

-- MỤC ĐÍCH: Danh mục khóa học / lớp học phần của trường học.
-- Student 360 - Dimension Course
CREATE TABLE s360.dim_course (
    id bigint,                          -- ID định danh duy nhất (Khóa chính)
    so_school_id integer,               -- ID trường học trên hệ thống School Online
    school_year_id integer,             -- ID năm học
    grade_id integer,                   -- ID khối lớp
    subject_id integer,                 -- ID môn học
    homeroom_class_id integer,          -- ID lớp chủ nhiệm
    code varchar,                       -- Mã định danh danh mục
    name varchar,                       -- Tên gọi danh mục
    type varchar,                       -- Loại phân loại
    max_student integer,                -- Sĩ số tối đa của lớp học phần
    start_date date,                    -- Ngày bắt đầu hiệu lực
    end_date date,                      -- Ngày kết thúc hiệu lực
    description varchar,
    status varchar,                     -- Trạng thái bản ghi
    is_online_training integer,         -- Cờ lớp học trực tuyến (LMS)
    is_locked integer,                  -- Cờ khóa dữ liệu (1: Đã khóa không cho sửa, 0: Cho sửa)
    is_extracurricular_activity integer,
    extracurricular_activity_id integer,-- ID hoạt động ngoại khóa liên kết
    el_course_id bigint,                -- ID khóa học tương ứng trên hệ thống LMS
    created_at varchar,                 -- Thời gian tạo bản ghi
    updated_at varchar                  -- Thời gian cập nhật bản ghi
);

-- MỤC ĐÍCH: Danh mục các kỳ thi và đầu điểm (Regular, Midterm, Final).
-- Student 360 - Dimension Exam
CREATE TABLE s360.dim_exam (
    id bigint,                      -- ID định danh duy nhất (Khóa chính)
    so_exam_id bigint,              -- ID đầu điểm kỳ thi trên hệ thống School Online
    school_year_id integer,         -- ID năm học
    subject_id integer,             -- ID môn học
    grade_id integer,               -- ID khối lớp
    grade_code varchar,             -- Mã khối lớp
    grade_name varchar,             -- Tên khối lớp
    exam_code varchar,
    exam_name varchar,
    so_parent_exam_id bigint,       -- ID kỳ thi cha liên kết
    report_type_id integer,         -- ID cấu hình loại báo cáo điểm số
    report_type_code varchar,       -- Mã loại báo cáo điểm số
    report_type_name varchar,       -- Tên loại báo cáo điểm số
    report_type_description varchar,-- Mô tả loại báo cáo điểm số
    is_moet integer,                -- Cờ kỳ thi chấm theo quy chế Bộ GD (1: Phải)
    is_upgrade integer,             -- Cờ kỳ thi nâng điểm
    is_attainment integer,          -- Cờ kỳ thi xét hoàn thành chương trình học
    coefficient decimal(10,1),      -- Hệ số tính điểm môn học (Ví dụ: 1.0, 2.0)
    moet_semester_index integer,    -- Học kỳ theo chuẩn MOET (1: HK1, 2: HK2)
    max_grade decimal(10,1),        -- Điểm số tối đa cho phép của đầu điểm
    is_periodic_exam integer,       -- Cờ kỳ thi định kỳ chính thức (Giữa kỳ, Cuối kỳ)
    convert_to_10 integer,          -- Cờ quy đổi thang điểm về thang điểm 10 (1: Có)
    is_display_grade_book integer,  -- Cờ hiển thị đầu điểm lên sổ điểm học bạ
    created_at varchar,             -- Thời gian tạo bản ghi
    updated_at varchar,             -- Thời gian cập nhật bản ghi
    is_deleted integer              -- Cờ xóa logic (1: Đã xóa, 0: Chưa)
);

-- MỤC ĐÍCH: Danh mục chi tiết các đầu điểm chuẩn hóa theo quy định của Bộ Giáo dục (MOET).
-- Student 360 - Dimension Exam Ministry of Education and Training
CREATE TABLE s360.dim_exam_moet (
    gradebook_type_item_id bigint,          -- ID danh mục cột điểm trong sổ điểm MOET
    tenant_id integer,                      -- ID đơn vị/tổ chức (Tenant ID)
    gradebook_type_id integer,              -- ID loại sổ điểm MOET
    gradebook_types_code varchar,           -- Mã loại sổ điểm MOET
    gradebook_types_fullname varchar,       -- Tên đầy đủ loại sổ điểm MOET
    gradebook_types_description varchar,    -- Mô tả loại sổ điểm MOET
    gradebook_type_items_code varchar,      -- Mã mục/cột điểm trong sổ điểm MOET
    gradebook_type_items_fullname varchar,  -- Tên đầy đủ mục/cột điểm trong sổ điểm MOET
    parent_id bigint,                       -- ID phần tử cha (Phục vụ phân cấp)
    moet_semester_index integer,            -- Học kỳ theo chuẩn MOET (1: HK1, 2: HK2)
    semester_stages integer,                -- Giai đoạn học kỳ (Ví dụ: Giữa kỳ, Cuối kỳ)
    process_type_default integer,
    coefficient decimal(10,1),              -- Hệ số tính điểm môn học (Ví dụ: 1.0, 2.0)
    max_grade decimal(10,1),                -- Điểm số tối đa cho phép của đầu điểm
    round_type integer,                     -- Cách thức làm tròn điểm số
    index_order integer,                    -- Thứ tự sắp xếp hiển thị
    is_allow_input integer,                 -- Cờ cho phép nhập điểm vào hệ thống (1: Cho phép)
    is_allow_mapping integer,               -- Cờ cho phép ánh xạ điểm số
    is_active integer,                      -- Cờ trạng thái hoạt động (1: Kích hoạt, 0: Khóa)
    is_category integer,                    -- Cờ phân loại danh mục (1: Là danh mục cha)
    is_deleted integer,                     -- Cờ xóa logic (1: Đã xóa, 0: Chưa)
    created_by bigint,                      -- ID người tạo bản ghi
    updated_by bigint,                      -- ID người cập nhật bản ghi
    created_at varchar,                     -- Thời gian tạo bản ghi
    updated_at varchar,                     -- Thời gian cập nhật bản ghi
    gradebook_type_items_path varchar,      -- Đường dẫn danh mục mục điểm
    gradebook_type_items_id_path varchar,   -- Đường dẫn danh mục ID mục điểm
    source_system varchar                   -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Danh mục các hoạt động ngoại khóa của trường.
-- Student 360 - Dimension Extracurricular Activity
CREATE TABLE s360.dim_extracurricular_activity (
    id integer,                                         -- ID định danh duy nhất (Khóa chính)
    so_school_id integer,                               -- ID trường học trên hệ thống School Online
    school_year varchar,                                -- Năm học (Ví dụ: 2025-2026)
    code varchar,                                       -- Mã định danh danh mục
    name varchar,                                       -- Tên gọi danh mục
    category_code varchar,
    category_name varchar,
    category_name_en varchar,
    scope_type integer,                                 -- Phạm vi tổ chức hoạt động
    scope_name varchar,                                 -- Tên phạm vi tổ chức hoạt động
    target_type integer,                                -- Đối tượng học sinh nhắm tới
    target_name varchar,                                -- Tên nhóm đối tượng học sinh nhắm tới
    cost decimal(10,1),                                 -- Chi phí hoạt động
    unit_cost varchar,                                  -- Đơn vị tính phí hoạt động
    start_date date,                                    -- Ngày bắt đầu hiệu lực
    end_date date,                                      -- Ngày kết thúc hiệu lực
    is_allow_register integer,                          -- Cờ mở đăng ký hoạt động (1: Cho phép đăng ký)
    register_open_date timestamp(6) with time zone,     -- Ngày giờ bắt đầu mở cổng đăng ký
    register_close_date timestamp(6) with time zone,    -- Ngày giờ kết thúc cổng đăng ký hoạt động
    number_of_user integer,                             -- Số lượng học sinh tối đa tham gia
    number_of_registers integer,                        -- Số lượng học sinh đăng ký thực tế
    status varchar,                                     -- Trạng thái bản ghi
    is_duplicate_semester2 integer,                     -- Cờ nhân bản hoạt động ngoại khóa sang HK2
    duplicate_semester2_id bigint,                      -- ID hoạt động ngoại khóa được nhân bản ở HK2
    duplicate_semester2_at timestamp(6) with time zone, -- Mốc thời gian nhân bản hoạt động sang HK2
    semester_1 integer,                                 -- Cờ hoạt động chạy ở Học kỳ 1 (1: Có)
    semester_2 integer,                                 -- Cờ hoạt động chạy ở Học kỳ 2 (1: Có)
    semester_all integer,                               -- Cờ hoạt động chạy ở Cả năm học (1: Có)
    code_1 varchar,                                     -- Mã đăng ký hoạt động ở Học kỳ 1
    code_2 varchar,                                     -- Mã đăng ký hoạt động ở Học kỳ 2
    code_all varchar,                                   -- Mã đăng ký hoạt động ở Cả năm
    cost_all integer,                                   -- Học phí hoạt động cả năm
    cost_2 integer,                                     -- Học phí hoạt động học kỳ 2
    cost_1 integer,                                     -- Học phí hoạt động học kỳ 1
    start_date_1 date,                                  -- Ngày bắt đầu hoạt động học kỳ 1
    start_date_2 date,                                  -- Ngày bắt đầu hoạt động học kỳ 2
    start_date_all date,                                -- Ngày bắt đầu hoạt động cả năm
    end_date_1 date,                                    -- Ngày kết thúc hoạt động học kỳ 1
    end_date_2 date,                                    -- Ngày kết thúc hoạt động học kỳ 2
    end_date_all date,                                  -- Ngày kết thúc hoạt động cả năm
    status_semester_1 integer,                          -- Trạng thái hoạt động học kỳ 1
    status_semester_2 integer,                          -- Trạng thái hoạt động học kỳ 2
    status_semester_all integer,                        -- Trạng thái hoạt động cả năm
    number_of_user_1 integer,                           -- Số lượng học sinh tham gia học kỳ 1
    number_of_user_2 integer,                           -- Số lượng học sinh tham gia học kỳ 2
    number_of_user_all integer,                         -- Số lượng học sinh tham gia cả năm
    created_at varchar,                                 -- Thời gian tạo bản ghi
    updated_at varchar,                                 -- Thời gian cập nhật bản ghi
    source_system varchar                               -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Danh mục các lớp chủ nhiệm của trường học.
-- Student 360 - Dimension Homeroom Class
CREATE TABLE s360.dim_homeroom_class (
    id bigint,                  -- ID định danh duy nhất (Khóa chính)
    so_school_id integer,       -- ID trường học trên hệ thống School Online
    school_year_id integer,     -- ID năm học
    grade_id integer,           -- ID khối lớp
    code varchar,               -- Mã định danh danh mục
    fullname varchar,           -- Tên đầy đủ
    homeroom_teacher_id bigint, -- ID giáo viên chủ nhiệm
    teacher_code varchar,       -- Mã số giáo viên
    class_leader_id bigint,     -- ID lớp trưởng (Học sinh)
    parent_leader_id bigint,    -- ID trưởng ban phụ huynh
    is_active integer,          -- Cờ trạng thái hoạt động (1: Kích hoạt, 0: Khóa)
    is_bilingual integer,       -- Cờ lớp học song ngữ
    is_bilingual_prep integer,  -- Cờ lớp học tiền song ngữ
    created_at varchar,         -- Thời gian tạo bản ghi
    updated_at varchar,         -- Thời gian cập nhật bản ghi
    source_system varchar       -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Danh sách liên kết học sinh với lớp chủ nhiệm của từng niên khóa.
-- Student 360 - Dimension Homeroom Class Student
CREATE TABLE s360.dim_homeroom_class_student (
    id bigint,                  -- ID định danh duy nhất (Khóa chính)
    tenant_id integer,          -- ID đơn vị/tổ chức (Tenant ID)
    so_student_id bigint,
    student_code varchar,       -- Mã số học sinh
    student_name varbinary,     -- Họ tên học sinh (Mã hóa bảo mật)
    homeroom_class_id integer,  -- ID lớp chủ nhiệm
    class_code varchar,         -- Mã lớp học
    class_name varchar,         -- Tên lớp học
    so_school_id integer,       -- ID trường học trên hệ thống School Online
    school_year_id integer,     -- ID năm học
    school_name varchar,        -- Tên trường học
    school_code varchar,        -- Mã trường học
    teacher_code varchar,       -- Mã số giáo viên
    campus_name varchar,        -- Tên cơ sở trường học
    grade_id integer,           -- ID khối lớp
    grade_name varchar,         -- Tên khối lớp
    moet_code varchar,
    join_date date,             -- Ngày học sinh gia nhập lớp
    is_graduated integer,       -- Cờ tốt nghiệp niên khóa (1: Đã tốt nghiệp)
    status integer,             -- Trạng thái bản ghi
    special_note varchar,       -- Ghi chú đặc biệt về học sinh
    is_deleted integer,         -- Cờ xóa logic (1: Đã xóa, 0: Chưa)
    is_active integer,          -- Cờ trạng thái hoạt động (1: Kích hoạt, 0: Khóa)
    created_at varchar,         -- Thời gian tạo bản ghi
    updated_at varchar,         -- Thời gian cập nhật bản ghi
    source_system varchar       -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Danh mục năm học học đường.
-- Student 360 - Dimension School Year
CREATE TABLE s360.dim_school_year (
    id integer,                 -- ID định danh duy nhất (Khóa chính)
    code varchar,               -- Mã định danh danh mục
    fullname varchar,           -- Tên đầy đủ
    start_date date,            -- Ngày bắt đầu hiệu lực
    end_date date,              -- Ngày kết thúc hiệu lực
    calculator_type integer,    -- Loại công thức tính điểm
    calculator_name varchar,    -- Tên công thức tính điểm
    is_locked integer,          -- Cờ khóa dữ liệu (1: Đã khóa không cho sửa, 0: Cho sửa)
    is_gradebook_locked integer,-- Cờ khóa sổ học bạ năm học
    is_current integer,         -- Cờ đánh dấu niên khóa/học kỳ hiện tại
    created_at varchar,         -- Thời gian tạo bản ghi
    updated_at varchar,         -- Thời gian cập nhật bản ghi
    source_system varchar       -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Danh mục bài tập / nhiệm vụ học tập được giao cho học sinh.
-- Student 360 - Dimension School Online Assignment
CREATE TABLE s360.dim_so_assignment (
    assignment_id bigint,                   -- ID bài tập được giao
    so_school_id integer,                   -- ID trường học trên hệ thống School Online
    grade_id integer,                       -- ID khối lớp
    grade_code varchar,                     -- Mã khối lớp
    grade_name varchar,                     -- Tên khối lớp
    semester_index integer,                 -- Học kỳ (1: Học kỳ 1, 2: Học kỳ 2)
    subject_id integer,                     -- ID môn học
    course_id bigint,                       -- ID khóa học / lớp học phần
    code varchar,                           -- Mã định danh danh mục
    fullname varchar,                       -- Tên đầy đủ
    course_lesson_id bigint,                -- ID tiết học học phần tương ứng
    gradebook_type_item_id integer,         -- ID danh mục cột điểm trong sổ điểm MOET
    gradebook_type_item_name varchar,       -- Tên mục điểm trong sổ điểm
    report_type_item_id integer,            -- ID loại báo cáo tiến trình môn học
    report_type_item_name varchar,          -- Tên loại báo cáo tiến trình môn học
    el_assignment_id bigint,                -- ID bài tập trên hệ thống LMS tương ứng
    max_grade decimal(10,0),                -- Điểm số tối đa cho phép của đầu điểm
    description varchar,
    due_date date,                          -- Hạn chót nộp bài tập
    locked_at timestamp(6) with time zone,
    is_locked integer,                      -- Cờ khóa dữ liệu (1: Đã khóa không cho sửa, 0: Cho sửa)
    is_mapping_locked integer,              -- Cờ khóa tính năng ánh xạ đầu điểm
    type integer,                           -- Loại phân loại
    is_homework_calendar integer,           -- Cờ đưa bài tập lên lịch làm bài ở nhà
    date_assigned date,                     -- Ngày giao bài tập
    is_deleted integer,                     -- Cờ xóa logic (1: Đã xóa, 0: Chưa)
    source_system varchar                   -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Thông tin đánh giá tổng kết tiến độ học tập của học sinh.
-- Student 360 - Dimension School Online Evaluate Progress
CREATE TABLE s360.dim_so_evaluate_progress (
    id bigint,                              -- ID định danh duy nhất (Khóa chính)
    tenant_id integer,                      -- ID đơn vị/tổ chức (Tenant ID)
    so_school_id integer,                   -- ID trường học trên hệ thống School Online
    school_name varchar,                    -- Tên trường học
    school_code varchar,                    -- Mã trường học
    campus_id integer,                      -- ID cơ sở trường học (Campus ID)
    school_year_id integer,                 -- ID năm học
    grade_id integer,                       -- ID khối lớp
    grade_code varchar,                     -- Mã khối lớp
    grade_name varchar,                     -- Tên khối lớp
    class_code varchar,                     -- Mã lớp học
    class_name varchar,                     -- Tên lớp học
    semester_index integer,                 -- Học kỳ (1: Học kỳ 1, 2: Học kỳ 2)
    semester_stages integer,                -- Giai đoạn học kỳ (Ví dụ: Giữa kỳ, Cuối kỳ)
    homeroom_class_id integer,              -- ID lớp chủ nhiệm
    user_id bigint,                         -- ID người dùng hệ thống
    student_code varchar,                   -- Mã số học sinh
    is_attach_report_moet integer,          -- Cờ đính kèm học bạ MOET
    is_attach_report_cam integer,           -- Cờ đính kèm học bạ Cambridge
    file_attach_report_moet varchar,        -- Đường dẫn file học bạ MOET đính kèm
    file_attach_report_cam varchar,         -- Đường dẫn file học bạ Cambridge đính kèm
    final_behavior_point integer,           -- Điểm rèn luyện tổng kết cả năm
    learning_capacity integer,              -- Học lực cả năm (Giỏi, Khá, Trung bình, Yếu)
    conduct_type integer,
    comment varchar,                        -- Nhận xét, đánh giá của giáo viên
    comment_21 varchar,
    comment_reply varchar,                  -- Ý kiến phản hồi từ phụ huynh
    comment_reply_by bigint,                -- ID phụ huynh phản hồi
    homeroom_teacher_fullname varchar,
    is_bilingual integer,                   -- Cờ lớp học song ngữ
    is_locked integer,                      -- Cờ khóa dữ liệu (1: Đã khóa không cho sửa, 0: Cho sửa)
    is_deleted integer,                     -- Cờ xóa logic (1: Đã xóa, 0: Chưa)
    created_by bigint,                      -- ID người tạo bản ghi
    created_at timestamp(6) with time zone, -- Thời gian tạo bản ghi
    updated_by bigint,                      -- ID người cập nhật bản ghi
    updated_at timestamp(6) with time zone, -- Thời gian cập nhật bản ghi
    source_system varchar                   -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Bảng ánh xạ cấu trúc môn học của từng trường theo khối lớp, lớp chủ nhiệm và năm học.
-- Student 360 - Dimension School Online School Mapping Subject
CREATE TABLE s360.dim_so_school_mapping_subject (
    so_school_id integer,       -- ID trường học trên hệ thống School Online
    school_name varchar,        -- Tên trường học
    subject_id integer,         -- ID môn học
    subject_name varchar,       -- Tên môn học
    school_year_id integer,     -- ID năm học
    grade_id integer,           -- ID khối lớp
    homeroom_class_id bigint    -- ID lớp chủ nhiệm
);

-- MỤC ĐÍCH: Danh mục môn học chính thức của trường.
-- Student 360 - Dimension Subject
CREATE TABLE s360.dim_subject (
    id integer,                 -- ID định danh duy nhất (Khóa chính)
    code varchar,               -- Mã định danh danh mục
    name varchar,               -- Tên gọi danh mục
    name_en varchar,
    education_stages integer,   -- Cấp học tương ứng (Tiểu học, THCS, THPT)
    subject_type varchar,       -- Phân loại môn học (Môn tính điểm / Môn nhận xét)
    is_credit integer,          -- Cờ môn học tính tín chỉ (1: Có tính)
    is_level_esl integer,       -- Cờ môn học phân cấp trình độ tiếng Anh ESL
    is_cambridge_k11 integer,   -- Cờ môn học thuộc hệ Cambridge khối 11
    is_active integer,          -- Cờ trạng thái hoạt động (1: Kích hoạt, 0: Khóa)
    is_sync_lms integer,        -- Cờ đồng bộ dữ liệu sang LMS (1: Có đồng bộ)
    created_at varchar,         -- Thời gian tạo bản ghi
    updated_at varchar,         -- Thời gian cập nhật bản ghi
    source_system varchar       -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Nhật ký chi tiết đơn xin nghỉ học của học sinh.
-- Student 360 - Fact Absent Logs
CREATE TABLE s360.fact_absent_logs (
    id bigint,                              -- ID định danh duy nhất (Khóa chính)
    absent_period_id bigint,                -- ID lượt xin nghỉ tiết học cụ thể
    so_school_id integer,                   -- ID trường học trên hệ thống School Online
    school_year_id integer,                 -- ID năm học
    homeroom_class_id integer,              -- ID lớp chủ nhiệm
    student_code varchar,                   -- Mã số học sinh
    reason varbinary,                       -- Lý do cụ thể (nghỉ học, đi muộn, vắng mặt)
    reason_norm varchar,                    -- Lý do chuẩn hóa
    reason_category varchar,                -- Phân loại nhóm lý do xin nghỉ
    from_date date,                         -- Nghỉ từ ngày
    to_date date,                           -- Nghỉ đến ngày
    is_approved integer,                    -- Cờ phê duyệt (1: Đã duyệt, 0: Chờ duyệt)
    approval_status varchar,                -- Trạng thái phê duyệt
    approved_at timestamp(6) with time zone,-- Thời gian phê duyệt
    is_auto_approved integer,               -- Cờ tự động phê duyệt (1: Tự động duyệt)
    is_full_day integer,                    -- Cờ nghỉ cả ngày (1: Nghỉ cả ngày, 0: Nghỉ theo tiết)
    absent_date date,                       -- Ngày vắng học
    timetable_period_code varchar,          -- Mã tiết học theo thời khóa biểu
    timetable_period_name varchar,          -- Tên tiết học (Ví dụ: Tiết 1, Tiết 2)
    created_at varchar,                     -- Thời gian tạo bản ghi
    updated_at varchar                      -- Thời gian cập nhật bản ghi
);

-- MỤC ĐÍCH: Nhật ký ghi nhận các hành vi rèn luyện của học sinh.
-- Student 360 - Fact Behavior Logs
CREATE TABLE s360.fact_behavior_logs (
    id bigint,                      -- ID định danh duy nhất (Khóa chính)
    so_school_id integer,           -- ID trường học trên hệ thống School Online
    school_year_id integer,         -- ID năm học
    student_code varchar,           -- Mã số học sinh
    behavior_id integer,            -- ID hành vi rèn luyện
    behavior_before_id bigint,
    object_type integer,
    object_id integer,
    behavior_code varchar,          -- Mã hành vi rèn luyện
    behavior_fullname varchar,      -- Tên đầy đủ hành vi rèn luyện
    behavior_fullname_clean varchar,-- Tên sạch hành vi (bỏ ký tự đặc biệt)
    behavior_level varchar,         -- Cấp độ hành vi rèn luyện
    behavior_point varchar,         -- Điểm rèn luyện của hành vi đó
    behavior_comment varchar,       -- Nhận xét cụ thể về hành vi rèn luyện
    comment_date date,              -- Ngày nhận xét
    sanction_code varchar,
    sanction_name varchar,
    created_at varchar,             -- Thời gian tạo bản ghi
    updated_at varchar,             -- Thời gian cập nhật bản ghi
    source_system varchar           -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Nhật ký điểm danh chuyên cần theo từng tiết học của các lớp học phần.
-- Student 360 - Fact Course Attendances
CREATE TABLE s360.fact_course_attendences (
    id bigint,                      -- ID định danh duy nhất (Khóa chính)
    so_school_id integer,           -- ID trường học trên hệ thống School Online
    school_year_id integer,         -- ID năm học
    course_id integer,              -- ID khóa học / lớp học phần
    timetable_period_code varchar,  -- Mã tiết học theo thời khóa biểu
    timetable_period_name varchar,  -- Tên tiết học (Ví dụ: Tiết 1, Tiết 2)
    _date date,                     -- Ngày ghi nhận sự kiện
    student_code varchar,           -- Mã số học sinh
    status integer,                 -- Trạng thái bản ghi
    status_name varchar,            -- Tên trạng thái
    comment varchar,                -- Nhận xét, đánh giá của giáo viên
    is_push_to_app integer,         -- Cờ đồng bộ dữ liệu lên ứng dụng phụ huynh (1: Đã đồng bộ)
    is_push_notification integer,   -- Cờ gửi thông báo đẩy tới điện thoại phụ huynh (1: Đã gửi)
    is_locked integer,              -- Cờ khóa dữ liệu (1: Đã khóa không cho sửa, 0: Cho sửa)
    created_at varchar,             -- Thời gian tạo bản ghi
    updated_at varchar,             -- Thời gian cập nhật bản ghi
    source_system varchar           -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Nhật ký ghi nhận học sinh đăng ký học phần (Course).
-- Student 360 - Fact Course Enrolls
CREATE TABLE s360.fact_course_enrolls (
    id bigint,                                  -- ID định danh duy nhất (Khóa chính)
    student_code varchar,                       -- Mã số học sinh
    course_id bigint,                           -- ID khóa học / lớp học phần
    is_moved_out integer,                       -- Cờ học sinh đã chuyển lớp học phần (1: Đã chuyển)
    moved_out_at timestamp(6) with time zone,   -- Mốc thời gian học sinh chuyển khỏi khóa học
    is_student integer,                         -- Cờ xác định là vai trò học sinh (1: Học sinh)
    is_teaching_assistant integer,              -- Cờ xác định là vai trò trợ giảng lớp học (1: Trợ giảng)
    created_at varchar,                         -- Thời gian tạo bản ghi
    updated_at varchar                          -- Thời gian cập nhật bản ghi
);

-- MỤC ĐÍCH: Dữ liệu giao dịch đóng tiền hoạt động ngoại khóa.
-- Student 360 - Fact Extracurricular Activity Payments
CREATE TABLE s360.fact_extracurricular_activity_payments (
    id bigint,                      -- ID định danh duy nhất (Khóa chính)
    so_school_id integer,           -- ID trường học trên hệ thống School Online
    school_year_id integer,         -- ID năm học
    homeroom_class varchar,         -- Tên lớp chủ nhiệm
    student_id integer,             -- ID học sinh
    student_code varchar,           -- Mã số học sinh
    vinclub_membership_rank varchar,-- Hạng thành viên Vinclub của phụ huynh
    vinclub_discount_percent double,-- Phần trăm giảm giá theo Vinclub
    original_price integer,         -- Học phí gốc
    discount_price integer,         -- Số tiền được giảm giá
    final_price integer,            -- Học phí thực tế phải đóng sau giảm giá
    price integer,                  -- Giá trị đóng phí
    status integer,                 -- Trạng thái bản ghi
    created_at varchar,             -- Thời gian tạo bản ghi
    updated_at varchar,             -- Thời gian cập nhật bản ghi
    source_system varchar           -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Danh sách đăng ký tham gia ngoại khóa của học sinh.
-- Student 360 - Fact Extracurricular Activity Registers
CREATE TABLE s360.fact_extracurricular_activity_registers (
    id bigint,                                      -- ID định danh duy nhất (Khóa chính)
    so_school_id integer,                           -- ID trường học trên hệ thống School Online
    school_year_id integer,                         -- ID năm học
    student_id bigint,                              -- ID học sinh
    student_code varchar,                           -- Mã số học sinh
    extracurricular_activity_id bigint,             -- ID hoạt động ngoại khóa liên kết
    object_type integer,
    object_id varchar,
    status integer,                                 -- Trạng thái bản ghi
    status_description varchar,                     -- Mô tả trạng thái
    cost integer,                                   -- Chi phí hoạt động
    paid_price integer,                             -- Số tiền thực tế học sinh đã đóng
    note varchar,                                   -- Ghi chú thêm
    is_upgrade_to_register integer,
    is_refund integer,                              -- Cờ hoàn trả học phí (1: Đã hoàn tiền)
    change_status_at timestamp(6) with time zone,   -- Thời gian thay đổi trạng thái đăng ký
    created_at varchar,                             -- Thời gian tạo bản ghi
    updated_at varchar,                             -- Thời gian cập nhật bản ghi
    source_system varchar                           -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Bảng điểm tổng hợp (Sổ điểm học bạ) của học sinh theo từng môn học và kỳ học.
-- Student 360 - Fact Gradebooks
CREATE TABLE s360.fact_gradebooks (
    id bigint,                      -- ID định danh duy nhất (Khóa chính)
    so_school_id integer,           -- ID trường học trên hệ thống School Online
    school_year_id integer,         -- ID năm học
    semester_index integer,         -- Học kỳ (1: Học kỳ 1, 2: Học kỳ 2)
    semester_stages integer,        -- Giai đoạn học kỳ (Ví dụ: Giữa kỳ, Cuối kỳ)
    student_code varchar,           -- Mã số học sinh
    homeroom_class varchar,         -- Tên lớp chủ nhiệm
    homeroom_teacher_id bigint,     -- ID giáo viên chủ nhiệm
    subject_id integer,             -- ID môn học
    course_id bigint,               -- ID khóa học / lớp học phần
    homeroom_class_id integer,      -- ID lớp chủ nhiệm
    so_exam_id bigint,              -- ID đầu điểm kỳ thi trên hệ thống School Online
    final_grade decimal(10,2),      -- Điểm tổng kết / Điểm số cuối cùng
    final_grade_convert varchar,    -- Điểm quy đổi (Thang điểm chữ hoặc thang khác)
    max_grade decimal(10,1),        -- Điểm số tối đa cho phép của đầu điểm
    is_grade_letter integer,        -- Cờ điểm chữ (1: Tính điểm chữ đạt/chưa đạt, 0: Cho điểm số)
    is_locked integer,              -- Cờ khóa dữ liệu (1: Đã khóa không cho sửa, 0: Cho sửa)
    is_move_in_grade integer,       -- Cờ điểm chuyển trường đến của học sinh
    is_semester_locked integer,     -- Cờ khóa điểm học kỳ (1: Đã khóa)
    is_input_grade integer,         -- Cờ cho phép nhập điểm vào hệ thống (1: Cho phép)
    is_input_after_summer integer,  -- Cờ cho phép nhập điểm thi lại sau hè (1: Cho phép)
    grade_id integer,               -- ID khối lớp
    created_at varchar,             -- Thời gian tạo bản ghi
    updated_at varchar,             -- Thời gian cập nhật bản ghi
    source_system varchar           -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Sổ điểm chuẩn hóa theo quy định của Bộ Giáo dục (MOET) dành cho học sinh.
-- Student 360 - Fact Gradebooks Ministry of Education and Training
CREATE TABLE s360.fact_gradebooks_moet (
    id bigint,                      -- ID định danh duy nhất (Khóa chính)
    tenant_id integer,              -- ID đơn vị/tổ chức (Tenant ID)
    so_school_id integer,           -- ID trường học trên hệ thống School Online
    school_code varchar,            -- Mã trường học
    school_name varchar,            -- Tên trường học
    campus_id integer,              -- ID cơ sở trường học (Campus ID)
    grade_id integer,               -- ID khối lớp
    grade_code varchar,             -- Mã khối lớp
    grade_name varchar,             -- Tên khối lớp
    subject_id integer,             -- ID môn học
    school_year_id integer,         -- ID năm học
    semester_index integer,         -- Học kỳ (1: Học kỳ 1, 2: Học kỳ 2)
    semester_stages integer,        -- Giai đoạn học kỳ (Ví dụ: Giữa kỳ, Cuối kỳ)
    so_user_id bigint,              -- ID người dùng trên hệ thống School Online
    student_code varchar,           -- Mã số học sinh
    course_id bigint,               -- ID khóa học / lớp học phần
    homeroom_class_id integer,      -- ID lớp chủ nhiệm
    gradebook_type_item_id bigint,  -- ID danh mục cột điểm trong sổ điểm MOET
    final_grade decimal(10,1),      -- Điểm tổng kết / Điểm số cuối cùng
    comment varchar,                -- Nhận xét, đánh giá của giáo viên
    is_semester_locked integer,     -- Cờ khóa điểm học kỳ (1: Đã khóa)
    is_grade_letter integer,        -- Cờ điểm chữ (1: Tính điểm chữ đạt/chưa đạt, 0: Cho điểm số)
    is_move_in_grade integer,       -- Cờ điểm chuyển trường đến của học sinh
    is_input_grade integer,         -- Cờ cho phép nhập điểm vào hệ thống (1: Cho phép)
    is_input_after_summer integer,  -- Cờ cho phép nhập điểm thi lại sau hè (1: Cho phép)
    is_locked integer,              -- Cờ khóa dữ liệu (1: Đã khóa không cho sửa, 0: Cho sửa)
    is_deleted integer,             -- Cờ xóa logic (1: Đã xóa, 0: Chưa)
    created_by bigint,              -- ID người tạo bản ghi
    updated_by bigint,              -- ID người cập nhật bản ghi
    created_at varchar,             -- Thời gian tạo bản ghi
    updated_at varchar,             -- Thời gian cập nhật bản ghi
    source_system varchar           -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Học bạ tổng kết kết quả học tập toàn diện của học sinh theo từng năm học.
-- Student 360 - Fact Overall Academic Records
CREATE TABLE s360.fact_overall_academic_records (
    id bigint,                                                  -- ID định danh duy nhất (Khóa chính)
    so_school_id integer,                                       -- ID trường học trên hệ thống School Online
    school_year_id bigint,                                      -- ID năm học
    grade_id bigint,                                            -- ID khối lớp
    homeroom_class_id bigint,                                   -- ID lớp chủ nhiệm
    student_id bigint,                                          -- ID học sinh
    student_code varchar,                                       -- Mã số học sinh
    join_date date,                                             -- Ngày học sinh gia nhập lớp
    final_grade decimal(10,1),                                  -- Điểm tổng kết / Điểm số cuối cùng
    s1_final_grade decimal(10,1),
    s2_final_grade decimal(10,1),
    final_grade_after_summer decimal(10,1),
    conduct varchar,                                            -- Hạnh kiểm cả năm (Tốt, Khá, TB, Yếu)
    s1_conduct varchar,                                         -- Hạnh kiểm học kỳ 1
    s2_conduct varchar,                                         -- Hạnh kiểm học kỳ 2
    conduct_after_summer varchar,                               -- Hạnh kiểm sau kỳ hè (thi lại/rèn luyện lại)
    learning_capacity varchar,                                  -- Học lực cả năm (Giỏi, Khá, Trung bình, Yếu)
    s1_learning_capacity varchar,                               -- Học lực học kỳ 1
    s2_learning_capacity varchar,                               -- Học lực học kỳ 2
    learning_capacity_after_summer varchar,                     -- Học lực sau kỳ thi lại hè
    final_behavior_point integer,                               -- Điểm rèn luyện tổng kết cả năm
    s1_final_behavior_point integer,                            -- Điểm rèn luyện tổng kết học kỳ 1
    s2_final_behavior_point integer,                            -- Điểm rèn luyện tổng kết học kỳ 2
    day_of_absent integer,                                      -- Số ngày nghỉ học cả năm
    s1_day_of_absent integer,                                   -- Số ngày nghỉ học học kỳ 1
    s2_day_of_absent integer,                                   -- Số ngày nghỉ học học kỳ 2
    homeroom_teacher_comment varchar,                           -- Nhận xét của GVCN cả năm
    s1_homeroom_teacher_comment varchar,                        -- Nhận xét của GVCN học kỳ 1
    s2_homeroom_teacher_comment varchar,                        -- Nhận xét của GVCN học kỳ 2
    comment_after_summer varchar,                               -- Nhận xét bổ sung sau hè
    principal_comment varchar,                                  -- Nhận xét, bút phê của Hiệu trưởng
    change_final_conduct_s1 integer,                            -- Cờ thay đổi hạnh kiểm HK1 (1: Có thay đổi)
    change_final_conduct_s1_by bigint,                          -- ID người duyệt thay đổi hạnh kiểm HK1
    change_final_conduct_s1_at timestamp(6) with time zone,     -- Thời gian duyệt thay đổi hạnh kiểm HK1
    change_final_conduct_s1_reason varchar,                     -- Lý do thay đổi hạnh kiểm HK1
    change_final_conduct_s2 integer,                            -- Cờ thay đổi hạnh kiểm HK2 (1: Có thay đổi)
    change_final_conduct_s2_by bigint,                          -- ID người duyệt thay đổi hạnh kiểm HK2
    change_final_conduct_s2_at timestamp(6) with time zone,     -- Thời gian duyệt thay đổi hạnh kiểm HK2
    change_final_conduct_s2_reason varchar,                     -- Lý do thay đổi hạnh kiểm HK2
    change_final_conduct integer,                               -- Cờ thay đổi hạnh kiểm cả năm (1: Có thay đổi)
    change_final_conduct_by bigint,                             -- ID người duyệt thay đổi hạnh kiểm cả năm
    change_final_conduct_at timestamp(6) with time zone,        -- Thời gian duyệt thay đổi hạnh kiểm cả năm
    change_final_conduct_reason varchar,                        -- Lý do thay đổi hạnh kiểm cả năm
    homeroom_teacher_fullname varchar,
    is_homeroom_teacher_approved integer,                       -- Cờ GVCN đã duyệt học bạ (1: Đã duyệt)
    homeroom_teacher_approved_at timestamp(6) with time zone,   -- Thời gian GVCN duyệt học bạ
    is_principal_approved integer,                              -- Cờ Hiệu trưởng đã duyệt học bạ (1: Đã duyệt)
    principal_approved_at timestamp(6) with time zone,          -- Thời gian Hiệu trưởng duyệt học bạ
    vocational_certificate varchar,                             -- Thông tin chứng chỉ nghề của học sinh
    vocational_certificate_type varchar,                        -- Loại chứng chỉ nghề
    reward varchar,                                             -- Khen thưởng học tập
    special_reward varchar,                                     -- Khen thưởng đặc biệt
    status integer,                                             -- Trạng thái bản ghi
    is_locked integer,                                          -- Cờ khóa dữ liệu (1: Đã khóa không cho sửa, 0: Cho sửa)
    is_s1_locked integer,
    is_s2_locked integer,
    is_after_summer integer,                                    -- Cờ kiểm tra lại sau hè (1: Đúng)
    is_passed_no_conditional integer,                           -- Cờ học sinh lên lớp thẳng không điều kiện (1: Đúng)
    is_graduated integer,                                       -- Cờ tốt nghiệp niên khóa (1: Đã tốt nghiệp)
    title varchar,                                              -- Danh hiệu học tập cả năm (Ví dụ: Học sinh giỏi)
    s1_title varchar,                                           -- Danh hiệu học tập học kỳ 1
    s2_title varchar,                                           -- Danh hiệu học tập học kỳ 2
    created_at varchar,                                         -- Thời gian tạo bản ghi
    updated_at varchar                                          -- Thời gian cập nhật bản ghi
);

-- MỤC ĐÍCH: Bảng tổng hợp thống kê dữ liệu nghỉ học và đi muộn của học sinh theo chu kỳ tuần/tháng/kỳ học.
-- Student 360 - Fact School Online Absent Extract Late
CREATE TABLE s360.fact_so_absent_extract_late (
    student_code varchar,               -- Mã số học sinh
    school_year_id integer,             -- ID năm học
    so_school_id integer,               -- ID trường học trên hệ thống School Online
    homeroom_class_id integer,          -- ID lớp chủ nhiệm
    absent_date date,                   -- Ngày vắng học
    original_reason_category varchar,   -- Phân loại lý do gốc
    reason_norm varchar,                -- Lý do chuẩn hóa
    reason varchar,                     -- Lý do cụ thể (nghỉ học, đi muộn, vắng mặt)
    school_year varchar,                -- Năm học (Ví dụ: 2025-2026)
    school_year_start_date date,        -- Ngày bắt đầu năm học
    school_year_end_date date,          -- Ngày kết thúc năm học
    reason_category varchar,            -- Phân loại nhóm lý do xin nghỉ
    school_code varchar,                -- Mã trường học
    class_code varchar,                 -- Mã lớp học
    class_name varchar,                 -- Tên lớp học
    school_name varchar,                -- Tên trường học
    grade_id integer,                   -- ID khối lớp
    grade_name varchar,                 -- Tên khối lớp
    week_start date,
    month_start date
);

-- MỤC ĐÍCH: Bảng ghi nhận kết quả điểm số bài tập (Assignment) được giáo viên chấm.
-- Student 360 - Fact School Online Assignment Grade
CREATE TABLE s360.fact_so_assignment_grade (
    id bigint,                      -- ID định danh duy nhất (Khóa chính)
    tenant_id bigint,               -- ID đơn vị/tổ chức (Tenant ID)
    school_id bigint,               -- ID trường học
    assignment_id bigint,           -- ID bài tập được giao
    is_sync_from_exam integer,
    user_id bigint,                 -- ID người dùng hệ thống
    student_code varchar,           -- Mã số học sinh
    final_grade decimal(10,1),      -- Điểm tổng kết / Điểm số cuối cùng
    comment varchar,                -- Nhận xét, đánh giá của giáo viên
    is_locked integer,              -- Cờ khóa dữ liệu (1: Đã khóa không cho sửa, 0: Cho sửa)
    is_push_notification integer,   -- Cờ gửi thông báo đẩy tới điện thoại phụ huynh (1: Đã gửi)
    is_deleted integer,             -- Cờ xóa logic (1: Đã xóa, 0: Chưa)
    created_by bigint,              -- ID người tạo bản ghi
    updated_by bigint,              -- ID người cập nhật bản ghi
    created_at varchar,             -- Thời gian tạo bản ghi
    updated_at varchar,             -- Thời gian cập nhật bản ghi
    source_system varchar           -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Bảng thống kê điểm danh chuyên cần của học sinh theo ngày.
-- Student 360 - Fact School Online Class Attendance Statistics
CREATE TABLE s360.fact_so_class_attendance_statistics (
    id bigint,                  -- ID định danh duy nhất (Khóa chính)
    so_user_id bigint,          -- ID người dùng trên hệ thống School Online
    student_code varchar,       -- Mã số học sinh
    date date,
    status integer,             -- Trạng thái bản ghi
    total_lesson integer,
    lesson_attend integer,
    lesson_not_attend integer,
    tenant_id integer,          -- ID đơn vị/tổ chức (Tenant ID)
    so_school_id integer,       -- ID trường học trên hệ thống School Online
    school_year_id integer,     -- ID năm học
    campus_id integer,          -- ID cơ sở trường học (Campus ID)
    grade_id integer,           -- ID khối lớp
    homeroom_class_id integer,  -- ID lớp chủ nhiệm
    created_at varchar,         -- Thời gian tạo bản ghi
    updated_at varchar,         -- Thời gian cập nhật bản ghi
    source_system varchar       -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Bảng thống kê điểm danh môn học theo ngày của học sinh.
-- Student 360 - Fact School Online Daily Attendance
CREATE TABLE s360.fact_so_daily_attendance (
    _date date,                         -- Ngày ghi nhận sự kiện
    week_start date,
    month_start date,
    school_year_id integer,             -- ID năm học
    school_id integer,                  -- ID trường học
    school_year varchar,                -- Năm học (Ví dụ: 2025-2026)
    school_year_start_date date,        -- Ngày bắt đầu năm học
    school_year_end_date date,          -- Ngày kết thúc năm học
    student_code varchar,               -- Mã số học sinh
    course_id integer,                  -- ID khóa học / lớp học phần
    subject_id integer,                 -- ID môn học
    school_code varchar,                -- Mã trường học
    homeroom_class_id integer,          -- ID lớp chủ nhiệm
    class_code varchar,                 -- Mã lớp học
    class_name varchar,                 -- Tên lớp học
    grade_id integer,                   -- ID khối lớp
    grade_name varchar,                 -- Tên khối lớp
    total_periods bigint,               -- Tổng số tiết học môn học trong ngày
    absent_periods bigint,              -- Tổng số tiết học vắng trong ngày
    absent_no_permission bigint,        -- Tổng số tiết vắng không phép
    absent_with_permission bigint,      -- Tổng số tiết vắng có phép
    any_absence_flag integer,           -- Cờ đánh dấu có bất kỳ tiết vắng nào trong ngày
    full_subject_absence_flag integer,  -- Cờ đánh dấu vắng học toàn bộ các tiết môn học trong ngày
    first_created_at varchar,           -- Thời gian tạo bản ghi lần đầu
    last_updated_at varchar             -- Thời gian cập nhật bản ghi cuối cùng
);

-- MỤC ĐÍCH: Kết quả đánh giá chi tiết của học sinh theo từng tiêu chí cụ thể của môn học.
-- Student 360 - Fact School Online Evaluate Process Subject Criterion
CREATE TABLE s360.fact_so_evaluate_process_subject_criterion (
    report_type_item_id integer,        -- ID loại báo cáo tiến trình môn học
    criterion_evaluate_id integer,      -- ID tiêu chí đánh giá năng lực
    id bigint,                          -- ID định danh duy nhất (Khóa chính)
    evaluate_progress_subject_id bigint,-- ID đánh giá tiến độ môn học
    evaluate_progress_id bigint,        -- ID phiếu đánh giá tiến độ tổng hợp
    so_school_id integer,               -- ID trường học trên hệ thống School Online
    grade_id integer,                   -- ID khối lớp
    homeroom_class_id integer,          -- ID lớp chủ nhiệm
    subject_id integer,                 -- ID môn học
    course_id bigint,                   -- ID khóa học / lớp học phần
    user_id bigint,                     -- ID người dùng hệ thống
    student_code varchar,               -- Mã số học sinh
    school_year_id integer,             -- ID năm học
    semester_index integer,             -- Học kỳ (1: Học kỳ 1, 2: Học kỳ 2)
    semester_stages integer,            -- Giai đoạn học kỳ (Ví dụ: Giữa kỳ, Cuối kỳ)
    final_grade varchar,                -- Điểm tổng kết / Điểm số cuối cùng
    final_grade_level varchar,          -- Mức độ xếp loại điểm tổng kết môn học (Hoàn thành tốt / Đạt / Chưa đạt)
    criterion_code varchar,             -- Mã tiêu chí đánh giá năng lực
    criterion_name varchar,             -- Tên tiêu chí đánh giá năng lực
    source_system varchar               -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Báo cáo đánh giá tiến trình học tập môn học định kỳ.
-- Student 360 - Fact School Online Evaluate Process Subjects
CREATE TABLE s360.fact_so_evaluate_process_subjects (
    id bigint,                              -- ID định danh duy nhất (Khóa chính)
    evaluate_progress_id bigint,            -- ID phiếu đánh giá tiến độ tổng hợp
    subject_id integer,                     -- ID môn học
    course_id bigint,                       -- ID khóa học / lớp học phần
    final_grade_level varchar,              -- Mức độ xếp loại điểm tổng kết môn học (Hoàn thành tốt / Đạt / Chưa đạt)
    end_of_year_final_grade_level varchar,  -- Mức độ xếp loại điểm môn học cả năm
    student_level varchar,                  -- Mức độ năng lực thực tế của học sinh
    student_level_expected varchar,         -- Mức độ năng lực kỳ vọng của học sinh
    comment varchar,                        -- Nhận xét, đánh giá của giáo viên
    comment_next_term varchar,              -- Nhận xét, định hướng học tập cho kỳ tiếp theo
    comment2 varchar,                       -- Nhận xét bổ sung 2
    comment3 varchar,                       -- Nhận xét bổ sung 3
    general_comment varchar,                -- Nhận xét chung của giáo viên
    action_for_improvement_student varchar, -- Hành động cải thiện từ phía học sinh
    action_for_improvement_teacher varchar, -- Hành động hỗ trợ cải thiện từ phía giáo viên
    reward varchar,                         -- Khen thưởng học tập
    teacher_fullname varchar,               -- Họ và tên giáo viên
    teacher2_fullname varchar,              -- Họ và tên giáo viên phụ trách phụ
    is_approved integer,                    -- Cờ phê duyệt (1: Đã duyệt, 0: Chờ duyệt)
    approved_by bigint,                     -- ID người phê duyệt
    approved_at timestamp(6) with time zone,-- Thời gian phê duyệt
    is_changed_final_grade_level integer,
    is_locked integer,                      -- Cờ khóa dữ liệu (1: Đã khóa không cho sửa, 0: Cho sửa)
    so_school_id integer,                   -- ID trường học trên hệ thống School Online
    grade_id integer,                       -- ID khối lớp
    homeroom_class_id integer,              -- ID lớp chủ nhiệm
    user_id bigint,                         -- ID người dùng hệ thống
    student_code varchar,                   -- Mã số học sinh
    school_year_id integer,                 -- ID năm học
    semester_index integer,                 -- Học kỳ (1: Học kỳ 1, 2: Học kỳ 2)
    semester_stages integer,                -- Giai đoạn học kỳ (Ví dụ: Giữa kỳ, Cuối kỳ)
    source_system varchar                   -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Nhật ký điểm danh lớp chủ nhiệm hàng ngày vào đầu giờ.
-- Student 360 - Fact School Online Homeroom Class Attendances
CREATE TABLE s360.fact_so_homeroom_class_attendances (
    id bigint,                                              -- ID định danh duy nhất (Khóa chính)
    tenant_id integer,                                      -- ID đơn vị/tổ chức (Tenant ID)
    so_school_id integer,                                   -- ID trường học trên hệ thống School Online
    campus_id integer,                                      -- ID cơ sở trường học (Campus ID)
    school_year_id integer,                                 -- ID năm học
    homeroom_class_id integer,                              -- ID lớp chủ nhiệm
    attendance_date date,                                   -- Ngày điểm danh
    so_user_id bigint,                                      -- ID người dùng trên hệ thống School Online
    student_code varchar,                                   -- Mã số học sinh
    status integer,                                         -- Trạng thái bản ghi
    comment varchar,                                        -- Nhận xét, đánh giá của giáo viên
    comment_meal varchar,                                   -- Nhận xét về bữa ăn bán trú của học sinh
    is_push_to_app integer,                                 -- Cờ đồng bộ dữ liệu lên ứng dụng phụ huynh (1: Đã đồng bộ)
    is_push_notification integer,                           -- Cờ gửi thông báo đẩy tới điện thoại phụ huynh (1: Đã gửi)
    is_locked integer,                                      -- Cờ khóa dữ liệu (1: Đã khóa không cho sửa, 0: Cho sửa)
    last_attendance_update_at timestamp(6) with time zone,  -- Mốc thời gian cập nhật trạng thái điểm danh cuối cùng
    is_deleted integer,                                     -- Cờ xóa logic (1: Đã xóa, 0: Chưa)
    created_by bigint,                                      -- ID người tạo bản ghi
    updated_by bigint,                                      -- ID người cập nhật bản ghi
    created_at varchar,                                     -- Thời gian tạo bản ghi
    updated_at varchar,                                     -- Thời gian cập nhật bản ghi
    source_system varchar                                   -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Nhật ký chi tiết các ca đi muộn lớp chủ nhiệm.
-- Student 360 - Fact School Online Homeroom Class Late Attendances
CREATE TABLE s360.fact_so_homeroom_class_late_attendances (
    id bigint,                                  -- ID định danh duy nhất (Khóa chính)
    tenant_id integer,                          -- ID đơn vị/tổ chức (Tenant ID)
    campus_id integer,                          -- ID cơ sở trường học (Campus ID)
    so_school_name varchar,
    so_school_id integer,                       -- ID trường học trên hệ thống School Online
    school_year_id integer,                     -- ID năm học
    grade_id integer,                           -- ID khối lớp
    homeroom_class_id integer,                  -- ID lớp chủ nhiệm
    homeroom_class_name varchar,                -- Tên lớp chủ nhiệm
    attendance_date date,                       -- Ngày điểm danh
    so_user_id integer,                         -- ID người dùng trên hệ thống School Online
    student_code varchar,                       -- Mã số học sinh
    user_name varchar,                          -- Tên tài khoản người dùng đăng nhập
    user_fullname varbinary,                    -- Họ tên người dùng (Mã hóa bảo mật)
    user_mail varbinary,                        -- Email người dùng (Mã hóa bảo mật)
    attendance_time timestamp(6) with time zone,-- Thời gian điểm danh thực tế
    is_late integer,                            -- Cờ đi học muộn (1: Đi muộn, 0: Đúng giờ)
    status_name varchar,                        -- Tên trạng thái
    ignore_late integer,                        -- Cờ bỏ qua lỗi đi học muộn (1: Bỏ qua)
    reason_ignore varchar,                      -- Lý do bỏ qua lỗi đi muộn
    image_path varchar,                         -- Đường dẫn ảnh minh chứng (đi muộn/xin nghỉ)
    time_late integer,                          -- Số phút đi muộn
    process_status bigint,                      -- Trạng thái xử lý lỗi
    is_deleted integer,                         -- Cờ xóa logic (1: Đã xóa, 0: Chưa)
    created_by bigint,                          -- ID người tạo bản ghi
    updated_by bigint,                          -- ID người cập nhật bản ghi
    created_at varchar,                         -- Thời gian tạo bản ghi
    updated_at varchar,                         -- Thời gian cập nhật bản ghi
    source_system varchar                       -- Hệ thống nguồn dữ liệu (Ví dụ: LMS, DWH)
);

-- MỤC ĐÍCH: Thống kê mức độ hoàn thành chuẩn đầu ra môn học của học sinh.
-- Student 360 - Fact School Online Subject Mastery
CREATE TABLE s360.fact_so_subject_mastery (
    so_school_id bigint,            -- ID trường học trên hệ thống School Online
    so_school_year_id bigint,       -- ID năm học
    semester_index integer,         -- Học kỳ (1: Học kỳ 1, 2: Học kỳ 2)
    semester_stages integer,        -- Giai đoạn học kỳ (Ví dụ: Giữa kỳ, Cuối kỳ)
    grade_id bigint,                -- ID khối lớp
    homeroom_class_name varchar,    -- Tên lớp chủ nhiệm
    homeroom_class_id bigint,       -- ID lớp chủ nhiệm
    subject_id integer,             -- ID môn học
    student_code varchar,           -- Mã số học sinh
    score_type varchar,             -- Phân loại đầu điểm (Miệng, Thường xuyên, Giữa kỳ, Cuối kỳ)
    final_grade double,             -- Điểm tổng kết / Điểm số cuối cùng
    final_grade_level varchar,      -- Mức độ xếp loại điểm tổng kết môn học (Hoàn thành tốt / Đạt / Chưa đạt)
    percent_target_min double,      -- Tỷ lệ phần trạng tối thiểu đạt mục tiêu môn học
    percent_target_max double,      -- Tỷ lệ phần trăm tối đa đạt mục tiêu môn học
    percent_target_normal double,   -- Tỷ lệ phần trăm đạt chuẩn trung bình môn học
    percent_target_exceed double    -- Tỷ lệ phần trăm vượt chuẩn mong đợi môn học
);

-- MỤC ĐÍCH: Kết quả học tập tổng kết của học sinh chi tiết theo từng môn học.
-- Student 360 - Fact Subject Academic Records
CREATE TABLE s360.fact_subject_academic_records (
    id bigint,                              -- ID định danh duy nhất (Khóa chính)
    overall_record_id bigint,               -- ID liên kết phiếu điểm học bạ tổng hợp
    subject_id bigint,                      -- ID môn học
    final_grade decimal(10,1),              -- Điểm tổng kết / Điểm số cuối cùng
    s1_final_grade decimal(10,1),
    s2_final_grade decimal(10,1),
    final_grade_after_summer decimal(10,1),
    is_teacher_approved integer,            -- Cờ giáo viên bộ môn đã duyệt điểm (1: Đã duyệt)
    is_after_summer integer,                -- Cờ kiểm tra lại sau hè (1: Đúng)
    is_input_final_grade_s1 integer,        -- Cờ giáo viên đã nhập điểm tổng kết HK1
    is_input_final_grade_s2 integer,        -- Cờ giáo viên đã nhập điểm tổng kết HK2
    is_input_final_grade_cn integer,        -- Cờ giáo viên đã nhập điểm tổng kết cả năm
    is_locked integer,                      -- Cờ khóa dữ liệu (1: Đã khóa không cho sửa, 0: Cho sửa)
    is_deleted integer,                     -- Cờ xóa logic (1: Đã xóa, 0: Chưa)
    created_at varchar,                     -- Thời gian tạo bản ghi
    updated_at varchar                      -- Thời gian cập nhật bản ghi
);

-- MỤC ĐÍCH: Bảng trung gian liên kết giữa thông tin đăng ký ngoại khóa và thông tin thanh toán.
-- Student 360 - Link Register Payment
CREATE TABLE s360.link_register_payment (
    id bigint,          -- ID định danh duy nhất (Khóa chính)
    payment_id integer, -- ID hóa đơn đóng phí
    register_id integer,-- ID lượt đăng ký hoạt động
    created_at varchar, -- Thời gian tạo bản ghi
    updated_at varchar  -- Thời gian cập nhật bản ghi
);

-- ============================================================
-- SCHEMA: t360
-- ============================================================

-- MỤC ĐÍCH: Danh mục phân công giáo viên chủ nhiệm hoặc giáo viên giảng dạy chính theo lớp, năm học và cơ sở trường.
-- Teacher 360 - Dimension Teacher 360 Homeroom Class Teacher
CREATE TABLE t360.dim_t360_homeroom_class_teacher (
    id bigint,                              -- ID định danh duy nhất (Khóa chính)
    tenant_id bigint,                       -- ID đơn vị/tổ chức (Tenant ID)
    homeroom_teacher_id decimal(20,0),      -- ID giáo viên chủ nhiệm
    teacher_code varchar,                   -- Mã số giáo viên
    teacher_name varbinary,                 -- Họ tên giáo viên (Mã hóa bảo mật)
    homeroom_class_id bigint,               -- ID lớp chủ nhiệm
    class_code varchar,                     -- Mã lớp học
    class_name varchar,                     -- Tên lớp học
    so_school_id integer,                   -- ID trường học trên hệ thống School Online
    school_name varchar,                    -- Tên trường học
    school_code varchar,                    -- Mã trường học
    so_campus_name varchar,                 -- Tên cơ sở trường học
    school_year_id integer,                 -- ID năm học
    school_year_code varchar,               -- Mã năm học
    grade_name varchar,                     -- Tên khối lớp
    is_moved_out integer,                   -- Cờ học sinh đã chuyển lớp học phần (1: Đã chuyển)
    teacher_type varchar,                   -- Vai trò của giáo viên trong lớp (GVCN / GV Bộ môn)
    is_deleted integer,                     -- Cờ xóa logic (1: Đã xóa, 0: Chưa)
    created_at timestamp(6) with time zone, -- Thời gian tạo bản ghi
    updated_at timestamp(6) with time zone  -- Thời gian cập nhật bản ghi
);
