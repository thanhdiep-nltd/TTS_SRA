# BÁO CÁO — Exam Validity & TEVI Analysis Flow

**Người viết**: [Tên] | **Ngày**: 26/08/2026

---

## 1. Giới thiệu

TEVI (Triangulation of Exam Validity & Integrity) là hệ thống đối chiếu 2 chỉ số độc lập để đánh giá độ tin cậy của điểm số:

- **EDI** (Empirical Difficulty Index): độ khó thực nghiệm từ điểm số thật của HS
- **CDI** (Content Difficulty Index): độ khó nội dung từ phân tích Bloom/chuẩn CT

Khi EDI và CDI lệch nhau → phát hiện bất thường (đề quá khó/quá dễ/nghi lộ đề).

Ngoài ra, **Student Fairness** phát hiện 2 dạng cảnh báo công bằng đánh giá:
- SUSPECT_FAVORITISM: nghi ưu ái ở điểm TX
- SUSPECT_SUPPRESSION: nghi chèn ép ở điểm TX

---

## 2. Kiến trúc tổng quan

### TEVI — Tam giác hóa

```
BGH chọn: kỳ, môn, khối
       │
       ▼
┌──────────────────┐
│  v_exam_validity │  ← Materialized view (tự tính EDI, CDI, divergence, flag)
│  (view)          │
└──────┬───────────┘
       │
       ├──► compute_validity()       → ExamValidityRead[] (chi tiết từng đề)
       ├──► school_overview()        → SchoolValidityOverview (tổng quan toàn trường)
       └──► content_adjusted_ranking() → ContentAdjustedRankRow[] (xếp hạng lớp)
```

### Student Fairness

```
BGH kiểm tra công bằng
       │
       ▼
┌──────────────────┐
│  student_fairness│  ← SQL query đối chiếu TX vs GK/CK
│  .py             │
└──────┬───────────┘
       │
       ├──► TX CDI cao + TX điểm cao + GK/CK thấp → SUSPECT_FAVORITISM
       └──► TX điểm thấp + GK/CK cao → SUSPECT_SUPPRESSION
```

---

## 3. Các thành phần chính

| File | Vai trò |
|------|---------|
| src/services/exam_validity.py | compute_validity(), school_overview(), content_adjusted_ranking() |
| src/services/student_fairness.py | SQL query + flag logic cho fairness |
| src/api/v1/exam_validity.py | GET /analytics/exam-validity, /overview, /content-adjusted-ranking, /student-fairness |
| src/schemas/exam_validity.py | ExamValidityRead, SchoolValidityOverview, ContentAdjustedRankRow |
| src/schemas/student_fairness.py | StudentFairnessRow |

---

## 4. Luồng hoạt động chi tiết

### TEVI

**EDI và CDI là gì?**

```
EDI = 1.0 - mean_score/10.0
  → 0 = dễ (HS làm tốt), 1 = khó (HS làm kém)

CDI = content_difficulty từ exam_papers
  → 0 = dễ (nội dung cơ bản), 1 = khó (Bloom cao)

divergence = CDI - EDI
  → divergence > 0: đề khó hơn thực tế (điểm thấp bất thường) → HAMMER
  → divergence < 0: đề dễ hơn thực tế (điểm cao bất thường) → INFLATED
  → divergence ≈ 0: đề tốt, đo đúng năng lực → VALID
```

**Flag system:**

| Flag | Điều kiện | Ý nghĩa |
|------|----------|---------|
| VALID | divergence gần 0 | Đề tốt, đo đúng năng lực |
| HAMMER | divergence dương cao | Đề khó hơn thực tế, điểm thấp bất thường |
| INFLATED | divergence âm cao | Điểm cao hơn năng lực thực, nghi lạm phát điểm |
| SUSPICIOUS | borderline | Cần rà soát thêm |
| NO_CONTENT | CDI chưa có | Chưa phân tích nội dung đề |
| LOW_SAMPLE | n < 30 | Mẫu quá nhỏ, không kết luận |

