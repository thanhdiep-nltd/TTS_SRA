// Các kiểu dữ liệu dùng chung, khớp với backend (src/models/enums.py).

export type UserRole =
  | "ADMIN"
  | "PRINCIPAL"
  | "GRADE_HEAD_PRIMARY"
  | "HOMEROOM_TEACHER_PRIMARY"
  | "SUBJECT_TEACHER"
  | "HOMEROOM_TEACHER_SECONDARY"
  | "SUBJECT_HEAD";

export type ScoreCategory = "ORAL" | "REGULAR" | "MIDTERM" | "FINAL";
export const SCORE_CATEGORY_LABELS: Record<ScoreCategory, string> = {
  ORAL: "Miệng", REGULAR: "Thường xuyên", MIDTERM: "Giữa kỳ", FINAL: "Cuối kỳ",
};
export type ScoreStatus = "DRAFT" | "SUBMITTED" | "APPROVED";

// Cấu trúc cột điểm 1 học kỳ (Miệng×3, TX×4, GK×2, CK×1) — đồng bộ backend scoring.py
export const SCORE_COLUMNS: { category: ScoreCategory; index: number; label: string }[] = [
  { category: "ORAL", index: 1, label: "Miệng 1" },
  { category: "ORAL", index: 2, label: "Miệng 2" },
  { category: "ORAL", index: 3, label: "Miệng 3" },
  { category: "REGULAR", index: 1, label: "TX1" },
  { category: "REGULAR", index: 2, label: "TX2" },
  { category: "REGULAR", index: 3, label: "TX3" },
  { category: "REGULAR", index: 4, label: "TX4" },
  { category: "MIDTERM", index: 1, label: "GK1" },
  { category: "MIDTERM", index: 2, label: "GK2" },
  { category: "FINAL", index: 1, label: "Cuối kỳ" },
];

export type RoleContext =
  | "HOMEROOM_PRIMARY"
  | "HOMEROOM_SECONDARY"
  | "SUBJECT_TEACHER"
  | "GRADE_HEAD"
  | "SUBJECT_HEAD";

export interface AcademicYear {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
}

