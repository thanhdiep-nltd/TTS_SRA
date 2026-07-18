# TÀI LIỆU THIẾT KẾ — TAM GIÁC HÓA ĐỘ KHÓ ĐỀ THI & ĐÁNH GIÁ THỰC LỰC TOÀN TRƯỜNG

**Dự án:** AI20K-075 — AI Trợ Lý Phân Tích Kết Quả Học Tập
**Tính năng:** Triangulated Exam Validity & Integrity (TEVI)
**Phiên bản:** 1.0.0 (Draft) · **Ngày:** 2026-06-27
**Trạng thái:** Thiết kế — sẵn sàng cho dev triển khai theo phase
**Tài liệu liên quan:** [RAG_design.md](RAG_design.md) (ingestion SGK) · [schema.sql](schema.sql) · [RAG_retrieval_design — knowledge_agent](../src/agents/knowledge_agent/)

> **Người đọc mục tiêu:** dev backend (FastAPI + SQLAlchemy + LangGraph) và data engineer (Airflow). Tài liệu mô tả *cái cần làm* và *vì sao*, kèm DDL/contract cụ thể. Không bắt buộc theo từng dòng — ưu tiên đúng mô hình toán & ranh giới module.

---

## 1. BÀI TOÁN & ĐỘNG LỰC

### 1.1. Vấn đề cốt lõi — vòng lặp logic của độ khó suy-từ-điểm
Hệ hiện tại đo độ khó bằng `mv_exam_difficulty`: `facility_index = AVG(điểm)/10`. Độ khó này **suy ra TỪ chính điểm số** → không thể tách **"đề khó"** khỏi **"học sinh yếu"**. `v_normalized_scores` chuẩn hóa theo TB khối (neo 7.0) chỉ là *mean-centering* → công bằng nội bộ nhưng **xóa thông tin về mức tuyệt đối**. Hệ quả: **không tự kiểm chứng được điểm số có phản ánh đúng thực lực hay không.**

### 1.2. Giải pháp — tam giác hóa 3 nguồn độc lập
Bổ sung **mỏ neo NGOÀI** = phân tích **nội dung đề** (ánh xạ vào chuẩn chương trình `curriculum_units` + thang Bloom). Kết hợp 3 nguồn:

| Nguồn | Ký hiệu | Bản chất | Phụ thuộc điểm? |
|------|---------|----------|-----------------|
| Độ khó **thực nghiệm** | **EDI** (Empirical) | phân phối điểm GK/CK | ✅ (nội sinh) |
| Độ khó **nội dung** | **CDI** (Content) | đề → chuẩn CT + Bloom (LLM/RAG) | ❌ (ngoại sinh) |
| Độ khó **khai báo** | **DDI** (Declared) | GV gán trước | ❌ (chủ quan) |

### 1.3. Mục tiêu sản phẩm
1. **Ước lượng thực lực ĐÚNG hơn**: chuẩn hóa điểm theo **CDI** (độc lập điểm) thay vì chỉ theo TB khối → phá vòng lặp.
2. **Phát hiện sớm bê bối/bất thường**: độ **phân kỳ** giữa CDI và EDI là tín hiệu (lạm phát điểm, nghi lộ đề, chấm lỏng, lỗ hổng dạy-học).
3. **Cơ sở giải trình cho BGH**: mỗi nhận định kèm bằng chứng (chuẩn CT phủ, phân bố Bloom, phân phối điểm, mức tin cậy).

### 1.4. Phạm vi
- **Trong phạm vi:** GK & CK (MIDTERM/FINAL) — vì `mv_exam_difficulty` đã gom theo khối cho 2 loại này; đề dùng chung cả khối → đủ mẫu thống kê.
- **Ngoài phạm vi (v1):** điểm TX/Miệng (đề theo lớp, mẫu nhỏ, nhiễu cao); chấm điểm item-level (DB chỉ có điểm tổng hợp mỗi cột).

---

## 2. MÔ HÌNH TOÁN

### 2.1. EDI — Empirical Difficulty Index (đã có sẵn dữ liệu)
Từ `mv_exam_difficulty` (mỗi `subject_id, semester_id, score_category, grade_id`):
```
EDI = 1 − facility_index            # cao = khó (theo kết quả làm bài)
phụ trợ: pct_below_5, stddev_score, n
```

