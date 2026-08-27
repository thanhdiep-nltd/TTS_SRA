# KẾ HOẠCH TRIỂN KHAI — Hệ thống Phân tích Độ khó Đề + EWS Giải trình bằng chứng LMS + Phát hiện Lỗ hổng Kiến thức + Dự đoán Pass/Fail

> Ngày: 2026-08-15 · Dự án: TTS_SRA (SRA - Student Risk Alert)
> Mục tiêu: Biến dữ liệu giáo trình (SGK upload + giáo án) + đề thi (trên lớp & LMS) thành **phân tích độ khó đề**, **EWS giải trình được nguyên nhân học tệ**, **lỗ hổng kiến thức của học sinh**, và **dự đoán số học sinh trượt/pass đề cuối kỳ**.

---

## PHẦN A — KẾT QUẢ KHẢO SÁT HIỆN TRẠNG (đã dùng memory + code-review-graph + đọc code thật)

### A1. Đã có sẵn, tái sử dụng được

| Thành phần | Đường dẫn | Đã làm gì |
|------------|-----------|-----------|
| **TEVI - Tam giác hóa độ khó đề** | `docs/exam_triangulation_design.md` + `docs/exam_triangulation_implementation_summary.md` | Tính EDI (thực nghiệm từ điểm), CDI (nội dung từ Bloom + LLM + RAG SGK), DDI (GV khai báo), divergence, cờ `INFLATION_OR_LEAK`/`LEARNING_GAP`. Đã có migration + view `v_exam_validity` + 3 endpoint + seed demo 2 case. |
| **Pipeline CDI tự động** | `src/services/content_difficulty.py` | OCR/trích text đề → LLM `classify_competencies` gán `(topic, bloom_level, weight, unit_code, excerpt)` → neo vào `curriculum_units` (constrained) → RAG SGK lấy `evidence` → ghi `exam_competencies` + `exam_papers.content_difficulty` + `ai_analysis`. |
| **Exam validity service** | `src/services/exam_validity.py` | Đọc `v_exam_validity`, tính confidence, xếp hạng `content_adjusted_ability`. |
| **EWS pipeline** | `src/ews/*` (feature_extractor, inference_service, pipeline_runner, llm_forecasting, job_worker) | CatBoost `v2_ensemble` 4 trụ cột (Score/LMS/Attendance/Behavior) + SHAP + LLM forecasting. Đã có `llm_narrative_summary` + `llm_forecast_trend` + `llm_recommended_actions`. |
| **EWS API + RBAC** | `src/api/v1/ews.py` | 8 endpoint (`/ews/meta, /overview, /predictions, /raw, /filters, /golden-set, /subject-drilldown`, + re-run LLM). `/ews/raw` đã trả raw LMS (bài nào nộp/chưa, điểm). |
| **RAG SGK** | `src/services/retrieval.py` + Qdrant | `search_textbook(query, mon, lop)` → khối 6-9, 9 môn, threshold 0.45. |

### A2. Lỗ hổng dữ liệu & năng lực cần xây mới (GAP)

1. **LMS thiếu dữ liệu hành vi làm bài**: `s360.fact_so_assignment_grade` hiện chỉ có `final_grade`. KHÔNG có `time_spent / attempts / submitted_at / started_at` → không thể chứng minh "nỗ lực làm lâu", "học qua loa làm nhanh".
2. **Chưa map LMS vào chuẩn chương trình**: `dim_so_assignment` không liên kết `curriculum_units`. Không thể biết bài LMS thuộc "chương A/B" → không thể nói "học tệ chương A".
3. **Chưa có Knowledge Gap detection**: chưa có module "soi từng unit theo điểm từng câu".
4. **EWS explainability chưa dùng LMS làm bằng chứng**: `llm_narrative_summary` chỉ xoay quanh biến cố gia đình + bệnh lý, chưa đưa bằng chứng LMS ("học tệ chương A", "làm qua loa", "nỗ lực nhưng không hiểu").
5. **Chưa có Pass/Fail prediction** cho đề cuối kỳ.
6. **Chưa xử lý "cột điểm không có đề"**: file đề không đính kèm → cần con đường khác (LMS + RAG SGK + học bạ).
7. **Đồng nhất PK về BIGINT (KHÔNG bridge)**: hiện `public` (`exam_papers`, `curriculum_units`, `exam_competencies`, `subjects`) còn dùng UUID trong ORM `src/models/tables.py`, trong khi `s360` dùng BIGINT. Vì đang giai đoạn dev & chưa có dữ liệu thật → **chuyển hẳn sang BIGINT**, không duy trì bảng bridge. `student_code` (VARCHAR) vẫn là khóa liên kết học sinh giữa 2 schema.

---

## PHẦN B — 5 MODULE TRIỂN KHAI (theo thứ tự phụ thuộc)

```
M0 (Data foundation) ──► M1 (Exam difficulty) ──► M2 (Knowledge gap)
                                                       │
M0 ────────────────────────────► M3 (EWS LMS evidence) │
                                                       ▼
M0 ──► M4 (Pass/Fail prediction) ◄─────────────────────┘
```

