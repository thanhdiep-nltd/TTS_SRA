"use client";

import { useState } from "react";
import { ShieldAlert } from "lucide-react";
import EwsWarningTab from "@/components/dashboard/EwsWarningTab";

type TabKey = "ews";

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: "ews", label: "Cảnh báo EWS", icon: ShieldAlert },
];

export default function DashboardV2Page() {
  const [tab, setTab] = useState<TabKey>("ews");

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

      {/* Tab bar */}
      <div className="flex flex-wrap gap-2">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition ${
                active
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
      {tab === "ews" && <EwsWarningTab />}
    </div>
  );
}
