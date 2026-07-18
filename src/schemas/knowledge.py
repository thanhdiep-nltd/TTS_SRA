"""Pydantic DTO cho RAG ingestion (upload SGK + trigger Airflow pipeline)."""

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Tham số nạp một tài liệu vào pipeline RAG."""

    s3_key: str = Field(description="Key của PDF trên MinIO, ví dụ raw_pdf/toan_9.pdf")
    mon: str = Field(description="Mã/môn học, ví dụ 'toan'")
    lop: str = Field(description="Khối/lớp, ví dụ '9'")
    chuong: str = Field(default="", description="Chương (tùy chọn)")


class IngestResponse(BaseModel):
    """Kết quả kích hoạt pipeline."""

    dag_run_id: str
    s3_key: str
    state: str


class DagRunStatus(BaseModel):
    dag_run_id: str
    state: str
