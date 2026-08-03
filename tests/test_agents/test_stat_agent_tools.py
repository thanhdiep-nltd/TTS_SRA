"""Test offline: xác nhận get_exam_validity_report được đăng ký vào stat_agent (mock LLM, không gọi
OpenAI thật) — phòng hồi quy khi có người thêm/bớt tool mà quên đồng bộ get_stat_agent().
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agents.stat_agent.tools import _match_units


@pytest.fixture
def stat_agent_instance():
    with patch("src.agents.stat_agent.node.get_llm") as mock_get_llm:
        mock_chat = MagicMock()
        mock_chat.bind_tools = MagicMock(return_value=mock_chat)
        mock_get_llm.return_value = mock_chat

        # get_stat_agent() cache module-level (_stat_agent) — reset để patch get_llm có hiệu lực.
        import src.agents.stat_agent.node as node

        node._stat_agent = None
        yield node.get_stat_agent()
        node._stat_agent = None


def test_get_exam_validity_report_registered_in_stat_agent(stat_agent_instance):
    tools_node = stat_agent_instance.nodes["tools"].bound
    assert "get_exam_validity_report" in tools_node.tools_by_name


def test_draft_exam_blueprint_registered_in_stat_agent(stat_agent_instance):
    tools_node = stat_agent_instance.nodes["tools"].bound
    assert "draft_exam_blueprint" in tools_node.tools_by_name


def _unit(name: str):
    return SimpleNamespace(id=name, name=name)


def test_match_units_substring_case_insensitive():
    units = [_unit("Phân thức đại số"), _unit("Hàm số và đồ thị")]
    matched, not_found = _match_units(units, ["phân thức", "Hàm số"])
    assert [u.name for u in matched] == ["Phân thức đại số", "Hàm số và đồ thị"]
    assert not_found == []


def test_match_units_reports_unmatched_names():
    units = [_unit("Phân thức đại số")]
    matched, not_found = _match_units(units, ["Phân thức", "Chương không tồn tại"])
    assert [u.name for u in matched] == ["Phân thức đại số"]
    assert not_found == ["Chương không tồn tại"]


def test_calculate_grade_statistics_missing_oltp_returns_clear_message(monkeypatch):
    """OLTP (bảng scores) không tồn tại trong môi trường DWH-only -> trả thông báo rõ ràng
    thay vì exception tràn ra ngoài khiến agent hiểu nhầm thành từ chối phân quyền."""
    from sqlalchemy.exc import ProgrammingError

    import src.agents.stat_agent.tools as stat_tools
    from src.agents.context import current_user_id, current_user_role, current_user_school_id

    def _fake_execute(stmt, *args, **kwargs):
        # Chỉ bảng scores (OLTP) bị "thiếu"; teacher_assignments vẫn trả rỗng để
        # accessible_score_filter chạy đủ trước khi guard của tool bắt lỗi.
        if "scores" in str(stmt):
            raise ProgrammingError(
                "SELECT ...", {}, Exception('relation "scores" does not exist')
            )
        res = MagicMock()
        res.scalars.return_value.all.return_value = []
        return res

    mock_session = MagicMock()
    mock_session.execute.side_effect = _fake_execute
    mock_local = MagicMock()
    mock_local.return_value.__enter__.return_value = mock_session
    monkeypatch.setattr(stat_tools, "SessionLocal", mock_local)

    tok_id = current_user_id.set(36)
    tok_role = current_user_role.set("HOMEROOM_TEACHER_SECONDARY")
    tok_school = current_user_school_id.set(1)
    try:
        result = stat_tools.calculate_grade_statistics.invoke(
            {"class_name": "6A2", "semester": 2, "subject": "Ngữ văn"}
        )
    finally:
        current_user_id.reset(tok_id)
        current_user_role.reset(tok_role)
        current_user_school_id.reset(tok_school)

    assert "chưa cấu hình" in result
    assert "get_class_grades" in result
    assert "does not exist" not in result
