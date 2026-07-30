# Phân tích: Cột đánh dấu điểm chính trong Gradebook

## Nguồn dữ liệu
- File 1: `docs_vsf/schemas/merged/score_focused_schema.sql`
- File 2: `docs/School Online Schema.csv`

## Kết luận

**Không có cột `is_main_score`, `is_primary_score`, `cột_chinh` hay tương tự** trong cả 2 file. Việc xác định "điểm chính" trong Gradebook được thực hiện gián tiếp qua các cột sau:

---

### 1. Ánh xạ Assignment LMS → Gradebook MOET
| Cột | File | Vai trò |
|-----|------|---------|
| `dim_so_assignment.gradebook_type_item_id` | CSV dòng 227 | Nếu ≠ NULL, bài tập LMS được map vào 1 đầu điểm cụ thể trong gradebook |
| `dim_so_assignment.report_type_item_id` | CSV dòng 229 | Tương tự, map vào report type |

### 2. Phân cấp đầu điểm MOET (dim_exam_moet)
| Cột | File | Vai trò |
|-----|------|---------|
| `is_category` | CSV dòng 103 | =1: danh mục nhóm (cha), =0: đầu điểm nhập liệu thực tế |
| `parent_id` | SQL dòng 446 | Liên kết cha-con trong cây phân cấp đầu điểm |
| `coefficient` | SQL dòng 447 | Hệ số (cuối kỳ=3, giữa kỳ=2, thường xuyên=1) — càng cao càng quan trọng |
| `is_allow_input` | CSV dòng 100 | Cho phép nhập điểm trực tiếp vào đầu điểm này không |
| `is_allow_mapping` | CSV dòng 101 | Cho phép map assignment vào đầu điểm này không |
| `index_order` | CSV dòng 99 | Thứ tự hiển thị trong gradebook |

### 3. Exam (kỳ thi định kỳ)
| Cột | File | Vai trò |
|-----|------|---------|
| `dim_exam.is_display_grade_book` | CSV dòng 80 | =1: kỳ thi hiển thị trong gradebook |
| `dim_exam.coefficient` | CSV dòng 75 | Hệ số của kỳ thi |
| `dim_exam.is_periodic_exam` | CSV dòng 78 | =1: là kỳ thi định kỳ (quan trọng) |
| `dim_exam.is_moet` | CSV dòng 72 | =1: theo chuẩn Bộ GD |

### 4. Gradebook Fact
| Cột | File | Vai trò |
|-----|------|---------|
| `fact_gradebooks.is_input_grade` | CSV dòng 422 | Đánh dấu điểm được nhập trực tiếp |
| `fact_gradebooks.is_move_in_grade` | CSV dòng 418 | Điểm được sao chép từ kỳ khác vào |
| `fact_gradebooks.is_semester_locked` | CSV dòng 419 | =1: học kỳ đã khóa (điểm chính thức) |
| `fact_gradebooks_moet.is_input_grade` | CSV dòng 451 | Tương tự cho gradebook MOET |

---

## Cơ chế xác định "điểm chính" (không có cột đánh dấu trực tiếp)

```
dim_so_assignment
  └── gradebook_type_item_id ───────────────┐
                                            ▼
                                    dim_exam_moet
                                      ├── is_category = 0  (đầu điểm thật)
                                      ├── coefficient = 3  (cuối kỳ, quan trọng nhất)
                                      └── is_allow_input = 1
                                            │
                                            ▼
                                    fact_gradebooks_moet
                                      └── final_grade (điểm số thực tế)
```

Một đầu điểm được coi là "chính" trong Gradebook khi:
1. `dim_exam_moet.is_category = 0` (đầu điểm thực tế, không phải nhóm)
2. `dim_exam_moet.coefficient` càng cao càng quan trọng (cuối kỳ = 3)
3. `dim_exam_moet.is_allow_input = 1` (cho phép nhập điểm)
4. Có dữ liệu trong `fact_gradebooks_moet.final_grade`
