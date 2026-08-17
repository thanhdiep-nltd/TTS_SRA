"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import SearchableSelect from "@/components/SearchableSelect";
import { api } from "@/lib/api";
import { PassFailForecastResult } from "@/lib/types";

export default function PassFailForecastPage() {
    const [subjects, setSubjects] = useState<{ id: string; name: string }[]>([]);
    const [subjectId, setSubjectId] = useState<string>("");
    const [gradeLevel, setGradeLevel] = useState<string>("");
    const [semester, setSemester] = useState<string>("1");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<PassFailForecastResult | null>(null);

    // Load subjects từ /ews/meta (lọc duy nhất theo name)
    useEffect(() => {
        api
            .get<{ subjects: { id: number; name: string }[] }>("/ews/meta")
            .then((meta) => {
                const seen = new Map<string, string>();
                for (const s of meta.subjects) {
                    if (!seen.has(s.name)) seen.set(s.name, String(s.id));
                }
                setSubjects(Array.from(seen, ([name, id]) => ({ id, name })));
            })
            .catch(() => setError("Không tải được danh sách môn học."));
    }, []);

    const runForecast = useCallback(async () => {
        if (!subjectId) return;
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            const params = new URLSearchParams({
                subject_id: subjectId,
                semester_index: semester,
            });
            if (gradeLevel) params.append("grade_id", gradeLevel);

            const data = await api.get<PassFailForecastResult>(
                `/pass-fail-forecast/by-subject?${params.toString()}`
            );
            setResult(data);
        } catch (e: any) {
            setError(e?.message ?? "Lỗi khi tải dự đoán pass/fail.");
        } finally {
            setLoading(false);
        }
    }, [subjectId, gradeLevel, semester]);

    // Grade level options
    const gradeOptions = Array.from({ length: 7 }, (_, i) => String(i + 6)); // 6..12

    return (
        <div className="p-6 md:p-8 max-w-[1500px] mx-auto space-y-5">
            <header>
                <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
                    Dự đoán Pass / Fail đề cuối kỳ
                </h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                    GV bỏ đề cuối kỳ (đã map chuẩn chương trình) → dự đoán bao nhiêu học sinh trượt/pass.
                </p>
            </header>

            {/* Filter card */}
            <div className="bg-white dark:bg-slate-900 border rounded-2xl p-4 flex flex-wrap items-end gap-3 shadow-sm">
                <div className="min-w-[180px]">
                    <label className="text-xs font-semibold text-slate-500 mb-1 block">Môn học</label>
                    <SearchableSelect
                        options={subjects.map((s) => ({ value: s.id, label: s.name }))}
                        value={subjectId}
                        onChange={setSubjectId}
                        placeholder="Chọn môn..."
                        className="min-w-[180px]"
                    />
                </div>
                <div className="min-w-[120px]">
                    <label className="text-xs font-semibold text-slate-500 mb-1 block">Khối</label>
                    <SearchableSelect
                        options={gradeOptions.map((g) => ({ value: g, label: `Khối ${g}` }))}
                        value={gradeLevel}
                        onChange={setGradeLevel}
                        className="min-w-[120px]"
                    />
                </div>
                <div className="min-w-[120px]">
                    <label className="text-xs font-semibold text-slate-500 mb-1 block">Học kỳ</label>
                    <SearchableSelect
                        options={[
                            { value: "1", label: "HK1" },
                            { value: "2", label: "HK2" },
                        ]}
                        value={semester}
                        onChange={setSemester}
                        className="min-w-[120px]"
                    />
                </div>
                <button
                    onClick={runForecast}
                    disabled={loading || !subjectId}
                    className="px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50"
                >
                    {loading ? "Đang dự đoán..." : "Dự đoán"}
                </button>
            </div>

            {error && (
                <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 px-4 py-3 text-sm text-rose-700 dark:text-rose-300">
                    {error}
                </div>
            )}

            {result && (
                <section className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden">
                    <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 grid grid-cols-2 md:grid-cols-4 gap-4">
                        <Metric label="Tổng học sinh" value={String(result.total)} cls="text-slate-900 dark:text-slate-100" />
                        <Metric label="Dự kiến ĐẬU" value={String(result.pass_count)} cls="text-emerald-600" />
                        <Metric label="Dự kiến TRƯỢT" value={String(result.fail_count)} cls="text-rose-600" />
                        <Metric label="Ranh giới" value={String(result.borderline_count)} cls="text-amber-600" />
                    </div>
                    <div className="px-5 py-3 border-b border-slate-100 dark:border-slate-800">
                        <span className="text-xs text-slate-500">
                            Tỉ lệ trượt dự kiến:{" "}
                            <span className="font-semibold text-rose-600">{(result.fail_rate * 100).toFixed(1)}%</span>
                        </span>
                        {result.cdi !== null && (
                            <span className="text-xs text-slate-500 ml-4">
                                · Độ khó nội dung (CDI): <span className="font-semibold">{result.cdi.toFixed(2)}</span>
                            </span>
                        )}
                    </div>
                    {result.students.length > 0 ? (
                        <StudentTable students={result.students} />
                    ) : (
                        <div className="px-5 py-8 text-center text-sm text-slate-400">Chưa có dữ liệu học sinh.</div>
                    )}
                </section>
            )}
        </div>
    );
}

function Metric({ label, value, cls }: { label: string; value: string; cls: string }) {
    return (
        <div>
            <p className="text-xs text-slate-500">{label}</p>
            <p className={`text-2xl font-bold ${cls}`}>{value}</p>
        </div>
    );
}

function StudentTable({ students }: { students: PassFailForecastResult["students"] }) {
    return (
        <div className="max-h-[400px] overflow-auto">
            <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white dark:bg-slate-900">
                    <tr className="text-left text-xs text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800">
                        <th className="px-5 py-3">Học sinh</th>
                        <th className="px-5 py-3">Điểm dự kiến</th>
                        <th className="px-5 py-3">Kết quả</th>
                    </tr>
                </thead>
                <tbody>
                    {students.map((s) => {
                        const verdictCls =
                            s.verdict === "PASS"
                                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
                                : s.verdict === "FAIL"
                                    ? "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300"
                                    : "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300";
                        const verdictLabel =
                            s.verdict === "PASS" ? "ĐẬU" : s.verdict === "FAIL" ? "TRƯỢT" : "Ranh giới";
                        return (
                            <tr
                                key={s.student_code}
                                className="border-b border-slate-50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                            >
                                <td className="px-5 py-2.5 font-medium text-slate-800 dark:text-slate-200">
                                    {s.student_name ?? s.student_code}
                                </td>
                                <td className="px-5 py-2.5 text-slate-600 dark:text-slate-300">{s.predicted_score.toFixed(2)}</td>
                                <td className="px-5 py-2.5">
                                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${verdictCls}`}>
                                        {verdictLabel}
                                    </span>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}