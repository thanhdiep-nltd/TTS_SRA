# KẾ HOẠCH TRIỂN KHAI — Phân tích đề thi neo theo Curriculum Catalog (KG phẳng), bỏ full-text RAG

> Ngày: 2026-08-15 · Dự án: TTS_SRA (SRA - Student Risk Alert)
> Mục tiêu: đơn giản hóa pipeline phân tích độ khó/độ phù hợp đề thi — chuyển từ "full-text RAG làm thẩm phán" sang "Catalog chuẩn chương trình (KG phẳng) + LLM map trực tiếp vào node", đồng thời dùng VLM đọc đề thay OCR để giữ công thức sạch.
> Phạm vi: chỉ phần phân tích nội dung đề (CDI) + chẩn đoán lỗ hổng kiến thức theo chương. Không đụng TEVI/EWS/pass-fail (giữ nguyên).

---

## PHẦN A — NGUYÊN NHÂN & QUYẾT ĐỊNH THIẾT KẾ (đã chốt với user)

### A1. Vì sao bỏ full-text RAG làm thẩm phán

Hiện tại 3 trục (Off-curriculum, Semantic Distance, Evidence Linking) đều phụ thuộc vào cosine similarity trên kho SGK OCR (`src/services/retrieval.py` + `content_difficulty.py::_attach_evidence`). Ba lỗi thực tế:

1. **Blind công thức/LaTeX**: embedding gần như mù với biến số → `x²−4=0` vs `x²+4=0` bị gom cụm giống nhau.
2. **False distance**: đề đổi ngữ cảnh đời thực (bài "ném bóng") → cosine thấp → `off_curriculum = evidence is None` báo nhầm "ngoài chương trình" (`content_difficulty.py:477-485`).
3. **Chunk phân mảnh**: định lý ở chunk A, ví dụ ở chunk B → trích dẫn thiếu/lệch.

**Kết luận:** RAG vẫn giữ cho chat hỏi đáp tự do, nhưng **không dùng trong pipeline phân tích đề**. Chuyển sang **KG phẳng (curriculum catalog)** + **LLM map trực tiếp vào node** + **trích dẫn chương/bài từ cây** (không lưu công thức).

### A2. "KG phẳng" nghĩa là gì (phân biệt với KG đầy đủ)

- **KG phẳng** = bảng danh mục `curriculum_units` (đã có sẵn), mỗi dòng 1 đơn vị kiến thức; quan hệ "thuộc chương/bài" ghi thành **cột + `parent_id`** (self-FK đã tồn tại). KHÔNG cần cạnh "tiên quyết".
- **KG đầy đủ** = thêm cạnh quan hệ giữa node (prerequisites, K-hop…) → **KHÔNG làm** ở giai đoạn này.

Node hiện tại (`src/models/tables.py::CurriculumUnit`) đã có: `id, subject_id, grade_number, parent_id, code, name, description, semester_number, is_active`.

### A3. Tổ hợp model (đã chốt)

| Thành phần | Vai trò |
|---|---|
| **Qwen3-VL-Flash** | "Mắt" — đọc ảnh/trang đề → text + LaTeX sạch (thay OCR Tesseract/text-layer) |
| **KG phẳng (curriculum_units)** | "Bản đồ giới hạn" — lọc theo (môn, khối, học kỳ) → shortlist ~15–30 node |
| **DeepSeek (lý luận mạnh)** | "Não phân loại" — decompose đề + chọn 1–3 `node_id` trong shortlist + tự kiểm công thức |

---

## PHẦN B — FLOW MỚI (end-to-end)

```
① Upload đề (PDF/ảnh) + metadata: môn, khối, học kỳ, loại đề (GK/CK)
        │
② Qwen3-VL-Flash: đọc ảnh/trang → text + LaTeX SẠCH   (bỏ OCR công thức)
        │
③ KG phẳng: lọc (môn, khối, học kỳ) → SHORTLIST node ứng viên
        │
④ DeepSeek: decompose đề + map MỖI Ý → 1–3 node (kèm weight từng node)
        │  đồng thời trả bloom_level (cả câu), excerpt, confidence
        │  └─ mọi node null (không khớp node nào) → ứng viên off-curriculum
        │
⑤ mọi node null → vòng 2: LLM tái thẩm định kèm lý do (dựa tri thức nội tại + tên/chương)
        │  └─ vẫn null → off_curriculum = TRUE (cờ MỀM) → xuất shortlist cho GV chốt
        │
⑥ Ghi exam_competencies (node + weight + bloom)   ← như cũ
        │
⑦ Tính 5 trục → lưu ai_analysis.content_analysis
        │
⑧ (Chẩn đoán) exam_competencies + điểm số → knowledge_gap.py
        → "câu này chương nào / sao học tệ"
```

