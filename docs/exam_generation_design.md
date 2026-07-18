# TÀI LIỆU THIẾT KẾ — TẠO ĐỀ THI CHÍNH THỨC TỪ NGÂN HÀNG CÂU HỎI (AI-ASSISTED)

**Dự án:** AI20K-075 — AI Trợ Lý Phân Tích Kết Quả Học Tập
**Tính năng:** AI Exam Generation — Item Bank + Blueprint Assembly (AEG)
**Phiên bản:** 1.0.0 (Draft) · **Ngày:** 2026-06-28
**Trạng thái:** Thiết kế — sẵn sàng triển khai theo phase
**Tài liệu liên quan:** [exam_triangulation_design.md](exam_triangulation_design.md) (CDI/TEVI) · [RAG_design.md](RAG_design.md) (ingestion SGK) · [schema.sql](schema.sql) · [knowledge_agent](../src/agents/knowledge_agent/)

> **Người đọc mục tiêu:** dev backend (FastAPI + SQLAlchemy + LangGraph) và data engineer. Tài liệu mô tả *cái cần làm* và *vì sao*, kèm DDL/contract cụ thể. Ưu tiên đúng mô hình & ranh giới module hơn là từng dòng code.

---

## 1. BÀI TOÁN & QUYẾT ĐỊNH KIẾN TRÚC

### 1.1. Yêu cầu
Cho phép người ra đề (GV bộ môn / Trưởng bộ môn) tạo **đề thi CHÍNH THỨC** (Giữa kỳ / Cuối kỳ — MIDTERM/FINAL) cho một **môn × khối**, với tùy chọn: chương/chủ đề nào, bao nhiêu câu, phân bố mức độ phân hóa (độ khó), thời lượng, tổng điểm. Đề phải:
- **bám chuẩn chương trình** (SGK đã nạp RAG) và **đúng môn/khối**;
- có **độ khó phù hợp năng lực thực tế của khối/lớp** (không quá dễ → mất phân hóa, không quá khó → sàn điểm);
- **tin cậy được** (đáp án đúng, không mơ hồ, không lệch chương trình) vì đây là điểm thật.

### 1.2. Hai phương án đã cân nhắc
| | PA1 — Ngân hàng câu hỏi | PA2 — AI sinh đề "nóng" trực tiếp |
|---|---|---|
| Chất lượng tại lúc thi | Đã duyệt 1 lần, tin được | Rủi ro hallucinate **rơi thẳng vào phòng thi** |
| Tái lập / nhiều mã đề | ✅ | ❌ |
| Độ khó | **CDI thực nghiệm** (đo từ phản hồi HS) | LLM tự khai (không đáng tin) |
| Giải trình / audit | ✅ truy vết từng câu | khó |
| Chi phí ban đầu | cao (xây kho) | thấp |

### 1.3. Quyết định — HYBRID, ngân hàng là "nguồn sự thật"
**Không chọn PA1 hoặc PA2 — dùng PA2 làm công cụ NẠP cho PA1:**

```
LLM + RAG (SGK)  ──sinh câu DRAFT──▶  NGÂN HÀNG CÂU HỎI  ──ráp theo ma trận──▶  ĐỀ CHÍNH THỨC
   (PA2 = cỗ máy)        │  duyệt tay (human-in-the-loop)        │ (PA1 = nguồn sự thật)
                         ▼                                        ▼
                  APPROVED mới dùng                    nhiều mã đề + đáp án + CDI
```

**Vì sao bắt buộc với đề CHÍNH THỨC:** lỗi đắt nhất (đáp án sai / câu không giải được) phải bị chặn **trước** kỳ thi, không phải lúc HS đang làm bài. Ngân hàng đưa khâu kiểm soát chất lượng ra **offline, một lần, có người duyệt**; còn độ khó thì lấy từ **CDI/TEVI** (đo thực nghiệm) chứ không tin nhãn LLM tự gán.

