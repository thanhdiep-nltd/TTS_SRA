# Implementation Plan

## [Overview]

Thêm đánh dấu và bộ lọc "nâng rủi ro do LLM" (LLM risk escalation) vào dashboard EWS để làm nổi bật và dễ tìm các trường hợp mà bước dự báo LLM **nâng** mức rủi ro của học sinh lên cao hơn so với mức nền CatBoost (ví dụ: MODERATE → HIGH).

Hiện tại, pipeline EWS tạo ra hai kết quả đánh giá rủi ro cho mỗi mốc (học sinh - môn học): rủi ro ML của CatBoost (`risk_score`, `risk_level`) và dự báo định tính có tăng cường LLM (`llm_risk_score`, `llm_risk_level`) được lưu trong các cột `llm_*` của bảng `s360.fact_student_subject_risk_predictions`. Dashboard (`/ews/predictions` API + tab `EwsWarningTab` frontend) đã hiển thị cả hai badge (`risk_level` và "✨ LLM: <mức>") trên mỗi dòng, và drawer chi tiết hiển thị phần diễn giải của LLM.

Tuy nhiên, hiện **không có cách nào** để biết khi nào LLM đã *tăng* mức rủi ro so với CatBoost. Việc này quan trọng vì một sự nâng cấp (ví dụ MODERATE → HIGH) nghĩa là ngữ cảnh định tính (biến cố gia đình, bệnh lý) đã phát hiện mức độ nghiêm trọng mà ML thuần bỏ sót — một tín hiệu ưu tiên cao, quan trọng cho quyết định. Triển khai này bổ sung: (1) một đánh dấu boolean `llm_risk_escalated` tính toán được trên mỗi dòng dự báo, và (2) bộ lọc `llm_escalated` trên endpoint `/ews/predictions` để người dùng cô lập chính xác các trường hợp này. Đây là cải tiến tối thiểu, chỉ-đọc, tuân theo pattern hiện có của codebase là tính toán các marker dẫn xuất (ví dụ `primary_badge`) trong Python thay vì lưu cột phi chuẩn hóa.

Cách tiếp cận cố ý tối giản: không thay đổi schema database, không migration, không thay đổi logic pipeline/forecasting. Việc nâng cấp được suy ra ở thời điểm đọc bằng cách so sánh thứ hạng (rank) thứ tự của `llm_risk_level` với `risk_level`. Bộ lọc được áp dụng trong SQL (qua biểu thức CASE so sánh rank) để phân trang server-side, `COUNT`, và `LIMIT/OFFSET` vẫn đúng. Phạm vi trải qua ba file: router API (`src/api/v1/ews.py`), schema Pydantic (`src/schemas/ews.py`), tab frontend (`frontend/src/components/dashboard/EwsWarningTab.tsx`), cùng unit test, API test, và test E2E bằng Playwright MCP.

## [Types]

Thêm helper xếp hạng thứ tự cho các mức rủi ro và bổ sung marker tính toán mới vào schema phản hồi API. Không giới thiệu kiểu hoặc cột database mới; helper là hằng số dùng chung cho cả marker trả về và bộ lọc SQL.

**Xếp hạng thứ tự mức rủi ro** — dùng để xác định sự nâng cấp (định nghĩa dùng chung, khớp thứ tự `RISK_LEVELS` hiện có):

| Mức | Rank |
|-----|------|
| LOW | 0 |
| MODERATE | 1 |
| HIGH | 2 |
| CRITICAL | 3 |

**Trường Pydantic mới trên `EwsPredictionRow`** (`src/schemas/ews.py`):

```python
llm_risk_escalated: Optional[bool] = Field(
    default=None,
    description="True nếu LLM nâng mức rủi ro so với CatBoost (rank(llm_risk_level) > rank(risk_level)). None nếu chưa có llm_risk_level.",
)
```

- `True`: có `llm_risk_level` và rank của nó lớn hơn hẳn rank của `risk_level` (ví dụ MODERATE → HIGH, HIGH → CRITICAL).
- `False`: cả hai mức đều có và rank bằng nhau, hoặc LLM hạ mức (ví dụ HIGH → MODERATE — vẫn là thay đổi nhưng không phải nâng).
- `None`: thiếu `llm_risk_level` (chưa có đánh giá LLM cho mốc này).

**Tham số query mới trên `GET /ews/predictions`:**

| Param | Kiểu | Giá trị |
|-------|------|---------|
| `llm_escalated` | `bool \| None` | `true` = chỉ các dòng có nâng cấp; `false` = chỉ các dòng LLM KHÔNG nâng; bỏ trống / `None` = không lọc (tất cả dòng) |

