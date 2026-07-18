# TEVI — Tam giác hóa độ khó đề thi: Tóm tắt triển khai (Phase 0 + Phase 1)

> Tóm tắt cho teammate. Thiết kế đầy đủ (công thức, ngưỡng, ví dụ số) xem [exam_triangulation_design.md](exam_triangulation_design.md).

## Bài toán

Hệ thống đo độ khó đề thi hiện tại (`mv_exam_difficulty.facility_index`) được **suy ra từ chính điểm số** → không tách được "đề khó" khỏi "học sinh yếu", không tự kiểm chứng được điểm có phản ánh đúng thực lực hay không.

**Giải pháp**: thêm một nguồn độ khó **độc lập với điểm số** — CDI (Content Difficulty Index), tính từ nội dung đề (`curriculum_units` + thang Bloom trong `exam_competencies`, nhập tay ở Phase 1). Đối chiếu CDI với EDI (độ khó thực nghiệm, suy ra từ điểm) để phát hiện **phân kỳ** (divergence) — tín hiệu cho BGH rà soát lạm phát điểm / nghi lộ đề / lỗ hổng dạy-học.

## Mô hình toán (rút gọn)

- **EDI** (thực nghiệm) = `1 - facility_index` (từ `mv_exam_difficulty`)
- **CDI** (nội dung) = `exam_papers.content_difficulty` (nhập tay hoặc tính từ Bloom weight)
- **DDI** (khai báo) = quy đổi từ `exam_papers.difficulty` (EASY=0.25 / MEDIUM=0.5 / HARD=0.75)
- **Divergence** `D = EDI - CDI`
- **Cờ phân loại**:
  | Điều kiện | Flag | Ý nghĩa |
  |---|---|---|
  | `cdi IS NULL` | `NO_CONTENT` | Chưa phân tích nội dung đề |
  | `n < 30` | `LOW_SAMPLE` | Mẫu điểm quá nhỏ, không đủ tin cậy |
  | `D ≤ -0.25` | `INFLATION_OR_LEAK` | Điểm cao bất thường so với độ khó nội dung → nghi lạm phát điểm/lộ đề |
  | `D ≥ 0.25` | `LEARNING_GAP` | Điểm thấp bất thường so với độ khó nội dung → nghi lỗ hổng dạy-học |
  | còn lại | `VALID` | Điểm khớp với độ khó nội dung |
- **Thực lực neo-nội-dung**: `ability = clamp(0..10, raw_average + k·(CDI - 0.5))`, `k = 3.0` — xếp hạng lớp theo thực lực độc lập với điểm trung bình cohort.

## Thay đổi DB (migration `b2f1d9a37e44`)

- `alembic/versions/b2f1d9a37e44_exam_validity_triangulation.py`
- `exam_papers` thêm 3 cột: `content_difficulty NUMERIC(4,3)`, `content_analyzed_at TIMESTAMPTZ`, `content_source file_type_enum` (đều nullable, `NULL` = chưa phân tích nội dung).
- View mới `v_exam_validity`: JOIN `mv_exam_difficulty` + `exam_column_mappings` + `exam_papers`, tính sẵn `edi/cdi/ddi/divergence/flag` + `school_id` (để service lọc theo trường không cần JOIN thêm).
- Đã chạy `alembic upgrade head` trên Neon — **không cần làm lại**, chỉ cần `git pull` rồi `alembic upgrade head` ở môi trường khác nếu DB đó chưa có.
- `src/models/tables.py` → `ExamPaper` đã có 3 field mới tương ứng.

## File mới

| File | Vai trò |
|---|---|
| `src/schemas/exam_validity.py` | DTO: `ExamValidityRead`, `SchoolValidityOverview`, `ContentAdjustedRankRow` |
| `src/services/exam_validity.py` | Logic nghiệp vụ: đọc `v_exam_validity` qua `text()`, tính `confidence`, sắp xếp theo độ nghiêm trọng, tính ability neo-nội-dung |
| `src/api/v1/exam_validity.py` | 3 endpoint REST (xem bảng dưới) |
| `tests/test_exam_validity_service.py` | 7 test offline cho công thức/ngưỡng (khớp ví dụ §13 design doc) |

## API mới (`/api/v1/analytics/...`)

