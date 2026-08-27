# EWS Pipeline (Early Warning System)

- **Mục đích**: Dự đoán nguy cơ học sinh rớt môn dựa trên 22 features (điểm, LMS, điểm danh, hạnh kiểm) → CatBoost ensemble inference → SHAP drivers → lưu vào `fact_student_subject_risk_predictions`. DB-backed FIFO queue, chỉ chạy 1 job/lần.
- **Phân hệ**: EWS / ML Pipeline
- **Trạng thái**: ✅ Đang hoạt động

---

## 1. Sơ đồ luồng

```mermaid
graph TD
    A[BGH/Frontend<br/>Control Panel] -->|POST /api/v1/ews/predict| B[ews.py API]
    B -->|Tạo EwsPipelineJob pending| C[(ews_pipeline_jobs)]
    C -->|Background task| D[job_worker.py]
    D -->|process_next_ews_job| E[pipeline_runner.py]
    E -->|run_pipeline| F[feature_extractor.py]
    F -->|22 features<br/>SQL từ s360 schema| G[(s360.fact_gradebooks<br/>dim_so_assignment<br/>fact_so_daily_attendance<br/>fact_behavior_logs)]
    E -->|Features array| H[inference_service.py]
    H -->|v1 CatBoost model| I[(models/)]
    H -->|v2_ensemble (5 folds)| J[(models/ensemble/)]
    H -->|SHAP drivers| K[compute_shap_drivers]
    E -->|Upsert predictions| L[(s360.fact_student_subject_risk_predictions)]
    D -->|Cập nhật progress| C
    D -->|Poll UI| M[Frontend: /admin/ews]
```

---

## 2. Các bước chi tiết

| Bước | Nơi xử lý | Hành động | File liên quan |
|------|-----------|-----------|----------------|
| 1 | `frontend/src/app/admin/ews/` | BGH cấu hình filter (trường, năm, kỳ, tuần) + bấm "Dự đoận" | `src/api/v1/ews.py` |
| 2 | `src/api/v1/ews.py` | Nhận request, kiểm tra `ADMIN`/`PRINCIPAL` role, tạo `EwsPipelineJob` status=pending | `src/api/v1/ews.py` |
| 3 | `src/main.py` (lifespan) | Startup tự động chạy `process_next_ews_job()` + self-healing job kẹt | `src/main.py` |
| 4 | `src/ews/job_worker.py` | FIFO queue: quét timeout (5p) → chống kẹt → lấy job pending cũ nhất → processing | `src/ews/job_worker.py` |
| 5 | `src/ews/pipeline_runner.py` | `run_pipeline()`: Extract Features → Inference → Persist. Gọi `_update_progress` callback để UI poll | `src/ews/pipeline_runner.py` |
| 6 | `src/ews/feature_extractor.py` | SQL extract 22 features từ s360 schema: 9 temporal scores + 5 LMS + 4 attendance + 3 behavior + 3 context | `src/ews/feature_extractor.py` |
| 7 | `src/ews/inference_service.py` | `load_model(path)` CatBoost → `run_inference()` cho v1; `load_ensemble()` 5 folds → `run_ensemble_inference()` cho v2 | `src/ews/inference_service.py` |
| 8 | `src/ews/inference_service.py` | `compute_shap_drivers()` → top-N feature ảnh hưởng nhất mỗi học sinh | `src/ews/inference_service.py` |
| 9 | `src/ews/pipeline_runner.py` | Upsert SQL vào `fact_student_subject_risk_predictions` (ON CONFLICT DO UPDATE theo student+subject+week) | `src/ews/pipeline_runner.py` (UPSERT_SQL) |
| 10 | `src/ews/job_worker.py` | Đánh dấu job completed, đệ quy xử lý job pending tiếp theo | `src/ews/job_worker.py` |
| 11 | `src/api/v1/ews.py` | Frontend poll `GET /ews/predict/jobs/{id}` → hiển thị progress + kết quả | `src/api/v1/ews.py` |

---

## 3. 22 Features chi tiết

```python
EWS_FEATURE_COLS = [
    # Categorical + Context (3)
    "subject_id", "subject_category", "grade_level",
    # Temporal Scores (9)
    "weighted_early_avg", "weighted_late_avg", "score_slope",
    "score_volatility", "max_drop", "last_score",
    "max_coefficient_so_far", "high_weight_score_count", "last_high_weight_score",
    # LMS (5)
    "lms_avg_score", "lms_recent_drop", "lms_submission_rate",
    "lms_recent_submission_rate", "lms_gradebook_gap",
    # Attendance (4)
    "daily_absence_rate", "unexcused_absent_rate",
    "excused_absent_days", "total_late_count",
    # Behavior (3)
    "total_demerit_points", "repeat_offense_count", "severe_sanction_count",
]
```

Nguồn dữ liệu:
- **9 Temporal**: `s360.fact_gradebooks` UNION `fact_gradebooks_moet`
- **5 LMS**: `s360.fact_so_assignment_grade` JOIN `dim_so_assignment`
- **4 Attendance**: `s360.fact_so_daily_attendance` LEFT JOIN `fact_absent_logs` & `late_attendances`
- **3 Behavior**: `s360.fact_behavior_logs`

---

## 4. File map