---

## PHẦN C — 6 TRỤC → 5 TRỤC

| Trục cũ | Trục mới | Thay đổi |
|---|---|---|
| **1. Bloom Matrix** | **Bloom (giữ nguyên)** | DeepSeek phân loại 1–6 (KHÔNG thêm critic — xem G2). KHÔNG đổi sang Bloom-by-graph. |
| **2. Coverage** | **Coverage theo node_id** | Đếm node kích hoạt / tổng node trong shortlist chương. |
| **3. Concentration** | **Concentration theo chương** | Tỉ trọng điểm dồn vào 1 chương (gộp node cùng `parent_id`). |
| **4. Off-curriculum** | **Off-curriculum (LLM-as-judge)** | mọi node null từ bước map (không phải cosine) → cờ mềm + shortlist GV chốt. |
| **5. Semantic Distance** | ❌ **BỎ hẳn** | Không K-hop, không `1−cos`. |
| **6. Evidence Linking** | **Trích dẫn từ cây chương/bài** | Ghi `chapter` + `lesson` từ `parent_id`/name. KHÔNG RAG, KHÔNG lưu công thức. |

Công thức giữ nguyên: `CDI = Σ(bloom×weight)/Σ(weight)/6` (`cdi_from_bloom_mix`), bloom_distribution + ALIGNED/BIASED (`_bloom_distribution_and_alignment`), coverage.ratio (`_coverage`), concentration.top_share (`_concentration`).

---

## PHẦN D — CÁC MODULE TRIỂN KHAI

```
M0 (Catalog chuẩn chương trình) ──► M1 (VLM reader) ──► M2 (LLM mapper)
                                                         │
M0 ─────────────────────────────► M3 (5 trục analysis) ◄─┘
                                                         │
M0 ──► M4 (Chẩn đoán chương/học tệ) ◄────────────────────┘
M5 (API/UI) ── M6 (test-case mẫu)
```

---

## MODULE M0 — Catalog chuẩn chương trình phẳng (nền móng)

**Mục tiêu:** `curriculum_units` đủ môn/khối, có cấu trúc chương→bài qua `parent_id`. KHÔNG lưu công thức chuẩn — LLM map trực tiếp từ tên/code/chương bằng tri thức nội tại.

### M0.1 — Seed catalog phẳng từ nguồn chuẩn (1 lần)

- Nguồn: khung PPCT Bộ GD + mục lục SGK + hệ thống soạn giáo án `s360.cm_*` (đã tích hợp ở `docs_vsf/plan_lesson_plan_integration.md`: `cm_course → cm_unit → cm_lesson → cm_lessonplan → cm_lessontarget`).
- LLM sinh `curriculum_units` (code, name, grade, subject, parent_id, semester_number) — cột `description` có thể chứa 1 dòng mô tả ngắn nếu cần, KHÔNG bắt buộc.
- Script mới: `scripts/seed_curriculum_nodes.py` (đọc JSON/CSV đầu vào → upsert `curriculum_units`).

**Người thực hiện:** backend (seed script) · **Test:** ruff sạch + `pytest`.

> **Tùy chọn Phase 2 (KHÔNG làm ở giai đoạn này):** bảng `curriculum_node_anchors` (công thức chuẩn + symbols + dạng bài + trang SGK) — chỉ cần khi (a) null-rate cao gây quá tải GV duyệt, hoặc (b) muốn trích dẫn "công thức chuẩn + trang SGK" tuyệt đối cho môn nặng công thức. Lúc đó thêm sau, không phải làm lại.

---

## MODULE M1 — VLM reader (đọc đề thay OCR)

**Mục tiêu:** trích đề thành text + LaTeX trung thực, không làm hỏng công thức.

- Sửa `src/services/content_difficulty.py::extract_exam_text` (hiện dùng text-layer PDF + Tesseract) → gọi **Qwen3-VL-Flash** (hoặc VLM cấu hình qua `src/config.py`) đọc trực tiếp ảnh/trang, trả LaTeX.
- Giữ nguyên ảnh gốc để bước tự kiểm (M2) đối chiếu khi nghi ngờ.
- Fallback: nếu VLM lỗi → OCR text-layer như hiện tại (chỉ cho câu nhiều chữ), kèm cờ `low_fidelity`.

**Người thực hiện:** backend · **Test:** `tests/test_content_difficulty.py` mock VLM, kiểm tra LaTeX không bị mất ký hiệu.