---

## MODULE M0 — Data Foundation (bắt buộc làm trước)

**Mục tiêu:** bổ sung dữ liệu còn thiếu để các module sau có "bằng chứng" mà chạy.

### M0.1 — Thêm cột hành vi làm bài LMS (có lọc nhiễu off-task)
Cập nhật trực tiếp DDL `score_focused_schema.sql` (dev chưa có dữ liệu thật, không cần migration Alembic):
```sql
ALTER TABLE s360.fact_so_assignment_grade
  ADD COLUMN IF NOT EXISTS started_at        TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS submitted_at      TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS attempt_count     INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS time_spent_sec    INTEGER,  -- tổng thời gian (giây, thô)
  ADD COLUMN IF NOT EXISTS active_time_sec   INTEGER,  -- thời gian tương tác THỰC (đã loại treo máy)
  ADD COLUMN IF NOT EXISTS tab_hidden_count  INTEGER DEFAULT 0,  -- số lần rời tab (visibilitychange)
  ADD COLUMN IF NOT EXISTS idle_sec          INTEGER DEFAULT 0,  -- tổng giây bất hoạt (không tương tác)
  ADD COLUMN IF NOT EXISTS rte               SMALLINT;           -- Response Time Effort: 1=effortful, 0=rapid-guess/off-task
```
- `dim_so_assignment` bổ sung: `allow_attempts INTEGER`, `time_limit_sec INTEGER` (nếu LMS cung cấp).
- **Frontend telemetry** (khi tích hợp LMS): dùng Page Visibility API (`visibilitychange`) + Idle Detection (`mousemove/scroll/keydown`) để đo `active_time_sec` thay vì chỉ `time_spent_sec` thô — tránh nhầm "treo máy" thành "nỗ lực làm lâu".
- Seed mock mở rộng `data_mock/mock_full_data/generate_full_system_mock_v4.py` để sinh các nhóm hành vi (để M3 có dữ liệu demo): (a) rapid-guess (làm nhanh + điểm thấp), (b) effortful-but-lost (active_time cao + điểm thấp), (c) off-task (time_spent cao nhưng active_time thấp + nhiều tab_hidden), (d) không nộp.

### M0.2 — Map LMS bài tập ↔ chuẩn chương trình
Bảng cầu nối mới (schema `public`, đặt cạnh `exam_competencies`):
```sql
CREATE TABLE public.assignment_competencies (
    assignment_id  BIGINT NOT NULL,          -- s360.dim_so_assignment.assignment_id
    unit_id        BIGINT NOT NULL REFERENCES public.curriculum_units(id),
    weight         NUMERIC(4,3) DEFAULT 0,
    bloom_level    SMALLINT,                 -- 1..6
    PRIMARY KEY (assignment_id, unit_id)
);
```
- Dùng chung ý tưởng pipeline CDI: LLM phân tích tiêu đề/nội dung bài LMS → map `curriculum_units` (môn + khối) + Bloom. Tái dùng `classify_competencies` trong `content_difficulty.py` (đã có catalog constrained).

### M0.3 — Bảng kết quả lỗ hổng kiến thức
```sql
CREATE TABLE public.student_knowledge_gaps (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    so_school_id     INTEGER NOT NULL,
    student_code     VARCHAR(50) NOT NULL,
    subject_id       INTEGER NOT NULL,       -- s360.dim_subject.id
    school_year_id   INTEGER NOT NULL,
    semester_index   INTEGER NOT NULL CHECK (semester_index IN (1,2)),
    unit_id          BIGINT NOT NULL REFERENCES public.curriculum_units(id),
    gap_score        NUMERIC(5,2),           -- 0..1, cao = hổng nặng
    evidence_source  VARCHAR(20),            -- 'EXAM' | 'LMS' | 'HYBRID'
    evidence_detail  JSONB,                  -- {cau_diem, lms_bai_diem, bloom, ...}
    status           VARCHAR(20) DEFAULT 'active',  -- active | reviewed | remediated
    detected_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (so_school_id, student_code, subject_id, school_year_id, semester_index, unit_id)
);
```

**Người thực hiện:** backend (DDL SQL + ORM `src/models/`) · **Test:** ruff sạch.

---

## MODULE M1 — Phân tích Độ khó Đề (hoàn thiện TEVI)

**Mục tiêu:** đáp ứng "dựa dữ liệu sách + LLM phân tích độ khó đề".

**Hiện trạng đã có 70%** (TEVI Phase 0+1 xong, Phase 2 tự động phân tích CDI cũng đã có `content_difficulty.py`). Công việc còn lại tập trung vào **chất lượng & vận hành**:

1. **Chuẩn hóa nguồn dữ liệu sách/giáo án**: xác nhận đường nạp SGK + giáo án (`knowledge_pipeline.py` + `retrieval.py`) để `_best_evidence` trong CDI pipeline có SGK đối chiếu đủ môn/khối. Nếu giáo án chưa được ingest → thêm bước ingest giáo án vào cùng index Qdrant (collection `edu_knowledge`) với metadata phân loại `sgk|giao_an`.
2. **Nâng CDI pipeline**:
   - Chuẩn hóa `exam_papers`/`curriculum_units`/`exam_competencies` sang BIGINT (đồng bộ với `s360.dim_exam`/`dim_subject`) → JOIN thẳng `fact_gradebooks` để tính CDI cho đề thật trong s360 (hiện CDI chỉ chạy trên ORM UUID cũ).
   - Lưu `unit_code/topic` của từng câu vào `ai_analysis` để M2 (knowledge gap) soi theo unit.
3. **Endpoint mở rộng**: đã có `/analytics/exam-validity*`; bổ sung `GET /exam-papers/{id}/content-analysis` trả Bloom dist + coverage (nếu chưa có).
4. **Xử lý đề không có file**: giữ nguyên chính sách `NO_CONTENT` (minh bạch), đồng thời cho phép GV nhập tay `exam_competencies` (đã hỗ trợ).

**Test:** tái chạy `tests/test_content_difficulty.py`, `tests/test_exam_validity_service.py`.

---

## MODULE M2 — Phát hiện Lỗ hổng Kiến thức (Knowledge Gap)

**Mục tiêu:** với 1 đề thi, biết học sinh **hổng kiến thức nào** (theo chuẩn CT / chương).

### M2.1 — Luồng chính (khi CÓ đề thi + điểm)
1. **Phân rã đề theo unit**: từ `exam_competencies` (đề → `unit_id` + `weight` + `bloom_level`). Nếu đề chưa phân tích → trigger `analyze_exam_paper` (M1).
2. **Soi điểm từng unit**: do DB không lưu điểm từng câu, dùng **xấp xỉ có trọng số** (giống triết lý `item_statistics.py`):
   - Điểm tổng cột của học sinh `s_cột` với `exam_paper_id` tương ứng (qua `exam_column_mappings`/`scores`) → phân bổ về từng unit theo `weight` của unit, hiệu chỉnh theo `bloom_level` (câu Bloom cao → hệ số khó cao hơn).
   - `unit_mastery = clamp01( (điểm_phân_bổ_unit / trọng_số_unit_tối_đa) )` → unit nào mastery thấp = **hổng**.
3. **Đối chiếu RAG SGK**: với mỗi unit hổng, gọi `search_textbook(unit.name, mon, lop)` để lấy "nội dung chuẩn" → LLM sinh **mô tả lỗ hổng** bằng tiếng Việt + gợi ý ôn tập.
4. **Ghi `student_knowledge_gaps`** (M0.3) với `evidence_source='EXAM'`.

### M2.2 — Con đường khác khi CỘT ĐIỂM KHÔNG CÓ ĐỀ (KHÔNG đoán mang máng từ điểm)

> **Nguyên tắc:** điểm tổng của một cột KHÔNG map được vào unit → KHÔNG được suy diễn "hổng unit nào" từ con số đó. Thay vào đó, dùng nguồn **item-level** (LMS) làm nguồn chính, vì LMS có dữ liệu từng bài tập + response time + attempts — giàu thông tin hơn điểm tổng trên lớp.

Thứ tự ưu tiên (từ chuẩn nhất → kém chuẩn nhất, luôn kèm `confidence`):

| Ưu tiên | Nguồn | Cách làm | Độ tin cậy |
|---------|-------|----------|-----------|
| 1 | **LMS item-level (gold standard)** | `assignment_competencies` (M0.2) map bài LMS → unit; dùng `final_grade` + `active_time_sec` + `rte` (đã lọc nhiễu off-task/rapid-guess) để ước lượng mastery từng unit. | Cao — có bằng chứng item-level |
| 2 | **Transfer từ đề KHÁC của cùng học sinh** | Nếu học sinh có làm đề khác (cùng môn) mà đề đó ĐÃ map unit, dùng kết quả unit của đề đó làm proxy (cùng học sinh → năng lực unit ổn định). | Trung bình-cao |
| 3 | **Cohort transfer (bạn cùng lớp)** | Nếu cả lớp cùng GV/chương trình, dùng phân bố unit yếu của cohort làm prior cho học sinh (giả định cùng tiến độ dạy). | Trung bình |
| 4 | **Bayesian prior (SGK RAG + điểm latent)** | Dùng điểm tổng như tín hiệu năng lực tổng thể `θ` (không theo unit) + SGK RAG để ước lượng prior độ khó unit; kết hợp thành posterior có độ bất định lớn. | Thấp — chỉ là prior, ghi rõ "ước lượng" |
| 5 | **Fallback** | Không đủ cơ sở → trả `evidence_source=null` + cờ "chưa đủ cơ sở" (minh bạch, không đoán bừa). | Không kết luận |

> **Lưu ý:** điểm tổng cột KHÔNG bao giờ được dùng ĐƠN ĐỘC để suy "hổng unit X". Nó chỉ được dùng ở mức 4 như prior năng lực tổng thể, và kết quả phải gắn nhãn `confidence=low` + `evidence_source='PRIOR'`.

