import re
import uuid

from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

from src.config import get_settings


def parse_dsml_tool_calls(text: str) -> list:
    """Parses DSML tool calls from text and returns standard tool call dicts."""
    tool_calls = []
    pipe = r"(?:\||\uff5c|\s)+"

    # Regex to find each invoke block (supports single/double quotes)
    invoke_pattern = re.compile(
        r"<"
        + pipe
        + r"DSML"
        + pipe
        + r"invoke\s+name=[\"']([^\"']+)[\"']\s*>(.*?)</"
        + pipe
        + r"DSML"
        + pipe
        + r"invoke\s*>",
        re.DOTALL,
    )

    # Regex to find each parameter inside an invoke block (supports single/double quotes)
    param_pattern = re.compile(
        r"<"
        + pipe
        + r"DSML"
        + pipe
        + r"parameter\s+name=[\"']([^\"']+)[\"']\s+string=[\"']([^\"']+)[\"']\s*>(.*?)</"
        + pipe
        + r"DSML"
        + pipe
        + r"parameter\s*>",
        re.DOTALL,
    )

    for match in invoke_pattern.finditer(text):
        tool_name = match.group(1)
        params_content = match.group(2)

        args = {}
        for p_match in param_pattern.finditer(params_content):
            p_name = p_match.group(1)
            is_string = p_match.group(2) == "true"
            p_val = p_match.group(3).strip()

            if is_string:
                args[p_name] = p_val
            else:
                if p_val.lower() == "true":
                    args[p_name] = True
                elif p_val.lower() == "false":
                    args[p_name] = False
                elif p_val.lower() == "none" or p_val.lower() == "null":
                    args[p_name] = None
                else:
                    try:
                        if "." in p_val:
                            args[p_name] = float(p_val)
                        else:
                            args[p_name] = int(p_val)
                    except ValueError:
                        args[p_name] = p_val

        tool_calls.append({"name": tool_name, "args": args, "id": f"call_{uuid.uuid4().hex[:12]}", "type": "tool_call"})

    return tool_calls


def clean_dsml_content(text: str) -> str:
    """Strips raw DSML tags block from message content."""
    pipe = r"(?:\||\uff5c|\s)+"
    pattern = re.compile(
        r"<" + pipe + r"DSML" + pipe + r"tool_calls\s*>.*?</" + pipe + r"DSML" + pipe + r"tool_calls\s*>", re.DOTALL
    )
    return pattern.sub("", text).strip()


class DeepSeekDSMLWrapper(ChatOpenAI):
    """Wrapper around ChatOpenAI to intercept and parse DeepSeek's custom XML DSML tags for tool calling."""

    def invoke(self, input, config=None, **kwargs):
        import time

        start = time.time()
        res = super().invoke(input, config, **kwargs)
        latency = time.time() - start
        print(
            f"⏱️ [LLM Call Latency]: Model {self.model or getattr(self, 'model_name', 'unknown')} (DeepSeek) phản hồi sau {latency:.2f} s"
        )
        return self._process_message(res)

    async def ainvoke(self, input, config=None, **kwargs):
        import time

        start = time.time()
        res = await super().ainvoke(input, config, **kwargs)
        latency = time.time() - start
        print(
            f"⏱️ [LLM Call Latency]: Model {self.model or getattr(self, 'model_name', 'unknown')} (DeepSeek) phản hồi sau {latency:.2f} s"
        )
        return self._process_message(res)

    def _process_message(self, message: BaseMessage) -> BaseMessage:
        if isinstance(message, AIMessage) and message.content and isinstance(message.content, str):
            content = message.content
            pipe = r"(?:\||\uff5c|\s)+"
            if re.search(r"<" + pipe + r"DSML" + pipe + r"tool_calls", content):
                tool_calls = parse_dsml_tool_calls(content)
                if tool_calls:
                    # Append parsed tool calls
                    message.tool_calls = (message.tool_calls or []) + tool_calls
                    # Clean up DSML tags from visual message content
                    message.content = clean_dsml_content(content)
        return message


class TimedChatOpenAI(ChatOpenAI):
    """Wrapper around ChatOpenAI to measure and log API latency."""

    def invoke(self, input, config=None, **kwargs):
        import time

        start = time.time()
        res = super().invoke(input, config, **kwargs)
        latency = time.time() - start
        print(
            f"⏱️ [LLM Call Latency]: Model {self.model or getattr(self, 'model_name', 'unknown')} (OpenAI) phản hồi sau {latency:.2f} s"
        )
        return res

    async def ainvoke(self, input, config=None, **kwargs):
        import time

        start = time.time()
        res = await super().ainvoke(input, config, **kwargs)
        latency = time.time() - start
        print(
            f"⏱️ [LLM Call Latency]: Model {self.model or getattr(self, 'model_name', 'unknown')} (OpenAI) phản hồi sau {latency:.2f} s"
        )
        return res


def _build_llm(provider: str, settings) -> ChatOpenAI:
    if provider == "deepseek":
        return DeepSeekDSMLWrapper(
            model=settings.deepseek_model_name,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_api_base,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_s,
            extra_body={"thinking": {"type": "disabled"}},
        )
    return TimedChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_s,
    )


def get_llm() -> ChatOpenAI:
    settings = get_settings()
    return _build_llm(settings.llm_provider, settings)


def get_judge_llm() -> ChatOpenAI:
    """LLM dùng cho Eval-as-a-Metric (Faithfulness/Groundedness judge, xem services/eval.py).

    Mặc định (`judge_llm_provider="same"`) dùng chung `get_llm()` — chấp nhận rủi ro thiên vị
    tự đánh giá để không bắt buộc cấu hình thêm API key cho MVP. Đặt `JUDGE_LLM_PROVIDER` khác
    `llm_provider` trong .env để có judge độc lập, đáng tin hơn.
    """
    settings = get_settings()
    provider = settings.judge_llm_provider
    if provider == "same" or provider == settings.llm_provider:
        return get_llm()
    return _build_llm(provider, settings)