---

## MODULE M2 — LLM mapper (decompose + map node)

**Mục tiêu:** mỗi ý của đề → 1–3 `node_id` trong shortlist + bloom + weight + confidence.

- Sửa `content_difficulty.py::classify_competencies` (hiện LLM chọn `unit_code` tự do) → **prompt constrained**: LLM chọn `node_id` TỪ SHORTLIST đã lọc (môn/khối/học kỳ), không phải toàn bộ catalog.
- Kết quả mỗi ý: `{ nodes: [{node_id, weight}], bloom_level, excerpt, confidence, reason }` (schema đầy đủ ở G2).
- Mọi node null → **vòng 2**: LLM tái thẩm định câu hỏi, yêu cầu đưa lý do (câu hỏi đang kiểm tra kỹ năng/khái niệm nào, gần chương nào nhất) rồi chọn lại trong shortlist → vẫn null → off-curriculum (cờ mềm) + trả 2–3 node ứng viên xếp hạng cho GV chốt.
- Bỏ fallback tạo unit phân mảnh (`_resolve_units` tạo unit từ topic) — thay bằng cờ `low_confidence` chờ GV.

**Người thực hiện:** backend (LLM) · **Test:** mock LLM trả `nodes`/null, kiểm tra vòng 2 tái thẩm định trả về lý do + shortlist ứng viên.

---

## MODULE M3 — 5 trục analysis (bỏ Semantic Distance)

**Mục tiêu:** dựng `ai_analysis.content_analysis` theo 5 trục.

Sửa `src/services/content_difficulty.py::build_content_analysis` + `src/schemas/exam_analysis.py`:

- **Xóa**: `avg_retrieval_distance` (trục Semantic Distance) và `EvidenceRef` (RAG) khỏi schema.
- **Thêm**: `node_ref { node_id, chapter, lesson }` cho Evidence Linking (lấy từ cây qua `parent_id`/name; không lưu công thức, không lưu trang SGK).
- **Giữ**: `coverage`, `coverage_units`, `concentration`, `off_curriculum_weight`, `bloom_distribution`, `bloom_alignment`, `cdi`.
- `off_curriculum_weight` giờ tính từ tổng weight của các node null (không từ cosine).

**Người thực hiện:** backend · **Test:** `tests/test_content_difficulty.py` cập nhật theo schema mới.

---

## MODULE M4 — Chẩn đoán "câu thuộc chương nào / sao học tệ"

**Mục tiêu:** map câu → node → chương; nối điểm số để biết học sinh hổng chương nào.

- **Đã có**: `src/services/knowledge_gap.py::compute_unit_mastery` (unit mastery/gap từ `exam_competencies` + điểm tổng) + API `src/api/v1/knowledge_gap.py`.
- **Bổ sung nhẹ**: trả kèm `chapter` (đi lên `parent_id` 1 bậc) để báo cáo ghi "chương X", và dùng `node_ref` từ M3 làm trích dẫn.
- **KHÔNG xây** tag LMS 2 chiều ở giai đoạn này (hoãn; `assignment_competencies` + LMS chỉ làm khi cần M2/M3 đầy đủ sau).

**Người thực hiện:** backend · **Test:** `tests/test_knowledge_gap.py` + mock DB.

---

## MODULE M5 — API/UI hiển thị

**Mục tiêu:** hiển thị kết quả 5 trục cho GV.

- API đã có: `GET /exam-papers/{id}/content-analysis` (`src/api/v1/exam_papers.py`) — chỉ cần cập nhật response theo schema M3.
- Frontend: nối trang hiện có `exam-difficulty` (xem G4) với `content-analysis`; hiển thị: CDI, phân bố Bloom, coverage, concentration, off-curriculum (cờ mềm + shortlist chờ GV chốt), trích dẫn node (chương + bài từ cây). Nếu muốn giải thích công thức, để LLM sinh kèm nhãn "do AI giải thích" — không phải trích nguyên văn.

**Người thực hiện:** backend + frontend · **Test:** lint + build.

---

## MODULE M6 — Test-case mẫu (giả lập/công khai)

**Mục tiêu:** chứng minh off-curriculum không báo nhầm + map đúng chương.

