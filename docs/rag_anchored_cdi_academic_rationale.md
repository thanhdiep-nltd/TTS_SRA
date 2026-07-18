# CƠ SỞ HỌC THUẬT — RAG-ANCHORED CDI (NÂNG CẤP PHÂN TÍCH NỘI DUNG ĐỀ THI)

> Tài liệu này giải thích **vì sao** pipeline tính CDI (Content Difficulty Index) cho TEVI được nâng cấp như hiện tại — mỗi thay đổi kỹ thuật bám theo một nguyên lý đã được kiểm chứng trong khoa học đo lường giáo dục (educational measurement/psychometrics) hoặc NLP sinh nội dung có kiểm chứng (grounded generation), không phải chỉnh sửa tùy hứng. Dùng để trình bày với mentor/Ban giám khảo.
>
> Tài liệu thiết kế gốc của TEVI (mô hình toán EDI/CDI/divergence): [exam_triangulation_design.md](exam_triangulation_design.md). Tài liệu học thuật song song cho luồng sinh câu hỏi AI (cùng gia đình nguyên lý — grounding, human-in-the-loop): [question_generation_v2_academic_rationale.md](question_generation_v2_academic_rationale.md). Code hiện thực: [src/services/content_difficulty.py](../src/services/content_difficulty.py), [src/schemas/exam_analysis.py](../src/schemas/exam_analysis.py).

---

## 1. Vấn đề xuất phát

Pipeline CDI bản đầu (xem [exam_triangulation_design.md](exam_triangulation_design.md)) đã giải quyết được vòng lặp logic "độ khó suy từ chính điểm số" bằng cách thêm một mỏ neo **nội dung** độc lập (CDI, dựa trên thang Bloom). Nhưng khi hiện thực, 3 lớp vấn đề mới xuất hiện — kinh điển của mọi hệ dùng LLM để phân loại/gắn nhãn nội dung ở quy mô lớn:

| Lớp vấn đề | Biểu hiện cụ thể | Rủi ro học thuật |
|---|---|---|
| **Phân mảnh phân loại (taxonomy fragmentation)** | LLM tự do đặt tên chủ đề mỗi lần phân tích — "Số nguyên", "số nguyên và phép cộng", "Phép tính với số nguyên" đều tạo `CurriculumUnit` mới | Ngân hàng câu hỏi + bảng lỗi tư duy (misconceptions) khóa theo `unit_id` bị phân tán, không thể tổng hợp thống kê theo đúng 1 chuẩn chương trình |
| **Mỏ neo tự phong (self-referential anchor)** | Tên gọi "RAG-anchored CDI" nhưng bản đầu KHÔNG có bước đối chiếu SGK nào — CDI chỉ dựa vào việc LLM tự chấm mức Bloom | CDI không có bằng chứng ngoại vi thật; nếu LLM chấm sai mức Bloom, không có cơ chế nào phát hiện — đúng loại vấn đề "vòng lặp logic" mà chính TEVI được sinh ra để phá vỡ, nay tái diễn ở tầng phân loại nội dung |
| **Thiếu chỉ số hợp lệ hóa nội dung (content validity indicators)** | Không đo được đề bám sát chương trình đến đâu (coverage) hay có dồn quá nhiều vào 1 chủ đề không (concentration) | Không phát hiện được "đề lệch tủ"/"dạy tủ" dù đã có EDI/CDI — một dạng đe dọa content validity kinh điển mà đo lường giáo dục quan tâm hàng đầu |

---

## 2. Luồng xử lý tổng quan (trước → sau)

