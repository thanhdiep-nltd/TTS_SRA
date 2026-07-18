# Tài liệu Yêu cầu Sản phẩm (Product Requirements Document - PRD)
## Dự án: Hệ Thống Cảnh Báo Sớm Học Sinh Có Nguy Cơ Sư Phạm (VSF Student Risk Alert - VSF SRA)

---

## 1. Tổng quan sản phẩm
Hệ thống VSF Student Risk Alert (VSF SRA) là giải pháp phân tích học thuật (Learning Analytics) sử dụng AI Agent để cảnh báo sớm các nguy cơ học tập và rèn luyện của học sinh K-12. Hệ thống giúp Ban Giám Hiệu và Giáo viên chủ động đưa ra các quyết định can thiệp sư phạm kịp thời dựa trên bằng chứng dữ liệu, thay thế cho quy trình báo cáo thủ công trễ hạn.

---

## 2. Đối tượng người dùng và Phân quyền (RBAC)
Hệ thống hỗ trợ xác thực JWT và phân quyền đa vai trò (Role-Based Access Control) cho 3 nhóm đối tượng người dùng chính:
- **Ban Giám Hiệu (Hiệu trưởng / Hiệu phó):**
  - Xem dashboard vĩ mô toàn trường (read-only đối với dữ liệu điểm số).
  - Sử dụng trợ lý AI hỏi đáp tiếng Việt để tra cứu dữ liệu tổng hợp.
- **Giáo viên chủ nhiệm & Giáo viên bộ môn:**
  - Quản lý, nhập/sửa điểm số học sinh thuộc lớp/môn phụ trách.
  - Tải lên đề thi và tài liệu môn học để chạy OCR và RAG phân tích.
  - Theo dõi danh sách học sinh có nguy cơ thuộc lớp chủ nhiệm hoặc bộ môn mình dạy để can thiệp kịp thời.
- **Admin Hệ thống (System Admin):**
  - Giám sát kỹ thuật và theo dõi các metrics vận hành của hệ thống (độ trễ phản hồi, độ chính xác của AI Agent, thống kê đánh giá/phản hồi chất lượng từ người dùng cuối) thông qua giao diện quản trị `/admin/ai-metrics`.

---

## 3. Yêu cầu Chức năng 

