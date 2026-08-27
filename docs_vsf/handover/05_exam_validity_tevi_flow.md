# Exam Validity & TEVI Analysis Flow

- **Mục đích**: Tam giác hóa độ khó đề thi (TEVI) — đối chiếu **EDI** (Empirical Difficulty Index — độ khó thực nghiệm từ điểm số) với **CDI** (Content Difficulty Index — độ khó nội dung từ Bloom/chuẩn CT) → phát hiện phân kỳ bất thường (lạm phát điểm, nghi lộ đề, lỗ hổng dạy-học). Cảnh báo công bằng đánh giá (Student Fairness).
- **Phân hệ**: Analytics / Exam Validity
- **Trạng thái**: ✅ Đang hoạt động

---

## 1. Sơ đồ luồng

```mermaid
graph TD
    subgraph "TEVI — Tam giác hóa"
        A[BGH chọn kỳ/môn/khối] -->|GET /analytics/exam-validity| B[exam_validity.py API]
        B -->|Query view v_exam_validity| C[(v_exam_validity)]
        C -->|so_school_id = user.school_id| D[compute_validity]
        D -->|Nếu flagged_only| E[Lọc: FLAG != VALID & NO_CONTENT]
        D -->|Xếp hạng| F[ExamValidityRead[]]
        
        G[BGH xem tổng quan] -->|GET /analytics/exam-validity/overview| H[school_overview]
        H -->|Đếm số cờ + top đề rà soát| I[SchoolValidityOverview]
        
        J[Xếp hạng lớp theo thực lực] -->|GET /analytics/content-adjusted-ranking| K[content_adjusted_ranking]
        K -->|Neo theo CDI + TB cohort| L[ContentAdjustedRankRow[]]
    end

    subgraph "Student Fairness"
        M[BGH kiểm tra công bằng] -->|GET /analytics/student-fairness| N[student_fairness.py]
        N -->|Đối chiếu TX vs GK/CK theo CDI| O{Phát hiện}
        O -->|TX khó + điểm cao, GK/CK thấp| P[SUSPECT_FAVORITISM]
        O -->|TX thấp, GK/CK cao| Q[SUSPECT_SUPPRESSION]
        P & Q --> R[StudentFairnessRow[]]
    end
```

---

## 2. Các bước chi tiết — TEVI

| Bước | Nơi xử lý | Hành động | File liên quan |
|------|-----------|-----------|----------------|
| 1 | `frontend/src/app/exam-difficulty/` | BGH chọn semester, subject (optional), grade (optional), bật "flagged_only" | `src/api/v1/exam_validity.py` |
| 2 | `src/api/v1/exam_validity.py` | `get_exam_validity()` — filter `so_school_id`, semester_id, optional subject_id/grade_id/score_category | `src/api/v1/exam_validity.py` |
| 3 | `src/services/exam_validity.py` | `compute_validity()` — query view `v_exam_validity` với bộ lọc | `src/services/exam_validity.py` |
| 4 | **Materialized View** | `v_exam_validity` tự tính: `EDI = 1.0 - mean_score/10.0`, `CDI` từ `exam_papers.content_difficulty`, `divergence = CDI - EDI`, `flag` theo ngưỡng | `src/services/exam_validity.py` + migration |
| 5 | `src/services/exam_validity.py` | `_confidence()` — `HIGH` nếu `n >= 30` và `cdi IS NOT NULL`, ngược lại `LOW` | `src/services/exam_validity.py` |
| 6 | `src/api/v1/exam_validity.py` | `get_exam_validity_overview()` — `school_overview()` đếm flag + top đề rà soát (chỉ ADMIN/PRINCIPAL) | `src/api/v1/exam_validity.py` |
| 7 | `src/api/v1/exam_validity.py` | `get_content_adjusted_ranking()` — xếp hạng lớp theo thực lực neo-nội-dung | `src/api/v1/exam_validity.py` |

---

## 3. Các bước chi tiết — Student Fairness

| Bước | Nơi xử lý | Hành động | File liên quan |
|------|-----------|-----------|----------------|
| 1 | `frontend/src/app/exam-difficulty/` | BGH chọn semester, optional subject_id → bấm "Cảnh báo công bằng" | `src/api/v1/exam_validity.py` |
| 2 | `src/api/v1/exam_validity.py` | `get_student_fairness()` — chỉ ADMIN/PRINCIPAL (không SUBJECT_HEAD — tránh xung đột lợi ích) | `src/api/v1/exam_validity.py` |
| 3 | `src/services/student_fairness.py` | Query SQL: `tx_cdi_by_class` (CDI từ exam_column_mappings cho REGULAR) + `periodic_cdi_by_grade` (CDI có trọng số GK×2, CK×3) | `src/services/student_fairness.py` |
| 4 | `src/services/student_fairness.py` | So sánh: `tx_cdi >= 0.6` (khó) + `tx_avg >= 8.0` (cao) + `periodic_avg <= 5.0` (thấp) + gap ≥ 3.0 → **SUSPECT_FAVORITISM** | `src/services/student_fairness.py` |
| 5 | `src/services/student_fairness.py` | So sánh: `periodic_avg >= 8.0` + `tx_avg <= 5.0` + gap ≥ 3.0 → **SUSPECT_SUPPRESSION** | `src/services/student_fairness.py` |
| 6 | `src/services/student_fairness.py` | Cần ít nhất 2 cột TX (`_MIN_COLUMNS = 2`) để đủ tin cậy | `src/services/student_fairness.py` |

