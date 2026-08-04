# Giải Pháp Thiết Kế Kiến Trúc Dữ Liệu Hai File Nhất Quán và Đồng Bộ Cho Hệ Thống Cảnh Báo Nguy Cơ Học Tập (TAD-PG + Multi-Matrix G1-G9 Master Spec)

## Bản chất lỗi logic trong sinh dữ liệu ngẫu nhiên và mô hình ràng buộc thực thể

Khi áp dụng các phương pháp lấy mẫu ngẫu nhiên độc lập (Naive Randomization) cho từng biến số riêng lẻ, dữ liệu sinh ra thường xuất hiện các mâu thuẫn logic nghiêm trọng làm mất đi tính chân thực của phân phối thực tế.

Hiện tượng một học sinh đạt điểm số môn Toán Tiếng Anh lên tới $9.8$ nhưng điểm Toán thông thường chỉ đạt $4.5$, hoặc một học sinh được định nghĩa là có học lực xuất sắc nhưng lại liên tục nghỉ học không phép mà không có bất kỳ sự suy giảm nào về kết quả học tập, là những minh chứng điển hình cho sự sụp đổ của logic tương quan hệ thống.

Do đó, để tạo ra một bộ dữ liệu giả lập có giá trị huấn luyện cho các mô hình học máy và AI Agents, quy trình khởi tạo phải dựa trên phương pháp **Sinh Dữ liệu Định hướng Lý thuyết và Kiểm soát Phân phối (Theory-Aligned and Distribution-Controllable Persona Generation - TAD-PG)** kết hợp với **Ma trận Mẫu Điểm Biến Động Đa Chiều (G1 ➔ G9)** và **22 Mã Hành Vi Kỷ Luật**.

---

## Kiến trúc hệ cơ sở dữ liệu hai phân hệ: Khung tham chiếu và Nhật ký thực thể

Cơ sở dữ liệu được phân rã thành hai phân hệ duy trì tính toàn vẹn tham chiếu chặt chẽ trên **37 Bảng CSDL**:

1. **Phân hệ Bảng Chiều (Dimension Tables)**: Chứa các thông tin định danh tĩnh và đặc tính ẩn mang tính định hình của từng học sinh (`students_dim` / `s360.dim_homeroom_class_student`), môn học (`s360.dim_subject`), đợt thi (`s360.dim_exam`), và tiêu chí kỷ luật (`s360.dim_behavior`).
2. **Phân hệ Bảng Sự Kiện (Fact Tables)**: Ghi nhận các chỉ số biến đổi theo từng học kỳ hoặc từng ngày (`s360.fact_gradebooks`, `s360.fact_behavior_logs`, `s360.fact_absent_logs`, `s360.fact_so_daily_attendance`...).

---

## Mô hình hóa toán học các thuộc tính ẩn và ma trận G1-G9

### 1. Vector Đặc Tính Ẩn (Latent Variables Vector)
Chúng ta gọi $\Theta_i = [C_{\text{Math}, i}, C_{\text{Lang}, i}, E_i]^T$ là vector đặc tính ẩn của học sinh $i$:
- $C_{\text{Math}, i}$: Năng lực tư duy định lượng & logic.
- $C_{\text{Lang}, i}$: Năng lực tư duy ngôn ngữ & xã hội.
- $E_i$: Mức độ nỗ lực tự giác (Effort/Engagement Level).

### 2. Ma Trận Phân Loại 5 Nhóm Persona Học Đường
| Tên nhóm Persona | Tỷ lệ | $C_{\text{Math}}$ | $C_{\text{Lang}}$ | Nỗ lực $E$ | Phân phối thực tế |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **High_Achiever** | **15%** | $> +1.5$ | $> +1.5$ | $> +1.5$ | Điểm giỏi toàn diện, vắng $\approx 0$, không vi phạm. |
| **STEM_Focus** | **15%** | $1.0 - 2.2$ | $-1.2 - -0.4$ | $0.2 - 1.0$ | Toán cao ($>8.5$), Văn & Anh ở mức trung bình. |
| **Humanities_Focus** | **15%** | $-1.2 - -0.4$ | $1.0 - 2.2$ | $0.2 - 1.2$ | Văn & Anh cao ($>8.5$), Toán ở mức trung bình. |
| **Diligent_Average** | **45%** | $-0.5 - 0.5$ | $-0.5 - 0.5$ | $0.6 - 1.2$ | Chăm chỉ, điểm khá ổn định mốc $6.5 - 7.5$. |
| **Academic_At_Risk** | **10%** | $< -1.0$ | $< -1.0$ | $-0.5 - 0.3$ | Học lực yếu, vắng nhiều, nguy cơ trượt cao. |