export interface User {
  id: string;
  school_id: string;
  school_name?: string;
  principal_name?: string;
  email: string;
  full_name: string;
  role: UserRole;
  school_level: string;
  phone: string | null;
  subject_id: string | null; // môn phụ trách (chuyên môn của GV)
  is_active: boolean;
  homeroom_class_id: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Grade {
  id: string;
  name: string;
  grade_number: number;
  school_level: string;
}

export interface ClassRow {
  id: string;
  grade_id: string;
  name: string;
  academic_year_id: string;
  student_count: number | null;
}

export type AssessmentType = "SCORED" | "REMARK";
export type PassFail = "DAT" | "CHUA_DAT";
export type Conduct = "TOT" | "KHA" | "TRUNG_BINH" | "YEU";

export interface Subject {
  id: string;
  name: string;
  code: string;
  applicable_level?: string;
  assessment_type?: AssessmentType;
}

export const PASS_FAIL_LABELS: Record<PassFail, string> = { DAT: "Đạt", CHUA_DAT: "Chưa đạt" };
export const CONDUCT_LABELS: Record<Conduct, string> = {
  TOT: "Tốt", KHA: "Khá", TRUNG_BINH: "Trung bình", YEU: "Yếu",
};
export const PASS_FAIL_OPTIONS = (Object.keys(PASS_FAIL_LABELS) as PassFail[]).map(
  (v) => ({ value: v, label: PASS_FAIL_LABELS[v] }));
export const CONDUCT_OPTIONS = (Object.keys(CONDUCT_LABELS) as Conduct[]).map(
  (v) => ({ value: v, label: CONDUCT_LABELS[v] }));

export interface Semester {
  id: string;
  academic_year_id: string;
  name: string;
  number: number;
  is_current: boolean;
}

export interface Student {
  id: string;
  student_code: string;
  full_name: string;
}

export interface Enrollment {
  id: string;
  student_id: string;
  class_id: string;
  academic_year_id: string;
  enrolled_at: string;
  is_active: boolean;
}

export interface Score {
  id: string;
  student_id: string;
  subject_id: string;
  class_id: string;
  semester_id: string;
  score_category: ScoreCategory;
  column_index: number;
  value: number;
  status: ScoreStatus;
  note: string | null;
  entered_by: string;
  approved_by: string | null;
  approved_at: string | null;
}

export interface DashboardOverview {
  total_students: number;
  total_classes: number;
  average_gpa: number | null;
  at_risk_classes: number;
  grade_distribution: { name: string; gioi: number; kha: number; trung_binh: number; yeu: number }[];
  gpa_trend: { name: string; gpa: number }[];
  grade_names: string[];
  grade_trend: { name: string; values: Record<string, number> }[];
}

// Quyền ghi điểm (đồng bộ với rbac.py): ADMIN + GV chủ nhiệm cấp 1 + GV bộ môn.
export const SCORE_WRITE_ROLES: UserRole[] = [
  "ADMIN",
  "HOMEROOM_TEACHER_PRIMARY",
  "SUBJECT_TEACHER",
];

export const APPROVE_ROLES: UserRole[] = ["ADMIN", "PRINCIPAL"];

export const ROLE_LABELS: Record<UserRole, string> = {
  ADMIN: "Quản trị viên",
  PRINCIPAL: "Ban Giám Hiệu",
  GRADE_HEAD_PRIMARY: "Trưởng khối (Cấp 1)",
  HOMEROOM_TEACHER_PRIMARY: "GV Chủ nhiệm (Cấp 1)",
  SUBJECT_TEACHER: "GV Bộ môn",
  HOMEROOM_TEACHER_SECONDARY: "GV Chủ nhiệm",
  SUBJECT_HEAD: "Trưởng bộ môn",
};

export const SCHOOL_LEVELS = [
  { value: "PRIMARY", label: "Tiểu học" },
  { value: "SECONDARY", label: "THCS" },
  { value: "HIGH", label: "THPT" },
  { value: "ALL", label: "Toàn cấp" },
];

export const ALL_ROLES: { value: UserRole; label: string }[] = (
  Object.keys(ROLE_LABELS) as UserRole[]
).map((r) => ({ value: r, label: ROLE_LABELS[r] }));

export const ROLE_CONTEXTS: { value: RoleContext; label: string }[] = [
  { value: "HOMEROOM_PRIMARY", label: "Chủ nhiệm (Cấp 1)" },
  { value: "HOMEROOM_SECONDARY", label: "Chủ nhiệm (Cấp 2/3)" },
  { value: "SUBJECT_TEACHER", label: "GV Bộ môn" },
  { value: "GRADE_HEAD", label: "Trưởng khối" },
  { value: "SUBJECT_HEAD", label: "Trưởng bộ môn" },
];

// ===== Tài khoản & phân công (redesign) =====
export interface UserListResponse {
  items: User[];
  total: number;
}

export interface AssignmentRow {
  id: string;
  user_id: string;
  academic_year_id: string;
  role_context: RoleContext;
  class_id: string | null;
  grade_id: string | null;
  subject_id: string | null;
  is_active: boolean;
}

export interface OptionItem {
  id: string;
  name: string;
  is_current?: boolean;
}

export interface ClassOption {
  id: string;
  name: string;
  academic_year_id: string;
}

export interface AssignmentOptions {
  allowed_contexts: RoleContext[];
  years: OptionItem[];
  classes: ClassOption[];
  grades: OptionItem[];
  subjects: OptionItem[];
}

export interface SubjectCoverage {
  subject_id: string;
  name: string;
  teacher_name: string | null;
}

export interface ClassCoverage {
  class_id: string;
  name: string;
  grade_name: string;
  homeroom_teacher: string | null;
  subjects: SubjectCoverage[];
}

export interface CoverageFilter {
  school_id: string;
  school_name: string;
  years: OptionItem[];
}

export interface TeacherOption {
  id: string;
  full_name: string;
  subject_id: string | null;
}

/** Field cần nhập cho từng loại phân công — khớp CONTEXT_FIELD_RULES backend. */
export const CONTEXT_FIELDS: Record<RoleContext, { class: boolean; grade: boolean; subject: boolean }> = {
  SUBJECT_TEACHER: { class: true, grade: false, subject: true },
  HOMEROOM_PRIMARY: { class: true, grade: false, subject: false },
  HOMEROOM_SECONDARY: { class: true, grade: false, subject: false },
  GRADE_HEAD: { class: false, grade: true, subject: false },
  SUBJECT_HEAD: { class: false, grade: false, subject: true },
};

// ===== Bảng điểm (gradebook) =====
export interface GradeCell {
  id: string | null;
  value: number | null;
}

export interface HocLucStat {
  label: string;
  count: number;
  ratio: number;
}

export interface GradebookRow {
  student_id: string;
  student_code: string;
  full_name: string;
  cells: Record<string, GradeCell>;
  dtb_hk: number | null;
  dtb_hk1: number | null;
  dtb_hk2: number | null;
  dtb_cn: number | null;
  hoc_luc: string | null;
  evaluation: string | null; // đánh giá học tập (nhận xét)
  result: PassFail | null;    // Đạt/CĐ cho môn REMARK
}

export interface GradebookColumn {
  key: string;
  category: ScoreCategory;
  index: number;
  label: string;
  mappable: boolean;
}

// ===== Đề thi & liên kết cột (exam mapping) =====
export type FileType = "PDF" | "WORD" | "IMAGE" | "OTHER";

export interface ExamPaper {
  id: string;
  subject_id: string;
  semester_id: string;
  grade_id: string | null;
  title: string;
  description: string | null;
  file_type: FileType | null;
  file_size_bytes: number | null;
  uploaded_by: string;
  created_at: string;
}

// Đề đã map vào một cột (để preview/đổi/gỡ) — khớp ExamRef backend.
export interface ExamRef {
  mapping_id: string;
  exam_paper_id: string;
  title: string;
  file_type: FileType | null;
  // Độ khó nội dung (CDI, TEVI) — LLM phân tích chạy nền, content_analyzed_at null = chưa xong.
  content_difficulty: number | null;
  content_analyzed_at: string | null;
}

export interface GradebookResponse {
  class_id: string;
  subject_id: string;
  semester_id: string;
  assessment_type: AssessmentType; // SCORED (điểm) hay REMARK (Đạt/CĐ)
  columns: GradebookColumn[];
  rows: GradebookRow[];
  mappings: Record<string, ExamRef>; // column_key -> đề đã map (nếu có)
  total_students: number;
  stats: HocLucStat[];
}

// Quyền map đề (đồng bộ rbac.can_map): GV bộ môn → TX (REGULAR); Trưởng bộ môn → GK/CK.
// Kiểm tra thô theo role để ẩn/hiện nút; backend vẫn chốt quyền theo phân công.
export function canMapCategory(role: UserRole, category: ScoreCategory): boolean {
  if (role === "ADMIN") return true;
  if (category === "REGULAR") return role === "SUBJECT_TEACHER";
  if (category === "MIDTERM" || category === "FINAL") return role === "SUBJECT_HEAD";
  return false; // ORAL không map
}

export interface SummaryRow {
  student_id: string;
  student_code: string;
  full_name: string;
  averages: Record<string, number | null>; // chỉ môn SCORED
  remarks: Record<string, string>;          // môn REMARK -> "DAT"/"CHUA_DAT"
  overall: number | null;
  hoc_luc: string | null;
  conduct: Conduct | null;       // hạnh kiểm
  general_comment: string | null; // đánh giá chung (chủ nhiệm)
  absent_days: number | null;     // số ngày nghỉ
}

export interface ClassSummaryResponse {
  class_id: string;
  semester_id: string;
  subjects: { id: string; name: string; code: string; assessment_type: AssessmentType }[];
  rows: SummaryRow[];
  total_students: number;
  stats: HocLucStat[];
  can_edit_report: boolean; // FE có cho sửa hạnh kiểm/đánh giá chung không
}

export interface SemesterOption {
  id: string;
  name: string;
  academic_year: string;
  is_current: boolean;
}

export interface SubjectOption {
  id: string;
  name: string;
  code: string;
}

export interface AcademicDivergenceRow {
  class_name: string;
  avg_subject_score: number;
  avg_gpao: number;
  delta_g: number;
}

export interface GradeInflationRow {
  class_name: string;
  gdi: number;
}

export interface LearningMomentumRow {
  class_name: string;
  positive_count: number;
  stable_count: number;
  negative_count: number;
}

export interface StudentArchetypeRow {
  class_name: string;
  consistent: number;
  procrastinator: number;
  high_effort: number;
  high_risk: number;
  others: number;
}

// ===== Dashboard v2 (BI 4 tab) =====
export interface ExecutiveKpi {
  avg_gpa: number | null;
  total_graded: number;
  gioi: number;
  kha: number;
  trung_binh: number;
  yeu: number;
  at_risk_count: number;
  conduct_good_ratio: number | null;
  attendance_available: boolean;
  promotion_available: boolean;
}

export interface LevelDistributionRow {
  level: string;
  gioi: number;
  kha: number;
  trung_binh: number;
  yeu: number;
}

export interface ClassRankRow {
  class_name: string;
  grade_name: string;
  gpa: number;
  student_count: number;
}

export interface ExecutiveSummary {
  semester_name: string;
  academic_year: string;
  kpi: ExecutiveKpi;
  level_distribution: LevelDistributionRow[];
  class_ranking: ClassRankRow[];
}

export interface SubjectMatrix {
  grades: string[];
  classes: string[];
  subjects: string[];
  grade_cells: Record<string, string | number>[]; // { subject, <khối>: avg }
  heatmap_cells: Record<string, string | number>[]; // { class_name, <môn>: avg }
  subject_ranking: ClassRankRow[];
}

export interface RiskStudent {
  student_code: string;
  full_name: string;
  class_name: string;
  gpa: number;
  conduct: Conduct | null;
  weakest_subject: string | null;
  weakest_score: number | null;
  risk_level: "Critical" | "High" | "Medium" | "Low";
}

export interface TalentStudent {
  student_code: string;
  full_name: string;
  class_name: string;
  gpa: number;
  best_subject: string | null;
  best_score: number | null;
}

export interface ScatterPoint {
  process_gpa: number;
  final_score: number;
  class_name: string;
  risk_level: "Critical" | "High" | "Medium" | "Low";
}

export interface RiskMatrixCell {
  level: "Low" | "Medium" | "High" | "Critical";
  count: number;
}

export interface WarningData {
  risk_students: RiskStudent[];
  talent_students: TalentStudent[];
  risk_matrix: RiskMatrixCell[];
  scatter: ScatterPoint[];
}

export interface YearGpaRow {
  academic_year: string;
  avg_gpa: number | null;
  student_count: number;
}

export interface YoYResponse {
  years: YearGpaRow[];
}

// ===== Tin cậy điểm số (TEVI — tam giác hóa độ khó đề thi) =====
export interface ExamValidityRow {
  exam_paper_id: string;
  subject_id: string;
  subject_name: string;
  semester_id: string;
  score_category: ScoreCategory;
  grade_id: string | null;
  grade_name: string;
  n: number;
  mean_score: number;
  edi: number;
  cdi: number | null;
  divergence: number | null;
  flag: string;
  confidence: "HIGH" | "LOW";
}

// ===== Phân tích nội dung đề (RAG-anchored CDI, ai_analysis.content_analysis v1) =====
export interface ExamEvidenceRef {
  score: number;
  heading: string | null;
  source_md: string | null;
}

export interface ExamAnalysisItem {
  topic: string;
  excerpt: string | null;
  unit_code: string | null;
  unit_name: string | null;
  matched_catalog: boolean;
  bloom_level: number;
  weight: number;
  evidence: ExamEvidenceRef | null;
  off_curriculum: boolean | null;
}

export interface ExamCoverageUnit {
  unit_code: string;
  unit_name: string;
  weight: number;
}

export interface ExamContentAnalysis {
  version: number;
  model: string | null;
  cdi: number;
  rag_available: boolean;
  items: ExamAnalysisItem[];
  coverage: { catalog_total: number; matched: number; ratio: number | null };
  coverage_units: ExamCoverageUnit[];
  concentration: {
    top_unit_code: string | null;
    top_unit_name: string | null;
    top_share: number | null;
    is_concentrated: boolean;
  };
  off_curriculum_weight: number | null;
}

export interface ExamPaperDetail extends ExamPaper {
  content_difficulty: number | null;
  content_analyzed_at: string | null;
  ai_analysis: { content_analysis?: ExamContentAnalysis;[k: string]: unknown };
}

export interface SchoolValidityOverview {
  total_checked: number;
  flags_count: Record<string, number>;
  flagged_items: ExamValidityRow[];
}

export interface ContentAdjustedRankRow {
  class_id: string;
  class_name: string;
  raw_average: number;
  content_adjusted_ability: number;
  cdi: number | null;
}

// Cảnh báo công bằng đánh giá cấp học sinh (TX vs GK/CK, neo theo CDI) — chỉ ADMIN/PRINCIPAL.
export interface StudentFairnessRow {
  student_id: string;
  student_code: string;
  full_name: string;
  class_id: string;
  class_name: string;
  subject_id: string;
  subject_name: string;
  semester_id: string;
  tx_avg: number | null;
  tx_cdi: number | null;
  periodic_avg: number | null;
  periodic_cdi: number | null;
  gap: number | null;
  flag: string;
  confidence: "HIGH" | "LOW";
  evidence: string;
}

// ===== Ngân hàng câu hỏi (AI Exam Generation) =====
export type QuestionType = "MCQ" | "TRUE_FALSE" | "SHORT_ANSWER" | "ESSAY";
export type ItemStatus = "DRAFT" | "REVIEW" | "APPROVED" | "REJECTED" | "RETIRED";
export type ItemSource = "AI_GENERATED" | "MANUAL" | "IMPORTED";

export const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  MCQ: "Trắc nghiệm",
  TRUE_FALSE: "Đúng/Sai",
  SHORT_ANSWER: "Trả lời ngắn",
  ESSAY: "Tự luận",
};

