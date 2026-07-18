# CLAUDE.md — AI20K-075

Hướng dẫn cho Claude Code khi làm việc trên repo này. Đọc kỹ trước khi sửa code.

---

## 1. Dự án là gì

**AI20K-075 — AI Trợ Lý Phân Tích Kết Quả Học Tập Toàn Trường cho Ban Giám Hiệu (K-12).**

Web app phân tích học lực dạng **Conversational BI + Learning Analytics**: trực quan hóa dữ liệu toàn trường, nhập/sửa/xem điểm theo phân quyền, và trợ lý AI hỏi đáp bằng tiếng Việt. Đồ án **VinUni AI20K Build Phase** (MVP 5 tuần), mục tiêu deploy online thật.

**Frontend hướng tới layout/phong cách của cổng vnEdu** (xem mockup [docs/gate_1/ui_gate_1.png](docs/gate_1/ui_gate_1.png) và ảnh tham chiếu vnEdu): portal sạch, top bar có logo + nút Đăng nhập, sidebar điều hướng trái, khối "Hỗ trợ kỹ thuật". 3 nhóm chức năng cốt lõi: **(1) Dashboard trực quan hóa dữ liệu toàn trường**, **(2) Quản lý điểm (xem/nhập/sửa) theo role**, **(3) Trợ lý chatbot AI**.

- Tài liệu nguồn (ngữ cảnh nghiệp vụ, **không** phải mô tả code hiện tại):
  - [docs/gate_1/PRD.md](docs/gate_1/PRD.md) — yêu cầu sản phẩm, guardrails, mô hình toán (β, σ).
  - [docs/gate_1/KE_HOACH_TRIEN_KHAI_AI20K-075_PRO.md](docs/gate_1/KE_HOACH_TRIEN_KHAI_AI20K-075_PRO.md) — RBAC 7 vai trò, API contract, sprint plan.
  - [docs/schema.sql](docs/schema.sql) — thiết kế DB v2.0 (đã hiện thực bằng ORM + migration).
  - [docs/guide/](docs/guide/) — Technical Guidebook 10 chương của BTC.

> ⚠️ PRD mô tả sản phẩm **mục tiêu**. Xem §3 để biết cái gì đã có thật. Đừng giả định một tính năng tồn tại chỉ vì nó nằm trong PRD.

---

## 2. Tech stack (thực tế trong repo)

| Layer | Công nghệ | Ghi chú |
|-------|-----------|---------|
| Frontend | **Next.js 16.2.7** + React 19 + Tailwind v4 | `frontend/`, App Router, `recharts`, `lucide-react`, `react-markdown` |
| Backend | FastAPI + Uvicorn (Python 3.11) | `src/` |
| Database | **PostgreSQL (Neon)** + SQLAlchemy 2.0 + Alembic | đã triển khai; driver `psycopg` (v3) |
| Auth | JWT (`pyjwt`) + `bcrypt` | access/refresh token, RBAC 7 vai trò |
| AI Agent | LangGraph + LangChain | **Multi-agent** `StateGraph`: Supervisor điều phối ↔ data/stat/pandas agent |
| LLM | `langchain-openai`, mặc định `gpt-4o-mini` | cấu hình qua `src/config.py` / `.env` |
| Test / Lint | pytest + httpx · Ruff (line-length 120, double quotes) | CI bắt buộc pass |
| DevOps | Docker, docker-compose, GitHub Actions | `Dockerfile`, `.github/workflows/ci.yml` |

> ✅ **Agent đã chuyển sang multi-agent + đọc DB:** cả backend CRUD/auth/analytics **và** chat agent đều chạy trên **PostgreSQL (Neon)**. Hệ agent gồm **Supervisor** điều phối 3 sub-agent: `data_agent` (truy vấn ORM), `stat_agent` (thống kê/chỉ số), `pandas_agent` (SQL thô qua guardrail). Code ReAct + 8 grade tools đọc CSV cũ đã chuyển vào `src/agents/old/` (legacy). Xem §6.

---

## 3. Trạng thái hiện tại vs mục tiêu

