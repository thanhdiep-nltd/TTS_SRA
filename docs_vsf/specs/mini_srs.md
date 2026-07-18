# Tài liệu Đặc tả Yêu cầu Rút gọn (mini-SRS)
## Dự án: Hệ Thống Cảnh Báo Sớm Học Sinh Có Nguy Cơ Sư Phạm (VSF Student Risk Alert - VSF SRA)

---

## 1. Giới thiệu dự án
Hệ thống VSF Student Risk Alert (VSF SRA) là một giải pháp AI Agent kết hợp Phân tích học thuật (Learning Analytics) hỗ trợ Ban Giám Hiệu và Giáo viên các trường phổ thông (K-12) phát hiện sớm các nguy cơ học thuật/sư phạm của học sinh. Khác với các hệ thống quản lý điểm số tĩnh truyền thống, VSF SRA áp dụng các thuật toán phân tích học máy và thống kê nâng cao từ dữ liệu điểm số, chuyên cần và hành vi rèn luyện nhằm đưa ra cảnh báo kịp thời và đề xuất giải pháp phụ đạo sư phạm nhân văn, tích cực.

---

## 2. Đối tượng sử dụng (User Roles)
Hệ thống xác định rõ 3 đối tượng người dùng chính tham gia vận hành và khai thác:
- **Ban Giám Hiệu (PRINCIPAL):**
  - Xem các báo cáo trực quan và dashboard vĩ mô toàn trường (read-only đối với dữ liệu điểm số).
  - Tương tác với trợ lý AI bằng câu hỏi tiếng Việt để truy xuất dữ liệu tổng hợp.
- **Giáo viên (CHỦ NHIỆM / BỘ MÔN):**
  - Xem danh sách cảnh báo học sinh có nguy cơ thuộc lớp chủ nhiệm hoặc các môn học mình giảng dạy.
  - Nhập, chỉnh sửa điểm số học sinh thuộc lớp/môn học được phân công.
  - Tải lên đề thi, giáo trình học tập của môn học để AI hỗ trợ phân tích ma trận kiến thức và độ khó.
- **Admin Hệ thống (SYSTEM ADMIN):**
  - Giám sát kỹ thuật toàn bộ hệ thống.
  - Theo dõi metrics vận hành của hệ thống (đo lường độ trễ phản hồi, độ chính xác của AI Agent, thống kê đánh giá/phản hồi chất lượng từ người dùng cuối) thông qua giao diện quản trị `/admin/ai-metrics`.

---

## 3. Mô hình Dữ liệu linh hoạt (Flexible Grading Model)
Để đảm bảo khả năng mở rộng cho nhiều trường học với các quy chế đánh giá khác nhau, hệ thống được thiết kế phi cứng nhắc (polymorphic):
- **Hỗ trợ đa trường/cơ sở (Multi-school/Multi-campus):** Cách ly dữ liệu theo từng trường thông qua cơ chế chèn tự động điều kiện `school_id`.
- **Hỗ trợ nhiều thang điểm và chuẩn đánh giá học thuật:**
  - *Thang điểm số:* Hệ 10 (Thông tư 22/2021/TT-BGDĐT kết hợp điểm số và nhận xét), Hệ 6 (quy chuẩn quốc tế), hoặc các hệ điểm số khác.
  - *Thang điểm chữ:* Hệ chữ A, B, C, D, F... dành cho các chương trình đào tạo quốc tế hoặc song ngữ.
  - *Đánh giá định tính:* Thang đánh giá Đạt (Pass) / Chưa đạt (Fail) dành cho các môn thể chất, nghệ thuật, trải nghiệm hướng nghiệp.
- **Ánh xạ thang điểm quy chuẩn:** Cơ chế tự động chuẩn hóa các hệ điểm về phân phối chuẩn chuẩn hóa ($Z$-score) để phục vụ các thuật toán phân tích nâng cao một cách nhất quán.

---

## 4. Kiến trúc Hệ thống & Yêu cầu Chức năng (Functional Requirements)

