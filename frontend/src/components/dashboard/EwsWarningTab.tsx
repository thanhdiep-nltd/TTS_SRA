"use client";

import { useEffect, useState, useMemo } from "react";
import {
  AlertTriangle,
  Award,
  ChevronLeft,
  ChevronRight,
  Filter,
  Info,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
  UserX,
  Users,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

import { api, ApiError } from "@/lib/api";
import { LoadingState } from "@/components/Loading";
import EwsDetailDrawer from "@/components/dashboard/EwsDetailDrawer";
import {
  EWS_RISK_COLORS,
  EWS_RISK_LABELS,
  EWS_RISK_ORDER,
  type EwsMeta,
  type EwsOverview,
  type EwsPagedResult,
  type EwsPredictionRow,
  type EwsRiskLevel,
} from "@/lib/types";

const PAGE_SIZE = 50;

const FACTOR_VI: Record<string, { label: string; icon: string; color: string }> = {
  SLOPE_DOWN: { label: "Tụt dốc điểm", icon: "📉", color: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20" },
  LAST_SCORE_LOW: { label: "Bài thi gần nhất rớt", icon: "⚠️", color: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20" },
  ABSENTEEISM: { label: "Vắng học nhiều", icon: "🚫", color: "bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20" },
};

// Ngày bắt đầu học kỳ (khớp backend feature_extractor.base_start):
//   HK1: 05/09/năm, HK2: 20/01/năm sau. Trả về chuỗi 'YYYY-MM-DD' để so sánh string (ISO-safe).
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

export default function EwsWarningTab() {
  const [meta, setMeta] = useState<EwsMeta | null>(null);
  const [overview, setOverview] = useState<EwsOverview | null>(null);
  const [predictions, setPredictions] = useState<EwsPagedResult | null>(null);
  const [selectedItem, setSelectedItem] = useState<EwsPredictionRow | null>(null);

  const [loadingMeta, setLoadingMeta] = useState(true);
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [loadingPreds, setLoadingPreds] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filter States
  const [schoolYearId, setSchoolYearId] = useState<number>(2025);
  const [semesterIndex, setSemesterIndex] = useState<number>(1);
  const [week, setWeek] = useState<number>(8);
  const [riskLevel, setRiskLevel] = useState<string>("ALL");
  const [subjectId, setSubjectId] = useState<string>("ALL");
  const [gradeId, setGradeId] = useState<string>("ALL");
  const [className, setClassName] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [debouncedQuery, setDebouncedQuery] = useState<string>("");
  const [page, setPage] = useState<number>(1);

  // 1. Fetch Metadata on Mount
  useEffect(() => {
    let isMounted = true;
    setLoadingMeta(true);
    setError(null);

    api
      .get<EwsMeta>("/ews/meta")
      .then((res) => {
        if (!isMounted) return;
        setMeta(res);
        if (res.weeks && res.weeks.length > 0) {
          const first = res.weeks[0];
          setSchoolYearId(first.school_year_id);
          setSemesterIndex(first.semester_index);
          setWeek(first.evaluated_at_week);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error("Failed to load EWS meta:", err);
        setError(err instanceof ApiError ? err.message : "Không thể tải danh sách bộ lọc EWS");
      })
      .finally(() => {
        if (isMounted) setLoadingMeta(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // 2. Fetch Overview & Predictions when Primary Filters Change
  useEffect(() => {
    if (loadingMeta) return;

    let isMounted = true;
    setLoadingOverview(true);

    const overviewParams = new URLSearchParams({
      school_year_id: String(schoolYearId),
      semester_index: String(semesterIndex),
      evaluated_at_week: String(week),
    });

    api
      .get<EwsOverview>(`/ews/overview?${overviewParams.toString()}`)
      .then((res) => {
        if (isMounted) setOverview(res);
      })
      .catch((err) => {
        console.error("Failed to fetch EWS overview:", err);
      })
      .finally(() => {
        if (isMounted) setLoadingOverview(false);
      });

    return () => {
      isMounted = false;
    };
  }, [schoolYearId, semesterIndex, week, loadingMeta]);

  // 3. Fetch Predictions List when Filter/Page Changes
  useEffect(() => {
    if (loadingMeta) return;

    let isMounted = true;
    setLoadingPreds(true);

    const offset = (page - 1) * PAGE_SIZE;
    const predParams = new URLSearchParams({
      school_year_id: String(schoolYearId),
      semester_index: String(semesterIndex),
      evaluated_at_week: String(week),
      limit: String(PAGE_SIZE),
      offset: String(offset),
    });

    if (riskLevel !== "ALL") predParams.set("risk_level", riskLevel);
    if (subjectId !== "ALL") predParams.set("subject_id", subjectId);
    if (gradeId !== "ALL") predParams.set("grade_id", gradeId);
    if (className !== "ALL") predParams.set("class_name", className);
    if (debouncedQuery) predParams.set("q", debouncedQuery);

    api
      .get<EwsPagedResult>(`/ews/predictions?${predParams.toString()}`)
      .then((res) => {
        if (isMounted) setPredictions(res);
      })
      .catch((err) => {
        console.error("Failed to fetch EWS predictions:", err);
      })
      .finally(() => {
        if (isMounted) setLoadingPreds(false);
      });

    return () => {
      isMounted = false;
    };
  }, [schoolYearId, semesterIndex, week, riskLevel, subjectId, gradeId, className, debouncedQuery, page, loadingMeta]);

  // Debounce từ khóa tìm kiếm (300ms) → tìm kiếm server-side qua param q
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedQuery(searchQuery.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [searchQuery]);

  // Làm mới danh sách Môn/Khối/Lớp theo đúng Mốc Đánh Giá đang chọn
  useEffect(() => {
    if (loadingMeta) return;
    let isMounted = true;
    api
      .get<EwsMeta>(
        `/ews/meta?school_year_id=${schoolYearId}&semester_index=${semesterIndex}&evaluated_at_week=${week}`
      )
      .then((res) => {
        if (!isMounted) return;
        setMeta((prev) =>
          prev ? { ...prev, subjects: res.subjects, grades: res.grades, classes: res.classes } : res
        );
      })
      .catch((err) => {
        console.error("Failed to refresh EWS filter options:", err);
      });
    return () => {
      isMounted = false;
    };
  }, [schoolYearId, semesterIndex, week, loadingMeta]);

  // Tùy chọn Lớp được lọc theo Khối đang chọn (Khối → Lớp liên kết đúng)
  const classOptions = useMemo(() => {
    if (!meta) return [];
    const gid = gradeId === "ALL" ? null : Number(gradeId);
    return gid === null ? meta.classes : meta.classes.filter((c) => c.grade_id === gid);
  }, [meta, gradeId]);

  // Danh sách dự báo trên trang hiện tại (tìm kiếm đã chuyển sang server-side qua param q)
  const predictionItems = predictions?.items || [];

  const totalPages = Math.ceil((predictions?.total || 0) / PAGE_SIZE);

  if (loadingMeta) {
    return <LoadingState message="Đang tải dữ liệu phân hệ Cảnh báo EWS AI..." />;
  }

  return (
    <div className="space-y-6">
      {/* HEADER SECTION */}
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
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setLoadingOverview(true);
              setLoadingPreds(true);
              setPage(1);
            }}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600/80 hover:bg-indigo-600 text-white font-medium text-sm rounded-xl transition-all shadow-sm"
          >
            <RefreshCw className="w-4 h-4" /> Làm mới
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 rounded-xl text-sm flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI OVERVIEW CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Tổng lượt dự báo */}
        <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-blue-500/10 text-blue-600 dark:text-blue-400 rounded-xl">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Tổng Lượt Dự Báo</p>
            <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              {loadingOverview ? "..." : (overview?.total_predictions || 0).toLocaleString()}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">{overview?.total_students || 0} học sinh unique</p>
          </div>
        </div>

        {/* Card 2: Học sinh nguy cơ HIGH + CRITICAL */}
        <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-rose-500/10 text-rose-600 dark:text-rose-400 rounded-xl">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Cần Can Thiệp (HIGH + CRIT)</p>
            <h3 className="text-2xl font-bold text-rose-600 dark:text-rose-400">
              {loadingOverview ? "..." : (overview?.at_risk_count || 0).toLocaleString()}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {overview?.total_predictions
                ? `${(((overview.at_risk_count || 0) / overview.total_predictions) * 100).toFixed(1)}% trên tổng số`
                : "0%"}
            </p>
          </div>
        </div>

        {/* Card 3: Tỷ lệ CRITICAL khẩn cấp */}
        <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-red-500/10 text-red-600 dark:text-red-400 rounded-xl">
            <ShieldAlert className="w-6 h-6 animate-bounce" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Mức CRITICAL (Khẩn cấp)</p>
            <h3 className="text-2xl font-bold text-red-600 dark:text-red-500">
              {loadingOverview
                ? "..."
                : (overview?.levels.find((l) => l.level === "CRITICAL")?.count || 0).toLocaleString()}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">Nguy cơ cấm thi / trượt môn cao</p>
          </div>
        </div>

        {/* Card 4: Điểm Rủi Ro Trung Bình */}
        <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-amber-500/10 text-amber-600 dark:text-amber-400 rounded-xl">
            <Award className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Điểm Rủi Ro TB (0-100)</p>
            <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              {loadingOverview ? "..." : overview?.avg_risk_score || "0.0"}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">Thang rủi ro chuẩn hóa CatBoost</p>
          </div>
        </div>
      </div>

      {/* CHARTS & HEATMAP GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart 1: Phân bố Rủi ro theo 4 Mức */}
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
            Phân Bố 4 Mức Độ Rủi Ro (Risk Level Distribution)
          </h4>
          <div className="h-64 w-full">
            {loadingOverview ? (
              <div className="h-full flex items-center justify-center text-slate-400">
                <Loader2 className="w-6 h-6 animate-spin" />
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={
                    overview?.levels.map((l) => ({
                      level: EWS_RISK_LABELS[l.level as EwsRiskLevel] || l.level,
                      rawLevel: l.level,
                      count: l.count,
                    })) || []
                  }
                  margin={{ top: 10, right: 10, left: 0, bottom: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                  <XAxis dataKey="level" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <RechartsTooltip
                    formatter={(val: any) => [`${Number(val || 0).toLocaleString()} dự báo`, "Số lượng"]}
                    contentStyle={{ borderRadius: "12px", fontSize: "12px" }}
                  />
                  <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                    {overview?.levels.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={EWS_RISK_COLORS[entry.level as EwsRiskLevel] || "#3b82f6"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Chart 2: Top Môn Học Nguy Cơ Cao Nhất */}
        <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
            Top 5 Môn Học Rủi Ro Cao Nhất
          </h4>
          <div className="space-y-3">
            {loadingOverview ? (
              <div className="py-12 flex justify-center text-slate-400">
                <Loader2 className="w-6 h-6 animate-spin" />
              </div>
            ) : overview?.top_risk_subjects && overview.top_risk_subjects.length > 0 ? (
              overview.top_risk_subjects.slice(0, 5).map((sub, idx) => (
                <div key={idx} className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">{sub.subject_name}</p>
                    <p className="text-[11px] text-slate-400">{sub.cnt} lượt dự báo</p>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-bold text-rose-600 dark:text-rose-400">{sub.avg_risk}</span>
                    <span className="text-[10px] text-slate-400 block">Risk Score</span>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-400 py-6 text-center">Không có dữ liệu môn rủi ro</p>
            )}
          </div>
        </div>
      </div>

      {/* FILTER BAR SECTION */}
      <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200 border-b border-slate-100 dark:border-slate-800 pb-3">
          <Filter className="w-4 h-4 text-indigo-500" />
          <span>Bộ Lọc Ngữ Cảnh Dự Báo</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {/* 1. Mốc Tuần / Học Kỳ */}
          <div className="col-span-1 lg:col-span-2 space-y-1">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Mốc Đánh Giá (Tuần / Kỳ)</label>
            <select
              value={`${schoolYearId}-${semesterIndex}-${week}`}
              onChange={(e) => {
                const [sy, sem, wk] = e.target.value.split("-").map(Number);
                setSchoolYearId(sy);
                setSemesterIndex(sem);
                setWeek(wk);
                // Danh sách Môn/Khối/Lớp thay đổi theo mốc → reset bộ lọc phụ thuộc
                setSubjectId("ALL");
                setGradeId("ALL");
                setClassName("ALL");
                setPage(1);
              }}
              className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500"
            >
              {meta?.weeks.map((w, idx) => (
                <option key={idx} value={`${w.school_year_id}-${w.semester_index}-${w.evaluated_at_week}`}>
                  {w.school_year_name || `Năm ${w.school_year_id}`} - Học kỳ {w.semester_index} (Mốc Tuần {w.evaluated_at_week})
                </option>
              ))}
            </select>
          </div>

          {/* 2. Mức Rủi Ro */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Mức Rủi Ro</label>
            <select
              value={riskLevel}
              onChange={(e) => {
                setRiskLevel(e.target.value);
                setPage(1);
              }}
              className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500 font-medium"
            >
              <option value="ALL">Tất cả (All Levels)</option>
              <option value="CRITICAL">🔴 CRITICAL (Nghiêm trọng)</option>
              <option value="HIGH">🟠 HIGH (Rủi ro cao)</option>
              <option value="MODERATE">🟡 MODERATE (Trung bình)</option>
              <option value="LOW">🟢 LOW (An toàn)</option>
            </select>
          </div>

          {/* 3. Môn Học */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Môn Học</label>
            <select
              value={subjectId}
              onChange={(e) => {
                setSubjectId(e.target.value);
                setPage(1);
              }}
              className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ALL">Tất cả môn học</option>
              {meta?.subjects.map((sub) => (
                <option key={sub.id} value={sub.id}>
                  {sub.name} ({sub.code})
                </option>
              ))}
            </select>
          </div>

          {/* 4. Khối Lớp */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Khối Lớp</label>
            <select
              value={gradeId}
              onChange={(e) => {
                setGradeId(e.target.value);
                setClassName("ALL"); // lớp cũ có thể không thuộc khối mới
                setPage(1);
              }}
              className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ALL">Tất cả khối lớp</option>
              {meta?.grades.map((g) => (
                <option key={g.grade_id} value={g.grade_id}>
                  {g.grade_name}
                </option>
              ))}
            </select>
          </div>

          {/* 5. Tên Lớp */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Lớp Học</label>
            <select
              value={className}
              onChange={(e) => {
                setClassName(e.target.value);
                setPage(1);
              }}
              className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ALL">Tất cả các lớp</option>
              {classOptions.map((cls, idx) => (
                <option key={idx} value={cls.class_name}>
                  {cls.class_name}
                </option>
              ))}
            </select>
          </div>

          {/* 6. Tìm kiếm Mã/Tên HS */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Tìm kiếm nhanh</label>
            <div className="relative">
              <input
                type="text"
                placeholder="Mã HS hoặc tên..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl pl-8 pr-3 py-2 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500"
              />
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            </div>
          </div>
        </div>
      </div>

      {/* PREDICTIONS DATA TABLE */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden space-y-4 p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-indigo-500" />
            <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              Danh Sách Dự Báo Chi Tiết ({predictions?.total.toLocaleString() || 0} Kết Quả)
            </h4>
          </div>
          <span className="text-xs text-slate-400">
            Hiển thị trang {page} / {totalPages || 1} ({PAGE_SIZE} bản ghi/trang)
          </span>
        </div>

        {/* DATA TABLE */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-200 dark:border-slate-700">
              <tr>
                <th className="py-3.5 px-4">Học Sinh</th>
                <th className="py-3.5 px-4">Khối / Lớp</th>
                <th className="py-3.5 px-4">Môn Học</th>
                <th className="py-3.5 px-4 text-center">Điểm Rủi Ro (0-100)</th>
                <th className="py-3.5 px-4 text-center">Mức Rủi Ro</th>
                <th className="py-3.5 px-4">Cờ Nguyên Nhân (Risk Badges)</th>
                <th className="py-3.5 px-4 text-right">Điểm Thi Gần Nhất</th>
                <th className="py-3.5 px-4 text-right">ĐTB Nửa Đầu</th>
                <th className="py-3.5 px-4 text-right">Xu Hướng (Slope)</th>
                <th className="py-3.5 px-4 text-right">ĐTB LMS</th>
                <th className="py-3.5 px-4 text-right">Tỷ Lệ Nộp LMS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {loadingPreds ? (
                <tr>
                  <td colSpan={11} className="py-12 text-center text-slate-400">
                    <div className="flex justify-center items-center gap-2">
                      <Loader2 className="w-5 h-5 animate-spin text-indigo-500" />
                      <span>Đang tải danh sách dự báo rủi ro...</span>
                    </div>
                  </td>
                </tr>
              ) : predictionItems.length > 0 ? (
                predictionItems.map((item, idx) => {
                  const riskColor = EWS_RISK_COLORS[item.risk_level] || "#94a3b8";
                  return (
                    <tr
                      key={idx}
                      onClick={() => setSelectedItem(item)}
                      title="Bấm để xem chi tiết 24 chỉ số EWS"
                      className="cursor-pointer hover:bg-indigo-50/60 dark:hover:bg-slate-800/80 transition-colors"
                    >
                      {/* Học sinh */}
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900 dark:text-slate-100">
                          {item.student_name || item.student_code}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono">{item.student_code}</div>
                        {item.join_date && item.join_date > semesterStartStr(schoolYearId, semesterIndex) && (
                          <div className="text-[10px] text-amber-600 dark:text-amber-400 flex items-center gap-1 mt-0.5">
                            <span>🏫</span>
                            <span>Chuyển tới từ {fmtDate(item.join_date)}</span>
                          </div>
                        )}
                      </td>

                      {/* Khối / Lớp */}
                      <td className="py-3 px-4">
                        <div className="text-slate-800 dark:text-slate-200 font-medium">{item.class_name || "—"}</div>
                        <div className="text-[11px] text-slate-400">{item.grade_name || "—"}</div>
                      </td>

                      {/* Môn Học */}
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-800 dark:text-slate-200">
                          {item.subject_name || item.subject_code}
                        </div>
                        {item.subject_category && (
                          <span className="inline-block mt-0.5 px-1.5 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-500 font-mono">
                            {item.subject_category}
                          </span>
                        )}
                      </td>

                      {/* Điểm Rủi Ro (0-100) */}
                      <td className="py-3 px-4 text-center">
                        <div className="inline-flex items-center gap-1.5 font-bold text-sm" style={{ color: riskColor }}>
                          {item.risk_score.toFixed(1)}
                        </div>
                        <div className="w-16 bg-slate-100 dark:bg-slate-800 rounded-full h-1.5 mx-auto mt-1 overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{ width: `${Math.min(item.risk_score, 100)}%`, backgroundColor: riskColor }}
                          />
                        </div>
                      </td>

                      {/* Mức Rủi Ro Badge */}
                      <td className="py-3 px-4 text-center">
                        <span
                          className="px-2.5 py-1 rounded-full text-[11px] font-bold text-white shadow-sm inline-block"
                          style={{ backgroundColor: riskColor }}
                        >
                          {item.risk_level}
                        </span>
                      </td>

                      {/* Risk Factors Badges */}
                      <td className="py-3 px-4">
                        <div className="flex flex-wrap gap-1">
                          {item.risk_factors && item.risk_factors.length > 0 ? (
                            item.risk_factors.map((f, fIdx) => {
                              const metaF = FACTOR_VI[f] || { label: f, icon: "⚠️", color: "bg-slate-100 text-slate-600" };
                              return (
                                <span
                                  key={fIdx}
                                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-medium border ${metaF.color}`}
                                >
                                  <span>{metaF.icon}</span>
                                  <span>{metaF.label}</span>
                                </span>
                              );
                            })
                          ) : (
                            <span className="text-[11px] text-slate-400 italic">Bình thường</span>
                          )}
                        </div>
                      </td>

                      {/* Điểm thi gần nhất */}
                      <td className="py-3 px-4 text-right font-medium text-slate-800 dark:text-slate-200">
                        {item.last_score !== null ? item.last_score.toFixed(1) : "—"}
                      </td>

                      {/* ĐTB sớm */}
                      <td className="py-3 px-4 text-right text-slate-600 dark:text-slate-400">
                        {item.weighted_early_avg !== null ? item.weighted_early_avg.toFixed(1) : "—"}
                      </td>

                      {/* Slope */}
                      <td className="py-3 px-4 text-right">
                        {item.score_slope !== null ? (
                          <span
                            className={`font-semibold ${
                              item.score_slope < 0
                                ? "text-rose-500"
                                : item.score_slope > 0
                                ? "text-emerald-500"
                                : "text-slate-400"
                            }`}
                          >
                            {item.score_slope > 0 ? `+${item.score_slope.toFixed(2)}` : item.score_slope.toFixed(2)}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>

                      {/* ĐTB LMS */}
                      <td className="py-3 px-4 text-right text-slate-600 dark:text-slate-400">
                        {item.lms_avg_score !== null ? item.lms_avg_score.toFixed(1) : "—"}
                      </td>

                      {/* Tỷ lệ nộp LMS */}
                      <td className="py-3 px-4 text-right text-slate-600 dark:text-slate-400">
                        {item.lms_submission_rate !== null ? `${(item.lms_submission_rate * 100).toFixed(1)}%` : "—"}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={11} className="py-12 text-center text-slate-400">
                    Không tìm thấy dữ liệu dự báo rủi ro phù hợp với bộ lọc.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* PAGINATION FOOTER */}
        <div className="flex items-center justify-between pt-4 border-t border-slate-100 dark:border-slate-800">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Hiển thị {predictionItems.length} trên tổng số {predictions?.total.toLocaleString() || 0} bản ghi
          </span>

          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1 || loadingPreds}
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              className="p-2 border border-slate-200 dark:border-slate-800 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-40 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <span className="text-xs font-semibold px-3 py-1 bg-slate-100 dark:bg-slate-800 rounded-lg text-slate-700 dark:text-slate-300">
              {page} / {totalPages || 1}
            </span>

            <button
              disabled={page >= totalPages || loadingPreds}
              onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
              className="p-2 border border-slate-200 dark:border-slate-800 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-40 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* DETAIL DRAWER FOR SELECTED ROW */}
      <EwsDetailDrawer
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
        schoolYearId={schoolYearId}
        semesterIndex={semesterIndex}
      />
    </div>
  );
}