**Backend — đã có và chạy được:**
- **DB tầng persistence**: 21 ORM models ([src/models/tables.py](src/models/tables.py)) + Alembic migration đã áp lên Neon; lớp đo lường độ khó (`mv_exam_difficulty`, `v_normalized_scores`) + hàm `calc_subject_average`.
- **Model điểm**: `scores` dùng `score_category` (ORAL/REGULAR/MIDTERM/FINAL) + `column_index` — Miệng×3, TX×4, GK×2, CK×1. ĐTB HK = Σ(hệ_số×điểm)/Σ(hệ_số) với hệ số Miệng/TX=1, GK=2, CK=3 ([src/services/scoring.py](src/services/scoring.py)). ĐTB CN = (HK1 + 2·HK2)/3. *(exam_papers giữ enum cũ `score_type`.)*
- **Môn theo cấp**: `subjects.applicable_level` (THCS/THPT…) + `assessment_type` — SCORED (cho điểm) hoặc REMARK (Đạt/CĐ, **không** tính ĐTB; vd GD thể chất, Âm nhạc, GDQP-AN…). Seed môn nhận xét: [scripts/seed_remark_subjects.py](scripts/seed_remark_subjects.py).
- **Đánh giá định tính**: `subject_evaluations` (GV bộ môn: nhận xét học tập / Đạt-CĐ) + `student_term_reports` (GV chủ nhiệm: hạnh kiểm + đánh giá chung). Tổng hợp lớp ([src/api/v1/gradebook.py](src/api/v1/gradebook.py)) gộp ĐTB môn SCORED + hạnh kiểm + đánh giá chung.
- **Auth + RBAC**: JWT login/refresh/logout/me ([src/api/v1/auth.py](src/api/v1/auth.py)); 7 vai trò + Row-Level Security cho điểm ([src/services/rbac.py](src/services/rbac.py)); quản lý user + phân công.
- **Phân công giảng dạy** ([src/services/assignments.py](src/services/assignments.py)): GV có `subject_id` (môn phụ trách); mỗi GV chỉ chủ nhiệm 1 lớp/năm; nhận chủ nhiệm → tự dạy môn phụ trách cho lớp đó. GV bộ môn dạy nhiều lớp được phân công. **BGH (PRINCIPAL) không sửa điểm**; GV chủ nhiệm cấp 2/3 chỉ xem bảng tổng hợp + nhập hạnh kiểm/đánh giá chung.
- **CRUD endpoints** (`/api/v1/*`, xem §5): cấu trúc trường, học sinh/ghi danh, điểm (lọc + batch + duyệt). Mọi endpoint data đã được bảo vệ bằng auth + role.
- **Chat agent (multi-agent)**: LangGraph `StateGraph` ([src/agents/graph.py](src/agents/graph.py)) — entry là **Supervisor** ([src/agents/supervisor/](src/agents/supervisor/)) định tuyến (`RouterDecision`) sang `data_agent`/`stat_agent`/`pandas_agent`, các sub-agent quay lại Supervisor tới khi `FINISH` thì LLM tổng hợp câu trả lời. Sub-agent đọc **DB**: `data_agent` (ORM `SessionLocal`), `pandas_agent` (SQL thô qua guardrail SQLGlot). `POST /api/v1/chat` set `school_id`/`role` vào `ContextVar` để tool tự lọc theo trường.

**Frontend — đã có:**
- Dashboard mock ([frontend/src/app/page.tsx](frontend/src/app/page.tsx)) — metrics + biểu đồ recharts + AI Highlights, **dữ liệu hardcode, chưa gọi API**, theme tối.
- Chat UI ([frontend/src/app/chat/page.tsx](frontend/src/app/chat/page.tsx)) — gọi `POST /api/v1/chat` thật.
- Sidebar 2 mục ([frontend/src/components/Sidebar.tsx](frontend/src/components/Sidebar.tsx)).

