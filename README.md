# ⛩️ GATE 1:
```bash
Link Brief: docs/gate_1/BRIEF.md
Link PRD: docs/gate_1/PRD.md
Link UI: docs/gate_1/ui_gate_1.png
```

# ⛩️ GATE 2:
```bash
Link Architecture: docs/gate_2/architecture.md
Link Video Demo: docs/gate_2/video_demo.md
Link Evaluation: docs/gate_2/evaluation.md
```

# ⛩️ GATE 3:

TÀI KHOẢN DEMO:

HIỆU TRƯỞNG: principal.c2@nguyendu.edu.vn  /  password123

ADMIN: admin@admin.edu.vn  /  admin123

TRƯỞNG BỘ MÔN: teacher.c2.1@nguyendu.edu.vn  /  password123

```bash
Link Demo: https://c2-app-051.up.railway.app/

Link Metric: https://c2-app-051.up.railway.app/admin/ai-metrics   (Đăng nhập tài khoản ADMIN để xem)

Link GATE_3: https://drive.google.com/drive/folders/1TbDW0MVhw9_VbCA1bOfp5MJaH3RS1BJK?usp=sharing
```



# 🏫 AI Trợ Lý Phân Tích Kết Quả Học Tập Toàn Trường (Trợ Lý A.I EduOwl)

Hệ thống AI Agent hỗ trợ Ban Giám Hiệu K-12 phân tích hiệu quả dạy và học, tự động hóa báo cáo học vụ và phân tích sâu kết quả thi cử qua giao diện Chat trực quan và Dashboard phân tích dữ liệu thông minh.

## 🛠 Tech Stack

| Layer | Công nghệ | Vị trí |
|-------|-----------|--------|
| **Frontend** | Next.js 16 (App Router) · React 19 · Tailwind v4 · Recharts | `frontend/src/` |
| **Backend** | FastAPI · Uvicorn (Python 3.11) | `src/` |
| **ORM/DB** | SQLAlchemy 2.0 · Alembic · PostgreSQL (Neon, driver `psycopg` v3) | `src/db/`, `src/models/`, `alembic/` |
| **Auth & RBAC** | JWT (access/refresh) · `bcrypt` · RBAC 7 vai trò | `src/core/security`, `src/api/deps.py`, `src/services/rbac.py` |
| **AI Agent** | LangGraph `StateGraph` (Supervisor + 3 sub-agents: `data_agent`, `stat_agent`, `pandas_agent`) | `src/agents/` |
| **LLM** | `langchain-openai` (`gpt-4o-mini`) hoặc DeepSeek | `src/services/llm.py` |
| **Guardrail** | SQLGlot (Chỉ cho phép `SELECT`, lọc whitelist bảng, chèn tự động `school_id`) | `src/core/security/sql_validator.py` |

---

## 🖥️ Hướng dẫn cài đặt & Chạy Backend (FastAPI)

### 1. Khởi tạo môi trường ảo (Python Virtual Environment)
Yêu cầu Python 3.11+. Di chuyển vào thư mục gốc của dự án và chạy:
```bash
# Tạo virtual environment
python -m venv .venv

# Kích hoạt môi trường ảo:
# Trên macOS/Linux:
source .venv/bin/activate
# Trên Windows (Command Prompt):
.venv\Scripts\activate
# Trên Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

### 2. Cài đặt các thư viện dependencies
```bash
pip install -r requirements.txt
```

### 3. Cấu hình biến môi trường (`.env`)
Sao chép file mẫu `.env.example` thành `.env`:
```bash
cp .env.example .env
```
Mở file `.env` và cấu hình các thông số phù hợp (xem bảng chi tiết ở phần dưới).

### 4. Áp dụng Database Migrations (Alembic)
Đồng bộ cấu trúc database lên PostgreSQL (Neon):
```bash
alembic upgrade head
```

### 5. Khởi tạo tài khoản và Dữ liệu mẫu (Tùy chọn)
Chạy các scripts nạp cấu hình bổ sung hoặc tài khoản quản trị:
```bash
# Seed các môn học đánh giá định tính (Đạt/Chưa đạt)
python scripts/seed_remark_subjects.py

# Tạo tài khoản quản trị (ADMIN) đầu tiên để đăng nhập
python scripts/create_admin.py --email admin@truong.edu.vn --password "MatKhau123"
```

### 6. Khởi chạy server Backend
Chạy server bằng Uvicorn:
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```
Hoặc sử dụng Makefile:
```bash
make run
```
*   **API Base URL**: `http://localhost:8000`
*   **Tài liệu Swagger UI**: `http://localhost:8000/docs`

---

## 🌐 Hướng dẫn cài đặt & Chạy Frontend (Next.js)

### 1. Di chuyển vào thư mục frontend
```bash
cd frontend
```

### 2. Cài đặt các thư viện Node.js
Yêu cầu Node.js v18+.
```bash
npm install
```

### 3. Cấu hình biến môi trường cho Frontend
Tạo file `frontend/.env.local` (nếu chưa có) và trỏ API endpoint về phía Backend:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 4. Khởi chạy môi trường Phát triển (Development)
```bash
npm run dev
```
*   **Frontend UI URL**: `http://localhost:3000`

---

## ⚙️ Cấu hình biến môi trường (Environment Variables)

### Backend (`.env`)

