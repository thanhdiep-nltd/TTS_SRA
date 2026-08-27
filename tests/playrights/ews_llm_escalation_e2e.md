# E2E — Kịch bản kiểm thử "Nâng Rủi Ro do LLM" (LLM Risk Escalation)

Kiểm thử UI dashboard EWS bằng **Playwright MCP** (`github.com/microsoft/playwright-mcp`).
Mục tiêu: xác nhận bộ lọc "Nâng Rủi Ro (LLM)" + badge "⬆ LLM nâng" hoạt động đúng ở cả 3 nhánh (`ALL` / `true` / `false`).

---

## Điều kiện tiên quyết

- Backend FastAPI chạy tại `http://127.0.0.1:8000`
- Frontend Next.js chạy tại `http://localhost:3000`
- Đã đăng nhập với vai trò **BGH (Ban Giám Hiệu)**
- Chỉ **model v2 (Factor-Ensemble)** mới có dữ liệu → bắt buộc chuyển Phiên bản Model sang **v2**.

### Thông tin đăng nhập (dự phòng nếu bị đăng xuất / hết phiên)

> Dùng tài khoản **BGH** này khi trang yêu cầu đăng nhập:

| Trường | Giá trị |
|--------|---------|
| Username | `principal_cp@vinschool.edu.vn` |
| Password | `password123` |

---

## Các bước thực hiện

### Bước 0 — Đăng nhập (chỉ khi bị đăng xuất / hết phiên)

Nếu không vào được `/dashboard` (bị redirect về trang login), thực hiện:

1. `browser_navigate  url="http://localhost:3000/login"` (hoặc URL login mà trang redirect tới).
2. `browser_snapshot` → lấy ref của ô nhập **Email/Username** và **Password**.
3. `browser_type` vào ô email: `principal_cp@vinschool.edu.vn`
4. `browser_type` vào ô password: `password123`
5. `browser_click` nút **Đăng nhập / Sign in**.
6. `browser_navigate  url="http://localhost:3000/dashboard"` → chuyển sang Bước 1.

### Bước 1 — Mở dashboard

```
browser_navigate  url="http://localhost:3000/dashboard"
browser_snapshot
```
Kết quả: trang "SchoolAI Analytics" hiển thị, tab "Cảnh báo EWS" (EwsWarningTab).

### Bước 2 — Chuyển Phiên bản Model sang v2

Dropdown "Phiên bản Model" là `<select>` thứ 2 trên trang (giá trị tùy chọn là `v1_single` / `v2_ensemble`).

```js
// Dùng browser_evaluate để set đúng select #2 (index 1)
const sels = document.querySelectorAll('select');
const sel = sels[1];
sel.value = 'v2_ensemble';
sel.dispatchEvent(new Event('change', { bubbles: true }));
return sel.value; // -> "v2_ensemble"
```
Kết quả: KPI hiển thị dữ liệu (tổng lượt dự báo > 0).

### Bước 3 — Mở bộ lọc "Nâng Rủi Ro (LLM)"

- `browser_find text="Nâng Rủi Ro (LLM)"` → lấy ref button của dropdown.
- `browser_click` vào button đó.
Kết quả: dropdown mở với 3 tùy chọn:
  - `Tất cả` (value `ALL`)
  - `Có — LLM nâng mức` (value `true`)
  - `Không nâng` (value `false`)

### Bước 4 — Bộ lọc `true` (Có — LLM nâng mức)

- `browser_click` vào "Có — LLM nâng mức".
- Kiểm tra network: `browser_network_requests filter="/ews/predictions"`.

Kỳ vọng request:
```
GET /api/v1/ews/predictions?school_year_id=2025&semester_index=1&evaluated_at_week=8
    &model_version=v2_ensemble&limit=10&offset=0&llm_escalated=true
```
Kỳ vọng UI: bảng "Danh Sách Dự Báo Chi Tiết" chỉ còn các dòng LLM nâng mức.

**Với dữ liệu có sẵn** (chưa seed): nếu không có case nào `rank(llm_risk_level) > rank(risk_level)` → hiển thị **0 Kết Quả** (đúng, backend lọc chính xác).

### Bước 5 — Bộ lọc `false` (Không nâng)

- Mở dropdown → chọn "Không nâng".
- Kiểm tra request có `llm_escalated=false`.
Kỳ vọng: trả về các dòng KHÔNG nâng mức (bao gồm cả dòng chưa có `llm_risk_level` như "không nâng").

### Bước 6 — Xác minh badge "⬆ LLM nâng" (cần 1 case escalation trong dữ liệu)

Nếu chưa có dữ liệu escalation, seed tạm 1 case để demo:

```sql
UPDATE s360.fact_student_subject_risk_predictions
SET llm_risk_level='HIGH', llm_risk_score=70,
    llm_narrative_summary='Demo', llm_forecast_trend='tang',
    llm_recommended_actions='[]', llm_evaluated_at=now()
WHERE student_code='HS0001' AND subject_id=2 AND school_year_id=2025
  AND semester_index=1 AND evaluated_at_week=8 AND so_school_id=1 AND model_version='v2_ensemble';
-- (dòng này risk_level='MODERATE' → llm='HIGH' = escalation)
```

Sau đó với bộ lọc `true`, dòng đó hiển thị:
```
MODERATE  ✨ LLM: HIGH  ⬆ LLM nâng
```
Badge "⬆ LLM nâng" xuất hiện cạnh badge `✨ LLM: <mức>` trong cột "Mức Rủi Ro".
Drawer chi tiết xác nhận: CatBoost `MODERATE` → LLM `HIGH`.

> ⚠️ Sau khi test, NHỚ revert dữ liệu seed lại `NULL` để không để sót dữ liệu giả.

---

## Kiểm tra hồi quy (console/network)

- `browser_console_messages level="error"` → không có lỗi console.
- `browser_network_requests` → các request `/ews/predictions` đều trả `[200] OK`, không lỗi 4xx/5xx.

---

## Ghi chú

- **Chỉ model v2 có dữ liệu** — model v1 trả 0 bản ghi (bỏ qua nếu thấy KPI = 0 khi đang ở v1).
- Select "Phiên bản Model" là `<select>` **thứ 2** trên trang (thứ nhất là "Mốc Đánh Giá").
- Playwright MCP lưu screenshot có sandbox giới hạn vào `~/.playwright-mcp` — không ghi trực tiếp vào project. Accessibility snapshot đủ để xác nhận.