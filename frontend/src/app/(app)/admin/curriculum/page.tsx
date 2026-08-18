"use client";

import { useCallback, useEffect, useState } from "react";
import {
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
  description: string | null;
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
}

interface IngestedChapter {
  code: string;
  name: string;
  semester_number: number | null;
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
  dry_run: boolean;
}

const SUBJECT_OPTIONS = [
  { value: "TOAN", label: "Toán (TOAN)" },
  { value: "VAN", label: "Ngữ văn (VAN)" },
  { value: "KHTN", label: "Khoa học tự nhiên (KHTN)" },
  { value: "LY", label: "Vật lý (LY)" },
  { value: "HOA", label: "Hóa học (HOA)" },
  { value: "SINH", label: "Sinh học (SINH)" },
];

export default function AdminCurriculumPage() {
  const [subjectCode, setSubjectCode] = useState("TOAN");
  const [grade, setGrade] = useState("");
  const [semester, setSemester] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);

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
  const [includeLessons, setIncludeLessons] = useState(false);
  const [bookPreview, setBookPreview] = useState<BookIngestResult | null>(null);
  const [bookUploading, setBookUploading] = useState(false);
  const [bookMsg, setBookMsg] = useState<string | null>(null);
  const [bookErr, setBookErr] = useState<string | null>(null);

  const fetchUnits = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ subject_code: subjectCode });
      if (grade) params.set("grade", grade);
      if (semester) params.set("semester", semester);
      if (includeInactive) params.set("include_inactive", "true");
      const rows = await api.get<CurriculumUnitRow[]>(`/curriculum/units?${params.toString()}`);
      setUnits(rows || []);
    } catch (e: any) {
      setError(e?.message ?? "Không tải được danh sách chương trình.");
      setUnits([]);
    } finally {
      setLoading(false);
    }
  }, [subjectCode, grade, semester, includeInactive]);

  useEffect(() => {
    fetchUnits();
  }, [fetchUnits]);

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
      fetchUnits();
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
    setBookMsg(null);
    const formData = new FormData();
    formData.append("file", bookFile);
    formData.append("subject_code", subjectCode);
    formData.append("grade", bookGrade);
    if (bookSemester) formData.append("semester", bookSemester);
    if (includeLessons) formData.append("include_lessons", "true");
    formData.append("dry_run", "true");
    try {
      const res = await api.upload<BookIngestResult>("/curriculum/ingest-book", formData);
      setBookPreview(res);
      setBookMsg(
        "Trích xuất " + res.chapters.length + " chương (nguồn: " + res.source + ") — kiểm tra cây bên dưới rồi bấm \"Lưu vào bảng\"."
      );
    } catch (e: any) {
      setBookErr(e?.message ?? "Trích xuất mục lục thất bại.");
    } finally {
      setBookUploading(false);
    }
  };

  const handleBookSave = async () => {
    if (!bookPreview || !bookPreview.chapters.length) {
      setBookErr("Chưa có cây chương/bài để lưu — hãy bấm \"Trích xuất\" trước.");
      return;
    }
    setBookUploading(true);
    setBookErr(null);
    setBookMsg(null);
    const formData = new FormData();
    formData.append("catalog", JSON.stringify(bookPreview.chapters));
    formData.append("subject_code", subjectCode);
    formData.append("grade", bookGrade);
    if (bookSemester) formData.append("semester", bookSemester);
    try {
      const res = await api.upload<BookIngestResult>("/curriculum/ingest-book/commit", formData);
      setBookPreview(res);
      setBookMsg(
        "Đã lưu " + res.inserted + " chương/bài mới, cập nhật " + res.updated + ", ẩn " +
        res.hidden_placeholders + " placeholder (nguồn: " + res.source + "). Lưu chạy nhanh vì không trích lại file."
      );
      fetchUnits();
    } catch (e: any) {
      setBookErr(e?.message ?? "Lưu vào bảng thất bại.");
    } finally {
      setBookUploading(false);
    }
  };

  const handleToggle = async (unit: CurriculumUnitRow) => {
    try {
      await api.post<CurriculumUnitRow>(`/curriculum/units/${unit.id}/toggle-active`);
      fetchUnits();
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
          onClick={fetchUnits}
          disabled={loading}
          className="px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
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
              options={SUBJECT_OPTIONS}
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
          Upload chính file SGK (<strong>PDF/DOCX/TXT/MD</strong>). Hệ thống đọc mục lục (bookmark PDF
          → text-layer → VLM nếu cần), sinh node chương và bài con. <strong>Bấm &quot;Trích xuất&quot;</strong> để xem
          trước cây dự kiến rồi mới <strong>lưu</strong>.
        </p>
        <div className="flex flex-wrap items-end gap-3">
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
        {bookPreview && bookPreview.chapters.length > 0 && (
          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/40 p-3 max-h-64 overflow-y-auto space-y-1.5">
            {bookPreview.chapters.map((ch) => (
              <div key={ch.code}>
                <div className="text-xs font-semibold text-brand-600 dark:text-brand-400">
                  <span className="font-mono">{ch.code}</span> — {ch.name}
                  {ch.semester_number ? ` (HK${ch.semester_number})` : ""}
                </div>
                {ch.lessons.length > 0 && (
                  <div className="ml-4 text-[11px] text-slate-500 dark:text-slate-400 space-y-0.5 mt-0.5">
                    {ch.lessons.map((lesson) => (
                      <div key={lesson.code}>
                        <span className="font-mono">{lesson.code}</span> — {lesson.name}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
      {/* Bộ lọc */}
      <section className="bg-white dark:bg-slate-900 border rounded-2xl p-4 flex flex-wrap items-end gap-3 shadow-sm">
        <div className="min-w-[200px]">
          <label className="text-xs font-semibold text-slate-500 mb-1 block">Môn học</label>
          <SearchableSelect
            options={SUBJECT_OPTIONS}
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

      {error && (
        <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 px-4 py-3 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </div>
      )}

      {/* Bảng */}
      <section className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <h3 className="font-semibold text-slate-900 dark:text-slate-100">Danh sách node chương/bài</h3>
          <span className="text-xs text-slate-400">{units.length} node</span>
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
                  <td colSpan={7} className="px-5 py-10 text-center text-sm text-slate-400">
                    Không có node nào cho bộ lọc hiện tại (môn phải có trong s360.dim_subject, vd TOAN_6).
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}