| Endpoint | Quyền | Mô tả |
|---|---|---|
| `GET /analytics/exam-validity?subject_id&semester_id&score_category&grade_id` | ADMIN, PRINCIPAL, SUBJECT_HEAD | Bảng tam giác hóa EDI/CDI/DDI theo môn/kỳ/khối |
| `GET /analytics/exam-validity/overview?semester_id` | ADMIN, PRINCIPAL | Tổng hợp toàn trường: đếm cờ + danh sách đề đáng rà soát nhất |
| `GET /analytics/content-adjusted-ranking?grade_id&semester_id&subject_id&score_category` | ADMIN, PRINCIPAL | Xếp hạng lớp theo thực lực neo-nội-dung |

Đã đăng ký router trong `src/api/v1/__init__.py` (cạnh `analytics.router`).

## Agent (chatbot) mới

- Tool `get_exam_validity_report(subject, grade_level, year, semester)` trong `src/agents/stat_agent/tools.py` — resolve môn/khối/học kỳ theo tên rồi trả JSON cờ GK+CK.
- Đăng ký vào `tools = [...]` trong `src/agents/stat_agent/node.py`.
- `STAT_AGENT_PROMPT` cập nhật thêm mục năng lực #4 (tam giác hóa độ khó) để Supervisor biết khi nào route sang `stat_agent`.
- **Không cần** sửa `RouterDecision`/`graph.py` — không có sub-agent mới, chỉ thêm năng lực cho `stat_agent` cũ.

## Dữ liệu demo (`scripts/seed_exam_validity_demo.py`)

Script mới, idempotent (bỏ qua nếu mapping đã tồn tại), tạo 2 case dựa trên **điểm thật đã có sẵn** trong `mv_exam_difficulty` (không cần seed điểm giả):

| Case | Môn/Khối/Kỳ | n | mean | EDI | CDI (Bloom mix) | Divergence | Flag thực tế |
|---|---|---|---|---|---|---|---|
| LEARNING_GAP | GD kinh tế & pháp luật, Khối 10, HK1 2025-2026, CK | 37 | 3.98 | 0.602 | 0.317 (40%B1+30%B2+30%B3) | +0.285 | `LEARNING_GAP` ✅ |
| INFLATION_OR_LEAK | Sinh học, Khối 11, HK1 2023-2024, CK | 33 | 8.73 | 0.127 | 0.650 (40%B3+30%B4+30%B5) | -0.523 | `INFLATION_OR_LEAK` ✅ |

Script tự tạo `exam_papers` (gắn `content_difficulty` = `CDI_bloom` tính theo công thức §2.2 design doc) + `exam_column_mappings` (map vào cột CK của khối) + `curriculum_units`/`exam_competencies` demo (`code` bắt đầu `DEMO-B`). Chạy: `PYTHONPATH=. python scripts/seed_exam_validity_demo.py` (cần `PYTHONPATH=.` nếu chạy ngoài root). Đã verify trực tiếp `SELECT * FROM v_exam_validity` trên Neon → đúng 2 cờ kỳ vọng.

## Trạng thái

- ✅ Migration đã chạy trên Neon, view verify đúng cấu trúc.
- ✅ `pytest tests/ -v` → **61/61 pass** (bao gồm 7 test mới, không vỡ `test_graph.py`).
- ✅ `ruff check` sạch trên toàn bộ file mới/sửa (bao gồm script seed).
- ✅ Đã có **2 dòng dữ liệu demo thật** trong `v_exam_validity` (1 `LEARNING_GAP`, 1 `INFLATION_OR_LEAK`) — gọi `GET /analytics/exam-validity` hoặc hỏi `stat_agent` qua `/chat` sẽ thấy kết quả thật, không còn toàn `NO_CONTENT`.
- ⏳ **Chưa commit/push** — chờ xác nhận trước khi tạo commit.

## Việc cần làm tiếp (ngoài phạm vi Phase 0+1)

- Phase 2 (chưa làm): pipeline tự tính `content_difficulty` từ `exam_competencies`/Bloom weight (OCR/LLM phân tích đề), thay vì nhập tay/script demo.
- Dữ liệu demo hiện chỉ 2 case, thuộc 2 trường khác nhau (`4bf3b51b...`) — muốn demo nhiều hơn thì mở rộng `CASES` trong script.
- Frontend: chưa có UI cho 3 endpoint mới (nằm trong nhóm Dashboard/Quản lý điểm theo `CLAUDE.md` §6, chưa được lên kế hoạch cụ thể).
