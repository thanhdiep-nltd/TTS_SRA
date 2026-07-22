# Quy Tắc Thiết Kế Sổ Điểm Chuẩn Bộ (MOET Gradebook Design Rules)

## 1. Nguyên Lý Thiết Kế Master Data (Standardized Presets + Custom Extension)

Bảng **`s360.dim_exam_moet`** và **`s360.fact_gradebooks_moet`** được thiết kế theo mô hình kết hợp giữa **Mã Code Chuẩn Hóa Cố Định** và **Tên Hiển Thị Tùy Chỉnh Linh Hoạt**:

### A. Cột Mã Code Cố Định (`gradebook_type_items_code`)
* **Bản chất**: Do Dev/Phần mềm định nghĩa sẵn danh sách các Preset Master Codes.
* **Tác dụng**: Giúp Backend, thuật toán tính $ĐTB$ tự động và AI Text-to-SQL Agent luôn truy vấn chuẩn xác 100% không bị ảnh hưởng khi người dùng gõ từ ngữ tùy ý.
* **Danh sách Mã chuẩn (Master Codes)**:
  - `MOET_ORAL`: Kiểm tra miệng (Đánh giá thường xuyên, Hệ số 1.0).
  - `MOET_QUIZ_15M`: Kiểm tra 15 phút (Đánh giá thường xuyên, Hệ số 1.0).
  - `MOET_MIDTERM`: Kiểm tra Giữa kỳ (Đánh giá định kỳ, Hệ số 2.0).
  - `MOET_FINAL`: Kiểm tra Cuối kỳ (Đánh giá định kỳ, Hệ số 3.0).

### B. Cột Tên Hiển Thị Tùy Chỉnh (`gradebook_type_items_fullname`)
* **Bản chất**: Cho phép Nhà trường / Giáo viên tự do nhập tên hiển thị (Custom Text) trên giao diện Web Admin / LMS.
* **Tác dụng**: Hiển thị linh hoạt và thân thiện theo từng môn học hoặc chủ đề bài học trên App Phụ huynh & Học sinh.
* **Ví dụ**:
  - Mã `MOET_ORAL` -> Tên hiển thị: *"Kiểm tra đọc phát âm Tiếng Anh"*
  - Mã `MOET_MIDTERM` -> Tên hiển thị: *"Bài thi Giữa kỳ 1 hệ Cambridge"*

---

## 2. Phân Nhóm Loại Đầu Điểm (`gradebook_types_code`) theo Thông tư Bộ GD&ĐT

Theo **Thông tư 22/2021/TT-BGDĐT**, các đầu điểm được gom vào 2 nhóm chính:

| `gradebook_types_code` | `gradebook_types_fullname` | `gradebook_type_items_code` | `gradebook_type_items_fullname` | Hệ số (`coefficient`) |
|---|---|---|---|:---:|
| `DG_TX` | Đánh giá thường xuyên | `MOET_ORAL` | Kiểm tra miệng | 1.0 |
| `DG_TX` | Đánh giá thường xuyên | `MOET_QUIZ_15M` | Kiểm tra 15 phút | 1.0 |
| `DG_DK` | Đánh giá định kỳ | `MOET_MIDTERM` | Kiểm tra Giữa kỳ | 2.0 |
| `DG_DK` | Đánh giá định kỳ | `MOET_FINAL` | Kiểm tra Cuối kỳ | 3.0 |

---

## 3. Hướng Dẫn Truy Vấn Cho Text-to-SQL Agent

* **Khi chạy báo cáo tự động / Tính điểm**: Truy vấn chính xác theo cột mã cố định `gradebook_type_items_code = 'MOET_ORAL'`.
* **Khi xử lý câu hỏi ngôn ngữ tự nhiên**: Truy vấn hỗ trợ cả mã code lẫn tên hiển thị `(gradebook_type_items_code = 'MOET_ORAL' OR gradebook_type_items_fullname ILIKE '%Kiểm tra miệng%')`.
