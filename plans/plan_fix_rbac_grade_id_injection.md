# Plan: Sửa lỗi RBAC inject `grade_id` sai cột + tín hiệu ACCESS_DENIED cho agent
# v2 — Đã tích hợp 3 phản biện: (1) RBAC cho template tools, (2) ACCESS_DENIED cho stat/report agent, (3) testcase eval grade-head

## 1. Bối cảnh / Vấn đề

Sau khi chỉnh hệ thống phân quyền, khi agent truy vấn điểm lớp 7A1 (Toán HK2), hệ thống trả về:
- **Lỗi SQL** với truy vấn Vinschool (`fact_gradebooks`) do bị chèn điều kiện `grade_id = 6` vào bảng không có cột `grade_id`.
- **Kết quả rỗng** với truy vấn MOET (`fact_gradebooks_moet`) và danh sách học sinh (`dim_homeroom_class_student`) vì filter `grade_id IN (6)` hợp lệ cú pháp nhưng loại hết khối 7.
- Agent **thử lại vài chục lần** rồi **kết luận sai**: "hệ thống không có học sinh khối 7, chưa nhập liệu" và soạn cả báo cáo gửi BGH đề nghị nhập liệu.

**Nguyên nhân gốc rễ** (đã xác nhận):
1. [`src/core/security/sql_validator.py`](../src/core/security/sql_validator.py:272) inject `{alias}.grade_id IN (...)` vào danh sách 5 bảng, trong đó **2 bảng không có cột `grade_id`** (`fact_gradebooks`, `fact_so_assignment_grade`) → lỗi `column "grade_id" does not exist`. Ngoài ra `fact_so_assignment_grade` còn bị inject `homeroom_class_id`/`subject_id` cũng không tồn tại.
2. Tool [`execute_read_only_query()`](../src/agents/data_service_agent/tools.py:232) nuốt mọi exception thành chuỗi `"Lỗi thực thi truy vấn SQL: ..."` chung chung → LLM không biết đây là lỗi phân quyền → retry vô ích.
3. Không có tín hiệu phân biệt "không có quyền" vs "không có dữ liệu" → LLM suy diễn sai, sinh báo cáo sai lệch.

## 2. Ma trận cột của các bảng bị inject RBAC (đối chiếu DDL mock)

| Bảng (`s360.`) | `homeroom_class_id` | `grade_id` | `subject_id` | `assignment_id` |
|---|---|---|---|---|
| `fact_gradebooks` | ✅ | ❌ | ✅ | ❌ (`so_exam_id`) |
| `fact_gradebooks_moet` | ✅ | ✅ | ✅ | ❌ (`gradebook_type_item_id`) |
| `fact_overall_academic_records` | ✅ | ✅ | ❌ | ❌ |
| `dim_homeroom_class_student` | ✅ | ✅ | ❌ | ❌ |
| `fact_so_assignment_grade` | ❌ | ❌ | ❌ | ✅ |

Bảng trung gian dùng để resolve:
- `s360.dim_homeroom_class` có `id`, `grade_id` → dùng để map `grade_id` → `homeroom_class_id`.
- `s360.dim_so_assignment` có `assignment_id`, `grade_id`, `subject_id` → dùng cho `fact_so_assignment_grade`.
- `s360.dim_homeroom_class_student` có `student_code`, `homeroom_class_id`, `grade_id` → dùng để map lớp cho `fact_so_assignment_grade`.

## 3. Thay đổi chi tiết theo từng file

### 3.1. `src/core/security/sql_validator.py` — Sửa lõi inject RBAC (BẮT BUỘC)

**a) Thêm exception riêng** (đặt sau các constant, trước `is_direct_table`):

```python
class PermissionDeniedError(Exception):
    """Truy vấn nằm ngoài phạm vi phân quyền của user hiện tại."""
```

**b) Tái cấu trúc khối inject RBAC** (thay thế khối `if rbac_meta and not ...` ở dòng ~270-287) bằng helper theo khả năng cột:

```python
_RBAC_TABLES = {
    "fact_gradebooks", "fact_gradebooks_moet", "fact_overall_academic_records",
    "fact_so_assignment_grade", "dim_homeroom_class_student",
}
# Bảng có cột grade_id trực tiếp
_DIRECT_GRADE_TABLES = {"fact_gradebooks_moet", "fact_overall_academic_records", "dim_homeroom_class_student"}
# Bảng có cặp (homeroom_class_id, subject_id) trực tiếp — dùng cho subject_class_pairs
_SUBJECT_CLASS_TABLES = {"fact_gradebooks", "fact_gradebooks_moet"}


def _rbac_clauses_for_table(t_name: str, alias: str, rbac_meta: dict) -> list[str]:
    """Sinh điều kiện RBAC theo cấu trúc cột thực của bảng.

    - Bảng có cột grade_id → dùng `{alias}.grade_id IN (...)`.
    - fact_gradebooks (không có grade_id) → resolve qua dim_homeroom_class.
    - fact_so_assignment_grade (không có class/grade/subject) → resolve qua
      dim_so_assignment + dim_homeroom_class_student.
    """
    homeroom_ids = rbac_meta.get("homeroom_class_ids") or []
    grade_ids = rbac_meta.get("grade_ids") or []
    pairs = rbac_meta.get("subject_class_pairs") or []
    clauses: list[str] = []

    if t_name == "fact_so_assignment_grade":
        if homeroom_ids:
            cids = ", ".join(map(str, homeroom_ids))
            clauses.append(
                f"{alias}.student_code IN (SELECT student_code FROM s360.dim_homeroom_class_student "
                f"WHERE homeroom_class_id IN ({cids}))"
            )
        if grade_ids:
            gids = ", ".join(map(str, grade_ids))
            clauses.append(
                f"{alias}.assignment_id IN (SELECT assignment_id FROM s360.dim_so_assignment "
                f"WHERE grade_id IN ({gids}))"
            )
        if pairs:
            pair_clauses = [
                f"{alias}.assignment_id IN (SELECT a.assignment_id FROM s360.dim_so_assignment a "
                f"JOIN s360.dim_homeroom_class_student s ON s.grade_id = a.grade_id "
                f"WHERE a.subject_id = {subid} AND s.homeroom_class_id = {cid})"
                for cid, subid in pairs
            ]
            clauses.append(f"({' OR '.join(pair_clauses)})")
        return clauses

    # Các bảng còn lại đều có homeroom_class_id
    if homeroom_ids:
        cids = ", ".join(map(str, homeroom_ids))
        clauses.append(f"{alias}.homeroom_class_id IN ({cids})")
    if grade_ids:
        gids = ", ".join(map(str, grade_ids))
        if t_name in _DIRECT_GRADE_TABLES:
            clauses.append(f"{alias}.grade_id IN ({gids})")
        else:  # fact_gradebooks
            clauses.append(
                f"{alias}.homeroom_class_id IN (SELECT id FROM s360.dim_homeroom_class "
                f"WHERE grade_id IN ({gids}))"
            )
    if pairs and t_name in _SUBJECT_CLASS_TABLES:
        pair_clauses = [f"({alias}.homeroom_class_id = {cid} AND {alias}.subject_id = {subid})" for cid, subid in pairs]
        clauses.append(f"({' OR '.join(pair_clauses)})")
    return clauses
```

**c) Trong vòng lặp `for select_node in ...`** — thay khối inject cũ bằng:

```python
if rbac_meta and not rbac_meta.get("is_full_access", True):
    if t_name in _RBAC_TABLES:
        rbac_clauses = _rbac_clauses_for_table(t_name, alias, rbac_meta)
        if rbac_clauses:
            constraints.append(f"({' OR '.join(rbac_clauses)})")
        else:
            # User có role nhưng KHÔNG có phân công phù hợp với bảng này
            # → từ chối rõ ràng để agent dừng sớm thay vì hiểu nhầm là không có dữ liệu.
            raise PermissionDeniedError(
                "Bạn không có quyền truy cập bảng này theo phân công hiện tại."
            )
```

