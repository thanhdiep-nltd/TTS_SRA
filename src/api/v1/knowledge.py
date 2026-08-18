"""Endpoint RAG ingestion: upload SGK (PDF) lên MinIO và trigger Airflow pipeline.

Chỉ ADMIN. Đây là ranh giới duy nhất giữa app FastAPI và hạ tầng ingestion.
"""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.api.deps import require_roles
from src.models import enums
from src.schemas.knowledge import DagRunStatus, IngestRequest, IngestResponse
from src.services import knowledge_pipeline

router = APIRouter(
    prefix="/knowledge",
    tags=["Knowledge (RAG)"],
    dependencies=[Depends(require_roles(enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL))],
)


@router.post("/upload", response_model=IngestResponse, status_code=202)
def upload_and_ingest(
    file: Annotated[UploadFile, File()],
    mon: Annotated[str, Form()],
    lop: Annotated[str, Form()],
    chuong: Annotated[str, Form()] = "",
):
    """Tải PDF lên MinIO rồi kích hoạt pipeline RAG (DAG 1)."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file PDF.")
    req = IngestRequest(s3_key="", mon=mon, lop=lop, chuong=chuong)
    req.s3_key = knowledge_pipeline.upload_pdf(file.file.read(), req)
    return _run(req)


@router.post("/ingest", response_model=IngestResponse, status_code=202)
def ingest(req: IngestRequest):
    """Kích hoạt pipeline cho một PDF đã có sẵn trên MinIO."""
    return _run(req)


@router.get("/status/{dag_run_id}", response_model=DagRunStatus)
def status(dag_run_id: str):
    """Xem trạng thái một lần chạy pipeline."""
    try:
        data = knowledge_pipeline.get_dag_run(dag_run_id)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Lỗi Airflow: {exc}") from exc
    return DagRunStatus(dag_run_id=data["dag_run_id"], state=data["state"])


def _run(req: IngestRequest) -> IngestResponse:
    """Gọi Airflow trigger và chuẩn hóa lỗi mạng thành 502."""
    try:
        data = knowledge_pipeline.trigger_ingest(req)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Không kích hoạt được pipeline: {exc}") from exc
    return IngestResponse(dag_run_id=data["dag_run_id"], s3_key=req.s3_key, state=data.get("state", "queued"))
