"use client";

import React, { useMemo, useState } from "react";
import {
    AlertCircle,
    AlertTriangle,
    BookOpen,
    CheckCircle2,
    Filter,
    Layers,
    Lightbulb,
    Target,
    User,
    X,
    Image as ImageIcon,
    ZoomIn,
    Info,
} from "lucide-react";
import type { ExamAnalysisItem, ExamPaperDetail, StudentForecastRow } from "@/lib/types";

const BLOOM_LABELS: Record<number, string> = {
    1: "Nhớ",
    2: "Hiểu",
    3: "Vận dụng",
    4: "Phân tích",
    5: "Đánh giá",
    6: "Sáng tạo",
};

const BLOOM_COLORS: Record<number, string> = {
    1: "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
    2: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800",
    3: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800",
    4: "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800",
    5: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800",
    6: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800",
};

interface GroupedQuestion {
    questionNumber: number;
    questionText: string;
    bloom_level: number;
    has_figure: boolean;
    image_url: string | null;
    totalWeight: number;
    subItems: ExamAnalysisItem[];
    // Năng lực LMS tổng hợp cho câu hỏi này
    avgAbility: number | null;
    riskStatus: "SAFE" | "WARNING" | "CRITICAL" | "NO_DATA";
}

interface Props {
    student: StudentForecastRow | null;
    examPaper: ExamPaperDetail | null;
    onClose: () => void;
}

