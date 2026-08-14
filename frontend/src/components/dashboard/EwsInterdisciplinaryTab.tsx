"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Cpu,
  BookOpen,
  AlertTriangle,
  Award,
  Users,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Filter,
  Eye,
  Activity,
  Layers,
} from "lucide-react";
import CustomDropdownSelect, { type CustomSelectOption } from "@/components/dashboard/CustomDropdownSelect";
import EwsInterdisciplinaryDrawer, {
  type StudentInterdisciplinaryDetail,
} from "@/components/dashboard/EwsInterdisciplinaryDrawer";
import { api } from "@/lib/api";

interface ClusterConfigItem {
  code: string;
  name: string;
  full_name: string;
  description: string;
  icon: string;
  color: string;
  pillar_count: number;
  pillars: Array<{ id: string; name: string; weight: number }>;
}

interface ClusterOverviewData {
  cluster_code: string;
  total_students: number;
  avg_cluster_risk: number;
  risk_distribution: Record<string, number>;
  bottleneck_count: number;
  bottleneck_ratio: number;
  top_bottlenecks: Array<{ subject_name: string; count: number; percentage: number }>;
}

interface StudentInterdisciplinaryRow {
  student_code: string;
  student_name: string;
  class_name: string;
  grade_id?: number | null;
  cluster_code: string;
  cluster_name: string;
  cluster_risk_score: number;
  cluster_risk_level: string;
  bottleneck_subject?: string | null;
  bottleneck_risk?: number | null;
  anchor_subject?: string | null;
  anchor_risk?: number | null;
  disparity_index: number;
  has_llm: boolean;
  pillars: Array<{
    pillar_id: string;
    pillar_name: string;
    weight: number;
    risk_score: number;
    risk_level: string;
    is_active: boolean;
    enrolled_subjects: any[];
  }>;
}

const RISK_COLORS: Record<string, string> = {
  CRITICAL: "#ef4444",
  HIGH: "#f97316",
  MODERATE: "#eab308",
  LOW: "#22c55e",
};

