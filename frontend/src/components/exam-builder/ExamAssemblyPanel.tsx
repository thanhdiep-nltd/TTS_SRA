"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, ChevronDown, ChevronUp, Eye, EyeOff, Printer } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import {
  GEN_EXAM_STATUS_LABELS,
  type AssembledItemRead,
  type BlueprintCreate,
  type BlueprintRead,
  type GeneratedExamDetail,
  type GeneratedExamRead,
  type VariantAnswerRead,
} from "@/lib/types";

interface Props {
  /** Ma trận ĐÃ LƯU (sửa ma trận có sẵn) — null nếu đang ở luồng tạo mới chưa ráp đề lần nào. */
  blueprint: BlueprintRead | null;
  /** Dữ liệu ma trận CHƯA LƯU (tạo mới) — chỉ thật sự POST /exam-blueprints khi ráp đề LẦN ĐẦU
   * thành công, tránh để lại ma trận rác nếu GV bỏ dở ở bước này. */
  draft: BlueprintCreate | null;
  semesterId: string;
  gradeId: string;
  canReview: boolean;
  /** Báo cho trang cha khi draft vừa được lưu thật lần đầu (để cập nhật activeBlueprint + làm
   * mới danh sách "ma trận đã có"). */
  onBlueprintSaved: (blueprint: BlueprintRead) => void;
}

