# CƠ SỞ HỌC THUẬT — NÂNG CẤP LUỒNG SINH CÂU HỎI AI (v2)

> Tài liệu này giải thích **vì sao** luồng sinh câu hỏi bằng AI (RAG) được thiết kế lại như hiện tại — mỗi thay đổi kỹ thuật đều bám theo một nguyên lý đã được kiểm chứng trong khoa học đo lường giáo dục (educational measurement) hoặc nghiên cứu AI/NLP, chứ không phải chỉnh sửa tùy hứng. Dùng để trình bày với mentor/Ban giám khảo.
>
> Tài liệu kỹ thuật đi kèm: [exam_generation_design.md](exam_generation_design.md) (kiến trúc, API, mô hình dữ liệu). Code hiện thực: [src/services/item_generation.py](../src/services/item_generation.py), [src/services/item_calibration.py](../src/services/item_calibration.py).

---

## 1. Vấn đề xuất phát

Một hệ sinh câu hỏi bằng LLM+RAG "chạy được" khác với một hệ **đáng tin cậy để đưa vào đánh giá học sinh thật**. Rà soát ban đầu cho thấy 3 lớp vấn đề kinh điển của mọi hệ AI-sinh-nội-dung-đánh-giá:

| Lớp vấn đề | Biểu hiện cụ thể | Rủi ro học thuật |
|---|---|---|
| **Ảo giác (hallucination)** | Guardrail "bám nguồn" chỉ kiểm tra câu trích dẫn không rỗng, không đối chiếu với SGK thật | Câu hỏi ngoài chương trình, sai kiến thức |
| **Tự kiểm định vòng tròn** | LLM được giao "sinh câu mức Bloom X" rồi tự báo cáo lại đúng mức X | Không có tín hiệu độc lập nào xác nhận độ khó nhận thức thật |
| **Chất lượng distractor (đáp án nhiễu) thấp** | Không có ràng buộc nào về việc phương án sai phải hợp lý | Câu hỏi dễ đoán bằng loại trừ, không đo được hiểu biết thật |

Ba lớp vấn đề này **không phải đặc thù của dự án** — chúng là chủ đề nghiên cứu tích cực trong cả hai ngành: *đo lường giáo dục* (educational measurement/psychometrics) và *NLP sinh nội dung có kiểm chứng* (grounded generation). Thiết kế v2 áp trực tiếp các giải pháp đã được kiểm chứng của hai ngành này vào một hệ thống thực tế.

---

## 2. Luồng xử lý tổng quan (pipeline)