### M2.3 — Service & API
- `src/services/knowledge_gap.py`: `compute_student_gaps(...)`, `aggregate_class_gaps(...)`, `explain_gap(...)` (LLM + RAG).
- `src/schemas/knowledge_gap.py`: DTO.
- `src/api/v1/knowledge_gap.py` (register vào `src/api/v1/__init__.py`):
  - `GET /knowledge-gaps/students/{student_code}?subject_id=...&semester=...`
  - `GET /knowledge-gaps/classes/{class_id}?subject_id=...` (danh sách unit hổng phổ biến của lớp)
  - `POST /knowledge-gaps/refresh` (chạy nền BackgroundTasks).
- RBAC: GV bộ môn xem lớp dạy; GVCN/BGH xem lớp/khối phụ trách (dùng `get_user_assignment_constraints` như `ews.py`).

**Test:** `tests/test_knowledge_gap.py` (mock DB + mock LLM/RAG, theo fixture `mock_llm`).

---

## MODULE M3 — EWS Giải trình bằng chứng LMS (Explainability)

**Mục tiêu:** trong dự đoán EWS, có bước **lý giải được tại sao học tệ**, dùng LMS làm bằng chứng:
- "Học tệ chương A, B" (LMS map unit → điểm thấp ở bài thuộc chương A/B).
- "Làm qua loa" (LMS `time_spent_sec` thấp + điểm thấp, hoặc `attempt_count=1` + nộp sát hạn).
- "Nỗ lực nhưng không hiểu" (LMS `time_spent_sec` cao / nhiều attempts + điểm thấp).
- "Không làm LMS chương đó → thi trên lớp câu giống LMS nhưng sai" (so sánh unit xuất hiện trong đề với LMS cùng unit).

### M3.0 — Lọc nhiễu hành vi LMS (bắt buộc trước khi kết luận)
Theo nghiên cứu `deepsearch_about_outliner_response_time.md`, dữ liệu LMS có 2 loại nhiễu phải loại TRƯỚC khi dùng làm bằng chứng:
- **Off-task (treo máy)**: `time_spent_sec` cao nhưng `active_time_sec` thấp + nhiều `tab_hidden` → KHÔNG được kết luận "nỗ lực làm lâu".
- **Rapid guessing (đoán mò)**: thời gian làm cực ngắn (< 3s hoặc < 10% thời gian đọc) → KHÔNG phản ánh năng lực, phải loại khỏi tính mastery.

Dùng `rte` (Response Time Effort) để gán nhãn: chỉ bản ghi `rte=1` (effortful) mới được dùng làm bằng chứng "nỗ lực nhưng không hiểu".

### M3.1 — Service phân loại hành vi LMS (`src/ews/lms_evidence.py`)
Hàm thuần (dễ test, không LLM):
```
classify_lms_behavior(assignment_rows) -> list[EvidencePattern]
```
Trong đó mỗi bài LMS → 1 trong: `WEAK_CHAPTER` (điểm thấp), `RUSHED` (rapid-guess: active_time cực ngắn), `OFF_TASK` (time_spent cao nhưng active_time thấp + tab_hidden nhiều), `EFFORT_BUT_LOST` (active_time cao + rte=1 + điểm thấp), `SKIPPED` (không nộp), `MISSING_IN_EXAM` (unit có trong đề nhưng LMS cùng unit không làm).
- Ngưỡng dùng **active_time_sec** (KHÔNG dùng time_spent_sec thô): `active_ratio = active_time_sec / time_limit_sec` (vd < 0.1 = RUSHED, > 0.6 = EFFORT).
- `OFF_TASK` = `time_spent_sec` cao nhưng `active_time_sec` thấp (vd active < 30% total) hoặc `tab_hidden_count` lớn.

### M3.2 — Nâng `llm_forecasting.py`
- `_build_llm_prompt` bổ sung khối **`--- Bằng chứng LMS ---`** (danh sách bài LMS: unit/tên, điểm, thời gian, attempts, trạng thái nộp) + 3 loại phân loại từ M3.1.
- Prompt yêu cầu LLM **viện dẫn bằng chứng cụ thể** vào `llm_narrative_summary` thay vì nói chung. Không phá vỡ "static prefix" (cache) — thêm biến động vào dynamic suffix.
- (Tùy chọn) thêm cột `llm_evidence_patterns JSONB` vào `fact_student_subject_risk_predictions` để lưu kết quả M3.1 (không bắt buộc — có thể tính on-the-fly ở API như `primary_badge`).

### M3.3 — Hiển thị
- `/ews/raw` đã trả LMS; bổ sung field `lms_evidence` (pattern + giải thích) vào `EwsRawDetail` để drawer EWS hiển thị.
- Frontend `EwsDetailDrawer.tsx` thêm block "Bằng chứng học tập LMS" (liệt kê chương yếu / qua loa / nỗ lực nhưng không hiểu), nằm trước block LLM Narrative.

