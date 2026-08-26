# BÁO CÁO — Curriculum Ingestion & RAG Knowledge Agent

**Người viết**: [Tên] | **Ngày**: 26/08/2026

---

## 1. Giới thiệu

Flow này gồm 2 pipeline liên quan:

1. **Curriculum Ingestion**: Upload PDF sách giáo khoa → VLM tự động quét, tách mục lục, chương, bài → lưu vào curriculum_units
2. **RAG Knowledge Agent**: Agent trong Multi-Agent Chat tra cứu nội dung SGK qua Qdrant vector search → trả lời có trích dẫn nguồn

---

## 2. Kiến trúc tổng quan

### Curriculum Ingestion

```
Upload PDF SGK (TOAN 6, HK1)
       │
       ▼
┌──────────────────┐
│   Job Queue      │  ← DB-backed FIFO, 1 job/lần, timeout 60p
│  (curriculum_    │
│   ingest_jobs)   │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  VLM Lượt A      │  ← Scan ~15 trang đầu → mục lục → cây chương/bài
│  (Mục lục)       │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  VLM Lượt B      │  ← Phân loại từng trang, chọn NEO từ danh sách
│  (Nội dung)      │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Làm giàu từng   │  ← Tóm tắt + từ khóa + mục con (VLM)
│  bài             │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Chuẩn hóa +     │  ← normalize, filter placeholder, sanity-check
│  Sanity check    │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  curriculum_     │  ← Lưu cây chương/bài vào DB
│  units + books   │
└──────────────────┘
```

### RAG Knowledge Agent

```
User hỏi: "Định nghĩa phân số là gì? (lớp 6)"
       │
       ▼
┌──────────────────┐
│  Supervisor      │  → RouterDecision → knowledge_agent
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  search_textbook │  → Query Qdrant vector store
│  (mon, lop, q)   │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Qdrant top-k    │  → Chunks nội dung SGK
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  LLM tổng hợp    │  → Trả lời + trích dẫn nguồn
│  (có trích dẫn)  │
└──────────────────┘
```

---

## 3. Các thành phần chính

| File | Vai trò |
|------|---------|
| src/services/curriculum_ingest.py | Core ingestion: VLM 2 lượt quét, làm giàu, chuẩn hóa, lưu DB |
| src/services/curriculum_job_worker.py | DB-backed FIFO queue worker, timeout 60p |
| src/services/curriculum_catalog.py | CurriculumBook + CurriculumUnit CRUD |
| src/services/vlm.py | VLM client (Qwen3-VL-Flash qua Replicate) |
| src/services/retrieval.py | RAG retrieval: Qdrant vector search |
| src/agents/knowledge_agent/node.py | Knowledge Agent node (ReAct agent) |
| src/agents/knowledge_agent/tools.py | search_textbook tool |
| src/api/v1/curriculum.py | POST /curriculum/ingest-book, GET /curriculum/books, jobs |
| src/models/tables.py | CurriculumUnit, CurriculumBook, CurriculumChunk, CurriculumIngestJob |

---

## 4. Luồng hoạt động chi tiết

### Curriculum Ingestion

**Bước 1: Upload PDF**
- Admin chọn môn, lớp, học kỳ, upload file PDF SGK
- API lưu file tạm vào uploads/curriculum_tmp/
- Tạo CurriculumIngestJob (status=pending, subject_code, grade_number, semester_number)

**Bước 2: Job worker xử lý**
- process_next_curriculum_ingest_job():
  - Quét timeout: job "processing" > 60p → "failed"
  - Nếu có job đang chạy → hoãn
  - Lấy job pending cũ nhất → "processing", progress=5

**Bước 3: VLM Lượt A — scan mục lục**
- Đọc PDF bytes, gửi ~15 trang đầu đến VLM (Qwen3-VL-Flash)
- VLM trả về cây chương→bài + danh sách NEO (tên bài chuẩn)
- Progress → 10-30%

**Bước 4: VLM Lượt B — phân loại trang**
- Duyệt từng trang nội dung, gửi đến VLM
- VLM chỉ chọn NEO từ danh sách (không tự đặt tên) → chống bịa
- Progress → 30-70%

**Bước 5: Làm giàu từng bài**
- Với mỗi bài, gửi TOÀN BỘ trang đến VLM
- VLM trả về: tóm tắt, từ khóa, mục con
- Progress → 70-95%

**Bước 6: Chuẩn hóa và lưu**
- _normalize_title(): chuẩn hóa tên bài
- _is_placeholder(): lọc template placeholder
- _is_phu_title(): gắn cờ phụ (ôn tập, kiểm tra...)
- _sanity_check(): kiểm tra hợp lệ
- Lưu vào curriculum_units + curriculum_books
- Progress → 100%, status=completed

### RAG Knowledge Agent

**Bước 1:** Supervisor nhận câu hỏi kiến thức → route đến knowledge_agent
**Bước 2:** knowledge_agent gọi search_textbook(mon, lop, query)
**Bước 3:** search_textbook query Qdrant vector store → top-k chunks (kèm metadata: môn, lớp, chương, bài)
**Bước 4:** LLM tổng hợp câu trả lời từ chunks, BẮT BUỘC trích dẫn nguồn
**Bước 5:** Nếu không có chunk nào → báo "không có dữ liệu SGK cho câu hỏi này"

---

## 5. Kết quả đạt được

| Hạng mục | Trạng thái | Chi tiết |
|----------|-----------|----------|
| VLM 2 lượt quét thông minh | Hoạt động | Lượt A lấy mục lục, Lượt B chọn NEO, chống bịa |
| Không dùng số trang in | Hoạt động | Xác định khoảng bài theo tên, chịu được PDF cắt ngắn |
| Chuỗi chuẩn hóa | Hoạt động | normalize, placeholder, phu_title, sanity-check |
| Dry run preview | Hoạt động | Xem trước cây dự kiến trước khi ghi DB |
| DB-backed queue | Hoạt động | FIFO, timeout 60p, 1 job/lần, tracking progress |
| RAG grounding | Hoạt động | search_textbook BẮT BUỘC gọi Qdrant trước, không bịa |
| DOCX/TXT/MD support | Hoạt động | Ngoài PDF, có thể nạp DOCX (heading styles), TXT/MD (regex) |
| Chunk enrichment | Hoạt động | Tóm tắt + từ khóa + mục con cho mỗi bài |

---

## 6. Cách chạy thử

```bash
# 1. Nạp sách (dry run)
curl -X POST http://localhost:8000/api/v1/curriculum/ingest-book \
  -H "Authorization: Bearer <token_admin>" \
  -F "file=@sgk_toan6.pdf" \
  -F "subject_code=TOAN" \
  -F "grade_number=6" \
  -F "semester_number=1" \
  -F "dry_run=true"

# 2. Xem danh sách job
curl http://localhost:8000/api/v1/curriculum/ingest-book/jobs \
  -H "Authorization: Bearer <token_admin>"

# 3. Test knowledge agent
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id": null, "message": "Định nghĩa phân số là gì? (lớp 6)"}'

# 4. Test
pytest tests/test_curriculum_*.py tests/test_agents/test_knowledge_agent.py -v
```