| Biến môi trường | Giá trị mẫu | Mô tả |
|-----------------|------------------|-------|
| `LLM_PROVIDER` | `openai` | Lựa chọn LLM provider: `openai` hoặc `deepseek` |
| `OPENAI_API_KEY` | `sk-your-key-here` | API Key của OpenAI (nếu LLM_PROVIDER=openai) |
| `MODEL_NAME` | `gpt-4o-mini` | Model OpenAI sử dụng cho tác vụ AI Agent |
| `DEEPSEEK_API_KEY` | `your-deepseek-key-here` | API Key của DeepSeek (nếu LLM_PROVIDER=deepseek) |
| `DEEPSEEK_MODEL_NAME` | `deepseek-v4-flash` | Model DeepSeek sử dụng |
| `DEEPSEEK_API_BASE` | `https://api.deepseek.com` | Base URL cho DeepSeek API |
| `DATABASE_URL` | `postgresql://...` | Đường dẫn kết nối CSDL PostgreSQL (Cloud Neon hoặc Local) |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | Thư mục lưu trữ vector store ChromaDB (nếu có) |
| `APP_ENV` | `development` | Môi trường chạy ứng dụng (`development`, `production`) |
| `APP_PORT` | `8000` | Port khởi chạy backend server |
| `APP_HOST` | `0.0.0.0` | Host bind cho backend server |
| `CORS_ORIGINS` | `http://localhost:3000` | Danh sách domain frontend được phép CORS (phân tách bằng dấu phẩy) |
| `JWT_SECRET_KEY` | `your-jwt-secret-key-here` | Mã bí mật mã hóa JWT tokens (tối thiểu 32 bytes ở prod) |
| `LANGCHAIN_API_KEY` | `your-langsmith-key-here` | API Key của LangSmith dùng để trace agent (Tùy chọn) |
| `LANGCHAIN_TRACING_V2` | `true` | Bật/tắt trace chi tiết lên LangSmith (Tùy chọn) |

### Frontend (`frontend/.env.local`)

| Biến môi trường | Giá trị mẫu | Mô tả |
|-----------------|------------------|-------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Địa chỉ URL dẫn tới backend API |

---

## 💬 Mẫu câu hỏi tương tác với AI Agent (Sample Queries)

Hệ thống Multi-Agent LangGraph sẽ tự động phân loại câu hỏi và định tuyến tới Sub-agent tương ứng để xử lý. Dưới đây là một số câu hỏi mẫu có thể nhập ở Chat UI:

### 1. Data Agent (Tra cứu hồ sơ & điểm trực tiếp qua ORM)
*   *"Cho tôi xem thông tin cá nhân và lớp học của học sinh Nguyễn Văn A."*
*   *"Liệt kê danh sách các điểm số của học sinh Trần Thị B trong học kỳ này."*
*   *"Hiển thị bảng điểm chi tiết môn Toán của lớp 9A."*

### 2. Stat Agent (Phân tích chỉ số học thuật nâng cao)
*   *"Tính phân bố học lực (Giỏi, Khá, Trung bình, Yếu) của khối 9."*
*   *"Ai là những học sinh có điểm trung bình cao nhất lớp 8B môn Ngữ Văn?"*
*   *"Lớp nào đang có chỉ số lệch điểm giữa kỳ và cuối kỳ (Delta G) cao nhất ở môn Tiếng Anh trong học kỳ 1?"*
*   *"Báo cáo chỉ số lạm phát điểm (GDI) của các lớp thuộc khối 7 đối với môn Vật Lý."*
*   *"Động lượng học tập (Learning Momentum) của lớp 6A sau kỳ thi giữa kỳ thế nào?"*

### 3. SQL Analyst Agent (Truy vấn dữ liệu phức tạp qua SQLGlot Guardrail)
*   *"Tìm 5 học sinh có tiến bộ lớn nhất về điểm số giữa kỳ 1 và kỳ 2 môn Toán."*
*   *"Hãy phân tích xem các học sinh có điểm kiểm tra thường xuyên thấp nhưng điểm cuối kỳ cao tập trung ở lớp nào nhiều nhất?"*

---

## 📁 Cấu trúc thư mục dự án

```
├── src/
│   ├── agents/           # 🧠 Thiết lập Multi-Agent LangGraph (Supervisor, sub-agents)
│   ├── api/              # 🌐 Routing REST API & WebSocket Chat
│   ├── core/             # 🛡️ Lớp bảo mật & SQLGlot Guardrail
│   ├── db/               # 🗄️ Kết nối session database
│   ├── models/           # 📋 Khai báo 21 bảng database ORM
│   ├── schemas/          # 📥 Pydantic Schemas (Request/Response DTOs)
│   ├── services/         # ⚙️ Business logic (RBAC, công thức tính điểm)
│   ├── config.py         # 🔧 Quản lý cấu hình ứng dụng
│   └── main.py           # 🚀 Điểm bắt đầu khởi chạy FastAPI
├── frontend/             # 🖥️ Next.js Web Frontend
│   ├── src/app/          # 📂 Cấu trúc trang (Dashboard, Gradebook, Chat, Admin)
│   ├── src/components/   # 📂 Reusable UI components (Sidebar, SearchableSelect...)
│   └── src/lib/          # 📂 Thư viện kết nối API & Auth context
├── alembic/              # 🗄️ Database migration version files
├── docs/                 # 📂 Tài liệu Gate 1 & Gate 2
├── tests/                # 🧪 Kiểm thử tự động pytest
├── requirements.txt      # 🐍 Danh sách thư viện Python
├── Dockerfile            # 🐳 Đóng gói ứng dụng dạng Docker
├── docker-compose.yml    # 🐙 Cấu hình container stack
└── README.md             # 📝 Tài liệu hướng dẫn sử dụng
```
