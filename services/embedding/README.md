# Embedding Service (sidecar)

Microservice nhúng ngữ nghĩa cho luồng **RAG retrieval**. Chạy `BAAI/bge-m3`
(sentence-transformers, 1024 chiều, chuẩn hóa L2) — **khớp tuyệt đối** không gian
vector đã index trong Qdrant bởi pipeline ingestion (`pipelines/airflow`).

Tách riêng khỏi backend FastAPI (`src/`) để API nghiệp vụ giữ nhẹ, không kéo theo
torch (~2.5GB). Backend gọi service này qua HTTP (`EMBEDDING_SERVICE_URL`).

## API
- `GET  /health` → `{status: "ready"|"loading", model}`
- `POST /embed`  body `{"texts": ["..."]}` → `{model, dim, vectors: [[...]]}`

## Biến môi trường
- `LOCAL_EMBED_MODEL` (mặc định `BAAI/bge-m3`) — **phải khớp pipeline**.
- `EMBEDDING_DIM` (1024), `EMBED_BATCH_SIZE` (12), `HF_HOME` (`/opt/hf_cache`).

## Chạy local
```bash
pip install -r requirements.txt
uvicorn app:app --port 8001
```

## Docker
```bash
docker build -t edu-embedding ./services/embedding
docker run -p 8001:8001 -v hf-cache:/opt/hf_cache edu-embedding
```
Lần đầu sẽ tải model ~2.2GB vào `HF_HOME` (mount volume để tái dùng).
