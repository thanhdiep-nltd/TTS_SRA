# THIẾT KẾ UI/UX — TẠO ĐỀ THI TỪ NGÂN HÀNG CÂU HỎI (FRONTEND)

**Dự án:** AI20K-075 — AI Trợ Lý Phân Tích Kết Quả Học Tập
**Tính năng:** AI Exam Generation — Frontend (Next.js App Router)
**Phiên bản:** 1.0.0 (Draft) · **Ngày:** 2026-06-28
**Trạng thái:** Kế hoạch thiết kế — backend (Phase 0-2) đã xong, frontend CHƯA code
**Tài liệu liên quan:** [exam_generation_design.md](exam_generation_design.md) (thiết kế backend/API) · [gate_1/ui_gate_1.png](gate_1/ui_gate_1.png) (mockup vnEdu chung)

> Tài liệu này mô tả **kế hoạch** giao diện trước khi viết code, bám sát quy ước frontend hiện có (`Sidebar.tsx`, pattern trang `/scores`, `lib/api.ts`, `lib/auth.tsx`, `SearchableSelect`, theme `brand`/`accent`). Không có route/component nào trong tài liệu này đã tồn tại — tất cả là **việc cần làm**.

---

## A. Sơ đồ luồng nghiệp vụ theo vai trò

```
GV bộ môn ──tạo/sinh câu (DRAFT)──▶ Trưởng bộ môn ──duyệt──▶ Kho APPROVED
                                         │                         │
                                         ▼                         ▼
                                  Tạo ma trận đề ──────────▶ Ráp đề (nhiều mã đề)
                                                                    │
                                                              Trưởng BM CHỐT đề
                                                                    │
                                                                    ▼
                                                    exam_papers (map vào cột GK/CK)
PRINCIPAL/ADMIN: chỉ XEM (giám sát toàn trường, không tạo/duyệt — trừ ADMIN có toàn quyền)
```

**Phân quyền** (khớp RBAC backend hiện có — [src/services/rbac.py](../src/services/rbac.py), không cần đổi backend):

| Hành động | SUBJECT_TEACHER | SUBJECT_HEAD | ADMIN | PRINCIPAL |
|---|---|---|---|---|
| Xem ngân hàng (môn mình/phụ trách) | ✅ | ✅ | ✅ | 👁️ chỉ số tổng hợp |
| Tạo câu thủ công / sinh AI | ✅ | ✅ | ✅ | ❌ |
| Sửa câu DRAFT/REVIEW | ✅ (câu mình) | ✅ | ✅ | ❌ |
| **Duyệt câu** (APPROVED/REJECTED) | ❌ | ✅ | ✅ | ❌ |
| Tạo ma trận đề + ráp thử (preview) | ✅ | ✅ | ✅ | ❌ |
| **Chốt đề chính thức** | ❌ | ✅ | ✅ | ❌ |

> **Nguyên tắc nhất quán:** GV bộ môn được "ráp thử xem trước" nhưng không chốt — giống cách GV bộ môn map TX còn Trưởng BM mới map GK/CK ở tính năng điểm hiện có (`rbac.can_map`). Giữ đúng tinh thần này khi code FE (ẩn nút "Chốt đề" với SUBJECT_TEACHER, không chỉ dựa vào backend 403).

---

## B. Cấu trúc trang & Sidebar

Thêm 1 mục mới vào `MENU` trong [Sidebar.tsx](../frontend/src/components/Sidebar.tsx) (nhóm "Chức năng chính", hiện theo điều kiện role SUBJECT_TEACHER/SUBJECT_HEAD/ADMIN):

```tsx
{ name: "Ngân hàng câu hỏi", path: "/question-bank", icon: BookOpen }
```

**3 route mới**, theo đúng pattern `(app)/scores/page.tsx` (filter form + bảng + modal):

1. **`/question-bank`** — màn chính: ngân hàng câu hỏi (CRUD + duyệt)
2. **`/question-bank/blueprints`** — ma trận đề + ráp đề (2 tab trong cùng 1 trang)
3. **`/question-bank/exams/[id]`** — xem chi tiết 1 đề đã ráp (các mã đề, trạng thái)

---

## C. Wireframe từng màn (mô tả)

### C.1. `/question-bank` — Ngân hàng câu hỏi