**Đang làm / mục tiêu kế tiếp:**
- **Frontend redesign theo phong cách vnEdu** (xem §6) + trang **Đăng nhập** (lưu JWT), **gọi API thật** thay mock.
- **Trang quản lý điểm theo role** (BGH xem toàn trường; GV nhập/sửa theo phân công) — wire vào `/api/v1/scores` + RBAC.
- Dashboard nối API thật (cần thêm **analytics endpoints** `/api/v1/analytics/*` — **chưa có**).
- Backend còn thiếu: import Excel (`/scores/import`), export PDF/Word.
- **RAG (Vector Store/ChromaDB): đang chờ, CHƯA triển khai** — có biến cấu hình `chroma_persist_dir` ([src/config.py](src/config.py)) nhưng chưa có luồng nạp/truy vấn embeddings trong code.
- ✅ Đã xong (so với kế hoạch cũ): multi-agent + agent đọc DB; Text-to-SQL có guardrail SQLGlot ([src/core/security/sql_validator.py](src/core/security/sql_validator.py)); analytics endpoints `/api/v1/analytics/*`.
- ✅ Sinh câu hỏi v2 ([src/services/item_generation.py](src/services/item_generation.py)): grounding kiểm chứng thật (đối chiếu quote với context, chuẩn hóa NFC), tách `grounding_context` không nhãn nguồn khỏi context cho LLM (chặn giả mạo guardrail), Bloom phân loại độc lập + agent phản biện (critic) chạy song song, dedup embedding + overgen, misconception-driven distractors (bảng `misconceptions`, mock môn Toán — [scripts/seed_misconceptions_toan.py](scripts/seed_misconceptions_toan.py)), calibration loop (`/question-bank/calibration`, `/question-bank/items/{id}/retire`, mock thống kê — [scripts/seed_item_stats_toan.py](scripts/seed_item_stats_toan.py)), báo lỗi nền khi sinh câu thất bại.

---

## 4. Lệnh thường dùng

Shell mặc định: **PowerShell trên Windows** (Makefile dùng cú pháp Unix — chạy lệnh trực tiếp khi cần).

**Backend** (thư mục gốc, đã activate `.venv`):
```powershell
uvicorn src.main:app --reload --port 8000   # API → http://localhost:8000 (docs: /docs)
pytest tests/ -v                             # test (mock LLM, không chạm DB)
ruff check src/ tests/                        # lint (CI bắt buộc pass) — thêm --fix để auto-sửa
alembic upgrade head                          # áp migration lên DB (Neon)
alembic revision --autogenerate -m "..."      # sinh migration mới từ ORM
python scripts/create_admin.py --email <e> --password <p>   # tạo admin đầu tiên
```

**Frontend** (`frontend/`):
```powershell
npm install
npm run dev      # next dev --webpack → http://localhost:3000
npm run build && npm run lint
```
Cần `frontend/.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8000`.

---

## 5. Backend: API & RBAC (để frontend tích hợp)

Tất cả dưới prefix `/api/v1`. Đăng nhập trả `access_token` (Bearer) — gắn header `Authorization: Bearer <token>` cho mọi request data.

| Nhóm | Endpoints | Quyền |
|------|-----------|-------|
| Auth | `POST /auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me` | public (trừ `/me`) |
| Users | `GET /users` (`q`/`role`/`is_active`/`school_id`/`page` → `{items,total}`), `POST/PATCH /users`, `POST /users/{id}/reset-password`, `POST/DELETE /users/assignments`, `/users/{id}/assignments`, `/users/{id}/assignment-options`, `GET /users/assignments/coverage`, `/coverage-filters` | đọc: ADMIN/PRINCIPAL (PRINCIPAL scoped trường mình) · ghi: **ADMIN** (MVP: ADMIN thấy mọi trường) |
| Cấu trúc trường | `/academic-years`, `/semesters`, `/grades`, `/classes`, `/subjects` (CRUD; subject có `applicable_level`+`assessment_type`); `GET /classes/accessible?academic_year_id=` (lớp user có quyền, theo RBAC) | đọc: mọi user · ghi: ADMIN |
| Học sinh | `/students` (CRUD + `/students/search?q=`), `/enrollments` | ghi: ADMIN/PRINCIPAL |
| Điểm | `GET/POST /scores` (filter `score_category`), `/scores/batch`, `PATCH/DELETE /scores/{id}` | đọc: theo RLS · ghi: theo phân công · duyệt: ADMIN/PRINCIPAL |
| Bảng điểm | `GET /scores/gradebook` (chi tiết môn: SCORED→điểm+nhận xét, REMARK→Đạt/CĐ), `GET /scores/class-summary` (tổng hợp lớp: ĐTB + hạnh kiểm + đánh giá chung) | đọc theo RLS; phải đăng ký TRƯỚC `/scores/{id}` |
| Đánh giá | `PUT /scores/subject-eval` (GV bộ môn: nhận xét/Đạt-CĐ), `PUT /scores/term-report` (GV chủ nhiệm: hạnh kiểm + đánh giá chung) | theo phân công môn/chủ nhiệm |
| Đề thi | `POST /exam-papers` (upload file), `GET /exam-papers`, `GET /exam-papers/{id}/file` (preview), `DELETE` | upload: mọi user · xóa: ADMIN |
| Map đề | `POST/GET /scores/mappings`, `DELETE /scores/mappings/{id}` | GV bộ môn map TX (lớp); Trưởng bộ môn map GK/CK (khối) |
| Analytics | `GET /analytics/overview` (metrics + phân bố + xu hướng học lực theo khối) | theo RLS |
| Chat AI | `POST /chat` (multi-agent), `GET /status` | đã gắn auth (`CurrentUser`); set `school_id`/`role` vào ContextVar để agent lọc theo trường |
| Health | `GET /health` (ping DB) | public |

