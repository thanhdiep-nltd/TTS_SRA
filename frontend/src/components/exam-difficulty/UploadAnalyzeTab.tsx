"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
    AlertCircle,
    AlertTriangle,
    ArrowRight,
    BarChart3,
    BookOpen,
    CheckCircle2,
    ChevronRight,
    FileText,
    FolderOpen,
    Layers,
    Loader2,
    Sparkles,
    Target,
    Upload,
    X,
    Image as ImageIcon,
    ZoomIn,
} from "lucide-react";
import SearchableSelect from "@/components/SearchableSelect";
import { api, ApiError } from "@/lib/api";
import type { ExamAnalysisItem, ExamPaper, ExamPaperDetail } from "@/lib/types";

type TeviStep = "extract" | "decompose" | "cdi" | "done";

const STEP_LABELS: Record<TeviStep, string> = {
    extract: "Nhận diện văn bản (VLM/OCR)",
    decompose: "Bóc tách & Map từng câu vào chương trình",
    cdi: "Tính CDI & Ma trận đề",
    done: "Hoàn tất phân tích",
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

const GRADE_OPTIONS = Array.from({ length: 7 }, (_, i) => String(i + 6));

interface GroupedQuestion {
    id: string;
    questionNumber: number;
    questionText: string;
    bloom_level: number;
    totalWeight: number;
    image_url?: string | null;
    has_figure?: boolean | null;
    subItems: ExamAnalysisItem[];
}

export default function UploadAnalyzeTab() {
    // ——— Shared Filter state ———
    const [subjects, setSubjects] = useState<{ id: string; name: string }[]>([]);
    const [subjectId, setSubjectId] = useState<string>("");
    const [gradeId, setGradeId] = useState<string>("6");
    const [semester, setSemester] = useState<string>("1");
    const [subTab, setSubTab] = useState<"existing" | "upload">("existing");

    // ——— File upload state ———
    const [file, setFile] = useState<File | null>(null);
    const [title, setTitle] = useState("");
    const [uploadBusy, setUploadBusy] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [toastMsg, setToastMsg] = useState<string | null>(null);

    // ——— Exam papers state ———
    const [examPapers, setExamPapers] = useState<ExamPaper[]>([]);
    const [selectedPaperId, setSelectedPaperId] = useState<string>("");

    // ——— TEVI Stepper & Polling ———
    const [analyzing, setAnalyzing] = useState(false);
    const [teviStep, setTeviStep] = useState<TeviStep>("extract");
    const [analyzeError, setAnalyzeError] = useState<string | null>(null);
    const teviPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const stepRef = useRef<TeviStep>("extract");

    // ——— Analysis Result state (Chỉ load khi bấm nút hoặc hoàn tất phân tích) ———
    const [items, setItems] = useState<ExamAnalysisItem[]>([]);
    const [cdi, setCdi] = useState<number | null>(null);
    const [rawText, setRawText] = useState<string | null>(null);
    const [loadingItems, setLoadingItems] = useState(false);
    const [loadedPaperId, setLoadedPaperId] = useState<string | null>(null);
    const [showRawText, setShowRawText] = useState(false);
    const [selectedImageModal, setSelectedImageModal] = useState<{ url: string; title: string } | null>(null);

    // ——— Load subjects on mount ———
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
                const toan6 = list.find((s) => s.name.toLowerCase().includes("toán 6")) || list.find((s) => s.name.toLowerCase().includes("toán"));
                if (toan6) setSubjectId(toan6.id);
            })
            .catch(() => setUploadError("Không tải được danh mục môn học."));
    }, []);

    // ——— Load exam papers khi đổi môn / kỳ ———
    const loadPapers = useCallback(async () => {
        if (!subjectId) {
            setExamPapers([]);
            setSelectedPaperId("");
            return;
        }
        try {
            const papers = await api.get<ExamPaper[]>(
                `/exam-papers?subject_id=${subjectId}&semester_id=${semester}`
            );
            setExamPapers(papers);
            if (papers.length > 0) {
                const analyzed = papers.filter((p) => p.content_difficulty !== null);
                if (analyzed.length > 0) {
                    setSelectedPaperId(analyzed[0].id);
                } else {
                    setSelectedPaperId(papers[0].id);
                }
            } else {
                setSelectedPaperId("");
            }
        } catch {
            setExamPapers([]);
            setSelectedPaperId("");
        }
    }, [subjectId, semester]);

    useEffect(() => {
        loadPapers();
    }, [loadPapers]);

    // ——— Cleanup interval khi unmount ———
    useEffect(() => {
        return () => {
            if (teviPollRef.current) clearInterval(teviPollRef.current);
        };
    }, []);

    // ——— Hành động tường minh: Bấm nút để tải ma trận đề ———
    const handleLoadAnalysis = useCallback(async (paperId: string) => {
        if (!paperId) return;
        setLoadingItems(true);
        setAnalyzeError(null);
        try {
            const detail = await api.get<ExamPaperDetail>(`/exam-papers/${paperId}`);
            setCdi(detail.content_difficulty);
            setRawText(detail.raw_text ?? null);

            const aiAnalysis = detail.ai_analysis;
            const ca = aiAnalysis?.content_analysis;
            if (ca?.items && Array.isArray(ca.items)) {
                setItems(ca.items);
            } else {
                setItems([]);
            }
            setLoadedPaperId(paperId);
        } catch {
            setItems([]);
            setCdi(null);
            setRawText(null);
            setLoadedPaperId(null);
            setAnalyzeError("Không thể tải kết quả phân tích cho đề này.");
        } finally {
            setLoadingItems(false);
        }
    }, []);

    // Tự động load 1 lần khi chọn đề lần đầu nếu danh sách trống
    useEffect(() => {
        if (selectedPaperId && !loadedPaperId && !analyzing && subTab === "existing") {
            handleLoadAnalysis(selectedPaperId);
        }
    }, [selectedPaperId, loadedPaperId, analyzing, subTab, handleLoadAnalysis]);

    // ——— Polling TEVI analysis ———
    const startPoll = useCallback((paperId: number) => {
        setAnalyzing(true);
        stepRef.current = "extract";
        setTeviStep("extract");
        setAnalyzeError(null);
        if (teviPollRef.current) clearInterval(teviPollRef.current);

        teviPollRef.current = setInterval(async () => {
            try {
                const detail = await api.get<ExamPaperDetail>(`/exam-papers/${paperId}`);

                if (detail.content_analyzed_at && stepRef.current === "extract") {
                    stepRef.current = "decompose";
                    setTeviStep("decompose");
                }
                const itemsArr = detail.ai_analysis?.content_analysis?.items;
                if (itemsArr && itemsArr.length > 0 && stepRef.current === "decompose") {
                    stepRef.current = "cdi";
                    setTeviStep("cdi");
                }
                if (detail.content_difficulty != null && stepRef.current === "cdi") {
                    stepRef.current = "done";
                    setTeviStep("done");
                }

                if (detail.content_analyzed_at) {
                    if (detail.ai_analysis?.error) {
                        if (teviPollRef.current) clearInterval(teviPollRef.current);
                        teviPollRef.current = null;
                        setAnalyzing(false);
                        setAnalyzeError("AI phân tích thất bại: " + detail.ai_analysis.error);
                        return;
                    }
                    if (stepRef.current === "done" || (itemsArr && itemsArr.length > 0)) {
                        if (teviPollRef.current) clearInterval(teviPollRef.current);
                        teviPollRef.current = null;
                        setAnalyzing(false);
                        setSelectedPaperId(String(paperId));
                        setSubTab("existing");
                        setToastMsg("Phân tích AI hoàn tất! Đã nạp ma trận câu hỏi bên dưới.");
                        handleLoadAnalysis(String(paperId));
                    }
                }
            } catch { /* retry */ }
        }, 2000);

        setTimeout(() => {
            if (teviPollRef.current) {
                clearInterval(teviPollRef.current);
                teviPollRef.current = null;
                setAnalyzing(false);
                setAnalyzeError("Quá thời gian chờ AI phân tích.");
            }
        }, 120_000);
    }, [handleLoadAnalysis]);

    // ——— Upload ———
    const handleUpload = useCallback(async () => {
        if (!subjectId || !file || !title.trim()) {
            setUploadError("Vui lòng chọn môn, nhập tên đề và chọn file.");
            return;
        }
        setUploadBusy(true);
        setUploadError(null);
        setAnalyzeError(null);
        try {
            const form = new FormData();
            form.set("subject_id", subjectId);
            form.set("semester_id", semester);
            form.set("title", title.trim());
            if (gradeId) form.set("grade_id", gradeId);
            form.set("file", file);

            const paper = await api.upload<ExamPaper>("/exam-papers", form);
            setExamPapers((prev) => [paper, ...prev]);
            setSelectedPaperId(paper.id);
            setTitle("");
            setFile(null);
            if (fileInputRef.current) fileInputRef.current.value = "";
            startPoll(Number(paper.id));
        } catch (e: any) {
            setUploadError(e instanceof ApiError ? e.message : "Tải đề lên thất bại.");
        } finally {
            setUploadBusy(false);
        }
    }, [subjectId, semester, gradeId, file, title, startPoll]);

    // ——— Gom nhóm câu hỏi thông minh (Smart Grouping) ———
    const groupedQuestions = useMemo<GroupedQuestion[]>(() => {
        const groups: GroupedQuestion[] = [];
        const map = new Map<string, GroupedQuestion>();

        items.forEach((item) => {
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
    }, [items]);

    const totalWeight = items.reduce((s, it) => s + it.weight, 0);

    return (
        <div className="space-y-5">
            {/* Toast Banner */}
            {toastMsg && (
                <div className="rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300 flex items-center justify-between shadow-xs animate-in fade-in">
                    <span className="flex items-center gap-2">
                        <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
                        {toastMsg}
                    </span>
                    <button onClick={() => setToastMsg(null)} className="text-emerald-500 hover:text-emerald-700 p-1">
                        <X className="w-4 h-4" />
                    </button>
                </div>
            )}

            {/* ===== Card Header Bộ lọc & Sub-tabs ===== */}
            <div className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden">
                {/* Thanh Bộ lọc Chung */}
                <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <Layers className="w-5 h-5 text-brand-600" />
                            Phân Tích Chi Tiết Đề Thi & Ma Trận Câu Hỏi
                        </h3>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                            Bóc tách từng câu hỏi, định vị đơn vị kiến thức SGK và đánh giá mức độ nhận thức theo chuẩn Bloom
                        </p>
                    </div>

                    {/* Dropdowns Môn / Khối / Học kỳ */}
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
                                options={GRADE_OPTIONS.map((g) => ({ value: g, label: `Khối ${g}` }))}
                                value={gradeId}
                                onChange={setGradeId}
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

                {/* Sub-tab Bar: Tách biệt hoàn toàn 2 ý định */}
                <div className="flex border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/30">
                    <button
                        onClick={() => setSubTab("existing")}
                        className={`flex-1 px-5 py-3 text-sm font-semibold border-b-2 transition-colors flex items-center justify-center gap-2 ${subTab === "existing"
                            ? "border-brand-600 text-brand-600 bg-white dark:bg-slate-900"
                            : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                            }`}
                    >
                        <FolderOpen className="w-4 h-4" />
                        <span>Chọn đề đã có trong thư viện ({examPapers.length})</span>
                    </button>
                    <button
                        onClick={() => setSubTab("upload")}
                        className={`flex-1 px-5 py-3 text-sm font-semibold border-b-2 transition-colors flex items-center justify-center gap-2 ${subTab === "upload"
                            ? "border-brand-600 text-brand-600 bg-white dark:bg-slate-900"
                            : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                            }`}
                    >
                        <Upload className="w-4 h-4" />
                        <span>Tải lên đề thi mới (AI phân tích)</span>
                    </button>
                </div>

                {/* Sub-tab Content */}
                <div className="p-5">
                    {subTab === "existing" ? (
                        /* Luồng 1: Chọn đề có sẵn */
                        <div className="flex flex-wrap items-center gap-3">
                            <div className="min-w-[280px] flex-1">
                                <SearchableSelect
                                    options={
                                        examPapers.length > 0
                                            ? examPapers.map((p) => ({
                                                value: p.id,
                                                label: `${p.title} ${p.content_difficulty !== null && p.content_difficulty !== undefined ? `(CDI: ${Number(p.content_difficulty).toFixed(2)})` : "(Chưa có CDI)"}`,
                                            }))
                                            : [{ value: "", label: "Chưa có đề trong môn/kỳ này — hãy chuyển tab Tải lên" }]
                                    }
                                    value={selectedPaperId}
                                    onChange={setSelectedPaperId}
                                    placeholder={examPapers.length > 0 ? "Chọn đề thi muốn xem ma trận..." : ""}
                                    className="w-full"
                                />
                            </div>
                            <button
                                onClick={() => handleLoadAnalysis(selectedPaperId)}
                                disabled={loadingItems || !selectedPaperId}
                                className="px-6 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2 shadow-xs transition-colors"
                            >
                                {loadingItems ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        Đang tải...
                                    </>
                                ) : (
                                    <>
                                        <BarChart3 className="w-4 h-4" />
                                        Xem Chi Tiết Ma Trận
                                    </>
                                )}
                            </button>
                        </div>
                    ) : (
                        /* Luồng 2: Form Tải lên đề mới sạch sẽ */
                        <div className="space-y-4 max-w-3xl">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1 block">
                                        Tên đề thi <span className="text-rose-500">*</span>
                                    </label>
                                    <input
                                        type="text"
                                        value={title}
                                        onChange={(e) => setTitle(e.target.value)}
                                        placeholder="VD: Đề cuối kỳ 1 Toán 6 - THCS Lê Quý Đôn"
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
                                        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                                        className="block w-full text-sm text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100 dark:file:bg-brand-900/30 dark:file:text-brand-300"
                                    />
                                </div>
                            </div>

                            <div className="flex items-center gap-3">
                                <button
                                    onClick={handleUpload}
                                    disabled={uploadBusy || analyzing || !subjectId || !file || !title.trim()}
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
                                    <span className="text-xs text-rose-600 font-medium flex items-center gap-1">
                                        <AlertCircle className="w-3.5 h-3.5" />
                                        {uploadError}
                                    </span>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Stepper tiến trình TEVI */}
            {analyzing && (
                <div className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden animate-in fade-in duration-200">
                    <div className="px-5 py-3.5 border-b border-slate-100 dark:border-slate-800 flex items-center gap-2 bg-slate-50/60 dark:bg-slate-950/40">
                        <Loader2 className="w-4 h-4 text-brand-600 animate-spin" />
                        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">
                            AI đang bóc tách và phân tích ma trận đề thi...
                        </h3>
                    </div>
                    <div className="p-5 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                        {(["extract", "decompose", "cdi", "done"] as TeviStep[]).map((step, idx) => {
                            const stepIndex = ["extract", "decompose", "cdi", "done"].indexOf(teviStep);
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

            {analyzeError && (
                <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 px-4 py-3 text-sm text-rose-700 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{analyzeError}</span>
                </div>
            )}

            {/* Loading items */}
            {loadingItems && (
                <div className="bg-white dark:bg-slate-900 border rounded-2xl p-8 flex items-center justify-center gap-3 text-sm text-slate-500 shadow-sm animate-pulse">
                    <Loader2 className="w-5 h-5 animate-spin text-brand-600" />
                    <span>Đang tải kết quả phân tích ma trận câu hỏi...</span>
                </div>
            )}

            {/* ===== BẢNG MA TRẬN CÂU HỎI ĐÃ GOM NHÓM (Chỉ hiện khi ở tab Xem hoặc vừa phân tích xong) ===== */}
            {!analyzing && !loadingItems && groupedQuestions.length > 0 && (
                <div className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden space-y-4 animate-in fade-in">
                    {/* Header */}
                    <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-950/30">
                        <div>
                            <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                <Layers className="w-4 h-4 text-brand-600" />
                                Ma Trận Câu Hỏi & Đơn Vị Kiến Thức Đánh Giá
                            </h3>
                            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                                Gom nhóm theo từng câu hỏi thực tế trong đề ({groupedQuestions.length} câu hỏi lớn · {items.length} ý đánh giá)
                            </p>
                        </div>
                        <div className="flex items-center gap-3">
                            {cdi !== null && (
                                <span className="px-3 py-1 rounded-full text-xs font-black bg-brand-50 text-brand-700 dark:bg-brand-950/40 dark:text-brand-300 border border-brand-200">
                                    CDI: {cdi.toFixed(3)}
                                </span>
                            )}
                            {rawText && (
                                <button onClick={() => setShowRawText(true)} className="text-xs text-brand-600 underline underline-offset-2 hover:text-brand-700 font-medium">
                                    Xem nguyên văn đề
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Danh sách Thẻ Câu Hỏi */}
                    <div className="p-5 space-y-4">
                        {groupedQuestions.map((q) => {
                            const isSingle = q.subItems.length === 1;

                            return (
                                <div
                                    key={q.id}
                                    className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-800/40 p-4 space-y-3 hover:border-brand-300 dark:hover:border-brand-700 transition-all shadow-xs"
                                >
                                    {/* Header Thẻ Câu */}
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
                                                    {!isSingle && (
                                                        <span className="flex items-center gap-1 text-[11px] text-slate-400 font-medium">
                                                            <Target className="w-3.5 h-3.5 text-brand-600 shrink-0" />
                                                            <span>Tích hợp {q.subItems.length} mục tiêu kiến thức SGK:</span>
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        </div>

                                        {/* Badge tổng trọng số */}
                                        <div className="text-right shrink-0">
                                            <span className="text-[10px] text-slate-400 block">Tổng trọng số:</span>
                                            <span className="font-black text-xs text-brand-600 dark:text-brand-400">
                                                {(q.totalWeight * 100).toFixed(1)}% điểm
                                            </span>
                                        </div>
                                    </div>

                                    {/* Preview ảnh cắt của câu hỏi từ đề gốc (Chỉ khi câu có hình vẽ: has_figure=true) */}
                                    {q.image_url && q.has_figure && (
                                        <div className="rounded-xl overflow-hidden border border-slate-200/80 dark:border-slate-700 bg-slate-50/70 dark:bg-slate-900/60 p-2.5 space-y-2">
                                            <div className="flex items-center justify-between text-[11px] text-slate-500 font-medium">
                                                <span className="flex items-center gap-1.5 text-brand-600 dark:text-brand-400 font-semibold">
                                                    <ImageIcon className="w-3.5 h-3.5" />
                                                    <span>Ảnh trích xuất từ đề gốc</span>
                                                </span>
                                                <button
                                                    type="button"
                                                    onClick={() => setSelectedImageModal({ url: q.image_url!, title: `Câu #${q.questionNumber} - Đề gốc` })}
                                                    className="inline-flex items-center gap-1 text-slate-500 hover:text-brand-600 font-medium transition-colors cursor-pointer"
                                                >
                                                    <ZoomIn className="w-3.5 h-3.5" />
                                                    <span>Phóng to</span>
                                                </button>
                                            </div>
                                            <div
                                                onClick={() => setSelectedImageModal({ url: q.image_url!, title: `Câu #${q.questionNumber} - Đề gốc` })}
                                                className="cursor-pointer group relative rounded-lg overflow-hidden border border-slate-200/60 dark:border-slate-800 max-h-48 bg-white dark:bg-slate-950 flex items-center justify-center p-1"
                                            >
                                                <img
                                                    src={q.image_url}
                                                    alt={`Câu #${q.questionNumber}`}
                                                    className="max-h-44 w-auto object-contain transition-transform group-hover:scale-[1.02]"
                                                />
                                                <div className="absolute inset-0 bg-slate-900/0 group-hover:bg-slate-900/10 transition-colors flex items-center justify-center">
                                                    <span className="opacity-0 group-hover:opacity-100 bg-black/70 text-white text-[10px] px-2 py-1 rounded-md font-medium transition-opacity">
                                                        Bấm để phóng to
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Danh sách các Ý / Năng lực con bên trong câu */}
                                    <div className="space-y-2 pt-1">
                                        {q.subItems.map((sub, idx) => {
                                            const isPrimary = sub.is_primary ?? (idx === 0 || (sub.question_share ?? 0) >= 0.5);
                                            const sharePct = sub.question_share != null
                                                ? Math.round(sub.question_share * 100)
                                                : (isSingle ? 100 : Math.round((sub.weight / (q.totalWeight || 1)) * 100));

                                            return (
                                                <div
                                                    key={idx}
                                                    className={`p-3 rounded-xl border transition-colors ${
                                                        isPrimary && !isSingle
                                                            ? "bg-brand-50/40 dark:bg-brand-950/20 border-brand-200/80 dark:border-brand-800/60"
                                                            : "bg-slate-50/80 dark:bg-slate-800/60 border-slate-100 dark:border-slate-700/60"
                                                    } space-y-1.5`}
                                                >
                                                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                                                        {/* Trái: Vị trí bài học SGK & Badge Trọng tâm chính / Tích hợp */}
                                                        <div className="flex items-center gap-2 min-w-0 flex-1">
                                                            <BookOpen className={`w-4 h-4 shrink-0 ${isPrimary && !isSingle ? "text-brand-600 dark:text-brand-400" : "text-slate-500"}`} />
                                                            <div className="min-w-0 flex items-center gap-2 flex-wrap">
                                                                <span className="font-semibold text-slate-900 dark:text-white">
                                                                    {sub.unit_name ?? sub.topic}
                                                                </span>
                                                                {sub.node_ref?.chapter && (
                                                                    <span className="text-slate-400 text-[11px] hidden sm:inline">
                                                                        ({sub.node_ref.chapter})
                                                                    </span>
                                                                )}
                                                                {!isSingle && (
                                                                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold ${
                                                                        isPrimary
                                                                            ? "bg-brand-100 text-brand-700 dark:bg-brand-900/50 dark:text-brand-300 border border-brand-200 dark:border-brand-800"
                                                                            : "bg-slate-200/70 text-slate-600 dark:bg-slate-700/60 dark:text-slate-300 border border-slate-300/60 dark:border-slate-600"
                                                                    }`}>
                                                                        {isPrimary ? <Target className="w-3 h-3" /> : <Layers className="w-3 h-3" />}
                                                                        <span>{isPrimary ? "Trọng tâm chính" : "Tích hợp / Bổ trợ"} ({sharePct}% câu)</span>
                                                                    </span>
                                                                )}
                                                            </div>
                                                        </div>

                                                        {/* Phải: Trọng số của ý trên toàn đề */}
                                                        <div className="flex items-center gap-2.5 shrink-0">
                                                            <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 min-w-[45px] text-right">
                                                                {(sub.weight * 100).toFixed(1)}% điểm đề
                                                            </span>
                                                        </div>
                                                    </div>

                                                    {/* Căn cứ / Lý do phân loại của AI */}
                                                    {(sub.reason || (sub.topic && sub.topic !== sub.unit_name)) && (
                                                        <p className="text-[11px] text-slate-500 dark:text-slate-400 pl-6 leading-relaxed">
                                                            <span className="font-medium text-slate-600 dark:text-slate-300">Căn cứ:</span> {sub.reason || sub.topic}
                                                        </p>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    {/* Footer tóm tắt & Nút chuyển tiếp liền mạch sang Dự Báo Pass/Fail */}
                    <div className="p-4 bg-gradient-to-r from-brand-50/60 via-indigo-50/40 to-slate-50 dark:from-brand-950/30 dark:via-indigo-950/20 dark:to-slate-900 border-t border-brand-100 dark:border-brand-900 flex flex-col sm:flex-row items-center justify-between gap-3">
                        <div className="text-xs text-slate-600 dark:text-slate-300">
                            <span>Tổng trọng số ma trận: <strong>{(totalWeight * 100).toFixed(1)}%</strong></span>
                            <span className="text-slate-400 ml-2">({groupedQuestions.length} câu hỏi lớn)</span>
                        </div>
                        {selectedPaperId && (
                            <Link
                                href={`/pass-fail-forecast?exam_paper_id=${selectedPaperId}&subject_id=${subjectId}&semester=${semester}`}
                                className="px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs flex items-center gap-2 shadow-xs transition-colors shrink-0"
                            >
                                <Target className="w-4 h-4" />
                                <span>Xem Dự Báo Đậu/Trượt Cả Lớp Cho Đề Này</span>
                                <ArrowRight className="w-4 h-4" />
                            </Link>
                        )}
                    </div>
                </div>
            )}

            {/* Khi không có câu hỏi nào và không đang tải */}
            {!analyzing && !loadingItems && items.length === 0 && selectedPaperId && !analyzeError && (
                <div className="rounded-2xl bg-white dark:bg-slate-900 border p-8 text-center text-sm text-slate-400 space-y-1">
                    <p className="font-semibold text-slate-600 dark:text-slate-300">Đề thi chưa có kết quả phân tích</p>
                    <p className="text-xs">Vui lòng chọn đề khác hoặc tải đề mới lên để AI bóc tách.</p>
                </div>
            )}

            {/* Raw text modal */}
            {showRawText && rawText && (
                <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-12" onClick={() => setShowRawText(false)}>
                    <div className="w-full max-w-3xl bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
                            <h3 className="font-bold text-slate-900 dark:text-white">Nguyên văn đề thi</h3>
                            <button onClick={() => setShowRawText(false)} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
                                <X className="w-5 h-5 text-slate-500" />
                            </button>
                        </div>
                        <div className="overflow-auto p-5">
                            <pre className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap font-sans leading-relaxed">{rawText}</pre>
                        </div>
                    </div>
                </div>
            )}

            {/* Modal Phóng to Ảnh Cắt Câu Hỏi */}
            {selectedImageModal && (
                <div
                    className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-200"
                    onClick={() => setSelectedImageModal(null)}
                >
                    <div
                        className="bg-white dark:bg-slate-900 rounded-2xl max-w-3xl max-h-[90vh] w-full overflow-hidden shadow-2xl flex flex-col"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
                            <h4 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
                                <ImageIcon className="w-4 h-4 text-brand-600" />
                                <span>{selectedImageModal.title}</span>
                            </h4>
                            <button
                                onClick={() => setSelectedImageModal(null)}
                                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <div className="p-6 overflow-auto flex items-center justify-center bg-slate-50/50 dark:bg-slate-950/50">
                            <img
                                src={selectedImageModal.url}
                                alt={selectedImageModal.title}
                                className="max-h-[70vh] w-auto object-contain rounded-lg shadow-sm border border-slate-200 dark:border-slate-800"
                            />
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}