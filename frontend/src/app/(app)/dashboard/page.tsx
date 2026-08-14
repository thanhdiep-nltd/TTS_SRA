"use client";

import { useEffect, useState } from "react";
import { Award, BarChart3, RefreshCw, Settings2, ShieldAlert } from "lucide-react";
import EwsWarningTab from "@/components/dashboard/EwsWarningTab";
import EwsGoldenSetTab from "@/components/dashboard/EwsGoldenSetTab";
import EwsSubjectRiskTab from "@/components/dashboard/EwsSubjectRiskTab";
import EwsControlPanel from "@/components/dashboard/EwsControlPanel";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { EwsMeta, EwsWeekOption } from "@/lib/types";

type TabKey = "ews" | "subject-risk" | "golden-set" | "ews-control";

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: "ews", label: "Cảnh báo EWS", icon: ShieldAlert },
  { key: "subject-risk", label: "Phân Tích Môn Học", icon: BarChart3 },
  { key: "golden-set", label: "Golden Set", icon: Award },
];

export default function DashboardV2Page() {
  const { user } = useAuth();
  const [tab, setTab] = useState<TabKey>("ews");
  const [modelVersion, setModelVersion] = useState<string>("v2_ensemble");
  const [refreshKey, setRefreshKey] = useState<number>(0);

  // Mốc Đánh Giá (Tuần / Kỳ) — nâng state lên header để dùng chung cho các tab
  const [schoolYearId, setSchoolYearId] = useState<number>(2025);
  const [semesterIndex, setSemesterIndex] = useState<number>(1);
  const [week, setWeek] = useState<number>(8);
  const [weeks, setWeeks] = useState<EwsWeekOption[]>([]);

  useEffect(() => {
    let isMounted = true;
    api
      .get<EwsMeta>("/ews/meta")
      .then((res) => {
        if (!isMounted) return;
        setWeeks(res.weeks);
        if (res.weeks.length > 0) {
          const first = res.weeks[0];
          setSchoolYearId(first.school_year_id);
          setSemesterIndex(first.semester_index);
          setWeek(first.evaluated_at_week);
        }
      })
      .catch(() => {});
    return () => {
      isMounted = false;
    };
  }, []);

  const isControl = user?.role === "ADMIN" || user?.role === "PRINCIPAL";
  const tabs = isControl
    ? [...TABS, { key: "ews-control" as TabKey, label: "Điều khiển EWS", icon: Settings2 }]
    : TABS;

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto w-full">
      {/* Header & Controls Toolbar */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Cảnh Báo Sớm Học Tập (EWS)</h2>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-800/60">
              v2 Ensemble
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Theo dõi phân loại rủi ro và xu hướng học tập học sinh
          </p>
        </div>

        {/* Global Controls */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Mốc Đánh Giá (Tuần / Kỳ) */}
          <select
            value={`${schoolYearId}-${semesterIndex}-${week}`}
            onChange={(e) => {
              const [sy, sem, wk] = e.target.value.split("-").map(Number);
              setSchoolYearId(sy);
              setSemesterIndex(sem);
              setWeek(wk);
              setRefreshKey((k) => k + 1);
            }}
            className="text-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-slate-800 dark:text-slate-200 font-medium focus:ring-2 focus:ring-indigo-500 shadow-2xs"
          >
            {weeks.map((w, idx) => (
              <option key={idx} value={`${w.school_year_id}-${w.semester_index}-${w.evaluated_at_week}`}>
                {w.school_year_name || `Năm ${w.school_year_id}`} - HK{w.semester_index} (Tuần {w.evaluated_at_week})
              </option>
            ))}
          </select>

          {/* Phiên bản Model */}
          <select
            value={modelVersion}
            onChange={(e) => {
              setModelVersion(e.target.value);
              setRefreshKey((k) => k + 1);
            }}
            className="text-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-slate-800 dark:text-slate-200 font-medium focus:ring-2 focus:ring-indigo-500 shadow-2xs"
          >
            <option value="v2_ensemble">Model v2 (Ensemble)</option>
            <option value="v1_single">Model v1 (Đơn)</option>
          </select>

          {/* Nút Làm mới */}
          <button
            onClick={() => setRefreshKey((k) => k + 1)}
            className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-xs rounded-xl transition-all shadow-xs"
            title="Làm mới dữ liệu"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Làm mới</span>
          </button>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex flex-wrap gap-2">
        {tabs.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition ${active
                ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30"
                : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
                }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {tab === "ews" && (
        <EwsWarningTab
          modelVersion={modelVersion}
          refreshKey={refreshKey}
          schoolYearId={schoolYearId}
          semesterIndex={semesterIndex}
          week={week}
        />
      )}
      {tab === "subject-risk" && (
        <EwsSubjectRiskTab
          modelVersion={modelVersion}
          refreshKey={refreshKey}
        />
      )}
      {tab === "golden-set" && <EwsGoldenSetTab />}
      {tab === "ews-control" && isControl && <EwsControlPanel />}
    </div>
  );
}