### 2.2. CDI — Content Difficulty Index (MỚI, ngoại sinh)
Tính từ `exam_competencies` (đã có cột `weight` + `bloom_level`) sau khi pipeline phân tích nội dung điền vào:
```
CDI_bloom = Σ(weightᵢ × bloomᵢ) / Σ(weightᵢ) / 6        # chuẩn hóa 0..1 (bloom 1..6)
CDI       = clamp01( α·CDI_bloom + β·coverage_depth + γ·structural )
```
- `CDI_bloom`: trọng tâm — đề thiên về Nhớ/Hiểu (Bloom 1-2) là dễ; Vận dụng/Phân tích/Sáng tạo (4-6) là khó.
- `coverage_depth` (tùy chọn v1.1): tỉ lệ chuẩn CT bậc sâu (chuẩn "vận dụng cao") trong đề.
- `structural` (tùy chọn): tỉ trọng câu tự luận/nhiều bước vs trắc nghiệm.
- Mặc định v1: `α=1, β=0, γ=0` (chỉ Bloom) → đơn giản, mở rộng sau.

### 2.3. DDI — Declared Difficulty Index
Ánh xạ `exam_papers.difficulty`: `EASY=0.25, MEDIUM=0.50, HARD=0.75`; hoặc dùng `(difficulty_coefficient − 0.5)` (dải 0.5–1.5 → 0..1).

### 2.4. Validity & Divergence (tín hiệu cốt lõi)
```
D = EDI − CDI            # phân kỳ có dấu, dải ~[-1, 1]
```
| Tình huống | Diễn giải | Cờ |
|-----------|-----------|----|
| `D ≪ 0` (kết quả dễ trên đề khó) | điểm cao bất thường so với độ khó nội dung | 🔴 INFLATION_OR_LEAK |
| `D ≫ 0` (kết quả khó trên đề dễ) | điểm thấp dù đề không khó | 🟠 LEARNING_GAP |
| `|D|` nhỏ | điểm khớp độ khó nội dung | 🟢 VALID |

**Mức tin cậy** (chặn báo động giả): chỉ kết luận khi `n ≥ N_MIN` (vd 30) và CDI có nguồn (đề đã được phân tích, không phải default). Trọng số tin cậy `conf = f(n, có_CDI, stddev)`.

### 2.5. Ước lượng thực lực neo theo nội dung (phá vòng lặp)
Thay vì `context_adjusted_value` (neo TB khối — nội sinh), thêm **`content_adjusted_ability`** neo theo CDI:
```
ability = clamp(0..10,  raw_value + k · (CDI − 0.5) )     # đề càng khó (CDI cao) → cộng bù
```
- `k` (vd 3.0) hiệu chỉnh theo dữ liệu lịch sử. Khi CDI=0.5 (trung tính) → ability = raw.
- Đây là điểm so sánh **xuyên đề/xuyên lớp/xuyên khối** công bằng vì neo vào **độ khó nội dung độc lập**, không vào TB cohort.

---

## 3. KIẾN TRÚC & LUỒNG DỮ LIỆU

```
┌─────────────────────────────────────────────────────────────────┐
│ A. NHÁNH NỘI DUNG (offline, Airflow) — tạo CDI                   │
│                                                                  │
│  exam_papers.file_url ──▶ extract_text (WORD/PDF-text=$0;        │
│      IMAGE/scan→OCR Tesseract/Vision) ──▶ LLM phân tích:         │
│      • tách câu/phần → map vào curriculum_units (RAG gợi ý)      │
│      • gán bloom_level (1..6) + weight                           │
│      ──▶ GHI exam_competencies + exam_papers.ai_analysis         │
│      ──▶ tính & lưu CDI                                          │
└─────────────────────────────────────────────────────────────────┘
                              │ (CDI sẵn trong DB)
┌─────────────────────────────▼───────────────────────────────────┐
│ B. NHÁNH TAM GIÁC HÓA (runtime/batch) — tạo báo cáo validity     │
│                                                                  │
│  mv_exam_difficulty (EDI) ┐                                      │
│  exam_competencies  (CDI) ┼─▶ triangulation_service             │
│  exam_papers.difficulty(DDI)┘     → D, cờ, conf, ability        │
│                                   → v_exam_validity (view/MV)    │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│ C. TIÊU THỤ                                                      │
│  • Analytics endpoint /api/v1/analytics/exam-validity           │
│  • stat_agent tool get_exam_validity_report (Supervisor route)  │
│  • Dashboard BGH: bảng cờ đỏ + drill-down bằng chứng            │
└─────────────────────────────────────────────────────────────────┘
```