### 1.4. Ranh giới với đề CHÍNH THỨC (quan trọng)
- Đề chính thức ⇒ **mọi HS cùng khối làm CHUNG một đề** (công bằng + quy chế). "Theo năng lực HS" áp ở **mức khối/lớp** (lái phân bố độ khó khi ráp), **KHÔNG cá nhân hóa từng em**.
- Cá nhân hóa / adaptive chỉ dành cho **đề luyện tập (formative)** — **ngoài phạm vi v1**, xem §11.

---

## 2. PHẠM VI

**Trong phạm vi (v1):**
- Ngân hàng câu hỏi (`question_items`) theo `subject × grade × curriculum_unit × bloom`.
- Pipeline sinh câu DRAFT bằng LLM+RAG (tái dùng `retrieval.search_textbook` / knowledge_agent).
- Quy trình duyệt câu (DRAFT → REVIEW → APPROVED/REJECTED) có RBAC.
- Ma trận đề (`exam_blueprints`) + máy ráp đề (assembly) tạo nhiều **mã đề** song song.
- Neo độ khó vào **CDI** (TEVI) + hiệu chỉnh bằng **thống kê câu hỏi** sau mỗi lần dùng.
- Xuất đề + đáp án (file) và **liên kết vào luồng chấm hiện có** (`exam_papers` + `exam_column_mappings`).

**Ngoài phạm vi (v1):**
- Đề cá nhân hóa / CAT (adaptive). Chấm tự động bài làm HS (chỉ tạo đề + đáp án mẫu).
- Câu hỏi đa phương tiện phức tạp (hình vẽ động, mô phỏng). v1: text + công thức (LaTeX) + ảnh tĩnh đính kèm.

---

## 3. MÔ HÌNH ĐỘ KHÓ — TÁI DÙNG TEVI, KHÔNG PHÁT MINH LẠI

Đề chính thức cần độ khó **đo được**, không phải LLM tự khai. Ta dùng **2 nguồn** đã có hạ tầng trong [exam_triangulation_design.md](exam_triangulation_design.md):

| Ký hiệu | Nguồn | Lúc nào có | Dùng để |
|--------|-------|-----------|---------|
| `bloom_level` (1–6) | LLM gán khi sinh câu, **người duyệt xác nhận** | ngay khi tạo câu | ước lượng độ khó **ban đầu** (proxy) |
| `p_value` (facility) | tỉ lệ HS làm đúng/đạt điểm câu đó | **sau** khi câu được dùng trong đề thật | độ khó **thực nghiệm** (đáng tin nhất) |
| `discrimination` | tương quan câu ↔ tổng điểm (point-biserial) | sau khi dùng | chất lượng phân hóa của câu |

**Độ khó hiệu dụng của một câu** (`item_difficulty ∈ [0,1]`, cao = khó):
```
nếu đã có thống kê:   item_difficulty = 1 − p_value
nếu chưa (câu mới):    item_difficulty = bloom_level / 6          # proxy tạm
```
- Khi ráp đề ta nhắm **phân bố `item_difficulty`** theo target (xem §6.2).
- **CDI của cả đề** vẫn tính đúng công thức TEVI §2.2 (`CDI_bloom = Σ(weightᵢ·bloomᵢ)/Σweightᵢ /6`) — đề ráp ra **đã có sẵn `exam_competencies`** (vì từng câu đã map `unit_id`+`bloom_level`+điểm=weight) → **không cần OCR/phân tích lại**. Đây là lợi thế lớn: đề tự ra đã "TEVI-ready".

**Lái độ khó theo năng lực khối/lớp:** ước lượng năng lực mục tiêu từ điểm lịch sử + `content_adjusted_ability` (TEVI §2.5) của khối → đặt **target_difficulty** cho ma trận (vd khối yếu môn Toán → giảm tỉ trọng Bloom 4–6).

