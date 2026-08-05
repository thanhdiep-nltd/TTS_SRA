"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Play,
  RotateCcw,
  Save,
  XCircle,
} from "lucide-react";

import { api } from "@/lib/api";
import type {
  EwsEffectiveConfig,
  EwsJob,
  EwsValidWeeks,
  EwsWeightConfig,
} from "@/lib/types";

const FACTOR_LABELS: Record<string, string> = {
  score: "Điểm số",
  lms: "LMS",
  attendance: "Chuyên cần",
  behavior: "Hạnh kiểm",
};

const LEVEL_LABELS = ["LOW", "MODERATE", "HIGH", "CRITICAL"];

const STATUS_META: Record<string, { label: string; cls: string; icon: React.ElementType }> = {
  pending: { label: "Chờ xử lý", cls: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300", icon: Activity },
  processing: { label: "Đang chạy", cls: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300", icon: Loader2 },
  completed: { label: "Hoàn tất", cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300", icon: CheckCircle2 },
  failed: { label: "Thất bại", cls: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300", icon: XCircle },
  cancelled: { label: "Đã hủy", cls: "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400", icon: XCircle },
};

const fmtTime = (s: string | null): string => {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
};

/* ===== Icon "i" hover -> tooltip giải thích ===== */
function InfoTip({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label="Giải thích"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-300 text-[10px] font-bold leading-none hover:bg-brand-500 hover:text-white transition-colors"
      >
        i
      </button>
      {open && (
        <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5 w-60 rounded-lg bg-slate-800 dark:bg-slate-700 text-white text-[11px] leading-relaxed p-2.5 shadow-xl z-30">
          {text}
        </span>
      )}
    </span>
  );
}

/* ===== Thanh trượt đa nút: 1 thanh, N đoạn, N-1 nút kéo ===== */
function MultiHandleBar({
  boundaries,
  max,
  segments,
  onChange,
  step = 1,
  format = (v: number) => v.toFixed(2),
}: {
  boundaries: number[];
  max: number;
  segments: { label: string; color: string }[];
  onChange: (b: number[]) => void;
  step?: number;
  format?: (v: number) => string;
}) {
  const barRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{ index: number } | null>(null);
  const boundariesRef = useRef(boundaries);
  useEffect(() => {
    boundariesRef.current = boundaries;
  }, [boundaries]);

  const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

  const handlePointerDown = (index: number) => (e: React.PointerEvent) => {
    e.preventDefault();
    dragRef.current = { index };
    const move = (ev: PointerEvent) => {
      if (!dragRef.current || !barRef.current) return;
      const rect = barRef.current.getBoundingClientRect();
      const ratio = clamp((ev.clientX - rect.left) / rect.width, 0, 1);
      const raw = Math.round((ratio * max) / step) * step;
      const i = dragRef.current.index;
      const cur = boundariesRef.current;
      const lo = i === 0 ? 0 : cur[i - 1];
      const hi = i === cur.length - 1 ? max : cur[i + 1];
      const next = [...cur];
      next[i] = clamp(raw, lo, hi);
      onChange(next);
    };
    const up = () => {
      dragRef.current = null;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const ends = [0, ...boundaries, max];

  return (
    <div ref={barRef} className="relative h-9 w-full select-none touch-none">
      {/* Các đoạn màu */}
      {segments.map((seg, i) => {
        const left = (ends[i] / max) * 100;
        const width = ((ends[i + 1] - ends[i]) / max) * 100;
        return (
          <div
            key={seg.label}
            className="absolute top-0 h-full flex items-center justify-center text-[10px] font-semibold text-white/90 overflow-hidden"
            style={{ left: `${left}%`, width: `${width}%`, backgroundColor: seg.color }}
            title={`${seg.label}: ${format(ends[i])} – ${format(ends[i + 1])}`}
          >
            {width > 10 ? seg.label : ""}
          </div>
        );
      })}
      {/* Các nút kéo */}
      {boundaries.map((b, i) => (
        <div
          key={i}
          onPointerDown={handlePointerDown(i)}
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-4 h-7 rounded-md bg-white border-2 border-slate-400 shadow cursor-ew-resize z-10 hover:border-brand-500"
          style={{ left: `${(b / max) * 100}%` }}
          title={format(b)}
        />
      ))}
    </div>
  );
}

export default function EwsControlPanel() {
  const [validWeeks, setValidWeeks] = useState<EwsValidWeeks | null>(null);
  const [jobs, setJobs] = useState<EwsJob[]>([]);
  const [config, setConfig] = useState<EwsEffectiveConfig | null>(null);

  // Form dự đoán
  const [schoolYear, setSchoolYear] = useState<number>(2025);
  const [semester, setSemester] = useState<number>(1);
  const [week, setWeek] = useState<number>(8);
  const [modelVersion, setModelVersion] = useState<string>("v2_ensemble");
  const [predicting, setPredicting] = useState<boolean>(false);

  // Form trọng số
  const [weights, setWeights] = useState<EwsWeightConfig>({});
  const [savingWeights, setSavingWeights] = useState<boolean>(false);
  const [weightError, setWeightError] = useState<string | null>(null);
  const [weightNotice, setWeightNotice] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadJobs = useCallback(async () => {
    try {
      const data = await api.get<EwsJob[]>("/ews/jobs");
      setJobs(data);
    } catch {
      /* ignore */
    }
  }, []);

  const loadConfig = useCallback(async () => {
    try {
      const data = await api.get<EwsEffectiveConfig>("/ews/weights");
      setConfig(data);
      setWeights(data.override ?? {});
    } catch {
      /* ignore */
    }
  }, []);

  const loadValidWeeks = useCallback(async () => {
    try {
      const data = await api.get<EwsValidWeeks>("/ews/valid-weeks");
      setValidWeeks(data);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadValidWeeks();
    loadJobs();
    loadConfig();
  }, [loadValidWeeks, loadJobs, loadConfig]);

  // Polling khi có job đang chạy
  useEffect(() => {
    const hasActive = jobs.some((j) => j.status === "pending" || j.status === "processing");
    if (hasActive && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        await loadJobs();
      }, 3000);
    } else if (!hasActive && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [jobs, loadJobs]);

  const weeks = semester === 1 ? validWeeks?.semester_1 ?? [] : validWeeks?.semester_2 ?? [];

  const handlePredict = async () => {
    setPredicting(true);
    try {
      await api.post<EwsJob>("/ews/predict", {
        school_year_id: schoolYear,
        semester_index: semester,
        evaluated_at_week: week,
        model_version: modelVersion,
      });
      await loadJobs();
    } catch (e) {
      setWeightError(e instanceof Error ? e.message : "Không thể tạo job dự đoán");
    } finally {
      setPredicting(false);
    }
  };

  const handleSaveWeights = async () => {
    setSavingWeights(true);
    setWeightError(null);
    setWeightNotice(null);
    try {
      const data = await api.put<EwsEffectiveConfig>("/ews/weights", weights);
      setConfig(data);
      setWeights(data.override ?? {});
      setWeightNotice("Đã lưu override trọng số cho trường.");
    } catch (e) {
      setWeightError(e instanceof Error ? e.message : "Lưu thất bại");
    } finally {
      setSavingWeights(false);
    }
  };

  const handleResetWeights = async () => {
    if (!window.confirm("Khôi phục trọng số về mặc định (baseline YAML)?")) return;
    setWeightError(null);
    setWeightNotice(null);
    try {
      await api.del("/ews/weights");
      await loadConfig();
      setWeights({});
      setWeightNotice("Đã khôi phục trọng số mặc định.");
    } catch (e) {
      setWeightError(e instanceof Error ? e.message : "Khôi phục thất bại");
    }
  };

  const setWeight = (key: keyof EwsWeightConfig, value: string) => {
    setWeights((prev) => {
      const next = { ...prev };
      if (value === "") {
        delete next[key];
      } else {
        next[key] = Number(value);
      }
      return next;
    });
  };

  // ===== Giá trị hiệu lực & mặc định =====
  const effW = (f: string) => Number(config?.effective.weights?.[f] ?? 0);
  const baseW = (f: string) => Number(config?.baseline.weights?.[f] ?? 0);
  const dispW = (f: string) => {
    const v = weights[`weight_${f}` as keyof EwsWeightConfig];
    return v != null ? Number(v) : effW(f);
  };
  const effT = (lv: string) => Number(config?.effective.thresholds?.[lv] ?? 0);
  const baseT = (lv: string) => Number(config?.baseline.thresholds?.[lv] ?? 0);
  const dispT = (lv: string) => {
    const v = weights[`threshold_${lv.toLowerCase()}` as keyof EwsWeightConfig];
    return v != null ? Number(v) : effT(lv);
  };

  // Thanh trọng số: 4 đoạn, 3 nút (ranh giới tích lũy)
  const weightBoundaries = [
    dispW("score"),
    dispW("score") + dispW("lms"),
    dispW("score") + dispW("lms") + dispW("attendance"),
  ];
  const onWeightChange = (b: number[]) => {
    setWeights((prev) => ({
      ...prev,
      weight_score: b[0],
      weight_lms: b[1] - b[0],
      weight_attendance: b[2] - b[1],
      weight_behavior: 1 - b[2],
    }));
  };

  // Thanh ngưỡng: 4 vùng, 3 nút (low/moderate/high); critical tự = 100
  const thrBoundaries = [dispT("LOW"), dispT("MODERATE"), dispT("HIGH")];
  const onThrChange = (b: number[]) => {
    setWeights((prev) => ({
      ...prev,
      threshold_low: b[0],
      threshold_moderate: b[1],
      threshold_high: b[2],
      threshold_critical: 100,
    }));
  };

  // Validation client-side: chỉ validate khi có override; chưa override = dùng mặc định (hợp lệ).
  const weightKeys = ["weight_score", "weight_lms", "weight_attendance", "weight_behavior"];
  const hasWeightOverride = weightKeys.some((k) => weights[k as keyof EwsWeightConfig] != null);
  const weightSum = weightKeys.reduce((acc, k) => acc + (Number(weights[k as keyof EwsWeightConfig]) || 0), 0);
  const weightSumValid = !hasWeightOverride || Math.abs(weightSum - 1) < 1e-6;

  const thrKeys = ["threshold_low", "threshold_moderate", "threshold_high", "threshold_critical"];
  const hasThrOverride = thrKeys.some((k) => weights[k as keyof EwsWeightConfig] != null);
  const thrVals = LEVEL_LABELS.map((lv) => Number(weights[`threshold_${lv.toLowerCase()}` as keyof EwsWeightConfig]) || 0);
  const thrValid = !hasThrOverride || thrVals.every((v, i) => i === 0 || v > thrVals[i - 1]);

  // Tổng hiển thị: dùng override nếu có, ngược lại dùng tổng hiệu lực (baseline).
  const displaySum = hasWeightOverride
    ? weightSum
    : effW("score") + effW("lms") + effW("attendance") + effW("behavior");

  // Dirty state: chỉ sáng nút Save khi có thay đổi so với override đã lưu.
  const sameConfig = (a: EwsWeightConfig, b: EwsWeightConfig) => {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const k of keys) {
      if ((a[k as keyof EwsWeightConfig] ?? null) !== (b[k as keyof EwsWeightConfig] ?? null)) return false;
    }
    return true;
  };
  const isDirty = !sameConfig(weights, config?.override ?? {});

  const numInput = (
    key: keyof EwsWeightConfig,
    label: string,
    step = "0.01",
    opts?: { hint?: string; info?: string; min?: number; max?: number; defaultValue?: number },
  ) => (
    <label className="block">
      <span className="flex items-center gap-1 text-xs font-medium text-slate-500 dark:text-slate-400">
        {label}
        {opts?.info && <InfoTip text={opts.info} />}
      </span>
      <input
        type="number"
        step={step}
        min={opts?.min}
        max={opts?.max}
        value={weights[key] ?? ""}
        placeholder={opts?.defaultValue != null ? String(opts.defaultValue) : ""}
        onChange={(e) => setWeight(key, e.target.value)}
        className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500"
      />
      {opts?.hint && <span className="text-[10px] text-slate-400">{opts.hint}</span>}
    </label>
  );

  // Thanh kéo 1 nút cho tham số đơn (weight_floor, worst_factor_beta) — giá trị nằm trong khoảng gợi ý.
  const sliderInput = (
    key: keyof EwsWeightConfig,
    label: string,
    opts: { min: number; max: number; step?: number; hint?: string; info?: string; defaultValue?: number },
  ) => {
    const val = weights[key] != null ? Number(weights[key]) : (opts.defaultValue ?? opts.min);
    return (
      <label className="block">
        <span className="flex items-center gap-1 text-xs font-medium text-slate-500 dark:text-slate-400">
          {label}
          {opts.info && <InfoTip text={opts.info} />}
        </span>
        <div className="mt-1 flex items-center gap-2">
          <input
            type="range"
            min={opts.min}
            max={opts.max}
            step={opts.step ?? 0.01}
            value={val}
            onChange={(e) => setWeight(key, e.target.value)}
            className="w-full accent-brand-600"
          />
          <span className="w-12 text-right text-sm font-semibold text-slate-700 dark:text-slate-200">
            {val.toFixed(2)}
          </span>
        </div>
        <span className="text-[10px] text-slate-400">
          {opts.hint}
          {opts.defaultValue != null && ` · mặc định ${opts.defaultValue}`}
        </span>
      </label>
    );
  };

  return (
    <div className="space-y-6">
      {/* ===== DỰ ĐOÁN THEO TUẦN ===== */}
      <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Play className="w-5 h-5 text-brand-600" />
          <h3 className="text-lg font-bold text-slate-900 dark:text-white">Thực hiện dự đoán theo tuần</h3>
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
          Nhấn dự đoán để tạo job chạy nền. Bạn có thể rời đi; khi xong kết quả sẽ tự cập nhật ở bảng "Lịch sử dự đoán" bên dưới.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <label className="block">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Năm học</span>
            <input
              type="number"
              value={schoolYear}
              onChange={(e) => setSchoolYear(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Học kỳ</span>
            <select
              value={semester}
              onChange={(e) => {
                const s = Number(e.target.value);
                setSemester(s);
                setWeek(s === 1 ? (validWeeks?.semester_1?.[0] ?? 8) : (validWeeks?.semester_2?.[0] ?? 23));
              }}
              className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
            >
              <option value={1}>Học kỳ 1</option>
              <option value={2}>Học kỳ 2</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Tuần</span>
            <select
              value={week}
              onChange={(e) => setWeek(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
            >
              {weeks.map((w) => (
                <option key={w} value={w}>Tuần {w}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Model</span>
            <select
              value={modelVersion}
              onChange={(e) => setModelVersion(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
            >
              <option value="v2_ensemble">v2 — Factor-Ensemble</option>
              <option value="v1_single">v1 — Model đơn</option>
            </select>
          </label>
          <div className="flex items-end">
            <button
              onClick={handlePredict}
              disabled={predicting}
              className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white font-semibold text-sm rounded-xl disabled:opacity-50"
            >
              {predicting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Dự đoán
            </button>
          </div>
        </div>
        {modelVersion === "v1_single" && (
          <p className="mt-3 text-xs text-amber-600 dark:text-amber-400">
            Lưu ý: override trọng số chỉ ảnh hưởng v2_ensemble. v1_single dùng trọng số học từ SHAP.
          </p>
        )}
      </section>

      {/* ===== LỊCH SỬ JOB ===== */}
      <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-5 h-5 text-brand-600" />
          <h3 className="text-lg font-bold text-slate-900 dark:text-white">Lịch sử dự đoán</h3>
        </div>
        {jobs.length === 0 ? (
          <p className="text-sm text-slate-400">Chưa có job nào.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-200 dark:border-slate-700">
                <tr>
                  <th className="py-2 px-3">ID</th>
                  <th className="py-2 px-3">Tuần</th>
                  <th className="py-2 px-3">Model</th>
                  <th className="py-2 px-3">Trạng thái</th>
                  <th className="py-2 px-3">Tiến độ</th>
                  <th className="py-2 px-3">Số dòng</th>
                  <th className="py-2 px-3">Tạo lúc</th>
                  <th className="py-2 px-3">Lỗi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {jobs.map((j) => {
                  const meta = STATUS_META[j.status] ?? STATUS_META.pending;
                  const Icon = meta.icon;
                  return (
                    <tr key={j.id}>
                      <td className="py-2 px-3 font-mono">#{j.id}</td>
                      <td className="py-2 px-3">HK{j.semester_index} · Tuần {j.evaluated_at_week}</td>
                      <td className="py-2 px-3">{j.model_version}</td>
                      <td className="py-2 px-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${meta.cls}`}>
                          <Icon className={`w-3 h-3 ${j.status === "processing" ? "animate-spin" : ""}`} />
                          {meta.label}
                        </span>
                      </td>
                      <td className="py-2 px-3">{j.progress}%</td>
                      <td className="py-2 px-3">{j.rows_processed ?? "—"}</td>
                      <td className="py-2 px-3">{fmtTime(j.created_at)}</td>
                      <td className="py-2 px-3 text-rose-600 dark:text-rose-400 max-w-[200px] truncate" title={j.error_message ?? ""}>
                        {j.error_message ?? "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ===== CHỈNH TRỌNG SỐ ===== */}
      <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6">
        <div className="flex items-center gap-2 mb-1">
          <Save className="w-5 h-5 text-brand-600" />
          <h3 className="text-lg font-bold text-slate-900 dark:text-white">Tinh chỉnh trọng số EWS</h3>
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
          Chỉ ảnh hưởng <b>v2_ensemble</b>. Kéo nút trên thanh để điều chỉnh; giá trị trong ngoặc là mặc định (baseline YAML).
        </p>

        {weightError && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-rose-50 dark:bg-rose-900/30 text-rose-700 dark:text-rose-300 px-3 py-2 text-sm">
            <AlertTriangle className="w-4 h-4" /> {weightError}
          </div>
        )}
        {weightNotice && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 px-3 py-2 text-sm">
            <CheckCircle2 className="w-4 h-4" /> {weightNotice}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Trọng số */}
          <div className="space-y-3">
            <h4 className="flex items-center gap-1 text-sm font-semibold text-slate-700 dark:text-slate-200">
              Trọng số (tổng = 1)
              <InfoTip text="Trọng số gốc cho từng yếu tố rủi ro. Tổng luôn = 1. Kéo 3 nút trên thanh để phân bổ lại giữa 4 yếu tố." />
            </h4>
            <MultiHandleBar
              boundaries={weightBoundaries}
              max={1}
              step={0.01}
              segments={[
                { label: "Điểm", color: "#3b82f6" },
                { label: "LMS", color: "#06b6d4" },
                { label: "Chuyên cần", color: "#f59e0b" },
                { label: "Hạnh kiểm", color: "#f43f5e" },
              ]}
              onChange={onWeightChange}
              format={(v) => `${(v * 100).toFixed(0)}%`}
            />
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              {Object.keys(FACTOR_LABELS).map((f) => (
                <div key={f} className="flex items-center justify-between rounded bg-slate-50 dark:bg-slate-800/60 px-2 py-1">
                  <span className="text-slate-500 dark:text-slate-400">{FACTOR_LABELS[f]}</span>
                  <span className="font-semibold text-slate-700 dark:text-slate-200">
                    {(dispW(f) * 100).toFixed(0)}%
                    <span className="ml-1 font-normal text-slate-400">(mặc định {(baseW(f) * 100).toFixed(0)}%)</span>
                  </span>
                </div>
              ))}
            </div>
            <div className={`text-xs font-medium ${weightSumValid ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
              Tổng trọng số: {displaySum.toFixed(4)} {weightSumValid ? "✓" : "— phải bằng 1.0"}
            </div>

            <h4 className="flex items-center gap-1 text-sm font-semibold text-slate-700 dark:text-slate-200 pt-2">
              Alpha động
              <InfoTip text="Hệ số khuếch đại softmax cho từng yếu tố. Càng cao → yếu tố rủi ro càng 'nở' trọng số. Gợi ý 0.5–3.0." />
            </h4>
            <div className="grid grid-cols-2 gap-3">
              {Object.keys(FACTOR_LABELS).map((f) => (
                <div key={`alpha_${f}`}>
                  {numInput(`alpha_${f}` as keyof EwsWeightConfig, FACTOR_LABELS[f], "0.1", {
                    min: 0,
                    max: 5,
                    defaultValue: Number(config?.baseline.alpha?.[f] ?? 1),
                  })}
                </div>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2">
              {sliderInput("weight_floor", "weight_floor", {
                min: 0,
                max: 0.2,
                step: 0.01,
                hint: "gợi ý 0–0.2",
                defaultValue: config?.baseline.weight_floor,
                info: "Sàn trọng số tối thiểu mỗi yếu tố, tránh bị triệt tiêu hoàn toàn.",
              })}
              {sliderInput("worst_factor_beta", "worst_factor_beta", {
                min: 0,
                max: 1,
                step: 0.01,
                hint: "gợi ý 0–1",
                defaultValue: config?.baseline.worst_factor_beta,
                info: "Pha trộn Worst-Factor Dominance vào final score. 0 = tắt.",
              })}
            </div>
          </div>

          {/* Ngưỡng */}
          <div className="space-y-3">
            <h4 className="flex items-center gap-1 text-sm font-semibold text-slate-700 dark:text-slate-200">
              Ngưỡng risk_level
              <InfoTip text="Chia thang điểm rủi ro [0–100] thành 4 vùng: LOW, MODERATE, HIGH, CRITICAL. Kéo 3 nút để đặt ranh giới giữa các vùng." />
            </h4>
            <MultiHandleBar
              boundaries={thrBoundaries}
              max={100}
              step={1}
              segments={[
                { label: "LOW", color: "#10b981" },
                { label: "MODERATE", color: "#f59e0b" },
                { label: "HIGH", color: "#f97316" },
                { label: "CRITICAL", color: "#ef4444" },
              ]}
              onChange={onThrChange}
              format={(v) => v.toFixed(0)}
            />
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              {LEVEL_LABELS.map((lv, idx) => {
                // Khoảng của từng mức: LOW [0, low), MODERATE [low, moderate),
                // HIGH [moderate, high), CRITICAL [high, 100].
                const lo = idx === 0 ? 0 : thrBoundaries[idx - 1];
                const hi = idx === LEVEL_LABELS.length - 1 ? 100 : thrBoundaries[idx];
                const loBase = idx === 0 ? 0 : baseT(LEVEL_LABELS[idx - 1]);
                const hiBase = idx === LEVEL_LABELS.length - 1 ? 100 : baseT(LEVEL_LABELS[idx]);
                return (
                  <div key={lv} className="flex items-center justify-between rounded bg-slate-50 dark:bg-slate-800/60 px-2 py-1">
                    <span className="text-slate-500 dark:text-slate-400">{lv}</span>
                    <span className="font-semibold text-slate-700 dark:text-slate-200">
                      {lo.toFixed(0)} → {hi.toFixed(0)}
                      <span className="ml-1 font-normal text-slate-400">(mặc định {loBase.toFixed(0)} → {hiBase.toFixed(0)})</span>
                    </span>
                  </div>
                );
              })}
            </div>
            <div className={`text-xs font-medium ${thrValid ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
              {thrValid ? "Ngưỡng tăng dần ✓" : "Ngưỡng phải tăng dần (LOW < MODERATE < HIGH < CRITICAL)"}
            </div>

            {config && (
              <div className="mt-4 rounded-lg bg-slate-50 dark:bg-slate-800/60 p-3 text-xs space-y-1">
                <div className="font-semibold text-slate-600 dark:text-slate-300">Baseline hiện tại (YAML)</div>
                <div className="text-slate-500 dark:text-slate-400">
                  weights: {JSON.stringify(config.baseline.weights)}
                </div>
                <div className="text-slate-500 dark:text-slate-400">
                  alpha: {JSON.stringify(config.baseline.alpha)}
                </div>
                <div className="text-slate-500 dark:text-slate-400">
                  floor: {config.baseline.weight_floor} · beta: {config.baseline.worst_factor_beta}
                </div>
                <div className="text-slate-500 dark:text-slate-400">
                  thresholds: {JSON.stringify(config.baseline.thresholds)}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="mt-5 flex items-center gap-3">
          <button
            onClick={handleSaveWeights}
            disabled={savingWeights || !weightSumValid || !thrValid || !isDirty}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white font-semibold text-sm rounded-xl disabled:opacity-50"
          >
            {savingWeights ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Lưu
          </button>
          <button
            onClick={handleResetWeights}
            className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-semibold text-sm rounded-xl"
          >
            <RotateCcw className="w-4 h-4" /> Khôi phục mặc định
          </button>
          {isDirty && (
            <span className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> Có thay đổi chưa lưu
            </span>
          )}
        </div>
      </section>
    </div>
  );
}