**RBAC (7 vai trò)** ở [src/services/rbac.py](src/services/rbac.py): `ADMIN`, `PRINCIPAL` xem toàn trường (PRINCIPAL **read-only điểm**); `GRADE_HEAD_PRIMARY`, `HOMEROOM_TEACHER_*`, `SUBJECT_TEACHER`, `SUBJECT_HEAD` bị giới hạn theo `teacher_assignments`. Hàm quyền: `can_write_score`, `can_edit_subject_eval` (GV bộ môn), `can_edit_term_report` (GV chủ nhiệm), `can_map`. `scores.entered_by`/`evaluated_by` server tự gán từ user đăng nhập (frontend **không** gửi).

---

## 6. Frontend: hướng thiết kế vnEdu

Mục tiêu giao diện bám **layout/phong cách cổng vnEdu** (sạch, sáng, kiểu portal hành chính giáo dục), áp dụng cho 3 nhóm chức năng của AI20K (không sao chép forum/tiện ích của vnEdu).

- **Layout chung**: top bar (logo trường + tên hệ thống + user/Đăng xuất), **sidebar trái** điều hướng, khối "Hỗ trợ kỹ thuật". Tham chiếu mockup [docs/gate_1/ui_gate_1.png](docs/gate_1/ui_gate_1.png).
- **Trang dự kiến** (App Router):
  - `/login` — đăng nhập (email/password → JWT), lưu token, redirect theo role.
  - `/` — **Dashboard** trực quan hóa toàn trường (recharts): GPA trend, phân bố học lực, AI Highlights. Lọc theo khối/lớp/môn/học kỳ.
  - `/scores` (quản lý điểm) — bảng xem/nhập/sửa điểm **theo role** (GV nhập lớp được phân công; BGH xem toàn trường, read-only).
  - `/chat` — trợ lý AI (đã có).
- **Tích hợp API**: gắn Bearer token; xử lý 401 (redirect login) / 403 (ẩn nút theo role). Ẩn/hiện chức năng theo `role` từ `/auth/me`.

**🎨 Bảng màu thương hiệu (hướng giáo dục):** chủ đạo **`#0D4D8B`** (xanh dương đậm), nhấn **`#C72127`** (đỏ). Khai báo token Tailwind v4 ở [frontend/src/app/globals.css](frontend/src/app/globals.css) (`@theme`: thang `brand-50..900`, `accent-*`) → dùng utility `bg-brand`, `text-brand`, `bg-accent`… Giữ **cả light (mặc định, portal vnEdu) + dark**. Quy ước: brand cho nút chính/link/active, `accent` cho điểm nhấn; **giữ** `rose`/`emerald`/`amber` cho ngữ nghĩa lỗi/thành công/cảnh báo.

