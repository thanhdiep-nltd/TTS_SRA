"use client";

import { useEffect, useState } from "react";
import { Award, Loader2, X } from "lucide-react";

import { api } from "@/lib/api";
import {
    EWS_RISK_COLORS,
    EWS_RISK_LABELS,
    type EwsGoldenSetCase,
    type EwsGoldenSetResult,
    type EwsRiskLevel,
} from "@/lib/types";

// Nhãn tiếng Việt cho 24 thông số đầu vào (khớp bảng dự báo phía trên)
const FEATURE_LABELS: Record<string, string> = {
    // Điểm số
    weighted_early_avg: "ĐTB Nửa Đầu Kỳ",
    weighted_late_avg: "ĐTB Nửa Sau Kỳ",
    score_slope: "Xu Hướng (Slope)",
    score_volatility: "Độ Biến Động (Volatility)",
    max_drop: "Tụt Điểm Lớn Nhất",
    last_score: "Điểm Thi Mới Nhất",
    max_coefficient_so_far: "Hệ Số Cao Nhất",
    high_weight_score_count: "Số Bài Hệ Số Lớn",
    last_high_weight_score: "Điểm Hệ Số Lớn Cuối",
    // LMS
    lms_avg_score: "ĐTB LMS",
    lms_recent_drop: "Điểm LMS Suy Giảm",
    lms_submission_rate: "Tỷ Lệ Nộp Bài LMS",
    lms_recent_submission_rate: "Tỷ Lệ Nộp Bài LMS Gần Đây",
    lms_gradebook_gap: "Lệch Điểm LMS",
    // Chuyên cần
    daily_absence_rate: "Tỷ Lệ Vắng Học",
    unexcused_absent_rate: "Tỷ Lệ Nghỉ Không Phép",
    excused_absent_days: "Số Ngày Nghỉ Có Phép",
    total_late_count: "Số Lần Đi Muộn",
    // Hạnh kiểm
    total_demerit_points: "Tổng Điểm Trừ Hạnh Kiểm",
    repeat_offense_count: "Số Lần Tái Phạm",
    severe_sanction_count: "Số Lần Kỷ Luật Nặng",
    // Context
    subject_id: "Môn Học",
    subject_category: "Nhóm Môn",
    grade_level: "Khối Lớp",
};

