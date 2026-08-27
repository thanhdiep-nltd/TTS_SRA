<p align="center">
  <img src="frontend/public/icon.png" width="110" alt="EduOwl Logo" />
</p>

<h1 align="center">Hệ Thống Cảnh Báo Sớm Học Sinh Có Nguy Cơ Sư Phạm (Build TTS: Student Risk Alert - SRA)</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Next.js-16.2+-black?style=flat-square&logo=next.js&logoColor=white" alt="Next.js 16" />
  <img src="https://img.shields.io/badge/PostgreSQL-Neon_Cloud-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL Neon" />
  <img src="https://img.shields.io/badge/AI_Agent-LangGraph-FF6F00?style=flat-square&logo=langchain&logoColor=white" alt="LangGraph" />
  <img src="https://img.shields.io/badge/ML-CatBoost_Ensemble-FFCC00?style=flat-square&logo=yandex&logoColor=black" alt="CatBoost" />
  <img src="https://img.shields.io/badge/Vector_DB-Qdrant-DC2626?style=flat-square&logo=qdrant&logoColor=white" alt="Qdrant" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License MIT" />
</p>


## 📌 1. Bối Cảnh & Phương Pháp Phát Triển (6-Week Sprint Context)

Dự án được nghiên cứu và phát triển trong lộ trình **6 tuần** thực tập, với yêu cầu nghiệp vụ chuyên sâu về phân tích dữ liệu giáo dục phổ thông K-12.

*   **Ràng buộc thực tế khi phát triển**:
    *   Đội ngũ được cung cấp Schema cơ sở dữ liệu quan hệ (`schema.sql` / `s360` DWH) nhưng **chưa được cấp máy truy cập trực tiếp vào môi trường dev nội bộ của hệ thống thật**.
    *   Hệ thống hiện tại đang vận hành ở môi trường **Development** với toàn bộ dữ liệu là **Data Mock / Synthetic Data**.
*   **Giải pháp & Phương pháp tiếp cận**:
    *   Chủ động thiết kế và lập trình **Pipeline sinh dữ liệu giả lập đa chiều (Multi-source Synthetic Data Generation)** dựa trên 14+ hồ sơ học sinh thực tế: điểm số các cột MOET (Miệng, 15p, Giữa kỳ, Cuối kỳ), lịch sử làm bài tập trắc nghiệm LMS, dữ liệu điểm danh chuyên cần, vi phạm hạnh kiểm và ma trận cấu trúc đề thi.
    *   Để thuận tiện cho việc phát triển cục bộ, chạy automated tests (CI/CD) và kiểm thử nhanh các phân quyền (RBAC 7 vai trò), các tài khoản mẫu trong scripts seed được **gán mật khẩu kiểm thử mặc định** *(chi tiết cấu hình xem trong các script seed tương ứng, không liệt kê mật khẩu cụ thể ở đây vì lý do an toàn thông tin)*.
    *   Xây dựng hệ thống kiểm thử độc lập (Offline Unit & Integration Tests với mock LLM) giúp bảo đảm mọi luồng nghiệp vụ, công thức tính toán và mô hình ML chạy chuẩn xác 100% trước khi kết nối môi trường thực tế.

---

## 🌟 2. 5 Flow Nghiệp Vụ & Kỹ Thuật Cốt Lõi (Core Capabilities)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   NGƯỜI DÙNG: BGH / TRƯỞNG BỘ MÔN / GIÁO VIÊN               │
└──────┬─────────────────┬──────────────────┬─────────────────┬───────────────┘
       │                 │                  │                 │
       ▼                 ▼                  ▼                 ▼