**Quy ước UI chung:**
- **Dropdown >5 mục** phải có ô tìm kiếm (lọc không dấu). Dùng component [frontend/src/components/SearchableSelect.tsx](frontend/src/components/SearchableSelect.tsx) (≤5 mục render `<select>` thường, >5 mục tự bật ô tìm). Áp dụng cho bảng điểm, phân quyền, các form CRUD.
- **Bộ lọc bảng điểm** (`/gradebook`): **không** có ô "Cấp học". Mặc định **niên khóa hiện tại** (`AcademicYear.is_current`); chỉ **ADMIN/PRINCIPAL** (`APPROVE_ROLES`) được chọn niên khóa trước, GV khóa ở niên khóa hiện tại. Dropdown Lớp/Khối chỉ hiển thị lớp **user có quyền** — lấy từ `GET /classes/accessible?academic_year_id=` ([src/services/rbac.py](src/services/rbac.py) `accessible_class_ids`), tránh chọn lớp không có quyền rồi tưởng lỗi.

> ⚠️ Dashboard cũ từng mock **Khối 10–12**, còn dữ liệu seed là **Khối 6–9 (THCS)**. Schema DB hỗ trợ cả K-12 — bám dữ liệu thật khi nối API.

---

## 7. Quy ước code (bắt buộc)

**Python** (xem [docs/guide/code-style/python.md](docs/guide/code-style/python.md)):
- Type hints bắt buộc, luôn có return type. Tối đa **30 dòng/function**, **3 tham số** (nhiều hơn → Pydantic model).
- Docstring tiếng Việt cho public functions. Import order: stdlib → third-party → local (`src.*`).
- Bắt exception cụ thể, **không** bare `except:`. Ruff: `py311`, line-length 120, double quotes — không pass ruff thì CI reject.
- **Kiến trúc backend phân lớp**: `schemas/` (Pydantic DTO) → `repositories/` (CRUD) → `api/v1/` (router) → `services/` (logic nghiệp vụ như rbac). Giữ đúng tầng khi thêm tính năng.

**Frontend:** TypeScript, App Router, Tailwind utility classes, UI/comment tiếng Việt theo style hiện có.

**Naming:** file/function `snake_case`, class `PascalCase`, constant `UPPER_SNAKE`.

---

## 8. Lưu ý quan trọng (gotchas)

- **🚨 Next.js bản breaking changes** ([frontend/AGENTS.md](frontend/AGENTS.md)): API/convention có thể KHÁC training data. **Đọc `node_modules/next/dist/docs/` trước khi viết frontend.** Dev server `--webpack` (không Turbopack).
- **Alembic phải dùng endpoint Neon TRỰC TIẾP**: pooler (`-pooler`) ở transaction-mode phá vỡ transaction DDL. [alembic/env.py](alembic/env.py) tự bỏ `-pooler`. App runtime vẫn dùng pooler bình thường.
- **Agent đọc DB qua 2 đường — cô lập theo trường (tenant) bằng `school_id`**: (1) tool ORM (`data_agent`) dùng `SessionLocal` + lọc `current_user_school_id`; (2) `pandas_agent` chạy SQL thô qua `execute_read_only_query` → **bắt buộc** đi qua `validate_and_secure_sql` ([src/core/security/sql_validator.py](src/core/security/sql_validator.py)): chỉ cho `SELECT`, whitelist 21 bảng, và **tự chèn điều kiện `school_id`** vào mọi SELECT. `school_id`/`role` được truyền qua `ContextVar` ([src/agents/context.py](src/agents/context.py)) — luôn `set` ở `/chat` và `reset` ở `finally`. *(CSV cũ `data_mock/data_mock.csv` + tool ở `src/agents/old/` chỉ còn là legacy, agent hiện tại không dùng.)*
- **JWT secret**: production **bắt buộc** đặt `JWT_SECRET_KEY` (≥32 byte) trong `.env`; default chỉ cho dev.
- **Test phải mock LLM**: fixture `mock_llm` ([tests/conftest.py](tests/conftest.py)). Tuyệt đối không gọi OpenAI thật trong test/CI. Test data/auth chạy **offline** (không chạm Neon).
- **AI logging hooks BẮT BUỘC**: [.claude/settings.json](.claude/settings.json) log prompt/tool-call vào `.ai-log/`; `git push` tự submit lên server BTC (pre-push hook). **Không xóa/sửa** các hook này (cả `.cursor/`, `.codex/`, `.gemini/`, `.github/hooks/`).
- **Multi-agent — giữ đồng bộ prompt ↔ định tuyến**: tên sub-agent trong `RouterDecision` + `SUPERVISOR_PROMPT` ([src/agents/supervisor/node.py](src/agents/supervisor/node.py)) phải khớp các node đăng ký ở `build_graph` ([src/agents/graph.py](src/agents/graph.py)) và nhánh `route_next` (`data_agent`/`stat_agent`/`pandas_agent`/`FINISH`). Thêm/sửa sub-agent thì cập nhật cả 3 chỗ. Supervisor dùng `with_structured_output` (OpenAI) hoặc `bind_tools` + parse thủ công (DeepSeek).
- `.env` **không commit** (đã gitignore). Dùng [.env.example](.env.example) làm mẫu.

