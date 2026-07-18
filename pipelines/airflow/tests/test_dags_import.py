"""Test DAG load không lỗi cú pháp / không cycle. Bỏ qua nếu chưa cài Airflow."""

import pathlib

import pytest

pytest.importorskip("airflow")

from airflow.models import DagBag  # noqa: E402

_DAGS_DIR = pathlib.Path(__file__).resolve().parents[1] / "dags"


def test_no_import_errors():
    dag_bag = DagBag(dag_folder=str(_DAGS_DIR), include_examples=False)
    assert dag_bag.import_errors == {}


def test_expected_dags_present():
    dag_bag = DagBag(dag_folder=str(_DAGS_DIR), include_examples=False)
    assert "hybrid_pdf_to_markdown" in dag_bag.dags
    assert "markdown_to_qdrant_ingestion" in dag_bag.dags
