# Báo Cáo Phân Tích & Đối Chiếu Schema: `score_focused_schema.sql` (25 Bảng) vs `school_online_schema.sql` (36 Bảng)

## 1. Tổng Quan Kiến Trúc

* **Mục tiêu dự án VSF SRA (Phase 1)**: Xây dựng Text-to-SQL Agent chuyên sâu truy vấn **Điểm Số & Kết Quả Học Tập** của học sinh.
* **`score_focused_schema.sql` (25 Bảng)**: Bản Schema được tinh gọn & hợp nhất chuyên biệt (gồm 10 bảng App Core + 15 bảng DWH Điểm số), tối ưu hóa prompt context và giảm nhiễu cho LLM khi sinh câu lệnh SQL.
* **`school_online_schema.sql` (36 Bảng)**: Bản DWH gốc đầy đủ của hệ thống School Online (bao gồm cả phân hệ Thu phí ngoại khóa, Chuyên cần tiết học, Đi học muộn và Đánh giá rèn luyện).

---

## 2. Danh Sách Các Bảng Tạm Thời Chưa Đưa Vào Phase 1 & Lý Do

Các bảng trong `school_online_schema.sql` chưa đưa vào `score_focused_schema.sql` được chia thành **5 nhóm nghiệp vụ**:

### 🔴 Nhóm 1: Quản Lý Thu Phí & Hoạt Động Ngoại Khóa (4 Bảng)
* **Danh sách bảng**:
  1. `s360.dim_extracurricular_activity`: Danh mục các CLB & Hoạt động ngoại khóa.
  2. `s360.fact_extracurricular_activity_registers`: Lịch sử học sinh đăng ký tham gia ngoại khóa.
  3. `s360.fact_extracurricular_activity_payments`: Giao dịch đóng tiền ngoại khóa & giảm giá thành viên VinClub.
  4. `s360.link_register_payment`: Bảng liên kết giữa phiếu đăng ký và hóa đơn thanh toán.
* **Lý do chưa dùng**: Đây là phân hệ **Tài chính & Thu phí CLB/Ngoại khóa**. Giai đoạn hiện tại Text-to-SQL Agent tập trung vào Học thuật & Điểm số, không xử lý truy vấn tài chính ngoại khóa.

---

### 🟡 Nhóm 2: Quản Lý Chuyên Cần, Xin Nghỉ Học & Đi Học Muộn (5 Bảng)
* **Danh sách bảng**:
  5. `s360.fact_absent_logs`: Lịch sử đơn xin nghỉ học của phụ huynh/học sinh.
  6. `s360.fact_so_homeroom_class_attendances`: Điểm danh lớp chủ nhiệm đầu giờ hàng ngày.
  7. `s360.fact_so_homeroom_class_late_attendances`: Chi tiết các ca đi học muộn (số phút đi muộn, ảnh minh chứng).
  8. `s360.fact_course_attendences`: Điểm danh chuyên cần theo từng tiết học phần.
  9. `s360.fact_so_daily_attendance` & `s360.fact_so_class_attendance_statistics`: Thống kê tổng hợp số tiết vắng mặt.
* **Lý do chưa dùng**: Phân hệ **Chuyên cần & Đi muộn**. Thông tin tổng số ngày nghỉ cả năm hiện tại đã có sẵn ở cột `day_of_absent` trong bảng `fact_overall_academic_records`. Chi tiết từng tiết vắng sẽ được tích hợp ở Phase 2 khi làm module **Cảnh báo Nguy cơ (At-Risk Early Warning System)**.

---

### 🟢 Nhóm 3: Nhật Ký Hành Vi & Cộng/Trừ Điểm Rèn Luyện (2 Bảng)
* **Danh sách bảng**:
  10. `s360.dim_behavior`: Danh mục các hành vi rèn luyện (tiêu chí cộng/trừ điểm rèn luyện).
  11. `s360.fact_behavior_logs`: Nhật ký ghi nhận từng vụ việc vi phạm/khen thưởng rèn luyện.
* **Lý do chưa dùng**: Phân hệ **Chi tiết Rèn luyện**. Xếp loại Hạnh kiểm (`conduct`) và Điểm rèn luyện tổng kết (`final_behavior_point`) đã được lưu trữ trong bảng tổng kết `fact_overall_academic_records`.

---

### 🔵 Nhóm 4: Đánh Giá Chi Tiết Tiêu Chí Phụ / Rubric (2 Bảng)
* **Danh sách bảng**:
  12. `s360.fact_so_evaluate_process_subject_criterion`: Đánh giá chi tiết từng tiêu chí phụ (Rubric).
  13. `s360.fact_so_subject_mastery`: Thống kê mức độ hoàn thành chuẩn đầu ra môn học.
* **Lý do chưa dùng**: Đánh giá Rubric quá chi tiết. Agent hiện tại chỉ cần truy vấn mức độ xếp loại môn tổng quan trong `fact_so_evaluate_process_subjects` là đủ đáp ứng nhu cầu báo cáo học tập.

---

### ⚪ Nhóm 5: Các Bảng Staging Trung Gian ETL (3 Bảng)
* **Danh sách bảng**:
  14. `default.stg_so_exam_moet_path`
  15. `default.stg_so_strand_path`
  16. `default.stg_so_students`
* **Lý do chưa dùng**: Bảng Staging tạm thời của Data Engineer khi xử lý dữ liệu đầu vào (ETL/ELT), không nằm trong mô hình Kho DWH phục vụ truy vấn báo cáo.

---

## 3. Lợi Ích Của Việc Tinh Gọn Cấu Trúc 25 Bảng Cho Text-to-SQL Agent

1. **Giảm Nhiễu (Noise Reduction)**: Tránh việc LLM (DeepSeek-v4-flash) chọn nhầm bảng Ngoại khóa hoặc Chuyên cần khi người dùng hỏi về Điểm số.
2. **Tăng Độ Chính Xác Đúp JOIN (Join Accuracy)**: LLM nắm bắt chính xác mối quan hệ giữa 6 Thang điểm, Bài thi định kỳ, Bài tập LMS và Sổ điểm Học bạ.
3. **Hiệu Năng Cao (Fast Latency)**: Prompt Schema gọn gàng giúp giảm số lượng token đầu vào, tăng tốc độ sinh câu lệnh SQL và giảm chi phí API.
