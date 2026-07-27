from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class MultiAgentState(TypedDict, total=False):
    """State schema cho Multi-Agent LangGraph.

    Mỗi node đọc và ghi vào state này.
    total=False cho phép tất cả fields là optional.
    """

    query: str
    context: str
    analysis: str
    response: str
    error: str
    metadata: dict
    messages: Annotated[list[BaseMessage], add_messages]
    next_agent: str
    school_context: dict
    standalone_query: str  # Query đã được LLM Contextualizer reformulate, độc lập tự thân


# Alias phục vụ khả năng tương thích ngược
AgentState = MultiAgentState
