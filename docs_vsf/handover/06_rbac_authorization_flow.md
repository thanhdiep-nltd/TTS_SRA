# RBAC & Authorization Flow

- **Mục đích**: Phân quyền 7 vai trò, Row-Level Security cho điểm số, JWT auth (access/refresh token), phân công giảng dạy, tenant isolation (school_id). Flow này cắt ngang (cross-cutting) toàn bộ hệ thống.
- **Phân hệ**: Core / Security
- **Trạng thái**: ✅ Đang hoạt động

---

## 1. Sơ đồ luồng

```mermaid
graph TD
    subgraph "Authentication"
        A[User FE: /login] -->|POST /auth/login| B[auth.py: login]
        B -->|Verify email+password<br/>bcrypt| C[(users)]
        C -->|Tạo JWT<br/>access + refresh| D[core/security.py]
        D -->|Trả token| A
        A -->|Gắn Bearer header| E[Mọi request sau]
    end

    subgraph "Authorization"
        E -->|Authorization: Bearer <access_token>| F[deps.py: get_current_user]
        F -->|Giải mã JWT<br/>Kiểm tra type=access| G{User.active?}
        G -->|Yes → CurrentUser| H[Endpoint handler]
        G -->|No → 401| I[Unauthorized]
        H -->|require_roles(...)| J{User.role in roles?}
        J -->|No → 403| K[Forbidden]
        J -->|Yes → tiếp tục| L
    end

    subgraph "Row-Level Security (RLS)"
        L -->|Endpoint need scores| M[rbac.py: accessible_score_filter]
        M -->|Nếu ADMIN/PRINCIPAL| N[school_filter: chỉ cùng school_id]
        M -->|Nếu khác| O[OR: các lớp + môn<br/>trong phân công]
        O -->|Chủ nhiệm| P[class_id = lớp CN]
        O -->|GV bộ môn| Q[subject_id + class_id]
        O -->|Trưởng bộ môn| R[subject_id mọi lớp]
        O -->|Trưởng khối| S[grade_id mọi lớp trong khối]
        N & O --> T[(scores filtered)]
    end

    subgraph "Agent Isolation"
        U[Chat endpoint] -->|set ContextVar| V[context.py]
        V -->|current_user_school_id| W[Agent tool ORM]
        V -->|current_user_role| X[Tool tự lọc]
        V -->|current_user_id| Y[Tool phân quyền]
    end
```

---

## 2. 7 Vai trò (UserRole)

| Role | Enum value | Mô tả | Ghi điểm | Duyệt câu | Chat scope |
|------|-----------|-------|----------|-----------|------------|
| **ADMIN** | `ADMIN` | Quản trị hệ thống | ✅ Toàn quyền | ✅ | Toàn trường |
| **PRINCIPAL** | `PRINCIPAL` | Ban Giám Hiệu | ❌ Read-only | ❌ | Toàn trường read-only |
| **GRADE_HEAD_PRIMARY** | `GRADE_HEAD_PRIMARY` | Trưởng khối Cấp 1 | ❌ Read-only | ❌ | Trong khối |
| **HOMEROOM_TEACHER_PRIMARY** | `HOMEROOM_TEACHER_PRIMARY` | GV chủ nhiệm Cấp 1 | ✅ Lớp mình, mọi môn | ❌ | Lớp CN |
| **HOMEROOM_TEACHER_SECONDARY** | `HOMEROOM_TEACHER_SECONDARY` | GV chủ nhiệm Cấp 2/3 | ❌ Chỉ xem tổng hợp | ❌ | Lớp CN |
| **SUBJECT_TEACHER** | `SUBJECT_TEACHER` | GV bộ môn | ✅ Môn/lớp được phân công | ❌ | Môn/lớp dạy |
| **SUBJECT_HEAD** | `SUBJECT_HEAD` | Trưởng bộ môn | ❌ Read-only môn phụ trách | ✅ | Môn phụ trách mọi lớp |

---

## 3. Các hàm quyền chi tiết (src/services/rbac.py)

