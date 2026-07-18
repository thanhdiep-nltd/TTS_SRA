# Architecture Diagram — AI20K-075

> Hệ Trợ lý Phân tích Kết quả Học tập Toàn trường (Conversational BI + Learning Analytics) cho Ban Giám Hiệu K‑12.
> Sơ đồ phản ánh **kiến trúc thực tế trong repo** (`src/`, `frontend/src/`). Cập nhật cho hệ **multi-agent**.

## 1. System Overview

```mermaid
graph TB
    User([Người dùng]) --> UI["Frontend<br/>Next.js 16 / React 19"]
    UI -->|"REST + Bearer JWT"| API["FastAPI Backend"]

    subgraph Backend["FastAPI Backend"]
        REST["REST /api/v1/* (CRUD · Analytics)"]
        AUTH["Auth JWT + RBAC (rbac.py)"]
        CHAT["/api/v1/chat"]
    end
    API --> REST --> AUTH
    API --> CHAT

    subgraph AgentSys["LangGraph Multi-Agent"]
        SUP["Supervisor<br/>(điều phối + tổng hợp)"]
        DA["data_agent (ORM)"]
        SA["stat_agent (chỉ số)"]
        PA["pandas_agent (SQL)"]
    end
    CHAT --> SUP
    SUP <--> DA
    SUP <--> SA
    SUP <--> PA

    SUP --> LLM["LLM Service<br/>OpenAI gpt-4o-mini / DeepSeek"]
    AUTH --> DB[("PostgreSQL / Neon")]
    DA --> DB
    SA --> DB
    PA -->|"qua SQL Guardrail (SQLGlot)"| DB

    VS["Vector Store / ChromaDB<br/>(RAG — ĐANG CHỜ, chưa triển khai)"]:::pending
    SUP -.->|"dự kiến"| VS

    classDef pending fill:#f3f4f6,stroke:#9ca3af,stroke-dasharray:5 5,color:#6b7280;
```

## 2. Multi-Agent Flow (`src/agents/graph.py`)

Entry point là **Supervisor**. Mỗi vòng, Supervisor (LLM `with_structured_output(RouterDecision)`) chọn sub‑agent kế tiếp hoặc `FINISH`; sub‑agent chạy xong **quay lại Supervisor**. Khi `FINISH`, Supervisor gọi LLM lần cuối để **tổng hợp** câu trả lời (Markdown, tiếng Việt, không lộ tên agent kỹ thuật).

```mermaid
stateDiagram-v2
    [*] --> Supervisor
    Supervisor --> data_agent: next_agent = data_agent
    Supervisor --> stat_agent: next_agent = stat_agent
    Supervisor --> pandas_agent: next_agent = pandas_agent
    Supervisor --> [*]: FINISH → tổng hợp câu trả lời
    data_agent --> Supervisor
    stat_agent --> Supervisor
    pandas_agent --> Supervisor
```

| Sub-agent | Vai trò | Nguồn dữ liệu |
|-----------|---------|---------------|
| `data_agent` | Tra cứu hồ sơ học sinh, bảng điểm chi tiết/lớp | **ORM** (`SessionLocal` + `models.tables`), lọc `school_id` |
| `stat_agent` | Thống kê, thủ khoa/HS yếu, xu hướng, chỉ số GDI · Delta G · Momentum | ORM/helpers |
| `pandas_agent` | SQL thô / phân tích động phức tạp (tương quan…) | **SQL** qua `execute_read_only_query` → guardrail |

## 3. Chat request — luồng xử lý

```mermaid
sequenceDiagram
    actor U as BGH
    participant FE as chat/page.tsx
    participant API as api/routes /chat (CurrentUser)
    participant CTX as ContextVar(school_id, role)
    participant G as LangGraph agent
    participant SUP as Supervisor (LLM)
    participant SA as sub-agent
    participant GR as sql_validator (SQLGlot)
    participant DB as PostgreSQL
    participant LLM as LLM Provider

    U->>FE: câu hỏi (tiếng Việt)
    FE->>API: POST /api/v1/chat {message} (Bearer)
    API->>CTX: set school_id + role từ JWT
    API->>G: ainvoke({query, school_context})
    loop tới khi FINISH
        G->>SUP: state(messages)
        SUP->>LLM: RouterDecision (chọn agent)
        alt cần dữ liệu
            SUP->>SA: instruction
            SA->>GR: (pandas) validate_and_secure_sql(SELECT)
            GR->>GR: chặn non-SELECT · whitelist bảng · chèn school_id
            SA->>DB: ORM / SQL đã lọc
            DB-->>SA: kết quả
            SA-->>SUP: messages
        else đủ thông tin
            SUP->>LLM: tổng hợp câu trả lời cuối
        end
    end
    G-->>API: {response, messages}
    API->>API: dựng Thought Trace (AIMessage/ToolMessage)
    API->>CTX: reset ContextVar
    API-->>FE: ChatResponse {response, analysis}
```

## 4. Bảo mật — cô lập theo trường (tenant isolation)

```mermaid
graph LR
    A["1) JWT Auth — get_current_user → school_id, role"] --> B
    B["2) RBAC / RLS — rbac.py (accessible_score_filter, accessible_class_ids…)"] --> C
    C["3) SQL Guardrail — sql_validator.py: SELECT-only · whitelist 21 bảng · chèn school_id"]
    C --> DB[("Neon")]
```

`/chat` truyền `school_id`/`role` qua `ContextVar` ([src/agents/context.py](../src/agents/context.py)); tool ORM lọc `school_id`, còn SQL thô của `pandas_agent` bắt buộc qua guardrail [src/core/security/sql_validator.py](../src/core/security/sql_validator.py).

## 5. Component Details

| Component | Technology | Purpose | File |
|-----------|-----------|---------|------|
| Frontend | Next.js 16 / React 19 / Tailwind v4 | Dashboard · Bảng điểm · Quản lý điểm · Chat · Admin | `frontend/src/` |
| Backend | FastAPI / Uvicorn | REST API + Auth + Analytics | `src/main.py`, `src/api/` |
| Supervisor | LangGraph + LLM | Điều phối sub-agent + tổng hợp trả lời | `src/agents/supervisor/` |
| Sub-agents | LangGraph nodes | data / stat / pandas | `src/agents/{data_agent,stat_agent,pandas_agent}/` |
| LLM | OpenAI `gpt-4o-mini` / DeepSeek | Reasoning + tổng hợp | `src/services/llm.py`, `src/config.py` |
| SQL Guardrail | SQLGlot | SELECT-only + whitelist + chèn `school_id` | `src/core/security/sql_validator.py` |
| Database | PostgreSQL (Neon) | 21 bảng + view độ khó | `src/models/tables.py`, Alembic |
| Vector Store | ChromaDB | **RAG / embeddings — ĐANG CHỜ, CHƯA triển khai** | (cfg `chroma_persist_dir`) |

> ⚠️ **RAG chưa triển khai:** mới có biến cấu hình `chroma_persist_dir` trong [src/config.py](../src/config.py); chưa có luồng nạp/truy vấn embeddings. Khi triển khai, dự kiến nối vào Supervisor như một nguồn ngữ cảnh (đường nét đứt ở sơ đồ §1).
>
> 📄 Sơ đồ chi tiết hơn (component frontend/backend, ER, deployment): xem `private_docs/architecture.md` (tài liệu nội bộ).
