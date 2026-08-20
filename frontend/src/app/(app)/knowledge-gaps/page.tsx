"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import SearchableSelect from "@/components/SearchableSelect";
import { api } from "@/lib/api";
import {
    ClassKnowledgeGaps,
    StudentKnowledgeGaps,
    KnowledgeGapItem,
} from "@/lib/types";

// Label + màu cho mức hổng (gap_score 0..1)
function gapLevel(gap: number): { label: string; cls: string } {
    if (gap >= 0.7) return { label: "Nặng", cls: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300" };
    if (gap >= 0.4) return { label: "Trung bình", cls: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300" };
    return { label: "Nhẹ", cls: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300" };
}

// Badge độ tin cậy (confidence) — HIGH xanh, MEDIUM vàng, LOW đỏ, INSUFFICIENT xám
const CONFIDENCE_META: Record<string, { label: string; cls: string }> = {
    HIGH: { label: "Độ tin cậy cao", cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300" },
    MEDIUM: { label: "Độ tin cậy TB", cls: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300" },
    LOW: { label: "Độ tin cậy thấp", cls: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300" },
    INSUFFICIENT: { label: "Chưa đủ dữ liệu", cls: "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400" },
};

// Badge trạng thái đối soát (integrity) — cảnh báo gian lận/lười
const INTEGRITY_META: Record<string, { label: string; cls: string }> = {
    OK: { label: "Khớp với trên lớp", cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300" },
    SUSPECTED_CHEATING: { label: "Nghi gian lận", cls: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300" },
    LOW_ENGAGEMENT: { label: "Tham gia LMS thấp", cls: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300" },
    LMS_ONLY: { label: "Chỉ từ LMS", cls: "bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300" },
    FLAGGED: { label: "Cần kiểm chứng", cls: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300" },
};

export default function KnowledgeGapsPage() {
    const router = useRouter();
    const [subjects, setSubjects] = useState<{ id: string; name: string }[]>([]);
    const [classes, setClasses] = useState<{ id: string; name: string }[]>([]);
    const [students, setStudents] = useState<{ code: string; name: string }[]>([]);

    const [subjectId, setSubjectId] = useState<string>("");
    const [classId, setClassId] = useState<string>("");
    const [studentCode, setStudentCode] = useState<string>("");

    const [studentGaps, setStudentGaps] = useState<StudentKnowledgeGaps | null>(null);
    const [classGaps, setClassGaps] = useState<ClassKnowledgeGaps | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Load subjects từ s360.dim_subject (danh mục dùng chung) — /knowledge-gaps/subject-options
    useEffect(() => {
        api
            .get<{ id: number; name: string }[]>("/knowledge-gaps/subject-options")
            .then((list) => {
                setSubjects((list ?? []).map((s) => ({ id: String(s.id), name: s.name })));
            })
            .catch(() => setError("Không tải được danh sách môn học."));
    }, []);

    // Load classes từ s360 (dữ liệu thật: dim_homeroom_class) — /knowledge-gaps/class-options
    useEffect(() => {
        api
            .get<{ class_id: number; class_name: string }[]>("/knowledge-gaps/class-options")
            .then((list) => {
                setClasses((list ?? []).map((c) => ({ id: String(c.class_id), name: c.class_name })));
            })
            .catch(() => setError("Không tải được danh sách lớp."));
    }, []);

    // Load students of selected class (s360: dim_homeroom_class_student)
    useEffect(() => {
        if (!classId) {
            setStudents([]);
            return;
        }
        api
            .get<{ student_code: string; student_name: string }[]>(`/knowledge-gaps/classes/${classId}/students`)
            .then((res) => {
                setStudents((res ?? []).map((s) => ({ code: s.student_code, name: s.student_name })));
            })
            .catch(() => setStudents([]));
    }, [classId]);

    const runStudent = useCallback(async () => {
        if (!studentCode || !subjectId) return;
        setLoading(true);
        setError(null);
        try {
            const data = await api.get<StudentKnowledgeGaps>(
                `/knowledge-gaps/students/${studentCode}?subject_id=${subjectId}&semester_index=1`
            );
            setStudentGaps(data);
        } catch (e: any) {
            setError(e?.message ?? "Lỗi khi tải lỗ hổng kiến thức học sinh.");
        } finally {
            setLoading(false);
        }
    }, [studentCode, subjectId]);

    const runClass = useCallback(async () => {
        if (!classId || !subjectId) return;
        setLoading(true);
        setError(null);
        try {
            const data = await api.get<ClassKnowledgeGaps>(
                `/knowledge-gaps/classes/${classId}?subject_id=${subjectId}&semester_index=1`
            );
            setClassGaps(data);
        } catch (e: any) {
            setError(e?.message ?? "Lỗi khi tải lỗ hổng kiến thức lớp.");
        } finally {
            setLoading(false);
        }
    }, [classId, subjectId]);

    return (
        <div className="p-6 md:p-8 max-w-[1500px] mx-auto space-y-5">
            <header>
                <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">Lỗ hổng kiến thức</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                    Ước lượng mức độ thành thạo theo chương từ kết quả bài tập LMS (item-level) kết hợp đối soát
                    với điểm thi trên lớp để chống gian lận.
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
                <div className="min-w-[160px]">
                    <label className="text-xs font-semibold text-slate-500 mb-1 block">Lớp</label>
                    <SearchableSelect
                        options={classes.map((c) => ({ value: c.id, label: c.name }))}
                        value={classId}
                        onChange={setClassId}
                        placeholder="Chọn lớp..."
                        className="min-w-[160px]"
                    />
                </div>
                <div className="min-w-[200px]">
                    <label className="text-xs font-semibold text-slate-500 mb-1 block">Học sinh</label>
                    <SearchableSelect
                        options={students.map((s) => ({ value: s.code, label: `${s.code} — ${s.name}` }))}
                        value={studentCode}
                        onChange={setStudentCode}
                        placeholder="Chọn học sinh..."
                        className="min-w-[200px]"
                    />
                </div>
                <button
                    onClick={runStudent}
                    disabled={loading || !studentCode || !subjectId}
                    className="px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50"
                >
                    {loading ? "Đang tải..." : "Xem học sinh"}
                </button>
                <button
                    onClick={runClass}
                    disabled={loading || !classId || !subjectId}
                    className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 text-sm font-semibold hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50"
                >
                    {loading ? "Đang tải..." : "Xem cả lớp"}
                </button>
            </div>

            {error && (
                <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 px-4 py-3 text-sm text-rose-700 dark:text-rose-300">
                    {error}
                </div>
            )}

            {/* Student gaps */}
            {studentGaps && (
                <section className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden">
                    <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800">
                        <h3 className="font-semibold text-slate-900 dark:text-slate-100">
                            Lỗ hổng của học sinh <span className="text-brand-600">{studentGaps.student_code}</span>
                        </h3>
                        <p className="text-xs text-slate-500">
                            {studentGaps.gaps.length === 0
                                ? "Không có lỗ hổng đáng kể."
                                : `Tìm thấy ${studentGaps.gaps.length} đơn vị kiến thức hổng.`}
                        </p>
                    </div>
                    {studentGaps.gaps.length > 0 ? (
                        <GapTable gaps={studentGaps.gaps} />
                    ) : (
                        <div className="px-5 py-8 text-center text-sm text-slate-400">
                            Chưa đủ dữ liệu để đánh giá học sinh này ở môn đã chọn — cần điểm thi trên lớp
                            hoặc kết quả bài tập LMS đã map chương.
                        </div>
                    )}
                </section>
            )}

            {/* Class gaps */}
            {classGaps && (
                <section className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden">
                    <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800">
                        <h3 className="font-semibold text-slate-900 dark:text-slate-100">
                            Unit hổng phổ biến của lớp <span className="text-brand-600">{classGaps.class_id}</span>
                        </h3>
                        <p className="text-xs text-slate-500">
                            {classGaps.gaps.length === 0
                                ? "Chưa có dữ liệu."
                                : `${classGaps.gaps.length} đơn vị kiến thức hổng phổ biến.`}
                        </p>
                    </div>
                    {classGaps.gaps.length > 0 ? (
                        <GapTable gaps={classGaps.gaps} />
                    ) : (
                        <div className="px-5 py-8 text-center text-sm text-slate-400">
                            Chưa có dữ liệu lỗ hổng cho lớp này.
                        </div>
                    )}
                </section>
            )}
        </div>
    );
}

function GapTable({ gaps }: { gaps: KnowledgeGapItem[] }) {
    return (
        <table className="w-full text-sm">
            <thead>
                <tr className="text-left text-xs text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800">
                    <th className="px-5 py-3">Chương / Bài</th>
                    <th className="px-5 py-3">Mức hổng</th>
                    <th className="px-5 py-3">Thành thạo</th>
                    <th className="px-5 py-3">Độ tin cậy</th>
                    <th className="px-5 py-3">Đối soát</th>
                    <th className="px-5 py-3">Nguồn</th>
                </tr>
            </thead>
            <tbody>
                {gaps.map((g) => {
                    const lvl = gapLevel(g.gap_score);
                    const conf = CONFIDENCE_META[g.confidence ?? "LOW"] ?? CONFIDENCE_META.LOW;
                    const integ = INTEGRITY_META[g.integrity_status ?? "OK"] ?? INTEGRITY_META.OK;
                    return (
                        <tr
                            key={g.unit_id}
                            className="border-b border-slate-50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                        >
                            <td className="px-5 py-3 font-medium text-slate-800 dark:text-slate-200">
                                {g.unit_name ?? `Unit ${g.unit_id}`}
                                {g.chapter && <div className="text-xs text-slate-400 font-normal">{g.chapter}</div>}
                            </td>
                            <td className="px-5 py-3">
                                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${lvl.cls}`}>
                                    {lvl.label}
                                </span>{" "}
                                <span className="text-slate-500 text-xs">{g.gap_score.toFixed(2)}</span>
                            </td>
                            <td className="px-5 py-3 text-slate-600 dark:text-slate-300">
                                {(g.mastery * 100).toFixed(0)}%
                                {g.coverage !== null && g.coverage !== undefined && (
                                    <span className="ml-1 text-[10px] text-slate-400">(phủ {Math.round(g.coverage * 100)}%)</span>
                                )}
                            </td>
                            <td className="px-5 py-3">
                                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${conf.cls}`}>
                                    {conf.label}
                                </span>
                            </td>
                            <td className="px-5 py-3">
                                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${integ.cls}`}>
                                    {integ.label}
                                </span>
                            </td>
                            <td className="px-5 py-3 text-xs text-slate-500">{g.evidence_source ?? "—"}</td>
                        </tr>
                    );
                })}
            </tbody>
        </table>
    );
}