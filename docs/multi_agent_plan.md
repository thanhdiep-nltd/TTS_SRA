# Kế hoạch Triển khai (Implementation Plan) - Project Antigravity
**Dự án:** AI Trợ Lý Phân Tích Kết Quả Học Tập Toàn Trường (Trợ Lý A.I EduOwl)
**Mục tiêu:** Chuyển đổi kiến trúc LangGraph từ Single ReAct Agent sang Multi-Agent (Supervisor + Sub-Agents) để xử lý các truy vấn phân tích học vụ phức tạp, kết hợp rào chắn an ninh SQLGlot và môi trường Pandas Sandbox.
**Ràng buộc cốt lõi:** Tuyệt đối KHÔNG thay đổi cấu trúc cơ sở dữ liệu hiện tại trong `schema.sql`.

---

## Giai đoạn 1: Tái cấu trúc thư mục (Refactor Directory Structure)
**Mục tiêu:** Phân rã thư mục `src/agents/` hiện tại (đang gom chung tools và nodes) sang cấu trúc chia theo Domain chuyên môn của từng Agent.

**Các bước thực hiện:**
1. Bỏ cấu trúc cũ: Dọn dẹp thư mục `src/agents/nodes/` và `src/agents/tools/`.
2. Tạo cấu trúc thư mục mới theo mô hình Multi-Agent:
   - `src/agents/supervisor/` (Điều phối tổng)
   - `src/agents/data_agent/` (Truy xuất & Kiểm toán)
   - `src/agents/stat_agent/` (Phân tích thống kê sâu)
   - `src/agents/sql_agent/` (Phân tích dữ liệu bằng SQL nâng cao)
3. Trong mỗi thư mục Agent mới, tạo sẵn các file: `__init__.py`, `node.py`, và `tools.py` (trừ supervisor có thể không cần `tools.py`).

---

## Giai đoạn 2: Phân rã Tools và Thiết lập Rào chắn An ninh (Core Setup)
**Mục tiêu:** Chia nhỏ `grade_tools.py` (11 tools) về đúng Agent quản lý và xây dựng lớp bảo vệ SQL.

**Các bước thực hiện:**
1. **Di chuyển Tools cho `data_agent`:**
   - Cắt các hàm: `get_student_info`, `get_student_grades`, `get_class_grades` đưa vào `src/agents/data_agent/tools.py`.
2. **Di chuyển Tools cho `stat_agent`:**
   - Cắt các hàm: `calculate_grade_statistics`, `find_top_students`, `find_struggling_students`, `compare_classes`, `get_student_academic_trend`, `get_academic_divergence_metrics`, `get_grade_inflation_report`, `get_evaluation_momentum` đưa vào `src/agents/stat_agent/tools.py`.
3. **Xây dựng Rào chắn SQLGlot (`src/core/security/sql_validator.py`):**
   - Tích hợp thư viện `sqlglot`.
   - Viết hàm `validate_and_secure_sql(query: str, current_school_id: str) -> str`:
     - Phân tích AST để chặn toàn bộ các lệnh thay đổi dữ liệu (DROP, UPDATE, DELETE, ALTER, INSERT).
     - Đảm bảo câu lệnh luôn có điều kiện giới hạn `school_id = current_user_school_id`.
4. **Viết Tool cho `sql_agent`:**
   - Trong `src/agents/sql_agent/tools.py`, tạo một tool `execute_read_only_query(sql_query: str) -> str`. Tool này phải gọi qua `validate_and_secure_sql` trước khi chạy thực tế trên Neon.tech để lấy dữ liệu JSON thô.

---

## Giai đoạn 3: Khởi tạo các Agent Nodes
**Mục tiêu:** Bọc các tools đã chia vào từng con AI cụ thể bằng cơ chế `create_react_agent` của LangGraph.

**Các bước thực hiện:**
1. **Data Agent (`src/agents/data_agent/node.py`):**
   - Khởi tạo LLM (GPT-4o-mini).
   - Bind các tool từ `data_agent/tools.py`.
   - System Prompt: Tập trung vào việc tra cứu đúng bảng `scores`, `students`, `classes` và trả kết quả chính xác, không lan man nhận xét.
2. **Stat Agent (`src/agents/stat_agent/node.py`):**
   - Khởi tạo LLM. Bind các tool từ `stat_agent/tools.py`.
   - System Prompt: Chuyên gia toán học sư phạm, đọc các chỉ số GDI, Delta G, Momentum để đưa ra số liệu thống kê.
3. **SQL Analyst Agent (`src/agents/sql_agent/node.py`):**
   - Khởi tạo LLM. Bind tool `execute_read_only_query`.
   - Cấu hình Prompt: Sinh câu lệnh PostgreSQL tối ưu, tự debug sửa sai khi SQL gặp lỗi, và phân tích dữ liệu thô.
4. **Supervisor Agent (`src/agents/supervisor/node.py`):**
   - Đóng vai trò Router. Không bind tool truy xuất.
   - Nhận câu hỏi, phân loại Intent và quyết định "Next Agent" là ai (`data_agent`, `stat_agent`, hay `sql_agent`).

---

## Giai đoạn 4: Biên dịch Đồ thị LangGraph (Orchestration)
**Mục tiêu:** Đấu nối các Node lại với nhau thành một luồng suy nghĩ hoàn chỉnh trong `src/agents/graph.py`.

**Các bước thực hiện:**
1. **Định nghĩa State (`src/agents/state.py`):**
   - Mở rộng `AgentState` thành `MultiAgentState`.
   - Bổ sung trường `next_agent: str` để định tuyến.
   - Bổ sung trường `school_context: dict` (chứa school_id, role) truyền từ API layer.
2. **Xây dựng Workflow (`src/agents/graph.py`):**
   - Thêm tất cả các node: `supervisor`, `data_agent`, `stat_agent`, `sql_agent`.
   - Node bắt đầu (Entry point): `supervisor`.
   - Thêm `conditional_edges` từ `supervisor` trỏ đến các Sub-agents dựa trên giá trị của `next_agent`.
   - Thêm `edges` từ tất cả các Sub-agents quay ngược lại `supervisor` để tổng hợp kết quả.
   - Thêm nhánh kết thúc (`END`) khi Supervisor nhận định đã thu thập đủ thông tin để trả lời BGH.

---

## Giai đoạn 5: Tích hợp API và Testing
**Mục tiêu:** Đảm bảo luồng gọi từ API xuống LangGraph mượt mà và kiểm thử các kịch bản ngoại lệ.

**Các bước thực hiện:**
1. **Cập nhật Route (`src/api/routes.py`):** Cập nhật endpoint `/chat` để truyền đúng `school_context` (từ CurrentUser) vào `MultiAgentState` khi gọi `graph.invoke`.
2. **Kiểm thử Tool có sẵn:** Yêu cầu BGH kiểm tra số cột điểm thường xuyên (sẽ kích hoạt `data_agent`).
3. **Kiểm thử Toán học:** Yêu cầu tính phân phối học lực (sẽ kích hoạt `stat_agent`).
4. **Kiểm thử Vượt biên (Edge Cases):** Yêu cầu tìm sự tương quan giữa điểm thi giữa kỳ và cuối kỳ (sẽ ép `supervisor` gọi `sql_agent` để lấy dữ liệu thô và tự chạy câu lệnh SQL phân tích).
5. **Kiểm thử Bảo mật:** Thử prompt injection chèn lệnh `DROP TABLE scores` để test lớp bảo vệ `SQLGlot`.