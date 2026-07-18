"use client";

import { useEffect, useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import SearchableSelect, { type Option } from "@/components/SearchableSelect";
import {
  BLOOM_OPTIONS,
  QUESTION_TYPE_LABELS,
  type BlueprintCell,
  type BlueprintCreate,
  type BlueprintRead,
  type CoverageCellResult,
  type QuestionType,
  type ScoreCategory,
} from "@/lib/types";

interface Props {
  subjectId: string;
  gradeNumber: number;
  scoreCategory: ScoreCategory;
  unitOptions: Option[];
  blueprint: BlueprintRead | null; // có sẵn -> sửa (PATCH); null -> tạo mới (POST)
  initialCells: BlueprintCell[];
  initialTitle: string;
  initialTargetDifficulty: number | null;
  rationale?: string[];
  /** Mục tiêu đã khai ở Step 1 — chỉ để CẢNH BÁO MỀM nếu ma trận thực tế lệch, không chặn lưu
   * (tổng điểm/số câu thật luôn tính sống từ cells, xem totalPoints/totalQuestions bên dưới). */
  targetTotalPoints?: number | null;
  targetTotalQuestions?: number | null;
  onSaved: (blueprint: BlueprintRead) => void;
  /** Chỉ có khi tạo MỚI (blueprint=null): thay vì lưu ngay, chuyển dữ liệu ma trận (chưa lưu DB)
   * sang bước ráp đề — ma trận chỉ thật sự được lưu khi ráp đề LẦN ĐẦU thành công (tránh rác
   * ma trận không ai dùng nếu GV bỏ dở giữa chừng). */
  onContinueUnsaved?: (draft: BlueprintCreate) => void;
}

const QUESTION_TYPES: QuestionType[] = ["MCQ", "TRUE_FALSE", "SHORT_ANSWER", "ESSAY"];
const QUESTION_TYPE_OPTIONS: Option[] = QUESTION_TYPES.map((t) => ({ value: t, label: QUESTION_TYPE_LABELS[t] }));

function blankCell(unitOptions: Option[]): BlueprintCell {
  return {
    unit_id: unitOptions[0]?.value ?? "",
    bloom_level: 1,
    question_type: "MCQ",
    num_questions: 1,
    points_each: 0.5,
  };
}

// CDI dự kiến của đề = Σ(điểm·bloom)/Σđiểm /6 — khớp công thức compute_cdi (exam_assembly.py).
function computeCdi(cells: BlueprintCell[]): number | null {
  const total = cells.reduce((s, c) => s + c.num_questions * c.points_each, 0);
  if (total <= 0) return null;
  const weighted = cells.reduce((s, c) => s + c.num_questions * c.points_each * c.bloom_level, 0);
  return Math.round((weighted / total / 6) * 1000) / 1000;
}

export default function MatrixEditor({
  subjectId, gradeNumber, scoreCategory, unitOptions, blueprint, initialCells, initialTitle,
  initialTargetDifficulty, rationale, targetTotalPoints, targetTotalQuestions, onSaved, onContinueUnsaved,
}: Props) {
  const [cells, setCells] = useState<BlueprintCell[]>(initialCells);
  const [title, setTitle] = useState(initialTitle);
  const [durationMin, setDurationMin] = useState(blueprint?.duration_min ? String(blueprint.duration_min) : "");
  const [targetDifficulty, setTargetDifficulty] = useState(
    initialTargetDifficulty !== null ? String(initialTargetDifficulty) : ""
  );
  const [coverage, setCoverage] = useState<CoverageCellResult[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalPoints = useMemo(
    () => Math.round(cells.reduce((s, c) => s + c.num_questions * c.points_each, 0) * 100) / 100,
    [cells]
  );
  const totalQuestions = useMemo(() => cells.reduce((s, c) => s + c.num_questions, 0), [cells]);
  const expectedCdi = useMemo(() => computeCdi(cells), [cells]);

  // Cảnh báo MỀM (không chặn lưu) nếu ma trận thực tế lệch mục tiêu đã khai ở Step 1 — trước
  // đây Step 1 "Tổng điểm" hoàn toàn bị bỏ qua khi lưu, GV không biết đã lệch cho tới khi xem đề.
  const pointsMismatch =
    targetTotalPoints != null && targetTotalPoints > 0 && Math.abs(totalPoints - targetTotalPoints) > 0.01;
  const questionsMismatch =
    targetTotalQuestions != null && targetTotalQuestions > 0 && totalQuestions !== targetTotalQuestions;

  // Đối chiếu kho — debounce 500ms để không gọi API mỗi lần gõ phím.
  useEffect(() => {
    if (cells.length === 0) {
      setCoverage(null);
      return;
    }
    const handle = setTimeout(() => {
      api
        .post<CoverageCellResult[]>("/exam-blueprints/coverage", {
          subject_id: subjectId,
          grade_number: gradeNumber,
          cells: cells.map((c) => ({
            unit_id: c.unit_id,
            bloom_level: c.bloom_level,
            question_type: c.question_type,
            num_questions: c.num_questions,
          })),
        })
        .then(setCoverage)
        .catch(() => setCoverage(null));
    }, 500);
    return () => clearTimeout(handle);
  }, [cells, subjectId, gradeNumber]);

  const updateCell = (idx: number, patch: Partial<BlueprintCell>) => {
    setCells((prev) => prev.map((c, i) => (i === idx ? { ...c, ...patch } : c)));
  };
  const removeCell = (idx: number) => setCells((prev) => prev.filter((_, i) => i !== idx));
  const addCell = () => setCells((prev) => [...prev, blankCell(unitOptions)]);

  const canSave = title.trim().length > 0 && cells.length > 0 && cells.every((c) => c.unit_id);

  const handleSave = async () => {
    const base = {
      title: title.trim(),
      total_points: totalPoints,
      duration_min: durationMin ? Number(durationMin) : null,
      target_difficulty: targetDifficulty ? Number(targetDifficulty) : null,
      cells,
    };
    // Tạo mới + có luồng hoãn lưu: KHÔNG gọi API — chỉ chuyển dữ liệu sang bước ráp đề, ma
    // trận thật sự được ghi DB khi ráp đề thành công lần đầu (xem onContinueUnsaved ở page.tsx).
    if (!blueprint && onContinueUnsaved) {
      onContinueUnsaved({
        ...base,
        subject_id: subjectId,
        grade_number: gradeNumber,
        score_category: scoreCategory,
      } satisfies BlueprintCreate);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const saved = blueprint
        ? await api.patch<BlueprintRead>(`/exam-blueprints/${blueprint.id}`, base)
        : await api.post<BlueprintRead>("/exam-blueprints", {
            ...base,
            subject_id: subjectId,
            grade_number: gradeNumber,
            score_category: scoreCategory,
          } satisfies BlueprintCreate);
      onSaved(saved);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Lưu ma trận thất bại");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {rationale && rationale.length > 0 && (
        <div className="p-3 rounded-lg bg-brand-50 dark:bg-brand-500/10 border border-brand-100 dark:border-brand-500/20 text-sm text-brand-800 dark:text-brand-200 space-y-1">
          <p className="font-semibold">Vì sao gợi ý như vậy:</p>
          <ul className="list-disc list-inside space-y-0.5">
            {rationale.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {error && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
        <div className="sm:col-span-2">
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Tiêu đề đề thi</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Thời lượng (phút)</label>
          <input
            type="number"
            min={1}
            value={durationMin}
            onChange={(e) => setDurationMin(e.target.value)}
            className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Độ khó mục tiêu (0–1)</label>
          <input
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={targetDifficulty}
            onChange={(e) => setTargetDifficulty(e.target.value)}
            className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
          />
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400">
            <tr>
              <th className="text-left px-3 py-2.5 font-medium">Chương</th>
              <th className="text-left px-3 py-2.5 font-medium">Bloom</th>
              <th className="text-left px-3 py-2.5 font-medium">Loại câu</th>
              <th className="text-left px-3 py-2.5 font-medium w-24">Số câu</th>
              <th className="text-left px-3 py-2.5 font-medium w-24">Điểm/câu</th>
              <th className="text-left px-3 py-2.5 font-medium">Kho</th>
              <th className="px-3 py-2.5"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {cells.map((cell, idx) => {
              const cov = coverage?.[idx];
              return (
                <tr key={idx}>
                  <td className="px-3 py-2 min-w-[180px]">
                    <SearchableSelect
                      value={cell.unit_id}
                      onChange={(v) => updateCell(idx, { unit_id: v })}
                      options={unitOptions}
                    />
                  </td>
                  <td className="px-3 py-2 min-w-[110px]">
                    <SearchableSelect
                      value={String(cell.bloom_level)}
                      onChange={(v) => updateCell(idx, { bloom_level: Number(v) })}
                      options={BLOOM_OPTIONS}
                    />
                  </td>
                  <td className="px-3 py-2 min-w-[140px]">
                    <SearchableSelect
                      value={cell.question_type}
                      onChange={(v) => updateCell(idx, { question_type: v as QuestionType })}
                      options={QUESTION_TYPE_OPTIONS}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      min={1}
                      value={cell.num_questions}
                      onChange={(e) => updateCell(idx, { num_questions: Math.max(1, Number(e.target.value)) })}
                      className="w-full px-2 py-1.5 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      min={0.25}
                      step={0.25}
                      value={cell.points_each}
                      onChange={(e) => updateCell(idx, { points_each: Math.max(0.25, Number(e.target.value)) })}
                      className="w-full px-2 py-1.5 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
                    />
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {cov ? (
                      cov.shortfall > 0 ? (
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300">
                          Thiếu {cov.shortfall} câu ({cov.available}/{cov.needed})
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                          Đủ ({cov.available}/{cov.needed})
                        </span>
                      )
                    ) : (
                      <span className="text-xs text-slate-400">…</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => removeCell(idx)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-500/10"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="p-3 border-t border-slate-200 dark:border-slate-800">
          <button
            type="button"
            onClick={addCell}
            disabled={unitOptions.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-brand-700 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-500/10 disabled:opacity-50"
          >
            <Plus className="w-4 h-4" /> Thêm ô
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4 p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-sm">
        <span className="text-slate-600 dark:text-slate-300">
          Tổng câu: <b className="text-slate-900 dark:text-white">{totalQuestions}</b>
        </span>
        <span className="text-slate-600 dark:text-slate-300">
          Tổng điểm: <b className="text-slate-900 dark:text-white">{totalPoints}</b>
        </span>
        <span className="text-slate-600 dark:text-slate-300">
          CDI dự kiến: <b className="text-slate-900 dark:text-white">{expectedCdi ?? "—"}</b>
        </span>
        <div className="flex-1" />
        <button
          type="button"
          onClick={handleSave}
          disabled={!canSave || saving}
          className="px-4 py-2 rounded-lg text-sm font-semibold bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {saving ? "Đang lưu…" : blueprint ? "Lưu thay đổi" : "Tiếp tục → Ráp đề"}
        </button>
      </div>

      {(pointsMismatch || questionsMismatch) && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          Lệch mục tiêu đã khai ở bước 1:
          {questionsMismatch && ` ${totalQuestions}/${targetTotalQuestions} câu.`}
          {pointsMismatch && ` ${totalPoints}/${targetTotalPoints} điểm.`} Có thể sửa số câu/điểm mỗi ô ở trên nếu muốn khớp chính xác.
        </p>
      )}
    </div>
  );
}