Chuẩn bị 4–5 đề mẫu:
1. **Đề chuẩn** (trong chương trình) → off-curriculum = false, coverage hợp lý.
2. **Đề ngoài chương trình** (câu lạ hẳn) → off-curriculum = true + shortlist.
3. **Đề nặng công thức ít chữ** (vd `∫ x²/(x+1) dx`, `lim_{x→∞}`) → map đúng chương nhờ LLM nhận diện ký hiệu + shortlist (môn/khối/học kỳ).
4. **Đề đổi ngữ cảnh đời thực** (bài "ném bóng" → Định luật II Newton) → KHÔNG bị gắn off-curriculum oan.
5. **Đề 2 node gần giống** (Đạo hàm vs Ứng dụng đạo hàm) → shortlist GV chốt.

**Người thực hiện:** dữ liệu + test · **Test:** `pytest` + báo cáo đối chiếu kết quả.

---

## PHẦN E — THỨ TỰ THỰC HIỆN & GATE

1. **M0 (nền)** — seed catalog phẳng (`curriculum_units`) từ nguồn chuẩn.
   **Gate:** `ruff check` + `pytest` xanh + seed chạy xong.
2. **M1 + M2 (đọc + map)** — VLM reader + LLM constrained mapper + vòng 2 tái thẩm định.
   **Gate:** demo 1 đề thật map đúng chương, công thức không hỏng.
3. **M3 (5 trục)** — sửa schema + bỏ Semantic Distance + trích dẫn tĩnh.
   **Gate:** `content-analysis` trả đúng 5 trục.
4. **M4 (chẩn đoán)** — nối chapter + điểm số vào knowledge_gap.
   **Gate:** báo cáo "chương nào / học tệ" cho 1 lớp mẫu.
5. **M5 + M6 (UI + test)** — nối frontend + 5 đề mẫu.
   **Gate:** UI hiển thị + test-case pass.

---

## PHẦN F — KỲ VỌNG TRUNG THỰC & RỦI RO

- **Độ chính xác map chương**: ~85–90% tự động sạch, ~10–15% cần GV nhìn qua (chủ yếu ca 2 node gần giống). Ở **cấp chương** gần như luôn đúng; ở **cấp node con** mới cần shortlist.
- **Rủi ro chính**: (1) VLM đọc sai 1 ký hiệu → lệch dây chuyền → chặn bằng bước tự kiểm công thức + retry; (2) LLM map sai ca 2 node gần giống → chặn bằng shortlist GV chốt; (3) off-curriculum báo nhầm → chặn bằng cờ MỀM + shortlist GV, không tự động kết luận.
- **Ranh giới rõ**: không tự động "xác nhận 100% ngoài chương trình" — luôn để con người chốt ca null.

---

## TÓM TẮT THAY ĐỔI CODE (bám file thật)

| File | Thay đổi |
|---|---|
| `scripts/seed_curriculum_nodes.py` (mới) | Seed catalog phẳng (`curriculum_units`) từ nguồn chuẩn |
| `src/services/content_difficulty.py` | `extract_exam_text`→VLM; `classify_competencies`→map node constrained; bỏ `_collect_evidence`/`_attach_evidence` RAG; bỏ `_resolve_units` fallback; `build_content_analysis`→5 trục |
| `src/schemas/exam_analysis.py` | Bỏ `avg_retrieval_distance` + `EvidenceRef`; thêm `node_ref` |
| `src/api/v1/exam_papers.py` | Response theo schema mới |
| `src/services/retrieval.py` | KHÔNG dùng trong pipeline (giữ cho chat) |
| `src/services/knowledge_gap.py` | Bổ sung chapter vào kết quả |

---

## QUYẾT ĐỊNH CUỐI (checklist để khỏi lệch)

- [ ] KG **phẳng** (bảng + parent_id), KHÔNG KG đầy đủ, KHÔNG K-hop, KHÔNG Bloom-by-graph.
- [ ] Bỏ **full-text RAG** khỏi pipeline phân tích đề; trích dẫn = chương/bài từ cây.
- [ ] Off-curriculum = **LLM map null** + vòng 2 tái thẩm định + **cờ mềm** chờ GV.
- [ ] KHÔNG lưu công thức chuẩn; LLM map trực tiếp trên bảng phẳng (`curriculum_node_anchors` chỉ là Phase 2 tùy chọn).
- [ ] 6 trục → **5 trục** (bỏ Semantic Distance).
- [ ] VLM (Qwen3-VL-Flash) đọc đề, **không OCR** công thức.
- [ ] Chẩn đoán dùng `knowledge_gap.py` + điểm số, **không** xây tag LMS 2 chiều.
- [ ] Một ý map được 1–3 node kèm weight (đa node); `exam_competencies` đã hỗ trợ — không đổi hạ tầng.

---

## PHẦN G — BỔ SUNG CHI TIẾT TRƯỚC KHI CODE (5 mục quyết định)

