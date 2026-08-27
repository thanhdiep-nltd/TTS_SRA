"use client";

import { LmsEvidencePattern } from "@/lib/types";

// Nhãn + màu cho từng pattern hành vi LMS (khớp backend src/ews/lms_evidence.py)
const PATTERN_META: Record<string, { label: string; cls: string }> = {
    EFFORT_BUT_LOST: { label: "Nỗ lực nhưng không hiểu", cls: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300" },
    RUSHED: { label: "Làm qua loa (đoán mò)", cls: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300" },
    OFF_TASK: { label: "Treo máy (nhiễu)", cls: "bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-400" },
    SKIPPED: { label: "Bỏ bê (không nộp)", cls: "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400" },
    WEAK_CHAPTER: { label: "Điểm thấp", cls: "bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300" },
    MISSING_IN_EXAM: { label: "Mất kiến thức", cls: "bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300" },
};

export default function LmsEvidenceBlock({ evidence }: { evidence: LmsEvidencePattern[] }) {
    if (!evidence || evidence.length === 0) return null;

    return (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 p-4 space-y-2">
            <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                Bằng chứng học tập LMS
            </h4>
            <ul className="space-y-1.5">
                {evidence.map((ev, i) => {
                    const meta = PATTERN_META[ev.pattern] ?? {
                        label: ev.pattern,
                        cls: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
                    };
                    return (
                        <li key={i} className="flex items-start gap-2 text-sm">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold shrink-0 mt-0.5 ${meta.cls}`}>
                                {meta.label}
                            </span>
                            <span className="text-slate-600 dark:text-slate-300">{ev.explanation}</span>
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}