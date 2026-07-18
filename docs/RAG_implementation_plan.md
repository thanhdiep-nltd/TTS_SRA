# KẾ HOẠCH TRIỂN KHAI — Edu-Knowledge Ingestion Pipeline

**Dự án:** AI20K-075 · **Phân hệ:** Data Ingestion & Vectorization (RAG)
**Tài liệu thiết kế nguồn:** [docs/RAG_design.md](RAG_design.md) (v1.2.0)
**Phạm vi bản kế hoạch này:** **CHỈ Ingestion** (PDF → Vector DB). Retrieval (rag_agent) sẽ lập kế hoạch ở tài liệu riêng.
**Stack (đúng nguyên bản doc):** Apache Airflow · MinIO/S3 · Qdrant · DeepSeek-V3 (format) · OpenAI `text-embedding-3-small` (embedding).
**Ngày:** 23/06/2026

---

## 0. Nguyên tắc tích hợp repo

Pipeline là hệ **batch/offline, decoupled** khỏi FastAPI runtime. Chỉ chạm `src/` ở **một** chỗ: endpoint trigger. Mọi thứ còn lại nằm trong `pipelines/`.

| Điểm doc gốc | Thực tế repo | Quyết định |
|---|---|---|
| Trigger Spring Boot webhook | Backend FastAPI | `POST /api/v1/knowledge/ingest` → Airflow REST API |
| Vector DB Qdrant | Có sẵn `chroma_persist_dir` | Dùng **Qdrant**; `chroma_persist_dir` = deprecated cho luồng RAG |
| Hạ tầng Airflow/MinIO/Qdrant | Chưa có | `pipelines/airflow/docker-compose.airflow.yml` (tách compose app) |
| Pipeline trong monorepo | Cùng repo | Thư mục `pipelines/`, **không import `src/`** |
| Airflow metadata DB | App dùng Neon | Postgres **riêng** cho Airflow (không đụng Neon) |

---

## 1. Cấu trúc thư mục

```
pipelines/airflow/
  docker-compose.airflow.yml
  Dockerfile.worker
  requirements.airflow.txt
  constraints.txt                  # pin theo Airflow/Python version
  .env.airflow.example
  dags/
    hybrid_pdf_to_markdown.py      # DAG 1
    markdown_to_qdrant.py          # DAG 2
  plugins/edu_pipeline/
    __init__.py
    config.py                      # đọc Airflow Variables/Connections
    s3_io.py                       # MinIO/S3 get/put (S3Hook hoặc boto3)
    pdf_extract.py                 # PyMuPDF (Marker optional)
    chunking.py                    # chunk thô ~3000 token + semantic chunk
    hashing.py                     # SHA-256(text) → point ID
    deepseek_format.py             # gọi DeepSeek-V3 (httpx)
    embedding.py                   # OpenAI embedding (batch)
    qdrant_io.py                   # init collection + upsert idempotent
    alerts.py                      # Slack on_failure callback
  tests/
    test_chunking.py · test_hashing.py · test_qdrant_io.py
    test_deepseek_format.py · test_embedding.py · test_dags_import.py
src/api/v1/knowledge.py            # endpoint upload + trigger (ADMIN) — phần duy nhất trong src/
```

---

## 2. Hạ tầng (docker-compose.airflow.yml)

Executor: **LocalExecutor** (đủ cho MVP 1 worker; lên Celery sau nếu cần).

| Service | Ghi chú |
|---|---|
| `airflow-init` | `db migrate` + tạo user admin |
| `airflow-webserver` | UI :8080 |
| `airflow-scheduler` | scheduler + chạy task (LocalExecutor) |
| `postgres-airflow` | metadata DB riêng (KHÔNG dùng Neon) |
| `minio` + `mc` (init) | object store; tạo bucket `edu-knowledge` |
| `qdrant` | :6333 REST / :6334 gRPC; volume persistent |

**Layout MinIO:**
```
edu-knowledge/
  raw_pdf/{mon}_{lop}.pdf
  raw_text/{mon}_{lop}.txt
  raw_chunks/{mon}_{lop}/{index}.txt   # tránh nhồi text lớn vào XCom
  clean_md/{mon}_{lop}.md
```

---

## 3. Dependencies (requirements.airflow.txt)

