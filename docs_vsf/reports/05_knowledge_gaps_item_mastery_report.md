# BÁO CÁO — Chẩn đoán Lỗ hổng Kiến thức & Năng lực Học sinh (Knowledge Gaps & Item Mastery)

**Người viết**: [Tên] | **Ngày**: 27/08/2026

---

## 1. Giới thiệu

Chẩn đoán Lỗ hổng Kiến thức (Knowledge Gap Diagnosis) là hệ thống đánh giá năng lực chi tiết của học sinh theo **Cây tri thức chuẩn chương trình (Môn học → Khối → Chương → Bài học)**. Hệ thống kết hợp 2 nguồn dữ liệu độc lập:
1. **Nguồn 1 - LMS (Online):** Hàng chục/hàng trăm câu hỏi trắc nghiệm học sinh làm hàng tuần (`lms_question_response`).
2. **Nguồn 2 - Điểm thi trên lớp (Exam/Offline):** Điểm thi tập trung có giám thị trên sổ điểm (`fact_gradebooks`).

Hệ thống tự động phát hiện các bài học học sinh chưa nắm vững (Mastery < 60%), tính toán **Độ tin cậy (Confidence Score)** dựa trên độ bao phủ thang đo Bloom, và thực hiện **Đối soát đa nguồn (Cross-Validation)** để đảm bảo tính trung thực học thuật.

---

## 2. Kiến trúc tổng quan

```
    ┌───────────────────────────┐      ┌──────────────────────────┐
    │     Câu hỏi làm trên LMS  │      │  Điểm thi có giám thị    │
    │  (lms_question_response)  │      │  (fact_gradebooks / MOET)│
    └─────────────┬─────────────┘      └────────────┬─────────────┘
                  │                                 │
                  ▼                                 ▼
    ┌───────────────────────────┐      ┌──────────────────────────┐
    │    Raw Unit Mastery       │      │  Exam Fallback &         │
    │  (Tỷ lệ đúng + Bloom      │      │  Decomposition           │
    │   Breadth/Depth Factor)   │      │  (Phân rã ma trận đề thi)│
    └─────────────┬─────────────┘      └────────────┬─────────────┘
                  │                                 │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │   Merge & Đối Soát Đa Nguồn   │
                   │   (Cross-Validation Engine)   │
                   └───────────────┬───────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │    student_unit_mastery       │
                   │  - adjusted_mastery           │
                   │  - confidence_score & reason  │
                   │  - integrity_status           │
                   └───────────────┬───────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │  Cấp Lớp: get_class_roster    │
                   │  - Majority Vote (Status)     │
                   │  - Average Confidence Score   │
                   │  - Danh sách bài học yếu      │
                   └───────────────┬───────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │   Frontend UI (Next.js)       │
                   │   - Bảng Roster lớp học       │
                   │   - Drawer chi tiết cây bài   │
                   │   - Phân tích Bloom & Đối soát│
                   └───────────────────────────────┘
```

---

## 3. Các thành phần chính

### Backend (Python / FastAPI / PostgreSQL)

| File | Vai trò |
|------|---------|
| `src/services/item_mastery.py` | Core engine: `raw_unit_mastery`, `merge_onclass_adjustment`, `generate_confidence_reason`, tính Bloom Breadth & Depth. |
| `src/api/v1/knowledge_gap.py` | API endpoints: Roster lớp (`/roster`), Chi tiết học sinh (`/student/{code}`), Tính lại năng lực (`/recalc-mastery`). |
| `src/schemas/knowledge_gap.py` | Pydantic schemas: `KnowledgeGapItem`, `StudentRosterSummary`, `ClassRosterResponse`, `MasteryTreeResponse`. |
| `src/models/tables.py` | ORM tables: `StudentUnitMastery`, `LmsQuestionResponse`, `CurriculumUnit`. |
| `scripts/seed_mock_toan6_gaps.py` | Data pipeline sinh dữ liệu chẩn đoán 14 profile học sinh thực tế cho Khối 6. |

### Frontend (Next.js / Tailwind CSS / Lucide)

| File | Vai trò |
|------|---------|
| `frontend/src/app/(app)/knowledge-gaps/page.tsx` | Trang quản lý chính: Lọc theo Môn/Lớp, bảng Roster, Badge đối soát & độ tin cậy. |
| `frontend/src/components/knowledgeGaps/KnowledgeGapDetailDrawer.tsx` | Drawer trượt chi tiết: Cây tri thức phân cấp, biểu đồ Bloom, giải trình đối soát từng bài. |

---

