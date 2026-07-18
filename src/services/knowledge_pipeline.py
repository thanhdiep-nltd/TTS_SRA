"""Cầu nối từ FastAPI sang hạ tầng RAG: upload PDF lên MinIO + trigger Airflow DAG.

Đây là phần DUY NHẤT trong src/ chạm tới pipeline ingestion (decoupled).
"""

import uuid

import httpx

from src.config import get_settings
from src.schemas.knowledge import IngestRequest

_DAG_ID = "hybrid_pdf_to_markdown"
_TIMEOUT = httpx.Timeout(30.0)


def upload_pdf(content: bytes, req: IngestRequest) -> str:
    """Đẩy nội dung PDF lên MinIO theo key raw_pdf/{mon}_{lop}.pdf; trả về s3_key."""
    import boto3

    s = get_settings()
    key = f"raw_pdf/{req.mon}_{req.lop}.pdf"
    client = boto3.client(
        "s3",
        endpoint_url=s.minio_endpoint,
        aws_access_key_id=s.minio_access_key,
        aws_secret_access_key=s.minio_secret_key,
    )
    client.put_object(Bucket=s.minio_bucket, Key=key, Body=content, ContentType="application/pdf")
    return key


def trigger_ingest(req: IngestRequest) -> dict:
    """Gọi Airflow REST API tạo DagRun cho DAG 1; trả về JSON DagRun."""
    s = get_settings()
    resp = httpx.post(
        f"{s.airflow_base_url.rstrip('/')}/api/v1/dags/{_DAG_ID}/dagRuns",
        auth=(s.airflow_user, s.airflow_password),
        json={
            "dag_run_id": f"ingest_{req.mon}_{req.lop}_{uuid.uuid4().hex[:8]}",
            "conf": {"s3_key": req.s3_key, "mon": req.mon, "lop": req.lop, "chuong": req.chuong},
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def get_dag_run(dag_run_id: str) -> dict:
    """Lấy trạng thái một DagRun của DAG 1."""
    s = get_settings()
    resp = httpx.get(
        f"{s.airflow_base_url.rstrip('/')}/api/v1/dags/{_DAG_ID}/dagRuns/{dag_run_id}",
        auth=(s.airflow_user, s.airflow_password),
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()