```
apache-airflow==2.10.*                 # cài kèm constraints.txt đúng version
apache-airflow-providers-amazon        # S3Hook / S3KeySensor (MinIO qua endpoint_url)
apache-airflow-providers-slack
pymupdf
# marker-pdf                           # optional (nặng) — bật nếu OCR PyMuPDF kém
langchain-text-splitters               # MarkdownHeaderTextSplitter
tiktoken
openai>=1.0
httpx
qdrant-client
```
> ⚠️ Bắt buộc cài Airflow với constraints file đúng (Python 3.11) trong `Dockerfile.worker`, nếu không sẽ vỡ dependency.

---

## 4. Secrets & cấu hình (Airflow Connections/Variables)

Không để key trong Git (doc §5.1). Khai báo qua Airflow UI hoặc env `AIRFLOW_CONN_*` / `AIRFLOW_VAR_*`.

| Tên | Loại | Dùng cho |
|---|---|---|
| `aws_minio` | Connection (aws) | S3Hook → MinIO (`endpoint_url`, key) |
| `deepseek_api` | Connection/Variable | base `https://api.deepseek.com` + key |
| `openai_api` | Variable | OpenAI key |
| `qdrant` | Variable | host/port/api_key |
| `slack_alerts` | Connection (slack) | webhook `#data-alerts` |
| Variables: `chunk_token_size=3000`, `embedding_model=text-embedding-3-small`, `qdrant_collection=edu_knowledge` | Variable | tham số pipeline |

**Pool:** `deepseek_pool` slots=**5** (doc §5.3) gắn vào task `deepseek_formatting`.

Thêm vào app config ([src/config.py](../src/config.py)) cho endpoint trigger: `airflow_base_url`, `airflow_user`, `airflow_password`, `minio_endpoint`, `minio_access_key`, `minio_secret_key`, `minio_bucket`.

---

## 5. DAG 1 — `hybrid_pdf_to_markdown`

`default_args`: `retries` theo task, `on_failure_callback=alerts.slack_on_failure`. `max_active_runs=1`.

| Task | Operator | Triển khai | Retry/Lỗi |
|---|---|---|---|
| `sensor_check_s3` | `S3KeySensor` (conn `aws_minio`) | chờ `raw_pdf/{key}`; `mode="reschedule"`, poke 30s | timeout 300s |
| `local_raw_extraction` | `@task` PyMuPDF | PDF→text thô → ghi `raw_text/{key}.txt` | retries=2 |
| `chunk_raw_text` | `@task` (tiktoken) | cắt ~3000 token, overlap ~150; ghi từng chunk `raw_chunks/.../{i}.txt`; trả `list[{index, key}]` | local |
| `deepseek_formatting` | `@task.expand` (pool=`deepseek_pool`) | mỗi chunk → DeepSeek-V3 (prompt format §5.1); trả `{index, md_key}` | retries=5, `retry_exponential_backoff=True`, `max_retry_delay=300s`; xử lý 429 |
| `stitch_and_save_md` | `@task` | sort theo `index`, nối → `clean_md/{key}.md`; Slack warning nếu <1KB | — |
| `trigger_vector_dag` | `TriggerDagRunOperator` | `conf={md_key, mon, lop, chuong}` | — |

**Idempotency/XCom:** truyền **S3 key** giữa các task, KHÔNG truyền nội dung text (tránh giới hạn size XCom). Dynamic Task Mapping giữ thứ tự bằng `index`.

**Prompt DeepSeek (`deepseek_format.py`):**
```
Bạn là biên tập viên SGK. Dọn dẹp văn bản thô OCR dưới đây:
- Tái tạo cấu trúc tiêu đề bằng Markdown (#, ##, ###) theo bài học/mục.
- Chuyển MỌI biểu thức toán/công thức sang LaTeX ($...$ inline, $$...$$ block).
- Giữ nguyên 100% nội dung kiến thức, TUYỆT ĐỐI không thêm/bịa.
- Chỉ trả về Markdown, không lời dẫn.
```

---

## 6. DAG 2 — `markdown_to_qdrant_ingestion`

| Task | Operator | Triển khai | Retry/Lỗi |
|---|---|---|---|
| `semantic_chunker` | `@task` `MarkdownHeaderTextSplitter` | split `#`,`##`,`###`; mỗi chunk kèm `heading` path | cảnh báo nếu chunk rỗng/quá to |
| `openai_embedding` | `@task` | batch embed (100/lần) `text-embedding-3-small` | retries=3 |
| `upsert_to_qdrant` | `@task` qdrant-client | `PointStruct(id=SHA256(text), vector, payload)` | idempotent |
| `cleanup_temp` | `@task`/Bash | xóa file tạm worker | `trigger_rule="all_done"`, soft fail |

