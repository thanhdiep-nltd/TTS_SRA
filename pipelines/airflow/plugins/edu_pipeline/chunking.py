"""Chia nhỏ văn bản: (1) chunk thô theo token cho DeepSeek; (2) semantic chunk theo heading."""

from typing import Any, Protocol


class Tokenizer(Protocol):
    """Giao diện tối thiểu của tiktoken Encoding — cho phép inject khi test."""

    def encode(self, text: str) -> list[Any]: ...
    def decode(self, tokens: list[Any]) -> str: ...


def _default_tokenizer() -> Tokenizer:
    """Tokenizer mặc định (cl100k_base) — load lười để test offline không cần tiktoken."""
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


def chunk_by_tokens(
    text: str,
    max_tokens: int = 3000,
    overlap: int = 150,
    tokenizer: Tokenizer | None = None,
) -> list[str]:
    """Cắt text thành các khối ~max_tokens token (có overlap) để tránh tràn ngữ cảnh DeepSeek."""
    tok = tokenizer or _default_tokenizer()
    ids = tok.encode(text)
    if not ids:
        return []
    step = max(1, max_tokens - overlap)
    chunks: list[str] = []
    for start in range(0, len(ids), step):
        piece = ids[start : start + max_tokens]
        chunks.append(tok.decode(piece))
        if start + max_tokens >= len(ids):
            break
    return chunks


def heading_path(metadata: dict[str, str]) -> str:
    """Ghép các cấp heading (h1 > h2 > h3) thành chuỗi để lưu metadata."""
    parts = [metadata[k] for k in ("h1", "h2", "h3") if metadata.get(k)]
    return " > ".join(parts)


def semantic_chunk(markdown: str) -> list[dict[str, str]]:
    """Cắt Markdown theo thẻ #, ##, ### — không làm đứt gãy bài học/định lý.

    Trả về danh sách {"text", "heading"} cho từng mảnh nội dung.
    """
    from langchain_text_splitters import MarkdownHeaderTextSplitter

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")]
    )
    docs = splitter.split_text(markdown)
    return [
        {"text": doc.page_content, "heading": heading_path(doc.metadata)}
        for doc in docs
        if doc.page_content.strip()
    ]
