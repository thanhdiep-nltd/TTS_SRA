"use client";

import { BookOpen } from "lucide-react";
import { Loader2 } from "lucide-react";

interface EwsTopSubjectItem {
    subject_name: string;
    cnt: number;
    avg_risk: number;
    low_cnt: number;
    moderate_cnt: number;
    high_cnt: number;
    critical_cnt: number;
    low_pct: number;
    moderate_pct: number;
    high_pct: number;
    critical_pct: number;
    ch_pct: number;
}

interface EwsTopSubjectsCardProps {
    subjects: EwsTopSubjectItem[];
    loading: boolean;
}

export default function EwsTopSubjectsCard({ subjects, loading }: EwsTopSubjectsCardProps) {
    return (
        <div className="bg-white dark:bg-slate-900 p-4 sm:p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3.5">
            {/* HEADER SECTION */}
            <div className="flex items-start justify-between gap-3">
                <div className="space-y-0.5">
                    <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                        Top 5 Môn Học Rủi Ro Cao Nhất
                    </h3>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight">
                        Xếp theo điểm rủi ro trung bình cao nhất.
                    </p>
                </div>
                <div className="p-1.5 bg-indigo-500/10 text-indigo-500 rounded-lg flex-shrink-0">
                    <BookOpen className="w-5 h-5 stroke-[2.2]" />
                </div>
            </div>

            {/* LEGEND BAR */}
            <div className="flex flex-wrap items-center justify-start gap-2.5 text-[11px] border-b border-slate-100 dark:border-slate-800 pb-2">
                <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-[#10b981]"></span>
                    <span className="text-slate-600 dark:text-slate-400 font-medium">Low</span>
                </span>
                <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-[#f59e0b]"></span>
                    <span className="text-slate-600 dark:text-slate-400 font-medium">Moderate</span>
                </span>
                <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-[#f97316]"></span>
                    <span className="text-slate-600 dark:text-slate-400 font-medium">High</span>
                </span>
                <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-[#ef4444]"></span>
                    <span className="text-slate-600 dark:text-slate-400 font-medium">Critical</span>
                </span>
            </div>

            {/* LIST OF TOP 5 SUBJECTS */}
            {loading ? (
                <div className="py-12 flex items-center justify-center text-slate-400">
                    <Loader2 className="w-5 h-5 animate-spin" />
                </div>
            ) : subjects.length > 0 ? (
                <div className="space-y-2.5">
                    {subjects.slice(0, 5).map((sub, idx) => (
                        <div
                            key={idx}
                            className="p-2.5 sm:p-3 bg-slate-50/70 dark:bg-slate-800/40 rounded-xl border border-slate-200/80 dark:border-slate-800 space-y-1.5"
                        >
                            {/* TOP ROW: RANK BADGE, SUBJECT NAME, STATS */}
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                    <div
                                        className={`w-5.5 h-5.5 rounded-full flex items-center justify-center font-bold text-[11px] text-white shadow-sm flex-shrink-0 ${
                                            idx === 0 ? "bg-[#ef4444]" : "bg-blue-600"
                                        }`}
                                    >
                                        {idx + 1}
                                    </div>
                                    <h4 className="text-xs sm:text-sm font-bold text-slate-900 dark:text-slate-100 truncate">
                                        {sub.subject_name}
                                    </h4>
                                </div>

                                <div className="flex items-center gap-1.5 text-[10px] sm:text-[11px] flex-wrap">
                                    <span className="text-slate-500 dark:text-slate-400 font-medium">Tổng: {sub.cnt}</span>
                                    <span className="px-1.5 py-0.5 bg-red-100 dark:bg-red-950/60 text-red-700 dark:text-red-400 rounded font-semibold">
                                        Critical: {sub.critical_cnt}
                                    </span>
                                    <span className="px-1.5 py-0.5 bg-orange-100 dark:bg-orange-950/60 text-orange-700 dark:text-orange-400 rounded font-semibold">
                                        High: {sub.high_cnt}
                                    </span>
                                    <span className="text-blue-600 dark:text-blue-400 font-bold">C+H: {sub.ch_pct}%</span>
                                </div>
                            </div>

                            {/* HORIZONTAL STACKED PROGRESS BAR */}
                            <div className="w-full h-3.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden flex text-[9px] font-bold text-white shadow-inner">
                                {sub.low_pct > 0 && (
                                    <div
                                        style={{ width: `${sub.low_pct}%` }}
                                        className="bg-[#10b981] h-full flex items-center justify-center transition-all duration-300"
                                    >
                                        {sub.low_pct >= 8 && `${sub.low_pct}%`}
                                    </div>
                                )}
                                {sub.moderate_pct > 0 && (
                                    <div
                                        style={{ width: `${sub.moderate_pct}%` }}
                                        className="bg-[#f59e0b] h-full flex items-center justify-center transition-all duration-300 text-slate-900"
                                    >
                                        {sub.moderate_pct >= 8 && `${sub.moderate_pct}%`}
                                    </div>
                                )}
                                {sub.high_pct > 0 && (
                                    <div
                                        style={{ width: `${sub.high_pct}%` }}
                                        className="bg-[#f97316] h-full flex items-center justify-center transition-all duration-300"
                                    >
                                        {sub.high_pct >= 8 && `${sub.high_pct}%`}
                                    </div>
                                )}
                                {sub.critical_pct > 0 && (
                                    <div
                                        style={{ width: `${sub.critical_pct}%` }}
                                        className="bg-[#ef4444] h-full flex items-center justify-center transition-all duration-300"
                                    >
                                        {sub.critical_pct >= 8 && `${sub.critical_pct}%`}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <p className="text-xs text-slate-400 py-6 text-center">Không có dữ liệu môn rủi ro</p>
            )}
        </div>
    );
}
