# Kiến trúc: Độ thành thạo theo chương (Mastery) từ LMS Item-Level + Đối soát chống gian lận

> Trạng thái: **BẢN THIẾT KẾ / BẢN KẾ HOẠCH** (đã duyệt plan-approval, chưa triển khai code).
> Phạm vi: thiết kế kiến trúc + DDL đề xuất + thuật toán + bản kế hoạch phân rã.
> Bản này là nền để khi chuyển sang giai đoạn code (GĐ-A/GĐ-B) triển khai.

> ✅ **CẬP NHẬT TRIỂN KHAI (GĐ-A + GĐ-B đã code xong):**
> - DDL 3 bảng đã thêm vào `docs_vsf/schemas/merged/score_focused_schema.sql` + `src/db/mini_migrations.py` (`CREATE TABLE IF NOT EXISTS`, idempotent, áp lúc startup).
> - `src/services/item_mastery.py`: raw mastery bloom-weighted, coverage penalty, đối soát bất cân xứng (5 mức có vùng đệm), INSUFFICIENT/INSUFFICIENT_STUDENT, fallback EXAM.
> - `src/services/lms_item_ingest.py`: validate_row, resolve_integrity (đoán mò), resolve_mastery (mapping 3 tầng), deduplicate_rows, build_best_attempt_flags.
> - `src/schemas/knowledge_gap.py` + `src/api/v1/knowledge_gap.py`: đọc `student_unit_mastery` trước (LMS item-level ưu tiên), fallback `compute_unit_mastery` khi chưa có; xuất confidence/coverage/integrity_status.
> - Frontend `/knowledge-gaps`: badge độ tin cậy (HIGH/MEDIUM/LOW/INSUFFICIENT) + badge đối soát (SUSPECTED_CHEATING/LOW_ENGAGEMENT/LMS_ONLY) + coverage % + thông báo "chưa đủ dữ liệu".
> - Tests: `tests/test_item_mastery.py` (14) + `tests/test_lms_item_ingest.py` (11) — tất cả pass. **Chưa làm:** GĐ-C (tự luận LLM), GĐ-D (cây thành thạo trực quan hoàn chỉnh), adapter nối DB thật của đối tác (`lms_item_ingest` hiện là hàm thuần, mapping_fn/UnitMapper do caller cấp khi có pipeline thật).

---

## 1. Bối cảnh & bài toán

### 1.1 Vấn đề gốc rễ
Hệ thống SRA chỉ có **điểm tổng** (vd 6.0/10) cho cả một đề kiểm tra nhiều chương. Đây là bài toán **ill-posed / underdetermined**:

- 6 chương = 6 ẩn `S_1..S_6`, điểm tổng là 1 phương trình `Σ w_i·S_i = 0.6` → vô số nghiệm thoả mãn.
- Thuật toán hiện tại (`compute_unit_mastery`, `src/services/knowledge_gap.py`) **áp giả định "học đều, chỉ lệch theo Bloom"** → báo mọi chương ≈ 0.6:
  - **False Positive**: báo hổng cả chương em giỏi thật.
  - **False Negative**: bỏ lọt chương em mất gốc hoàn toàn.

### 1.2 Hướng giải quyết đã chốt
Chuyển từ dữ liệu **vô hướng** sang **Item-Response Matrix** `Y_{student × question} ∈ {0,1}` (phân giải cao) để định vị mastery theo từng chương. Vì **không xây lại hệ LMS/chấm bài**, dữ liệu item-level được **đổ từ đối tác**.

- **LMS online** = nguồn phân giải cao nhưng dễ bị gian lận (đoán mò, nhờ người làm, dùng AI).
- **Điểm thi trên lớp** (giám thị) = nguồn "thực lực" gần đúng → dùng **đối soát chống gian lận** và hạ nhiệt độ tin cậy.

### 1.3 Quyết định phạm vi (đã thống nhất)
- Nguồn item-level: **đối tác đổ thêm** (thiết kế schema mở rộng; không xây hệ tạo bài/chấm).
- Đơn vị đo: **`public.curriculum_units` (cây SGK: Chương › Bài)** làm Single Source of Truth.
- Phần **trắc nghiệm (MCQ)** trước; **tự luận (ESSAY)** dùng LLM quét để **sau** (không trong scope đầu).
- Đợt hiện tại: **chỉ thiết kế kiến trúc + DDL đề xuất + bản kế hoạch** (chưa code).

---

## 2. Xác minh dữ liệu hiện trạng (grounding trong repo)