## 4. Luồng hoạt động chi tiết

### Bước 1: Tính Năng Lực Cơ Sở từ LMS (Raw Unit Mastery)
Với mỗi học sinh và mỗi bài học cụ thể:
1. Đếm tổng số câu hỏi đã làm ($N_{items}$) và số câu trả lời đúng ($N_{correct}$).
2. Tính tỷ lệ thành thạo thô: $\text{Base Mastery} = \frac{N_{correct}}{N_{items}}$.
3. Đánh giá độ phủ Bloom:
   - **Độ rộng (Breadth Ratio):** Số bậc Bloom học sinh đã làm / Tổng số bậc Bloom bài học có ($\frac{\text{distinct\_bloom}}{\text{max\_bloom}}$).
   - **Độ sâu (Depth Factor):** Trọng số ghi nhận năng lực ở các câu hỏi mức độ Vận dụng / Vận dụng cao (Bloom 3-6).
4. Tính điểm tin cậy bài học:
   $$\text{c\_volume} = \min(1.0, \frac{N_{items}}{15})$$
   $$\text{c\_bloom} = \sqrt{\text{breadth\_ratio}} \times \text{depth\_factor}$$
   $$\text{Confidence Score} = 0.5 \times \text{c\_volume} + 0.5 \times \text{c\_bloom}$$

### Bước 2: Đối Soát Chéo với Điểm Thi Trên Lớp (Cross-Validation)
1. Lấy điểm thi chính thức gần nhất có giám thị ($Exam$).
2. So sánh độ lệch giữa bài tập LMS và điểm thi:
   $$\Delta = \text{Raw Mastery} - Exam$$
3. Xác định trọng số dung hòa ($lm\_weight, exam\_weight$) và trạng thái đối soát:
   - **Đồng thuận ($|\Delta| \le 0.30$):** $lm = 0.7, exam = 0.3 \rightarrow \text{Trạng thái: } \mathbf{OK}$.
   - **LMS vượt trội ($\Delta > 0.30$):** Học sinh làm online điểm rất cao nhưng thi thật điểm thấp $\rightarrow$ Hạ trọng số LMS ($lm = 0.3, exam = 0.7$), gán cờ cảnh báo $\mathbf{LMS\_EXCEEDS\_EXAM}$.
   - **Điểm thi cao hơn LMS ($\Delta < -0.30$):**
     * Nếu $N_{items} \ge 5$: Học sinh chăm làm bài nhưng hổng bài này $\rightarrow \mathbf{OK}$ (Lỗ hổng kiến thức thực chất).
     * Nếu $N_{items} < 5$: Học sinh bỏ không làm bài tập LMS $\rightarrow \mathbf{LOW\_ENGAGEMENT}$.

### Bước 3: Tổng hợp Cấp Học sinh trên Danh sách Lớp (Roster Aggregation)
Khi hiển thị danh sách toàn lớp:
1. **Xác định Nguồn bằng chứng chung (`overall_evidence_source`):** Áp dụng **Majority Vote** (chọn nguồn chiếm đa số từ 32 bài học: `HYBRID`, `LMS`, hoặc `EXAM`).
2. **Xác định Trạng thái Đối soát chung (`overall_integ`):** Áp dụng **Quy tắc Đa số (Majority Rule)**:
   - Nếu $100\%$ bài học không có LMS ($N_{items} = 0$) $\rightarrow \mathbf{EXAM\_ONLY}$ (Chỉ từ bài thi).
   - Nếu số bài cảnh báo gian lận chiếm đa số ($N_{exceed} \ge N_{ok}$) $\rightarrow \mathbf{LMS\_EXCEEDS\_EXAM}$ (LMS vượt trội).
   - Nếu số bài lười làm chiếm đa số ($N_{low} \ge N_{ok}$) $\rightarrow \mathbf{LOW\_ENGAGEMENT}$ (Ít luyện tập LMS).
   - Ngược lại $\rightarrow \mathbf{OK}$ (Đồng thuận).
3. **Độ tin cậy tổng thể (`summary_conf_score`):** Trung bình cộng thực tế độ tin cậy của các bài học.

---

## 5. Hệ thống Trạng thái Đối soát (Integrity Status)

