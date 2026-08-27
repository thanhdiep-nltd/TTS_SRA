Hiện tượng học sinh mở tab bài tập trên hệ thống LMS rồi bỏ đi làm việc khác (hoặc ngược lại: bấm chọn đáp án bừa bãi chỉ sau vài giây) là dạng **nhiễu hành vi (Off-task Behavior / Aberrant Response Behavior)** rất phổ biến trong đánh giá trực tuyến. Nếu đưa trực tiếp dữ liệu thô này vào để tính toán độ khó của câu hỏi ($b_i$) hay năng lực người học ($\theta$), mô hình đo lường sẽ bị sai lệch nghiêm trọng.

Để xử lý và loại trừ nhiễu này một cách triệt để, bạn có thể triển khai hệ thống lọc đa tầng theo các giải pháp dưới đây:

---

### 1. Thu thập vi dữ liệu hành vi trên giao diện (Frontend Telemetry)

Thay vì chỉ ghi nhận thời gian bắt đầu và thời gian nộp bài tổng quát (`Elapsed Time`), hệ thống LMS cần bóc tách được **Thời gian tương tác thực tế (Active Time on Task)** thông qua các sự kiện trình duyệt:

* **Bắt sự kiện chuyển tab (Page Visibility API):** Lắng nghe sự kiện `visibilitychange`, `window.onblur` và `window.onfocus`. Ngay khi học sinh chuyển sang tab khác hoặc thu nhỏ trình duyệt, bộ đếm thời gian làm bài của câu hỏi đó sẽ tự động tạm dừng (pause) và ghi nhận cờ `tab_hidden = true`.
* **Phát hiện trạng thái bất hoạt (Idle Detection):** Theo dõi các tương tác vi mô gồm di chuyển chuột (`mousemove`), cuộn trang (`scroll`), nhấn phím (`keydown`) hoặc chạm màn hình (`touchstart`). Nếu trong khoảng thời gian nhất định (ví dụ $45$–$60$ giây) không có bất kỳ tương tác nào, hệ thống chuyển sang trạng thái chờ (idle) và không cộng dồn thời gian này vào thời gian suy nghĩ của câu hỏi.
* **Thời gian tương tác thực (Active Dwell Time):** Chỉ tính toán thời gian học sinh thực sự tương tác với nội dung của câu hỏi cụ thể, loại bỏ hoàn toàn khoảng thời gian "treo máy".

---

### 2. Lọc nhiễu theo Mô hình Thời gian Phản hồi (Psychometric Response Time Filtering)

Dựa trên lý thuyết đo lường khảo thí hiện đại (đặc biệt là mô hình thời gian phản hồi Log-normal của *Wim van der Linden*), thời gian làm bài thực tế của một câu hỏi tuân theo phân phối chuẩn sau khi logarit hóa:

$$\ln(T_{ij}) \sim \mathcal{N}(\beta_i - \tau_j, \alpha_i^{-2})$$

Trong đó $T_{ij}$ là thời gian học sinh $j$ làm câu $i$, $\beta_i$ là cường độ thời gian của câu hỏi, $\tau_j$ là tốc độ thao tác của học sinh, và $\alpha_i$ là độ phân biệt thời gian. Từ đây, hệ thống thiết lập hai ngưỡng lọc nhiễu tự động:

* **Xử lý ngưỡng trên (Off-task / Outlier Threshold):**
* Những lượt làm bài có thời gian $T_{ij} > \mu_i + 3\sigma_i$ (hoặc vượt ngưỡng $Q_3 + 1.5 \times \text{IQR}$) của câu hỏi đó sẽ bị xếp vào diện bất thường.


* Dữ liệu thời gian này sẽ được cắt tỉa (Winsorization) hoặc đưa về giá trị chặn trên tối đa, không để một vài lượt làm bài hàng tiếng đồng hồ kéo tụt tốc độ giải trung bình của câu hỏi.


* **Xử lý ngưỡng dưới (Rapid-Guessing Behavior):**
* Nếu học sinh nộp bài câu hỏi nhanh bất thường (ví dụ: dưới $10\%$ thời gian đọc hiểu trung bình hoặc dưới 3 giây đối với câu hỏi lý thuyết dài), hành vi này được xác định là đoán mò vô thức (Rapid Guessing).




* **Chỉ số Nỗ lực Thời gian Phản hồi (Response Time Effort - RTE):**
* Gán nhãn cho từng câu trả lời: chỉ những câu nào có thời gian nằm trong khoảng hợp lý $[T_{\text{min}}, T_{\text{max}}]$ mới được tính là có sự nỗ lực làm bài thực chất ($\text{RTE} = 1$).





---

### 3. Hiệu chỉnh dữ liệu khi nạp vào Mô hình Đánh giá Độ khó (Bayesian IRT Cleansing)

Khi nạp dữ liệu LMS vào thuật toán để cập nhật tham số độ khó của đề thi, các bản ghi bị gắn cờ nhiễu sẽ được xử lý qua 3 phương án:

| Loại Nhiễu | Biểu Hiện Trên Dữ Liệu | Cách Hệ Thống Xử Lý Trước Khi Tính Độ Khó |
| --- | --- | --- |
| **Bỏ máy đi làm việc khác (Idle / Off-task)** | Thời gian làm câu hỏi kéo dài bất thường; có nhiều sự kiện rời tab. | Tách lấy `Active Time` thay vì `Total Time`; nếu thời gian chờ quá dài dẫn đến bài làm bị đứt quãng, bản ghi câu đó được xem là khuyết thiếu ngẫu nhiên (Missing at Random - MAR) thay vì tính là câu quá khó.

 |
| **Đoán mò siêu tốc (Rapid Guessing)** | Chọn đáp án trong vòng 1–3 giây mà không cần đọc đề. | Loại bỏ (Exclude) câu trả lời này khỏi tập dữ liệu huấn luyện của câu hỏi đó, vì nó không phản ánh năng lực $\theta$ của học sinh lẫn độ khó $b_i$ của câu hỏi.

 |
| **Làm bài nghiêm túc (Effortful Response)** | Thời gian nằm trong phân phối chuẩn, có tương tác chuột/cuộn đều đặn. | Giữ nguyên dữ liệu để đưa vào hàm khả dĩ Bayesian IRT cập nhật tham số $b_i$ và phân tích chất lượng phương án sai.

 |

---

### 4. Đối soát chéo với Bài thi trên lớp (Triangulation)

Vì bài tập về nhà trên LMS không có giám sát trực tiếp, hệ thống dùng **kết quả từ các cột điểm thi trên lớp** (môi trường có giám sát, học sinh làm bài tập trung cao độ) để làm mỏ neo hiệu chuẩn.

Nếu một câu hỏi trên LMS có tỷ lệ làm sai cao bất thường nhưng thời gian ghi nhận bị phân tán mạnh (dấu hiệu của việc làm bài đối phó hoặc bỏ tab), mô hình Bayesian sẽ ưu tiên trọng số tiên nghiệm từ LLM/Giáo trình và dữ liệu thi trên lớp hơn là để dữ liệu nhiễu từ LMS làm biến dạng độ khó của câu hỏi.