// Loại đề theo cơ cấu trắc nghiệm/tự luận — TN = MCQ+TRUE_FALSE+SHORT_ANSWER, TL = ESSAY.
export type ExamFormat = "MCQ_ONLY" | "ESSAY_ONLY" | "MIXED";

export const EXAM_FORMAT_LABELS: Record<ExamFormat, string> = {
  MCQ_ONLY: "100% Trắc nghiệm",
  ESSAY_ONLY: "100% Tự luận",
  MIXED: "Kết hợp (TN + TL)",
};

// Điểm/câu mặc định theo Bloom khi tự soạn ma trận thủ công (sửa tự do ở Step 2) — TN thấp
// hơn TL vì cùng 1 câu, viết tự luận đòi hỏi trình bày nhiều hơn chọn đáp án.
export const DEFAULT_POINTS_EACH: Record<"MCQ" | "ESSAY", Record<number, number>> = {
  MCQ: { 1: 0.25, 2: 0.25, 3: 0.5, 4: 0.5, 5: 0.75, 6: 0.75 },
  ESSAY: { 1: 0.5, 2: 0.5, 3: 1, 4: 1, 5: 1.5, 6: 2 },
};

export const ITEM_STATUS_LABELS: Record<ItemStatus, string> = {
  DRAFT: "Chờ duyệt",
  REVIEW: "Đang xem xét",
  APPROVED: "Đã duyệt",
  REJECTED: "Bị từ chối",
  RETIRED: "Đã ngừng dùng",
};

