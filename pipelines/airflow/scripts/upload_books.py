"""Upload SGK PDF lên MinIO và trigger DAG ingestion qua Airflow REST API.

Phân tích cây thư mục data_mock/book/lop_{N}/canh_dieu/*.pdf -> metadata
(mon, lop, tap), upload vào bucket, rồi (tùy chọn) kích hoạt DAG 1.

Ví dụ:
  # Một cuốn, chạy thật:
  python upload_books.py --book ../../../data_mock/book/lop_8/canh_dieu/toan_8_tap_1.pdf
  # Tất cả nhưng bỏ qua sách scan (không có text layer):
  python upload_books.py --all --skip-scanned
  # Chỉ upload, không trigger:
  python upload_books.py --all --no-trigger
"""

import argparse
import pathlib
import re
import sys

import boto3
import fitz  # PyMuPDF — để phát hiện sách scan
import httpx

# Bản đồ nhận diện môn từ tên file (substring -> mã môn chuẩn hóa).
_SUBJECT_MAP: dict[str, str] = {
    "khoa_hoc_tu_nhien": "khoa_hoc_tu_nhien",
    "lich_su_va_ia_li": "lich_su_dia_li", "lich_su_va_dia_li": "lich_su_dia_li",
    "lich_su_va_ia_ly": "lich_su_dia_li",
    "giao_duc_cong_dan": "gdcd", "giao_duc_the_chat": "gdtc",
    "hoat_dong_trai_nghiem": "hdtn", "hoat_ong_trai_nghiem": "hdtn",
    "ngu_van": "ngu_van", "tieng_anh": "tieng_anh", "tin_hoc": "tin_hoc",
    "cong_nghe": "cong_nghe", "am_nhac": "am_nhac",
    "mi_thuat": "mi_thuat", "my_thuat": "mi_thuat", "toan": "toan",
}

DEFAULT_MINIO = "http://localhost:9000"
DEFAULT_AIRFLOW = "http://localhost:8080"
BUCKET = "edu-knowledge"
DAG_ID = "hybrid_pdf_to_markdown"

# Hybrid OCR: môn nhiều công thức/hình -> Vision LLM; còn lại -> Tesseract (nếu scan).
_VISION_SUBJECTS = {"toan", "khoa_hoc_tu_nhien"}


def decide_extract_mode(meta: dict, has_text: bool) -> str:
    """Chọn chế độ bóc tách: text (có sẵn) / vision (Toán-KHTN scan) / tesseract."""
    if has_text:
        return "text"
    return "vision" if meta["mon"] in _VISION_SUBJECTS else "tesseract"


def parse_metadata(path: pathlib.Path) -> dict:
    """Suy ra {mon, lop, tap} từ đường dẫn/tên file."""
    name = path.stem.lower()
    lop_match = re.search(r"lop_(\d+)", str(path).lower().replace("\\", "/"))
    lop = lop_match.group(1) if lop_match else ""
    mon = next((code for key, code in _SUBJECT_MAP.items() if key in name), name)
    tap_match = re.search(r"tap_?(\d)", name)
    tap = tap_match.group(1) if tap_match else ""
    return {"mon": mon, "lop": lop, "tap": tap}


def s3_key_for(meta: dict) -> str:
    """Sinh key duy nhất trên MinIO: raw_pdf/lop_{lop}/{mon}[_tap{N}].pdf."""
    suffix = f"_tap{meta['tap']}" if meta["tap"] else ""
    return f"raw_pdf/lop_{meta['lop']}/{meta['mon']}{suffix}.pdf"


def has_text_layer(path: pathlib.Path, sample: int = 8, threshold: int = 200) -> bool:
    """True nếu PDF có lớp text (không phải sách scan ảnh)."""
    doc = fitz.open(path)
    n = doc.page_count
    idxs = sorted({int(n * f) for f in (0.1, 0.3, 0.5, 0.7, 0.9) if int(n * f) < n})[:sample]
    chars = sum(len(doc[i].get_text("text")) for i in idxs)
    doc.close()
    return chars > threshold


def upload(client, path: pathlib.Path, key: str) -> None:
    """Đẩy file PDF lên MinIO."""
    client.upload_file(str(path), BUCKET, key, ExtraArgs={"ContentType": "application/pdf"})


