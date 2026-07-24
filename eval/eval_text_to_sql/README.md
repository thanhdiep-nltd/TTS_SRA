# 📊 AI Agent Text-to-SQL Evaluation Suite

Bộ công cụ kiểm thử tự động 2 tầng (**2-Tier Evaluation Suite**) cho phân hệ Text-to-SQL.

## 🚀 Cú Pháp Lệnh Chạy (CLI Commands)

### 1. Đánh giá nhanh Tầng 1 (Sub-Agent & SQL Validation - 0đ LLM Judge Cost):
```powershell
$env:PYTHONPATH="."; .venv\Scripts\python.exe eval/eval_text_to_sql/run_eval_suite.py --mode=tier1
```

### 2. Đánh giá đầy đủ Tầng 2 (End-to-End Workflow + LLM-as-a-Judge):
```powershell
$env:PYTHONPATH="."; .venv\Scripts\python.exe eval/eval_text_to_sql/run_eval_suite.py --mode=full
```

---

## 📁 Cấu Trúc File
- `eval_dataset.json`: Bộ dữ liệu 20 test-cases (Ground Truth).
- `run_eval_suite.py`: Script runner CLI.
- `results/`: Thư mục tự động xuất báo cáo kết quả JSON.
