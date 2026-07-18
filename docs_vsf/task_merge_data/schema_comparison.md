# Báo cáo So sánh và Phân tích Cấu trúc Database (Schema Comparison)
**Dự án:** VSF Student Risk Alert (VSF SRA)  
**Tác giả:** AI Assistant  
**Ngày lập:** 18/07/2026

---

## 1. Tổng quan số lượng bảng dữ liệu
Hệ thống bao gồm hai nguồn cấu trúc cơ sở dữ liệu cần đối chiếu:
*   **Dự án cũ (`schema.sql`):** Gồm **23 bảng** dữ liệu, tất cả nằm trong schema mặc định (`public`). Tập trung vào quản lý kết quả học tập tổng hợp của từng môn học và phân tích độ khó đề thi.
*   **Dự án mới (`school_online_schema.sql`):** Gồm **36 bảng** dữ liệu, được chia làm **3 schema** nghiệp vụ:
    *   `default`: 3 bảng staging dữ liệu thô.
    *   `s360`: 32 bảng chính (Dimension và Fact) phục vụ phân tích học tập toàn diện.
    *   `t360`: 1 bảng quản lý phân công giáo viên chủ nhiệm.

---

## 2. Phân nhóm các bảng chung lĩnh vực nghiệp vụ (Mapping)

Dưới đây là sơ đồ ánh xạ (mapping) các thực thể tương đồng giữa hai hệ thống để phục vụ việc tích hợp:

### 2.1. Lĩnh vực Cơ cấu Trường lớp (School & Class Structure)
*   **Cũ:** `academic_years`, `semesters`, `grades`, `classes`
*   **Mới:** `dim_school_year`, `dim_homeroom_class`
*   **Đặc tính & So sánh:**
    *   Cơ chế quản lý năm học và học kỳ ở DB cũ được chia thành 2 bảng (`academic_years` và `semesters`). Ở DB mới tích hợp trực tiếp năm học vào bảng chiều `dim_school_year`.
    *   Bảng khối lớp (`grades`) ở DB mới được đơn giản hóa thành thuộc tính trong bảng lớp chủ nhiệm hoặc học phần thay vì tách bảng riêng.

### 2.2. Lĩnh vực Học sinh & Phân lớp (Students & Homeroom Class)
*   **Cũ:** `students`, `enrollments`
*   **Mới:** `stg_so_students` (staging), `dim_homeroom_class_student`
*   **Đặc tính & So sánh:**
    *   Hệ thống cũ quản lý học sinh thuộc lớp nào thông qua bảng trung gian `enrollments` (1 dòng cho mỗi niên khóa học sinh ở một lớp).
    *   Hệ thống mới quản lý thông qua bảng chiều `dim_homeroom_class_student`, bổ sung thêm các trường chi tiết như cơ sở học (`campus`), trạng thái học tập (đang học, bảo lưu, chuyển trường) và ngày gia nhập lớp.

### 2.3. Lĩnh vực Môn học (Subjects)
*   **Cũ:** `subjects`
*   **Mới:** `dim_subject`, `dim_so_school_mapping_subject`
*   **Đặc tính & So sánh:**
    *   Hệ thống cũ quản lý danh mục môn học chung cho toàn trường.
    *   Hệ thống mới bổ sung thêm bảng ánh xạ môn học `dim_so_school_mapping_subject`. Điều này rất quan trọng khi triển khai đa trường (multi-school), cho phép map tên môn viết tắt hoặc môn học tự chọn của từng trường cụ thể về danh mục môn học chuẩn chung.

### 2.4. Lĩnh vực Điểm số và Đánh giá (Scores & Gradebooks)
*   **Cũ:** `scores`, `subject_evaluations`, `student_term_reports`
*   **Mới:** `fact_gradebooks`, `fact_gradebooks_moet`, `fact_subject_academic_records`, `fact_overall_academic_records`, `dim_so_evaluate_progress`, `fact_so_evaluate_process_subjects`, `fact_so_evaluate_process_subject_criterion`
*   **Đặc tính & So sánh:**
    *   Cả hai hệ thống đều phân loại điểm thành 4 nhóm chính: Kiểm tra miệng (Oral), Kiểm tra thường xuyên (Regular), Giữa kỳ (Midterm), và Cuối kỳ (Final).
    *   Hệ thống mới bổ sung phân hệ đánh giá tiến trình học tập chuyên sâu (`fact_so_evaluate_process_subjects`) lưu nhận xét, đánh giá chi tiết theo từng tiêu chí môn học của giáo viên bộ môn và kế hoạch cải thiện của học sinh.

