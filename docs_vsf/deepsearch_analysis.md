# PHÂN TÍCH BÀI NGHIÊN CỨU — Đánh giá Độ khó Đề thi bằng LLM + Lý thuyết Khảo thí Đa chiều

> Nguồn: `docs_vsf/deepsearch_about_task.md`
> Mục đích: rút bài học áp dụng vào dự án TTS_SRA, mapping vào `docs_vsf/plan_exam_learning_analytics.md`.
> Quyết định kiến trúc: **giữ MVP hiện tại (EDI/CDI đơn giản) rồi nâng dần** — không chuyển sang IRT/Bayesian ngay.

---

## 1. Tóm tắt bài nghiên cứu

Bài đưa ra khung phương pháp luận hoàn chỉnh để đánh giá độ khó đề thi tự động, gồm các trụ cột:

| Trụ cột | Nội dung |
|---|---|
| **Lý thuyết đo lường** | CTT (`p+`) → IRT (Rasch 1PL / 3PL: độ khó `b_i`, phân biệt `a_i`, đoán mò `c_i`). Bloom là trục định tính, **không đồng nhất HOCS = khó thống kê**. |
| **Concept Knowledge Graph** | Từ SGK + giáo án xây đồ thị (nút concept/rule/skill, cạnh `prerequisite_of`/`part_of`/`applied_in`). 2 chỉ số: **Topological Depth** + **Retrieval Semantic Distance**. |
| **Phân biệt LMS vs thi trên lớp** | LMS = dữ liệu **vi mô** (response time, attempts, distractor); thi trên lớp = **vĩ mô** (neo năng lực `θ`). |
| **4 kỹ thuật ước lượng tiên nghiệm (cold-start)** | Pairwise (Bradley-Terry/Glicko-2), OPR (distractor), CoT trace, Agentic IRT simulation. |
| **Bayesian IRT** | Hợp nhất tiên nghiệm `b_i ~ N(μ0, σ0²)` + thực nghiệm qua 3 trạng thái cold-start → sparse → dense. |
| **Đánh giá toàn đề** | TIF + SEM + Curriculum Blueprint Alignment + phân bố Bloom chuẩn 40/30/20/10. |

---

## 2. Đối chiếu với hiện trạng dự án

Dự án **đã có một phần** (TEVI, CDI từ Bloom+LLM+RAG SGK, EWS, RAG Qdrant). Bài nghiên cứu chỉ ra **3 điểm hiện tại đang "đơn giản hóa"**:

| Hiện trạng | Bài nghiên cứu đề xuất | GAP |
|---|---|---|
| CDI = Bloom-weighted (`content_difficulty.py`) | Thêm Retrieval Semantic Distance + Pairwise | CDI chưa đo "khoảng cách câu hỏi vs SGK" |
| `curriculum_units` là cây phẳng | Concept KG có cạnh `prerequisite` | Chưa phát hiện "hổng kiến thức tiền đề" |
| EDI = `1 - facility` (`exam_validity.py`) | IRT/Bayesian | Cần ma trận phản hồi item-level (DB chưa có) |

---

## 3. Bài học → mapping vào plan (3 mức ưu tiên)

### ✅ Mức A — Áp dụng ngay (chi phí thấp, giá trị cao)

| # | Bài học | Áp dụng vào module nào | Cụ thể |
|---|---|---|---|
| A1 | **Retrieval Semantic Distance** | M1 (CDI) | Bổ sung đo embedding câu hỏi vs SGK hit trong `content_difficulty.py` — thêm vào `ai_analysis`, không thay Bloom. |
| A2 | **Phân biệt LMS vi mô vs thi vĩ mô** | M0.1 + M3 | Khớp chính xác yêu cầu "LMS chứng minh nỗ lực làm lâu nhưng điểm tệ / học qua loa". Củng cố thêm `time_spent_sec`/`attempt_count` + `lms_evidence.py`. |
| A3 | **Curriculum Blueprint Alignment** | M1/M2 | Đối soát đề vs giáo án, phát hiện "blind spot" (vùng kiến thức bị bỏ quên). `curriculum_units` đã có. |
| A4 | **Phân bố Bloom chuẩn 40/30/20/10** | M1 | Làm tham chiếu trong báo cáo độ khó (so sánh phân bố thực tế vs chuẩn). |

### 🟡 Mức B — Trung hạn (cần dữ liệu/refactor, làm sau MVP)

| # | Bài học | Áp dụng | Ghi chú |
|---|---|---|---|
| B1 | **Pairwise/Glicko-2** | M1 | Thay chấm Bloom tuyệt đối → ổn định CDI. Giải quyết đúng nhược điểm "LLM chấm điểm tuyệt đối kém ổn định". |
| B2 | **Concept KG có cạnh prerequisite** | M0/M2 | Thêm bảng `curriculum_unit_prerequisites` → phát hiện "hổng kiến thức tiền đề". |
| B3 | **Bayesian IRT** | M1/M4 | Thay `EDI = 1 - facility`; dùng năng lực `θ` cho pass/fail. Cần ma trận phản hồi item-level. |

### 🔴 Mức C — Để giai đoạn sau (nặng / ngoài MVP)

| # | Bài học | Lý do hoãn |
|---|---|---|
| C1 | **Agentic IRT simulation** | Tốn LLM nhiều, phức tạp. |
| C2 | **OPR (distractor plausibility)** | Cần dữ liệu distractor — đề tự luận VN ít trắc nghiệm chuẩn. |
| C3 | **Full TIF/SEM** | Cần ma trận phản hồi item-level mà DB chưa có. |

---

## 4. Quyết định kiến trúc (đã chốt)

- **Giữ MVP hiện tại**: EDI (`1 - facility`) + CDI (Bloom-weighted) — đơn giản, đã chạy được.
- **Nâng dần theo lộ trình**: Mức A ngay trong các module M0/M1/M3 hiện tại → Mức B khi có dữ liệu item-level → Mức C tùy nhu cầu.
- **Không chuyển sang IRT/Bayesian ngay** vì DB hiện chỉ lưu điểm tổng mỗi cột, chưa có ma trận phản hồi từng câu.

---

## 5. Tác động cụ thể lên `plan_exam_learning_analytics.md`

| Module trong plan | Thay đổi từ bài nghiên cứu |
|---|---|
| **M0** | Thêm (tùy chọn, Mức B) bảng `curriculum_unit_prerequisites` cho Concept KG. |
| **M1** | CDI bổ sung Retrieval Semantic Distance (A1) + báo cáo phân bố Bloom chuẩn (A4). |
| **M3** | Khẳng định thêm `time_spent_sec`/`attempt_count` (A2) — đúng như plan đã có. |
| **M4** | (Mức B) dùng năng lực `θ` thay điểm thô khi có IRT. |

---

## 6. Kết luận

Bài nghiên cứu **xác nhận hướng đi đúng** của dự án (TEVI/CDI/EWS/RAG) và cung cấp **lộ trình nâng cấp có thứ tự**: trước mắt bổ sung Retrieval Semantic Distance + phân biệt LMS vi mô/vĩ mô (Mức A), về lâu dài Pairwise + Concept KG + Bayesian IRT (Mức B). Các kỹ thuật nặng (Agentic IRT, OPR, full TIF) để giai đoạn sau.