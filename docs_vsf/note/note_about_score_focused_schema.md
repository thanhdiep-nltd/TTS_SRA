# Kế hoạch Thiết kế `score_focused_schema.sql` & Chi Tiết Bảng Bỏ Qua từ `School Online Schema.csv`

## Danh sách Bảng từ `School Online Schema.csv` Tạm Thời Bỏ Qua (~23 Bảng DWH)

Dưới đây là danh sách toàn bộ các bảng có trong **`School Online Schema.csv`** nhưng được **tạm thời bỏ qua** trong `score_focused_schema.sql` để rút gọn schema, giúp Text-to-SQL Agent tập trung tối đa vào phân hệ điểm số:

---

### 1. Phân hệ Hoạt động Ngoại khóa & Học phí (4 Bảng)
- **`s360.dim_extracurricular_activity`**: Danh mục các hoạt động ngoại khóa.
- **`s360.fact_extracurricular_activity_payments`**: Giao dịch đóng tiền ngoại khóa.
- **`s360.fact_extracurricular_activity_registers`**: Danh sách học sinh đăng ký ngoại khóa.
- **`s360.link_register_payment`**: Liên kết đăng ký và thanh toán ngoại khóa.
> *Lý do bỏ qua*: Thuộc phân hệ tài chính / dịch vụ ngoài giờ, không ảnh hưởng đến điểm số học tập.

---

### 2. Phân hệ Điểm danh & Chuyên cần Chi tiết (7 Bảng)
- **`s360.fact_absent_logs`**: Nhật ký đơn xin nghỉ học của học sinh.
- **`s360.fact_course_attendences`**: Điểm danh chuyên cần theo từng tiết học.
- **`s360.fact_so_absent_extract_late`**: Thống kê dữ liệu nghỉ học và đi muộn theo chu kỳ.
- **`s360.fact_so_class_attendance_statistics`**: Thống kê điểm danh theo ngày.
- **`s360.fact_so_daily_attendance`**: Thống kê điểm danh môn học theo ngày.
- **`s360.fact_so_homeroom_class_attendances`**: Điểm danh lớp chủ nhiệm đầu giờ.
- **`s360.fact_so_homeroom_class_late_attendances`**: Nhật ký các ca đi muộn lớp chủ nhiệm.
> *Lý do bỏ qua*: Thuộc phân hệ nề nếp / điểm danh hàng ngày. Số ngày nghỉ học tổng kết (`day_of_absent`, `s1_day_of_absent`, `s2_day_of_absent`) đã được lưu sẵn trong bảng tổng kết `fact_overall_academic_records`.

---

### 3. Phân hệ Rèn luyện Hành vi & Điểm phạt Chi tiết (2 Bảng)
- **`s360.dim_behavior`**: Danh mục các tiêu chí hành vi cộng/trừ điểm rèn luyện.
- **`s360.fact_behavior_logs`**: Nhật ký từng lần ghi nhận hành vi rèn luyện.
> *Lý do bỏ qua*: Chi tiết nhật ký cộng/trừ điểm nề nếp. Tổng điểm rèn luyện (`final_behavior_point`) và Xếp loại hạnh kiểm (`conduct`) đã có sẵn trong bảng `fact_overall_academic_records`.

---

### 4. Phân hệ Đăng ký Học phần LMS & Lớp Khóa học (2 Bảng)
- **`s360.dim_course`**: Danh mục khóa học / lớp học phần LMS.
- **`s360.fact_course_enrolls`**: Nhật ký đăng ký học phần.
> *Lý do bỏ qua*: Thuộc phân hệ xếp lớp học phần LMS. Điểm môn học đã được ánh xạ trực tiếp theo `homeroom_class_id` và `subject_id` trong `fact_gradebooks`.

---

### 5. Phân hệ Báo cáo Chi tiết Tiêu chí & Chuẩn đầu ra (3 Bảng)
- **`s360.fact_so_evaluate_process_subject_criterion`**: Kết quả đánh giá theo từng tiêu chí nhỏ của môn học.
- **`s360.fact_so_subject_mastery`**: Thống kê mức độ đạt chuẩn đầu ra môn học.
- **`s360.dim_so_school_mapping_subject`**: Bảng ánh xạ cấu hình môn học riêng của từng trường.
> *Lý do bỏ qua*: Phục vụ báo cáo phân tích sâu theo từng tiêu chí nhỏ, chưa cần thiết cho đợt kiểm thử Text-to-SQL Agent với 6 thang điểm chính.

---

### 6. Bảng Staging & Phân công Giáo viên (4 Bảng)
- **`default.stg_so_exam_moet_path`**: Staging phân cấp danh mục cột điểm MOET.
- **`default.stg_so_strand_path`**: Staging phân cấp chương trình môn học.
- **`default.stg_so_students`**: Staging dữ liệu học sinh sơ bộ.
- **`t360.dim_t360_homeroom_class_teacher`**: Phân công GV. (Thông tin GV đã có sẵn ở `public.users` và `s360.dim_homeroom_class`).
> *Lý do bỏ qua*: Bảng trung gian staging và bảng dư thừa dữ liệu giáo viên.

---

## Tổng kết So Sánh Bảng `School Online Schema.csv`

| Nhóm Bảng | Tổng Số Bảng | Số Bảng GIỮ LẠI trong `score_focused_schema.sql` | Số Bảng TẠM BỎ KHI TEST |
|---|:---:|:---:|:---:|
| **Điểm số & Học lực (`s360`)** | 14 Bảng | **14 Bảng** | 0 Bảng |
| **Ngoại khóa & Tài chính (`s360`)** | 4 Bảng | 0 Bảng | **4 Bảng** |
| **Điểm danh & Chuyên cần (`s360`)** | 7 Bảng | 0 Bảng | **7 Bảng** |
| **Hành vi rèn luyện (`s360`)** | 2 Bảng | 0 Bảng | **2 Bảng** |
| **Học phần LMS (`s360`)** | 2 Bảng | 0 Bảng | **2 Bảng** |
| **Tiêu chí & Ánh xạ (`s360`)** | 4 Bảng | 1 Bảng (`dim_grade_scale_detail`) | **3 Bảng** |
| **Staging & Teacher (`default` & `t360`)** | 4 Bảng | 0 Bảng | **4 Bảng** |
| **TỔNG CỘNG** | **37 Bảng** | **14 Bảng DWH (+5 Bảng App Core = 19 Bảng)** | **22 Bảng DWH (+2 Staging)** |