### 2.1 Schema đối tác (`docs_vsf/schemas/new/School Online Schema.csv`) — xác nhận
- `fact_so_assignment_grade` (assignment_id, student_code, final_grade) — **chỉ điểm TỔNG bài**, không có từng câu.
- `dim_so_assignment` (course_id, **course_lesson_id**, **el_assignment_id**, gradebook_type_item_id, type, max_grade) → nối assignment vào **bài học / hệ e-learning**.
- `stg_so_strand_path` (strand_id, parent_id, path, id_path, subject_id) — **cây strand/chương của đối tác** (dùng để map hỗ trợ).
- `fact_so_subject_mastery` (score_type, final_grade, percent_target_min/max/normal/exceed) — đối tác đã có khái niệm mastery môn (ưu tiên thấp, cần xác nhận ngữ nghĩa).
- **KHÔNG có bảng item-response nào** (không `is_correct`, `chosen_option`, `question_id` bài trắc nghiệm).

### 2.2 Schema hiện tại (`docs_vsf/schemas/merged/score_focused_schema.sql`) — xác nhận
- `public.exam_competencies` (exam_paper_id→unit_id, weight, bloom_level) — đề → unit.
- `public.assignment_competencies` (assignment_id→unit_id, weight, bloom_level) — bài LMS → unit SGK (chìa khóa; đã có).
- `public.curriculum_units` (parent_id, summary, keywords) — cây SGK.
- `s360.fact_gradebooks` (điểm tổng) + `s360.fact_gradebooks_moet` (điểm theo `gradebook_type_item_id` = theo đầu cột thi) + `s360.dim_exam_moet` (danh mục đầu điểm, `coefficient`).
- `public.student_knowledge_gaps` (student_code, subject_id, unit_id, gap_score, `evidence_source`, `evidence_detail` JSONB) — **đã có sẵn**, dùng để truyền kết quả lỗ hổng.

### 2.3 Nghiệp vụ hiện có (tái dùng)
- `src/services/knowledge_gap.py` — `compute_unit_mastery`, `aggregate_class_gaps`, `_BLOOM_DIFFICULTY` `{1:0.5,2:0.7,3:1.0,4:1.3,5:1.6,6:2.0}`, `GAP_MASTERY_THRESHOLD=0.6`.
- `src/ews/lms_evidence.py` — phân loại hành vi LMS: SKIPPED/RUSHED/OFF_TASK/EFFORT_BUT_LOST/WEAK_CHAPTER/MISSING_IN_EXAM (dùng phát hiện nhiễu/gian lận).
- `src/services/question_classify.py` + `src/api/v1/question_classify.py` — **Kiểm tra câu hỏi**: tách câu → chương + bloom (đang chạy ở `/exam-difficulty`), dùng làm **Tầng 3 (AI fallback)** của mapping.

### 2.4 Kết luận
- Không item-level trong cả 2 DB → cần **schema mở rộng** để đón dữ liệu mới.
- Nguồn nối (course_lesson_id, strand, assignment_competencies) đã sẵn → mapping khả thi, **không cần xây hệ chấm**.

---

## 3. Kiến trúc tổng thể

```
[Đối tác đổ item-response]            (el / view / csv qua adapter)
        │
        ▼
[Mapping fallback 3 tầng]             (Direct → Strand → AI Classifier)
        ▼
[lms_question_bank]                   (cat: question_id, assignment_id, subject_id, unit_id, bloom, type)
        │
        ▼
[lms_question_response]               (fact: is_correct, score, response_time, attempt_number, is_best_attempt, integrity_flag)
        │
        ▼
[Lọc nhiễu theo lms_evidence]         (gắn integrity_flag 0/1; bỏ hoặc đánh cờ)
        │
        ▼
[Raw mastery theo chương (Bloom-weighted) + Coverage penalty]   → item_mastery.py
        │
        ▼
[Đối soát bất cân xứng LMS ↔ điểm trên lớp]  → adjusted_mastery + confidence + integrity_status
        │
        ▼
[student_unit_mastery]                 (bảng tổng hợp; nối student_knowledge_gaps)
        ▼
[Cây thành thạo theo chương]          (API /knowledge-gaps + frontend)
```

---

## 4. Schema mở rộng (DDL đề xuất)

