"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
    AlertTriangle,
    ArrowRight,
    Award,
    BookOpen,
    Brain,
    CheckCircle2,
    Filter,
    GraduationCap,
    Info,
    Laptop,
    Layers,
    RotateCcw,
    Search,
    ShieldAlert,
    ShieldCheck,
    Sparkles,
    Target,
    TrendingUp,
    User,
    Users,
    X,
} from "lucide-react";
import SearchableSelect from "@/components/SearchableSelect";
import KnowledgeGapDetailDrawer from "@/components/knowledgeGaps/KnowledgeGapDetailDrawer";
import { api } from "@/lib/api";
import {
    ClassRosterResponse,
    StudentRosterSummary,
} from "@/lib/types";

// Ngưỡng thành thạo đạt chuẩn
const GAP_THRESHOLD = 0.6;

// Badge độ tin cậy (confidence)
const CONFIDENCE_META: Record<string, { label: string; cls: string; dotCls: string }> = {
    HIGH: { label: "Tin cậy cao", cls: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/20", dotCls: "bg-emerald-500" },
    MEDIUM: { label: "Tin cậy TB", cls: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/20", dotCls: "bg-amber-500" },
    LOW: { label: "Tin cậy thấp", cls: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-500/20", dotCls: "bg-rose-500" },
    INSUFFICIENT: { label: "Chưa đủ dữ liệu", cls: "bg-slate-50 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700", dotCls: "bg-slate-400" },
};

// Badge trạng thái đối soát (integrity)
const INTEGRITY_META: Record<string, { label: string; cls: string; icon: React.ReactNode }> = {
    OK: { label: "Đồng thuận", cls: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/20", icon: <CheckCircle2 className="w-3 h-3 text-emerald-500" /> },
    LMS_EXCEEDS_EXAM: { label: "LMS vượt trội", cls: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:border-sky-500/20", icon: <TrendingUp className="w-3 h-3 text-sky-500" /> },
    SUSPECTED_CHEATING: { label: "LMS vượt trội", cls: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:border-sky-500/20", icon: <TrendingUp className="w-3 h-3 text-sky-500" /> },
    LOW_ENGAGEMENT: { label: "Ít luyện tập LMS", cls: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/20", icon: <Laptop className="w-3 h-3 text-amber-500" /> },
    LMS_ONLY: { label: "Chỉ từ LMS", cls: "bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700", icon: <Laptop className="w-3 h-3 text-slate-500" /> },
    FLAGGED: { label: "Cần kiểm chứng", cls: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/20", icon: <AlertTriangle className="w-3 h-3 text-amber-500" /> },
};

type FilterTab = "ALL" | "NEED_SUPPORT" | "MASTERED" | "ALERT";

export default function KnowledgeGapsPage() {
    const router = useRouter();
    const [subjects, setSubjects] = useState<{ id: string; name: string }[]>([]);
    const [classes, setClasses] = useState<{ id: string; name: string }[]>([]);

    const [subjectId, setSubjectId] = useState<string>("");
    const [classId, setClassId] = useState<string>("");

    const [rosterData, setRosterData] = useState<ClassRosterResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [isRecalculating, setIsRecalculating] = useState(false);
    const [recalcMsg, setRecalcMsg] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Bộ lọc danh sách học sinh
    const [searchTerm, setSearchTerm] = useState("");
    const [activeTab, setActiveTab] = useState<FilterTab>("ALL");

    // Drawer chi tiết của 1 học sinh
    const [selectedStudent, setSelectedStudent] = useState<StudentRosterSummary | null>(null);

    // 1. Load subjects từ s360.dim_subject
    useEffect(() => {
        api
            .get<{ id: number; name: string }[]>("/knowledge-gaps/subject-options")
            .then((list) => {
                const mapped = (list ?? []).map((s) => ({ id: String(s.id), name: s.name }));
                setSubjects(mapped);
                // Mặc định chọn môn Toán 6 (hoặc id 106) nếu có
                const toan6 = mapped.find((m) => m.name.toLowerCase().includes("toán 6") || m.id === "106") || mapped.find((m) => m.name.toLowerCase().includes("toán"));
                if (toan6) setSubjectId(toan6.id);
            })
            .catch(() => setError("Không tải được danh sách môn học."));
    }, []);

    // 2. Load classes từ s360
    useEffect(() => {
        api
            .get<{ class_id: number; class_name: string }[]>("/knowledge-gaps/class-options")
            .then((list) => {
                const mapped = (list ?? []).map((c) => ({ id: String(c.class_id), name: c.class_name }));
                setClasses(mapped);
                // Mặc định chọn lớp Khối 6 (6A1, 6A, Lớp 6...) nếu có
                const class6 = mapped.find((c) => c.name.startsWith("6") || c.name.toLowerCase().includes("lớp 6") || c.name.toLowerCase().includes("6a")) || mapped[0];
                if (class6) setClassId(class6.id);
            })
            .catch(() => setError("Không tải được danh sách lớp."));
    }, []);

    // 3. Tự động tải Roster khi đã có cả Subject và Class
    const loadRoster = useCallback(async () => {
        if (!classId || !subjectId) return;
        setLoading(true);
        setError(null);
        try {
            const data = await api.get<ClassRosterResponse>(
                `/knowledge-gaps/classes/${classId}/roster?subject_id=${subjectId}&semester_index=1`
            );
            setRosterData(data);
        } catch (e: any) {
            setError(e?.message ?? "Lỗi khi tải danh sách chẩn đoán học sinh.");
        } finally {
            setLoading(false);
        }
    }, [classId, subjectId]);

    useEffect(() => {
        if (classId && subjectId) {
            loadRoster();
        }
    }, [classId, subjectId, loadRoster]);

    // 3.1 Tính toán lại toàn bộ student_unit_mastery từ LMS item-response
    const handleRecalcMastery = async () => {
        if (!subjectId) return;
        setIsRecalculating(true);
        setError(null);
        setRecalcMsg(null);
        try {
            const res = await api.post<{ success: boolean; records_calculated: number; message: string }>(
                `/knowledge-gaps/recalc-mastery?subject_id=${subjectId}&semester_index=1`
            );
            setRecalcMsg(res.message || `Đã tính toán lại năng lực thành công (${res.records_calculated} bản ghi).`);
            await loadRoster();
            setTimeout(() => setRecalcMsg(null), 6000);
        } catch (e: any) {
            setError(e?.message ?? "Lỗi khi tính lại năng lực học sinh.");
        } finally {
            setIsRecalculating(false);
        }
    };

    // 4. Lọc học sinh theo Search & Tab
    const filteredStudents = useMemo(() => {
        if (!rosterData) return [];
        return rosterData.students.filter((s) => {
            // Lọc theo search
            const matchSearch =
                s.student_code.toLowerCase().includes(searchTerm.toLowerCase()) ||
                s.student_name.toLowerCase().includes(searchTerm.toLowerCase());
            if (!matchSearch) return false;

            // Lọc theo Tab
            if (activeTab === "NEED_SUPPORT") return s.gap_count > 0;
            if (activeTab === "MASTERED") return s.gap_count === 0 && s.total_units > 0;
            if (activeTab === "ALERT")
                return (
                    s.integrity_status === "LMS_EXCEEDS_EXAM" ||
                    s.integrity_status === "SUSPECTED_CHEATING" ||
                    s.integrity_status === "LOW_ENGAGEMENT" ||
                    s.integrity_status === "FLAGGED"
                );
            return true;
        });
    }, [rosterData, searchTerm, activeTab]);

    return (
        <div className="p-6 md:p-8 max-w-[1500px] mx-auto space-y-6">
            {/* HEADER */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2.5">
                        <Brain className="w-7 h-7 text-brand-600 dark:text-brand-400" />
                        Chẩn đoán Lỗ hổng Kiến thức
                    </h2>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Theo dõi mức độ thành thạo từng chương của toàn bộ học sinh trong lớp. Nhấp vào học sinh bất kỳ để xem giải trình chi tiết.
                    </p>
                </div>
            </div>

            {/* BỘ LỌC CHỌN MÔN & LỚP */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs flex flex-wrap items-end gap-4">
                <div className="min-w-[200px] flex-1 sm:flex-initial">
                    <label className="text-xs font-bold text-slate-600 dark:text-slate-400 mb-1.5 flex items-center gap-1.5">
                        <BookOpen className="w-3.5 h-3.5 text-brand-500" />
                        Môn học
                    </label>
                    <SearchableSelect
                        options={subjects.map((s) => ({ value: s.id, label: s.name }))}
                        value={subjectId}
                        onChange={setSubjectId}
                        placeholder="Chọn môn học..."
                        className="w-full"
                    />
                </div>

                <div className="min-w-[180px] flex-1 sm:flex-initial">
                    <label className="text-xs font-bold text-slate-600 dark:text-slate-400 mb-1.5 flex items-center gap-1.5">
                        <Users className="w-3.5 h-3.5 text-indigo-500" />
                        Lớp học
                    </label>
                    <SearchableSelect
                        options={classes.map((c) => ({ value: c.id, label: c.name }))}
                        value={classId}
                        onChange={setClassId}
                        placeholder="Chọn lớp..."
                        className="w-full"
                    />
                </div>

                <button
                    onClick={loadRoster}
                    disabled={loading || !classId || !subjectId}
                    className="px-4 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold shadow-xs disabled:opacity-50 transition-all flex items-center gap-2"
                >
                    <RotateCcw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                    Làm mới dữ liệu
                </button>

                <button
                    onClick={handleRecalcMastery}
                    disabled={isRecalculating || !subjectId}
                    className="px-4 py-2.5 rounded-xl border border-indigo-200 dark:border-indigo-800 bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/40 dark:hover:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 text-sm font-semibold shadow-xs disabled:opacity-50 transition-all flex items-center gap-2"
                    title="Tính toán lại toàn bộ độ thành thạo học sinh từ kết quả làm bài LMS mới nhất"
                >
                    <Sparkles className={`w-4 h-4 text-indigo-600 dark:text-indigo-400 ${isRecalculating ? "animate-spin" : ""}`} />
                    {isRecalculating ? "Đang tính..." : "Tính lại năng lực"}
                </button>
            </div>

            {recalcMsg && (
                <div className="rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 px-5 py-4 text-sm text-emerald-700 dark:text-emerald-300 flex items-center justify-between gap-3 animate-in fade-in duration-200">
                    <div className="flex items-center gap-2.5">
                        <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
                        <span>{recalcMsg}</span>
                    </div>
                    <button onClick={() => setRecalcMsg(null)} className="text-emerald-500 hover:text-emerald-700 p-1">
                        <X className="w-4 h-4" />
                    </button>
                </div>
            )}

            {error && (
                <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 px-5 py-4 text-sm text-rose-700 dark:text-rose-300 flex items-center gap-3">
                    <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0" />
                    <span>{error}</span>
                </div>
            )}

            {/* NỘI DUNG ROSTER CẢ LỚP */}
            {rosterData && (
                <div className="space-y-6">
                    {/* HERO KPI STATS CARDS */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {/* 1. Sĩ số lớp */}
                        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xs flex items-center justify-between">
                            <div>
                                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 block">
                                    Sĩ số Lớp {rosterData.class_name}
                                </span>
                                <div className="flex items-baseline gap-1.5 mt-1.5">
                                    <span className="text-2xl font-black text-slate-900 dark:text-white">
                                        {rosterData.total_students}
                                    </span>
                                    <span className="text-xs font-medium text-slate-400">
                                        học sinh
                                    </span>
                                </div>
                            </div>
                            <div className="w-11 h-11 rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400 flex items-center justify-center">
                                <Users className="w-5 h-5" />
                            </div>
                        </div>

                        {/* 2. Đạt chuẩn toàn bộ */}
                        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xs flex items-center justify-between">
                            <div>
                                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 block">
                                    Nắm Vững Toàn Bộ
                                </span>
                                <div className="flex items-baseline gap-1.5 mt-1.5">
                                    <span className="text-2xl font-black text-emerald-600 dark:text-emerald-400">
                                        {rosterData.mastered_all_count}
                                    </span>
                                    <span className="text-xs font-medium text-slate-400">
                                        / {rosterData.total_students} em (≥60%)
                                    </span>
                                </div>
                            </div>
                            <div className="w-11 h-11 rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400 flex items-center justify-center">
                                <Award className="w-5 h-5" />
                            </div>
                        </div>

                        {/* 3. Cần can thiệp */}
                        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xs flex items-center justify-between">
                            <div>
                                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 block">
                                    Cần Củng Cố Kiến Thức
                                </span>
                                <div className="flex items-baseline gap-1.5 mt-1.5">
                                    <span className={`text-2xl font-black ${rosterData.need_support_count > 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                                        {rosterData.need_support_count}
                                    </span>
                                    <span className="text-xs font-medium text-slate-400">
                                        / {rosterData.total_students} em (&lt;60%)
                                    </span>
                                </div>
                            </div>
                            <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${rosterData.need_support_count > 0 ? "bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-400" : "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400"}`}>
                                <Target className="w-5 h-5" />
                            </div>
                        </div>

                        {/* 4. Cảnh báo đối soát */}
                        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xs flex items-center justify-between">
                            <div>
                                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 block">
                                    Lệch Đối Soát LMS
                                </span>
                                <div className="flex items-baseline gap-1.5 mt-1.5">
                                    <span className={`text-2xl font-black ${rosterData.cheating_alert_count + rosterData.low_engagement_count > 0 ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                                        {rosterData.cheating_alert_count + rosterData.low_engagement_count}
                                    </span>
                                    <span className="text-xs font-medium text-slate-400">
                                        ({rosterData.cheating_alert_count} vượt trội • {rosterData.low_engagement_count} ít làm)
                                    </span>
                                </div>
                            </div>
                            <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${rosterData.cheating_alert_count + rosterData.low_engagement_count > 0 ? "bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400" : "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400"}`}>
                                <ShieldAlert className="w-5 h-5" />
                            </div>
                        </div>
                    </div>

                    {/* DANH SÁCH CHẨN ĐOÁN HỌC SINH */}
                    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden p-5 space-y-4">
                        {/* Thanh tìm kiếm & Tabs lọc */}
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100 dark:border-slate-800">
                            {/* Tabs */}
                            <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-100 dark:bg-slate-800/80 max-w-fit flex-wrap">
                                <button
                                    onClick={() => setActiveTab("ALL")}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                                        activeTab === "ALL"
                                            ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-xs"
                                            : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"
                                    }`}
                                >
                                    Tất cả ({rosterData.total_students})
                                </button>
                                <button
                                    onClick={() => setActiveTab("NEED_SUPPORT")}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                                        activeTab === "NEED_SUPPORT"
                                            ? "bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300 shadow-xs"
                                            : "text-slate-500 dark:text-slate-400 hover:text-rose-600"
                                    }`}
                                >
                                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                                    Cần củng cố ({rosterData.need_support_count})
                                </button>
                                <button
                                    onClick={() => setActiveTab("MASTERED")}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                                        activeTab === "MASTERED"
                                            ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 shadow-xs"
                                            : "text-slate-500 dark:text-slate-400 hover:text-emerald-600"
                                    }`}
                                >
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                                    Vững vàng ({rosterData.mastered_all_count})
                                </button>
                                <button
                                    onClick={() => setActiveTab("ALERT")}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                                        activeTab === "ALERT"
                                            ? "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300 shadow-xs"
                                            : "text-slate-500 dark:text-slate-400 hover:text-amber-600"
                                    }`}
                                >
                                    <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
                                    Cảnh báo đối soát ({rosterData.cheating_alert_count + rosterData.low_engagement_count})
                                </button>
                            </div>

                            {/* Search Input */}
                            <div className="relative min-w-[240px]">
                                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                                <input
                                    type="text"
                                    placeholder="Tìm tên hoặc mã học sinh..."
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    className="w-full pl-9 pr-3.5 py-2 rounded-xl text-xs bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-500/20 text-slate-800 dark:text-slate-200"
                                />
                            </div>
                        </div>

                        {/* Bảng Danh sách Học sinh */}
                        {filteredStudents.length > 0 ? (
                            <div className="border border-slate-100 dark:border-slate-800 rounded-xl overflow-hidden">
                                <table className="w-full text-sm table-fixed">
                                    <thead>
                                        <tr className="text-left text-xs font-bold text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                                            <th className="px-5 py-3 w-[22%]">Học sinh</th>
                                            <th className="px-5 py-3 w-[22%]">Mức độ Thành thạo</th>
                                            <th className="px-5 py-3 w-[36%]">Trọng tâm Cần củng cố</th>
                                            <th className="px-5 py-3 w-[12%]">Đối soát LMS</th>
                                            <th className="px-5 py-3 w-[8%] text-right">Chi tiết</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                                        {filteredStudents.map((s) => {
                                            const masteryPct = Math.round(s.avg_mastery * 100);
                                            const conf = CONFIDENCE_META[s.confidence ?? "LOW"] ?? CONFIDENCE_META.LOW;
                                            const integ = INTEGRITY_META[s.integrity_status ?? "OK"] ?? INTEGRITY_META.OK;

                                            // Gom lỗ hổng theo cấp Chương từ cây gaps
                                            const weakChapters = (s.gaps || [])
                                                .filter((ch) => (ch.gap_lessons_count ?? 0) > 0 || (ch.raw_mastery ?? ch.mastery) < 0.6)
                                                .map((ch) => ({
                                                    name: ch.unit_name || ch.chapter || `Chương ${ch.unit_id}`,
                                                    gapLessons: ch.gap_lessons_count ?? 1,
                                                    totalLessons: ch.total_lessons_count ?? (ch.lessons?.length || 1),
                                                }));

                                            return (
                                                <tr
                                                    key={s.student_code}
                                                    onClick={() => setSelectedStudent(s)}
                                                    className="cursor-pointer hover:bg-brand-50/40 dark:hover:bg-slate-800/60 transition-colors group h-[64px]"
                                                >
                                                    {/* Cột 1: Học sinh */}
                                                    <td className="px-5 py-3">
                                                        <div className="flex items-center gap-3">
                                                            <div className="w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold text-xs flex items-center justify-center shrink-0 border border-slate-200/60 dark:border-slate-700">
                                                                {s.student_name.slice(0, 1)}
                                                            </div>
                                                            <div className="min-w-0">
                                                                <span className="font-bold text-slate-900 dark:text-slate-100 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors block truncate text-xs">
                                                                    {s.student_name}
                                                                </span>
                                                                <span className="text-[11px] font-mono text-slate-400 block truncate">
                                                                    {s.student_code}
                                                                </span>
                                                            </div>
                                                        </div>
                                                    </td>

                                                    {/* Cột 2: Thành thạo & Tình trạng lỗ hổng (Gộp gọn) */}
                                                    <td className="px-5 py-3">
                                                        <div className="space-y-1.5 pr-4">
                                                            <div className="flex items-center justify-between text-xs">
                                                                <span className={`font-bold ${masteryPct >= 70 ? "text-emerald-600 dark:text-emerald-400" : masteryPct >= 50 ? "text-amber-600 dark:text-amber-400" : "text-rose-600 dark:text-rose-400"}`}>
                                                                    {masteryPct}%
                                                                </span>
                                                                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                                                                    {s.gap_count > 0 ? (
                                                                        <span className="text-rose-600 dark:text-rose-400 font-semibold">
                                                                            Hổng {s.gap_count}/{s.total_units} bài
                                                                        </span>
                                                                    ) : (
                                                                        <span className="text-emerald-600 dark:text-emerald-400">
                                                                            Vững {s.total_units}/{s.total_units} bài
                                                                        </span>
                                                                    )}
                                                                </span>
                                                            </div>
                                                            <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                                                <div
                                                                    className={`h-full rounded-full transition-all duration-300 ${
                                                                        masteryPct >= 70
                                                                            ? "bg-emerald-500"
                                                                            : masteryPct >= 50
                                                                            ? "bg-amber-500"
                                                                            : "bg-rose-500"
                                                                    }`}
                                                                    style={{ width: `${Math.min(100, Math.max(5, masteryPct))}%` }}
                                                                />
                                                            </div>
                                                        </div>
                                                    </td>

                                                    {/* Cột 3: Trọng tâm cần củng cố (Gom theo Chương, không bung tràn lan) */}
                                                    <td className="px-5 py-3">
                                                        {weakChapters.length > 0 ? (
                                                            <div className="flex items-center gap-1.5 flex-wrap">
                                                                {weakChapters.slice(0, 2).map((ch, idx) => (
                                                                    <span
                                                                        key={idx}
                                                                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 text-xs font-medium border border-rose-200/60 dark:border-rose-900/40 truncate max-w-[200px]"
                                                                        title={`${ch.name} (Hổng ${ch.gapLessons}/${ch.totalLessons} bài)`}
                                                                    >
                                                                        <span className="truncate">{ch.name.replace(/^Chương\s+/i, "C")}</span>
                                                                        <span className="text-[10px] font-bold text-rose-500 shrink-0 bg-white dark:bg-rose-900/60 px-1 py-0.2 rounded">
                                                                            {ch.gapLessons} bài
                                                                        </span>
                                                                    </span>
                                                                ))}
                                                                {weakChapters.length > 2 && (
                                                                    <span
                                                                        className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 text-xs font-semibold"
                                                                        title={weakChapters.slice(2).map(c => `${c.name} (${c.gapLessons} bài)`).join(", ")}
                                                                    >
                                                                        +{weakChapters.length - 2} chương nữa
                                                                    </span>
                                                                )}
                                                            </div>
                                                        ) : (
                                                            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                                                                <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                                                                Không có lỗ hổng kiến thức
                                                            </span>
                                                        )}
                                                    </td>

                                                    {/* Cột 4: Đối soát LMS (Tinh gọn 1 chip) */}
                                                    <td className="px-5 py-3">
                                                        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border bg-slate-50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700" title={`${integ.label} • ${conf.label}`}>
                                                            {integ.icon}
                                                            <span className="text-[11px] text-slate-700 dark:text-slate-300">{integ.label}</span>
                                                            <span className={`w-1.5 h-1.5 rounded-full ${conf.dotCls} shrink-0`} />
                                                        </div>
                                                    </td>

                                                    {/* Cột 5: Xem chi tiết */}
                                                    <td className="px-5 py-3 text-right">
                                                        <span className="text-brand-600 dark:text-brand-400 text-xs font-bold group-hover:translate-x-0.5 transition-transform inline-flex items-center gap-1">
                                                            Chi tiết <ArrowRight className="w-3.5 h-3.5" />
                                                        </span>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <div className="py-12 text-center text-sm text-slate-400 space-y-2">
                                <Users className="w-8 h-8 mx-auto text-slate-300 dark:text-slate-600" />
                                <p>Không tìm thấy học sinh nào phù hợp với bộ lọc hiện tại.</p>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* DRAWER CHI TIẾT KHI CLICK VÀO HỌC SINH */}
            {selectedStudent && (
                <KnowledgeGapDetailDrawer
                    studentCode={selectedStudent.student_code}
                    studentName={selectedStudent.student_name}
                    className={rosterData?.class_name ?? `Lớp ${classId}`}
                    subjectName={rosterData?.subject_name ?? `Môn ${subjectId}`}
                    gaps={selectedStudent.gaps}
                    onClose={() => setSelectedStudent(null)}
                />
            )}
        </div>
    );
}