# Schema Review: score_focused_schema.sql → Hỗ trợ Plan 1 EWS

> **Mục đích:** Review [`score_focused_schema.sql`](docs_vsf/schemas/merged/score_focused_schema.sql) để xác định cần thêm/bớt table/column gì so với [`School Online Schema.csv`](docs_vsf/schemas/new/School Online Schema.csv) nhằm hỗ trợ đầy đủ Plan 1 EWS.

---

## I. Kết luận QUAN TRỌNG

**Schema hiện tại (`score_focused_schema.sql`) ĐÃ ĐỦ để thực hiện Giai đoạn 1 của Plan 1.**

Không cần:
- ❌ Thêm bảng `fact_weekly_subject_scores`
- ❌ Thêm cột `week_number` vào bất kỳ bảng nào
- ❌ ALTER TABLE để thêm column
- ❌ Thêm bảng mới từ School Online CSV

Lý do: Mỗi bảng fact đều có cột thời gian (`created_at`, `_date`, `comment_date`, `absent_date`, `date_assigned`, ...) và `dim_school_year` có `start_date`/`end_date` → có thể tính `week_number` động trong SQL bằng `EXTRACT(WEEK FROM date)` hoặc `(date - school_year_start_date) / 7`.

---

## II. Ánh xạ Plan 1 formulas → Schema hiện tại

### Công thức 1: Grade Slope `REGR_SLOPE(score, week_number)`

**Nguồn dữ liệu đề xuất:** `fact_so_assignment_grade` + `dim_so_assignment.date_assigned`

```sql
SELECT 
    fag.student_code,
    REGR_SLOPE(fag.final_grade, EXTRACT(WEEK FROM dsa.date_assigned)) AS grade_slope,
    REGR_INTERCEPT(fag.final_grade, EXTRACT(WEEK FROM dsa.date_assigned)) AS grade_intercept
FROM s360.fact_so_assignment_grade fag
JOIN s360.dim_so_assignment dsa ON fag.assignment_id = dsa.assignment_id
GROUP BY fag.student_code;
```

| Bảng trong schema | Vai trò |
|-------------------|---------|
| `fact_so_assignment_grade` | Điểm bài tập LMS — có `created_at`, `final_grade` |
| `dim_so_assignment` | Thông tin bài tập — có `date_assigned`, `due_date` |
| `dim_school_year` | `start_date` — dùng để tính week offset nếu cần |

### Công thức 2: WAR — Weighted Absenteeism Rate

```sql
SELECT 
    fda.student_code,
    (SUM(fda.absent_no_permission * 1.0 + fda.absent_with_permission * 0.2)
     + COALESCE(late.tardy_count, 0) * 0.1) 
    / NULLIF(SUM(fda.total_periods), 0) * 100 AS war
FROM s360.fact_so_daily_attendance fda
LEFT JOIN (
    SELECT student_code, COUNT(*) AS tardy_count
    FROM s360.fact_so_homeroom_class_late_attendances
    WHERE is_late = 1
    GROUP BY student_code
) late ON fda.student_code = late.student_code
GROUP BY fda.student_code, late.tardy_count;
```

| Bảng trong schema | Vai trò |
|-------------------|---------|
| `fact_so_daily_attendance` | `absent_no_permission`, `absent_with_permission`, `total_periods`, `_date`, `week_start` |
| `fact_so_homeroom_class_late_attendances` | `is_late`, `attendance_date`, `time_late` |
| `fact_absent_logs` | `reason_category`, `absent_date`, `is_full_day` (optional detail) |

### Công thức 3: Behavior Demerits

```sql
SELECT 
    student_code,
    SUM(CASE WHEN behavior_point < 0 THEN 1 ELSE 0 END) AS behavior_demerits
FROM s360.fact_behavior_logs
WHERE comment_date >= :start_date
GROUP BY student_code;
```

| Bảng trong schema | Vai trò |
|-------------------|---------|
| `fact_behavior_logs` | `behavior_point`, `comment_date`, `behavior_code` |

---

## III. So sánh schema tổng quan

| Tiêu chí | score_focused_schema.sql | School Online Schema.csv | Cần cho Plan 1? |
|----------|--------------------------|--------------------------|-----------------|
| Tables | 34 (10 public + 24 s360) | 35 (3 staging + 31 s360 + 1 t360) | ✅ Đủ |
| Time-series scores | `fact_so_assignment_grade` + `dim_so_assignment.date_assigned` | Giống | ✅ Đủ |
| Attendance tracking | `fact_so_daily_attendance`, `fact_absent_logs`, `fact_so_homeroom_class_late_attendances` | Giống + thêm `fact_so_absent_extract_late` | ✅ Đủ |
| Behavior tracking | `fact_behavior_logs` (22 columns) | Giống | ✅ Đủ |
| Grade scales | `dim_grade_scale_detail` (8 rows seed) | ❌ Không có | ✅ Có lợi thế |
| Metadata index | `metadata_index` (vector embedding) | ❌ Không có | ✅ Có lợi thế |
| Ngoại khóa | ❌ Không có | `dim_extracurricular_activity` + 2 fact | ❌ Không cần |
| Evaluate progress criterion | ❌ Không có | `fact_so_evaluate_process_subject_criterion` | ⚠️ Có thể hữu ích cho GĐ2 |

---

## IV. Vấn đề thực sự: Mock data chưa đủ

**Schema ổn, nhưng `generate_full_system_mock.py` chưa seed đủ dữ liệu để chạy các công thức Plan 1.**

### Những gì cần sửa trong mock data:

| Bảng | Hiện trạng | Cần sửa |
|------|------------|---------|
| `fact_so_assignment_grade` | Chỉ 4 assignments/môn, thiếu time distribution | Tăng lên 8-12 assignments/môn, trải đều theo tuần |
| `fact_so_daily_attendance` | **CHƯA ĐƯỢC SEED** | Seed 365 ngày × student với pattern theo persona |
| `fact_so_homeroom_class_attendances` | Chưa seed | Seed điểm danh đầu giờ hàng ngày |
| `fact_so_homeroom_class_late_attendances` | Chưa seed | Seed đi muộn với `is_late` và `attendance_date` |
| `fact_behavior_logs` | Chỉ 5-10 records/học sinh nguy cơ, không temporal | Tăng temporal distribution, behavior_point thay đổi theo thời gian |
| `fact_absent_logs` | Chỉ 2-4 records/học sinh nguy cơ | Tăng số lượng với `absent_date` trải đều |
| `fact_gradebooks` | Seed đủ HK1+HK2 | Giữ nguyên, đã ổn |

---

## V. Kết luận

1. **✅ Không cần thay đổi schema** — `score_focused_schema.sql` đã đủ cho Plan 1 Giai đoạn 1
2. **✅ Công thức Grade Slope** dùng `fact_so_assignment_grade` + `dim_so_assignment.date_assigned`
3. **✅ WAR** dùng `fact_so_daily_attendance` + `fact_so_homeroom_class_late_attendances`
4. **✅ Behavior Demerits** dùng `fact_behavior_logs`
5. **🔧 Chỉ cần sửa `generate_full_system_mock.py`** để seed đủ dữ liệu time-series

→ Chuyển trọng tâm sang fix mock data generator, bỏ qua schema changes.