┌──────────────┐  ┌──────────────┐   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│    Flow 1    │  │    Flow 2    │   │    Flow 3    │  │    Flow 4    │  │    Flow 5    │
│ Multi-Agent  │  │ EWS Pipeline │   │  Curriculum  │  │  Pass/Fail   │  │Knowledge Gaps│
│   Chat AI    │  │(CatBoost+LLM)│   │ Ingestion+RAG│  │ Exam Forecast│  │& Item Mastery│
│(Supervisor+4)│  │(22 Features) │   │ (2-Pass VLM) │  │ (Deterministic) (Cross-Valid) │
└──────────────┘  └──────────────┘   └──────────────┘  └──────────────┘  └──────────────┘
```

---

### 🤖 Flow 1: Trợ Lý Multi-Agent Chat AI (LangGraph StateGraph)

Hệ thống hỏi đáp ngôn ngữ tự nhiên bằng tiếng Việt sử dụng kiến trúc **Multi-Agent** điều phối qua `StateGraph` thay vì một LLM duy nhất.

*   **Kiến trúc**: **Supervisor Node** (Router Decision với Structured Output) nhận diện ý định câu hỏi và định tuyến linh hoạt đến 4 Sub-agents chuyên biệt:
    1.  `data_service_agent`: Truy vấn hồ sơ học sinh, lớp học, bảng điểm chi tiết qua ORM SQLAlchemy (`SessionLocal`).
    2.  `stat_agent`: Tính toán các chỉ số học thuật nâng cao: Chỉ số lạm phát điểm (GDI), Độ lệch điểm giữa kỳ & cuối kỳ ($\Delta G$), Động lượng học tập (*Learning Momentum*), phân bố học lực.
    3.  `knowledge_agent`: Tra cứu kiến thức SGK qua RAG (Qdrant vector search), bắt buộc trích dẫn nguồn chuẩn xác.
    4.  `report_agent`: Kết xuất báo cáo học vụ tự động theo 4 mẫu chuẩn hoặc tùy biến (DOCX, PDF, HTML).
*   **Điểm nổi bật**:
    *   Hỗ trợ **Streaming token real-time** qua SSE/WebSocket.
    *   Hỗ trợ đính kèm tệp tin (File Attachments) trích xuất nội dung tự động vào ngữ cảnh hội thoại.
    *   Cô lập tenant triệt để qua `ContextVar` (`current_user_school_id`, `role`), chống rò rỉ dữ liệu giữa các trường.
    *   Tích hợp Judge LLM tự động chấm điểm tính trung thực (*Faithfulness / Groundedness*) cho từng phản hồi.

---

### ⚠️ Flow 2: Hệ Thống Cảnh Báo Sớm Nguy Cơ Học Tập (EWS Pipeline)

Hệ thống kết hợp **2 Tầng Phân Tích (Hybrid 2-Tier Architecture)** giữa Học máy (Machine Learning) và Mô hình Ngôn ngữ Lớn (LLM) để phát hiện và can thiệp toàn diện nguy cơ trượt môn hoặc suy giảm học lực của học sinh:

#### 🔹 Tầng 1: Đánh Giá Định Lượng Qua Mô Hình ML (CatBoost GBDT)
*   **22 Features Đa Nguồn (Multi-source Feature Extraction)**:
    *   *Temporal Scores (9)*: Điểm trung bình có trọng số đầu kỳ/cuối kỳ, độ dốc xu hướng điểm (`score_slope`), độ biến động (`volatility`), mức tụt điểm tối đa (`max_drop`), điểm gần nhất.
    *   *LMS Engagement (5)*: Điểm trung bình bài tập LMS, tỷ lệ nộp bài gần đây, độ lệch giữa điểm LMS và điểm sổ cái.
    *   *Attendance (4)*: Tỷ lệ vắng học, số ngày vắng không phép, vắng có phép, số lần đi muộn.
    *   *Behavior & Context (4)*: Điểm trừ hạnh kiểm, số lần tái phạm kỷ luật, phân loại môn học, khối lớp.
*   **Kiến trúc & Tối ưu**:
    *   **DB-backed FIFO Job Queue**: Chạy bất đồng bộ, timeout 5 phút, cơ chế tự phục hồi (*self-healing*) khi server restart.
    *   **Tối ưu SQL Materialized CTE**: Rút ngắn thời gian trích xuất đặc trưng từ **86s xuống < 5s**.
    *   **Ensemble Model**: Mặc định chạy `v2_ensemble` kết hợp 5-fold CatBoost averaging và tính toán **SHAP Drivers** để chỉ rõ nguyên nhân rủi ro hàng đầu cho từng học sinh.

#### 🔹 Tầng 2: Đánh Giá Định Tính Chuyên Sâu Qua LLM (LLM Qualitative Forecasting)
CatBoost thuần túy chỉ phân tích các con số định lượng, hoàn toàn không nắm bắt được các **yếu tố đời sống phi cấu trúc** tác động nghiêm trọng đến tâm lý và việc học của học sinh. Vì vậy, tầng LLM được kích hoạt tự động theo điều kiện Trigger:
*   **Điều kiện Kích hoạt (Trigger Condition)**:
    *   Học sinh rơi vào mức rủi ro cao từ CatBoost (`risk_level IN ('HIGH', 'CRITICAL')`).
    *   HOẶC học sinh có ghi nhận **Biến cố gia đình đang diễn ra** (`life_event` với `status = 'ONGOING'`, ví dụ: tang chế, bố mẹ ly hôn, biến động kinh tế gia đình).
    *   HOẶC học sinh có ghi nhận **Bệnh tật / Vấn đề y tế đang điều trị** (`medical` với `status = 'ONGOING'`, ví dụ: bệnh mãn tính `is_chronic = true`, hoặc mức độ nghiêm trọng `severity IN ('MODERATE', 'HIGH')`).
*   **Kết quả Phân tích Tầng LLM**:
    *   `llm_risk_score` & `llm_risk_level`: Điểm và mức độ rủi ro được LLM cân đối lại sau khi tổng hòa các chỉ số học lực với biến cố đời sống và sức khỏe.
    *   `llm_narrative_summary`: Báo cáo tóm tắt diễn giải chi tiết nguyên nhân gốc rễ (Root Cause) bằng ngôn ngữ tự nhiên.
    *   `llm_forecast_trend`: Dự báo xu hướng học tập trong các tuần tới (Cải thiện, Đi ngang, Suy giảm).
    *   `llm_recommended_actions`: Danh sách các hành động can thiệp cá nhân hóa dành riêng cho Giáo viên chủ nhiệm, Giáo viên bộ môn và Ban Giám Hiệu.
*   **Cơ chế Thực thi & Ổn định**:
    *   Chạy đa luồng song song (`ThreadPoolExecutor`, tối đa 5 workers) kèm Retry Exponential Backoff khi gặp Rate Limit (HTTP 429).
    *   Cơ chế ổn định điểm số (`LLM_RERUN_STABILITY_DELTA`): Giữ nguyên điểm số giữa các lần chạy lại nếu độ lệch $< 1.0$, tránh biến động điểm ngẫu nhiên.

---

### 📖 Flow 3: Trích Xuất SGK Tự Động & RAG Tri Thức (Curriculum Ingestion)

Tự động hóa số hóa sách giáo khoa và xây dựng cơ sở tri thức phục vụ giảng dạy và giải đáp.

*   **VLM 2 Lượt Quét Chống Ảo Giác (2-Pass Vision-Language Ingestion)**:
    *   *Lượt A (Quét Mục Lục)*: Đọc ~15 trang đầu của PDF SGK bằng VLM (Qwen-VL qua Replicate / OpenRouter) để dựng cây cấu trúc Chương → Bài học và tạo danh sách các khái niệm định danh chuẩn (NEO Anchors).
    *   *Lượt B (Phân Loại Nội Dung)*: Duyệt từng trang nội dung và **chỉ được phép gán vào NEO có sẵn từ Lượt A**, loại bỏ hoàn toàn hiện tượng VLM tự bịa tên bài học.
    *   *Làm giàu dữ liệu (Enrichment)*: Tự động trích xuất tóm tắt trọng tâm, từ khóa cốt lõi và các mục con cho từng bài học.
*   **Knowledge Retrieval**: Vector store Qdrant lưu trữ các chunks tri thức, hỗ trợ tìm kiếm ngữ nghĩa theo khối/môn/chương với độ chính xác cao.

---

### 🎯 Flow 4: Dự Báo Đỗ/Trượt Kỳ Thi Cuối Kỳ (Pass/Fail Exam Forecast)

Module phân tích **thuần logic - giải tích sư phạm** (Pure Deterministic Logic, không phụ thuộc LLM/ML) giúp giáo viên bộ môn dự đoán kết quả bài thi sắp tới.

*   **Chuỗi fallback 4 cấp độ năng lực (Ability Resolution)**:
    `Unit có LMS` → `TB Chương của HS` → `TB Môn của HS` → `INSUFFICIENT`
*   **Công thức Dự đoán Điểm**:
    $$\text{Predicted Score} = \left( \frac{\sum (w_u \cdot \text{Ability}_u)}{\sum w_u} \right) \cdot \text{DifficultyAdj}(\text{CDI})$$
    Trong đó hệ số điều chỉnh độ khó nội dung: $\text{DifficultyAdj}(\text{CDI}) = 1.0 + (0.5 - \text{CDI}) \times 0.5$ (dao động từ $0.75$ đến $1.25$).
*   **Phân loại kết quả**: $\ge 5.5$ (**PASS**), $< 4.5$ (**FAIL**), $4.5 - 5.5$ (**BORDERLINE**).
*   **Đề xuất hành động**: Tự động chỉ ra **Top 2 bài học học sinh bị hổng nặng nhất** dựa trên độ mất điểm: $\text{Loss} = (10 - \text{Ability}_u) \cdot w_u$.

---

### 🔍 Flow 5: Chẩn Đoán Lỗ Hổng Kiến Thức & Đối Soát Đa Nguồn (Knowledge Gaps & Item Mastery)

Đánh giá mức độ thành thạo của học sinh theo từng bài học cụ thể trong cây tri thức môn học kết hợp cơ chế kiểm chứng tính trung thực học thuật.

*   **Đo lường năng lực chuẩn hóa Bloom**:
    *   Kết hợp **Độ rộng (Breadth Ratio)** (số bậc Bloom đã làm) và **Độ sâu (Depth Factor)** (trọng số câu hỏi Vận dụng / Vận dụng cao) để tính toán **Điểm tin cậy (Confidence Score)** từ $0.0$ đến $1.0$.
*   **Động cơ Đối soát Đa nguồn (Cross-Validation Engine)**:
    *   So sánh độ lệch $\Delta = \text{Raw Mastery (LMS)} - \text{Exam}$ (với $\text{Exam}$ là điểm thi tập trung có giám thị) để tự động điều chỉnh trọng số và gán nhãn:
        *   🟢 `OK` (Đồng thuận): Điểm bài tập online và điểm thi tương đồng ($|\Delta| \le 30\%$).
        *   🔵 `LMS_EXCEEDS_EXAM` (LMS vượt trội): Làm online điểm rất cao ($\ge 9.5$) nhưng thi thật điểm thấp ($< 4.5$) $\rightarrow$ Cảnh báo nguy cơ học sinh tra đáp án hoặc gian lận.
        *   🟡 `LOW_ENGAGEMENT` (Ít luyện tập): Học sinh bỏ bài tập LMS ($N_{items} < 5$).
        *   🟣 `EXAM_ONLY` / ⚪ `LMS_ONLY` / 🟠 `FLAGGED` (Làm bài siêu tốc bất thường).
*   **Quy tắc Đa số (Majority Voting Rule)**: Tự động tổng hợp trạng thái đối soát và nguồn bằng chứng cấp toàn lớp (Class Roster).

---

## 📊 3. Bảng So Sánh Toàn Diện Các Phân Hệ Phân Tích & Nghiệp Vụ

| Phân hệ / Flow | Mục tiêu cốt lõi | Mức độ chi tiết | Mô hình / Công nghệ xử lý | Nguồn dữ liệu đầu vào | Đối tượng sử dụng |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 🤖 **Flow 1: Multi-Agent Chat AI** | Hỏi đáp dữ liệu & tự động hóa báo cáo học vụ qua ngôn ngữ tự nhiên | Toàn trường / Khối / Lớp / Cá nhân | LangGraph StateGraph (Supervisor + 4 Sub-agents) | DB PostgreSQL + Qdrant Vector SGK | BGH, Trưởng bộ môn, Giáo viên |
| ⚠️ **Flow 2: Cảnh Báo Sớm (EWS)** | Dự báo rủi ro rớt môn / bỏ học toàn kỳ & thấu hiểu biến cố đời sống | Cấp độ **Toàn môn học & Học kỳ** | **Hybrid 2-Tier**: CatBoost GBDT (22 Features) + LLM Qualitative Forecasting | Điểm số, LMS, Điểm danh, Hạnh kiểm + Hồ sơ Biến cố/Y tế | BGH, Trưởng khối, GVCN |
| 📖 **Flow 3: Curriculum Ingestion** | Số hóa sách giáo khoa và xây dựng kho tri thức GDPT 2018 | Cấp độ **Chương / Bài học SGK** | 2-Pass VLM (Qwen-VL) + Qdrant Vector Search | Tệp PDF Sách giáo khoa, Kế hoạch bài dạy | Trưởng bộ môn, Giáo viên |
| 🎯 **Flow 4: Dự Báo Đỗ/Trượt (Pass/Fail)** | Dự đoán điểm số & xác suất qua/rớt bài thi cuối kỳ sắp tới | Cấp độ **Bài thi chuẩn bị diễn ra** | Công thức giải tích thuần ($\sum \text{Ability} \times w \times \text{CDI}$) | Năng lực LMS + Ma trận trọng số đề | Giáo viên bộ môn |
| 🔍 **Flow 5: Chẩn Đoán Lỗ Hổng (Gaps)** | Chỉ rõ từng khái niệm/bài học bị hổng & đối soát độ trung thực | Cấp độ **Từng bài học / Câu hỏi Bloom** | Đối soát Đa nguồn (Cross-Validation) + Bloom Weighting | Bài tập LMS + Điểm thi tập trung có giám thị | Giáo viên bộ môn, Học sinh |

---

## 🛠️ 4. Tech Stack & Kiến Trúc Hệ Thống

| Tầng (Layer) | Công nghệ chính | Chi tiết triển khai |
| :--- | :--- | :--- |
| **Frontend** | **Next.js 16 (App Router)** · React 19 · TailwindCSS v4 · Recharts · Lucide | Giao diện chuẩn Portal giáo dục (phong cách vnEdu), hỗ trợ Dark/Light mode |
| **Backend API** | **FastAPI** · Python 3.11 · Uvicorn · Pydantic v2 | RESTful API, SSE/WebSocket streaming, kiến trúc phân lớp Clean Architecture |
| **Database & ORM** | **PostgreSQL (Neon Cloud)** · SQLAlchemy 2.0 · Alembic · `pgvector` | 21+ bảng thực thể quan hệ, hỗ trợ multi-tenancy qua `school_id` |
| **Vector DB / RAG** | **Qdrant** (Local/Cloud) · Embeddings models | Lưu trữ và tìm kiếm ngữ nghĩa chunks sách giáo khoa |
| **AI Multi-Agent** | **LangGraph** (`StateGraph`) · LangChain · OpenAI GPT-4o-mini / DeepSeek v4 Flash | Supervisor Router điều phối 4 sub-agents: Data, Stat, Knowledge, Report |
| **Machine Learning** | **CatBoost** · Scikit-Learn · NumPy · Pandas | Pipeline huấn luyện và suy luận EWS 22 features, giải trình SHAP values |
| **Vision Language (VLM)** | **Qwen-VL** (qua OpenRouter / Replicate) | Quét mục lục 2 lượt tự động trích xuất cấu trúc sách giáo khoa |
| **Bảo mật & Guardrails** | **SQLGlot** · JWT (Access/Refresh) · BCrypt · RLS | Bắt buộc truy vấn Read-only SELECT, tự động inject `school_id`, RBAC 7 vai trò |
| **Observability** | **Prometheus** · Langfuse / LangSmith tracing | Thu thập telemetry, latency, token usage và audit log |

---

## 🚀 5. Hướng Dẫn Cài Đặt & Chạy Ứng Dụng

### 1. Yêu cầu môi trường
*   Python 3.11+
*   Node.js 18+ & npm / pnpm
*   PostgreSQL Database (Neon Cloud hoặc Local PostgreSQL)
*   Docker (tùy chọn: dùng để chạy Qdrant Vector DB local)

---

### 2. Cài đặt Backend (FastAPI)

```bash
# 1. Tạo và kích hoạt môi trường ảo
python -m venv .venv

