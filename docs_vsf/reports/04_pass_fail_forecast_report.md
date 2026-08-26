# BÁO CÁO — Pass/Fail Forecast Flow

**Người viết**: [Tên] | **Ngày**: 26/08/2026

---

## 1. Giới thiệu

Pass/Fail Forecast dự đoán tỷ lệ học sinh pass/fail cho đề thi cuối kỳ, dựa trên năng lực LMS cấp bài + trọng số unit của đề + độ khó CDI. Đây là module **thuần logic** (không ML, không LLM) — chỉ dùng công thức tính.

---

## 2. Kiến trúc tổng quan

```
GV chọn đề cuối kỳ (exam_paper_id)
       │
       ▼
┌──────────────────┐
│  Load exam_      │  ← exam_competencies: unit_id, weight
│  competencies    │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Load CDI        │  ← exam_papers.content_difficulty (có thể NULL)
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Load LMS        │  ← student_unit_mastery.raw_mastery
│  mastery (batch) │     (1 query cho tất cả HS, chống N+1)
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  resolve_        │  ← Chuỗi fallback:
│  abilities()     │     bài có LMS → raw×10
│                  │     thiếu → TB chương
│                  │     chương trống → TB môn
│                  │     không LMS → None (INSUFFICIENT)
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  forecast_exam() │  ← predict_student_score() × CDI_adj
│  + classify      │     → PASS / FAIL / BORDERLINE / INSUFFICIENT
│  _verdict()      │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  summarize()     │  ← Tổng hợp: pass, fail, borderline,
│  + weak_units()  │     fail_rate, weak units top 2
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Frontend        │  ← Biểu đồ + bảng kết quả
│  (biểu đồ)       │
└──────────────────┘
```

---

## 3. Các thành phần chính

| File | Vai trò |
|------|---------|
| src/services/pass_fail_forecast.py | Core logic: resolve_abilities, forecast_exam, predict_student_score, classify_verdict, summarize, compute_weak_units |
| src/api/v1/pass_fail_forecast.py | GET /pass-fail-forecast |
| src/schemas/pass_fail_forecast.py | PassFailForecastResult, StudentForecastRow |
| frontend/src/app/pass-fail-forecast/ | Trang frontend |

---

## 4. Luồng hoạt động chi tiết

### Bước 1: GV chọn đề

GV chọn exam_paper_id (đề cuối kỳ đã map unit qua exam_competencies)

### Bước 2: Load dữ liệu

- **Load exam_units**: SELECT unit_id, weight FROM exam_competencies WHERE exam_paper_id = :eid
- **Load CDI**: SELECT content_difficulty FROM exam_papers WHERE id = :eid (NULL nếu chưa phân tích)
- **Load LMS mastery**: 1 query batch cho tất cả HS (tránh N+1)

### Bước 3: Resolve abilities

Với mỗi HS, resolve ability cho từng unit trong đề:
- Unit có LMS data → ability = raw_mastery × 10
- Unit thiếu → trung bình chương của HS đó
- Chương trống → trung bình toàn môn của HS
- Không LMS gì cả → None (INSUFFICIENT)

### Bước 4: Dự đoán điểm

```
predicted_score = ( Σ(weight_u × ability_u) / Σ(weight) ) × difficulty_adj(CDI)

difficulty_adj(CDI) = 1.0 + (0.5 - CDI) × 0.5
  CDI=0.0 (dễ) → adj=1.25
  CDI=0.5 (vừa) → adj=1.0
  CDI=1.0 (khó) → adj=0.75
```

### Bước 5: Phân loại

| predicted_score | Verdict |
|----------------|---------|
| >= 5.5 | PASS |
| < 4.5 | FAIL |
| 4.5 - 5.5 | BORDERLINE |
| None | INSUFFICIENT |

### Bước 6: Tổng hợp

- **summarize()**: pass_count, fail_count, borderline_count, insufficient_count, fail_rate
- **compute_weak_units()**: top 2 bài yếu nhất (loss = (10 - ability) × weight)

---

## 5. Công thức

```
predicted_score = weighted_ability_avg × difficulty_adj(CDI)

weighted_ability_avg = Σ(weight_u × ability_u) / Σ(weight_u)

ability_u = raw_mastery × 10  (0..10)
CDI_adj = 1.0 + (0.5 - CDI) × 0.5  (0.75..1.25)

Verdict:
  >= 5.5 → PASS
  < 4.5  → FAIL
  else   → BORDERLINE
  None   → INSUFFICIENT
```

---

## 6. So sánh với EWS

| Tiêu chí | Pass/Fail Forecast | EWS Pipeline |
|----------|-------------------|--------------|
| Cách tiếp cận | Công thức thuần (Σ ability × weight × CDI) | CatBoost ML (22 features) |
| Đầu vào | LMS mastery (1 nguồn) | 4 nguồn (điểm, LMS, điểm danh, hạnh kiểm) |
| Đầu ra | Dự đoán điểm 0-10 + verdict | Risk score + probability + SHAP |
| Thời điểm | Trước thi cuối kỳ | Bất kỳ (weekly evaluation) |
| Người dùng | GV bộ môn | BGH |
| Phụ thuộc DWH | Không (dùng public schema) | Có (s360 schema) |

---

## 7. Kết quả đạt được

| Hạng mục | Trạng thái | Chi tiết |
|----------|-----------|----------|
| resolve_abilities | Hoạt động | Chuỗi fallback 4 cấp (bài→chương→môn→None) |
| forecast_exam | Hoạt động | Dự đoán điểm từng HS |
| classifiy_verdict | Hoạt động | PASS/FAIL/BORDERLINE/INSUFFICIENT |
| summarize | Hoạt động | Tổng hợp tỷ lệ pass/fail |
| compute_weak_units | Hoạt động | Top 2 bài yếu nhất cho mỗi HS |
| CDI adjustment | Hoạt động | Điều chỉnh điểm theo độ khó nội dung |
| Batch query chống N+1 | Hoạt động | 1 query LMS cho tất cả HS |
| Pure function | Hoạt động | Module không DB, không LLM → dễ test |

---

## 8. Cách chạy thử

```bash
# 1. API
curl "http://localhost:8000/api/v1/pass-fail-forecast?exam_paper_id=101&subject_id=1&semester_index=1" \
  -H "Authorization: Bearer <token>"

# 2. Test unit (pure functions, không cần DB)
pytest tests/test_pass_fail_forecast.py -v
```
