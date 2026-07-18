import enum


class SchoolLevel(enum.StrEnum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    HIGH = "HIGH"
    ALL = "ALL"


class RecordingRank(enum.StrEnum):
    EXCELLENT = "EXCELLENT"
    SATISFACTORY = "SATISFACTORY"
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"


class UserRole(enum.StrEnum):
    ADMIN = "ADMIN"
    PRINCIPAL = "PRINCIPAL"
    GRADE_HEAD_PRIMARY = "GRADE_HEAD_PRIMARY"
    HOMEROOM_TEACHER_PRIMARY = "HOMEROOM_TEACHER_PRIMARY"
    SUBJECT_TEACHER = "SUBJECT_TEACHER"
    HOMEROOM_TEACHER_SECONDARY = "HOMEROOM_TEACHER_SECONDARY"
    SUBJECT_HEAD = "SUBJECT_HEAD"


class RoleContext(enum.StrEnum):
    HOMEROOM_PRIMARY = "HOMEROOM_PRIMARY"
    HOMEROOM_SECONDARY = "HOMEROOM_SECONDARY"
    SUBJECT_TEACHER = "SUBJECT_TEACHER"
    GRADE_HEAD = "GRADE_HEAD"
    SUBJECT_HEAD = "SUBJECT_HEAD"


class ScoreType(enum.StrEnum):
    """(Legacy) dùng cho exam_papers.score_type. scores đã chuyển sang ScoreCategory + column_index."""

    TX1 = "TX1"
    TX2 = "TX2"
    TX3 = "TX3"
    TX4 = "TX4"
    GK = "GK"
    CK = "CK"


class ScoreCategory(enum.StrEnum):
    """Nhóm đầu điểm; số cột mỗi nhóm do column_index quyết định (Miệng×3, TX×4, GK×2, CK×1)."""

    ORAL = "ORAL"  # Kiểm tra miệng — hệ số 1
    REGULAR = "REGULAR"  # Kiểm tra thường xuyên — hệ số 1
    MIDTERM = "MIDTERM"  # Giữa kỳ — hệ số 2
    FINAL = "FINAL"  # Cuối kỳ — hệ số 3


class ScoreStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"


class AssessmentType(enum.StrEnum):
    """Cách đánh giá môn: SCORED = cho điểm 0–10 (tính ĐTB); REMARK = Đạt/Chưa đạt (không tính ĐTB)."""

    SCORED = "SCORED"
    REMARK = "REMARK"


class PassFail(enum.StrEnum):
    """Kết quả môn đánh giá bằng nhận xét."""

    DAT = "DAT"  # Đạt
    CHUA_DAT = "CHUA_DAT"  # Chưa đạt


class Conduct(enum.StrEnum):
    """Hạnh kiểm (do GV chủ nhiệm đánh giá)."""

    TOT = "TOT"  # Tốt
    KHA = "KHA"  # Khá
    TRUNG_BINH = "TRUNG_BINH"  # Trung bình
    YEU = "YEU"  # Yếu


class FileType(enum.StrEnum):
    PDF = "PDF"
    WORD = "WORD"
    IMAGE = "IMAGE"
    OTHER = "OTHER"


class Difficulty(enum.StrEnum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class AiSessionRole(enum.StrEnum):
    user = "user"
    assistant = "assistant"
    system = "system"


class GuardrailStatus(enum.StrEnum):
    PASSED = "PASSED"
    BLOCKED_INJECTION = "BLOCKED_INJECTION"
    BLOCKED_SQL = "BLOCKED_SQL"
    BLOCKED_PII = "BLOCKED_PII"
    BLOCKED_SENSITIVE = "BLOCKED_SENSITIVE"


class QuestionType(enum.StrEnum):
    """Loại câu hỏi trong ngân hàng đề."""

    MCQ = "MCQ"  # trắc nghiệm nhiều lựa chọn
    TRUE_FALSE = "TRUE_FALSE"  # đúng/sai
    SHORT_ANSWER = "SHORT_ANSWER"  # trả lời ngắn
    ESSAY = "ESSAY"  # tự luận (chấm theo rubric)


class ExamFormat(enum.StrEnum):
    """Cơ cấu trắc nghiệm/tự luận của đề. TN = MCQ+TRUE_FALSE+SHORT_ANSWER, TL = ESSAY
    (khớp cấu trúc đề thi THPT 2025/CT GDPT 2018). Tham số đầu vào cho gợi ý ma trận
    (RecommendBlueprintRequest); trên ExamBlueprint đây là giá trị SUY RA từ cells, không
    phải input client ghi trực tiếp — xem blueprint_recommendation.derive_exam_format."""

    MCQ_ONLY = "MCQ_ONLY"  # 100% trắc nghiệm
    ESSAY_ONLY = "ESSAY_ONLY"  # 100% tự luận
    MIXED = "MIXED"  # kết hợp, tỉ lệ theo điểm (mặc định 70% TN / 30% TL)


class ItemStatus(enum.StrEnum):
    """Vòng đời câu hỏi; CHỈ APPROVED mới được ráp vào đề chính thức."""

    DRAFT = "DRAFT"  # vừa tạo (LLM/thủ công), chưa kiểm
    REVIEW = "REVIEW"  # đang chờ duyệt
    APPROVED = "APPROVED"  # đã duyệt, dùng được
    REJECTED = "REJECTED"  # bị loại
    RETIRED = "RETIRED"  # ngừng dùng (cũ/lộ/sai sót phát hiện sau)


class ItemSource(enum.StrEnum):
    """Nguồn gốc câu hỏi (để truy vết)."""

    AI_GENERATED = "AI_GENERATED"
    MANUAL = "MANUAL"
    IMPORTED = "IMPORTED"


class GenExamStatus(enum.StrEnum):
    """Trạng thái một lần ráp đề."""

    DRAFT = "DRAFT"  # đã ráp, chưa chốt
    FINALIZED = "FINALIZED"  # đã chốt + sinh exam_papers/exam_competencies
    PUBLISHED = "PUBLISHED"  # đã phát hành cho kỳ thi


class NotificationType(enum.StrEnum):
    """Loại thông báo — phân biệt sự kiện hệ thống tự động vs thông báo do người soạn."""

    QUESTION_SUBMITTED = "QUESTION_SUBMITTED"  # có câu hỏi mới chờ duyệt
    ITEM_REVIEWED = "ITEM_REVIEWED"  # câu hỏi đã được duyệt/từ chối
    EXAM_FINALIZED = "EXAM_FINALIZED"  # đề đã được chốt chính thức
    ANNOUNCEMENT = "ANNOUNCEMENT"  # thông báo do BGH/Trưởng bộ môn soạn gửi
    GENERATION_FAILED = "GENERATION_FAILED"  # sinh câu AI ở nền thất bại (RAG thiếu/ lỗi LLM)


class AnnouncementScope(enum.StrEnum):
    """Phạm vi gửi thông báo chủ động (compose)."""

    SCHOOL = "SCHOOL"  # toàn trường — chỉ ADMIN/PRINCIPAL
    SUBJECT = "SUBJECT"  # toàn thành viên 1 bộ môn — BGH (chọn môn) hoặc Trưởng BM (môn mình)
    INDIVIDUAL = "INDIVIDUAL"  # 1 cá nhân cụ thể
