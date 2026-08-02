import time
from typing import Any, Dict, Literal, Optional

StepCategory = Literal["safety", "routing", "decomposition", "retrieval", "filtering", "synthesis"]
StepStatus = Literal["pending", "running", "completed", "warning", "error"]


class AgentStepTrace:
    """Đối tượng biểu diễn 1 bước trong Workflow Trace của Agent."""

    def __init__(
        self,
        id: str,
        category: StepCategory,
        title: str,
        summary: str,
        status: StepStatus = "completed",
        icon: str = "Search",
        detail: Optional[str] = None,
        elapsed_ms: Optional[int] = None,
    ):
        self.id = id
        self.category = category
        self.title = title
        self.summary = summary
        self.status = status
        self.icon = icon
        self.detail = detail
        self.elapsed_ms = elapsed_ms
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "summary": self.summary,
            "status": self.status,
            "icon": self.icon,
            "detail": self.detail,
            "elapsed_ms": self.elapsed_ms,
            "timestamp": self.timestamp,
        }


def create_safety_step(
    summary: str = "Đã kiểm tra an toàn nội dung & ngữ cảnh phân quyền",
    detail: Optional[str] = None,
    status: StepStatus = "completed",
) -> Dict[str, Any]:
    return AgentStepTrace(
        id="safety_check",
        category="safety",
        title="An toàn",
        summary=summary,
        status=status,
        icon="ShieldCheck",
        detail=detail,
    ).to_dict()


def create_routing_step(
    target_agent: str,
    instruction: str = "",
    detail: Optional[str] = None,
    status: StepStatus = "completed",
) -> Dict[str, Any]:
    agent_names = {
        "data_service_agent": "Tra cứu & Truy vấn CSDL",
        "stat_agent": "Thống kê & Phân tích Học tập",
        "knowledge_agent": "Tra cứu Quy chế & Tài liệu",
        "report_agent": "Lập Báo cáo Học đường",
        "CLARIFICATION": "Yêu cầu Người dùng Làm rõ",
        "FINISH": "Hoàn tất Xử lý",
    }
    target_label = agent_names.get(target_agent, target_agent)
    summary = f"Đã xác định nhóm câu hỏi: {target_label}"
    if instruction:
        summary += f" ({instruction[:60]}...)" if len(instruction) > 60 else f" ({instruction})"

    return AgentStepTrace(
        id="routing",
        category="routing",
        title="Định tuyến",
        summary=summary,
        status=status,
        icon="GitFork",
        detail=detail,
    ).to_dict()


def create_decomposition_step(
    slots_summary: str,
    detail: Optional[str] = None,
    status: StepStatus = "completed",
) -> Dict[str, Any]:
    return AgentStepTrace(
        id="decomposition",
        category="decomposition",
        title="Phân tích",
        summary=slots_summary or "Đã bóc tách thực thể & phân chia hướng tra cứu",
        status=status,
        icon="Layers",
        detail=detail,
    ).to_dict()


def create_retrieval_step(
    tool_name: str,
    result_summary: str,
    elapsed_ms: Optional[int] = None,
    detail: Optional[str] = None,
    status: StepStatus = "completed",
) -> Dict[str, Any]:
    tool_titles = {
        "search_textbook": "Tra cứu Tài liệu Quy chế",
        "execute_read_only_query": "Truy vấn CSDL PostgreSQL",
        "validate_and_secure_sql": "Kiểm duyệt An toàn SQL",
    }
    title_prefix = tool_titles.get(tool_name, f"Tra cứu ({tool_name})")
    return AgentStepTrace(
        id=f"retrieval_{tool_name}",
        category="retrieval",
        title="Tra cứu",
        summary=f"{title_prefix}: {result_summary}",
        status=status,
        icon="Search",
        detail=detail,
        elapsed_ms=elapsed_ms,
    ).to_dict()


def create_filtering_step(
    summary: str = "Đủ bằng chứng để trả lời · Đã rà soát & xác minh dữ liệu",
    detail: Optional[str] = None,
    status: StepStatus = "completed",
) -> Dict[str, Any]:
    return AgentStepTrace(
        id="filtering",
        category="filtering",
        title="Lọc",
        summary=summary,
        status=status,
        icon="Filter",
        detail=detail,
    ).to_dict()


def create_synthesis_step(
    summary: str = "Đã rà soát an toàn, không có cảnh báo",
    detail: Optional[str] = None,
    status: StepStatus = "completed",
) -> Dict[str, Any]:
    return AgentStepTrace(
        id="synthesis",
        category="synthesis",
        title="Rà soát",
        summary=summary,
        status=status,
        icon="PenTool",
        detail=detail,
    ).to_dict()