| Trạng thái | Mã hiển thị | Ý nghĩa sư phạm | Hành động khuyến nghị |
| :--- | :--- | :--- | :--- |
| 🟢 **Đồng thuận** | `OK` | Điểm bài tập online và điểm thi khớp nhau ($|\Delta| \le 30\%$). | Dữ liệu chuẩn xác, tập trung phụ đạo các bài học bị hổng. |
| 🔵 **LMS vượt trội** | `LMS_EXCEEDS_EXAM` | Bài tập online cao bất thường ($\ge 9.5$) nhưng điểm thi thấp ($< 4.5$). | Cảnh báo: Học sinh có thể tra đáp án hoặc nhờ người làm hộ. |
| 🟡 **Ít luyện tập LMS** | `LOW_ENGAGEMENT` | Học sinh bỏ bài tập ở đa số bài học ($N_{items} < 5$). | Nhắc nhở học sinh hoàn thành bài tập trực tuyến. |
| 🟣 **Chỉ từ Bài thi** | `EXAM_ONLY` | Học sinh hoàn toàn không tham gia làm bài LMS ($0\%$ nộp bài). | Kết quả tạm thời suy ra từ bài thi giấy, cần giao bài LMS. |
| ⚪ **Chỉ từ LMS** | `LMS_ONLY` | Môn học chưa có điểm thi chính thức, chỉ có bài tập LMS. | Đánh giá ban đầu dựa trên tiến độ tự học. |
| 🟠 **Cần kiểm chứng** | `FLAGGED` | Thời gian làm bài câu hỏi quá nhanh bất thường ($1 - 2$ giây/câu). | Giáo viên kiểm tra trực tiếp học sinh trên lớp. |

---

## 6. So sánh với các Module Phân tích khác

| Tiêu chí | Chẩn đoán Lỗ hổng Kiến thức | Pass/Fail Forecast | EWS Risk Pipeline |
| :--- | :--- | :--- | :--- |
| **Mục tiêu** | Chỉ ra chính xác học sinh hổng bài nào, chương nào trong SGK | Dự đoán điểm số và kết quả đỗ/trượt kỳ thi cuối kỳ | Dự báo nguy cơ học sinh rớt môn/bỏ học để can thiệp sớm |
| **Mức độ chi tiết** | Cấp độ **Từng bài học / Câu hỏi Bloom** | Cấp độ **Bài thi chuẩn bị diễn ra** | Cấp độ **Toàn môn học cả học kỳ** |
| **Mô hình xử lý** | Đối soát Đa nguồn + Cây tri thức + Bloom Weighting | Công thức thuần (Σ Ability × Weight × CDI) | Machine Learning CatBoost (22 Features DWH) |
| **Đối tượng dùng** | Giáo viên bộ môn & Học sinh | Giáo viên bộ môn | Ban Giám Hiệu & Trưởng khối |

---

## 7. Kết quả đạt được

| Hạng mục | Trạng thái | Chi tiết |
| :--- | :---: | :--- |
| Cây tri thức chuẩn SGK | Hoạt động | Phân cấp Chương → Bài học con, tự động cuộn điểm cha/con. |
| Đánh giá thang đo Bloom | Hoạt động | Tính toán độ bao phủ Bloom 1-6 và trọng số câu hỏi tư duy cao. |
| Đối soát Đa nguồn tự động | Hoạt động | Phát hiện bất thường giữa học online và thi thật, tự điều chỉnh trọng số. |
| Quy tắc Đa số (Majority Rule) | Hoạt động | Gộp trạng thái cấp học sinh chính xác, không bị lỗi đè nhãn cục bộ. |
| Giải trình minh bạch | Hoạt động | Tooltip và Drawer giải thích rõ số lượng câu hỏi và nguồn bằng chứng. |
| Tối ưu hiệu năng | Hoạt động | API nạp danh sách 40 học sinh kèm cây 35 bài chỉ mất < 200ms. |

---

## 8. Cách chạy thử & Kiểm thử

```bash
# 1. Tải danh sách chẩn đoán Roster của Lớp 6A1 môn Toán 6
curl -X GET "http://localhost:8000/api/v1/knowledge-gaps/classes/1/roster?subject_id=106&semester_index=1" \
  -H "Authorization: Bearer <token>"

# 2. Xem chi tiết chẩn đoán từng bài học của học sinh HS0001
curl -X GET "http://localhost:8000/api/v1/knowledge-gaps/student/HS0001?subject_id=106&semester_index=1" \
  -H "Authorization: Bearer <token>"

# 3. Kích hoạt tính toán lại toàn bộ năng lực từ LMS Item Responses
curl -X POST "http://localhost:8000/api/v1/knowledge-gaps/recalc-mastery?subject_id=106&semester_index=1" \
  -H "Authorization: Bearer <token>"

# 4. Chạy toàn bộ Unit Tests của module
pytest tests/test_knowledge_gap.py -v
```