### 4.1 `public.lms_question_bank` — danh mục câu hỏi (có `subject_id` lọc nhanh)
```sql
CREATE TABLE public.lms_question_bank (
    question_id   BIGINT PRIMARY KEY,          -- id hệ đối tác
    assignment_id BIGINT NOT NULL,
    so_school_id  INTEGER NOT NULL,            -- tenant isolation
    subject_id    INTEGER NOT NULL,            -- lọc theo môn, không cần JOIN qua curriculum_units
    unit_id       BIGINT REFERENCES public.curriculum_units(id), -- NULL nếu chưa map
    bloom_level   SMALLINT DEFAULT 3,          -- 1..6
    question_type VARCHAR(20) DEFAULT 'MCQ',   -- MCQ | ESSAY
    item_weight   NUMERIC(5,2),
    is_active     INTEGER DEFAULT 1,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_lqb_subject ON public.lms_question_bank(subject_id, unit_id);
```

### 4.2 `public.lms_question_response` — Staging Fact (cốt lõi)
```sql
CREATE TABLE public.lms_question_response (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id INTEGER NOT NULL,
    student_code VARCHAR(50) NOT NULL,
    assignment_id BIGINT NOT NULL,
    question_id  BIGINT NOT NULL,
    unit_id      BIGINT REFERENCES public.curriculum_units(id),  -- denormalized để query nhanh
    bloom_level  SMALLINT NOT NULL DEFAULT 3,
    question_type VARCHAR(20) DEFAULT 'MCQ',
    attempt_number SMALLINT DEFAULT 1,         -- lượt làm thứ mấy (multi-attempt)
    is_best_attempt BOOLEAN DEFAULT TRUE,      -- lần tốt nhất để tính mastery
    is_correct   BOOLEAN NOT NULL,
    score_received NUMERIC(5,2) NOT NULL,
    max_score    NUMERIC(5,2) NOT NULL,
    response_time_seconds INTEGER,             -- phát hiện đoán mò siêu tốc (lms_evidence)
    response_payload JSONB,                    -- {'chosen_option':'B', 'text':...} (ESSAY để sau)
    integrity_flag SMALLINT DEFAULT 0,         -- 0 Normal | 1 Suspected | 2 Flagged
    attempt_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_lqr_calc ON public.lms_question_response(student_code, unit_id, is_best_attempt, integrity_flag);
CREATE UNIQUE INDEX uq_lqr_attempt ON public.lms_question_response(student_code, assignment_id, question_id, attempt_number);
```

### 4.3 `public.student_unit_mastery` — tổng hợp Mastery + đối soát
```sql
CREATE TABLE public.student_unit_mastery (
    student_code     VARCHAR(50) NOT NULL,
    subject_id       INTEGER NOT NULL,
    so_school_id     INTEGER NOT NULL,
    unit_id          BIGINT NOT NULL REFERENCES public.curriculum_units(id),
    semester_index   INTEGER NOT NULL,
    raw_mastery      NUMERIC(5,4),
    n_items          INT DEFAULT 0,
    n_correct        INT DEFAULT 0,
    coverage         NUMERIC(4,3) DEFAULT 0,
    lm_weight        NUMERIC(3,2),             -- w_lms
    exam_weight      NUMERIC(3,2),             -- w_exam
    adjusted_mastery NUMERIC(5,4),
    confidence       SMALLINT DEFAULT 1,       -- 1 LOW | 2 MEDIUM | 3 HIGH
    evidence_source  VARCHAR(20),              -- LMS | HYBRID | EXAM | PRIOR | INSUFFICIENT
    integrity_status VARCHAR(20),              -- OK | SUSPECTED_CHEATING | LOW_ENGAGEMENT | FLAGGED
    evidence_detail  JSONB,
    detected_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_sum_mastery UNIQUE (so_school_id, student_code, subject_id, unit_id, semester_index)
);
```
> Nối với `public.student_knowledge_gaps` đã có (cùng `unit_id`).

#### 4.3.1 Cách áp DDL (quy trình dev — KHÔNG dùng Alembic)
- Dữ liệu đang ở môi trường **dev** → **không dùng Alembic migration**.
- Các bảng mới được thêm thẳng vào `docs_vsf/schemas/merged/score_focused_schema.sql` (nguồn schema duy nhất).
- Đồng thời đăng ký câu `CREATE TABLE IF NOT EXISTS` (hoặc `ALTER ... IF NOT EXISTS`) vào **`src/db/mini_migrations.py`** (`_MINI_MIGRATIONS`) để `apply_mini_migrations` chạy lúc startup (`src/main.py` lifespan) áp lên DB dev một cách **idempotent** — câu nào lỗi chỉ qua 1 lần, không crash.
- Không khởi tạo gì thêm; mỗi câu bọc try/except theo đúng mẫu `mini_migrations.py` hiện có.

