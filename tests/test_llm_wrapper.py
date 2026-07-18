from langchain_core.messages import AIMessage

from src.services.llm import DeepSeekDSMLWrapper


def test_dsml_wrapper_processes_message():
    wrapper = DeepSeekDSMLWrapper(openai_api_key="test-key")

    # Test case 1: Normal message without DSML
    msg_normal = AIMessage(content="Hello, how can I help you today?")
    processed_normal = wrapper._process_message(msg_normal)
    assert processed_normal.content == "Hello, how can I help you today?"
    assert not processed_normal.tool_calls

    # Test case 2: Message with DSML tool calls
    dsml_content = (
        "[Supervisor]: Chuyển yêu cầu sang compare_classes.\n"
        "< | | DSML | | tool_calls> "
        '< | | DSML | | invoke name="compare_classes"> '
        '< | | DSML | | parameter name="year" string="false">2024</ | | DSML | | parameter> '
        '< | | DSML | | parameter name="semester" string="false">1</ | | DSML | | parameter> '
        '< | | DSML | | parameter name="subject" string="true">Khoa học tự nhiên</ | | DSML | | parameter> '
        '< | | DSML | | parameter name="grade_level" string="false">8</ | | DSML | | parameter> '
        "</ | | DSML | | invoke> "
        "</ | | DSML | | tool_calls>"
    )
    msg_dsml = AIMessage(content=dsml_content)
    processed_dsml = wrapper._process_message(msg_dsml)

    # Content should be cleaned of DSML tags
    assert processed_dsml.content == "[Supervisor]: Chuyển yêu cầu sang compare_classes."

    # Tool calls should be populated
    assert len(processed_dsml.tool_calls) == 1
    call = processed_dsml.tool_calls[0]
    assert call["name"] == "compare_classes"
    assert call["args"] == {"year": 2024, "semester": 1, "subject": "Khoa học tự nhiên", "grade_level": 8}


def test_dsml_wrapper_processes_message_fullwidth():
    wrapper = DeepSeekDSMLWrapper(openai_api_key="test-key")

    # Test case 3: Message with fullwidth pipeline chars and single/double quotes mixture
    dsml_content = (
        "<｜DSML｜tool_calls>"
        "<｜DSML｜invoke name='get_student_info'>"
        "<｜DSML｜parameter name='student_code' string='true'>HS001</｜DSML｜parameter>"
        "</｜DSML｜invoke>"
        "</｜DSML｜tool_calls>"
    )
    msg_dsml = AIMessage(content=dsml_content)
    processed_dsml = wrapper._process_message(msg_dsml)

    assert processed_dsml.content == ""
    assert len(processed_dsml.tool_calls) == 1
    call = processed_dsml.tool_calls[0]
    assert call["name"] == "get_student_info"
    assert call["args"] == {"student_code": "HS001"}