# Trên Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Trên macOS/Linux:
source .venv/bin/activate

# 2. Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt

# 3. Thiết lập biến môi trường
cp .env.example .env
# Chỉnh sửa thông tin DATABASE_URL, OPENAI_API_KEY, JWT_SECRET_KEY trong file .env

# 7. Khởi chạy Backend Server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```
*   **Swagger API Docs**: `http://localhost:8000/docs`
*   **Health Check**: `http://localhost:8000/health`

---

### 3. Cài đặt Frontend (Next.js)

```bash
# 1. Di chuyển vào thư mục frontend
cd frontend

# 2. Cài đặt gói dependencies
npm install

# 3. Cấu hình biến môi trường frontend
# Tạo file frontend/.env.local và thêm dòng sau:
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# 4. Khởi chạy giao diện phát triển
npm run dev
```
*   **Frontend UI**: `http://localhost:3000`

---

## 💬 6. Mẫu Câu Hỏi Tương Tác Với Trợ Lý AI Chat

| Nhóm Nghiệp Vụ | Mẫu câu hỏi tương tác mẫu |
| :--- | :--- |
| **Tra cứu Hồ sơ & Sổ điểm** | • *"Hiển thị bảng điểm chi tiết môn Toán học kỳ 1 của lớp 9A."*<br>• *"Cho tôi xem danh sách học sinh lớp 6B và giáo viên chủ nhiệm."* |
| **Xuất Báo Cáo Tự Động** | • *"Xuất báo cáo tổng kết tình hình học tập học kỳ 1 của khối 9 dạng Word (DOCX)."*<br>• *"Tổng hợp báo cáo các môn có tỷ lệ học sinh chưa đạt trên 15%."* |

