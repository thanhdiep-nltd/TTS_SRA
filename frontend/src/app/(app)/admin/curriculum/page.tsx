"use client";

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Brain,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Database,
  Eraser,
  FileUp,
  Folder,
  FolderTree,
  ListOrdered,
  Loader2,
  Lock,
  RefreshCw,
  Sparkles,
  Trash2,
  Unlock,
  UploadCloud,
  X,
} from "lucide-react";
import SearchableSelect from "@/components/SearchableSelect";
import { api } from "@/lib/api";

interface CurriculumSection {
  name: string;
}

interface CurriculumUnitRow {
  id: number;
  code: string;
  name: string;
  grade_number: number;
  semester_number: number | null;
  parent_id: number | null;
  parent_name: string | null;
  is_active: boolean;
  is_phu: boolean;
  description: string | null;
  // Làm giàu nội dung khi nạp sách (quét toàn cuốn): tóm tắt, từ khóa, mục con.
  summary: string | null;
  keywords: string[] | null;
  sections: CurriculumSection[] | null;
  book_id: number | null;
  book_title: string | null;
}

interface CurriculumBookRow {
  id: number;
  title: string;
  subject_code: string;
  subject_id: number;
  grade_number: number;
  semester_number: number | null;
  volume?: string | null;
  school_year_id: number | null;
  school_year_name?: string | null;
  is_locked?: boolean;
  filename: string | null;
  unit_count: number;
  chunk_count: number;
  created_at: string | null;
}

interface SchoolYear {
  id: number;
  code: string;
  fullname: string;
  is_current: boolean;
  is_locked: boolean;
}

interface TeachingScheduleRow {
  id: number;
  school_year_id: number;
  subject_id: number;
  grade_number: number;
  semester_number: number;
  week_number: number;
  unit_id: number | null;
  unit_code: string | null;
  unit_name: string | null;
  topic: string | null;
  num_periods: number;
  notes: string | null;
}

interface UploadResult {
  subject_code: string;
  source: string;
  grades: number[];
  inserted: number;
  updated: number;
  hidden_placeholders: number;
}
interface IngestedLesson {
  code: string;
  name: string;
  is_phu: boolean;
  summary?: string | null;
  keywords?: string[] | null;
  sections?: CurriculumSection[] | null;
}

interface IngestedChapter {
  code: string;
  name: string;
  semester_number: number | null;
  is_phu: boolean;
  summary?: string | null;
  keywords?: string[] | null;
  sections?: CurriculumSection[] | null;
  lessons: IngestedLesson[];
}

interface BookIngestResult {
  subject_code: string;
  grade: number;
  semester: number | null;
  source: string;
  chapters: IngestedChapter[];
  inserted: number;
  updated: number;
  hidden_placeholders: number;
  warnings: string[];
  dry_run: boolean;
}

interface BookIngestJob {
  job_id: number;
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  subject_code: string;
  grade_number: number;
  semester_number: number | null;
  filename: string | null;
  book_title: string | null;
  vlm_model?: string | null;
  result: BookIngestResult | null;
  error: string | null;
  created_at: string | null;
}

const INGEST_STATUS_META: Record<string, { label: string; cls: string }> = {
  pending: { label: "Chờ xử lý", cls: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300" },
  processing: {
    label: "Đang trích xuất",
    cls: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  },
  completed: { label: "Hoàn tất", cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300" },
  failed: { label: "Thất bại", cls: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300" },
};

// Fallback nếu chưa gọi được /curriculum/subjects — ĐẦY ĐỦ 24 môn theo SUBJECTS_23 mock v4
const FALLBACK_SUBJECT_OPTIONS = [
  { value: "TOAN_6", label: "Toán 6 (TOAN_6)" },
  { value: "TOAN_7", label: "Toán 7 (TOAN_7)" },
  { value: "TOAN_8", label: "Toán 8 (TOAN_8)" },
  { value: "TOAN_9", label: "Toán 9 (TOAN_9)" },
  { value: "TOAN_10", label: "Toán 10 (TOAN_10)" },
  { value: "TOAN_11", label: "Toán 11 (TOAN_11)" },
  { value: "VAN", label: "Ngữ văn (VAN)" },
  { value: "ANH", label: "Tiếng Anh (ANH)" },
  { value: "LY", label: "Vật lý (LY)" },
  { value: "HOA", label: "Hóa học (HOA)" },
  { value: "SINH", label: "Sinh học (SINH)" },
  { value: "KHTN", label: "Khoa học tự nhiên (KHTN)" },
  { value: "LS_DL", label: "Lịch sử & Địa lý (LS_DL)" },
  { value: "CAM_ENG", label: "Tiếng Anh Cambridge (CAM_ENG)" },
  { value: "CAM_MATH", label: "Toán Cambridge (CAM_MATH)" },
  { value: "IB_MATH", label: "Toán IB (IB_MATH)" },
  { value: "IB_SCI", label: "Khoa học IB (IB_SCI)" },
  { value: "TIN", label: "Tin học (TIN)" },
  { value: "ROBOTICS", label: "STEM Robotics (ROBOTICS)" },
  { value: "GPA_HONOR", label: "Môn Chuyên Honor (GPA_HONOR)" },
  { value: "THE_DUC", label: "Giáo dục thể chất (THE_DUC)" },
  { value: "MY_THUAT", label: "Mỹ thuật (MY_THUAT)" },
  { value: "AM_NHAC", label: "Âm nhạc (AM_NHAC)" },
  { value: "GDCD", label: "Giáo dục công dân (GDCD)" },
];

/** Card vuông 1 cuốn sách: ảnh bìa (trang đầu PDF) + tên + môn/khối + số node + Năm học & Khóa. */
function BookCard({
  book,
  onOpen,
  onDelete,
  onToggleLock,
  togglingLockId,
}: {
  book: CurriculumBookRow;
  onOpen: (b: CurriculumBookRow) => void;
  onDelete: (b: CurriculumBookRow) => void;
  onToggleLock: (b: CurriculumBookRow) => void;
  togglingLockId: number | null;
}) {
  const [coverUrl, setCoverUrl] = useState<string | null>(null);

  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    api
      .blob(`/curriculum/books/${book.id}/cover`)
      .then((blob) => {
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setCoverUrl(url);
      })
      .catch(() => {
        /* chưa có file gốc → placeholder */
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [book.id]);

  return (
    <div className="relative group flex flex-col rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm hover:shadow-md hover:border-brand-300 dark:hover:border-brand-700 transition-all text-left">
      {/* Nút Khóa / Mở khóa cuốn sách */}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onToggleLock(book);
        }}
        disabled={togglingLockId === book.id}
        className={`absolute top-2 right-10 z-10 p-1.5 rounded-full shadow-xs border transition-all ${
          book.is_locked
            ? "bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700"
            : "bg-white/90 dark:bg-slate-900/90 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 border-slate-200 dark:border-slate-700"
        } opacity-80 hover:opacity-100 hover:scale-105`}
        title={book.is_locked ? "Sách đang KHÓA (Click để mở khóa)" : "Sách đang MỞ (Click để khóa bảo vệ dữ liệu)"}
      >
        {togglingLockId === book.id ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : book.is_locked ? (
          <Lock className="w-3.5 h-3.5" />
        ) : (
          <Unlock className="w-3.5 h-3.5" />
        )}
      </button>

      {/* Nút Xóa cuốn sách (vô hiệu hóa nếu sách bị khóa) */}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          if (book.is_locked) {
            alert("Cuốn sách này đã bị KHÓA. Hãy mở khóa sách trước khi xóa.");
            return;
          }
          onDelete(book);
        }}
        className={`absolute top-2 right-2 z-10 p-1.5 rounded-full shadow-xs border transition-all ${
          book.is_locked
            ? "bg-slate-100 dark:bg-slate-800 text-slate-300 dark:text-slate-600 border-slate-200 dark:border-slate-700 cursor-not-allowed"
            : "bg-white/90 dark:bg-slate-900/90 text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/60 border-slate-200 dark:border-slate-700 opacity-70 hover:opacity-100 hover:scale-105"
        }`}
        title={book.is_locked ? "Không thể xóa cuốn sách đang bị khóa" : `Xóa cuốn "${book.title}" và toàn bộ node`}
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>

      <button
        type="button"
        onClick={() => onOpen(book)}
        className="flex flex-col flex-1 text-left"
        title={`Xem node của "${book.title}"`}
      >
        {/* Ảnh bìa — vuông, hiển thị trang đầu PDF */}
        <div className="relative aspect-[3/4] w-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
          {coverUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={coverUrl}
              alt={`Bìa ${book.title}`}
              className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform"
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-slate-300 dark:text-slate-600">
              <BookOpen className="w-10 h-10" />
              <span className="text-[10px] font-medium px-2 text-center">{book.subject_code}</span>
            </div>
          )}
          <span className="absolute top-2 left-2 inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold bg-white/90 dark:bg-slate-900/80 text-brand-700 dark:text-brand-300 border border-slate-200 dark:border-slate-700">
            Khối {book.grade_number}
            {book.semester_number ? ` · HK${book.semester_number}` : ""}
          </span>
          {book.is_locked && (
            <span className="absolute bottom-2 left-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500 text-white shadow-xs">
              <Lock className="w-2.5 h-2.5" /> Đã khóa
            </span>
          )}
        </div>
        {/* Thông tin */}
        <div className="p-3 space-y-1 flex-1 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-1.5 flex-wrap mb-1">
              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
                {book.school_year_name || "Năm 2024-2025"}
              </span>
              {book.volume && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                  {book.volume}
                </span>
              )}
            </div>
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 line-clamp-2 leading-snug">
              {book.title}
            </p>
            <p className="text-[11px] text-slate-400 flex items-center gap-1.5 flex-wrap">
              <span>{book.subject_code} · {book.unit_count} node</span>
              <span className={`px-1.5 py-0.2 rounded text-[10px] font-semibold ${
                book.chunk_count > 0
                  ? "bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800"
                  : "bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-800"
              }`}>
                {book.chunk_count > 0 ? `🧠 ${book.chunk_count} chunks` : "⚠️ Chưa index"}
              </span>
            </p>
          </div>
          <span className="inline-flex mt-2 px-2 py-1 rounded-lg text-[11px] font-semibold bg-brand-50 dark:bg-brand-950/50 text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-900 group-hover:bg-brand-100 dark:group-hover:bg-brand-900/40 transition-colors self-start">
            Xem node →
          </span>
        </div>
      </button>
    </div>
  );
}