> **Nguyên tắc neo:** câu mới dùng Bloom làm proxy; mỗi lần đề được chấm xong → pipeline cập nhật `p_value`/`discrimination` (§9) → lần ráp sau dùng số thực. Kho **tự hiệu chỉnh** theo thời gian, đúng tinh thần TEVI (phá vòng lặp "độ khó suy từ điểm").

---

## 4. MÔ HÌNH DỮ LIỆU

### 4.1. Tái sử dụng (KHÔNG tạo mới)
- `subjects` (`assessment_type`=SCORED, `applicable_level`) · `grades` · `semesters` · `schools`
- `curriculum_units` (chuẩn CT phân cấp `code/name/parent_id` theo `subject_id+grade_number`) — **trục phân loại câu hỏi**
- `exam_papers` + `exam_competencies` — **đích đến**: đề ráp xong ghi 1 bản ghi `exam_papers` (file đề) + `exam_competencies` (để TEVI/chấm dùng tiếp)
- `exam_column_mappings` + `scores.exam_paper_id` — liên kết đề vào cột điểm GK/CK (đã có)
- RAG `edu_knowledge` qua `src/services/retrieval.py` — nguồn nội dung sinh câu

### 4.2. Bảng mới

**(a) `question_items` — ngân hàng câu hỏi (nguồn sự thật)**
```sql
CREATE TABLE question_items (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id       UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  subject_id      UUID NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
  grade_number    SMALLINT NOT NULL CHECK (grade_number BETWEEN 1 AND 12),
  unit_id         UUID NOT NULL REFERENCES curriculum_units(id) ON DELETE RESTRICT,
  bloom_level     SMALLINT NOT NULL CHECK (bloom_level BETWEEN 1 AND 6),
  question_type   question_type_enum NOT NULL,          -- MCQ | TRUE_FALSE | SHORT_ANSWER | ESSAY
  stem            TEXT NOT NULL,                          -- đề bài (Markdown/LaTeX)
  options         JSONB,                                  -- [{key:'A',text:..}], NULL nếu tự luận
  answer_key      JSONB NOT NULL,                         -- {correct:'B'} | {answer:..,rubric:..}
  solution        TEXT,                                   -- lời giải/giải thích (cho người duyệt + ngân hàng)
  default_points  NUMERIC(4,2) NOT NULL DEFAULT 1.0,
  status          item_status_enum NOT NULL DEFAULT 'DRAFT', -- DRAFT|REVIEW|APPROVED|REJECTED|RETIRED
  source          item_source_enum NOT NULL DEFAULT 'AI_GENERATED', -- AI_GENERATED|MANUAL|IMPORTED
  provenance      JSONB NOT NULL DEFAULT '{}',            -- {model, rag_sources:[...], prompt_hash}
  -- thống kê thực nghiệm (cập nhật sau mỗi lần dùng — §9)
  times_used      INT NOT NULL DEFAULT 0,
  p_value         NUMERIC(4,3),                           -- facility 0..1 (NULL = chưa dùng)
  discrimination  NUMERIC(4,3),
  exposure_at     TIMESTAMPTZ,                            -- lần cuối xuất hiện trong đề (kiểm soát lộ)
  created_by      UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  reviewed_by     UUID REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at     TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_qi_pick ON question_items(subject_id, grade_number, unit_id, bloom_level, status);
CREATE INDEX idx_qi_school ON question_items(school_id);
```
> **Đáp án trắc nghiệm để JSONB** (`options`/`answer_key`) thay vì bảng con: đơn giản, đủ cho v1, tránh join thừa. Tự luận: `answer_key` chứa `rubric` (thang chấm) để GV chấm tay.