**Nguyên tắc:** Nhánh A (nặng OCR+LLM) **decoupled** trong `pipelines/airflow` giống ingestion SGK; nhánh B & C nằm trong `src/` (đọc DB). Tách rõ để A không chặn runtime.

---

## 4. MÔ HÌNH DỮ LIỆU

### 4.1. Tái sử dụng (đã có — KHÔNG cần tạo mới)
- `exam_papers` (difficulty, difficulty_coefficient, topics[], **ai_analysis JSONB**, file_url, file_type)
- `curriculum_units` (chuẩn CT phân cấp: code, name, parent_id)
- `exam_competencies` (**weight, bloom_level** — chính là nơi chứa CDI thô)
- `exam_column_mappings` (đề ↔ cột điểm) · `scores.exam_paper_id`
- `mv_exam_difficulty` (EDI) · `v_normalized_scores`

### 4.2. Bổ sung mới
**(a) Cột trên `exam_papers`** — lưu kết quả phân tích nội dung:
```sql
ALTER TABLE exam_papers
  ADD COLUMN content_difficulty NUMERIC(4,3),         -- CDI đã tính, 0..1 (NULL = chưa phân tích)
  ADD COLUMN content_analyzed_at TIMESTAMPTZ,
  ADD COLUMN content_source file_type_enum;           -- nguồn text: PDF-text/OCR... (truy vết)
-- ai_analysis JSONB lưu chi tiết: { bloom_dist:{1..6}, coverage:[unit_code..], notes, model, confidence }
```

**(b) View tam giác hóa `v_exam_validity`** — kết quả cho BGH:
```sql
CREATE VIEW v_exam_validity AS
SELECT
  d.subject_id, d.semester_id, d.score_category, d.grade_id,
  d.n, d.mean_score, d.stddev_score, d.pct_below_5,
  (1 - d.facility_index)                               AS edi,          -- thực nghiệm
  ep.content_difficulty                                AS cdi,          -- nội dung (NULL nếu chưa phân tích)
  CASE ep.difficulty WHEN 'EASY' THEN 0.25 WHEN 'MEDIUM' THEN 0.5
                     WHEN 'HARD' THEN 0.75 END         AS ddi,          -- khai báo
  ((1 - d.facility_index) - ep.content_difficulty)     AS divergence,   -- D = EDI - CDI
  CASE
    WHEN ep.content_difficulty IS NULL THEN 'NO_CONTENT'
    WHEN d.n < 30 THEN 'LOW_SAMPLE'
    WHEN ((1 - d.facility_index) - ep.content_difficulty) <= -0.25 THEN 'INFLATION_OR_LEAK'
    WHEN ((1 - d.facility_index) - ep.content_difficulty) >=  0.25 THEN 'LEARNING_GAP'
    ELSE 'VALID'
  END                                                  AS flag
FROM mv_exam_difficulty d
JOIN exam_column_mappings m
  ON m.subject_id=d.subject_id AND m.semester_id=d.semester_id
 AND m.score_category=d.score_category AND m.grade_id=d.grade_id
JOIN exam_papers ep ON ep.id = m.exam_paper_id;
```
> Ngưỡng `±0.25`, `n≥30` là tham số — đưa vào config để hiệu chỉnh. Có thể nâng thành **MATERIALIZED VIEW** nếu cần refresh cùng `mv_exam_difficulty`.

**(c) (Tùy chọn v1.1) Collection Qdrant `curriculum_units`** để RAG gợi ý ánh xạ đề→chuẩn:
- Embed `curriculum_units.name + description` bằng BGE-m3 (dùng lại embedding-service sidecar) → tìm chuẩn gần nhất với từng câu hỏi đề. Tách collection riêng với `edu_knowledge`.

---

## 5. NHÁNH A — PIPELINE PHÂN TÍCH NỘI DUNG ĐỀ (tạo CDI)

### 5.1. Trigger
- FastAPI `POST /api/v1/exam-papers/{id}/analyze` (ADMIN/PRINCIPAL/SUBJECT_HEAD) → gọi Airflow DAG `exam_content_analysis` với `conf={exam_paper_id}`.
- Hoặc tự động sau khi `POST /exam-papers` có `file_url` + đã `POST /scores/mappings`.