---

## 📁 7. Cấu Trúc Thư Mục Dự Án (Repository Map)

```
├── src/
│   ├── agents/                   # 🧠 Multi-Agent LangGraph (Supervisor, sub-agents)
│   │   ├── supervisor/           #   Router decision & LLM Response synthesis
│   │   ├── data_service_agent/   #   Sub-agent tra cứu ORM database
│   │   ├── stat_agent/           #   Sub-agent tính chỉ số học vụ (GDI, Delta G, Momentum)
│   │   ├── knowledge_agent/      #   Sub-agent RAG tra cứu SGK qua Qdrant
│   │   ├── report_agent/         #   Sub-agent sinh báo cáo học vụ (DOCX/PDF/HTML)
│   │   └── graph.py              #   Biên dịch StateGraph & Conditional Edges
│   ├── api/v1/                   # 🌐 Hệ thống Router endpoints REST API
│   │   ├── chat.py               #   Chat streaming, sessions & feedback
│   │   ├── ews.py                #   Pipeline EWS dự báo nguy cơ học tập & job status
│   │   ├── knowledge_gap.py      #   Chẩn đoán lỗ hổng kiến thức & Class Roster
│   │   ├── pass_fail_forecast.py #   Dự báo điểm thi cuối kỳ
│   │   ├── gradebook.py          #   Sổ điểm điện tử & Bảng tổng hợp lớp
│   │   ├── scores.py             #   Nhập điểm, phê duyệt & Row-level Security
│   │   ├── users.py              #   Quản lý tài khoản & phân công giảng dạy
│   │   └── curriculum.py         #   Ingestion SGK & Quản lý cây bài học
│   ├── core/security/            # 🛡️ SQLGlot Query Validator & Tenant Isolation
│   ├── db/                       # 🗄️ Database Session & Engine
│   ├── ews/                      # ⚠️ Early Warning System Core Engine
│   │   ├── feature_extractor.py  #   SQL trích xuất 22 features qua Materialized CTE
│   │   ├── inference_service.py  #   CatBoost v1 & v2 ensemble inference + SHAP
│   │   ├── llm_forecasting.py    #   Tầng 2 LLM Qualitative Forecasting (Biến cố & Bệnh tật)
│   │   ├── job_worker.py         #   FIFO Queue Worker & Self-healing timeout
│   │   ├── pipeline_runner.py    #   Điều phối toàn bộ chu trình EWS
│   │   ├── risk_config.py        #   Cấu hình ngưỡng rủi ro & Factor keys
│   │   └── risk_weights.yaml     #   Trọng số các thành phần đánh giá nguy cơ
│   ├── models/                   # 📋 21+ ORM Models (SQLAlchemy)
│   ├── schemas/                  # 📥 Pydantic DTO Schemas
│   └── services/                 # ⚙️ Business Logic (Item Mastery, Scoring, RBAC, VLM)
├── frontend/                     # 🖥️ Next.js 16 App Router
│   ├── src/app/(app)/            # 📂 Các trang tính năng chính:
│   │   ├── dashboard/            #   Executive Dashboard & Learning Analytics
│   │   ├── chat/                 #   Giao diện Chat AI Streaming
│   │   ├── gradebook/            #   Sổ điểm điện tử & Phân quyền RBAC
│   │   ├── knowledge-gaps/       #   Chẩn đoán Lỗ hổng kiến thức & Bloom Drawer
│   │   ├── pass-fail-forecast/   #   Dự báo đỗ/trượt kỳ thi
│   │   ├── question-bank/        #   Ngân hàng câu hỏi & Bloom Taxonomy
│   │   └── lesson-plans/         #   Trợ lý Soạn giáo án (CV 5512)
│   └── src/components/           # 📂 Reusable UI Components
├── data_mock/                    # 📦 Dữ liệu giả lập mẫu (CSV / JSON) & synthetic generator
├── alembic/                      # 🗄️ Database Migrations
├── docs_vsf/                     # 📑 Hồ sơ 6 tuần thực tập & 5 Bản báo cáo kỹ thuật chi tiết các Flow (docs_vsf/reports/)
├── monitoring/                   # 📊 Cấu hình giám sát hệ thống (Prometheus & Grafana Dashboards)
├── scripts/                      # 🐍 Data Seeding & Admin Creation Scripts
└── tests/                        # 🧪 Kiểm thử tự động pytest
```