### 3.1. Module Text-to-Query (Hỏi đáp ngôn ngữ tự nhiên)
- **Yêu cầu:** 
  - Tiếp nhận câu hỏi ngôn ngữ tự nhiên tiếng Việt về kết quả học tập từ BGH và dịch thành câu lệnh truy vấn dữ liệu (SQL cho PostgreSQL hoặc Pandas Query).
  - Tích hợp lớp kiểm tra AST (`SQLGlot`) để chặn toàn bộ các lệnh thay đổi dữ liệu (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`).
  - Áp dụng Row-Level Security (RLS) bằng cách tự động chèn tham số `school_id` của người dùng vào câu truy vấn trước khi thực thi để cách ly dữ liệu.

### 3.2. Module Phân tích Yếu tố Tác động & Các Mô hình Học thuật
- **Yêu cầu tích hợp dữ liệu:**
  - Hệ thống tự động thu thập và phân tích **6 nhóm yếu tố đầu vào** từ cơ sở dữ liệu làm biến số dự báo:
    1. *Điểm số:* Lịch sử điểm số từ học bạ và sổ điểm (`fact_gradebooks`, `fact_subject_academic_records`).
    2. *Mức độ hoàn thành bài tập / LMS:* Điểm số, tỷ lệ nộp bài tập tự học (`fact_so_assignment_grade`).
    3. *Chuyên cần:* Số buổi vắng mặt có/không phép, đi muộn (`fact_absent_logs`, `fact_so_daily_attendance`).
    4. *Hành vi rèn luyện:* Điểm cộng/trừ hành vi (`fact_behavior_logs`) hoặc các trường hợp chăm sóc đặc biệt (trầm cảm, bệnh lý mãn tính,…).
    5. *Khảo sát học sinh:* Mức độ hài lòng của học sinh đối với môi trường học tập.
    6. *Biến cố gia đình:* Thông tin biến cố gia đình tác động đến tâm lý học sinh.
- **Các mô hình toán / học máy bắt buộc:**
  *Lưu ý quan trọng: Các mô hình toán và học máy dưới đây hiện chỉ mang tính chất **dự thảo đề xuất (proposed drafts)**, chưa được xác nhận chính thức sẽ sử dụng trong bài toán thực tế. Các tham số, trọng số hoặc mô hình có thể được thêm bớt hoặc thay đổi linh hoạt tùy thuộc vào mức độ đầy đủ của dữ liệu thu thập được để tránh phát sinh khối lượng công việc dư thừa. Các công thức toán học chi tiết hiện được ẩn đi bằng comment.*
  
  - **Mô hình dự báo nguy cơ học thuật sớm ($P(Fail)$):** Dự đoán xác suất học sinh trượt môn ($P(Fail) \ge 0.7$) trước khi diễn ra các kỳ thi lớn (ví dụ: trước kỳ thi học kỳ) dựa trên dữ liệu điểm số thường xuyên, lịch sử học tập và chuyên cần để tự động gắn cờ cảnh báo (Đỏ/Vàng) giúp giáo viên kịp thời can thiệp.
    <!--
    Công thức toán học dự thảo:
    $$P(Fail_i) = \sigma(w_1 \cdot TX_{mean, i} + w_2 \cdot LMS_{score, i} + w_3 \cdot Absent_{rate, i} + w_4 \cdot Behavior_{score, i} + b)$$
    Trong đó \sigma(x) = \frac{1}{1 + e^{-x}} là hàm kích hoạt Sigmoid quy đổi xác suất về khoảng [0, 1].
    -->
    
  - **Phân cụm học sinh đa chiều bằng NMF (Non-negative Matrix Factorization):** Phân tích và phân rã ma trận đặc trưng hợp nhất bao gồm: **Ma trận điểm số + Ma trận hành vi rèn luyện + Ma trận tác động ngoại cảnh** của học sinh để nhóm học sinh thành 4 cụm mô thức học tập thực tế: Consistent Achievers (Ổn định), Procrastinators (Trì hoãn bứt phá), High-effort Low-performance (Chăm chỉ nhưng thi kém), High-risk Learners (Sa sút liên tục).
    <!--
    Công thức phân rã ma trận dự thảo:
    $$V_{N \times M} \approx W_{N \times K} \times H_{K \times M}$$
    Hàm mục tiêu cực tiểu hóa chuẩn Frobenius dưới ràng buộc không âm:
    $$\min_{W, H \ge 0} \|V - WH\|_F^2 = \min_{W, H \ge 0} \sum_{i,j} (V_{ij} - (WH)_{ij})^2$$
    -->
    
  - **Mô hình dự báo học lực cơ bản:** Dự báo xu hướng kết quả học tập thông qua Hồi quy tuyến tính hoặc LLM-based forecasting kết hợp các yếu tố hành vi/chuyên cần định tính để chỉ ra chiều hướng học tập đi lên hoặc đi xuống.
    <!--
    Công thức hồi quy tuyến tính dự thảo:
    y = \beta x + \alpha với hệ số góc \beta đo tốc độ sa sút (\beta < 0) hoặc tiến bộ học lực (\beta > 0).
    -->

### 3.3. Module Multi-Agent System 
- **Kiến trúc:** Đồ thị trạng thái tuần hoàn (StateGraph) trên LangGraph được điều phối bởi **Supervisor Agent** (Tác tử giám sát):
  - *Data Agent:* Phục vụ truy xuất thông tin thô của học sinh, lớp học, điểm số.
  - *Stat Agent:* Thực hiện tính toán thống kê sâu.
  - *Report Agent:* Tự động sinh báo cáo hành chính (PDF/Word) kèm biểu đồ trực quan.
  - *Prediction Agent:* Thực thi mô hình dự báo học lực và xác định mức độ nguy cơ.
- **Phân quyền cho Data Agent:** 
  - Data Agent tuân thủ nghiêm ngặt cơ chế phân quyền RBAC của hệ thống (ADMIN/PRINCIPAL/GRADE_HEAD/HOMEROOM/SUBJECT_TEACHER/SUBJECT_HEAD).
  - Data Agent sử dụng Token xác thực của người dùng hiện tại để thực thi truy vấn, đảm bảo cách ly dữ liệu và không xảy ra đọc vượt quyền.

### 3.4. Module RAG + LLM & OCR 
- **Pipeline RAG & OCR 1 (Ingestion):** Quét giáo trình, sách giáo khoa, đề cương môn học dạng PDF/Ảnh -> OCR trích xuất văn bản -> Chunking & Embedding -> Lưu trữ vào **Qdrant Vector Database** phục vụ làm cơ sở tri thức đối chiếu.
- **Pipeline RAG & OCR 2 (Exam Analysis):** Nhận file đề thi do giáo viên tải lên -> OCR trích xuất đề thi -> LLM đối chiếu với tri thức giáo trình trong Qdrant -> Đánh giá mức độ bám sát chương trình, phân loại Bloom các câu hỏi (Nhận biết, Thông hiểu, Vận dụng, Vận dụng cao) và xuất chỉ số độ khó đề thi (CDI - Content Difficulty Index).
- **Quy định Giới hạn Tài liệu Tải lên (Rate Limiting & File Constraints):**
  - Định dạng file được hỗ trợ: `.pdf`, `.png`, `.jpg`, `.jpeg`.
  - Giới hạn dung lượng: Tối đa 25MB đối với file PDF và tối đa 10MB đối với file hình ảnh.
---


## 4. Yêu cầu Phi chức năng

### 4.1. Bảo mật
- Toàn bộ các API được bảo vệ bằng mã hóa JWT Token.
- SQL Validator phải đảm bảo 100% không cho phép SQL Injection hoặc thực thi các lệnh thay đổi dữ liệu (`INSERT/UPDATE/DELETE`).
- Dữ liệu giữa các trường học (school) phải được cách ly tuyệt đối ở tầng cơ sở dữ liệu và API truy vấn thông qua bộ lọc `school_id`.

### 4.2. Thiết kế Dữ liệu linh hoạt
- ERD cơ sở dữ liệu phải cho phép lưu trữ và chuyển đổi linh hoạt giữa nhiều chuẩn điểm: hệ điểm 10, hệ điểm 6, hệ điểm chữ (A, B, C...), hoặc định tính Đạt/Chưa đạt để hệ thống chạy ổn định cho các chương trình đào tạo khác nhau.

### 4.3. Triển khai
- Ứng dụng phải hỗ trợ đóng gói bằng Docker và triển khai dễ dàng lên các nền tảng đám mây (như Railway hoặc Render).

### 4.4. Giới hạn chi phí và tối ưu LLM
- Áp dụng **cơ chế Cache Prompt** (lưu trữ tạm thời System Prompts, cấu trúc DB, và nội dung giáo trình mẫu) cho các API truy vấn LLM để tối ưu hóa chi phí token đầu vào (giảm 50-80% lượng token lặp lại) và tăng tốc phản hồi.
