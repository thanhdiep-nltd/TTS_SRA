"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, Award, BarChart3, ChevronDown, ChevronUp, GraduationCap, Info, Layers,
  LayoutGrid, LineChart as LineIcon, Loader2, ShieldAlert, ShieldCheck, TrendingUp, UserX, Users,
} from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from "recharts";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { LoadingState } from "@/components/Loading";
import SearchableSelect from "@/components/SearchableSelect";
import ExamAnalysisDrawer from "@/components/dashboard/ExamAnalysisDrawer";
import { useTheme } from "@/lib/theme";
import { CONDUCT_LABELS, SCORE_CATEGORY_LABELS } from "@/lib/types";
import type {
  ContentAdjustedRankRow, DashboardOverview, ExamValidityRow, ExecutiveSummary,
  Grade, ScoreCategory, SchoolValidityOverview, SemesterOption, StudentFairnessRow, Subject,
  SubjectMatrix, WarningData, YoYResponse,
  AcademicDivergenceRow, GradeInflationRow, LearningMomentumRow, StudentArchetypeRow,
} from "@/lib/types";

type TabKey = "overview" | "drilldown" | "trend" | "warning" | "validity" | "edm";

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: "overview", label: "Tổng quan", icon: LayoutGrid },
  { key: "drilldown", label: "Phân tích chuyên môn", icon: BarChart3 },
  { key: "trend", label: "Xu hướng & Tiến bộ", icon: LineIcon },
  { key: "warning", label: "Cảnh báo sớm", icon: ShieldAlert },
  { key: "validity", label: "Tin cậy điểm số", icon: ShieldCheck },
  { key: "edm", label: "Phân Tích Chuyên Sâu EDM", icon: Layers },
];

const HL_COLORS = { gioi: "#10b981", kha: "#3b82f6", trung_binh: "#f59e0b", yeu: "#ef4444" };
const RISK_COLORS = { Low: "#10b981", Medium: "#f59e0b", High: "#f97316", Critical: "#ef4444" };
const CLUSTER_COLORS = ["#0d4d8b", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4", "#ec4899", "#64748b"];
const FLAG_COLORS: Record<string, string> = {
  INFLATION_OR_LEAK: "#ef4444",
  LEARNING_GAP: "#f59e0b",
  VALID: "#10b981",
  NO_CONTENT: "#94a3b8",
  LOW_SAMPLE: "#94a3b8",
};
const FLAG_VI: Record<string, string> = {
  INFLATION_OR_LEAK: "Lạm phát/nghi lộ đề",
  LEARNING_GAP: "Lỗ hổng học tập",
  VALID: "Đáng tin",
  NO_CONTENT: "Chưa phân tích đề",
  LOW_SAMPLE: "Mẫu quá nhỏ",
};
const VALIDITY_OVERVIEW_ROLES = ["ADMIN", "PRINCIPAL"];

// Cảnh báo công bằng đánh giá — chỉ ADMIN/PRINCIPAL (nhạy cảm hơn TEVI, nhắm vào HS/GV cụ thể).
const FAIRNESS_ROLES = ["ADMIN", "PRINCIPAL"];
const FAIRNESS_FLAG_COLORS: Record<string, string> = {
  SUSPECT_FAVORITISM: "#f97316",
  SUSPECT_SUPPRESSION: "#8b5cf6",
};
const FAIRNESS_FLAG_VI: Record<string, string> = {
  SUSPECT_FAVORITISM: "Nghi tủ đề / ưu ái TX",
  SUSPECT_SUPPRESSION: "Nghi bị chèn ép TX",
};

function pct(n: number, total: number): string {
  return total > 0 ? `${Math.round((n / total) * 100)}%` : "—";
}

// Màu nền ô heatmap theo điểm (đỏ→vàng→xanh).
function heatColor(v: number | undefined): string {
  if (v == null) return "transparent";
  if (v >= 8) return "rgba(16,185,129,0.85)";
  if (v >= 6.5) return "rgba(132,204,22,0.7)";
  if (v >= 5) return "rgba(245,158,11,0.7)";
  if (v >= 3.5) return "rgba(249,115,22,0.75)";
  return "rgba(239,68,68,0.85)";
}

function Card({ title, desc, icon, children }: {
  title: string; desc?: string; icon?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm space-y-4">
      <div>
        <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
          {icon}{title}
        </h3>
        {desc && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{desc}</p>}
      </div>
      {children}
    </div>
  );
}

function Kpi({ label, value, sub, tone, soon }: {
  label: string; value: string; sub?: string; tone: string; soon?: boolean;
}) {
  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm relative">
      {soon && (
        <span className="absolute top-3 right-3 text-[10px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-400">
          Sắp có
        </span>
      )}
      <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{label}</p>
      <h3 className={`text-2xl font-bold mt-1 ${soon ? "text-slate-300 dark:text-slate-600" : "text-slate-900 dark:text-white"}`}>{value}</h3>
      {sub && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{sub}</p>}
      <div className={`mt-3 h-1 rounded-full ${tone}`} />
    </div>
  );
}

function InfoTooltip({ content }: { content: React.ReactNode }) {
  return (
    <span className="group relative inline-block ml-1.5 align-middle select-none">
      <Info className="w-4 h-4 text-slate-400 dark:text-slate-500 hover:text-brand-500 dark:hover:text-brand-400 cursor-help transition-colors duration-200" />
      <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-80 scale-95 opacity-0 group-hover:scale-100 group-hover:opacity-100 transition-all duration-200 bg-slate-900/95 dark:bg-slate-950/95 backdrop-blur-md text-white text-xs rounded-xl p-3 shadow-lg z-50 border border-slate-700 dark:border-slate-800 leading-relaxed font-normal normal-case">
        {content}
        <span className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-slate-900/95 dark:border-t-slate-950/95"></span>
      </span>
    </span>
  );
}