---

## 🧠 8. Ghi Chú Kiến Trúc & Cảnh Báo Vận Hành Dành Cho AI Agent / Kỹ Sư Phát Triển (Agent System Context)

> **Mục tiêu của phần này**: để bất kỳ AI Agent hoặc Kỹ sư nào khi tiếp quản dự án đều hiểu rõ **tại sao hệ thống lại được thiết kế như vậy**, tránh sửa sai cấu trúc hoặc hiểu nhầm về trạng thái dữ liệu.
### 1. Bối Cảnh Dữ Liệu Mock & Hardcoded Credentials trong Development
*   **Tại sao có Data Mock?** Vì đội ngũ ban đầu không được cấp máy truy cập trực tiếp vào hệ thống dev/staging của trường, toàn bộ các bảng trong CSDL (`fact_gradebooks`, `lms_question_response`, `fact_so_daily_attendance`, `fact_behavior_logs`, v.v.) đều được nạp dữ liệu giả lập từ các kịch bản seed (`scripts/seed_*.py`).
*   **Tại sao Hardcode Password trong Seed Data?** Để phục vụ việc test tự động (Automated Integration Tests), benchmark hiệu năng, và cho phép kiểm thử các vai trò RBAC (Admin, Hiệu trưởng, Giáo viên chủ nhiệm, Giáo viên bộ môn) mà không cần bước đăng ký/kích hoạt phức tạp, mật khẩu các tài khoản seed được gán giá trị mặc định cho môi trường dev *(chi tiết xem trong các script seed tương ứng)*.