```
┌─ Bộ lọc: [Môn ▾] [Khối ▾] [Chủ đề ▾ SearchableSelect] [Bloom ▾] [Trạng thái ▾]  [+ Sinh câu AI] [+ Tạo câu thủ công]
├─ Tabs: Tất cả | Chờ duyệt (DRAFT) | Đã duyệt | Bị từ chối | ⚠️ Cần rà soát kỹ (self_consistency=mismatch)
├─ Bảng:
│   Câu hỏi (rút gọn) │ Chủ đề │ Bloom │ Loại │ Nguồn │ Trạng thái │ Đã dùng │ Hành động
│   ...               │ ...    │ 2     │ MCQ  │ 🤖 AI  │ [Badge]    │ 0 lần   │ Xem/Sửa/Duyệt
└─ Click 1 dòng → mở Drawer chi tiết (xem C.2)
```

- **Badge trạng thái** tái dùng pattern `STATUS_STYLE` đã có ở `/scores`: `DRAFT`=slate, `REVIEW`=amber, `APPROVED`=emerald, `REJECTED`=rose, `RETIRED`=slate viền đậm.
- **Cờ "⚠️ Cần rà soát kỹ"**: badge `accent` (đỏ thương hiệu) khi `provenance.self_consistency === "mismatch"` — tín hiệu guardrail quan trọng nhất, phải nổi bật, không chỉ ẩn trong chi tiết.
- **Đáp án KHÔNG hiện trong bảng** (chỉ stem rút gọn) — chỉ hiện khi mở chi tiết (xem D.1).

### C.2. Drawer/Modal chi tiết câu hỏi

```
Đề bài: ...
Đáp án: [A] [B✓] [C] [D]      Lời giải: ...
─────────────────────────────
Nguồn gốc: 🤖 AI (deepseek-v4-flash) | Tự giải lại: ✅ khớp / ⚠️ KHÔNG khớp
Trích dẫn SGK: "..." (RAG grounding — bằng chứng cho người duyệt)
─────────────────────────────
Tạo bởi: Nguyễn Văn A · 12/06/2026     Đã dùng: 2 lần (gần nhất: 3 ngày trước ⚠️)
─────────────────────────────
[Nếu DRAFT/REVIEW + có quyền duyệt] → [Duyệt ✓] [Từ chối ✗ (bắt buộc nhập lý do)]
[Nếu DRAFT/REVIEW + là tác giả/Trưởng BM] → [Sửa]
```

"Đã dùng: ... (gần nhất: 3 ngày trước ⚠️)" — cảnh báo chống lộ đề, dùng `exposure_at`/`times_used` đã có ở backend (`question_items`).

### C.3. Modal "Sinh câu bằng AI"

Form 1 bước:

```
Môn: [đã chọn từ filter, readonly]   Khối: [...]
Chủ đề (chuẩn CT): [SearchableSelect — bắt buộc]
Mức Bloom: [1 Nhớ .. 6 Sáng tạo — radio/chip]
Loại câu: [MCQ / Đúng-sai / Trả lời ngắn / Tự luận]
Số câu: [1-20]
[Sinh câu] → toast "Đang sinh câu ở nền, có thể mất 1-2 phút..."
```

**Vấn đề UX cần xử lý** (xem E.1): `POST /question-bank/generate` trả `202` ngay rồi chạy nền (`BackgroundTasks`) — FE không biết khi nào xong/lỗi. Giải pháp v1 (không cần sửa backend): sau khi gọi, FE tự poll `GET /question-bank/items?...&status=DRAFT` mỗi 5s trong 2 phút, so sánh `created_at` mới hơn thời điểm bấm nút → toast "Đã sinh thêm N câu" hoặc "Không sinh được câu nào (RAG có thể chưa có nội dung chủ đề này)" nếu hết 2 phút không có gì mới.

### C.4. Ma trận đề + Ráp đề (1 trang, 2 tab)

**Tab "Ma trận đề"** — danh sách + form tạo (wizard 2 bước):

```
Bước 1: Thông tin đề        Bước 2: Ma trận (thêm từng ô)
  Môn, Khối, Loại (GK/CK)     [+ Thêm ô] Chủ đề | Bloom | Loại câu | Số câu | Điểm/câu
  Tên đề, Tổng điểm,          (hiện số câu APPROVED khả dụng cho mỗi chủ đề để GV biết kho đủ không)
  Thời lượng, Độ khó mục tiêu  Tổng điểm tự tính, validate khớp Tổng điểm khai báo
```

**Tab "Ráp đề"** — chọn ma trận đã tạo → chọn học kỳ/khối/số mã đề → **[Ráp thử]**:

```
Xem trước:
  Mã đề 101: [danh sách 10 câu, có đáp án — chỉ người ráp xem được]
  Mã đề 102: [cùng câu, thứ tự + đáp án đã xáo khác]
  CDI dự kiến: 0.45 (MEDIUM) ── so với mục tiêu 0.45 ✅ khớp
  [⚠️ nếu lệch >0.15 so với target_difficulty]: "Độ khó thực tế lệch mục tiêu — cân nhắc đổi ô ma trận"
[Ráp lại với seed khác]   [Chốt đề chính thức →] (chỉ Trưởng BM/ADMIN thấy nút này)
```

**Modal xác nhận CHỐT đề** (hành động không thể hoàn tác — bắt buộc xác nhận 2 bước):

```
⚠️ Chốt đề sẽ tạo bản ghi đề thi chính thức, không thể sửa câu hỏi trong đề sau khi chốt.
Tóm tắt: 10 câu · 10 điểm · CDI=0.45 · 2 mã đề · Môn Toán khối 8 · Cuối kỳ HK1 2025-2026
[Hủy]  [Xác nhận chốt đề]
```

Sau khi chốt → gợi ý "Map đề vào cột điểm" (link tới luồng `/scores/mappings` đã có API, **nhưng frontend cho mapping hiện chưa có UI riêng** — xem E.3).

### C.5. Dashboard giám sát cho PRINCIPAL/ADMIN (read-only)

Thêm 1 khối nhỏ ở trang `/question-bank` (hoặc widget trong Dashboard chính) khi role là PRINCIPAL:

```
Ngân hàng câu hỏi toàn trường: 110 câu (88 đã duyệt, 20 chờ duyệt, 2 cần rà soát ⚠️)
Theo môn: Toán 60 · KHTN 50
```

Đáp ứng tinh thần PRD: BGH cần "nhìn thấy" mà không cần sửa.

### C.6. Thông báo (Notification) — Trưởng BM biết để vào duyệt

**Hiện trạng (đã xác minh, KHÔNG có sẵn):** hệ thống chưa có bảng `notifications`, email/SMTP, WebSocket/SSE, hay badge chuông ở đâu cả. Đây là gap **toàn hệ thống** — luồng điểm số (`scores.status` DRAFT→SUBMITTED→APPROVED) cũng gặp y vấn đề này: người duyệt phải tự vào lọc `status=SUBMITTED` định kỳ, không được báo. Nếu không thiết kế thêm, câu hỏi DRAFT cũng vậy.

**Thiết kế đề xuất — bảng `notifications` generic** (tái dùng được cho cả gap điểm số, không xây riêng cho từng tính năng):

```sql
notifications(
  id, user_id, type, entity_type, entity_id, message,
  read_at, created_at
)
```

**Sự kiện 2 chiều** (vòng phản hồi trách nhiệm sư phạm — không chỉ báo 1 phía):

| Sự kiện | Người nhận | Nội dung |
|---|---|---|
| GV tạo/AI sinh xong câu mới (DRAFT) | Tất cả Trưởng BM của môn đó (qua `teacher_assignments`) | "Có N câu mới chờ duyệt — môn Toán khối 8" |
| Trưởng BM duyệt/từ chối câu | Tác giả câu hỏi (`created_by`) | "Câu hỏi của bạn đã được duyệt" / "...bị từ chối: <lý do>" |
| Trưởng BM/ADMIN chốt đề | Người tạo ma trận + Trưởng BM | "Đề Toán khối 8 đã chốt — map vào cột điểm tại đây" |

**UI:** icon 🔔 ở Sidebar/topbar + badge số chưa đọc, click mở dropdown 5-10 thông báo gần nhất kèm link tới mục liên quan, nút "đánh dấu đã đọc". FE polling đơn giản `GET /notifications?unread=true` mỗi 30-60s khi tab mở.

**Cố tình KHÔNG làm cho v1** (over-engineering cho quy mô vài chục GV/trường, MVP 5 tuần):
- Email/SMTP — chưa có hạ tầng, thêm xác thực domain phức tạp.
- WebSocket/SSE real-time — polling 30-60s đủ tốt cho tần suất sự kiện này.

