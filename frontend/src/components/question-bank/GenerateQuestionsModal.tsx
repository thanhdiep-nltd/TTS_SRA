"use client";

import { useEffect, useRef, useState } from "react";
import { Sparkles, X } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { BLOOM_OPTIONS, QUESTION_TYPE_LABELS, type QuestionItemListPage, type QuestionType } from "@/lib/types";
import ChapterLessonSelect from "../ChapterLessonSelect";
import SearchableSelect, { type Option } from "../SearchableSelect";

interface Props {
  subjectId: string;
  gradeNumber?: number;
  onClose: () => void;
  onGenerated: () => void;
  /** Gọi ngay khi request "/generate" được nhận (202) — để trang tự refresh ở cấp page, không
   * phụ thuộc việc modal này còn mở hay đã bị đóng (xem ghi chú ở question-bank/page.tsx). */
  onSubmitted?: () => void;
}

const QUESTION_TYPES: QuestionType[] = ["MCQ", "TRUE_FALSE", "SHORT_ANSWER", "ESSAY"];
const GRADE_OPTIONS: Option[] = [6, 7, 8, 9, 10, 11, 12].map((g) => ({ value: String(g), label: `Khối ${g}` }));
const POLL_INTERVAL_MS = 5_000;
const POLL_TIMEOUT_MS = 120_000;

type Phase = "form" | "waiting" | "done" | "timeout";

// Sinh câu hỏi bằng LLM+RAG. Endpoint trả 202 ngay (chạy nền) nên FE phải tự poll danh sách
// DRAFT mới để biết khi nào xong/thất bại — xem docs/exam_generation_ui_design.md mục C.3.
export default function GenerateQuestionsModal({
  subjectId, gradeNumber, onClose, onGenerated, onSubmitted,
}: Props) {
  const [unitId, setUnitId] = useState("");
  const [grade, setGrade] = useState(gradeNumber ? String(gradeNumber) : "");
  const [bloom, setBloom] = useState("2");
  const [qType, setQType] = useState<QuestionType>("MCQ");
  const [count, setCount] = useState("5");
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("form");
  const [createdCount, setCreatedCount] = useState(0);
  const startTimeRef = useRef(0);
  // Chặn double-submit (double-click) bằng ref, không dùng state: state là async/batched nên 2
  // click liên tiếp trong cùng tick có thể vẫn đọc được giá trị cũ trước khi re-render — ref đọc/
  // ghi đồng bộ ngay lập tức, chặn được chắc chắn. Đã từng gây sinh trùng + báo trùng 1 câu.
  const submittingRef = useRef(false);
  const [submitting, setSubmitting] = useState(false); // chỉ để disable nút hiển thị (UX)

  // Đổi Khối -> danh sách chương đổi -> chủ đề đã chọn có thể không còn hợp lệ.
  useEffect(() => {
    setUnitId("");
  }, [grade]);

  const canSubmit = !!unitId && !!grade;

  useEffect(() => {
    if (phase !== "waiting") return;
    const baseline = startTimeRef.current;
    const interval = setInterval(async () => {
      try {
        const res = await api.get<QuestionItemListPage>(
          `/question-bank/items?subject_id=${subjectId}&unit_id=${unitId}&bloom_level=${bloom}&status=DRAFT&limit=100`
        );
        const fresh = res.items.filter((i) => new Date(i.created_at).getTime() >= baseline);
        if (fresh.length > 0) {
          setCreatedCount(fresh.length);
          setPhase("done");
          onGenerated();
          clearInterval(interval);
          return;
        }
      } catch {
        // lỗi poll tạm thời — thử lại ở lần kế tiếp, không báo lỗi ồn ào
      }
      if (Date.now() - baseline > POLL_TIMEOUT_MS) {
        setPhase("timeout");
        clearInterval(interval);
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [phase, subjectId, unitId, bloom, onGenerated]);

  const handleSubmit = async () => {
    if (submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    setError(null);
    try {
      startTimeRef.current = Date.now();
      await api.post("/question-bank/generate", {
        subject_id: subjectId,
        grade_number: Number(grade),
        unit_id: unitId,
        bloom_level: Number(bloom),
        question_type: qType,
        count: Number(count),
      });
      setPhase("waiting");
      onSubmitted?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Sinh câu hỏi thất bại");
      submittingRef.current = false; // cho phép thử lại khi lỗi
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-accent-600" /> Sinh câu hỏi bằng AI
          </h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {phase === "form" && (
            <>
              {error && (
                <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
                  {error}
                </div>
              )}
              <p className="text-xs text-slate-500 dark:text-slate-400">
                AI sẽ tra cứu nội dung SGK và soạn câu hỏi DRAFT — vẫn cần người duyệt trước khi dùng ráp đề.
              </p>
              <SearchableSelect label="Khối" value={grade} onChange={setGrade} options={GRADE_OPTIONS} />
              <ChapterLessonSelect subjectId={subjectId} gradeNumber={grade} value={unitId} onChange={setUnitId} />
              <div className="grid grid-cols-2 gap-3">
                <SearchableSelect label="Mức Bloom" value={bloom} onChange={setBloom} options={BLOOM_OPTIONS} />
                <SearchableSelect
                  label="Loại câu"
                  value={qType}
                  onChange={(v) => setQType(v as QuestionType)}
                  options={QUESTION_TYPES.map((t) => ({ value: t, label: QUESTION_TYPE_LABELS[t] }))}
                />
              </div>
              <div className="w-32">
                <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Số câu</label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={count}
                  onChange={(e) => setCount(e.target.value)}
                  className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
                />
              </div>
            </>
          )}

          {phase === "waiting" && (
            <div className="py-8 flex flex-col items-center gap-3 text-center">
              <Sparkles className="w-8 h-8 text-accent-600 animate-pulse" />
              <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Đang sinh câu hỏi ở nền…</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Có thể mất 1-2 phút, bạn có thể đóng và chờ thông báo.
              </p>
            </div>
          )}

          {phase === "done" && (
            <div className="py-8 flex flex-col items-center gap-2 text-center">
              <p className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">
                ✅ Đã sinh thêm {createdCount} câu hỏi mới (DRAFT)
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Vào tab &quot;Chờ duyệt&quot; để xem và duyệt.</p>
            </div>
          )}

          {phase === "timeout" && (
            <div className="py-8 flex flex-col items-center gap-2 text-center">
              <p className="text-sm font-semibold text-accent-600 dark:text-accent-400">
                Không sinh được câu nào sau 2 phút
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                RAG có thể chưa có nội dung SGK cho chủ đề này. Hãy thử chủ đề khác hoặc tạo câu thủ công.
              </p>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-slate-200 dark:border-slate-800">
          {phase === "form" ? (
            <>
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Hủy
              </button>
              <button
                onClick={handleSubmit}
                disabled={!canSubmit || submitting}
                className="px-4 py-2 rounded-lg text-sm font-semibold bg-accent-600 text-white hover:bg-accent-700 disabled:opacity-50"
              >
                Sinh câu hỏi
              </button>
            </>
          ) : (
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm font-semibold bg-brand-600 text-white hover:bg-brand-700"
            >
              Đóng
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