export const ITEM_STATUS_STYLE: Record<ItemStatus, string> = {
  DRAFT: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  REVIEW: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  APPROVED: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  REJECTED: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300",
  RETIRED: "bg-slate-200 text-slate-500 dark:bg-slate-800 dark:text-slate-500",
};

export const BLOOM_LABELS: Record<number, string> = {
  1: "1 - Nhớ", 2: "2 - Hiểu", 3: "3 - Vận dụng", 4: "4 - Phân tích", 5: "5 - Đánh giá", 6: "6 - Sáng tạo",
};
export const BLOOM_OPTIONS = Object.entries(BLOOM_LABELS).map(([v, label]) => ({ value: v, label }));

export interface QuestionOption {
  key: string;
  text: string;
  misconception?: string | null;
}

// Một đoạn SGK (RAG) đã dùng làm ngữ cảnh sinh câu — chi tiết hơn rag_sources (chỉ là chuỗi trích dẫn thô).
export interface RagHit {
  chuong?: string | null;
  heading?: string | null;
  source_md?: string | null;
  score?: number | null;
}

export interface QuestionProvenance {
  model?: string | null;
  rag_sources?: string[];
  rag_hits?: RagHit[];
  self_consistency?: "match" | "mismatch" | "unknown";
  bloom_check?: "match" | "mismatch" | "unknown";
  critic?: { score: number; issues: string[] } | null;
  duplicate_of?: string | null;
}

