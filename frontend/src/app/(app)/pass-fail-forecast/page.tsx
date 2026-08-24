"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
    AlertCircle,
    AlertTriangle,
    Award,
    BarChart3,
    BookOpen,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    FileText,
    FolderOpen,
    HelpCircle,
    Layers,
    Lightbulb,
    Loader2,
    Search,
    Sparkles,
    Target,
    Upload,
    X,
} from "lucide-react";
import SearchableSelect from "@/components/SearchableSelect";
import StudentExamMatchingDrawer from "@/components/dashboard/StudentExamMatchingDrawer";
import { api, ApiError } from "@/lib/api";
import { ExamPaper, ExamPaperDetail, PassFailForecastResult, StudentForecastRow, WeakUnitInfo } from "@/lib/types";

type TeviStatus = "idle" | "running" | "done" | "failed";
type TeviStep = "extract" | "decompose" | "cdi" | "forecast";

const STEP_LABELS: Record<TeviStep, string> = {
    extract: "Nhận diện văn bản (VLM/OCR)",
    decompose: "Bóc tách câu hỏi & Map CT",
    cdi: "Tính CDI & Ma trận đề",
    forecast: "Dự báo Pass/Fail cả lớp",
};

const BLOOM_LABELS: Record<number, string> = {
    1: "Nhớ",
    2: "Hiểu",
    3: "Vận dụng",
    4: "Phân tích",
    5: "Đánh giá",
    6: "Sáng tạo",
};

const BLOOM_COLORS: Record<number, string> = {
    1: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300 border-emerald-200",
    2: "bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300 border-sky-200",
    3: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300 border-amber-200",
    4: "bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-300 border-purple-200",
    5: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300 border-rose-200",
    6: "bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300 border-indigo-200",
};

type FilterKey = "all" | "fail" | "borderline" | "pass" | "insufficient";

function removeVietnameseTones(str: string): string {
    return str
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/đ/g, "d")
        .replace(/Đ/g, "D")
        .toLowerCase();
}

interface GroupedQuestion {
    id: string;
    questionNumber: number;
    questionText: string;
    bloom_level: number;
    totalWeight: number;
    image_url?: string | null;
    has_figure?: boolean | null;
    subItems: { topic: string; bloom_level: number; weight: number; unit_name: string | null; excerpt?: string | null; image_url?: string | null; has_figure?: boolean | null }[];
}

