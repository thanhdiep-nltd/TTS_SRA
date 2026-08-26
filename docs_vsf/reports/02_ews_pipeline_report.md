# BÁO CÁO — EWS Pipeline (Early Warning System)

**Người viết**: [Tên] | **Ngày**: 26/08/2026

---

## 1. Giới thiệu

EWS (Early Warning System) là hệ thống dự đoán nguy cơ học sinh rớt môn, sử dụng **CatBoost ML model** trên 22 features từ 4 nguồn dữ liệu: điểm số, LMS, điểm danh, hạnh kiểm. Mục tiêu là giúp BGH phát hiện sớm học sinh có nguy cơ để can thiệp kịp thời.

---

## 2. Kiến trúc tổng quan

```
BGH kích hoạt pipeline
       │
       ▼
┌──────────────────┐
│   EWS Job Queue  │  ← DB-backed FIFO, 1 job/lần, timeout 5p
│  (ews_pipeline_  │
│   jobs)          │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Feature Extract │  ← SQL từ s360 schema (MATERIALIZED CTE)
│  22 features     │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  CatBoost Model  │  ← v1 (single) hoặc v2_ensemble (5 folds)
│  Inference       │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  SHAP Drivers    │  ← Feature importance cho từng HS
└──────┬───────────┘
       │
       ▼
┌─────────────────────────────────┐
│  fact_student_subject_risk_    │  ← UPSERT kết quả
│  predictions                    │
└─────────────────────────────────┘
```

**Model version:**
- **v1**: `catboost_ews_v1.cbm` — single model
- **v2_ensemble**: 5 CatBoost folds — ensemble averaging (mặc định)

---

## 3. Các thành phần chính

| File | Vai trò |
|------|---------|
| src/ews/feature_extractor.py | SQL extract 22 features từ s360 schema, dùng MATERIALIZED CTE |
| src/ews/inference_service.py | load_model, run_inference, load_ensemble, run_ensemble_inference, compute_shap_drivers |
| src/ews/pipeline_runner.py | run_pipeline() — điều phối extract → inference → persist |
| src/ews/job_worker.py | DB-backed FIFO queue worker (process_next_ews_job) |
| src/ews/risk_config.py + risk_weights.yaml | Risk configuration, factor keys |
| src/ews/ews_config_service.py | get_effective_config() theo trường |
| src/ews/golden_set.py | Precomputed predictions để verify regression |
| src/api/v1/ews.py | POST /ews/predict, GET /ews/predict/jobs |
| src/models/tables.py | EwsPipelineJob model |
| src/models/gbdt/train_catboost_ews.py | Training script v1 |
| src/models/gbdt/train_catboost_ews_ensemble.py | Training script v2 ensemble |

---

## 4. Luồng hoạt động chi tiết

### Bước 1: BGH kích hoạt

BGH vào control panel → chọn filter (trường, năm, kỳ, tuần, model version)
- Frontend POST /api/v1/ews/predict
- Backend kiểm tra ADMIN/PRINCIPAL role
- Tạo EwsPipelineJob (status=pending)
- Trả về job_id → frontend poll

### Bước 2: Job worker xử lý

process_next_ews_job():
- Quét timeout: job "processing" > 5 phút → "failed" (self-healing)
- Nếu có job đang processing → hoãn (chỉ chạy 1 job/lần)
- Lấy job pending cũ nhất → chuyển sang "processing"
- Gọi run_pipeline()

### Bước 3: Feature extraction

run_pipeline() gọi feature_extractor.py:
- SQL query từ s360 schema, dùng MATERIALIZED CTE
- 22 features được tính từ 5 bảng s360:
  + 9 temporal scores: fact_gradebooks + fact_gradebooks_moet
  + 5 LMS: fact_so_assignment_grade + dim_so_assignment
  + 4 attendance: fact_so_daily_attendance + absent_logs + late_attendances
  + 3 behavior: fact_behavior_logs
  + 3 context: dim_subject + dim_homeroom_class_student

### Bước 4: Inference

run_pipeline() gọi inference_service.py:
- Config check: use_ensemble = true/false
- true → load_ensemble() → run_ensemble_inference() → 5 folds average
- false → load_model() → run_inference() → single CatBoost
- compute_shap_drivers() → top-N feature importance cho mỗi HS

### Bước 5: Persist

UPSERT vào fact_student_subject_risk_predictions:
- ON CONFLICT (student_code, subject_id, school_year_id, semester_index, evaluated_at_week, model_version)
- DO UPDATE: risk_score, risk_level, risk_probability, shap_drivers

### Bước 6: Hoàn tất

- Cập nhật job progress → 100%
- Đánh dấu job "completed", lưu rows_processed
- Worker đệ quy xử lý job pending tiếp theo (nếu có)
- Frontend poll thấy status=completed → hiển thị kết quả

---

## 5. 22 Features Map

| # | Nhóm | Feature | Nguồn |
|---|------|---------|-------|
| 1-3 | Context | subject_id, subject_category, grade_level | dim_subject, dim_homeroom_class_student |
| 4-12 | Temporal Scores | weighted_early_avg, weighted_late_avg, score_slope, score_volatility, max_drop, last_score, max_coefficient_so_far, high_weight_score_count, last_high_weight_score | fact_gradebooks + fact_gradebooks_moet |
| 13-17 | LMS | lms_avg_score, lms_recent_drop, lms_submission_rate, lms_recent_submission_rate, lms_gradebook_gap | fact_so_assignment_grade + dim_so_assignment |
| 18-21 | Attendance | daily_absence_rate, unexcused_absent_rate, excused_absent_days, total_late_count | fact_so_daily_attendance + absent_logs + late_attendances |
| 22-24 | Behavior | total_demerit_points, repeat_offense_count, severe_sanction_count | fact_behavior_logs |

---

## 6. Kết quả đạt được

| Hạng mục | Trạng thái | Chi tiết |
|----------|-----------|----------|
| DB-backed FIFO queue | Hoạt động | 1 job/lần, timeout 5p, startup self-healing |
| Feature extraction SQL | Hoạt động | MATERIALIZED CTE, tối ưu từ 86s → <5s |
| CatBoost v1 inference | Hoạt động | single model |
| CatBoost v2 ensemble | Hoạt động | 5-fold ensemble averaging |
| SHAP drivers | Hoạt động | Feature importance cho từng HS |
| Golden set verification | Hoạt động | Precomputed predictions, detect regression |
| Per-school config | Hoạt động | Baseline + override weights |
| Risk level classification | Hoạt động | risk_score, risk_level, risk_probability |
| Progress tracking | Hoạt động | Frontend poll job.progress 0-100% |


