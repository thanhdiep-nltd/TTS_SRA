from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.state import MultiAgentState
from src.agents.supervisor.node import RouterDecision, supervisor_node


@pytest.mark.asyncio
async def test_supervisor_clarification_decision():
    """Verify that supervisor node returns clarifying response and next_agent='FINISH' when requested."""
    state = MultiAgentState(
        query="xuất báo cáo năm học 2025-2026 tình hình học tập khối 6",
        messages=[],
    )

    with patch("src.agents.supervisor.node.get_llm") as mock_get_llm:
        mock_chat = MagicMock()

        # Simulated decision: supervisor realizes semester is missing and asks user.
        mock_decision = RouterDecision(
            next_agent="FINISH",
            instruction="Hỏi làm rõ thông tin học kỳ",
            response="Bạn muốn xuất báo cáo tình hình học tập của cả năm học hay của một học kỳ cụ thể (Học kỳ 1 / Học kỳ 2)?",
        )

        # If openai provider is used (which uses with_structured_output)
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_decision)
        mock_chat.with_structured_output = MagicMock(return_value=mock_structured)

        # If deepseek provider is used (which uses bind_tools and parses tool_calls)
        mock_chat.bind_tools = MagicMock(return_value=mock_chat)
        mock_chat.ainvoke = AsyncMock(
            return_value=MagicMock(tool_calls=[{"args": mock_decision.model_dump(), "name": "RouterDecision"}])
        )

        mock_get_llm.return_value = mock_chat

        # Execute the supervisor node
        result = await supervisor_node(state)

        # Verify next_agent is FINISH
        assert result["next_agent"] == "FINISH"

        # Verify the clarification question is returned as response
        assert "Học kỳ 1 / Học kỳ 2" in result["response"]
