"""DAG 1 — hybrid_pdf_to_markdown.

PDF (S3) -> bóc tách text thô (PyMuPDF, local, $0) -> chunk ~3000 token
-> định dạng Markdown/LaTeX (DeepSeek-V3, Dynamic Task Mapping, pool giới hạn)
-> nối lại & ghi clean_md/*.md -> kích hoạt DAG 2.

Trigger: FastAPI POST /api/v1/knowledge/ingest -> Airflow REST API, truyền
conf={s3_key, mon, lop, chuong}.
"""

from datetime import timedelta

import pendulum
from airflow.decorators import dag, task
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from edu_pipeline import config, pdf_extract, s3_io
from edu_pipeline.alerts import slack_on_failure
from edu_pipeline.chunking import chunk_by_tokens
from edu_pipeline.deepseek_format import format_chunk

_DEFAULT_ARGS = {
    "owner": "edu-knowledge",
    "retries": 2,
    "retry_delay": timedelta(seconds=30),
    "on_failure_callback": slack_on_failure,
}


@dag(
    dag_id="hybrid_pdf_to_markdown",
    description="PDF -> Markdown sạch (PyMuPDF + DeepSeek)",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args=_DEFAULT_ARGS,
    tags=["rag", "ingestion"],
    params={"s3_key": "", "mon": "", "lop": "", "chuong": "", "extract_mode": "text", "max_pages": 0},
)
def hybrid_pdf_to_markdown():
    bucket = config.minio_bucket()

    @task(execution_timeout=timedelta(hours=2))
    def local_raw_extraction(**ctx) -> str:
        """[KHÂU BÓC TÁCH] Đọc PDF từ S3 theo extract_mode (text/tesseract/vision), ghi raw_text/*.txt."""
        params = ctx["params"]
        s3_key = params["s3_key"]
        mode, max_pages = params.get("extract_mode", "text"), int(params.get("max_pages", 0))
        stem = s3_key.removeprefix("raw_pdf/").removesuffix(".pdf")
        pdf = s3_io.get_bytes(bucket, s3_key)
        if mode == "vision":
            provider = config.vision_provider()
            if provider == "gemini":
                text = pdf_extract.extract_with_gemini(pdf, config.gemini_api_key(), config.gemini_model(), max_pages)
            elif provider == "qwen":
                text = pdf_extract.extract_with_vision(
                    pdf, config.qwen_api_key(), config.qwen_model(), max_pages, base_url=config.qwen_api_base()
                )
            else:
                text = pdf_extract.extract_with_vision(pdf, config.openai_api_key(), config.vision_model(), max_pages)
        elif mode == "tesseract":
            text = pdf_extract.extract_with_tesseract(pdf, config.ocr_lang(), max_pages)
        else:
            text = pdf_extract.extract_text_layer(pdf, max_pages)
        return s3_io.put_text(bucket, f"raw_text/{stem}.txt", text)

    @task
    def chunk_raw_text(text_key: str) -> list[dict]:
        """Cắt text thô thành các khối ~3000 token để tránh tràn ngữ cảnh DeepSeek."""
        stem = text_key.removeprefix("raw_text/").removesuffix(".txt")
        text = s3_io.get_text(bucket, text_key)
        pieces = chunk_by_tokens(text, max_tokens=config.chunk_token_size())
        keys = [s3_io.put_text(bucket, f"raw_chunks/{stem}/{i}.txt", p) for i, p in enumerate(pieces)]
        return [{"index": i, "key": k} for i, k in enumerate(keys)]

    @task(pool="deepseek_pool", retries=5, retry_exponential_backoff=True, max_retry_delay=timedelta(minutes=5))
    def deepseek_formatting(chunk: dict) -> dict:
        """[CHẤT LƯỢNG CAO] Gọi DeepSeek-V3 tái cấu trúc 1 chunk -> Markdown + LaTeX."""
        cfg = config.deepseek_config()
        raw = s3_io.get_text(bucket, chunk["key"])
        md = format_chunk(raw, cfg.api_key, cfg.api_base, cfg.model)
        md_key = chunk["key"].replace("raw_chunks/", "md_chunks/").removesuffix(".txt") + ".md"
        return {"index": chunk["index"], "key": s3_io.put_text(bucket, md_key, md)}

    @task
    def stitch_and_save_md(formatted: list[dict], **ctx) -> str:
        """Nối các khối Markdown theo thứ tự index, ghi clean_md/*.md (cảnh báo nếu < 1KB)."""
        ordered = sorted(formatted, key=lambda x: x["index"])
        merged = "\n\n".join(s3_io.get_text(bucket, item["key"]) for item in ordered)
        if len(merged.encode("utf-8")) < 1024:
            slack_on_failure({"task_instance": None, "exception": "File Markdown < 1KB — nghi ngờ lỗi"})
        s3_key = ctx["params"]["s3_key"]
        stem = s3_key.removeprefix("raw_pdf/").removesuffix(".pdf")
        return s3_io.put_text(bucket, f"clean_md/{stem}.md", merged)

    sensor_check_s3 = S3KeySensor(
        task_id="sensor_check_s3",
        aws_conn_id="aws_minio",
        bucket_name=bucket,
        bucket_key="{{ params.s3_key }}",
        mode="reschedule",
        poke_interval=30,
        timeout=300,
    )

    text_key = local_raw_extraction()
    chunks = chunk_raw_text(text_key)
    sensor_check_s3 >> text_key
    formatted = deepseek_formatting.expand(chunk=chunks)
    md_key = stitch_and_save_md(formatted)

    trigger_vector_dag = TriggerDagRunOperator(
        task_id="trigger_vector_dag",
        trigger_dag_id="markdown_to_qdrant_ingestion",
        conf={
            "md_key": "{{ ti.xcom_pull(task_ids='stitch_and_save_md') }}",
            "mon": "{{ params.mon }}",
            "lop": "{{ params.lop }}",
            "chuong": "{{ params.chuong }}",
        },
    )
    md_key >> trigger_vector_dag


hybrid_pdf_to_markdown()
