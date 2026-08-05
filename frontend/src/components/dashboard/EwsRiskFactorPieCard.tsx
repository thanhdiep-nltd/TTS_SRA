"use client";

import { PieChart, Pie, Cell, Tooltip as RechartsTooltip, ResponsiveContainer } from "recharts";
import { AlertTriangle } from "lucide-react";

// Nhóm cờ nguyên nhân → 4 nhóm yếu tố chính (khớp phân nhóm trong UI & RISK_FACTOR_CONDITIONS backend)
const FACTOR_GROUP_BY_CODE: Record<string, string> = {
    // Điểm số
    SLOPE_DOWN: "Điểm số",
    LAST_SCORE_LOW: "Điểm số",
    SCORE_VOLATILE: "Điểm số",
    MAX_DROP_HIGH: "Điểm số",
    HIGH_WEIGHT_FAIL: "Điểm số",
    // LMS
    LMS_LOW_SUBMISSION: "LMS",
    LMS_LOW_SCORE: "LMS",
    LMS_DROP: "LMS",
    LMS_GAP: "LMS",
    // Chuyên cần
    ABSENTEEISM: "Chuyên cần",
    UNEXCUSED_ABSENT: "Chuyên cần",
    LATE_MANY: "Chuyên cần",
    // Hạnh kiểm
    DEMERIT_HIGH: "Hạnh kiểm",
    REPEAT_OFFENSE: "Hạnh kiểm",
    SEVERE_SANCTION: "Hạnh kiểm",
};

// Thứ tự & màu cho 4 nhóm chính
const GROUP_ORDER = ["Điểm số", "LMS", "Chuyên cần", "Hạnh kiểm"];
const GROUP_COLORS: Record<string, string> = {
    "Điểm số": "#ef4444",
    "LMS": "#3b82f6",
    "Chuyên cần": "#10b981",
    "Hạnh kiểm": "#d946ef",
};

interface EwsRiskFactorPieCardProps {
    factors: Array<{ code: string; label: string; cnt: number }>;
    loading: boolean;
}

export default function EwsRiskFactorPieCard({ factors, loading }: EwsRiskFactorPieCardProps) {
    // Nhóm các cờ nguyên nhân thành 4 nhóm yếu tố chính
    const groupTotals: Record<string, number> = {};
    for (const f of factors) {
        const group = FACTOR_GROUP_BY_CODE[f.code] || "Khác";
        groupTotals[group] = (groupTotals[group] || 0) + f.cnt;
    }

    const data = GROUP_ORDER.filter((g) => (groupTotals[g] || 0) > 0).map((g) => ({
        name: g,
        value: groupTotals[g],
        color: GROUP_COLORS[g] || "#94a3b8",
    }));

    const total = data.reduce((sum, d) => sum + d.value, 0);

    return (
        <div className="bg-white dark:bg-slate-900 p-4 sm:p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3.5">
            {/* HEADER SECTION */}
            <div className="flex items-start justify-between gap-3">
                <div className="space-y-0.5">
                    <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                        Yếu Tố Gây Rủi Ro Cao Nhất
                    </h3>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight">
                        Phân bố theo nhóm yếu tố trên học sinh HIGH + CRITICAL.
                    </p>
                </div>
                <div className="p-1.5 bg-rose-500/10 text-rose-500 rounded-lg flex-shrink-0">
                    <AlertTriangle className="w-5 h-5 stroke-[2.2]" />
                </div>
            </div>

            {loading ? (
                <div className="py-12 flex items-center justify-center text-slate-400">
                    <span className="animate-pulse">Đang tải...</span>
                </div>
            ) : data.length === 0 ? (
                <p className="text-xs text-slate-400 py-6 text-center">Không có dữ liệu yếu tố rủi ro</p>
            ) : (
                <div className="space-y-4">
                    {/* PIE CHART */}
                    <div className="h-48 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={data}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={42}
                                    outerRadius={70}
                                    paddingAngle={3}
                                    dataKey="value"
                                    label={({ name, percent }: any) => `${(percent * 100).toFixed(0)}%`}
                                    labelLine={false}
                                >
                                    {data.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Pie>
                                <RechartsTooltip
                                    formatter={(val: any, name: any) => [`${val} lượt`, name]}
                                    contentStyle={{ borderRadius: "12px", fontSize: "12px" }}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>

                    {/* TOP 3 SUMMARY */}
                    <div className="space-y-1.5">
                        {data.map((d) => (
                            <div key={d.name} className="flex items-center justify-between text-xs">
                                <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
                                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
                                    {d.name}
                                </span>
                                <span className="font-semibold text-slate-800 dark:text-slate-100">
                                    {d.value.toLocaleString()} <span className="text-slate-400 font-normal">({total > 0 ? ((d.value / total) * 100).toFixed(1) : 0}%)</span>
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}