> Bổ sung ngày 2026-08-15. Plan chốt hướng; phần này chốt chi tiết để bắt tay code liền. Mỗi mục có **Quyết định khuyến nghị** — nếu lệch thì sửa tại đây trước khi code.

### G1 — Thiết kế VLM reader cụ thể (M1)

Hiện `content_difficulty.py::extract_exam_text` dùng text-layer PDF + Tesseract. Quyết định cho VLM:

| Vấn đề | Quyết định khuyến nghị |
|---|---|
| Provider/API | Thêm cấu hình vào `src/config.py`: `vlm_provider`, `vlm_model` (mặc định `qwen3-vl-flash`), `vlm_api_base`, `vlm_api_key`, `vlm_timeout_s` — tách khỏi `get_llm()` (LLM text) để mock độc lập trong test |
| Đề nhiều trang PDF | Render từng trang → ảnh → gọi VLM **từng trang**, ghép kết quả; giữ nguyên file gốc để bước tự kiểm (M2) |
| Output parsing | VLM trả markdown/LaTeX; chuẩn hóa: tách câu/ý lớn, giữ LaTeX `$...$` nguyên vẹn. Parse lỗi → đánh dấu trang `low_fidelity` |
| Retry/fallback | Retry 1 lần với độ phân giải cao hơn nếu text ngắn bất thường (< `_MIN_CLASSIFY_CHARS`); vẫn lỗi → fallback OCR text-layer + cờ `low_fidelity` (không crash pipeline) |
| Mock trong test | Fixture `mock_vlm` (pattern `mock_llm` ở `tests/conftest.py`): trả LaTeX giả định, kiểm tra không mất ký hiệu |

> **Lưu ý (chốt với user):** cứ gọi thẳng **Qwen (Qwen3-VL-Flash)** trong code — user sẽ tự cấu hình API key sau. KHÔNG chặn/hoãn code vì thiếu key: đọc key từ config/env, chưa set thì log cảnh báo `vlm_key_missing` và fallback OCR text-layer + cờ `low_fidelity`.

### G2 — Prompt contract + shortlist filter (M2)

**Shortlist filter** (bám code thật): `POST /exam-papers` bắt buộc `subject_id` + `semester_id`, còn `grade_id` **tùy chọn** (`src/api/v1/exam_papers.py`).

| Trường hợp | Quy tắc |
|---|---|
| Có đủ môn + khối + học kỳ | Lọc `curriculum_units` theo (subject_id, grade_number, semester_number khớp hoặc NULL) → shortlist ~15–30 node |
| Thiếu `grade_id` | Resolve từ `exam_column_mappings` → class → grade (đã có `_resolve_grade_number`); vẫn thiếu → **shortlist = cả môn** + cờ `shortlist_wide` (LLM khó hơn, chấp nhận cho MVP) |

**Output schema của DeepSeek** (mỗi ý 1 object, CHỈ JSON array):

```json
{
  "topic": "Chuyển động trên mặt phẳng nghiêng",
  "nodes": [
    { "node_id": 210, "weight": 0.6 },   // Định luật II Newton
    { "node_id": 215, "weight": 0.4 }    // Lực ma sát — câu ghép 2 đơn vị
  ],                                     // 1–3 node; Σweight = 1; câu 1 chủ đề chỉ cần 1 node
  "bloom_level": 4,                      // 1..6, của CẢ câu (mức tư duy chi phối)
  "excerpt": "Vật trượt trên mặt phẳng nghiêng có ma sát...",
  "confidence": 0.8,                     // 0..1
  "reason": "cần kết hợp ĐL II Newton với lực ma sát"
}
```

- **Validation**: mọi `node_id` phải nằm trong shortlist (ngoài → bỏ + cảnh báo log); tối đa 3 node/ý; Σweight = 1 (service chuẩn hóa lại như `classify_competencies` cũ); `bloom_level` 1..6.
- **Câu đa node (1 ý → nhiều node)**: `exam_competencies` đã hỗ trợ sẵn (PK exam_paper_id + unit_id, `merge_by_unit` gộp trọng số) — chỉ đổi schema đầu vào. Coverage đếm mọi node có weight > 0; Concentration tự giảm khi câu trải nhiều chương (đúng bản chất); knowledge_gap phân bổ điểm theo weight tích lũy. Off-curriculum: chỉ 1 node null → cờ "một phần ngoài chương trình" (weight = Σ weight null); toàn null mới là off hoàn toàn. Bloom giữ 1 mức cho cả câu. LLM muốn > 3 node → bắt decompose thành nhiều ý con (mỗi ý ≤ 3 node).
- **Retry**: JSON hỏng hoặc > 30% ý trả node_id ngoài shortlist → gọi lại 1 lần.
- **Critic (chốt lại)**: plan cũ ghi "Bloom + critic độc lập" nhưng `classify_competencies` hiện KHÔNG có critic (critic chỉ ở `item_generation.py`). **Quyết định: KHÔNG thêm critic ở M2** — dùng vòng 2 tái thẩm định cho ca null là đủ; nếu Bloom lệch nhiều sau eval (G3) mới thêm critic.
- **Chương**: resolve bằng đi lên `parent_id` 1 bậc (node cha = chương); không lưu cột chapter riêng.

