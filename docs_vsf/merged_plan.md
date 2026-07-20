# Kế hoạch Gộp CSDL VSF SRA: Tạo File SQL DDL Gộp Độc Lập (54 Bảng)

Tài liệu kế hoạch gộp CSDL **VSF Student Risk Alert (VSF SRA)** mới nhất, tập trung vào mục tiêu tạo duy nhất 01 file SQL DDL gộp hoàn chỉnh tại đường dẫn [`docs_vsf/schemas/merged/merged_vsf_sra_schema.sql`](file:///f:/PROJECT_VSF/TTS_SRA/docs_vsf/schemas/merged/merged_vsf_sra_schema.sql).

---

## 🎯 1. Phạm vi Công việc (Scope of Work)

* **Mục tiêu duy nhất**: Tạo file SQL DDL gộp đầy đủ **54 bảng** chuẩn PostgreSQL.
* **Đường dẫn đầu ra**: [`docs_vsf/schemas/merged/merged_vsf_sra_schema.sql`](file:///f:/PROJECT_VSF/TTS_SRA/docs_vsf/schemas/merged/merged_vsf_sra_schema.sql).
* **Tạm hoãn (Out of Scope giai đoạn này)**: Chưa sinh mock data, chưa cập nhật Python ORM models, và chưa chạy kiểm thử backend API.

---

## 🏗️ 2. Quyết định Kiến trúc & Cấu trúc Schemas

File SQL DDL gộp sẽ đặt trong **1 Database PostgreSQL duy nhất**, khởi tạo **4 Schemas**:

1. `CREATE SCHEMA IF NOT EXISTS public;` (18 Bảng Vận hành App Core, Auth & AI Engine)
2. `CREATE SCHEMA IF NOT EXISTS s360;` (32 Bảng Kho dữ liệu Học sinh DWH Student 360)
3. `CREATE SCHEMA IF NOT EXISTS t360;` (1 Bảng Kho dữ liệu Giáo viên DWH Teacher 360)
4. `CREATE SCHEMA IF NOT EXISTS default;` (3 Bảng Staging nhập liệu)

---

## ❌ 3. Danh sách 10 Bảng Schema Cũ BỊ LOẠI BỎ (Gộp vào DWH)

Dưới đây là 10 bảng từ Schema Cũ bị **loại bỏ hoàn toàn** và được thay thế bằng các bảng đa dạng, chuẩn hóa hơn từ Schema Mới (DWH `s360` & `t360`):

| STT | Bảng Schema Cũ bị BỎ | Lý do loại bỏ & Bảng Schema Mới thay thế |
| :---: | :--- | :--- |
| **1** | `scores` | **Thay bằng `s360.fact_gradebooks_moet` & `s360.fact_gradebooks`**<br>→ Bảng cũ chỉ lưu điểm 0-10 thô đơn giản; bảng mới hỗ trợ cả điểm chuẩn Bộ GD (hệ số 1,2,3, làm tròn) lẫn điểm LMS/điểm chữ. |
| **2** | `students` | **Thay bằng `s360.dim_homeroom_class_student`**<br>→ Bảng mới quản lý chi tiết thông tin học sinh gắn liền với từng lớp chủ nhiệm, niên khóa, cơ sở trường (`campus_id`). |
| **3** | `enrollments` | **Thay bằng `s360.dim_homeroom_class_student` & `s360.fact_course_enrolls`**<br>→ Tách biệt rõ ràng luồng biên chế Lớp chủ nhiệm và luồng Đăng ký Lớp học phần/tín chỉ. |
| **4** | `classes` | **Thay bằng `s360.dim_homeroom_class` & `s360.dim_course`**<br>→ Quản lý song song cả Lớp chủ nhiệm (Homeroom Class) và Lớp môn học phần (Course LMS). |
| **5** | `grades` | **Thay bằng thông tin Khối tích hợp sẵn (`grade_id`, `grade_code`, `grade_name`)**<br>→ Các bảng DWH mới đã nhúng trực tiếp mã và tên khối lớp vào từng bản ghi để tối ưu hóa tốc độ truy vấn analytics. |
| **6** | `academic_years` | **Thay bằng `s360.dim_school_year`**<br>→ Bảng danh mục năm học chuẩn của DWH (có thêm cờ khóa sổ học bạ `is_gradebook_locked`). |
| **7** | `semesters` | **Thay bằng chỉ số `moet_semester_index` & `semester_stages`**<br>→ Tích hợp thẳng học kỳ (HK1, HK2) và giai đoạn (Giữa kỳ, Cuối kỳ) vào các bảng điểm và đánh giá. |
| **8** | `subjects` | **Thay bằng `s360.dim_subject` & `s360.dim_so_school_mapping_subject`**<br>→ Quản lý danh mục môn học toàn hệ thống và ánh xạ môn học riêng của từng trường/cơ sở. |
| **9** | `subject_evaluations` | **Thay bằng `s360.fact_so_evaluate_process_subjects`**<br>→ Thay thế bằng phiếu đánh giá tiến trình môn học chi tiết (có nhận xét, định hướng kỳ tới và hành động cải thiện). |
| **10** | `student_term_reports` | **Thay bằng `s360.fact_overall_academic_records` & `s360.dim_so_evaluate_progress`**<br>→ Thay thế bằng học bạ tổng kết toàn diện cả năm (điểm $S1, S2, CN, Sau hè$, hạnh kiểm, học lực, điểm rèn luyện và ngày nghỉ). |

---

## 📋 4. Phân loại 54 Bảng trong Schema Gộp (Cập nhật, Mới, Giữ nguyên)

### 🔄 A. Nhóm Bảng được Cập Nhật (Modified/Updated Tables - 9 Bảng)
*Các bảng kế thừa từ Schema cũ nhưng được điều chỉnh thay đổi kiểu dữ liệu (từ `UUID` sang `INTEGER`) hoặc thêm các cột mã code để đồng bộ chuẩn xác với DWH mới:*

1. **`public.users`**: Bổ sung cột liên kết DWH `teacher_code` (VARCHAR), `student_code` (VARCHAR).
2. **`public.classroom_recordings`**: Đổi kiểu cột `subject_id`, `class_id`, `semester_id` từ `UUID` sang `INTEGER`.
3. **`public.exam_papers`**: Đổi kiểu cột `subject_id`, `semester_id`, `grade_id` từ `UUID` sang `INTEGER`.
4. **`public.exam_competencies`**: Cập nhật kiểu cột `unit_id` để map sang mã phân cấp bài học của DWH.
5. **`public.exam_column_mappings`**: Đổi kiểu cột `subject_id`, `semester_id`, `class_id`, `grade_id` từ `UUID` sang `INTEGER`.
6. **`public.question_items`**: Đổi kiểu cột `subject_id` từ `UUID` sang `INTEGER`.
7. **`public.misconceptions`**: Đổi kiểu cột `subject_id` từ `UUID` sang `INTEGER`.
8. **`public.exam_blueprints`**: Đổi kiểu cột `subject_id` từ `UUID` sang `INTEGER`.
9. **`public.generated_exams`**: Đổi kiểu cột `semester_id`, `grade_id` từ `UUID` sang `INTEGER`.

---

### 🆕 B. Nhóm Bảng được Cài Mới (New Tables - 36 Bảng)
*Toàn bộ 36 bảng thuộc các schema DWH của hệ thống School Online:*

* **Schema `default` (Staging - 3 bảng)**:
  10. `default.stg_so_exam_moet_path`
  11. `default.stg_so_strand_path`
  12. `default.stg_so_students`
* **Schema `s360` (DWH Student 360 - 32 bảng)**:
  13. `s360.dim_behavior`
  14. `s360.dim_course`
  15. `s360.dim_exam`
  16. `s360.dim_exam_moet`
  17. `s360.dim_extracurricular_activity`
  18. `s360.dim_homeroom_class`
  19. `s360.dim_homeroom_class_student`
  20. `s360.dim_school_year`
  21. `s360.dim_so_assignment`
  22. `s360.dim_so_evaluate_progress`
  23. `s360.dim_so_school_mapping_subject`
  24. `s360.dim_subject`
  25. `s360.fact_absent_logs`
  26. `s360.fact_behavior_logs`
  27. `s360.fact_course_attendences`
  28. `s360.fact_course_enrolls`
  29. `s360.fact_extracurricular_activity_payments`
  30. `s360.fact_extracurricular_activity_registers`
  31. `s360.fact_gradebooks`
  32. `s360.fact_gradebooks_moet`
  33. `s360.fact_overall_academic_records`
  34. `s360.fact_so_absent_extract_late`
  35. `s360.fact_so_assignment_grade`
  36. `s360.fact_so_class_attendance_statistics`
  37. `s360.fact_so_daily_attendance`
  38. `s360.fact_so_evaluate_process_subject_criterion`
  39. `s360.fact_so_evaluate_process_subjects`
  40. `s360.fact_so_homeroom_class_attendances`
  41. `s360.fact_so_homeroom_class_late_attendances`
  42. `s360.fact_so_subject_mastery`
  43. `s360.fact_subject_academic_records`
  44. `s360.link_register_payment`
* **Schema `t360` (DWH Teacher 360 - 1 bảng)**:
  45. `t360.dim_t360_homeroom_class_teacher`

---

### 📌 C. Nhóm Bảng Giữ Nguyên Như Cũ (Unchanged Tables - 9 Bảng)
*Các bảng ứng dụng hoặc đo lường AI từ Schema cũ được giữ nguyên 100% cấu trúc:*

46. **`public.refresh_tokens`**
47. **`public.audit_logs`**
48. **`public.ai_sessions`**
49. **`public.ai_messages`**
50. **`public.ai_session_attachments`**
51. **`public.report_schedules`**
52. **`public.generated_exam_items`**
53. **`public.notifications`**
54. **`public.ai_observability_snapshots`**

---

## 🛠️ 5. Các bước thực hiện (Proposed Execution)

1. Tạo thư mục `docs_vsf/schemas/merged/` nếu chưa tồn tại.
2. Viết file SQL DDL [`docs_vsf/schemas/merged/merged_vsf_sra_schema.sql`](file:///f:/PROJECT_VSF/TTS_SRA/docs_vsf/schemas/merged/merged_vsf_sra_schema.sql) chứa đầy đủ:
   * Extensions (`uuid-ossp`, `pg_trgm`, `vector`).
   * Enums và Types.
   * `CREATE TABLE` DDL cho 54 bảng với `COMMENT ON TABLE` và `COMMENT ON COLUMN` bằng tiếng Việt rõ ràng.
   * Các Chỉ mục (Indexes) và Triggers tự động cập nhật `updated_at`.