export default function StudentExamMatchingDrawer({ student, examPaper, onClose }: Props) {
    const [selectedFilter, setSelectedFilter] = useState<"ALL" | "CRITICAL" | "WARNING" | "SAFE">("ALL");
    const [selectedImageModal, setSelectedImageModal] = useState<{ url: string; title: string } | null>(null);

    const items = examPaper?.ai_analysis?.content_analysis?.items || [];
    const unitAbilities = student?.unit_abilities || {};

    // Nhóm items theo từng câu hỏi lớn và đối chiếu năng lực LMS
    const groupedQuestions: GroupedQuestion[] = useMemo(() => {
        if (!items || items.length === 0) return [];

        const map = new Map<string, GroupedQuestion>();
        let autoQNum = 1;

        items.forEach((item) => {
            const rawExcerpt = item.excerpt?.trim() || "";
            const match = rawExcerpt.match(/^(?:Câu|Bài)\s*(\d+)/i);
            const key = match ? `q_${match[1]}` : (item.image_url ? `img_${item.image_url}` : `auto_${autoQNum}`);

            if (!map.has(key)) {
                const qNum = match ? parseInt(match[1], 10) : autoQNum++;
                map.set(key, {
                    questionNumber: qNum,
                    questionText: rawExcerpt || item.topic,
                    bloom_level: item.bloom_level,
                    has_figure: Boolean(item.has_figure),
                    image_url: item.image_url || null,
                    totalWeight: 0,
                    subItems: [],
                    avgAbility: null,
                    riskStatus: "SAFE",
                });
            }

            const g = map.get(key)!;
            g.totalWeight += item.weight;
            if (item.bloom_level > g.bloom_level) g.bloom_level = item.bloom_level;
            if (item.has_figure) g.has_figure = true;
            if (item.image_url && !g.image_url) g.image_url = item.image_url;
            g.subItems.push(item);
        });

        const list = Array.from(map.values()).sort((a, b) => a.questionNumber - b.questionNumber);

        // Tính năng lực LMS đối chiếu cho từng câu hỏi
        list.forEach((q) => {
            let totalWeightedAbility = 0;
            let totalSubWeight = 0;
            let hasAnyData = false;

            q.subItems.forEach((sub) => {
                const uId = sub.node_ref?.node_id;
                const ab = uId ? unitAbilities[uId] : null;
                const w = sub.question_share ?? sub.weight;
                if (ab !== null && ab !== undefined) {
                    totalWeightedAbility += ab * w;
                    totalSubWeight += w;
                    hasAnyData = true;
                }
            });

            if (hasAnyData && totalSubWeight > 0) {
                const finalAb = totalWeightedAbility / totalSubWeight;
                q.avgAbility = finalAb;
                if (finalAb >= 7.0) {
                    q.riskStatus = "SAFE";
                } else if (finalAb >= 5.0) {
                    q.riskStatus = "WARNING";
                } else {
                    q.riskStatus = "CRITICAL";
                }
            } else {
                q.avgAbility = null;
                q.riskStatus = "NO_DATA";
            }
        });

        return list;
    }, [items, unitAbilities]);

    if (!student || !examPaper) return null;

    // Thống kê nhanh số câu theo mức độ
    const stats = {
        total: groupedQuestions.length,
        critical: groupedQuestions.filter((q) => q.riskStatus === "CRITICAL").length,
        warning: groupedQuestions.filter((q) => q.riskStatus === "WARNING").length,
        safe: groupedQuestions.filter((q) => q.riskStatus === "SAFE").length,
    };

    const filteredQuestions = groupedQuestions.filter((q) => {
        if (selectedFilter === "ALL") return true;
        return q.riskStatus === selectedFilter;
    });

    const verdictCls =
        student.verdict === "PASS"
            ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
            : student.verdict === "FAIL"
            ? "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border border-rose-200 dark:border-rose-800"
            : student.verdict === "BORDERLINE"
            ? "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800"
            : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border border-slate-200 dark:border-slate-700";

    const verdictLabel =
        student.verdict === "PASS"
            ? "DỰ BÁO ĐẬU"
            : student.verdict === "FAIL"
            ? "DỰ BÁO TRƯỢT"
            : student.verdict === "BORDERLINE"
            ? "NGUY CƠ MÉP ĐẬU/TRƯỢT"
            : "CHƯA ĐỦ DỮ LIỆU LMS";

    return (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-xs flex justify-end animate-in fade-in duration-200">
            <div className="absolute inset-0" onClick={onClose} />

            <div className="relative w-full max-w-3xl bg-white dark:bg-slate-900 shadow-2xl h-full flex flex-col border-l border-slate-200 dark:border-slate-800 z-10 animate-in slide-in-from-right duration-300">
                {/* HEADER */}
                <div className="p-5 border-b border-slate-100 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/50 flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3.5 min-w-0">
                        <div className="w-11 h-11 rounded-2xl bg-brand-50 dark:bg-brand-950/60 border border-brand-100 dark:border-brand-900/50 flex items-center justify-center text-brand-600 dark:text-brand-400 shrink-0 shadow-2xs">
                            <User className="w-5 h-5" />
                        </div>
                        <div className="space-y-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                                <h3 className="text-lg font-bold text-slate-900 dark:text-white truncate">
                                    {student.student_name || student.student_code}
                                </h3>
                                <span className="px-2 py-0.5 text-xs font-mono font-medium rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-700/80">
                                    {student.student_code}
                                </span>
                                {student.class_name && (
                                    <span className="px-2 py-0.5 text-xs font-medium rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                                        {student.class_name.toLowerCase().startsWith("lớp") ? student.class_name : `Lớp ${student.class_name}`}
                                    </span>
                                )}
                                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${verdictCls}`}>
                                    {verdictLabel}
                                </span>
                            </div>
                            <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2 flex-wrap">
                                <span>Đề thi: <strong className="text-slate-700 dark:text-slate-200">{examPaper.title}</strong></span>
                                {student.predicted_score !== null && (
                                    <span>• Điểm dự báo: <strong className="text-brand-600 dark:text-brand-400 font-mono text-sm">{student.predicted_score.toFixed(2)}/10</strong></span>
                                )}
                            </p>
                        </div>
                    </div>

                    <button
                        onClick={onClose}
                        className="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                        title="Đóng"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* THÔNG BÁO CẢNH BÁO ĐỘ LỆCH THI vs LMS NẾU CÓ */}
                {student.discrepancy_warning && (
                    <div className="mx-5 mt-4 p-3.5 rounded-2xl bg-amber-50/90 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 text-xs text-amber-900 dark:text-amber-200 flex items-start gap-3 shadow-2xs">
                        <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                        <div className="space-y-1">
                            <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-bold text-slate-900 dark:text-white">Lưu ý độ tin cậy dự báo:</span>
                                <span className="px-2 py-0.2 rounded-full text-[10px] font-bold bg-amber-200/70 dark:bg-amber-900/60 text-amber-800 dark:text-amber-300">
                                    {student.integrity_status === "LOW_ENGAGEMENT" ? "Ít luyện tập LMS" : student.integrity_status === "LMS_EXCEEDS_EXAM" ? "LMS vượt trội" : "Chênh lệch điểm"}
                                </span>
                            </div>
                            <p className="text-slate-700 dark:text-slate-300 leading-relaxed font-medium">
                                {student.discrepancy_warning}
                            </p>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 italic">
                                💡 Lưu ý: Hệ thống dự báo dựa trên năng lực làm bài LMS. Do học sinh có điểm thi trên lớp khác biệt so với kết quả làm bài tập, kết quả dự báo này có thể kém chuẩn xác hơn so với phong độ thi thực tế.
                            </p>
                        </div>
                    </div>
                )}

                {/* THẺ TỔNG QUAN CHẨN ĐOÁN & BỘ LỌC CÂU HỎI */}
                <div className="p-5 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3 shrink-0">
                    <div className="grid grid-cols-3 gap-2.5">
                        <button
                            type="button"
                            onClick={() => setSelectedFilter(selectedFilter === "CRITICAL" ? "ALL" : "CRITICAL")}
                            className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                                selectedFilter === "CRITICAL"
                                    ? "bg-rose-50 dark:bg-rose-950/40 border-rose-300 dark:border-rose-700 shadow-xs"
                                    : "bg-slate-50/70 dark:bg-slate-800/40 border-slate-200/60 dark:border-slate-800 hover:border-rose-200"
                            }`}
                        >
                            <div className="flex items-center justify-between text-xs text-rose-600 dark:text-rose-400 font-semibold">
                                <span className="flex items-center gap-1.5">
                                    <AlertCircle className="w-3.5 h-3.5" />
                                    <span>Nguy cơ mất điểm</span>
                                </span>
                                <span className="font-bold text-base font-mono">{stats.critical}</span>
                            </div>
                            <p className="text-[11px] text-slate-400 mt-1">LMS &lt; 5.0 điểm (Cần ôn gấp)</p>
                        </button>

                        <button
                            type="button"
                            onClick={() => setSelectedFilter(selectedFilter === "WARNING" ? "ALL" : "WARNING")}
                            className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                                selectedFilter === "WARNING"
                                    ? "bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-700 shadow-xs"
                                    : "bg-slate-50/70 dark:bg-slate-800/40 border-slate-200/60 dark:border-slate-800 hover:border-amber-200"
                            }`}
                        >
                            <div className="flex items-center justify-between text-xs text-amber-600 dark:text-amber-400 font-semibold">
                                <span className="flex items-center gap-1.5">
                                    <AlertTriangle className="w-3.5 h-3.5" />
                                    <span>Cần củng cố</span>
                                </span>
                                <span className="font-bold text-base font-mono">{stats.warning}</span>
                            </div>
                            <p className="text-[11px] text-slate-400 mt-1">LMS 5.0 – 6.9 điểm</p>
                        </button>

                        <button
                            type="button"
                            onClick={() => setSelectedFilter(selectedFilter === "SAFE" ? "ALL" : "SAFE")}
                            className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                                selectedFilter === "SAFE"
                                    ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-700 shadow-xs"
                                    : "bg-slate-50/70 dark:bg-slate-800/40 border-slate-200/60 dark:border-slate-800 hover:border-emerald-200"
                            }`}
                        >
                            <div className="flex items-center justify-between text-xs text-emerald-600 dark:text-emerald-400 font-semibold">
                                <span className="flex items-center gap-1.5">
                                    <CheckCircle2 className="w-3.5 h-3.5" />
                                    <span>Nắm vững</span>
                                </span>
                                <span className="font-bold text-base font-mono">{stats.safe}</span>
                            </div>
                            <p className="text-[11px] text-slate-400 mt-1">LMS &ge; 7.0 điểm</p>
                        </button>
                    </div>

                    <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
                        <span className="font-medium flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
                            <Filter className="w-3.5 h-3.5 text-brand-600" />
                            <span>Hiển thị {filteredQuestions.length} / {groupedQuestions.length} câu hỏi</span>
                        </span>
                        {selectedFilter !== "ALL" && (
                            <button
                                type="button"
                                onClick={() => setSelectedFilter("ALL")}
                                className="text-xs text-brand-600 hover:text-brand-700 font-semibold underline cursor-pointer"
                            >
                                Xem tất cả các câu
                            </button>
                        )}
                    </div>
                </div>

                {/* DANH SÁCH TỪNG CÂU HỎI ĐỐI CHIẾU NĂNG LỰC */}
                <div className="flex-1 overflow-y-auto p-5 space-y-4">
                    {filteredQuestions.length === 0 ? (
                        <div className="text-center py-12 text-sm text-slate-400 space-y-1">
                            <p className="font-semibold text-slate-600 dark:text-slate-300">Không có câu hỏi nào theo bộ lọc đã chọn</p>
                            <p className="text-xs">Bấm "Xem tất cả các câu" để theo dõi toàn bộ đề thi.</p>
                        </div>
                    ) : (
                        filteredQuestions.map((q) => {
                            const isSingle = q.subItems.length <= 1;

                            // Badge trạng thái của toàn câu
                            const qStatusBadge =
                                q.riskStatus === "CRITICAL"
                                    ? { label: "Nguy cơ mất điểm", cls: "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border-rose-200 dark:border-rose-800", icon: AlertCircle }
                                    : q.riskStatus === "WARNING"
                                    ? { label: "Cần củng cố", cls: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border-amber-200 dark:border-amber-800", icon: AlertTriangle }
                                    : q.riskStatus === "SAFE"
                                    ? { label: "Dự kiến làm tốt", cls: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800", icon: CheckCircle2 }
                                    : { label: "Chưa có LMS", cls: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border-slate-200 dark:border-slate-700", icon: Info };

                            const StatusIcon = qStatusBadge.icon;

                            return (
                                <div
                                    key={q.questionNumber}
                                    className={`p-4 rounded-2xl border transition-all space-y-3.5 ${
                                        q.riskStatus === "CRITICAL"
                                            ? "bg-rose-50/20 dark:bg-rose-950/10 border-rose-200/80 dark:border-rose-900/40"
                                            : q.riskStatus === "WARNING"
                                            ? "bg-amber-50/20 dark:bg-amber-950/10 border-amber-200/80 dark:border-amber-900/40"
                                            : "bg-white dark:bg-slate-800/60 border-slate-200/80 dark:border-slate-700"
                                    }`}
                                >
                                    {/* HÀNG TIÊU ĐỀ CÂU HỎI */}
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="flex items-start gap-2.5 flex-1 min-w-0">
                                            <span className="w-7 h-7 rounded-xl bg-slate-100 dark:bg-slate-700 text-slate-800 dark:text-slate-200 font-black text-xs flex items-center justify-center shrink-0 mt-0.5">
                                                #{q.questionNumber}
                                            </span>
                                            <div className="space-y-1.5 min-w-0 flex-1">
                                                <p className="font-semibold text-sm text-slate-900 dark:text-white leading-snug">
                                                    {q.questionText}
                                                </p>
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold border ${BLOOM_COLORS[q.bloom_level]}`}>
                                                        Bloom {q.bloom_level} · {BLOOM_LABELS[q.bloom_level] ?? ""}
                                                    </span>
                                                    {q.has_figure && (
                                                        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                                                            Hình vẽ / Đồ thị
                                                        </span>
                                                    )}
                                                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold border ${qStatusBadge.cls}`}>
                                                        <StatusIcon className="w-3 h-3 shrink-0" />
                                                        <span>{qStatusBadge.label}</span>
                                                    </span>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="text-right shrink-0">
                                            <span className="text-[10px] text-slate-400 block">Trọng số đề:</span>
                                            <span className="font-black text-xs text-brand-600 dark:text-brand-400 font-mono">
                                                {(q.totalWeight * 100).toFixed(1)}% điểm
                                            </span>
                                        </div>
                                    </div>

                                    {/* ẢNH TRÍCH XUẤT TỪ ĐỀ GỐC NẾU CÓ */}
                                    {q.image_url && q.has_figure && (
                                        <div className="rounded-xl overflow-hidden border border-slate-200/80 dark:border-slate-700 bg-slate-50/70 dark:bg-slate-900/60 p-2.5 space-y-2">
                                            <div className="flex items-center justify-between text-[11px] text-slate-500 font-medium">
                                                <span className="flex items-center gap-1.5 text-brand-600 dark:text-brand-400 font-semibold">
                                                    <ImageIcon className="w-3.5 h-3.5" />
                                                    <span>Hình vẽ đề gốc</span>
                                                </span>
                                                <button
                                                    type="button"
                                                    onClick={() => setSelectedImageModal({ url: q.image_url!, title: `Câu #${q.questionNumber}` })}
                                                    className="inline-flex items-center gap-1 text-slate-500 hover:text-brand-600 font-medium transition-colors cursor-pointer"
                                                >
                                                    <ZoomIn className="w-3.5 h-3.5" />
                                                    <span>Phóng to</span>
                                                </button>
                                            </div>
                                            <div
                                                onClick={() => setSelectedImageModal({ url: q.image_url!, title: `Câu #${q.questionNumber}` })}
                                                className="cursor-pointer group relative rounded-lg overflow-hidden border border-slate-200/60 dark:border-slate-800 max-h-40 bg-white dark:bg-slate-950 flex items-center justify-center p-1"
                                            >
                                                <img
                                                    src={q.image_url}
                                                    alt={`Câu #${q.questionNumber}`}
                                                    className="max-h-36 w-auto object-contain transition-transform group-hover:scale-[1.02]"
                                                />
                                            </div>
                                        </div>
                                    )}

                                    {/* KHỐI ĐỐI CHIẾU NĂNG LỰC LMS TỪNG BÀI HỌC CỦA CÂU */}
                                    <div className="space-y-2 pt-1">
                                        {q.subItems.map((sub, idx) => {
                                            const uId = sub.node_ref?.node_id;
                                            const ab = uId ? unitAbilities[uId] : null;
                                            const isPrimary = sub.is_primary ?? (idx === 0 || (sub.question_share ?? 0) >= 0.5);

                                            const subAbilityBadge =
                                                ab === null || ab === undefined
                                                    ? { label: "Chưa có dữ liệu LMS", cls: "bg-slate-100 text-slate-600 border-slate-200", barColor: "#94a3b8" }
                                                    : ab >= 7.0
                                                    ? { label: `Nắm vững (${ab.toFixed(1)}/10)`, cls: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800", barColor: "#16a34a" }
                                                    : ab >= 5.0
                                                    ? { label: `Cần củng cố (${ab.toFixed(1)}/10)`, cls: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800", barColor: "#ea580c" }
                                                    : { label: `Hổng kiến thức (${ab.toFixed(1)}/10)`, cls: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800", barColor: "#e11d48" };

                                            return (
                                                <div
                                                    key={idx}
                                                    className="p-3 rounded-xl bg-slate-50/90 dark:bg-slate-800/80 border border-slate-200/70 dark:border-slate-700 space-y-2"
                                                >
                                                    <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
                                                        <div className="flex items-center gap-2 min-w-0 flex-1">
                                                            <BookOpen className="w-3.5 h-3.5 text-brand-600 shrink-0" />
                                                            <span className="font-semibold text-slate-800 dark:text-slate-200 truncate">
                                                                {sub.unit_name ?? sub.topic}
                                                            </span>
                                                            {!isSingle && (
                                                                <span className="inline-flex items-center gap-1 text-[10px] font-bold text-slate-500">
                                                                    {isPrimary ? <Target className="w-3 h-3 text-brand-600" /> : <Layers className="w-3 h-3 text-slate-400" />}
                                                                    <span>{isPrimary ? "Trọng tâm" : "Tích hợp"}</span>
                                                                </span>
                                                            )}
                                                        </div>

                                                        <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold border ${subAbilityBadge.cls}`}>
                                                            {subAbilityBadge.label}
                                                        </span>
                                                    </div>

                                                    {/* Thanh năng lực LMS */}
                                                    {ab !== null && ab !== undefined && (
                                                        <div className="space-y-1">
                                                            <div className="h-1.5 w-full rounded-full bg-slate-200/80 dark:bg-slate-700/80 overflow-hidden">
                                                                <div
                                                                    className="h-full rounded-full transition-all duration-500"
                                                                    style={{
                                                                        width: `${Math.min(100, Math.max(0, ab * 10))}%`,
                                                                        backgroundColor: subAbilityBadge.barColor,
                                                                    }}
                                                                />
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* FOOTER LỜI KHUYÊN SƯ PHẠM */}
                <div className="p-4 bg-slate-50 dark:bg-slate-950/60 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
                        <Lightbulb className="w-4 h-4 text-amber-500 shrink-0" />
                        <span>
                            {stats.critical > 0
                                ? `Học sinh có ${stats.critical} câu hỏi nguy cơ mất điểm cao — cần ưu tiên giao bài tập luyện tập các bài này.`
                                : "Năng lực LMS của học sinh đáp ứng tốt hầu hết các câu trong đề thi."}
                        </span>
                    </div>
                    <button
                        onClick={onClose}
                        className="px-4 py-2 rounded-xl bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 font-semibold text-slate-700 dark:text-slate-200 transition-colors shrink-0"
                    >
                        Đóng
                    </button>
                </div>
            </div>

            {/* Modal phóng to ảnh đề */}
            {selectedImageModal && (
                <div
                    className="fixed inset-0 z-60 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
                    onClick={() => setSelectedImageModal(null)}
                >
                    <div className="relative max-w-4xl w-full bg-white dark:bg-slate-900 rounded-2xl p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-between border-b pb-2">
                            <h4 className="font-bold text-sm text-slate-900 dark:text-white">{selectedImageModal.title}</h4>
                            <button onClick={() => setSelectedImageModal(null)} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
                                <X className="w-5 h-5 text-slate-500" />
                            </button>
                        </div>
                        <div className="max-h-[75vh] overflow-auto flex items-center justify-center">
                            <img src={selectedImageModal.url} alt={selectedImageModal.title} className="max-h-[70vh] w-auto object-contain rounded-lg" />
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