Toàn bộ luồng nằm trong một hàm duy nhất — [`generate_items()`](../src/services/item_generation.py#L446), gọi RAG **đúng một lần** ở đầu; không có bước "gọi lại RAG để xác thực" — việc xác thực ở bước 4 là so khớp chuỗi nội bộ với chính nội dung đã lấy về, không phải một vòng truy vấn RAG mới.

```
GV chọn: môn, khối, chuẩn CT (chương/bài), mức Bloom, loại câu, số lượng
        │
        ▼
① Truy vấn RAG (Qdrant) — MỘT LẦN DUY NHẤT
   Lấy các đoạn SGK liên quan → tạo 2 bản ngữ cảnh từ CÙNG một kết quả:
     • context           (có nhãn nguồn "[Nguồn i: chương — mục]") → đưa vào prompt cho LLM
     • grounding_context  (KHÔNG nhãn)                              → chỉ dùng để xác thực ở bước ④
   Không tìm được gì → dừng lại, báo lỗi nền (không "treo" âm thầm)
        │
        ▼
② Gọi LLM sinh câu — MỘT LẦN DUY NHẤT
   Sinh dư ~50% số câu cần (cần 3 → xin ~5), kèm context + mức Bloom yêu cầu
   + danh sách lỗi tư duy phổ biến (misconception) của chủ đề nếu có
        │
        ▼
③ Guardrail CỨNG (logic thuần, không gọi LLM/RAG lại) — loại câu không đạt
     • Quote có thật sự khớp (fuzzy) với grounding_context không? (chống ảo giác)
     • Cấu trúc đáp án có hợp lệ không? (đúng 4 lựa chọn A-D, không "tất cả đáp án trên"...)
   → giữ lại đúng `count` câu đầu tiên đạt
        │
        ▼
④ 3 tín hiệu MỀM — chạy SONG SONG cho từng câu còn lại (không loại câu, chỉ gắn cờ ưu tiên rà soát)
     • Tự giải lại độc lập (self-consistency)
     • Phân loại Bloom độc lập (không được biết mức đã yêu cầu)
     • Agent phản biện (critic) chấm theo rubric khảo thí
        │
        ▼
⑤ Dedup — so cosine similarity embedding với các câu đã có trong cùng chuẩn CT
        │
        ▼
⑥ Lưu vào kho ở trạng thái DRAFT, kèm đầy đủ provenance (nguồn RAG, 3 tín hiệu mềm, dedup)
   → CHƯA dùng được ngay — chờ Trưởng bộ môn duyệt (APPROVED) mới vào đề thi thật
        │
        ▼
⑦ (Sau khi dùng trong đề thi thật) Vòng hiệu chỉnh CTT — p-value, discrimination
   → tự gắn cờ câu "bệnh" → khuyến nghị RETIRE/REVIEW (xem mục 4.10)
```

**3 điểm dễ hiểu nhầm, cần lưu ý khi trình bày:**
- RAG **không** chạy lại sau khi LLM sinh câu — "xác thực" (bước ③) là so chuỗi (`difflib`) với ngữ cảnh đã có sẵn từ bước ①, không phải một truy vấn RAG/LLM mới.
- Guardrail cứng và 3 tín hiệu mềm (bước ④) là **hai lượt gọi khác nhau, tách biệt hoàn toàn**: cứng chạy trước để lọc câu, mềm chạy sau chỉ trên các câu đã qua lọc, và không bao giờ dùng để loại câu.
- Một câu AI sinh ra **không "kết thúc" ở bước ⑥** — nó chỉ thực sự được xác nhận chất lượng sau khi có dữ liệu thi thật quay lại qua bước ⑦ (mục 4.10).

---

## 3. Nguyên lý thiết kế xuyên suốt

**AI đề xuất — con người quyết định (human-in-the-loop).** Mọi câu AI sinh ra luôn ở trạng thái `DRAFT`, không bao giờ vào đề thi thật nếu chưa qua duyệt của Trưởng bộ môn (`APPROVED`). Đây là nguyên tắc trách nhiệm giải trình (accountability) bắt buộc với mọi hệ thống AI tác động đến đánh giá con người — AI không được phép là người quyết định cuối cùng về nội dung dùng để chấm điểm học sinh.

**Guardrail cứng ≠ guardrail mềm.** Hệ phân biệt rõ hai loại tín hiệu:
- **Guardrail cứng** (loại câu ngay): chỉ áp dụng cho thứ *có thể kiểm chứng khách quan bằng logic/thuật toán* — câu có bám nguồn SGK thật không, cấu trúc đáp án có hợp lệ không.
- **Cờ mềm** (ưu tiên rà soát, không loại câu): áp dụng cho thứ *cần phán đoán chuyên môn* — mức Bloom có đúng không, chất lượng sư phạm có ổn không. Đây là ranh giới quan trọng: không để AI tự quyết định thứ đòi hỏi chuyên môn con người, nhưng vẫn dùng AI để **ưu tiên hóa** khối lượng công việc rà soát của Trưởng bộ môn.

---

## 4. Từng cải tiến và cơ sở học thuật

### 4.1. Grounding kiểm chứng thật (chống ảo giác RAG)

**Trước:** `is_grounded()` chỉ kiểm tra `grounded_quotes` không rỗng — LLM có thể bịa trích dẫn và vẫn qua.
**Sau:** Đối chiếu từng quote với nội dung SGK thực tế đã truy xuất (chuẩn hóa Unicode NFC + khoảng trắng, cho phép sai khác nhỏ qua `difflib` longest-match ratio ≥ 0.8).

**Cơ sở:** Đây chính là vấn đề *faithfulness* (tính trung thực với nguồn) trong kiến trúc RAG (Lewis et al., 2020, *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*) — một hệ RAG không tự động "trung thực" chỉ vì có bước truy xuất; phải **xác minh** đầu ra thực sự bắt nguồn từ tài liệu truy xuất, không phải do LLM tự suy diễn (confabulation). Việc dùng fuzzy-matching thay vì exact-match phản ánh thực tế: LLM diễn đạt lại (paraphrase) nhẹ khi trích dẫn, nhưng vẫn phải neo được vào câu chữ gốc.

**Chi tiết bảo mật liên quan:** khi thêm nhãn nguồn `[Nguồn i: chương — mục]` vào ngữ cảnh để người duyệt truy vết (mục 4.2), hệ phát hiện một lỗ hổng: nếu dùng CHÍNH chuỗi có nhãn để kiểm chứng, LLM có thể "trích dẫn" ngược lại cái nhãn đó để giả mạo qua guardrail (một dạng *prompt injection ngược* — mô hình lợi dụng chính cấu trúc kiểm chứng). Giải pháp: tách hai bản ngữ cảnh — bản có nhãn (`context`, chỉ đưa vào prompt cho LLM) và bản không nhãn (`grounding_context`, chỉ dùng để kiểm chứng) — nguyên tắc *separation of concerns* giữa nội dung sinh và nội dung xác minh.

### 4.2. Truy vết nguồn cho người duyệt

Mỗi câu AI sinh lưu lại `rag_hits` (chương/mục/điểm tương đồng SGK đã dùng) trong `provenance`. Đây là yêu cầu **minh bạch mô hình** (model transparency) — người duyệt (Trưởng bộ môn) không thể đánh giá chất lượng một câu hỏi AI-sinh nếu không biết nó dựa trên đoạn SGK nào; đây là điều kiện tiên quyết cho *human oversight có ý nghĩa* (không phải chỉ bấm duyệt hình thức).

### 4.3. Chuẩn cấu trúc trắc nghiệm (item-writing guidelines)

**Trước:** MCQ chấp nhận số lượng đáp án bất kỳ.
**Sau:** MCQ bắt buộc đúng 4 lựa chọn A–D; cấm distractor kiểu "Tất cả các đáp án trên"/"A và B đúng".

**Cơ sở:** Đây là hai trong số các nguyên tắc kinh điển của *item-writing guidelines* trong khảo thí trắc nghiệm (Haladyna, Downing & Rodriguez, 2002, *A Review of Multiple-Choice Item-Writing Guidelines for Classroom Assessment*) — các dạng "kết hợp nhiều lựa chọn" (complex/K-type items) đã được chứng minh làm giảm độ tin cậy đo lường vì học sinh có thể chọn đúng bằng suy luận loại trừ một phần, không phản ánh đúng năng lực thật.

### 4.4. Phân loại Bloom độc lập (phá vỡ tự kiểm định vòng tròn)

**Trước:** yêu cầu LLM sinh câu ở mức Bloom X, sau đó tự so `bloom_level` do chính nó gán với X — luôn đúng, không có giá trị thông tin.
**Sau:** một lệnh LLM **riêng biệt**, không được biết mức Bloom yêu cầu ban đầu, tự phân loại lại câu hỏi từ đầu. Kết quả so với mức yêu cầu → cờ `match`/`mismatch`.

**Cơ sở:** Thang Bloom (Bloom, 1956; bản sửa đổi — Anderson & Krathwohl, 2001, *A Taxonomy for Learning, Teaching, and Assessing*) phân loại câu hỏi theo mức độ nhận thức (Nhớ → Hiểu → Vận dụng → Phân tích → Đánh giá → Sáng tạo) — việc gán đúng mức Bloom là yếu tố cốt lõi để một đề thi phản ánh đúng phổ năng lực cần đo (ma trận đề). Về mặt phương pháp đánh giá mô hình AI, đây áp dụng nguyên tắc **đánh giá độc lập với quá trình sinh** (independent verification) — một mô hình không thể tự chấm điểm bài của chính nó một cách đáng tin cậy nếu câu hỏi chấm điểm trùng với câu hỏi đã tạo ra kết quả đó.

### 4.5. Agent phản biện (LLM-as-critic)

Một lệnh LLM thứ ba chấm mỗi câu theo rubric khảo thí (đáp án duy nhất không tranh cãi, distractor hợp lý, đề bài tự đủ ngữ cảnh, ngôn ngữ phù hợp lứa tuổi) — trả điểm 0–10 kèm danh sách vấn đề cụ thể.

**Cơ sở:** Đây là mẫu hình *LLM-as-a-judge* đang được dùng rộng rãi để đánh giá chất lượng nội dung AI sinh ở quy mô lớn (Zheng et al., 2023, *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*) — khi việc con người chấm từng câu là không khả thi ở quy mô lớn, một agent chuyên trách đánh giá theo rubric tường minh giúp **ưu tiên hóa** (không thay thế) sự chú ý của người duyệt, đưa câu điểm thấp lên đầu hàng đợi rà soát.

### 4.6. Tự giải lại độc lập (self-consistency)

Một lệnh LLM riêng giải lại câu hỏi *như một học sinh*, không được xem đáp án có sẵn — so đáp án tự giải với đáp án gốc.

**Cơ sở:** Vận dụng ý tưởng *self-consistency* trong suy luận LLM (Wang et al., 2022, *Self-Consistency Improves Chain of Thought Reasoning in Language Models*) — nếu mô hình không tự giải ra đáp án đã công bố khi giải độc lập, đó là tín hiệu mạnh cho thấy đáp án/đề bài có vấn đề (mơ hồ, sai, hoặc thiếu dữ kiện) mà không cần con người giải trước.

### 4.7. Distractor bám lỗi tư duy thật (misconception-driven distractors)

**Trước:** phương án nhiễu do LLM tự bịa, không có căn cứ.
**Sau:** prompt yêu cầu mỗi distractor gắn với một lỗi tư duy cụ thể (misconception), và tùy chọn "tiêm" vào prompt một danh sách lỗi sai phổ biến đã biết của chủ đề (từ bảng `misconceptions`) để LLM ưu tiên bám theo lỗi thật thay vì bịa ngẫu nhiên.

**Cơ sở:** Đây là khoảng cách học thuật lớn nhất của các hệ sinh trắc nghiệm AI thông thường — chất lượng của một câu MCQ nằm chủ yếu ở **chất lượng phương án nhiễu**, không phải câu hỏi đúng. Distractor tốt phải phản ánh lỗi nhận thức thật của người học (Haladyna et al., 2002, nguyên tắc "distractor hợp lý dựa trên lỗi phổ biến"); đây cũng là nền tảng của *cognitive diagnostic assessment* — mô hình đánh giá chẩn đoán nhận thức, nơi đáp án sai được chọn không phải ngẫu nhiên mà cho biết **học sinh đang hiểu sai điều gì cụ thể**, từ đó GV can thiệp đúng chỗ.

### 4.8. Chống trùng lặp bằng embedding (semantic deduplication)

So sánh cosine similarity giữa vector embedding của câu mới với các câu đã có trong cùng chuẩn chương trình; câu vượt ngưỡng tương đồng (0.92) được gắn cờ nghi trùng.

**Cơ sở:** Trong khảo thí chuẩn hóa quy mô lớn, **kiểm soát mức độ lộ đề** (item exposure control) và tránh trùng lặp ngân hàng câu hỏi là yêu cầu bắt buộc để duy trì độ giá trị (validity) của kỳ thi qua nhiều lần sử dụng — so khớp bằng embedding ngữ nghĩa (thay vì so chuỗi ký tự) bắt được cả các câu diễn đạt khác nhau nhưng đo cùng một kiến thức theo cùng một cách.

### 4.9. Sinh dư rồi lọc (generate-then-filter)

Yêu cầu LLM sinh nhiều hơn ~50% số câu cần, rồi mới áp guardrail và cắt còn đúng số lượng — thay vì sinh đúng số rồi hy vọng tất cả đều qua được.

**Cơ sở:** Mẫu hình *over-generate and filter* phổ biến trong sinh nội dung có ràng buộc chất lượng — chấp nhận đánh đổi chi phí tính toán (gọi LLM nhiều hơn) để giữ **hiệu suất đầu ra ổn định** (yield) bất kể tỷ lệ câu bị guardrail loại bỏ dao động thế nào.

### 4.10. Vòng hiệu chỉnh kho câu (calibration loop) — Lý thuyết trắc nghiệm cổ điển (CTT)

Sau khi câu được dùng trong đề thi thật, hai chỉ số thống kê kinh điển của **Lý thuyết trắc nghiệm cổ điển** (Classical Test Theory — Crocker & Algina, 1986, *Introduction to Classical and Modern Test Theory*) được gắn vào từng câu:

- **p-value (độ khó/facility index):** tỉ lệ học sinh làm đúng câu đó.
- **Discrimination index (độ phân biệt):** mức độ câu hỏi phân biệt được học sinh giỏi với học sinh yếu — cụ thể, tương quan giữa việc làm đúng câu này với kết quả tổng thể của bài thi (tương tự hệ số tương quan điểm-nhị phân, point-biserial correlation, trong CTT).

Hệ tự động gắn cờ:
- **`NEGATIVE_DISCRIMINATION`** (phân biệt âm — học sinh giỏi sai câu này NHIỀU HƠN học sinh yếu): đây là tín hiệu CTT kinh điển cho thấy **gần như chắc chắn đáp án/đề bài sai**, không phải học sinh yếu → khuyến nghị `RETIRE` (ngừng dùng vĩnh viễn).
- **`LOW_DISCRIMINATION`**: câu không phân biệt được năng lực → cần rà soát lại.
- **`DIFFICULTY_DRIFT`**: độ khó thực nghiệm lệch xa so với dự đoán từ mức Bloom → dấu hiệu câu khó/dễ hơn tưởng, cần hiệu chỉnh mức Bloom hoặc nội dung.

**Cơ sở:** Đây chính là cách các tổ chức khảo thí chuẩn hóa lớn (SAT, TOEFL, các kỳ thi quốc gia) **hiệu chỉnh ngân hàng câu hỏi liên tục** sau mỗi lần sử dụng thật — một câu hỏi không "hoàn hảo" chỉ vì AI hoặc con người soạn ra nó cẩn thận; nó chỉ được xác nhận là "tốt" sau khi có dữ liệu thực nghiệm từ học sinh thật. Đây là điểm khác biệt cốt lõi so với hầu hết công cụ sinh đề AI trên thị trường — chúng dừng lại ở bước "sinh câu", không có vòng phản hồi khép kín từ **kết quả sử dụng thật** quay lại **chất lượng ngân hàng câu hỏi**.

*(Ghi chú giới hạn hiện tại: do dự án đang ở giai đoạn demo, chưa có dữ liệu bài làm học sinh thật cho môn Toán → thống kê p-value/discrimination hiện được mock có chủ đích [scripts/seed_item_stats_toan.py](../scripts/seed_item_stats_toan.py) để minh họa đúng cơ chế; khi có dữ liệu chấm thi thật, luồng tính toán các chỉ số này từ `scores` là hạng mục tiếp theo, không cần đổi kiến trúc.)*

---

## 5. Điểm khác biệt so với công cụ sinh đề AI thông thường

| Đặc điểm | Công cụ sinh đề AI phổ biến | Hệ thống này |
|---|---|---|
| Bám nguồn SGK | Không kiểm chứng, hoặc chỉ tin lời LLM | Đối chiếu quote thật với nội dung truy xuất |
| Mức độ nhận thức (Bloom) | LLM tự báo cáo | Phân loại độc lập, không mớm trước |
| Chất lượng distractor | Ngẫu nhiên/generic | Bám lỗi tư duy thật của học sinh (misconception bank) |
| Vòng đời câu hỏi | Sinh xong là dùng luôn | DRAFT → REVIEW → APPROVED → dùng thật → thống kê → RETIRE/REVIEW |
| Phản hồi từ kết quả sử dụng thật | Không có | Vòng hiệu chỉnh CTT (p-value, discrimination) |
| Vai trò AI | Quyết định nội dung | Đề xuất + ưu tiên hóa; con người quyết định cuối |

---

## 6. Tài liệu tham khảo

- Bloom, B. S. (1956). *Taxonomy of Educational Objectives*.
- Anderson, L. W., & Krathwohl, D. R. (2001). *A Taxonomy for Learning, Teaching, and Assessing* (bản sửa đổi thang Bloom).
- Crocker, L., & Algina, J. (1986). *Introduction to Classical and Modern Test Theory* (p-value, discrimination index).
- Haladyna, T. M., Downing, S. M., & Rodriguez, M. C. (2002). *A Review of Multiple-Choice Item-Writing Guidelines for Classroom Assessment*.
- Lewis, P. et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* (RAG, faithfulness).
- Wang, X. et al. (2022). *Self-Consistency Improves Chain of Thought Reasoning in Language Models*.
- Zheng, L. et al. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*.
