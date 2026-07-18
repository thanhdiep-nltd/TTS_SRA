from langgraph.graph import END, StateGraph

from src.agents.data_agent import data_agent_node
from src.agents.knowledge_agent import knowledge_agent_node
from src.agents.report_agent import report_agent_node
from src.agents.sql_agent import sql_agent_node
from src.agents.stat_agent import stat_agent_node
from src.agents.state import MultiAgentState
from src.agents.supervisor import supervisor_node


def route_next(state: MultiAgentState) -> str:
    """Hàm điều hướng sau khi Supervisor đưa ra quyết định."""
    return state.get("next_agent")


def build_graph() -> StateGraph:
    """Biên dịch đồ thị Multi-Agent StateGraph."""
    workflow = StateGraph(MultiAgentState)

    # 1. Đăng ký các Node
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("data_agent", data_agent_node)
    workflow.add_node("stat_agent", stat_agent_node)
    workflow.add_node("sql_agent", sql_agent_node)
    workflow.add_node("knowledge_agent", knowledge_agent_node)
    workflow.add_node("report_agent", report_agent_node)

    # 2. Thiết lập điểm bắt đầu (Entry Point) là Supervisor
    workflow.set_entry_point("supervisor")

    # 3. Thêm các cạnh có điều kiện từ Supervisor đi sang Sub-Agents hoặc END
    workflow.add_conditional_edges(
        "supervisor",
        route_next,
        {
            "data_agent": "data_agent",
            "stat_agent": "stat_agent",
            "sql_agent": "sql_agent",
            "knowledge_agent": "knowledge_agent",
            "report_agent": "report_agent",
            "CLARIFICATION": END,
            "FINISH": END,
        },
    )

    # 4. Thêm các cạnh nối từ các Sub-Agents quay về lại Supervisor
    workflow.add_edge("data_agent", "supervisor")
    workflow.add_edge("stat_agent", "supervisor")
    workflow.add_edge("sql_agent", "supervisor")
    workflow.add_edge("knowledge_agent", "supervisor")
    workflow.add_edge("report_agent", "supervisor")

    return workflow.compile()


# Xuất biến agent đại diện cho đồ thị đã biên dịch
agent = build_graph()
