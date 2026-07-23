# Ghi Chú Cấu Trúc Bảng DWH & Định Hướng Sử Dụng `score_focused_schema.sql`

## 1. Danh Sách 25 Bảng Cốt Lõi (App Core + DWH Score)

### Schema `public` (App Core & Auth - 10 Bảng)
1. `public.users`: Quản lý tài khoản & phân quyền (Admin, Hiệu trưởng, Khối trưởng, GVCN, GV Bộ môn, Học sinh).
2. `public.refresh_tokens`: Token đăng nhập JWT.
3. `public.exam_papers`: Đề thi upload & Metadata AI.
4. `public.curriculum_units`: Phân cấp chương trình môn học.
5. `public.exam_competencies`: Trọng số chuẩn Bloom đề thi.
6. `public.audit_logs`: Nhật ký thay đổi dữ liệu.
7. `public.report_schedules`: Lịch gửi báo cáo tự động.
8. `public.classroom_recordings`: Ghi âm bài giảng & Đánh giá AI.
9. `public.ai_sessions`: Phiên hội thoại AI Chat Text-to-SQL Agent.
10. `public.ai_messages`: Nhật ký tin nhắn AI Chat & Telemetry SQL.

### Schema `s360` (Student 360 DWH - 15 Bảng)
11. `s360.dim_school_year`: Danh mục năm học (Năm 2025-2026 hiện tại).
12. `s360.dim_homeroom_class`: Danh mục lớp chủ nhiệm (Khối 7 -> Khối 11).
13. `s360.dim_homeroom_class_student`: Danh sách học sinh & liên kết lớp chủ nhiệm.
14. `s360.dim_subject`: Danh mục 18 môn học chính thức & cấu hình thang điểm.
15. `s360.dim_exam`: Danh mục kỳ thi định kỳ (Giữa kỳ, Cuối kỳ).
16. `s360.dim_exam_moet`: Danh mục đầu điểm chuẩn Bộ GD (MOET).
17. `s360.dim_so_assignment`: Danh mục bài tập / nhiệm vụ học tập LMS.
18. `s360.dim_grade_scale_detail`: Ma trận quy đổi 6 thang điểm (SCALE_10, SCALE_100, SCALE_4, SCALE_6, LETTER_AF, PASS_FAIL).
19. `s360.fact_gradebooks`: Sổ điểm học phần / môn học tổng hợp trên lớp.
20. `s360.fact_gradebooks_moet`: Sổ điểm trên lớp chuẩn Bộ GD (MOET).
21. `s360.fact_so_assignment_grade`: Điểm bài tập LMS chi tiết.
22. `s360.fact_subject_academic_records`: Học bạ tổng kết cả năm chi tiết theo môn.
23. `s360.fact_overall_academic_records`: Học bạ tổng kết cả năm toàn diện (GPA, Học lực, Hạnh kiểm).
24. `s360.fact_so_evaluate_process_subjects`: Đánh giá nhận xét tiến trình môn học định kỳ.
25. `s360.fact_course_enrolls`: Nhật ký ghi nhận học sinh đăng ký & rút môn học phần tự chọn.

---

## 2. Ghi Chú Khi Tra Cứu So Sánh Với Schema 36 Bảng Gốc

Vui lòng xem file [schema_comparison_25_vs_36.md](file:///f:/PROJECT_VSF/TTS_SRA/docs_vsf/note/schema_comparison_25_vs_36.md) để biết chi tiết 11 bảng thuộc phân hệ Chuyên cần, Học phí ngoại khóa, Đi học muộn và Điểm rèn luyện rải rác chưa dùng ở Phase 1.