def trigger(airflow_url: str, conf: dict) -> str:
    """Gọi Airflow REST tạo DagRun cho DAG 1; trả dag_run_id."""
    run_id = f"ingest_{conf['mon']}_{conf['lop']}_{conf['tap'] or '0'}_{conf['extract_mode']}"
    resp = httpx.post(
        f"{airflow_url.rstrip('/')}/api/v1/dags/{DAG_ID}/dagRuns",
        auth=("airflow", "airflow"),
        json={"dag_run_id": run_id, "conf": conf},
        timeout=30.0,
    )
    if resp.status_code == 409:
        return f"{run_id} (đã tồn tại)"
    resp.raise_for_status()
    return resp.json()["dag_run_id"]


def collect_files(args: argparse.Namespace) -> list[pathlib.Path]:
    """Lấy danh sách PDF theo --book hoặc --all (+ lọc --lop)."""
    if args.book:
        return [pathlib.Path(args.book)]
    root = pathlib.Path(args.root)
    files = sorted(root.glob("**/*.pdf"))
    if args.lop:
        files = [f for f in files if f"lop_{args.lop}" in str(f).replace("\\", "/")]
    if args.subjects:
        wanted = {s.strip() for s in args.subjects.split(",")}
        files = [f for f in files if parse_metadata(f)["mon"] in wanted]
    return files[: args.limit] if args.limit else files


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload SGK + trigger pipeline RAG")
    parser.add_argument("--book", help="Đường dẫn 1 file PDF")
    parser.add_argument("--all", action="store_true", help="Quét toàn bộ thư mục sách")
    parser.add_argument("--root", default="data_mock/book", help="Thư mục gốc chứa sách")
    parser.add_argument("--lop", help="Lọc theo khối, ví dụ 8")
    parser.add_argument("--subjects", help="Lọc theo môn (mã, phân tách bằng dấu phẩy), ví dụ toan,ngu_van")
    parser.add_argument("--limit", type=int, help="Giới hạn số file")
    parser.add_argument("--skip-scanned", action="store_true", help="Bỏ qua sách scan (không text layer)")
    parser.add_argument("--no-trigger", action="store_true", help="Chỉ upload, không kích hoạt DAG")
    parser.add_argument("--mode", choices=["auto", "text", "tesseract", "vision"], default="auto",
                        help="Ép chế độ bóc tách (mặc định auto = quyết định theo môn/text-layer)")
    parser.add_argument("--max-pages", type=int, default=0, help="Giới hạn số trang (0=toàn bộ) để chạy thử rẻ")
    parser.add_argument("--minio", default=DEFAULT_MINIO)
    parser.add_argument("--airflow", default=DEFAULT_AIRFLOW)
    args = parser.parse_args()

    files = collect_files(args)
    if not files:
        print("Không tìm thấy file PDF nào.")
        return 1

    client = boto3.client(
        "s3", endpoint_url=args.minio,
        aws_access_key_id="minioadmin", aws_secret_access_key="minioadmin",
    )
    done, skipped = 0, 0
    for path in files:
        if not path.exists():
            print(f"[BỎ QUA] không tồn tại: {path}")
            continue
        if args.skip_scanned and not has_text_layer(path):
            print(f"[SCAN-SKIP] {path.name} (không có text layer)")
            skipped += 1
            continue
        meta = parse_metadata(path)
        key = s3_key_for(meta)
        mode = args.mode if args.mode != "auto" else decide_extract_mode(meta, has_text_layer(path))
        upload(client, path, key)
        conf = {"s3_key": key, "chuong": "", "extract_mode": mode, "max_pages": args.max_pages, **meta}
        msg = (f"[OK] {path.name} -> s3://{BUCKET}/{key}  mon={meta['mon']} lop={meta['lop']} "
               f"tap={meta['tap'] or '-'} mode={mode}")
        if not args.no_trigger:
            msg += f"  | DAG run: {trigger(args.airflow, conf)}"
        print(msg)
        done += 1

    print(f"\nHoàn tất: upload+trigger {done} file, bỏ qua scan {skipped}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
