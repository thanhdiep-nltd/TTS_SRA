"use client";

import { useEffect, useState } from "react";
import { Loader2, Upload, X } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { ExamPaper, ExamRef, GradebookColumn } from "@/lib/types";

interface Props {
  column: GradebookColumn;       // cột đang map (category + index + label)
  subjectId: string;
  semesterId: string;
  classId: string;               // cho REGULAR (TX)
  gradeId: string;               // cho MIDTERM/FINAL
  existing?: ExamRef;            // đề đang map (nếu "Đổi")
  onClose: () => void;
  onChanged: () => void;         // reload gradebook sau khi map thành công
}

type Tab = "existing" | "upload";

// Modal chọn/upload đề rồi map vào một cột của bảng điểm.
export default function MapExamModal({
  column, subjectId, semesterId, classId, gradeId, existing, onClose, onChanged,
}: Props) {
  const [tab, setTab] = useState<Tab>("existing");
  const [papers, setPapers] = useState<ExamPaper[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // form upload
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    api
      .get<ExamPaper[]>(`/exam-papers?subject_id=${subjectId}&semester_id=${semesterId}`)
      .then(setPapers)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Lỗi tải danh sách đề thi"));
  }, [subjectId, semesterId]);

  // Gỡ map cũ (nếu có) rồi tạo map mới cho đề được chọn.
  const mapPaper = async (examPaperId: string) => {
    setError(null);
    setBusy(true);
    try {
      if (existing) await api.del(`/scores/mappings/${existing.mapping_id}`);
      await api.post("/scores/mappings", {
        subject_id: subjectId,
        semester_id: semesterId,
        score_category: column.category,
        column_index: column.index,
        exam_paper_id: examPaperId,
        class_id: column.category === "REGULAR" ? classId : null,
        grade_id: column.category === "REGULAR" ? null : gradeId,
      });
      onChanged();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Liên kết đề thi thất bại");
      setBusy(false);
    }
  };

  const uploadAndMap = async () => {
    if (!file || !title.trim()) {
      setError("Vui lòng nhập tên đề thi và chọn tệp tin đề thi.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const form = new FormData();
      form.set("subject_id", subjectId);
      form.set("semester_id", semesterId);
      form.set("title", title.trim());
      if (column.category !== "REGULAR") form.set("grade_id", gradeId);
      form.set("file", file);
      const paper = await api.upload<ExamPaper>("/exam-papers", form);
      await mapPaper(paper.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Tải đề thi lên thất bại");
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-white">
              {existing ? "Thay đổi đề thi" : "Liên kết đề thi"} — Cột điểm {column.label}
            </h3>
            {existing && (
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Đề thi đang sử dụng: {existing.title}</p>
            )}
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        <div className="flex border-b border-slate-200 dark:border-slate-800">
          {(["existing", "upload"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px ${
                tab === t
                  ? "border-brand-600 text-brand-600 dark:text-brand-400"
                  : "border-transparent text-slate-500 dark:text-slate-400"
              }`}
            >
              {t === "existing" ? "Đề thi có sẵn" : "Tải lên đề thi mới"}
            </button>
          ))}
        </div>

        {error && (
          <div className="mx-5 mt-4 p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
            {error}
          </div>
        )}

        <div className="p-5 overflow-y-auto">
          {tab === "existing" ? (
            papers.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400 text-center py-8">
                Chưa có đề thi nào cho môn học và học kỳ này. Vui lòng chuyển sang tab “Tải lên đề thi mới”.
              </p>
            ) : (
              <ul className="space-y-2">
                {papers.map((p) => (
                  <li key={p.id}>
                    <button
                      disabled={busy}
                      onClick={() => mapPaper(p.id)}
                      className="w-full text-left px-3 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-brand-500 hover:bg-brand-50 dark:hover:bg-brand-500/10 disabled:opacity-50 flex items-center justify-between gap-2"
                    >
                      <span className="text-sm font-medium text-slate-800 dark:text-slate-100 truncate">{p.title}</span>
                      <span className="text-[10px] uppercase shrink-0 px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                        {p.file_type ?? "FILE"}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )
          ) : (
            <div className="space-y-4">
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Tên đề thi</label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder={`VD: Đề kiểm tra ${column.label} môn ...`}
                  className="px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 text-sm outline-none focus:border-brand-500"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Tệp tin đề thi (PDF/Word/Ảnh, dung lượng tối đa 20MB)</label>
                <input
                  type="file"
                  accept=".pdf,.doc,.docx,image/*"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="text-sm text-slate-600 dark:text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-brand-600 file:text-white file:text-sm file:font-medium hover:file:bg-brand-700"
                />
              </div>
              <button
                disabled={busy}
                onClick={uploadAndMap}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                Tải lên và liên kết với cột điểm {column.label}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