**d) Cập nhật `get_user_assignment_constraints`** để trả về scope dạng thân thiện cho tool (thêm key `"scope_summary"`):

```python
return {
    "is_full_access": False,
    "homeroom_class_ids": list(homeroom_class_ids),
    "grade_ids": list(grade_ids),
    "subject_class_pairs": list(subject_class_pairs),
    "scope_summary": (
        f"homeroom_class_ids={sorted(homeroom_class_ids)}; "
        f"grade_ids={sorted(grade_ids)}; "
        f"subject_class_pairs={sorted(subject_class_pairs)}"
    ),
}
```

Lưu ý: trường hợp DB lỗi (except) hiện trả `is_full_access: True` — GIỮ NGUYÊN (fail-open để không chặn nhầm), chỉ thêm `scope_summary` trong nhánh thành công.

### 3.2. `src/agents/data_service_agent/tools.py` — Tín hiệu ACCESS_DENIED + scope hint (BẮT BUỘC)

Sửa hàm `execute_read_only_query`:

1. **Import** thêm `PermissionDeniedError`, `get_user_assignment_constraints` từ `sql_validator`.
2. **Check nhanh trước khi chạy**: nếu user không phải ADMIN/PRINCIPAL và không có assignment nào → trả về `ACCESS_DENIED` ngay (không tốn query).

```python
rbac_meta = get_user_assignment_constraints(user_id, user_role)
if rbac_meta.get("is_full_access") is False and not (
    rbac_meta.get("homeroom_class_ids") or rbac_meta.get("grade_ids") or rbac_meta.get("subject_class_pairs")
):
    return (
        "ACCESS_DENIED: Tài khoản của bạn chưa được phân công giảng dạy/chủ nhiệm nào "
        "nên không thể truy cập dữ liệu học sinh. Vui lòng dừng truy vấn và báo người dùng "
        "liên hệ Ban Giám Hiệu để cấp quyền."
    )
```

3. **Bắt `PermissionDeniedError` riêng** (trước `except Exception`):

```python
except PermissionDeniedError as e:
    return f"ACCESS_DENIED: {e}"
```

4. **Scope hint khi kết quả rỗng + RBAC đang hoạt động**: sau khi `rows = ...fetchall()`, nếu `not rows` và `rbac_meta` không full access thì trả về thông báo nêu rõ phạm vi được phép:

```python
if not rows:
    scope = rbac_meta.get("scope_summary", "")
    return (
        "Không tìm thấy dữ liệu khớp với truy vấn trong phạm vi phân quyền hiện tại. "
        f"Phạm vi bạn được phép truy cập: {scope}. "
        "Nếu đối tượng cần tra cứu (lớp/khối/môn) nằm NGOÀI phạm vi trên, đây là giới hạn "
        "phân quyền chứ KHÔNG phải dữ liệu không tồn tại — hãy dừng lại và báo người dùng "
        "liên hệ Ban Giám Hiệu nếu cần mở rộng quyền."
    )
```

> Giữ nguyên hành vi hiện tại khi RBAC không hoạt động (full access): vẫn trả `[]` JSON để LLM tự kết luận "không có dữ liệu".

### 3.3. `src/agents/data_service_agent/prompts.py` — Dừng retry khi ACCESS_DENIED (BẮT BUỘC)

Thêm quy tắc mới vào `DATA_SERVICE_AGENT_SQL_PROMPT` (phần `QUY TẮC VẬN HÀNH BẮT BUỘC`):