export interface QuestionItemRow {
  id: string;
  subject_id: string;
  grade_number: number;
  unit_id: string;
  bloom_level: number;
  question_type: QuestionType;
  stem: string;
  options: QuestionOption[] | null;
  solution: string | null;
  default_points: number;
  status: ItemStatus;
  source: ItemSource;
  times_used: number;
  p_value: number | null;
  exposure_at: string | null;
  created_at: string;
  created_by: string;
  created_by_name: string;
  reviewed_by: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  provenance: QuestionProvenance;
}

export interface QuestionItemDetailRow extends QuestionItemRow {
  answer_key: Record<string, unknown>;
}

export interface QuestionItemListPage {
  items: QuestionItemRow[];
  total: number;
}

export interface CurriculumUnitOption {
  id: string;
  name: string;
  code: string;
  grade_number: number;
  semester_number: number | null; // null = SGK không tách tập, chương dạy cả năm
  parent_id: string | null; // null = chương gốc; khác null = bài học con của 1 chương
}

// Hàng thống kê hiệu chỉnh (calibration) của 1 câu hỏi — p-value, độ phân biệt, đề xuất RETIRE/REVIEW.
export interface CalibrationRow {
  item_id: string;
  stem: string;
  bloom_level: number;
  status: ItemStatus;
  times_used: number;
  p_value: number | null;
  discrimination: number | null;
  flags: string[];
  recommendation: "RETIRE" | "REVIEW" | null;
}

// Quyền quản lý ngân hàng câu hỏi (đồng bộ rbac.can_manage_question_bank / can_review_question).
export const QUESTION_BANK_ROLES: UserRole[] = ["ADMIN", "SUBJECT_HEAD", "SUBJECT_TEACHER"];
export const QUESTION_REVIEW_ROLES: UserRole[] = ["ADMIN", "SUBJECT_HEAD"];

// ===== Tạo đề thi từ ngân hàng câu hỏi (Exam Builder — khớp src/schemas/exam_generation.py) =====

export interface BlueprintCell {
  unit_id: string;
  bloom_level: number;
  question_type: QuestionType;
  num_questions: number;
  points_each: number;
}

export interface BlueprintCreate {
  subject_id: string;
  grade_number: number;
  score_category: ScoreCategory; // chỉ MIDTERM/FINAL
  title: string;
  total_points: number;
  duration_min?: number | null;
  target_difficulty?: number | null;
  cells: BlueprintCell[];
}

export type BlueprintUpdate = Partial<BlueprintCreate>;

export interface BlueprintRead {
  id: string;
  subject_id: string;
  grade_number: number;
  score_category: ScoreCategory;
  title: string;
  total_points: number;
  duration_min: number | null;
  target_difficulty: number | null;
  cells: BlueprintCell[];
  exam_format: ExamFormat | null; // suy ra từ cells khi lưu, không tự khai được
  created_at: string;
}