**Bước 1: BGH chọn filter**
- Chọn học kỳ, môn (optional), khối (optional), bật flagged_only (optional)

**Bước 2: Query v_exam_validity**
- Filter WHERE so_school_id = user.school_id AND semester_id = ...
- Nếu flagged_only=true → WHERE flag NOT IN ('VALID', 'NO_CONTENT')

**Bước 3: Tính confidence**
- HIGH: n >= 30 AND cdi IS NOT NULL
- LOW: n < 30 OR cdi IS NULL

**Bước 4: Trả kết quả**
- Chi tiết: ExamValidityRead[] (exam_paper_id, subject, grade, n, mean_score, edi, cdi, divergence, flag, confidence)
- Overview: SchoolValidityOverview (đếm flag, top đề rà soát)
- Ranking: ContentAdjustedRankRow[] (xếp hạng lớp theo thực lực)

### Student Fairness

**Bước 1: BGH chọn semester**
- Endpoint: GET /analytics/student-fairness?semester_id=1
- Chỉ ADMIN/PRINCIPAL (không SUBJECT_HEAD — tránh xung đột lợi ích)

**Bước 2: Tính CDI theo lớp**
- tx_cdi_by_class: AVG CDI của exam_column_mappings cho REGULAR (theo lớp)
- periodic_cdi_by_grade: CDI weighted average (GK×2 + CK×3) / 5 (theo khối)

**Bước 3: Phát hiện bất thường**

| Dạng | Điều kiện | Ý nghĩa sư phạm |
|------|----------|-----------------|
| FAVORITISM | TX CDI >= 0.6 (khó) + TX avg >= 8.0 + GK/CK avg <= 5.0 + gap >= 3.0 | Nghi GV "tủ đề" hoặc ưu ái khi chấm TX |
| SUPPRESSION | TX avg <= 5.0 + GK/CK avg >= 8.0 + gap >= 3.0 | Nghi bị "chèn ép" ở TX |

**Lưu ý: Đây là TÍN HIỆU CẢNH BÁO để BGH rà soát, KHÔNG phải kết luận.**

---

## 5. Kết quả đạt được

| Hạng mục | Trạng thái | Chi tiết |
|----------|-----------|----------|
| v_exam_validity view | Hoạt động | Materialized view, tự tính EDI/CDI/divergence/flag |
| compute_validity | Hoạt động | Lọc theo môn, khối, kỳ, flagged_only |
| school_overview | Hoạt động | Đếm flag, top đề rà soát |
| content_adjusted_ranking | Hoạt động | Xếp hạng lớp neo-CDI |
| Student Fairness: FAVORITISM | Hoạt động | Phát hiện ưu ái TX |
| Student Fairness: SUPPRESSION | Hoạt động | Phát hiện chèn ép TX |
| RBAC chặt chẽ | Hoạt động | Student Fairness chỉ ADMIN/PRINCIPAL |
| Confidence mapping | Hoạt động | HIGH/LOW theo n >= 30 và CDI có |

---

## 6. Cách chạy thử

```bash
# 1. Xem bảng tam giác hóa toàn trường
curl "http://localhost:8000/api/v1/analytics/exam-validity?semester_id=1&flagged_only=true" \
  -H "Authorization: Bearer <token_admin>"

# 2. Xem tổng quan toàn trường
curl "http://localhost:8000/api/v1/analytics/exam-validity/overview?semester_id=1" \
  -H "Authorization: Bearer <token_admin>"

# 3. Student fairness
curl "http://localhost:8000/api/v1/analytics/student-fairness?semester_id=1" \
  -H "Authorization: Bearer <token_admin>"

# 4. Xếp hạng lớp theo thực lực
curl "http://localhost:8000/api/v1/analytics/content-adjusted-ranking?grade_id=1&semester_id=1&subject_id=1" \
  -H "Authorization: Bearer <token_admin>"

# 5. Test
pytest tests/test_exam_validity_*.py tests/test_student_fairness_service.py -v
```