### 3. Ma Trận 9 Nhóm Mẫu Điểm Biến Động Thực Tế (Score Profiles G1 ➔ G9)
| Mã Nhóm | Tỷ Lệ % | Tên Mẫu Điểm | Mô Tả Biến Động Thực Tế |
| :--- | :--- | :--- | :--- |
| **G1** | **60%** | **Giỏi & Ổn định** | Điểm LMS và Điểm Thi đều cao ổn định: $8.0 - 10.0$. |
| **G2** | **15%** | **Trung bình ổn định** | Điểm LMS và Điểm Thi duy trì mức khá/trung bình: $5.0 - 7.5$. |
| **G3** | **3%** | **Lội ngược dòng (Progress)** | Đầu kỳ điểm thấp $3.0 - 4.0$, cuối kỳ bứt phá lên $8.0 - 9.0$ (nhờ gia sư/phụ đạo). |
| **G4** | **5%** | **Sát ngưỡng trượt (Borderline)** | Điểm bấp bênh quanh mốc nguy cơ $3.8 - 5.5$. |
| **G5** | **5%** | **Thi giỏi nhưng Bỏ LMS** | Bài tập LMS $0.0 - 3.0$ (lười nộp), nhưng Điểm Thi tập trung đạt $7.0 - 9.0$ (Học sinh thông minh bất mãn). |
| **G6** | **5%** | **LMS cao nhưng Thi thấp** | LMS đạt $9.0 - 10.0$ (chép bài/dùng AI gánh), nhưng Điểm Thi rớt xuống $2.0 - 4.0$ (Học vẹt/chép bài). |
| **G7** | **4%** | **Sụt giảm đột ngột (Crisis)** | Đầu năm giỏi $8.0 - 9.0$, giữa năm sút thảm hại xuống $2.0 - 3.0$ (biến cố gia đình/tâm lý). |
| **G8** | **2%** | **Yếu kém toàn diện** | Cả bài tập LMS lẫn Điểm Thi cử đều dưới $3.5$. |
| **G9** | **1%** | **Trắng điểm / Vắng thi** | Bỏ thi / Nhận điểm $0.0$ do sự cố vắng mặt đột xuất. |

### 4. Cơ chế đồng thuận điểm số và liên kết chéo (Joint Dependency)
Toán Tiếng Anh ($\text{Math\_English}$) tuân theo hàm liên kết tuyến tính phụ thuộc Toán ($\text{Math}$) và Tiếng Anh ($\text{English}$):

$$\text{Math\_English}_i = \text{Clip}\left( 0.7 \cdot \text{Math}_i + 0.3 \cdot \text{English}_i + \epsilon_{i}, \, 0, \, 10 \right)$$

Trong đó $\epsilon_i \sim \mathcal{N}(0, 0.2^2)$ là biến động ngẫu nhiên nhỏ trong phòng thi.

### 5. Cơ chế đệm chuyên cần thích ứng (Adaptive Attendance Buffer) và Phạt phi tuyến
Ngưỡng đệm tự học $T_i$:
$$T_i = \max\left(0, \, \lfloor 1.5 \cdot C_i \rfloor\right)$$

Hệ số phạt điểm do nghỉ học không phép giảm sâu theo hàm mũ đối với học sinh giỏi:
$$\gamma_i = 0.04 \cdot e^{-0.5 \cdot C_i}$$

Điểm số cuối cùng sau khi áp dụng phạt chuyên cần hiệu dụng $A_{\text{effective}, i} = \max(0, A_{\text{unexcused}, i} - T_i)$:
$$\text{Score}_{\text{final}, i} = \text{Score}_{\text{base}, i} \cdot \left(1 - \gamma_i \cdot A_{\text{effective}, i}\right)$$

---

## Danh Mục 22 Tiêu Chí Hành Vi & Phân Phối Kỷ Luật (`s360.dim_behavior`)