**(b) `exam_blueprints` — ma trận đề (cấu hình ráp, tái dùng được)**
```sql
CREATE TABLE exam_blueprints (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id     UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  subject_id    UUID NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
  grade_number  SMALLINT NOT NULL,
  score_category score_category_enum NOT NULL,           -- MIDTERM | FINAL
  title         VARCHAR(255) NOT NULL,
  total_points  NUMERIC(5,2) NOT NULL DEFAULT 10.0,
  duration_min  SMALLINT,
  target_difficulty NUMERIC(4,3),                         -- mức khó mong muốn 0..1 (lái theo năng lực khối)
  cells         JSONB NOT NULL,                           -- ma trận: xem dưới
  created_by    UUID NOT NULL REFERENCES users(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- cells = [{unit_id, bloom_level, question_type, num_questions, points_each}, ...]
-- ràng buộc mềm (kiểm ở service): Σ(num_questions·points_each) = total_points
```

**(c) `generated_exams` — một lần ráp (gồm nhiều mã đề)**
```sql
CREATE TABLE generated_exams (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id     UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  blueprint_id  UUID NOT NULL REFERENCES exam_blueprints(id) ON DELETE RESTRICT,
  semester_id   UUID NOT NULL REFERENCES semesters(id),
  grade_id      UUID REFERENCES grades(id),
  num_variants  SMALLINT NOT NULL DEFAULT 1,             -- số mã đề
  status        gen_exam_status_enum NOT NULL DEFAULT 'DRAFT', -- DRAFT|FINALIZED|PUBLISHED
  exam_paper_id UUID REFERENCES exam_papers(id) ON DELETE SET NULL, -- bản ghi đề chính thức (sau FINALIZE)
  created_by    UUID NOT NULL REFERENCES users(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**(d) `generated_exam_items` — câu trong từng mã đề (thứ tự + xáo)**
```sql
CREATE TABLE generated_exam_items (
  generated_exam_id UUID NOT NULL REFERENCES generated_exams(id) ON DELETE CASCADE,
  variant_code   VARCHAR(8) NOT NULL,                    -- '101','102'... (mã đề)
  position       SMALLINT NOT NULL,
  item_id        UUID NOT NULL REFERENCES question_items(id) ON DELETE RESTRICT,
  points         NUMERIC(4,2) NOT NULL,
  option_order   JSONB,                                  -- thứ tự đáp án sau khi xáo (giữ map đáp án đúng)
  PRIMARY KEY (generated_exam_id, variant_code, position)
);
```

**(e) Enum mới** (`src/models/enums.py`):
`QuestionType`, `ItemStatus`, `ItemSource`, `GenExamStatus`. `score_category_enum` tái dùng (chỉ cho phép MIDTERM/FINAL ở v1 — chặn ở service).

---

## 5. NHÁNH A — SINH CÂU HỎI VÀO KHO (LLM + RAG)

### 5.1. Trigger
- `POST /api/v1/question-bank/generate` (SUBJECT_HEAD / SUBJECT_TEACHER theo phân công môn) — body: `subject_id`, `grade_number`, `unit_id[]`, `bloom_distribution`, `question_type`, `count`.
- Sinh ra câu ở trạng thái **`DRAFT`** — **chưa dùng được để ráp đề**.

### 5.2. Luồng sinh (per câu, có RAG grounding)
```
1. retrieval.search_textbook(query=unit.name, mon=subject.code, lop=grade)  → ngữ cảnh SGK (k đoạn)
2. LLM (structured output) sinh câu BÁM ngữ cảnh:
      - stem + options + answer_key + solution
      - tự gán bloom_level (phải khớp ô ma trận yêu cầu)
      - provenance.rag_sources = [heading/score của các đoạn đã dùng]  ← để giải trình & chống bịa
3. Tự kiểm (guardrail máy, §5.3) → nếu fail thì regenerate (tối đa N lần)
4. UPSERT question_items (status=DRAFT)
```
**Pydantic structured output:**
```python
class GeneratedOption(BaseModel):
    key: str           # 'A'..'D'
    text: str