**State & type mới phía frontend** (`frontend/src/lib/types.ts` và `EwsWarningTab.tsx`):
- `EwsPredictionRow` thêm `llm_risk_escalated: boolean | null`.
- Giá trị lọc mới `"ALL" | "true" | "false"` (qua `CustomDropdownSelect`) được serialize thành query param `llm_escalated`.

## [Files]

Sửa 3 file nguồn, 2 file cho types/test, và thêm 1 file test mới. Không xóa hoặc di chuyển file; không thay đổi file cấu hình.

**Các file được sửa:**

1. **`src/schemas/ews.py`**
   - Thêm hằng số xếp hạng thứ tự `RISK_LEVEL_RANK: dict[str, int] = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}` (cấp module, gần `EwsPredictionRow`).
   - Thêm trường `llm_risk_escalated: Optional[bool] = None` vào `EwsPredictionRow` (sau các trường `llm_*` hiện có, ~dòng 93).

2. **`src/api/v1/ews.py`**
   - Import `RISK_LEVEL_RANK` từ `src.schemas.ews`.
   - Trong `get_ews_predictions` (`~dòng 524`):
     - Thêm query param `llm_escalated: bool | None = Query(None, description="True = chỉ học sinh được LLM nâng mức rủi ro (rank llm_risk_level > rank risk_level)")`.
     - Khi `llm_escalated is not None`, thêm mệnh đề WHERE so sánh rank trong SQL tham chiếu cả `rp.risk_level` và `rp.llm_risk_level` (xem [Functions]).
     - Thêm mục `params`: `"rank_base"` / `"rank_llm"` hoặc boolean `"llm_escalated"` tùy dạng SQL chọn.
   - Trong vòng lặp serialize dòng (`~dòng 740`), tính toán và truyền `llm_risk_escalated=` vào `EwsPredictionRow` bằng helper nhỏ `_llm_risk_escalated(base_level, llm_level)`.
   - (Tùy chọn, không phá vỡ) Thêm số lượng nâng cấp vào `EwsOverview` để card KPI hiển thị — chỉ khi cần; giữ ngoài phạm vi để tối giản.

3. **`frontend/src/lib/types.ts`**
   - Thêm `llm_risk_escalated: boolean | null;` vào interface `EwsPredictionRow` (gần trường `llm_risk_level` hiện có).

4. **`frontend/src/components/dashboard/EwsWarningTab.tsx`**
   - Thêm state lọc mới `const [llmEscalated, setLlmEscalated] = useState<string>("ALL");`.
   - Thêm vào deps của effect fetch `/ews/predictions` và serialize: `if (llmEscalated !== "ALL") predParams.set("llm_escalated", llmEscalated);`.
   - Thêm control `CustomDropdownSelect` lọc (vd nhãn "Nâng Rủi Ro (LLM)") với các tùy chọn: `ALL` (Tất cả), `true` (Có — LLM nâng mức), `false` (Không nâng).
   - Trong ô "Mức Rủi Ro" của bảng dữ liệu, khi `item.llm_risk_escalated` là truthy, hiển thị thêm badge nâng cấp (vd pill amber/rose "⬆ LLM nâng") cạnh badge `✨ LLM:` hiện có.

**File mới:**

5. **`tests/test_ews_llm_escalation.py`**
   - Unit test cho helper `_llm_risk_escalated` mới (hàm thuần).
   - Test schema rằng `EwsPredictionRow` chấp nhận trường `llm_risk_escalated` mới (mô phỏng `tests/test_shap_drivers.py`).
   - Test kiểu integration cho bộ lọc endpoint `/ews/predictions`: xác nhận lọc theo `llm_escalated=true` chỉ trả về các dòng nâng cấp và phân trang/đếm phản ánh đúng tập đã lọc.

**File test được sửa:**

6. **`tests/test_shap_drivers.py`** (tùy chọn)
   - Mở rộng các test xây dựng `EwsPredictionRow` hiện có để cũng kiểm tra trường mới mặc định là `None` (giữ suite hiện tại xanh và ghi lại mặc định mới).

## [Functions]

Logic mới cốt lõi là một helper thuần duy nhất cộng với việc nối bộ lọc SQL. Không phá vỡ chữ ký hàm hiện có; chúng ta chỉ mở rộng `get_ews_predictions` với một tham số tùy chọn mới.

**Hàm mới:**

1. **`_llm_risk_escalated(base_level: str | None, llm_level: str | None) -> bool | None`** — `src/api/v1/ews.py`
   - Mục đích: xác định LLM có nâng mức rủi ro so với CatBoost hay không.
   - Logic:
     ```python
     RISK_LEVEL_RANK = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
     def _llm_risk_escalated(base_level, llm_level):
         if not llm_level:
             return None
         b = RISK_LEVEL_RANK.get((base_level or "").upper())
         l = RISK_LEVEL_RANK.get((llm_level or "").upper())
         if b is None or l is None:
             return None
         return l > b
     ```