**Collection `edu_knowledge`** (`qdrant_io.init_collection`): tạo nếu chưa có, `size=1536`, `distance=Cosine`; payload index `mon`, `lop`, `chuong`.

**Metadata payload (chuẩn cho Retrieval về sau):**
```python
payload = {
  "mon": "toan", "lop": 9, "chuong": "Chương 1",
  "heading": "Bài 2 > Định lý Pytago",
  "source_md": "clean_md/toan_9.md",
  "text": "<nội dung chunk>",
  "ingested_at": "<iso8601>",
}
```

---

## 7. Trigger từ FastAPI (`src/api/v1/knowledge.py`)

Tuân thủ kiến trúc phân lớp + RBAC (chỉ `ADMIN`).

- `POST /api/v1/knowledge/upload` — upload PDF → MinIO `raw_pdf/` → gọi ingest.
- `POST /api/v1/knowledge/ingest` — gọi Airflow REST `POST /api/v1/dags/hybrid_pdf_to_markdown/dagRuns` với `conf`; trả `dag_run_id`.
- `GET /api/v1/knowledge/status/{dag_run_id}` (tùy chọn) — proxy trạng thái DagRun.

Đăng ký router trong [src/main.py](../src/main.py). Không để pipeline import ngược vào FastAPI.

---

## 8. Monitoring & Resilience (doc §5.2/5.3)

- `on_failure_callback` = `alerts.slack_on_failure` (`SlackWebhookHook`) → `#data-alerts`, nhấn mạnh task gọi API (429/timeout sau khi hết retry).
- Pool `deepseek_pool=5`; cân nhắc `openai_pool` nếu cần.
- `max_active_runs=1`/DAG; idempotency Qdrant đảm bảo retry an toàn.
- Đặt `execution_timeout` cho task gọi API tránh treo worker.

---

## 9. Testing (offline, mock API — theo quy ước repo)

| File | Kiểm tra |
|---|---|
| `test_chunking.py` | chunk ~3000 token đúng ranh giới, có overlap, không mất ký tự |
| `test_hashing.py` | cùng text → cùng ID; khác text → khác ID |
| `test_qdrant_io.py` | upsert 2 lần cùng text → 1 point (Qdrant `:memory:`) |
| `test_deepseek_format.py` / `test_embedding.py` | mock `httpx`/`openai`, không gọi API thật |
| `test_dags_import.py` | load mọi DAG: không lỗi cú pháp, không cycle |

**Tuyệt đối không gọi API thật trong test/CI.** Ruff áp dụng cho `pipelines/` (line-length 120, double quotes).

---

## 10. Lộ trình (milestones)

| # | Mục tiêu | Định nghĩa hoàn thành |
|---|---|---|
| **M1** | Hạ tầng | `docker-compose.airflow.yml` lên xanh (Airflow UI + MinIO + Qdrant); bucket + collection tạo; Connections/Variables/Pool khai báo |
| **M2** | Helpers + tests | `edu_pipeline/*` + unit test xanh (chưa cần API thật) |
| **M3** | DAG 1 | 1 PDF mẫu → `clean_md/*.md` (DeepSeek thật qua Connection) |
| **M4** | DAG 2 | `.md` → vectors → Qdrant; verify search 1 query |
| **M5** | Trigger FastAPI | endpoint upload/ingest + RBAC ADMIN; chạy full luồng từ API |
| **M6** | Hardening | Slack alert · pool · backoff · idempotency lặp · README vận hành |

---

## 11. Rủi ro & giảm thiểu

| Rủi ro | Giảm thiểu |
|---|---|
| Airflow dependency hell | Pin `constraints.txt` đúng Airflow/Python 3.11 trong Dockerfile |
| XCom size limit (text lớn) | Truyền S3 key, không truyền nội dung |
| DeepSeek/OpenAI 429/timeout | Backoff + pool + Slack; `execution_timeout` |
| OCR PyMuPDF kém với PDF scan ảnh | Đánh giá ở M3; fallback Marker/tesseract (optional) |
| Dim mismatch Qdrant ↔ model | Cố định `size=1536`, validate khi init collection |
| Trùng dữ liệu khi chạy lại | Point ID = SHA-256(text) → upsert idempotent |

---

## 12. Ngoài phạm vi (để tài liệu sau)

- **Retrieval / rag_agent:** thêm sub-agent vào Supervisor graph ([src/agents/graph.py](../src/agents/graph.py)), filter Qdrant theo `mon/lop/chuong`, đồng bộ RBAC.
- Chuyển MinIO → S3 thật khi deploy production.
- Celery executor + nhiều worker khi tải tăng.
