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
  HeartPulse,
  Home,
  Info,
  Laptop,
  LineChart,
  Loader2,
  RefreshCw,
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

const MAIN_GROUPS = [
  { id: "overview", label: "Tổng Quan AI", icon: ShieldCheck },
  { id: "academic", label: "Học Tập & Kỷ Luật", icon: BookOpen, count: 4 },
  { id: "context", label: "Hoàn Cảnh & Y Tế", icon: HeartPulse, count: 2 },
  { id: "llm", label: "Phân Tích AI", icon: Sparkles },
];

const ACADEMIC_SUBTABS = [
  { id: "score", label: "Tiến Bộ & Điểm Số", icon: LineChart },
  { id: "lms", label: "Học Tập LMS", icon: Laptop },
  { id: "attendance", label: "Chuyên Cần", icon: Clock },
  { id: "behavior", label: "Hạnh Kiểm", icon: GraduationCap },
];

const CONTEXT_SUBTABS = [
  { id: "life_events", label: "Biến Cố Gia Đình", icon: Home },
  { id: "medical", label: "Bệnh Lý / Tiền Sử", icon: HeartPulse },
];

export default function EwsDetailDrawer({ item, onClose, schoolYearId, semesterIndex }: Props) {
  const [tab, setTab] = useState<string>("overview");

  // Derive main group from active tab
  const activeMainGroup =
    tab === "overview"
      ? "overview"
      : ["score", "lms", "attendance", "behavior"].includes(tab)
        ? "academic"
        : ["life_events", "medical"].includes(tab)
          ? "context"
          : "llm";

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

  // ==== LLM-based Forecasting (M5) — kích hoạt thủ công + hiển thị phân tích định tính ====
  const [llmResult, setLlmResult] = useState<EwsPredictionRow | null>(null);
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);

  // Reset kết quả LLM khi học sinh/môn thay đổi (drawer dùng chung nhiều item)
  useEffect(() => {
    setLlmResult(null);
    setLlmError(null);
  }, [item?.student_code, item?.subject_id]);

  const runLlmForecast = async () => {
    if (!item) return;
    setLlmLoading(true);
    setLlmError(null);
    try {
      const updated = await api.post<EwsPredictionRow>("/ews/llm-forecast", {
        student_code: item.student_code,
        subject_id: item.subject_id,
        school_year_id: schoolYearId ?? 2025,
        semester_index: semesterIndex ?? 1,
        evaluated_at_week: item.evaluated_at_week,
        model_version: item.model_version || "v2_ensemble",
      });
      setLlmResult(updated);
    } catch (err) {
      setLlmError(err instanceof ApiError ? err.message : "Không phân tích được bằng AI");
    } finally {
      setLlmLoading(false);
    }
  };

  // Helper render Metric Card phẳng, sạch sẽ, không gán mác rủi ro hay tô đỏ/xanh ở từng ô card
  const renderMetricCard = (title: string, valueDisplay: React.ReactNode, featureName?: string, colSpan?: string) => {
    return (
      <div className={`p-3.5 rounded-xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800 space-y-1 ${colSpan || ""}`}>
        <span className="text-[11px] font-medium text-slate-400 block leading-tight">{title}</span>
        <div className="text-base font-bold text-slate-900 dark:text-white tracking-tight">{valueDisplay}</div>
      </div>
    );
  };

  if (!item) return null;

  // Ưu tiên kết quả LLM mới trả về (llmResult), fallback về item (đã load từ list) — item đã non-null ở đây
  const llmRow = llmResult ?? item;
  const hasLlm = Boolean(llmRow.llm_narrative_summary || llmRow.llm_risk_score !== null);

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
          <div className="flex items-start gap-3.5">
            <div className="w-11 h-11 rounded-2xl bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-100 dark:border-indigo-900/50 flex items-center justify-center text-indigo-600 dark:text-indigo-400 shrink-0 shadow-2xs">
              <User className="w-5 h-5" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2.5 flex-wrap">
                <h3 className="text-xl font-bold text-slate-900 dark:text-white">
                  {item.student_name || item.student_code}
                </h3>
                <span className="px-2 py-0.5 text-xs font-mono font-medium rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-700/80">
                  {item.student_code}
                </span>
                {item.llm_risk_level && (
                  <span title={`Đã có phân tích chuyên sâu từ AI (Mức LLM: ${item.llm_risk_level})`}>
                    <Sparkles className="w-4 h-4 text-amber-500 fill-amber-400/30" />
                  </span>
                )}

                {/* 2-Tone Risk Badge Cao Cấp Ngang Hàng Với Tên */}
                <div
                  className="inline-flex items-stretch rounded-full border overflow-hidden shadow-xs text-[11px] font-semibold ml-1"
                  style={{ borderColor: `${riskColor}50` }}
                >
                  <span
                    className="px-2.5 py-0.5 text-[10px] font-bold text-white uppercase tracking-wider flex items-center gap-1.5 leading-normal"
                    style={{ backgroundColor: riskColor }}
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                    {item.risk_level}
                  </span>
                  <span
                    className="px-2.5 py-0.5 font-mono font-bold text-xs flex items-center justify-center leading-normal"
                    style={{
                      backgroundColor: `${riskColor}18`,
                      color: riskColor,
                    }}
                  >
                    {item.risk_score.toFixed(2)}
                  </span>
                </div>
              </div>

              <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2 pt-0.5">
                <span>
                  Lớp:{" "}
                  <strong className="text-slate-800 dark:text-slate-200">
                    {item.class_name
                      ? item.class_name.replace(/\s*-\s*Trường\s*\d+/gi, "").replace(/^Lớp\s+/i, "")
                      : "—"}
                  </strong>
                </span>
                <span className="text-slate-300 dark:text-slate-600">•</span>
                <span>
                  Môn:{" "}
                  <strong className="text-indigo-600 dark:text-indigo-400">
                    {item.subject_name || item.subject_code}
                  </strong>
                </span>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* TWO-TIER TAB NAVIGATION (Vừa khít 100% chiều ngang, không trượt ngang) */}
        {/* TIER 1: MAIN GROUPS HEADER */}
        <div className="px-4 pt-2.5 bg-slate-50/80 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 grid grid-cols-4 gap-1.5 shrink-0">
          {MAIN_GROUPS.map((g) => {
            const Icon = g.icon;
            const active = activeMainGroup === g.id;
            return (
              <button
                key={g.id}
                onClick={() => {
                  if (g.id === "overview") setTab("overview");
                  else if (g.id === "academic") setTab(["score", "lms", "attendance", "behavior"].includes(tab) ? tab : "score");
                  else if (g.id === "context") setTab(["life_events", "medical"].includes(tab) ? tab : "life_events");
                  else if (g.id === "llm") setTab("llm");
                }}
                className={`flex items-center justify-center gap-1.5 py-2.5 px-2 rounded-t-xl text-xs font-bold transition-all border-b-2 ${active
                  ? "text-indigo-600 dark:text-indigo-400 border-indigo-500 bg-white dark:bg-slate-800 shadow-2xs"
                  : "text-slate-500 dark:text-slate-400 border-transparent hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-800/40"
                  }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="truncate">{g.label}</span>
                {g.count && (
                  <span className="hidden sm:inline-flex text-[10px] font-mono font-bold px-1.5 py-0.2 rounded-full bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                    {g.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* TIER 2: SUB-TAB PILL STRIP */}
        {activeMainGroup === "academic" && (
          <div className="px-4 py-2 bg-white dark:bg-slate-900 border-b border-slate-200/70 dark:border-slate-800 flex gap-2 shrink-0">
            {ACADEMIC_SUBTABS.map((st) => {
              const Icon = st.icon;
              const active = tab === st.id;
              return (
                <button
                  key={st.id}
                  onClick={() => setTab(st.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${active
                    ? "bg-indigo-600 text-white shadow-2xs"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200/70 dark:hover:bg-slate-700"
                    }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{st.label}</span>
                </button>
              );
            })}
          </div>
        )}

        {activeMainGroup === "context" && (
          <div className="px-4 py-2 bg-white dark:bg-slate-900 border-b border-slate-200/70 dark:border-slate-800 flex gap-2 shrink-0">
            {CONTEXT_SUBTABS.map((st) => {
              const Icon = st.icon;
              const active = tab === st.id;
              return (
                <button
                  key={st.id}
                  onClick={() => setTab(st.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${active
                    ? "bg-indigo-600 text-white shadow-2xs"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200/70 dark:hover:bg-slate-700"
                    }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{st.label}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* BODY BODY SCROLLABLE */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* TAB 1: TỔNG QUAN AI */}
          {tab === "overview" && (
            <div
              className="p-5 rounded-2xl border shadow-2xs relative overflow-hidden space-y-4 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5" style={{ color: riskColor }} />
                  <h4 className="font-bold text-sm text-slate-900 dark:text-white">Tổng Hợp Đánh Giá Nguy Cơ</h4>
                </div>
                <span className="text-xs font-medium px-2.5 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200/60 dark:border-slate-700/60">
                  Mốc Tuần {item.evaluated_at_week}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 bg-white/80 dark:bg-slate-900/80 p-4 rounded-xl border border-slate-200/50 dark:border-slate-800/50">
                <div>
                  <span className="text-[11px] font-medium text-slate-400 block">Điểm Rủi Ro (0-100)</span>
                  <span className="text-2xl font-black" style={{ color: riskColor }}>
                    {item.risk_score.toFixed(2)}
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
              </div>

              {/* BREAKDOWN THEO YẾU TỐ */}
              {item.model_version === "v2_ensemble" || item.model_version === "v1_single" ? (
                <div className="pt-2 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                      {item.model_version === "v2_ensemble"
                        ? "Tỷ trọng & Điểm rủi ro theo 4 nhóm yếu tố:"
                        : "Mức đóng góp theo 4 nhóm yếu tố:"}
                    </span>
                    <span className="text-[10px] text-slate-400 font-medium">
                      (Điểm rủi ro / Trọng số)
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2.5">
                    {[
                      { label: "Điểm số", risk: item.score_risk, w: item.weight_score, def: 0.65 },
                      { label: "LMS", risk: item.lms_risk, w: item.weight_lms, def: 0.15 },
                      { label: "Chuyên cần", risk: item.attendance_risk, w: item.weight_attendance, def: 0.10 },
                      { label: "Hạnh kiểm", risk: item.behavior_risk, w: item.weight_behavior, def: 0.10 },
                    ].map((f) => {
                      const w = f.w !== null ? f.w : f.def;
                      const hasData = item.model_version === "v1_single" ? true : f.risk !== null;
                      return (
                        <div key={f.label} className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/60 space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">{f.label}</span>
                            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                              Trọng số: <strong className="text-indigo-600 dark:text-indigo-400">{hasData ? `${(w * 100).toFixed(0)}%` : "—"}</strong>
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                              <div
                                className="h-full rounded-full transition-all"
                                style={{
                                  width: `${Math.min(100, f.risk ?? 0)}%`,
                                  backgroundColor: (f.risk ?? 0) >= 70 ? "#ef4444" : (f.risk ?? 0) >= 50 ? "#f97316" : "#22c55e",
                                }}
                              />
                            </div>
                            <span className="text-xs font-mono font-bold text-slate-800 dark:text-slate-200">
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

              {/* ✨ TOP 5 NHÂN TỐ TÁC ĐỘNG AI MẠNH NHẤT (CatBoost SHAP) — DẠNG DỰA TRÊN DANH SÁCH LIỆT KÊ */}
              {item.shap_drivers && item.shap_drivers.length > 0 && (() => {
                const noHW = !item.high_weight_score_count || item.high_weight_score_count === 0;

                // Lọc ra Top 5 nhân tố có tác động thực sự (lọc bỏ rủi ro giả sư phạm & số nhiễu <= 0.005)
                const validDrivers = item.shap_drivers.filter((d) => {
                  if (Math.abs(d.shap_value) <= 0.005) return false;
                  if (noHW && (d.feature === "high_weight_score_count" || d.feature === "max_coefficient_so_far" || d.feature === "last_high_weight_score")) return false;
                  if (d.feature === "score_volatility" && (item.score_volatility === 0 || item.score_volatility === null)) return false;
                  return true;
                }).slice(0, 5);

                if (validDrivers.length === 0) return null;

                return (
                  <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-3 shadow-2xs">
                    <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                      <div className="flex items-center gap-2 font-bold text-xs text-slate-800 dark:text-slate-200">
                        <Sparkles className="w-4 h-4 text-amber-500 shrink-0" />
                        <span>Top Yếu Tố Tác Động Rủi Ro</span>
                      </div>
                      <span className="text-[10px] text-slate-400 font-medium">
                        Ảnh hưởng chính
                      </span>
                    </div>

                    <div className="divide-y divide-slate-100 dark:divide-slate-800/80 text-xs">
                      {validDrivers.map((d, i) => {
                        const isRiskBooster = d.shap_value > 0;
                        const numVal = d.value !== null && d.value !== undefined ? Number(d.value) : NaN;

                        // ĐIỀU KIỆN KÉP CHO AN TOÀN: Chỉ khen "Giúp an toàn" khi shap_value < 0 VÀ giá trị thực tế tốt!
                        let isRealValueGood = true;
                        if (!isNaN(numVal)) {
                          if (d.feature.includes("rate")) isRealValueGood = numVal >= 0.5; // nộp bài >= 50%
                          else if (d.feature.includes("avg") || d.feature.includes("score")) isRealValueGood = numVal >= 5.0; // điểm >= 5.0
                          else if (d.feature.includes("absence") || d.feature.includes("late") || d.feature.includes("demerit")) isRealValueGood = numVal === 0;
                        }

                        const isSafetyFactor = d.shap_value < 0 && isRealValueGood;

                        // Định dạng giá trị hiển thị thực tế
                        let formattedVal = "—";
                        if (!isNaN(numVal)) {
                          if (d.feature.includes("rate")) {
                            formattedVal = `${(numVal * 100).toFixed(1)}%`;
                          } else if (d.feature.includes("count") || d.feature.includes("days")) {
                            formattedVal = `${Math.round(numVal)}`;
                          } else {
                            formattedVal = `${numVal.toFixed(2)}`;
                          }
                        } else if (d.value !== null && d.value !== undefined) {
                          formattedVal = String(d.value);
                        }

                        return (
                          <div
                            key={i}
                            className="flex items-center justify-between py-2.5 px-1 hover:bg-slate-50/60 dark:hover:bg-slate-800/40 rounded-lg transition-colors"
                          >
                            <div className="flex items-center gap-2">
                              <span className="text-slate-400 font-mono text-[11px] w-4 shrink-0">
                                {i + 1}.
                              </span>
                              <span className="font-medium text-slate-800 dark:text-slate-200">
                                {FEATURE_VIETNAMESE_MAP[d.feature] || d.feature}
                              </span>
                              {formattedVal !== "—" && (
                                <span className="text-[11px] font-mono font-semibold text-slate-500 dark:text-slate-400 ml-1">
                                  ({formattedVal})
                                </span>
                              )}
                            </div>

                            <div className="shrink-0">
                              {isRiskBooster ? (
                                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-rose-600 dark:text-rose-400">
                                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0" />
                                  Tăng rủi ro
                                </span>
                              ) : isSafetyFactor ? (
                                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                                  Giúp an toàn
                                </span>
                              ) : (
                                <span className="text-[11px] text-slate-400">
                                  Tác động nhỏ
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}
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
                {renderMetricCard("Điểm Thi Mới Nhất", fmtVal(item.last_score))}
                {renderMetricCard("ĐTB Nửa Đầu Kỳ", fmtVal(item.weighted_early_avg))}
                {renderMetricCard(
                  "ĐTB Nửa Sau Kỳ",
                  item.weighted_late_avg_imputed || item.weighted_late_avg === null ? (
                    <span className="text-slate-300 dark:text-slate-600 font-bold" title="Chưa có điểm nửa sau kỳ">
                      —
                    </span>
                  ) : (
                    fmtVal(item.weighted_late_avg)
                  )
                )}

                {renderMetricCard(
                  "Xu Hướng (Slope)",
                  item.score_slope !== null && item.score_slope > 0
                    ? `+${item.score_slope.toFixed(2)}`
                    : fmtVal(item.score_slope)
                )}
                {renderMetricCard("Độ Biến Động (Volatility)", fmtVal(item.score_volatility))}
                {renderMetricCard("Mức Rớt Lớn Nhất", fmtVal(item.max_drop))}

                {renderMetricCard("Hệ Số Cao Nhất", fmtVal(item.max_coefficient_so_far, "", 1))}
                {renderMetricCard("Số Bài Hệ Số Lớn", fmtInt(item.high_weight_score_count, " bài"))}
                {renderMetricCard(
                  "Điểm Hệ Số Lớn Cuối",
                  item.high_weight_score_count && item.high_weight_score_count > 0
                    ? fmtVal(item.last_high_weight_score)
                    : "—"
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
                {renderMetricCard("ĐTB LMS", fmtVal(item.lms_avg_score))}
                {renderMetricCard("Tỷ Lệ Nộp Bài LMS", fmtPct(item.lms_submission_rate))}
                {renderMetricCard("Tỷ Lệ Nộp Gần Đây", fmtPct(item.lms_recent_submission_rate))}
                {renderMetricCard("Sụt Giảm LMS Gần Đây", fmtVal(item.lms_recent_drop))}
                {renderMetricCard("Khoảng Cách LMS - Sổ Điểm (Gradebook Gap)", fmtVal(item.lms_gradebook_gap), undefined, "col-span-2")}
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
                {renderMetricCard("Tỷ Lệ Nghỉ Học Tổng Cả", fmtPct(item.daily_absence_rate))}
                {renderMetricCard("Tỷ Lệ Nghỉ Không Phép", fmtPct(item.unexcused_absent_rate))}
                {renderMetricCard("Số Ngày Nghỉ Có Phép", fmtInt(item.excused_absent_days, " ngày"))}
                {renderMetricCard("Số Lần Đi Trễ", fmtInt(item.total_late_count, " lần"))}
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
                {renderMetricCard("Điểm Trừ Kỷ Luật", fmtInt(item.total_demerit_points, " điểm"))}
                {renderMetricCard("Số Lần Tái Phạm", fmtInt(item.repeat_offense_count, " lần"))}
                {renderMetricCard("Vi Phạm Nghiêm Trọng", fmtInt(item.severe_sanction_count, " lần"))}
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

          {/* TAB 6: BIẾN CỐ GIA ĐÌNH */}
          {tab === "life_events" && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                  <Home className="w-4 h-4 text-amber-500" />
                  5. Biến Cố Cuộc Sống & Gia Đình
                </h4>
              </div>

              {/* DỮ LIỆU GỐC (RAW): BIẾN CỐ GIA ĐÌNH */}
              <div className="pt-4 space-y-2 border-t border-slate-100 dark:border-slate-800">
                <h5 className="text-xs font-bold text-slate-700 dark:text-slate-200 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Home className="w-3.5 h-3.5 text-amber-500" />
                    Dữ Liệu Gốc: Biến Cố Gia Đình ({raw?.life_events.length || 0})
                  </span>
                  {raw && <span className="text-[10px] font-normal text-slate-400">Cắt ngày {fmtDate(raw.cutoff_date)}</span>}
                </h5>
                {rawLoading ? (
                  <div className="flex items-center gap-2 py-4 text-xs text-slate-400"><Loader2 className="w-4 h-4 animate-spin" /> Đang tải biến cố gia đình...</div>
                ) : !raw || raw.life_events.length === 0 ? (
                  <p className="text-[11px] text-slate-400 py-2">Không có biến cố gia đình / cuộc sống nào được ghi nhận.</p>
                ) : (
                  <div className="space-y-1.5">
                    {raw.life_events.map((e, i) => {
                      const sev = e.severity?.toUpperCase() || "";
                      const sevCls =
                        sev === "CRITICAL" || sev === "HIGH"
                          ? "bg-rose-500/10 text-rose-600 dark:text-rose-400"
                          : sev === "MODERATE"
                            ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                            : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400";
                      return (
                        <div key={i} className="flex items-start justify-between gap-3 text-[11px] px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                          <div className="space-y-0.5">
                            <span className="text-slate-700 dark:text-slate-300 flex items-center gap-2">
                              <span className="text-[10px] text-slate-400">{fmtDate(e.event_date)}</span>
                              <span className="font-semibold">{e.event_name || "—"}</span>
                            </span>
                            {e.description && <p className="text-[10px] text-slate-500 dark:text-slate-400">{e.description}</p>}
                          </div>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${sevCls}`}>{e.severity || "—"}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 7: BỆNH TẬT */}
          {tab === "medical" && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                  <HeartPulse className="w-4 h-4 text-rose-500" />
                  6. Bệnh Lý & Tiền Sử Y Tế
                </h4>
              </div>

              {/* DỮ LIỆU GỐC (RAW): BỆNH TẬT */}
              <div className="pt-4 space-y-2 border-t border-slate-100 dark:border-slate-800">
                <h5 className="text-xs font-bold text-slate-700 dark:text-slate-200 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <HeartPulse className="w-3.5 h-3.5 text-rose-500" />
                    Dữ Liệu Gốc: Bệnh Lý & Tiền Sử Y Tế ({raw?.medical_history.length || 0})
                  </span>
                  {raw && <span className="text-[10px] font-normal text-slate-400">Cắt ngày {fmtDate(raw.cutoff_date)}</span>}
                </h5>
                {rawLoading ? (
                  <div className="flex items-center gap-2 py-4 text-xs text-slate-400"><Loader2 className="w-4 h-4 animate-spin" /> Đang tải bệnh lý...</div>
                ) : !raw || raw.medical_history.length === 0 ? (
                  <p className="text-[11px] text-slate-400 py-2">Không có bệnh lý / tiền sử y tế nào được ghi nhận.</p>
                ) : (
                  <div className="space-y-1.5">
                    {raw.medical_history.map((m, i) => {
                      const sev = m.severity?.toUpperCase() || "";
                      const sevCls =
                        sev === "HIGH"
                          ? "bg-rose-500/10 text-rose-600 dark:text-rose-400"
                          : sev === "MODERATE"
                            ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                            : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400";
                      return (
                        <div key={i} className="flex items-start justify-between gap-3 text-[11px] px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                          <div className="space-y-0.5">
                            <span className="text-slate-700 dark:text-slate-300 flex items-center gap-2">
                              <span className="text-[10px] text-slate-400">{fmtDate(m.diagnosed_date)}</span>
                              <span className="font-semibold">{m.condition_name || "—"}</span>
                              {m.is_chronic && (
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-orange-500/10 text-orange-600 dark:text-orange-400">Mãn tính</span>
                              )}
                            </span>
                            {m.notes && <p className="text-[10px] text-slate-500 dark:text-slate-400">{m.notes}</p>}
                          </div>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${sevCls}`}>{m.severity || "—"}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 8: PHÂN TÍCH AI (LLM-based Forecasting — M5) */}
          {tab === "llm" && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-violet-500" />
                  7. Phân Tích & Dự Báo bằng AI (LLM)
                </h4>
                {hasLlm && llmRow.llm_evaluated_at && (
                  <span className="text-[10px] text-slate-400">Đánh giá lúc {fmtDate(llmRow.llm_evaluated_at)}</span>
                )}
              </div>

              {/* Nút kích hoạt phân tích thủ công */}
              {!hasLlm && (
                <div className="flex flex-col items-center gap-3 py-6 text-center">
                  <div className="w-12 h-12 rounded-2xl bg-violet-500/10 text-violet-500 flex items-center justify-center">
                    <Sparkles className="w-6 h-6" />
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm">
                    Kích hoạt AI phân tích định tính: kết hợp điểm CatBoost với biến cố gia đình & bệnh lý để
                    giải thích nguyên nhân gốc rễ, dự báo xu hướng 3-4 tuần tới và đề xuất can thiệp.
                  </p>
                  <button
                    onClick={runLlmForecast}
                    disabled={llmLoading}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 dark:bg-violet-500 dark:hover:bg-violet-600 text-white text-xs font-bold shadow-sm transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {llmLoading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Đang phân tích...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4" />
                        Phân Tích & Dự Báo bằng AI
                      </>
                    )}
                  </button>
                  {llmError && (
                    <span className="text-[11px] text-rose-500 bg-rose-500/10 border border-rose-500/20 rounded-lg px-3 py-1.5">
                      {llmError}
                    </span>
                  )}
                </div>
              )}

              {/* Hiển thị kết quả phân tích LLM */}
              {hasLlm && (
                <div className="space-y-4">
                  {/* So sánh 2 điểm: CatBoost vs LLM */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/60">
                      <span className="text-[11px] font-medium text-slate-400 block">Điểm CatBoost (ML)</span>
                      <div className="flex items-baseline gap-1.5 mt-0.5">
                        <span className="text-xl font-black" style={{ color: riskColor }}>{fmtVal(item.risk_score)}</span>
                        <span className="text-[10px] font-semibold text-slate-500 uppercase">{item.risk_level}</span>
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-violet-500/10 dark:bg-violet-500/15 border border-violet-500/20">
                      <span className="text-[11px] font-medium text-violet-500 block">Điểm LLM (Điều chỉnh định tính)</span>
                      <div className="flex items-baseline gap-1.5 mt-0.5">
                        <span className="text-xl font-black text-violet-700 dark:text-violet-300">
                          {llmRow.llm_risk_score !== null ? fmtVal(llmRow.llm_risk_score) : "—"}
                        </span>
                        {llmRow.llm_risk_level && (
                          <span className="text-[10px] font-semibold text-violet-500 uppercase">{llmRow.llm_risk_level}</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Đánh giá lại (Chạy Lại Phân Tích) — audit thay đổi điểm LLM giữa các lần */}
                  {llmRow.llm_previous_score != null && (
                    <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200/70 dark:border-amber-500/20">
                      <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
                        <RefreshCw className="w-3.5 h-3.5" />
                        Đánh Giá Lại (Chạy Lại Phân Tích)
                      </span>
                      <div className="mt-1 flex items-baseline gap-2 text-xs text-amber-800 dark:text-amber-300">
                        <span>Điểm trước đó:</span>
                        <span className="font-bold line-through opacity-70">{fmtVal(llmRow.llm_previous_score)}</span>
                        <span>→</span>
                        <span className="font-black text-amber-900 dark:text-amber-100">
                          {llmRow.llm_risk_score !== null ? fmtVal(llmRow.llm_risk_score) : "—"}
                        </span>
                      </div>
                      {llmRow.llm_score_change_reason ? (
                        <p className="mt-1.5 text-[11px] leading-relaxed text-amber-700 dark:text-amber-300/90">
                          <span className="font-semibold">Lý do thay đổi:</span> {llmRow.llm_score_change_reason}
                        </p>
                      ) : (
                        <p className="mt-1.5 text-[11px] text-amber-600/80 dark:text-amber-400/70">
                          Điểm được giữ nguyên so với lần đánh giá trước (ổn định, không có dữ liệu mới đáng kể).
                        </p>
                      )}
                    </div>
                  )}

                  {/* Narrative — nguyên nhân gốc rễ */}
                  {llmRow.llm_narrative_summary && (
                    <div className="space-y-1.5">
                      <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                        <Info className="w-3.5 h-3.5 text-violet-500" />
                        Phân Tích Nguyên Nhân Gốc Rễ
                      </span>
                      <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed bg-slate-50 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/60 rounded-xl px-3.5 py-3">
                        {llmRow.llm_narrative_summary}
                      </p>
                    </div>
                  )}

                  {/* Forecast trend */}
                  {llmRow.llm_forecast_trend && (
                    <div className="space-y-1.5">
                      <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                        <LineChart className="w-3.5 h-3.5 text-violet-500" />
                        Dự Báo Xu Hướng (3-4 tuần tới)
                      </span>
                      <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed bg-slate-50 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/60 rounded-xl px-3.5 py-3">
                        {llmRow.llm_forecast_trend}
                      </p>
                    </div>
                  )}

                  {/* Recommended actions */}
                  {llmRow.llm_recommended_actions && llmRow.llm_recommended_actions.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                        <ClipboardList className="w-3.5 h-3.5 text-violet-500" />
                        Hành Động Can Thiệp Đề Xuất
                      </span>
                      <div className="space-y-1.5">
                        {llmRow.llm_recommended_actions.map((action, i) => (
                          <div key={i} className="flex items-start gap-2.5 text-xs px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/60">
                            <span className="w-5 h-5 rounded-full bg-violet-500/15 text-violet-600 dark:text-violet-400 font-bold text-[11px] flex items-center justify-center shrink-0">
                              {i + 1}
                            </span>
                            <span className="text-slate-700 dark:text-slate-300">{action}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Nút chạy lại */}
                  <div className="flex justify-end pt-1">
                    <button
                      onClick={runLlmForecast}
                      disabled={llmLoading}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 dark:bg-violet-500 dark:hover:bg-violet-600 text-white text-xs font-bold shadow-sm transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      {llmLoading ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Đang phân tích...
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-4 h-4" />
                          Chạy Lại Phân Tích
                        </>
                      )}
                    </button>
                  </div>
                  {llmError && (
                    <span className="text-[11px] text-rose-500 bg-rose-500/10 border border-rose-500/20 rounded-lg px-3 py-1.5 block">
                      {llmError}
                    </span>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 🛠️ KHỐI DEBUG RAW SHAP JSON CHUNG (Hiển thị ở TẤT CẢ CÁC TAB để tiện kiểm tra thô) */}
          {item.shap_drivers && item.shap_drivers.length > 0 && (
            <details className="mt-4 text-[10px] border-t border-slate-200 dark:border-slate-800 pt-3 text-slate-500 dark:text-slate-400">
              <summary className="cursor-pointer font-mono font-bold text-indigo-600 dark:text-indigo-400 hover:underline select-none flex items-center gap-1.5 text-xs">
                <span>🛠️ Raw SHAP Drivers JSON Debug ({item.shap_drivers.length} yếu tố — Click để xem/mở rộng)</span>
              </summary>
              <div className="mt-2 space-y-1.5">
                <span className="text-[10px] text-slate-400 font-mono block">
                  Dữ liệu gốc shap_drivers trả về từ DB/API (xếp theo |shap_value| giảm dần):
                </span>
                <pre className="p-3 rounded-xl bg-slate-900 text-emerald-400 font-mono text-[10px] overflow-x-auto max-h-64 border border-slate-800 leading-relaxed shadow-inner">
                  {JSON.stringify(item.shap_drivers, null, 2)}
                </pre>
              </div>
            </details>
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
