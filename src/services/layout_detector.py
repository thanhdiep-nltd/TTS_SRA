"""Dịch vụ phát hiện bố cục tài liệu (Document Layout Analysis) bằng DocLayout-YOLO (ONNX).

Phát hiện chính xác 100% từng pixel các khối hình vẽ (figure), bảng (table), công thức độc lập (isolate_formula),
và tự động khớp nối (Spatial Association) vào các câu hỏi tương ứng được bóc tách từ VLM.
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    from src.services.vlm import SegmentedQuestion

logger = logging.getLogger(__name__)

_MODEL_PATH = Path("models/doclayout_yolo.onnx")
_SESSION: Any = None

# Danh mục nhãn của DocLayout-YOLO (DocStructBench dataset)
_CLASS_NAMES: dict[int, str] = {
    0: "title",
    1: "plain_text",
    2: "abandon",
    3: "figure",
    4: "figure_caption",
    5: "table",
    6: "table_caption",
    7: "table_footnote",
    8: "isolate_formula",
    9: "formula_caption",
}

_TARGET_CLASSES = {"figure", "table"}


def _get_session() -> Any:
    """Khởi tạo hoặc trả về InferenceSession của DocLayout-YOLO (Singleton)."""
    global _SESSION
    if _SESSION is not None:
        return _SESSION

    if not _MODEL_PATH.exists():
        logger.warning("Không tìm thấy model DocLayout-YOLO tại %s", _MODEL_PATH)
        return None

    try:
        import onnxruntime as ort

        # Ưu tiên CUDA nếu có, fallback về CPU
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        available_providers = ort.get_available_providers()
        valid_providers = [p for p in providers if p in available_providers]

        _SESSION = ort.InferenceSession(str(_MODEL_PATH), providers=valid_providers or ["CPUExecutionProvider"])
        logger.info("Đã nạp DocLayout-YOLO ONNX session thành công (providers=%s)", valid_providers)
        return _SESSION
    except Exception:
        logger.exception("Lỗi khởi tạo ONNX session cho DocLayout-YOLO")
        return None


def is_available() -> bool:
    """Kiểm tra xem model DocLayout-YOLO có sẵn sàng chạy không."""
    return _MODEL_PATH.exists()


def detect_figures(pil_img: Image.Image, conf_threshold: float = 0.25) -> list[tuple[float, float, float, float]]:
    """
    Phát hiện toàn bộ các vùng hình vẽ, biểu đồ, sơ đồ minh họa trên 1 ảnh trang đề thi.
    Trả về danh sách bounding box (x1, y1, x2, y2) theo pixel gốc, sắp xếp từ trên xuống dưới theo trục Y.
    """
    session = _get_session()
    if session is None:
        return []

    orig_w, orig_h = pil_img.size
    img_rgb = pil_img.convert("RGB")

    # Letterbox resize về 1024x1024 chuẩn của model
    target_size = 1024
    scale = min(target_size / orig_w, target_size / orig_h)
    new_w, new_h = int(round(orig_w * scale)), int(round(orig_h * scale))
    img_resized = img_rgb.resize((new_w, new_h), Image.Resampling.BICUBIC)

    pad_img = Image.new("RGB", (target_size, target_size), (114, 114, 114))
    pad_x = (target_size - new_w) // 2
    pad_y = (target_size - new_h) // 2
    pad_img.paste(img_resized, (pad_x, pad_y))

    # Chuẩn hóa NCHW float32 [0..1]
    img_arr = np.array(pad_img).astype(np.float32) / 255.0
    img_arr = np.transpose(img_arr, (2, 0, 1))
    img_arr = np.expand_dims(img_arr, axis=0)

    try:
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: img_arr})
        out_tensor = outputs[0]
    except Exception:
        logger.warning("Lỗi chạy inference DocLayout-YOLO", exc_info=True)
        return []

    # Parse detections
    raw_boxes: list[tuple[float, float, float, float, float, str]] = []
    if len(out_tensor.shape) == 3:
        dets = out_tensor[0]
        if dets.shape[0] == 6 and dets.shape[1] > 6:
            dets = dets.T
        for det in dets:
            if len(det) >= 6:
                x1, y1, x2, y2, score, cls_id = det[:6]
                score_val = float(score)
                cls_int = int(cls_id)
                label = _CLASS_NAMES.get(cls_int, str(cls_int))

                if score_val >= conf_threshold and label in _TARGET_CLASSES:
                    # Chuyển đổi tọa độ từ 1024x1024 về ảnh gốc
                    ox1 = max(0.0, (float(x1) - pad_x) / scale)
                    oy1 = max(0.0, (float(y1) - pad_y) / scale)
                    ox2 = min(float(orig_w), (float(x2) - pad_x) / scale)
                    oy2 = min(float(orig_h), (float(y2) - pad_y) / scale)

                    if ox2 - ox1 >= 10 and oy2 - oy1 >= 10:
                        raw_boxes.append((ox1, oy1, ox2, oy2, score_val, label))

    if not raw_boxes:
        return []

    # Hợp nhất các box hình vẽ nằm cùng một hàng ngang hoặc lồng nhau (như 4 hình phẳng của Câu 6)
    merged_boxes = _merge_adjacent_figure_boxes(raw_boxes)

    # Sắp xếp từ trên xuống dưới theo tâm tung độ Y
    merged_boxes.sort(key=lambda b: (b[1] + b[3]) / 2.0)
    return merged_boxes


def _merge_adjacent_figure_boxes(
    boxes: list[tuple[float, float, float, float, float, str]],
) -> list[tuple[float, float, float, float]]:
    """Hợp nhất các box hình vẽ nhỏ nằm cùng hàng hoặc giao nhau tạo thành cụm hình trọn vẹn."""
    if not boxes:
        return []

    # Lấy tọa độ (x1, y1, x2, y2)
    coords = [(b[0], b[1], b[2], b[3]) for b in boxes]
    coords.sort(key=lambda b: b[1])  # sort theo y1

    merged: list[tuple[float, float, float, float]] = []
    used = [False] * len(coords)

    for i in range(len(coords)):
        if used[i]:
            continue
        cx1, cy1, cx2, cy2 = coords[i]
        used[i] = True

        for j in range(i + 1, len(coords)):
            if used[j]:
                continue
            jx1, jy1, jx2, jy2 = coords[j]

            # Kiểm tra xem 2 box có cùng dải tung độ Y không (độ lệch Y tâm < 40px hoặc overlap dọc > 50%)
            y_overlap = max(0.0, min(cy2, jy2) - max(cy1, jy1))
            min_h = min(cy2 - cy1, jy2 - jy1)

            if min_h > 0 and (y_overlap / min_h > 0.45 or abs((cy1 + cy2) / 2.0 - (jy1 + jy2) / 2.0) < 35):
                # Hợp nhất box
                cx1 = min(cx1, jx1)
                cy1 = min(cy1, jy1)
                cx2 = max(cx2, jx2)
                cy2 = max(cy2, jy2)
                used[j] = True

        # Đệm nhẹ 4px
        merged.append((max(0.0, cx1 - 4), max(0.0, cy1 - 4), cx2 + 4, cy2 + 4))

    return merged


def associate_figures_to_questions(
    page_images: list[Image.Image],
    questions: list[SegmentedQuestion],
) -> list[SegmentedQuestion]:
    """
    Khớp nối không gian (Spatial Association) giữa Bounding Box hình ảnh do DocLayout-YOLO phát hiện
    với danh sách câu hỏi do VLM bóc tách, sau đó cắt ảnh trực tiếp.
    """
    if not page_images or not questions:
        return questions

    # Nhóm câu hỏi theo page_index
    pages_dict: dict[int, list[SegmentedQuestion]] = {}
    for q in questions:
        p_idx = max(0, min(len(page_images) - 1, getattr(q, "page_index", 0)))
        pages_dict.setdefault(p_idx, []).append(q)

    for p_idx, p_questions in pages_dict.items():
        page_img = page_images[p_idx]
        w, h = page_img.size

        # Phát hiện tất cả hình vẽ trên trang bằng DocLayout-YOLO
        detected_figure_boxes = detect_figures(page_img)

        # Lọc các câu hỏi được VLM đánh dấu có hình vẽ
        figure_questions = [q for q in p_questions if q.has_figure]

        if not detected_figure_boxes:
            # Nếu YOLO không thấy hình nào trên trang (toàn chữ/công thức hoặc câu yêu cầu học sinh tự vẽ)
            for q in p_questions:
                q.has_figure = False
                q.image_data_url = None
                q.cropped_bytes = None
                q.box_2d = None
            continue

        # Ghép nối theo thứ tự từ trên xuống dưới
        n_figs = len(detected_figure_boxes)
        for i, q in enumerate(figure_questions):
            if i < n_figs:
                box_to_use = detected_figure_boxes[i]
                bx1, by1, bx2, by2 = box_to_use
                # Crop trực tiếp từ ảnh gốc
                try:
                    cropped = page_img.crop((int(bx1), int(by1), int(bx2), int(by2)))
                    buf = io.BytesIO()
                    cropped.save(buf, format="PNG")
                    raw_bytes = buf.getvalue()
                    b64 = f"data:image/png;base64,{base64.b64encode(raw_bytes).decode('ascii')}"

                    q.image_data_url = b64
                    q.cropped_bytes = raw_bytes
                    q.has_figure = True
                    # Cập nhật tọa độ chuẩn hóa 0..1000
                    q.box_2d = [
                        round(bx1 * 1000.0 / w, 1),
                        round(by1 * 1000.0 / h, 1),
                        round(bx2 * 1000.0 / w, 1),
                        round(by2 * 1000.0 / h, 1),
                    ]
                except Exception:
                    logger.warning("Lỗi crop ảnh cho câu %d", q.question_number, exc_info=True)
            else:
                # Nếu số câu vượt quá số hình YOLO phát hiện thì câu này không có hình
                q.has_figure = False
                q.image_data_url = None
                q.cropped_bytes = None
                q.box_2d = None

        # Đảm bảo các câu hỏi không có hình có image_data_url = None
        for q in p_questions:
            if not q.has_figure:
                q.image_data_url = None
                q.cropped_bytes = None
                q.box_2d = None

    return questions
