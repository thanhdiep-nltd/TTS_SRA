# Plan: Fix Multi-Statement SQL & No Forced UNION ALL

## 1. Vấn Đề

### Issue 1: Multi-Statement SQL (Semicolon Split)
**Hiện tượng**: Agent gửi 2+ câu SELECT phân tách bằng `;` trong 1 lượt gọi `execute_read_only_query`.

**Nguyên nhân gốc rễ**: LLM cố gắng "tiết kiệm" lượt gọi tool. Prompt đã cấm (dòng 84) nhưng LLM đôi khi vẫn vi phạm do recency bias/context dilution.

**Code chịu trách nhiệm**: 
- Tool [`execute_read_only_query`](src/agents/data_service_agent/tools.py:194-216) — không có pre-check multi-statement

### Issue 2: No Forced UNION ALL
**Hiện tượng**: Agent dùng UNION ALL/CTE để gộp dữ liệu từ 2 bảng khác cấu trúc (Vinschool vs MOET) trong 1 câu SQL.

---

## 2. Giải Pháp

### 2.1. Multi-Statement SQL — Pre-check trong Tool Layer

**File**: [`src/agents/data_service_agent/tools.py`](src/agents/data_service_agent/tools.py)

Thêm pre-check trong `execute_read_only_query` trước khi gọi `validate_and_secure_sql`:

**Import cần thêm**: `import re` ở đầu file (hiện tại tools.py chưa import `re`).

**Vị trí pre-check**: Sau dòng 201 (`user_role = current_user_role.get()`), trước `try:` ở dòng 203.

```python
    # Pre-check: Phát hiện multi-statement SQL (semicolon split)
    cleaned = re.sub(r"--.*$", "", sql_query, flags=re.MULTILINE)       # Xoá line comment -- ...
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)        # Xoá block comment /* ... */
    cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", "", cleaned)                  # Xoá string literals
    cleaned = cleaned.rstrip(";")                                        # Strip trailing ; (hợp lệ)
    if ";" in cleaned:
        # Vẫn còn dấu ; sau khi strip trailing → multi-statement
        return "LỖI: Phát hiện nhiều câu lệnh SQL trong 1 lượt gọi. " \
               "Mỗi lượt gọi chỉ được gửi DUY NHẤT 1 câu lệnh SELECT. " \
               "Vui lòng chia thành các câu lệnh đơn riêng biệt."
```

### 2.2. Prompt Rule — No Forced UNION ALL

**File**: [`src/agents/data_service_agent/prompts.py`](src/agents/data_service_agent/prompts.py)

Thêm rule mới **giữa dòng 90 (hết rule 5) và dòng 91 (rule "7" hiện tại — Trình bày kết quả)**.

> **Lưu ý**: Prompt hiện tại đã có rule 3 về UNION ALL granularity (dòng 85-88). Rule mới này nhấn mạnh khía cạnh **khác cấu trúc bảng** (Vinschool vs MOET) một cách tường minh hơn.

```
7. NGUYÊN TẮC KHÔNG GỘP UNION ALL KHI KHÁC CẤU TRÚC (NO FORCED UNION ALL):
   - KHÔNG dùng UNION ALL/CTE để gộp dữ liệu từ 2 bảng có cấu trúc khác nhau
     (vd: fact_gradebooks Vinschool vs fact_gradebooks_moet MOET).
   - Nếu cần dữ liệu từ nhiều bảng, hãy thực hiện từng câu lệnh SELECT riêng biệt
     ở các lượt gọi tool khác nhau, sau đó tự tổng hợp kết quả.
```

---

## 3. Files Cần Sửa

| File | Khu vực | Thay đổi |
|------|---------|----------|
| [`src/agents/data_service_agent/tools.py`](src/agents/data_service_agent/tools.py) | `execute_read_only_query` | Thêm pre-check multi-statement trước validate |
| [`src/agents/data_service_agent/prompts.py`](src/agents/data_service_agent/prompts.py) | Giữa rule 5 (dòng 90) và rule "7" cũ (dòng 91) | Thêm rule 7 mới: No Forced UNION ALL |

---

## 4. Logic Pre-check Multi-Statement

```python
cleaned = sql_query
cleaned = re.sub(r"--.*$", "", cleaned, flags=re.MULTILINE)       # Xoá line comment
cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)      # Xoá block comment
cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", "", cleaned)                # Xoá string literals
cleaned = cleaned.rstrip(";")                                      # Bỏ ; cuối (hợp lệ)
if ";" in cleaned:                                                 # Còn ; → multi-statement
    return "LỖI: ..."
```

**Test cases**:
| Input | Sau xoá comment/string | After rstrip | `";" in` | Kết quả |
|-------|----------------------|-------------|----------|---------|
| `SELECT * FROM table;` | `SELECT * FROM table;` | `SELECT * FROM table` | False | ✅ Cho qua |
| `SELECT * FROM table` | `SELECT * FROM table` | `SELECT * FROM table` | False | ✅ Cho qua |
| `SELECT 1; SELECT 2` | `SELECT 1; SELECT 2` | `SELECT 1; SELECT 2` | True | ✅ Chặn |
| `SELECT * FROM t WHERE x = 'a;b';` | `SELECT * FROM t WHERE x = '';` | `SELECT * FROM t WHERE x = ''` | False | ✅ Cho qua |
| `/* comment ; here */ SELECT 1;` | ` SELECT 1;` | ` SELECT 1` | False | ✅ Cho qua |
| `SELECT 1; /* block */ SELECT 2` | `SELECT 1;  SELECT 2` | `SELECT 1;  SELECT 2` | True | ✅ Chặn |
