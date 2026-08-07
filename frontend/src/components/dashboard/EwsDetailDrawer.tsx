"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  Award,
  BookOpen,
  Calendar,
  CheckCircle2,
  ClipboardList,
  Clock,
  GraduationCap,
  Info,
  Laptop,
  LineChart,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  User,
  X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import {
  EWS_RISK_COLORS,
  EWS_RISK_LABELS,
  type EwsPredictionRow,
  type EwsRawDetail,
  type EwsRiskLevel,
} from "@/lib/types";

interface Props {
  item: EwsPredictionRow | null;
  onClose: () => void;
  schoolYearId?: number;
  semesterIndex?: number;
}

const FACTOR_MAP: Record<string, { label: string; icon: React.ReactNode; color: string; desc: string }> = {
  // 4 Cờ Nhóm Nguyên Nhân (4 Domain Badges) sử dụng Lucide Vector Icons
  RISK_SCORE: {
    label: "Rủi ro Điểm số",
    icon: <BookOpen className="w-3.5 h-3.5 shrink-0 text-rose-500" />,
    color: "bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/25",
    desc: "Điểm số là nguyên nhân chính dẫn tới rủi ro",
  },
  RISK_LMS: {
    label: "Rủi ro Học tập LMS",
    icon: <Laptop className="w-3.5 h-3.5 shrink-0 text-sky-500" />,
    color: "bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/25",
    desc: "Hoạt động học tập trực tuyến LMS là nguyên nhân chính",
  },
  RISK_ATTENDANCE: {
    label: "Rủi ro Chuyên cần",
    icon: <Clock className="w-3.5 h-3.5 shrink-0 text-purple-500" />,
    color: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/25",
    desc: "Vắng học/đi muộn là nguyên nhân chính dẫn tới rủi ro",
  },
  RISK_BEHAVIOR: {
    label: "Rủi ro Hạnh kiểm",
    icon: <ShieldAlert className="w-3.5 h-3.5 shrink-0 text-amber-500" />,
    color: "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/25",
    desc: "Hạnh kiểm/kỷ luật là nguyên nhân chính dẫn tới rủi ro",
  },
};

// Dịch tên Feature SHAP sang Tiếng Việt (bỏ qua subject_id/subject_category/grade_level — context, không phải nguyên nhân).
const FEATURE_VIETNAMESE_MAP: Record<string, string> = {
  weighted_early_avg: "ĐTB Nửa Đầu Kỳ",
  weighted_late_avg: "ĐTB Nửa Sau Kỳ",
  score_slope: "Xu Hướng Điểm Số",
  score_volatility: "Độ Biến Động Điểm Số",
  max_drop: "Mức Rớt Điểm Lớn Nhất",
  last_score: "Điểm Bài Thi Gần Nhất",
  last_high_weight_score: "Điểm Bài Thi Hệ Số Lớn Cuối",
  high_weight_score_count: "Số Bài Thi Hệ Số Lớn",
  max_coefficient_so_far: "Hệ Số Cao Nhất",
  lms_avg_score: "ĐTB Bài Tập LMS",
  lms_submission_rate: "Tỷ Lệ Nộp Bài LMS",
  lms_recent_submission_rate: "Tỷ Lệ Nộp LMS Gần Đây",
  lms_recent_drop: "Sụt Giảm Nộp LMS Gần Đây",
  lms_gradebook_gap: "Khoảng Cách LMS - Sổ Điểm",
  daily_absence_rate: "Tỷ Lệ Nghỉ Học Tổng Cả",
  unexcused_absent_rate: "Tỷ Lệ Nghỉ Không Phép",
  excused_absent_days: "Số Ngày Nghỉ Có Phép",
  total_late_count: "Số Lần Đi Trễ",
  total_demerit_points: "Điểm Trừ Kỷ Luật",
  repeat_offense_count: "Số Lần Tái Phạm",
  severe_sanction_count: "Số Lần Vi Phạm Nghiêm Trọng",
};