**Test:** `tests/test_ews_lms_evidence.py` (unit test `classify_lms_behavior` thuần) + mock LLM cho prompt mới.

---

## MODULE M4 — Dự đoán Pass/Fail cho Đề Cuối Kỳ

**Mục tiêu:** GV bỏ đề cuối kỳ vào → hệ thống dự đoán **có bao nhiêu học sinh trượt/pass**.

### M4.1 — Luồng
1. **GV upload đề cuối kỳ** → M1 phân tích CDI + map unit (`exam_competencies`).
2. **Ước lượng năng lực từng học sinh** trên các unit của đề:
   - Từ `fact_gradebooks` (điểm trên lớp đến hiện tại) + `fact_so_assignment_grade` (LMS theo unit, M0.2) + `student_knowledge_gaps` (M2).
   - Vector năng lực `ability_u` theo từng unit u của đề (0..10).
3. **Dự đoán điểm từng học sinh** trên đề:
   ```
   predicted_score_i = Σ_u (weight_u × ability_u) × difficulty_adj(CDI)
   ```
   hoặc dùng mô hình đơn giản hồi quy trên features lịch sử (tái dùng feature EWS: `last_score`, `lms_avg_score`, `score_slope`) → dự đoán `predicted_score`.
4. **Phân loại pass/fail**: ngưỡng `pass_threshold` (mặc định 5.0, cấu hình theo trường/môn) → đếm `n_pass`, `n_fail`, `n_borderline` (4.5–5.5).
5. **Cảnh báo rủi ro lớp**: % dự kiến trượt cao → gợi ý ôn tập các unit hổng phổ biến (liên kết M2).

### M4.2 — Service & API
- `src/services/pass_fail_forecast.py`: `forecast_exam_pass_fail(exam_paper_id)` → DTO.
- `src/schemas/pass_fail_forecast.py`.
- `src/api/v1/pass_fail_forecast.py`:
  - `POST /pass-fail-forecast` (nhận `exam_paper_id` hoặc upload đề mới).
  - `GET /pass-fail-forecast/{id}` (kết quả + breakdown theo lớp/học sinh).
- RBAC: ADMIN/PRINCIPAL/SUBJECT_HEAD/HOMEROOM + SUBJECT_TEACHER theo phạm vi.

### M4.3 — Giải trình
Mỗi dự đoán kèm `drivers` (unit hổng đóng góp, điểm LMS thấp, xu hướng điểm) để GV tin được con số — tái dùng pattern `risk_factor_details` của EWS.

**Test:** `tests/test_pass_fail_forecast.py` (mock score history, kiểm tra ngưỡng pass/fail + phân loại borderline).

---

## PHẦN C — THỨ TỰ THỰC HIỆN & PHÂN CHIA VIỆC

### Bước 1 (nền móng) — M0
- Cập nhật DDL SQL `score_focused_schema.sql` (M0.1 + M0.2 + M0.3).
- Cập nhật ORM `src/models/` (s360_tables.py + tables.py) + seed mock v4.
- **Gate:** `ruff check` + DDL chạy sạch trên Neon + `pytest` xanh.

### Bước 2 (độ khó đề) — M1
- Chuẩn hóa `exam_papers`/`curriculum_units`/`exam_competencies` sang BIGINT (đồng bộ với `s360.dim_exam`/`dim_subject`), bỏ UUID.
- Ingest giáo án vào Qdrant (nếu thiếu).
- **Gate:** demo CDI cho 1 đề thật trong s360.

### Bước 3 (kiến thức hổng) — M2
- `knowledge_gap.py` + API + phân rã theo unit + con đường thay thế.
- **Gate:** với 1 đề có `exam_competencies` + điểm, liệt kê đúng unit hổng; với cột không có đề, dùng LMS/học bạ thay thế.

### Bước 4 (EWS giải trình) — M3
- `lms_evidence.py` + nâng prompt `llm_forecasting.py` + UI drawer.
- **Gate:** narrative EWS dẫn chứng cụ thể "chương X yếu / làm qua loa / nỗ lực nhưng không hiểu".

### Bước 5 (dự đoán pass/fail) — M4
- `pass_fail_forecast.py` + API + UI.
- **Gate:** upload đề cuối kỳ → ra số dự kiến trượt/pass + breakdown unit hổng.

### Bước 6 — Tích hợp multi-agent (chatbot)
- Thêm tool `get_knowledge_gap_report` + `get_pass_fail_forecast` vào sub-agent phù hợp (`data_service_agent` hoặc `stat_agent`), cập nhật `SUPERVISOR_PROMPT` để định tuyến câu hỏi "học sinh hổng gì?" / "mấy em trượt?".
- **(Lưu ý quy ước multi-agent):** nếu thêm sub-agent mới phải đồng bộ 3 chỗ (`RouterDecision`, `SUPERVISOR_PROMPT`, `build_graph/route_next`). Khuyến nghị: **KHÔNG tạo agent mới**, thêm tool vào `stat_agent`/`data_service_agent` (theo đúng pattern `get_exam_validity_report` đã có).

