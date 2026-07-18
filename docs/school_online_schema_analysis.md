# Tài liệu Cấu trúc Database - School Online Schema

Tài liệu này liệt kê chi tiết toàn bộ các bảng dữ liệu có trong file [School Online Schema.csv](file:///f:/PROJECT_VINUNI/BUILD_COHORT/C2-App-051/docs/School%20Online%20Schema.csv), được phân loại theo **Schema** và **Loại bảng** (Staging, Dimension, Fact, Link) nhằm phục vụ việc tích hợp và phân tích dữ liệu học tập.

---

## 1. Schema `default` (Dữ liệu Staging / Dữ liệu thô)

Các bảng trong schema này đóng vai trò là nơi tiếp nhận dữ liệu thô (Staging) từ hệ thống nguồn trước khi được chuẩn hóa và đưa vào kho dữ liệu.

| Tên bảng | Số lượng cột | Chức năng chi tiết |
| :--- | :---: | :--- |
| `stg_so_exam_moet_path` | 6 | Lưu trữ thông tin phân cấp (cây danh mục) của các mục trong loại sổ điểm MOET. Phục vụ việc xác định mối quan hệ cha-con (level, path, id_path). |
| `stg_so_strand_path` | 8 | Lưu cấu trúc phân cấp chương trình học tập (Môn học -> Chủ đề kiến thức/Strand). Phục vụ việc theo dõi cây kiến thức và chuẩn đầu ra môn học. |
| `stg_so_students` | 2 | Bảng staging lưu giữ thông tin sơ bộ của học sinh gồm mã học sinh (`code`) và ID hệ thống để phục vụ đối chiếu dữ liệu. |

---

## 2. Schema `s360` (Dimension & Fact Tables)

Đây là schema chính của Kho dữ liệu (DWH), được thiết kế theo mô hình hình sao (Star Schema) phục vụ phân tích 360 độ về học sinh.

### A. Nhóm bảng Chiều (Dimension Tables)
Lưu giữ thông tin danh mục, cấu trúc nền tảng của trường học.

| Tên bảng | Số lượng cột | Chức năng chi tiết |
| :--- | :---: | :--- |
| `dim_behavior` | 19 | Danh mục các hành vi rèn luyện (tiêu chí cộng/trừ điểm). Lưu trữ điểm mặc định, khoảng điểm, phạm vi áp dụng (học sinh, giáo viên, lớp chủ nhiệm) và cách thức xử lý trùng lặp hành vi. |
| `dim_course` | 21 | Danh mục khóa học / lớp học phần của trường học. Chứa thông tin về môn học, năm học, khối lớp, giáo viên phụ trách, thời gian bắt đầu/kết thúc và sĩ số tối đa. |
| `dim_exam` | 26 | Danh mục các kỳ thi và đầu điểm (Regular, Midterm, Final). Chứa thông tin về hệ số điểm, điểm tối đa, kỳ thi có chuẩn MOET không, và cấu trúc phân cấp kỳ thi. |
| `dim_exam_moet` | 28 | Danh mục chi tiết các đầu điểm chuẩn hóa theo quy định của Bộ Giáo dục (MOET), quản lý phân cấp đầu điểm, hệ số, kỳ học và thiết lập cho phép nhập điểm/ánh xạ điểm. |
| `dim_extracurricular_activity` | 49 | Danh mục các hoạt động ngoại khóa của trường. Quản lý chi phí, hạn đăng ký, đối tượng áp dụng, sĩ số tối đa và trạng thái của hoạt động theo từng học kỳ. |
| `dim_homeroom_class` | 16 | Danh mục các lớp chủ nhiệm của trường học. Lưu thông tin giáo viên chủ nhiệm, hội trưởng phụ huynh, trạng thái lớp (song ngữ/chuẩn) và năm học. |
| `dim_homeroom_class_student` | 26 | Danh sách liên kết học sinh với lớp chủ nhiệm của từng niên khóa. Quản lý thông tin trạng thái học tập của học sinh tại lớp, cơ sở học (campus), khối lớp và ngày gia nhập lớp. |
| `dim_school_year` | 13 | Danh mục năm học học đường. Lưu ngày bắt đầu/kết thúc năm học, trạng thái khóa sổ điểm/học bạ và năm học hiện tại. |
| `dim_so_assignment` | 27 | Danh mục bài tập / nhiệm vụ học tập được giao cho học sinh. Lưu thông tin điểm tối đa, hạn nộp, liên kết với cột điểm trong sổ điểm, và trạng thái khóa bài tập. |
| `dim_so_evaluate_progress` | 37 | Thông tin đánh giá tổng kết tiến độ học tập của học sinh. Lưu kết quả học lực, hạnh kiểm, ý kiến nhận xét của giáo viên chủ nhiệm và phản hồi từ phụ huynh. |
| `dim_so_school_mapping_subject` | 7 | Bảng ánh xạ cấu trúc môn học của từng trường theo khối lớp, lớp chủ nhiệm và năm học để định nghĩa khung chương trình học áp dụng. |
| `dim_subject` | 14 | Danh mục môn học chính thức của trường. Quản lý mã môn, tên tiếng Anh/Việt, cấp học áp dụng, hình thức đánh giá (cho điểm hay nhận xét) và tích hợp đồng bộ LMS. |

### B. Nhóm bảng Sự kiện (Fact Tables & Link Tables)
Lưu trữ các giao dịch, lịch sử học tập, chuyên cần, rèn luyện và điểm số của học sinh.

| Tên bảng | Số lượng cột | Chức năng chi tiết |
| :--- | :---: | :--- |
| `fact_absent_logs` | 21 | Nhật ký chi tiết đơn xin nghỉ học của học sinh. Lưu lý do vắng mặt, mốc thời gian, trạng thái phê duyệt (tự động duyệt hay giáo viên duyệt) và thông tin tiết nghỉ học. |
| `fact_behavior_logs` | 20 | Nhật ký ghi nhận các hành vi rèn luyện của học sinh. Ghi nhận thời gian, mã hành vi, giáo viên đánh giá, điểm số thay đổi và hình thức kỷ luật đi kèm (nếu có). |
| `fact_course_attendences` | 17 | Nhật ký điểm danh chuyên cần theo từng tiết học của các lớp học phần. Quản lý trạng thái đi học, đi muộn, vắng mặt, ghi chú của giáo viên và đồng bộ thông báo tới phụ huynh. |
| `fact_course_enrolls` | 9 | Nhật ký ghi nhận học sinh đăng ký học phần (Course). Lưu trữ vai trò tham gia (học sinh/trợ giảng) và trạng thái chuyển lớp. |
| `fact_extracurricular_activity_payments` | 16 | Dữ liệu giao dịch đóng tiền hoạt động ngoại khóa. Lưu giá gốc, giảm giá theo hạng thành viên Vinclub, số tiền thực tế phải nộp và trạng thái thanh toán. |
| `fact_extracurricular_activity_registers` | 19 | Danh sách đăng ký tham gia ngoại khóa của học sinh. Quản lý trạng thái duyệt đăng ký, số tiền đã đóng, ghi chú hoàn trả học phí. |
| `fact_gradebooks` | 25 | Bảng điểm tổng hợp (Sổ điểm học bạ) của học sinh theo từng môn học và kỳ học. Quản lý điểm số cuối cùng, trạng thái khóa điểm theo kỳ và nguồn gốc dữ liệu. |
| `fact_gradebooks_moet` | 32 | Sổ điểm chuẩn hóa theo quy định của Bộ Giáo dục (MOET) dành cho học sinh. Lưu kết quả điểm, comment nhận xét chi tiết, và trạng thái khóa/phê duyệt điểm của từng đầu điểm. |
| `fact_overall_academic_records` | 64 | Học bạ tổng kết kết quả học tập toàn diện của học sinh theo từng năm học. Gồm điểm trung bình HK1/HK2/Cả năm, học lực, hạnh kiểm, số ngày nghỉ học, nhận xét của hiệu trưởng và trạng thái xét tốt nghiệp/lên lớp. |
| `fact_so_absent_extract_late` | 20 | Bảng tổng hợp thống kê dữ liệu nghỉ học và đi muộn của học sinh theo chu kỳ tuần/tháng/kỳ học để làm báo cáo chuyên cần. |
| `fact_so_assignment_grade` | 17 | Bảng ghi nhận kết quả điểm số bài tập (Assignment) được giáo viên chấm. Lưu điểm số, nhận xét chi tiết, trạng thái khóa điểm và đồng bộ thông báo. |
| `fact_so_class_attendance_statistics` | 17 | Bảng thống kê điểm danh chuyên cần của học sinh theo ngày (tổng số tiết trong ngày, số tiết tham gia, số tiết vắng mặt). |
| `fact_so_daily_attendance` | 25 | Bảng thống kê điểm danh môn học theo ngày của học sinh. Tính tổng số tiết vắng có phép/không phép và cờ đánh dấu vắng mặt. |
| `fact_so_evaluate_process_subject_criterion` | 20 | Kết quả đánh giá chi tiết của học sinh theo từng tiêu chí cụ thể của môn học (đối với các lớp đánh giá năng lực chi tiết). |
| `fact_so_evaluate_process_subjects` | 32 | Báo cáo đánh giá tiến trình học tập môn học định kỳ. Chứa đánh giá tổng quát, kế hoạch cải thiện của học sinh/giáo viên, và phê duyệt điểm của bộ môn. |
| `fact_so_homeroom_class_attendances` | 22 | Nhật ký điểm danh lớp chủ nhiệm hàng ngày vào đầu giờ. Quản lý đi học, vắng mặt, ăn bán trú, trạng thái khóa dữ liệu và đồng bộ app. |
| `fact_so_homeroom_class_late_attendances` | 29 | Nhật ký chi tiết các ca đi muộn lớp chủ nhiệm. Quản lý mốc thời gian đi muộn, lý do đi muộn, minh chứng bằng hình ảnh và trạng thái xử lý đi muộn. |
| `fact_so_subject_mastery` | 16 | Thống kê mức độ hoàn thành chuẩn đầu ra môn học của học sinh. Lưu điểm trung bình môn học, xếp loại học tập, tỷ lệ phần trăm đạt mục tiêu tối thiểu/vượt mức. |
| `fact_subject_academic_records` | 16 | Kết quả học tập tổng kết của học sinh chi tiết theo từng môn học (ĐTB HK1, HK2, cả năm, thi lại sau hè) để liên kết vào phiếu học bạ tổng hợp. |
| `link_register_payment` | 5 | Bảng trung gian liên kết giữa thông tin đăng ký ngoại khóa (`register_id`) và thông tin thanh toán (`payment_id`). |

---

## 3. Schema `t360` (Dimension Phân công Giáo viên)

Schema này lưu trữ các chiều phân công giáo viên theo cấu trúc DWH 360 độ của trường học.

| Tên bảng | Số lượng cột | Chức năng chi tiết |
| :--- | :---: | :--- |
| `dim_t360_homeroom_class_teacher` | 20 | Danh mục phân công giáo viên chủ nhiệm hoặc giáo viên giảng dạy chính theo lớp, năm học và cơ sở trường (campus). Phục vụ việc theo dõi lịch sử giảng dạy và chuyển giao trách nhiệm. |