```
TRƯỚC:
GV upload đề → OCR → LLM chấm (topic tự do, bloom_level, weight)
             → tạo/lấy CurriculumUnit theo topic (KHÔNG kiểm tra trùng ngữ nghĩa)
             → CDI = Σ(bloom×weight)/Σweight/6
             → lưu content_difficulty (KHÔNG có bằng chứng SGK nào)

SAU:
GV upload đề → OCR → tải catalog curriculum_units có sẵn (môn+khối)
             → LLM chấm CÓ RÀNG BUỘC: chọn unit_code từ catalog (hoặc null nếu không khớp)
                                     + trích excerpt nguyên văn cho mỗi ý
             → CDI = Σ(bloom×weight)/Σweight/6  (KHÔNG đổi công thức — vẫn tam giác hóa được với EDI)
             → đối chiếu RAG (Qdrant) TỪNG Ý bằng (topic + excerpt) → bằng chứng SGK thật hoặc "ngoài chương trình"
             → tính coverage (phủ bao nhiêu % catalog) + concentration ("lệch tủ" chủ đề nào)
             → lưu vào exam_papers.ai_analysis.content_analysis (versioned) — hiển thị drill-down cho BGH
```

**3 điểm dễ hiểu nhầm khi trình bày:**
- CDI (con số 0-1, dùng để tam giác hóa với EDI) **không đổi công thức** — vẫn là trung bình Bloom có trọng số ([`cdi_from_bloom_mix`](../src/services/content_difficulty.py#L93)). Cái thay đổi là **cách xác định chủ đề** (constrained thay vì tự do) và **thêm 2 chỉ số mới hoàn toàn độc lập với CDI** (coverage, concentration) — không phải thay thế CDI.
- RAG (Qdrant) trong bản nâng cấp này dùng để **đối chiếu bằng chứng cho từng câu/ý**, không phải để "sinh" nội dung — khác vai trò RAG ở luồng sinh câu hỏi ([question_generation_v2_academic_rationale.md](question_generation_v2_academic_rationale.md) §4.1), nơi RAG cấp ngữ liệu đầu vào cho LLM.
- Câu/ý không khớp catalog **không bị loại** — vẫn fallback tạo `CurriculumUnit` từ tên LLM tự đặt như bản cũ (chấp nhận phân mảnh cho môn/khối chưa seed catalog), chỉ là giờ có cờ `matched_catalog=False` để phân biệt rõ với ý đã neo đúng.

---

## 3. Nguyên lý thiết kế xuyên suốt

**Kiểm chứng khách quan trước, mềm dẻo sau.** Giống triết lý guardrail cứng/mềm ở luồng sinh câu hỏi: "khớp `unit_code` trong catalog" và "có bằng chứng SGK đạt ngưỡng điểm tương đồng" là hai điều kiện *kiểm chứng được bằng thuật toán*; "câu này có thật sự đúng 1 chủ đề duy nhất theo nghĩa sư phạm" vẫn là phán đoán chuyên môn — hệ không tự quyết định điều đó, chỉ gắn cờ (`matched_catalog`, `off_curriculum`) để BGH/Trưởng bộ môn ưu tiên rà soát.

**Fail-soft tuyệt đối với RAG.** Đối chiếu SGK là tín hiệu bổ sung, không phải điều kiện tiên quyết để tính CDI — Qdrant/embedding sidecar gián đoạn thì CDI vẫn tính bình thường (`rag_available=False`), tránh biến 1 pipeline chạy nền (BackgroundTasks) thành điểm hỏng dây chuyền (single point of failure) chỉ vì một dịch vụ phụ trợ tạm ngưng.

**Không đổi bản chất human-in-the-loop đã có của TEVI.** Cờ `flag` (VALID/INFLATION_OR_LEAK/LEARNING_GAP/...) và mức tin cậy (`confidence`) ở tầng tam giác hóa ([exam_triangulation_design.md](exam_triangulation_design.md) §2.4) không đổi — nâng cấp này chỉ làm cho INPUT của tầng đó (CDI + dữ liệu đứng sau nó) đáng tin hơn.

---

## 4. Từng cải tiến và cơ sở học thuật

### 4.1. Phân loại có ràng buộc (constrained classification) — chống phân mảnh taxonomy

**Trước:** LLM tự do đặt `topic` bằng ngôn ngữ tự nhiên, không có bảng chuẩn nào để đối chiếu.
**Sau:** [`build_classify_prompt`](../src/services/content_difficulty.py#L62) chèn danh sách chuẩn chương trình (`curriculum_units` đã seed cho môn+khối) vào prompt, buộc LLM chọn `unit_code` từ danh sách đó (hoặc `null` nếu không khớp) — [`classify_competencies`](../src/services/content_difficulty.py#L157) sau đó **loại bỏ mọi mã LLM tự bịa** không có trong catalog (chống hallucination ở tầng phân loại, không chỉ ở tầng nội dung).

**Cơ sở:** Đây là ứng dụng trực tiếp nguyên lý *bảng đặc tả đề thi* (Table of Specifications/Test Blueprint) trong khảo thí chuẩn hóa — một hệ thống phân loại nội dung chỉ có giá trị thống kê khi mọi câu hỏi được ánh xạ **nhất quán** về cùng một tập hạng mục cố định (Notar, Zuelke, Wilson & Yunker, 2004, *The Table of Specifications: Ensuring Accountability in Teacher Made Tests*). Không có ràng buộc này, mọi phép cộng dồn theo `unit_id` (coverage, misconception theo chủ đề, thống kê p-value/discrimination theo unit ở vòng hiệu chỉnh) đều sai vì mẫu số (số lượng "chủ đề" thực) không ổn định giữa các lần phân tích.

### 4.2. Đối chiếu bằng chứng SGK cho TỪNG Ý (grounded evidence per item)

Mỗi ý sau khi phân loại được truy hồi ngữ liệu SGK độc lập qua [`_best_evidence`](../src/services/content_difficulty.py#L323) (dùng `topic + excerpt` làm query — xem [`_evidence_query`](../src/services/content_difficulty.py#L318)), lấy hit tốt nhất đã qua ngưỡng `retrieval_score_floor` của Qdrant. Không có hit nào → ứng viên "ngoài chương trình".

**Cơ sở:** Cùng gốc lý thuyết *faithfulness* trong kiến trúc RAG (Lewis et al., 2020, *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*) đã dùng cho luồng sinh câu hỏi — nhưng áp dụng theo chiều ngược: thay vì RAG cấp ngữ liệu để LLM SINH nội dung, ở đây RAG dùng để **XÁC MINH** nội dung đã có (đề thi thật) có neo được vào SGK hay không. Đây là điểm khác biệt cốt lõi khiến tên gọi "RAG-anchored" trở thành sự thật — bản trước hoàn toàn không có bước này.

### 4.3. Độ phủ chương trình (content coverage)

[`_coverage`](../src/services/content_difficulty.py#L369) tính tỉ lệ chủ đề trong catalog thực sự được đề "chạm tới" (`matched = số unit có ít nhất 1 ý weight > 0` / `catalog_total`), liệt kê đủ mọi unit kể cả những unit đề không đề cập (`weight=0`).

**Cơ sở:** Đây là chỉ số *content validity evidence* theo đúng khung của *Standards for Educational and Psychological Testing* (AERA, APA & NCME, 2014) — bằng chứng giá trị nội dung đòi hỏi phải chứng minh được bài kiểm tra lấy mẫu đại diện từ toàn bộ miền nội dung (domain) cần đo, không chỉ một phần. Về mặt định lượng, đây cũng chính là ý tưởng của *chỉ số tương thích chương trình* (curriculum/content alignment index — Porter, A. C., 2002, *Measuring the Content of Instruction: Uses in Research and Practice*, Educational Researcher): so khớp nội dung đã dạy/kiểm tra với nội dung "dự định" (intended curriculum) một cách có thể đo lường được, thay vì chỉ dựa vào cảm nhận chủ quan của người ra đề.

### 4.4. Mức độ tập trung chủ đề — "lệch tủ" (concentration)

[`_concentration`](../src/services/content_difficulty.py#L384) tính tỉ trọng của chủ đề chiếm nhiều điểm số nhất trên tổng đề (`top_share`); vượt ngưỡng `_CONCENTRATION_SHARE = 0.6` → gắn cờ `is_concentrated`. Tính trên **toàn bộ** ý đã neo (kể cả unit fallback ngoài catalog) — vì một đề dồn hết vào 1 chủ đề vẫn là "lệch tủ" dù chủ đề đó chưa nằm trong catalog đã seed.

**Cơ sở:** Liên hệ trực tiếp hiện tượng *curriculum narrowing*/"dạy tủ, học tủ" (teaching to the test) đã được nghiên cứu rộng trong đo lường giáo dục — khi một đề thi (hoặc một chuỗi đề lặp lại) dồn trọng số bất thường vào một phạm vi hẹp, nó làm sai lệch suy luận về năng lực học sinh trên toàn bộ chương trình (Popham, W. J., 2001, *"Teaching to the Test"? What you need to know*, Educational Leadership). Đây là tín hiệu **độc lập với CDI** (một đề có thể vừa "khó" theo Bloom vừa "lệch tủ" theo phạm vi — hai trục đo khác nhau, không thay thế nhau).

### 4.5. Cờ "ngoài chương trình" (off-curriculum flag)

`off_curriculum` (True/False/None) gắn cho từng ý: `False` khi RAG xác nhận có bằng chứng SGK, `True` khi RAG hoạt động nhưng không tìm thấy hit nào, `None` khi RAG không khả dụng (chưa xác định được) — xem [`_attach_evidence`](../src/services/content_difficulty.py#L434).

**Cơ sở:** Đây là công cụ phát hiện sớm một trong hai mối đe dọa giá trị (validity threats) kinh điển theo khung của Messick (1989, *Validity*, in R. L. Linn (Ed.), *Educational Measurement*, 3rd ed.) — **construct-irrelevant content**: đề đưa vào nội dung nằm ngoài phạm vi cần đo (ngoài chương trình đã học), khiến điểm số phản ánh sai năng lực thực sự đang muốn đánh giá. Việc tách 3 trạng thái (đúng/sai/chưa xác định) thay vì chỉ 2 (đúng/sai) là cố ý — tránh kết luận sai khi RAG chưa chạy được (một câu chưa kiểm tra không đồng nghĩa với câu sai phạm vi).

### 4.6. Kết nối với tam giác hóa TEVI (EDI/CDI/divergence)

CDI vẫn được tính và ghi vào `exam_papers.content_difficulty` y hệt công thức cũ — nhưng giờ **đứng sau** một bước phân loại đã được ràng buộc + có bằng chứng đối chiếu, thay vì một con số hoàn toàn "tự phong" của LLM. Điều này trực tiếp củng cố tiền đề của toàn bộ thiết kế tam giác hóa ([exam_triangulation_design.md](exam_triangulation_design.md) §1.2): CDI phải là một **mỏ neo ngoại sinh đáng tin cậy** để phép so sánh `D = EDI − CDI` có ý nghĩa. Một CDI được tính từ taxonomy phân mảnh và không có bằng chứng gì là một mỏ neo yếu — nâng cấp này không thay đổi mô hình toán của TEVI, mà củng cố độ tin cậy của một trong hai biến đầu vào cốt lõi của nó.

### 4.7. Fail-soft & versioned schema — kỷ luật công trình (engineering rigor) song hành với học thuật

Hai quyết định kỹ thuật tuy không xuất phát từ tài liệu đo lường giáo dục nhưng **bảo vệ toàn vẹn của các bằng chứng học thuật ở trên** khỏi bị hạ tầng phá vỡ:
- [`_collect_evidence`](../src/services/content_difficulty.py#L333) bắt lỗi Qdrant/embedding sidecar ngay tại chỗ, trả `rag_available=False` thay vì để lỗi lan ra làm hỏng cả pipeline nền (BackgroundTasks) — nguyên lý *graceful degradation*, đảm bảo dữ liệu content-validity (dù không đầy đủ RAG) vẫn được ghi lại thay vì mất trắng.
- `ai_analysis.content_analysis.version = 1` ([src/schemas/exam_analysis.py](../src/schemas/exam_analysis.py)) cho phép mở rộng shape JSON sau này (thêm `coverage_depth`, `structural` như §2.2 của thiết kế TEVI gốc dự kiến) mà không phá dữ liệu đã lưu của các đề cũ.

---

## 5. So sánh trước/sau

| Đặc điểm | Bản trước | Bản nâng cấp (RAG-anchored) |
|---|---|---|
| Xác định chủ đề | LLM tự đặt tên tự do | Chọn từ catalog chuẩn CT (constrained), fallback có cờ rõ ràng |
| Bằng chứng SGK | Không có | Đối chiếu Qdrant từng ý, kèm nguồn (heading/source_md) + điểm tương đồng |
| Độ phủ chương trình | Không đo được | `coverage` (matched/catalog_total, per-unit weight) |
| Phát hiện lệch tủ | Không có | `concentration` (top_share + ngưỡng 0.6) |
| Ý ngoài chương trình | Không phát hiện được | `off_curriculum` 3 trạng thái (đúng/sai/chưa xác định) |
| Độ tin cậy của CDI (đầu vào tam giác hóa) | Tự phong, không kiểm chứng | Đứng sau constrained classification + RAG evidence |
| Khả năng chịu lỗi hạ tầng | — | Fail-soft khi Qdrant/embedding gián đoạn, không chặn CDI |

---

## 6. Hạn chế đã biết & hướng phát triển tiếp theo

Trình bày minh bạch với mentor/BGK — đây là các đánh đổi có chủ đích hoặc phát hiện qua code review, chưa xử lý trong bản này:

- **Fallback vẫn tạo `CurriculumUnit` cho ý không khớp catalog** (giữ hành vi cũ, quyết định có chủ đích cho môn/khối chưa seed đủ chuẩn CT) — về lâu dài nên có bước rà soát định kỳ các unit "fallback" để gộp/chuẩn hóa thủ công, tránh catalog phình dần theo thời gian.
- **`analyze_exam_paper` hiện vượt quy ước 30 dòng/hàm** của dự án (đã tách 6 helper thuần nhưng hàm điều phối chính còn dài) — cần tách thêm 1 lớp orchestration trong đợt refactor tiếp theo.
- **Đối chiếu RAG chạy tuần tự cho từng ý** thay vì song song hóa (đề nhiều ý → nhiều lượt gọi Qdrant nối tiếp) — có thể tối ưu bằng `ThreadPoolExecutor` giống pattern đã dùng ở luồng sinh câu hỏi khi cần giảm độ trễ.
- **Phạm vi RBAC của toàn bộ tài nguyên `exam_papers`** (không chỉ `ai_analysis`) hiện chưa giới hạn theo môn ở một số endpoint — một hạng mục bảo mật rộng hơn, nằm ngoài phạm vi tính năng CDI, để xử lý riêng.

---

## 7. Tài liệu tham khảo

- AERA, APA, & NCME (2014). *Standards for Educational and Psychological Testing.* American Educational Research Association.
- Lewis, P. et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* (RAG, faithfulness).
- Messick, S. (1989). *Validity.* In R. L. Linn (Ed.), *Educational Measurement* (3rd ed.). American Council on Education/Macmillan.
- Notar, C. E., Zuelke, D. C., Wilson, J. D., & Yunker, B. D. (2004). *The Table of Specifications: Ensuring Accountability in Teacher Made Tests.* Journal of Instructional Psychology.
- Popham, W. J. (2001). *"Teaching to the Test"? What you need to know.* Educational Leadership, 58(6), 16–20.
- Porter, A. C. (2002). *Measuring the Content of Instruction: Uses in Research and Practice.* Educational Researcher, 31(7), 3–14.