export default function EwsGoldenSetTab() {
    const [goldenSet, setGoldenSet] = useState<EwsGoldenSetResult | null>(null);
    const [selectedGoldenCase, setSelectedGoldenCase] = useState<EwsGoldenSetCase | null>(null);
    const [loadingGoldenSet, setLoadingGoldenSet] = useState(true);

    // Golden set: bộ test chuẩn để kiểm chứng độ chính xác của mô hình (demo)
    useEffect(() => {
        let isMounted = true;
        setLoadingGoldenSet(true);
        api
            .get<EwsGoldenSetResult>("/ews/golden-set")
            .then((res) => {
                if (!isMounted) return;
                setGoldenSet(res);
            })
            .catch(() => {
                if (!isMounted) return;
                setGoldenSet(null);
            })
            .finally(() => {
                if (isMounted) setLoadingGoldenSet(false);
            });
        return () => {
            isMounted = false;
        };
    }, []);

    return (
        <div className="space-y-6">
            {/* GOLDEN SET — BỘ TEST CHUẨN KIỂM CHỨNG MÔ HÌNH (DEMO) */}
            <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                        <Award className="w-5 h-5 text-emerald-500" />
                        <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                            Golden Set — Kiểm Chứng Độ Chính Xác Mô Hình
                        </h4>
                    </div>
                    {goldenSet && (
                        <div className="flex items-center gap-3 text-xs">
                            <span className="px-3 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-medium">
                                {goldenSet.passed}/{goldenSet.total} case đúng
                            </span>
                            <span
                                className={`px-3 py-1 rounded-lg font-bold ${goldenSet.accuracy >= 0.8
                                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                                    : goldenSet.accuracy >= 0.6
                                        ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                                        : "bg-red-500/10 text-red-600 dark:text-red-400"
                                    }`}
                            >
                                Độ chính xác: {(goldenSet.accuracy * 100).toFixed(1)}%
                            </span>
                        </div>
                    )}
                </div>

                <p className="text-xs text-slate-500 dark:text-slate-400">
                    Bộ 8 tình huống chuẩn (học giỏi + nghỉ nhiều, học yếu, hạnh kiểm kém, ...) chạy qua đúng pipeline dự báo thật để
                    đối chiếu với kỳ vọng (ground truth) — dùng để demo độ hiệu quả của mô hình.
                </p>

                {loadingGoldenSet ? (
                    <div className="flex items-center justify-center py-8 text-slate-400">
                        <Loader2 className="w-5 h-5 animate-spin" />
                    </div>
                ) : !goldenSet ? (
                    <div className="py-6 text-center text-sm text-slate-400">
                        Không tải được dữ liệu golden set (có thể backend chưa khởi động hoặc thiếu model).
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                            <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-200 dark:border-slate-700">
                                <tr>
                                    <th className="py-2.5 px-3">Case</th>
                                    <th className="py-2.5 px-3">Tình huống</th>
                                    <th className="py-2.5 px-3 text-center">Điểm Rủi Ro</th>
                                    <th className="py-2.5 px-3 text-center">Dự Báo</th>
                                    <th className="py-2.5 px-3 text-center">Kỳ Vọng</th>
                                    <th className="py-2.5 px-3 text-center">Kết Quả</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                {goldenSet.cases.map((c) => (
                                    <tr
                                        key={c.id}
                                        onClick={() => setSelectedGoldenCase(c)}
                                        className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer"
                                        title="Bấm để xem chi tiết 24 thông số đầu vào"
                                    >
                                        <td className="py-2.5 px-3 font-mono font-semibold text-slate-700 dark:text-slate-300">{c.id}</td>
                                        <td className="py-2.5 px-3 text-slate-600 dark:text-slate-300">
                                            {c.description}
                                            <span className="ml-2 text-[10px] text-indigo-500 dark:text-indigo-400 font-medium">👁 Xem chi tiết</span>
                                        </td>
                                        <td className="py-2.5 px-3 text-center font-semibold text-slate-700 dark:text-slate-200">
                                            {c.risk_score.toFixed(1)}
                                        </td>
                                        <td className="py-2.5 px-3 text-center">
                                            <span
                                                className="px-2 py-0.5 rounded-md text-[11px] font-semibold"
                                                style={{
                                                    backgroundColor: `${EWS_RISK_COLORS[c.predicted as EwsRiskLevel]}22`,
                                                    color: EWS_RISK_COLORS[c.predicted as EwsRiskLevel],
                                                }}
                                            >
                                                {EWS_RISK_LABELS[c.predicted as EwsRiskLevel] || c.predicted}
                                            </span>
                                        </td>
                                        <td className="py-2.5 px-3 text-center">
                                            <span
                                                className="px-2 py-0.5 rounded-md text-[11px] font-semibold"
                                                style={{
                                                    backgroundColor: `${EWS_RISK_COLORS[c.expected as EwsRiskLevel]}22`,
                                                    color: EWS_RISK_COLORS[c.expected as EwsRiskLevel],
                                                }}
                                            >
                                                {EWS_RISK_LABELS[c.expected as EwsRiskLevel] || c.expected}
                                            </span>
                                        </td>
                                        <td className="py-2.5 px-3 text-center">
                                            {c.passed ? (
                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[11px] font-bold">
                                                    ✓ PASS
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-red-500/10 text-red-600 dark:text-red-400 text-[11px] font-bold">
                                                    ✗ FAIL
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

            {/* GOLDEN SET CASE DETAIL MODAL */}
            {selectedGoldenCase && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
                    onClick={() => setSelectedGoldenCase(null)}
                >
                    <div
                        className="bg-white dark:bg-slate-900 w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl border border-slate-200 dark:border-slate-700 shadow-2xl"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="sticky top-0 bg-white dark:bg-slate-900 border-b border-slate-100 dark:border-slate-800 px-5 py-4 flex items-start justify-between gap-3">
                            <div>
                                <div className="flex items-center gap-2">
                                    <span className="font-mono font-bold text-slate-800 dark:text-slate-100">{selectedGoldenCase.id}</span>
                                    <span
                                        className={`px-2 py-0.5 rounded-md text-[11px] font-bold ${selectedGoldenCase.passed
                                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                                            : "bg-red-500/10 text-red-600 dark:text-red-400"
                                            }`}
                                    >
                                        {selectedGoldenCase.passed ? "✓ PASS" : "✗ FAIL"}
                                    </span>
                                </div>
                                <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">{selectedGoldenCase.description}</p>
                            </div>
                            <button
                                onClick={() => setSelectedGoldenCase(null)}
                                className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="p-5 space-y-5">
                            {/* Kết quả dự báo */}
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60">
                                    <p className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Điểm Rủi Ro</p>
                                    <p className="text-lg font-bold text-slate-800 dark:text-slate-100">{selectedGoldenCase.risk_score.toFixed(1)}</p>
                                </div>
                                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60">
                                    <p className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Dự Báo</p>
                                    <p
                                        className="text-lg font-bold"
                                        style={{ color: EWS_RISK_COLORS[selectedGoldenCase.predicted as EwsRiskLevel] }}
                                    >
                                        {EWS_RISK_LABELS[selectedGoldenCase.predicted as EwsRiskLevel] || selectedGoldenCase.predicted}
                                    </p>
                                </div>
                                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60">
                                    <p className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Kỳ Vọng</p>
                                    <p
                                        className="text-lg font-bold"
                                        style={{ color: EWS_RISK_COLORS[selectedGoldenCase.expected as EwsRiskLevel] }}
                                    >
                                        {EWS_RISK_LABELS[selectedGoldenCase.expected as EwsRiskLevel] || selectedGoldenCase.expected}
                                    </p>
                                </div>
                                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60">
                                    <p className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Trọng số Hành vi</p>
                                    <p className="text-lg font-bold text-slate-800 dark:text-slate-100">
                                        {selectedGoldenCase.weight_behavior !== null ? selectedGoldenCase.weight_behavior.toFixed(3) : "—"}
                                    </p>
                                </div>
                            </div>

                            {/* Sub-scores theo yếu tố */}
                            <div>
                                <h5 className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-2">Điểm Rủi Ro Theo Yếu Tố (Thang 0 - 100%)</h5>
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                                    {[
                                        { label: "Điểm số", val: selectedGoldenCase.score_risk },
                                        { label: "LMS", val: selectedGoldenCase.lms_risk },
                                        { label: "Chuyên cần", val: selectedGoldenCase.attendance_risk },
                                        { label: "Hạnh kiểm", val: selectedGoldenCase.behavior_risk },
                                    ].map((f) => {
                                        const v = f.val;
                                        const isHigh = v !== null && v >= 60;
                                        const isMod = v !== null && v >= 30;
                                        return (
                                            <div key={f.label} className="p-2.5 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30">
                                                <p className="text-slate-400 font-medium text-[11px]">{f.label}</p>
                                                <div className="flex items-baseline gap-1 mt-0.5">
                                                    <span
                                                        className={`text-base font-bold ${v === null
                                                            ? "text-slate-400"
                                                            : isHigh
                                                                ? "text-red-500"
                                                                : isMod
                                                                    ? "text-amber-500"
                                                                    : "text-emerald-600 dark:text-emerald-400"
                                                            }`}
                                                    >
                                                        {v !== null ? v.toFixed(1) : "—"}
                                                    </span>
                                                    {v !== null && <span className="text-[10px] text-slate-400 font-normal">/100</span>}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* 24 thông số đầu vào */}
                            <div>
                                <h5 className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-2">
                                    Bộ {Object.keys(selectedGoldenCase.features || {}).length} Thông Số Đầu Vào
                                </h5>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5">
                                    {Object.entries(selectedGoldenCase.features || {}).map(([k, v]) => (
                                        <div key={k} className="flex items-center justify-between text-xs py-0.5 border-b border-slate-50 dark:border-slate-800/60">
                                            <span className="text-slate-500 dark:text-slate-400">{FEATURE_LABELS[k] || k}</span>
                                            <span className="font-semibold text-slate-700 dark:text-slate-200">
                                                {v !== null ? v : <span className="text-slate-400">—</span>}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}