from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.agents.graph import agent
from src.agents.supervisor.node import RouterDecision


@pytest.fixture(autouse=True)
def mock_llm():
    """Mock get_llm to prevent real OpenAI API calls during unit tests."""
    with (
        patch("src.agents.supervisor.node.get_llm") as mock_get_llm_sup,
        patch("src.agents.data_agent.node.get_llm") as mock_get_llm_data,
        patch("src.agents.stat_agent.node.get_llm") as mock_get_llm_stat,
        patch("src.agents.sql_agent.node.get_llm") as mock_get_llm_sql,
        patch("src.agents.report_agent.node.get_llm") as mock_get_llm_report,
    ):
        mock_chat = MagicMock()

        # Mock ainvoke to return a fake AI Message
        mock_response = AIMessage(content="Đây là câu trả lời giả lập từ AI.")
        mock_chat.ainvoke = AsyncMock(return_value=mock_response)

        # Mock bind_tools to return the mock chat model itself
        mock_chat.bind_tools = MagicMock(return_value=mock_chat)

        # Mock with_structured_output to return a mock returning RouterDecision(next_agent="FINISH")
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=RouterDecision(next_agent="FINISH", instruction="Hoàn thành"))
        mock_chat.with_structured_output = MagicMock(return_value=mock_structured)

        mock_get_llm_sup.return_value = mock_chat
        mock_get_llm_data.return_value = mock_chat
        mock_get_llm_stat.return_value = mock_chat
        mock_get_llm_sql.return_value = mock_chat
        mock_get_llm_report.return_value = mock_chat
        yield mock_chat


@pytest.mark.asyncio
async def test_agent_basic_flow():
    result = await agent.ainvoke({"query": "Hello"})
    assert "response" in result
    assert result["response"] == "Đây là câu trả lời giả lập từ AI."


@pytest.mark.asyncio
async def test_agent_state_structure():
    result = await agent.ainvoke({"query": "Test query"})
    assert isinstance(result, dict)
    assert "query" in result
    assert result["query"] == "Test query"