### 5.2. DAG `exam_content_analysis` (Airflow, `pipelines/airflow/dags/`)
| Task | Công nghệ | Mô tả | Lỗi/Retry |
|------|-----------|-------|-----------|
| `fetch_exam_file` | boto3/MinIO hoặc file_url | Tải file đề | retry 2 |
| `extract_text` | **Hybrid theo file_type** | WORD→python-docx; PDF có text→PyMuPDF ($0); **IMAGE/PDF-scan→OCR** (Tesseract `vie`; môn nhiều công thức→Vision Qwen). Tái dùng `edu_pipeline.pdf_extract`. | retry 2 |
| `segment_questions` | LLM/regex | Tách đề thành câu/phần + điểm từng câu (nếu có) | soft |
| `map_to_curriculum` | **RAG + LLM** | Mỗi câu → semantic search `curriculum_units` (subject+grade) gợi ý top-k → LLM chọn `unit_id` + gán `bloom_level` (1-6) + `weight` (chuẩn hóa Σ=1) | pool LLM, retry 5 |
| `compute_cdi` | Python | `CDI_bloom` (§2.2) từ kết quả map | local |
| `persist` | SQLAlchemy | UPSERT `exam_competencies`; cập nhật `exam_papers.{content_difficulty, ai_analysis, content_analyzed_at, content_source}` | retry 3 |

**LLM output (structured)** cho `map_to_curriculum` — Pydantic schema:
```python
class MappedUnit(BaseModel):
    unit_code: str          # khớp curriculum_units.code
    weight: float           # 0..1, Σ≈1
    bloom_level: int        # 1..6
    evidence: str           # trích câu hỏi/đoạn đề làm bằng chứng (giải trình)
class ExamContentAnalysis(BaseModel):
    units: list[MappedUnit]
    bloom_distribution: dict[int, float]   # {1:0.1, 2:0.3, ...}
    coverage_note: str
    estimated_cdi: float
```

### 5.3. Xử lý "không có file đề"
- Nếu `file_url` NULL nhưng GV đã nhập `topics[]` + `difficulty` + (lý tưởng) `exam_competencies` thủ công → vẫn tính được CDI từ `exam_competencies`. Pipeline chỉ là cách **tự động điền** `exam_competencies`; nhập tay vẫn hợp lệ.
- Nếu hoàn toàn không có nội dung → `content_difficulty` NULL → `flag='NO_CONTENT'` (báo BGH "chưa đủ cơ sở nội dung, chỉ có EDI tương đối").

---

## 6. NHÁNH B — DỊCH VỤ TAM GIÁC HÓA (`src/`)

### 6.1. Module `src/services/exam_validity.py`
- `compute_validity(subject_id, semester_id, grade_id, score_category)` → đọc `v_exam_validity` → trả DTO {edi, cdi, ddi, divergence, flag, conf, evidence}.
- `school_overview(school_id, semester_id)` → tổng hợp toàn trường: đếm cờ theo loại, danh sách đề "đáng ngờ" xếp theo `|divergence|×conf`.
- `content_adjusted_ranking(grade_id, semester_id, subject_id)` → xếp hạng lớp theo `content_adjusted_ability` (§2.5) — so sánh công bằng theo độ khó nội dung.

### 6.2. Repository/Schema
- `src/schemas/exam_validity.py`: `ExamValidityRead`, `SchoolValidityOverview`, `AnomalyFlag`.
- Tôn trọng tầng: schemas → repositories (đọc view) → services (logic cờ/ngưỡng) → api.
- **RBAC:** chỉ ADMIN/PRINCIPAL/SUBJECT_HEAD xem báo cáo validity toàn trường (nhạy cảm — liên quan "bê bối"). Lọc theo `school_id`.

---

## 7. PHÁT HIỆN BÊ BỐI / BẤT THƯỜNG (anomaly rules)

Ngoài cờ cơ bản từ `divergence`, bổ sung luật (chạy ở service, có thể lưu `audit_logs`):

| Mã | Điều kiện | Nghi vấn |
|----|-----------|----------|
| `INFLATION` | CDI cao + EDI thấp + `stddev` thấp + `pct_below_5≈0` | Chấm lỏng / nâng điểm đại trà |
| `LEAK` | EDI thấp đột biến so với **lịch sử cùng môn/khối** + phân phối dồn sát điểm tối đa | Nghi lộ đề |
| `TEACHER_OUTLIER` | Một lớp có EDI lệch mạnh khỏi các lớp cùng khối/cùng đề (cùng GV chấm) | GV chấm bất thường |
| `LEARNING_GAP` | CDI thấp/TB + EDI cao + `pct_below_5` cao | Lỗ hổng dạy-học thật |
| `MAPPING_ERROR` | `|divergence|` cực lớn + nội dung lệch hẳn môn/khối | Map sai đề ↔ cột điểm |