export interface CoverageCellResult {
  unit_id: string;
  bloom_level: number;
  question_type: QuestionType;
  needed: number;
  available: number;
  shortfall: number;
}

export interface RecommendBlueprintRequest {
  subject_id: string;
  grade_number: number;
  grade_id: string;
  semester_id: string;
  score_category: ScoreCategory;
  unit_ids: string[];
  total_points: number;
  exam_format: ExamFormat;
  total_questions: number;
  mix_mcq_ratio?: number; // chỉ áp dụng khi exam_format=MIXED, mặc định 0.7
}

export interface RecommendCellDraft {
  unit_id: string;
  unit_name: string;
  bloom_level: number;
  question_type: QuestionType;
  num_questions: number;
  points_each: number;
  available: number;
  shortfall: number;
}

export interface BlueprintDraft {
  subject_id: string;
  grade_number: number;
  target_difficulty: number;
  ability_used: number;
  expected_cdi: number | null;
  cells: RecommendCellDraft[];
  rationale: string[];
}

export type GenExamStatus = "DRAFT" | "FINALIZED" | "PUBLISHED";
export const GEN_EXAM_STATUS_LABELS: Record<GenExamStatus, string> = {
  DRAFT: "Đã ráp (nháp)",
  FINALIZED: "Đã chốt",
  PUBLISHED: "Đã phát hành",
};

export interface AssembleRequest {
  blueprint_id: string;
  semester_id: string;
  grade_id: string;
  num_variants: number;
}

export interface AssembledItemRead {
  position: number;
  item_id: string;
  points: number;
  stem: string;
  question_type: QuestionType;
  options: QuestionOption[] | null;
}

export interface VariantRead {
  variant_code: string;
  items: AssembledItemRead[];
}

export interface GeneratedExamRead {
  id: string;
  blueprint_id: string;
  semester_id: string;
  grade_id: string | null;
  num_variants: number;
  status: GenExamStatus;
  exam_paper_id: string | null;
  created_at: string;
}

export interface GeneratedExamDetail extends GeneratedExamRead {
  variants: VariantRead[];
}

export interface AnswerKeyItemRead {
  position: number;
  item_id: string;
  points: number;
  answer_key: Record<string, unknown>;
  solution: string | null;
}

export interface VariantAnswerRead {
  variant_code: string;
  items: AnswerKeyItemRead[];
}

// ===== Thông báo =====
export type NotificationType = "QUESTION_SUBMITTED" | "ITEM_REVIEWED" | "EXAM_FINALIZED" | "ANNOUNCEMENT";
export type AnnouncementScope = "SCHOOL" | "SUBJECT" | "INDIVIDUAL";

export interface NotificationItem {
  id: string;
  sender_id: string | null;
  sender_name: string | null;
  type: NotificationType;
  title: string;
  message: string;
  entity_type: string | null;
  entity_id: string | null;
  read_at: string | null;
  created_at: string;
}

export interface RecipientOption {
  id: string;
  full_name: string;
}

export interface ObservabilityAlertItem {
  type: string;
  message: string;
  sent_at: string;
}

// Tên node khớp `agent_node_names`/`TOOL_AGENT_MAP` (src/observability.py) và các node đăng ký
// trong build_graph (src/agents/graph.py) — dùng chung cho /admin/ai-metrics và /dashboard/agents.
export const AGENT_LABEL: Record<string, string> = {
  supervisor: "Supervisor",
  data_agent: "Data Agent",
  stat_agent: "Stat Agent",
  sql_agent: "SQL Agent",
  knowledge_agent: "Knowledge Agent",
  report_agent: "Report Agent",
};

export const AGENT_ROLE_DESCRIPTION: Record<string, string> = {
  supervisor: "Điều phối & Routing",
  data_agent: "Tra cứu hồ sơ/bảng điểm (ORM)",
  stat_agent: "Thống kê & chỉ số học vụ",
  sql_agent: "Truy vấn SQL thô có guardrail",
  knowledge_agent: "Tra cứu tri thức (RAG)",
  report_agent: "Tổng hợp báo cáo",
};

// Khớp ObservabilitySummaryResponse (src/models/schemas.py) — dùng chung cho trang
// /admin/ai-metrics (bảng chi tiết) và /dashboard/agents (sơ đồ Multi-Agent).
export interface ObservabilitySummaryResponse {
  daily_cost_usd: number;
  daily_budget_usd: number;
  latency_p95_ms: number | null;
  ttft_p95_ms: number | null;
  faithfulness_avg: number | null;
  groundedness_avg: number | null;
  tool_success_rate: number | null;
  recent_alerts: ObservabilityAlertItem[];
  agent_routes: Record<string, number>;
  agent_step_p95_ms: Record<string, number | null>;
  sql_guardrail_rejections_total: number;
}