### 2.5. Lĩnh vực Đề thi & Khung chương trình (Exams & Curriculum)
*   **Cũ:** `exam_papers`, `curriculum_units`, `exam_competencies`, `exam_column_mappings`
*   **Mới:** `dim_exam`, `dim_exam_moet`, `stg_so_exam_moet_path`, `stg_so_strand_path`
*   **Đặc tính & So sánh:**
    *   Hệ thống cũ quản lý siêu dữ liệu (metadata) của các file đề thi thực tế (PDF/Word), độ khó ước lượng và phân phối Bloom để AI phân tích RAG.
    *   Hệ thống mới quản lý danh mục và phân cấp các đầu điểm thi chuẩn hóa theo Bộ Giáo dục (MOET) thông qua bảng `dim_exam` và `dim_exam_moet`.

---

## 3. Các phân hệ nghiệp vụ MỚI HOÀN TOÀN (Chỉ có ở DB mới)

Các bảng này cung cấp dữ liệu đầu vào quan trọng cho hệ thống **VSF SRA** nhằm xây dựng các chỉ số dự báo rủi ro học sinh (như bỏ học, trượt môn, kỷ luật):

1.  **Phân hệ Chuyên cần & Điểm danh (6 bảng):**
    *   *Các bảng:* `fact_absent_logs`, `fact_so_daily_attendance`, `fact_so_class_attendance_statistics`, `fact_so_absent_extract_late`, `fact_so_homeroom_class_attendances`, `fact_so_homeroom_class_late_attendances`.
    *   *Mục đích:* Thống kê chi tiết số tiết nghỉ học, đi muộn, về sớm theo ngày/tuần/tháng. Đây là chỉ số trực tiếp cấu thành nguy cơ rủi ro bỏ học học đường.
2.  **Phân hệ Hành vi & Kỷ luật (2 bảng):**
    *   *Các bảng:* `dim_behavior`, `fact_behavior_logs`.
    *   *Mục đích:* Lưu lịch sử các hành vi vi phạm kỷ luật của học sinh (như quậy phá, chuyên cần kém, hoặc tuyên dương). Phục vụ đắc lực cho mô hình phân cụm học sinh đa chiều (NMF).
3.  **Phân hệ Hoạt động ngoại khóa & Tài chính (4 bảng):**
    *   *Các bảng:* `dim_extracurricular_activity`, `fact_extracurricular_activity_registers`, `fact_extracurricular_activity_payments`, `link_register_payment`.
    *   *Mục đích:* Đánh giá mức độ năng động, hòa nhập cộng đồng và rủi ro tài chính học phí của học sinh.

---

## 4. Các điểm xung đột cấu trúc (Conflicts) chi tiết

Khi tiến hành gộp hoặc chuyển đổi dữ liệu (Merge Data), cần đặc biệt xử lý các điểm xung đột thiết kế cốt lõi sau:

### Conflict 1: Lớp chủ nhiệm (Homeroom Class) vs Lớp học phần (Course Class)
*   **Chi tiết xung đột:**
    *   Hệ thống cũ chỉ định nghĩa một bảng `classes` chung. Học sinh thuộc lớp nào sẽ học cố định mọi môn tại lớp đó.
    *   Hệ thống mới tách biệt hoàn toàn: **Lớp chủ nhiệm** (`dim_homeroom_class`) quản lý mặt hành chính, chuyên cần chung và hạnh kiểm; còn **Lớp học phần** (`dim_course`) quản lý việc giảng dạy các môn học cụ thể (học sinh lớp 9A có thể học lớp học phần Toán nâng cao với học sinh lớp 9B).
*   **Hệ quả:** Logic cũ truy cập trực tiếp điểm số qua `class_id` của lớp chủ nhiệm sẽ bị sai lệch.
*   **Giải pháp:** Phải viết lại các câu lệnh SQL truy vấn kết quả học tập để đi qua bảng liên kết học phần `fact_course_enrolls` và lấy điểm danh từ `fact_course_attendences`.