### 4.4 Ghi chú về `student_knowledge_gaps`
- Giữ nguyên bảng lỗ hổng hiện có; kết quả cuối từ `student_unit_mastery` được xem là nguồn xuất lỗ hổng.
- Thêm `integrity_status`/`evidence_source` đã có sẵn để truyền trạng thái gian lận/lười.

---

## 5. Thuật toán (hàm thuần — đặt `src/services/item_mastery.py`)

### 5.1 Raw mastery Bloom-weighted + Coverage penalty
```python
_bloom = {1:0.5, 2:0.7, 3:1.0, 4:1.3, 5:1.6, 6:2.0}   # tái dùng knowledge_gap._BLOOM_DIFFICULTY

raw_u = (Σ over items j∈u, is_best_attempt=TRUE, integrity_flag=0)
        Σ( score_received_j × _bloom[j.bloom_level] ) / Σ( max_score_j × _bloom[j.bloom_level] )

coverage_u = min(1.0, n_items_u / N_MIN)     # N_MIN = 5 (tham số khởi tạo)
confidence = LOW(1) nếu coverage_u < 0.6 hoặc n_items_u == 0
```

### 5.2 Đối soát bất cân xứng (Asymmetric Integrity Calibration) — có vùng đệm
`exam_mastery_u` = `compute_unit_mastery(...)` của `exam_competencies` (điểm trên lớp, giám thị).
`Δ_u = raw_mastery_u − exam_mastery_u`:

| Điều kiện `Δ` | w_lms | w_exam | Confidence | integrity_status |
|---|---|---|---|---|
| `|Δ| ≤ 0.15` (khớp chặt) | 0.8 | 0.2 | HIGH (3) | OK |
| `0.15 < |Δ| ≤ 0.30` (lệch nhẹ — vùng đệm) | 0.6 | 0.4 | MEDIUM (2) | OK |
| `Δ > +0.30` (LMS ≫ thi → nghi gian lận) | 0.2 | 0.8 | LOW (1) | SUSPECTED_CHEATING |
| `Δ < −0.30` (LMS ≪ thi → lười/kém tham gia) | 0.3 | 0.7 | MEDIUM (2) | LOW_ENGAGEMENT |
| Không có exam (fallback) | 1.0 (raw) | 0.0 | LOW | LMS-only |

`adjusted_mastery_u = w_lms·raw_u + w_exam·exam_mastery_u`
- **Bản chất khác nhau:** LMS cao bất thường = nghi gian lận (bias về thi, LOW); thi cao hơn LMS = cảnh báo thái độ học (không phạt gian lận, chỉ ưu tiên thi).

### 5.3 Cơ chế "chưa đủ dữ liệu" (INSUFFICIENT)
Phân biệt rõ 3 trạng thái để UI/AI báo đúng, **không vẽ giá trị 0 gây hiểu nhầm "student yếu"**:
- **`INSUFFICIENT`** — `n_items_u == 0` hoặc `coverage_u < 0.6` → báo "Chưa đủ dữ liệu về chương này" (confidence thấp nhất).
- **`INSUFFICIENT_STUDENT`** — học sinh chưa có item nào trên môn/kỳ (mọi `n_items=0`) → báo "Chưa đủ dữ liệu để đánh giá học sinh này", **không liệt kê gaps**.
- **full** — có đủ câu + đối soát → báo mastery + confidence bình thường.
- UI: badge/dòng rose cho `INSUFFICIENT`/`INSUFFICIENT_STUDENT` thay vì vẽ 0.

### 5.4 Multi-attempt handling
- Lưu toàn bộ attempt trong fact; chỉ tính mastery trên `is_best_attempt=TRUE` (lịch sử giữ để theo dõi tiến bộ — feature sau).
- **Logic `is_best_attempt` trong Ingestion (pro-tip):** khi nạp attempt `k` của (student, assignment, question):
  - `score_k > score_best` → trong **một giao dịch**: `UPDATE ... SET is_best_attempt=FALSE WHERE ... is_best_attempt=TRUE`, rồi INSERT/UPDATE attempt `k` với `TRUE`.
  - `score_k ≤ score_best` → INSERT attempt `k` với `FALSE`.

### 5.5 Fallback EXAM
- Không có item-response → quay về `compute_unit_mastery` hiện tại (`evidence_source='EXAM'`, `confidence=LOW`) — **giữ hành vi cũ 100%, không crash**.

---

## 6. Pipeline Ingestion & Mapping fallback 3 tầng

