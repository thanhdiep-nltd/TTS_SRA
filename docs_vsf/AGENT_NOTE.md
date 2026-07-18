# HƯỚNG DẪN CẤU TRÚC TÀI LIỆU (AGENT_NOTE.md)

Thư mục `docs_vsf` chứa toàn bộ tài liệu đặc tả, kế hoạch và sơ đồ cơ sở dữ liệu cho dự án **VSF Student Risk Alert (VSF SRA)** mới.

### 1. Phân chia thư mục chính:
- [docs_vsf/specs/](file:///f:/PROJECT_VSF/VSF_SRA/docs_vsf/specs/): Thư mục chứa các tài liệu đặc tả mô tả về dự án.
  - [PRD.md](file:///f:/PROJECT_VSF/VSF_SRA/docs_vsf/specs/PRD.md): Tài liệu yêu cầu sản phẩm (Product Requirements Document).
  - [mini_srs.md](file:///f:/PROJECT_VSF/VSF_SRA/docs_vsf/specs/mini_srs.md): Đặc tả yêu cầu phần mềm rút gọn (mini-SRS).
  - [sprint_plan.md](file:///f:/PROJECT_VSF/VSF_SRA/docs_vsf/specs/sprint_plan.md): Lộ trình phát triển chi tiết trong 7 tuần.
  - [school_online_schema_analysis.md](file:///f:/PROJECT_VSF/VSF_SRA/docs_vsf/specs/school_online_schema_analysis.md): Phân tích sự khác biệt giữa hai schema cũ.
- [docs_vsf/schemas/](file:///f:/PROJECT_VSF/VSF_SRA/docs_vsf/schemas/): Thư mục quản lý các file thiết kế cơ sở dữ liệu.
  - [schemas/old/schema.sql](file:///f:/PROJECT_VSF/VSF_SRA/docs_vsf/schemas/old/schema.sql): File thiết kế cơ sở dữ liệu **cũ** cho dự án cũ.
  - [schemas/new/school_online_schema.sql](file:///f:/PROJECT_VSF/VSF_SRA/docs_vsf/schemas/new/school_online_schema.sql): File cấu trúc dữ liệu **mới**, dữ liệu này chưa được tích hợp vào hệ thống nó đang dùng ở product khác.
  - [schemas/new/School Online Schema.csv](file:///f:/PROJECT_VSF/VSF_SRA/docs_vsf/schemas/new/School%20Online%20Schema.csv): File CSV mô tả cấu trúc dữ liệu thực tế đang áp dụng của hệ thống mới.

### 2. Các thư mục mã nguồn:
- `src/`: Mã nguồn phần BACKEND (FastAPI + LangGraph + PostgreSQL/Alembic + Qdrant DB).
- `frontend/`: Mã nguồn phần FRONTEND (React).