### Conflict 2: Cấu trúc lưu trữ Điểm số (Row-based vs Column-based)
*   **Chi tiết xung đột:**
    *   Bảng cũ `scores` lưu trữ điểm số theo cấu trúc **dọc (Row-based)**:
        *   Mỗi điểm số của học sinh cho một môn học/loại điểm/cột điểm là một dòng bản ghi riêng biệt.
    *   Bảng mới `fact_gradebooks` / `fact_gradebooks_moet` lưu theo cấu trúc **ngang/phẳng (Column-based)**:
        *   Mỗi học sinh chỉ có một bản ghi duy nhất cho mỗi môn học trong một học kỳ. Các cột điểm (TX1, TX2, giữa kỳ, cuối kỳ) được thiết kế thành các cột cụ thể nằm trên cùng một dòng.
*   **Hệ quả:** Các hàm tính điểm trung bình (như hàm `calc_subject_average` viết bằng PL/pgSQL ở hệ thống cũ) và logic truy cập điểm của AI Agent sẽ bị lỗi hoàn toàn nếu không được sửa đổi câu lệnh SQL.
*   **Giải pháp:** Thiết kế lại tầng Data Access Object (DAO) của AI Agent để truy xuất dữ liệu điểm số từ các cột phẳng của bảng `fact_gradebooks` hoặc viết một View trung gian để convert ngược lại dạng dọc phục vụ mô hình học máy.

### Conflict 3: Cơ chế biểu diễn cây kiến thức môn học (Curriculum representation)
*   **Chi tiết xung đột:**
    *   Hệ thống cũ sử dụng bảng đệ quy `curriculum_units` thông qua trường liên kết `parent_id` để xây dựng cây bài học và chuẩn đầu ra môn học.
    *   Hệ thống mới lưu dạng cấu trúc Materialized Path thông qua bảng `stg_so_strand_path` (các cột `level`, `path`, `id_path`) và liên kết trực tiếp mức độ thành thạo của học sinh qua `fact_so_subject_mastery`.
*   **Giải pháp:** Chuyển đổi dữ liệu cây đệ quy cũ sang dạng đường dẫn phẳng (Path) để nạp vào hệ thống mới.

### Conflict 4: Phân quyền & Phân công giáo viên (Teacher Assignments)
*   **Chi tiết xung đột:**
    *   Bảng cũ `teacher_assignments` quản lý tập trung mọi loại vai trò phân quyền (chủ nhiệm cấp 1, khối trưởng, giáo viên bộ môn, chủ nhiệm cấp 2, trưởng bộ môn) bằng một bảng kết hợp check constraint.
    *   Hệ thống mới chia việc quản lý: Phân công chủ nhiệm nằm ở bảng `dim_t360_homeroom_class_teacher`, còn phân công giảng dạy môn học nằm trực tiếp trong thuộc tính giáo viên phụ trách của lớp học phần (`dim_course`).
*   **Giải pháp:** Khi migrate thông tin giáo viên, cần phân tách bản ghi cũ thành hai luồng nạp dữ liệu vào hai thực thể mới tương ứng.

---

## 5. Khuyến nghị triển khai gộp dữ liệu (Merge Data Recommendations)

1.  **Bước 1: Chuẩn hóa thực thể nền tảng (Dimensions)**
    *   Đồng bộ danh sách Trường học (`schools`), Năm học/Học kỳ (`dim_school_year`), Lớp chủ nhiệm (`dim_homeroom_class`), Học sinh (`stg_so_students` -> `dim_homeroom_class_student`).
2.  **Bước 2: Chuyển đổi cấu trúc điểm số (ETL Scores)**
    *   Viết một script chuyển đổi dữ liệu (ETL script) để gom (aggregate) các bản ghi dạng dọc của bảng `scores` cũ thành các bản ghi dạng ngang phẳng của bảng `fact_gradebooks` mới.
3.  **Bước 3: Tích hợp logic AI Agent**
    *   Cập nhật cấu hình mô hình Text-to-SQL (SQLGlot) để ánh xạ các từ khóa hỏi đáp về chuyên cần và hành vi vào các phân hệ bảng mới (`fact_absent_logs`, `fact_behavior_logs`).
    *   Điều chỉnh tác tử dự báo rủi ro học tập (`Prediction Agent`) chuyển sang đọc dữ liệu điểm số tổng hợp từ `fact_gradebooks` và tích hợp thêm trọng số chuyên cần từ `fact_so_class_attendance_statistics`.
