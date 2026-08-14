# Implementation Plan

## [Overview]

Đảm bảo LLM Forecasting trả kết quả nhất quán và có tính giải trình khi "Chạy Lại Phân Tích" (re-run) — cùng 1 học sinh, môn, tuần → nếu đã từng đánh giá thì kết quả mới phải giữ điểm cũ trừ khi có lý do thuyết phục để đổi, và mọi thay đổi phải kèm lý do rõ ràng.

Hiện tại, mỗi lần chạy LLM forecast (qua nút "Chạy Lại Phân Tích" trong `EwsDetailDrawer` hoặc qua pipeline tự lặp lại đúng tuần) đều gọi LLM mới với `temperature=0.7` (`src/config.py`) và **ghi đè** cột `llm_*` mà không so sánh kết quả cũ → người dùng thấy điểm thay đổi ngẫu nhiên (93 → 97 → 92). Nguyên nhân gốc: (1) temperature>0 làm LLM sampling ngẫu nhiên, (2) không có cơ chế neo/so sánh điểm cũ, (3) `_should_trigger` bỏ sót mức `CRITICAL` cho bệnh lý.

Cách tiếp cận (đã chốt với user — "Cách A"): luôn gọi LLM lại khi re-run, NHƯNG prompt yêu cầu **suy xét kỹ** — mặc định GIỮ NGUYÊN điểm cũ, chỉ đổi nếu có lý do thuyết phục (dữ liệu/biến cố/bệnh thay đổi), nếu đổi phải nêu rõ lý do. Hệ thống lưu cả điểm cũ lẫn lý do thay đổi để UI hiển thị minh bạch. Nguyên tắc thống nhất: lấy DB làm nguồn chân lý — "điểm cũ" = `llm_risk_score` đang lưu cho khóa `(student_code, subject_id, school_year_id, semester_index, evaluated_at_week, model_version)`, áp dụng cho cả re-run tự động lẫn thủ công.

## [Types]

Thêm 2 cột DB + 2 trường schema để lưu điểm cũ và lý do thay đổi.

**Cột mới trên `s360.fact_student_subject_risk_predictions`:**

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `llm_previous_score` | `FLOAT DOUBLE PRECISION NULL` | Điểm LLM trước đó (trước lần re-run này), NULL nếu chưa từng có |
| `llm_score_change_reason` | `TEXT NULL` | Lý do thay đổi điểm (nếu đổi), NULL nếu giữ nguyên điểm cũ |

**Trường Pydantic mới trên `EwsPredictionRow`** (`src/schemas/ews.py`):
```python
llm_previous_score: Optional[float] = Field(default=None, description="Điểm LLM trước đó (re-run). None nếu chưa từng đánh giá.")
llm_score_change_reason: Optional[str] = Field(default=None, description="Lý do thay đổi điểm LLM trong lần re-run. None nếu giữ nguyên điểm cũ.")
```

## [Files]

Sửa 5 file nguồn backend + 1 frontend + migration mới.

**`alembic/versions/`** — migration mới (vd `20260813_ews_llm_rerun_audit.py`) theo pattern file `20260804_ews_multi_tenant_isolation.py`: `op.add_column("fact_student_subject_risk_predictions", ...)` thêm `llm_previous_score` (FLOAT) + `llm_score_change_reason` (TEXT), `schema="s360"`.

**`src/ews/llm_forecasting.py`** — sửa:
- `LLM_OUTPUT_COLS` thêm `"llm_previous_score"`, `"llm_score_change_reason"`.
- `_build_llm_prompt(...)` thêm tham số `previous_llm_result: Optional[Dict[str, Any]] = None` → chèn khối prompt "Điểm trước đó & chính sách ổn định".
- `_normalize_llm_result(data, cb_score, previous_llm_result=None)` → nếu có điểm cũ và LLM không thay đổi thì giữ điểm cũ; set `llm_previous_score` + `llm_score_change_reason`.
- `forecast_student_risk(...)` thêm `previous_llm_result: Optional[Dict[str, Any]] = None` → truyền vào prompt + normalize + persist.
- `run_llm_forecasting_batch(...)` → trong `_worker`, SELECT `llm_risk_score`/`llm_risk_level` cũ theo key rồi truyền làm `previous_llm_result`.
- `_persist_llm_columns(...)` thêm cột `llm_previous_score`, `llm_score_change_reason`.
- `_should_trigger(...)` → sửa điều kiện bệnh: `severity in ("MODERATE", "HIGH", "CRITICAL")`.

**`src/schemas/ews.py`** — thêm 2 trường vào `EwsPredictionRow`.