### 2. ⚠️ LƯU Ý QUAN TRỌNG KHI TRIỂN KHAI PRODUCTION (Production Deployment Checkpoints)
Khi kết nối với cơ sở dữ liệu thật của Sở GD&ĐT / Nhà trường hoặc triển khai lên môi trường Production, **BẮT BUỘC** thực hiện các bước sau:
1.  **Đổi toàn bộ mật khẩu**: Tuyệt đối không giữ các mật khẩu mặc định của môi trường dev. Bắt buộc ép đổi mật khẩu (force reset password) ngay lần đầu đăng nhập.
2.  **Ngừng chạy các script Seed Data Mock**: Không chạy các file `scripts/seed_mock_*.py` lên môi trường Production để tránh làm ô nhiễm dữ liệu thật.
3.  **Thay đổi JWT Secret Key**: Thiết lập biến môi trường `JWT_SECRET_KEY` bằng một chuỗi ngẫu nhiên bảo mật cao (tối thiểu 32 bytes) trong `.env`.
4.  **Chuyển đổi nguồn dữ liệu**: Cập nhật `DATABASE_URL` sang hệ thống PostgreSQL chính thức và kết nối API đồng bộ với cổng LMS/Sổ điểm điện tử của trường.
5.  **Rà soát & chuẩn hóa ma trận phân quyền (RBAC Matrix)**: Trong phiên bản phát triển hiện tại, do giới hạn thời gian demo và để phục vụ kiểm thử nhanh (testing/demo), một số quyền hạn đang được điều chỉnh linh hoạt giữa các role (ví dụ: tài khoản *Hiệu trưởng* được cấp tạm một số quyền quản trị của *Admin*). Khi triển khai chính thức lên Production, cần rà soát và siết chặt lại ma trận RBAC theo đúng quy định chuẩn của nhà trường.

