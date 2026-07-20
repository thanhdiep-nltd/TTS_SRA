# Hướng dẫn Giải thích và Suy luận Nghiệp vụ Toàn bộ Database (School Online Schema)
**Dự án:** VSF Student Risk Alert (VSF SRA)  
**Tài liệu gốc đối chiếu:** [`School Online Schema.csv`](file:///f:/PROJECT_VSF/TTS_SRA/docs_vsf/schemas/new/School%20Online%20Schema.csv)

---

Tài liệu này giải thích chi tiết **toàn bộ 36 bảng và các cột thông số** trong hệ thống cơ sở dữ liệu `School Online Schema` dựa trên phương pháp luận **phân tích ngôn ngữ học, quy ước đặt tên (Naming Conventions) và kiểu dữ liệu** chỉ từ file thô [`School Online Schema.csv`](file:///f:/PROJECT_VSF/TTS_SRA/docs_vsf/schemas/new/School%20Online%20Schema.csv) (không sử dụng các tài liệu đặc tả khác bên ngoài).

---

## I. PHƯƠNG PHÁP LUẬN SUY LUẬN NGÔN NGỮ HỌC & KIỂU DỮ LIỆU (METHODOLOGY)

Khi tiếp cận một file CSV thô chứa danh mục bảng và cột, ý nghĩa nghiệp vụ và chức năng của từng thực thể được giải mã thông qua việc bóc tách các thành phần cấu tạo nên tên gọi (tokens) và sự tương quan với kiểu dữ liệu của chúng:

### 1. Giải mã Tiền tố Tên bảng (Table Prefix)
*   **`stg_so_` (Staging School Online):** 
    *   *Từ khóa:* `stg` = Staging (kho chứa tạm thời/dữ liệu thô); `so` = School Online (nguồn gốc hệ thống).
    *   *Ý nghĩa:* Nơi tiếp nhận dữ liệu gốc nguyên bản, chưa qua xử lý làm sạch.
*   **`dim_` (Dimension - Chiều danh mục):** 
    *   *Từ khóa:* `dim` = Dimension (chiều thông tin).
    *   *Ý nghĩa:* Chứa thông tin danh mục thực thể cố định hoặc ít biến đổi (nhân sự, trường lớp, môn học).
*   **`fact_` (Fact - Sự kiện/Giao dịch):** 
    *   *Từ khóa:* `fact` = Thực tế/Sự kiện.
    *   *Ý nghĩa:* Chứa dữ liệu nhật ký giao dịch, điểm số, chuyên cần phát sinh liên tục trong quá trình vận hành trường học.
*   **`link_` (Liên kết trung gian):** 
    *   *Từ khóa:* `link` = Kết nối.
    *   *Ý nghĩa:* Giải quyết mối quan hệ nhiều - nhiều (N-N) giữa các thực thể lớn.

### 2. Giải mã Hậu tố & Từ khóa trong Tên cột (Column Keywords)
*   **`_id` (bigint / integer):** Khóa chính (Primary Key) hoặc khóa ngoại (Foreign Key) dùng để thiết lập mối quan hệ liên kết bảng.
*   **`_code` (varchar):** Mã định danh quản lý (như mã học sinh `student_code`, mã môn `subject_code`) dùng để tra cứu nhanh.
*   **`_name` / `_fullname` (varchar):** Tên hiển thị dạng chữ thân thiện với người dùng.
*   **`is_` / `ignore_` (integer / boolean):** Cờ logic (Flag). Kiểu `integer` có giá trị `1` (True - Đã kích hoạt/Đã xảy ra) và `0` (False - Chưa kích hoạt/Bình thường).
*   **`_date` (date) / `_time` (timestamp):** Ghi nhận mốc thời gian xảy ra hành động/sự kiện.
*   **`created_at` / `updated_at` (varchar / timestamp):** Trường theo dõi lịch sử hệ thống (audit trail metadata).

---

## II. GIẢI THÍCH CHI TIẾT CỦA CẢ 36 BẢNG DỮ LIỆU

Dưới đây là phân tích chi tiết ý nghĩa và cách suy luận cho toàn bộ 36 bảng dữ liệu có trong file CSV:

---

### PHÂN HỆ 1: DỮ LIỆU STAGING THÔ (default - 3 bảng)

#### 1. Bảng `default.stg_so_exam_moet_path`
*   **Chức năng:** Lưu trữ thông tin phân cấp (cây danh mục) thô của các mục sổ điểm MOET.
*   **Suy luận ý nghĩa từ các cột:**
    *   `gradebook_type_item_id` (bigint): ID định danh cột điểm.
    *   `parent_id` (bigint): ID của phần tử cha, chỉ ra cấu trúc đệ quy (cây phân cấp).
    *   `level` (integer): Cấp độ phân cấp (Ví dụ: khối -> môn -> kỳ thi).
    *   `path` & `id_path` (varchar): Lưu đường dẫn dạng chuỗi (ví dụ: `1/3/5`) để truy vấn nhanh cây phân cấp mà không cần duyệt đệ quy.

#### 2. Bảng `default.stg_so_strand_path`
*   **Chức năng:** Lưu cấu trúc phân cấp thô chương trình học tập (Môn học -> Mạch kiến thức/Strand).
*   **Suy luận ý nghĩa từ các cột:**
    *   `strand_id` (bigint) & `strand_name` (varchar): ID và tên của mạch kiến thức (chủ đề bài học).
    *   `subject_id` (integer) & `subject_name` (varchar): Liên kết trực tiếp mạch kiến thức này thuộc môn học nào.

#### 3. Bảng `default.stg_so_students`
*   **Chức năng:** Lưu giữ thông tin sơ bộ dạng mã thô của học sinh từ School Online.
*   **Suy luận ý nghĩa từ các cột:**
    *   `id` (decimal(20,0)): Khóa chính định danh học sinh.
    *   `code` (varchar): Mã số học sinh dùng để đối chiếu dữ liệu giữa các phân hệ.

---

### PHÂN HỆ 2: CHIỀU DANH MỤC NỀN TẢNG (s360 dim - 12 bảng)

#### 4. Bảng `s360.dim_behavior`
*   **Chức năng:** Danh mục tiêu chí hành vi rèn luyện (cộng/trừ điểm kỷ luật).
*   **Suy luận ý nghĩa từ các cột:**
    *   `point` (double): Điểm số thiết lập cho hành vi (dương là cộng, âm là trừ).
    *   `point_min` / `point_max` (integer): Phạm vi giới hạn điểm.
    *   `is_duplicate_behavior` (integer): Cờ logic xác định hành vi này có được tính lặp lại hay không.
    *   `is_apply_student` / `is_apply_teacher` (integer): Cờ logic xác định đối tượng áp dụng (1: áp dụng, 0: không áp dụng).

#### 5. Bảng `s360.dim_course`
*   **Chức năng:** Danh mục khóa học / lớp học phần môn học.
*   **Suy luận ý nghĩa từ các cột:**
    *   `grade_id`, `subject_id`, `homeroom_class_id` (integer): Liên kết lớp học phần này thuộc khối nào, môn nào và có liên kết với lớp chủ nhiệm nào.
    *   `max_student` (integer): Sĩ số tối đa học sinh được đăng ký học lớp này.
    *   `start_date` / `end_date` (date): Thời gian bắt đầu và kết thúc của học phần.
    *   `is_online_training` (integer): Cờ xác định lớp học online (LMS) hay offline.

#### 6. Bảng `s360.dim_exam`
*   **Chức năng:** Danh mục các kỳ thi và đầu điểm số.
*   **Suy luận ý nghĩa từ các cột:**
    *   `coefficient` (decimal): Hệ số điểm (nhân hệ số).
    *   `max_grade` (decimal): Thang điểm tối đa (thường là 10.0).
    *   `is_moet` (integer): Cờ xác định kỳ thi này có tuân theo chuẩn quy chế Bộ Giáo dục hay không.
    *   `is_periodic_exam` (integer): Cờ xác định kỳ thi định kỳ (giữa kỳ/cuối kỳ) hay kiểm tra thường xuyên.

#### 7. Bảng `s360.dim_exam_moet`
*   **Chức năng:** Danh mục các kỳ thi chuẩn hóa theo Bộ Giáo dục.
*   **Suy luận ý nghĩa từ các cột:**
    *   `moet_semester_index` (integer): Học kỳ 1 hoặc 2.
    *   `round_type` (integer): Quy tắc làm tròn điểm.
    *   `is_allow_input` (integer): Cờ cho phép nhập điểm vào cột này hay không.

#### 8. Bảng `s360.dim_extracurricular_activity`
*   **Chức năng:** Danh mục các hoạt động ngoại khóa của trường.
*   **Suy luận ý nghĩa từ các cột:**
    *   `original_price` & `price` (double): Chi phí gốc và chi phí thực tế sau khi áp dụng chính sách ưu đãi.
    *   `register_slots` & `max_register` (integer): Số chỗ đã đăng ký và số lượng đăng ký tối đa.
    *   `status` (varchar): Trạng thái hoạt động (đang mở đăng ký, đã đóng, đã hủy).

#### 9. Bảng `s360.dim_homeroom_class`
*   **Chức năng:** Danh mục lớp chủ nhiệm hành chính.
*   **Suy luận ý nghĩa từ các cột:**
    *   `homeroom_teacher_id` (bigint): ID giáo viên chủ nhiệm quản lý lớp.
    *   `is_bilingual` (integer): Lớp học hệ song ngữ hay hệ chuẩn.
    *   `status` (varchar): Trạng thái lớp (đang hoạt động, đã ra trường).

#### 10. Bảng `s360.dim_homeroom_class_student`
*   **Chức năng:** Sơ đồ kết nối học sinh vào từng lớp chủ nhiệm theo năm học.
*   **Suy luận ý nghĩa từ các cột:**
    *   `homeroom_class_id` & `student_id` (bigint): Cặp khóa ngoại xác định học sinh thuộc lớp nào.
    *   `campus_id` & `grade_id` (integer): Xác định cơ sở học và khối lớp học sinh đang học.
    *   `join_date` (date): Ngày học sinh chính thức vào lớp này.

#### 11. Bảng `s360.dim_school_year`
*   **Chức năng:** Danh mục niên khóa học đường.
*   **Suy luận ý nghĩa từ các cột:**
    *   `start_date` & `end_date` (date): Thời gian bắt đầu và kết thúc năm học.
    *   `is_current` (integer): Cờ logic đánh dấu năm học hiện tại đang chạy trên hệ thống.
    *   `is_locked_gradebook` (integer): Cờ khóa sổ điểm năm học (không cho sửa điểm cũ).

#### 12. Bảng `s360.dim_so_assignment`
*   **Chức năng:** Danh mục các bài tập về nhà / nhiệm vụ học tập trên hệ thống LMS.
*   **Suy luận ý nghĩa từ các cột:**
    *   `max_grade` (double): Điểm số tối đa của bài tập.
    *   `due_date` (date): Hạn nộp bài tập.
    *   `is_required` (integer): Bài tập bắt buộc hoàn thành hay tự chọn.

#### 13. Bảng `s360.dim_so_evaluate_progress`
*   **Chức năng:** Các mốc đánh giá tiến độ học tập định kỳ của học sinh.
*   **Suy luận ý nghĩa từ các cột:**
    *   `progress_code` & `progress_name` (varchar): Mã và tên mốc đánh giá (ví dụ: Đánh giá giữa kỳ, Đánh giá cuối kỳ).
    *   `is_active` (integer): Cờ xác định mốc đánh giá đang hoạt động.

#### 14. Bảng `s360.dim_so_school_mapping_subject`
*   **Chức năng:** Ánh xạ mã môn học của các trường thành môn học chuẩn.
*   **Suy luận ý nghĩa từ các cột:**
    *   `school_subject_code` (varchar) & `subject_id` (integer): Bản đồ ánh xạ mã môn viết tắt của từng trường cụ thể về ID môn học chuẩn chung của toàn hệ thống.

#### 15. Bảng `s360.dim_subject`
*   **Chức năng:** Danh mục môn học chuẩn của hệ thống.
*   **Suy luận ý nghĩa từ các cột:**
    *   `code` & `name` (varchar): Mã môn và tên môn (Toán, Lý, Hóa).
    *   `assessment_type` (varchar): Hình thức đánh giá (cho điểm hay nhận xét).
    *   `is_active` (integer): Trạng thái môn học có được giảng dạy hay không.

---

### PHÂN HỆ 3: NHẬT KÝ SỰ KIỆN & GIAO DỊCH (s360 fact/link - 20 bảng)

#### 16. Bảng `s360.fact_absent_logs`
*   **Chức năng:** Nhật ký xin nghỉ học và vắng mặt của học sinh.
*   **Suy luận ý nghĩa từ các cột:**
    *   `absent_date` (date): Ngày xin nghỉ.
    *   `is_allow` (integer): Cờ xác định nghỉ học có phép (1) hay không phép (0).
    *   `reason_category` (varchar): Danh mục lý do nghỉ (ốm, việc riêng).
    *   `is_auto_approve` (integer): Cờ xin nghỉ được duyệt tự động bởi hệ thống.

#### 17. Bảng `s360.fact_behavior_logs`
*   **Chức năng:** Nhật ký ghi nhận các hành vi rèn luyện thực tế của học sinh.
*   **Suy luận ý nghĩa từ các cột:**
    *   `behavior_id` (bigint): Liên kết với danh mục hành vi (`dim_behavior`).
    *   `student_code` (varchar): Học sinh vi phạm hoặc được khen thưởng.
    *   `point` (double): Số điểm rèn luyện thay đổi thực tế của lần ghi nhận này.

#### 18. Bảng `s360.fact_course_attendences`
*   **Chức năng:** Nhật ký điểm danh chuyên cần theo từng lớp học phần.
*   **Suy luận ý nghĩa từ các cột:**
    *   `course_id` (bigint): Lớp học phần thực hiện điểm danh.
    *   `attendance_status` (varchar): Trạng thái điểm danh (đi học, vắng mặt, đi muộn).
    *   `is_notify_parent` (integer): Cờ xác định hệ thống đã gửi thông báo chuyên cần về cho phụ huynh hay chưa.

#### 19. Bảng `s360.fact_course_enrolls`
*   **Chức năng:** Danh sách học sinh đăng ký tham gia lớp học phần môn học.
*   **Suy luận ý nghĩa từ các cột:**
    *   `course_id` & `student_id` (bigint): Xác định học sinh nào học lớp học phần nào.
    *   `role` (varchar): Vai trò tham gia (ví dụ: học sinh, trợ giảng).

#### 20. Bảng `s360.fact_extracurricular_activity_payments`
*   **Chức năng:** Nhật ký đóng tiền phí hoạt động ngoại khóa.
*   **Suy luận ý nghĩa từ các cột:**
    *   `amount` & `discount_amount` (double): Số tiền gốc và số tiền được giảm giá.
    *   `payment_status` (varchar): Trạng thái thanh toán (đã đóng, chưa đóng, hoàn phí).

#### 21. Bảng `s360.fact_extracurricular_activity_registers`
*   **Chức năng:** Nhật ký đăng ký tham gia hoạt động ngoại khóa của học sinh.
*   **Suy luận ý nghĩa từ các cột:**
    *   `activity_id` (bigint) & `student_code` (varchar): Liên kết học sinh đăng ký hoạt động ngoại khóa nào.
    *   `status` (varchar): Trạng thái đăng ký (chờ duyệt, đã duyệt, đã hủy).

#### 22. Bảng `s360.fact_gradebooks`
*   **Chức năng:** Sổ điểm học bạ môn học của học sinh (Lưu điểm theo dạng phẳng ngang).
*   **Suy luận ý nghĩa từ các cột:**
    *   `score_oral_1` -> `score_oral_5` (double): Các cột điểm miệng hệ số 1.
    *   `score_regular_1` -> `score_regular_5` (double): Các cột điểm kiểm tra thường xuyên hệ số 1.
    *   `score_midterm_1`, `score_midterm_2` (double): Điểm thi giữa kỳ (Hệ số 2).
    *   `score_final` (double): Điểm thi cuối kỳ (Hệ số 3).
    *   `gpa` (double): Điểm trung bình môn học tự động tính toán.

#### 23. Bảng `s360.fact_gradebooks_moet`
*   **Chức năng:** Sổ điểm làm tròn và định dạng chuẩn Bộ Giáo dục (MOET).
*   **Suy luận ý nghĩa từ các cột:**
    *   Chứa các trường tương tự như bảng `fact_gradebooks` nhưng có thêm hậu tố `_moet` và cột `round_grade` (điểm đã làm tròn) nhằm tuân thủ quy chế kiểm tra học sinh.

#### 24. Bảng `s360.fact_overall_academic_records`
*   **Chức năng:** Học bạ tổng hợp kết quả học tập toàn diện của học sinh theo từng học kỳ/năm học.
*   **Suy luận ý nghĩa từ các cột:**
    *   `gpa` (double): Điểm trung bình tổng kết cả học kỳ/năm học.
    *   `conduct` (varchar): Xếp loại hạnh kiểm (Tốt, Khá, Trung bình, Yếu).
    *   `total_absent` (integer): Tổng số ngày học sinh nghỉ học trong kỳ.
    *   `is_passed` (integer): Cờ logic xác định học sinh có đủ điều kiện lên lớp hay không.

#### 25. Bảng `s360.fact_so_absent_extract_late`
*   **Chức năng:** Nhật ký tổng hợp chuyên cần (nghỉ học, đi muộn, về sớm) theo chu kỳ tuần/tháng.
*   **Suy luận ý nghĩa từ các cột:**
    *   `absent_date` (date): Ngày vắng học.
    *   `week_start` & `month_start` (date): Ngày bắt đầu của tuần và tháng xảy ra sự kiện để thực hiện gom dữ liệu làm biểu đồ báo cáo chuyên cần theo chu kỳ.

#### 26. Bảng `s360.fact_so_assignment_grade`
*   **Chức năng:** Sổ điểm chấm bài tập (Assignment) của học sinh trên LMS.
*   **Suy luận ý nghĩa từ các cột:**
    *   `assignment_id` (bigint): Bài tập được chấm.
    *   `final_grade` (decimal): Điểm số bài tập đạt được.
    *   `comment` (varchar): Nhận xét bài làm của giáo viên.

#### 27. Bảng `s360.fact_so_class_attendance_statistics`
*   **Chức năng:** Bảng thống kê điểm danh chuyên cần của học sinh theo ngày.
*   **Suy luận ý nghĩa từ các cột:**
    *   `total_lesson` (integer): Tổng số tiết học trong ngày.
    *   `lesson_attend` & `lesson_not_attend` (integer): Số tiết đi học thực tế và số tiết nghỉ học trong ngày đó.

#### 28. Bảng `s360.fact_so_daily_attendance`
*   **Chức năng:** Điểm danh học đường hàng ngày của học sinh.
*   **Suy luận ý nghĩa từ các cột:**
    *   `attendance_date` (date): Ngày điểm danh.
    *   `is_absent` (integer): Cờ xác định học sinh có vắng mặt trong ngày hay không.

#### 29. Bảng `s360.fact_so_evaluate_process_subject_criterion`
*   **Chức năng:** Kết quả đánh giá tiến trình học tập chi tiết của học sinh theo từng tiêu chí môn học.
*   **Suy luận ý nghĩa từ các cột:**
    *   `criterion_code` & `criterion_name` (varchar): Mã và tên tiêu chí đánh giá môn học.
    *   `evaluate_status` (varchar): Trạng thái đánh giá tiêu chí (Đạt / Chưa đạt / Cần cố gắng).

#### 30. Bảng `s360.fact_so_evaluate_process_subjects`
*   **Chức năng:** Báo cáo đánh giá tiến trình học tập môn học tổng quát theo các mốc thời gian.
*   **Suy luận ý nghĩa từ các cột:**
    *   `evaluate_comment` (varchar): Nhận xét tổng quan của giáo viên bộ môn.
    *   `improve_plan` (varchar): Kế hoạch cải thiện kết quả học tập của học sinh.

#### 31. Bảng `s360.fact_so_homeroom_class_attendances`
*   **Chức năng:** Nhật ký điểm danh chuyên cần tại các buổi sinh hoạt lớp chủ nhiệm hàng ngày.
*   **Suy luận ý nghĩa từ các cột:**
    *   `attendance_date` (date): Ngày điểm danh.
    *   `is_absent` (integer): Cờ vắng mặt.
    *   `is_boarding` (integer): Cờ xác định học sinh có ăn bán trú tại trường ngày hôm đó hay không.

#### 32. Bảng `s360.fact_so_homeroom_class_late_attendances`
*   **Chức năng:** Nhật ký chi tiết các ca đi học muộn ghi nhận bởi giáo viên chủ nhiệm.
*   **Suy luận ý nghĩa từ các cột:**
    *   `attendance_time` (timestamp): Thời gian thực tế học sinh bước vào lớp.
    *   `time_late` (integer): Số phút học sinh đi học muộn.
    *   `is_late` (integer): Cờ logic xác định trạng thái đi muộn.
    *   `image_path` (varchar): Đường dẫn ảnh minh chứng đi muộn hoặc giấy phép đi muộn của phụ huynh.

#### 33. Bảng `s360.fact_so_subject_mastery`
*   **Chức năng:** Thống kê mức độ hoàn thành và đạt chuẩn đầu ra môn học của học sinh.
*   **Suy luận ý nghĩa từ các cột:**
    *   `percent_target_min` / `percent_target_max` (double): Tỷ lệ phần trăm tối thiểu và tối đa đạt mục tiêu chuẩn đầu ra.
    *   `final_grade_level` (varchar): Mức độ xếp loại đạt chuẩn môn học (Hoàn thành tốt / Đạt / Chưa đạt).

#### 34. Bảng `s360.fact_subject_academic_records`
*   **Chức năng:** Kết quả học tập tổng kết của học sinh chi tiết theo từng môn học cuối kỳ/năm.
*   **Suy luận ý nghĩa từ các cột:**
    *   `s1_final_grade` & `s2_final_grade` (decimal): Điểm tổng kết môn học ở Học kỳ 1 và Học kỳ 2.
    *   `final_grade_after_summer` (decimal): Điểm thi lại sau hè (nếu điểm kỳ chính thức bị trượt).
    *   `is_after_summer` (integer): Cờ logic xác định điểm này có phải là điểm thi lại sau hè hay không.

#### 35. Bảng `s360.link_register_payment`
*   **Chức năng:** Bảng liên kết trung gian giữa đăng ký ngoại khóa và hóa đơn thanh toán ngoại khóa.
*   **Suy luận ý nghĩa từ các cột:**
    *   `register_id` & `payment_id` (integer): Cặp khóa ngoại thực hiện liên kết N-N.

---

### PHÂN HỆ 4: CHIỀU PHÂN CÔNG GIẢI THUYẾT/NHÂN SỰ (t360 - 1 bảng)

#### 36. Bảng `t360.dim_t360_homeroom_class_teacher`
*   **Chức năng:** Danh mục phân công giáo viên làm chủ nhiệm hoặc giảng dạy chính theo lớp, năm học và cơ sở.
*   **Suy luận ý nghĩa từ các cột:**
    *   `homeroom_teacher_id` (decimal(20,0)) & `teacher_code` (varchar): Xác định giáo viên được phân công.
    *   `homeroom_class_id` (bigint) & `class_code` (varchar): Xác định lớp chủ nhiệm được phân công giảng dạy.
    *   `teacher_type` (varchar): Loại phân công (Giáo viên chủ nhiệm - GVCN hoặc Giáo viên bộ môn - GVBM).
    *   `is_moved_out` (integer): Cờ giáo viên đã kết thúc nhiệm vụ giảng dạy hoặc chuyển lớp học phần.