### G3 — Bộ eval đo chất lượng (QUAN TRỌNG NHẤT, làm cùng M2)

LLM pipeline không có thước đo thì không biết "đủ tốt". Quyết định:

1. **Bộ nhãn vàng**: 50–100 câu (từ 5 đề mẫu M6 + đề công khai) gán tay `node_id` đúng + nhãn `off_curriculum` đúng → file `tests/fixtures/exam_labeled.jsonl`.
2. **Metric** (chạy sau M2, ghi vào CI như test thường):
   - `top-1 accuracy` (map đúng node) — mục tiêu ≥ 0.85 ở cấp chương, ≥ 0.70 ở cấp node.
   - `top-3 accuracy` (node đúng nằm trong shortlist GV chốt) — mục tiêu ≥ 0.95.
   - `null-rate` (tỉ lệ ý trả null) — mục tiêu ≤ 0.15.
   - `off-curriculum precision / recall` — mục tiêu precision ≥ 0.9 (báo nhầm ít), recall ≥ 0.8.
3. **Cách chạy**: script `scripts/eval_exam_mapping.py` + pytest wrapper; kết quả in bảng theo môn/khối để thấy chỗ yếu (môn nào, cấp nào, dạng nào).

### G4 — Frontend: wire vào trang có sẵn

Repo **đã có** `frontend/src/app/(app)/exam-difficulty/page.tsx` (UI TEVI: cờ NORMAL / INFLATION_OR_LEAK / LEARNING_GAP + drawer chi tiết đề).

**Quyết định:** nối `GET /exam-papers/{id}/content-analysis` vào **drawer chi tiết đề của trang này** (thêm tab/block "Phân tích nội dung: CDI, Bloom dist, coverage, concentration, off-curriculum (cờ mềm + shortlist GV chốt), trích dẫn chương/bài") — không tạo trang mới. Phần GV chốt shortlist: form đơn giản trong cùng drawer (chọn 1 node trong shortlist → `PATCH` ai_analysis hoặc ghi override).

### G5 — Scope seed M0 (chốt môn/khối trước)

**Quyết định:** seed **Toán 6–9 trước**, tận dụng nguồn đã có `docs/Chuong_Trinh_Toan_Canh_Dieu_6_9.md` (mục lục Cánh diều 6–9, đã chia tập 1/2). Sau khi chạy được end-to-end, mở rộng thêm 1–2 môn (VD KHTN 6–9) từ `s360.cm_*`. Không seed toàn bộ cùng lúc — vừa đủ để demo + eval, tránh tốn công rà tay trên dữ liệu chưa dùng.
### G6 — Điểm còn mở (không chặn code, chốt khi đến module liên quan)

1. **Biểu diễn off-curriculum một phần**: thống nhất schema — mỗi ý có `off_curriculum_weight` (0..1, = Σ weight của node null) thay vì bool; `off_curriculum` bool chỉ bật khi toàn null. Gộp toàn đề thành `off_curriculum_weight` tổng như M3.
2. **Quyền GV chốt shortlist (override)**: hiện `_can_view_analysis` chỉ cho ADMIN/PRINCIPAL + `can_manage_question_bank`. Đề xuất: ai xem được phân tích thì được chốt, lưu kèm `confirmed_by` + `confirmed_at` (đồng bộ với `_ANALYSIS_ROLES`).
3. **Dọn unit phân mảnh cũ**: bỏ fallback `_resolve_units` thì các unit rác cũ (đã ẩn `is_active=False`) vẫn còn trong DB — seed M0 nên đánh dấu rõ/loại khỏi shortlist để tránh LLM chọn nhầm node rác.

---

## GHI CHÚ CẬP NHẬT