> ✅ **Backend đã hiện thực** (khác các phần còn lại của tài liệu này — chỉ là kế hoạch): bảng
> `notifications`, service [src/services/notifications.py](../src/services/notifications.py),
> router [src/api/v1/notifications.py](../src/api/v1/notifications.py)
> (`GET /notifications`, `GET /notifications/unread-count`, `POST /notifications/{id}/read`,
> `POST /notifications/read-all`, `POST /notifications/announcements`). Đã tích hợp tự động ở
> 3 điểm sự kiện: tạo câu hỏi (thủ công + AI sinh xong), duyệt/từ chối câu, chốt đề.
>
> **Thông báo chủ động (compose)** — đúng yêu cầu nghiệp vụ: BGH (`ADMIN`/`PRINCIPAL`) gửi
> `SCHOOL` (toàn trường) / `SUBJECT` (chọn 1 bộ môn bất kỳ) / `INDIVIDUAL` (chọn 1 cá nhân bất
> kỳ, cùng trường). Trưởng bộ môn (`SUBJECT_HEAD`) chỉ gửi `SUBJECT` (ép buộc về đúng bộ môn
> mình phụ trách qua `Subject.subject_head_id`) hoặc `INDIVIDUAL` (chỉ thành viên có
> `users.subject_id` khớp bộ môn mình) — ép buộc ở `create_announcement`, không tin payload
> client. 31 test offline cho RBAC phạm vi này.
>
> **FE còn thiếu hoàn toàn**: icon chuông, badge, dropdown, modal soạn thông báo (xem C.6) — đây
> vẫn là phần kế hoạch frontend trong tài liệu.

---

## D. Quy tắc UI/UX bắt buộc (giáo dục chuyên nghiệp)

1. **Không bao giờ lộ đáp án ngoài phạm vi cần thiết** — bảng danh sách chỉ hiện stem; đáp án chỉ trong drawer chi tiết, chỉ render khi `user` có `can_manage_question_bank`.
2. **Luôn hiển thị truy vết người**: tạo bởi / duyệt bởi / ngày — không hiện UUID, phải map sang tên (xem E.4).
3. **Trạng thái màu nhất quán** với `/scores` (emerald=duyệt, amber=chờ, rose=từ chối) — không phát sinh bảng màu mới.
4. **Cảnh báo chống lộ đề** hiển thị tường minh (`exposure_at`/`times_used`).
5. **Hành động không thể hoàn tác (chốt đề, từ chối câu) luôn có modal xác nhận + tóm tắt**.
6. **Trạng thái rỗng/lỗi rõ ràng**: "Chưa có câu nào cho chủ đề này — Sinh câu bằng AI hoặc tạo thủ công" thay vì bảng trống im lặng.
7. **Dropdown >5 mục dùng `SearchableSelect`** (chủ đề, môn nếu nhiều) theo đúng quy ước CLAUDE.md §6.

---

## E. Các gap cần xử lý (nói rõ trước khi làm FE)

| Gap | Mức độ | Đề xuất |
|---|---|---|
| **E.1. Sinh câu AI chạy nền, FE không biết tiến trình/lỗi** | Trung bình | v1: polling phía FE (xem C.3). Phase sau (nếu cần chính xác hơn): thêm bảng `generation_jobs` (status, error_message) |
| **E.2. Chưa có export PDF/Word đề thi để in** | Cao (cần thật khi thi) | [exam_generation_design.md](exam_generation_design.md) §6.3 đã note nhưng chưa code. Cần làm trước khi dùng thật ngoài đời; v1 demo có thể tạm "in từ trình duyệt" (CSS `@media print`) |
| **E.3. Chưa có UI map đề vào cột điểm** | Trung bình | API `/scores/mappings` đã có (dùng chung cho cả đề upload tay), nhưng chưa có trang FE nào gọi. Nên làm chung 1 lần cho cả 2 luồng (đề AI + đề upload tay) |
| **E.4. `created_by`/`reviewed_by` chỉ là UUID** | Thấp | FE gọi `/users?ids=...` hoặc backend trả kèm tên — quyết định khi code |
| **E.5. Không có cơ chế thông báo "có câu chờ duyệt"** | Cao (đã xác minh, gap toàn hệ thống) | Bảng `notifications` generic + UI chuông (xem C.6). Nên làm sớm vì giải quyết luôn gap tương tự ở luồng điểm số SUBMITTED |

---

## F. Kế hoạch triển khai theo Phase (frontend)

- **Phase A** — Ngân hàng câu hỏi: trang `/question-bank`, filter, bảng, drawer chi tiết, tạo thủ công, sửa, duyệt/từ chối. *(Dùng được ngay, không phụ thuộc AI)*
- **Phase A.5** — Thông báo (E.5): bảng `notifications` + endpoint + icon chuông. Làm sớm ngay sau Phase A vì Trưởng BM cần nó để biết vào duyệt — không nên để cuối.
- **Phase B** — Modal "Sinh câu AI" + polling tiến trình (E.1).
- **Phase C** — Ma trận đề + Ráp đề + Chốt đề (modal xác nhận, hiển thị CDI).
- **Phase D** — Export PDF/in đề (E.2) + UI map đề vào cột điểm (E.3) — phụ thuộc quyết định có làm ngay hay để sau demo.
