"""DAG 2 — markdown_to_qdrant_ingestion.

clean_md/*.md -> semantic chunk theo heading -> embedding (OpenAI) ->
upsert vào Qdrant (idempotent theo hash) -> dọn file tạm.

Trigger: tự động từ DAG 1 (TriggerDagRunOperator), conf={md_key, mon, lop, chuong}.
"""

from datetime import timedelta

import pendulum
from airflow.decorators import dag, task
from edu_pipeline import config, qdrant_io, s3_io
from edu_pipeline.alerts import slack_on_failure
from edu_pipeline.chunking import semantic_chunk
from edu_pipeline.embedding import embed_with_gemini, embed_with_local, embed_with_openai

_DEFAULT_ARGS = {
    "owner": "edu-knowledge",
    "retries": 3,
    "retry_delay": timedelta(seconds=30),
    "on_failure_callback": slack_on_failure,
}


@dag(
    dag_id="markdown_to_qdrant_ingestion",
    description="Markdown sạch -> Vector Qdrant",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args=_DEFAULT_ARGS,
    tags=["rag", "ingestion"],
    params={"md_key": "", "mon": "", "lop": "", "chuong": ""},
)
def markdown_to_qdrant_ingestion():
    bucket = config.minio_bucket()

    @task
    def semantic_chunker(**ctx) -> list[dict]:
        """Cắt Markdown theo thẻ #/##/### — không làm đứt gãy bài học/định lý."""
        params = ctx["params"]
        markdown = s3_io.get_text(bucket, params["md_key"])
        chunks = semantic_chunk(markdown)
        for chunk in chunks:
            chunk["payload"] = {
                "mon": params["mon"], "lop": params["lop"], "chuong": params["chuong"],
                "heading": chunk["heading"], "source_md": params["md_key"], "text": chunk["text"],
            }
        return chunks

    @task(retries=3, retry_exponential_backoff=True, max_retry_delay=timedelta(minutes=5))
    def embedding(chunks: list[dict]) -> list[dict]:
        """[CỐT LÕI RAG] Biến các mảnh văn bản thành vector (local BGE-m3 / OpenAI / Gemini)."""
        if not chunks:
            return []
        texts = [c["text"] for c in chunks]
        provider = config.embedding_provider()
        if provider == "local":
            vectors = embed_with_local(texts, config.local_embed_model(), config.embedding_dim())
        elif provider == "gemini":
            vectors = embed_with_gemini(texts, config.gemini_api_key(), config.gemini_embed_model(), config.embedding_dim())
        else:
            vectors = embed_with_openai(texts, config.openai_api_key(), config.embedding_model())
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk["vector"] = vector
        return chunks

    @task
    def upsert_to_qdrant(chunks: list[dict]) -> int:
        """Đẩy Vector + Metadata vào Qdrant. ID = hash(text) -> idempotent."""
        cfg = config.qdrant_config()
        client = qdrant_io.get_client(cfg.url, cfg.api_key)
        qdrant_io.init_collection(client, cfg.collection, config.embedding_dim())
        return qdrant_io.upsert_chunks(client, cfg.collection, chunks)

    @task(trigger_rule="all_success")
    def cleanup_temp(**ctx) -> None:
        """Xóa file tạm md_chunks/raw_chunks trên S3 sau khi upsert THÀNH CÔNG.

        Dùng all_success (không all_done) để nếu embedding/upsert fail thì task này
        upstream_failed -> DAG run được đánh dấu FAILED (không bị cleanup che giấu lỗi).
        """
        md_key = ctx["params"]["md_key"]
        stem = md_key.removeprefix("clean_md/").removesuffix(".md")
        for prefix in (f"raw_chunks/{stem}/", f"md_chunks/{stem}/"):
            try:
                s3_io.delete_prefix(bucket, prefix)
            except Exception:  # noqa: BLE001 — dọn rác không được phép làm hỏng DAG
                pass

    chunks = semantic_chunker()
    embedded = embedding(chunks)
    upserted = upsert_to_qdrant(embedded)
    upserted >> cleanup_temp()


markdown_to_qdrant_ingestion()