// Quyền soạn thông báo chủ động (đồng bộ notifications._BROADCAST_ROLES).
export const ANNOUNCEMENT_ROLES: UserRole[] = ["ADMIN", "PRINCIPAL", "SUBJECT_HEAD"];
export const SCHOOL_WIDE_ANNOUNCEMENT_ROLES: UserRole[] = ["ADMIN", "PRINCIPAL"];

// ============================================================================
// EWS DASHBOARD TYPES & CONSTANTS
// ============================================================================

export type EwsRiskLevel = "LOW" | "MODERATE" | "HIGH" | "CRITICAL";

export const EWS_RISK_ORDER: EwsRiskLevel[] = ["LOW", "MODERATE", "HIGH", "CRITICAL"];

export const EWS_RISK_LABELS: Record<EwsRiskLevel, string> = {
  LOW: "Thấp",
  MODERATE: "Trung bình",
  HIGH: "Cao",
  CRITICAL: "Nghiêm trọng",
};

export const EWS_RISK_COLORS: Record<EwsRiskLevel, string> = {
  LOW: "#10b981",
  MODERATE: "#f59e0b",
  HIGH: "#f97316",
  CRITICAL: "#ef4444",
};

// Top 5 nhân tố tác động AI (CatBoost SHAP) — Signed SHAP, giữ dấu âm/dương.
export interface ShapDriver {
  rank: number;
  feature: string;
  shap_value: number; // > 0 = tăng rủi ro, < 0 = giảm rủi ro
  value?: any; // giá trị feature thực tế của học sinh
}

export interface EwsPredictionRow {
  student_code: string;
  student_name: string | null;
  class_name: string | null;
  grade_name: string | null;
  grade_level: number | null;
  subject_id: number;
  subject_name: string | null;
  subject_code: string | null;
  subject_category: string | null;
  evaluated_at_week: number;
  risk_score: number;
  risk_level: EwsRiskLevel;
  risk_probability: number | null;
  risk_factors: string[];
  primary_badge: string[];
  risk_factor_details: string[];
  shap_drivers?: ShapDriver[];
  evaluated_at_date: string | null;
  cutoff_date: string | null;
  join_date: string | null;
  model_version: string | null;

  // Sub-scores & trọng số (chỉ có ở v2_ensemble)
  score_risk: number | null;
  lms_risk: number | null;
  attendance_risk: number | null;
  behavior_risk: number | null;
  weight_score: number | null;
  weight_lms: number | null;
  weight_attendance: number | null;
  weight_behavior: number | null;

  // 1. Temporal Scores (9)
  weighted_early_avg: number | null;
  weighted_late_avg: number | null;
  weighted_late_avg_imputed: boolean;
  score_slope: number | null;
  score_volatility: number | null;
  max_drop: number | null;
  last_score: number | null;
  max_coefficient_so_far: number | null;
  high_weight_score_count: number | null;
  last_high_weight_score: number | null;

  // 2. LMS (5)
  lms_avg_score: number | null;
  lms_recent_drop: number | null;
  lms_submission_rate: number | null;
  lms_recent_submission_rate: number | null;
  lms_gradebook_gap: number | null;

  // 3. Attendance (4)
  daily_absence_rate: number | null;
  unexcused_absent_rate: number | null;
  excused_absent_days: number | null;
  total_late_count: number | null;

  // 4. Behavior (3)
  total_demerit_points: number | null;
  repeat_offense_count: number | null;
  severe_sanction_count: number | null;
}

export interface EwsLevelCount {
  level: EwsRiskLevel;
  count: number;
}

export interface EwsOverview {
  school_year_id: number;
  semester_index: number;
  evaluated_at_week: number;
  total_predictions: number;
  total_students: number;
  at_risk_count: number;
  avg_risk_score: number | null;
  levels: EwsLevelCount[];
  top_risk_subjects: Array<{
    subject_name: string;
    cnt: number;
    avg_risk: number;
    low_cnt: number;
    moderate_cnt: number;
    high_cnt: number;
    critical_cnt: number;
    low_pct: number;
    moderate_pct: number;
    high_pct: number;
    critical_pct: number;
    ch_pct: number;
  }>;
  top_risk_factors: Array<{ code: string; label: string; cnt: number }>;
}

export interface EwsGoldenSetCase {
  id: string;
  description: string;
  predicted: EwsRiskLevel;
  expected: EwsRiskLevel;
  passed: boolean;
  risk_score: number;
  score_risk: number | null;
  lms_risk: number | null;
  attendance_risk: number | null;
  behavior_risk: number | null;
  weight_attendance: number | null;
  weight_behavior: number | null;
  features: Record<string, number | string | null>;
}

export interface EwsGoldenSetResult {
  total: number;
  passed: number;
  accuracy: number;
  cases: EwsGoldenSetCase[];
}

export interface EwsWeekOption {
  school_year_id: number;
  semester_index: number;
  evaluated_at_week: number;
  school_year_name: string | null;
}

export interface EwsClassOption {
  grade_id: number | null;
  grade_name: string | null;
  class_name: string;
}