export default function PassFailForecastPage() {
    const searchParams = useSearchParams();
    const queryExamId = searchParams.get("exam_paper_id");
    const querySubjectId = searchParams.get("subject_id");
    const querySemester = searchParams.get("semester");

    // ——— Shared filter state ———
    const [subjects, setSubjects] = useState<{ id: string; name: string }[]>([]);
    const [subjectId, setSubjectId] = useState<string>(querySubjectId ?? "");
    const [gradeLevel, setGradeLevel] = useState<string>("6");
    const [semester, setSemester] = useState<string>(querySemester ?? "1");
    const [activeTab, setActiveTab] = useState<"existing" | "upload">("existing");

    // ——— Forecast state ———
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<PassFailForecastResult | null>(null);
    const [filterKey, setFilterKey] = useState<FilterKey>("all");
    const [searchText, setSearchText] = useState("");
    const [expandedCode, setExpandedCode] = useState<string | null>(null);
    const [toastMsg, setToastMsg] = useState<string | null>(null);

    // ——— Upload state ———
    const [uploadTitle, setUploadTitle] = useState("");
    const [uploadFile, setUploadFile] = useState<File | null>(null);
    const [uploadBusy, setUploadBusy] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // ——— TEVI polling state ———
    const [teviStatus, setTeviStatus] = useState<TeviStatus>("idle");
    const [teviStep, setTeviStep] = useState<TeviStep>("extract");
    const [teviExamId, setTeviExamId] = useState<number | null>(null);
    const teviPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // ——— Exam list ———
    const [examPapers, setExamPapers] = useState<ExamPaper[]>([]);
    const [selectedExamId, setSelectedExamId] = useState<string>(queryExamId ?? "");

    // ——— Exam analysis data & Side panel detail ———
    const [selectedStudentForDrawer, setSelectedStudentForDrawer] = useState<StudentForecastRow | null>(null);
    const [paperDetail, setPaperDetail] = useState<ExamPaperDetail | null>(null);
    const [analysisLoading, setAnalysisLoading] = useState(false);
    const [analysisData, setAnalysisData] = useState<{
        cdi: number | null;
        items: { topic: string; bloom_level: number; weight: number; unit_name: string | null; excerpt?: string | null }[];
        coverage: { catalog_total: number; matched: number; ratio: number | null };
        concentration: { top_unit_name: string | null; top_share: number | null; is_concentrated: boolean };
        bloom_distribution: Record<string, number> | null;
    } | null>(null);

    // Load subjects
    useEffect(() => {
        api
            .get<{ subjects: { id: number; name: string }[] }>("/ews/meta")
            .then((meta) => {
                const seen = new Map<string, string>();
                for (const s of meta.subjects) {
                    if (!seen.has(s.name)) seen.set(s.name, String(s.id));
                }
                const list = Array.from(seen, ([name, id]) => ({ id, name }));
                setSubjects(list);
                if (!subjectId) {
                    const toan6 = list.find((s) => s.name.toLowerCase().includes("toán 6")) || list.find((s) => s.name.toLowerCase().includes("toán"));
                    if (toan6) setSubjectId(toan6.id);
                }
            })
            .catch(() => setError("Không tải được danh sách môn học."));
    }, []);

    // Load exams khi đổi môn/HK
    const loadExams = useCallback(async () => {
        if (!subjectId) {
            setExamPapers([]);
            setSelectedExamId("");
            return;
        }
        try {
            const papers = await api.get<ExamPaper[]>(
                `/exam-papers?subject_id=${subjectId}&semester_id=${semester}`
            );
            setExamPapers(papers);
            if (queryExamId && papers.some((p) => String(p.id) === queryExamId)) {
                setSelectedExamId(queryExamId);
            } else {
                const finals = papers.filter(
                    (p) =>
                        p.title.toLowerCase().includes("cuối kỳ") ||
                        p.title.toLowerCase().includes("cuối kì") ||
                        p.title.toLowerCase().includes("final")
                );
                if (finals.length > 0) {
                    setSelectedExamId(finals[0].id);
                } else if (papers.length > 0) {
                    setSelectedExamId(papers[0].id);
                } else {
                    setSelectedExamId("");
                }
            }
        } catch {
            setExamPapers([]);
            setSelectedExamId("");
        }
    }, [subjectId, semester, queryExamId]);

    useEffect(() => {
        loadExams();
    }, [loadExams]);

    useEffect(() => {
        return () => {
            if (teviPollRef.current) clearInterval(teviPollRef.current);
        };
    }, []);

    // Run forecast
    const runForecastWithId = useCallback(
        async (examId: string) => {
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
                    `/pass-fail-forecast/${examId}?${params.toString()}`
                );
                setResult(data);
                setTeviStep("forecast");
            } catch (e: any) {
                setError(e?.message ?? "Lỗi khi tải dự đoán pass/fail.");
            } finally {
                setLoading(false);
            }
        },
        [subjectId, gradeLevel, semester]
    );

    const runForecast = useCallback(() => {
        if (selectedExamId) runForecastWithId(selectedExamId);
    }, [selectedExamId, runForecastWithId]);

    // Tự động chạy dự đoán nếu được điều hướng từ trang exam-difficulty
    useEffect(() => {
        if (queryExamId && selectedExamId === queryExamId && subjectId && !result && !loading) {
            runForecastWithId(queryExamId);
        }
    }, [queryExamId, selectedExamId, subjectId]);

    // Tự động load Ma trận đề thi cho Panel Trái khi có đề
    useEffect(() => {
        const examId = result?.exam_paper_id ? String(result.exam_paper_id) : selectedExamId;
        if (!examId) {
            setAnalysisData(null);
            setPaperDetail(null);
            return;
        }
        setAnalysisLoading(true);
        api.get<ExamPaperDetail>(`/exam-papers/${examId}`)
            .then((p) => setPaperDetail(p))
            .catch(() => setPaperDetail(null));

        api.get<any>(`/exam-papers/${examId}/content-analysis`)
            .then((data) => {
                setAnalysisData({
                    cdi: data.cdi,
                    items: data.items,
                    coverage: data.coverage,
                    concentration: data.concentration,
                    bloom_distribution: data.bloom_distribution,
                });
            })
            .catch(() => {
                setAnalysisData(null);
            })
            .finally(() => {
                setAnalysisLoading(false);
            });
    }, [result?.exam_paper_id, selectedExamId]);

    // TEVI Polling
    const startTeviPoll = useCallback((paperId: number) => {
        setTeviStatus("running");
        setTeviStep("extract");
        setTeviExamId(paperId);
        if (teviPollRef.current) clearInterval(teviPollRef.current);

        teviPollRef.current = setInterval(async () => {
            try {
                const detail = await api.get<{
                    content_difficulty: number | null;
                    content_analyzed_at: string | null;
                    ai_analysis?: {
                        error?: string;
                        content_analysis?: { items?: any[] };
                    };
                }>(`/exam-papers/${paperId}`);

                if (detail.ai_analysis?.content_analysis?.items) {
                    setTeviStep("decompose");
                }
                if (detail.content_difficulty !== null) {
                    setTeviStep("cdi");
                }
                if (detail.content_analyzed_at) {
                    if (detail.ai_analysis?.error) {
                        if (teviPollRef.current) clearInterval(teviPollRef.current);
                        teviPollRef.current = null;
                        setTeviStatus("failed");
                        setUploadError(
                            "AI phân tích thất bại: " +
                            (detail.ai_analysis.error === "LLM analysis failed"
                                ? "có thể do thiếu API key hoặc lỗi kết nối LLM."
                                : detail.ai_analysis.error)
                        );
                        return;
                    }
                    if (teviPollRef.current) clearInterval(teviPollRef.current);
                    teviPollRef.current = null;
                    setTeviStatus("done");
                    setActiveTab("existing");
                    setToastMsg("Phân tích hoàn tất! Đã nạp đề vào ma trận và dự báo kết quả.");
                }
            } catch { /* retry */ }
        }, 2000);

        setTimeout(() => {
            if (teviPollRef.current) {
                clearInterval(teviPollRef.current);
                teviPollRef.current = null;
                setTeviStatus((prev) => (prev === "running" ? "failed" : prev));
                setUploadError("Quá thời gian chờ AI phân tích.");
            }
        }, 180_000);
    }, []);

    // Upload handler
    const handleUpload = useCallback(async () => {
        if (!subjectId || !uploadFile || !uploadTitle.trim()) {
            setUploadError("Vui lòng chọn môn, nhập tên đề và chọn file.");
            return;
        }
        setUploadBusy(true);
        setUploadError(null);
        setResult(null);
        setTeviStatus("idle");
        setTeviExamId(null);
        try {
            const form = new FormData();
            form.set("subject_id", subjectId);
            form.set("semester_id", semester);
            form.set("title", uploadTitle.trim());
            if (gradeLevel) form.set("grade_id", gradeLevel);
            form.set("file", uploadFile);

            const paper = await api.upload<ExamPaper>("/exam-papers", form);
            setExamPapers((prev) => [paper, ...prev]);
            setSelectedExamId(paper.id);
            setUploadTitle("");
            setUploadFile(null);
            if (fileInputRef.current) fileInputRef.current.value = "";
            startTeviPoll(Number(paper.id));
        } catch (e: any) {
            setUploadError(e instanceof ApiError ? e.message : "Tải đề lên thất bại.");
        } finally {
            setUploadBusy(false);
        }
    }, [subjectId, semester, gradeLevel, uploadFile, uploadTitle, startTeviPoll]);

    useEffect(() => {
        if (teviStatus === "done" && teviExamId !== null && subjectId) {
            runForecastWithId(String(teviExamId));
        }
    }, [teviStatus, teviExamId, subjectId, runForecastWithId]);

    // Lọc danh sách học sinh
    const filteredStudents = useMemo(() => {
        if (!result) return [];
        let list = result.students;
        if (filterKey === "fail") list = list.filter((s) => s.verdict === "FAIL");
        else if (filterKey === "borderline") list = list.filter((s) => s.verdict === "BORDERLINE");
        else if (filterKey === "pass") list = list.filter((s) => s.verdict === "PASS");
        else if (filterKey === "insufficient") list = list.filter((s) => s.verdict === "INSUFFICIENT" || s.predicted_score === null);

        if (searchText.trim()) {
            const q = removeVietnameseTones(searchText.trim());
            list = list.filter(
                (s) =>
                    removeVietnameseTones(s.student_code).includes(q) ||
                    (s.student_name && removeVietnameseTones(s.student_name).includes(q))
            );
        }
        return list;
    }, [result, filterKey, searchText]);

    const gradeOptions = Array.from({ length: 7 }, (_, i) => String(i + 6));

    return (
        <div className="p-6 md:p-8 max-w-[1600px] mx-auto space-y-5">
            {/* Toast Banner */}
            {toastMsg && (
                <div className="rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300 flex items-center justify-between shadow-sm animate-in fade-in slide-in-from-top-2">
                    <span className="flex items-center gap-2">
                        <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
                        {toastMsg}
                    </span>
                    <button onClick={() => setToastMsg(null)} className="text-emerald-500 hover:text-emerald-700 p-1">
                        <X className="w-4 h-4" />
                    </button>
                </div>
            )}

            {/* ===== Header Tiêu đề & Bộ lọc chung ===== */}
            <div className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden">
                <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                            <Target className="w-5 h-5 text-brand-600" />
                            Dự đoán Pass / Fail Đề Cuối Kỳ
                        </h2>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                            Tải đề thi hoặc chọn đề có sẵn → AI phân tích ma trận → dự đoán tỉ lệ trượt/pass dựa trên năng lực LMS từng bài
                        </p>
                    </div>

                    {/* Bộ lọc Môn / Khối / Học kỳ */}
                    <div className="flex flex-wrap items-center gap-2.5">
                        <div className="min-w-[140px]">
                            <SearchableSelect
                                options={subjects.map((s) => ({ value: s.id, label: s.name }))}
                                value={subjectId}
                                onChange={setSubjectId}
                                placeholder="Chọn môn..."
                                className="min-w-[140px]"
                            />
                        </div>
                        <div className="min-w-[110px]">
                            <SearchableSelect
                                options={gradeOptions.map((g) => ({ value: g, label: `Khối ${g}` }))}
                                value={gradeLevel}
                                onChange={setGradeLevel}
                                placeholder="Khối..."
                                className="min-w-[110px]"
                            />
                        </div>
                        <div className="min-w-[95px]">
                            <SearchableSelect
                                options={[
                                    { value: "1", label: "HK1" },
                                    { value: "2", label: "HK2" },
                                ]}
                                value={semester}
                                onChange={setSemester}
                                className="min-w-[95px]"
                            />
                        </div>
                    </div>
                </div>

                {/* ===== Tab bar: Chọn đề cũ vs Tải đề mới ===== */}
                <div className="flex border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/30">
                    <button
                        onClick={() => setActiveTab("existing")}
                        className={`flex-1 px-5 py-3 text-sm font-semibold border-b-2 transition-colors flex items-center justify-center gap-2 ${activeTab === "existing"
                            ? "border-brand-600 text-brand-600 bg-white dark:bg-slate-900"
                            : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                            }`}
                    >
                        <FolderOpen className="w-4 h-4 text-brand-600" />
                        <span>Chọn đề có sẵn trong thư viện ({examPapers.length})</span>
                    </button>
                    <button
                        onClick={() => setActiveTab("upload")}
                        className={`flex-1 px-5 py-3 text-sm font-semibold border-b-2 transition-colors flex items-center justify-center gap-2 ${activeTab === "upload"
                            ? "border-brand-600 text-brand-600 bg-white dark:bg-slate-900"
                            : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                            }`}
                    >
                        <Upload className="w-4 h-4 text-brand-600" />
                        <span>Tải lên đề thi mới (AI phân tích)</span>
                    </button>
                </div>

                {/* ===== Tab content ===== */}
                <div className="p-5">
                    {activeTab === "existing" ? (
                        <div className="flex flex-wrap items-center gap-3">
                            <div className="min-w-[280px] flex-1">
                                <SearchableSelect
                                    options={
                                        examPapers.length > 0
                                            ? examPapers.map((p) => ({
                                                value: p.id,
                                                label: `${p.title} (${new Date(p.created_at).toLocaleDateString("vi-VN")})`,
                                            }))
                                            : [{ value: "", label: "Chưa có đề — chuyển tab Tải lên" }]
                                    }
                                    value={selectedExamId}
                                    onChange={setSelectedExamId}
                                    placeholder={examPapers.length > 0 ? "Chọn đề thi dự đoán..." : ""}
                                    className="w-full"
                                />
                            </div>
                            <button
                                onClick={runForecast}
                                disabled={loading || !subjectId || !selectedExamId}
                                className="px-6 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2 shadow-xs transition-colors"
                            >
                                {loading ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        Đang dự đoán...
                                    </>
                                ) : (
                                    <>
                                        <BarChart3 className="w-4 h-4" />
                                        Chạy Dự Đoán Pass/Fail
                                    </>
                                )}
                            </button>
                        </div>
                    ) : (
                        <div className="space-y-4 max-w-3xl">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1 block">
                                        Tên đề thi <span className="text-rose-500">*</span>
                                    </label>
                                    <input
                                        type="text"
                                        value={uploadTitle}
                                        onChange={(e) => setUploadTitle(e.target.value)}
                                        placeholder="VD: Đề cuối kỳ 1 Toán 6"
                                        className="w-full px-3.5 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1 block">
                                        Tệp đề thi (PDF / Ảnh / Word) <span className="text-rose-500">*</span>
                                    </label>
                                    <input
                                        ref={fileInputRef}
                                        type="file"
                                        accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.webp,.tiff"
                                        onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                                        className="block w-full text-sm text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100 dark:file:bg-brand-900/30 dark:file:text-brand-300"
                                    />
                                </div>
                            </div>

                            <div className="flex items-center gap-3">
                                <button
                                    onClick={handleUpload}
                                    disabled={uploadBusy || !subjectId || !uploadFile || !uploadTitle.trim()}
                                    className="px-5 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2 shadow-xs transition-colors"
                                >
                                    {uploadBusy ? (
                                        <>
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            Đang tải lên...
                                        </>
                                    ) : (
                                        <>
                                            <Upload className="w-4 h-4" />
                                            Tải lên & Phân tích AI
                                        </>
                                    )}
                                </button>
                                {uploadError && (
                                    <span className="text-xs text-rose-600 font-medium">{uploadError}</span>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* ===== TEVI Progress Stepper ===== */}
            {teviStatus === "running" && (
                <div className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden animate-in fade-in duration-200">
                    <div className="px-5 py-3.5 border-b border-slate-100 dark:border-slate-800 flex items-center gap-2 bg-slate-50/60 dark:bg-slate-950/40">
                        <Loader2 className="w-4 h-4 text-brand-600 animate-spin" />
                        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">
                            AI đang bóc tách và phân tích ma trận đề thi...
                        </h3>
                    </div>
                    <div className="p-5 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                        {(["extract", "decompose", "cdi", "forecast"] as TeviStep[]).map((step, idx) => {
                            const stepIndex = ["extract", "decompose", "cdi", "forecast"].indexOf(teviStep as string);
                            const done = idx < stepIndex;
                            const active = idx === stepIndex;
                            return (
                                <div key={step} className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex items-center gap-3">
                                    <div
                                        className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${done
                                            ? "bg-emerald-100 text-emerald-600 dark:bg-emerald-950/50"
                                            : active
                                                ? "bg-brand-100 text-brand-600 dark:bg-brand-950/50 ring-2 ring-brand-500/20"
                                                : "bg-slate-100 text-slate-400 dark:bg-slate-800"
                                            }`}
                                    >
                                        {done ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> : active ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : idx + 1}
                                    </div>
                                    <span className={`text-xs font-medium ${done ? "text-emerald-700 dark:text-emerald-400" : active ? "text-brand-600 dark:text-brand-400 font-bold" : "text-slate-400"}`}>
                                        {STEP_LABELS[step]}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Error Banner */}
            {error && (
                <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 px-4 py-3 text-sm text-rose-700 dark:text-rose-300">
                    {error}
                </div>
            )}

            {/* ===== BỐ CỤC 2 CỘT SONG SONG (SPLIT-SCREEN MASTER-DETAIL) ===== */}
            {result && result.total > 0 && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
                    {/* PANEL TRÁI (5/12): MA TRẬN & ĐỘ KHÓ ĐỀ THI (GOM NHÓM THÔNG MINH) */}
                    <div className="lg:col-span-5 space-y-4">
                        {analysisData ? (
                            <ExamIntelligencePanel analysisData={analysisData} />
                        ) : (
                            <div className="bg-white dark:bg-slate-900 border rounded-2xl p-6 text-center text-sm text-slate-400">
                                {analysisLoading ? (
                                    <div className="space-y-2">
                                        <Loader2 className="w-5 h-5 animate-spin mx-auto text-brand-600" />
                                        <p>Đang tải cấu trúc đề thi...</p>
                                    </div>
                                ) : (
                                    <p>Chưa có dữ liệu phân tích cấu trúc cho đề này.</p>
                                )}
                            </div>
                        )}
                    </div>

                    {/* PANEL PHẢI (7/12): BẢNG DỰ BÁO HỌC SINH CẢ LỚP */}
                    <div className="lg:col-span-7 bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden space-y-3">
                        {/* Header & KPI filter chips */}
                        <div className="p-4 border-b border-slate-100 dark:border-slate-800 space-y-3">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <h3 className="font-bold text-sm text-slate-800 dark:text-slate-200 flex items-center gap-2">
                                    <Award className="w-4 h-4 text-brand-600" />
                                    Dự Báo Điểm & Nguy Cơ Pass/Fail Cả Lớp
                                </h3>
                                <span className="text-xs text-slate-400">
                                    Tỉ lệ trượt dự kiến: <strong className="text-rose-600">{(result.fail_rate * 100).toFixed(1)}%</strong>
                                </span>
                            </div>

                            {/* KPI Chips */}
                            <div className="flex flex-wrap items-center gap-1.5 pt-1">
                                <FilterChip label="Tất cả" count={result.total} active={filterKey === "all"} onClick={() => setFilterKey("all")} />
                                <FilterChip label="Trượt" icon={AlertCircle} count={result.fail_count} active={filterKey === "fail"} onClick={() => setFilterKey("fail")} cls="text-rose-700 bg-rose-50 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300" />
                                <FilterChip label="Ranh giới" icon={AlertTriangle} count={result.borderline_count} active={filterKey === "borderline"} onClick={() => setFilterKey("borderline")} cls="text-amber-700 bg-amber-50 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300" />
                                <FilterChip label="Đậu" icon={CheckCircle2} count={result.pass_count} active={filterKey === "pass"} onClick={() => setFilterKey("pass")} cls="text-emerald-700 bg-emerald-50 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300" />
                                <FilterChip label="Thiếu LMS" icon={HelpCircle} count={result.insufficient_count} active={filterKey === "insufficient"} onClick={() => setFilterKey("insufficient")} cls="text-slate-600 bg-slate-100 border-slate-200 dark:bg-slate-800 dark:text-slate-400" />
                            </div>

                            {/* Search box */}
                            {result.students.length > 3 && (
                                <div className="relative">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                                    <input
                                        type="text"
                                        value={searchText}
                                        onChange={(e) => setSearchText(e.target.value)}
                                        placeholder="Tìm theo tên học sinh hoặc mã HS..."
                                        className="w-full pl-8 pr-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                                    />
                                </div>
                            )}
                        </div>

                        {/* Forecast Table */}
                        {filteredStudents.length > 0 ? (
                            <ForecastTable
                                students={filteredStudents}
                                expandedCode={expandedCode}
                                onToggleExpand={(code) => setExpandedCode(code === expandedCode ? null : code)}
                                onOpenDrawer={(s) => setSelectedStudentForDrawer(s)}
                            />
                        ) : (
                            <div className="p-8 text-center text-xs text-slate-400">
                                Không tìm thấy học sinh phù hợp bộ lọc.
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* SIDE PANEL ĐỐI SÁNH TỪNG CÂU HỎI VỚI NĂNG LỰC HỌC SINH */}
            {selectedStudentForDrawer && paperDetail && (
                <StudentExamMatchingDrawer
                    student={selectedStudentForDrawer}
                    examPaper={paperDetail}
                    onClose={() => setSelectedStudentForDrawer(null)}
                />
            )}

            {/* Empty state */}
            {result && result.total === 0 && (
                <div className="rounded-2xl bg-white dark:bg-slate-900 border p-8 text-center text-sm text-slate-400 space-y-1">
                    <p className="font-semibold text-slate-600 dark:text-slate-300">Đề thi chưa có dữ liệu dự báo</p>
                    <p className="text-xs">Chưa có dữ liệu học sinh hoặc đề chưa được AI map chương/bài.</p>
                </div>
            )}

            {/* Loading Skeleton */}
            {loading && !result && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start animate-pulse">
                    <div className="lg:col-span-5 h-96 bg-white dark:bg-slate-900 border rounded-2xl" />
                    <div className="lg:col-span-7 h-96 bg-white dark:bg-slate-900 border rounded-2xl" />
                </div>
            )}
        </div>
    );
}

// ——— PANEL TRÁI: MA TRẬN & ĐỘ KHÓ ĐỀ THI (GOM NHÓM THÔNG MINH) ———
function ExamIntelligencePanel({
    analysisData,
}: {
    analysisData: {
        cdi: number | null;
        items: { topic: string; bloom_level: number; weight: number; unit_name: string | null; excerpt?: string | null }[];
        coverage: { catalog_total: number; matched: number; ratio: number | null };
        concentration: { top_unit_name: string | null; top_share: number | null; is_concentrated: boolean };
        bloom_distribution: Record<string, number> | null;
    };
}) {
    // Gom nhóm câu hỏi thông minh
    const groupedQuestions = useMemo<GroupedQuestion[]>(() => {
        const groups: GroupedQuestion[] = [];
        const map = new Map<string, GroupedQuestion>();

        analysisData.items.forEach((item) => {
            const key = (item.excerpt?.trim() || item.topic.trim());
            let group = map.get(key);
            if (!group) {
                group = {
                    id: `q-${groups.length + 1}`,
                    questionNumber: groups.length + 1,
                    questionText: key,
                    bloom_level: item.bloom_level,
                    totalWeight: 0,
                    image_url: item.image_url ?? null,
                    has_figure: item.has_figure ?? null,
                    subItems: [],
                };
                map.set(key, group);
                groups.push(group);
            }
            if (!group.image_url && item.image_url) {
                group.image_url = item.image_url;
            }
            if (item.has_figure) {
                group.has_figure = true;
            }
            group.totalWeight += item.weight;
            if (item.bloom_level > group.bloom_level) {
                group.bloom_level = item.bloom_level;
            }
            group.subItems.push(item);
        });

        return groups;
    }, [analysisData.items]);

    return (
        <div className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden space-y-4 p-5">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
                <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
                    <BookOpen className="w-4 h-4 text-brand-600" />
                    Ma Trận & Cấu Trúc Đề Thi
                </h3>
                <span className="text-xs text-slate-400 font-medium">
                    {groupedQuestions.length} câu lớn · {analysisData.items.length} ý đánh giá
                </span>
            </div>

            {/* 3 Thẻ Chỉ số Cốt lõi */}
            <div className="grid grid-cols-3 gap-2.5">
                {/* 1. CDI */}
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 space-y-1">
                    <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 block">Độ khó CDI</span>
                    <div className="flex items-baseline gap-1">
                        <span className="text-xl font-black text-brand-600 dark:text-brand-400">
                            {analysisData.cdi?.toFixed(2) ?? "—"}
                        </span>
                        <span className="text-[10px] text-slate-400">/ 1.0</span>
                    </div>
                </div>

                {/* 2. Coverage */}
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 space-y-1">
                    <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 block">Độ phủ SGK</span>
                    <span className="text-xl font-black text-slate-800 dark:text-slate-200 block">
                        {analysisData.coverage.ratio !== null
                            ? `${(analysisData.coverage.ratio * 100).toFixed(0)}%`
                            : "—"}
                    </span>
                </div>

                {/* 3. Concentration */}
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 space-y-1">
                    <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 block">Phân bổ</span>
                    <span className="text-xs font-bold text-slate-700 dark:text-slate-300 block pt-1 truncate">
                        {analysisData.concentration.is_concentrated ? "Lệch chuyên đề" : "Phân bổ đều"}
                    </span>
                </div>
            </div>

            {/* Phân bố Bloom Stacked Bar */}
            {analysisData.bloom_distribution && (
                <div className="p-3.5 rounded-xl bg-slate-50/70 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800 space-y-2">
                    <div className="flex items-center justify-between text-xs font-semibold text-slate-600 dark:text-slate-300">
                        <span>Phân bố Nhận thức Bloom:</span>
                    </div>

                    <div className="h-2.5 w-full bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden flex shadow-inner">
                        {Number(analysisData.bloom_distribution.remember ?? 0) > 0 && (
                            <div className="h-full bg-emerald-500" style={{ width: `${analysisData.bloom_distribution.remember}%` }} />
                        )}
                        {Number(analysisData.bloom_distribution.understand ?? 0) > 0 && (
                            <div className="h-full bg-sky-500" style={{ width: `${analysisData.bloom_distribution.understand}%` }} />
                        )}
                        {Number(analysisData.bloom_distribution.apply ?? 0) > 0 && (
                            <div className="h-full bg-amber-500" style={{ width: `${analysisData.bloom_distribution.apply}%` }} />
                        )}
                        {Number(analysisData.bloom_distribution.analyze ?? 0) > 0 && (
                            <div className="h-full bg-purple-500" style={{ width: `${analysisData.bloom_distribution.analyze}%` }} />
                        )}
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
                        <span className="flex items-center gap-1.5 text-slate-500">
                            <span className="w-2 h-2 rounded-full bg-amber-500" />
                            Vận dụng: <strong>{analysisData.bloom_distribution.apply ?? 0}%</strong>
                        </span>
                        <span className="flex items-center gap-1.5 text-slate-500">
                            <span className="w-2 h-2 rounded-full bg-purple-500" />
                            Vận dụng cao: <strong>{analysisData.bloom_distribution.analyze ?? 0}%</strong>
                        </span>
                    </div>
                </div>
            )}

            {/* Danh sách Câu Hỏi Lớn Gom Nhóm */}
            <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-bold text-slate-700 dark:text-slate-300">
                    <span>Chi tiết từng câu hỏi trong đề:</span>
                    <span className="text-[11px] text-slate-400 font-normal">Gom nhóm thông minh</span>
                </div>

                <div className="space-y-3 max-h-[460px] overflow-y-auto pr-1">
                    {groupedQuestions.map((q) => {
                        const isSingle = q.subItems.length === 1;

                        return (
                            <div
                                key={q.id}
                                className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-800/60 text-xs space-y-2 shadow-2xs"
                            >
                                {/* Header Câu */}
                                <div className="flex items-start justify-between gap-2">
                                    <div className="flex items-start gap-2 flex-1 min-w-0">
                                        <span className="w-6 h-6 rounded-lg bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 font-black text-[11px] flex items-center justify-center shrink-0 mt-0.5">
                                            #{q.questionNumber}
                                        </span>
                                        <div className="space-y-1 min-w-0 flex-1">
                                            <span className="font-semibold text-slate-900 dark:text-white leading-tight block">
                                                {q.questionText}
                                            </span>
                                            <div className="flex items-center gap-2">
                                                <span className={`inline-flex items-center px-1.5 py-0.2 rounded text-[9px] font-bold border ${BLOOM_COLORS[q.bloom_level]}`}>
                                                    Bloom {q.bloom_level} · {BLOOM_LABELS[q.bloom_level] ?? ""}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                    <span className="text-brand-600 dark:text-brand-400 font-black shrink-0 text-[11px]">
                                        {(q.totalWeight * 100).toFixed(1)}%
                                    </span>
                                </div>

                                {/* Ý đánh giá con */}
                                <div className="space-y-1.5 pl-2 border-l-2 border-slate-100 dark:border-slate-700/60">
                                    {q.subItems.map((sub, idx) => {
                                        return (
                                            <div
                                                key={idx}
                                                className="p-1.5 rounded-lg bg-slate-50/70 dark:bg-slate-800/40 flex items-center justify-between gap-2 text-[11px]"
                                            >
                                                <div className="flex items-center gap-1.5 min-w-0 flex-1">
                                                    <BookOpen className="w-3 h-3 text-brand-600 shrink-0" />
                                                    <span className="text-slate-600 dark:text-slate-300 truncate">
                                                        {sub.unit_name ?? sub.topic}
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-1.5 shrink-0">
                                                    <span className="text-slate-500 font-medium">
                                                        {(sub.weight * 100).toFixed(1)}%
                                                    </span>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}

// ——— Filter chip ———
function FilterChip({
    label, count, active, onClick, cls = "", icon: Icon,
}: { label: string; count: number; active: boolean; onClick: () => void; cls?: string; icon?: React.ElementType }) {
    return (
        <button
            onClick={onClick}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${active
                ? "bg-brand-600 text-white shadow-xs"
                : `border border-slate-200 dark:border-slate-700 text-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800 ${cls}`
                }`}
        >
            {Icon && <Icon className={`w-3.5 h-3.5 ${active ? "text-white" : ""}`} />}
            <span>{label}</span>
            <span className={`text-[11px] font-bold ${active ? "opacity-90" : ""}`}>{count}</span>
        </button>
    );
}

// ——— Forecast Table (PANEL PHẢI) ———
function ForecastTable({
    students, expandedCode, onToggleExpand, onOpenDrawer,
}: {
    students: StudentForecastRow[];
    expandedCode: string | null;
    onToggleExpand: (code: string) => void;
    onOpenDrawer: (student: StudentForecastRow) => void;
}) {
    return (
        <div className="max-h-[580px] overflow-auto">
            <table className="w-full text-xs">
                <thead className="sticky top-0 bg-slate-50/90 dark:bg-slate-900/90 backdrop-blur-xs z-10">
                    <tr className="text-left text-[11px] font-bold text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800">
                        <th className="px-3 py-2.5 w-6"></th>
                        <th className="px-0 py-2.5">Học sinh</th>
                        <th className="px-3 py-2.5">Điểm dự kiến</th>
                        <th className="px-2 py-2.5">Kết quả</th>
                        <th className="px-3 py-2.5">Top bài hổng trong đề</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {students.map((s) => {
                        const isExpanded = expandedCode === s.student_code;
                        return (
                            <ForecastRow
                                key={s.student_code}
                                student={s}
                                isExpanded={isExpanded}
                                onToggle={() => onToggleExpand(s.student_code)}
                                onOpenDrawer={onOpenDrawer}
                            />
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

function ForecastRow({
    student, isExpanded, onToggle, onOpenDrawer,
}: {
    student: StudentForecastRow;
    isExpanded: boolean;
    onToggle: () => void;
    onOpenDrawer: (student: StudentForecastRow) => void;
}) {
    const isInsufficient = student.verdict === "INSUFFICIENT" || student.predicted_score === null;
    const verdictCls = isInsufficient
        ? "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 border border-slate-200 dark:border-slate-700"
        : student.verdict === "PASS"
            ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
            : student.verdict === "FAIL"
                ? "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border border-rose-200 dark:border-rose-800 font-bold"
                : "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800 font-bold";
    const verdictLabel = isInsufficient
        ? "Thiếu LMS"
        : student.verdict === "PASS" ? "ĐẬU" : student.verdict === "FAIL" ? "TRƯỢT" : "RANH GIỚI";

    const scorePct = student.predicted_score !== null ? Math.min(1, student.predicted_score / 10) : 0;

    return (
        <>
            <tr
                className="hover:bg-slate-50/70 dark:hover:bg-slate-800/50 cursor-pointer transition-colors group"
                onClick={onToggle}
            >
                <td className="px-3 py-2.5 text-slate-400">
                    {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-brand-600" /> : <ChevronRight className="w-3.5 h-3.5" />}
                </td>
                <td className="px-0 py-2.5">
                    <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-bold text-[10px] flex items-center justify-center shrink-0">
                            {(student.student_name ?? student.student_code).charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                            <span className="font-bold text-slate-800 dark:text-slate-200 block truncate leading-tight">
                                {student.student_name ?? student.student_code}
                            </span>
                            <span className="text-[10px] text-slate-400 block truncate">
                                {student.student_code} {student.class_name ? `· ${student.class_name}` : ""}
                            </span>
                        </div>
                    </div>
                </td>
                <td className="px-3 py-2.5 whitespace-nowrap">
                    {student.predicted_score !== null ? (
                        <div className="flex items-center gap-2">
                            <div className="w-12 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden shrink-0">
                                <div
                                    className={`h-full rounded-full ${scorePct >= 0.6 ? "bg-emerald-500" : scorePct >= 0.5 ? "bg-amber-500" : "bg-rose-500"}`}
                                    style={{ width: `${scorePct * 100}%` }}
                                />
                            </div>
                            <span className="text-slate-700 dark:text-slate-300 font-mono text-xs font-bold">
                                {student.predicted_score.toFixed(2)}
                            </span>
                        </div>
                    ) : (
                        <span className="text-slate-400">—</span>
                    )}
                </td>
                <td className="px-2 py-2.5 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${verdictCls}`}>
                        {verdictLabel}
                    </span>
                </td>
                <td className="px-3 py-2.5">
                    <div className="flex items-center justify-between gap-2">
                        {student.weak_units.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                                {student.weak_units.map((wu, i) => (
                                    <span
                                        key={i}
                                        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border border-rose-100 dark:border-rose-900/40"
                                        title={`${wu.unit_name} — Điểm LMS: ${wu.ability !== null ? wu.ability.toFixed(1) : "—"}/10 · Chiếm ${(wu.exam_weight * 100).toFixed(0)}% điểm đề`}
                                    >
                                        <AlertTriangle className="w-2.5 h-2.5 text-rose-500 shrink-0" />
                                        <span className="max-w-[110px] truncate">{wu.unit_name}</span>
                                        <span className="font-bold opacity-85">({(wu.exam_weight * 100).toFixed(0)}%)</span>
                                    </span>
                                ))}
                            </div>
                        ) : (
                            <span className="text-slate-400">—</span>
                        )}

                        <button
                            type="button"
                            onClick={(e) => {
                                e.stopPropagation();
                                onOpenDrawer(student);
                            }}
                            className="opacity-0 group-hover:opacity-100 inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-brand-50 hover:bg-brand-100 dark:bg-brand-950/60 dark:hover:bg-brand-900/60 text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-800 text-[10px] font-semibold transition-all cursor-pointer shrink-0"
                            title="Mở Side Panel đối sánh từng câu hỏi với năng lực LMS"
                        >
                            <Target className="w-3 h-3" />
                            <span>Đối sánh cả đề</span>
                        </button>
                    </div>
                </td>
            </tr>
            {/* Expanded row Drill-down */}
            {isExpanded && !isInsufficient && (
                <tr>
                    <td colSpan={5} className="bg-slate-50/80 dark:bg-slate-800/40 px-4 py-3 border-t border-slate-100 dark:border-slate-800">
                        <div className="text-xs space-y-2.5">
                            <p className="font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                                <Sparkles className="w-3.5 h-3.5 text-brand-600" />
                                <span>Top bài học sinh bị hổng nặng nhất trong đề thi (Cần phụ đạo gấp):</span>
                            </p>
                            {student.weak_units.length > 0 ? (
                                <div className="space-y-1.5">
                                    {student.weak_units.map((wu, i) => (
                                        <div key={i} className="p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 flex flex-wrap items-center justify-between gap-2">
                                            <span className="font-medium text-slate-700 dark:text-slate-300 truncate max-w-[220px]">
                                                {wu.unit_name}
                                            </span>
                                            <div className="flex items-center gap-3">
                                                <div className="flex items-center gap-1.5">
                                                    <span className="text-slate-400 text-[11px]">Năng lực LMS:</span>
                                                    <span className="font-black text-rose-600 dark:text-rose-400 font-mono">
                                                        {wu.ability !== null ? wu.ability.toFixed(1) : "—"}/10
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-1.5">
                                                    <span className="text-slate-400 text-[11px]">Trọng số đề:</span>
                                                    <span className="font-bold text-slate-800 dark:text-slate-200">
                                                        {(wu.exam_weight * 100).toFixed(0)}% điểm
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-slate-400 text-xs">Học sinh không có bài yếu trọng yếu nào trong đề thi này.</p>
                            )}

                            <div className="pt-2 flex items-center justify-between gap-3 flex-wrap border-t border-slate-200/60 dark:border-slate-700/60">
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 italic flex items-center gap-1.5">
                                    <Lightbulb className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                                    <span>Lời khuyên sư phạm: Cần củng cố sớm các bài trên trước ngày thi để kéo điểm dự báo lên mức ĐẬU an toàn.</span>
                                </p>
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onOpenDrawer(student);
                                    }}
                                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-brand-50 hover:bg-brand-100 dark:bg-brand-950/60 dark:hover:bg-brand-900/60 text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-800 text-xs font-semibold transition-all cursor-pointer shadow-2xs shrink-0"
                                >
                                    <Target className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400" />
                                    <span>Đối sánh chi tiết cả đề (Side Panel)</span>
                                </button>
                            </div>
                        </div>
                    </td>
                </tr>
            )}
        </>
    );
}