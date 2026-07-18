# TÀI LIỆU THIẾT KẾ HỆ THỐNG (SYSTEM DESIGN DOCUMENT)
**Dự án:** Hệ thống Xử lý & Lưu trữ Tri thức Giáo dục (Edu-Knowledge Pipeline)
**Phân hệ:** Data Ingestion & Vectorization (Kiến trúc Lai - Tối ưu chi phí)
**Công cụ điều phối cốt lõi:** Apache Airflow
**Phiên bản:** 1.2.0 | **Ngày cập nhật:** 23/06/2026
**Trạng thái:** Sẵn sàng triển khai (Ready for Implementation)

> **Ghi chú phiên bản 1.2.0 (đồng bộ với repo AI20K-075):** kiến trúc doanh nghiệp (Airflow + MinIO/S3 + Qdrant + DeepSeek + OpenAI) **giữ nguyên**. Bản này chỉ chỉnh các điểm để khớp repo thực tế: (1) backend là **FastAPI** chứ không phải Spring Boot — trigger pipeline qua endpoint FastAPI gọi Airflow REST API; (2) chốt Vector DB = **Qdrant** (biến `chroma_persist_dir` trong [src/config.py](../src/config.py) coi như **deprecated**, không dùng cho luồng RAG này); (3) toàn bộ pipeline đặt trong thư mục **`pipelines/`** tách rời, **không** import `src/` của app (decoupled). Kế hoạch triển khai chi tiết: [docs/RAG_implementation_plan.md](RAG_implementation_plan.md). Phạm vi bản này: **chỉ Ingestion** (PDF → Vector DB); phần Retrieval (rag_agent) sẽ thiết kế ở tài liệu riêng.

---

## 1. TỔNG QUAN (EXECUTIVE SUMMARY)
### 1.1. Mục tiêu hệ thống
Xây dựng một Data Pipeline tự động để chuyển đổi sách giáo khoa định dạng PDF thành vector ngữ nghĩa. Điểm nhấn của phiên bản 1.1.0 là áp dụng **Chiến lược Phân tầng Năng lực (Tiered Compute Strategy)**: sử dụng các công cụ mã nguồn mở miễn phí cho các tác vụ bóc tách thô, và chỉ sử dụng API của các LLM chất lượng cao (DeepSeek, OpenAI) cho các khâu đòi hỏi tư duy logic và định dạng phức tạp. 

### 1.2. Phân bổ Nguồn lực & Chi phí
* **Bóc tách ký tự thô (OCR):** Dùng `Marker` / `PyMuPDF` (Chạy local, Chi phí $0).
* **Tái cấu trúc, xử lý LaTeX (Cognitive Formatting):** Dùng `DeepSeek-V3 API` (Siêu rẻ, tư duy text xuất sắc).
* **Nhúng ngữ nghĩa (Embedding):** Dùng `OpenAI text-embedding-3-small` (Độ chính xác cao nhất cho hệ thống RAG).

---

## 2. KIẾN TRÚC TỔNG THỂ (HIGH-LEVEL ARCHITECTURE)
Hệ thống áp dụng kiến trúc **Event-Driven & Decoupled Pipeline** tách biệt làm 2 luồng (DAGs) chính, giao tiếp qua kho lưu trữ S3.

### 2.1. Các thành phần chính
1.  **Storage Layer:** MinIO / Amazon S3 (Lưu PDF, Text thô, Markdown sạch).
2.  **Orchestration Layer:** Apache Airflow (Quản lý DAGs, Retry, Alert).
3.  **Local Compute Node:** Các máy chủ chạy Airflow Worker có cài sẵn thư viện xử lý ảnh.
4.  **External AI APIs:**
    * *Formatting Engine:* DeepSeek-V3 API.
    * *Embedding Engine:* OpenAI API.
5.  **Vector Database:** Qdrant / Pinecone.

---

