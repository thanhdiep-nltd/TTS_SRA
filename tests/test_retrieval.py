"""Test offline cho các hàm thuần của src.services.retrieval (không gọi Qdrant/embedding thật)."""

from src.services import retrieval


def test_rag_mon_slug_maps_known_subject_codes():
    assert retrieval.rag_mon_slug("TOAN") == "toan"
    assert retrieval.rag_mon_slug("KHTN") == "khoa_hoc_tu_nhien"


def test_rag_mon_slug_falls_back_to_lowercase_for_unknown_code():
    assert retrieval.rag_mon_slug("VAN") == "van"


def test_has_rag_true_for_ingested_subjects():
    assert retrieval.has_rag("TOAN") is True
    assert retrieval.has_rag("KHTN") is True


def test_has_rag_false_for_subjects_without_ingested_textbooks():
    assert retrieval.has_rag("VAN") is False
