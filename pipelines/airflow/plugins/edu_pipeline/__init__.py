"""Edu-Knowledge Pipeline — thư viện dùng chung cho 2 DAG ingestion.

Module thuần Python, decoupled khỏi `src/` của app FastAPI. Chỉ phụ thuộc
Airflow (Variables/Connections/Hooks) và các thư viện AI/vector trong
requirements.airflow.txt.
"""