## 3. THIẾT KẾ DATA PIPELINE TRÊN AIRFLOW

### 3.1. DAG 1: `hybrid_pdf_to_markdown`
**Mô tả:** Đọc PDF, bóc tách chữ thô (local) $\rightarrow$ Định dạng lại chuẩn Markdown & LaTeX (Cloud API).
**Trigger:** Endpoint **FastAPI** `POST /api/v1/knowledge/ingest` (chỉ ADMIN) gọi **Airflow REST API** để tạo DagRun với `conf={s3_key, mon, lop, chuong}` khi có PDF mới được upload lên MinIO/S3.

| Tên Task | Phân bổ Công nghệ | Mô tả & Chức năng | Cơ chế Lỗi & Retry |
| :--- | :--- | :--- | :--- |
| `sensor_check_s3` | Airflow Sensor | Kiểm tra file PDF đã sẵn sàng trên S3. | Timeout: 5 mins |
| `local_raw_extraction` | `PyMuPDF` hoặc `Marker` (Python) | **[KHÂU THÔ - $0]** Cắt PDF, trích xuất toàn bộ text lộn xộn. Không quan tâm định dạng. | Retry: 2 lần (Lỗi do file hỏng) |
| `chunk_raw_text` | Python Script | Chia nhỏ text thô thành các khối vừa phải (khoảng 3000 token) để tránh tràn bộ nhớ DeepSeek. | Local execution |
| `deepseek_formatting` | `DeepSeek-V3 API` (Dynamic Task Mapping) | **[KHÂU QUAN TRỌNG - CHẤT LƯỢNG CAO]** Gửi text thô vào DeepSeek. Prompt: *"Dọn dẹp text thô, tái tạo cấu trúc thẻ Heading, chuyển biểu thức toán thành LaTeX. Không bịa kiến thức."* | Retries: 5 lần.<br>Exponential Backoff: Bật. |
| `stitch_and_save_md` | Python Regex | Nối các khối Markdown đã định dạng lại. Ghi đè vào S3 (VD: `clean_md/toan_9.md`). | Cảnh báo Slack nếu file < 1KB |
| `trigger_vector_dag` | TriggerDagRun | Kích hoạt DAG 2. | N/A |

### 3.2. DAG 2: `markdown_to_qdrant_ingestion`
**Mô tả:** Cắt file Markdown theo cấu trúc bài học và tạo ngữ nghĩa đưa vào Vector DB.
**Trigger:** Kích hoạt tự động từ DAG 1.

| Tên Task | Phân bổ Công nghệ | Mô tả & Chức năng | Cơ chế Lỗi & Retry |
| :--- | :--- | :--- | :--- |
| `semantic_chunker` | `MarkdownHeaderTextSplitter` | Nhận diện thẻ `#`, `##`. Phân mảnh nội dung không làm đứt gãy bài học/định lý. | Cảnh báo Data Quality |
| `openai_embedding` | `OpenAI API` | **[KHÂU CỐT LÕI - CHẤT LƯỢNG RAG]** Biến các mảnh văn bản thành vector. Dùng model `text-embedding-3-small` để tối ưu chi phí nhưng độ nhạy bén cao nhất. | Retries: 3 |
| `upsert_to_qdrant` | `Qdrant Client` | Đẩy Vector + Metadata (Lớp, Môn, Chương) vào DB. ID sinh ra từ mã Hash của đoạn text để chống trùng lặp. | Trạng thái Idempotent |
| `cleanup_temp` | BashOperator | Xóa file tạm trên ổ cứng Worker. | Soft fail |

---

## 4. BÀI TOÁN KINH TẾ (ROI & COST ANALYSIS)
So với kiến trúc cũ dùng Vision LLM cho mọi khâu, kiến trúc 1.1.0 mang lại hiệu quả vượt trội:

