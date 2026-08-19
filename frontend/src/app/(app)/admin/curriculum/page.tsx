"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  FileUp,
  FolderTree,
  Loader2,
  RefreshCw,
  UploadCloud,
  X,
} from "lucide-react";
import SearchableSelect from "@/components/SearchableSelect";
import { api } from "@/lib/api";

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
  filename: string | null;
  unit_count: number;
  created_at: string | null;
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
}

interface IngestedChapter {
  code: string;
  name: string;
  semester_number: number | null;
  is_phu: boolean;
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

export default function AdminCurriculumPage() {
  const [subjectCode, setSubjectCode] = useState("TOAN_6");
  const [grade, setGrade] = useState("");
  const [semester, setSemester] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [subjectOptions, setSubjectOptions] = useState(FALLBACK_SUBJECT_OPTIONS);

  // Chế độ xem: "books" = danh sách sách; "nodes" = node của 1 cuốn đang chọn
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
  const [bookSemester, setBookSemester] = useState(""); // "" = tự đoán từ tên file
  const [bookTitle, setBookTitle] = useState(""); // Tên cuốn / Chương - Tập - Mô tả
  const [includeLessons, setIncludeLessons] = useState(false);
  const [bookPreview, setBookPreview] = useState<BookIngestResult | null>(null);
  const [bookJobId, setBookJobId] = useState<number | null>(null);
  const [bookUploading, setBookUploading] = useState(false);
  const [bookMsg, setBookMsg] = useState<string | null>(null);
  const [bookErr, setBookErr] = useState<string | null>(null);

  // Lịch sử nạp sách (job queue, poll như EWS)
  const [ingestJobs, setIngestJobs] = useState<BookIngestJob[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);

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

  // Tải danh sách sách (view "books") — lọc theo môn/khối như cũ
  const fetchBooks = useCallback(async () => {
    setBooksLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (subjectCode) params.set("subject_code", subjectCode);
      if (grade) params.set("grade", grade);
      const rows = await api.get<CurriculumBookRow[]>(`/curriculum/books?${params.toString()}`);
      setBooks(rows || []);
    } catch (e: any) {
      setError(e?.message ?? "Không tải được danh sách sách.");
      setBooks([]);
    } finally {
      setBooksLoading(false);
    }
  }, [subjectCode, grade]);

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

  // Poll lịch sử khi có job đang pending/processing (như EWS)
  useEffect(() => {
    const active = ingestJobs.some((j) => j.status === "pending" || j.status === "processing");
    if (!active) return;
    const timer = setInterval(() => {
      loadIngestJobs();
    }, 3000);
    return () => clearInterval(timer);
  }, [ingestJobs, loadIngestJobs]);

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


