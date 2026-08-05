"use client";

import { useEffect, useState } from "react";
import { Loader2, Trophy } from "lucide-react";
import { api } from "@/lib/api";
import type { EwsTopClassRiskItem } from "@/lib/types";

interface EwsTopRiskClassesCardProps {
  schoolYearId: number;
  semesterIndex: number;
  week: number;
  modelVersion: string;
}

export default function EwsTopRiskClassesCard({
  schoolYearId,
  semesterIndex,
  week,
  modelVersion,
}: EwsTopRiskClassesCardProps) {
  const [classes, setClasses] = useState<EwsTopClassRiskItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    const params = new URLSearchParams({
      school_year_id: String(schoolYearId),
      semester_index: String(semesterIndex),
      evaluated_at_week: String(week),
      model_version: modelVersion,
      limit: "5",
    });

    api
      .get<EwsTopClassRiskItem[]>(`/ews/top-risk-classes?${params.toString()}`)
      .then((res) => {
        if (isMounted) setClasses(res);
      })
      .catch((err) => {
        console.error("Failed to load top risk classes:", err);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [schoolYearId, semesterIndex, week, modelVersion]);

  return (
    <div className="bg-white dark:bg-slate-900 p-4 sm:p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3.5">
      {/* HEADER SECTION */}
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-0.5">
          <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 tracking-tight">
            Top 5 lớp rủi ro cao nhất
          </h3>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight">
            Xếp theo số Critical → High → % (Critical + High).
          </p>
        </div>
        <div className="p-1.5 bg-amber-500/10 text-amber-500 rounded-lg flex-shrink-0">
          <Trophy className="w-5 h-5 stroke-[2.2]" />
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

      {/* LIST OF TOP 5 CLASSES */}
      {loading ? (
        <div className="py-12 flex items-center justify-center text-slate-400">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
      ) : classes.length > 0 ? (
        <div className="space-y-2.5">
          {classes.map((cls) => (
            <div
              key={cls.rank}
              className="p-2.5 sm:p-3 bg-slate-50/70 dark:bg-slate-800/40 rounded-xl border border-slate-200/80 dark:border-slate-800 space-y-1.5"
            >
              {/* TOP ROW: RANK BADGE, CLASS NAME, STATS */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div
                    className={`w-5.5 h-5.5 rounded-full flex items-center justify-center font-bold text-[11px] text-white shadow-sm flex-shrink-0 ${
                      cls.rank === 1 ? "bg-[#ef4444]" : "bg-blue-600"
                    }`}
                  >
                    {cls.rank}
                  </div>
                  <h4 className="text-xs sm:text-sm font-bold text-slate-900 dark:text-slate-100">{cls.class_name}</h4>
                </div>

                <div className="flex items-center gap-1.5 text-[10px] sm:text-[11px] flex-wrap">
                  <span className="text-slate-500 dark:text-slate-400 font-medium">Tổng: {cls.total_cnt}</span>
                  <span className="px-1.5 py-0.5 bg-red-100 dark:bg-red-950/60 text-red-700 dark:text-red-400 rounded font-semibold">
                    Critical: {cls.critical_cnt}
                  </span>
                  <span className="px-1.5 py-0.5 bg-orange-100 dark:bg-orange-950/60 text-orange-700 dark:text-orange-400 rounded font-semibold">
                    High: {cls.high_cnt}
                  </span>
                  <span className="text-blue-600 dark:text-blue-400 font-bold">C+H: {cls.ch_pct}%</span>
                </div>
              </div>

              {/* HORIZONTAL STACKED PROGRESS BAR */}
              <div className="w-full h-3.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden flex text-[9px] font-bold text-white shadow-inner">
                {cls.low_pct > 0 && (
                  <div
                    style={{ width: `${cls.low_pct}%` }}
                    className="bg-[#10b981] h-full flex items-center justify-center transition-all duration-300"
                  >
                    {cls.low_pct >= 8 && `${cls.low_pct}%`}
                  </div>
                )}
                {cls.moderate_pct > 0 && (
                  <div
                    style={{ width: `${cls.moderate_pct}%` }}
                    className="bg-[#f59e0b] h-full flex items-center justify-center transition-all duration-300 text-slate-900"
                  >
                    {cls.moderate_pct >= 8 && `${cls.moderate_pct}%`}
                  </div>
                )}
                {cls.high_pct > 0 && (
                  <div
                    style={{ width: `${cls.high_pct}%` }}
                    className="bg-[#f97316] h-full flex items-center justify-center transition-all duration-300"
                  >
                    {cls.high_pct >= 8 && `${cls.high_pct}%`}
                  </div>
                )}
                {cls.critical_pct > 0 && (
                  <div
                    style={{ width: `${cls.critical_pct}%` }}
                    className="bg-[#ef4444] h-full flex items-center justify-center transition-all duration-300"
                  >
                    {cls.critical_pct >= 8 && `${cls.critical_pct}%`}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-slate-400 py-6 text-center">Không có dữ liệu lớp rủi ro</p>
      )}
    </div>
  );
}
