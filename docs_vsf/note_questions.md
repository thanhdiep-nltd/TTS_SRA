1. Các thông số report_... trong dim_exam sẽ có ý nghĩa như thế nào? các thông số này lấy ở đâu?
2. calculator_type, calculator_name sẽ được sử dụng như thế nào và các thông số này lấy ở đâu?
3. Trường học định nghĩa thang điểm (Thang 10, Thang 6, Thang chữ A/B/C/D...) tự tạo ra cá chuẩn riêng hay sẽ lựa chọn 1 trong các thang điểm có sẵng trong hệ thống?
4. Mặc dù trong trường hợp mỗi 1 môn có 1 thang điểm riêng, nhưng BGH vẫn phải set năm học đó dim_school_year, calculator_type, calculator_name trong database để xác định cả năm học đó tính điểm như thế nào à? => Cả năm học này sẽ dùng Thuật toán/Công thức nào để tổng kết điểm về một Chuẩn duy nhất! Nên BGH bắt buộc phải chọn công thức để chuyển về.

5. final_grade_convert trong fact_gradebooks đó là gì? trong trường hợp mỗi môn có 1 thang điểm riêng thì cái final_grade_convert này sẽ là gì?

=> Đề xuất tạo ra 2 bảng dim_grade_scale_detail chứa các quy tắc Tỷ lệ % Đại diện (Midpoint Percentage):
Điểm chữ A (Dải $85% - 100%$) $\rightarrow$ Tỷ lệ % đại diện = $92.5%$ (Quy sang Thang 10 = $9.25$).
Điểm chữ B (Dải $70% - 84%$) $\rightarrow$ Tỷ lệ % đại diện = $77.0%$ (Quy sang Thang 10 = $7.7$).
Điểm chữ Đạt $\rightarrow$ Tỷ lệ % đại diện = $100%$ (Quy sang Thang 10 = $10.0$).
Điểm chữ Chưa đạt $\rightarrow$ Tỷ lệ % đại diện = $40%$ (Quy sang Thang 10 = $4.0$).

=> Nghiệp vụ đang được hiểu như thế này:
- Áp dụng cho nhiều trường.
- Mỗi trường có thể có nhiều thang đánh giá điểm khác nhau, tuy nhiên mỗi môn học trong 1 trường nhiều hệ ví dụ VinSchool có thể có 2 môn học song song chung kỳ nhưng thang điểm khác nhau: ví dụ học theo hệ của MOET và một số môn Hệ Cambridge cùng lúc thì Moet đánh giá theo Thang 10, Cambridge đánh giá theo Thang 100.
- Schema mới từ VSF vẫn chưa hộ trợ custorm thang điểm theo từng môn học nên phải có bảng mới để lưu trữ các thông tin này. Vậy có cần tích hợp vào 2 bảng dim_grade_scale_detail và dim_grading_policy để lưu trữ thông tin thang điểm của từng môn học, từng hệ học ở từng năm học không? 
- Vì có nhiều môn học theo nhiều chuẩn nên BGH đầu năm phải cấu hình cả dim_school_year, calculator_type, calculator_name trong database để xác định cả năm học đó tính điểm như thế nào à? => Cả năm học này sẽ dùng Thuật toán/Công thức nào để tổng kết điểm về một Chuẩn duy nhất! Nên BGH bắt buộc phải chọn công thức để chuyển về. Bắt buộc tạo thêm 1 bảng dim_calculator để lưu trữ các thuật toán công thức đó. 

Kết quả: tạo dim_grade_scale_detail lưu các công thức của các thang điểm về dạng %. Rồi từ đó dùng để chuyển qua lại giữa các hệ điểm. 

-