- 2026-08-15: bỏ `curriculum_node_anchors` khỏi core (LLM map từ bảng phẳng); vòng 2 = tái thẩm định; trích dẫn = chương/bài từ cây. Thêm PHẦN G (5 quyết định trước khi code) + G6 (3 điểm mở).
- 2026-08-15: chốt gọi thẳng Qwen (Qwen3-VL-Flash) trong code; user sẽ cấu hình API key sau — code không được chặn vì thiếu key.
- 2026-08-15: **M0 hoàn thành** — `scripts/seed_curriculum_nodes.py` + `scripts/seed_data/toan_canh_dieu_6_9.json` (31 chương Toán Cánh diều 6–9) đã seed lên Neon (inserted=31); đồng bộ schema `curriculum_units` (semester_number, is_active, unique) vào `score_focused_schema.sql` + ALTER DB. Test: `tests/test_seed_curriculum_nodes.py` + ruff xanh.
- 2026-08-15: **M1+M2+M3 hoàn thành** — (M1) `src/services/vlm.py` + config `VLM_*` (Qwen3-VL-Flash, key user cấu hình sau, fallback OCR); (M2) `build_shortlist` + `map_items`/`parse_mapped_items` (LLM map 1–3 node/ý, constrained theo shortlist) + `rejudge_null_items` (vòng 2 tái thẩm định + candidates GV); (M3) `src/schemas/exam_analysis.py` bỏ `avg_retrieval_distance`/`EvidenceRef`, thêm `NodeRef` + `off_curriculum_weight`; `content_difficulty.py` bỏ hẳn RAG/evidence cũ. Test: `tests/test_content_difficulty.py` + `tests/test_vlm_service.py` (35 test, ruff sạch, không fail mới so với baseline).
- 2026-08-15: **M4 + M5 + M6/G3 hoàn thành** — (M4) `knowledge_gap` API trả thêm `chapter`/`lesson` (resolve qua parent_id); (M5) frontend `exam-difficulty/page.tsx` wire `GET /exam-papers/{id}/content-analysis` vào drawer, thay 2 block RAG cũ bằng block 5 trục (coverage, concentration, off-curriculum cờ mềm, trích dẫn chương/bài); (M6/G3) `tests/fixtures/exam_labeled.jsonl` (42 câu nhãn vàng) + 5 đề mẫu `tests/fixtures/exam_samples/` + `scripts/eval_exam_mapping.py` (metric exact/top1/overlap/null-rate/off precision-recall, chạy real LLM sau khi có key) + `tests/test_exam_eval.py`. ESLint 0 errors; 49 test backend xanh.
- 2026-08-15: **Chạy thật + sửa 3 bug** — (1) guard `_MIN_CLASSIFY_CHARS 50→10` (câu hỏi ngắn hợp lệ bị bỏ → eval null-rate giả tạo 55%); (2) drift `exam_papers.score_type` thiếu cột → ALTER DB + DDL (chặn cả upload thật); (3) weight semantics: prompt weight là tỉ trọng TRONG ý (Σ/ý≈1) nhưng `merge_by_unit` cộng dồn theo unit → tổng > 1 vi phạm CHECK → thêm `_normalize_resolved` (chuẩn hóa tổng đề = 1). **Kết quả eval thật (DeepSeek, 42 câu)**: exact 0.95, top1 0.975, null 0.024, off-precision 1.0, off-recall 0.5 (1/2 ca off nhập nhằng → cờ mềm chờ GV). **E2E demo thành công**: đề mẫu Toán 6 → CDI 0.300, coverage 3/3 (1.0), concentration Số tự nhiên 60% (Dồn chương), off 0.0, bloom ALIGNED (40/40/20/0), exam_competencies [(121,0.6,2),(122,0.2,2),(123,0.2,1)].
- 2026-08-15: **Trang admin quản lý catalog phẳng + upload không RAG** — `src/services/curriculum_catalog.py` (dùng chung CLI + API: load/parse markdown mục lục/parse JSON/build specs/resolve subject/upsert/ẩn placeholder), `scripts/seed_curriculum_nodes.py` thành CLI mỏng, `src/api/v1/curriculum.py` (ADMIN: GET /curriculum/units, POST /curriculum/upload — JSON/markdown ghi thẳng curriculum_units KHÔNG qua Qdrant/Airflow, POST /units/{id}/toggle-active), frontend `admin/curriculum/page.tsx` + menu sidebar. Test thật: parse file mục lục Cánh diều gốc → 31 chương, upsert idempotent (0 inserted/31 updated).
- 2026-08-15: **Nạp sách giáo khoa tự tách mục lục** — `src/services/curriculum_ingest.py` (upload chính cuốn SGK PDF/DOCX/TXT/MD → pipeline đọc TOC: bookmark PDF → text-layer regex → VLM fallback `vlm.read_pdf_toc`, sinh node chương C1.. + bài con {chương}_B{n} theo parent_code, upsert cây 2 bước, `dry_run` xem trước trước khi ghi), API `POST /curriculum/ingest-book` (subject_code + grade + semester tự đoán từ tên file + include_lessons + dry_run), schema `BookIngestResult`/chapter/lesson, frontend section "Nạp sách giáo khoa" (Trích xuất → xem cây → Lưu). Không còn phải tự tổng hợp file mục lục tay cho sách có bookmark/text. Test: `tests/test_curriculum_ingest.py` (12 test, ruff sạch).
- 2026-08-15: **Chống 500 khi VLM provider 5xx trong ingest sách** — (1) `vlm._chat_completions` retry 1 lần khi HTTP ≥500 (vd 503 provider tạm quá tải); (2) `extract_toc_from_pdf` bắt `VlmUnavailableError` → degrade về `([], "pdf")` → API trả 422 thông báo rõ ("sách không bookmark/text-layer và VLM thất bại — thử lại hoặc dùng file có bookmark/markdown") thay vì Internal Server Error. Test: retry 5xx + degrade VLM fail (46 test liên quan pass).
- 2026-08-15: **Lưu từ preview không trích lại file** — lỗi thực tế: "Trích xuất" (dry_run) thành công nhưng "Lưu vào bảng" chạy LẠI pipeline trích xuất (gọi lại VLM 8 trang → dễ 503). Sửa: `POST /curriculum/ingest-book/commit` nhận JSON cây chương/bài từ preview + `save_catalog_from_preview` (upsert thẳng theo code, KHÔNG trích lại, KHÔNG VLM, idempotent) — frontend gửi `bookPreview.chapters`, nút Lưu không cần file. Test: `save_catalog_from_preview` upsert + empty-raises (15 test ingest pass, ruff + eslint sạch).
- 2026-08-16: **Trích xuất PDF đi thẳng VLM (Qwen3-VL-Flash), bỏ bookmark/regex** — vì regex quét toàn bộ text-layer nhặt cả ruột sách (8 chương/23 bài sai, placeholder "Tên chương"): `extract_toc_from_pdf` giờ render ảnh 8 trang đầu → VLM nhận diện trang MỤC LỤC và xuất JSON cấu trúc (`{"toc_page": false/true, "chapters":[{"name","lessons":[{"name","kind":"lesson|phu"}]}]}`), gom nhiều trang, dedupe. Mọi nguồn (VLM/DOCX/TXT) qua `_normalize_title` (bỏ số trang), `_is_placeholder` (loại "Tên chương/Tên bài"), `_is_phu_title` (gắn cờ Ôn tập/Kiểm tra/Hoạt động), `_sanity_check` (cảnh báo số chương>6, bài/chương>30, trùng tên → hiện ở preview). **Schema**: thêm cột `curriculum_units.is_phu` (model + ALTER DB dev + DDL score_focused_schema.sql, không Alembic theo yêu cầu); `build_shortlist` lọc `is_phu=false` (node phụ giữ trong cây nhưng không map đề). **Bỏ seed Cánh diều**: xóa `scripts/seed_curriculum_nodes.py`, `scripts/seed_data/toan_canh_dieu_6_9.json`, `tests/test_seed_curriculum_nodes.py`, xóa `load_catalog`/`DEFAULT_DATA_PATH` khỏi `curriculum_catalog.py` — dữ liệu chỉ vào qua "Nạp sách giáo khoa". Frontend: badge "Phụ" + banner warnings + nguồn trích. **Smoke test thật (VLM)**: PDF giả lập trang MỤC LỤC → 2 chương đúng, "Ôn tập chương I" tự gắn is_phu. 75 test liên quan pass; full suite 623 pass (baseline 48 fail + 3 error pre-existing không đụng); ruff + eslint sạch.
- 2026-08-16: **Nạp sách bất đồng bộ (không giữ request 5 phút)** — `POST /curriculum/ingest-book` giờ trả `job_id` NGAY (202, `BookIngestJobRead`): job VLM chạy thread nền (job store in-memory + lock + TTL 15 phút), frontend poll `GET /curriculum/ingest-book/jobs/{job_id}` mỗi 2s (running | success + result | failed + error, timeout 3 phút). `POST /curriculum/ingest-book/commit` giữ sync (chỉ upsert DB, không VLM). Smoke test thật: POST 0.0s, VLM nền 12s, poll nhận 2 chương đúng. ESLint sạch.