export default function EwsInterdisciplinaryTab({
  schoolYearId,
  semesterIndex,
  week,
  modelVersion,
  refreshKey = 0,
}: {
  schoolYearId: number;
  semesterIndex: number;
  week: number;
  modelVersion: string;
  refreshKey?: number;
}) {
  const [clusters, setClusters] = useState<ClusterConfigItem[]>([]);
  const [activeCluster, setActiveCluster] = useState<string>("STEM");
  const [overview, setOverview] = useState<ClusterOverviewData | null>(null);
  const [students, setStudents] = useState<StudentInterdisciplinaryRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalPages, setTotalPages] = useState(1);
  const [pageInput, setPageInput] = useState("1");

  // Filters
  const [riskLevel, setRiskLevel] = useState<string>("ALL");
  const [gradeId, setGradeId] = useState<string>("ALL");
  const [className, setClassName] = useState<string>("ALL");
  const [bottleneckOnly, setBottleneckOnly] = useState<boolean>(false);

  const [loading, setLoading] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<StudentInterdisciplinaryDetail | null>(null);

  // 1. Fetch danh sách Cụm
  useEffect(() => {
    api
      .get<ClusterConfigItem[]>("/ews/interdisciplinary/clusters")
      .then((data) => {
        if (Array.isArray(data)) setClusters(data);
      })
      .catch((err) => console.error("Load clusters error:", err));
  }, []);

  // 2. Fetch Overview & Students
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Overview
      const ovRes = await api.get<ClusterOverviewData>(
        `/ews/interdisciplinary/overview?school_year_id=${schoolYearId}&semester_index=${semesterIndex}&week=${week}&cluster_code=${activeCluster}${
          modelVersion ? `&model_version=${modelVersion}` : ""
        }`
      );
      setOverview(ovRes);

      // Students
      const params = new URLSearchParams({
        school_year_id: String(schoolYearId),
        semester_index: String(semesterIndex),
        week: String(week),
        cluster_code: activeCluster,
        risk_level: riskLevel,
        page: String(page),
        page_size: String(pageSize),
        bottleneck_only: String(bottleneckOnly),
      });
      if (gradeId !== "ALL") params.append("grade_id", gradeId);
      if (className !== "ALL") params.append("class_name", className);
      if (modelVersion) params.append("model_version", modelVersion);

      const stRes = await api.get<{ items: StudentInterdisciplinaryRow[]; total: number; total_pages: number }>(
        `/ews/interdisciplinary/students?${params.toString()}`
      );
      setStudents(stRes.items || []);
      setTotal(stRes.total || 0);
      setTotalPages(stRes.total_pages || 1);
      setPageInput(String(page));
    } catch (err) {
      console.error("Fetch interdisciplinary data error:", err);
    } finally {
      setLoading(false);
    }
  }, [schoolYearId, semesterIndex, week, activeCluster, riskLevel, gradeId, className, bottleneckOnly, page, pageSize, modelVersion, refreshKey]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle Page input
  const handlePageJump = () => {
    const p = parseInt(pageInput, 10);
    if (!isNaN(p) && p >= 1 && p <= totalPages) {
      setPage(p);
    } else {
      setPageInput(String(page));
    }
  };

  const riskOptions: CustomSelectOption[] = [
    { value: "ALL", label: "Tất cả mức rủi ro" },
    { value: "CRITICAL", label: "Nghiêm trọng (CRITICAL)" },
    { value: "HIGH", label: "Cao (HIGH)" },
    { value: "MODERATE", label: "Trung bình (MODERATE)" },
    { value: "LOW", label: "Thấp (LOW)" },
  ];

  const gradeOptions: CustomSelectOption[] = [
    { value: "ALL", label: "Tất cả các khối" },
    { value: "6", label: "Khối 6" },
    { value: "7", label: "Khối 7" },
    { value: "8", label: "Khối 8" },
    { value: "9", label: "Khối 9" },
    { value: "10", label: "Khối 10" },
    { value: "11", label: "Khối 11" },
  ];

  const currentClusterCfg = clusters.find((c) => c.code === activeCluster);

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* CỤM SELECTOR TABS */}
      <div className="flex items-center justify-between gap-4 flex-wrap border-b border-slate-200 dark:border-slate-800 pb-3">
        <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-800/80 p-1.5 rounded-2xl border border-slate-200/60 dark:border-slate-700/60 shadow-2xs">
          <button
            type="button"
            onClick={() => {
              setActiveCluster("STEM");
              setPage(1);
            }}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${
              activeCluster === "STEM"
                ? "bg-white dark:bg-slate-900 text-brand-600 dark:text-brand-400 shadow-sm border border-slate-200/60 dark:border-slate-800"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 hover:bg-slate-200/40"
            }`}
          >
            <Cpu className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <span>Liên Môn STEM (5 Trụ Cột)</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveCluster("WAR_AND_PEACE");
              setPage(1);
            }}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${
              activeCluster === "WAR_AND_PEACE"
                ? "bg-white dark:bg-slate-900 text-pink-600 dark:text-pink-400 shadow-sm border border-slate-200/60 dark:border-slate-800"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 hover:bg-slate-200/40"
            }`}
          >
            <BookOpen className="w-4 h-4 text-pink-500" />
            <span>Chiến Tranh & Hòa Bình (Xã Hội)</span>
          </button>
        </div>

        <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2">
          <span>Đang phân tích:</span>
          <span className="font-semibold text-slate-800 dark:text-slate-200">
            {currentClusterCfg?.description || "Tổ hợp tích hợp"}
          </span>
        </div>
      </div>

      {/* KPI OVERVIEW CARDS */}
      {overview && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Tổng số học sinh */}
          <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs space-y-2 hover:border-slate-300 dark:hover:border-slate-700 transition-all flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Quy Mô Học Sinh</span>
              <div className="p-2 rounded-xl bg-brand-50 dark:bg-brand-950/50 text-brand-600 dark:text-brand-400">
                <Users className="w-4 h-4" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-mono font-black text-slate-900 dark:text-white">
                {overview.total_students}
              </span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-brand-50 dark:bg-brand-950/60 text-brand-600 dark:text-brand-400 font-mono">
                Học sinh
              </span>
            </div>
            <div className="text-[11px] text-slate-400 font-medium">
              Có kết quả dự báo trong tuần {week}
            </div>
          </div>

          {/* Card 2: Điểm rủi ro trung bình cụm */}
          <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs space-y-2 hover:border-slate-300 dark:hover:border-slate-700 transition-all flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Rủi Ro Trung Bình</span>
              <div className="p-2 rounded-xl bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400">
                <Activity className="w-4 h-4" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-mono font-black text-brand-600 dark:text-brand-400">
                {overview.avg_cluster_risk.toFixed(2)}
              </span>
              <span className="text-[11px] text-slate-400 font-mono">/ 100</span>
            </div>
            <div className="w-full">
              <div className="h-1.5 w-full rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(100, overview.avg_cluster_risk)}%`,
                    backgroundColor:
                      overview.avg_cluster_risk >= 70
                        ? "#ef4444"
                        : overview.avg_cluster_risk >= 50
                        ? "#f97316"
                        : overview.avg_cluster_risk >= 30
                        ? "#eab308"
                        : "#10b981",
                  }}
                />
              </div>
            </div>
          </div>

          {/* Card 3: Số học sinh bị nghẽn Bottleneck */}
          <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs space-y-2 hover:border-slate-300 dark:hover:border-slate-700 transition-all flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Nút Thắt (Bottleneck)</span>
              <div className="p-2 rounded-xl bg-rose-50 dark:bg-rose-950/50 text-rose-600 dark:text-rose-400">
                <AlertTriangle className="w-4 h-4" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-mono font-black text-rose-600 dark:text-rose-400">
                {overview.bottleneck_count}
              </span>
              <span className="text-[11px] font-bold font-mono px-2 py-0.5 rounded-full bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-900/50">
                {overview.bottleneck_ratio}% cụm
              </span>
            </div>
            <div className="text-[11px] text-slate-400 font-medium">
              Có 1 môn kéo tụt cả cụm liên môn
            </div>
          </div>

          {/* Card 4: Phân bổ 4 mức rủi ro */}
          {(() => {
            const total = overview.total_students || 1;
            const cCrit = overview.risk_distribution["CRITICAL"] || 0;
            const cHigh = overview.risk_distribution["HIGH"] || 0;
            const cMod = overview.risk_distribution["MODERATE"] || 0;
            const cLow = overview.risk_distribution["LOW"] || 0;

            const pCrit = ((cCrit / total) * 100).toFixed(0);
            const pHigh = ((cHigh / total) * 100).toFixed(0);
            const pMod = ((cMod / total) * 100).toFixed(0);
            const pLow = ((cLow / total) * 100).toFixed(0);

            return (
              <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs space-y-2 hover:border-slate-300 dark:hover:border-slate-700 transition-all flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Phân Bổ 4 Mức Rủi Ro</span>
                  <div className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                    <Layers className="w-4 h-4" />
                  </div>
                </div>

                {/* Thanh phân bố đa sắc thái */}
                <div className="space-y-1.5">
                  <div className="flex h-2 w-full rounded-full overflow-hidden bg-slate-100 dark:bg-slate-800 p-0.5 gap-0.5 shadow-2xs">
                    <div style={{ width: `${pCrit}%` }} className="h-full rounded-xs bg-rose-600 transition-all" title={`CRITICAL: ${cCrit}`} />
                    <div style={{ width: `${pHigh}%` }} className="h-full rounded-xs bg-orange-500 transition-all" title={`HIGH: ${cHigh}`} />
                    <div style={{ width: `${pMod}%` }} className="h-full rounded-xs bg-amber-500 transition-all" title={`MODERATE: ${cMod}`} />
                    <div style={{ width: `${pLow}%` }} className="h-full rounded-xs bg-emerald-500 transition-all" title={`LOW: ${cLow}`} />
                  </div>

                  <div className="grid grid-cols-4 gap-1 text-center pt-0.5">
                    <div className="px-1 py-0.5 rounded bg-rose-50 dark:bg-rose-950/40 border border-rose-200/60 dark:border-rose-900/40">
                      <span className="text-[9px] font-bold text-rose-500 uppercase block">Crit</span>
                      <span className="text-[11px] font-mono font-black text-rose-700 dark:text-rose-300">{cCrit}</span>
                    </div>
                    <div className="px-1 py-0.5 rounded bg-orange-50 dark:bg-orange-950/40 border border-orange-200/60 dark:border-orange-900/40">
                      <span className="text-[9px] font-bold text-orange-500 uppercase block">High</span>
                      <span className="text-[11px] font-mono font-black text-orange-700 dark:text-orange-300">{cHigh}</span>
                    </div>
                    <div className="px-1 py-0.5 rounded bg-amber-50 dark:bg-amber-950/40 border border-amber-200/60 dark:border-amber-900/40">
                      <span className="text-[9px] font-bold text-amber-500 uppercase block">Mod</span>
                      <span className="text-[11px] font-mono font-black text-amber-700 dark:text-amber-300">{cMod}</span>
                    </div>
                    <div className="px-1 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200/60 dark:border-emerald-900/40">
                      <span className="text-[9px] font-bold text-emerald-500 uppercase block">Low</span>
                      <span className="text-[11px] font-mono font-black text-emerald-700 dark:text-emerald-300">{cLow}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* FILTER TOOLBAR */}
      <div className="p-4 rounded-2xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/80 dark:border-slate-800 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap flex-1">
          <div className="flex items-center gap-1.5 text-slate-400 text-xs font-semibold">
            <Filter className="w-3.5 h-3.5" />
            <span>Bộ lọc:</span>
          </div>

          <div className="w-48">
            <CustomDropdownSelect
              value={riskLevel}
              onChange={(v) => {
                setRiskLevel(v);
                setPage(1);
              }}
              options={riskOptions}
              placeholder="Mức rủi ro"
            />
          </div>

          <div className="w-40">
            <CustomDropdownSelect
              value={gradeId}
              onChange={(v) => {
                setGradeId(v);
                setPage(1);
              }}
              options={gradeOptions}
              placeholder="Khối lớp"
            />
          </div>

          <button
            type="button"
            onClick={() => {
              setBottleneckOnly(!bottleneckOnly);
              setPage(1);
            }}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all border ${
              bottleneckOnly
                ? "bg-rose-500 text-white border-rose-500 shadow-2xs"
                : "bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-100"
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Chỉ Học Sinh Bị Kẹt Bottleneck</span>
          </button>
        </div>

        <div className="text-xs text-slate-500 font-medium">
          Tìm thấy <strong className="text-slate-900 dark:text-white">{total}</strong> học sinh
        </div>
      </div>

      {/* DATA TABLE */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden bg-white dark:bg-slate-900 shadow-2xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 font-semibold border-b border-slate-200 dark:border-slate-800 uppercase tracking-wider text-[10px]">
              <tr>
                <th className="py-3 px-4">Học Sinh</th>
                <th className="py-3 px-4">Lớp</th>
                <th className="py-3 px-4 text-center">Rủi Ro Cụm</th>
                <th className="py-3 px-4">Phân Bổ Các Trụ Cột</th>
                <th className="py-3 px-4">Môn Kéo Tụt (Bottleneck)</th>
                <th className="py-3 px-4">Môn Nâng Đỡ (Anchor)</th>
                <th className="py-3 px-4 text-right">Chi Tiết</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    Đang tính toán rủi ro liên môn...
                  </td>
                </tr>
              ) : students.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    Không có học sinh nào phù hợp với bộ lọc.
                  </td>
                </tr>
              ) : (
                students.map((st) => {
                  const riskColor = RISK_COLORS[st.cluster_risk_level] || "#94a3b8";

                  return (
                    <tr
                      key={st.student_code}
                      className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors"
                    >
                      {/* Học sinh */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-900 dark:text-white">
                            {st.student_name}
                          </span>
                          <span className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
                            {st.student_code}
                          </span>
                          {st.has_llm && (
                            <Sparkles className="w-3.5 h-3.5 text-amber-500 fill-amber-400/30" />
                          )}
                        </div>
                      </td>

                      {/* Lớp */}
                      <td className="py-3 px-4">
                        <span className="font-semibold text-slate-800 dark:text-slate-200">
                          {st.class_name ? st.class_name.replace(/\s*-\s*Trường\s*\d+/gi, "").replace(/^Lớp\s+/i, "") : "—"}
                        </span>
                      </td>

                      {/* 2-Tone Risk Badge Cụm */}
                      <td className="py-3 px-4 text-center whitespace-nowrap">
                        <div
                          className="inline-flex items-stretch rounded-full border overflow-hidden shadow-2xs text-[10px] font-semibold"
                          style={{ borderColor: `${riskColor}50` }}
                        >
                          <span
                            className="px-2.5 py-0.5 text-white uppercase tracking-wider"
                            style={{ backgroundColor: riskColor }}
                          >
                            {st.cluster_risk_level}
                          </span>
                          <span
                            className="px-2.5 py-0.5 font-mono font-bold"
                            style={{ backgroundColor: `${riskColor}18`, color: riskColor }}
                          >
                            {st.cluster_risk_score.toFixed(2)}
                          </span>
                        </div>
                      </td>

                      {/* Phân bổ các trụ cột môn */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {st.pillars.map((p) => {
                            const pCol = RISK_COLORS[p.risk_level] || "#94a3b8";
                            if (!p.is_active) {
                              return (
                                <span
                                  key={p.pillar_id}
                                  title={`${p.pillar_name}: Không đăng ký học`}
                                  className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-400 opacity-50"
                                >
                                  {p.pillar_name.split(" ")[0]}
                                </span>
                              );
                            }
                            return (
                              <span
                                key={p.pillar_id}
                                title={`${p.pillar_name}: Rủi ro ${p.risk_score.toFixed(2)} (${p.risk_level})`}
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold font-mono border"
                                style={{
                                  backgroundColor: `${pCol}15`,
                                  borderColor: `${pCol}40`,
                                  color: pCol,
                                }}
                              >
                                <span>{p.pillar_name.split(" ")[0]}:</span>
                                <strong>{p.risk_score.toFixed(2)}</strong>
                              </span>
                            );
                          })}
                        </div>
                      </td>

                      {/* Môn Kéo Tụt (Bottleneck) */}
                      <td className="py-3 px-4">
                        {st.bottleneck_subject ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-bold bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-900/50">
                            <AlertTriangle className="w-3 h-3 text-rose-500 shrink-0" />
                            <span>{st.bottleneck_subject}</span>
                            <span className="font-mono text-[10px]">({st.bottleneck_risk?.toFixed(2)})</span>
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>

                      {/* Môn Nâng Đỡ (Anchor) */}
                      <td className="py-3 px-4">
                        {st.anchor_subject ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-900/50">
                            <Award className="w-3 h-3 text-emerald-500 shrink-0" />
                            <span>{st.anchor_subject}</span>
                            <span className="font-mono text-[10px]">({st.anchor_risk?.toFixed(2)})</span>
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>

                      {/* Nút Xem chi tiết */}
                      <td className="py-3 px-4 text-right">
                        <button
                          type="button"
                          onClick={() => setSelectedStudent(st as StudentInterdisciplinaryDetail)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-brand-50 hover:text-brand-600 dark:hover:bg-brand-950/50 dark:hover:text-brand-400 transition-all border border-slate-200/60 dark:border-slate-700/60"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>Chi Tiết</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* PHÂN TRANG (PAGINATION) */}
        {totalPages > 1 && (
          <div className="p-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between gap-4 flex-wrap">
            <span className="text-xs text-slate-500">
              Trang <strong>{page}</strong> / <strong>{totalPages}</strong> ({total} học sinh)
            </span>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage(1)}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed"
                title="Về trang đầu"
              >
                <ChevronsLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed"
                title="Trang trước"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              <div className="flex items-center gap-1 text-xs">
                <span className="text-slate-400">Trang</span>
                <input
                  type="text"
                  value={pageInput}
                  onChange={(e) => setPageInput(e.target.value)}
                  onBlur={handlePageJump}
                  onKeyDown={(e) => e.key === "Enter" && handlePageJump()}
                  className="w-12 text-center py-1 px-1.5 rounded-lg border border-slate-200 dark:border-slate-700 font-mono font-bold text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
                <span className="text-slate-400">/ {totalPages}</span>
              </div>

              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed"
                title="Trang sau"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage(totalPages)}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed"
                title="Tới trang cuối"
              >
                <ChevronsRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* DRAWER CHI TIẾT */}
      {selectedStudent && (
        <EwsInterdisciplinaryDrawer
          item={selectedStudent}
          onClose={() => setSelectedStudent(null)}
          week={week}
        />
      )}
    </div>
  );
}
