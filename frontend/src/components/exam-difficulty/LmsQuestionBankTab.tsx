"use client";

// Tab "Ngân hàng câu hỏi LMS" (trang Phân tích độ khó đề thi /exam-difficulty).
// Danh sách câu hỏi kèm thống kê làm bài:
// - Phân định rõ ràng: Bài do GV gán (LMS ban đầu) vs. Bài do AI Phân tách (lms_question_unit)
// - Mức độ Bloom (AI)
// - Background Job & Thanh tiến trình Realtime

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Cpu,
  Database,
  Layers,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";
import SearchableSelect from "@/components/SearchableSelect";
import { api } from "@/lib/api";
import type { LmsQuestionBankItem } from "@/lib/types";

const PAGE_SIZE = 12;

const BLOOM_LABELS: Record<number, string> = {
  1: "Nhớ",
  2: "Hiểu",
  3: "Vận dụng",
  4: "Phân tích",
  5: "Đánh giá",
  6: "Sáng tạo",
};

const BLOOM_COLORS: Record<number, string> = {
  1: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  2: "bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  3: "bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300",
  4: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  5: "bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300",
  6: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300",
};

function accuracyColor(acc: number | null): string {
  if (acc === null) return "text-slate-400";
  if (acc < 0.4) return "text-rose-600 dark:text-rose-400";
  if (acc < 0.6) return "text-amber-600 dark:text-amber-400";
  return "text-emerald-600 dark:text-emerald-400";
}

interface JobStatus {
  job_id: string | null;
  subject_id: number | null;
  status: "idle" | "pending" | "running" | "completed" | "failed";
  total_questions: number;
  processed_questions: number;
  progress_percent: number;
  bloom_distribution: Record<number, number>;
  unclassified_remaining: number;
  error_message: string | null;
  message: string;
}