export default function DashboardV2Page() {
  const { theme } = useTheme();
  const { user } = useAuth();
  const [tab, setTab] = useState<TabKey>("overview");

  const [semesters, setSemesters] = useState<SemesterOption[]>([]);
  const [semesterId, setSemesterId] = useState<string>("");

  const [exec, setExec] = useState<ExecutiveSummary | null>(null);
  const [matrix, setMatrix] = useState<SubjectMatrix | null>(null);
  const [warning, setWarning] = useState<WarningData | null>(null);
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [yoy, setYoy] = useState<YoYResponse | null>(null);

  const [loading, setLoading] = useState(true);
  const [loadingMatrix, setLoadingMatrix] = useState(false);
  const [loadingWarning, setLoadingWarning] = useState(false);
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Tab "Tin cậy điểm số" (TEVI).
  const canSeeValidityOverview = !!user && VALIDITY_OVERVIEW_ROLES.includes(user.role);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [grades, setGrades] = useState<Grade[]>([]);
  const [subjectId, setSubjectId] = useState<string>("");
  const [gradeId, setGradeId] = useState<string>("");
  const [scoreCategory, setScoreCategory] = useState<ScoreCategory>("FINAL");
  const [validityOverview, setValidityOverview] = useState<SchoolValidityOverview | null>(null);
  const [validityRows, setValidityRows] = useState<ExamValidityRow[]>([]);
  const [analysisPaperId, setAnalysisPaperId] = useState<string | null>(null);
  const [ranking, setRanking] = useState<ContentAdjustedRankRow[]>([]);
  const [validityLoading, setValidityLoading] = useState(false);
  // Mặc định (chưa chọn Môn): tự quét toàn trường, chỉ hiện dòng có cờ bất thường — tab phụ để
  // lọc theo loại cờ. Chọn Môn (*) tay -> xem đầy đủ (kể cả VALID) như trước.
  const [validityFlagTab, setValidityFlagTab] = useState<string>("ALL");
  const [showValidityInfo, setShowValidityInfo] = useState(false);
  const canSeeFairness = !!user && FAIRNESS_ROLES.includes(user.role);
  const [fairnessRows, setFairnessRows] = useState<StudentFairnessRow[]>([]);

  // Tab "Phân tích chuyên sâu EDM"
  const [edmSubjectId, setEdmSubjectId] = useState<string>("");
  const [divergence, setDivergence] = useState<AcademicDivergenceRow[]>([]);
  const [inflation, setInflation] = useState<GradeInflationRow[]>([]);
  const [momentum, setMomentum] = useState<LearningMomentumRow[]>([]);
  const [archetypes, setArchetypes] = useState<StudentArchetypeRow[]>([]);
  const [loadingEDM, setLoadingEDM] = useState(false);

  const grid = theme === "dark" ? "#1e293b" : "#e2e8f0";
  const axis = theme === "dark" ? "#94a3b8" : "#64748b";
  const tooltipStyle = {
    backgroundColor: theme === "dark" ? "#0f172a" : "#ffffff",
    border: `1px solid ${grid}`, borderRadius: "12px",
    color: theme === "dark" ? "#f8fafc" : "#0f172a", fontSize: 12,
  };

  // Tải danh sách học kỳ + YoY (1 lần).
  useEffect(() => {
    api.get<SemesterOption[]>("/analytics/semesters")
      .then((list) => {
        setSemesters(list);
        const cur = list.find((s) => s.is_current) || list[0];
        if (cur) setSemesterId(cur.id);
        else setLoading(false);
      })
      .catch((e) => { setError(e instanceof ApiError ? e.message : "Không tải được học kỳ"); setLoading(false); });
    api.get<YoYResponse>("/analytics/v2/yoy").then(setYoy).catch(() => {});
    api.get<Subject[]>("/subjects?limit=200").then(setSubjects).catch(() => {});
    api.get<Grade[]>("/grades?limit=200").then(setGrades).catch(() => {});
  }, []);

  // Tải dữ liệu tab "Tin cậy điểm số" — chỉ khi tab đang mở, để tránh gọi API thừa.
  useEffect(() => {
    if (tab !== "validity" || !semesterId) return;
    setValidityLoading(true);
    const calls: [Promise<SchoolValidityOverview | null>, Promise<ExamValidityRow[]>, Promise<ContentAdjustedRankRow[]>] = [
      canSeeValidityOverview
        ? api.get<SchoolValidityOverview>(`/analytics/exam-validity/overview?semester_id=${semesterId}`)
        : Promise.resolve(null),
      // Chưa chọn Môn (*) tay -> tự quét TOÀN TRƯỜNG, chỉ lấy dòng có cờ bất thường (flagged_only).
      // Đã chọn Môn -> xem đầy đủ (kể cả VALID) đúng bộ lọc, như hành vi cũ.
      subjectId
        ? api.get<ExamValidityRow[]>(
            `/analytics/exam-validity?semester_id=${semesterId}&subject_id=${subjectId}&score_category=${scoreCategory}${gradeId ? `&grade_id=${gradeId}` : ""}`,
          )
        : api.get<ExamValidityRow[]>(`/analytics/exam-validity?semester_id=${semesterId}&flagged_only=true`),
      canSeeValidityOverview && subjectId && gradeId
        ? api.get<ContentAdjustedRankRow[]>(
            `/analytics/content-adjusted-ranking?semester_id=${semesterId}&subject_id=${subjectId}&grade_id=${gradeId}&score_category=${scoreCategory}`,
          )
        : Promise.resolve([]),
    ];
    Promise.all(calls)
      .then(([o, rows, rank]) => { setValidityOverview(o); setValidityRows(rows); setRanking(rank); })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được dữ liệu tin cậy điểm số"))
      .finally(() => setValidityLoading(false));
  }, [tab, semesterId, subjectId, gradeId, scoreCategory, canSeeValidityOverview]);

  // Đổi giữa chế độ tự quét (mặc định) và lọc tay -> bỏ filter cờ phụ đang chọn để tránh nhầm.
  useEffect(() => { setValidityFlagTab("ALL"); }, [subjectId]);

  const [fairnessLoading, setFairnessLoading] = useState(false);
  useEffect(() => {
    if (tab !== "warning" || !semesterId || !canSeeFairness) return;
    setFairnessLoading(true);
    api.get<StudentFairnessRow[]>(`/analytics/student-fairness?semester_id=${semesterId}`)
      .then(setFairnessRows)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được cảnh báo công bằng đánh giá"))
      .finally(() => setFairnessLoading(false));
  }, [tab, semesterId, canSeeFairness]);

  // Khởi tạo edmSubjectId khi có danh sách môn học (ưu tiên môn Toán)
  useEffect(() => {
    if (subjects.length > 0 && !edmSubjectId) {
      const mathSubject = subjects.find(s => s.name === "Toán" || s.name === "Toán học");
      if (mathSubject) {
        setEdmSubjectId(mathSubject.id);
      } else {
        setEdmSubjectId(subjects[0].id);
      }
    }
  }, [subjects, edmSubjectId]);

  // Tải dữ liệu EDM khi mở tab EDM
  useEffect(() => {
    if (tab !== "edm" || !semesterId || !edmSubjectId) return;
    setLoadingEDM(true);
    setError(null);
    const params = `?semester_id=${semesterId}&subject_id=${edmSubjectId}`;
    Promise.all([
      api.get<AcademicDivergenceRow[]>(`/analytics/academic-divergence${params}`),
      api.get<GradeInflationRow[]>(`/analytics/grade-inflation${params}`),
      api.get<LearningMomentumRow[]>(`/analytics/momentum${params}`),
      api.get<StudentArchetypeRow[]>(`/analytics/student-archetypes?semester_id=${semesterId}`)
    ])
      .then(([divRes, infRes, momRes, arcRes]) => {
        setDivergence(divRes);
        setInflation(infRes);
        setMomentum(momRes);
        setArchetypes(arcRes);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Không tải được dữ liệu phân tích chuyên sâu EDM");
      })
      .finally(() => setLoadingEDM(false));
  }, [tab, semesterId, edmSubjectId]);

  // Reset dữ liệu riêng từng tab khi đổi học kỳ, để các tab lazy tải lại đúng học kỳ mới.
  useEffect(() => {
    setMatrix(null);
    setWarning(null);
    setOverview(null);
  }, [semesterId]);

  // Tab "Tổng quan" (mặc định) — tải ngay vì đây là tab hiển thị đầu tiên + header dùng exec.semester_name.
  useEffect(() => {
    if (!semesterId) return;
    setLoading(true);
    setError(null);
    api.get<ExecutiveSummary>(`/analytics/v2/executive?semester_id=${semesterId}`)
      .then(setExec)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được dữ liệu phân tích"))
      .finally(() => setLoading(false));
  }, [semesterId]);

  // Tab "Phân tích chuyên môn" — chỉ tải khi mở tab, tránh gọi API thừa lúc vào trang.
  useEffect(() => {
    if (tab !== "drilldown" || !semesterId || matrix) return;
    setLoadingMatrix(true);
    api.get<SubjectMatrix>(`/analytics/v2/subject-matrix?semester_id=${semesterId}`)
      .then(setMatrix)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được dữ liệu phân tích chuyên môn"))
      .finally(() => setLoadingMatrix(false));
  }, [tab, semesterId, matrix]);

  // Tab "Xu hướng & Tiến bộ" — chỉ tải khi mở tab.
  useEffect(() => {
    if (tab !== "trend" || !semesterId || overview) return;
    setLoadingOverview(true);
    api.get<DashboardOverview>(`/analytics/overview?semester_id=${semesterId}`)
      .then(setOverview)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được dữ liệu xu hướng"))
      .finally(() => setLoadingOverview(false));
  }, [tab, semesterId, overview]);

  // Tab "Cảnh báo sớm" — chỉ tải khi mở tab.
  useEffect(() => {
    if (tab !== "warning" || !semesterId || warning) return;
    setLoadingWarning(true);
    api.get<WarningData>(`/analytics/v2/warnings?semester_id=${semesterId}`)
      .then(setWarning)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được dữ liệu cảnh báo sớm"))
      .finally(() => setLoadingWarning(false));
  }, [tab, semesterId, warning]);

  const kpi = exec?.kpi;
  const total = kpi?.total_graded ?? 0;

  const donutData = useMemo(() => kpi ? [
    { name: "Giỏi", value: kpi.gioi, fill: HL_COLORS.gioi },
    { name: "Khá", value: kpi.kha, fill: HL_COLORS.kha },
    { name: "Trung bình", value: kpi.trung_binh, fill: HL_COLORS.trung_binh },
    { name: "Yếu", value: kpi.yeu, fill: HL_COLORS.yeu },
  ] : [], [kpi]);

  // Tính toán dữ liệu radar cho biểu đồ phân cụm EDM
  const radarData = useMemo(() => {
    const totalArchetypes = archetypes.reduce(
      (acc, cur) => {
        acc.consistent += cur.consistent;
        acc.procrastinator += cur.procrastinator;
        acc.high_effort += cur.high_effort;
        acc.high_risk += cur.high_risk;
        return acc;
      },
      { consistent: 0, procrastinator: 0, high_effort: 0, high_risk: 0 }
    );
    return [
      { name: "Chăm chỉ ổn định", value: totalArchetypes.consistent, fullMark: 100 },
      { name: "Trì hoãn bứt phá", value: totalArchetypes.procrastinator, fullMark: 100 },
      { name: "Cần cù học vẹt", value: totalArchetypes.high_effort, fullMark: 100 },
      { name: "Nguy cơ học thuật", value: totalArchetypes.high_risk, fullMark: 100 },
    ];
  }, [archetypes]);

  if (loading && !exec) {
    return <div className="flex h-screen items-center justify-center"><LoadingState message="Đang tải Dashboard…" /></div>;
  }

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
            Tổng quan → Phân tích → Xu hướng → Cảnh báo. {exec && `${exec.semester_name} · ${exec.academic_year}`}
          </p>
        </div>
        <div className="flex items-center gap-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-3 py-1.5 rounded-xl shadow-sm">
          <Layers className="w-4 h-4 text-brand-500" />
          <select
            value={semesterId}
            onChange={(e) => setSemesterId(e.target.value)}
            className="bg-transparent text-sm text-slate-800 dark:text-slate-200 outline-none cursor-pointer font-medium"
          >
            {semesters.map((s) => (
              <option key={s.id} value={s.id} className="dark:bg-slate-950">{s.name} ({s.academic_year})</option>
            ))}
          </select>
          {loading && <Loader2 className="w-4 h-4 text-brand-500 animate-spin" />}
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
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition ${active
                ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30"
                : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"}`}
            >
              <Icon className="w-4 h-4" />{t.label}
            </button>
          );
        })}
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm flex items-center gap-2">
          <AlertTriangle className="w-5 h-5" />{error}
        </div>
      )}

      {/* ===== TAB 1: EXECUTIVE OVERVIEW ===== */}
      {tab === "overview" && kpi && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Kpi label="ĐTB toàn trường" value={kpi.avg_gpa != null ? `${kpi.avg_gpa} / 10` : "—"}
              sub={`${total} HS có xếp loại`} tone="bg-brand-500" />
            <Kpi label="Tỷ lệ Giỏi" value={pct(kpi.gioi, total)} sub={`${kpi.gioi} học sinh`} tone="bg-emerald-500" />
            <Kpi label="Tỷ lệ Khá" value={pct(kpi.kha, total)} sub={`${kpi.kha} học sinh`} tone="bg-blue-500" />
            <Kpi label="Tỷ lệ Trung bình" value={pct(kpi.trung_binh, total)} sub={`${kpi.trung_binh} học sinh`} tone="bg-amber-500" />
            <Kpi label="Tỷ lệ Yếu" value={pct(kpi.yeu, total)} sub={`${kpi.yeu} học sinh`} tone="bg-rose-500" />
            <Kpi label="HS bị cảnh báo" value={String(kpi.at_risk_count)} sub="ĐTB < 5.0" tone="bg-rose-500" />
            <Kpi label="Hạnh kiểm Tốt+Khá"
              value={kpi.conduct_good_ratio != null ? `${Math.round(kpi.conduct_good_ratio * 100)}%` : "—"}
              sub={kpi.conduct_good_ratio != null ? "trên tổng đánh giá" : "chưa nhập"} tone="bg-indigo-500" />
            <Kpi label="Tỷ lệ chuyên cần" value="—" sub="chưa có nguồn dữ liệu" tone="bg-slate-300" soon />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Cơ cấu học lực toàn trường" desc="Tỷ lệ Giỏi / Khá / TB / Yếu (theo ĐTB học kỳ)"
              icon={<GraduationCap className="w-5 h-5 text-brand-500" />}>
              <div className="h-72">
                {total > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={donutData} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="85%" paddingAngle={2}>
                        {donutData.map((d) => <Cell key={d.name} fill={d.fill} />)}
                      </Pie>
                      <Tooltip contentStyle={tooltipStyle} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : <div className="flex h-full items-center justify-center text-slate-400">Không có dữ liệu</div>}
              </div>
            </Card>

            <Card title="So sánh cơ cấu theo cấp học" desc="Phân bố học lực giữa THCS / THPT (100% Stacked)"
              icon={<Users className="w-5 h-5 text-indigo-500" />}>
              <div className="h-72">
                {exec.level_distribution.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={exec.level_distribution} stackOffset="expand" margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={grid} />
                      <XAxis dataKey="level" stroke={axis} fontSize={11} />
                      <YAxis stroke={axis} fontSize={11} domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Bar dataKey="gioi" name="Giỏi" stackId="a" fill={HL_COLORS.gioi} />
                      <Bar dataKey="kha" name="Khá" stackId="a" fill={HL_COLORS.kha} />
                      <Bar dataKey="trung_binh" name="TB" stackId="a" fill={HL_COLORS.trung_binh} />
                      <Bar dataKey="yeu" name="Yếu" stackId="a" fill={HL_COLORS.yeu} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : <div className="flex h-full items-center justify-center text-slate-400">Không có dữ liệu</div>}
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Top 5 lớp xuất sắc" desc="Xếp theo ĐTB trung bình của lớp"
              icon={<Award className="w-5 h-5 text-emerald-500" />}>
              <RankBars rows={exec.class_ranking.slice(0, 5)} color="#10b981" axis={axis} grid={grid} tooltipStyle={tooltipStyle} />
            </Card>
            <Card title="5 lớp cần cải thiện" desc="ĐTB thấp nhất trường — ưu tiên can thiệp"
              icon={<TrendingUp className="w-5 h-5 text-rose-500" />}>
              <RankBars rows={[...exec.class_ranking].slice(-5).reverse()} color="#ef4444" axis={axis} grid={grid} tooltipStyle={tooltipStyle} />
            </Card>
          </div>
        </div>
      )}

      {/* ===== TAB 2: DRILL-DOWN ===== */}
      {tab === "drilldown" && loadingMatrix && !matrix && (
        <div className="py-24"><LoadingState message="Đang tải phân tích chuyên môn…" /></div>
      )}
      {tab === "drilldown" && matrix && (
        <div className="space-y-6">
          <Card title="ĐTB các môn theo khối" desc="Clustered bar — trục X: môn học, trục Y: điểm TB, mỗi cột là một khối"
            icon={<BarChart3 className="w-5 h-5 text-brand-500" />}>
            <div className="h-96">
              {matrix.grade_cells.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={matrix.grade_cells} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={grid} />
                    <XAxis dataKey="subject" stroke={axis} fontSize={10} interval={0} angle={-20} textAnchor="end" height={60} />
                    <YAxis domain={[0, 10]} stroke={axis} fontSize={11} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {matrix.grades.map((g, i) => (
                      <Bar key={g} dataKey={g} fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]} radius={[3, 3, 0, 0]} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              ) : <div className="flex h-full items-center justify-center text-slate-400">Không có dữ liệu</div>}
            </div>
          </Card>

          <Card title="Heatmap điểm Lớp × Môn" desc="Đỏ = thấp, Vàng = trung bình, Xanh = cao. Phát hiện môn yếu của từng lớp.">
            {matrix.heatmap_cells.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="text-xs border-collapse">
                  <thead>
                    <tr>
                      <th className="sticky left-0 bg-white dark:bg-slate-900 p-2 text-left text-slate-500 font-semibold">Lớp \ Môn</th>
                      {matrix.subjects.map((s) => (
                        <th key={s} className="p-2 text-slate-500 dark:text-slate-400 font-semibold whitespace-nowrap min-w-[64px]">{s}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {matrix.heatmap_cells.map((row) => (
                      <tr key={row.class_name as string}>
                        <td className="sticky left-0 bg-white dark:bg-slate-900 p-2 font-semibold text-slate-700 dark:text-slate-300 whitespace-nowrap">{row.class_name}</td>
                        {matrix.subjects.map((s) => {
                          const v = row[s] as number | undefined;
                          return (
                            <td key={s} className="p-2 text-center font-medium text-slate-800 dark:text-slate-900"
                              style={{ backgroundColor: heatColor(v) }}>
                              {v != null ? Number(v).toFixed(1) : "—"}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="py-8 text-center text-slate-400">Không có dữ liệu</div>}
          </Card>

          <Card title="Xếp hạng môn học toàn trường" desc="ĐTB trung bình của mỗi môn — môn cuối bảng cần rà soát chất lượng dạy/học.">
            <RankTable
              rows={matrix.subject_ranking.map((r, i) => ({
                rank: i + 1, name: r.class_name, sub: "", gpa: r.gpa,
              }))}
              nameLabel="Môn học"
            />
          </Card>
        </div>
      )}

      {/* ===== TAB 3: TREND & PROGRESS ===== */}
      {tab === "trend" && loadingOverview && !overview && (
        <div className="py-24"><LoadingState message="Đang tải xu hướng & tiến bộ…" /></div>
      )}
      {tab === "trend" && overview && (
        <div className="space-y-6">
          <Card title="ĐTB theo các đợt đánh giá" desc="Xu hướng điểm trung bình toàn trường qua từng đầu điểm (TX1 → Cuối kỳ)"
            icon={<LineIcon className="w-5 h-5 text-brand-500" />}>
            <div className="h-80">
              {overview.gpa_trend.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={overview.gpa_trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={grid} />
                    <XAxis dataKey="name" stroke={axis} fontSize={11} />
                    <YAxis domain={[0, 10]} stroke={axis} fontSize={11} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Line type="monotone" dataKey="gpa" name="ĐTB trường" stroke="#0d4d8b" strokeWidth={3} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              ) : <div className="flex h-full items-center justify-center text-slate-400">Không có dữ liệu</div>}
            </div>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Phân bố học lực theo khối" desc="Cơ cấu Giỏi/Khá/TB/Yếu của từng khối (100% Stacked)">
              <div className="h-80">
                {overview.grade_distribution.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={overview.grade_distribution} stackOffset="expand" margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={grid} />
                      <XAxis dataKey="name" stroke={axis} fontSize={11} />
                      <YAxis domain={[0, 1]} stroke={axis} fontSize={11} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Bar dataKey="gioi" name="Giỏi" stackId="a" fill={HL_COLORS.gioi} />
                      <Bar dataKey="kha" name="Khá" stackId="a" fill={HL_COLORS.kha} />
                      <Bar dataKey="trung_binh" name="TB" stackId="a" fill={HL_COLORS.trung_binh} />
                      <Bar dataKey="yeu" name="Yếu" stackId="a" fill={HL_COLORS.yeu} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : <div className="flex h-full items-center justify-center text-slate-400">Không có dữ liệu</div>}
              </div>
            </Card>

            <Card title="So sánh giữa các năm học (YoY)" desc="ĐTB cuối kỳ trung bình theo từng năm học">
              <div className="h-80">
                {yoy && yoy.years.length > 1 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={yoy.years} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={grid} />
                      <XAxis dataKey="academic_year" stroke={axis} fontSize={11} />
                      <YAxis domain={[0, 10]} stroke={axis} fontSize={11} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Bar dataKey="avg_gpa" name="ĐTB cuối kỳ" fill="#0d4d8b" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full flex-col items-center justify-center text-slate-400 gap-2 text-center px-4">
                    <LineIcon className="w-8 h-8 opacity-40" />
                    <p className="text-sm">Cần dữ liệu ≥ 2 năm học để so sánh. Hiện chỉ có {yoy?.years.length ?? 0} năm.</p>
                  </div>
                )}
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* ===== TAB 4: EARLY WARNING ===== */}
      {tab === "warning" && loadingWarning && !warning && (
        <div className="py-24"><LoadingState message="Đang tải cảnh báo sớm…" /></div>
      )}
      {tab === "warning" && warning && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Ma trận rủi ro học sinh" desc="Phân loại theo ĐTB + hạnh kiểm"
              icon={<ShieldAlert className="w-5 h-5 text-rose-500" />}>
              <div className="grid grid-cols-2 gap-3">
                {warning.risk_matrix.map((m) => (
                  <div key={m.level} className="rounded-xl p-4 text-white" style={{ backgroundColor: RISK_COLORS[m.level] }}>
                    <p className="text-3xl font-bold">{m.count}</p>
                    <p className="text-sm font-medium opacity-90">{RISK_VI[m.level]}</p>
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-2">
                Critical: ĐTB&lt;3.5 hoặc hạnh kiểm Yếu · High: ĐTB&lt;5.0 hoặc HK Trung bình · Medium: ĐTB&lt;6.5 · Low: còn lại.
              </p>
            </Card>

            <Card title="Tương quan Quá trình × Cuối kỳ" desc="Trục X: ĐTB quá trình (Miệng+TX+GK), Trục Y: điểm cuối kỳ. Góc dưới-trái = nguy cơ.">
              <div className="h-72">
                {warning.scatter.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={grid} />
                      <XAxis type="number" dataKey="process_gpa" name="Quá trình" domain={[0, 10]} stroke={axis} fontSize={11} />
                      <YAxis type="number" dataKey="final_score" name="Cuối kỳ" domain={[0, 10]} stroke={axis} fontSize={11} />
                      <ZAxis range={[40, 40]} />
                      <Tooltip contentStyle={tooltipStyle} cursor={{ strokeDasharray: "3 3" }} />
                      <Scatter data={warning.scatter}>
                        {warning.scatter.map((p, i) => <Cell key={i} fill={RISK_COLORS[p.risk_level]} fillOpacity={0.6} />)}
                      </Scatter>
                    </ScatterChart>
                  </ResponsiveContainer>
                ) : <div className="flex h-full items-center justify-center text-slate-400">Không có dữ liệu</div>}
              </div>
            </Card>
          </div>

          {canSeeFairness && (
            <Card
              title={`Cảnh báo công bằng đánh giá (${fairnessRows.length})`}
              desc="Tự động quét TOÀN TRƯỜNG (mọi môn/khối) — đối chiếu điểm Thường xuyên (TX, GV bộ môn ra đề) với Giữa kỳ/Cuối kỳ (đề chung toàn khối) theo độ khó nội dung (CDI). Đây là TÍN HIỆU RÀ SOÁT, KHÔNG phải kết luận tiêu cực đã xác nhận."
              icon={<UserX className="w-5 h-5 text-rose-500" />}
            >
              {fairnessLoading ? (
                <p className="py-6 text-center text-slate-400 text-sm">Đang quét toàn trường…</p>
              ) : fairnessRows.length > 0 ? (
                <div className="space-y-3 max-h-[34rem] overflow-y-auto">
                  {fairnessRows.map((r) => (
                    <div key={`${r.student_id}-${r.subject_id}`}
                      className="rounded-xl border border-slate-200 dark:border-slate-800 p-4 space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <span className="font-semibold text-slate-800 dark:text-slate-200">{r.full_name}</span>
                          <span className="text-xs text-slate-400 ml-2">{r.student_code} · Lớp {r.class_name} · Môn {r.subject_name}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded-full text-xs font-semibold"
                            style={{ backgroundColor: `${FAIRNESS_FLAG_COLORS[r.flag] ?? "#94a3b8"}20`, color: FAIRNESS_FLAG_COLORS[r.flag] ?? "#94a3b8" }}>
                            {FAIRNESS_FLAG_VI[r.flag] ?? r.flag}
                          </span>
                          <span className="text-xs text-slate-400">Độ tin cậy: {r.confidence === "HIGH" ? "Cao" : "Thấp"}</span>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div className="rounded-lg bg-slate-50 dark:bg-slate-800/60 px-3 py-2">
                          <p className="text-[11px] text-slate-400 uppercase tracking-wide">TX (CDI)</p>
                          <p className="font-semibold text-slate-800 dark:text-slate-200">
                            {r.tx_avg != null ? r.tx_avg.toFixed(2) : "—"}
                            <span className="text-slate-400 font-normal"> ({r.tx_cdi != null ? r.tx_cdi.toFixed(2) : "chưa rõ"})</span>
                          </p>
                        </div>
                        <div className="rounded-lg bg-slate-50 dark:bg-slate-800/60 px-3 py-2">
                          <p className="text-[11px] text-slate-400 uppercase tracking-wide">GK/CK (CDI)</p>
                          <p className="font-semibold text-slate-800 dark:text-slate-200">
                            {r.periodic_avg != null ? r.periodic_avg.toFixed(2) : "—"}
                            <span className="text-slate-400 font-normal"> ({r.periodic_cdi != null ? r.periodic_cdi.toFixed(2) : "chưa rõ"})</span>
                          </p>
                        </div>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400 italic">
                        <span className="font-semibold not-italic">Bằng chứng:</span> {r.evidence}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="py-6 text-center text-slate-400 text-sm">Không phát hiện trường hợp bất thường nào trong học kỳ này 🎉</p>
              )}
            </Card>
          )}

          <Card title={`Học sinh nguy cơ cao (${warning.risk_students.length})`} desc="ĐTB < 6.5 — sắp theo điểm tăng dần. Cần can thiệp sớm."
            icon={<AlertTriangle className="w-5 h-5 text-rose-500" />}>
            <StudentTable
              head={["Mã HS", "Họ tên", "Lớp", "ĐTB", "Hạnh kiểm", "Môn yếu nhất", "Mức rủi ro"]}
              rows={warning.risk_students.map((s) => [
                s.student_code, s.full_name, s.class_name, s.gpa.toFixed(2),
                s.conduct ? CONDUCT_LABELS[s.conduct] : "—",
                s.weakest_subject ? `${s.weakest_subject} (${s.weakest_score?.toFixed(1)})` : "—",
                <span key="r" className="px-2 py-0.5 rounded-full text-white text-[11px] font-semibold"
                  style={{ backgroundColor: RISK_COLORS[s.risk_level] }}>{RISK_VI[s.risk_level]}</span>,
              ])}
              empty="Không có học sinh nào dưới ngưỡng cảnh báo 🎉"
            />
          </Card>

          <Card title={`Học sinh tài năng (${warning.talent_students.length})`} desc="ĐTB ≥ 8.0 — ứng viên bồi dưỡng học sinh giỏi."
            icon={<Award className="w-5 h-5 text-emerald-500" />}>
            <StudentTable
              head={["Mã HS", "Họ tên", "Lớp", "ĐTB", "Môn nổi bật"]}
              rows={warning.talent_students.map((s) => [
                s.student_code, s.full_name, s.class_name,
                <span key="g" className="font-bold text-emerald-600 dark:text-emerald-400">{s.gpa.toFixed(2)}</span>,
                s.best_subject ? `${s.best_subject} (${s.best_score?.toFixed(1)})` : "—",
              ])}
              empty="Chưa có học sinh đạt ngưỡng Giỏi."
            />
          </Card>
        </div>
      )}

      {/* ===== TAB 5: TIN CẬY ĐIỂM SỐ (TEVI) ===== */}
      {tab === "validity" && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-3 rounded-xl">
            <SearchableSelect label="Môn (lọc tay)" value={subjectId} onChange={setSubjectId} className="min-w-[160px]"
              options={subjects.map((s) => ({ value: s.id, label: s.name }))} placeholder="Để trống = tự quét toàn trường" />
            <SearchableSelect label="Loại điểm" value={scoreCategory}
              onChange={(v) => setScoreCategory(v as ScoreCategory)} className="min-w-[140px]"
              options={(Object.keys(SCORE_CATEGORY_LABELS) as ScoreCategory[]).map((c) => ({ value: c, label: SCORE_CATEGORY_LABELS[c] }))}
              disabled={!subjectId} />
            <SearchableSelect label="Khối" value={gradeId} onChange={setGradeId} className="min-w-[120px]"
              options={grades.map((g) => ({ value: g.id, label: g.name }))} placeholder="Tất cả khối"
              disabled={!subjectId} />
            {subjectId && (
              <button onClick={() => { setSubjectId(""); setGradeId(""); }}
                className="text-xs font-semibold text-brand-600 dark:text-brand-400 hover:underline">
                ← Quay lại tự quét toàn trường
              </button>
            )}
            {validityLoading && <Loader2 className="w-4 h-4 text-brand-500 animate-spin" />}
          </div>

          {canSeeValidityOverview && validityOverview && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <Kpi label="Tổng đề đã kiểm" value={String(validityOverview.total_checked)} tone="bg-brand-500" />
              <Kpi label="Nghi lạm phát/lộ đề" value={String(validityOverview.flags_count["INFLATION_OR_LEAK"] ?? 0)}
                sub="Cần rà soát đề/coi thi" tone="bg-rose-500" />
              <Kpi label="Lỗ hổng học tập" value={String(validityOverview.flags_count["LEARNING_GAP"] ?? 0)}
                sub="Dạy chưa khớp nội dung kiểm tra" tone="bg-amber-500" />
              <Kpi label="Đáng tin cậy"
                value={String((validityOverview.flags_count["VALID"] ?? 0) + (validityOverview.flags_count["NO_CONTENT"] ?? 0))}
                tone="bg-emerald-500" />
            </div>
          )}

          <Card
            title={subjectId ? "Chi tiết tam giác hóa độ khó đề thi" : "Chi tiết tam giác hóa độ khó đề thi — tự quét toàn trường"}
            desc="EDI: độ khó ước lượng từ điểm số · CDI: độ khó theo nội dung đề. Lệch lớn giữa EDI và CDI → nghi ngờ độ tin cậy. Mặc định chỉ hiện các dòng có cờ bất thường, sắp theo Môn → Khối; chọn Môn (lọc tay) ở trên để xem đầy đủ kể cả dòng Đáng tin."
            icon={<ShieldCheck className="w-5 h-5 text-brand-500" />}>
            <button onClick={() => setShowValidityInfo((v) => !v)}
              className="flex items-center gap-1.5 text-xs font-semibold text-brand-600 dark:text-brand-400 hover:underline -mt-2">
              <Info className="w-3.5 h-3.5" />
              Biểu đồ này đánh giá dựa trên gì? Độ tin cậy ra sao?
              {showValidityInfo ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>

            {showValidityInfo && (
              <div className="rounded-xl bg-brand-50 dark:bg-brand-500/10 border border-brand-200 dark:border-brand-500/20 p-4 text-sm text-slate-700 dark:text-slate-300 space-y-2">
                <p>
                  <span className="font-semibold">Cách đánh giá:</span> hệ thống đối chiếu <span className="font-semibold">2 nguồn độ khó độc lập với nhau</span> cho cùng 1 đề thi —
                  (1) <span className="font-semibold">EDI</span>: suy ra từ điểm số học sinh làm bài thật (điểm trung bình thấp ↔ "trông" khó, điểm cao ↔ "trông" dễ), và
                  (2) <span className="font-semibold">CDI</span>: AI đọc nội dung đề (câu hỏi khó đến đâu về mặt kiến thức/tư duy) để tự đánh giá độ khó, không phụ thuộc ai đã làm bài.
                  Nếu 2 nguồn này <span className="font-semibold">khớp nhau</span> → đáng tin; nếu <span className="font-semibold">lệch nhau nhiều</span> → có gì đó bất thường (ví dụ điểm rất cao nhưng đề lại khó → nghi lạm phát điểm/lộ đề; điểm thấp nhưng đề lại dễ → nghi học sinh hổng kiến thức).
                </p>
                <p>
                  <span className="font-semibold">Độ tin cậy:</span> được đánh giá <span className="font-semibold text-emerald-600 dark:text-emerald-400">Cao</span> khi có
                  đủ số bài thi để so sánh (≥30 bài) <span className="italic">và</span> AI đã phân tích được nội dung đề; ngược lại là
                  <span className="font-semibold text-amber-600 dark:text-amber-400"> Thấp</span> (mẫu quá ít hoặc đề chưa được phân tích nội dung) — kết quả khi đó chỉ mang tính tham khảo.
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 italic">
                  Lưu ý: đây là <span className="font-semibold not-italic">tín hiệu cảnh báo để rà soát thêm</span>, KHÔNG phải kết luận chắc chắn —
                  AI phân tích đề có thể chưa hoàn hảo, và chênh lệch điểm số có thể do nhiều nguyên nhân khác (đề khó/dễ một cách tự nhiên theo từng năm, học sinh ôn tập lệch trọng tâm, v.v.). Cần GV/BGH kiểm tra lại trước khi đưa ra kết luận chính thức.
                </p>
              </div>
            )}

            {!subjectId && (
              <div className="flex flex-wrap gap-2 -mt-2">
                {(["ALL", "INFLATION_OR_LEAK", "LEARNING_GAP", "LOW_SAMPLE"] as const).map((f) => {
                  const count = f === "ALL" ? validityRows.length : validityRows.filter((r) => r.flag === f).length;
                  if (f !== "ALL" && count === 0) return null;
                  const active = validityFlagTab === f;
                  return (
                    <button key={f} onClick={() => setValidityFlagTab(f)}
                      className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${active
                        ? "bg-brand-600 text-white"
                        : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"}`}>
                      {f === "ALL" ? "Tất cả cờ" : FLAG_VI[f] ?? f} ({count})
                    </button>
                  );
                })}
              </div>
            )}
            {(() => {
              const shown = !subjectId && validityFlagTab !== "ALL"
                ? validityRows.filter((r) => r.flag === validityFlagTab)
                : validityRows;
              return shown.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                        <th className="py-2 px-3">Môn</th>
                        <th className="py-2 px-3">Khối</th>
                        <th className="py-2 px-3">Loại điểm</th>
                        <th className="py-2 px-3 text-right">n</th>
                        <th className="py-2 px-3 text-right">Mean</th>
                        <th className="py-2 px-3 text-right">EDI</th>
                        <th className="py-2 px-3 text-right">CDI</th>
                        <th className="py-2 px-3 text-right">Lệch (Δ)</th>
                        <th className="py-2 px-3">Cờ</th>
                        <th className="py-2 px-3">Độ tin cậy</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shown.map((r, i) => (
                        <tr
                          key={`${r.subject_id}-${r.grade_id}-${r.score_category}-${i}`}
                          onClick={() => setAnalysisPaperId(r.exam_paper_id)}
                          className="border-b border-slate-100 dark:border-slate-800/60 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40"
                        >
                          <td className="py-2 px-3 font-medium text-slate-800 dark:text-slate-200">{r.subject_name}</td>
                          <td className="py-2 px-3">{r.grade_name}</td>
                          <td className="py-2 px-3">{SCORE_CATEGORY_LABELS[r.score_category]}</td>
                          <td className="py-2 px-3 text-right">{r.n}</td>
                          <td className="py-2 px-3 text-right">{r.mean_score.toFixed(2)}</td>
                          <td className="py-2 px-3 text-right">{r.edi.toFixed(2)}</td>
                          <td className="py-2 px-3 text-right">{r.cdi != null ? r.cdi.toFixed(2) : "—"}</td>
                          <td className="py-2 px-3 text-right">{r.divergence != null ? r.divergence.toFixed(2) : "—"}</td>
                          <td className="py-2 px-3">
                            <span className="px-2 py-0.5 rounded-full text-xs font-semibold"
                              style={{ backgroundColor: `${FLAG_COLORS[r.flag] ?? "#94a3b8"}20`, color: FLAG_COLORS[r.flag] ?? "#94a3b8" }}>
                              {FLAG_VI[r.flag] ?? r.flag}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-slate-500 dark:text-slate-400">{r.confidence === "HIGH" ? "Cao" : "Thấp"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="py-8 text-center text-slate-400">
                  {validityLoading ? "Đang tải…" : !subjectId ? "Không phát hiện đề nào bất thường trong học kỳ này 🎉" : "Không có dữ liệu"}
                </div>
              );
            })()}
          </Card>

          {analysisPaperId && <ExamAnalysisDrawer paperId={analysisPaperId} onClose={() => setAnalysisPaperId(null)} />}

          {canSeeValidityOverview && (
            <Card title="Xếp hạng thực lực neo nội dung" desc="So sánh ĐTB thô với năng lực đã hiệu chỉnh theo độ khó nội dung đề — chọn đủ Môn + Khối để xem."
              icon={<BarChart3 className="w-5 h-5 text-brand-500" />}>
              <div className="h-80">
                {ranking.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={ranking} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={grid} />
                      <XAxis dataKey="class_name" stroke={axis} fontSize={11} />
                      <YAxis domain={[0, 10]} stroke={axis} fontSize={11} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Bar dataKey="raw_average" name="ĐTB thô" fill={CLUSTER_COLORS[0]} radius={[4, 4, 0, 0]} />
                      <Bar dataKey="content_adjusted_ability" name="Năng lực hiệu chỉnh" fill={CLUSTER_COLORS[1]} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-slate-400 text-sm text-center px-4">
                    Chọn đủ Môn và Khối để xem xếp hạng thực lực neo nội dung.
                  </div>
                )}
              </div>
            </Card>
          )}

        </div>
      )}

      {/* ===== TAB 6: ADVANCED EDM ANALYSIS ===== */}
      {tab === "edm" && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-50 dark:bg-slate-900/50 p-4 rounded-2xl border border-slate-200 dark:border-slate-800">
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase">Môn học</span>
                <select
                  value={edmSubjectId}
                  onChange={(e) => setEdmSubjectId(e.target.value)}
                  className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-3 py-1.5 rounded-xl text-sm outline-none font-semibold text-slate-800 dark:text-slate-200"
                >
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
            </div>
            {loadingEDM && <Loader2 className="w-5 h-5 text-brand-500 animate-spin" />}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            
            {/* 1. Academic Divergence (Delta G) */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm space-y-4">
              <div>
                <h4 className="text-lg font-bold text-slate-900 dark:text-white flex items-center">
                  <span>Chỉ số Dị biệt Học thuật Lớp học (ΔG<sub>Class</sub>)</span>
                  <InfoTooltip
                    content={
                      <div className="space-y-2 text-left">
                        <p className="font-bold text-brand-400 text-sm">Chỉ số Dị biệt Học thuật (ΔG_Class)</p>
                        <p>Đo lường sự khác biệt giữa điểm trung bình môn này với điểm trung bình của tất cả các môn học khác (GPAO) của cùng một lớp học.</p>
                        <div className="p-1.5 bg-slate-850 dark:bg-slate-900 rounded border border-slate-700 text-[10px] font-mono">
                          Công thức: ΔG = Điểm Môn Học - Điểm GPAO
                        </div>
                        <ul className="list-disc pl-4 space-y-1 text-slate-300">
                          <li><strong className="text-emerald-400">ΔG &gt; 0:</strong> Lớp học tốt môn này vượt trội hơn mặt bằng chung các môn học khác của lớp.</li>
                          <li><strong className="text-rose-400">ΔG &lt; 0:</strong> Điểm số môn này thấp hơn mức trung bình các môn khác, báo hiệu môn học gặp khó khăn.</li>
                        </ul>
                      </div>
                    }
                  />
                </h4>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">So sánh điểm trung bình môn thực tế với điểm trung bình các môn khác (GPAO) của lớp.</p>
              </div>
              <div className="h-80 w-full">
                {loadingEDM ? (
                  <div className="flex h-full items-center justify-center text-slate-500">
                    <Loader2 className="w-5 h-5 animate-spin mr-2 text-brand-500" />
                    <span className="text-sm font-medium">Đang tải dữ liệu...</span>
                  </div>
                ) : divergence.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={divergence} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={grid} />
                      <XAxis dataKey="class_name" stroke={axis} fontSize={11} />
                      <YAxis domain={[0, 10]} stroke={axis} fontSize={11} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Legend wrapperStyle={{ fontSize: 11, paddingTop: 10 }} />
                      <Bar dataKey="avg_subject_score" name="ĐTB Môn học" fill="#6366f1" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="avg_gpao" name="ĐTB môn khác (GPAO)" fill="#94a3b8" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-slate-400">Không có dữ liệu dị biệt</div>
                )}
              </div>
            </div>

            {/* 2. Grade Inflation (GDI Flags) */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-lg font-bold text-slate-900 dark:text-white flex items-center">
                    <span>Chỉ số Lệch pha & Lạm phát điểm (GDI<sub>Class</sub>)</span>
                    <InfoTooltip
                      content={
                        <div className="space-y-2 text-left">
                          <p className="font-bold text-brand-400 text-sm">Chỉ số Lệch pha & Lạm phát điểm (GDI)</p>
                          <p>So sánh kết quả điểm đánh giá thường xuyên (quá trình trên lớp) và kiểm tra cuối kỳ (định kỳ) thông qua hiệu số Z-score chuẩn hóa.</p>
                          <div className="p-1.5 bg-slate-850 dark:bg-slate-900 rounded border border-slate-700 text-[10px] font-mono">
                            Công thức: GDI = Z-score(TX) - Z-score(CK)
                          </div>
                          <ul className="list-disc pl-4 space-y-1 text-slate-300">
                            <li><strong className="text-rose-400">GDI ≥ 1.0 (Lạm phát):</strong> Điểm quá trình cao bất thường so với thi cuối kỳ. Có thể do kiểm tra trên lớp quá dễ hoặc chấm điểm lỏng tay.</li>
                            <li><strong className="text-brand-400">GDI ≤ -1.0:</strong> Điểm thi cuối kỳ vượt trội điểm quá trình (học sinh "học tài thi phận" hoặc điểm quá trình quá khắt khe).</li>
                          </ul>
                        </div>
                      }
                    />
                  </h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">So sánh Z-score điểm thường xuyên (TX) trên lớp và thi cuối kỳ (CK). Màu Đỏ biểu thị lạm phát.</p>
                </div>
                <ShieldAlert className="w-5 h-5 text-rose-500 animate-pulse" />
              </div>
              <div className="h-80 w-full overflow-y-auto">
                {loadingEDM ? (
                  <div className="flex h-full items-center justify-center text-slate-500">
                    <Loader2 className="w-5 h-5 animate-spin mr-2 text-brand-500" />
                    <span className="text-sm font-medium">Đang tải dữ liệu...</span>
                  </div>
                ) : inflation.length > 0 ? (
                  <div className="space-y-4 pr-2 pt-2">
                    {inflation.map((item, idx) => {
                      const isInflated = item.gdi >= 1.0;
                      const isDeflated = item.gdi <= -1.0;
                      const barColor = isInflated ? "bg-rose-500" : isDeflated ? "bg-brand-500" : "bg-slate-400";
                      return (
                        <div key={idx} className="space-y-1">
                          <div className="flex justify-between text-xs font-semibold text-slate-700 dark:text-slate-300">
                            <span>Lớp {item.class_name}</span>
                            <span className={`${isInflated ? "text-rose-500 font-bold" : isDeflated ? "text-brand-500" : "text-slate-500"}`}>
                              GDI: {item.gdi} {isInflated && "⚠️ Lạm phát"}
                            </span>
                          </div>
                          <div className="w-full bg-slate-100 dark:bg-slate-800 h-3.5 rounded-full overflow-hidden flex">
                            <div className="w-1/2 flex justify-end">
                              {item.gdi < 0 && (
                                <div
                                  className={`h-full ${barColor}`}
                                  style={{ width: `${Math.min(Math.abs(item.gdi) * 25, 100)}%` }}
                                />
                              )}
                            </div>
                            <div className="w-1/2 flex justify-start">
                              {item.gdi > 0 && (
                                <div
                                  className={`h-full ${barColor}`}
                                  style={{ width: `${Math.min(item.gdi * 25, 100)}%` }}
                                />
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="flex h-full items-center justify-center text-slate-400">Không có dữ liệu lạm phát</div>
                )}
              </div>
            </div>

            {/* 3. Learning Momentum Index */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm space-y-4">
              <div>
                <h4 className="text-lg font-bold text-slate-900 dark:text-white flex items-center">
                  <span>Phân phối Động lượng học tập sau kỳ giữa kỳ (∇M)</span>
                  <InfoTooltip
                    content={
                      <div className="space-y-2 text-left">
                        <p className="font-bold text-brand-400 text-sm">Động lượng Học tập (∇M)</p>
                        <p>Đo lường mức độ tiến bộ hoặc sa sút của học sinh ở giai đoạn nửa sau học kỳ (TX3, TX4) so với nửa đầu học kỳ (TX1, TX2), chuẩn hóa theo điểm thi giữa kỳ.</p>
                        <div className="p-1.5 bg-slate-850 dark:bg-slate-900 rounded border border-slate-700 text-[10px] font-mono">
                          Công thức: ∇M = (ĐTB Sau GK - ĐTB Trước GK) / Điểm Giữa Kỳ
                        </div>
                        <ul className="list-disc pl-4 space-y-1 text-slate-300">
                          <li><strong className="text-emerald-400">Tiến bộ (∇M &gt; 0.05):</strong> Học sinh có sự bứt phá và gia tăng nỗ lực vượt bậc sau khi thi giữa kỳ.</li>
                          <li><strong className="text-amber-400">Ổn định:</strong> Giữ vững phong độ học tập ổn định trong suốt cả học kỳ.</li>
                          <li><strong className="text-rose-400">Sa sút (∇M &lt; -0.05):</strong> Báo động đỏ học tập có chiều hướng đi xuống, cần giáo viên can thiệp sớm.</li>
                        </ul>
                      </div>
                    }
                  />
                </h4>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Thống kê số học sinh có Động lượng tiến bộ (Dương), Ổn định hoặc Sa sút (Âm).</p>
              </div>
              <div className="h-80 w-full">
                {loadingEDM ? (
                  <div className="flex h-full items-center justify-center text-slate-500">
                    <Loader2 className="w-5 h-5 animate-spin mr-2 text-brand-500" />
                    <span className="text-sm font-medium">Đang tải dữ liệu...</span>
                  </div>
                ) : momentum.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={momentum} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={grid} />
                      <XAxis dataKey="class_name" stroke={axis} fontSize={11} />
                      <YAxis stroke={axis} fontSize={11} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Legend wrapperStyle={{ fontSize: 11, paddingTop: 10 }} />
                      <Bar dataKey="positive_count" name="Tiến bộ (Dương)" fill="#10b981" stackId="a" />
                      <Bar dataKey="stable_count" name="Ổn định" fill="#f59e0b" stackId="a" />
                      <Bar dataKey="negative_count" name="Sa sút (Âm)" fill="#ef4444" stackId="a" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-slate-400">Không có dữ liệu động lượng</div>
                )}
              </div>
            </div>

            {/* 4. Latent Archetypes Radar */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm space-y-4">
              <div>
                <h4 className="text-lg font-bold text-slate-900 dark:text-white flex items-center">
                  <span>Bản đồ Phân cụm Năng lực học tập ẩn toàn trường</span>
                  <InfoTooltip
                    content={
                      <div className="space-y-2 text-left">
                        <p className="font-bold text-brand-400 text-sm">Bản đồ Phân cụm Năng lực ẩn</p>
                        <p>Phân cụm tự động học sinh toàn trường thành 4 nhóm đặc trưng hành vi học tập dựa trên sự đối chiếu giữa nỗ lực quá trình và kết quả thi cử.</p>
                        <ul className="list-disc pl-4 space-y-1 text-slate-300">
                          <li><strong className="text-emerald-400">Chăm chỉ ổn định:</strong> Nỗ lực cao và thi cử xuất sắc (TX ≥ 8.0, CK ≥ 8.0).</li>
                          <li><strong className="text-brand-400">Trì hoãn bứt phá:</strong> Quá trình học lơ là nhưng thi cuối kỳ bứt phá (TX &lt; 6.5, CK ≥ 7.5).</li>
                          <li><strong className="text-amber-400">Cần cù học vẹt:</strong> Học tập chăm chỉ nhưng kết quả thi cử kém (TX ≥ 7.5, CK &lt; 5.5).</li>
                          <li><strong className="text-rose-400">Nguy cơ học thuật:</strong> Cả quá trình và thi cử đều rất kém (TX &lt; 5.0, CK &lt; 5.0).</li>
                        </ul>
                      </div>
                    }
                  />
                </h4>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Biểu đồ mạng nhện (Radar Chart) phân nhóm học tập dựa trên sự kết hợp bài tập trên lớp và bài kiểm tra.</p>
              </div>
              <div className="h-80 w-full flex items-center justify-center">
                {loadingEDM ? (
                  <div className="flex h-full items-center justify-center text-slate-500">
                    <Loader2 className="w-5 h-5 animate-spin mr-2 text-brand-500" />
                    <span className="text-sm font-medium">Đang tải dữ liệu...</span>
                  </div>
                ) : archetypes.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart cx="50%" cy="50%" outerRadius="75%" data={radarData}>
                      <PolarGrid stroke={grid} />
                      <PolarAngleAxis dataKey="name" stroke={axis} fontSize={11} />
                      <PolarRadiusAxis stroke={axis} angle={30} domain={[0, 'auto']} fontSize={9} />
                      <Radar name="Học sinh" dataKey="value" stroke="#0d4d8b" fill="#0d4d8b" fillOpacity={0.3} />
                      <Tooltip contentStyle={tooltipStyle} />
                    </RadarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-slate-400">Không có dữ liệu phân cụm</div>
                )}
              </div>
            </div>

          </div>
        </div>
      )}
    </div>
  );
}

const RISK_VI: Record<string, string> = { Low: "Thấp", Medium: "Trung bình", High: "Cao", Critical: "Nghiêm trọng" };

// Bar ngang xếp hạng lớp.
function RankBars({ rows, color, axis, grid, tooltipStyle }: {
  rows: { class_name: string; gpa: number }[]; color: string; axis: string; grid: string; tooltipStyle: object;
}) {
  if (rows.length === 0) return <div className="h-64 flex items-center justify-center text-slate-400">Không có dữ liệu</div>;
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} horizontal={false} />
          <XAxis type="number" domain={[0, 10]} stroke={axis} fontSize={11} />
          <YAxis type="category" dataKey="class_name" stroke={axis} fontSize={11} width={60} />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar dataKey="gpa" name="ĐTB lớp" fill={color} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Bảng xếp hạng đơn giản.
function RankTable({ rows, nameLabel }: {
  rows: { rank: number; name: string; sub: string; gpa: number }[]; nameLabel: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
            <th className="py-2 px-3 w-12">#</th>
            <th className="py-2 px-3">{nameLabel}</th>
            <th className="py-2 px-3 text-right">ĐTB</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name} className="border-b border-slate-100 dark:border-slate-800/60">
              <td className="py-2 px-3 text-slate-400">{r.rank}</td>
              <td className="py-2 px-3 font-medium text-slate-800 dark:text-slate-200">{r.name}</td>
              <td className="py-2 px-3 text-right font-bold text-slate-900 dark:text-white">{r.gpa.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Bảng học sinh (risk/talent).
function StudentTable({ head, rows, empty }: {
  head: string[]; rows: React.ReactNode[][]; empty: string;
}) {
  if (rows.length === 0) return <p className="py-6 text-center text-slate-400 text-sm">{empty}</p>;
  return (
    <div className="overflow-x-auto max-h-96 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-white dark:bg-slate-900">
          <tr className="text-left text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
            {head.map((h) => <th key={h} className="py-2 px-3 whitespace-nowrap">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, i) => (
            <tr key={i} className="border-b border-slate-100 dark:border-slate-800/60">
              {cells.map((c, j) => <td key={j} className="py-2 px-3 whitespace-nowrap text-slate-700 dark:text-slate-300">{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
