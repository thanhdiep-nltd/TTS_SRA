"""Tool RAG cho knowledge_agent: tra cứu nội dung sách giáo khoa trong Qdrant."""

from langchain_core.tools import tool

from src.observability import logger
from src.services import retrieval


def _format_hits(hits: list[dict]) -> str:
    """Định dạng kết quả kèm TRÍCH DẪN nguồn (môn/lớp/heading) để câu trả lời có thể dẫn nguồn."""
    blocks = []
    for i, h in enumerate(hits, 1):
        mon = h.get("mon", "?")
        lop = h.get("lop", "?")
        heading = h.get("heading") or "(không tiêu đề)"
        text = (h.get("text") or "").strip()
        blocks.append(f"[Nguồn {i}] Môn={mon} · Lớp={lop} · Mục: {heading} (độ liên quan {h['score']:.2f})\n{text}")
    return "\n\n---\n\n".join(blocks)


@tool
def search_textbook(query: str, mon: str | None = None, lop: str | None = None) -> str:
    """Tra cứu NỘI DUNG KIẾN THỨC trong sách giáo khoa (định nghĩa, công thức, giải thích bài học).

    Dùng cho câu hỏi về nội dung môn học, KHÔNG dùng cho điểm số/hồ sơ học sinh.

    Args:
        query: Câu hỏi/nội dung cần tìm (tiếng Việt).
        mon: (tùy chọn) Mã môn để thu hẹp: toan, ngu_van, khoa_hoc_tu_nhien,
            lich_su_dia_li, tieng_anh, tin_hoc, cong_nghe, gdcd, hdtn.
        lop: (tùy chọn) Khối lớp 6-9.

    Returns:
        Các đoạn SGK liên quan nhất kèm trích dẫn nguồn, hoặc thông báo không tìm thấy.
    """
    try:
        hits = retrieval.search_textbook(query, mon=mon, lop=lop)
        # Lọc kết quả theo ngưỡng độ liên quan để tránh ảo tưởng. 0.45 hiệu chỉnh thực nghiệm
        # cho text-embedding-3-large 1024D: câu lạc đề đo được tối đa ~0.42, câu đúng chủ đề >= 0.41.
        hits = [h for h in hits if h.get("score", 0.0) >= 0.45]
    except retrieval.RetrievalUnavailableError:
        return "Kho tri thức sách giáo khoa tạm thời không khả dụng. Vui lòng thử lại sau."

    if not hits:
        logger.info("rag_zero_hits", query=query, mon=mon, lop=lop)
        scope = f" (môn={mon}, lớp={lop})" if (mon or lop) else ""
        return f"Không tìm thấy nội dung phù hợp trong sách giáo khoa cho yêu cầu này{scope}."

    return _format_hits(hits)
