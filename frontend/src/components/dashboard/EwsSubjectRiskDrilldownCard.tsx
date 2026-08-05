"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, Home, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import {
  EwsRiskLevel,
  type EwsSubjectDrilldownResponse,
} from "@/lib/types";

interface EwsSubjectRiskDrilldownCardProps {
  schoolYearId: number;
  semesterIndex: number;
  week: number;
  modelVersion: string;
}

export default function EwsSubjectRiskDrilldownCard({
  schoolYearId,
  semesterIndex,
  week,
  modelVersion,
}: EwsSubjectRiskDrilldownCardProps) {
  const [level, setLevel] = useState<"group" | "subject" | "class" | "student">("group");
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [selectedSubjectId, setSelectedSubjectId] = useState<number | null>(null);
  const [selectedClass, setSelectedClass] = useState<string | null>(null);

  const [data, setData] = useState<EwsSubjectDrilldownResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Fetch drill-down data when filters or level change
  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    const params = new URLSearchParams({
      school_year_id: String(schoolYearId),
      semester_index: String(semesterIndex),
      evaluated_at_week: String(week),
      model_version: modelVersion,
      level,
    });

    if (selectedGroup) params.set("subject_category", selectedGroup);
    if (selectedSubjectId !== null) params.set("subject_id", String(selectedSubjectId));
    if (selectedClass) params.set("class_name", selectedClass);

    api
      .get<EwsSubjectDrilldownResponse>(`/ews/subject-drilldown?${params.toString()}`)
      .then((res) => {
        if (isMounted) setData(res);
      })
      .catch((err) => {
        console.error("Failed to load subject drilldown data:", err);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [schoolYearId, semesterIndex, week, modelVersion, level, selectedGroup, selectedSubjectId, selectedClass]);

  const handleBack = () => {
    if (level === "student") {
      setLevel("class");
      setSelectedClass(null);
    } else if (level === "class") {
      setLevel("subject");
      setSelectedSubjectId(null);
    } else if (level === "subject") {
      setLevel("group");
      setSelectedGroup(null);
    }
  };

  const handleItemClick = (item: { id?: string | number | null; name: string }) => {
    if (level === "group") {
      setSelectedGroup(item.name);
      setLevel("subject");
    } else if (level === "subject") {
      if (item.id !== undefined && item.id !== null) {
        setSelectedSubjectId(Number(item.id));
      }
      setLevel("class");
    } else if (level === "class") {
      setSelectedClass(item.name);
      setLevel("student");
    }
  };

  const getRiskBadgeStyle = (riskLevel: EwsRiskLevel) => {
    switch (riskLevel) {
      case "CRITICAL":
        return "bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800";
      case "HIGH":
        return "bg-orange-50 dark:bg-orange-950/40 text-orange-600 dark:text-orange-400 border border-orange-200 dark:border-orange-800";
      case "MODERATE":
        return "bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-800";
      case "LOW":
        return "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800";
      default:
        return "bg-slate-100 text-slate-700";
    }
  };

  const getScoreTextColor = (score: number) => {
    if (score >= 50) return "text-red-600 dark:text-red-400 font-bold";
    if (score >= 30) return "text-amber-600 dark:text-amber-400 font-bold";
    return "text-emerald-600 dark:text-emerald-400 font-bold";
  };

  return (
    <div className="bg-white dark:bg-slate-900 p-4 sm:p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3.5">
      {/* HEADER SECTION */}
      <div className="space-y-0.5">
        <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 tracking-tight">
          Phân tích rủi ro theo môn học
        </h3>
        <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight">
          Drill-down kiểu Power BI: Nhóm môn → Môn → Lớp → Học sinh. Phân quyền theo vai trò AcademicStaff.
        </p>
      </div>

      {/* BREADCRUMB & NAV & LEGEND BAR */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] border-b border-slate-100 dark:border-slate-800 pb-2">
        <div className="flex items-center gap-1.5 flex-wrap">
          {level !== "group" && (
            <button
              onClick={handleBack}
              className="flex items-center gap-1 px-2 py-0.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-medium rounded-md transition-colors border border-slate-200 dark:border-slate-700 text-[11px]"
            >
              <ArrowLeft className="w-3 h-3" />
              <span>Back</span>
            </button>
          )}

          <div className="flex items-center gap-1 text-slate-600 dark:text-slate-300 font-medium">
            <span
              onClick={() => {
                setLevel("group");
                setSelectedGroup(null);
                setSelectedSubjectId(null);
                setSelectedClass(null);
              }}
              className="flex items-center gap-1 cursor-pointer hover:text-indigo-600 dark:hover:text-indigo-400"
            >
              <Home className="w-3 h-3 text-indigo-500" />
              <span>Subject Group</span>
            </span>

            {data?.breadcrumb && data.breadcrumb.length > 1 && (
              <>
                {data.breadcrumb.slice(1).map((bc, idx) => (
                  <span key={idx} className="flex items-center gap-1">
                    <span className="text-slate-400">›</span>
                    <span className={idx === data.breadcrumb.length - 2 ? "font-semibold text-slate-900 dark:text-slate-100" : ""}>
                      {bc}
                    </span>
                  </span>
                ))}
              </>
            )}
          </div>
        </div>

        {/* LEGEND BADGES */}
        <div className="flex items-center gap-2.5">
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
      </div>

      {/* CONTENT AREA */}
      {loading ? (
        <div className="py-12 flex items-center justify-center text-slate-400">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
      ) : level !== "student" ? (
        /* LEVEL 1 - 3: STACKED BAR ROWS */
        <div className="space-y-2.5">
          {data?.items && data.items.length > 0 ? (
            data.items.map((item, idx) => (
              <div
                key={idx}
                onClick={() => handleItemClick(item)}
                className="group p-2.5 sm:p-3 bg-slate-50/70 hover:bg-indigo-50/40 dark:bg-slate-800/40 dark:hover:bg-slate-800/80 rounded-xl border border-slate-200/80 dark:border-slate-800 transition-all cursor-pointer space-y-1.5"
              >
                {/* ROW TOP: TITLE & STATS */}
                <div className="flex flex-wrap items-center justify-between gap-1.5">
                  <h4 className="text-xs sm:text-sm font-semibold text-slate-800 dark:text-slate-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                    {item.name}
                  </h4>

                  <div className="flex items-center gap-1.5 text-[10px] sm:text-[11px] flex-wrap">
                    <span className="text-slate-500 dark:text-slate-400 font-medium">
                      Tổng: {item.total_cnt}
                    </span>
                    <span className="px-1.5 py-0.5 bg-red-100 dark:bg-red-950/60 text-red-700 dark:text-red-400 rounded font-semibold">
                      Critical: {item.critical_cnt}
                    </span>
                    <span className="px-1.5 py-0.5 bg-orange-100 dark:bg-orange-950/60 text-orange-700 dark:text-orange-400 rounded font-semibold">
                      High: {item.high_cnt}
                    </span>
                    <span className="text-blue-600 dark:text-blue-400 font-bold">
                      C+H: {item.ch_pct}%
                    </span>
                  </div>
                </div>

                {/* HORIZONTAL STACKED PROGRESS BAR */}
                <div className="w-full h-3.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden flex text-[9px] font-bold text-white shadow-inner">
                  {item.low_pct > 0 && (
                    <div
                      style={{ width: `${item.low_pct}%` }}
                      className="bg-[#10b981] h-full flex items-center justify-center transition-all duration-300"
                    >
                      {item.low_pct >= 8 && `${item.low_pct}%`}
                    </div>
                  )}
                  {item.moderate_pct > 0 && (
                    <div
                      style={{ width: `${item.moderate_pct}%` }}
                      className="bg-[#f59e0b] h-full flex items-center justify-center transition-all duration-300 text-slate-900"
                    >
                      {item.moderate_pct >= 8 && `${item.moderate_pct}%`}
                    </div>
                  )}
                  {item.high_pct > 0 && (
                    <div
                      style={{ width: `${item.high_pct}%` }}
                      className="bg-[#f97316] h-full flex items-center justify-center transition-all duration-300"
                    >
                      {item.high_pct >= 8 && `${item.high_pct}%`}
                    </div>
                  )}
                  {item.critical_pct > 0 && (
                    <div
                      style={{ width: `${item.critical_pct}%` }}
                      className="bg-[#ef4444] h-full flex items-center justify-center transition-all duration-300"
                    >
                      {item.critical_pct >= 8 && `${item.critical_pct}%`}
                    </div>
                  )}
                </div>
              </div>
            ))
          ) : (
            <p className="text-xs text-slate-400 py-6 text-center">Không có dữ liệu rủi ro ở cấp này</p>
          )}
        </div>
      ) : (
        /* LEVEL 4: STUDENT DETAIL TABLE */
        <div className="space-y-3">
          {/* SUMMARY BAR */}
          {data?.summary && (
            <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-800 space-y-1.5">
              <p className="text-[11px] text-slate-600 dark:text-slate-300 font-medium">
                Tổng: {data.summary.total_cnt} bản ghi · Low {data.summary.low_cnt}/{data.summary.low_pct}% · Moderate{" "}
                {data.summary.moderate_cnt}/{data.summary.moderate_pct}% · High {data.summary.high_cnt}/
                {data.summary.high_pct}% · Critical {data.summary.critical_cnt}/{data.summary.critical_pct}%
              </p>

              <div className="w-full h-3.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden flex text-[9px] font-bold text-white shadow-inner">
                {data.summary.low_pct > 0 && (
                  <div
                    style={{ width: `${data.summary.low_pct}%` }}
                    className="bg-[#10b981] h-full flex items-center justify-center"
                  >
                    {data.summary.low_pct >= 8 && `${data.summary.low_pct}%`}
                  </div>
                )}
                {data.summary.moderate_pct > 0 && (
                  <div
                    style={{ width: `${data.summary.moderate_pct}%` }}
                    className="bg-[#f59e0b] h-full flex items-center justify-center text-slate-900"
                  >
                    {data.summary.moderate_pct >= 8 && `${data.summary.moderate_pct}%`}
                  </div>
                )}
                {data.summary.high_pct > 0 && (
                  <div
                    style={{ width: `${data.summary.high_pct}%` }}
                    className="bg-[#f97316] h-full flex items-center justify-center"
                  >
                    {data.summary.high_pct >= 8 && `${data.summary.high_pct}%`}
                  </div>
                )}
                {data.summary.critical_pct > 0 && (
                  <div
                    style={{ width: `${data.summary.critical_pct}%` }}
                    className="bg-[#ef4444] h-full flex items-center justify-center"
                  >
                    {data.summary.critical_pct >= 8 && `${data.summary.critical_pct}%`}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TABLE OF STUDENTS */}
          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-100/70 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-semibold border-b border-slate-200 dark:border-slate-700 uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="p-2.5 sm:p-3">HỌC SINH</th>
                  <th className="p-2.5 sm:p-3">TUẦN</th>
                  <th className="p-2.5 sm:p-3">RISK</th>
                  <th className="p-2.5 sm:p-3 text-right">SCORE</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 bg-white dark:bg-slate-900 text-xs">
                {data?.student_items && data.student_items.length > 0 ? (
                  data.student_items.map((st, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="p-2.5 sm:p-3 font-medium text-slate-800 dark:text-slate-200">{st.student_name}</td>
                      <td className="p-2.5 sm:p-3 text-slate-500 dark:text-slate-400">{st.week_label}</td>
                      <td className="p-2.5 sm:p-3">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full font-semibold text-[10px] ${getRiskBadgeStyle(
                            st.risk_level
                          )}`}
                        >
                          {st.risk_level.charAt(0) + st.risk_level.slice(1).toLowerCase()}
                        </span>
                      </td>
                      <td className={`p-2.5 sm:p-3 text-right font-bold ${getScoreTextColor(st.risk_score)}`}>
                        {st.risk_score}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="p-4 text-center text-slate-400">
                      Không có học sinh trong danh sách
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
