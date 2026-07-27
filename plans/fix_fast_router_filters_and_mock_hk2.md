# Fix: FastTemplateDecision Drop Filters + Mock Data Only HK1

## Root Causes (Confirmed)

1. **Backend — FastTemplateDecision thiếu filters**: `FastTemplateDecision` tại [`src/agents/data_service_agent/node.py:37`](../src/agents/data_service_agent/node.py:37) chỉ có 2 fields (`selected_tool`, `extracted_param`), không có `semester`/`subject`. Khi LLM router gọi `get_student_grades(student_id="HS1250705281")`, tool SELECT ALL grades vì thiếu `WHERE semester_index=2 AND subject ILIKE '%Toán%'`.

2. **Data — Mock chỉ có HK1**: [`data_mock/generate_full_system_mock.py`](../data_mock/generate_full_system_mock.py) ghi cứng `semester_index=1` ở 5 câu INSERT (lines 478, 485, 512, 521). Không có bản ghi nào `semester_index=2` trong `s360.fact_gradebooks`.

---

## Fix 1: FastTemplateDecision — Bổ sung `semester` & `subject` fields

### File: [`src/agents/data_service_agent/node.py`](../src/agents/data_service_agent/node.py)

#### 1a. Mở rộng `FastTemplateDecision` (line 37-49)

```python
class FastTemplateDecision(BaseModel):
    selected_tool: str = Field(
        description=(
            "Chọn 'get_student_grades' (nếu tra cứu điểm cá nhân 1 học sinh), "
            "'get_class_grades' (nếu tra cứu danh sách bảng điểm/sổ điểm thi của 1 lớp chủ nhiệm cụ thể), "
            "'get_student_info' (nếu tra cứu hồ sơ/thông tin 1 học sinh), "
            "hoặc 'NONE' (nếu là bài toán sĩ số/đếm học sinh, so sánh giữa các lớp/năm, thống kê rủi ro, hoặc truy vấn phức tạp cần viết SQL)."
        )
    )
    extracted_param: str | None = Field(
        default=None,
        description="Mã/họ tên học sinh hoặc mã lớp bóc tách được (ví dụ: '7A1', '10A1', 'HS25071001', 'Bùi Thành Hải')."
    )
    semester: int | None = Field(
        default=None,
        description="Học kỳ (1 hoặc 2). Chỉ điền nếu câu hỏi đề cập rõ học kỳ. Ví dụ: 'học kỳ 1', 'HK1' -> semester=1."
    )
    subject: str | None = Field(
        default=None,
        description="Tên môn học cụ thể. Chỉ điền nếu câu hỏi đề cập rõ môn học. Ví dụ: 'Toán học', 'Âm nhạc', 'Mỹ thuật'."
    )
```

#### 1b. Cập nhật System Prompt cho Fast Router (line 76-84)

Thêm hướng dẫn trích xuất `semester` và `subject`:
```python
SystemMessage(content=(
    "Bạn là Fast Router Tầng 1. Nhiệm vụ của bạn là chọn đúng công cụ Fast Template Tầng 1 hoặc chọn 'NONE'.\n"
    "QUY TẮC BẮT BUỘC:\n"
    "- Nếu câu hỏi tra cứu điểm/hồ sơ cá nhân 1 học sinh -> chọn 'get_student_grades' hoặc 'get_student_info'.\n"
    "- Nếu câu hỏi tra cứu danh sách sổ điểm thi của 1 lớp -> chọn 'get_class_grades'.\n"
    "- CHÚ Ý CỰC KỲ QUAN TRỌNG: Nếu câu hỏi về SĨ SỐ HỌC SINH (ví dụ: 'Lớp 7A1 có bao nhiêu học sinh?'), "
    "SO SÁNH NĂM HỌC/LỚP HỌC, THỐNG KÊ RỦI RO -> BẮT BUỘC CHỌN 'NONE'.\n"
    "- Nếu câu hỏi đề cập rõ HỌC KỲ (ví dụ: 'học kỳ 1', 'học kỳ 2', 'HK1', 'HK2') -> điền vào field 'semester'.\n"
    "- Nếu câu hỏi đề cập rõ MÔN HỌC (ví dụ: 'Toán', 'Ngữ văn', 'Âm nhạc') -> điền vào field 'subject'."
))
```