```text
X. QUY TẮC XỬ LÝ PHÂN QUYỀN (ACCESS CONTROL):
   - Nếu kết quả tool chứa "ACCESS_DENIED" hoặc cụm "phạm vi phân quyền" / "ngoài phạm vi":
     ĐÓ LÀ LỖI PHÂN QUYỀN, KHÔNG phải lỗi SQL hay dữ liệu trống.
   - TUYỆT ĐỐI KHÔNG thử lại bằng câu SQL khác, không đổi bảng, không UNION ALL thử nghiệm.
   - DỪNG NGAY, kết thúc lượt và phản hồi rằng người dùng không có quyền truy cập dữ liệu
     lớp/khối/môn này theo phân công hiện tại.
```

### 3.4. `src/agents/supervisor/node.py` — Phân biệt "không có quyền" vs "không có dữ liệu" (BẮT BUỘC)

1. Mở rộng quy tắc RBAC ở dòng ~76-78: nhận diện thêm `ACCESS_DENIED` và scope hint.

2. Mở rộng nhánh NO DATA HANDLING ở dòng ~357-360 (trong prompt `system_prompt`): nếu Sub-Agent phản hồi chứa `ACCESS_DENIED` / "phạm vi phân quyền" → chọn `FINISH` và phản hồi:
   *"Rất tiếc, theo chính sách phân quyền học vụ, Thầy/Cô không có quyền truy cập dữ liệu của lớp/khối/môn này. Vui lòng liên hệ Ban Giám Hiệu nếu cần thêm thông tin."*
   và TUYỆT ĐỐI KHÔNG đưa ra khuyến nghị "nhập liệu / thiếu dữ liệu".

3. Cập nhật prompt tổng hợp (`synthesis_prompt` dòng ~549): nếu transcript chứa `ACCESS_DENIED`, không soạn báo cáo "không có dữ liệu" mà trả lời về giới hạn phân quyền.

### 3.5. `src/agents/data_service_agent/node.py` — Giới hạn retry (NÊN LÀM)

Tại dòng ~216, thêm `config` với `recursion_limit`:

```python
result = await agent_instance.ainvoke(
    {"messages": exec_messages},
    config={"recursion_limit": 12},  # chặn vòng lặp "thử vài chục lần"
)
```

Kết hợp với 3.3, agent sẽ dừng ngay khi gặp ACCESS_DENIED thay vì chạm giới hạn.

### 3.6. PHẢN BIỆN 1 — Bọc RBAC cho template tools `get_student_grades` / `get_class_grades` / `get_student_info` (BẮT BUỘC, đợt này)

**Vấn đề**: [`get_student_grades()`](../src/agents/data_service_agent/tools.py:50), [`get_class_grades()`](../src/agents/data_service_agent/tools.py:124), [`get_student_info()`](../src/agents/data_service_agent/tools.py:12) chạy raw SQL qua `session.execute(text(...))` chỉ lọc `so_school_id` → **bỏ qua RBAC hoàn toàn** → user trưởng khối 6 vẫn truy xuất được điểm/lớp/khối 7 qua template (rò rỉ dữ liệu).

**Giải pháp** (an toàn, KHÔNG rewrite SQL qua validator vì các query dùng bind param `:sid`):

a) Thêm helper dùng chung trong `tools.py`:

```python
from src.core.security.sql_validator import get_user_assignment_constraints

def _rbac_denied(scope: str) -> str:
    return (
        "ACCESS_DENIED: Dữ liệu bạn yêu cầu nằm ngoài phạm vi phân quyền hiện tại. "
        f"Phạm vi bạn được phép truy cập: {scope}. "
        "Vui lòng dừng lại và báo người dùng liên hệ Ban Giám Hiệu nếu cần mở rộng quyền."
    )

def _is_scope_allowed(rbac_meta: dict, grade_id=None, homeroom_class_id=None, subject_id=None) -> bool:
    if rbac_meta.get("is_full_access", False):
        return True
    if grade_id and int(grade_id) in set(rbac_meta.get("grade_ids") or []):
        return True
    if homeroom_class_id and int(homeroom_class_id) in set(rbac_meta.get("homeroom_class_ids") or []):
        return True
    if homeroom_class_id and subject_id:
        pairs = {(int(c), int(s)) for c, s in rbac_meta.get("subject_class_pairs") or []}
        if (int(homeroom_class_id), int(subject_id)) in pairs:
            return True
    return False
```