| Hàm | Mô tả | Cho ai? | Gọi ở đâu? |
|-----|-------|---------|------------|
| `accessible_score_filter()` | WHERE clause SQL giới hạn điểm user được xem | Mọi role trừ ADMIN/PRINCIPAL | `scores.py`, `gradebook.py` |
| `accessible_class_ids()` | Danh sách class_id user được phép (None=không giới hạn) | Mọi role | `gradebook.py`, FE dropdown |
| `can_write_score()` | Được nhập/sửa điểm? | ADMIN, HOMEROOM_PRIMARY, SUBJECT_TEACHER | `scores.py`, `score_import.py` |
| `can_edit_subject_eval()` | Được nhập nhận xét/Đạt-CĐ? | Giống `can_write_score` | `gradebook.py` |
| `can_edit_term_report()` | Được nhập hạnh kiểm + đánh giá chung? | ADMIN, HOMEROOM (cả primary & secondary) | `gradebook.py` |
| `can_map()` | Được map đề vào cột điểm? | GV bộ môn → TX (lớp), Trưởng BM → GK/CK (khối) | `mappings.py` |
| `can_manage_question_bank()` | Tạo/sửa câu hỏi, ráp đề? | ADMIN + GV bộ môn/Trưởng BM của môn đó | `question_bank.py`, `exams.py` |
| `can_review_question()` | DUYỆT câu, CHỐT đề? | ADMIN + Trưởng bộ môn 🡺 SUBJECT_HEAD | `question_bank.py`, `exams.py` |

---

## 4. JWT Auth Flow

```
Access Token:
  - type: "access"
  - sub: user_id (int)
  - exp: 30 phút (mặc định)
  - school_id, role (trong payload)

Refresh Token:
  - type: "refresh"
  - sub: user_id
  - exp: 7 ngày
  - Lưu ở bảng refresh_tokens (để revoke)

Endpoints:
  POST /auth/login       → trả {access_token, refresh_token}
  POST /auth/refresh     → cấp access_token mới từ refresh_token
  POST /auth/logout      → revoke refresh_token
  GET  /auth/me          → thông tin user hiện tại (dùng FE check role)
```

File: `src/core/security.py` — `create_token()`, `decode_token()` với `JWT_SECRET_KEY`.

---

## 5. Phân công giảng dạy (TeacherAssignment)

Mỗi user (GV) có thể có nhiều phân công, xác định bởi bảng `teacher_assignments`:

| `role_context` | `subject_id` | `class_id` | `grade_id` | Ý nghĩa |
|---------------|-------------|--------|---------|---------|
| `HOMEROOM_PRIMARY` | NULL | class_id | NULL | GV chủ nhiệm Cấp 1 của lớp |
| `HOMEROOM_SECONDARY` | NULL | class_id | NULL | GV chủ nhiệm Cấp 2/3 của lớp |
| `SUBJECT_TEACHER` | subject_id | class_id | NULL | Dạy môn X ở lớp Y |
| `SUBJECT_HEAD` | subject_id | NULL | NULL | Trưởng bộ môn X |
| `GRADE_HEAD` | NULL | NULL | grade_id | Trưởng khối |

**Quy tắc nghiệp vụ** (`src/services/assignments.py`):
- Mỗi GV chỉ chủ nhiệm 1 lớp/năm học
- Nhận chủ nhiệm → tự động dạy môn phụ trách cho lớp đó
- GV bộ môn có thể dạy nhiều lớp (phân công riêng từng lớp)
- `is_active` flag để bật/tắt mà không xóa

```python
# Ví dụ kiểm tra quyền ghi điểm:
can_write_score(db, user, subject_id, class_id)
# → ADMIN luôn true
# → HOMEROOM_PRIMARY nếu class_id khớp lớp CN (mọi môn)
# → SUBJECT_TEACHER nếu subject_id + class_id khớp phân công
```

---

## 6. Tenant Isolation (school_id)

Chiến lược 2 lớp:

### Lớp 1 — API endpoint
Mọi CRUD endpoint tự lọc `school_id` từ `CurrentUser`:
```python
# Ví dụ trong CRUD router factory (crud_router.py):
query = query.filter(Model.school_id == user.school_id)
```

### Lớp 2 — Agent ContextVar
Chat/supervisor agent dùng ContextVar:
```python
# src/agents/context.py
from contextvars import ContextVar
current_user_school_id: ContextVar[int] = ContextVar("school_id")
current_user_role: ContextVar[str] = ContextVar("role")
current_user_id: ContextVar[str] = ContextVar("user_id")
```

Set ở `chat.py` trước khi invoke agent, reset ở `finally`:
```python
token = current_user_school_id.set(user.school_id)
try:
    result = await agent.ainvoke(...)
finally:
    current_user_school_id.reset(token)
```

