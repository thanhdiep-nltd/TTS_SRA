
CÁC BẢNG chưa hiểu rõ:
+ stg_so_exam_moet_path
+ stg_so_strand_path
+ dim_school_year : calculator_type và calculator_name là gì?

+ dim_so_evaluate_progress
+ fact_course_enrolls: Có tính sinh viên không hay chỉ K-12? hay áp dụng cho tất cả khối lớp từ mẫu giáo tới đại học?

+ Nhà trường có được tự custorm thang chấm điểm hay không?

+ fact_overall_academic_records
+ fact_so_evaluate_process_subject_criterion: criterion_code định nghĩa ở đâu?
+ fact_so_evaluate_process_subjects

+ fact_so_subject_mastery: các thông số percent_... có ý nghĩa là gì.
+ fact_subject_academic_records.



# CÁC Bảng sẽ tạm thời bỏ qua

merged_vsf_sra_schema.sql
 bảng này sau khi merge quá nhiều thông tin nên tạm thời lên plan loại bỏ bớt để tập trung vào phần điểm trước vì agent của tôi trong 

src
 đang có text-to-sql nên tôi đang muốn test agent làm việc với 6 thang điểm mà hôm qua tôi đã liệt kê, thang 4, thang 6, thang 10, thang 100, thang chữ A...F, thang đạt/không đạt
