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
  const [modelVersion, setModelVersion] = useState<string>("v1_single");
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
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Dashboard</h2>
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-brand-600 text-white">BETA</span>
          </div>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Hệ thống phân tích & cảnh báo sớm học tập (EWS)
          </p>
        </div>
      </div>

      {/* HEADER SECTION — Hệ Thống Cảnh Báo Rủi Ro Học Tập (CatBoost EWS) */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-6 rounded-2xl shadow-lg border border-indigo-500/20">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-7 h-7 text-rose-400 animate-pulse" />
            <h2 className="text-2xl font-bold tracking-tight">Hệ Thống Cảnh Báo Rủi Ro Học Tập (CatBoost EWS)</h2>
          </div>
          <p className="text-sm text-slate-300">
            Dự báo sớm 4 mức độ rủi ro (`LOW`, `MODERATE`, `HIGH`, `CRITICAL`) từ mô hình GBDT dựa trên 22 chỉ số tiến trình học tập, LMS và nếp sống kỷ luật.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Mốc Đánh Giá (Tuần / Kỳ) */}
          <div className="flex items-center gap-2">
            <label className="text-xs font-medium text-slate-300 whitespace-nowrap">Mốc Đánh Giá</label>
            <select
              value={`${schoolYearId}-${semesterIndex}-${week}`}
              onChange={(e) => {
                const [sy, sem, wk] = e.target.value.split("-").map(Number);
                setSchoolYearId(sy);
                setSemesterIndex(sem);
                setWeek(wk);
                setRefreshKey((k) => k + 1);
              }}
              className="text-xs bg-slate-800/80 border border-slate-600/60 rounded-xl px-3 py-2 text-white focus:ring-2 focus:ring-indigo-500 font-medium"
            >
              {weeks.map((w, idx) => (
                <option key={idx} value={`${w.school_year_id}-${w.semester_index}-${w.evaluated_at_week}`}>
                  {w.school_year_name || `Năm ${w.school_year_id}`} - HK{w.semester_index} (Tuần {w.evaluated_at_week})
                </option>
              ))}
            </select>
          </div>
          {/* Phiên bản Model */}
          <div className="flex items-center gap-2">
            <label className="text-xs font-medium text-slate-300 whitespace-nowrap">Phiên bản Model</label>
            <select
              value={modelVersion}
              onChange={(e) => {
                setModelVersion(e.target.value);
                setRefreshKey((k) => k + 1);
              }}
              className="text-xs bg-slate-800/80 border border-slate-600/60 rounded-xl px-3 py-2 text-white focus:ring-2 focus:ring-indigo-500 font-medium"
            >
              <option value="v1_single">v1 — Model đơn (hiện tại)</option>
              <option value="v2_ensemble">v2 — Factor-Ensemble (mới)</option>
            </select>
          </div>
          <button
            onClick={() => setRefreshKey((k) => k + 1)}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600/80 hover:bg-indigo-600 text-white font-medium text-sm rounded-xl transition-all shadow-sm"
          >
            <RefreshCw className="w-4 h-4" /> Làm mới
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