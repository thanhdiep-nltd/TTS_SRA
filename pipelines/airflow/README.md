# Edu-Knowledge Ingestion Pipeline (Airflow)

Pipeline batch nạp **sách giáo khoa PDF → vector Qdrant** cho hệ RAG.
Thiết kế: [docs/RAG_design.md](../../docs/RAG_design.md) · Kế hoạch: [docs/RAG_implementation_plan.md](../../docs/RAG_implementation_plan.md).

Decoupled khỏi app FastAPI — chỉ giao tiếp qua (1) Airflow REST API (trigger) và (2) collection Qdrant.

## Thành phần
- **DAG 1** `hybrid_pdf_to_markdown`: PDF → text thô (PyMuPDF, $0) → chunk ~3000 token → DeepSeek-V3 định dạng Markdown/LaTeX → `clean_md/*.md` → trigger DAG 2.
  - **Vision OCR provider** (môn nhiều công thức): chọn qua `VISION_PROVIDER` = `openai` (gpt-4o, `VISION_MODEL`), `gemini` (Gemini Flash, `GEMINI_MODEL`+`GEMINI_API_KEY`), hoặc `qwen` (qwen3-vl-flash qua DashScope OpenAI-compatible: `QWEN_MODEL`+`QWEN_API_KEY`+`QWEN_API_BASE`, tối ưu chi phí). DeepSeek API **không** hỗ trợ ảnh nên không dùng cho OCR.
- **DAG 2** `markdown_to_qdrant_ingestion`: semantic chunk theo heading → embedding OpenAI `text-embedding-3-small` → upsert Qdrant (idempotent theo hash) → dọn tạm.
- `plugins/edu_pipeline/`: thư viện dùng chung. `tests/`: unit test offline (mock API).

## Chạy hạ tầng
```bash
cd pipelines/airflow
cp .env.airflow.example .env.airflow        # điền DEEPSEEK/OPENAI/Slack key
docker compose -f docker-compose.airflow.yml --env-file .env.airflow up -d --build
```
- Airflow UI: http://localhost:8080 (airflow/airflow)
- MinIO Console: http://localhost:9001 · Qdrant: http://localhost:6333/dashboard
- Pool `deepseek_pool=5` và bucket `edu-knowledge` được tạo tự động khi init.

## Kích hoạt pipeline
Qua app FastAPI (chỉ ADMIN):
```
POST /api/v1/knowledge/upload   (multipart: file=PDF, mon, lop, chuong?)
POST /api/v1/knowledge/ingest   (PDF đã có trên MinIO: {s3_key, mon, lop, chuong})
GET  /api/v1/knowledge/status/{dag_run_id}
```
Hoặc trigger trực tiếp DAG `hybrid_pdf_to_markdown` trên Airflow UI với `conf={"s3_key","mon","lop","chuong"}`.

## Test offline
```bash
cd pipelines/airflow
python -m pytest -q       # chunking/hashing/format/embedding chạy được; qdrant/airflow auto-skip nếu thiếu lib
```

## Cần dữ liệu để chạy thật
Để chạy end-to-end (M3–M4) cần **file PDF sách giáo khoa mẫu** + **API key DeepSeek & OpenAI**. Đặt PDF lên MinIO `raw_pdf/{mon}_{lop}.pdf` rồi trigger.