### Lớp 3 — SQL Guardrail (pandas_agent)
SQL thô qua `validate_and_secure_sql` tự chèn điều kiện `school_id`:
```sql
-- Input:  SELECT * FROM scores WHERE subject_id = 1
-- Output: SELECT * FROM scores WHERE subject_id = 1 AND school_id = :school_id
```

---

## 7. File map

```
📁 src/core/
├── security.py                       # JWT (create_token, decode_token, ACCESS/REFRESH constants)

📁 src/api/
├── deps.py                           # get_current_user, require_roles(), CurrentUser type alias

📁 src/services/
├── rbac.py                           # Core RBAC: accessible_score_filter, can_write_score, can_edit_subject_eval, can_edit_term_report, can_map, can_manage_question_bank, can_review_question, accessible_class_ids, scope_summary_for_user, rbac_denied_message
├── assignments.py                    # Phân công giảng dạy logic (1 chủ nhiệm/năm)

📁 src/core/security/
├── sql_validator.py                  # SQL guardrail + school_id injection + get_user_assignment_constraints

📁 src/agents/
├── context.py                        # ContextVar: current_user_school_id, current_user_role, current_user_id

📁 src/models/
├── enums.py                          # UserRole, RoleContext, ScoreCategory, ScoreStatus...
├── tables.py                         # User, TeacherAssignment, Score, RefreshToken

📁 src/api/v1/
├── auth.py                           # POST /auth/login, /refresh, /logout, GET /auth/me
```

---

## 8. Database tables liên quan

| Bảng | Cột quan trọng | Vai trò |
|------|----------------|---------|
| `users` | id, email, hashed_password, role, so_school_id, subject_id, is_active, teacher_code | Tài khoản + role |
| `refresh_tokens` | id, user_id, token_hash, expires_at, revoked | Refresh token store |
| `teacher_assignments` | user_id, role_context, subject_id, class_id, grade_id, school_year_id, is_active | Phân công giảng dạy |
| `scores` | student_id, subject_id, class_id, semester_id, score_category, value, status, entered_by | Bảng điểm có RLS theo school_id qua class |

---

## 9. Lưu ý kỹ thuật (Gotchas)

1. **⚠️ JWT secret production**: BẮT BUỘC đặt `JWT_SECRET_KEY` ≥ 32 byte trong `.env`. Default chỉ dùng cho dev. Mỗi lần đổi → tất cả token cũ expire.

2. **⚠️ Refresh token trong DB**: Refresh token lưu hash trong `refresh_tokens` để có thể revoke. Logout gọi `DELETE /auth/logout` → xóa token khỏi DB.

3. **⚠️ `accessible_score_filter` so với `accessible_class_ids`**: Filter dùng cho SQL (WHERE), class_ids dùng cho FE dropdown. Cả hai đều query `_active_assignments()`.

4. **⚠️ HOMEROOM_TEACHER_SECONDARY (cấp 2/3)**: Không được ghi điểm (chỉ xem tổng hợp). Chỉ được nhập hạnh kiểm + đánh giá chung qua `can_edit_term_report`.

5. **⚠️ ContextVar trong agent**: Phải set trước mỗi lần invoke agent graph và reset trong `finally`. Quên reset → agent sau dùng sai tenant.

6. **⚠️ SQL guardrail tenant injection**: Dùng `sqlglot` parse AST → tìm table → chèn `so_school_id` vào WHERE. Chỉ cho `SELECT`. Whitelist 21 bảng. Nếu không parse được → reject với `sql_guardrail_rejections_total` counter.

7. **⚠️ Test cần mock LLM**: `tests/conftest.py` fixture `mock_llm` để test RBAC offline, không gọi OpenAI thật.

---

## 10. Cách kiểm tra

```bash
# 1. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@admin.edu.vn", "password": "admin123"}'
# → {access_token, refresh_token, user_info}

# 2. GET /auth/me
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
# → {id, email, role, so_school_id, full_name, ...}

# 3. Test RBAC: thử endpoint không có quyền
curl http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer <token_giao_vien>"
# → 403 Forbidden: "Bạn không có quyền thực hiện thao tác này"

# 4. Test token hết hạn → 401

# 5. Test
pytest tests/test_rbac_classes.py tests/test_crud_router_tenant.py tests/test_sql_validator_rbac.py -v
```