  const handleBookExtract = async () => {
    if (!bookFile) {
      setBookErr("Vui lòng chọn file sách giáo khoa (PDF/DOCX/TXT/MD).");
      return;
    }
    setBookUploading(true);
    setBookErr(null);
    setBookMsg("Đang gửi file và trích xuất mục lục (VLM chạy nền, mất ~30s–2 phút)...");
    setBookPreview(null);
    setBookJobId(null);
    const formData = new FormData();
    formData.append("file", bookFile);
    formData.append("subject_code", subjectCode);
    formData.append("grade", bookGrade);
    if (bookSemester) formData.append("semester", bookSemester);
    if (bookTitle.trim()) formData.append("book_title", bookTitle.trim());
    if (includeLessons) formData.append("include_lessons", "true");
    formData.append("dry_run", "true");
    try {
      const job = await api.upload<BookIngestJob>("/curriculum/ingest-book", formData);
      setBookJobId(job.job_id);
      loadIngestJobs();
      // Poll job (tối đa ~3 phút) — không giữ request đồng bộ 5 phút
      const deadline = Date.now() + 180_000;
      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const st = await api.get<BookIngestJob>(`/curriculum/ingest-book/jobs/${job.job_id}`);
        if (st.status === "completed" && st.result) {
          setBookPreview(st.result);
          setBookMsg(
            "Trích xuất " + st.result.chapters.length + " chương (nguồn: " + st.result.source + ") — kiểm tra cây bên dưới rồi bấm \"Lưu vào bảng\"."
          );
          setBookUploading(false);
          return;
        }
        if (st.status === "failed") {
          setBookErr(st.error ?? "Trích xuất mục lục thất bại.");
          setBookUploading(false);
          return;
        }
      }
      setBookErr("Trích xuất quá lâu (>3 phút) — kiểm tra VLM_API_KEY/provider rồi thử lại.");
    } catch (e: any) {
      setBookErr(e?.message ?? "Gửi file trích xuất thất bại.");
    } finally {
      setBookUploading(false);
      loadIngestJobs();
    }
  };

  const handleBookSave = async () => {
    if (!bookPreview || !bookPreview.chapters.length) {
      setBookErr("Chưa có cây chương/bài để lưu — hãy bấm \"Trích xuất\" trước.");
      return;
    }
    if (!bookJobId) {
      setBookErr("Thiếu mã job — hãy bấm \"Trích xuất\" lại.");
      return;
    }
    setBookUploading(true);
    setBookErr(null);
    setBookMsg(null);
    const formData = new FormData();
    formData.append("job_id", String(bookJobId));
    try {
      const res = await api.upload<BookIngestResult>("/curriculum/ingest-book/commit", formData);
      setBookPreview(res);
      setBookMsg(
        "Đã lưu " + res.inserted + " chương/bài mới, cập nhật " + res.updated + ", ẩn " +
        res.hidden_placeholders + " placeholder (nguồn: " + res.source + "). Lưu chạy nhanh vì không trích lại file."
      );
      fetchUnits();
      loadIngestJobs();
      // Đang xem danh sách sách thì làm mới cả list sách (số node thay đổi)
      if (view === "books") fetchBooks();
    } catch (e: any) {
      setBookErr(e?.message ?? "Lưu vào bảng thất bại.");
    } finally {
      setBookUploading(false);
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

  return (
    <div className="p-6 md:p-8 max-w-[1400px] mx-auto space-y-6">
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-brand-50 dark:bg-brand-950/50 text-brand-600 dark:text-brand-400 border border-brand-100 dark:border-brand-900/50">
              <FolderTree className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
              Quản lý Chương trình học (Catalog phẳng)
            </h2>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Bảng <code className="text-xs">curriculum_units</code> — bộ xương chương trình (chương/bài) để LLM map câu hỏi đề thi.
          </p>
        </div>
        <button
          onClick={refreshCurrentView}
          disabled={loading || booksLoading}
          className="px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${loading || booksLoading ? "animate-spin" : ""}`} />
          Làm mới
        </button>
      </header>

      {/* Banner: KHÔNG RAG */}
      <div className="flex items-start gap-2.5 rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">
        <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
        <span>
          <strong>Không dùng RAG:</strong> dữ liệu ghi thẳng vào bảng{" "}
          <code className="text-xs">curriculum_units</code>, không đi qua Qdrant/Airflow. RAG chỉ phục vụ
          chat hỏi đáp SGK (trang &quot;Kho tri thức &amp; SGK&quot;).
        </span>
      </div>

      {/* Upload */}
      <section className="bg-white dark:bg-slate-900 border rounded-2xl p-5 shadow-sm space-y-3">
        <h3 className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <UploadCloud className="w-4 h-4 text-brand-500" />
          Tải lên mục lục chương trình (không RAG)
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Nhận file <strong>JSON</strong> (định dạng catalog) hoặc <strong>markdown mục lục SGK</strong>{" "}
          (dạng &quot;## LỚP 6 / ### Tập 1 / * **Chương I: Tên** / mô tả&quot;). Upsert theo mã node — chạy lại an toàn.
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


      {/* Nạp sách giáo khoa — tự tách mục lục thành node */}
      <section className="bg-white dark:bg-slate-900 border rounded-2xl p-5 shadow-sm space-y-3">
        <h3 className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-brand-500" />
          Nạp sách giáo khoa — pipeline tự tách chương/bài (không RAG)
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Upload chính file SGK (<strong>PDF/DOCX/TXT/MD</strong>). Với PDF, VLM (Qwen3-VL-Flash) nhìn
          ảnh trang mục lục và xuất cây chương/bài; DOCX dùng heading; TXT/MD dùng dòng mục lục.
          <strong>Bấm &quot;Trích xuất&quot;</strong> để xem trước cây dự kiến (kèm cảnh báo) rồi mới <strong>lưu</strong>.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[200px]">
            <label className="text-xs font-semibold text-slate-500 mb-1 block">
              Môn học <span className="text-rose-500">*</span>
            </label>
            <SearchableSelect
              options={subjectOptions}
              value={subjectCode}
              onChange={(v) => {
                setSubjectCode(v);
                // Môn dạng TOAN_6/TOAN_7... đã gắn khối trong mã → tự đồng bộ ô Khối lớp
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
          <label className="flex items-center gap-2 cursor-pointer pb-2.5 text-xs font-medium text-slate-700 dark:text-slate-300">
            <input
              type="checkbox"
              checked={includeLessons}
              onChange={(e) => setIncludeLessons(e.target.checked)}
              className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            <span>Tách cả bài con (BÀI n)</span>
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
                setBookPreview(null);
                setBookErr(null);
              }}
            />
          </label>
          <button
            onClick={handleBookExtract}
            disabled={bookUploading || !bookFile}
            className="px-4 py-2.5 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2"
          >
            {bookUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <BookOpen className="w-4 h-4" />}
            {bookUploading ? "Đang trích xuất..." : "Trích xuất"}
          </button>
          <button
            onClick={handleBookSave}
            disabled={bookUploading || !bookPreview}
            className="px-4 py-2.5 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-2"
          >
            <UploadCloud className="w-4 h-4" />
            Lưu vào bảng
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
        {bookPreview && bookPreview.warnings.length > 0 && (
          <div className="rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 px-3 py-2 text-xs text-amber-700 dark:text-amber-300 space-y-1">
            {bookPreview.warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                <span>{w}</span>
              </div>
            ))}
          </div>
        )}
        {bookPreview && bookPreview.chapters.length > 0 && (
          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/40 p-3 max-h-64 overflow-y-auto space-y-1.5">
            {bookPreview.chapters.map((ch) => (
              <div key={ch.code}>
                <div className="text-xs font-semibold text-brand-600 dark:text-brand-400">
                  <span className="font-mono">{ch.code}</span> — {ch.name}
                  {ch.is_phu && (
                    <span className="ml-1.5 inline-flex px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300">
                      Phụ
                    </span>
                  )}
                  {ch.semester_number ? ` (HK${ch.semester_number})` : ""}
                </div>
                {ch.lessons.length > 0 && (
                  <div className="ml-4 text-[11px] text-slate-500 dark:text-slate-400 space-y-0.5 mt-0.5">
                    {ch.lessons.map((lesson) => (
                      <div key={lesson.code}>
                        <span className="font-mono">{lesson.code}</span> — {lesson.name}
                        {lesson.is_phu && (
                          <span className="ml-1.5 inline-flex px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300">
                            Phụ
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
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
          Mỗi lần &quot;Trích xuất&quot; tạo một job chạy nền (DB-backed queue, 1 job/lúc theo FIFO). Bạn có thể rời
          đi; khi xong kết quả tự cập nhật tại đây — giống &quot;Lịch sử dự đoán&quot; của EWS.
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
                  <th className="px-4 py-2.5">Kết quả / Lỗi</th>
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
                        {j.book_title || "—"}
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
                      <td className="px-4 py-2.5 text-xs text-slate-500 max-w-[200px] truncate" title={j.error ?? (j.result ? `${j.result.inserted} mới · ${j.result.updated} cập nhật` : "")}>
                        {j.status === "failed" ? (
                          <span className="text-rose-600 dark:text-rose-400">{j.error ?? "Thất bại"}</span>
                        ) : j.result ? (
                          <span className="text-emerald-600 dark:text-emerald-400">
                            {j.result.chapters.length} chương · {j.result.inserted} mới · {j.result.updated} cập nhật
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

      {/* Bộ lọc (chỉ hiển thị ở view danh sách sách; khi xem node của 1 cuốn thì ẩn) */}
      {view === "books" && (
        <section className="bg-white dark:bg-slate-900 border rounded-2xl p-4 flex flex-wrap items-end gap-3 shadow-sm">
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

      {error && (
        <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 px-4 py-3 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </div>
      )}

      {/* ===== View: danh sách sách (mặc định) ===== */}
      {view === "books" && (
        <section className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900 dark:text-slate-100">Danh sách sách giáo khoa</h3>
            <span className="text-xs text-slate-400">{books.length} cuốn</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                  <th className="px-5 py-3">Tên cuốn</th>
                  <th className="px-5 py-3">Môn</th>
                  <th className="px-5 py-3 text-center">Khối</th>
                  <th className="px-5 py-3 text-center">HK</th>
                  <th className="px-5 py-3 text-center">Số node</th>
                  <th className="px-5 py-3">File nguồn</th>
                  <th className="px-5 py-3">Tạo lúc</th>
                  <th className="px-5 py-3 text-center">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                {books.map((b) => (
                  <tr key={b.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                    <td className="px-5 py-3 font-medium text-slate-800 dark:text-slate-200">
                      <span className="inline-flex items-center gap-1.5">
                        <BookOpen className="w-3.5 h-3.5 text-brand-500 shrink-0" />
                        {b.title}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-xs text-slate-500">{b.subject_code}</td>
                    <td className="px-5 py-3 text-center text-xs text-slate-500">{b.grade_number}</td>
                    <td className="px-5 py-3 text-center text-xs text-slate-500">
                      {b.semester_number ? `HK${b.semester_number}` : "—"}
                    </td>
                    <td className="px-5 py-3 text-center text-xs text-slate-500">{b.unit_count}</td>
                    <td className="px-5 py-3 text-xs text-slate-500 truncate max-w-[200px]" title={b.filename ?? ""}>
                      {b.filename ?? "—"}
                    </td>
                    <td className="px-5 py-3 text-xs text-slate-400 font-mono whitespace-nowrap">
                      {b.created_at ? new Date(b.created_at).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" }) : "—"}
                    </td>
                    <td className="px-5 py-3 text-center">
                      <button
                        onClick={() => openBook(b)}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-50 dark:bg-brand-950/50 text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-900 hover:bg-brand-100 dark:hover:bg-brand-900/40 transition-colors"
                      >
                        Xem node
                      </button>
                    </td>
                  </tr>
                ))}
                {books.length === 0 && !booksLoading && (
                  <tr>
                    <td colSpan={8} className="px-5 py-10 text-center text-sm text-slate-400">
                      Chưa có cuốn sách nào cho bộ lọc hiện tại — hãy dùng "Nạp sách giáo khoa" ở trên rồi bấm Lưu.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
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
            <span className="text-xs text-slate-400 shrink-0">{units.length} node</span>
          </div>
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
                {units.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                    <td className="px-5 py-3 font-mono text-xs text-brand-600 dark:text-brand-400">{u.code}</td>
                    <td className="px-5 py-3 font-medium text-slate-800 dark:text-slate-200">
                      {u.name}
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
                    <td className="px-5 py-3 text-center">
                      <button
                        onClick={() => handleToggle(u)}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors"
                        title={u.is_active ? "Ẩn khỏi shortlist map" : "Kích hoạt lại"}
                      >
                        {u.is_active ? "Ẩn" : "Kích hoạt"}
                      </button>
                    </td>
                  </tr>
                ))}
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
  );
}