### Bước 7 — Frontend
- Trang/panel: "Phân tích đề & lỗ hổng kiến thức" + block "Bằng chứng LMS" trong EWS drawer + "Dự đoán pass/fail" khi upload đề CK.
- (Đọc `frontend/node_modules/next/dist/docs/` trước khi viết — Next.js 16 breaking changes.)

### Bước 8 — Test & CI
- Mock LLM (fixture `mock_llm`) cho mọi test dùng LLM.
- `ruff check` + `pytest` trước push.

---

## PHẦN D — RỦI RO & LƯU Ý

| Rủi ro | Giảm thiểu |
|--------|-----------|
| **Đồng nhất PK BIGINT** | Đang dev, chưa có dữ liệu → chuyển `public` (exam_papers/curriculum_units/...) sang BIGINT hẳn, KHÔNG duy trì bridge UUID↔BIGINT. `student_code` vẫn là khóa liên kết học sinh. |
| **DB không lưu điểm từng câu** | Chấp nhận xấp xỉ theo trọng số unit + Bloom (ghi rõ trong `evidence_detail`); không gọi là "chính xác CTT". |
| **LMS thiếu time/attempts (nếu nguồn LMS không cung cấp)** | M0.1 thiết kế nullable; M3 fallback dùng `submitted`/final_grade nếu không có thời gian. |
| **LLM map sai unit/Bloom** | Bắt buộc `evidence` (trích câu) + cho GV duyệt `exam_competencies`/`assignment_competencies`; lưu confidence. |
| **Báo động giả (mẫu nhỏ)** | Ngưỡng `n≥30` + confidence (đã có pattern ở exam_validity). |
| **Đề không có file** | Luôn minh bạch `NO_CONTENT`, dùng con đường thay thế (M2.2), không đoán bừa. |
| **Nhạy cảm dữ liệu học sinh** | RBAC theo `get_user_assignment_constraints`; tenant isolation `so_school_id`. |

---

## PHẦN E — ĐỊNH NGHĨA HOÀN THÀNH (DoD)

- [ ] M0: DDL `score_focused_schema.sql` chạy sạch, ORM + seed mock sync đúng schema.
- [ ] M1: CDI được tính cho đề thật trong s360, giáo án được RAG tra cứu.
- [ ] M2: 1 học sinh được liệt kê chính xác các unit hổng (có bằng chứng câu/đề), và 1 trường hợp cột không có đề dùng LMS/học bạ thay thế đúng.
- [ ] M3: narrative EWS dẫn chứng cụ thể "chương X yếu / qua loa / nỗ lực nhưng không hiểu / bỏ bài LMS".
- [ ] M4: upload đề CK → ra số dự kiến trượt/pass kèm breakdown unit hổng + ngưỡng borderline.
- [ ] Multi-agent: chatbot trả lời đúng "học sinh hổng gì" / "mấy em trượt".
- [ ] Frontend hiển thị đủ 4 năng lực; `ruff check` + `pytest` xanh (mock LLM).

---

## PHẦN F — NÂNG CẤP TỪ BÀI NGHIÊN CỨU DEEPSEARCH (tham chiếu `docs_vsf/deepsearch_analysis.md`)

> Quyết định: **giữ MVP hiện tại (EDI/CDI đơn giản) rồi nâng dần** — không chuyển sang IRT/Bayesian ngay vì DB chưa có ma trận phản hồi item-level.

Các bài học từ bài nghiên cứu được xếp 3 mức ưu tiên và gắn vào từng module:

### Mức A — Áp dụng ngay trong các module hiện tại
| Bài học | Module | Cụ thể |
|---|---|---|
| **Retrieval Semantic Distance** | M1 | Bổ sung đo embedding câu hỏi vs SGK hit trong `content_difficulty.py` (thêm vào `ai_analysis`, không thay Bloom). |
| **Phân biệt LMS vi mô vs thi vĩ mô** | M0.1 + M3 | Khớp yêu cầu "LMS chứng minh nỗ lực làm lâu nhưng điểm tệ / học qua loa". Củng cố `time_spent_sec`/`attempt_count` + `lms_evidence.py`. |
| **Curriculum Blueprint Alignment** | M1/M2 | Đối soát đề vs giáo án, phát hiện "blind spot" (vùng kiến thức bị bỏ quên). |
| **Phân bố Bloom chuẩn 40/30/20/10** | M1 | Làm tham chiếu trong báo cáo độ khó. |

### Mức B — Trung hạn (làm sau MVP, khi có dữ liệu item-level)
| Bài học | Module | Ghi chú |
|---|---|---|
| **Pairwise/Glicko-2** | M1 | Thay chấm Bloom tuyệt đối → ổn định CDI. |
| **Concept KG có cạnh prerequisite** | M0/M2 | Thêm bảng `curriculum_unit_prerequisites` → phát hiện "hổng kiến thức tiền đề". |
| **Bayesian IRT** | M1/M4 | Thay `EDI = 1 - facility`; dùng năng lực `θ` cho pass/fail. |

