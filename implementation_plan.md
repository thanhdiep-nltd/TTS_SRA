# Implementation Plan

[Overview]
Thêm LLM-based Forecasting vào EWS: sau khi CatBoost cho risk_score gốc, tự động gọi LLM cho học sinh HIGH/CRITICAL hoặc LOW/MODERATE có biến cố gia đình/bệnh lý, lưu kết quả (llm_risk_score + narrative) vào cột mới, và cho phép kích hoạt thủ công từ UI.

Tính năng này cần thiết để bổ sung lớp phân tích định tính (biến cố gia đình, bệnh tật) mà CatBoost thuần ML không nắm được. Nó giữ nguyên risk_score CatBoost để audit, đồng thời lưu llm_risk_score riêng + narrative để GVCN/cố vấn tâm lý hiểu nguyên nhân gốc rễ. Hiện chưa có LLM-based Forecasting trong dự án — đây là tính năng mới hoàn toàn, hook vào sau bước inference của pipeline_runner.py.

Trigger condition (tinh chỉnh — tránh trigger thừa cho biến cố/bệnh đã RESOLVED hoặc nhẹ không ảnh hưởng):
```
Trigger = (risk_level IN ['HIGH', 'CRITICAL'])
       OR (EXISTS life_event WHERE status='ONGOING')
       OR (EXISTS medical WHERE status='ONGOING' AND (is_chronic = TRUE OR severity IN ('MODERATE','HIGH')))
```
→ Học sinh trật khớp 3 năm trước (status=RESOLVED) → KHÔNG trigger.
→ Học sinh dị ứng nhẹ (severity=LOW) dù ONGOING nhưng đang Xuất sắc → không trigger (chỉ lưu hồ sơ, không gọi LLM).
→ Bệnh mãn tính ONGOING → LUÔN trigger (is_chronic).

[Types]
Thêm 6 cột LLM + mô hình thời gian (Temporal Status) cho 2 bảng biến cố/bệnh + Pydantic schema + TypeScript type.

**A. Bảng `s360.fact_student_subject_risk_predictions` — 6 cột LLM:**
- `llm_risk_score` DECIMAL(5,2) — điểm rủi ro 0-100 do LLM đánh giá (điều chỉnh định tính)
- `llm_risk_level` VARCHAR(15) — LOW/MODERATE/HIGH/CRITICAL
- `llm_narrative_summary` TEXT — phân tích nguyên nhân gốc rễ kết hợp biến cố/bệnh tật
- `llm_forecast_trend` TEXT — dự báo xu hướng 3-4 tuần tới
- `llm_recommended_actions` JSONB — 2-3 hành động can thiệp khuyến nghị
- `llm_evaluated_at` TIMESTAMPTZ — thời điểm LLM đánh giá

**B. Bảng `s360.fact_student_life_events` — mô hình thời gian (biến cố):**
- `time_quantity INT` — số lượng (3, 5, 10) — "đã diễn ra X đơn vị"
- `time_unit VARCHAR(20)` — DAY/WEEK/MONTH/YEAR
- `status VARCHAR(20)` — ONGOING (đang diễn ra) / RESOLVED (đã kết thúc) / UNKNOWN (không rõ)
- `event_date DATE` — ngày chính xác NẾU có (NULL = ước lượng qua time_quantity/time_unit)
- `created_at` (đã có) — ngày TẠO/nhập hệ thống = recorded_at

**C. Bảng `s360.fact_student_medical_history` — mô hình thời gian (bệnh):**
- `time_quantity INT` — "đã X đơn vị" (vd gãy tay 3 tháng)
- `time_unit VARCHAR(20)` — DAY/WEEK/MONTH/YEAR
- `status VARCHAR(20)` — ONGOING / RESOLVED (đã hồi phục) / UNKNOWN
- `diagnosed_date DATE` (đã có) — ngày chẩn đoán NẾU có
- `is_chronic BOOLEAN` (đã có) — mãn tính thì status luôn ONGOING
- `created_at` (đã có) — ngày nhập hệ thống

**Cách LLM dùng:** nhận `created_at` (mốc nhập) + `time_quantity/time_unit` (đã bao lâu) + `status` (còn ảnh hưởng hay không) + `duration_profile` suy từ loại. Không cần ngày thực tế — `time_quantity/time_unit` là ước lượng đủ cho LLM phán đoán "biến cố cũ giảm trọng số nhưng không bỏ qua, bệnh mãn tính luôn ONGOING".

Pydantic (`src/schemas/ews.py`): thêm field llm_* vào `EwsPredictionRow`; thêm `time_quantity`, `time_unit`, `status` vào `EwsRawLifeEventItem` + `EwsRawMedicalItem`.