#### 1c. Cập nhật JSON fallback parser (line 100-106)

```python
data = json.loads(j_match.group(0))
decision = FastTemplateDecision(
    selected_tool=data.get("selected_tool", "NONE"),
    extracted_param=data.get("extracted_param"),
    semester=data.get("semester"),
    subject=data.get("subject"),
)
```

#### 1d. Cập nhật logic gọi tool — truyền filters (lines 111-119)

```python
if decision.selected_tool == "get_class_grades" and decision.extracted_param:
    kwargs = {"class_name": decision.extracted_param.strip()}
    if decision.semester:
        kwargs["semester"] = decision.semester
    if decision.subject:
        kwargs["subject"] = decision.subject
    logger.info(f"[data_service_agent] Tầng 1: Chạy get_class_grades cho lớp {decision.extracted_param} "
                f"semester={decision.semester} subject={decision.subject}")
    template_result = get_class_grades.invoke(kwargs)
elif decision.selected_tool == "get_student_grades" and decision.extracted_param:
    kwargs = {"student_id": decision.extracted_param.strip()}
    if decision.semester:
        kwargs["semester"] = decision.semester
    if decision.subject:
        kwargs["subject"] = decision.subject
    logger.info(f"[data_service_agent] Tầng 1: Chạy get_student_grades cho HS {decision.extracted_param} "
                f"semester={decision.semester} subject={decision.subject}")
    template_result = get_student_grades.invoke(kwargs)
```

---

## Fix 2: Seed HK2 Data vào Mock Database

### File: [`data_mock/generate_full_system_mock.py`](../data_mock/generate_full_system_mock.py)

#### 2a. Tìm vòng lặp ghi `fact_gradebooks` (khoảng line 472-529)

Hiện tại code ghi `semester_index=1` cho mỗi học sinh. Cần **nhân đôi** khối INSERT này với `semester_index=2` và **điều chỉnh điểm số HK2** (cùng cấu trúc, cùng score nhưng sàn: HK2 score = HK1 score + noise [-1.0, +1.0], clamped [0, 10]).

**Logic cụ thể:**

Sau khi ghi xong HK1 (lines 472-529), thêm một khối tương tự cho HK2:

```python
# ── HK2: Seed Fact Gradebooks (SCORED Subjects) ──
for sub_id, score_val in student_scored_subjects:
    # HK2 score: biến động nhẹ so với HK1
    hk2_score = max(0.0, min(10.0, score_val + random.uniform(-1.0, 1.0)))
    pf_status = 'DAT' if hk2_score >= 5.0 else 'CHUA_DAT'
    session.execute(text("""
        INSERT INTO s360.fact_gradebooks
        (id, so_school_id, school_year_id, semester_index, student_code, homeroom_class_id, subject_id, so_exam_id, final_grade, pass_fail_status)
        VALUES (:id, :sid, :syid, 2, :scode, :cid, :subid, 2, :score, CAST(:pf AS public.pass_fail_enum))
        ON CONFLICT (id) DO NOTHING;
    """), {"id": gradebook_id, "sid": sid, "syid": syid, "scode": scode, "cid": cid, "subid": sub_id, "score": round(hk2_score, 1), "pf": pf_status})

    # fact_gradebooks_moet
    session.execute(text("""
        INSERT INTO s360.fact_gradebooks_moet
        (id, so_school_id, school_year_id, semester_index, grade_id, homeroom_class_id, student_code, subject_id, gradebook_type_item_id, final_grade)
        VALUES (:id, :sid, :syid, 2, :gid, :cid, :scode, :subid, 2, :score)
        ON CONFLICT (id) DO NOTHING;
    """), {"id": gradebook_id, "sid": sid, "syid": syid, "gid": gid, "cid": cid, "scode": scode, "subid": sub_id, "score": round(hk2_score, 1)})

    gradebook_id += 1

# ── HK2: Seed Fact Gradebooks (REMARK Subjects) ──
for sub_id in student_remark_subjects:
    pf_status = 'DAT' if (eff > -1.0 or prof != "Academic_At_Risk") else 'CHUA_DAT'
    session.execute(text("""
        INSERT INTO s360.fact_gradebooks
        (id, so_school_id, school_year_id, semester_index, student_code, homeroom_class_id, subject_id, so_exam_id, final_grade, pass_fail_status)
        VALUES (:id, :sid, :syid, 2, :scode, :cid, :subid, 2, NULL, CAST(:pf AS public.pass_fail_enum))
        ON CONFLICT (id) DO NOTHING;
    """), {"id": gradebook_id, "sid": sid, "syid": syid, "scode": scode, "cid": cid, "subid": sub_id, "pf": pf_status})

    # fact_so_evaluate_process_subjects
    cmt_text = remark_comments[sub_id][0] if pf_status == 'DAT' else remark_comments[sub_id][1]
    session.execute(text("""
        INSERT INTO s360.fact_so_evaluate_process_subjects
        (id, evaluate_progress_id, subject_id, student_code, school_year_id, semester_index, final_grade_level, student_level, comment, teacher_fullname)
        VALUES (:id, :eid, :subid, :scode, :syid, 2, :fgl, :slevel, :comment, :tname)
        ON CONFLICT (id) DO NOTHING;
    """), {
        "id": gradebook_id, "eid": gradebook_id, "subid": sub_id, "scode": scode, "syid": syid,
        "fgl": pf_status, "slevel": "ĐẠT" if pf_status == 'DAT' else "CHƯA ĐẠT",
        "comment": cmt_text, "tname": "Giáo viên Bộ Môn"
    })

    gradebook_id += 1
```