| STT | Mã Tiêu Chí (`code`) | Tên Tiêu Chí | Nhóm Hành Vi | Điểm Phạt/Thưởng |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `BEH_LATE_MORNING` | Đi học muộn đầu giờ sáng (sau 7h30) | Nếp sống & Chuyên cần | -2.0 |
| 2 | `BEH_ABSENT_FULLDAY_NO_PERM` | Nghỉ học cả ngày không xin phép | Nếp sống & Chuyên cần | -5.0 |
| 3 | `BEH_ABSENT_FULLDAY_WITH_PERM` | Nghỉ học cả ngày có đơn xin phép / ốm | Nếp sống & Chuyên cần | 0.0 |
| 4 | `BEH_ABSENT_PERIOD_NO_PERM` | Vắng mặt / Bỏ tiết học môn phần không lý do | Nếp sống & Chuyên cần | -3.0 |
| 5 | `BEH_LATE_PERIOD` | Vào lớp muộn sau chuông báo tiết học | Nếp sống & Chuyên cần | -1.0 |
| 6 | `BEH_LEAVE_EARLY` | Tự ý về sớm trước giờ tan học | Nếp sống & Chuyên cần | -4.0 |
| 7 | `BEH_UNIFORM_WRONG` | Mặc sai đồng phục quy định của trường | Trang phục & Tác phong | -1.0 |
| 8 | `BEH_NO_STUDENT_CARD` | Không đeo thẻ học sinh | Trang phục & Tác phong | -1.0 |
| 9 | `BEH_HAIRCUT_VIOLATION` | Đầu tóc, trang điểm vi phạm nội quy | Trang phục & Tác phong | -2.0 |
| 10 | `BEH_HOMEWORK_MISSING` | Không làm bài tập về nhà | Nề nếp Học tập | -2.0 |
| 11 | `BEH_NO_EQUIPMENT` | Thiếu sách vở / dụng cụ học tập | Nề nếp Học tập | -1.0 |
| 12 | `BEH_CELLPHONE_CLASS` | Sử dụng điện thoại riêng trong giờ học | Nề nếp Học tập | -3.0 |
| 13 | `BEH_TALKING_IN_CLASS` | Mất trật tự, làm việc riêng trong giờ | Nề nếp Học tập | -1.0 |
| 14 | `BEH_CHEATING_TEST` | Gian lận trong khi làm bài kiểm tra | Nề nếp Học tập | -10.0 |
| 15 | `BEH_BAD_LANGUAGE` | Nói tục, chửi thề trong khuôn viên trường | Kỷ luật & Giao tiếp | -3.0 |
| 16 | `BEH_LITTERING` | Xả rác bừa bãi không đúng nơi quy định | Kỷ luật & Giao tiếp | -2.0 |
| 17 | `BEH_DISRESPECT_TEACHER` | Cãi lời / Vô lễ với thầy cô giáo | Kỷ luật & Giao tiếp | -10.0 |
| 18 | `BEH_FIGHTING` | Gây nổ đố / Đánh nhau trong trường | Kỷ luật & Giao tiếp | -15.0 |
| 19 | `BEH_GOOD_DEED` | Nhặt được của rơi trả lại người mất | Khen thưởng & Việc tốt | +5.0 |
| 20 | `BEH_HELP_PEER` | Tích cực phụ đạo / Giúp đỡ bạn học tiến bộ | Khen thưởng & Việc tốt | +3.0 |
| 21 | `BEH_SCHOOL_EVENT_VOLUNTEER` | Hỗ trợ tích cực sự kiện truyền thông của trường | Khen thưởng & Việc tốt | +4.0 |
| 22 | `BEH_CLEAN_CLASSROOM` | Chủ động vệ sinh giữ gìn lớp học sạch đẹp | Khen thưởng & Việc tốt | +2.0 |

Dữ liệu nhật ký vi phạm (`fact_behavior_logs`) được phân phối theo mô hình Pareto 70/20/10:
- **70% Học sinh ngoan**: 0 đến 1 vi phạm nhẹ / học kỳ.
- **20% Học sinh thỉnh thoảng vi phạm**: 2 đến 4 vi phạm.
- **10% Học sinh Rủi ro Kỷ luật (At-Risk)**: 5 đến 12 vi phạm (kích hoạt cờ phạt tái phạm tăng nặng).