2. **`_risk_level_rank_case(column: str) -> str`** — `src/api/v1/ews.py` (helper tùy chọn)
   - Mục đích: sinh biểu thức SQL `CASE` tái sử dụng ánh xạ một cột mức rủi ro sang rank thứ tự cho mệnh đề WHERE của bộ lọc.
   - Trả về: `CASE {column} WHEN 'LOW' THEN 0 WHEN 'MODERATE' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'CRITICAL' THEN 3 ELSE -1 END`.
   - Dùng để xây mệnh đề WHERE nâng cấp (giữ SQL dễ đọc và an toàn tham số vì `column` là literal cố định, không phải đầu vào người dùng).

**Hàm được sửa:**

3. **`get_ews_predictions`** — `src/api/v1/ews.py` (`~dòng 524`)
   - Thêm query param `llm_escalated: bool | None = Query(None, ...)`.
   - Khi có giá trị, thêm vào `where_clauses`:
     ```python
     if llm_escalated is not None:
         base_rank = _risk_level_rank_case("rp.risk_level")
         llm_rank = _risk_level_rank_case("rp.llm_risk_level")
         if llm_escalated:
             where_clauses.append(f"({llm_rank} > {base_rank} AND rp.llm_risk_level IS NOT NULL)")
         else:
             where_clauses.append(f"NOT ({llm_rank} > {base_rank} AND rp.llm_risk_level IS NOT NULL)")
     ```
   - Lưu ý: `llm_escalated=false` cố ý giữ các dòng có `llm_risk_level IS NULL` (chưa chạy LLM) là "không nâng" — khớp view mặc định của dashboard. Nếu product muốn chỉ các dòng đã đánh giá cho `false`, bọc nhánh `false` trong `AND rp.llm_risk_level IS NOT NULL` (nêu rõ là quyết định trong [Testing]).
   - Trong vòng lặp serialize, thay đổi vị trí dòng `llm_risk_level=r.llm_risk_level,` cũng truyền `llm_risk_escalated=_llm_risk_escalated(r.risk_level, r.llm_risk_level),`.

**Hàm bị xóa:** Không có.

## [Classes]

Không có class nào được thêm, xóa, hoặc thay đổi cấu trúc. Thay đổi duy nhất ở cấp class là thêm một trường vào model Pydantic hiện có.

**Class được sửa:**

1. **`EwsPredictionRow`** — `src/schemas/ews.py`
   - Thêm trường `llm_risk_escalated: Optional[bool] = None` (sau các trường dự báo `llm_*`).
   - Thêm hằng số cấp module `RISK_LEVEL_RANK`.

**Class mới:** Không có.

**Class bị xóa:** Không có.

## [Dependencies]

Không có dependency mới nào cho Python hoặc frontend. Triển khai dựa trên: thư viện chuẩn Python (`src/schemas/ews.py`, `src/api/v1/ews.py`), `pydantic`, `fastapi`, `sqlalchemy` hiện có; và các dependency frontend hiện có (`lucide-react` icons, `CustomDropdownSelect`). Không thay đổi `requirements.txt` hoặc `package.json`. Test E2E dùng MCP server Playwright (`github.com/microsoft/playwright-mcp`) — không cần cài đặt thêm.

## [Testing]

Ba tầng test: unit + schema, API integration, và E2E Playwright MCP. Tất cả phải chạy qua mà không có thay đổi schema DB.

**Tầng 1 — Unit & Schema (`tests/test_ews_llm_escalation.py`):**

1. `TestLlmRiskEscalated` — test hàm thuần `_llm_risk_escalated`:
   - `MODERATE → HIGH` trả về `True` (ví dụ chính người dùng nêu).
   - `HIGH → CRITICAL` trả về `True`.
   - Các mức bằng nhau (`HIGH → HIGH`) trả về `False`.
   - Hạ mức (`HIGH → MODERATE`) trả về `False`.
   - Thiếu `llm_level` trả về `None`.
   - Mức không biết / `None` cho base hoặc llm trả về `None`.

2. `TestEwsPredictionRowLlmEscalation` — test schema:
   - Xây `EwsPredictionRow` với `llm_risk_escalated=True` và kiểm tra round-trip; kiểm tra mặc định là `None` khi bỏ trống.

