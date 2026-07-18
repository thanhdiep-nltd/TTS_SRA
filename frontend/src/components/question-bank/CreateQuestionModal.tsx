"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { BLOOM_OPTIONS, QUESTION_TYPE_LABELS, type QuestionType } from "@/lib/types";
import ChapterLessonSelect from "../ChapterLessonSelect";
import SearchableSelect, { type Option } from "../SearchableSelect";

interface Props {
  subjectId: string;
  gradeNumber?: number;
  onClose: () => void;
  onCreated: () => void;
}

const QUESTION_TYPES: QuestionType[] = ["MCQ", "TRUE_FALSE", "SHORT_ANSWER", "ESSAY"];
const GRADE_OPTIONS: Option[] = [6, 7, 8, 9, 10, 11, 12].map((g) => ({ value: String(g), label: `Khối ${g}` }));

// Tạo câu hỏi thủ công (status=DRAFT, source=MANUAL) — đi cùng quy trình duyệt như câu AI sinh.
export default function CreateQuestionModal({ subjectId, gradeNumber, onClose, onCreated }: Props) {
  const [unitId, setUnitId] = useState("");
  const [grade, setGrade] = useState(gradeNumber ? String(gradeNumber) : "");
  const [bloom, setBloom] = useState("2");
  const [qType, setQType] = useState<QuestionType>("MCQ");
  const [options, setOptions] = useState([
    { key: "A", text: "" },
    { key: "B", text: "" },
    { key: "C", text: "" },
    { key: "D", text: "" },
  ]);
  const [correct, setCorrect] = useState("A");
  const [stem, setStem] = useState("");
  const [answerText, setAnswerText] = useState("");
  const [rubric, setRubric] = useState("");
  const [solution, setSolution] = useState("");
  const [points, setPoints] = useState("1");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Đổi Khối -> danh sách chương đổi -> chủ đề đã chọn có thể không còn hợp lệ.
  useEffect(() => {
    setUnitId("");
  }, [grade]);

  const isMcq = qType === "MCQ" || qType === "TRUE_FALSE";

  // Đổi loại câu -> dựng lại bộ đáp án mặc định phù hợp (TRUE_FALSE chỉ có Đúng/Sai, cố định).
  useEffect(() => {
    if (qType === "TRUE_FALSE") {
      setOptions([{ key: "A", text: "Đúng" }, { key: "B", text: "Sai" }]);
      setCorrect("A");
    } else if (qType === "MCQ") {
      setOptions([{ key: "A", text: "" }, { key: "B", text: "" }, { key: "C", text: "" }, { key: "D", text: "" }]);
      setCorrect("A");
    }
  }, [qType]);

  const canSubmit =
    !!unitId &&
    !!grade &&
    !!stem.trim() &&
    (isMcq ? options.every((o) => o.text.trim().length > 0) : answerText.trim().length > 0);

  const handleSubmit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post("/question-bank/items", {
        subject_id: subjectId,
        grade_number: Number(grade),
        unit_id: unitId,
        bloom_level: Number(bloom),
        question_type: qType,
        stem: stem.trim(),
        options: isMcq ? options : null,
        answer_key: isMcq ? { correct } : { answer: answerText.trim(), rubric: rubric.trim() || undefined },
        solution: solution.trim() || undefined,
        default_points: Number(points),
      });
      onCreated();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Tạo câu hỏi thất bại");
    } finally {
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
          <h3 className="font-bold text-slate-900 dark:text-white">Tạo câu hỏi thủ công</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
              {error}
            </div>
          )}

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

          <div>
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Đề bài</label>
            <textarea
              value={stem}
              onChange={(e) => setStem(e.target.value)}
              rows={3}
              className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
            />
          </div>

          {isMcq ? (
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Đáp án (bấm chọn ô đúng)</label>
              {options.map((o, idx) => (
                <div key={o.key} className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setCorrect(o.key)}
                    className={`w-8 h-8 shrink-0 rounded-lg border text-sm font-bold flex items-center justify-center ${
                      correct === o.key
                        ? "bg-emerald-600 text-white border-emerald-600"
                        : "border-slate-300 dark:border-slate-700 text-slate-500"
                    }`}
                  >
                    {o.key}
                  </button>
                  <input
                    value={o.text}
                    disabled={qType === "TRUE_FALSE"}
                    onChange={(e) => {
                      const next = [...options];
                      next[idx] = { ...o, text: e.target.value };
                      setOptions(next);
                    }}
                    className="flex-1 px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand disabled:opacity-60"
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Đáp án mẫu</label>
                <textarea
                  value={answerText}
                  onChange={(e) => setAnswerText(e.target.value)}
                  rows={2}
                  className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
                />
              </div>
              {qType === "ESSAY" && (
                <div>
                  <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Thang chấm (rubric)</label>
                  <textarea
                    value={rubric}
                    onChange={(e) => setRubric(e.target.value)}
                    rows={2}
                    className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
                  />
                </div>
              )}
            </div>
          )}

          <div>
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Lời giải (tùy chọn)</label>
            <textarea
              value={solution}
              onChange={(e) => setSolution(e.target.value)}
              rows={2}
              className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
            />
          </div>

          <div className="w-32">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Điểm</label>
            <input
              type="number"
              min={0.25}
              step={0.25}
              value={points}
              onChange={(e) => setPoints(e.target.value)}
              className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-slate-200 dark:border-slate-800">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            Hủy
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || busy}
            className="px-4 py-2 rounded-lg text-sm font-semibold bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {busy ? "Đang lưu…" : "Tạo câu hỏi"}
          </button>
        </div>
      </div>
    </div>
  );
}
