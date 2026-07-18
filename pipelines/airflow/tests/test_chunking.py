"""Test cắt chunk theo token với tokenizer giả (offline, không cần tiktoken)."""

from edu_pipeline.chunking import chunk_by_tokens, heading_path


class FakeTokenizer:
    """Tokenizer ký tự: mỗi ký tự là 1 token — đủ để kiểm tra logic cắt/overlap."""

    def encode(self, text: str) -> list[str]:
        return list(text)

    def decode(self, tokens: list[str]) -> str:
        return "".join(tokens)


def test_empty_text_returns_empty():
    assert chunk_by_tokens("", tokenizer=FakeTokenizer()) == []


def test_short_text_single_chunk():
    chunks = chunk_by_tokens("abc", max_tokens=10, overlap=2, tokenizer=FakeTokenizer())
    assert chunks == ["abc"]


def test_splits_with_overlap():
    text = "abcdefghij"  # 10 ký tự
    chunks = chunk_by_tokens(text, max_tokens=4, overlap=1, tokenizer=FakeTokenizer())
    # step = 3 -> bắt đầu tại 0,3,6; dừng ở 6 vì 6+4>=10 (không sinh đuôi thừa)
    assert chunks == ["abcd", "defg", "ghij"]


def test_no_data_loss():
    text = "0123456789ABCDEF"
    chunks = chunk_by_tokens(text, max_tokens=5, overlap=2, tokenizer=FakeTokenizer())
    # Mọi ký tự đều xuất hiện ít nhất một lần
    assert set("".join(chunks)) == set(text)


def test_heading_path():
    assert heading_path({"h1": "Chương 1", "h2": "Bài 2"}) == "Chương 1 > Bài 2"
    assert heading_path({}) == ""