```
📁 src/ews/
├── feature_extractor.py            # SQL extract 22 features, pandas processing (MATERIALIZED CTE)
├── inference_service.py            # load_model, run_inference, load_ensemble, run_ensemble_inference, compute_shap_drivers, compute_ensemble_shap_drivers
├── pipeline_runner.py              # run_pipeline() — điều phối extract → inference → persist
├── job_worker.py                   # DB-backed FIFO queue worker (process_next_ews_job)
├── risk_config.py                  # RiskConfig, FACTOR_KEYS, risk_weights.yaml loading
├── risk_weights.yaml               # Weight mapping cho 4 pillar risk scores
├── ews_config_service.py           # get_effective_config() — baseline + override theo trường
├── golden_set.py                   # Golden set: precomputed predictions để verify regression
├── golden_set_data.json            # Mock golden set data
├── llm_forecasting.py              # LLM-based forecasting (secondary channel)
├── interdisciplinary_service.py    # Cross-subject interdisciplinary risk analysis
├── lms_evidence.py                 # LMS evidence integration

📁 src/api/v1/
├── ews.py                           # POST /ews/predict, GET /ews/predict/jobs/{id}, GET /ews/predict/jobs

📁 src/models/
├── tables.py                        # EwsPipelineJob model
└── gbdt/
    ├── train_catboost_ews.py        # Training script v1
    └── train_catboost_ews_ensemble.py  # Training script v2 (5-fold ensemble)

📁 models/
├── catboost_ews_v1.cbm             # Trained CatBoost model v1
└── ensemble_v2/                     # 5-fold ensemble models
```

---

## 5. RBAC

| Vai trò | Quyền | Ghi chú |
|---------|-------|---------|
| ADMIN | ✅ Chạy pipeline + xem mọi kết quả | Toàn quyền |
| PRINCIPAL | ✅ Chạy pipeline + xem toàn trường | Scope theo trường |
| SUBJECT_HEAD | ❌ Chỉ xem kết quả môn phụ trách | Không chạy pipeline |
| SUBJECT_TEACHER | ❌ Chỉ xem kết quả lớp/môn dạy | Không chạy pipeline |
| HOMEROOM_* | ❌ Chỉ xem kết quả lớp chủ nhiệm | Không chạy pipeline |
| GRADE_HEAD | ❌ Chỉ xem kết quả khối | Không chạy pipeline |

---

## 6. Database tables liên quan

| Bảng | Mục đích |
|------|----------|
| `ews_pipeline_jobs` | Hàng chờ job EWS: status, progress, model_version, kết quả |
| `s360.fact_student_subject_risk_predictions` | Kết quả dự đoán (risk_score, risk_level, risk_probability, shap_drivers) |
| `s360.dim_homeroom_class_student` | Học sinh theo lớp (join_date dùng cho window) |
| `s360.fact_gradebooks` | Điểm số thực tế môn học |
| `s360.fact_so_assignment_grade` | LMS assignment grades |
| `s360.fact_so_daily_attendance` | Điểm danh hằng ngày |
| `s360.fact_behavior_logs` | Vi phạm hạnh kiểm |

---

## 7. Lưu ý kỹ thuật (Gotchas)

1. **⚠️ Chỉ chạy 1 job/lần**: Job worker kiểm tra có `processing` job nào không trước khi lấy pending. Nếu có → return ngay, không xếp chồng.

2. **⚠️ Timeout 5 phút**: Job nào ở "processing" quá 5 phút → tự động đánh dấu "failed". Phòng trường hợp worker crash giữa chừng.

3. **⚠️ MATERIALIZED CTE**: Feature extractor SQL dùng `AS MATERIALIZED` cho các CTE nặng (`student_grades`, `all_scores`, `lms_features`) để tránh PostgreSQL Nested Loop (đã từng ~86s → vượt statement_timeout). Bắt buộc giữ MATERIALIZED nếu sửa query.

4. **⚠️ Golden set**: `golden_set.py` chứa precomputed predictions để verify sau mỗi lần train/redeploy. Nếu test sai lệch > threshold → cảnh báo.

5. **⚠️ Model versioning**: `model_version` (varchar) trong `EwsPipelineJob` và `fact_student_subject_risk_predictions` để trace model nào sinh prediction nào.

6. **⚠️ v1 vs v2_ensemble**: `run_pipeline` check config `use_ensemble`. v1 là single CatBoost, v2 là ensemble 5 folds (stacking average). SHAP drivers được tính riêng cho ensemble.

7. **⚠️ Startup self-healing**: Khi backend restart, mọi job "processing" cũ được đánh dấu "failed" + khởi chạy lại queue.

---

## 8. Cách chạy thử

```bash
# Chạy EWS pipeline từ command line (không qua queue)
python scripts/run_ews_pipeline.py

# Gọi API
curl -X POST http://localhost:8000/api/v1/ews/predict \
  -H "Authorization: Bearer <token_admin>" \
  -H "Content-Type: application/json" \
  -d '{"school_year_id": 2025, "semester_index": 1, "evaluated_at_week": 12}'

# Xem job status
curl http://localhost:8000/api/v1/ews/predict/jobs \
  -H "Authorization: Bearer <token_admin>"

# Test
pytest tests/test_ews*.py -v
```