b) Trong `get_class_grades`: resolve `class_name → grade_id` qua `dim_homeroom_class`; nếu user không full access và `grade_id` KHÔNG thuộc `grade_ids` (đồng thời không khớp `homeroom_class_ids`/`subject_class_pairs`) → trả `ACCESS_DENIED` trước khi chạy query điểm.

c) Trong `get_student_grades`: resolve `student_code → (grade_id, homeroom_class_id)` qua `dim_homeroom_class_student`; kiểm tra cùng quy tắc → trả `ACCESS_DENIED` nếu học sinh nằm ngoài phạm vi.

d) Trong `get_student_info`: cũng gate theo lớp/khối của học sinh tìm được (ngăn rò rỉ thông tin danh sách học sinh ngoài phạm vi).

**Tác động tới `node.py` Tầng 1** (dòng ~186): `template_result` bắt đầu bằng `ACCESS_DENIED` KHÔNG bắt đầu bằng `"Không tìm thấy"` → hiện đã trả về ngay cho Supervisor (không fallback Tầng 2). Xác nhận không cần đổi logic Tầng 1, chỉ cần đổi tools.

### 3.7. PHẢN BIỆN 2 — Đồng bộ tín hiệu ACCESS_DENIED cho stat_agent & report_agent (BẮT BUỘC)

**Hiện trạng**: [`calculate_grade_statistics()`](../src/agents/stat_agent/tools.py:18) và các tool stat khác đã áp `accessible_score_filter(session, user)` (RBAC public schema). Nhưng khi bị lọc rỗng chúng trả về thông báo **"không có dữ liệu"** chung → LLM hiểu nhầm là dữ liệu không tồn tại. report_agent dùng lại các tool stat + tool báo cáo riêng (ORM public schema).

**Giải pháp**:

a) `src/services/rbac.py`: thêm helper `scope_summary_for_user(user)` trả về chuỗi mô tả phạm vi (từ `accessible_class_ids`) để tool báo rõ.

b) `src/agents/stat_agent/tools.py`: trong các tool khi RBAC active (user không PRINCIPAL/ADMIN) và kết quả rỗng → trả về chuỗi chứa `ACCESS_DENIED` + phạm vi phân quyền thay vì "không có dữ liệu" (dùng helper `_rbac_denied` tương tự 3.6 — tách module để tránh import chéo).

c) Prompt [`STAT_AGENT_PROMPT`](../src/agents/stat_agent/node.py:19): thêm quy tắc — "Nếu kết quả công cụ chứa `ACCESS_DENIED` hoặc cụm 'phạm vi phân quyền' → DỪNG NGAY (FINISH), KHÔNG gọi thêm công cụ khác, phản hồi về giới hạn phân quyền."

d) Prompt [`REPORT_AGENT_PROMPT`](../src/agents/report_agent/node.py:16): sửa mục "Nếu hệ thống báo không có dữ liệu" (dòng ~39) — thêm: nếu tool trả `ACCESS_DENIED` → KHÔNG tạo báo cáo, KHÔNG đề nghị nhập liệu, phản hồi về phân quyền.

e) (Phòng thủ) thêm `config={"recursion_limit": 12}` vào [`stat_agent_node.ainvoke`](../src/agents/stat_agent/node.py:103) và [`report_agent_node.ainvoke`](../src/agents/report_agent/node.py:89).

### 3.8. PHẢN BIỆN 3 — Bổ sung testcase RBAC vào eval suite (BẮT BUỘC)

Hiện [`run_rbac_eval.py`](../eval/eval_text_to_sql/run_rbac_eval.py:1) chỉ map email cho `PRINCIPAL`/`HOMEROOM`/`SUBJECT`, KHÔNG có nhánh `GRADE_HEAD` → chưa cover kịch bản trưởng khối 6 hỏi khối 7 (đúng lỗi gốc đang sửa).