class GeneratedItem(BaseModel):
    stem: str
    question_type: QuestionType
    options: list[GeneratedOption] | None
    answer_key: dict          # {correct:'B'} hoặc {answer, rubric}
    solution: str             # BẮT BUỘC — lời giải để người duyệt kiểm
    bloom_level: int          # 1..6
    grounded_quotes: list[str]  # trích đoạn SGK đã dựa vào (bằng chứng bám chuẩn)
```

### 5.3. Guardrail tự động (chặn rác trước khi tới người duyệt)
| Kiểm | Cách | Fail ⇒ |
|------|------|--------|
| Bám nguồn | `grounded_quotes` không rỗng + match được đoạn RAG | regenerate |
| Đáp án hợp lệ | MCQ: đúng 1 `correct` ∈ options; không trùng option | regenerate |
| Bloom khớp ô | `bloom_level` = yêu cầu ô ma trận | regenerate |
| **Tự giải lại** | LLM thứ 2 (vai HS) giải độc lập → so với `answer_key`; lệch ⇒ nghi đáp án sai | gắn cờ `needs_review_hard` |
| Trùng lặp | so embedding `stem` với câu APPROVED cùng unit (ngưỡng cosine) | đánh dấu duplicate |

> **Self-consistency check** (giải lại bằng LLM độc lập) là tuyến phòng thủ rẻ cho lỗi nguy hiểm nhất — đáp án sai. Nhưng **KHÔNG thay người duyệt**: nó chỉ xếp ưu tiên/đánh cờ.

### 5.4. Duyệt (human-in-the-loop) — BẮT BUỘC cho đề chính thức
```
DRAFT ──(GV/Trưởng BM kiểm)──▶ REVIEW ──▶ APPROVED  (mới được ráp)
                                       └─▶ REJECTED (kèm lý do)
APPROVED ──(quá cũ/lộ/sai sót phát hiện sau)──▶ RETIRED
```
- UI duyệt hiển thị: stem, đáp án, **lời giải**, `grounded_quotes`, cờ guardrail, unit/bloom. Cho phép **sửa tay** rồi duyệt.
- **RBAC:** SUBJECT_TEACHER tạo/sửa DRAFT môn mình; **chỉ SUBJECT_HEAD (Trưởng bộ môn) hoặc ADMIN APPROVE** (vì đề chính thức GK/CK do trưởng bộ môn chịu trách nhiệm — khớp `can_map` GK/CK theo khối ở [rbac.py](../src/services/rbac.py)).

---

## 6. NHÁNH B — RÁP ĐỀ TỪ KHO (assembly)

### 6.1. Trigger
`POST /api/v1/exams/assemble` — body: `blueprint_id`, `semester_id`, `grade_id`, `num_variants`. Chỉ chọn từ câu **APPROVED**, cùng `school_id`.

### 6.2. Thuật toán chọn câu (theo từng ô ma trận)
```
Với mỗi cell (unit_id, bloom_level, question_type, num_questions):
   pool = APPROVED items khớp (subject, grade, unit, bloom, type), cùng school
   loại câu có exposure_at quá gần (chống lộ: vd dùng trong N kỳ gần nhất)
   xếp ưu tiên: |item_difficulty − target| nhỏ  +  discrimination cao  +  ít dùng
   chọn num_questions câu (ưu tiên đa dạng câu, tránh trùng nội dung)
   nếu pool < num_questions  ⇒  trả lỗi 409 + gợi ý "sinh thêm câu ô X" (không tự bịa)