### Mức C — Để giai đoạn sau (nặng / ngoài MVP)
- **Agentic IRT simulation** (tốn LLM nhiều).
- **OPR — distractor plausibility** (cần dữ liệu distractor, đề tự luận VN ít trắc nghiệm chuẩn).
- **Full TIF/SEM** (cần ma trận phản hồi item-level).

> Chi tiết đầy đủ xem `docs_vsf/deepsearch_analysis.md`.

---

## PHẦN G — THIẾT KẾ UI (mô tả từng màn hình)

> Bám sát quy ước frontend hiện có: `Sidebar.tsx` (menu theo role), pattern trang `/scores` (filter form + bảng + drawer/modal), `SearchableSelect` cho dropdown >5 mục, màu thương hiệu `brand #0D4D8B` / `accent #C72127`, badge trạng thái emerald/amber/rose. Tham khảo thêm `docs/exam_generation_ui_design.md` (đã có sẵn).

### G.1. Màn "Phân tích độ khó đề" (M1 — TEVI)

**Route:** `/exam-difficulty` · **Role:** ADMIN / PRINCIPAL / SUBJECT_HEAD

```
┌─ Bộ lọc: [Môn ▾] [Khối ▾] [Học kỳ ▾] [Loại: GK/CK ▾]  [Năm học ▾]
├─ Bảng tam giác hóa (mỗi dòng = 1 đề/cột):
│   Môn │ Khối │ Kỳ │ EDI │ CDI │ DDI │ Divergence │ Cờ │ Mức tin cậy │ Xem chi tiết
│   ... │ ...  │ ...│0.60 │0.32 │0.50 │  +0.28     │ 🟠 LEARNING_GAP │ 87% │ →
└─ Cờ đỏ nổi bật (accent): INFLATION_OR_LEAK / LEARNING_GAP
```

**Drawer chi tiết 1 đề** (khi click "Xem chi tiết"):
```
Độ khó thực nghiệm (EDI): 0.60  ← từ phân phối điểm (n=37, mean=3.98)
Độ khó nội dung (CDI):    0.32  ← Bloom: 40% Nhớ + 30% Hiểu + 30% Vận dụng
Độ khó khai báo (DDI):    0.50  ← GV gán MEDIUM
Divergence: +0.28 → 🟠 LEARNING_GAP (điểm thấp dù đề không khó)
────────────────────────────────────
Phân bố Bloom (bar chart): Nhớ ████ 40% · Hiểu ███ 30% · Vận dụng ███ 30%
Chuẩn tham chiếu: 40/30/20/10 (đánh dấu lệch nếu có)
Chuẩn CT phủ (coverage): 5/8 unit · Blind spot: [Chương 4 — chưa được kiểm tra]
Bằng chứng SGK (RAG): "..." (trích dẫn cho từng unit)
```

### G.2. Màn "Lỗ hổng kiến thức" (M2)

**Route:** `/knowledge-gaps` · **Role:** SUBJECT_TEACHER (lớp dạy) / HOMEROOM / SUBJECT_HEAD / PRINCIPAL

```
┌─ Bộ lọc: [Lớp ▾] [Môn ▾] [Học kỳ ▾]  [Học sinh ▾ SearchableSelect]
├─ 2 tab:
│   Tab "Theo học sinh":  Chọn 1 HS → danh sách unit hổng
│   Tab "Theo lớp":       Danh sách unit hổng PHỔ BIẾN của cả lớp (top unit yếu)
└─ Bảng unit hổng (mỗi dòng = 1 unit):
    Chương/Bài │ Mức hổng (gap_score) │ Nguồn bằng chứng │ Bloom │ Gợi ý ôn tập
    Chương 2   │ ████ 0.72 (nặng)     │ 📝 EXAM (câu 3,5) │ 3     │ [Xem SGK]
```

**Drawer chi tiết 1 unit hổng:**
```
Unit: "Phân số — Chương 2" (Toán 6)
Mức hổng: 0.72 (nặng)
Nguồn bằng chứng: 📝 EXAM — câu 3 (sai), câu 5 (sai) · Bloom 3 (Vận dụng)
────────────────────────────────────
Nội dung chuẩn (RAG SGK): "..." (trích SGK)
Giải thích lỗ hổng (LLM): "Học sinh chưa nắm quy đồng mẫu số..."
Gợi ý: [Bài tập ôn] [Gửi phụ đạo]
────────────────────────────────────
⚠️ Nếu nguồn = PRIOR (cột không có đề): badge "Ước lượng — confidence thấp"
```

### G.3. EWS drawer — block "Bằng chứng LMS" (M3)

**Vị trí:** trong `EwsDetailDrawer.tsx` hiện có, chèn block mới TRƯỚC block LLM Narrative.