TypeScript (`frontend/src/lib/types.ts`): thêm llm_* vào `EwsPredictionRow`; thêm `time_quantity`, `time_unit`, `status` vào `EwsRawLifeEventItem` + `EwsRawMedicalItem`.

[Files]
Sửa file schema + backend + frontend; tạo 1 file service mới.

- **New**: `src/ews/llm_forecasting.py` — dịch vụ LLM-based forecasting (gọi `get_llm()` từ `src/services/llm.py`)
- **Modify**: `docs_vsf/schemas/merged/score_focused_schema.sql` — thêm 6 cột vào `fact_student_subject_risk_predictions` (kèm ALTER TABLE idempotent cho DB đã tồn tại)
- **Modify**: `src/ews/pipeline_runner.py` — sau Step 2 inference, gọi `run_llm_forecasting_batch()` cho nhóm trigger; thêm cột llm_* vào UPSERT_SQL + UPSERT_REQUIRED_COLS
- **Modify**: `src/schemas/ews.py` — thêm field llm_* vào `EwsPredictionRow`
- **Modify**: `src/api/v1/ews.py` — endpoint mới `POST /ews/llm-forecast` (trigger thủ công 1 học sinh); trả llm_* trong predictions/raw
- **Modify**: `frontend/src/lib/types.ts` — thêm field llm_* vào `EwsPredictionRow`
- **Modify**: `frontend/src/components/dashboard/EwsDetailDrawer.tsx` — nút "Phân tích & Dự báo bằng AI" + hiển thị llm_* (narrative, trend, actions, cả 2 điểm)
- **Modify**: `frontend/src/components/dashboard/EwsWarningTab.tsx` — hiển thị cột llm_risk_level/badge nếu có
- **Modify**: `data_mock/mock_full_data/generate_full_system_mock_v4.py` — cập nhật `seed_life_events_and_medical()` để tự điền `time_quantity` (vd 2), `time_unit` ('MONTH'/'YEAR'), `status` ('ONGOING'/'RESOLVED') đồng bộ với schema mới

[Functions]
Thêm hàm service + hook pipeline + endpoint.

- **New** `run_llm_forecasting_batch(session, df, cfg)` (src/ews/llm_forecasting.py): lọc nhóm trigger, gọi LLM song song (thread pool), trả DataFrame có cột llm_*
- **New** `forecast_student_risk(session, student_code, subject_id, ...)` (src/ews/llm_forecasting.py): gọi LLM cho 1 học sinh, build prompt từ features + life_events + medical, parse JSON, lưu
- **New** `_build_llm_prompt(features, life_events, medical)` (src/ews/llm_forecasting.py): tạo prompt structured JSON
- **Modified** `run_pipeline()` (src/ews/pipeline_runner.py): gọi `run_llm_forecasting_batch` sau inference khi `enable_llm=True`
- **New** `POST /ews/llm-forecast` (src/api/v1/ews.py): trigger thủ công, gọi `forecast_student_risk`, trả `EwsPredictionRow` cập nhật

[Classes]
Dùng hàm `get_llm()` hiện có (không tạo class mới).

- **New** không bắt buộc; có thể gói logic vào module `llm_forecasting.py` với helper `_parse_llm_response(text) -> dict`

[Dependencies]
Dùng `get_llm()` từ `src/services/llm.py` (đã cấu hình qua `.env` `LLM_PROVIDER=openai/deepseek`). Không thêm package mới. Cần `concurrent.futures` (stdlib) cho batch.

[Testing]
Thêm test đơn vị cho việc parse LLM response + logic trigger.

- **New** `tests/test_llm_forecasting.py`: mock `get_llm()` → kiểm tra `_parse_llm_response`, `forecast_student_risk` lưu đúng cột, trigger condition đúng
- **Modify** `tests/test_ews_control_panel.py` (nếu cần): kiểm tra endpoint mới

[Implementation Order]
1. Schema: thêm 6 cột vào `score_focused_schema.sql` + ALTER TABLE idempotent → apply
2. Backend schema `src/schemas/ews.py`: thêm field llm_* vào `EwsPredictionRow`
3. Tạo `src/ews/llm_forecasting.py` (prompt + parse + forecast_student_risk + batch)
4. Hook `pipeline_runner.py`: gọi batch sau inference + thêm llm_* vào UPSERT
5. Endpoint `POST /ews/llm-forecast` trong `src/api/v1/ews.py`
6. Frontend type `types.ts`: thêm field llm_*
7. Frontend UI `EwsDetailDrawer.tsx`: nút + hiển thị llm_*
8. Frontend `EwsWarningTab.tsx`: hiển thị llm_risk_level badge
9. Mock generator v4: cập nhật `seed_life_events_and_medical()` điền `time_quantity/time_unit/status` → chạy lại seed
10. Test + build (`tsc --noEmit`)