```
- **Mã đề (variants):** giữ **cùng tập câu**, **xáo thứ tự câu + thứ tự đáp án** (lưu `option_order` để map lại đáp án đúng). Đảm bảo công bằng (cùng độ khó) mà chống nhìn bài.
- **Kiểm tổng:** Σ điểm = `total_points`; CDI đề ráp ≈ `target_difficulty` (cảnh báo nếu lệch).

### 6.3. Hoàn tất (FINALIZE) — nối vào luồng chấm hiện có
Khi người ra đề chốt:
1. Render file đề + phiếu đáp án (mỗi mã đề) → lưu storage → tạo **1 `exam_papers`** (`file_url`, `num_questions`, `total_points`, `topics[]`=unit names, `difficulty` từ target).
2. Ghi **`exam_competencies`** từ các câu đã chọn (`unit_id`, `bloom_level`, `weight`=điểm/tổng) → **TEVI dùng ngay**, `content_difficulty` (CDI) tính trực tiếp **không cần OCR**.
3. `generated_exams.exam_paper_id` ← bản ghi vừa tạo; trạng thái `FINALIZED`.
4. GV map đề vào cột điểm qua `POST /scores/mappings` (đã có) để chấm GK/CK.

> Đây là mấu chốt khép vòng: **đề sinh ra tự "TEVI-ready"** — sau khi HS thi và nhập điểm, hệ tự tính EDI, đối chiếu CDI (đã biết chính xác) → validity tin cậy hơn cả đề upload (vì CDI không phải đoán qua OCR).

---

## 7. KIẾN TRÚC & PHÂN LỚP (theo CLAUDE.md §7)

```
schemas/exam_generation.py   (DTO: GenerateItemsRequest, BlueprintRead, AssembleRequest, ...)
   └─ repositories/question_items.py, blueprints.py   (CRUD thuần)
        └─ services/
             item_generation.py   (gọi LLM+RAG sinh câu + guardrail §5)
             exam_assembly.py      (thuật toán chọn câu + xáo mã đề §6)
             item_statistics.py    (cập nhật p_value/discrimination §9)
        └─ api/v1/question_bank.py, exams.py   (router + RBAC)
```
- **Tách nhánh A nặng:** `item_generation` gọi LLM theo lô — chạy **background task** (FastAPI `BackgroundTasks` cho v1; nâng Airflow nếu khối lượng lớn, giống pipeline SGK/CDI). Không chặn request.
- Giữ đúng tầng; function ≤30 dòng, ≤3 tham số (nhiều hơn → Pydantic).

---

## 8. TÍCH HỢP MULTI-AGENT (tùy chọn, sau API)

Người ra đề có thể yêu cầu bằng ngôn ngữ tự nhiên qua chat. **Không tạo agent mới** — thêm tool cho một agent phù hợp và để Supervisor định tuyến:

- Tool `draft_exam_blueprint(subject, grade, score_category, focus_units, difficulty)` → gợi ý **ma trận đề** (không tự ráp/không tự bịa câu) dựa trên `curriculum_units` + năng lực khối (đọc DB). Đặt ở **stat_agent** (cần số liệu năng lực) hoặc agent mới `exam_agent` nếu sau này phình to.
- `knowledge_agent` **bổ trợ**: giải thích "chuẩn CT/chủ đề này gồm gì" để người ra đề chọn unit — đúng vai RAG SGK.
- **Lằn ranh an toàn:** agent chỉ **đề xuất cấu hình** + trigger pipeline; **việc sinh câu vẫn qua nhánh A có duyệt**. Tuyệt đối không để Supervisor trả thẳng "đề thi" ra chat (rơi lại PA2 nguy hiểm).
- Nếu thêm tool/agent: đồng bộ **4 chỗ** `RouterDecision` + `SUPERVISOR_PROMPT` + `build_graph` + `route_next` (CLAUDE.md §8).

---

## 9. VÒNG LẶP HIỆU CHỈNH — THỐNG KÊ CÂU HỎI (sau khi thi)

Sau khi điểm GK/CK của đề được duyệt (`scores.status=APPROVED`):
```
service item_statistics.update_from_exam(generated_exam_id):
  với mỗi item trong đề:
     p_value        = AVG(điểm câu)/điểm tối đa câu        # cần điểm item-level
     discrimination = point-biserial(câu, tổng điểm)
     times_used += 1 ; exposure_at = now()