> v1 làm `INFLATION`, `LEARNING_GAP`, `NO_CONTENT`, `LOW_SAMPLE` (đủ dữ liệu sẵn). `LEAK`/`TEACHER_OUTLIER` cần so sánh lịch sử + cấp lớp → v1.1.

---

## 8. TÍCH HỢP MULTI-AGENT

### 8.1. Tool mới cho `stat_agent` (KHÔNG phải knowledge_agent)
`src/agents/stat_agent/tools.py`:
```python
@tool
def get_exam_validity_report(subject: str, grade_level: int, year: int, semester: int) -> str:
    """Đối chiếu độ khó NỘI DUNG đề (Bloom/chuẩn CT) vs độ khó THỰC NGHIỆM (điểm) để
    đánh giá điểm có phản ánh đúng thực lực + phát hiện bất thường (lạm phát/lỗ hổng).
    Dùng cho câu hỏi về tính TIN CẬY của điểm, độ khó đề, nghi vấn bê bối điểm số."""
```
- Trả bảng: môn/khối, EDI, CDI, DDI, divergence, cờ, mức tin cậy, bằng chứng (Bloom dist + phân phối điểm).

### 8.2. Cập nhật Supervisor (đồng bộ 4 chỗ — xem [graph.py](../src/agents/graph.py))
- `RouterDecision` mô tả + `SUPERVISOR_PROMPT`: thêm năng lực "đánh giá độ tin cậy điểm / độ khó đề / nghi vấn bất thường" vào `stat_agent` (không tạo agent mới — đây là phân tích thống kê).
- **Phối hợp đa agent**: câu hỏi "đề Toán 8 HK1 có đáng tin không, vì sao khó?" → Supervisor có thể gọi `stat_agent` (validity) **và** `knowledge_agent` (giải thích chuẩn CT/chủ đề trong đề) rồi tổng hợp. Đây là chỗ knowledge_agent *bổ trợ* (giải thích nội dung chuẩn CT), không phải nơi tính độ khó.

### 8.3. Phân vai rõ ràng
| Việc | Agent | Lý do |
|------|-------|-------|
| Tính EDI/CDI/divergence, cờ bất thường | **stat_agent** (DB analytics) | dữ liệu có cấu trúc |
| Giải thích "chuẩn CT này là gì", nội dung chủ đề | **knowledge_agent** (RAG SGK) | nội dung kiến thức |
| Tra điểm thô 1 HS/lớp | data_agent | tra cứu |
| Truy vấn tùy biến tương quan | sql_agent | SQL động |

---

## 9. API CONTRACT (prefix `/api/v1`)

| Method | Endpoint | Quyền | Mô tả |
|--------|----------|-------|-------|
| POST | `/exam-papers/{id}/analyze` | ADMIN/PRINCIPAL/SUBJECT_HEAD | Trigger pipeline nội dung (DAG) |
| GET | `/exam-papers/{id}/content-analysis` | đọc theo RLS | Kết quả CDI + Bloom + chuẩn CT phủ |
| GET | `/analytics/exam-validity` | ADMIN/PRINCIPAL/SUBJECT_HEAD | Bảng validity theo môn/khối/HK (filter) |
| GET | `/analytics/exam-validity/overview` | ADMIN/PRINCIPAL | Tổng hợp toàn trường + danh sách cờ đỏ |
| GET | `/analytics/content-adjusted-ranking` | ADMIN/PRINCIPAL | Xếp hạng lớp theo thực lực neo-nội-dung |

---

## 10. KẾ HOẠCH TRIỂN KHAI THEO PHASE

**Phase 0 — Nền tảng dữ liệu (1-2 ngày)**
- Migration: cột mới `exam_papers.content_*`; tạo `v_exam_validity`.
- Seed `curriculum_units` mẫu cho 1-2 môn/khối (vd Toán 8) để test.
- Nhập tay `exam_competencies` cho vài đề mẫu → kiểm chứng công thức CDI & `v_exam_validity` chạy đúng **trước khi** làm pipeline.

**Phase 1 — Tam giác hóa + tiêu thụ (cốt lõi, dùng được ngay)**
- `services/exam_validity.py` + schemas + repositories + 3 endpoint validity.
- Tool `stat_agent.get_exam_validity_report` + cập nhật Supervisor.
- Test offline (mock DB) cho công thức + cờ.
- ✅ Mốc: BGH hỏi "đề nào đáng ngờ?" → trả bảng cờ (với đề đã có exam_competencies).