a) [`eval_dataset.json`](../eval/eval_text_to_sql/eval_dataset.json:1): thêm 2 case:

```json
{
  "id": "TC_026_RBAC_GRADE_HEAD_UNAUTHORIZED",
  "category": "RBAC_PERMISSIONS",
  "query": "Bảng điểm môn Toán lớp 7A1 năm học 2025-2026",
  "school_id": 1,
  "role": "GRADE_HEAD_PRIMARY",
  "expected_routing": "data_service_agent",
  "expected_rbac_blocked": true,
  "expected_no_sql_error": true
},
{
  "id": "TC_027_RBAC_GRADE_HEAD_AUTHORIZED",
  "category": "RBAC_PERMISSIONS",
  "query": "Bảng điểm môn Toán lớp 6A1 năm học 2025-2026",
  "school_id": 1,
  "role": "GRADE_HEAD_PRIMARY",
  "expected_routing": "data_service_agent",
  "expected_rbac_blocked": false,
  "expected_no_sql_error": true
}
```

b) [`run_rbac_eval.py`](../eval/eval_text_to_sql/run_rbac_eval.py:55): thêm nhánh `elif "GRADE_HEAD" in tc_id: email = "grade_head_6_cp@vinschool.edu.vn"` (email tồn tại trong mock [`phase_users`](../data_mock/mock_full_data/generate_full_system_mock_v2.py:290), phân công `grade_id=6`).

c) Bổ sung assert "không văng lỗi SQL": với case `expected_no_sql_error=true`, sau `validate_and_secure_sql` kiểm tra `secured_sql` KHÔNG chứa `fact_gradebooks.grade_id` mà phải chứa `homeroom_class_id IN (SELECT id FROM s360.dim_homeroom_class WHERE grade_id IN (6))` → đảm bảo inject đúng cột, không trả ERROR.

d) (Nâng cao, tùy chọn) chạy qua `execute_read_only_query` với ContextVars user grade-head → assert output chứa `ACCESS_DENIED`.

### 3.9. Ghi chú phụ (KHÔNG chặn tiến độ)

- `src/agents/old_sql_agent/tools.py` cũng gọi validator nhưng không truyền `user_id`/`user_role` (dòng 33) → không có RBAC. Đề xuất đồng bộ hoặc gỡ nếu agent cũ không còn dùng.

## 4. Kế hoạch kiểm thử

### 4.1. Tests mới — `tests/test_sql_validator_rbac.py`

Dùng `monkeypatch` để mock `get_user_assignment_constraints` trả về dict cố định (KHÔNG cần DB):

- `test_fact_gradebooks_grade_filter_via_homeroom_class`: user có `grade_ids=[6]`, query `SELECT * FROM s360.fact_gradebooks` → assert SQL chứa `homeroom_class_id IN (SELECT id FROM s360.dim_homeroom_class WHERE grade_id IN (6))` và KHÔNG chứa `fact_gradebooks.grade_id`.
- `test_fact_gradebooks_moet_direct_grade_filter`: query `fact_gradebooks_moet` → assert chứa `fact_gradebooks_moet.grade_id IN (6)`.
- `test_fact_so_assignment_grade_filters`: với `homeroom_class_ids`, `grade_ids`, `subject_class_pairs` → assert sinh điều kiện qua `dim_so_assignment`/`dim_homeroom_class_student`, không chứa `fact_so_assignment_grade.grade_id`/`.homeroom_class_id`/`.subject_id`.
- `test_no_assignments_raises_permission_denied`: `get_user_assignment_constraints` trả về 3 list rỗng → `pytest.raises(PermissionDeniedError)`.
- `test_full_access_no_rbac`: user ADMIN → không chèn thêm clause RBAC (giữ nguyên hành vi cũ).

### 4.2. Regression