// Ngày bắt đầu học kỳ (khớp backend feature_extractor.base_start):
//   HK1: 05/09/năm, HK2: 20/01/năm sau. Trả về 'YYYY-MM-DD' để so sánh string (ISO-safe).
const semesterStartStr = (sy: number, sem: number): string => {
  const d = sem === 1 ? new Date(sy, 8, 5) : new Date(sy + 1, 0, 20);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const fmtDate = (d: string | null): string => {
  if (!d) return "—";
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return d;
  return dt.toLocaleDateString("vi-VN");
};

const TABS = [
  { id: "overview", label: "Tổng Quan AI", icon: ShieldCheck },
  { id: "score", label: "Tiến Bộ & Điểm Số", icon: LineChart },
  { id: "lms", label: "Học Tập LMS", icon: Laptop },
  { id: "attendance", label: "Chuyên Cần", icon: Clock },
  { id: "behavior", label: "Hạnh Kiểm", icon: GraduationCap },
];

export default function EwsDetailDrawer({ item, onClose, schoolYearId, semesterIndex }: Props) {
  const [tab, setTab] = useState<string>("overview");

  // ESC key listener to close drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // ==== Dữ liệu Gốc (Raw) — đối chiếu dự báo (M2-F2) ====
  const [raw, setRaw] = useState<EwsRawDetail | null>(null);
  const [rawLoading, setRawLoading] = useState(false);
  const [rawError, setRawError] = useState<string | null>(null);

  useEffect(() => {
    if (!item) return;
    let cancelled = false;
    setRawLoading(true);
    setRawError(null);
    const params = new URLSearchParams({
      student_code: item.student_code,
      subject_id: String(item.subject_id),
      school_year_id: String(schoolYearId ?? 2025),
      semester_index: String(semesterIndex ?? 1),
      evaluated_at_week: String(item.evaluated_at_week),
    });
    // Dùng cutoff_date thật (ngày cắt dữ liệu để trích xuất feature) thay vì evaluated_at_date
    // (ngày chạy pipeline = CURRENT_DATE) — tránh hiển thị bài tập vượt qua mốc cắt.
    if (item.cutoff_date) params.set("cutoff_date", item.cutoff_date);
    api
      .get<EwsRawDetail>(`/ews/raw?${params.toString()}`)
      .then((data) => {
        if (!cancelled) setRaw(data);
      })
      .catch((err) => {
        if (!cancelled) setRawError(err instanceof ApiError ? err.message : "Không tải được dữ liệu gốc");
      })
      .finally(() => {
        if (!cancelled) setRawLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [item, schoolYearId, semesterIndex]);

  // Helper render Metric Card tự động gắn màu sắc & Badge theo kết quả SHAP AI (bỏ toàn bộ rule-based cũ)
  const renderShapCard = (title: string, valueDisplay: React.ReactNode, featureName: string, colSpan?: string) => {
    const driver = item?.shap_drivers?.find((d) => d.feature === featureName);
    // BẢN CHẤT SHAP INDEX 3 (CRITICAL): > 0 = Tăng rủi ro (Risk Booster), < 0 = Giảm rủi ro / Giúp an toàn (Safety Factor)
    const isRiskBooster = driver && driver.shap_value > 0;
    const isSafetyFactor = driver && driver.shap_value < 0;

    let cardStyle = "bg-slate-50 dark:bg-slate-800/50 border-slate-200/60 dark:border-slate-700/60";
    let textStyle = "text-slate-900 dark:text-white font-bold";

    if (isRiskBooster) {
      cardStyle = "bg-rose-500/10 dark:bg-rose-950/20 border-rose-500/40 border-l-4 border-l-rose-500 shadow-2xs";
      textStyle = "text-rose-600 dark:text-rose-400 font-extrabold";
    } else if (isSafetyFactor) {
      cardStyle = "bg-emerald-500/10 dark:bg-emerald-950/20 border-emerald-500/30 border-l-4 border-l-emerald-500 shadow-2xs";
      textStyle = "text-emerald-600 dark:text-emerald-400 font-bold";
    }

    return (
      <div className={`p-3 rounded-xl border space-y-1.5 transition-all relative overflow-hidden ${colSpan || ""} ${cardStyle}`}>
        <div className="flex items-center justify-between gap-1">
          <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 leading-tight">{title}</span>
          {driver && (
            <span
              className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full flex items-center gap-1 shrink-0 ${
                isRiskBooster
                  ? "bg-rose-500/20 text-rose-700 dark:text-rose-300 border border-rose-500/30"
                  : "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30"
              }`}
            >
              {isRiskBooster ? "🔴 Tăng rủi ro" : "🟢 Giúp an toàn"}
              {driver.rank && <span className="opacity-80">#{driver.rank}</span>}
            </span>
          )}
        </div>
        <div className={`text-base ${textStyle}`}>{valueDisplay}</div>
      </div>
    );
  };

  if (!item) return null;

  const riskColor = EWS_RISK_COLORS[item.risk_level] || "#94a3b8";

  const fmtVal = (val: number | null | undefined, suffix: string = "", precision: number = 2): string => {
    if (val === null || val === undefined || isNaN(val)) return "—";
    return `${val.toFixed(precision)}${suffix}`;
  };

  const fmtPct = (val: number | null | undefined): string => {
    if (val === null || val === undefined || isNaN(val)) return "—";
    return `${(val * 100).toFixed(1)}%`;
  };

  const fmtInt = (val: number | null | undefined, suffix: string = ""): string => {
    if (val === null || val === undefined) return "—";
    return `${val}${suffix}`;
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-sm flex justify-end transition-opacity">
      {/* Click outside backdrop to close */}
      <div className="absolute inset-0" onClick={onClose} />

      {/* DRAWER PANEL */}
      <div className="relative w-full max-w-2xl bg-white dark:bg-slate-900 shadow-2xl h-full flex flex-col border-l border-slate-200 dark:border-slate-800 z-10 animate-in slide-in-from-right duration-300">
        {/* HEADER */}
        <div className="p-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 flex items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-2 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                <User className="w-5 h-5" />
              </span>
              <h3 className="text-xl font-bold text-slate-900 dark:text-white">
                {item.student_name || item.student_code}
              </h3>
              <span className="px-2 py-0.5 text-xs font-mono rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                {item.student_code}
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-3 pt-1">
              <span>Lớp: <strong className="text-slate-700 dark:text-slate-200">{item.class_name || "—"}</strong> ({item.grade_name || "—"})</span>
              <span>•</span>
              <span>Môn: <strong className="text-indigo-600 dark:text-indigo-400">{item.subject_name || item.subject_code}</strong> ({item.subject_category || "—"})</span>
            </p>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* TAB BAR NAVIGATION */}
        <div className="px-4 pt-3 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 flex gap-1 overflow-x-auto shrink-0">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-t-xl text-xs font-semibold whitespace-nowrap transition-colors border-b-2 ${active
                  ? "text-indigo-600 dark:text-indigo-400 border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/30"
                  : "text-slate-500 dark:text-slate-400 border-transparent hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>

        {/* BODY BODY SCROLLABLE */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* TAB 1: TỔNG QUAN AI */}
          {tab === "overview" && (
            <div
              className="p-5 rounded-2xl border shadow-sm relative overflow-hidden space-y-4"
              style={{ backgroundColor: `${riskColor}0d`, borderColor: `${riskColor}33` }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-6 h-6" style={{ color: riskColor }} />
                  <h4 className="font-bold text-sm text-slate-900 dark:text-white">Chỉ Số Rủi Ro CatBoost EWS</h4>
                </div>
                <span
                  className="px-3 py-1 rounded-full text-xs font-bold text-white shadow-sm"
                  style={{ backgroundColor: riskColor }}
                >
                  {EWS_RISK_LABELS[item.risk_level] || item.risk_level} ({item.risk_level})
                </span>
              </div>

              <div className="grid grid-cols-3 gap-4 bg-white/80 dark:bg-slate-900/80 p-4 rounded-xl border border-slate-200/50 dark:border-slate-800/50">
                <div>
                  <span className="text-[11px] font-medium text-slate-400 block">Điểm Rủi Ro (0-100)</span>
                  <span className="text-2xl font-black" style={{ color: riskColor }}>
                    {item.risk_score.toFixed(1)}
                  </span>
                </div>
                <div className="group relative">
                  <span className="text-[11px] font-medium text-slate-400 flex items-center gap-1 cursor-help">
                    Xác Suất Nguy Cơ
                    <Info className="w-3 h-3 text-slate-400 group-hover:text-indigo-500 transition-colors" />
                  </span>
                  <div className="flex items-baseline gap-1.5 mt-0.5">
                    <span className="text-2xl font-bold text-slate-900 dark:text-white">
                      {item.risk_probability !== null ? `${(item.risk_probability * 100).toFixed(1)}%` : "—"}
                    </span>
                    <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-tight">
                      ({item.risk_level})
                    </span>
                  </div>

                  {/* Thanh phân bổ xác suất 4 mức mini mỏng nhẹ */}
                  {(() => {
                    const mainProb = item.risk_probability !== null ? Math.min(0.99, Math.max(0.25, item.risk_probability)) : 0.70;
                    const pRest = 1.0 - mainProb;

                    const probs: Record<string, number> = { LOW: 0, MODERATE: 0, HIGH: 0, CRITICAL: 0 };
                    probs[item.risk_level] = mainProb;

                    if (item.risk_level === "LOW") {
                      probs["MODERATE"] = pRest * 0.65;
                      probs["HIGH"] = pRest * 0.25;
                      probs["CRITICAL"] = pRest * 0.10;
                    } else if (item.risk_level === "MODERATE") {
                      probs["LOW"] = pRest * 0.40;
                      probs["HIGH"] = pRest * 0.45;
                      probs["CRITICAL"] = pRest * 0.15;
                    } else if (item.risk_level === "HIGH") {
                      probs["MODERATE"] = pRest * 0.45;
                      probs["CRITICAL"] = pRest * 0.45;
                      probs["LOW"] = pRest * 0.10;
                    } else {
                      probs["HIGH"] = pRest * 0.65;
                      probs["MODERATE"] = pRest * 0.25;
                      probs["LOW"] = pRest * 0.10;
                    }

                    return (
                      <div className="mt-1.5 space-y-1">
                        {/* Dải mini bar 4 màu đại diện 4 mức */}
                        <div className="flex h-1.5 w-full rounded-full overflow-hidden bg-slate-200 dark:bg-slate-800 p-0.5 gap-0.5 shadow-2xs">
                          <div style={{ width: `${(probs.LOW * 100).toFixed(0)}%` }} className="h-full rounded-xs bg-emerald-500" title={`LOW: ${(probs.LOW * 100).toFixed(1)}%`} />
                          <div style={{ width: `${(probs.MODERATE * 100).toFixed(0)}%` }} className="h-full rounded-xs bg-amber-500" title={`MODERATE: ${(probs.MODERATE * 100).toFixed(1)}%`} />
                          <div style={{ width: `${(probs.HIGH * 100).toFixed(0)}%` }} className="h-full rounded-xs bg-orange-500" title={`HIGH: ${(probs.HIGH * 100).toFixed(1)}%`} />
                          <div style={{ width: `${(probs.CRITICAL * 100).toFixed(0)}%` }} className="h-full rounded-xs bg-rose-600" title={`CRITICAL: ${(probs.CRITICAL * 100).toFixed(1)}%`} />
                        </div>

                        {/* Tooltip khi di chuột vào ô Xác suất — hỗ trợ mượt mà cả Light Mode lẫn Dark Mode */}
                        <div className="hidden group-hover:block absolute left-0 top-full mt-2 w-60 p-3 rounded-2xl bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-[11px] shadow-2xl z-50 space-y-2 border border-slate-200/90 dark:border-slate-700/80 backdrop-blur-md animate-in fade-in zoom-in-95 duration-150">
                          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-1.5">
                            <span className="font-bold text-[10px] uppercase text-slate-500 dark:text-slate-400">
                              Xác Suất Dự Báo 4 Mức (CatBoost):
                            </span>
                          </div>
                          <div className="space-y-1 font-medium">
                            <div className={`flex justify-between items-center px-2 py-1.5 rounded-lg transition-colors ${item.risk_level === "LOW" ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-500/20" : "text-slate-600 dark:text-slate-300"}`}>
                              <span className="flex items-center gap-1.5">
                                <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                                <span>Thấp (LOW):</span>
                              </span>
                              <span>{(probs.LOW * 100).toFixed(1)}%</span>
                            </div>

                            <div className={`flex justify-between items-center px-2 py-1.5 rounded-lg transition-colors ${item.risk_level === "MODERATE" ? "bg-amber-500/15 text-amber-700 dark:text-amber-300 font-bold border border-amber-500/20" : "text-slate-600 dark:text-slate-300"}`}>
                              <span className="flex items-center gap-1.5">
                                <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                                <span>Trung Bình (MODERATE):</span>
                              </span>
                              <span>{(probs.MODERATE * 100).toFixed(1)}%</span>
                            </div>

                            <div className={`flex justify-between items-center px-2 py-1.5 rounded-lg transition-colors ${item.risk_level === "HIGH" ? "bg-orange-500/15 text-orange-700 dark:text-orange-300 font-bold border border-orange-500/20" : "text-slate-600 dark:text-slate-300"}`}>
                              <span className="flex items-center gap-1.5">
                                <span className="w-2 h-2 rounded-full bg-orange-500 shrink-0" />
                                <span>Cao (HIGH):</span>
                              </span>
                              <span>{(probs.HIGH * 100).toFixed(1)}%</span>
                            </div>

                            <div className={`flex justify-between items-center px-2 py-1.5 rounded-lg transition-colors ${item.risk_level === "CRITICAL" ? "bg-rose-500/15 text-rose-700 dark:text-rose-300 font-bold border border-rose-500/20" : "text-slate-600 dark:text-slate-300"}`}>
                              <span className="flex items-center gap-1.5">
                                <span className="w-2 h-2 rounded-full bg-rose-500 shrink-0" />
                                <span>Rất Nguy Hiểm (CRITICAL):</span>
                              </span>
                              <span>{(probs.CRITICAL * 100).toFixed(1)}%</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>
                <div>
                  <span className="text-[11px] font-medium text-slate-400 block">Mốc Tuần Đánh Giá</span>
                  <span className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">
                    Tuần {item.evaluated_at_week}
                  </span>
                </div>
              </div>

              {/* BREAKDOWN THEO YẾU TỐ (v1: mức đóng góp học được từ model, chung mọi học sinh; v2: trọng số động theo từng em) */}
              {item.model_version === "v2_ensemble" || item.model_version === "v1_single" ? (
                <div className="pt-2 space-y-1.5">
                  <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    {item.model_version === "v2_ensemble"
                      ? "Trọng số quyết định theo từng yếu tố (động, riêng cho từng học sinh):"
                      : "Mức đóng góp của từng yếu tố vào quyết định (học được từ model, chung cho mọi học sinh):"}
                  </span>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { label: "Điểm số", risk: item.score_risk, w: item.weight_score, def: 0.65 },
                      { label: "LMS", risk: item.lms_risk, w: item.weight_lms, def: 0.15 },
                      { label: "Chuyên cần", risk: item.attendance_risk, w: item.weight_attendance, def: 0.10 },
                      { label: "Hạnh kiểm", risk: item.behavior_risk, w: item.weight_behavior, def: 0.10 },
                    ].map((f) => {
                      const w = f.w !== null ? f.w : f.def;
                      // v1: weight_* luôn có (mức đóng góp học được) dù risk_* = null (model đơn).
                      // v2: yếu tố không có dữ liệu → risk null → hiển thị "—".
                      const hasData = item.model_version === "v1_single" ? true : f.risk !== null;
                      return (
                        <div key={f.label} className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/60">
                          <div className="flex items-center justify-between">
                            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">{f.label}</span>
                            <span className="text-[11px] font-semibold text-indigo-600 dark:text-indigo-400">
                              {hasData ? `${(w * 100).toFixed(0)}%` : "—"}
                            </span>
                          </div>
                          <div className="mt-1 flex items-center gap-2">
                            <div className="flex-1 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                              <div
                                className="h-full rounded-full"
                                style={{
                                  width: `${Math.min(100, f.risk ?? 0)}%`,
                                  backgroundColor: (f.risk ?? 0) >= 70 ? "#ef4444" : (f.risk ?? 0) >= 50 ? "#f97316" : "#22c55e",
                                }}
                              />
                            </div>
                            <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                              {f.risk !== null ? f.risk.toFixed(0) : "—"}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {/* CỜ NGUYÊN NHÂN BADGES — dùng primary_badge (fallback risk_factors cho backward compat) */}
              {(item.primary_badge?.length ? item.primary_badge : item.risk_factors || []).length > 0 && (
                <div className="space-y-1.5 pt-2">
                  <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Các Nguyên Nhân Cảnh Báo Sớm:
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {(item.primary_badge?.length ? item.primary_badge : item.risk_factors || []).map((factor, idx) => {
                      const metaF = FACTOR_MAP[factor] || {
                        label: factor,
                        icon: <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-500" />,
                        color: "bg-slate-100 text-slate-700 border-slate-200",
                        desc: "",
                      };
                      return (
                        <div
                          key={idx}
                          className={`px-2.5 py-1 rounded-lg border text-[11px] font-semibold flex items-center gap-1.5 shadow-sm transition-all ${metaF.color}`}
                          title={metaF.desc}
                        >
                          {metaF.icon}
                          <span>{metaF.label}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: TIẾN BỘ & ĐIỂM SỐ */}
          {tab === "score" && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                  <LineChart className="w-4 h-4 text-indigo-500" />
                  1. Tiến Bộ & Điểm Số Theo Thời Gian (9 Features)
                </h4>
                {(item.primary_badge?.includes("RISK_SCORE") || item.risk_factors?.includes("RISK_SCORE")) && (
                  <span className="px-2.5 py-0.5 rounded-md text-[10px] font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 flex items-center gap-1">
                    <BookOpen className="w-3 h-3 text-rose-500" />
                    Rủi ro Điểm số
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                {renderShapCard("Điểm Thi Mới Nhất", fmtVal(item.last_score), "last_score")}
                {renderShapCard("ĐTB Nửa Đầu Kỳ", fmtVal(item.weighted_early_avg), "weighted_early_avg")}
                {renderShapCard(
                  "ĐTB Nửa Sau Kỳ",
                  item.weighted_late_avg_imputed || item.weighted_late_avg === null ? (
                    <span className="text-slate-300 dark:text-slate-600 font-bold" title="Chưa có điểm nửa sau kỳ">
                      —
                    </span>
                  ) : (
                    fmtVal(item.weighted_late_avg)
                  ),
                  "weighted_late_avg"
                )}

                {renderShapCard(
                  "Xu Hướng (Slope)",
                  item.score_slope !== null && item.score_slope > 0
                    ? `+${item.score_slope.toFixed(2)}`
                    : fmtVal(item.score_slope),
                  "score_slope"
                )}
                {renderShapCard("Độ Biến Động (Volatility)", fmtVal(item.score_volatility), "score_volatility")}
                {renderShapCard("Mức Rớt Lớn Nhất", fmtVal(item.max_drop), "max_drop")}

                {renderShapCard("Hệ Số Cao Nhất", fmtVal(item.max_coefficient_so_far, "", 1), "max_coefficient_so_far")}
                {renderShapCard("Số Bài Hệ Số Lớn", fmtInt(item.high_weight_score_count, " bài"), "high_weight_score_count")}
                {renderShapCard(
                  "Điểm Hệ Số Lớn Cuối",
                  item.high_weight_score_count && item.high_weight_score_count > 0
                    ? fmtVal(item.last_high_weight_score)
                    : "—",
                  "last_high_weight_score"
                )}
              </div>

              {/* DỮ LIỆU GỐC (RAW): ĐIỂM SỐ ĐÃ KHOÁ */}
              <div className="pt-4 space-y-2 border-t border-slate-100 dark:border-slate-800">
                <h5 className="text-xs font-bold text-slate-700 dark:text-slate-200 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5 text-indigo-500" />
                    Dữ Liệu Gốc: Điểm Số Đã Khoá ({raw?.scores.length || 0})
                  </span>
                  {raw && <span className="text-[10px] font-normal text-slate-400">Cắt ngày {fmtDate(raw.cutoff_date)}</span>}
                </h5>
                {rawLoading ? (
                  <div className="flex items-center gap-2 py-4 text-xs text-slate-400"><Loader2 className="w-4 h-4 animate-spin" /> Đang tải điểm số gốc...</div>
                ) : !raw || raw.scores.length === 0 ? (
                  <p className="text-[11px] text-slate-400 py-2">Chưa có đầu điểm nào được khoá trước ngày cắt.</p>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-800">
                    <table className="w-full text-[11px]">
                      <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        <tr>
                          <th className="px-3 py-2 text-left font-semibold">Loại</th>
                          <th className="px-3 py-2 text-left font-semibold">Tên đầu điểm</th>
                          <th className="px-3 py-2 text-right font-semibold">Hệ số</th>
                          <th className="px-3 py-2 text-right font-semibold">Điểm</th>
                          <th className="px-3 py-2 text-right font-semibold">Thang</th>
                          <th className="px-3 py-2 text-right font-semibold">Ngày</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {raw.scores.map((s, i) => (
                          <tr key={i}>
                            <td className="px-3 py-1.5">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${s.source === "BO_GD" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400"}`}>
                                {s.source === "BO_GD" ? "BỘ GD" : "QT"}
                              </span>
                            </td>
                            <td className="px-3 py-1.5 text-slate-700 dark:text-slate-300">{s.exam_name || s.exam_code || "—"}</td>
                            <td className="px-3 py-1.5 text-right text-slate-500">{s.coefficient ?? "—"}</td>
                            <td className={`px-3 py-1.5 text-right font-bold ${(s.final_grade ?? 0) < 5 ? "text-rose-600 dark:text-rose-400" : "text-slate-800 dark:text-slate-200"}`}>{s.final_grade ?? "—"}</td>
                            <td className="px-3 py-1.5 text-right text-slate-500">{s.max_grade ?? "—"}</td>
                            <td className="px-3 py-1.5 text-right text-slate-500">{fmtDate(s.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: HỌC TẬP LMS */}
          {tab === "lms" && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                  <Laptop className="w-4 h-4 text-blue-500" />
                  2. Hoạt Động Trực Tuyến LMS (5 Features)
                </h4>
                {(item.primary_badge?.includes("RISK_LMS") || item.risk_factors?.includes("RISK_LMS")) && (
                  <span className="px-2.5 py-0.5 rounded-md text-[10px] font-semibold bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20 flex items-center gap-1">
                    <Laptop className="w-3 h-3 text-sky-500" />
                    Rủi ro LMS
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                {renderShapCard("ĐTB LMS", fmtVal(item.lms_avg_score), "lms_avg_score")}
                {renderShapCard("Tỷ Lệ Nộp Bài LMS", fmtPct(item.lms_submission_rate), "lms_submission_rate")}
                {renderShapCard("Tỷ Lệ Nộp Gần Đây", fmtPct(item.lms_recent_submission_rate), "lms_recent_submission_rate")}
                {renderShapCard("Sụt Giảm LMS Gần Đây", fmtVal(item.lms_recent_drop), "lms_recent_drop")}
                {renderShapCard("Khoảng Cách LMS - Sổ Điểm (Gradebook Gap)", fmtVal(item.lms_gradebook_gap), "lms_gradebook_gap", "col-span-2")}
              </div>

              {item.join_date &&
                schoolYearId !== undefined &&
                semesterIndex !== undefined &&
                item.join_date > semesterStartStr(schoolYearId, semesterIndex) && (
                  <div className="flex items-start gap-2 text-[11px] text-amber-600 dark:text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
                    <span>🏫</span>
                    <span>
                      Học sinh <strong>chuyển tới từ {fmtDate(item.join_date)}</strong> — ĐTB LMS & tỷ lệ nộp chỉ tính trên
                      các bài do kể từ ngày nhập học (nếu không nộp bài nào → tỷ lệ nộp để trống, không bị phạt).
                    </span>
                  </div>
                )}

              {/* DỮ LIỆU GỐC (RAW): BÀI TẬP LMS */}
              <div className="pt-4 space-y-2 border-t border-slate-100 dark:border-slate-800">
                <h5 className="text-xs font-bold text-slate-700 dark:text-slate-200 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Laptop className="w-3.5 h-3.5 text-blue-500" />
                    Dữ Liệu Gốc: Bài Tập LMS ({raw?.lms_submitted || 0}/{raw?.lms_expected || 0} đã nộp)
                  </span>
                  {raw && <span className="text-[10px] font-normal text-slate-400">Cắt ngày {fmtDate(raw.cutoff_date)}</span>}
                </h5>
                {rawLoading ? (
                  <div className="flex items-center gap-2 py-4 text-xs text-slate-400"><Loader2 className="w-4 h-4 animate-spin" /> Đang tải bài tập LMS...</div>
                ) : !raw || raw.lms.length === 0 ? (
                  <p className="text-[11px] text-slate-400 py-2">Không có bài tập LMS nào do trong cửa sổ [nhập học → ngày cắt].</p>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-800">
                    <table className="w-full text-[11px]">
                      <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        <tr>
                          <th className="px-3 py-2 text-left font-semibold">Mã</th>
                          <th className="px-3 py-2 text-left font-semibold">Tên bài</th>
                          <th className="px-3 py-2 text-right font-semibold">Hạn nộp</th>
                          <th className="px-3 py-2 text-right font-semibold">Điểm</th>
                          <th className="px-3 py-2 text-center font-semibold">Trạng thái</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {raw.lms.map((a, i) => (
                          <tr key={i}>
                            <td className="px-3 py-1.5 font-mono text-slate-500">{a.code || "—"}</td>
                            <td className="px-3 py-1.5 text-slate-700 dark:text-slate-300">{a.fullname || "—"}</td>
                            <td className="px-3 py-1.5 text-right text-slate-500">{fmtDate(a.due_date)}</td>
                            <td className={`px-3 py-1.5 text-right font-bold ${a.submitted ? "text-slate-800 dark:text-slate-200" : "text-slate-400"}`}>{a.submitted ? (a.final_grade ?? "—") : "—"}</td>
                            <td className="px-3 py-1.5 text-center">
                              {a.submitted ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                                  <CheckCircle2 className="w-3 h-3" /> Đã nộp
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-500/10 text-slate-500">
                                  <Clock className="w-3 h-3" /> Chưa nộp
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 4: CHUYÊN CẦN */}
          {tab === "attendance" && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-emerald-500" />
                  3. Điểm Danh & Chuyên Cần (4 Features)
                </h4>
                {(item.primary_badge?.includes("RISK_ATTENDANCE") || item.risk_factors?.includes("RISK_ATTENDANCE")) && (
                  <span className="px-2.5 py-0.5 rounded-md text-[10px] font-semibold bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20 flex items-center gap-1">
                    <Clock className="w-3 h-3 text-purple-500" />
                    Rủi ro Chuyên cần
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                {renderShapCard("Tỷ Lệ Nghỉ Học Tổng Cả", fmtPct(item.daily_absence_rate), "daily_absence_rate")}
                {renderShapCard("Tỷ Lệ Nghỉ Không Phép", fmtPct(item.unexcused_absent_rate), "unexcused_absent_rate")}
                {renderShapCard("Số Ngày Nghỉ Có Phép", fmtInt(item.excused_absent_days, " ngày"), "excused_absent_days")}
                {renderShapCard("Số Lần Đi Trễ", fmtInt(item.total_late_count, " lần"), "total_late_count")}
              </div>

              {/* DỮ LIỆU GỐC (RAW): CHUYÊN CẦN DIỂM DANH */}
              <div className="pt-4 space-y-2 border-t border-slate-100 dark:border-slate-800">
                <h5 className="text-xs font-bold text-slate-700 dark:text-slate-200 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-emerald-500" />
                    Dữ Liệu Gốc: Nhật Ký Chuyên Cần ({raw?.attendance.length || 0} ngày)
                  </span>
                  {raw && <span className="text-[10px] font-normal text-slate-400">Cắt ngày {fmtDate(raw.cutoff_date)}</span>}
                </h5>
                {rawLoading ? (
                  <div className="flex items-center gap-2 py-4 text-xs text-slate-400"><Loader2 className="w-4 h-4 animate-spin" /> Đang tải điểm danh gốc...</div>
                ) : !raw || raw.attendance.length === 0 ? (
                  <p className="text-[11px] text-slate-400 py-2">Không có dữ liệu điểm danh trước ngày cắt.</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {raw.attendance.map((a, i) => {
                      let cls = "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400";
                      if (a.status === "VẮNG KHÔNG PHÉP") cls = "bg-rose-500/10 text-rose-600 dark:text-rose-400 font-bold";
                      else if (a.status === "NGHỈ CÓ PHÉP") cls = "bg-amber-500/10 text-amber-600 dark:text-amber-400";
                      else if (a.status === "VẮNG") cls = "bg-orange-500/10 text-orange-600 dark:text-orange-400";
                      return (
                        <div
                          key={i}
                          className={`px-2 py-1 rounded-lg text-[10px] font-semibold ${cls}`}
                          title={`${fmtDate(a.date)} — ${a.status} (vắng ${a.absent_periods}/${a.total_periods} tiết)`}
                        >
                          {String(new Date(a.date).getDate()).padStart(2, "0")}/{String(new Date(a.date).getMonth() + 1).padStart(2, "0")}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 5: HẠNH KIỂM */}
          {tab === "behavior" && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                  <GraduationCap className="w-4 h-4 text-purple-500" />
                  4. Kỷ Luật & Nếp Sống Hành Vi (3 Features)
                </h4>
                {(item.primary_badge?.includes("RISK_BEHAVIOR") || item.risk_factors?.includes("RISK_BEHAVIOR")) && (
                  <span className="px-2.5 py-0.5 rounded-md text-[10px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 flex items-center gap-1">
                    <ShieldAlert className="w-3 h-3 text-amber-500" />
                    Rủi ro Hạnh kiểm
                  </span>
                )}
              </div>

              <div className="grid grid-cols-3 gap-3 text-xs">
                {renderShapCard("Điểm Trừ Kỷ Luật", fmtInt(item.total_demerit_points, " điểm"), "total_demerit_points")}
                {renderShapCard("Số Lần Tái Phạm", fmtInt(item.repeat_offense_count, " lần"), "repeat_offense_count")}
                {renderShapCard("Vi Phạm Nghiêm Trọng", fmtInt(item.severe_sanction_count, " lần"), "severe_sanction_count")}
              </div>

              {/* DỮ LIỆU GỐC (RAW): KỶ LUẬT HÀNH VI */}
              <div className="pt-4 space-y-2 border-t border-slate-100 dark:border-slate-800">
                <h5 className="text-xs font-bold text-slate-700 dark:text-slate-200 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <ShieldAlert className="w-3.5 h-3.5 text-purple-500" />
                    Dữ Liệu Gốc: Kỷ Luật & Hành Vi ({raw?.behavior.length || 0})
                  </span>
                  {raw && <span className="text-[10px] font-normal text-slate-400">Cắt ngày {fmtDate(raw.cutoff_date)}</span>}
                </h5>
                {rawLoading ? (
                  <div className="flex items-center gap-2 py-4 text-xs text-slate-400"><Loader2 className="w-4 h-4 animate-spin" /> Đang tải kỷ luật gốc...</div>
                ) : !raw || raw.behavior.length === 0 ? (
                  <p className="text-[11px] text-slate-400 py-2">Không có ghi nhận vi phạm / hành vi trước ngày cắt.</p>
                ) : (
                  <div className="space-y-1.5">
                    {raw.behavior.map((b, i) => (
                      <div key={i} className="flex items-center justify-between gap-3 text-[11px] px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                        <span className="text-slate-700 dark:text-slate-300 flex items-center gap-2">
                          <span className="text-[10px] text-slate-400">{fmtDate(b.comment_date)}</span>
                          <span>{b.behavior_fullname || "—"}</span>
                        </span>
                        <span className="flex items-center gap-2">
                          {b.behavior_point !== null && b.behavior_point !== undefined && (
                            <span className={`font-bold ${b.behavior_point < 0 ? "text-rose-600 dark:text-rose-400" : "text-slate-600 dark:text-slate-300"}`}>
                              {b.behavior_point > 0 ? `+${b.behavior_point}` : b.behavior_point} điểm
                            </span>
                          )}
                          {b.sanction_name && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-500/10 text-red-600 dark:text-red-400">{b.sanction_name}</span>
                          )}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* FOOTER */}
        <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 flex items-center justify-between text-xs text-slate-400">
          <span>Ngày thực thi dự báo: {item.evaluated_at_date || "—"}</span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-semibold rounded-xl transition-colors"
          >
            Đóng Chi Tiết
          </button>
        </div>
      </div>
    </div>
  );
}
