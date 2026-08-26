# BÁO CÁO — RBAC & Authorization Flow

**Người viết**: [Tên] | **Ngày**: 26/08/2026

---

## 1. Giới thiệu

RBAC (Role-Based Access Control) là tầng bảo mật xuyên suốt toàn bộ hệ thống, ảnh hưởng đến mọi API endpoint. Hệ thống có **7 vai trò**, phân quyền theo 3 chiều:

1. **Vai trò** (role) — 7 loại, xác định quyền tổng quan
2. **Phân công giảng dạy** (teacher_assignments) — xác định scope chi tiết
3. **Tenant isolation** (school_id) — mỗi trường chỉ thấy dữ liệu của trường mình

---

## 2. Kiến trúc tổng quan

### 3 lớp bảo vệ

```
Lớp 1: JWT Auth
  ┌────────────────────────────────────────────┐
  │  POST /auth/login → verify email+password  │
  │  → access_token (30p) + refresh_token (7d) │
  │  → Mọi request sau: Bearer <access_token>  │
  └────────────────────────────────────────────┘
                      │
                      ▼
Lớp 2: Role Check
  ┌────────────────────────────────────────────┐
  │  get_current_user() → decode JWT → User    │
  │  require_roles(ADMIN, PRINCIPAL, ...)      │
  │  → 401 nếu token hết hạn                   │
  │  → 403 nếu role không đủ quyền             │
  └────────────────────────────────────────────┘
                      │
                      ▼
Lớp 3: RLS + Tenant
  ┌────────────────────────────────────────────┐
  │  accessible_score_filter() → WHERE clause  │
  │  tự động theo role + phân công + school_id │
  │  SQL guardrail: tự chèn school_id vào SELECT│
  │  ContextVar: set/reset cho mỗi request chat │
  └────────────────────────────────────────────┘
```

---

## 3. 7 Vai trò

| Role | Mô tả | Ghi điểm | Duyệt câu | Chat scope |
|------|-------|----------|-----------|------------|
| **ADMIN** | Quản trị hệ thống | Toàn quyền | Toàn quyền | Toàn trường |
| **PRINCIPAL** | Ban Giám Hiệu | Read-only | Không | Toàn trường |
| **GRADE_HEAD_PRIMARY** | Trưởng khối Cấp 1 | Read-only | Không | Trong khối |
| **HOMEROOM_TEACHER_PRIMARY** | GV chủ nhiệm Cấp 1 | Lớp mình, mọi môn | Không | Lớp CN |
| **HOMEROOM_TEACHER_SECONDARY** | GV chủ nhiệm Cấp 2/3 | Chỉ xem tổng hợp | Không | Lớp CN |
| **SUBJECT_TEACHER** | GV bộ môn | Môn/lớp được phân công | Không | Môn/lớp dạy |
| **SUBJECT_HEAD** | Trưởng bộ môn | Read-only môn phụ trách | Môn mình | Môn phụ trách |

---

## 4. Các thành phần chính

| File | Vai trò |
|------|---------|
| src/core/security.py | JWT: create_token, decode_token, ACCESS/REFRESH constants |
| src/api/deps.py | get_current_user, require_roles(), CurrentUser type alias |
| src/services/rbac.py | 8 hàm quyền: accessible_score_filter, accessible_class_ids, can_write_score, can_edit_subject_eval, can_edit_term_report, can_map, can_manage_question_bank, can_review_question |
| src/services/assignments.py | Phân công giảng dạy logic (1 chủ nhiệm/năm) |
| src/core/security/sql_validator.py | SQL guardrail + school_id injection |
| src/agents/context.py | ContextVar: current_user_school_id, role, user_id |
| src/models/enums.py | UserRole, RoleContext, ScoreCategory enums |
| src/models/tables.py | User, TeacherAssignment, Score, RefreshToken |
| src/api/v1/auth.py | POST /auth/login, /refresh, /logout, GET /auth/me |

---

## 5. Luồng hoạt động chi tiết

### Authentication

**Bước 1: Đăng nhập**
- User gửi email + password → POST /auth/login
- Backend verify bcrypt hash → nếu sai → 401
- Nếu đúng → tạo access_token (30 phút) + refresh_token (7 ngày)
- Lưu refresh_token_hash vào bảng refresh_tokens
- Trả {access_token, refresh_token, user_info}

**Bước 2: Mọi request sau**
- Frontend gắn Authorization: Bearer <access_token>
- get_current_user(): decode JWT → check type="access" → check user.active
- Nếu token hết hạn → 401 → FE redirect /login

**Bước 3: Refresh token**
- POST /auth/refresh với refresh_token
- Kiểm tra hash trong DB, check revoked
- Cấp access_token mới

### Authorization

**Bước 4: Role check**
- Endpoint gọi require_roles(ADMIN, PRINCIPAL)
- Nếu user.role không nằm trong danh sách → 403 Forbidden

