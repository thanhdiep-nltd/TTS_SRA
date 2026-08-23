"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardPaste,
  FileText,
  ImagePlus,
  Loader2,
  Sparkles,
  Trash2,
} from "lucide-react";
import SearchableSelect from "@/components/SearchableSelect";
import { api, ApiError } from "@/lib/api";
import type { QuestionClassifyResult } from "@/lib/types";

const GRADE_OPTIONS = [6, 7, 8, 9, 10, 11, 12].map((g) => ({ value: String(g), label: `Khối ${g}` }));
// Text VLM đọc được chỉ hiện tối đa N ký tự trong box (đủ để GV kiểm tra AI đọc đúng chưa).
const MAX_TEXT_CHARS = 600;

const BLOOM_LABELS: Record<number, string> = {
  1: "Nhớ",
  2: "Hiểu",
  3: "Vận dụng",
  4: "Phân tích",
  5: "Đánh giá",
  6: "Sáng tạo",
};

/**
 * Tab "Kiểm tra câu hỏi" (trang Phân tích độ khó đề thi TEVI).
 *
 * Test 1 CÂU HỎI (không phải 1 đề): chọn môn + khối → dán ảnh (Ctrl+V) hoặc upload
 * ảnh/PDF → AI đọc bằng VLM và xác định câu hỏi thuộc chương/bài nào của SGK đã nạp.
 * Không lưu gì vào DB — kết quả chỉ để GV kiểm tra nhanh.
 */