---

## 9. Git & quy trình (chuẩn doanh nghiệp)

- Branch: `main` (prod) ← `feature/*`. **Không commit thẳng `main`.** PR review + CI (ruff + pytest) xanh trước merge.
- Commit/push **chỉ khi user yêu cầu**. Trước push: chạy `ruff check` + `pytest`. Commit message kết thúc bằng:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

---

## 10. Bản đồ thư mục

```
src/
  main.py                  # FastAPI app + CORS + /health + handler IntegrityError
  config.py                # Pydantic Settings (env: DB, JWT, LLM)
  core/security.py         # bcrypt + JWT (access/refresh)
  db/                      # Base, engine, SessionLocal, get_db
  models/
    tables.py              # 19 ORM models (khớp docs/schema.sql)
    enums.py               # PG enum (StrEnum)
    schemas.py             # Pydantic ChatRequest/ChatResponse (cho agent)
  schemas/                 # Pydantic DTO cho API data (auth, user, school, student, score)
  repositories/base.py     # CRUDBase generic
  services/
    llm.py                 # khởi tạo ChatOpenAI
    rbac.py                # Row-Level Security + quyền nhập điểm/đánh giá
    scoring.py             # cấu trúc cột điểm + công thức ĐTB/học lực
    assignments.py         # nghiệp vụ phân công (1 chủ nhiệm/năm + tự dạy môn phụ trách)
  api/
    deps.py                # get_db, get_current_user, require_roles
    crud_router.py         # factory sinh router CRUD (có auth + role)
    routes.py              # /chat, /status (agent)
    v1/                    # auth, users, school, students, scores, gradebook, mappings, exam_papers, analytics
  agents/                  # Multi-agent LangGraph: graph.py · state.py · context.py · helpers.py
    supervisor/            #   điều phối (RouterDecision) + tổng hợp câu trả lời cuối
    data_agent/            #   tra cứu hồ sơ/bảng điểm qua ORM (SessionLocal)
    stat_agent/            #   thống kê + chỉ số học vụ (GDI, Delta G, Momentum…)
    pandas_agent/          #   SQL thô qua guardrail (sql_validator)
    old/                   #   LEGACY: ReAct + 8 grade tools đọc CSV (không dùng)
  core/security/sql_validator.py  # guardrail SQLGlot: SELECT-only + whitelist + chèn school_id
alembic/                   # migration (env.py dùng endpoint Neon trực tiếp)
tests/                     # pytest (mock_llm; test data/auth/assignments/gradebook offline)
scripts/create_admin.py    # bootstrap tài khoản ADMIN
scripts/seed_remark_subjects.py  # seed môn đánh giá nhận xét (Đạt/CĐ) theo cấp
frontend/src/app/          # Next.js App Router (page.tsx dashboard, chat/, layout.tsx)
frontend/src/components/    # Sidebar...
data_mock/data_mock.csv    # LEGACY: nguồn dữ liệu của agent CSV cũ (src/agents/old/); agent hiện đọc DB
docs/gate_1/               # PRD, kế hoạch, UI mockup · docs/schema.sql · docs/guide/
```