**`src/api/v1/ews.py`** — sửa endpoint re-run (`~line 1670`): sau khi load `row`, đọc `llm_risk_score` cũ từ DB (khóa đầy đủ) để truyền làm `previous_llm_result`; thêm 2 trường vào response.

**`frontend/src/components/dashboard/EwsDetailDrawer.tsx`** — hiển thị "Điểm LLM trước: X → mới: Y" + lý do thay đổi (nếu có).

## [Functions]

**Hàm mới:**
1. `_get_previous_llm_result(session, student_code, subject_id, school_year_id, semester_index, evaluated_at_week) -> Optional[Dict]` — `src/ews/llm_forecasting.py`. SELECT `llm_risk_score, llm_risk_level` theo khóa; trả dict nếu `llm_risk_score IS NOT NULL`, else None.

**Hàm sửa:**
2. `_build_llm_prompt(..., previous_llm_result=None)` — thêm khối prompt: "Điểm LLM trước đó của học sinh là X (mức Y). **CHÍNH SÁCH ỔN ĐỊNH**: mặc định GIỮ NGUYÊN điểm cũ. Chỉ thay đổi điểm/mức nếu có lý do thuyết phục (dữ liệu biến cố/bệnh/điểm số thay đổi). Nếu giữ nguyên → trả llm_risk_score = X. Nếu đổi → trường llm_score_change_reason phải giải thích rõ ràng tại sao."
3. `_normalize_llm_result(data, cb_score, previous_llm_result=None)` — nếu `previous_llm_result` có `llm_risk_score`:
   - Nếu LLM trả score "gần" điểm cũ (sai lệch ≤ ngưỡng, vd ≤1 hoặc raw == cũ) hoặc không có lý do → **giữ điểm cũ**: `score = previous`, `llm_previous_score = previous`, `llm_score_change_reason = None`.
   - Nếu LLM đổi (sai lệch > ngưỡng) → dùng score mới, `llm_previous_score = previous`, `llm_score_change_reason = <lý do từ LLM>`.
   - Luôn set `llm_previous_score` khi có điểm cũ.
4. `forecast_student_risk(..., previous_llm_result=None)` — truyền vào `_build_llm_prompt` + `_normalize_llm_result` + `_persist_llm_columns`.
5. `run_llm_forecasting_batch(...)` — trong `_worker`, gọi `_get_previous_llm_result` trước khi build prompt.
6. `_persist_llm_columns(...)` — thêm 2 cột vào INSERT/params.
7. `_should_trigger(...)` — bệnh: đổi `severity in ("MODERATE", "HIGH")` → `("MODERATE", "HIGH", "CRITICAL")`.

## [Classes]

Không thêm/xóa class. Sửa `EwsPredictionRow` (schema) thêm 2 trường mới.

## [Dependencies]

Không dependency mới. Dùng thư viện hiện có (pydantic, sqlalchemy, alembic, frontend lucide-react). Không đổi `requirements.txt`/`package.json`.

## [Testing]

- Sửa `tests/test_llm_forecasting.py`: test `_normalize_llm_result` giữ điểm cũ khi không có lý do, đổi điểm khi có lý do + set `llm_previous_score`/`llm_score_change_reason`; test `_should_trigger` với `CRITICAL`.
- Sửa `tests/test_ews_llm_escalation.py` (nếu dùng schema) + `tests/test_shap_drivers.py` để bảo toàn default `None` của 2 trường mới.
- Test API re-run: seed bản ghi có `llm_risk_score` cũ, gọi re-run, mock LLM trả điểm giống → khẳng định giữ nguyên + `llm_previous_score` được set.
- Chạy: `pytest tests/test_llm_forecasting.py tests/test_ews_llm_escalation.py tests/test_ews_control_panel.py tests/test_shap_drivers.py`; lint `ruff`; build frontend `npm run lint`.

## [Implementation Order]

1. Migration DB thêm 2 cột.
2. `src/ews/llm_forecasting.py`: `_get_previous_llm_result`, sửa `_build_llm_prompt`, `_normalize_llm_result`, `_persist_llm_columns`, `_should_trigger`, `forecast_student_risk`, `run_llm_forecasting_batch`, `LLM_OUTPUT_COLS`.
3. `src/schemas/ews.py`: thêm 2 trường.
4. `src/api/v1/ews.py`: truyền `previous_llm_result` từ DB + thêm 2 trường response.
5. Frontend `EwsDetailDrawer.tsx`: hiển thị điểm cũ/mới + lý do.
6. Test backend + sửa test hiện có; lint + build frontend; chạy test E2E Playwright MCP nếu cần.