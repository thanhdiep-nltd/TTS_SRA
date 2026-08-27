"""Unit tests cho src/services/lms_question_analyzer.py — Background Job & Progress Tracking."""

import json
from unittest.mock import MagicMock, patch

from src.models.tables import CurriculumUnit, LmsQuestionBank
from src.services.lms_question_analyzer import (
    LmsAnalysisJobManager,
    _build_batch_analysis_prompt,
    _parse_llm_json_response,
    job_manager,
    run_analysis_job_in_background,
)


def test_parse_llm_json_response_clean():
    raw = json.dumps([
        {"question_id": 1, "bloom_level": 2, "nodes": [{"node_id": 10, "weight": 1.0}], "confidence": 0.9}
    ])
    res = _parse_llm_json_response(raw)
    assert len(res) == 1
    assert res[0]["question_id"] == 1
    assert res[0]["bloom_level"] == 2


def test_parse_llm_json_response_with_markdown():
    raw = """```json
    [
      {"question_id": 2, "bloom_level": 4, "nodes": [{"node_id": 11, "weight": 0.6}, {"node_id": 12, "weight": 0.4}], "confidence": 0.85}
    ]
    ```"""
    res = _parse_llm_json_response(raw)
    assert len(res) == 1
    assert res[0]["question_id"] == 2
    assert res[0]["bloom_level"] == 4
    assert len(res[0]["nodes"]) == 2


def test_build_batch_analysis_prompt():
    shortlist = [
        CurriculumUnit(id=1, name="Bài 1: Tập hợp", grade_number=6, semester_number=1, keywords=["tập hợp", "phần tử"]),
        CurriculumUnit(id=2, name="Bài 2: Phép cộng", grade_number=6, semester_number=1, keywords=["phép cộng", "số tự nhiên"]),
    ]
    questions = [
        {"question_id": 101, "question_text": "Cho tập hợp A = {1, 2, 3}. Hãy tìm số phần tử."},
    ]
    sys_prompt, user_msg = _build_batch_analysis_prompt(shortlist, questions)
    assert "Bài 1: Tập hợp" in sys_prompt
    assert "bloom_level" in sys_prompt
    assert "ID #101" in user_msg


def test_job_manager_lifecycle():
    manager = LmsAnalysisJobManager()
    job_id = manager.create_job(subject_id=106, total_questions=20)
    assert job_id.startswith("job_lms_")

    job = manager.get_job(job_id)
    assert job is not None
    assert job.status == "pending"
    assert job.total_questions == 20

    manager.set_running(job_id, total_questions=20)
    job = manager.get_job(job_id)
    assert job.status == "running"

    manager.update_progress(job_id, processed_count=10, bloom_dist={1: 5, 2: 5}, unclassified_remaining=10)
    job = manager.get_job(job_id)
    assert job.processed_questions == 10
    assert job.progress_percent == 50
    assert job.bloom_distribution[1] == 5

    manager.complete_job(job_id, processed_count=20, bloom_dist={1: 10, 2: 10}, unclassified_remaining=0)
    job = manager.get_job(job_id)
    assert job.status == "completed"
    assert job.progress_percent == 100

    latest = manager.get_latest_job(106)
    assert latest is not None
    assert latest.job_id == job_id


def test_run_analysis_job_in_background_mock():
    mock_db = MagicMock()

    unit1 = CurriculumUnit(id=392, parent_id=391, name="Bài 1: Tập hợp", grade_number=6, is_active=True)
    unit2 = CurriculumUnit(id=393, parent_id=391, name="Bài 2: Phép cộng", grade_number=6, is_active=True)
    shortlist = [unit1, unit2]

    q1 = LmsQuestionBank(question_id=1, subject_id=106, question_text="Tập hợp A có bao nhiêu phần tử?", bloom_level=None)
    q2 = LmsQuestionBank(question_id=2, subject_id=106, question_text="Tính 12 + 15 = ?", bloom_level=None)

    with patch("src.services.lms_question_analyzer.SessionLocal", return_value=mock_db):
        mock_db.__enter__.return_value = mock_db
        with patch("src.services.content_difficulty.build_shortlist", return_value=shortlist):
            mock_db.execute.return_value.scalars.return_value.all.return_value = [q1, q2]
            mock_db.execute.return_value.scalar.return_value = 0

            fake_llm_response = MagicMock()
            fake_llm_response.content = json.dumps([
                {"question_id": 1, "bloom_level": 1, "nodes": [{"node_id": 392, "weight": 1.0}], "confidence": 0.95},
                {"question_id": 2, "bloom_level": 2, "nodes": [{"node_id": 393, "weight": 1.0}], "confidence": 0.90},
            ])

            mock_llm = MagicMock()
            mock_llm.invoke.return_value = fake_llm_response

            with patch("src.services.lms_question_analyzer.get_custom_llm", return_value=mock_llm):
                job_id = job_manager.create_job(subject_id=106, total_questions=2)
                run_analysis_job_in_background(
                    job_id=job_id,
                    subject_id=106,
                    model_name="google/gemini-3.7-flash",
                    re_analyze=False,
                    limit=2,
                )

                job = job_manager.get_job(job_id)
                assert job is not None
                assert job.status == "completed"
                assert job.processed_questions == 2
                assert q1.bloom_level == 1
                assert q2.bloom_level == 2
                assert mock_db.commit.called