**Lưu ý**: 
- `so_exam_id` cho HK2 dùng `id=2` (phân biệt với HK1 `id=1`)
- `gradebook_type_item_id` cho HK2 dùng `id=2`
- Cần đảm bảo `dim_exam` và `dim_exam_moet` đã có bản ghi HK2 (kiểm tra lines 186-198)
- `gradebook_id` tiếp tục increment (không reset)

#### 2b. Kiểm tra `dim_exam` và `dim_exam_moet` seeding

Đọc lines 186-198 để xác nhận exam HK2 đã được seed. Nếu chưa, cần thêm:
```python
# Thêm exam cho HK2
session.execute(text("""
    INSERT INTO s360.dim_exam (id, school_year_id, subject_id, grade_id, exam_code, exam_name, coefficient, moet_semester_index)
    VALUES (2, :syid, :subid, :gid, 'GK2', 'Kiểm tra Giữa Học kỳ 2', 1, 2)
    ON CONFLICT (id) DO NOTHING;
"""), {"syid": syid, "subid": sub_id, "gid": gid})
```

---

## Implementation Checklist

| # | Action | File | Priority |
|---|--------|------|----------|
| 1 | Add `semester: int \| None` field to `FastTemplateDecision` | `src/agents/data_service_agent/node.py` | P0 |
| 2 | Add `subject: str \| None` field to `FastTemplateDecision` | `src/agents/data_service_agent/node.py` | P0 |
| 3 | Update System prompt — hướng dẫn LLM extract semester/subject | `src/agents/data_service_agent/node.py` | P0 |
| 4 | Update JSON fallback parser — đọc semester/subject từ JSON | `src/agents/data_service_agent/node.py` | P0 |
| 5 | Update tool invocation logic — truyền kwargs với filters | `src/agents/data_service_agent/node.py` | P0 |
| 6 | Seed HK2 scored grades (fact_gradebooks + fact_gradebooks_moet) | `data_mock/generate_full_system_mock.py` | P0 |
| 7 | Seed HK2 remark grades (fact_gradebooks + fact_so_evaluate_process_subjects) | `data_mock/generate_full_system_mock.py` | P0 |
| 8 | Verify HK2 exam entries in dim_exam / dim_exam_moet | `data_mock/generate_full_system_mock.py` | P0 |
| 9 | Re-run eval test suite: `python eval/eval_text_to_sql/run_eval_suite.py --mode=tier1` | CLI | P1 |
| 10 | Manual test: flow "còn học kỳ 2 thì sao?" trả về đúng Toán HK2 | Manual | P1 |
