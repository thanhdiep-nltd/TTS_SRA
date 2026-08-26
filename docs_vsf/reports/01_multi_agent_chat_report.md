# BÁO CÁO — Multi-Agent Chat Flow

**Người viết**: [Tên] | **Ngày**: 26/08/2026

---

## 1. Giới thiệu

Multi-Agent Chat là trợ lý AI cho phép Ban Giám Hiệu và Giáo viên hỏi đáp bằng tiếng Việt tự nhiên về mọi dữ liệu học tập trong trường: điểm số, thống kê, báo cáo, kiến thức SGK. Thay vì một agent "làm tất cả", hệ thống dùng **Supervisor điều phối 4 sub-agent chuyên biệt**, mỗi agent làm một việc riêng.

---

## 2. Kiến trúc tổng quan

```
                         ┌──────────────┐
                         │  SUPERVISOR  │
                         │  (Router)    │
                         └──────┬───────┘
                    ┌───────────┼───────────┐
                    │           │           │
              ┌─────┴────┐ ┌───┴────┐ ┌────┴─────┐
              │   Data   │ │  Stat  │ │Knowledge │
              │ Service  │ │ Agent  │ │  Agent   │
              │  Agent   │ │        │ │  (RAG)   │
              └──────────┘ └────────┘ └────┬─────┘
                                           │
                                    ┌──────┴──────┐
                                    │   Report    │
                                    │   Agent     │
                                    └─────────────┘
```

**4 sub-agent:**
- **data_service_agent**: Tra cứu điểm, hồ sơ học sinh, lớp — dùng ORM (SQLAlchemy)
- **stat_agent**: Tính thống kê, chỉ số học thuật nâng cao (GDI, Delta G, Learning Momentum)
- **knowledge_agent**: Tra cứu nội dung SGK qua RAG (Qdrant vector search), có trích dẫn nguồn
- **report_agent**: Tạo báo cáo DOCX/PDF/HTML từ 4 mẫu chuẩn hoặc custom

---

## 3. Các thành phần chính

### Backend (Python/FastAPI)

| File | Vai trò |
|------|---------|
| src/agents/graph.py | Định nghĩa StateGraph: supervisor + 4 sub-agent + conditional edges |
| src/agents/supervisor/node.py | Supervisor: nhận câu hỏi → LLM quyết định next_agent |
| src/agents/data_service_agent/node.py | Data agent: tool ORM đọc DB (SessionLocal) |
| src/agents/stat_agent/node.py + tools.py | Stat agent: GDI, Delta G, Momentum, phân bố học lực |
| src/agents/knowledge_agent/node.py + tools.py | Knowledge agent: search_textbook → Qdrant → LLM |
| src/agents/report_agent/node.py + tools.py | Report agent: lấy dữ liệu → sinh DOCX/PDF/HTML |
| src/agents/context.py | ContextVar: current_user_school_id, role, user_id |
| src/agents/state.py | MultiAgentState: messages, next_agent, school_context |
| src/api/v1/chat.py | POST /chat (streaming), sessions, feedback, telemetry |
| src/services/eval.py | Faithfulness/Groundedness judge |
| src/observability.py | Prometheus metrics, Langfuse tracing |

### Frontend (Next.js)

| File | Vai trò |
|------|---------|
| frontend/src/app/chat/page.tsx | Giao diện chat: gửi câu hỏi, nhận streaming, file đính kèm |
| frontend/src/lib/api.ts | API client, tự động gắn Bearer token |

---

## 4. Luồng hoạt động chi tiết

### Bước 1: User gửi câu hỏi

User gõ: "Cho tôi xem điểm trung bình môn Toán lớp 9A"
- Frontend POST /api/v1/chat (kèm Bearer token)
- Backend: giải mã JWT → CurrentUser (id, role, school_id)
- Set ContextVar: current_user_school_id, current_user_role, current_user_id
- Lấy/Create session từ ai_sessions
- Ghép SystemMessage + HumanMessage + attachment block (nếu có file)
- Invoke agent graph: agent.ainvoke({messages, school_context})

### Bước 2: Supervisor định tuyến

Supervisor chạy LLM (gpt-4o-mini) với toàn bộ messages
- LLM trả về RouterDecision: {next_agent: "data_service_agent"}
- Graph route_next(): next_agent="data_service_agent" → chạy data_service_agent node

### Bước 3: Sub-agent xử lý

data_service_agent chạy ReAct loop:
- Tool 1: query ORM lấy scores WHERE subject=Toán, class=9A, school_id=X
- Tool 2: tính average
- LLM tổng hợp: "Điểm trung bình môn Toán lớp 9A là 7.8"
- Trả messages mới về Supervisor

Supervisor chạy lại:
- Quyết định: FINISH (đã trả lời xong)
- Vào END node

### Bước 4: Trả kết quả

StreamingResponse gửi token về frontend
- Frontend render real-time (react-markdown)
- Lưu lịch sử vào ai_messages
- Reset ContextVar
- Nền: Judge LLM chấm Faithfulness/Groundedness (5% sample)

---

## 5. Kết quả đạt được

| Hạng mục | Trạng thái | Chi tiết |
|----------|-----------|----------|
| Supervisor định tuyến | Hoạt động | RouterDecision với Structured Output, tự động detect agent |
| Data service agent | Hoạt động | ORM queries, tự lọc theo school_id |
| Stat agent | Hoạt động | GDI, Delta G, Momentum, phân bố học lực |
| Knowledge agent | Hoạt động | search_textbook → Qdrant → LLM, có trích dẫn nguồn |
| Report agent | Hoạt động | 4 mẫu báo cáo + custom, xuất DOCX/PDF/HTML |
| Chat streaming | Hoạt động | Token stream real-time, không chờ hết response |
| File attachments | Hoạt động | Upload file → trích xuất văn bản → inject vào context |
| Session management | Hoạt động | Tự động tạo/lưu session, đính kèm file |
| Eval (Faithfulness/Groundedness) | Hoạt động | Judge LLM chấm chất lượng câu trả lời |
| Prometheus metrics | Hoạt động | agent_requests_total, latency, rejections |
| Langfuse tracing | Hoạt động | Trace từng agent step |
| ContextVar tenant isolation | Hoạt động | Mỗi request set/reset school_id, chống rò rỉ |

---

## 6. Cách chạy thử

```bash
# 1. Khởi động backend
uvicorn src.main:app --reload --port 8000

# 2. Login lấy token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@admin.edu.vn", "password": "admin123"}'

# 3. Chat thử nghiệm
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id": null, "message": "Cho tôi xem điểm trung bình môn Toán của lớp 9A"}'

# 4. Kiểm tra agent status
curl http://localhost:8000/api/v1/status

# 5. Chạy test
pytest tests/test_agents/ -v
```

**Tài khoản demo:**
- ADMIN: admin@admin.edu.vn / admin123
- HIỆU TRƯỞNG: principal.c2@nguyendu.edu.vn / password123
- TRƯỞNG BỘ MÔN: teacher.c2.1@nguyendu.edu.vn / password123