Khi đối tác đẩy item chưa có `unit_id`/`bloom_level`, giải quyết theo thứ tự:
1. **Tầng 1 — Direct Mapping**: từ `public.assignment_competencies` hoặc `dim_so_assignment.course_lesson_id`.
2. **Tầng 2 — Strand Mapping**: map `stg_so_strand_path` → `curriculum_units` (strand làm cầu nối).
3. **Tầng 3 — AI Classifier**: gọi `src/services/question_classify.py` (tái dùng pipeline /exam-difficulty) để LLM gán `unit_id` + `bloom_level`.
- item không map được → `unit_id=NULL`, **không tính**, log để xử lý sau.
- Adapter: `src/services/lms_item_ingest.py` nhận view/csv → validate → ghi 3 bảng → chạy mapping hierarchy.

---

## 7. API & DTO

- `src/schemas/knowledge_gap.py`: `KnowledgeGapItem` bổ sung `confidence`, `coverage`, `integrity_status`; `evidence_source` thêm nhãn `INSUFFICIENT`/`INSUFFICIENT_STUDENT`.
- `src/api/v1/knowledge_gap.py`: đọc `student_unit_mastery` trước, fallback `compute_unit_mastery` khi trống.
- (Sau) `GET /knowledge-gaps/mastery-tree` → cây chương kèm mastery/confidence/coverage/integrity + marker "chưa đủ dữ liệu".

---

## 8. Phân rã triển khai (để chuyển sang code)

- **GĐ-A**: DDL 3 bảng + migration (SQL + `mini_migrations.py`/Alembic) + `lms_item_ingest.py` (mapping 3 tầng + logic `is_best_attempt` transaction).
- **GĐ-B**: `src/services/item_mastery.py` (mục 5) + nối `src/ews/lms_evidence.py` gắn `integrity_flag`/`response_time` + cập nhật `knowledge_gap.py`/router/schema.
- **GĐ-C** (sau): tự luận — `question_type='ESSAY'`, dùng `response_payload` + `question_classify` + LLM chấm/mastery theo chương.
- **GĐ-D**: frontend `/knowledge-gaps` — cây thành thạo theo chương, badge confidence/coverage/integrity, thông báo "chưa đủ dữ liệu".

---

## 9. Thử nghiệm (khâu khi code)

- `lms_item_ingest`: mapping 3 tầng; logic `is_best_attempt` khi điểm mới cao hơn/thấp hơn; duplicate attempt bị unique index chặn.
- `item_mastery`: bloom-weighted raw; coverage penalty; đối soát 5 trường hợp (có vùng đệm); multi-attempt chọn best; `INSUFFICIENT`/`INSUFFICIENT_STUDENT`; fallback EXAM.
- API: override `get_db`/`get_current_user`; student & class trả mastery/confidence/integrity + marker chưa đủ dữ liệu.
- Seed script dữ liệu mẫu giả lập nộp bài LMS để test blend/confidence trước khi nối frontend.

---

## 10. Edge cases & failure modes

- Chưa item-response → fallback EXAM (không đổi hành vi).
- Coverage thấp/0 câu → `INSUFFICIENT`, không khẳng định mastery.
- LMS nhiễu → `integrity_flag` lọc; `SUSPECTED_CHEATING` bias về thi.
- Câu chưa map → NULL, không tính, log.
- Trùng attempt → unique index `uq_lqr_attempt` chặn; `is_best_attempt` do transaction quản lý.
- `max_score=0` → guard chia 0.
- Multi-tenant → `so_school_id` trong mọi query (quyền trường).

---

## 11. Giới hạn & quyết định chờ dữ liệu

- **Chưa code** (đợt này thiết kế + DDL đề xuất).
- Dữ liệu đối tác còn là giả định → **kiểm chứng 1 lần**: mẫu item-response + API hệ EL + ngữ nghĩa `fact_so_subject_mastery` để chốt shape/dữ liệu/format.
- `strand` chỉ dùng map hỗ trợ (chuẩn đo = `curriculum_units`).
- Trọng số blend + `N_MIN=5` + vùng đệm `0.15/0.30` là **tham số khởi tạo**, cần data thật để tinh chỉnh.
- Tự luận (LLM quét) để sau; phần đầu chỉ trắc nghiệm.

---

## 12. Giả định

- Đối tác cung cấp pipeline item-level (MCQ: question_id, is_correct hoặc chấm được điểm câu) — không cần xây hệ chấm.
- `curriculum_units` là chuẩn "chương" duy nhất (dùng chung với TEVI/Kiểm tra câu hỏi).
- Điểm trên lớp đáng tin gấp phần hơn LMS online → đối soát hợp lệ.
- Ngôn ngữ UI/comment tiếng Việt; tuân thủ ruff + style frontend hiện có.