```
┌─ Bằng chứng học tập LMS ─────────────────────┐
│ Chương 2 (Phân số):    điểm 3/10 · ⏱ 25 phút · 2 lần thử → 🔴 NỖ LỰC NHƯNG KHÔNG HIỂU
│ Chương 3 (Số thập phân): điểm 2/10 · ⏱ 40 giây · 1 lần   → 🟠 LÀM QUA LOA (rapid-guess)
│ Chương 4 (Hình học):   KHÔNG NỘP                          → ⚪ BỎ BÊ
│ Chương 5:              (đề có câu nhưng LMS không làm)     → 🔵 MẤT KIẾN THỨC
└──────────────────────────────────────────────┘
```

- Mỗi dòng gồm: tên unit + điểm + thời gian (active_time) + số lần thử + **nhãn hành vi**.
- Nhãn hành vi (từ `classify_lms_behavior`): `EFFORT_BUT_LOST` (đỏ), `RUSHED` (cam), `OFF_TASK` (xám — treo máy, KHÔNG kết luận), `SKIPPED` (xám), `MISSING_IN_EXAM` (xanh).
- **Lọc nhiễu**: bản ghi `OFF_TASK`/`RUSHED` hiển thị kèm chú thích "dữ liệu nhiễu, không dùng làm bằng chứng".

### G.4. Màn "Dự đoán Pass/Fail đề cuối kỳ" (M4)

**Route:** `/pass-fail-forecast` · **Role:** SUBJECT_TEACHER / SUBJECT_HEAD / PRINCIPAL

**Bước 1 — Upload đề:**
```
[Kéo thả / chọn file đề CK (Word/PDF/ảnh)]  →  tự chạy phân tích CDI (M1)
Sau phân tích: "Đề đã phân tích: CDI=0.45 · 10 câu · 6 unit · Bloom 40/30/20/10"
```

**Bước 2 — Kết quả dự đoán:**
```
┌─ Tổng quan: 42 học sinh · ✅ Pass 28 (67%) · ❌ Fail 9 (21%) · ⚠️ Ranh giới 5 (12%)
├─ Biểu đồ phân bố điểm dự kiến (histogram, vạch ngưỡng 5.0)
├─ Bảng theo lớp:
│   Lớp │ Sĩ số │ Pass │ Fail │ Borderline │ % trượt │ Unit hổng phổ biến
│   8A1 │  42   │  28  │  9   │     5      │  21%    │ Chương 2, Chương 4
└─ Cảnh báo nếu % trượt > 30%: "Lớp 8A2 có 35% dự kiến trượt — gợi ý ôn Chương 4"
```

**Drill-down 1 học sinh:** điểm dự kiến + `drivers` (unit nào kéo điểm xuống, điểm LMS thấp, xu hướng điểm).

### G.5. Menu Sidebar (bổ sung)

Thêm 3 mục mới vào `Sidebar.tsx` (theo role):

```tsx
{ name: "Phân tích độ khó đề", path: "/exam-difficulty", icon: Gauge }        // ADMIN/PRINCIPAL/SUBJECT_HEAD
{ name: "Lỗ hổng kiến thức",  path: "/knowledge-gaps",  icon: AlertTriangle } // GV/SUBJECT_HEAD/PRINCIPAL
{ name: "Dự đoán pass/fail",  path: "/pass-fail-forecast", icon: TrendingUp } // GV/SUBJECT_HEAD/PRINCIPAL
```

### G.6. Quy tắc UI/UX bắt buộc (kế thừa từ exam_generation_ui_design.md)

1. **Không lộ đáp án** ngoài phạm vi cần thiết (áp dụng cho drawer chi tiết câu).
2. **Luôn hiển thị truy vết người** (tạo bởi / duyệt bởi / ngày) — không hiện UUID.
3. **Badge màu nhất quán** với `/scores` (emerald=pass/duyệt, amber=ranh giới/chờ, rose=fail/từ chối).
4. **Hành động không hoàn tác** (chốt đề, từ chối) luôn có modal xác nhận.
5. **Trạng thái rỗng rõ ràng** — không bảng trống im lặng.
6. **Dropdown >5 mục dùng `SearchableSelect`**.
7. **Cờ "ước lượng" (PRIOR/confidence thấp)** phải hiển thị tường minh, không che giấu độ bất định.

### G.7. Kế hoạch triển khai frontend (theo phase)

- **Phase A** — Màn "Phân tích độ khó đề" (G.1): bảng tam giác + drawer chi tiết (backend TEVI đã có sẵn).
- **Phase B** — Màn "Lỗ hổng kiến thức" (G.2): bảng unit hổng + drawer (phụ thuộc M2 backend).
- **Phase C** — Block "Bằng chứng LMS" trong EWS drawer (G.3): phụ thuộc M3 backend.
- **Phase D** — Màn "Dự đoán pass/fail" (G.4): upload + kết quả (phụ thuộc M4 backend).
- **Phase E** — Tinh chỉnh: badge ước lượng, trạng thái rỗng, SearchableSelect, responsive.

> **Lưu ý:** Next.js 16 có breaking changes — đọc `frontend/node_modules/next/dist/docs/` trước khi viết code.