"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Printer } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { LoadingState } from "@/components/Loading";
import SearchableSelect from "@/components/SearchableSelect";
import {
  SCORE_CATEGORY_LABELS,
  type AssembledItemRead,
  type BlueprintRead,
  type Grade,
  type GeneratedExamDetail,
  type Semester,
  type Subject,
  type VariantAnswerRead,
} from "@/lib/types";

// @page mặc định (globals.css) là A4 landscape — đề thi cần A4 dọc, ghi đè riêng ở trang này.
const PORTRAIT_PAGE_CSS = `@media print { @page { size: A4 portrait; margin: 1.4cm; } }`;

export default function ExamPrintPage() {
  const params = useParams<{ examId: string }>();
  const { user } = useAuth();

  const [exam, setExam] = useState<GeneratedExamDetail | null>(null);
  const [blueprint, setBlueprint] = useState<BlueprintRead | null>(null);
  const [subject, setSubject] = useState<Subject | null>(null);
  const [grade, setGrade] = useState<Grade | null>(null);
  const [semester, setSemester] = useState<Semester | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [variantFilter, setVariantFilter] = useState("ALL");
  const [includeAnswers, setIncludeAnswers] = useState(false);
  const [answerData, setAnswerData] = useState<VariantAnswerRead[] | null>(null);
  const [answerError, setAnswerError] = useState<string | null>(null);

  useEffect(() => {
    const examId = params.examId;
    if (!examId) return;
    setLoading(true);
    setError(null);
    api
      .get<GeneratedExamDetail>(`/exams/${examId}`)
      .then(async (detail) => {
        setExam(detail);
        const [bp, subs, grades, sems] = await Promise.all([
          api.get<BlueprintRead>(`/exam-blueprints/${detail.blueprint_id}`),
          api.get<Subject[]>("/subjects?limit=200"),
          api.get<Grade[]>("/grades?limit=200"),
          api.get<Semester[]>("/semesters?limit=50"),
        ]);
        setBlueprint(bp);
        setSubject(subs.find((s) => s.id === bp.subject_id) ?? null);
        setGrade(grades.find((g) => g.id === detail.grade_id) ?? null);
        setSemester(sems.find((s) => s.id === detail.semester_id) ?? null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Không tải được đề thi"))
      .finally(() => setLoading(false));
  }, [params.examId]);

  const handleToggleAnswers = async () => {
    if (includeAnswers) {
      setIncludeAnswers(false);
      return;
    }
    setAnswerError(null);
    try {
      const data = answerData ?? (await api.get<VariantAnswerRead[]>(`/exams/${params.examId}/answer-key`));
      setAnswerData(data);
      setIncludeAnswers(true);
    } catch (e) {
      setAnswerError(e instanceof ApiError ? e.message : "Không xem được đáp án");
    }
  };

  const variantOptions = useMemo(
    () => [{ value: "ALL", label: "Tất cả mã đề" }, ...(exam?.variants.map((v) => ({ value: v.variant_code, label: `Mã đề ${v.variant_code}` })) ?? [])],
    [exam]
  );

  const variantsToShow = useMemo(
    () => exam?.variants.filter((v) => variantFilter === "ALL" || v.variant_code === variantFilter) ?? [],
    [exam, variantFilter]
  );

  if (loading) return <LoadingState message="Đang tải đề thi…" className="p-8" />;
  if (error || !exam || !blueprint) {
    return (
      <div className="p-8">
        <div className="max-w-md mx-auto text-center py-16 text-rose-500 text-sm">
          {error ?? "Không tìm thấy đề thi"}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-3xl mx-auto space-y-6 print-area">
      <style>{PORTRAIT_PAGE_CSS}</style>

      <div className="no-print flex flex-wrap items-center gap-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4">
        <SearchableSelect value={variantFilter} onChange={setVariantFilter} options={variantOptions} className="w-48" />
        <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
          <input type="checkbox" checked={includeAnswers} onChange={handleToggleAnswers} className="rounded border-slate-300 dark:border-slate-600" />
          Kèm phiếu đáp án
        </label>
        {answerError && <span className="text-sm text-rose-600 dark:text-rose-400">{answerError}</span>}
        <div className="flex-1" />
        <button
          type="button"
          onClick={() => window.print()}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold bg-brand-600 text-white hover:bg-brand-700"
        >
          <Printer className="w-4 h-4" /> In / Xuất PDF
        </button>
      </div>

      {variantsToShow.map((v, idx) => (
        <ExamPaper
          key={v.variant_code}
          schoolName={user?.school_name}
          blueprint={blueprint}
          subjectName={subject?.name ?? ""}
          gradeName={grade?.name ?? ""}
          semesterName={semester?.name ?? ""}
          variantCode={v.variant_code}
          items={v.items}
          isLast={idx === variantsToShow.length - 1 && !includeAnswers}
        />
      ))}

      {includeAnswers &&
        answerData
          ?.filter((v) => variantFilter === "ALL" || v.variant_code === variantFilter)
          .map((v, idx, arr) => (
            <AnswerSheet key={v.variant_code} variantCode={v.variant_code} items={v.items} isLast={idx === arr.length - 1} />
          ))}
    </div>
  );
}

function ExamPaper({
  schoolName,
  blueprint,
  subjectName,
  gradeName,
  semesterName,
  variantCode,
  items,
  isLast,
}: {
  schoolName?: string;
  blueprint: BlueprintRead;
  subjectName: string;
  gradeName: string;
  semesterName: string;
  variantCode: string;
  items: AssembledItemRead[];
  isLast: boolean;
}) {
  return (
    <div className={`bg-white text-black p-8 print:p-0 border border-slate-200 dark:border-slate-800 print:border-0 rounded-2xl print:rounded-none ${isLast ? "" : "break-after-page"}`}>
      <div className="text-center space-y-0.5 mb-4">
        <p className="text-sm font-semibold uppercase">{schoolName ?? "Trường học"}</p>
        <p className="text-lg font-bold uppercase mt-2">
          Đề kiểm tra {SCORE_CATEGORY_LABELS[blueprint.score_category].toLowerCase()}
        </p>
        <p className="text-sm">
          Môn: {subjectName} — Khối: {gradeName} — {semesterName}
        </p>
        {blueprint.duration_min && <p className="text-sm">Thời gian làm bài: {blueprint.duration_min} phút</p>}
      </div>

      <div className="flex items-center justify-between text-sm mb-4 pb-2 border-b border-black/30">
        <span>
          Họ tên: ..................................................... — Lớp: ..............
        </span>
        <span className="font-bold whitespace-nowrap ml-4">Mã đề: {variantCode}</span>
      </div>

      <ol className="space-y-4">
        {items.map((item) => (
          <li key={item.item_id}>
            <p className="text-sm font-medium">
              Câu {item.position} ({item.points}đ). {item.stem}
            </p>
            {item.options ? (
              <div className="mt-1.5 grid grid-cols-2 gap-x-4 gap-y-1 pl-4">
                {item.options.map((o) => (
                  <p key={o.key} className="text-sm">
                    {o.key}. {o.text}
                  </p>
                ))}
              </div>
            ) : (
              <div className="mt-2 pl-4 space-y-3">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="border-b border-black/40 h-4" />
                ))}
              </div>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

function AnswerSheet({ variantCode, items, isLast }: { variantCode: string; items: VariantAnswerRead["items"]; isLast: boolean }) {
  return (
    <div className={`bg-white text-black p-8 print:p-0 border border-slate-200 dark:border-slate-800 print:border-0 rounded-2xl print:rounded-none ${isLast ? "" : "break-after-page"}`}>
      <p className="text-center text-lg font-bold uppercase mb-4">Phiếu đáp án — Mã đề {variantCode}</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-black/40">
            <th className="text-left py-1.5">Câu</th>
            <th className="text-left py-1.5">Đáp án</th>
            <th className="text-left py-1.5">Lời giải</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => {
            const correct = typeof it.answer_key.correct === "string" ? it.answer_key.correct : null;
            const rubric = typeof it.answer_key.rubric === "string" ? it.answer_key.rubric : null;
            const answerText = typeof it.answer_key.answer === "string" ? it.answer_key.answer : null;
            return (
              <tr key={it.item_id} className="border-b border-black/10 align-top">
                <td className="py-1.5 pr-2">{it.position}</td>
                <td className="py-1.5 pr-2 font-semibold">
                  {correct ?? answerText ?? "—"}
                  {rubric && <div className="font-normal text-xs">Rubric: {rubric}</div>}
                </td>
                <td className="py-1.5 text-xs">{it.solution ?? ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
