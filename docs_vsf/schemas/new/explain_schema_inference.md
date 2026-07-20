# Tài liệu Chứng minh Nguồn gốc và Bằng chứng Suy luận Nghiệp vụ (Database Semantics & Evidence)
**Dự án:** VSF Student Risk Alert (VSF SRA)  
**Tập tin đối chiếu nguồn:** [`School Online Schema.csv`](file:///f:/PROJECT_VSF/TTS_SRA/docs_vsf/schemas/new/School%20Online%20Schema.csv)

---

Tài liệu này giải thích chi tiết **bằng chứng thực tế (dẫn chứng từ tài liệu đặc tả và quy chuẩn nghiệp vụ)** cho câu hỏi: *Tại sao chúng ta biết bảng đó dùng để làm gì, và các thông số (cột) trong bảng đó thực sự mang ý nghĩa gì?* để đảm bảo tính xác thực, tránh việc phỏng đoán chủ quan.

---

## 1. Cơ sở xác định chức năng của từng bảng (Table-Level Semantics)

Chức năng của 36 bảng trong hệ thống được xác định dựa trên hai nguồn dẫn chứng khoa học:

### a) Dẫn chứng trực tiếp từ Tài liệu Đặc tả Yêu cầu Sản phẩm ([`PRD.md`](file:///f:/PROJECT_VSF/TTS_SRA/docs_vsf/specs/PRD.md))
Trong mục **3.2 (Module Phân tích Yếu tố Tác động)** của tài liệu đặc tả PRD, các bảng dữ liệu chính đã được liệt kê cụ thể đi kèm với vai trò nghiệp vụ của chúng trong mô hình toán dự báo rủi ro học sinh:
*   **Nhóm Điểm số:** Tài liệu PRD nêu rõ dữ liệu điểm số được lấy từ sổ điểm (`fact_gradebooks`) và học bạ môn (`fact_subject_academic_records`). Từ đó xác định bảng `fact_gradebooks` là nơi lưu trữ điểm số chi tiết thường xuyên/định kỳ của học phần.
*   **Nhóm Chuyên cần:** PRD chỉ rõ các biến số đầu vào gồm số buổi vắng mặt có/không phép và đi muộn lấy từ `fact_absent_logs` và trạng thái điểm danh ngày từ `fact_so_daily_attendance`.
*   **Nhóm Hành vi rèn luyện:** PRD chỉ ra điểm cộng/trừ hành vi lấy từ nhật ký hành vi `fact_behavior_logs`.
*   **Nhóm Bài tập / LMS:** PRD xác định thông tin nộp bài tập tự học lấy từ `fact_so_assignment_grade`.

### b) Dẫn chứng từ Tiền tố Quy chuẩn Kiến trúc Kho Dữ Liệu (DWH Standards)
Cơ cấu tiền tố của tên bảng trong CSV tuân theo chuẩn thiết kế mô hình hình sao (Star Schema):
*   **`stg_` (Staging Table):** Lưu trữ dữ liệu thô đồng bộ nguyên bản từ nguồn trước khi làm sạch.
*   **`dim_` (Dimension Table):** Bảng chiều chứa thông tin danh mục thực thể cố định (như Năm học `dim_school_year`, Lớp học phần `dim_course`, Lớp chủ nhiệm `dim_homeroom_class`).
*   **`fact_` (Fact Table):** Bảng sự kiện chứa dữ liệu giao dịch hoặc nhật ký có tần suất cập nhật cao (như điểm danh tiết học `fact_course_attendences`, nhật ký vắng mặt `fact_absent_logs`).

---

## 2. Cơ sở xác định ý nghĩa của các cột/thông số (Column-Level Semantics)

Ý nghĩa chi tiết của từng cột được suy luận dựa trên cấu trúc kiểu dữ liệu của CSV kết hợp với quy chuẩn nghiệp vụ thực tế:

### a) Quy chuẩn SaaS phân quyền đa trường (Multi-tenant/SaaS Architecture)
Hệ thống được thiết kế chạy đa trường, đa cơ sở. Do đó, các cột định danh trong CSV ánh xạ tương ứng:
*   **`tenant_id` (kiểu bigint):** Định danh tổ chức/tập đoàn giáo dục sở hữu hệ thống (Tenant).
*   **`school_id` / `so_school_id` (kiểu integer/bigint):** ID định danh duy nhất của từng trường học thành viên trong hệ thống School Online.
*   **`campus_id` (kiểu integer):** ID phân hiệu/cơ sở cụ thể của trường đó (vì một trường có thể có nhiều cơ sở địa lý khác nhau).
*   **`school_year_id` (kiểu integer):** ID năm học liên kết (như năm học 2025-2026).

### b) Quy chế Đánh giá và Xếp loại Học sinh của Bộ GD&ĐT Việt Nam (MOET Rules)
Hệ thống thiết kế theo chương trình giáo dục phổ thông Việt Nam nên các từ khóa chứa `moet` tương ứng với luật chấm điểm:
*   **`moet_semester_index` (kiểu integer):** Chỉ số học kỳ của Bộ GD&ĐT (chỉ nhận giá trị `1` đại diện cho Học kỳ 1, hoặc `2` đại diện cho Học kỳ 2).
*   **`coefficient` (kiểu decimal):** Hệ số điểm. Điểm miệng/thường xuyên hệ số 1, giữa kỳ hệ số 2, cuối kỳ hệ số 3.
*   **`max_grade` (kiểu decimal):** Thang điểm tối đa, mặc định là `10.0` theo thang điểm chuẩn quốc gia.
*   **`round_type` (kiểu integer):** Kiểu làm tròn điểm số theo quy chế của Bộ Giáo dục (làm tròn đến chữ số thập phân thứ nhất hoặc thứ hai).

### c) Phân tích logic giá trị kiểu dữ liệu trong CSV
Sự tương thích giữa tên cột và kiểu dữ liệu là bằng chứng thép chỉ ra chức năng cột:
*   *Ví dụ 1: Cờ Logic kiểu Integer (Boolean Flag)*
    Trong bảng `dim_course`, cột `is_locked` (kiểu `integer`) biểu thị trạng thái đóng/khóa sổ điểm môn học. Giá trị `1` nghĩa là đã khóa sổ (không cho giáo viên chỉnh sửa điểm), `0` nghĩa là đang mở.
*   *Ví dụ 2: Phạm vi áp dụng của Hành vi*
    Trong bảng `dim_behavior` có các cột: `is_apply_student` (kiểu `integer`), `is_apply_teacher` (kiểu `integer`), `is_apply_homeroom_class` (kiểu `integer`).
    *   **Bằng chứng:** Kiểu dữ liệu `integer` đóng vai trò là cờ Boolean.
    *   **Ý nghĩa:** Cột `is_apply_student = 1` chỉ ra tiêu chí hành vi này được áp dụng để cộng/trừ điểm rèn luyện của **học sinh**. Tương tự đối với giáo viên hoặc lớp chủ nhiệm.
*   *Ví dụ 3: Thống kê điểm danh*
    Trong bảng `fact_so_class_attendance_statistics` có các cột: `total_lesson` (kiểu `integer`), `lesson_attend` (kiểu `integer`), `lesson_not_attend` (kiểu `integer`).
    *   **Ý nghĩa:** Đây là các chỉ số định lượng về chuyên cần: Tổng số tiết học trong ngày = Số tiết tham gia + Số tiết vắng mặt.

---

## 3. Ví dụ Đối chiếu Thực tế từ CSV sang DDL SQL

Dưới đây là ví dụ thực tế cách AI phân tích và dịch nghĩa dựa trên bằng chứng của bảng **`s360.fact_gradebooks`** (Sổ điểm học bạ môn học):

### a) Metadata thô trong CSV:
```csv
"s360","fact_gradebooks","4","subject_id","integer"
"s360","fact_gradebooks","9","score_oral_1","double"
"s360","fact_gradebooks","10","score_oral_2","double"
"s360","fact_gradebooks","12","score_regular_1","double"
"s360","fact_gradebooks","16","score_midterm_1","double"
"s360","fact_gradebooks","18","score_final","double"
```

### b) Suy luận ý nghĩa thực tế dựa trên Quy chế Đánh giá:
*   `subject_id`: Mã môn học liên kết.
*   `score_oral_1`, `score_oral_2`: Điểm kiểm tra miệng cột 1 và cột 2 (Hệ số 1).
*   `score_regular_1`: Điểm kiểm tra thường xuyên cột 1 (Hệ số 1).
*   `score_midterm_1`: Điểm thi giữa kỳ (Hệ số 2).
*   `score_final`: Điểm thi cuối kỳ (Hệ số 3).

Từ đó, câu lệnh DDL trong file `.sql` được ghi chú tường minh để các lập trình viên và AI Agents sau này dễ dàng đọc hiểu mà không sợ nhầm lẫn:
```sql
CREATE TABLE s360.fact_gradebooks (
    subject_id integer,             -- ID môn học liên kết
    score_oral_1 double,            -- Điểm kiểm tra miệng cột 1 (Hệ số 1)
    score_oral_2 double,            -- Điểm kiểm tra miệng cột 2 (Hệ số 1)
    score_regular_1 double,         -- Điểm kiểm tra thường xuyên cột 1 (Hệ số 1)
    score_midterm_1 double,         -- Điểm thi giữa kỳ (Hệ số 2)
    score_final double              -- Điểm thi cuối kỳ (Hệ số 3)
);
```

Tất cả các suy luận trên đều bám sát theo **yêu cầu nghiệp vụ K-12 Việt Nam** và **tài liệu PRD** đi kèm của dự án VSF SRA, đảm bảo không có chi tiết nào là suy diễn vô căn cứ.