export default function AdminCurriculumPage() {
  const [subjectCode, setSubjectCode] = useState("TOAN_6");
  const [grade, setGrade] = useState("");
  const [semester, setSemester] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [subjectOptions, setSubjectOptions] = useState(FALLBACK_SUBJECT_OPTIONS);

  // Danh mục năm học
  const [schoolYears, setSchoolYears] = useState<SchoolYear[]>([]);
  const [selectedSchoolYearId, setSelectedSchoolYearId] = useState<number | null>(2025);
  const [bookSchoolYearId, setBookSchoolYearId] = useState<string>("2025");
  const [togglingLockId, setTogglingLockId] = useState<number | null>(null);

  // Phân phối chương trình (Teaching Schedules)
  const [teachingSchedules, setTeachingSchedules] = useState<TeachingScheduleRow[]>([]);
  const [teachingSchedulesLoading, setTeachingSchedulesLoading] = useState(false);

  // Main Dashboard Tab: "catalog" = Thư viện Sách & Cây Mục Lục, "ingest" = Nạp Sách Mới, "schedule" = Phân phối 35 tuần
  const [mainTab, setMainTab] = useState<"catalog" | "ingest" | "schedule">("catalog");

  // Chế độ xem bên trong catalog: "books" = danh sách sách; "nodes" = node của 1 cuốn đang chọn
  const [view, setView] = useState<"books" | "nodes">("books");
  const [activeBook, setActiveBook] = useState<CurriculumBookRow | null>(null);
  const [books, setBooks] = useState<CurriculumBookRow[]>([]);
  const [booksLoading, setBooksLoading] = useState(false);

  const [units, setUnits] = useState<CurriculumUnitRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [uploadErr, setUploadErr] = useState<string | null>(null);

  const [bookFile, setBookFile] = useState<File | null>(null);
  const [bookGrade, setBookGrade] = useState("6");
  const [bookVolume, setBookVolume] = useState("Tập 1");
  const [bookSemester, setBookSemester] = useState("1"); // Tự động đồng bộ theo Tập sách
  const [bookTitle, setBookTitle] = useState(""); // Tên cuốn / Chương - Tập - Mô tả
  const [includeLessons, setIncludeLessons] = useState(true);
  // Làm giàu nội dung khi nạp PDF: quét toàn cuốn + VLM tạo tóm tắt/từ khóa/mục con cho từng bài.
  const [enrichContent, setEnrichContent] = useState(true);
  const [overwriteEnrichment, setOverwriteEnrichment] = useState(true);
  const [selectedVlmModel, setSelectedVlmModel] = useState("google/gemini-3.7-flash");
  const [customVlmModel, setCustomVlmModel] = useState("");
  const [bookUploading, setBookUploading] = useState(false);
  const [bookMsg, setBookMsg] = useState<string | null>(null);
  const [bookErr, setBookErr] = useState<string | null>(null);

  // Hàng chi tiết (tóm tắt/từ khóa/mục con) đang mở rộng trong view node — null = không mở.
  const [expandedUnitId, setExpandedUnitId] = useState<number | null>(null);

  // Node đang xem chi tiết trong modal — null = đóng.
  const [detailUnit, setDetailUnit] = useState<CurriculumUnitRow | null>(null);

  // Làm giàu lại từ file PDF gốc đã lưu (job nền) — theo dõi ở Lịch sử nạp sách.
  const [reEnriching, setReEnriching] = useState(false);
  const [clearingEnrichment, setClearingEnrichment] = useState(false);
  const [reEnrichMsg, setReEnrichMsg] = useState<string | null>(null);
  const [reEnrichErr, setReEnrichErr] = useState<string | null>(null);

  // Cắt và index chunks RAG trực tiếp (không quét lại mục lục)
  const [reIndexingChunks, setReIndexingChunks] = useState(false);
  const [reIndexMsg, setReIndexMsg] = useState<string | null>(null);
  const [reIndexErr, setReIndexErr] = useState<string | null>(null);
  const [bookToIndexChunks, setBookToIndexChunks] = useState<CurriculumBookRow | null>(null);
  const [chunkModalVlmModel, setChunkModalVlmModel] = useState<string>("google/gemini-3.7-flash");
  const [chunkModalCustomModel, setChunkModalCustomModel] = useState<string>("");

  // Lịch sử nạp sách (job queue, poll như EWS)
  const [ingestJobs, setIngestJobs] = useState<BookIngestJob[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);

  // Xóa cuốn sách
  const [bookToDelete, setBookToDelete] = useState<CurriculumBookRow | null>(null);
  const [deletingBook, setDeletingBook] = useState(false);
  const [deleteErr, setDeleteErr] = useState<string | null>(null);
  const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);

  // Xem chi tiết cảnh báo của Job
  const [selectedJobWarnings, setSelectedJobWarnings] = useState<{
    jobId: number;
    filename: string;
    warnings: string[];
  } | null>(null);
  const [warningSearch, setWarningSearch] = useState("");
  const [copiedWarningIdx, setCopiedWarningIdx] = useState<number | null>(null);

  // Tải danh mục năm học từ backend
  const fetchSchoolYears = useCallback(async () => {
    try {
      const res = await api.get<SchoolYear[]>("/curriculum/school-years");
      if (res && res.length > 0) {
        setSchoolYears(res);
        const current = res.find((y) => y.is_current) || res[0];
        if (current && !selectedSchoolYearId) {
          setSelectedSchoolYearId(current.id);
          setBookSchoolYearId(String(current.id));
        }
      }
    } catch {
      // fallback
    }
  }, [selectedSchoolYearId]);

  useEffect(() => {
    fetchSchoolYears();
  }, [fetchSchoolYears]);

  // Khóa / Mở khóa cuốn sách
  const handleToggleLock = useCallback(
    async (book: CurriculumBookRow) => {
      setTogglingLockId(book.id);
      try {
        const res = await api.post<{ book_id: number; is_locked: boolean; message: string }>(
          `/curriculum/books/${book.id}/toggle-lock`
        );
        setBooks((prev) =>
          prev.map((b) => (b.id === book.id ? { ...b, is_locked: res.is_locked } : b))
        );
        if (activeBook && activeBook.id === book.id) {
          setActiveBook((prev) => (prev ? { ...prev, is_locked: res.is_locked } : null));
        }
      } catch (e: any) {
        alert(e?.message ?? "Không thể thay đổi trạng thái khóa sách.");
      } finally {
        setTogglingLockId(null);
      }
    },
    [activeBook]
  );

  // Tải phân phối chương trình 35 tuần
  const fetchTeachingSchedules = useCallback(async () => {
    setTeachingSchedulesLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedSchoolYearId) params.set("school_year_id", String(selectedSchoolYearId));
      if (subjectCode) params.set("subject_code", subjectCode);
      if (grade) params.set("grade", grade);
      if (semester) params.set("semester", semester);
      const rows = await api.get<TeachingScheduleRow[]>(`/curriculum/teaching-schedules?${params.toString()}`);
      setTeachingSchedules(rows || []);
    } catch {
      setTeachingSchedules([]);
    } finally {
      setTeachingSchedulesLoading(false);
    }
  }, [selectedSchoolYearId, subjectCode, grade, semester]);

  useEffect(() => {
    if (mainTab === "schedule") {
      fetchTeachingSchedules();
    }
  }, [mainTab, fetchTeachingSchedules]);

  const fetchUnits = useCallback(
    async (bookId?: number) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ subject_code: subjectCode });
        if (grade) params.set("grade", grade);
        if (semester) params.set("semester", semester);
        if (includeInactive) params.set("include_inactive", "true");
        if (bookId != null) params.set("book_id", String(bookId));
        const rows = await api.get<CurriculumUnitRow[]>(`/curriculum/units?${params.toString()}`);
        setUnits(rows || []);
      } catch (e: any) {
        setError(e?.message ?? "Không tải được danh sách chương trình.");
        setUnits([]);
      } finally {
        setLoading(false);
      }
    },
    [subjectCode, grade, semester, includeInactive]
  );

  // Quản lý thu gọn/mở rộng các chương cha trong chế độ xem phân cấp
  const [collapsedParents, setCollapsedParents] = useState<Set<number>>(new Set());

  const toggleParentCollapse = useCallback((parentId: number) => {
    setCollapsedParents((prev) => {
      const next = new Set(prev);
      if (next.has(parentId)) {
        next.delete(parentId);
      } else {
        next.add(parentId);
      }
      return next;
    });
  }, []);

  // Xây dựng danh sách phân cấp động (Tree View): sắp xếp tự nhiên mã node, gom con theo parent_id
  const hierarchicalUnits = useMemo(() => {
    const naturalCompare = (a: CurriculumUnitRow, b: CurriculumUnitRow) => {
      return a.code.localeCompare(b.code, undefined, { numeric: true, sensitivity: "base" });
    };

    const sorted = [...units].sort(naturalCompare);
    const byId = new Map<number, CurriculumUnitRow>();
    const childrenMap = new Map<number, CurriculumUnitRow[]>();

    for (const u of sorted) {
      byId.set(u.id, u);
    }

    for (const u of sorted) {
      if (u.parent_id && byId.has(u.parent_id)) {
        if (!childrenMap.has(u.parent_id)) childrenMap.set(u.parent_id, []);
        childrenMap.get(u.parent_id)!.push(u);
      }
    }

    // Các node gốc: không có parent_id hoặc parent_id không nằm trong danh sách hiện tại
    const roots = sorted.filter((u) => !u.parent_id || !byId.has(u.parent_id));

    interface FlatTreeNode {
      unit: CurriculumUnitRow;
      isParent: boolean;
      level: number;
      childCount: number;
      hiddenByCollapse: boolean;
    }

    const result: FlatTreeNode[] = [];

    const traverse = (list: CurriculumUnitRow[], level: number, parentCollapsed: boolean) => {
      for (const u of list) {
        const children = childrenMap.get(u.id) || [];
        const isParent = children.length > 0;
        const isCollapsed = collapsedParents.has(u.id);

        result.push({
          unit: u,
          isParent,
          level,
          childCount: children.length,
          hiddenByCollapse: parentCollapsed,
        });

        if (isParent) {
          traverse(children, level + 1, parentCollapsed || isCollapsed);
        }
      }
    };

    traverse(roots, 0, false);
    return result;
  }, [units, collapsedParents]);

  // Tải danh sách sách (view "books") — lọc theo môn/khối/năm học
  const fetchBooks = useCallback(async () => {
    setBooksLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (subjectCode) params.set("subject_code", subjectCode);
      if (grade) params.set("grade", grade);
      if (selectedSchoolYearId) params.set("school_year_id", String(selectedSchoolYearId));
      const rows = await api.get<CurriculumBookRow[]>(`/curriculum/books?${params.toString()}`);
      setBooks(rows || []);
    } catch (e: any) {
      setError(e?.message ?? "Không tải được danh sách sách.");
      setBooks([]);
    } finally {
      setBooksLoading(false);
    }
  }, [subjectCode, grade, selectedSchoolYearId]);

  // Bấm vào 1 cuốn → chuyển sang xem node của đúng cuốn đó
  const openBook = useCallback(
    (book: CurriculumBookRow) => {
      setActiveBook(book);
      setView("nodes");
      fetchUnits(book.id);
    },
    [fetchUnits]
  );

  // Quay lại danh sách sách
  const backToBooks = useCallback(() => {
    setActiveBook(null);
    setView("books");
    setUnits([]);
  }, []);

  // Làm mới dữ liệu theo view hiện tại (books → danh sách sách; nodes → node cuốn đang chọn)
  const refreshCurrentView = useCallback(() => {
    if (view === "nodes" && activeBook) {
      fetchUnits(activeBook.id);
    } else {
      fetchBooks();
    }
  }, [view, activeBook, fetchUnits, fetchBooks]);

  useEffect(() => {
    if (view === "books") {
      fetchBooks();
    } else if (view === "nodes" && activeBook) {
      fetchUnits(activeBook.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, fetchBooks, fetchUnits]);

  // Tải danh sách môn từ DB (đồng bộ mock v4); fallback list tĩnh nếu lỗi
  useEffect(() => {
    api
      .get<{ code: string; name: string }[]>("/curriculum/subjects")
      .then((rows) => {
        if (rows && rows.length) {
          setSubjectOptions(rows.map((s) => ({ value: s.code, label: `${s.name} (${s.code})` })));
          // Giữ môn đang chọn nếu còn; nếu không, ưu tiên TOAN_6 rồi tới môn đầu list.
          setSubjectCode((cur) => {
            if (rows.some((s) => s.code === cur)) return cur;
            return rows.some((s) => s.code === "TOAN_6") ? "TOAN_6" : (rows[0].code ?? "TOAN_6");
          });
        }
      })
      .catch(() => {
        /* giữ fallback */
      });
  }, []);

  // Tải lịch sử nạp sách (job queue)
  const loadIngestJobs = useCallback(async () => {
    setJobsLoading(true);
    try {
      const rows = await api.get<BookIngestJob[]>("/curriculum/ingest-book/jobs");
      setIngestJobs(rows || []);
    } catch {
      /* ignore */
    } finally {
      setJobsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadIngestJobs();
  }, [loadIngestJobs]);

  // Poll lịch sử khi có job đang pending/processing (như EWS); khi job cuối hoàn tất → làm mới dữ liệu 1 lần.
  const prevJobsActiveRef = useRef(false);
  useEffect(() => {
    const active = ingestJobs.some((j) => j.status === "pending" || j.status === "processing");
    const wasActive = prevJobsActiveRef.current;
    prevJobsActiveRef.current = active;
    if (!active) {
      if (wasActive) refreshCurrentView(); // job vừa xong (vd làm giàu lại) → cập nhật node/sách
      return;
    }
    const timer = setInterval(() => {
      loadIngestJobs();
      fetchBooks();
    }, 3000);
    return () => clearInterval(timer);
  }, [ingestJobs, loadIngestJobs, fetchBooks, refreshCurrentView]);

  const handleUpload = async () => {
    if (!selectedFile) {
      setUploadErr("Vui lòng chọn file mục lục (JSON hoặc markdown).");
      return;
    }
    setUploading(true);
    setUploadErr(null);
    setUploadMsg(null);
    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("subject_code", subjectCode);
    try {
      const res = await api.upload<UploadResult>("/curriculum/upload", formData);
      setUploadMsg(
        `Đã nạp ${res.inserted} mới, cập nhật ${res.updated}, ẩn ${res.hidden_placeholders} placeholder (nguồn: ${res.source}).`
      );
      setSelectedFile(null);
      refreshCurrentView();
    } catch (e: any) {
      setUploadErr(e?.message ?? "Upload thất bại.");
    } finally {
      setUploading(false);
    }
  };

  const handleBookIngestDirect = async () => {
    if (!bookFile) {
      setBookErr("Vui lòng chọn file sách giáo khoa (PDF/DOCX/TXT/MD).");
      return;
    }
    setBookUploading(true);
    setBookErr(null);
    setBookMsg("Đang nạp file và lưu tự động vào hệ thống (VLM/AI quét toàn cuốn + làm giàu nội dung, mất ~1–3 phút)...");
    const formData = new FormData();
    formData.append("file", bookFile);
    formData.append("subject_code", subjectCode);
    formData.append("grade", bookGrade);
    if (bookVolume) formData.append("volume", bookVolume);
    if (bookSemester) formData.append("semester", bookSemester);
    if (bookSchoolYearId) formData.append("school_year_id", bookSchoolYearId);
    if (bookTitle.trim()) formData.append("book_title", bookTitle.trim());
    if (includeLessons) formData.append("include_lessons", "true");
    if (enrichContent) formData.append("enrich", "true");
    if (overwriteEnrichment) formData.append("overwrite_enrichment", "true");
    const finalModel = selectedVlmModel === "custom" ? customVlmModel.trim() : selectedVlmModel;
    if (finalModel) formData.append("vlm_model", finalModel);
    formData.append("dry_run", "false"); // Tự động lưu thẳng vào DB khi trích xuất xong
    try {
      const job = await api.upload<BookIngestJob>("/curriculum/ingest-book", formData);
      loadIngestJobs();
      // Poll job để cập nhật trạng thái thời gian thực
      const deadline = Date.now() + 180_000;
      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 2500));
        const st = await api.get<BookIngestJob>(`/curriculum/ingest-book/jobs/${job.job_id}`);
        if (st.status === "completed") {
          const insertedCount = st.result?.inserted ?? 0;
          const updatedCount = st.result?.updated ?? 0;
          setBookMsg(
            `Đã nạp và lưu thành công ${st.result?.chapters?.length ?? 0} chương (${insertedCount} node mới, ${updatedCount} cập nhật) vào hệ thống.`
          );
          setBookFile(null);
          setBookUploading(false);
          await fetchBooks();
          if (view === "nodes" && activeBook) {
            await fetchUnits(activeBook.id);
          } else {
            await fetchUnits();
          }
          return;
        }
        if (st.status === "failed") {
          setBookErr(st.error ?? "Nạp sách thất bại.");
          setBookUploading(false);
          return;
        }
      }
      setBookMsg("Job nạp sách đang tiếp tục chạy ngầm trong hệ thống. Bạn có thể theo dõi tiến độ ở bảng Lịch sử bên dưới.");
    } catch (e: any) {
      setBookErr(e?.message ?? "Gửi file nạp sách thất bại.");
    } finally {
      setBookUploading(false);
      loadIngestJobs();
    }
  };

  const handleToggle = async (unit: CurriculumUnitRow) => {
    try {
      await api.post<CurriculumUnitRow>(`/curriculum/units/${unit.id}/toggle-active`);
      refreshCurrentView();
    } catch (e: any) {
      setError(e?.message ?? "Không bật/tắt được node.");
    }
  };

  const handleDeleteBook = useCallback((book: CurriculumBookRow) => {
    setBookToDelete(book);
    setDeleteErr(null);
  }, []);

  // Chạy lại bước làm giàu nội dung cho cuốn đang xem (từ file PDF gốc đã lưu, không cần upload lại).
  const handleReEnrich = async () => {
    if (!activeBook) return;
    setReEnriching(true);
    setReEnrichErr(null);
    setReEnrichMsg(null);
    const finalModel = selectedVlmModel === "custom" ? customVlmModel.trim() : selectedVlmModel;
    try {
      await api.post<BookIngestJob>(`/curriculum/books/${activeBook.id}/re-enrich`, {
        vlm_model: finalModel || null,
      });
      setReEnrichMsg(`Đã tạo job làm giàu lại với model ${finalModel || "mặc định"} — theo dõi ở bảng 'Lịch sử nạp sách'.`);
      loadIngestJobs();
    } catch (e: any) {
      setReEnrichErr(e?.message ?? "Không tạo được job làm giàu lại.");
    } finally {
      setReEnriching(false);
    }
  };

  // Xóa sạch toàn bộ nội dung làm giàu (tóm tắt/từ khóa/mục con) của cuốn sách đang xem
  const handleClearEnrichment = async () => {
    if (!activeBook) return;
    if (
      !window.confirm(
        `Xóa toàn bộ tóm tắt, từ khóa, mục con của ${units.length} node thuộc cuốn "${activeBook.title}" để làm giàu lại từ đầu?`
      )
    ) {
      return;
    }
    setClearingEnrichment(true);
    setReEnrichErr(null);
    setReEnrichMsg(null);
    try {
      const res = await api.post<{ book_id: number; cleared_units_count: number; message: string }>(
        `/curriculum/books/${activeBook.id}/clear-enrichment`
      );
      setReEnrichMsg(res.message || "Đã xóa sạch dữ liệu làm giàu của cuốn sách.");
      await fetchUnits(activeBook.id);
    } catch (e: any) {
      setReEnrichErr(e?.message ?? "Không xóa được dữ liệu làm giàu.");
    } finally {
      setClearingEnrichment(false);
    }
  };

  // Cắt lát và index chunks RAG trực tiếp (không quét lại mục lục/cây bài)
  const handleExecuteIndexChunks = async () => {
    if (!bookToIndexChunks) return;
    setReIndexingChunks(true);
    setReIndexErr(null);
    setReIndexMsg(null);
    const finalModel = chunkModalVlmModel === "custom" ? chunkModalCustomModel.trim() : chunkModalVlmModel;
    try {
      const res = await api.post<{ book_id: number; title: string; chunk_count: number; message: string }>(
        `/curriculum/books/${bookToIndexChunks.id}/re-index-chunks`,
        { vlm_model: finalModel || null }
      );
      setReIndexMsg(res.message || `Đã index thành công ${res.chunk_count} chunks RAG vào PostgreSQL.`);
      await fetchBooks();
      if (activeBook && activeBook.id === bookToIndexChunks.id) {
        setActiveBook((prev) => (prev ? { ...prev, chunk_count: res.chunk_count } : null));
      }
      setBookToIndexChunks(null);
    } catch (e: any) {
      setReIndexErr(e?.message ?? "Lỗi khi cắt và index chunks.");
    } finally {
      setReIndexingChunks(false);
    }
  };

  const confirmDeleteBook = async () => {
    if (!bookToDelete) return;
    setDeletingBook(true);
    setDeleteErr(null);
    try {
      await api.del(`/curriculum/books/${bookToDelete.id}`);
      setDeleteSuccess(`Đã xóa cuốn "${bookToDelete.title}" và toàn bộ node chương/bài thuộc cuốn.`);
      const deletedId = bookToDelete.id;
      setBookToDelete(null);
      await fetchBooks();
      if (view === "nodes" && activeBook?.id === deletedId) {
        backToBooks();
      } else if (view === "nodes" && activeBook) {
        fetchUnits(activeBook.id);
      }
    } catch (e: any) {
      setDeleteErr(e?.message ?? "Lỗi khi xóa cuốn sách.");
    } finally {
      setDeletingBook(false);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-[1400px] mx-auto space-y-6">
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-brand-50 dark:bg-brand-950/50 text-brand-600 dark:text-brand-400 border border-brand-100 dark:border-brand-900/50">
              <FolderTree className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
              Quản lý Sách & Chương trình học (Curriculum)
            </h2>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Quản lý danh mục SGK, cây node chương/bài và pipeline nạp sách tự động bằng AI.
          </p>
        </div>
        <button
          onClick={refreshCurrentView}
          disabled={loading || booksLoading}
          className="px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2 shadow-xs transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading || booksLoading ? "animate-spin" : ""}`} />
          Làm mới dữ liệu
        </button>
      </header>

      {/* 3-Tab Dashboard Navigation Bar */}
      <div className="flex items-center gap-3 border-b border-slate-200 dark:border-slate-800 pb-3 flex-wrap">
        <button
          onClick={() => setMainTab("catalog")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
            mainTab === "catalog"
              ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30"
              : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
          }`}
        >
          <BookOpen className="w-4 h-4" />
          Thư viện Sách & Cây Mục Lục
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-bold ${
              mainTab === "catalog" ? "bg-white/20 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
            }`}
          >
            {books.length} cuốn
          </span>
        </button>

        <button
          onClick={() => setMainTab("schedule")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
            mainTab === "schedule"
              ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30"
              : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
          }`}
        >
          <Calendar className="w-4 h-4" />
          Phân phối chương trình (35 tuần)
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-bold ${
              mainTab === "schedule" ? "bg-white/20 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
            }`}
          >
            35 tuần
          </span>
        </button>

        <button
          onClick={() => setMainTab("ingest")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
            mainTab === "ingest"
              ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30"
              : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
          }`}
        >
          <UploadCloud className="w-4 h-4" />
          Nạp Sách Mới & Hàng Đợi (AI)
          {ingestJobs.some((j) => j.status === "pending" || j.status === "processing") && (
            <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500 text-white animate-pulse">
              <Loader2 className="w-3 h-3 animate-spin" />
              Đang xử lý
            </span>
          )}
        </button>
      </div>

      {/* TAB 2: NẠP SÁCH & HÀNG ĐỢI NỀN */}
      {mainTab === "ingest" && (
        <div className="space-y-6">
          {/* Nạp sách giáo khoa — pipeline tự động bóc tách & lưu thẳng vào hệ thống */}
          <section className="bg-white dark:bg-slate-900 border rounded-2xl p-5 shadow-sm space-y-3">
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-brand-500" />
              Nạp sách giáo khoa — tự động trích xuất & lưu trực tiếp
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Upload file SGK (<strong>PDF/DOCX/TXT/MD</strong>). Với PDF hệ thống <strong>quét toàn bộ cuốn</strong>,
              tự bóc tách mục lục và làm giàu nội dung (tóm tắt, từ khóa, mục con) rồi <strong>lưu thẳng vào cơ sở dữ liệu</strong>.
              Bạn có thể rời đi hoặc làm việc khác trong khi AI xử lý.
            </p>
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[180px]">
                <label className="text-xs font-semibold text-slate-500 mb-1 block">
                  Năm học áp dụng <span className="text-rose-500">*</span>
                </label>
                <SearchableSelect
                  options={
                    schoolYears.length > 0
                      ? schoolYears.map((y) => ({
                          value: String(y.id),
                          label: y.fullname + (y.is_current ? " (Hiện tại)" : ""),
                        }))
                      : [
                          { value: "2025", label: "Năm học 2024-2025 (Hiện tại)" },
                          { value: "2026", label: "Năm học 2025-2026" },
                        ]
                  }
                  value={bookSchoolYearId}
                  onChange={setBookSchoolYearId}
                  className="min-w-[180px]"
                />
              </div>
              <div className="min-w-[200px]">
                <label className="text-xs font-semibold text-slate-500 mb-1 block">
                  Môn học <span className="text-rose-500">*</span>
                </label>
                <SearchableSelect
                  options={subjectOptions}
                  value={subjectCode}
                  onChange={(v) => {
                    setSubjectCode(v);
                    const m = v.match(/^([A-Z_]+)_(\d+)$/);
                    if (m) setBookGrade(m[2]);
                  }}
                  className="min-w-[200px]"
                />
              </div>
              <div className="min-w-[180px]">
                <label className="text-xs font-semibold text-slate-500 mb-1 block">Khối lớp</label>
                <SearchableSelect
                  options={[
                    { value: "6", label: "Khối 6" },
                    { value: "7", label: "Khối 7" },
                    { value: "8", label: "Khối 8" },
                    { value: "9", label: "Khối 9" },
                  ]}
                  value={bookGrade}
                  onChange={setBookGrade}
                  className="min-w-[180px]"
                />
              </div>
              <div className="min-w-[160px]">
                <label className="text-xs font-semibold text-slate-500 mb-1 block">Tập sách</label>
                <SearchableSelect
                  options={[
                    { value: "Tập 1", label: "Tập 1 (HK1)" },
                    { value: "Tập 2", label: "Tập 2 (HK2)" },
                    { value: "Cả năm", label: "Cả năm (Trọn bộ)" },
                  ]}
                  value={bookVolume}
                  onChange={(v) => {
                    setBookVolume(v);
                    if (v === "Tập 1") setBookSemester("1");
                    else if (v === "Tập 2") setBookSemester("2");
                    else if (v === "Cả năm") setBookSemester("");
                  }}
                  className="min-w-[160px]"
                />
              </div>
              <div className="min-w-[160px]">
                <label className="text-xs font-semibold text-slate-500 mb-1 block">Học kỳ</label>
                <SearchableSelect
                  options={[
                    { value: "", label: "Tự đoán (tên file)" },
                    { value: "1", label: "Học kỳ 1" },
                    { value: "2", label: "Học kỳ 2" },
                  ]}
                  value={bookSemester}
                  onChange={setBookSemester}
                  className="min-w-[160px]"
                />
              </div>
              <div className="min-w-[240px] flex-1">
                <label className="text-xs font-semibold text-slate-500 mb-1 block">
                  Tên cuốn / Chương / Tập / Mô tả (Tùy chọn)
                </label>
                <input
                  type="text"
                  value={bookTitle}
                  onChange={(e) => {
                    setBookTitle(e.target.value);
                    setBookErr(null);
                  }}
                  placeholder='Ví dụ: Tập 1 - Chương 1 Số học'
                  className="w-full px-3.5 py-2 rounded-xl text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-850 text-slate-800 dark:text-slate-200 focus:outline-hidden focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div className="w-full sm:w-auto min-w-[220px]">
                <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">
                  Mô hình AI (VLM):
                </label>
                <select
                  value={selectedVlmModel}
                  onChange={(e) => setSelectedVlmModel(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-850 text-slate-800 dark:text-slate-200 focus:outline-hidden focus:ring-2 focus:ring-brand-500 font-medium"
                >
                  <optgroup label="OpenRouter (Khuyên dùng)">
                    <option value="google/gemini-3.7-flash">⚡ Google Gemini 3.7 Flash (Mới nhất, siêu rẻ & nhanh)</option>
                    <option value="xiaomi/mimo-v2.5">⚡ Xiaomi Mimo 2.5</option>
                    <option value="openai/gpt-4o-mini">⚡ OpenAI GPT-4o Mini</option>
                    <option value="qwen/qwen-2.5-vl-72b-instruct">⚡ Qwen 2.5 VL 72B Instruct</option>
                  </optgroup>
                  <optgroup label="ShopAIKey / DashScope">
                    <option value="qwen3-vl-flash">🇨🇳 Qwen 3 VL Flash (ShopAIKey)</option>
                  </optgroup>
                  <option value="custom">✏️ Tùy chỉnh Model ID...</option>
                </select>
              </div>
              {selectedVlmModel === "custom" && (
                <div className="w-full sm:w-auto min-w-[200px]">
                  <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">
                    Nhập Model ID:
                  </label>
                  <input
                    type="text"
                    value={customVlmModel}
                    onChange={(e) => setCustomVlmModel(e.target.value)}
                    placeholder="vd: google/gemini-pro-vision"
                    className="w-full px-3.5 py-2 rounded-xl text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-850 text-slate-800 dark:text-slate-200 focus:outline-hidden focus:ring-2 focus:ring-brand-500"
                  />
                </div>
              )}
              <label className="flex items-center gap-2 cursor-pointer pb-2.5 text-xs font-medium text-slate-700 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={includeLessons}
                  onChange={(e) => setIncludeLessons(e.target.checked)}
                  className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span>Tách cả bài con (BÀI n)</span>
              </label>
              <label
                className="flex items-center gap-2 cursor-pointer pb-2.5 text-xs font-medium text-slate-700 dark:text-slate-300"
                title="PDF: quét toàn cuốn, VLM tạo tóm tắt + từ khóa + mục con cho từng bài (chậm hơn ~1-2 phút)"
              >
                <input
                  type="checkbox"
                  checked={enrichContent}
                  onChange={(e) => setEnrichContent(e.target.checked)}
                  className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span className="inline-flex items-center gap-1">
                  <Sparkles className="w-3.5 h-3.5 text-brand-500" />
                  Làm giàu nội dung (tóm tắt, từ khóa, mục con)
                </span>
              </label>
              <label
                className="flex items-center gap-2 cursor-pointer pb-2.5 text-xs font-medium text-slate-700 dark:text-slate-300"
                title="Tự động xóa sạch/làm mới tóm tắt và từ khóa cũ của các bài học bị trùng mã khi nạp lại sách"
              >
                <input
                  type="checkbox"
                  checked={overwriteEnrichment}
                  onChange={(e) => setOverwriteEnrichment(e.target.checked)}
                  className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span className="inline-flex items-center gap-1">
                  <RefreshCw className="w-3.5 h-3.5 text-slate-500" />
                  Ghi đè làm giàu cũ nếu trùng bài
                </span>
              </label>
              <label className="flex-1 min-w-[240px] flex items-center gap-2 rounded-xl border border-dashed border-slate-300 dark:border-slate-700 px-3 py-2.5 cursor-pointer hover:border-brand-400 text-sm text-slate-500">
                <FileUp className="w-4 h-4 shrink-0" />
                {bookFile ? (
                  <span className="truncate text-slate-800 dark:text-slate-200">{bookFile.name}</span>
                ) : (
                  <span>Chọn file SGK .pdf / .docx / .txt / .md...</span>
                )}
                <input
                  type="file"
                  accept=".pdf,.docx,.txt,.md"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0] ?? null;
                    setBookFile(file);
                    setBookErr(null);
                  }}
                />
              </label>
              <button
                onClick={handleBookIngestDirect}
                disabled={bookUploading || !bookFile}
                className="px-5 py-2.5 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2 shadow-sm transition-all"
              >
                {bookUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
                {bookUploading ? "Đang nạp & lưu sách..." : "Nạp sách vào hệ thống"}
              </button>
            </div>
            {bookMsg && (
              <p className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" /> {bookMsg}
              </p>
            )}
            {bookErr && (
              <p className="text-xs text-rose-600 dark:text-rose-400 flex items-center gap-1.5">
                <X className="w-3.5 h-3.5" /> {bookErr}
              </p>
            )}
          </section>

          {/* Upload JSON / Markdown thủ công */}
          <section className="bg-white dark:bg-slate-900 border rounded-2xl p-5 shadow-sm space-y-3">
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <UploadCloud className="w-4 h-4 text-brand-500" />
              Tải lên mục lục chương trình từ file JSON / Markdown
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Nhận file <strong>JSON</strong> (định dạng catalog) hoặc <strong>markdown mục lục SGK</strong> (dạng &quot;## LỚP 6 / ### Tập 1 / * **Chương I: Tên** / mô tả&quot;).
            </p>
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[200px]">
                <label className="text-xs font-semibold text-slate-500 mb-1 block">Môn học</label>
                <SearchableSelect
                  options={subjectOptions}
                  value={subjectCode}
                  onChange={setSubjectCode}
                  className="min-w-[200px]"
                />
              </div>
              <label className="flex-1 min-w-[260px] flex items-center gap-2 rounded-xl border border-dashed border-slate-300 dark:border-slate-700 px-3 py-2.5 cursor-pointer hover:border-brand-400 text-sm text-slate-500">
                <FileUp className="w-4 h-4 shrink-0" />
                {selectedFile ? (
                  <span className="truncate text-slate-800 dark:text-slate-200">{selectedFile.name}</span>
                ) : (
                  <span>Chọn file .json / .md / .txt...</span>
                )}
                <input
                  type="file"
                  accept=".json,.md,.txt"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0] ?? null;
                    setSelectedFile(f);
                    setUploadErr(null);
                  }}
                />
              </label>
              <button
                onClick={handleUpload}
                disabled={uploading || !selectedFile}
                className="px-4 py-2.5 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-2"
              >
                {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
                {uploading ? "Đang nạp..." : "Tải lên"}
              </button>
            </div>
            {uploadMsg && (
              <p className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" /> {uploadMsg}
              </p>
            )}
            {uploadErr && (
              <p className="text-xs text-rose-600 dark:text-rose-400 flex items-center gap-1.5">
                <X className="w-3.5 h-3.5" /> {uploadErr}
              </p>
            )}
          </section>

          {/* Lịch sử nạp sách (job queue) */}
          <section className="bg-white dark:bg-slate-900 border rounded-2xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-1">
              <h3 className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <RefreshCw className={`w-4 h-4 text-brand-500 ${ingestJobs.some((j) => j.status === "pending" || j.status === "processing") ? "animate-spin" : ""}`} />
                Lịch sử nạp sách (hàng đợi nền)
              </h3>
              <span className="text-xs text-slate-400">{ingestJobs.length} job</span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
              Mỗi lần nạp sách tạo một job chạy nền (DB-backed queue). Kết quả và trạng thái tự cập nhật thời gian thực tại đây.
            </p>
            {ingestJobs.length === 0 ? (
              <p className="text-sm text-slate-400 py-4 text-center">
                Chưa có job nạp sách nào. {jobsLoading ? "Đang tải..." : ""}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                      <th className="px-4 py-2.5">ID</th>
                      <th className="px-4 py-2.5">File</th>
                      <th className="px-4 py-2.5">Môn · Khối</th>
                      <th className="px-4 py-2.5">Tên cuốn</th>
                      <th className="px-4 py-2.5">Trạng thái</th>
                      <th className="px-4 py-2.5 text-center">Tiến độ</th>
                      <th className="px-4 py-2.5">Tạo lúc</th>
                      <th className="px-4 py-2.5">Kết quả / Thông báo</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                    {ingestJobs.map((j) => {
                      const meta = INGEST_STATUS_META[j.status];
                      return (
                        <tr key={j.job_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                          <td className="px-4 py-2.5 font-mono text-xs text-slate-400">#{j.job_id}</td>
                          <td className="px-4 py-2.5 text-xs text-slate-600 dark:text-slate-300 truncate max-w-[180px]" title={j.filename ?? ""}>
                            {j.filename ?? "—"}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-slate-500">
                            {j.subject_code} · Khối {j.grade_number}
                            {j.semester_number ? ` · HK${j.semester_number}` : ""}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-slate-500 truncate max-w-[160px]" title={j.book_title ?? ""}>
                            <div>{j.book_title || "—"}</div>
                            {j.vlm_model && (
                              <span className="inline-block mt-0.5 px-1.5 py-0.2 rounded text-[10px] font-mono bg-slate-100 dark:bg-slate-800 text-slate-500 border border-slate-200 dark:border-slate-700 truncate max-w-[150px]" title={j.vlm_model}>
                                {j.vlm_model.split("/").pop()}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-2.5">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${meta.cls}`}>
                              {j.status === "processing" ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : j.status === "completed" ? (
                                <CheckCircle2 className="w-3 h-3" />
                              ) : j.status === "failed" ? (
                                <X className="w-3 h-3" />
                              ) : (
                                <RefreshCw className="w-3 h-3" />
                              )}
                              {meta.label}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-center text-xs text-slate-500">{j.progress}%</td>
                          <td className="px-4 py-2.5 text-xs text-slate-400 font-mono whitespace-nowrap">
                            {j.created_at ? new Date(j.created_at).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" }) : "—"}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-slate-500 max-w-[320px]">
                            {j.status === "failed" ? (
                              <span className="text-rose-600 dark:text-rose-400 font-medium" title={j.error ?? ""}>
                                {j.error ?? "Thất bại"}
                              </span>
                            ) : j.result ? (
                              <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                                {j.result.chapters?.length ?? 0} chương · {j.result.inserted} node mới · {j.result.updated} cập nhật
                                {j.result.warnings?.length ? (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setSelectedJobWarnings({
                                        jobId: j.job_id,
                                        filename: j.filename ?? "Tài liệu",
                                        warnings: j.result?.warnings ?? [],
                                      });
                                      setWarningSearch("");
                                    }}
                                    className="mt-1.5 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-50 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800/80 hover:bg-amber-100 dark:hover:bg-amber-900/40 transition-all text-left group shadow-2xs cursor-pointer"
                                  >
                                    <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 group-hover:scale-110 transition-transform" />
                                    <span>⚠ {j.result.warnings.length} cảnh báo (Nhấn để xem chi tiết)</span>
                                    <ChevronRight className="w-3.5 h-3.5 text-amber-400 shrink-0 ml-1 group-hover:translate-x-0.5 transition-transform" />
                                  </button>
                                ) : null}
                              </span>
                            ) : (
                              "—"
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}

      {/* TAB 1: THƯ VIỆN SÁCH & CÂY MỤC LỤC */}
      {mainTab === "catalog" && (
        <div className="space-y-6">
          {/* Bộ lọc (chỉ hiển thị ở view danh sách sách; khi xem node của 1 cuốn thì ẩn) */}
          {view === "books" && (
            <section className="bg-white dark:bg-slate-900 border rounded-2xl p-4 flex flex-wrap items-end gap-3 shadow-sm">
            <div className="min-w-[180px]">
              <label className="text-xs font-semibold text-slate-500 mb-1 block">Năm học</label>
              <SearchableSelect
                options={[
                  { value: "", label: "Tất cả năm học" },
                  ...(schoolYears.length > 0
                    ? schoolYears.map((y) => ({
                        value: String(y.id),
                        label: y.fullname + (y.is_current ? " (Hiện tại)" : ""),
                      }))
                    : [
                        { value: "2025", label: "Năm học 2024-2025" },
                        { value: "2026", label: "Năm học 2025-2026" },
                      ]),
                ]}
                value={selectedSchoolYearId ? String(selectedSchoolYearId) : ""}
                onChange={(v) => setSelectedSchoolYearId(v ? Number(v) : null)}
                className="min-w-[180px]"
              />
            </div>
            <div className="min-w-[200px]">
              <label className="text-xs font-semibold text-slate-500 mb-1 block">Môn học</label>
              <SearchableSelect
                options={subjectOptions}
                value={subjectCode}
                onChange={setSubjectCode}
                className="min-w-[200px]"
              />
            </div>
            <div className="min-w-[130px]">
              <label className="text-xs font-semibold text-slate-500 mb-1 block">Khối</label>
              <SearchableSelect
                options={[
                  { value: "", label: "Tất cả khối" },
                  ...Array.from({ length: 7 }, (_, i) => ({ value: String(i + 6), label: `Khối ${i + 6}` })),
                ]}
                value={grade}
                onChange={setGrade}
                className="min-w-[130px]"
              />
            </div>
            <div className="min-w-[120px]">
              <label className="text-xs font-semibold text-slate-500 mb-1 block">Học kỳ</label>
              <SearchableSelect
                options={[
                  { value: "", label: "Cả năm" },
                  { value: "1", label: "Học kỳ 1" },
                  { value: "2", label: "Học kỳ 2" },
                ]}
                value={semester}
                onChange={setSemester}
                className="min-w-[120px]"
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer pb-2.5 text-xs font-medium text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={includeInactive}
                onChange={(e) => setIncludeInactive(e.target.checked)}
                className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
              <span>Bao gồm node đã ẩn</span>
            </label>
          </section>
          )}

      {deleteSuccess && (
        <div className="rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{deleteSuccess}</span>
          </div>
          <button
            onClick={() => setDeleteSuccess(null)}
            className="text-emerald-600 hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-200"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {error && (
        <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 px-4 py-3 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </div>
      )}

      {/* ===== View: danh sách sách (mặc định) — card vuông có ảnh bìa ===== */}
      {view === "books" && (
        <section className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900 dark:text-slate-100">Danh sách sách giáo khoa</h3>
            <span className="text-xs text-slate-400">{books.length} cuốn</span>
          </div>
          <div className="p-5">
            {books.length === 0 && !booksLoading ? (
              <p className="text-sm text-slate-400 text-center py-10">
                Chưa có cuốn sách nào cho bộ lọc hiện tại — hãy dùng "Nạp sách giáo khoa" ở trên rồi bấm Lưu.
              </p>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-4">
                {books.map((b) => (
                  <BookCard
                    key={b.id}
                    book={b}
                    onOpen={openBook}
                    onDelete={handleDeleteBook}
                    onToggleLock={handleToggleLock}
                    togglingLockId={togglingLockId}
                  />
                ))}
              </div>
            )}
          </div>
        </section>
      )}

      {/* ===== View: node của 1 cuốn đã chọn ===== */}
      {view === "nodes" && (
        <section className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <button
                onClick={backToBooks}
                className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors"
              >
                ← Về danh sách sách
              </button>
              <h3 className="font-semibold text-slate-900 dark:text-slate-100 truncate">
                {activeBook ? (
                  <span className="inline-flex items-center gap-1.5">
                    <BookOpen className="w-4 h-4 text-brand-500 shrink-0" />
                    {activeBook.title}
                    <span className="text-xs font-normal text-slate-400">
                      ({activeBook.subject_code} · Khối {activeBook.grade_number})
                    </span>
                  </span>
                ) : (
                  "Danh sách node chương/bài"
                )}
              </h3>
            </div>
            <div className="flex items-center gap-2 shrink-0 flex-wrap">
              <span className="text-xs text-slate-400">
                {units.length} node
                {activeBook && (
                  <>
                    {" "}·{" "}
                    <strong className={(activeBook.chunk_count ?? 0) > 0 ? "text-emerald-600 dark:text-emerald-400 font-semibold" : "text-amber-600 dark:text-amber-400 font-medium"}>
                      {(activeBook.chunk_count ?? 0) > 0 ? `🧠 ${activeBook.chunk_count} chunks` : "⚠️ Chưa có chunks"}
                    </strong>
                  </>
                )}
              </span>
              {activeBook && (
                <>
                  <button
                    type="button"
                    onClick={() => handleToggleLock(activeBook)}
                    disabled={togglingLockId === activeBook.id}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                      activeBook.is_locked
                        ? "bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700"
                        : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-200"
                    }`}
                    title={activeBook.is_locked ? "Click để mở khóa sách" : "Click để khóa sách"}
                  >
                    {togglingLockId === activeBook.id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : activeBook.is_locked ? (
                      <Lock className="w-3.5 h-3.5 text-amber-600" />
                    ) : (
                      <Unlock className="w-3.5 h-3.5" />
                    )}
                    <span>{activeBook.is_locked ? "Sách Đã Khóa 🔒" : "Khóa sách"}</span>
                  </button>

                  {/* Nút Index Chunks (RAG) riêng lẻ — mở modal chọn model */}
                  <button
                    type="button"
                    onClick={() => {
                      setReIndexErr(null);
                      setReIndexMsg(null);
                      setBookToIndexChunks(activeBook);
                    }}
                    disabled={reIndexingChunks || reEnriching || clearingEnrichment || activeBook.is_locked}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-purple-200 dark:border-purple-900 bg-purple-50 dark:bg-purple-950/30 hover:bg-purple-100 dark:hover:bg-purple-900/50 text-purple-700 dark:text-purple-300 transition-colors disabled:opacity-50"
                    title={activeBook.is_locked ? "Sách đã bị khóa" : "Cắt lát các bài học hiện có và nhúng vector RAG vào pgvector (không quét lại mục lục, tiết kiệm chi phí)"}
                  >
                    {reIndexingChunks ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Brain className="w-3.5 h-3.5" />}
                    <span>{reIndexingChunks ? "Đang xử lý..." : "Index chunks (RAG)"}</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleReEnrich}
                    disabled={reEnriching || reIndexingChunks || clearingEnrichment || activeBook.is_locked}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-brand-200 dark:border-brand-900 bg-brand-50 dark:bg-brand-950/30 hover:bg-brand-100 dark:hover:bg-brand-900/50 text-brand-700 dark:text-brand-300 transition-colors disabled:opacity-50"
                    title={activeBook.is_locked ? "Sách đã bị khóa" : "Chạy lại bước làm giàu (tóm tắt/từ khóa/mục con) từ file PDF gốc đã lưu"}
                  >
                    {reEnriching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    <span>{reEnriching ? "Đang tạo job..." : "Làm giàu lại"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleClearEnrichment}
                    disabled={clearingEnrichment || reIndexingChunks || reEnriching || activeBook.is_locked}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/30 hover:bg-amber-100 dark:hover:bg-amber-900/50 text-amber-700 dark:text-amber-300 transition-colors disabled:opacity-50"
                    title={activeBook.is_locked ? "Sách đã bị khóa" : "Xóa sạch toàn bộ tóm tắt, từ khóa, mục con của cuốn này để làm giàu lại từ đầu"}
                  >
                    {clearingEnrichment ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Eraser className="w-3.5 h-3.5" />}
                    <span>{clearingEnrichment ? "Đang xóa..." : "Xóa tất cả làm giàu"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteBook(activeBook)}
                    disabled={clearingEnrichment || reIndexingChunks || reEnriching || activeBook.is_locked}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-rose-200 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/30 hover:bg-rose-100 dark:hover:bg-rose-900/50 text-rose-700 dark:text-rose-300 transition-colors disabled:opacity-50"
                    title={activeBook.is_locked ? "Sách đã bị khóa" : `Xóa cuốn "${activeBook.title}" và toàn bộ node`}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Xóa cuốn này</span>
                  </button>
                </>
              )}
            </div>
          </div>
          {activeBook?.is_locked && (
            <div className="mx-5 mt-4 p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-xs flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Lock className="w-4 h-4 text-amber-600 shrink-0" />
                <span>
                  <strong>Sách đang bị KHÓA:</strong> Cuốn sách này đã được khóa cho năm học {activeBook.school_year_name || ""}. Các thao tác sửa đổi, làm giàu lại và xóa node tạm thời bị vô hiệu hóa để bảo vệ tính toàn vẹn dữ liệu.
                </span>
              </div>
              <button
                type="button"
                onClick={() => handleToggleLock(activeBook)}
                disabled={togglingLockId === activeBook.id}
                className="px-3 py-1 rounded-lg font-semibold bg-amber-600 hover:bg-amber-700 text-white shrink-0 transition flex items-center gap-1.5 cursor-pointer text-xs"
              >
                {togglingLockId === activeBook.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Unlock className="w-3 h-3" />}
                Mở khóa sách
              </button>
            </div>
          )}
          {reIndexMsg && (
            <p className="px-5 py-2 text-xs text-purple-700 dark:text-purple-300 bg-purple-50/60 dark:bg-purple-950/20 border-b border-purple-100 dark:border-purple-900/40 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-purple-600" /> {reIndexMsg}
            </p>
          )}
          {reIndexErr && (
            <p className="px-5 py-2 text-xs text-rose-600 dark:text-rose-400 bg-rose-50/60 dark:bg-rose-950/20 border-b border-rose-100 dark:border-rose-900/40 flex items-center gap-1.5">
              <X className="w-3.5 h-3.5 shrink-0" /> {reIndexErr}
            </p>
          )}
          {reEnrichMsg && (
            <p className="px-5 py-2 text-xs text-emerald-600 dark:text-emerald-400 bg-emerald-50/60 dark:bg-emerald-950/20 border-b border-emerald-100 dark:border-emerald-900/40 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0" /> {reEnrichMsg}
            </p>
          )}
          {reEnrichErr && (
            <p className="px-5 py-2 text-xs text-rose-600 dark:text-rose-400 bg-rose-50/60 dark:bg-rose-950/20 border-b border-rose-100 dark:border-rose-900/40 flex items-center gap-1.5">
              <X className="w-3.5 h-3.5 shrink-0" /> {reEnrichErr}
            </p>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                  <th className="px-5 py-3">Mã node</th>
                  <th className="px-5 py-3">Tên</th>
                  <th className="px-5 py-3 text-center">Khối</th>
                  <th className="px-5 py-3 text-center">HK</th>
                  <th className="px-5 py-3">Chương cha</th>
                  <th className="px-5 py-3">Cuốn sách nguồn</th>
                  <th className="px-5 py-3 text-center">Trạng thái</th>
                  <th className="px-5 py-3 text-center">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                {hierarchicalUnits.map((item) => {
                  if (item.hiddenByCollapse) return null;
                  const u = item.unit;
                  const hasDetail = Boolean(u.summary || (u.keywords?.length ?? 0) > 0 || (u.sections?.length ?? 0) > 0);
                  const expanded = expandedUnitId === u.id;
                  const isRoot = item.level === 0;

                  return (
                    <Fragment key={u.id}>
                      <tr
                        className={`transition-colors ${
                          isRoot
                            ? "bg-slate-50/80 dark:bg-slate-800/40 font-semibold border-t-2 border-slate-200/80 dark:border-slate-700/80 hover:bg-slate-100/70 dark:hover:bg-slate-800/70"
                            : "hover:bg-slate-50 dark:hover:bg-slate-800/50"
                        }`}
                      >
                        <td className="px-5 py-3 font-mono text-xs text-brand-600 dark:text-brand-400">{u.code}</td>
                        <td className="px-5 py-3 text-slate-800 dark:text-slate-200">
                          {isRoot ? (
                            <div className="flex items-center gap-2">
                              {item.isParent ? (
                                <button
                                  type="button"
                                  onClick={() => toggleParentCollapse(u.id)}
                                  className="p-1 -ml-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-500 transition-colors"
                                  title={collapsedParents.has(u.id) ? "Mở rộng các bài con" : "Thu gọn các bài con"}
                                >
                                  {collapsedParents.has(u.id) ? (
                                    <ChevronRight className="w-4 h-4" />
                                  ) : (
                                    <ChevronDown className="w-4 h-4" />
                                  )}
                                </button>
                              ) : (
                                <span className="w-4 inline-block" />
                              )}
                              <Folder className="w-4 h-4 text-brand-500 shrink-0" />
                              <span className="font-bold text-slate-900 dark:text-slate-100">{u.name}</span>
                              {item.isParent && (
                                <span className="ml-1.5 px-2 py-0.5 rounded-full text-[10px] font-normal bg-slate-200/70 dark:bg-slate-700/70 text-slate-600 dark:text-slate-300">
                                  {item.childCount} bài con
                                </span>
                              )}
                              {u.is_phu && (
                                <span className="ml-1 px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300">
                                  Phụ
                                </span>
                              )}
                            </div>
                          ) : (
                            <div
                              className="flex items-start gap-2"
                              style={{ paddingLeft: `${item.level * 1.75}rem` }}
                            >
                              <span className="text-slate-300 dark:text-slate-600 select-none font-mono text-sm mt-0.5 shrink-0">
                                ↳
                              </span>
                              {hasDetail && (
                                <button
                                  type="button"
                                  onClick={() => setExpandedUnitId(expanded ? null : u.id)}
                                  className="mt-0.5 shrink-0 text-slate-400 hover:text-brand-500 transition-colors"
                                  title={expanded ? "Thu gọn chi tiết" : "Xem chi tiết nội dung (tóm tắt/từ khóa/mục con)"}
                                >
                                  {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                                </button>
                              )}
                              <div>
                                <span className="font-medium text-slate-800 dark:text-slate-200">{u.name}</span>
                                {u.is_phu && (
                                  <span className="ml-1.5 inline-flex px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300">
                                    Phụ
                                  </span>
                                )}
                                {u.description && (
                                  <span className="block text-[11px] font-normal text-slate-400 max-w-md truncate">
                                    {u.description}
                                  </span>
                                )}
                              </div>
                            </div>
                          )}
                        </td>
                        <td className="px-5 py-3 text-center text-xs text-slate-500">{u.grade_number}</td>
                        <td className="px-5 py-3 text-center text-xs text-slate-500">
                          {u.semester_number ? `HK${u.semester_number}` : "—"}
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-500">{u.parent_name ?? "—"}</td>
                        <td className="px-5 py-3 text-xs text-slate-500">
                          {u.book_title ? (
                            <span className="inline-flex items-center gap-1 text-brand-600 dark:text-brand-400">
                              <BookOpen className="w-3 h-3 shrink-0" />
                              <span className="truncate max-w-[160px]" title={u.book_title}>{u.book_title}</span>
                            </span>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-center">
                          <span
                            className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                              u.is_active
                                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800"
                                : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 border-slate-200 dark:border-slate-700"
                            }`}
                          >
                            {u.is_active ? "Hoạt động" : "Đã ẩn"}
                          </span>
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex items-center justify-center gap-1.5">
                            <button
                              onClick={() => setDetailUnit(u)}
                              className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-brand-200 dark:border-brand-900 bg-brand-50 dark:bg-brand-950/40 hover:bg-brand-100 dark:hover:bg-brand-900/50 text-brand-700 dark:text-brand-300 transition-colors"
                              title="Xem chi tiết node (tóm tắt, từ khóa, mục con)"
                            >
                              Chi tiết
                            </button>
                            <button
                              onClick={() => handleToggle(u)}
                              className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors"
                              title={u.is_active ? "Ẩn khỏi shortlist map" : "Kích hoạt lại"}
                            >
                              {u.is_active ? "Ẩn" : "Kích hoạt"}
                            </button>
                          </div>
                        </td>
                      </tr>
                      {expanded && hasDetail && (
                        <tr className="bg-brand-50/50 dark:bg-brand-950/20 border-t border-brand-100 dark:border-brand-900/40">
                          <td colSpan={8} className="px-5 py-4">
                            <div className="space-y-2.5">
                              {u.summary && (
                                <div>
                                  <p className="text-[10px] font-bold uppercase tracking-wide text-brand-600 dark:text-brand-400 mb-1">
                                    Tóm tắt
                                  </p>
                                  <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed max-w-3xl">
                                    {u.summary}
                                  </p>
                                </div>
                              )}
                              {(u.keywords?.length ?? 0) > 0 && (
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <span className="text-[10px] font-bold uppercase tracking-wide text-brand-600 dark:text-brand-400">
                                    Từ khóa:
                                  </span>
                                  {u.keywords!.map((k) => (
                                    <span
                                      key={k}
                                      className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300"
                                    >
                                      {k}
                                    </span>
                                  ))}
                                </div>
                              )}
                              {(u.sections?.length ?? 0) > 0 && (
                                <div className="space-y-1">
                                  <p className="text-[10px] font-bold uppercase tracking-wide text-brand-600 dark:text-brand-400">
                                    Mục con trong bài
                                  </p>
                                  <ol className="list-decimal list-inside space-y-0.5">
                                    {u.sections!.map((s, i) => (
                                      <li key={`${s.name}-${i}`} className="text-xs text-slate-600 dark:text-slate-300">
                                        {s.name}
                                      </li>
                                    ))}
                                  </ol>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
                {units.length === 0 && !loading && (
                  <tr>
                    <td colSpan={8} className="px-5 py-10 text-center text-sm text-slate-400">
                      Không có node nào cho bộ lọc hiện tại.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
        </div>
      )}

      {/* TAB 3: PHÂN PHỐI CHƯƠNG TRÌNH 35 TUẦN */}
      {mainTab === "schedule" && (
        <div className="space-y-6">
          {/* Bộ lọc phân phối chương trình */}
          <section className="bg-white dark:bg-slate-900 border rounded-2xl p-4 flex flex-wrap items-end gap-3 shadow-sm">
            <div className="min-w-[180px]">
              <label className="text-xs font-semibold text-slate-500 mb-1 block">Năm học</label>
              <SearchableSelect
                options={
                  schoolYears.length > 0
                    ? schoolYears.map((y) => ({
                        value: String(y.id),
                        label: y.fullname + (y.is_current ? " (Hiện tại)" : ""),
                      }))
                    : [
                        { value: "2025", label: "Năm học 2024-2025 (Hiện tại)" },
                        { value: "2026", label: "Năm học 2025-2026" },
                      ]
                }
                value={selectedSchoolYearId ? String(selectedSchoolYearId) : "2025"}
                onChange={(v) => setSelectedSchoolYearId(v ? Number(v) : 2025)}
                className="min-w-[180px]"
              />
            </div>
            <div className="min-w-[200px]">
              <label className="text-xs font-semibold text-slate-500 mb-1 block">Môn học</label>
              <SearchableSelect
                options={subjectOptions}
                value={subjectCode}
                onChange={setSubjectCode}
                className="min-w-[200px]"
              />
            </div>
            <div className="min-w-[130px]">
              <label className="text-xs font-semibold text-slate-500 mb-1 block">Khối</label>
              <SearchableSelect
                options={[
                  { value: "", label: "Tất cả khối" },
                  ...Array.from({ length: 7 }, (_, i) => ({ value: String(i + 6), label: `Khối ${i + 6}` })),
                ]}
                value={grade}
                onChange={setGrade}
                className="min-w-[130px]"
              />
            </div>
            <div className="min-w-[140px]">
              <label className="text-xs font-semibold text-slate-500 mb-1 block">Học kỳ</label>
              <SearchableSelect
                options={[
                  { value: "", label: "Cả năm (35 tuần)" },
                  { value: "1", label: "Học kỳ 1 (Tuần 1-18)" },
                  { value: "2", label: "Học kỳ 2 (Tuần 19-35)" },
                ]}
                value={semester}
                onChange={setSemester}
                className="min-w-[140px]"
              />
            </div>
            <button
              onClick={fetchTeachingSchedules}
              disabled={teachingSchedulesLoading}
              className="px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2 shadow-xs transition"
            >
              <RefreshCw className={`w-4 h-4 ${teachingSchedulesLoading ? "animate-spin" : ""}`} />
              Tải lại
            </button>
          </section>

          {/* Bảng Kế hoạch 35 tuần */}
          <section className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <ListOrdered className="w-4 h-4 text-brand-500" />
                  Kế hoạch Giảng dạy & Phân phối chương trình chi tiết
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Phân bổ 35 tuần học theo quy định GDPT 2018. Tự động ánh xạ bài học với mã node chuẩn để theo dõi tiến độ.
                </p>
              </div>
              <span className="text-xs font-semibold text-brand-600 bg-brand-50 dark:bg-brand-950/40 px-3 py-1 rounded-lg border border-brand-200 dark:border-brand-900">
                {teachingSchedules.length} tuần học
              </span>
            </div>

            {teachingSchedules.length === 0 ? (
              <div className="p-10 text-center text-slate-400">
                {teachingSchedulesLoading ? (
                  <p className="flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" /> Đang tải dữ liệu phân phối chương trình...
                  </p>
                ) : (
                  <p>Chưa có dữ liệu phân phối chương trình cho bộ lọc này. Hãy chọn Môn Toán 6, Khối 6, Năm 2024-2025.</p>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                      <th className="px-4 py-3 font-semibold text-center w-16">Tuần</th>
                      <th className="px-4 py-3 font-semibold w-24">Học kỳ</th>
                      <th className="px-4 py-3 font-semibold">Chủ đề / Tên bài học</th>
                      <th className="px-4 py-3 font-semibold w-36">Node bài học</th>
                      <th className="px-4 py-3 font-semibold text-center w-24">Số tiết</th>
                      <th className="px-4 py-3 font-semibold">Ghi chú / Mốc đánh giá</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                    {teachingSchedules.map((item) => {
                      const isMidterm = item.week_number === 9 || item.week_number === 27;
                      const isFinal = item.week_number === 18 || item.week_number === 35;
                      const isSpecial = isMidterm || isFinal;

                      return (
                        <tr
                          key={item.id}
                          className={`transition-colors ${
                            isSpecial
                              ? "bg-amber-50/70 dark:bg-amber-950/20 font-semibold"
                              : "hover:bg-slate-50/80 dark:hover:bg-slate-800/40"
                          }`}
                        >
                          <td className="px-4 py-3 text-center">
                            <span
                              className={`inline-flex items-center justify-center w-8 h-8 rounded-xl text-xs font-bold ${
                                isSpecial
                                  ? "bg-amber-500 text-white shadow-xs"
                                  : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                              }`}
                            >
                              T{item.week_number}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-500">
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                              Học kỳ {item.semester_number}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="text-slate-800 dark:text-slate-200 font-medium">
                              {item.topic || "—"}
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            {item.unit_code ? (
                              <span className="inline-flex px-2 py-0.5 rounded font-mono text-[11px] font-semibold bg-brand-50 dark:bg-brand-950/50 text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-900">
                                {item.unit_code}
                              </span>
                            ) : (
                              <span className="text-xs text-slate-400 italic">Kiểm tra tập trung</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className="font-semibold text-slate-700 dark:text-slate-300">
                              {item.num_periods} tiết
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs">
                            {isSpecial ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800 shadow-2xs">
                                🎯 {isMidterm ? "Kiểm tra Giữa kỳ" : "Kiểm tra Cuối kỳ (Học kỳ)"}
                              </span>
                            ) : (
                              <span className="text-slate-500">{item.notes || "—"}</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}

      {/* Modal xem chi tiết node: meta + tóm tắt + từ khóa + mục con + thao tác */}
      {detailUnit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-xl border border-slate-200 dark:border-slate-800 space-y-4">
            {/* Header */}
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3 min-w-0">
                <div className="p-2 rounded-xl bg-brand-50 dark:bg-brand-950/50 text-brand-600 dark:text-brand-400 border border-brand-100 dark:border-brand-900/50 shrink-0">
                  <BookOpen className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <h4 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    <span className="truncate">{detailUnit.name}</span>
                    {detailUnit.is_phu && (
                      <span className="shrink-0 inline-flex px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300">
                        Phụ
                      </span>
                    )}
                  </h4>
                  <p className="font-mono text-xs text-brand-600 dark:text-brand-400">{detailUnit.code}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setDetailUnit(null)}
                className="shrink-0 p-1.5 rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                title="Đóng"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Meta nhanh */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
              <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 px-3 py-2">
                <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Khối</p>
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Khối {detailUnit.grade_number}</p>
              </div>
              <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 px-3 py-2">
                <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Học kỳ</p>
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {detailUnit.semester_number ? `HK${detailUnit.semester_number}` : "Cả năm"}
                </p>
              </div>
              <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 px-3 py-2">
                <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Chương cha</p>
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-200 truncate" title={detailUnit.parent_name ?? ""}>
                  {detailUnit.parent_name ?? "—"}
                </p>
              </div>
              <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 px-3 py-2">
                <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Cuốn sách nguồn</p>
                <p className="text-sm font-semibold text-brand-600 dark:text-brand-400 truncate" title={detailUnit.book_title ?? ""}>
                  {detailUnit.book_title ?? "—"}
                </p>
              </div>
            </div>

            {/* Trạng thái + thao tác */}
            <div className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 px-3.5 py-2.5">
              <span
                className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                  detailUnit.is_active
                    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800"
                    : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 border-slate-200 dark:border-slate-700"
                }`}
              >
                {detailUnit.is_active ? "Hoạt động (có trong shortlist map đề)" : "Đã ẩn (không map đề thi)"}
              </span>
              <button
                onClick={() => {
                  handleToggle(detailUnit);
                  setDetailUnit(null);
                }}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors"
              >
                {detailUnit.is_active ? "Ẩn khỏi map đề" : "Kích hoạt lại"}
              </button>
            </div>

            {/* Mô tả (nạp tay / markdown catalog) */}
            {detailUnit.description && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400 mb-1">Mô tả</p>
                <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{detailUnit.description}</p>
              </div>
            )}

            {/* Tóm tắt */}
            {detailUnit.summary && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wide text-brand-600 dark:text-brand-400 mb-1">
                  Tóm tắt nội dung
                </p>
                <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{detailUnit.summary}</p>
              </div>
            )}

            {/* Từ khóa */}
            {(detailUnit.keywords?.length ?? 0) > 0 && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wide text-brand-600 dark:text-brand-400 mb-1.5">
                  Từ khóa kiến thức
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {detailUnit.keywords!.map((k) => (
                    <span
                      key={k}
                      className="inline-flex px-2.5 py-1 rounded-full text-xs font-semibold bg-brand-50 dark:bg-brand-950/40 border border-brand-200 dark:border-brand-900 text-brand-700 dark:text-brand-300"
                    >
                      {k}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Mục con */}
            {(detailUnit.sections?.length ?? 0) > 0 && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wide text-brand-600 dark:text-brand-400 mb-1.5">
                  Mục con trong bài ({detailUnit.sections!.length})
                </p>
                <ol className="list-decimal list-inside space-y-1">
                  {detailUnit.sections!.map((s, i) => (
                    <li key={`${s.name}-${i}`} className="text-sm text-slate-700 dark:text-slate-200">
                      {s.name}
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Chưa có dữ liệu làm giàu */}
            {!detailUnit.summary &&
              (detailUnit.keywords?.length ?? 0) === 0 &&
              (detailUnit.sections?.length ?? 0) === 0 && (
                <p className="text-xs text-slate-400">
                  Node này chưa có nội dung làm giàu (sách nạp trước khi tính năng ra đời, hoặc tắt
                  "Làm giàu nội dung" khi nạp). Hãy nạp lại cuốn sách với bật "Làm giàu nội dung".
                </p>
              )}
          </div>
        </div>
      )}

      {/* Modal xác nhận xóa sách */}
      {bookToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="w-full max-w-md rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-xl border border-slate-200 dark:border-slate-800 space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-rose-100 dark:bg-rose-950/50 text-rose-600 dark:text-rose-400">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <h4 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Xác nhận xóa sách
                </h4>
                <p className="text-xs text-slate-500">
                  Thao tác này sẽ xóa vĩnh viễn và không thể khôi phục.
                </p>
              </div>
            </div>

            <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 p-3.5 text-xs text-slate-600 dark:text-slate-300 space-y-1.5 border border-slate-100 dark:border-slate-800">
              <p>
                <strong>Cuốn sách:</strong> {bookToDelete.title}
              </p>
              <p>
                <strong>Môn · Khối:</strong> {bookToDelete.subject_code} · Khối {bookToDelete.grade_number}
                {bookToDelete.semester_number ? ` · HK${bookToDelete.semester_number}` : ""}
              </p>
              <p className="text-rose-600 dark:text-rose-400 font-medium">
                ⚠️ Toàn bộ <strong>{bookToDelete.unit_count} node chương/bài</strong> thuộc cuốn sách này cùng các ma trận liên quan sẽ bị xóa sạch khỏi hệ thống.
              </p>
            </div>

            {deleteErr && (
              <p className="text-xs text-rose-600 dark:text-rose-400 flex items-center gap-1.5">
                <X className="w-3.5 h-3.5" /> {deleteErr}
              </p>
            )}

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                disabled={deletingBook}
                onClick={() => {
                  setBookToDelete(null);
                  setDeleteErr(null);
                }}
                className="px-4 py-2 rounded-xl text-xs font-semibold border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                disabled={deletingBook}
                onClick={confirmDeleteBook}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 transition-colors flex items-center gap-1.5 disabled:opacity-50"
              >
                {deletingBook ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                {deletingBook ? "Đang xóa..." : "Xác nhận xóa"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal xem danh sách cảnh báo của Job */}
      {selectedJobWarnings && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="w-full max-w-2xl max-h-[85vh] flex flex-col rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            {/* Header */}
            <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/30">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-100 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-800/60">
                  <AlertTriangle className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    Danh Sách Cảnh Báo Job #{selectedJobWarnings.jobId}
                    <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
                      {selectedJobWarnings.warnings.length} cảnh báo
                    </span>
                  </h4>
                  <p className="text-xs text-slate-500 truncate max-w-md" title={selectedJobWarnings.filename}>
                    File: <strong>{selectedJobWarnings.filename}</strong>
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedJobWarnings(null)}
                className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Search filter & Action bar */}
            <div className="p-4 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center gap-3">
              <input
                type="text"
                value={warningSearch}
                onChange={(e) => setWarningSearch(e.target.value)}
                placeholder="Lọc cảnh báo theo từ khóa (vd: Bài 2, JSON, trang...)..."
                className="flex-1 px-3.5 py-2 rounded-xl text-xs border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
              />
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(selectedJobWarnings.warnings.join("\n"));
                  setCopiedWarningIdx(-1);
                  setTimeout(() => setCopiedWarningIdx(null), 2000);
                }}
                className="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors shrink-0 cursor-pointer"
              >
                {copiedWarningIdx === -1 ? "Đã chép tất cả!" : "Sao chép tất cả"}
              </button>
            </div>

            {/* Warnings list body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-2.5 divide-y divide-slate-100 dark:divide-slate-800/60">
              {(() => {
                const filtered = selectedJobWarnings.warnings.filter((w) =>
                  w.toLowerCase().includes(warningSearch.toLowerCase())
                );
                if (filtered.length === 0) {
                  return (
                    <p className="text-xs text-slate-400 py-8 text-center">
                      Không tìm thấy cảnh báo nào khớp với "{warningSearch}".
                    </p>
                  );
                }
                return filtered.map((w, idx) => (
                  <div
                    key={idx}
                    className="pt-2.5 first:pt-0 flex items-start justify-between gap-3 group"
                  >
                    <div className="flex items-start gap-2.5 min-w-0">
                      <span className="w-6 h-6 rounded-md bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 font-mono text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5 border border-amber-200 dark:border-amber-800/50">
                        {idx + 1}
                      </span>
                      <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed break-words">
                        {w}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(w);
                        setCopiedWarningIdx(idx);
                        setTimeout(() => setCopiedWarningIdx(null), 2000);
                      }}
                      className="opacity-0 group-hover:opacity-100 px-2 py-1 rounded text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-slate-900 transition-all shrink-0 cursor-pointer"
                    >
                      {copiedWarningIdx === idx ? "Đã chép" : "Sao chép"}
                    </button>
                  </div>
                ));
              })()}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex items-center justify-end">
              <button
                type="button"
                onClick={() => setSelectedJobWarnings(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 hover:opacity-90 transition-opacity cursor-pointer"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Cắt Lát & Index Chunks (RAG) */}
      {bookToIndexChunks && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="w-full max-w-lg flex flex-col rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            {/* Header */}
            <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-purple-50/50 dark:bg-purple-950/20">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-purple-100 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400 border border-purple-200 dark:border-purple-800/60">
                  <Brain className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    Cắt Lát & Index Chunks (RAG)
                  </h4>
                  <p className="text-xs text-slate-500 truncate max-w-xs" title={bookToIndexChunks.title}>
                    Cuốn: <strong>{bookToIndexChunks.title}</strong> ({bookToIndexChunks.subject_code} · Khối {bookToIndexChunks.grade_number})
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => !reIndexingChunks && setBookToIndexChunks(null)}
                disabled={reIndexingChunks}
                className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-50 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Body */}
            <div className="p-5 space-y-4 text-xs">
              <div className="p-3 rounded-xl bg-purple-50/60 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800/60 text-purple-900 dark:text-purple-200 space-y-1">
                <div className="flex items-center gap-2 font-semibold">
                  <Sparkles className="w-4 h-4 text-purple-600 shrink-0" />
                  <span>Cắt lát bài học & Tạo Vector Embeddings</span>
                </div>
                <p className="text-slate-600 dark:text-slate-300 text-[11px] leading-relaxed">
                  Hệ thống sẽ lấy danh sách <strong>{units.length} node bài học</strong> đã có trong DB và cắt thành các chunks theo đề mục, sau đó nhúng vector RAG vào CSDL pgvector. <strong>Hoàn toàn KHÔNG quét lại mục lục</strong>, tiết kiệm tối đa chi phí.
                </p>
              </div>

              {/* VLM Model Selector */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Chọn Mô hình AI (VLM OCR nếu có trang scan):
                </label>
                <select
                  value={chunkModalVlmModel}
                  onChange={(e) => setChunkModalVlmModel(e.target.value)}
                  disabled={reIndexingChunks}
                  className="w-full px-3.5 py-2.5 rounded-xl text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-hidden focus:ring-2 focus:ring-purple-500 font-medium cursor-pointer"
                >
                  <optgroup label="OpenRouter (Khuyên dùng)">
                    <option value="google/gemini-3.7-flash">⚡ Google Gemini 3.7 Flash (Mới nhất, siêu rẻ & nhanh)</option>
                    <option value="xiaomi/mimo-v2.5">⚡ Xiaomi Mimo 2.5</option>
                    <option value="openai/gpt-4o-mini">⚡ OpenAI GPT-4o Mini</option>
                    <option value="qwen/qwen-2.5-vl-72b-instruct">⚡ Qwen 2.5 VL 72B Instruct</option>
                  </optgroup>
                  <optgroup label="ShopAIKey / DashScope">
                    <option value="qwen3-vl-flash">🇨🇳 Qwen 3 VL Flash (ShopAIKey)</option>
                  </optgroup>
                  <option value="custom">✏️ Tùy chỉnh Model ID...</option>
                </select>
              </div>

              {chunkModalVlmModel === "custom" && (
                <div className="space-y-1.5 animate-in fade-in duration-150">
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Nhập Model ID Tùy Chỉnh:
                  </label>
                  <input
                    type="text"
                    value={chunkModalCustomModel}
                    onChange={(e) => setChunkModalCustomModel(e.target.value)}
                    placeholder="Ví dụ: google/gemini-2.0-flash-001 hoặc qwen/qwen-vl-plus"
                    disabled={reIndexingChunks}
                    className="w-full px-3.5 py-2 rounded-xl text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-hidden focus:ring-2 focus:ring-purple-500"
                  />
                </div>
              )}

              {reIndexErr && (
                <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
                  <X className="w-4 h-4 shrink-0" />
                  <span>{reIndexErr}</span>
                </div>
              )}
            </div>

            {/* Footer Actions */}
            <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={() => setBookToIndexChunks(null)}
                disabled={reIndexingChunks}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors disabled:opacity-50 cursor-pointer"
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                onClick={handleExecuteIndexChunks}
                disabled={reIndexingChunks}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-purple-600 hover:bg-purple-700 text-white shadow-xs transition-colors flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
              >
                {reIndexingChunks ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Đang index vector RAG...</span>
                  </>
                ) : (
                  <>
                    <Brain className="w-3.5 h-3.5" />
                    <span>Bắt đầu Index Vector</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}