---

## 4. File map

```
📁 src/services/
├── exam_validity.py                 # compute_validity(), school_overview(), content_adjusted_ranking()
├── student_fairness.py              # Student fairness SQL query + flag logic

📁 src/api/v1/
├── exam_validity.py                 # GET /analytics/exam-validity, /exam-validity/overview, /content-adjusted-ranking, /student-fairness

📁 src/schemas/
├── exam_validity.py                 # ExamValidityRead, SchoolValidityOverview, ContentAdjustedRankRow
├── student_fairness.py              # StudentFairnessRow

📁 frontend/src/app/
├── exam-difficulty/                 # Trang TEVI + Student Fairness
├── admin/                           # Overview cho BGH
```

---

## 5. RBAC

| Vai trò | TEVI | Student Fairness | Ghi chú |
|---------|------|-----------------|---------|
| ADMIN | ✅ Toàn quyền | ✅ Toàn quyền | |
| PRINCIPAL | ✅ Toàn quyền | ✅ Toàn quyền | |
| SUBJECT_HEAD | ✅ Môn phụ trách (detail) | ❌ (tránh xung đột lợi ích) | Chỉ xem dòng, không overview |
| SUBJECT_TEACHER | ❌ | ❌ | |
| HOMEROOM_* | ❌ | ❌ | |
| GRADE_HEAD | ❌ | ❌ | |

Endpoint `/student-fairness` đặc biệt nhạy cảm — chỉ ADMIN/PRINCIPAL.

---

## 6. Database tables liên quan

| Table / View | Mục đích |
|-------------|----------|
| `v_exam_validity` | Materialized view: EDI, CDI, divergence, flag (HAMMER/INFLATED/SUSPICIOUS/VALID/NO_CONTENT/LOW_SAMPLE) |
| `exam_papers` | content_difficulty (CDI), score_category, subject_id |
| `exam_competencies` | unit_id, weight (cho CDI tổng hợp) |
| `exam_column_mappings` | Map đề → cột điểm (REGULAR/MIDTERM/FINAL) |
| `scores` | score_category, status=APPROVED, value |
| `students` | student_code, full_name |

---

## 7. Lưu ý kỹ thuật (Gotchas)

1. **⚠️ View `v_exam_validity` là **materialized view** — cần refresh định kỳ hoặc sau khi nhập điểm xong. Không tự cập nhật real-time.

2. **⚠️ Confidence `LOW`**: Khi `n < 30` hoặc `cdi IS NULL` → flag ở `LOW` confidence. Đề chưa có CDI (chưa phân tích nội dung) không được tam giác hóa đầy đủ.

3. **⚠️ Student Fairness là TÍN HIỆU CẢNH BÁO, KHÔNG phải kết luận**: Chênh lệch có thể do nguyên nhân khác (ốm, ôn lệch). BGH cần rà soát thêm.

4. **⚠️ Ngưỡng `_MIN_COLUMNS = 2`**: Cần ít nhất 2 cột điểm TX mới phát hiện fairness — nếu chỉ có 1 cột TX, bỏ qua.

5. **⚠️ Role `SUBJECT_HEAD` bị chặn khỏi Student Fairness**: Vì endpoint này nhắm vào GV/HS cụ thể, tránh xung đột lợi ích với trưởng bộ môn.

6. **⚠️ `content_adjusted_ranking`**: Xếp hạng lớp theo thực lực đã neo độ khó nội dung, độc lập với cohort. Dùng cho BGH đánh giá chất lượng dạy học công bằng.

---

## 8. Cách chạy thử

```bash
# 1. Xem bảng tam giác hóa toàn trường
curl "http://localhost:8000/api/v1/analytics/exam-validity?semester_id=1&flagged_only=true" \
  -H "Authorization: Bearer <token_admin>"

# 2. Xem tổng quan
curl "http://localhost:8000/api/v1/analytics/exam-validity/overview?semester_id=1" \
  -H "Authorization: Bearer <token_admin>"

# 3. Student fairness
curl "http://localhost:8000/api/v1/analytics/student-fairness?semester_id=1" \
  -H "Authorization: Bearer <token_admin>"

# 4. Content-adjusted ranking
curl "http://localhost:8000/api/v1/analytics/content-adjusted-ranking?grade_id=1&semester_id=1&subject_id=1" \
  -H "Authorization: Bearer <token_admin>"

# 5. Test
pytest tests/test_exam_validity_*.py tests/test_student_fairness_service.py -v
```