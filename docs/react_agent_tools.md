# Tài liệu Tools của ReAct Agent (Trợ Lý A.I EduOwl)

Tài liệu này giới thiệu chi tiết về hệ thống **Tools (Công cụ)** của AI Agent sử dụng mô hình lập luận và hành động **ReAct (Reason + Act)** được xây dựng bằng **LangGraph** trong thư mục `src/`.

---

## 1. Tổng quan về ReAct Agent & Cơ chế Hoạt động

### 1.1. Luồng ReAct (Reason + Act) trong LangGraph
Agent của chúng ta hoạt động dưới dạng một đồ thị trạng thái tuần hoàn (StateGraph) được cấu hình tại [graph.py](file:///f:/PROJECT_VINUNI/BUILD_COHORT/C2-App-051/src/agents/graph.py). Luồng hoạt động gồm các bước:
1. **Nhận yêu cầu:** Người dùng gửi câu hỏi (ví dụ: *"So sánh lớp 8A1 và 8A2 môn Toán học kỳ 1 năm 2023"*).
2. **Suy luận (Agent Node):** Agent sử dụng System Prompt [SYSTEM_PROMPT](file:///f:/PROJECT_VINUNI/BUILD_COHORT/C2-App-051/src/agents/graph.py#L38-L62) để suy nghĩ xem có cần gọi công cụ nào không.
3. **Hành động (Tools Node):** Nếu LLM quyết định gọi một hoặc nhiều công cụ, đồ thị sẽ chuyển nhánh sang node `tools` để thực thi hàm tương ứng với các đối số do LLM tạo ra.
4. **Cập nhật & Phản hồi:** Kết quả của tool được ghi lại vào lịch sử tin nhắn trong `AgentState`. Agent tiếp tục suy luận dựa trên kết quả đó. Nếu đã đủ thông tin, Agent sẽ kết luận và trả về câu trả lời cuối cùng cho người dùng.

### 1.2. Cơ chế Bảo mật và Cách ly Dữ liệu (Multi-tenancy Scoping)
Để đảm bảo an toàn thông tin giữa các trường học khác nhau, hệ thống sử dụng cơ chế truyền ngữ cảnh bảo mật qua `ContextVar` tại [grade_tools.py](file:///f:/PROJECT_VINUNI/BUILD_COHORT/C2-App-051/src/agents/tools/grade_tools.py#L11-L12):
* `current_user_school_id`: Lưu ID của trường học của người dùng hiện tại đang đăng nhập.
* `current_user_role`: Lưu vai trò của người dùng (ví dụ: `TEACHER`, `PRINCIPAL`, `ADMIN`).

Trước khi gọi Agent thực thi thông qua API `/chat` tại [routes.py](file:///f:/PROJECT_VINUNI/BUILD_COHORT/C2-App-051/src/api/routes.py#L12-L57), thông tin này được lấy từ đối tượng `CurrentUser` và gán vào ngữ cảnh an toàn. Tất cả các tool liên quan tới cơ sở dữ liệu sẽ tự động lấy `school_id = current_user_school_id.get()` để lọc phạm vi truy vấn (scope check), ngăn chặn việc truy xuất dữ liệu chéo giữa các trường học.

---

## 2. Chi tiết Danh sách 11 Tools của Agent

Toàn bộ các tool nghiệp vụ chính được định nghĩa tại [grade_tools.py](file:///f:/PROJECT_VINUNI/BUILD_COHORT/C2-App-051/src/agents/tools/grade_tools.py).

### Nhóm 1: Truy vấn thông tin học sinh & Điểm số cá nhân

#### 1. `get_student_info(name_or_id: str) -> str`
* **Mô tả:** Tìm kiếm thông tin cá nhân của học sinh trong trường dựa trên Họ tên hoặc Mã học sinh.
* **Tham số:**
  * `name_or_id` (str): Họ tên học sinh (ví dụ: `Ngô Ngọc Hoa`) hoặc Mã học sinh (ví dụ: `2502151184`).
* **Đầu ra:** Chuỗi JSON chứa danh sách các học sinh khớp thông tin.
* **Dữ liệu trả về mẫu:**
  ```json
  [
    {
      "Mã học sinh": "2502151184",
      "Họ và Tên": "Ngô Ngọc Hoa",
      "Ngày sinh": "2010-05-12",
      "Lớp (HK gần nhất)": "8A1",
      "Niên khóa (Năm vào trường)": 2022
    }
  ]
  ```

#### 2. `get_student_grades(student_id: str, year: int = None, semester: int = None, subject: str = None) -> str`
* **Mô tả:** Tra cứu điểm số chi tiết của một học sinh theo Mã học sinh và các bộ lọc tùy chọn.
* **Tham số:**
  * `student_id` (str): Mã học sinh (10 chữ số).
  * `year` (int, tùy chọn): Năm học bắt đầu (ví dụ: `2023` đại diện cho năm học `2023-2024`).
  * `semester` (int, tùy chọn): Học kỳ (`1` hoặc `2`).
  * `subject` (str, tùy chọn): Tên môn học cần lọc (ví dụ: `Toán học`).
* **Đầu ra:** Chuỗi JSON chứa danh sách điểm số chi tiết bao gồm điểm thường xuyên (TX1-TX4), giữa kỳ (GK), cuối kỳ (CK), điểm trung bình môn học kỳ (ĐTB) tính theo thuật toán và xếp loại học lực theo thông tư GDPT 2018.

---

### Nhóm 2: Báo cáo & Thống kê theo Lớp và Khối

#### 3. `get_class_grades(class_name: str, year: int, semester: int, subject: str = None) -> str`
* **Mô tả:** Tra cứu danh sách điểm trung bình môn học kỳ của tất cả học sinh trong một lớp học cụ thể.
* **Tham số:**
  * `class_name` (str): Tên lớp học (ví dụ: `6A1`, `10A2`).
  * `year` (int): Năm học bắt đầu (ví dụ: `2023`).
  * `semester` (int): Học kỳ (`1` hoặc `2`).
  * `subject` (str, tùy chọn): Tên môn học cần lọc.
* **Đầu ra:** Chuỗi JSON chứa danh sách điểm số trung bình học kỳ của từng học sinh trong lớp đối với các môn học tương ứng.

#### 4. `calculate_grade_statistics(class_name: str = None, grade_level: int = None, year: int = None, semester: int = None, subject: str = None) -> str`
* **Mô tả:** Tính toán các thống kê học tập (Điểm trung bình, Cao nhất, Thấp nhất, Phân bố học lực) của một lớp hoặc toàn bộ khối lớp.
* **Tham số:**
  * `class_name` (str, tùy chọn): Tên lớp học.
  * `grade_level` (int, tùy chọn): Khối lớp (`6` đến `12`).
  * `year` (int, tùy chọn): Năm học bắt đầu.
  * `semester` (int, tùy chọn): Học kỳ (`1` hoặc `2`).
  * `subject` (str, tùy chọn): Tên môn học.
* **Đầu ra:** Chuỗi JSON chứa thống kê chi tiết.
* **Dữ liệu trả về mẫu:**
  ```json
  {
    "Tổng số bản ghi điểm học sinh": 35,
    "Điểm trung bình (ĐTB)": 7.45,
    "Điểm cao nhất": 9.8,
    "Điểm thấp nhất": 4.2,
    "Phân phối học lực": {
      "Tốt": 15,
      "Khá": 12,
      "Đạt": 6,
      "Chưa đạt": 2
    }
  }
  ```

#### 5. `find_top_students(year: int, semester: int, class_name: str = None, grade_level: int = None, subject: str = None, limit: int = 5) -> str`
* **Mô tả:** Tìm danh sách những học sinh có điểm số cao nhất (Thủ khoa, top học sinh giỏi) theo lớp hoặc theo khối.
* **Tham số:**
  * `year` (int), `semester` (int): Năm học và Học kỳ bắt buộc.
  * `class_name` (str, tùy chọn), `grade_level` (int, tùy chọn): Bộ lọc lớp hoặc khối.
  * `subject` (str, tùy chọn): Tên môn học cụ thể.
  * `limit` (int, mặc định `5`): Số lượng học sinh tối đa hiển thị.

#### 6. `find_struggling_students(year: int, semester: int, class_name: str = None, grade_level: int = None, subject: str = None, limit: int = 5) -> str`
* **Mô tả:** Tìm danh sách những học sinh có kết quả học tập thấp nhất (học sinh yếu, kém) để có biện pháp hỗ trợ kịp thời.
* **Tham số:** Tương tự như tool `find_top_students`.

#### 7. `compare_classes(year: int, semester: int, subject: str, grade_level: int) -> str`
* **Mô tả:** So sánh điểm trung bình giữa tất cả các lớp trong cùng một khối lớp của một môn học.
* **Tham số:**
  * `year` (int), `semester` (int): Năm học và Học kỳ bắt đầu.
  * `subject` (str): Tên môn học.
  * `grade_level` (int): Khối lớp muốn so sánh (`6` đến `12`).
* **Đầu ra:** Bảng xếp hạng các lớp học theo điểm trung bình môn từ cao xuống thấp.

---

### Nhóm 3: Phân tích chuyên sâu & Chỉ số Đo lường Học thuật

#### 8. `get_student_academic_trend(student_id: str, subject: str = None) -> str`
* **Mô tả:** Phân tích xu hướng học tập (tăng tiến, sa sút hay ổn định) của một học sinh qua các học kỳ.
* **Tham số:**
  * `student_id` (str): Mã học sinh.
  * `subject` (str, tùy chọn): Môn học cần theo dõi. Nếu để trống, hệ thống sẽ tính dựa trên điểm trung bình tất cả các môn.
* **Đầu ra:** Lịch sử điểm GPA qua các kỳ và nhận xét xu hướng tiến bộ/sa sút dựa trên chênh lệch giữa học kỳ cuối và học kỳ đầu tiên.

#### 9. `get_academic_divergence_metrics(class_name: str, year: int, semester: int, subject: str) -> str`
* **Mô tả:** Tính toán chỉ số **Dị biệt Học thuật Tập thể (Delta G_Class)** của một lớp học đối với một môn học cụ thể.
* **Phương pháp tính:** 
  * So sánh điểm trung bình của môn học mục tiêu với điểm trung bình của tất cả các môn học khác của chính học sinh đó (gọi là $GPAO$). 
  * Chỉ số của cả lớp được tính bằng trung bình các hiệu số $\Delta G = \text{Điểm môn mục tiêu} - GPAO$ của các thành viên trong lớp.
* **Giải nghĩa chỉ số:**
  * $\Delta G \le -1.0$ (Dị biệt âm lớn): Điểm môn học này tụt hẳn so với mặt bằng học lực các môn khác của lớp. Có thể do giáo viên chấm quá khắt khe hoặc đề thi quá khó.
  * $\Delta G \ge 1.0$ (Dị biệt dương lớn): Kết quả môn học này nổi trội hơn hẳn năng lực chung của lớp.
  * $-0.3 < \Delta G < 1.0$: Điểm số môn này tương đồng với năng lực học tập chung của lớp.

#### 10. `get_grade_inflation_report(year: int, semester: int, grade_level: int, subject: str) -> str`
* **Mô tả:** Báo cáo chỉ số **Lệch pha tiêu chuẩn & Lạm phát điểm (GDI - Grade Inflation Index)** của các lớp học trong một khối.
* **Phương pháp tính:**
  * Chuẩn hóa điểm đánh giá thường xuyên trung bình ($TX_{\text{mean}}$) và điểm thi cuối kỳ ($CK$) của từng học sinh về giá trị Z-score tương ứng trong toàn khối.
  * Tính toán chỉ số lạm phát điểm của cá nhân bằng: $GDI = Z_{TX} - Z_{CK}$.
  * Chỉ số của lớp ($GDI_{\text{Class}}$) là trung bình cộng của các thành viên.
* **Giải nghĩa chỉ số:**
  * $GDI_{\text{Class}} \ge 1.0$ (Lệch pha dương lớn): Lớp có hiện tượng lạm phát điểm số đánh giá thường xuyên (chốt điểm thường xuyên lỏng tay hoặc cho điểm quá cao so với thực lực thể hiện qua bài thi cuối kỳ tập trung).
  * $GDI_{\text{Class}} \le -1.0$ (Lệch pha âm lớn): Chấm điểm thường xuyên quá khắt khe hoặc bài thi cuối kỳ quá dễ dẫn đến điểm thi cuối kỳ cao vượt trội.

#### 11. `get_evaluation_momentum(class_name: str, year: int, semester: int, subject: str) -> str`
* **Mô tả:** Tính toán chỉ số **Động lượng học tập (Momentum Index - M)** của học sinh sau kỳ thi giữa kỳ nhằm đo lường nỗ lực và sự thích nghi tự điều chỉnh.
* **Phương pháp tính:**
  * $M = \frac{\text{ĐTB sau giữa kỳ} (TX3, TX4) - \text{ĐTB trước giữa kỳ} (TX1, TX2)}{\text{Điểm Giữa kỳ} (GK)}$.
* **Đầu ra:** Báo cáo liệt kê Top 3 học sinh tiến bộ nhiều nhất (động lượng dương cao nhất) và Top 3 học sinh sa sút mạnh nhất (động lượng âm thấp nhất) sau kỳ thi giữa kỳ để giáo viên chủ nhiệm/bộ môn có định hướng hỗ trợ.

---

## 3. Các bước Đăng ký và Phát triển Tool mới

### 3.1. Hướng dẫn thêm Tool mới
Khi cần bổ sung một công cụ mới cho Agent, hãy tuân thủ các bước sau:

1. **Khởi tạo hàm trong [grade_tools.py](file:///f:/PROJECT_VINUNI/BUILD_COHORT/C2-App-051/src/agents/tools/grade_tools.py):**
   * Sử dụng decorator `@tool` từ thư viện `langchain_core.tools`.
   * **Bắt buộc viết docstring chi tiết:** LLM dựa hoàn toàn vào mô tả hàm và tham số trong docstring để đưa ra quyết định khi nào cần gọi tool.
   * **Định nghĩa Type Hints rõ ràng** cho tất cả các đối số đầu vào.
   * **Xử lý ngoại lệ (Error Handling) cục bộ:** Tránh ném ra lỗi (Exception) trực tiếp làm sập đồ thị LangGraph. Nên trả về thông điệp lỗi dưới dạng chuỗi thông báo trực quan để Agent có thể đọc được lỗi và tự sửa chữa hoặc phản hồi lại cho người dùng.

   ```python
   @tool
   def get_new_metric(class_name: str, year: int) -> str:
       """Mô tả công dụng của tool ở đây để LLM hiểu.
       
       Args:
           class_name: Tên lớp học (ví dụ: '6A1').
           year: Năm học bắt đầu (ví dụ: 2023).
       """
       try:
           # Logic truy xuất DB hoặc tính toán ở đây
           return "Kết quả xử lý"
       except Exception as e:
           return f"Lỗi xảy ra khi tính toán chỉ số: {str(e)}"
   ```

2. **Đăng ký tool trong [graph.py](file:///f:/PROJECT_VINUNI/BUILD_COHORT/C2-App-051/src/agents/graph.py):**
   * Import hàm tool mới vừa viết.
   * Thêm hàm đó vào danh sách `tools` của Agent để ràng buộc với mô hình:
     ```python
     tools = [
         # ... các tool cũ ...
         get_new_metric,
     ]
     ```

3. **Cập nhật SYSTEM_PROMPT:**
   * Nếu tool mới cần sự chỉ dẫn đặc biệt về ngữ cảnh sử dụng, hãy cập nhật mô tả của tool đó vào `SYSTEM_PROMPT` tại `graph.py` để tối ưu khả năng suy luận của LLM.