* **Giảm tải đám mây:** Khâu nặng nhất là đọc file PDF và nhận diện ký tự được đẩy về xử lý miễn phí ở máy chủ nội bộ.
* **Chi phí API siêu rẻ:** DeepSeek-V3 có giá cực kỳ cạnh tranh cho tác vụ xử lý Text. Định dạng 1 cuốn sách 200 trang tốn dưới `$0.05`.
* **Bảo vệ độ chính xác RAG:** Vẫn đầu tư ngân sách vào OpenAI Embedding API để đảm bảo Sub-agent tìm kiếm tài liệu chuẩn xác tuyệt đối. Hệ thống không bị "ngu" đi dù tiết kiệm được 90% chi phí bóc tách.

---

## 5. TIÊU CHUẨN DOANH NGHIỆP TRONG TRIỂN KHAI

### 5.1. Cơ chế Quản lý Biến & Bảo mật (Security & Secrets)
* **Vault Integration:** API Keys của DeepSeek và OpenAI được lưu trữ và mã hóa qua Airflow Connections, tuyệt đối không xuất hiện trong Git repository.

### 5.2. Cơ chế Giám sát & Cảnh báo (Alerting & Monitoring)
* **Slack Integration:** Bất kỳ task nào (đặc biệt là bước gọi API DeepSeek/OpenAI) gặp lỗi timeout hoặc API Limit (HTTP 429) sau 5 lần thử lại sẽ bắn thẳng log lỗi vào kênh `#data-alerts` trên Slack.

### 5.3. Quản lý Tài nguyên (Resource Management)
* **Concurrency Limits:** Airflow Pool được thiết lập để giới hạn tối đa 5 kết nối đồng thời gọi sang DeepSeek API, tránh tình trạng bị khóa tài khoản do spam request từ hàng chục tác vụ chạy song song.

---

## 6. TÍCH HỢP VỚI REPO AI20K-075 (REPO INTEGRATION)

Pipeline ingestion là hệ **batch/offline**, **decoupled** khỏi runtime FastAPI. Hai hệ chỉ giao tiếp qua 2 ranh giới rõ ràng:

1. **Trigger:** FastAPI (`src/api/v1/knowledge.py`) gọi **Airflow REST API** để chạy DAG 1. Đây là phần *duy nhất* trong `src/` chạm tới pipeline.
2. **Vector DB (Qdrant):** pipeline ghi vào collection `edu_knowledge`; sau này rag_agent (tài liệu Retrieval riêng) đọc lại.

### 6.1. Vị trí code (tách rời `src/`)
```
pipelines/airflow/
  docker-compose.airflow.yml   # airflow + minio + qdrant (TÁCH với compose app)
  Dockerfile.worker            # airflow + PyMuPDF/tiktoken/qdrant-client...
  dags/                        # hybrid_pdf_to_markdown.py · markdown_to_qdrant.py
  plugins/edu_pipeline/        # s3_io · pdf_extract · chunking · deepseek_format · embedding · qdrant_io · hashing · alerts
  tests/                       # unit test offline (mock API)
src/api/v1/knowledge.py        # endpoint upload + trigger DagRun (ADMIN)
```

### 6.2. Hạ tầng & metadata
* **Airflow metadata DB** dùng PostgreSQL **riêng** (KHÔNG dùng Neon của app). MinIO bucket `edu-knowledge` (prefix `raw_pdf/`, `raw_text/`, `clean_md/`).
* **Qdrant collection `edu_knowledge`:** vector `size=1536` (`text-embedding-3-small`), `distance=Cosine`. Payload index cho `mon`, `lop`, `chuong` để phục vụ filter (RBAC/khối-môn) ở khâu Retrieval.
* **Point ID = SHA-256(text)** → upsert **idempotent**, chạy lại không trùng.

> Chi tiết task-by-task, secrets (Airflow Connections/Variables), Pool, kế hoạch test và milestones: xem [docs/RAG_implementation_plan.md](RAG_implementation_plan.md).