**Tầng 2 — API integration (`TestPredictionsLlmEscalationFilter` trong `tests/test_ews_llm_escalation.py`):**
   - Dùng test client/mock DB theo quy ước `tests/test_ews_control_panel.py`.
   - Seed các dòng: (a) base `MODERATE` + `llm HIGH` (nâng), (b) base `MODERATE` + `llm MODERATE` (không), (c) base `HIGH` + `llm HIGH` (không), (d) base `HIGH` + `llm null` (không LLM).
   - `GET /ews/predictions?llm_escalated=true` → chỉ trả về (a).
   - `GET /ews/predictions?llm_escalated=false` → trả về (b), (c), (d) (với ngữ nghĩa `false` đã chọn — xác nhận có bao gồm (d) hay không).
   - Xác nhận `total` phản ánh số lượng đã lọc và phân trang hoạt động.

**Tầng 3 — E2E Playwright MCP (dùng `github.com/microsoft/playwright-mcp`):**

Vì frontend không có setup Playwright test cục bộ (không có dependency `@playwright/test`), việc kiểm thử UI E2E được thực hiện qua **Playwright MCP server**. Luồng: khởi động backend FastAPI + frontend `next dev`, rồi dùng browser_* tools của Playwright MCP để thao tác và xác minh trực quan. Các kịch bản:

1. **Mở dashboard EWS** — `browser_navigate` tới URL frontend → tab "Cảnh báo EWS"/`EwsWarningTab`. `browser_snapshot` để xác nhận bảng dự báo render.
2. **Chọn mốc đánh giá có dữ liệu LLM** — điều hướng tới mốc (`school_year_id`/`semester_index`/`evaluated_at_week`) có `llm_risk_level` khác rỗng.
3. **Kiểm tra badge nâng cấp** — xác nhận các dòng có `llm_risk_escalated=true` hiển thị badge "⬆ LLM nâng" bên cạnh badge `✨ LLM:` trong ô "Mức Rủi Ro". `browser_find` hoặc `browser_snapshot` để lấy văn bản.
4. **Mở bộ lọc "Nâng Rủi Ro (LLM)"** — `browser_click` dropdown, chọn tùy chọn "Có — LLM nâng mức". Xác nhận dropdown hiển thị.
5. **Áp dụng bộ lọc = true** — sau khi chọn, kiểm tra request tới `/ews/predictions` có chứa `llm_escalated=true` qua `browser_network_requests`, và bảng chỉ còn các dòng nâng cấp (mọi badge `✨ LLM:` đều cao hơn mức nền).
6. **Kiểm tra `false`** — chọn "Không nâng", xác nhận bảng chỉ còn dòng không-nâng và request có `llm_escalated=false`.
7. **Chụp ảnh xác minh** — `browser_take_screenshot` lưu ảnh trước/sau khi lọc để lưu hồ sơ (vd `tests/playrights/ews_llm_escalation_filter.png`), ghi kết quả vào file báo cáo tham chiếu `tests/playrights/chat_reports.txt` như quy ước hiện có.
8. **Kiểm tra hồi quy** — dùng `browser_network_requests` đảm bảo không lỗi console/network (`browser_console_messages` với level `error`) khi thay đổi bộ lọc.

**Các test hiện có** — xác nhận không hồi quy:
- `pytest tests/test_llm_forecasting.py tests/test_shap_drivers.py tests/test_ews_control_panel.py`

## [Implementation Order]

Các bước được sắp xếp để giữ backend nhất quán trước khi đụng frontend, thêm test ở từng lớp, và E2E Playwright MCP ở cuối sau khi UI hoàn chỉnh.

1. **Thêm hỗ trợ schema** — `src/schemas/ews.py`: thêm hằng số `RISK_LEVEL_RANK` và trường `llm_risk_escalated` vào `EwsPredictionRow`.
2. **Thêm helper API + bộ lọc** — `src/api/v1/ews.py`: thêm helper `_llm_risk_escalated` và `_risk_level_rank_case`; thêm query param `llm_escalated` + mệnh đề WHERE SQL; điền `llm_risk_escalated` vào các dòng phản hồi.
3. **Thêm test backend (unit + API)** — tạo `tests/test_ews_llm_escalation.py` (helper, schema, endpoint filter); chạy và xác nhận xanh.
4. **Cập nhật types frontend** — `frontend/src/lib/types.ts`: thêm `llm_risk_escalated: boolean | null` vào `EwsPredictionRow`.
5. **Cập nhật UI frontend** — `frontend/src/components/dashboard/EwsWarningTab.tsx`: thêm state `llmEscalated` + dropdown lọc + gửi param `llm_escalated`; hiển thị badge nâng cấp trong ô mức rủi ro.
6. **Xác minh backend + build frontend** — chạy `pytest` backend và build/lint frontend (`npm run lint` / `npm run build`).
7. **Test E2E Playwright MCP** — khởi động backend + `next dev`, dùng Playwright MCP kiểm tra dropdown lọc, badge nâng cấp, request `llm_escalated`, chụp ảnh, và kiểm tra lỗi console/network.