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

const FACTOR_MAP: Record<string, { label: string; icon: string; desc: string }> = {
  // Điểm số
  SLOPE_DOWN: { label: "Tụt dốc điểm số", icon: "📉", desc: "Xu hướng điểm số qua các bài thi rớt mạnh hơn -0.5 điểm/tuần" },
  LAST_SCORE_LOW: { label: "Bài thi gần nhất rớt", icon: "⚠️", desc: "Bài kiểm tra mới nhất có điểm < 5.0" },
  SCORE_VOLATILE: { label: "Điểm số biến động mạnh", icon: "🎢", desc: "Độ lệch chuẩn điểm số vượt quá 2.0" },
  MAX_DROP_HIGH: { label: "Tụt điểm lớn", icon: "📉", desc: "Mức tụt điểm lớn nhất giữa các bài thi > 2.0" },
  HIGH_WEIGHT_FAIL: { label: "Trượt bài hệ số cao", icon: "🧮", desc: "Bài kiểm tra hệ số cao gần nhất có điểm < 5.0" },
  // LMS
  LMS_LOW_SUBMISSION: { label: "Nộp bài LMS thấp", icon: "📤", desc: "Tỷ lệ nộp bài trên LMS dưới 50%" },
  LMS_LOW_SCORE: { label: "Điểm LMS thấp", icon: "💻", desc: "Điểm trung bình bài tập LMS < 5.0" },
  LMS_DROP: { label: "Điểm LMS suy giảm", icon: "📉", desc: "Điểm LMS gần đây tụt hơn 1.0 so với trước" },
  LMS_GAP: { label: "Lệch điểm LMS", icon: "⚖️", desc: "Chênh lệch điểm LMS so với điểm lớp < -2.0" },
  // Chuyên cần
  ABSENTEEISM: { label: "Vắng học nhiều", icon: "🚫", desc: "Tỷ lệ nghỉ học vượt quá 10% số buổi học" },
  UNEXCUSED_ABSENT: { label: "Nghỉ không phép", icon: "🏃", desc: "Tỷ lệ nghỉ không phép vượt quá 5%" },
  LATE_MANY: { label: "Đi muộn nhiều", icon: "⏰", desc: "Tổng số lần đi muộn từ 5 lần trở lên" },
  // Hạnh kiểm
  DEMERIT_HIGH: { label: "Nhiều điểm trừ hạnh kiểm", icon: "📛", desc: "Tổng điểm trừ hạnh kiểm từ 5 điểm trở lên" },
  REPEAT_OFFENSE: { label: "Tái phạm nhiều lần", icon: "🔁", desc: "Số lần tái phạm vi phạm từ 2 lần trở lên" },
  SEVERE_SANCTION: { label: "Kỷ luật nặng", icon: "⛔", desc: "Có ít nhất 1 hình thức kỷ luật nặng" },
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

export default function EwsDetailDrawer({ item, onClose, schoolYearId, semesterIndex }: Props) {
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

        {/* BODY BODY SCROLLABLE */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* SECTION 1: KẾT QUẢ DỰ BÁO AI */}
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
              <div>
                <span className="text-[11px] font-medium text-slate-400 block">Xác Suất Nguy Cơ</span>
                <span className="text-2xl font-bold text-slate-800 dark:text-slate-200">
                  {item.risk_probability !== null ? `${(item.risk_probability * 100).toFixed(1)}%` : "—"}
                </span>
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

            {/* CỜ NGUYÊN NHÂN BADGES */}
            {item.risk_factors && item.risk_factors.length > 0 && (
              <div className="space-y-1.5 pt-2">
                <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Các Nguyên Nhân Cảnh Báo Sớm:
                </span>
                <div className="flex flex-wrap gap-2">
                  {item.risk_factors.map((factor, idx) => {
                    const metaF = FACTOR_MAP[factor] || { label: factor, icon: "⚠️", desc: "" };
                    return (
                      <div
                        key={idx}
                        className="px-3 py-1.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-xs font-medium flex items-center gap-1.5"
                        title={metaF.desc}
                      >
                        <span>{metaF.icon}</span>
                        <span>{metaF.label}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* SECTION 2: 9 TEMPORAL SCORES FEATURES */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <LineChart className="w-4 h-4 text-indigo-500" />
              1. Tiến Bộ & Điểm Số Theo Thời Gian (9 Features)
            </h4>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Điểm Thi Mới Nhất</span>
                <span className="text-base font-bold text-slate-900 dark:text-white">
                  {fmtVal(item.last_score)}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">ĐTB Nửa Đầu Kỳ</span>
                <span className="text-base font-bold text-slate-900 dark:text-white">
                  {fmtVal(item.weighted_early_avg)}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">ĐTB Nửa Sau Kỳ</span>
                {item.weighted_late_avg_imputed || item.weighted_late_avg === null ? (
                  <span
                    className="text-base font-bold text-slate-300 dark:text-slate-600"
                    title="Chưa có điểm nửa sau kỳ thật — giá trị giả định chỉ dùng cho mô hình, không phải điểm thật"
                  >
                    —
                  </span>
                ) : (
                  <span className="text-base font-bold text-slate-900 dark:text-white">
                    {fmtVal(item.weighted_late_avg)}
                  </span>
                )}
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Xu Hướng (Slope)</span>
                <span
                  className={`text-base font-bold ${
                    item.score_slope !== null && item.score_slope < 0
                      ? "text-rose-500"
                      : item.score_slope !== null && item.score_slope > 0
                      ? "text-emerald-500"
                      : "text-slate-700 dark:text-slate-300"
                  }`}
                >
                  {item.score_slope !== null && item.score_slope > 0 ? `+${item.score_slope.toFixed(2)}` : fmtVal(item.score_slope)}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Độ Biến Động (Volatility)</span>
                <span className="text-base font-bold text-slate-900 dark:text-white">
                  {fmtVal(item.score_volatility)}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Mức Rớt Lớn Nhất</span>
                <span className={`text-base font-bold ${item.max_drop && item.max_drop > 0 ? "text-rose-600 dark:text-rose-400" : "text-slate-900 dark:text-white"}`}>
                  {fmtVal(item.max_drop)}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Hệ Số Cao Nhất</span>
                <span className="text-base font-bold text-slate-900 dark:text-white">
                  {fmtVal(item.max_coefficient_so_far, "", 1)}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Số Bài Hệ Số Lớn</span>
                <span className="text-base font-bold text-slate-900 dark:text-white">
                  {fmtInt(item.high_weight_score_count, " bài")}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Điểm Hệ Số Lớn Cuối</span>
                <span className="text-base font-bold text-slate-900 dark:text-white">
                  {item.high_weight_score_count && item.high_weight_score_count > 0 ? fmtVal(item.last_high_weight_score) : "—"}
                </span>
              </div>
            </div>
          </div>

          {/* SECTION 3: 5 LMS FEATURES */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Laptop className="w-4 h-4 text-blue-500" />
              2. Hoạt Động Trực Tuyến LMS (5 Features)
            </h4>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">ĐTB LMS</span>
                <span className="text-base font-bold text-slate-900 dark:text-white">
                  {fmtVal(item.lms_avg_score)}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Tỷ Lệ Nộp Bài LMS</span>
                <span className="text-base font-bold text-slate-900 dark:text-white">
                  {fmtPct(item.lms_submission_rate)}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Tỷ Lệ Nộp Gần Đây</span>
                <span className="text-base font-bold text-slate-900 dark:text-white">
                  {fmtPct(item.lms_recent_submission_rate)}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Sụt Giảm LMS Gần Đây</span>
                <span className="text-base font-bold text-rose-600 dark:text-rose-400">
                  {fmtVal(item.lms_recent_drop)}
                </span>
              </div>

              <div className="col-span-2 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Khoảng Cách LMS - Sổ Điểm (Gradebook Gap)</span>
                <span className="text-base font-bold text-indigo-600 dark:text-indigo-400">
                  {fmtVal(item.lms_gradebook_gap)}
                </span>
              </div>
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
          </div>

          {/* SECTION 4: 4 ATTENDANCE FEATURES */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-emerald-500" />
              3. Điểm Danh & Chuyên Cần (4 Features)
            </h4>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Tỷ Lệ Nghỉ Học Tổng Cả</span>
                <span className="text-base font-bold text-slate-900 dark:text-white">
                  {fmtPct(item.daily_absence_rate)}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Tỷ Lệ Nghỉ Không Phép</span>
                <span className="text-base font-bold text-rose-600 dark:text-rose-400">
                  {fmtPct(item.unexcused_absent_rate)}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Số Ngày Nghỉ Có Phép</span>
                <span className="text-base font-bold text-slate-900 dark:text-white">
                  {fmtInt(item.excused_absent_days, " ngày")}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Số Lần Đi Trễ</span>
                <span className="text-base font-bold text-amber-600 dark:text-amber-400">
                  {fmtInt(item.total_late_count, " lần")}
                </span>
              </div>
            </div>
          </div>

          {/* SECTION 5: 3 BEHAVIOR FEATURES */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <GraduationCap className="w-4 h-4 text-purple-500" />
              4. Kỷ Luật & Nếp Sống Hành Vi (3 Features)
            </h4>

            <div className="grid grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Điểm Trừ Kỷ Luật</span>
                <span className="text-base font-bold text-slate-900 dark:text-white">
                  {fmtInt(item.total_demerit_points, " điểm")}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Số Lần Tái Phạm</span>
                <span className="text-base font-bold text-amber-600 dark:text-amber-400">
                  {fmtInt(item.repeat_offense_count, " lần")}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1">
                <span className="text-slate-400 block">Vi Phạm Nghiêm Trọng</span>
                <span className="text-base font-bold text-rose-600 dark:text-rose-400">
                  {fmtInt(item.severe_sanction_count, " lần")}
                </span>
              </div>
            </div>
          </div>

          {/* SECTION 6: DỮ LIỆU GỐC (RAW) — ĐỐI CHIẾU */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                <ClipboardList className="w-4 h-4 text-cyan-500" />
                5. Dữ Liệu Gốc (Raw) — Đối Chiếu
              </h4>
              {raw && (
                <span className="text-[11px] text-slate-400">
                  Cắt tại {fmtDate(raw.cutoff_date)} • Nhập học {fmtDate(raw.join_date)}
                </span>
              )}
            </div>

            {rawLoading ? (
              <div className="flex items-center justify-center gap-2 py-8 text-xs text-slate-400">
                <Loader2 className="w-4 h-4 animate-spin" /> Đang tải dữ liệu gốc...
              </div>
            ) : rawError ? (
              <div className="text-xs text-rose-500 bg-rose-500/10 border border-rose-500/20 rounded-lg px-3 py-2">
                Không tải được dữ liệu gốc: {rawError}
              </div>
            ) : !raw ? (
              <div className="text-xs text-slate-400 py-6 text-center">Không có dữ liệu.</div>
            ) : (
              <div className="space-y-5">
                {/* 5.1 Điểm số đã khoá */}
                <div className="space-y-2">
                  <h5 className="text-xs font-semibold text-slate-600 dark:text-slate-300 flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5 text-indigo-500" />
                    📊 Điểm số đã khoá ({raw.scores.length})
                  </h5>
                  {raw.scores.length === 0 ? (
                    <p className="text-[11px] text-slate-400">Chưa có đầu điểm nào được khoá trước ngày cắt.</p>
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

                {/* 5.2 Bài tập LMS */}
                <div className="space-y-2">
                  <h5 className="text-xs font-semibold text-slate-600 dark:text-slate-300 flex items-center gap-1.5">
                    <Laptop className="w-3.5 h-3.5 text-blue-500" />
                    📝 Bài tập LMS ({raw.lms_submitted}/{raw.lms_expected} đã nộp)
                  </h5>
                  {raw.lms.length === 0 ? (
                    <p className="text-[11px] text-slate-400">Không có bài tập LMS nào do trong cửa sổ [nhập học → ngày cắt].</p>
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

                {/* 5.3 Điểm danh */}
                <div className="space-y-2">
                  <h5 className="text-xs font-semibold text-slate-600 dark:text-slate-300 flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-emerald-500" />
                    🗓️ Chuyên cần — {raw.attendance.length} ngày gần nhất
                  </h5>
                  {raw.attendance.length === 0 ? (
                    <p className="text-[11px] text-slate-400">Không có dữ liệu điểm danh trước ngày cắt.</p>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {raw.attendance.map((a, i) => {
                        let cls = "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400";
                        if (a.status === "VẮNG KHÔNG PHÉP") cls = "bg-rose-500/10 text-rose-600 dark:text-rose-400";
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

                {/* 5.4 Hành vi / kỷ luật */}
                <div className="space-y-2">
                  <h5 className="text-xs font-semibold text-slate-600 dark:text-slate-300 flex items-center gap-1.5">
                    <ShieldAlert className="w-3.5 h-3.5 text-purple-500" />
                    ⚖️ Kỷ luật & Hành vi ({raw.behavior.length})
                  </h5>
                  {raw.behavior.length === 0 ? (
                    <p className="text-[11px] text-slate-400">Không có ghi nhận vi phạm / hành vi trước ngày cắt.</p>
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