- `pytest tests/test_sql_validator.py tests/test_sql_validator_complex.py tests/test_guardrails_new.py` — các test này gọi validator không có `user_id`/`user_role` → phải giữ nguyên pass.
- `pytest tests/test_rbac_classes.py` — logic `accessible_class_ids` không đổi.
- Chạy `ruff check src/core/security/sql_validator.py src/agents/data_service_agent/ src/agents/stat_agent/ src/agents/report_agent/ src/services/rbac.py` để không vi phạm lint.

### 4.3. Tests mới cho template tools RBAC (Phản biện 1) — `tests/test_agents/test_data_service_tools_rbac.py`

- `test_get_class_grades_out_of_scope_denied`: mock `get_user_assignment_constraints` trả `grade_ids=[6]`; gọi `get_class_grades(class_name="7A1")` → assert output chứa `ACCESS_DENIED`.
- `test_get_class_grades_in_scope_allowed`: `grade_ids=[6]`, class `"6A1"` → assert KHÔNG chứa `ACCESS_DENIED`.
- `test_get_student_grades_out_of_scope_denied` / `test_get_student_info_out_of_scope_denied`: tương tự theo `(grade_id, homeroom_class_id)` của học sinh.
- Lưu ý: tools đọc ContextVars `current_user_id`/`current_user_role` → test cần setup `contextvars` (dùng fixture tương tự `conftest` hiện có).

### 4.4. Eval suite RBAC (Phản biện 3)

- `python eval/eval_text_to_sql/run_rbac_eval.py` → kỳ vọng 7/7 RBAC cases pass (TC_021..TC_027), KHÔNG có dòng `[❌ ERROR]`.

## 5. Xác minh nghiệp vụ (manual smoke test)

Với tài khoản `grade_head_6_cp@vinschool.edu.vn` (trưởng khối 6, phân công `grade_id = 6`):
1. Hỏi agent: "Điểm Toán HK2 lớp 7A1" → kỳ vọng: agent trả lời **không có quyền truy cập khối 7** (KHÔNG còn lỗi SQL, KHÔNG còn "hệ thống không có khối 7", KHÔNG báo cáo đề nghị nhập liệu).
2. Hỏi agent: "Điểm Toán HK2 lớp 6A1" → kỳ vọng: trả về dữ liệu thật của khối 6 (không bị lỗi).
3. Quan sát log: không còn chuỗi `column "grade_id" does not exist`; số tool-call giảm mạnh (không còn "vài chục lần").
4. Hỏi qua template path: "Xem điểm của học sinh HS... thuộc khối 7" (kèm student_code khối 7) → kỳ vọng trả `ACCESS_DENIED`, KHÔNG rò rỉ điểm.
5. Hỏi Stat/Report: "Thống kê học lực khối 7" / "Lập báo cáo khối 7" → kỳ vọng agent dừng ngay, phản hồi giới hạn phân quyền, KHÔNG tạo báo cáo khối 7.

## 6. Tiêu chí hoàn thành

- [ ] Không còn lỗi `column grade_id does not exist` khi user có phân công khối.
- [ ] Agent dừng ngay và trả lời đúng nghiệp vụ phân quyền khi hỏi ngoài phạm vi (không retry "vài chục lần").
- [ ] Kết quả MOET/Vinschool trong phạm vi phân quyền trả về đúng dữ liệu.
- [ ] Template tools `get_student_grades` / `get_class_grades` / `get_student_info` không rò rỉ dữ liệu ngoài phạm vi (trả `ACCESS_DENIED`).
- [ ] stat_agent và report_agent dừng ngay (FINISH) khi nhận `ACCESS_DENIED`, không tạo báo cáo/đề nghị nhập liệu sai lệch.
- [ ] `run_rbac_eval.py` có testcase grade-head × khối 7 pass, KHÔNG có lỗi SQL (`expected_no_sql_error` đạt).
- [ ] Toàn bộ test mới + regression pass.
