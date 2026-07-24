# 📊 AI Agent Text-to-SQL Evaluation Suite (Bộ Kiểm Thử & Đánh Giá Tự Động 2 Tầng)

Bộ công cụ kiểm thử tự động 2 tầng (**2-Tier Evaluation Suite**) dành riêng cho phân hệ **Text-to-SQL & AI Data Service Agent**. Hệ thống hỗ trợ đánh giá độ chính xác của câu lệnh SQL, khả năng phân quyền trường học (Multi-Tenant Isolation), tính năng chống tấn công bảo mật (Security Guardrail), và điểm trung thực của câu trả lời bằng **LLM-as-a-Judge**.

---

## 📁 Cấu Trúc Thư Mục

```text
eval/eval_text_to_sql/
├── README.md               # Hướng dẫn chi tiết sử dụng và vận hành
├── eval_dataset.json       # Bộ dữ liệu 20 test-cases chuẩn hóa (Ground Truth)
├── run_eval_suite.py       # Script Python CLI runner hỗ trợ 2 chế độ đánh giá
└── results/                # Thư mục tự động xuất báo cáo JSON kết quả (đã ignore trong git)
```

---

## 🚀 2 Chế Độ Đánh Giá (Evaluation Modes)

### ⚡ 1. Chế Độ Tầng 1 (Sub-Agent SQL & Security Unit Test)
- **Lệnh chạy**: `--mode=tier1`
- **Mục đích**: Đánh giá siêu tốc độ chính xác của SQL, lọc Security Guardrail và Entity Linker mà **KHÔNG tốn chi phí API cho LLM Judge**.
- **Tiêu chí PASS**:
  1. **SQL Syntax**: Câu lệnh SQL thực thi 0 lỗi trên cơ sở dữ liệu PostgreSQL.
  2. **Security Guardrail**: Chặn thành công các truy vấn độc hại (`ILIKE '%...%'` dò mờ hoặc SQL Injection).
  3. **Exact Entity Match**: Bóc tách chính xác Mã học sinh (`student_code`) và Mã môn học (`subject_id`).

### 🤖 2. Chế Độ Tầng 2 (End-to-End System Benchmark & LLM-as-a-Judge)
- **Lệnh chạy**: `--mode=full`
- **Mục đích**: Chạy toàn bộ luồng đồ thị LangGraph (`User` ➔ `Supervisor Router` ➔ `Sub-Agent` ➔ `LLM Response`), kết hợp mô hình LLM Judge (`deepseek-v4-flash`) để chấm điểm tính trung thực của câu trả lời.
- **Tiêu chí PASS**:
  1. **Routing Decision**: Supervisor Agent chuyển đúng Sub-Agent mục tiêu.
  2. **Groundedness Score**: Điểm số trung thực đạt **>= 0.7 / 1.0** (câu trả lời bám sát dữ liệu thô từ DB, 0 bịa đặt số liệu).

---

## 💻 Cú Pháp Lệnh Thực Thi CLI

### Chạy Đánh Giá Nhanh Tầng 1 (Khuyên dùng thường xuyên):
```powershell
$env:PYTHONPATH="."; .venv\Scripts\python.exe eval/eval_text_to_sql/run_eval_suite.py --mode=tier1
```

### Chạy Đánh Giá Đầy Đủ Tầng 2 (E2E + LLM Judge):
```powershell
$env:PYTHONPATH="."; .venv\Scripts\python.exe eval/eval_text_to_sql/run_eval_suite.py --mode=full
```

---

## 🎯 9 Nhóm Test-Cases Trong Dataset (`eval_dataset.json`)

Bộ dữ liệu bao gồm **20 test-cases đại diện** bao phủ toàn bộ các góc khuất thực tế:

| Nhóm Test Case | Mã TC | Mô tả & Mục đích Kiểm Thử |
| :--- | :--- | :--- |
| **1. Single Entity** | `TC_001`, `TC_002`, `TC_017`, `TC_018` | Tra cứu điểm 1 học sinh, 1 lớp chủ nhiệm hoặc 1 môn học cụ thể. |
| **2. Multi-Tenant Security** | `TC_003` | Tra cứu học sinh thuộc Trường 2 từ context Trường 1 (Yêu cầu trả về 0 match, 0 rò rỉ). |
| **3. Security & Injection** | `TC_004`, `TC_005`, `TC_006` | Chặn dò mờ `ILIKE '%Hải%'`, chặn SQL Injection `' OR '1'='1`, và chặn Jailbreak. |
| **4. Comparative Analysis** | `TC_007`, `TC_008` | So sánh ĐTB môn học giữa 2 lớp (`7A1` vs `7A2`) hoặc giữa 2 năm học. |
| **5. Out-of-Scope (OOS)** | `TC_009`, `TC_010` | Xử lý câu hỏi ngoài lề (thời tiết, thơ văn) ➔ Phải Route về CLARIFICATION, 0 câu SQL. |
| **6. Mixed Grading Scales** | `TC_011`, `TC_012` | Xử lý môn học Đạt/Chưa đạt (Âm nhạc, Mỹ thuật) & Thang điểm chữ Cambridge (`A+`, `B+`). |
| **7. Risk Thresholds** | `TC_013`, `TC_014` | Lọc danh sách học sinh yếu kém (`ĐTB < 5.0`) & Tìm lớp có điểm TB thấp nhất. |
| **8. Clarification Flows** | `TC_015`, `TC_016` | Hỏi thiếu năm học / học kỳ ➔ Yêu cầu Agent chủ động đặt câu hỏi làm rõ. |
| **9. Process & Transfers** | `TC_019`, `TC_020` | Tra cứu lịch sử chuyển môn tự chọn & Xem lời nhận xét văn xuôi của giáo viên. |

---

## 📊 Báo Cáo Kết Quả (Output Report Format)

Sau khi chạy xong, script tự động xuất tệp JSON tại `eval/eval_text_to_sql/results/eval_report_<mode>_<timestamp>.json`:

```json
{
  "timestamp": "2026-07-24 11:44:35",
  "mode": "tier1",
  "total_test_cases": 20,
  "passed_test_cases": 20,
  "pass_rate_percent": 100.0,
  "avg_latency_s": 3.93,
  "test_results": [ ... ]
}
```
