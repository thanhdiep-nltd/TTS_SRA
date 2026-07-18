"""Test offline (không gọi LLM/RAG/DB thật) cho pipeline sinh câu hỏi LLM+RAG + guardrail."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.models import enums
from src.services import item_generation


def _fake_llm_response(content: str):
    return SimpleNamespace(content=content)


def _item(**overrides):
    base = {
        "stem": "1 + 1 = ?",
        "options": [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}],
        "answer_key": {"correct": "B"},
        "solution": "1 + 1 = 2",
        "bloom_level": 1,
        "grounded_quotes": ["Phép cộng hai số tự nhiên..."],
    }
    base.update(overrides)
    return item_generation.GeneratedItem(**base)


# ----------------------------- rag_mon_slug -----------------------------


def test_rag_mon_slug_maps_known_subject_codes():
    """subjects.code (TOAN/KHTN) khác slug 'mon' đã index trong Qdrant (toan/khoa_hoc_tu_nhien)."""
    assert item_generation.rag_mon_slug("TOAN") == "toan"
    assert item_generation.rag_mon_slug("KHTN") == "khoa_hoc_tu_nhien"


def test_rag_mon_slug_falls_back_to_lowercase_for_unknown_code():
    assert item_generation.rag_mon_slug("VAN") == "van"


# ----------------------------- build_context / rag_hit_meta -----------------------------


def test_build_context_labels_each_block_with_source():
    hits = [
        {"text": "Đoạn 1", "chuong": "Chương I", "heading": "Bài 1. Tập hợp"},
        {"text": "Đoạn 2"},
    ]
    ctx = item_generation.build_context(hits)
    assert "[Nguồn 1: Chương I — Bài 1. Tập hợp]\nĐoạn 1" in ctx
    assert "[Nguồn 2]\nĐoạn 2" in ctx


def test_build_context_truncates_at_max_chars():
    hits = [{"text": "a" * 30}, {"text": "b" * 30}, {"text": "c" * 30}]
    ctx = item_generation.build_context(hits, max_chars=40)
    assert "c" * 30 not in ctx and "b" * 30 in ctx


def test_build_context_empty_when_no_hits():
    assert item_generation.build_context([]) == ""


def test_rag_hit_meta_extracts_source_fields_only():
    hits = [{"text": "x" * 999, "chuong": "C1", "heading": "H1", "source_md": "toan6.md", "score": 0.71}]
    assert item_generation.rag_hit_meta(hits) == [
        {"chuong": "C1", "heading": "H1", "source_md": "toan6.md", "score": 0.71}
    ]


def test_rag_hit_meta_excludes_hits_truncated_away_by_max_chars():
    """rag_hits không được liệt kê nguồn đã bị cắt bỏ trước khi vào context thật."""
    hits = [{"text": "a" * 30, "chuong": "C1"}, {"text": "b" * 30, "chuong": "C2"}, {"text": "c" * 30, "chuong": "C3"}]
    meta = item_generation.rag_hit_meta(hits, max_chars=40)
    assert [m["chuong"] for m in meta] == ["C1", "C2"]  # C3 bị cắt, không xuất hiện


def test_build_grounding_context_excludes_source_labels():
    hits = [{"text": "Nội dung thật", "chuong": "Chương I", "heading": "Bài 1"}]
    grounding = item_generation.build_grounding_context(hits)
    assert "[Nguồn" not in grounding
    assert "Nội dung thật" in grounding


def test_is_grounded_rejects_quote_that_only_matches_source_label_not_actual_text():
    """Chặn LLM trích dẫn ngược nhãn [Nguồn i: ...] để giả bám nguồn (không phải nội dung SGK thật)."""
    hits = [{"text": "Nội dung SGK thật sự", "chuong": "Chương I", "heading": "Bài 1. Tập hợp"}]
    labeled_context = item_generation.build_context(hits)  # có nhãn [Nguồn 1: Chương I — Bài 1. Tập hợp]
    grounding_context = item_generation.build_grounding_context(hits)  # không có nhãn
    fake_quote = "Chương I — Bài 1. Tập hợp"  # LLM "trích dẫn" chính cái nhãn, không phải nội dung SGK
    assert (
        item_generation.quote_in_context(fake_quote, labeled_context) is True
    )  # chứng minh lỗ hổng CÓ TỒN TẠI nếu dùng sai context
    assert (
        item_generation.quote_in_context(fake_quote, grounding_context) is False
    )  # nhưng KHÔNG lọt qua nếu dùng đúng grounding_context


# ----------------------------- parse_generated_items -----------------------------


def test_parse_generated_items_parses_valid_array():
    raw = (
        '```json\n[{"stem": "Câu 1?", "answer_key": {"answer": "x"}, "solution": "...", '
        '"bloom_level": 2, "grounded_quotes": ["sgk"]}]\n```'
    )
    items = item_generation.parse_generated_items(raw)
    assert len(items) == 1
    assert items[0].bloom_level == 2


def test_parse_generated_items_skips_malformed_entries_without_crashing():
    raw = '[{"stem": "ok", "answer_key": {}, "solution": "s", "bloom_level": 9}, "không phải object"]'
    # bloom_level=9 vi phạm ge/le -> ValidationError -> bỏ qua; entry 2 không phải dict -> bỏ qua
    assert item_generation.parse_generated_items(raw) == []


def test_parse_generated_items_returns_empty_on_invalid_json():
    assert item_generation.parse_generated_items("không phải JSON đâu") == []


def test_parse_generated_items_returns_empty_when_not_a_list():
    assert item_generation.parse_generated_items('{"stem": "ok"}') == []


# ----------------------------- guardrail: quote_in_context / is_grounded -----------------------------


def test_quote_in_context_true_for_exact_substring():
    ctx = "Số hữu tỉ là số viết được dưới dạng phân số a/b với a, b nguyên, b khác 0."
    assert item_generation.quote_in_context("số viết được dưới dạng phân số a/b", ctx) is True


def test_quote_in_context_ignores_whitespace_and_case():
    ctx = "Số hữu tỉ  là số\nviết được dưới dạng phân số."
    assert item_generation.quote_in_context("SỐ HỮU TỈ LÀ SỐ VIẾT ĐƯỢC", ctx) is True


def test_quote_in_context_false_when_fabricated():
    ctx = "Số hữu tỉ là số viết được dưới dạng phân số."
    assert item_generation.quote_in_context("Định lý Pythagore áp dụng cho tam giác vuông", ctx) is False


def test_quote_in_context_false_for_empty_quote():
    assert item_generation.quote_in_context("   ", "nội dung") is False


def test_quote_in_context_matches_across_nfc_nfd_unicode_forms():
    """Chống lệch chuẩn hóa Unicode: SGK trích xuất PDF có thể ra NFD, LLM trả NFC — vẫn phải khớp."""
    import unicodedata

    ctx_nfc = "Số hữu tỉ là số viết được dưới dạng phân số."
    ctx_nfd = unicodedata.normalize("NFD", ctx_nfc)
    quote_nfc = "số viết được dưới dạng phân số"
    assert item_generation.quote_in_context(quote_nfc, ctx_nfd) is True


def test_quote_in_context_true_via_fuzzy_match_not_exact_substring():
    """Sai khác nhỏ (khác từ cuối câu) vẫn qua nếu longest-match ratio >= 0.8 — không phải substring chính xác."""
    ctx = "Phép cộng hai số nguyên cùng dấu ta cộng hai giá trị tuyệt đối rồi giữ nguyên dấu chung."
    quote = "Phép cộng hai số nguyên cùng dấu ta cộng hai giá trị tuyệt đối rồi giữ nguyên dấu nhau."
    # xác nhận đây KHÔNG phải substring chính xác (so trên dạng đã chuẩn hóa như quote_in_context thực hiện)
    assert item_generation._normalize_for_match(quote) not in item_generation._normalize_for_match(ctx)
    assert item_generation.quote_in_context(quote, ctx) is True  # nhưng vẫn qua nhờ fuzzy match


def test_is_grounded_requires_quote_present_in_context():
    ctx = "Phép cộng hai số tự nhiên luôn cho kết quả là số tự nhiên."
    assert item_generation.is_grounded(_item(grounded_quotes=["Phép cộng hai số tự nhiên"]), ctx) is True
    assert item_generation.is_grounded(_item(grounded_quotes=["trích dẫn bịa hoàn toàn khác"]), ctx) is False
    assert item_generation.is_grounded(_item(grounded_quotes=[]), ctx) is False


# ----------------------------- guardrail: has_valid_mcq_answer -----------------------------


def test_has_valid_mcq_answer_true_for_correct_match():
    item = _item(options=[{"key": "A", "text": "1"}, {"key": "B", "text": "2"}], answer_key={"correct": "B"})
    assert item_generation.has_valid_mcq_answer(item, enums.QuestionType.TRUE_FALSE) is True


def test_has_valid_mcq_answer_false_when_correct_not_in_options():
    item = _item(answer_key={"correct": "Z"})
    assert item_generation.has_valid_mcq_answer(item, enums.QuestionType.TRUE_FALSE) is False


def test_has_valid_mcq_answer_false_when_duplicate_keys():
    item = _item(options=[{"key": "A", "text": "x"}, {"key": "A", "text": "y"}])
    assert item_generation.has_valid_mcq_answer(item, enums.QuestionType.TRUE_FALSE) is False


def test_has_valid_mcq_answer_true_for_essay_without_options():
    item = _item(options=None, answer_key={"answer": "tự luận", "rubric": "..."})
    assert item_generation.has_valid_mcq_answer(item, enums.QuestionType.ESSAY) is True


def test_has_valid_mcq_answer_requires_exactly_4_options_a_to_d():
    ok = _item(options=[{"key": k, "text": k} for k in "ABCD"], answer_key={"correct": "B"})
    assert item_generation.has_valid_mcq_answer(ok, enums.QuestionType.MCQ) is True
    two = _item(options=[{"key": "A", "text": "1"}, {"key": "B", "text": "2"}], answer_key={"correct": "A"})
    assert item_generation.has_valid_mcq_answer(two, enums.QuestionType.MCQ) is False


def test_has_valid_mcq_answer_true_false_needs_exactly_2_options():
    tf = _item(options=[{"key": "A", "text": "Đúng"}, {"key": "B", "text": "Sai"}], answer_key={"correct": "A"})
    assert item_generation.has_valid_mcq_answer(tf, enums.QuestionType.TRUE_FALSE) is True
    assert item_generation.has_valid_mcq_answer(tf, enums.QuestionType.MCQ) is False


def test_has_valid_mcq_answer_essay_skips_rule():
    e = _item(options=None, answer_key={"answer": "x", "rubric": "y"})
    assert item_generation.has_valid_mcq_answer(e, enums.QuestionType.ESSAY) is True


# ----------------------------- guardrail: passes_guardrails -----------------------------


_DEFAULT_CONTEXT = "Phép cộng hai số tự nhiên luôn cho kết quả là số tự nhiên."


def test_passes_guardrails_true_for_valid_item():
    item = _item(options=[{"key": k, "text": k} for k in "ABCD"], answer_key={"correct": "B"})
    assert item_generation.passes_guardrails(item, enums.QuestionType.MCQ, _DEFAULT_CONTEXT) is True


def test_passes_guardrails_false_when_not_grounded():
    item = _item(options=[{"key": k, "text": k} for k in "ABCD"], answer_key={"correct": "B"}, grounded_quotes=[])
    assert item_generation.passes_guardrails(item, enums.QuestionType.MCQ, _DEFAULT_CONTEXT) is False


def test_passes_guardrails_false_when_mcq_answer_invalid():
    item = _item(options=[{"key": k, "text": k} for k in "ABCD"], answer_key={"correct": "Z"})
    assert item_generation.passes_guardrails(item, enums.QuestionType.MCQ, _DEFAULT_CONTEXT) is False


def test_passes_guardrails_no_longer_blocks_on_bloom():
    """Bloom lệch chỉ là cờ mềm (Task 5) — không loại câu."""
    ctx = "Phép cộng hai số tự nhiên luôn có kết quả."
    item = _item(
        options=[{"key": k, "text": k} for k in "ABCD"],
        answer_key={"correct": "B"},
        bloom_level=1,
        grounded_quotes=["Phép cộng hai số tự nhiên"],
    )
    assert item_generation.passes_guardrails(item, enums.QuestionType.MCQ, ctx) is True


# ----------------------------- self-consistency -----------------------------


def test_self_consistency_matches_true_when_same_answer():
    item = _item(answer_key={"correct": "B"})
    assert item_generation.self_consistency_matches(item, {"correct": "B"}) is True


def test_self_consistency_matches_false_when_different_answer():
    """Đây là tín hiệu quan trọng nhất: LLM tự giải ra đáp án KHÁC answer_key gốc -> nghi đáp án sai."""
    item = _item(answer_key={"correct": "B"})
    assert item_generation.self_consistency_matches(item, {"correct": "A"}) is False


def test_self_consistency_matches_none_when_solve_failed():
    assert item_generation.self_consistency_matches(_item(), None) is None


def test_self_consistency_matches_none_for_essay():
    """Tự luận: câu trả lời tự do, không so trực tiếp được -> không xác định (không chặn câu)."""
    item = _item(options=None, answer_key={"answer": "...", "rubric": "..."})
    assert item_generation.self_consistency_matches(item, {"answer": "khác hoàn toàn"}) is None


def test_consistency_label_mapping():
    assert item_generation.consistency_label(True) == "match"
    assert item_generation.consistency_label(False) == "mismatch"
    assert item_generation.consistency_label(None) == "unknown"


# ----------------------------- parse_solve_answer -----------------------------


def test_parse_solve_answer_parses_fenced_json():
    assert item_generation.parse_solve_answer('```json\n{"correct": "B"}\n```') == {"correct": "B"}


def test_parse_solve_answer_none_on_invalid_json():
    assert item_generation.parse_solve_answer("không phải JSON") is None


# ----------------------------- build_generate_prompt / build_solve_prompt -----------------------------


def test_build_generate_prompt_includes_key_fields():
    prompt = item_generation.build_generate_prompt(
        "Toán", 8, "Phân thức đại số", 2, enums.QuestionType.MCQ, 5, "ngữ cảnh SGK", misconceptions=[]
    )
    assert "Toán" in prompt
    assert "lớp 8" in prompt
    assert "Phân thức đại số" in prompt
    assert "ngữ cảnh SGK" in prompt
    assert "5 câu" in prompt


def test_build_generate_prompt_v2_includes_rules_and_misconceptions():
    prompt = item_generation.build_generate_prompt(
        "Toán",
        7,
        "Số hữu tỉ",
        2,
        enums.QuestionType.MCQ,
        5,
        "ngữ cảnh SGK",
        misconceptions=["Cộng hai phân số bằng cách cộng tử với tử, mẫu với mẫu"],
    )
    assert "ĐÚNG 4 lựa chọn" in prompt
    assert "Tất cả các đáp án trên" in prompt  # luật cấm được nêu trong prompt
    assert "cộng tử với tử" in prompt  # misconception được tiêm vào
    assert "misconception" in prompt  # yêu cầu field trong JSON


def test_build_generate_prompt_v2_without_misconceptions_omits_block():
    prompt = item_generation.build_generate_prompt(
        "Toán", 7, "Số hữu tỉ", 2, enums.QuestionType.MCQ, 5, "ngữ cảnh SGK", misconceptions=[]
    )
    assert "LỖI SAI PHỔ BIẾN" not in prompt


def test_generated_option_accepts_misconception_field():
    opt = item_generation.GeneratedOption(key="B", text="5/6", misconception="cộng tử với tử")
    assert opt.misconception == "cộng tử với tử"
    assert item_generation.GeneratedOption(key="A", text="đúng").misconception is None


def test_build_solve_prompt_includes_options_for_mcq():
    prompt = item_generation.build_solve_prompt(_item())
    assert "A. 1" in prompt and "B. 2" in prompt


def test_build_solve_prompt_omits_options_for_essay():
    item = _item(options=None, answer_key={"answer": "...", "rubric": "..."})
    prompt = item_generation.build_solve_prompt(item)
    assert "A." not in prompt


# ----------------------------- bloom check độc lập + critic -----------------------------


def test_build_bloom_check_prompt_hides_requested_level():
    prompt = item_generation.build_bloom_check_prompt(_item(bloom_level=3))
    assert "1 + 1 = ?" in prompt
    assert "mức Bloom 3" not in prompt  # không được mớm mức yêu cầu


def test_parse_bloom_check_valid_and_invalid():
    assert item_generation.parse_bloom_check('{"bloom_level": 4}') == 4
    assert item_generation.parse_bloom_check('{"bloom_level": 9}') is None
    assert item_generation.parse_bloom_check("hỏng") is None


def test_parse_bloom_check_rejects_bool_disguised_as_int():
    """bool là subclass của int trong Python -> phải chặn tường minh, không được lọt qua như mức 1."""
    assert item_generation.parse_bloom_check('{"bloom_level": true}') is None


def test_bloom_check_label():
    assert item_generation.bloom_check_label(2, 2) == "match"
    assert item_generation.bloom_check_label(4, 2) == "mismatch"
    assert item_generation.bloom_check_label(None, 2) == "unknown"


def test_build_critic_prompt_contains_rubric_and_answer():
    prompt = item_generation.build_critic_prompt(_item())
    assert "1 + 1 = ?" in prompt
    assert "Đáp án công bố: B" in prompt


def test_parse_critic_result_clamps_and_validates():
    assert item_generation.parse_critic_result('{"score": 7, "issues": ["stem mơ hồ"]}') == {
        "score": 7,
        "issues": ["stem mơ hồ"],
    }
    assert item_generation.parse_critic_result('{"score": 99}') is None
    assert item_generation.parse_critic_result("not json") is None


def test_parse_critic_result_rejects_bool_disguised_as_number():
    """bool là subclass của int trong Python -> phải chặn tường minh, không được lọt qua như score 1.0."""
    assert item_generation.parse_critic_result('{"score": true}') is None


def test_parse_critic_result_filters_whitespace_only_issues():
    assert item_generation.parse_critic_result('{"score": 5, "issues": ["  ", ""]}') == {"score": 5.0, "issues": []}


def test_parse_critic_result_defaults_missing_issues_to_empty_list():
    assert item_generation.parse_critic_result('{"score": 8}') == {"score": 8.0, "issues": []}


# ----------------------------- generate_items (tầng DB + LLM, mock) -----------------------------


def test_generate_items_raises_when_no_rag_context(monkeypatch):
    """RAG không tìm thấy nội dung -> KHÔNG sinh câu (chặn LLM bịa ngoài chương trình)."""
    fake_db = MagicMock()
    fake_db.get.side_effect = lambda model, _id: SimpleNamespace(code="toan", name="Toán")
    monkeypatch.setattr(item_generation.retrieval, "search_textbook", lambda *a, **k: [])

    with pytest.raises(item_generation.InsufficientContextError):
        item_generation.generate_items(fake_db, uuid4(), uuid4(), uuid4(), 8, uuid4(), 2, enums.QuestionType.MCQ, 3)


def test_generate_items_raises_when_subject_or_unit_missing(monkeypatch):
    fake_db = MagicMock()
    fake_db.get.return_value = None
    with pytest.raises(ValueError):
        item_generation.generate_items(fake_db, uuid4(), uuid4(), uuid4(), 8, uuid4(), 2, enums.QuestionType.MCQ, 3)


def test_generate_items_creates_only_items_passing_guardrails(monkeypatch):
    """1 câu hợp lệ + 1 câu quote bịa (bị loại) -> chỉ 1 QuestionItem; provenance đủ cờ mềm."""
    fake_db = MagicMock()
    fake_db.get.side_effect = lambda model, _id: SimpleNamespace(code="toan", name="Toán")
    fake_db.execute.return_value.scalars.return_value.all.return_value = []  # không misconception/câu cũ
    monkeypatch.setattr(item_generation.retrieval, "search_textbook", lambda *a, **k: [{"text": "Nội dung SGK Toán"}])
    monkeypatch.setattr(item_generation.retrieval, "embed_query", lambda *a, **k: [1.0, 0.0])

    generate_raw = (
        '[{"stem":"Câu hợp lệ","options":[{"key":"A","text":"1"},{"key":"B","text":"2"},'
        '{"key":"C","text":"3"},{"key":"D","text":"4"}],"answer_key":{"correct":"B"},"solution":"...",'
        '"bloom_level":2,"grounded_quotes":["Nội dung SGK Toán"]},'
        '{"stem":"Câu quote bịa","options":[{"key":"A","text":"1"},{"key":"B","text":"2"},'
        '{"key":"C","text":"3"},{"key":"D","text":"4"}],"answer_key":{"correct":"A"},"solution":"...",'
        '"bloom_level":2,"grounded_quotes":["trích dẫn hoàn toàn bịa đặt khác xa"]}]'
    )

    def fake_invoke(prompt):
        if "soạn" in prompt and "JSON array" in prompt:
            return _fake_llm_response(generate_raw)
        if "Phân loại mức Bloom" in prompt:
            return _fake_llm_response('{"bloom_level": 2}')
        if "chuyên gia khảo thí" in prompt:
            return _fake_llm_response('{"score": 9, "issues": []}')
        return _fake_llm_response('{"correct": "B"}')  # solve

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = fake_invoke
    monkeypatch.setattr(item_generation, "get_llm", lambda: mock_llm)

    created = item_generation.generate_items(
        fake_db, uuid4(), uuid4(), uuid4(), 8, uuid4(), 2, enums.QuestionType.MCQ, 5
    )

    assert len(created) == 1
    prov = created[0].provenance
    assert prov["self_consistency"] == "match"
    assert prov["bloom_check"] == "match"
    assert prov["critic"] == {"score": 9, "issues": []}
    assert prov["duplicate_of"] is None
    assert prov["rag_hits"] == [{"chuong": None, "heading": None, "source_md": None, "score": None}]
    assert prov["stem_embedding"] == [1.0, 0.0]
    fake_db.commit.assert_called_once()


def test_generate_items_intra_batch_duplicate_stores_real_flushed_id(monkeypatch):
    """2 câu trong CÙNG 1 lô trùng nhau -> duplicate_of của câu 2 phải là id THẬT (đã flush) của câu 1,
    không phải UUID giả (bug đã sửa: db.flush() ngay sau db.add() để lấy id server-generated)."""
    fake_db = MagicMock()
    fake_db.get.side_effect = lambda model, _id: SimpleNamespace(code="toan", name="Toán")
    fake_db.execute.return_value.scalars.return_value.all.return_value = []  # không câu cũ trong DB

    added_items: list = []
    fake_db.add.side_effect = added_items.append

    def fake_flush() -> None:
        for obj in added_items:
            if obj.id is None:
                obj.id = uuid4()  # giả lập RETURNING của Postgres khi flush

    fake_db.flush.side_effect = fake_flush

    monkeypatch.setattr(item_generation.retrieval, "search_textbook", lambda *a, **k: [{"text": "Nội dung SGK Toán"}])
    # cùng 1 vector cho MỌI câu -> 2 câu bất kỳ trong lô luôn được coi là "trùng" (cosine = 1.0)
    monkeypatch.setattr(item_generation.retrieval, "embed_query", lambda *a, **k: [1.0, 0.0])

    generate_raw = (
        '[{"stem":"Câu 1","options":[{"key":"A","text":"1"},{"key":"B","text":"2"},'
        '{"key":"C","text":"3"},{"key":"D","text":"4"}],"answer_key":{"correct":"B"},"solution":"...",'
        '"bloom_level":2,"grounded_quotes":["Nội dung SGK Toán"]},'
        '{"stem":"Câu 2","options":[{"key":"A","text":"1"},{"key":"B","text":"2"},'
        '{"key":"C","text":"3"},{"key":"D","text":"4"}],"answer_key":{"correct":"B"},"solution":"...",'
        '"bloom_level":2,"grounded_quotes":["Nội dung SGK Toán"]}]'
    )

    def fake_invoke(prompt):
        if "soạn" in prompt and "JSON array" in prompt:
            return _fake_llm_response(generate_raw)
        if "Phân loại mức Bloom" in prompt:
            return _fake_llm_response('{"bloom_level": 2}')
        if "chuyên gia khảo thí" in prompt:
            return _fake_llm_response('{"score": 9, "issues": []}')
        return _fake_llm_response('{"correct": "B"}')  # solve

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = fake_invoke
    monkeypatch.setattr(item_generation, "get_llm", lambda: mock_llm)

    created = item_generation.generate_items(
        fake_db, uuid4(), uuid4(), uuid4(), 8, uuid4(), 2, enums.QuestionType.MCQ, 5
    )

    assert len(created) == 2
    assert created[0].id is not None  # đã được gán id thật qua flush
    assert created[0].provenance["duplicate_of"] is None  # câu đầu tiên, chưa có gì để so
    assert created[1].provenance["duplicate_of"] == str(created[0].id)  # id THẬT, không phải UUID giả


def test_generate_items_background_notifies_on_failure(monkeypatch):
    """Thất bại nền phải BÁO người bấm sinh — không còn hố đen."""
    fake_session = MagicMock()
    monkeypatch.setattr(item_generation, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(
        item_generation,
        "generate_items",
        MagicMock(side_effect=item_generation.InsufficientContextError("không có ngữ cảnh")),
    )
    notify_mock = MagicMock()
    monkeypatch.setattr(item_generation.notifications, "notify_generation_failed", notify_mock)

    school, user, subject = uuid4(), uuid4(), uuid4()
    item_generation.generate_items_background(school, user, subject, 8, uuid4(), 2, enums.QuestionType.MCQ, 3)

    notify_mock.assert_called_once()
    fake_session.close.assert_called_once()


def test_generate_items_background_swallows_errors(monkeypatch):
    """Lỗi trong luồng nền KHÔNG được raise ra ngoài (BackgroundTasks không có ai bắt lỗi)."""
    fake_session = MagicMock()
    monkeypatch.setattr(item_generation, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(item_generation.notifications, "notify_generation_failed", MagicMock())

    def _boom(*_a, **_k):
        raise item_generation.InsufficientContextError("không có ngữ cảnh")

    monkeypatch.setattr(item_generation, "generate_items", _boom)

    item_generation.generate_items_background(uuid4(), uuid4(), uuid4(), 8, uuid4(), 2, enums.QuestionType.MCQ, 3)

    fake_session.rollback.assert_called_once()
    fake_session.close.assert_called_once()


# ----------------------------- dedup + overgen -----------------------------


def test_cosine_similarity_basics():
    assert item_generation.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert item_generation.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert item_generation.cosine_similarity([1.0], []) == 0.0


def test_find_duplicate_returns_most_similar_above_threshold():
    a, b = uuid4(), uuid4()
    existing = [(a, [1.0, 0.0]), (b, [0.9, 0.1])]
    assert item_generation.find_duplicate([1.0, 0.0], existing, threshold=0.99) == a
    assert item_generation.find_duplicate([0.0, 1.0], existing, threshold=0.99) is None


def test_overgen_count_requests_extra_but_capped():
    assert item_generation.overgen_count(5) == 8  # ceil(5*1.5)
    assert item_generation.overgen_count(1) == 2
    assert item_generation.overgen_count(20) == 30  # trần
