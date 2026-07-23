# Kiến Trúc Song Song 2 Bảng Fact Sổ Điểm Độc Lập (Dual-System Gradebook Fact Architecture)

## 1. Tổng Quan Kiến Trúc (Architectural Overview)

Trong Kho dữ liệu (Data Warehouse - DWH) của Vinschool, hai bảng **`s360.fact_gradebooks`** và **`s360.fact_gradebooks_moet`** được thiết kế theo mô hình **Song Song 2 Phân Hệ Độc Lập (Decoupled Dual-System Architecture)**:

* **Không có Khóa Ngoại (Foreign Key) trực tiếp** nối 2 bảng Fact với nhau.
* Cả 2 bảng đều là bảng Fact độc lập, chỉ gặp nhau ở tầng DWH khi dùng chung các **Dimensions dùng chung (Conformed Dimensions)** như `s360.dim_school_year`, `s360.dim_subject` và `student_code`.

---

## 2. So Sánh Chi Tiết 2 Phân Hệ Điểm

| Đặc Tính | `s360.fact_gradebooks` | `s360.fact_gradebooks_moet` |
|---|---|---|
| **Hệ Thống Nguồn (`source_system`)** | `'SCHOOL_ONLINE'` (Vinschool LMS & ERP) | `'MOET_APP'` (Phân hệ Sổ điểm Chuẩn Bộ) |
| **Mục Đích Nghiệp Vụ** | Đánh giá học tập nội bộ theo chương trình Vinschool (Cambridge, IB, Honor, STEM) | Xuất báo cáo pháp lý & In Học bạ Điện tử nộp cho Sở/Bộ GD&ĐT |
| **Thang Điểm Sử Dụng** | Đa dạng 6 thang điểm (Thang 10, 100, 4.0, 6.0, Điểm chữ A-F, Pass/Fail) | Bắt buộc Thang điểm 10.0 chuẩn Bộ GD&ĐT |
| **Độ Chi Tiết Bản Ghi (Granularity)** | Điểm tổng kết học phần Vinschool theo kỳ<br/>*(1 bản ghi / học sinh / môn / học kỳ)* | Điểm từng con thành phần chi tiết (Miệng, 15 phút, Giữa kỳ, Cuối kỳ)<br/>*(Nhiều bản ghi / học sinh / môn / học kỳ)* |
| **Khóa Ngoại Kỳ Thi / Đầu Điểm** | `so_exam_id` ➡️ `s360.dim_exam`<br/>*(Kỳ thi nội bộ do Vinschool tổ chức)* | `gradebook_type_item_id` ➡️ `s360.dim_exam_moet`<br/>*(Cột vị trí trên trang Sổ điểm điện tử của Bộ)* |

---

## 3. Lý Do Thiết Kế Tách Bảng Độc Lập

1. **Tách biệt Trách nhiệm Hệ thống (Separation of Concerns)**:
   - Đảm bảo khi quy định của Bộ GD&ĐT thay đổi (ví dụ Thông tư mới), phân hệ `MOET_APP` và bảng `fact_gradebooks_moet` có thể nâng cấp độc lập mà không làm ảnh hưởng đến thuật toán tính GPA và xếp loại học bạ nội bộ của Vinschool trên `fact_gradebooks`.
2. **Khác biệt về Mức độ Chi tiết (Granularity Differences)**:
   - `fact_gradebooks` quản lý mức Tổng kết (Summary layer).
   - `fact_gradebooks_moet` quản lý mức Chi tiết thành phần (Detailed line-item layer).
3. **Phục vụ Đa dạng Loại Báo Cáo**:
   - Khi Ban Giám Hiệu xem báo cáo chất lượng học tập nội bộ Vinschool ➡️ Truy vấn `fact_gradebooks`.
   - Khi Phòng Học vụ xuất Sổ điểm nộp cho Sở GD&ĐT ➡️ Truy vấn `fact_gradebooks_moet`.

---

## 4. Hướng Dẫn Truy Vấn Cho AI Text-to-SQL Agent

* **Khi câu hỏi liên quan đến Điểm Vinschool / Điểm Thang 100 / Điểm GPA 4.0 / Thang IB 6**:
  - Query vào bảng **`s360.fact_gradebooks`**.
* **Khi câu hỏi liên quan đến Điểm Chuẩn Bộ / Điểm Miệng / Điểm 15 Phút / Điểm Sổ Điện Tử MOET**:
  - Query vào bảng **`s360.fact_gradebooks_moet`** kết hợp với **`s360.dim_exam_moet`**.