**Phase 2 — Pipeline tự động phân tích nội dung (nặng)**
- DAG `exam_content_analysis` (extract hybrid + OCR + LLM map curriculum/Bloom).
- (Tùy chọn) index `curriculum_units` lên Qdrant để RAG gợi ý ánh xạ.
- ✅ Mốc: upload đề (Word/PDF/ảnh) → tự sinh `exam_competencies` + CDI.

**Phase 3 — Phát hiện bê bối nâng cao + Dashboard**
- Luật `LEAK`, `TEACHER_OUTLIER` (so sánh lịch sử + cấp lớp/GV).
- Dashboard BGH: bản đồ nhiệt cờ đỏ + drill-down bằng chứng (Bloom dist, phân phối điểm, chuẩn CT phủ).

---

## 11. RỦI RO & LƯU Ý

| Rủi ro | Giảm thiểu |
|--------|-----------|
| **LLM map sai chuẩn CT / Bloom** | Bắt buộc `evidence` (trích câu) để người kiểm; cho GV duyệt/sửa `exam_competencies`; lưu `model`+`confidence` trong ai_analysis |
| **CDI default che giấu thiếu dữ liệu** | KHÔNG đặt CDI mặc định — để NULL → cờ `NO_CONTENT` minh bạch |
| **Báo động giả** (mẫu nhỏ) | Ngưỡng `n≥30` + trọng số tin cậy; chỉ cảnh báo, KHÔNG kết tội tự động |
| **Nhạy cảm "bê bối"** | Là **tín hiệu để rà soát**, không phải kết luận; RBAC chặt; ghi `audit_logs`; ngôn ngữ báo cáo trung lập ("cần rà soát") |
| **OCR nhiễu công thức** | Toán/KHTN dùng Vision Qwen (LaTeX) như pipeline SGK; cho phép GV chỉnh tay |
| **`curriculum_units` chưa đầy đủ** | Phase 0 seed dần theo môn ưu tiên; CDI chỉ tính trên phần đã map |
| **OCR chỉ cần cho ảnh/scan** | WORD/PDF-text trích thẳng ($0); xem mục 5.2 |

---

## 12. TIÊU CHÍ HOÀN THÀNH (Definition of Done)
- [ ] `v_exam_validity` trả đúng EDI/CDI/DDI/divergence/flag trên dữ liệu seed.
- [ ] `content_adjusted_ability` khác biệt rõ với `context_adjusted_value` khi CDI≠0.5 (chứng minh phá vòng lặp).
- [ ] `stat_agent` trả báo cáo validity + Supervisor định tuyến đúng câu hỏi "độ tin cậy điểm".
- [ ] Pipeline phân tích 1 đề Word + 1 đề scan → sinh `exam_competencies` + CDI hợp lý (có evidence).
- [ ] Phát hiện đúng 1 ca INFLATION và 1 ca LEARNING_GAP trên dữ liệu dựng sẵn.
- [ ] Test offline pass; ruff sạch; RBAC chặn đúng vai.

---

## 13. PHỤ LỤC — VÍ DỤ MINH HỌA

**Đề Toán 8 HK1, Khối 8:**
- Nội dung: 70% Bloom 1-2 (nhớ/hiểu), 30% Bloom 3 → `CDI_bloom = (0.7·1.5 + 0.3·3)/6 ≈ 0.325` → đề **dễ-trung bình**.
- Điểm: mean=4.8 → `facility=0.48` → `EDI=0.52` → kết quả **khó**.
- `D = 0.52 − 0.325 = +0.195` < 0.25 nhưng dương đáng kể, `pct_below_5` cao → cờ chớm **LEARNING_GAP**: *đề không khó nhưng cả khối điểm thấp → rà soát dạy-học môn Toán khối 8*, KHÔNG phải tại đề.
- Ngược lại nếu mean=9.2 (`EDI=0.08`) trên cùng đề → `D=−0.245` → **INFLATION_OR_LEAK**: điểm cao bất thường so với độ khó nội dung → rà soát chấm/đề.

→ Cùng một bộ điểm, **chỉ khi có CDI mới phân biệt được "trò yếu" vs "đề/chấm có vấn đề"** — đó là giá trị cốt lõi của tam giác hóa.