export interface EwsRiskFactorOption {
  code: string;
  label: string;
}

export interface EwsMeta {
  weeks: EwsWeekOption[];
  subjects: Array<{ id: number; name: string; code: string; subject_category: string | null }>;
  grades: Array<{ grade_id: number; grade_name: string }>;
  classes: EwsClassOption[];
  risk_factors: EwsRiskFactorOption[];
}

export interface EwsPagedResult {
  items: EwsPredictionRow[];
  total: number;
  limit: number;
  offset: number;
}

// ==== Dữ liệu Gốc (Raw) — đối chiếu dự báo EWS (M2-F2) ====
export interface EwsRawScore {
  exam_name: string | null;
  exam_code: string | null;
  coefficient: number | null;
  final_grade: number | null;
  max_grade: number | null;
  created_at: string | null;
  source: string; // QUOC_TE | BO_GD
}

export interface EwsRawLmsItem {
  code: string | null;
  fullname: string | null;
  max_grade: number | null;
  due_date: string | null;
  submitted: boolean;
  final_grade: number | null;
}

export interface EwsRawAttendanceItem {
  date: string;
  total_periods: number;
  absent_periods: number;
  absent_no_permission: number;
  absent_with_permission: number;
  status: string; // CÓ MẶT | VẮNG | VẮNG KHÔNG PHÉP | NGHỈ CÓ PHÉP
}

export interface EwsRawBehaviorItem {
  comment_date: string | null;
  behavior_fullname: string | null;
  behavior_point: number | null;
  sanction_name: string | null;
}

export interface EwsRawDetail {
  student_code: string;
  subject_id: number;
  school_year_id: number;
  semester_index: number;
  cutoff_date: string | null;
  join_date: string | null;
  scores: EwsRawScore[];
  lms: EwsRawLmsItem[];
  lms_expected: number;
  lms_submitted: number;
  attendance: EwsRawAttendanceItem[];
  behavior: EwsRawBehaviorItem[];
}

export interface EwsRiskBreakdownItem {
  id?: string | number | null;
  name: string;
  total_cnt: number;
  low_cnt: number;
  moderate_cnt: number;
  high_cnt: number;
  critical_cnt: number;
  low_pct: number;
  moderate_pct: number;
  high_pct: number;
  critical_pct: number;
  ch_pct: number;
}

export interface EwsStudentRiskDetailItem {
  student_code: string;
  student_name: string;
  week_label: string;
  risk_level: EwsRiskLevel;
  risk_score: number;
}

export interface EwsSubjectDrilldownResponse {
  level: "group" | "subject" | "class" | "student";
  breadcrumb: string[];
  items: EwsRiskBreakdownItem[];
  student_items: EwsStudentRiskDetailItem[];
  summary?: EwsRiskBreakdownItem | null;
}

export interface EwsTopClassRiskItem {
  rank: number;
  class_name: string;
  total_cnt: number;
  low_cnt: number;
  moderate_cnt: number;
  high_cnt: number;
  critical_cnt: number;
  low_pct: number;
  moderate_pct: number;
  high_pct: number;
  critical_pct: number;
  ch_pct: number;
}

// ============================================================================
// EWS CONTROL PANEL (BGH) — dự đoán theo tuần + tinh chỉnh trọng số
// ============================================================================

export interface EwsPredictRequest {
  school_year_id: number;
  semester_index: number;
  evaluated_at_week: number;
  model_version: string;
}

export interface EwsJob {
  id: number;
  so_school_id: number;
  requested_by: number;
  school_year_id: number;
  semester_index: number;
  evaluated_at_week: number;
  cutoff_date: string | null;
  model_version: string;
  status: "pending" | "processing" | "completed" | "failed" | "cancelled";
  progress: number;
  rows_processed: number | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface EwsWeightConfig {
  weight_score?: number | null;
  weight_lms?: number | null;
  weight_attendance?: number | null;
  weight_behavior?: number | null;
  alpha_score?: number | null;
  alpha_lms?: number | null;
  alpha_attendance?: number | null;
  alpha_behavior?: number | null;
  weight_floor?: number | null;
  worst_factor_beta?: number | null;
  threshold_low?: number | null;
  threshold_moderate?: number | null;
  threshold_high?: number | null;
  threshold_critical?: number | null;
}

export interface EwsEffectiveConfig {
  baseline: {
    weights: Record<string, number>;
    alpha: Record<string, number>;
    weight_floor: number;
    worst_factor_beta: number;
    thresholds: Record<string, number>;
  };
  override: EwsWeightConfig | null;
  effective: {
    weights: Record<string, number>;
    alpha: Record<string, number>;
    weight_floor: number;
    worst_factor_beta: number;
    thresholds: Record<string, number>;
  };
}

export interface EwsValidWeeks {
  semester_1: number[];
  semester_2: number[];
}