### Module 1: Text-to-Query (Hỏi đáp dữ liệu học tập)
- **Chức năng:** Cho phép Ban Giám Hiệu nhập câu hỏi bằng ngôn ngữ tự nhiên tiếng Việt (Ví dụ: *"Lớp 10A1 học kỳ 1 có bao nhiêu học sinh có nguy cơ trượt môn Toán?"*) và tự động dịch thành câu lệnh truy vấn dữ liệu (SQL cho PostgreSQL hoặc Pandas Query).
- **Rào chắn an ninh (Guardrails):**
  - Sử dụng AST parser (`SQLGlot`) để quét và chặn toàn bộ các câu lệnh gây thay đổi dữ liệu (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`).
  - Chỉ cho phép các lệnh `SELECT` thuộc danh sách bảng được phân quyền (whitelist).
  - Tự động bắt buộc thêm điều kiện lọc `school_id` tương ứng với quyền truy cập của người dùng để tránh rò rỉ dữ liệu chéo giữa các trường học.

### Module 2: Multi-Agent System (Hệ thống đa tác tử)
- **Kiến trúc:** Đồ thị trạng thái tuần hoàn (StateGraph) trên LangGraph dưới sự điều phối của một **Supervisor Agent** (Tác tử giám sát) phân phối nhiệm vụ cho các tác tử chuyên biệt:
  - *Data Agent:* Phụ trách tra cứu, kiểm toán và hiển thị dữ liệu học sinh, lớp học, điểm số thô.
  - *Stat Agent:* Tính toán các chỉ số thống kê toán học sư phạm nâng cao.
  - *Report Agent:* Tổng hợp kết quả, kết xuất các biểu đồ trực quan và sinh báo cáo tự động (PDF/Word).
  - *Prediction Agent:* Dự báo xu hướng học lực và đánh giá nguy cơ học thuật.
- **Phân quyền dữ liệu cho Data Agent:** 
  - Data Agent tuân thủ nghiêm ngặt cơ chế phân quyền RBAC của hệ thống (ADMIN/PRINCIPAL/GRADE_HEAD/HOMEROOM/SUBJECT_TEACHER/SUBJECT_HEAD).
  - Data Agent chỉ được phép truy vấn dữ liệu thông qua Token xác thực của người dùng hiện tại, tự động giới hạn phạm vi truy xuất (ví dụ: GV bộ môn chỉ được phép đọc điểm của học sinh thuộc các lớp mình trực tiếp giảng dạy).

### Module 3: RAG + LLM (Phân tích Đề thi và Giáo trình)
- **Quy trình luồng xử lý RAG (RAG Ingestion & Query Flow):**
  1. Ban Giám Hiệu hoặc Giáo viên tải lên các tài liệu nền tảng (sách giáo khoa, giáo trình môn học, đề cương ôn tập mẫu) dưới dạng file PDF hoặc hình ảnh.
  2. Hệ thống kích hoạt module OCR để bóc tách văn bản thô, dọn dẹp dữ liệu nhiễu, chia nhỏ văn bản (chunking), tạo vector nhúng (embedding).
  3. Các vector này được lưu trữ tập trung vào **Qdrant Vector Database**.
  4. Khi giáo viên tải một đề thi mới lên để kiểm định, hệ thống thực thi OCR đề thi đó và truy vấn Vector DB Qdrant để so khớp, đối chiếu với tri thức giáo trình, xếp loại Bloom các câu hỏi và chấm chỉ số độ khó đề thi (CDI - Content Difficulty Index).
- **Quy định Giới hạn Tài liệu Tải lên (Rate Limiting & File Constraints):**
  - Định dạng file được hỗ trợ: `.pdf`, `.png`, `.jpg`, `.jpeg`.
  - Giới hạn dung lượng: Tối đa 25MB đối với file PDF và tối đa 10MB đối với file hình ảnh.

### Module 4: OCR (Optical Character Recognition)
- **Chức năng:** Trích xuất văn bản từ hình ảnh và PDF scan, được tích hợp trong hai pipeline:
  - *Pipeline Ingestion (Xử lý giáo trình):* Số hóa giáo trình học tập phục vụ nạp tri thức Vector DB phục vụ RAG.
  - *Pipeline Exam Analysis (Xử lý đề thi):* Số hóa đề kiểm tra do giáo viên tải lên để làm đầu vào so khớp và phân loại Bloom.

---

## 5. Các Thuật toán Phân tích Học thuật (Academic Algorithms)

> [!NOTE]
> **Lưu ý quan trọng:** Các mô hình toán và học máy dưới đây hiện chỉ mang tính chất **dự thảo đề xuất (proposed drafts)**, chưa được xác nhận chính thức sẽ sử dụng trong bài toán thực tế. Các tham số, trọng số hoặc mô hình có thể được thêm bớt hoặc thay đổi linh hoạt tùy thuộc vào mức độ đầy đủ của dữ liệu thu thập được để tránh phát sinh khối lượng công việc dư thừa. Các công thức toán học chi tiết hiện được ẩn đi để phục vụ việc thống nhất sau này.

Hệ thống thu thập và phân tích **6 nhóm yếu tố đầu vào (Input Features)** từ cơ sở dữ liệu làm biến số dự báo:
1. **Điểm số:** Lịch sử điểm số từ học bạ và sổ điểm (`fact_gradebooks`, `fact_subject_academic_records`).
2. **Mức độ hoàn thành bài tập / LMS:** Tỷ lệ nộp bài và điểm số các bài tập tự học (`fact_so_assignment_grade`).
3. **Chuyên cần:** Tỷ lệ nghỉ học có phép/không phép, đi muộn học đường (`fact_absent_logs`, `fact_so_daily_attendance`).
4. **Hành vi rèn luyện:** Ghi nhận điểm rèn luyện, vi phạm kỷ luật hoặc hồ sơ chăm sóc đặc biệt (`fact_behavior_logs`).
5. **Khảo sát học sinh:** Mức độ hài lòng của học sinh đối với môi trường học tập.
6. **Biến cố gia đình:** Các thông tin đột xuất về hoàn cảnh gia đình tác động đến tâm lý học sinh.

### 5.1. Dự báo nguy cơ học thuật sớm ($P(Fail)$)
Dự báo xác suất trượt môn hoặc sa sút học tập nghiêm trọng của học sinh trước khi diễn ra các kỳ thi lớn (ví dụ trước thi học kỳ) dựa trên dữ liệu điểm số thường xuyên, lịch sử học tập và chuyên cần nhằm giúp giáo viên kịp thời can thiệp sư phạm. Nếu xác suất dự báo vượt ngưỡng quy định ($\ge 0.7$), hệ thống sẽ tự động gắn cờ Đỏ (nguy cơ cao) trên Dashboard.
<!--
Công thức toán học dự thảo:
$$P(Fail_i) = \sigma(w_1 \cdot TX_{mean, i} + w_2 \cdot LMS_{score, i} + w_3 \cdot Absent_{rate, i} + w_4 \cdot Behavior_{score, i} + b)$$
Trong đó \sigma(x) = \frac{1}{1 + e^{-x}} là hàm kích hoạt Sigmoid quy đổi xác suất về khoảng [0, 1].
-->

### 5.2. Phân cụm Học sinh đa chiều bằng NMF (Non-negative Matrix Factorization)
Phân cụm đa chiều bằng cách phân tích và phân rã ma trận đặc trưng hợp nhất bao gồm: **Ma trận điểm số + Ma trận hành vi rèn luyện + Ma trận tác động ngoại cảnh** của học sinh. 
Thuật toán phân tách học sinh thành 4 cụm mô thức học tập thực tế: Consistent Achievers (Ổn định), Procrastinators (Trì hoãn bứt phá), High-effort Low-performance (Chăm chỉ nhưng thi kém), và High-risk Learners (Sa sút liên tục).
<!--
Công thức phân rã ma trận dự thảo:
$$V_{N \times M} \approx W_{N \times K} \times H_{K \times M}$$
Hàm mục tiêu cực tiểu hóa chuẩn Frobenius dưới ràng buộc không âm:
$$\min_{W, H \ge 0} \|V - WH\|_F^2 = \min_{W, H \ge 0} \sum_{i=1}^{N} \sum_{j=1}^{M} \left( V_{ij} - \sum_{k=1}^{K} W_{ik} H_{kj} \right)^2$$
-->

### 5.3. Mô hình dự báo học lực cơ bản (Trend/Regression hoặc LLM-based forecasting)
- **Phương pháp thống kê/hồi quy (Trend/Regression):** Sử dụng hồi quy tuyến tính trên chuỗi điểm trung bình theo thời gian để tính toán hệ số góc (độ dốc) đo xu hướng tiến bộ (hệ số dương) hoặc sa sút học lực (hệ số âm).
- **Phương pháp AI (LLM-based forecasting):** Sử dụng Large Language Model (LLM) để tổng hợp các đặc trưng định tính (hành vi rèn luyện, chuyên cần, biến cố gia đình) kết hợp với chuỗi điểm số lịch sử nhằm sinh ra các nhận định dự báo xu hướng học lực của học kỳ tiếp theo.
<!--
Công thức hồi quy tuyến tính dự thảo:
$$y = \beta x + \alpha$$
Trong đó x là chuỗi thời gian các cột điểm, y là điểm số tương ứng, \beta là hệ số góc.
-->

---

## 6. Yêu cầu Phi chức năng (Non-Functional Requirements)

- **Bảo mật dữ liệu:** 
  - Mã hóa 100% các API giao tiếp bằng JWT Token.
  - Phân tách và cách ly dữ liệu đa trường tuyệt đối ở tầng CSDL bằng tham số `school_id`.
- **Giới hạn chi phí và tối ưu LLM:**
  - Áp dụng **cơ chế Cache Prompt** (lưu trữ tạm thời System Prompts, cấu trúc DB, và nội dung giáo trình mẫu) cho các API truy vấn LLM. Cơ chế này giúp tối ưu hóa chi phí token đầu vào (giảm tới 50-80% chi phí token lặp lại) và tăng tốc độ xử lý các câu hỏi liên tiếp của người dùng.