export default function LmsQuestionBankTab() {
  const [subjects, setSubjects] = useState<{ id: string; name: string }[]>([]);
  const [subjectId, setSubjectId] = useState<string>("106"); // mặc định Toán 6 (mock)
  const [search, setSearch] = useState("");
  const [bloomFilter, setBloomFilter] = useState<string>("ALL"); // 'ALL' | 'UNCLASSIFIED' | 'CLASSIFIED'
  const [page, setPage] = useState(1);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<LmsQuestionBankItem[]>([]);

  // Tùy chọn Phân tích AI trực tiếp trên giao diện (chuẩn hóa danh mục như trang nạp SGK)
  const [selectedModel, setSelectedModel] = useState<string>("google/gemini-3.7-flash");
  const [customModel, setCustomModel] = useState<string>("");
  const [limitChoice, setLimitChoice] = useState<number | null>(20); // Mặc định 20 câu để test nhanh
  const [reAnalyze, setReAnalyze] = useState(false);
  const [analyzeMsg, setAnalyzeMsg] = useState<string | null>(null);

  // Background Job & Realtime Progress State
  const [jobState, setJobState] = useState<JobStatus | null>(null);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const isRunning = jobState?.status === "pending" || jobState?.status === "running";

  // Danh sách môn từ s360.dim_subject
  useEffect(() => {
    api
      .get<{ id: number; name: string }[]>("/knowledge-gaps/subject-options")
      .then((list) => setSubjects((list ?? []).map((s) => ({ id: String(s.id), name: s.name }))))
      .catch(() => setError("Không tải được danh sách môn học."));
  }, []);

  const fetchBank = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (subjectId) params.set("subject_id", subjectId);
      const data = await api.get<LmsQuestionBankItem[]>(`/knowledge-gaps/lms-question-bank?${params.toString()}`);
      setItems(data || []);
      setPage(1);
    } catch (e: any) {
      setError(e?.message ?? "Không tải được ngân hàng câu hỏi LMS.");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [subjectId]);

  useEffect(() => {
    fetchBank();
  }, [fetchBank]);

  // Kiểm tra trạng thái Job hiện tại (khi đổi môn hoặc khi load lại trang)
  const checkJobStatus = useCallback(async () => {
    if (!subjectId) return;
    try {
      const res = await api.get<JobStatus>(`/knowledge-gaps/lms-question-bank/analyze/status?subject_id=${subjectId}`);
      if (res && res.status !== "idle") {
        setJobState(res);
      }
    } catch {
      // Bỏ qua lỗi check status nhẹ
    }
  }, [subjectId]);

  useEffect(() => {
    checkJobStatus();
  }, [checkJobStatus]);

  // Vòng lặp Polling tiến độ thời gian thực
  useEffect(() => {
    if (!isRunning || !subjectId) {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      return;
    }

    pollTimerRef.current = setInterval(async () => {
      try {
        const res = await api.get<JobStatus>(`/knowledge-gaps/lms-question-bank/analyze/status?subject_id=${subjectId}`);
        if (res) {
          setJobState(res);
          if (res.status === "completed") {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
            let bloomSummary = "";
            if (res.bloom_distribution && Object.keys(res.bloom_distribution).length > 0) {
              bloomSummary = Object.entries(res.bloom_distribution)
                .map(([b, count]) => `${BLOOM_LABELS[parseInt(b, 10)] ?? `Bậc ${b}`}: ${count}`)
                .join(" · ");
            }
            setAnalyzeMsg(
              res.message +
                (bloomSummary ? ` (Phân bố: ${bloomSummary})` : "") +
                (res.unclassified_remaining > 0 ? ` — Còn ${res.unclassified_remaining} câu chưa phân tích.` : "")
            );
            await fetchBank();
          } else if (res.status === "failed") {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
            setError(res.error_message || "Tác vụ phân tích AI gặp sự cố.");
          }
        }
      } catch (e: any) {
        // Tạm bỏ qua lỗi mạng lẻ trong lúc polling
      }
    }, 1200);

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [isRunning, subjectId, fetchBank]);

  // Xử lý gửi yêu cầu Khởi tạo Background Job Phân tích AI
  const handleStartAnalysis = async () => {
    if (!subjectId || isRunning) return;
    setError(null);
    setAnalyzeMsg(null);

    const actualModel = selectedModel === "custom" ? (customModel.trim() || "google/gemini-3.7-flash") : selectedModel;

    try {
      const res = await api.post<{ success: boolean; job_id: string; message: string }>(
        "/knowledge-gaps/lms-question-bank/analyze",
        {
          subject_id: parseInt(subjectId, 10),
          model_name: actualModel,
          re_analyze: reAnalyze,
          limit: limitChoice,
        }
      );

      setJobState({
        job_id: res.job_id,
        subject_id: parseInt(subjectId, 10),
        status: "pending",
        total_questions: limitChoice || 0,
        processed_questions: 0,
        progress_percent: 0,
        bloom_distribution: {},
        unclassified_remaining: 0,
        error_message: null,
        message: "Đang khởi tạo tác vụ phân tích AI...",
      });
    } catch (e: any) {
      setError(e?.message ?? "Lỗi khi bắt đầu phân tích câu hỏi bằng AI.");
    }
  };

  // Lọc nhanh phía client theo mã câu/bài/tên chương/nội dung/trạng thái Bloom
  const filtered = useMemo(() => {
    let list = items;
    if (bloomFilter === "UNCLASSIFIED") {
      list = list.filter((it) => it.bloom_level === null);
    } else if (bloomFilter === "CLASSIFIED") {
      list = list.filter((it) => it.bloom_level !== null);
    }

    const q = search.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (it) =>
        String(it.question_id).includes(q) ||
        String(it.assignment_id).includes(q) ||
        (it.unit_name ?? "").toLowerCase().includes(q) ||
        (it.chapter ?? "").toLowerCase().includes(q) ||
        (it.question_text ?? "").toLowerCase().includes(q)
    );
  }, [items, search, bloomFilter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageItems = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const stats = useMemo(() => {
    const active = items.filter((i) => i.is_active === 1).length;
    const unclassified = items.filter((i) => i.bloom_level === null).length;
    const classified = items.filter((i) => i.bloom_level !== null).length;
    const unmapped = items.filter((i) => i.unit_id === null).length;
    const multi = items.filter((i) => i.units.length > 1).length;
    const withResp = items.filter((i) => i.n_responses !== null && i.n_responses > 0);
    const avgAcc =
      withResp.length > 0
        ? withResp.reduce((s, i) => s + (i.accuracy ?? 0), 0) / withResp.length
        : null;
    return {
      total: items.length,
      active,
      unclassified,
      classified,
      unmapped,
      multi,
      withResp: withResp.length,
      avgAcc,
    };
  }, [items]);

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-3.5 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-500 block">Tổng câu hỏi</span>
          <span className="text-xl font-bold text-slate-900 dark:text-slate-100">{stats.total}</span>
        </div>
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-3.5 shadow-sm">
          <span className="text-[11px] font-semibold text-indigo-600 block">Đã gắn Bloom</span>
          <span className="text-xl font-bold text-indigo-600">{stats.classified}</span>
        </div>
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-3.5 shadow-sm">
          <span className="text-[11px] font-semibold text-amber-600 block">Chưa phân tích</span>
          <span className="text-xl font-bold text-amber-600">{stats.unclassified}</span>
        </div>
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-3.5 shadow-sm">
          <span className="text-[11px] font-semibold text-sky-600 block">Câu đa bài (AI)</span>
          <span className="text-xl font-bold text-sky-600">{stats.multi}</span>
        </div>
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-3.5 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-500 block">Câu HS đã làm</span>
          <span className="text-xl font-bold text-slate-900 dark:text-slate-100">{stats.withResp}</span>
        </div>
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-3.5 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-500 block">Độ đúng TB</span>
          <span className={`text-xl font-bold ${accuracyColor(stats.avgAcc)}`}>
            {stats.avgAcc !== null ? `${(stats.avgAcc * 100).toFixed(0)}%` : "—"}
          </span>
        </div>
      </div>

      {/* BẢNG ĐIỀU KHIỂN PHÂN TÍCH AI (Background Task + Progress Bar) */}
      <div className="bg-gradient-to-r from-indigo-50/90 via-purple-50/50 to-slate-50 dark:from-indigo-950/40 dark:via-purple-950/20 dark:to-slate-900 border border-indigo-200/90 dark:border-indigo-800/80 rounded-2xl p-4 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-indigo-100/80 dark:border-indigo-900/50 pb-2.5">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-500/20">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                Phân Tích AI: Gán Mức Độ Bloom & Phân Tách Bài Học
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-300">
                  {stats.unclassified} câu chưa gán Bloom
                </span>
                {isRunning && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-300 animate-pulse flex items-center gap-1">
                    <Loader2 className="w-3 h-3 animate-spin" /> Đang chạy ngầm
                  </span>
                )}
              </h4>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Tự động đọc đề bài, đối chiếu cây SGK để phân loại Bloom 1–6 và phân tách vào đúng các bài học con.
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end pt-1">
          {/* 1. Chọn Model AI (Khớp chuẩn trang nạp SGK) */}
          <div className={selectedModel === "custom" ? "md:col-span-3" : "md:col-span-4"}>
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
              <Bot className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              Mô hình AI:
            </label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={isRunning}
              className="w-full py-2 px-3 rounded-xl border border-indigo-200 dark:border-indigo-800 bg-white dark:bg-slate-800 text-xs font-medium text-slate-800 dark:text-slate-200 outline-none focus:ring-2 focus:ring-indigo-500/40 disabled:opacity-60"
            >
              <optgroup label="OpenRouter (Khuyên dùng)">
                <option value="google/gemini-3.7-flash">⚡ Google Gemini 3.7 Flash (Mới nhất, siêu rẻ & nhanh)</option>
                <option value="xiaomi/mimo-v2.5">⚡ Xiaomi Mimo 2.5</option>
                <option value="openai/gpt-4o-mini">⚡ OpenAI GPT-4o Mini</option>
                <option value="qwen/qwen-2.5-vl-72b-instruct">⚡ Qwen 2.5 VL 72B Instruct</option>
              </optgroup>
              <optgroup label="ShopAIKey / DashScope">
                <option value="qwen3-vl-flash">🇨🇳 Qwen 3 VL Flash (ShopAIKey)</option>
              </optgroup>
              <option value="custom">✏️ Tùy chỉnh Model ID...</option>
            </select>
          </div>

          {/* Ô nhập Custom Model ID nếu chọn tùy chỉnh */}
          {selectedModel === "custom" && (
            <div className="md:col-span-2">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                Nhập Model ID:
              </label>
              <input
                type="text"
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                placeholder="vd: google/gemini-2.0-flash-001"
                disabled={isRunning}
                className="w-full py-2 px-3 rounded-xl border border-indigo-200 dark:border-indigo-800 bg-white dark:bg-slate-800 text-xs text-slate-800 dark:text-slate-200 outline-none focus:ring-2 focus:ring-indigo-500/40 disabled:opacity-60"
              />
            </div>
          )}

          {/* 2. Chọn Phạm vi kiểm thử (10 câu / 20 câu / Toàn bộ) */}
          <div className={selectedModel === "custom" ? "md:col-span-4" : "md:col-span-5"}>
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              Phạm vi phân tách:
            </label>
            <div className="flex items-center gap-1.5 flex-wrap">
              <button
                type="button"
                onClick={() => setLimitChoice(10)}
                disabled={isRunning}
                className={`py-2 px-3 rounded-xl text-xs font-semibold transition-all ${
                  limitChoice === 10
                    ? "bg-indigo-600 text-white shadow-sm shadow-indigo-500/30"
                    : "bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50"
                } disabled:opacity-60`}
              >
                Thử 10 câu
              </button>
              <button
                type="button"
                onClick={() => setLimitChoice(20)}
                disabled={isRunning}
                className={`py-2 px-3 rounded-xl text-xs font-bold transition-all ${
                  limitChoice === 20
                    ? "bg-indigo-600 text-white shadow-sm shadow-indigo-500/30 ring-2 ring-indigo-400 dark:ring-indigo-600"
                    : "bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50"
                } disabled:opacity-60`}
              >
                Thử 20 câu (Khuyến nghị)
              </button>
              <button
                type="button"
                onClick={() => setLimitChoice(null)}
                disabled={isRunning}
                className={`py-2 px-3 rounded-xl text-xs font-semibold transition-all ${
                  limitChoice === null
                    ? "bg-indigo-600 text-white shadow-sm shadow-indigo-500/30"
                    : "bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50"
                } disabled:opacity-60`}
              >
                Toàn bộ ({stats.unclassified > 0 ? stats.unclassified : stats.total} câu)
              </button>
            </div>
          </div>

          {/* 3. Nút Bắt đầu Phân tích AI */}
          <div className="md:col-span-3 flex flex-col items-end gap-1.5">
            <label className="flex items-center gap-1.5 cursor-pointer text-[11px] font-medium text-slate-600 dark:text-slate-400 self-start md:self-end">
              <input
                type="checkbox"
                checked={reAnalyze}
                onChange={(e) => setReAnalyze(e.target.checked)}
                disabled={isRunning}
                className="rounded text-indigo-600 focus:ring-indigo-500/40 disabled:opacity-60"
              />
              <span>Phân tích lại (Ghi đè)</span>
            </label>

            <button
              onClick={handleStartAnalysis}
              disabled={isRunning || loading || !subjectId}
              className="w-full py-2 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold flex items-center justify-center gap-2 shadow-md shadow-indigo-500/30 transition-all disabled:opacity-60 hover:scale-[1.01] active:scale-[0.99]"
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Đang phân tích ngầm ({jobState?.processed_questions ?? 0}/{jobState?.total_questions ?? limitChoice ?? "..."})...
                </>
              ) : (
                <>
                  <Wand2 className="w-4 h-4 text-indigo-200" />
                  Bắt đầu phân tích {limitChoice ? `(${limitChoice} câu)` : "(Toàn bộ)"}
                </>
              )}
            </button>
          </div>
        </div>

        {/* THANH TIẾN TRÌNH REALTIME (PROGRESS BAR) */}
        {isRunning && jobState && (
          <div className="mt-3 pt-3 border-t border-indigo-100/80 dark:border-indigo-900/50 space-y-2 animate-in fade-in duration-300">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-600 dark:text-indigo-400" />
                <span className="font-semibold text-indigo-900 dark:text-indigo-200">
                  {jobState.message || `Đang xử lý ${jobState.processed_questions}/${jobState.total_questions} câu hỏi...`}
                </span>
              </div>
              <span className="font-mono font-bold text-indigo-600 dark:text-indigo-300 text-xs">
                {jobState.progress_percent}%
              </span>
            </div>

            {/* Animated Progress Track */}
            <div className="w-full h-2.5 rounded-full bg-indigo-100/80 dark:bg-indigo-950/80 overflow-hidden p-0.5 border border-indigo-200/60 dark:border-indigo-800/60">
              <div
                className="h-full rounded-full bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-600 transition-all duration-500 ease-out shadow-sm"
                style={{ width: `${Math.max(4, jobState.progress_percent)}%` }}
              />
            </div>

            {/* Phân bố Bloom trực tiếp khi đang chạy */}
            {jobState.bloom_distribution && Object.keys(jobState.bloom_distribution).length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                <span className="text-[10px] text-slate-400">Tạm tính:</span>
                {Object.entries(jobState.bloom_distribution)
                  .filter(([_, count]) => count > 0)
                  .map(([bloom, count]) => (
                    <span
                      key={bloom}
                      className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300"
                    >
                      Bậc {bloom}: {count}
                    </span>
                  ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Success Notification Banner */}
      {analyzeMsg && !isRunning && (
        <div className="rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300 flex items-center justify-between gap-3 animate-in fade-in duration-200">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
            <span>{analyzeMsg}</span>
          </div>
          <button onClick={() => setAnalyzeMsg(null)} className="text-emerald-500 hover:text-emerald-700 p-1">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 px-4 py-3 text-sm text-rose-700 dark:text-rose-300 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white dark:bg-slate-900 border rounded-2xl p-4 flex flex-wrap items-end gap-3 shadow-sm">
        <div className="min-w-[180px]">
          <label className="text-xs font-semibold text-slate-500 mb-1 block">Môn học</label>
          <SearchableSelect
            options={[{ value: "", label: "Tất cả các môn" }, ...subjects.map((s) => ({ value: s.id, label: s.name }))]}
            value={subjectId}
            onChange={setSubjectId}
            placeholder="Chọn môn..."
            className="min-w-[180px]"
          />
        </div>

        <div className="min-w-[150px]">
          <label className="text-xs font-semibold text-slate-500 mb-1 block">Bộ lọc Bloom</label>
          <select
            value={bloomFilter}
            onChange={(e) => {
              setBloomFilter(e.target.value);
              setPage(1);
            }}
            className="w-full py-2 px-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-800 dark:text-slate-200 outline-none focus:ring-2 focus:ring-brand-500/40"
          >
            <option value="ALL">Tất cả ({stats.total})</option>
            <option value="UNCLASSIFIED">Chưa gán Bloom ({stats.unclassified})</option>
            <option value="CLASSIFIED">Đã gán Bloom ({stats.classified})</option>
          </select>
        </div>

        <div className="min-w-[200px] flex-1">
          <label className="text-xs font-semibold text-slate-500 mb-1 block">Tìm nhanh</label>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Mã câu / nội dung / tên bài..."
              className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-800 dark:text-slate-200 placeholder:text-slate-400 outline-none focus:ring-2 focus:ring-brand-500/40"
            />
          </div>
        </div>

        <button
          onClick={fetchBank}
          disabled={loading || isRunning}
          className="px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 text-sm font-semibold flex items-center gap-1.5 disabled:opacity-50"
          title="Tải lại danh sách"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Làm mới
        </button>
      </div>

      {/* Table Section */}
      <section className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden space-y-4 p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-indigo-500" />
            <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              Danh Sách Câu Hỏi LMS ({filtered.length.toLocaleString()} Kết Quả)
            </h4>
          </div>
          <span className="text-xs text-slate-400">
            Hiển thị trang {safePage} / {totalPages} ({PAGE_SIZE} bản ghi/trang)
          </span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12 text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin text-indigo-500 mr-2" /> Đang tải ngân hàng câu hỏi...
          </div>
        ) : pageItems.length === 0 ? (
          <div className="py-12 text-center text-sm text-slate-400">
            Chưa có câu hỏi LMS nào phù hợp với bộ lọc.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-200 dark:border-slate-700">
                <tr>
                  <th className="py-3 px-4">Câu Hỏi</th>
                  <th className="py-3 px-4">Bài / Chương (GV Gán)</th>
                  <th className="py-3 px-4">AI Phân Tách Bài Học</th>
                  <th className="py-3 px-4 text-center">Mức độ Bloom</th>
                  <th className="py-3 px-4 text-center">Trạng Thái</th>
                  <th className="py-3 px-4 text-right" title="Số học sinh đã làm (best-attempt) và số học sinh trả lời đúng">HS Làm / Đúng</th>
                  <th className="py-3 px-4 text-right">Độ Đúng</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {pageItems.map((it) => {
                  const hasBloom = it.bloom_level !== null;
                  const bloomCls = hasBloom ? (BLOOM_COLORS[it.bloom_level!] ?? BLOOM_COLORS[3]) : "";
                  const acc = it.accuracy;
                  const hasAiUnits = it.units && it.units.length > 0;

                  return (
                    <tr key={it.question_id} className="group hover:bg-indigo-50/60 dark:hover:bg-slate-800/80 transition-colors">
                      {/* 1. Câu hỏi */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span className="inline-block px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-mono font-medium text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-700/80">
                            #{it.question_id}
                          </span>
                          <span className="font-mono text-[10px] text-slate-400">Bài #{it.assignment_id}</span>
                        </div>
                        <div className="mt-1 text-slate-800 dark:text-slate-200 leading-snug max-w-[340px]">
                          {it.question_text || "—"}
                        </div>
                        {it.question_type && it.question_type !== "MCQ" && (
                          <span className="inline-block mt-0.5 px-1.5 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-500 font-mono">
                            {it.question_type}
                          </span>
                        )}
                      </td>

                      {/* 2. Bài / Chương GỐC do Thầy cô gán ban đầu */}
                      <td className="py-3 px-4 min-w-[180px]">
                        <div className="font-semibold text-slate-800 dark:text-slate-200">
                          {it.unit_name ?? "Chưa gán bài"}
                        </div>
                        {it.chapter && it.chapter !== it.unit_name && (
                          <div className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5 truncate max-w-[200px]">
                            Chương: {it.chapter}
                          </div>
                        )}
                      </td>

                      {/* 3. TRƯỜNG RIÊNG: Các bài con do HỆ THỐNG AI PHÂN TÁCH CHO CÂU ĐÓ */}
                      <td className="py-3 px-4 min-w-[200px]">
                        {hasAiUnits ? (
                          <div className="space-y-1">
                            {it.units.map((u) => (
                              <div
                                key={u.unit_id}
                                className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200/70 dark:border-indigo-800/70 text-[11px] font-medium text-indigo-700 dark:text-indigo-300 mr-1.5 mb-1"
                                title={`AI phân tách vào bài: ${u.unit_name} (Đóng góp ${Math.round(u.weight * 100)}%)`}
                              >
                                <Sparkles className="w-3 h-3 text-indigo-500 shrink-0" />
                                <span className="font-semibold">{u.unit_name ?? `Bài #${u.unit_id}`}</span>
                                <span className="text-[10px] text-indigo-500 font-mono font-bold">
                                  {Math.round(u.weight * 100)}%
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-50 dark:bg-slate-800 text-slate-400 border border-dashed border-slate-300 dark:border-slate-700">
                            Chưa phân tách AI
                          </span>
                        )}
                      </td>

                      {/* 4. Mức độ Bloom (AI) */}
                      <td className="py-3 px-4 text-center whitespace-nowrap">
                        {hasBloom ? (
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${bloomCls}`}>
                            {it.bloom_level} — {BLOOM_LABELS[it.bloom_level!] ?? ""}
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-400 border border-dashed border-slate-300 dark:border-slate-700">
                            Chưa gán Bloom
                          </span>
                        )}
                      </td>

                      {/* 5. Trạng thái */}
                      <td className="py-3 px-4 text-center">
                        {it.is_active === 1 ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                            Hoạt động
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                            Tắt
                          </span>
                        )}
                      </td>

                      {/* 6. HS làm */}
                      <td className="py-3 px-4 text-right">
                        {it.n_responses !== null ? (
                          <div title={`${it.n_responses} học sinh đã làm câu này (best-attempt); trong đó ${it.n_correct ?? 0} học sinh trả lời đúng`}>
                            <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                              {it.n_responses}
                            </span>
                            <span className="text-slate-400 text-[10px]"> HS làm · </span>
                            <span className="font-mono text-emerald-600 dark:text-emerald-400">
                              {it.n_correct ?? 0}
                            </span>
                            <span className="text-slate-400 text-[10px]"> HS đúng</span>
                          </div>
                        ) : (
                          <span className="text-slate-300 dark:text-slate-600">—</span>
                        )}
                      </td>

                      {/* 7. Độ đúng */}
                      <td className="py-3 px-4 text-right">
                        {acc !== null ? (
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-16 h-1.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                              <div
                                className={`h-full rounded-full ${acc < 0.4 ? "bg-rose-500" : acc < 0.6 ? "bg-amber-500" : "bg-emerald-500"}`}
                                style={{ width: `${Math.round(acc * 100)}%` }}
                              />
                            </div>
                            <span className={`font-mono font-semibold ${accuracyColor(acc)}`}>
                              {(acc * 100).toFixed(0)}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-slate-300 dark:text-slate-600">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {!loading && totalPages > 1 && (
          <div className="flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-800">
            <span className="text-[11px] text-slate-400">
              Trang {safePage}/{totalPages} — {filtered.length} câu
            </span>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage <= 1}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage >= totalPages}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </section>

      <p className="text-[11px] text-slate-400 flex items-center gap-1.5 px-1">
        <Layers className="w-3.5 h-3.5 shrink-0" />
        Nguồn: bảng <code className="font-mono">lms_question_bank</code> (gốc GV gán) + <code className="font-mono">lms_question_unit</code> (kết quả AI phân tách bài con) + <code className="font-mono">lms_question_response</code> (độ đúng HS).
      </p>
    </div>
  );
}