export default function QuestionTestTab() {
  const [subjects, setSubjects] = useState<{ code: string; name: string }[]>([]);
  const [subjectCode, setSubjectCode] = useState("");
  const [grade, setGrade] = useState("6");
  const [semester, setSemester] = useState<string>("1");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QuestionClassifyResult | null>(null);

  // Danh sách môn có trong danh mục chương trình (code = TOAN_6, VAN, ...) — khớp /curriculum/units.
  useEffect(() => {
    api
      .get<{ code: string; name: string }[]>("/curriculum/subjects")
      .then((subs) => {
        setSubjects(subs);
        const toan6 = subs.find((s) => s.code.toLowerCase().includes("toan_6")) || subs.find((s) => s.name.toLowerCase().includes("toán 6")) || subs.find((s) => s.code.toLowerCase().includes("toan"));
        if (toan6) setSubjectCode(toan6.code);
      })
      .catch(() => setSubjects([]));
  }, []);

  // Preview ảnh dán/chọn bằng object URL — thu hồi khi đổi file.
  useEffect(() => {
    if (!file || !file.type.startsWith("image/")) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // Thay file → xóa kết quả cũ (kết quả không còn khớp với câu hỏi mới).
  const setQuestionFile = useCallback((f: File | null) => {
    setFile(f);
    setResult(null);
    setError(null);
  }, []);

  // Dán ảnh Ctrl+V ở BẤT KỲ đâu trong tab (kể cả chưa click vào vùng upload).
  useEffect(() => {
    const onWindowPaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of Array.from(items)) {
        if (item.kind === "file" && item.type.startsWith("image/")) {
          const f = item.getAsFile();
          if (f) {
            setQuestionFile(f);
            e.preventDefault();
            return;
          }
        }
      }
    };
    window.addEventListener("paste", onWindowPaste);
    return () => window.removeEventListener("paste", onWindowPaste);
  }, [setQuestionFile]);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f && (f.type.startsWith("image/") || f.type === "application/pdf")) {
      setQuestionFile(f);
    } else {
      setError("Chỉ chấp nhận ảnh (PNG/JPEG/WebP) hoặc PDF của câu hỏi.");
    }
  };

  const handleClassify = async () => {
    if (!subjectCode) {
      setError("Vui lòng chọn môn học của câu hỏi.");
      return;
    }
    if (!grade) {
      setError("Vui lòng chọn khối của câu hỏi.");
      return;
    }
    if (!file) {
      setError("Vui lòng dán ảnh (Ctrl+V) hoặc chọn ảnh/PDF của câu hỏi trước.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("subject_code", subjectCode);
      fd.append("grade_number", grade);
      if (semester && semester !== "all") {
        fd.append("semester_number", semester);
      }
      fd.append("file", file);
      const res = await api.upload<QuestionClassifyResult>("/exam-difficulty/classify-question", fd);
      setResult(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Lỗi khi phân loại câu hỏi. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  };

  const subjectOptions = subjects.map((s) => ({ value: s.code, label: `${s.name} (${s.code})` }));
  const isPdf = !!file && file.type === "application/pdf";
  const textPreview =
    result && result.text.length > MAX_TEXT_CHARS ? `${result.text.slice(0, MAX_TEXT_CHARS)}…` : result?.text;

  return (
    <div className="space-y-6">
      {/* Giải thích ngắn */}
      <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 p-4 flex items-start gap-3 shadow-sm">
        <Sparkles className="w-5 h-5 text-brand-500 shrink-0 mt-0.5" />
        <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
          Dán (Ctrl+V) hoặc tải lên <b>1 ảnh / PDF của 1 câu hỏi</b> bất kỳ, chọn môn + khối + học kỳ — AI
          (VLM + LLM) sẽ đọc nội dung và xác định câu hỏi thuộc{" "}
          <b>chương nào (và bài nào) trong SGK đã nạp</b> cho môn/khối đó. Kết quả chỉ để kiểm tra
          nhanh, không lưu lại.
        </p>
      </div>

      {/* Bộ lọc môn + khối + học kỳ */}
      <div className="bg-white dark:bg-slate-900 border rounded-2xl p-4 flex flex-wrap items-end gap-3 shadow-sm">
        <div className="min-w-[220px] flex-1">
          <label className="text-xs font-semibold text-slate-500 mb-1 block">Môn học của câu hỏi</label>
          <SearchableSelect
            options={subjectOptions}
            value={subjectCode}
            onChange={(v) => {
              setSubjectCode(v);
              setResult(null);
            }}
            placeholder="Chọn môn..."
            className="min-w-[220px]"
          />
        </div>
        <div className="min-w-[130px]">
          <label className="text-xs font-semibold text-slate-500 mb-1 block">Khối</label>
          <SearchableSelect
            options={GRADE_OPTIONS}
            value={grade}
            onChange={(v) => {
              setGrade(v);
              setResult(null);
            }}
            placeholder="Chọn khối..."
            className="min-w-[130px]"
          />
        </div>
        <div className="min-w-[110px]">
          <label className="text-xs font-semibold text-slate-500 mb-1 block">Học kỳ</label>
          <SearchableSelect
            options={[
              { value: "1", label: "HK1" },
              { value: "2", label: "HK2" },
              { value: "all", label: "Cả năm" },
            ]}
            value={semester}
            onChange={(v) => {
              setSemester(v);
              setResult(null);
            }}
            placeholder="Học kỳ..."
            className="min-w-[110px]"
          />
        </div>
      </div>

      {/* Vùng dán / upload ảnh câu hỏi */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`relative rounded-2xl border-2 border-dashed p-6 flex flex-col items-center justify-center gap-3 text-center transition-colors cursor-pointer ${
          dragOver
            ? "border-brand-500 bg-brand-50/60 dark:bg-brand-950/40"
            : "border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-brand-400"
        }`}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,application/pdf"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0] ?? null;
            if (f) setQuestionFile(f);
            e.target.value = "";
          }}
        />

        {file && previewUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={previewUrl} alt="Câu hỏi" className="max-h-72 rounded-xl border border-slate-200 dark:border-slate-700" />
        ) : file && isPdf ? (
          <div className="flex items-center gap-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-4 py-3">
            <FileText className="w-6 h-6 text-rose-500" />
            <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{file.name}</span>
          </div>
        ) : (
          <>
            <div className="p-3 rounded-2xl bg-brand-50 dark:bg-brand-950/50 text-brand-600 dark:text-brand-400 border border-brand-100 dark:border-brand-900/50">
              <ClipboardPaste className="w-8 h-8" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Dán ảnh câu hỏi bằng <kbd className="px-1.5 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs">Ctrl+V</kbd>
              </p>
              <p className="text-xs text-slate-400 mt-1">
                hoặc kéo-thả / bấm để chọn ảnh (PNG, JPEG, WebP) · PDF 1 câu hỏi
              </p>
            </div>
          </>
        )}

        {file && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setQuestionFile(null);
            }}
            className="absolute top-3 right-3 p-1.5 rounded-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-400 hover:text-rose-600 hover:border-rose-300 transition-colors"
            title="Xóa ảnh câu hỏi"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Nút phân tích */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={handleClassify}
          disabled={loading}
          className="px-5 py-2.5 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" /> Đang phân loại...
            </>
          ) : (
            <>
              <ImagePlus className="w-4 h-4" /> Xác định chương
            </>
          )}
        </button>
        {loading && (
          <span className="text-xs text-slate-400">
            AI đang đọc ảnh và so khớp với chương/bài của SGK — thường mất 10–30 giây.
          </span>
        )}
      </div>

      {error && (
        <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 px-4 py-3 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </div>
      )}

      {/* Kết quả phân loại */}
      {result && (
        <section className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900 dark:text-slate-100">Kết quả phân loại</h3>
            {result.matched ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                <CheckCircle2 className="w-3.5 h-3.5" /> Khớp chương trình
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                <AlertTriangle className="w-3.5 h-3.5" /> Ngoài chương trình
              </span>
            )}
          </div>

          <div className="p-5 space-y-4">
            {result.matched && result.items.length > 0 ? (
              <div className="space-y-2.5">
                {result.items.map((it, i) => (
                  <div
                    key={i}
                    className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800"
                  >
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <span className="font-semibold text-slate-800 dark:text-slate-200">
                        {it.chapter}
                        {it.lesson ? (
                          <>
                            {" "}
                            <span className="text-slate-400">›</span>{" "}
                            <span className="text-brand-700 dark:text-brand-300">{it.lesson}</span>
                          </>
                        ) : null}
                      </span>
                      <span className="flex items-center gap-1.5 flex-wrap">
                        <span className="px-2 py-0.5 rounded-full bg-brand-50 dark:bg-brand-500/10 text-brand-700 dark:text-brand-300 text-[10px] font-bold">
                          Bloom {it.bloom_level} · {BLOOM_LABELS[it.bloom_level] ?? ""}
                        </span>
                        <span className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 text-[10px] font-bold">
                          {Math.round(it.weight * 100)}%
                        </span>
                        {it.confidence != null && (
                          <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300 text-[10px] font-bold">
                            Tin cậy {(it.confidence * 100).toFixed(0)}%
                          </span>
                        )}
                      </span>
                    </div>
                    {it.topic && (
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5 line-clamp-2">{it.topic}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-3.5 rounded-xl bg-amber-50/70 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 text-sm text-amber-700 dark:text-amber-300">
                Không tìm thấy chương/bài nào khớp câu hỏi này trong SGK đã nạp cho môn/khối đã chọn
                (câu hỏi có thể ngoài chương trình, hoặc sách chưa nạp đủ).
                {result.candidates.length > 0 && (
                  <div className="mt-2 text-xs">
                    <span className="font-semibold">Node gần nhất để rà soát: </span>
                    {result.candidates.join(" · ")}
                  </div>
                )}
              </div>
            )}

            {result.text.trim() && (
              <div className="pt-3 border-t border-slate-100 dark:border-slate-800">
                <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                  Nội dung AI đọc được từ ảnh
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 whitespace-pre-wrap break-words max-h-40 overflow-y-auto bg-slate-50 dark:bg-slate-800/40 rounded-lg p-3">
                  {textPreview}
                  {result.text.length > MAX_TEXT_CHARS && (
                    <span className="text-slate-400"> (hiển thị {MAX_TEXT_CHARS} ký tự đầu)</span>
                  )}
                </p>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