export default function ExamAssemblyPanel({ blueprint, draft, semesterId, gradeId, canReview, onBlueprintSaved }: Props) {
  const [numVariants, setNumVariants] = useState("2");
  const [savedBlueprint, setSavedBlueprint] = useState<BlueprintRead | null>(blueprint);
  const [history, setHistory] = useState<GeneratedExamRead[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [activeExam, setActiveExam] = useState<GeneratedExamDetail | null>(null);
  const [activeVariant, setActiveVariant] = useState("");
  const [answerKey, setAnswerKey] = useState<VariantAnswerRead[] | null>(null);
  const [showAnswer, setShowAnswer] = useState(false);
  const [assembling, setAssembling] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!savedBlueprint) {
      setHistory([]);
      return;
    }
    api
      .get<GeneratedExamRead[]>(`/exams?subject_id=${savedBlueprint.subject_id}`)
      .then((rows) => setHistory(rows.filter((r) => r.blueprint_id === savedBlueprint.id)))
      .catch(() => setHistory([]));
  }, [savedBlueprint]);

  const loadDetail = async (id: string) => {
    setError(null);
    try {
      const detail = await api.get<GeneratedExamDetail>(`/exams/${id}`);
      setActiveExam(detail);
      setActiveVariant(detail.variants[0]?.variant_code ?? "");
      setAnswerKey(null);
      setShowAnswer(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không tải được đề đã ráp");
    }
  };

  const handleAssemble = async () => {
    setAssembling(true);
    setError(null);
    let bp = savedBlueprint;
    let justCreated = false;
    try {
      if (!bp) {
        if (!draft) throw new Error("Thiếu dữ liệu ma trận để ráp đề");
        bp = await api.post<BlueprintRead>("/exam-blueprints", draft);
        justCreated = true;
      }
      const gen = await api.post<GeneratedExamRead>("/exams/assemble", {
        blueprint_id: bp.id,
        semester_id: semesterId,
        grade_id: gradeId,
        num_variants: Number(numVariants),
      });
      setSavedBlueprint(bp);
      if (justCreated) onBlueprintSaved(bp);
      setHistory((prev) => [gen, ...prev]);
      await loadDetail(gen.id);
    } catch (e) {
      // Ráp đề thất bại NGAY LẦN ĐẦU (thiếu câu trong kho...) -> dọn ma trận vừa tạo, không để
      // lại rác chưa ai dùng tới (đúng yêu cầu "chỉ lưu khi ráp đề thành công").
      if (justCreated && bp) {
        api.del(`/exam-blueprints/${bp.id}`).catch(() => {});
      }
      setError(e instanceof ApiError ? e.message : "Ráp đề thất bại — có thể thiếu câu trong kho");
    } finally {
      setAssembling(false);
    }
  };

  const handleFinalize = async () => {
    if (!activeExam) return;
    setFinalizing(true);
    setError(null);
    try {
      const updated = await api.post<GeneratedExamRead>(`/exams/${activeExam.id}/finalize`);
      setActiveExam((prev) => (prev ? { ...prev, status: updated.status, exam_paper_id: updated.exam_paper_id } : prev));
      setHistory((prev) => prev.map((g) => (g.id === updated.id ? updated : g)));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Chốt đề thất bại");
    } finally {
      setFinalizing(false);
    }
  };

  const toggleAnswer = async () => {
    if (!activeExam) return;
    if (showAnswer) {
      setShowAnswer(false);
      return;
    }
    setError(null);
    try {
      const keys = answerKey ?? (await api.get<VariantAnswerRead[]>(`/exams/${activeExam.id}/answer-key`));
      setAnswerKey(keys);
      setShowAnswer(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không xem được đáp án");
    }
  };

  const currentVariant = activeExam?.variants.find((v) => v.variant_code === activeVariant) ?? null;
  const answerMap = useMemo(() => {
    const variant = answerKey?.find((v) => v.variant_code === activeVariant);
    return new Map((variant?.items ?? []).map((i) => [i.item_id, i]));
  }, [answerKey, activeVariant]);

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
          {error}
        </div>
      )}

      {history.length > 0 && (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <button
            type="button"
            onClick={() => setShowHistory((s) => !s)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-200"
          >
            Đề đã ráp trước đây ({history.length})
            {showHistory ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {showHistory && (
            <div className="border-t border-slate-100 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800">
              {history.map((g) => (
                <button
                  key={g.id}
                  onClick={() => loadDetail(g.id)}
                  className={`w-full flex items-center justify-between px-4 py-2.5 text-sm text-left hover:bg-slate-50 dark:hover:bg-slate-800/50 ${
                    activeExam?.id === g.id ? "bg-brand-50 dark:bg-brand-500/10" : ""
                  }`}
                >
                  <span className="text-slate-700 dark:text-slate-200">
                    {g.num_variants} mã đề — {new Date(g.created_at).toLocaleString("vi-VN")}
                  </span>
                  <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                    {GEN_EXAM_STATUS_LABELS[g.status]}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-end gap-3 p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
        <div>
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Số mã đề</label>
          <input
            type="number"
            min={1}
            max={20}
            value={numVariants}
            onChange={(e) => setNumVariants(e.target.value)}
            className="mt-1.5 w-24 px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
          />
        </div>
        <button
          type="button"
          onClick={handleAssemble}
          disabled={assembling || (!savedBlueprint && !draft)}
          className="px-4 py-2 rounded-lg text-sm font-semibold bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {assembling ? "Đang ráp đề…" : "Ráp đề mới"}
        </button>
      </div>

      {activeExam && (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                {GEN_EXAM_STATUS_LABELS[activeExam.status]}
              </span>
              {activeExam.exam_paper_id && (
                <span className="inline-flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Đã nối vào luồng chấm — map cột điểm ở Bảng điểm.
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <a
                href={`/exam-builder/print/${activeExam.id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-brand-700 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-500/10"
              >
                <Printer className="w-3.5 h-3.5" /> In đề
              </a>
              <button
                type="button"
                onClick={toggleAnswer}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-brand-700 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-500/10"
              >
                {showAnswer ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                {showAnswer ? "Ẩn đáp án" : "Xem đáp án"}
              </button>
              {canReview && activeExam.status === "DRAFT" && (
                <button
                  type="button"
                  onClick={handleFinalize}
                  disabled={finalizing}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-accent-600 text-white hover:bg-accent-700 disabled:opacity-50"
                >
                  {finalizing ? "Đang chốt…" : "Chốt đề"}
                </button>
              )}
            </div>
          </div>

          <div className="flex gap-1.5 px-4 pt-3 border-b border-slate-200 dark:border-slate-800 flex-wrap">
            {activeExam.variants.map((v) => (
              <button
                key={v.variant_code}
                onClick={() => setActiveVariant(v.variant_code)}
                className={`px-3 py-1.5 text-sm font-medium rounded-t-lg border-b-2 -mb-px ${
                  activeVariant === v.variant_code
                    ? "border-brand-600 text-brand-600 dark:text-brand-400"
                    : "border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                }`}
              >
                Mã đề {v.variant_code}
              </button>
            ))}
          </div>

          <div className="p-4 space-y-4">
            {currentVariant?.items.map((item) => (
              <QuestionRow key={item.item_id} item={item} answer={showAnswer ? answerMap.get(item.item_id) : undefined} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function QuestionRow({
  item,
  answer,
}: {
  item: AssembledItemRead;
  answer?: { answer_key: Record<string, unknown>; solution: string | null };
}) {
  const correctKey = typeof answer?.answer_key.correct === "string" ? (answer.answer_key.correct as string) : null;
  return (
    <div className="pb-4 border-b border-slate-100 dark:border-slate-800 last:border-0 last:pb-0">
      <p className="text-sm font-medium text-slate-800 dark:text-slate-100">
        Câu {item.position} ({item.points}đ). {item.stem}
      </p>
      {item.options && (
        <div className="mt-2 space-y-1">
          {item.options.map((o) => (
            <p
              key={o.key}
              className={`text-sm pl-3 ${
                correctKey === o.key
                  ? "text-emerald-700 dark:text-emerald-400 font-semibold"
                  : "text-slate-600 dark:text-slate-300"
              }`}
            >
              {o.key}. {o.text} {correctKey === o.key && "✓"}
            </p>
          ))}
        </div>
      )}
      {answer && !item.options && (
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
          Đáp án: {String(answer.answer_key.answer ?? "")}
          {typeof answer.answer_key.rubric === "string" && ` — Rubric: ${answer.answer_key.rubric}`}
        </p>
      )}
      {answer?.solution && (
        <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400 italic">Lời giải: {answer.solution}</p>
      )}
    </div>
  );
}
