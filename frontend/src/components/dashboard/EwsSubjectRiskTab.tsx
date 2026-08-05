"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { LoadingState } from "@/components/Loading";
import EwsSubjectRiskDrilldownCard from "@/components/dashboard/EwsSubjectRiskDrilldownCard";
import { type EwsMeta } from "@/lib/types";

interface EwsSubjectRiskTabProps {
    modelVersion: string;
    refreshKey: number;
}

export default function EwsSubjectRiskTab({ modelVersion, refreshKey }: EwsSubjectRiskTabProps) {
    const [meta, setMeta] = useState<EwsMeta | null>(null);
    const [loadingMeta, setLoadingMeta] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Filter States
    const [schoolYearId, setSchoolYearId] = useState<number>(2025);
    const [semesterIndex, setSemesterIndex] = useState<number>(1);
    const [week, setWeek] = useState<number>(8);

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

    if (loadingMeta) {
        return <LoadingState message="Đang tải dữ liệu phân tích rủi ro theo môn học..." />;
    }

    return (
        <div className="space-y-6">
            {error && (
                <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 rounded-xl text-sm flex items-center gap-2">
                    <span>⚠️ {error}</span>
                </div>
            )}

            {/* Mốc đánh giá */}
            {meta && meta.weeks.length > 0 && (
                <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200 border-b border-slate-100 dark:border-slate-800 pb-3">
                        <span>🗓️</span>
                        <span>Mốc Đánh Giá</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {/* Mốc Tuần / Học Kỳ */}
                        <div className="space-y-1">
                            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Mốc Đánh Giá (Tuần / Kỳ)</label>
                            <select
                                value={`${schoolYearId}-${semesterIndex}-${week}`}
                                onChange={(e) => {
                                    const [sy, sem, wk] = e.target.value.split("-").map(Number);
                                    setSchoolYearId(sy);
                                    setSemesterIndex(sem);
                                    setWeek(wk);
                                }}
                                className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500"
                            >
                                {meta.weeks.map((w, idx) => (
                                    <option key={idx} value={`${w.school_year_id}-${w.semester_index}-${w.evaluated_at_week}`}>
                                        {w.school_year_name || `Năm ${w.school_year_id}`} - Học kỳ {w.semester_index} (Mốc Tuần {w.evaluated_at_week})
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                </div>
            )}

            {/* Drill-down card */}
            <EwsSubjectRiskDrilldownCard
                key={`${schoolYearId}-${semesterIndex}-${week}-${modelVersion}-${refreshKey}`}
                schoolYearId={schoolYearId}
                semesterIndex={semesterIndex}
                week={week}
                modelVersion={modelVersion}
            />
        </div>
    );
}