### 3. Lý Do Thiết Kế Kiến Trúc (Architecture Design Rationales)
*   **Tại sao dùng Multi-Agent StateGraph thay vì Single LLM?**
    *   Một LLM duy nhất dễ bị quá tải ngữ cảnh (Context Overflow) và hallucination khi vừa phải viết SQL, vừa tính toán chỉ số thống kê, vừa tra cứu sách giáo khoa, vừa render file Word.
    *   Kiến trúc 4 Sub-agents chuyên biệt giúp cô lập lỗi: Agent tra cứu dữ liệu (`data_service_agent`) chỉ dùng ORM an toàn; Agent thống kê (`stat_agent`) tập trung vào logic toán học; Agent tri thức (`knowledge_agent`) bắt buộc gọi Vector Search; Agent báo cáo (`report_agent`) chuyên xử lý định dạng tệp.
*   **Tại sao Pass/Fail Forecast (Flow 4) là Thuật Toán Thuần Logic (Deterministic)?**
    *   Dự báo đỗ/trượt kỳ thi cần tốc độ phản hồi tính bằng mili-giây, tính nhất quán 100% không bị ngẫu nhiên (non-hallucinative) và có thể giải trình minh bạch công thức cho giáo viên và học sinh xem xét.
*   **Tại sao EWS Pipeline (Flow 2) lại kết hợp CatBoost ML (Định lượng) và LLM Forecasting (Định tính)?**
    *   *CatBoost ML* xử lý xuất sắc dữ liệu dạng bảng (Tabular Data) với hàng chục ngàn dòng điểm số, điểm danh, LMS theo chuỗi thời gian nhưng hoàn toàn "mù" trước các thông tin văn bản phi cấu trúc như biến cố gia đình (ly hôn, tang chế, biến động kinh tế) hay hồ sơ bệnh tật/y tế của học sinh.
    *   *LLM Qualitative Forecasting* lấp đầy khoảng trống này: tự động kích hoạt khi học sinh có rủi ro cao hoặc có biến cố/bệnh tật để đọc hồ sơ, giải trình nguyên nhân gốc rễ (Narrative Summary) và đưa ra khuyến nghị can thiệp nhân văn, có tính sư phạm cao.
    *   Hàng đợi FIFO (DB-backed) có cơ chế timeout 5 phút và tự phục hồi (*self-healing*) giúp server kiểm soát tải, không bị cạn kiệt tài nguyên khi BGH kích hoạt quét toàn trường cùng lúc.
*   **Tại sao Curriculum Ingestion (Flow 3) dùng VLM 2 Lượt Quét?**
    *   Sách giáo khoa PDF tiếng Việt có cấu trúc trình bày phức tạp. Nếu cho VLM quét tự do, model sẽ tự bịa (hallucinate) tên chương/bài.
    *   Lượt A cố định cây khung bài học (NEO Anchors); Lượt B ép từng trang nội dung phải gán vào NEO có sẵn, bảo đảm độ chính xác 100% của cây tri thức.
*   **Tại sao Knowledge Gap (Flow 5) cần Động Cơ Đối Soát Đa Nguồn (Cross-Validation)?**
    *   Học sinh làm bài tập trực tuyến trên LMS có nguy cơ tra Google/hỏi bạn (điểm online cao bất thường). Nếu chỉ tin LMS sẽ chẩn đoán sai.
    *   Hệ thống bắt buộc đối soát chéo với điểm thi tập trung có giám thị trên lớp để phát hiện độ lệch $\Delta$, phân loại chính xác giữa học sinh giỏi thực chất, học sinh gian lận online (`LMS_EXCEEDS_EXAM`) hay học sinh lười làm bài (`LOW_ENGAGEMENT`).
