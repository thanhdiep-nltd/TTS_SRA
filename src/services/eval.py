"""Eval-as-a-Metric (Giai đoạn 3): chấm điểm Faithfulness/Groundedness cho câu trả lời của agent.

Không dùng package `ragas` (xung đột dependency với langchain 1.x đang dùng trong dự án
— xem requirements.txt). Thay bằng Judge tự viết: gọi `get_judge_llm()` (mặc định trùng
`get_llm()`, có thể cấu hình độc lập qua `JUDGE_LLM_PROVIDER` — xem services/llm.py) với
structured output, cùng pattern đã dùng cho RouterDecision của Supervisor.

Có 2 judge độc lập:
- `judge_faithfulness`: cho knowledge_agent (RAG sách giáo khoa) — so câu trả lời với
  context trích dẫn từ Qdrant.
- `judge_groundedness`: cho data_agent/stat_agent/sql_agent/report_agent — so câu trả lời với
  dữ liệu thô mà các tool đã trả về (bảng điểm, số liệu thống kê, kết quả SQL), để bắt trường
  hợp agent bịa số liệu không khớp với DB dù tool đã chạy thành công (điều mà `tool_calls_total`
  không bắt được vì nó chỉ biết tool có lỗi/exception hay không, không biết câu trả lời cuối có
  trung thực với kết quả tool hay không).
"""

import random

from pydantic import BaseModel, Field

from src.config import get_settings
from src.observability import eval_score_gauge, logger
from src.services.alerting import track_eval_score
from src.services.llm import get_judge_llm


class FaithfulnessJudgement(BaseModel):
    score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Điểm 0.0-1.0: câu trả lời bám sát nội dung trích dẫn (context) đến đâu. "
            "1.0 = mọi thông tin trong câu trả lời đều có trong context. "
            "0.0 = câu trả lời bịa đặt hoàn toàn, không liên quan context."
        ),
    )
    reasoning: str = Field(description="Giải thích ngắn gọn vì sao chấm điểm như vậy.")


_JUDGE_PROMPT = """Bạn là Giám khảo (Judge) đánh giá độ trung thực (Faithfulness) của câu trả lời AI so với tài liệu trích dẫn.

Câu hỏi của người dùng:
{question}

Tài liệu trích dẫn (context) mà AI có quyền sử dụng:
{contexts}

Câu trả lời của AI:
{answer}

Hãy chấm điểm Faithfulness: câu trả lời có bịa đặt thông tin KHÔNG có trong context không?
Trả lời bằng cách gọi công cụ FaithfulnessJudgement."""


def should_sample() -> bool:
    """Quyết định có sample câu trả lời này để eval không (mặc định 5%, tắt hẳn ở môi trường test)."""
    settings = get_settings()
    if settings.app_env == "test":
        return False
    return random.random() < settings.eval_sample_rate


async def judge_faithfulness(question: str, contexts: str, answer: str) -> float | None:
    """Chấm điểm Faithfulness bằng LLM-as-a-Judge. Trả None nếu lỗi (fail-soft, không raise)."""
    try:
        llm = get_judge_llm()
        structured_llm = llm.with_structured_output(FaithfulnessJudgement)
        judgement: FaithfulnessJudgement = await structured_llm.ainvoke(
            _JUDGE_PROMPT.format(question=question, contexts=contexts[:4000], answer=answer[:2000])
        )
        eval_score_gauge.labels(metric_name="faithfulness").set(judgement.score)
        logger.info("eval_score", metric="faithfulness", score=judgement.score, reasoning=judgement.reasoning)
        track_eval_score("faithfulness", judgement.score)
        return judgement.score
    except Exception as exc:
        logger.warning("eval_judge_failed", error=str(exc))
        return None


class GroundednessJudgement(BaseModel):
    score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Điểm 0.0-1.0: câu trả lời có khớp với dữ liệu thô (kết quả truy vấn/tính toán) mà "
            "công cụ đã trả về hay không. 1.0 = mọi số liệu/tên/kết luận trong câu trả lời đều "
            "có căn cứ trong dữ liệu thô. 0.0 = câu trả lời bịa số liệu hoặc suy diễn sai hoàn "
            "toàn so với dữ liệu thô."
        ),
    )
    reasoning: str = Field(description="Giải thích ngắn gọn vì sao chấm điểm như vậy.")


_GROUNDEDNESS_JUDGE_PROMPT = """Bạn là Giám khảo (Judge) đánh giá độ trung thực (Groundedness) của câu trả lời AI \
so với dữ liệu thô mà các công cụ tra cứu/tính toán đã trả về (bảng điểm, chỉ số thống kê, kết quả SQL).

Câu hỏi của người dùng:
{question}

Dữ liệu thô từ công cụ (data_agent/stat_agent/sql_agent/report_agent):
{tool_outputs}

Câu trả lời cuối cùng của AI:
{answer}

Hãy chấm điểm Groundedness: câu trả lời có bịa đặt số liệu/tên/kết luận KHÔNG có trong dữ liệu thô không?
Trả lời bằng cách gọi công cụ GroundednessJudgement."""


async def judge_groundedness(question: str, tool_outputs: str, answer: str) -> float | None:
    """Chấm điểm Groundedness (đối tượng: data_agent/stat_agent/sql_agent) bằng LLM-as-a-Judge.

    Trả None nếu lỗi (fail-soft, không raise)."""
    try:
        llm = get_judge_llm()
        structured_llm = llm.with_structured_output(GroundednessJudgement)
        judgement: GroundednessJudgement = await structured_llm.ainvoke(
            _GROUNDEDNESS_JUDGE_PROMPT.format(question=question, tool_outputs=tool_outputs[:4000], answer=answer[:2000])
        )
        eval_score_gauge.labels(metric_name="groundedness").set(judgement.score)
        logger.info("eval_score", metric="groundedness", score=judgement.score, reasoning=judgement.reasoning)
        track_eval_score("groundedness", judgement.score)
        return judgement.score
    except Exception as exc:
        logger.warning("eval_judge_failed", error=str(exc))
        return None