```
**Lưu ý dữ liệu:** DB hiện chỉ lưu **điểm tổng mỗi cột** (`scores`), **không có điểm từng câu** → để có `p_value` thật cần một trong:
- (a) nhập điểm item-level (mở rộng tương lai — ngoài v1), hoặc
- (b) **xấp xỉ ở cấp đề**: dùng EDI của cả đề (TEVI) để hiệu chỉnh **proxy độ khó trung bình**, phân bổ ngược về các câu theo bloom (thô nhưng khả thi v1).

> v1 dùng (b): cập nhật `item_difficulty` proxy theo EDI cả đề; (a) là nâng cấp khi có chấm item-level. Ghi rõ để không hứa quá năng lực dữ liệu hiện có.

---

## 10. API CONTRACT (prefix `/api/v1`)

| Method | Endpoint | Quyền | Mô tả |
|--------|----------|-------|-------|
| POST | `/question-bank/generate` | SUBJECT_HEAD/SUBJECT_TEACHER (theo môn) | Sinh câu DRAFT bằng LLM+RAG (background) |
| GET | `/question-bank/items` | theo phân công môn | Lọc câu (subject/grade/unit/bloom/status) |
| POST | `/question-bank/items` | SUBJECT_TEACHER | Tạo câu thủ công (source=MANUAL) |
| PATCH | `/question-bank/items/{id}` | tác giả / SUBJECT_HEAD | Sửa câu (DRAFT/REVIEW) |
| POST | `/question-bank/items/{id}/review` | **SUBJECT_HEAD/ADMIN** | Duyệt: APPROVED/REJECTED (+lý do) |
| GET/POST | `/exam-blueprints` | theo môn | Tạo/đọc ma trận đề |
| POST | `/exams/assemble` | SUBJECT_HEAD/SUBJECT_TEACHER | Ráp đề từ kho (chọn APPROVED) → nhiều mã đề |
| POST | `/exams/{id}/finalize` | SUBJECT_HEAD/ADMIN | Render file + tạo exam_papers + exam_competencies |
| GET | `/exams/{id}` | theo RLS | Xem đề ráp + mã đề + đáp án (ẩn đáp án theo quyền) |

- **RBAC** (tái dùng [rbac.py](../src/services/rbac.py)): mọi truy vấn lọc `school_id`; đáp án (`answer_key`/`solution`) chỉ trả cho người ra đề/duyệt, **không** lộ qua endpoint HS. PRINCIPAL/ADMIN xem read-only toàn trường.
- Ghi `audit_logs` cho mọi APPROVE/FINALIZE (đề chính thức — cần truy vết trách nhiệm).

---

## 11. KẾ HOẠCH TRIỂN KHAI THEO PHASE

**Phase 0 — Nền dữ liệu (1–2 ngày)**
- Migration: 4 bảng mới + enum. Seed `curriculum_units` cho 1 môn/khối thử (vd Toán 8 — tái dùng seed của TEVI Phase 0).
- Nhập tay vài câu APPROVED → kiểm máy ráp đề chạy đúng **trước khi** làm LLM sinh câu.

**Phase 1 — Ráp đề từ kho (cốt lõi, dùng được ngay)**
- `exam_blueprints` + `exam_assembly` (chọn câu + mã đề + xáo) + finalize → `exam_papers`/`exam_competencies`.
- ✅ Mốc: có kho câu (nhập tay) → ráp được đề GK Toán 8 nhiều mã đề, TEVI tính được CDI.

**Phase 2 — Sinh câu bằng LLM+RAG + duyệt**
- `item_generation` + guardrail (self-consistency) + UI/endpoint duyệt.
- ✅ Mốc: 1 lệnh sinh 20 câu DRAFT bám SGK → trưởng BM duyệt → vào kho ráp đề.

**Phase 3 — Hiệu chỉnh & agent**
- `item_statistics` cập nhật độ khó sau thi (xấp xỉ EDI). Tool `draft_exam_blueprint` cho chat.
- (Tùy chọn) đề luyện tập cá nhân hóa (formative) — mở rộng ngoài v1.

---

## 12. RỦI RO & GIẢM THIỂU

| Rủi ro | Giảm thiểu |
|--------|-----------|
| **Đáp án sai lọt vào đề thật** | Bắt buộc duyệt người (SUBJECT_HEAD) + self-consistency check máy + lưu `solution`/`grounded_quotes` để kiểm |
| LLM bịa nội dung ngoài chương trình | RAG grounding bắt buộc (`grounded_quotes` rỗng ⇒ loại); map cứng vào `curriculum_units` |
| Kho cạn câu khi ráp | Báo lỗi 409 + gợi ý sinh thêm đúng ô; **không tự bịa câu lúc ráp** |
| **Lộ đề / học tủ** | `exposure_at` loại câu vừa dùng; nhiều mã đề; nhãn RETIRED |
| Độ khó LLM tự khai không đúng | Dùng Bloom làm **proxy tạm**; hiệu chỉnh bằng EDI/thống kê sau thi (§9) |
| Thiếu điểm item-level | v1 xấp xỉ ở cấp đề (EDI); ghi rõ giới hạn, không hứa p_value chính xác |
| Trùng câu | check embedding khi sinh + khi ráp |
| Nhạy cảm (đề chính thức) | RBAC chặt, ẩn đáp án, `audit_logs` mọi APPROVE/FINALIZE |

---

## 13. TIÊU CHÍ HOÀN THÀNH (Definition of Done)
- [ ] Migration 4 bảng + enum áp lên Neon; ràng buộc CHECK đúng.
- [ ] Ráp được đề GK Toán 8 từ kho APPROVED, ≥2 mã đề (xáo câu + đáp án), Σ điểm = total_points.
- [ ] Finalize tạo `exam_papers` + `exam_competencies` → TEVI tính `content_difficulty` (CDI) **không cần OCR**.
- [ ] Sinh câu LLM+RAG có `grounded_quotes`; guardrail loại được câu sai đáp án (self-consistency).
- [ ] Duyệt RBAC đúng: SUBJECT_TEACHER tạo DRAFT, chỉ SUBJECT_HEAD/ADMIN APPROVE; đáp án không lộ qua endpoint sai vai.
- [ ] Test offline (mock LLM) cho assembly + guardrail; ruff sạch; `audit_logs` ghi APPROVE/FINALIZE.

---

## 14. PHỤ LỤC — VÍ DỤ MINH HỌA

**Ráp đề Cuối kỳ Toán 8, khối yếu (target_difficulty=0.40):**
- Ma trận: Chương "Phân thức" 4 câu MCQ Bloom 2 (0.5đ) + 2 câu tự luận Bloom 3 (1.0đ); Chương "Phương trình" 3 câu MCQ Bloom 2 + 1 tự luận Bloom 4 … Σ = 10đ.
- Máy chọn từ kho APPROVED: ưu tiên câu `item_difficulty≈0.40`, discrimination cao, chưa dùng kỳ gần.
- Sinh 3 mã đề (101/102/103): cùng câu, xáo thứ tự + đáp án.
- Finalize → `exam_papers` (num_questions=10, total=10) + `exam_competencies`:
  `CDI_bloom = (Σ weightᵢ·bloomᵢ)/Σweightᵢ /6 ≈ (2·0.05·2 + 1.0·0.10·3 + …)/6` → vd `0.38` ≈ target ✅.
- HS thi → nhập điểm → EDI = 1 − mean/10. Nếu EDI lệch xa CDI=0.38 → TEVI gắn cờ (INFLATION/LEARNING_GAP) như [exam_triangulation_design.md](exam_triangulation_design.md) §2.4.

→ Đề **bám chuẩn (RAG) + độ khó đo được (Bloom→CDI→EDI) + tin cậy (duyệt người) + tái lập (nhiều mã đề)** — đủ điều kiện cho **đề thi chính thức** triển khai thật.