**Bước 5: RLS — accessible_score_filter()**
- Nếu ADMIN/PRINCIPAL: chỉ WHERE school_id = user.school_id
- Nếu GRADE_HEAD: WHERE class_id IN (lớp trong khối)
- Nếu HOMEROOM: WHERE class_id = lớp CN
- Nếu SUBJECT_TEACHER: WHERE subject_id AND class_id
- Nếu SUBJECT_HEAD: WHERE subject_id (mọi lớp)
- Nếu không có phân công: WHERE 1=0 (false → không thấy gì)

### Phân công giảng dạy

**Bảng teacher_assignments:**
- HOMEROOM_PRIMARY: class_id (lớp CN) — ghi được điểm mọi môn
- HOMEROOM_SECONDARY: class_id (lớp CN) — chỉ xem tổng hợp, nhập hạnh kiểm
- SUBJECT_TEACHER: subject_id + class_id — dạy môn X ở lớp Y
- SUBJECT_HEAD: subject_id — trưởng bộ môn X
- GRADE_HEAD: grade_id — trưởng khối

**Quy tắc:**
- Mỗi GV chỉ chủ nhiệm 1 lớp/năm học
- Nhận chủ nhiệm → tự động dạy môn phụ trách cho lớp đó
- GV bộ môn có thể dạy nhiều lớp

### ContextVar tenant isolation (Chat)

```
Chat endpoint:
  Trước invoke: current_user_school_id.set(user.school_id)
                current_user_role.set(user.role)
                current_user_id.set(user.id)
  invoke agent graph
  Sau:         current_user_school_id.reset(token)
```

### SQL Guardrail (pandas_agent)

SQL thô qua validate_and_secure_sql():
- Chỉ cho SELECT
- 21 bảng whitelist
- Tự chèn school_id vào WHERE
- Nếu không parse được → reject + increment counter

---

## 6. Ma trận quyền chi tiết

| Tính năng | ADMIN | PRINCIPAL | GRADE_HEAD | HOMEROOM_PRIMARY | HOMEROOM_SECONDARY | SUBJECT_TEACHER | SUBJECT_HEAD |
|-----------|-------|-----------|------------|-----------------|-------------------|----------------|--------------|
| Điểm: Xem | Toàn trường | Toàn trường | Trong khối | Lớp CN | Lớp CN (tổng hợp) | Môn/lớp dạy | Môn phụ trách |
| Điểm: Ghi | Có | Không | Không | Lớp CN (mọi môn) | Không | Môn/lớp dạy | Không |
| Nhập Excel | Có | Không | Không | Lớp CN | Không | Môn/lớp dạy | Không |
| Nhận xét môn | Có | Không | Không | Lớp CN | Không | Môn/lớp dạy | Không |
| Hạnh kiểm | Có | Không | Không | Lớp CN | Lớp CN | Không | Không |
| Map đề TX | Có | Không | Không | Không | Không | Môn/lớp | Không |
| Map đề GK/CK | Có | Không | Không | Không | Không | Không | Môn |
| Tạo câu hỏi | Có | Không | Không | Không | Không | Môn/lớp | Môn |
| Duyệt câu | Có | Không | Không | Không | Không | Không | Môn |
| Chat AI | Trường | Trường | Khối | Lớp CN | Lớp CN | Môn/lớp | Môn |
| EWS: Chạy pipeline | Có | Có | Không | Không | Không | Không | Không |
| TEVI: Xem validity | Có | Có | Không | Không | Không | Không | Môn |
| TEVI: Student Fairness | Có | Có | Không | Không | Không | Không | Không |
| Upload SGK | Có | Không | Không | Không | Không | Không | Môn |
| Quản lý user | Có | Không | Không | Không | Không | Không | Không |

---

## 7. Kết quả đạt được

| Hạng mục | Trạng thái | Chi tiết |
|----------|-----------|----------|
| JWT access/refresh token | Hoạt động | 30p access + 7d refresh, lưu hash trong DB |
| 7 vai trò phân quyền | Hoạt động | Mọi endpoint đều có role check + RLS |
| accessible_score_filter | Hoạt động | WHERE clause động, tự sinh OR các điều kiện |
| accessible_class_ids | Hoạt động | FE dropdown chỉ hiển thị lớp user có quyền |
| can_write_score batch | Hoạt động | Hỗ trợ truyền sẵn assignments list chống N+1 |
| Phân công giảng dạy | Hoạt động | 5 role_context, 1 CN/năm, tự động gán môn |
| SQL guardrail | Hoạt động | SELECT-only, whitelist, chèn school_id |
| ContextVar tenant isolation | Hoạt động | set/reset cho mỗi request chat |

---

## 8. Cách kiểm tra

```bash
# 1. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@admin.edu.vn", "password": "admin123"}'

# 2. GET /auth/me
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"

# 3. Test 403: dùng token GV gọi endpoint admin
curl http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer <token_giao_vien>"
# → 403 Forbidden

# 4. Test 401: token hết hạn
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer token_het_han"
# → 401 Unauthorized

# 5. Test
pytest tests/test_rbac_classes.py tests/test_crud_router_tenant.py tests/test_sql_validator_rbac.py -v
```
