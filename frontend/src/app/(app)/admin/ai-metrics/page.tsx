"use client";

import { useEffect, useState, useMemo } from "react";
import {
  BarChart3,
  Clock,
  Coins,
  Cpu,
  HelpCircle,
  MessageSquareCode,
  ThumbsDown,
  ThumbsUp,
  Workflow,
  ChevronRight,
  Search,
  Code2,
  ShieldAlert,
  Calendar,
  AlertOctagon,
  MessageSquare,
  Activity,
  AlertTriangle,
  Gauge,
  Wrench,
  BadgeCheck
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
  ReferenceLine
} from "recharts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { AGENT_LABEL, type ObservabilitySummaryResponse } from "@/lib/types";

interface ThoughtLog {
  type: "status" | "thought";
  content: string;
  timestamp: number;
}

interface TelemetryMessageDetail {
  id: string;
  session_id: string;
  role: string;
  content: string;
  generated_sql: string | null;
  created_at: string;
  rating: number | null;
  feedback_tag: string | null;
  feedback_text: string | null;
  feedback_at: string | null;
  thought_trace: ThoughtLog[] | null;
  latency_ms: number | null;
  input_token_count: number | null;
  output_token_count: number | null;
  cost: number | null;
  llm_provider: string | null;
  model_used: string | null;
}

interface AiTelemetryStatsResponse {
  total_cost: number;
  avg_latency_ms: number;
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
  helpful_count: number;
  unhelpful_count: number;
  total_feedbacks: number;
  helpful_ratio: number;
  feedback_rate: number;
  positive_feedback_ratio: number | null;
  pii_flagged_count: number;
  total_sessions: number;
  total_requests: number;
  total_errors: number;
  error_rate: number;
  avg_cost_per_request: number;
  messages: TelemetryMessageDetail[];
}

interface SchoolTelemetryItem {
  school_id: string;
  school_name: string;
  total_requests: number;
  total_errors: number;
  error_rate: number;
  total_cost: number;
  avg_latency_ms: number;
}

interface SchoolTelemetryResponse {
  schools: SchoolTelemetryItem[];
}

interface ObservabilitySnapshotItem {
  captured_at: string;
  daily_cost_usd: number;
  daily_budget_usd: number;
  latency_p95_ms: number | null;
  ttft_p95_ms: number | null;
  faithfulness_avg: number | null;
  groundedness_avg: number | null;
  tool_success_rate: number | null;
  total_requests: number;
  total_tokens_in: number;
  total_tokens_out: number;
}

interface ObservabilityHistoryResponse {
  snapshots: ObservabilitySnapshotItem[];
}

const ALERT_TYPE_LABEL: Record<string, string> = {
  budget_warning: "Vượt ngân sách",
  faithfulness_degradation: "Suy thoái chất lượng",
  agent_runaway: "Agent kẹt vòng lặp",
  error_rate_high: "Tỷ lệ lỗi cao",
};

export default function AiMetricsPage() {
  const { user } = useAuth();

  const [stats, setStats] = useState<AiTelemetryStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMessage, setSelectedMessage] = useState<TelemetryMessageDetail | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterRating, setFilterRating] = useState<"all" | "helpful" | "unhelpful" | "unrated">("all");
  const [filterProvider, setFilterProvider] = useState<"all" | "openai" | "deepseek">("all");
  const [selectedDays, setSelectedDays] = useState<number | "all">(7);
  const [currentPage, setCurrentPage] = useState(1);

  const [activeTab, setActiveTab] = useState<"messages" | "health">("messages");
  const [health, setHealth] = useState<ObservabilitySummaryResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthLoadedOnce, setHealthLoadedOnce] = useState(false);

  const [historyDays, setHistoryDays] = useState(7);
  const [history, setHistory] = useState<ObservabilitySnapshotItem[] | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const [schoolStats, setSchoolStats] = useState<SchoolTelemetryItem[] | null>(null);
  const [schoolStatsLoading, setSchoolStatsLoading] = useState(false);
  const [schoolStatsError, setSchoolStatsError] = useState<string | null>(null);

  const loadHealth = () => {
    setHealthLoading(true);
    api.get<ObservabilitySummaryResponse>("/chat/admin/observability-summary")
      .then((data) => {
        setHealth(data);
        setHealthError(null);
      })
      .catch((err) => {
        setHealthError(err instanceof ApiError ? err.message : "Không thể kết nối đến máy chủ");
      })
      .finally(() => {
        setHealthLoading(false);
        setHealthLoadedOnce(true);
      });
  };

  const loadSchoolStats = () => {
    setSchoolStatsLoading(true);
    api.get<SchoolTelemetryResponse>("/chat/admin/telemetry-by-school?days=7")
      .then((data) => {
        setSchoolStats(data.schools);
        setSchoolStatsError(null);
      })
      .catch((err) => {
        setSchoolStatsError(err instanceof ApiError ? err.message : "Không thể kết nối đến máy chủ");
      })
      .finally(() => {
        setSchoolStatsLoading(false);
      });
  };

  const loadHistory = (days: number) => {
    setHistoryLoading(true);
    api.get<ObservabilityHistoryResponse>(`/chat/admin/observability-history?days=${days}`)
      .then((data) => {
        setHistory(data.snapshots);
        setHistoryError(null);
      })
      .catch((err) => {
        setHistoryError(err instanceof ApiError ? err.message : "Không thể kết nối đến máy chủ");
      })
      .finally(() => {
        setHistoryLoading(false);
      });
  };

  useEffect(() => {
    if (user && user.role === "ADMIN" && activeTab === "health" && !healthLoadedOnce) {
      loadHealth();
      loadHistory(historyDays);
      loadSchoolStats();
    }
    // historyDays cố ý không nằm trong deps — lần load đầu dùng giá trị mặc định,
    // đổi số ngày sau đó do effect dưới xử lý riêng (tránh fetch trùng 2 lần).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, activeTab, healthLoadedOnce]);

  useEffect(() => {
    if (user && user.role === "ADMIN" && healthLoadedOnce) {
      loadHistory(historyDays);
    }
    // user/healthLoadedOnce cố ý không nằm trong deps — effect này CHỈ phản ứng khi
    // người dùng đổi bộ lọc số ngày, lần load đầu đã do effect trên xử lý.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historyDays]);

  const loadStats = () => {
    setLoading(true);
    const query = selectedDays === "all" ? "" : `?days=${selectedDays}`;
    api.get<AiTelemetryStatsResponse>(`/chat/admin/telemetry${query}`)
      .then((data) => {
        setStats(data);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Không thể kết nối đến máy chủ");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    if (user && user.role === "ADMIN") {
      loadStats();
    }
  }, [user, selectedDays]);

  const filteredMessages = useMemo(() => {
    if (!stats) return [];
    return stats.messages.filter((msg) => {
      // 1. Search filter
      const matchesSearch = searchQuery === "" || 
        msg.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (msg.feedback_text && msg.feedback_text.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (msg.feedback_tag && msg.feedback_tag.toLowerCase().includes(searchQuery.toLowerCase()));
      
      // 2. Rating filter
      let matchesRating = true;
      if (filterRating === "helpful") matchesRating = msg.rating === 1;
      else if (filterRating === "unhelpful") matchesRating = msg.rating === -1;
      else if (filterRating === "unrated") matchesRating = msg.rating === null;

      // 3. Provider filter
      const matchesProvider = filterProvider === "all" || 
        (msg.llm_provider && msg.llm_provider.toLowerCase() === filterProvider.toLowerCase());

      return matchesSearch && matchesRating && matchesProvider;
    });
  }, [stats, searchQuery, filterRating, filterProvider]);

  const totalPages = Math.ceil(filteredMessages.length / 10);
  
  const paginatedMessages = useMemo(() => {
    const startIndex = (currentPage - 1) * 10;
    return filteredMessages.slice(startIndex, startIndex + 10);
  }, [filteredMessages, currentPage]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, filterRating, filterProvider, stats]);

  const tokenPieData = useMemo(() => {
    if (!stats) return [];
    return [
      { name: "Prompt (Input)", value: stats.total_input_tokens, color: "#3b82f6" },
      { name: "Completion (Output)", value: stats.total_output_tokens, color: "#10b981" },
    ];
  }, [stats]);

  if (user && user.role !== "ADMIN") {
    return (
      <div className="flex h-full flex-col items-center justify-center text-center p-8">
        <ShieldAlert className="w-12 h-12 text-rose-500 mb-3" />
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Không có quyền truy cập</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Khu vực thống kê AI chỉ dành cho tài khoản ADMIN.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[500px] gap-3">
        <div className="w-10 h-10 border-4 border-brand border-t-transparent rounded-full animate-spin"></div>
        <p className="text-slate-500 dark:text-slate-400 text-sm">Đang tải thống kê Telemetry...</p>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="p-8 max-w-6xl mx-auto w-full">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6 text-center">
          <p className="text-red-700 dark:text-red-400 font-semibold">Đã xảy ra lỗi</p>
          <p className="text-red-600 dark:text-red-500 text-sm mt-1">{error}</p>
          <button 
            onClick={loadStats}
            className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md text-sm transition-colors"
          >
            Thử lại
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto w-full space-y-8 animate-in fade-in duration-300">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Đánh giá & Thống kê AI Agent</h2>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Đo lường các chỉ số Telemetry (độ trễ, tokens, chi phí) và phản hồi thực tế từ người dùng.</p>
        </div>
        
        {/* Time Range Selector — chỉ áp dụng cho tab "Chi tiết tin nhắn" (loadStats). Tab "Tình
            trạng hệ thống AI" có bộ lọc thời gian riêng (cửa sổ trượt realtime + historyDays cho
            trend chart) nên ẩn đi để tránh hiểu lầm "đổi mà không thấy gì thay đổi". */}
        {activeTab === "messages" && (
        <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg border border-slate-200 dark:border-slate-700/80 shrink-0">
          {[
            { label: "Hôm nay", value: 1 },
            { label: "7 ngày", value: 7 },
            { label: "30 ngày", value: 30 },
            { label: "Tất cả", value: "all" }
          ].map((opt) => (
            <button
              key={opt.value}
              onClick={() => setSelectedDays(opt.value as any)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition ${
                selectedDays === opt.value
                  ? "bg-white dark:bg-slate-900 text-brand dark:text-brand-400 shadow-xs border border-slate-200/50 dark:border-slate-800"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        )}
      </div>

      {/* Tab switcher */}
      <div className="flex items-center gap-1 border-b border-slate-200 dark:border-slate-800">
        <button
          onClick={() => setActiveTab("messages")}
          className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "messages"
              ? "border-brand text-brand"
              : "border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
          }`}
        >
          Chi tiết tin nhắn
        </button>
        <button
          onClick={() => setActiveTab("health")}
          className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors inline-flex items-center gap-1.5 ${
            activeTab === "health"
              ? "border-brand text-brand"
              : "border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
          }`}
        >
          <Activity className="w-4 h-4" />
          Tình trạng hệ thống AI
        </button>
      </div>

      {activeTab === "health" ? (
        <ObservabilityHealthTab
          health={health}
          loading={healthLoading}
          error={healthError}
          onRetry={loadHealth}
          history={history}
          historyLoading={historyLoading}
          historyError={historyError}
          historyDays={historyDays}
          onHistoryDaysChange={setHistoryDays}
          schoolStats={schoolStats}
          schoolStatsLoading={schoolStatsLoading}
          schoolStatsError={schoolStatsError}
        />
      ) : (
      <>
      {stats.pii_flagged_count > 0 && (
        <div className="flex items-center gap-2 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/60 rounded-lg px-4 py-2.5 text-sm text-amber-800 dark:text-amber-300">
          <ShieldAlert className="w-4 h-4 shrink-0" />
          <span>
            <strong>{stats.pii_flagged_count}</strong> câu trả lời AI có thể chứa dữ liệu cá nhân (SĐT/email/CCCD) chưa
            được che — kiểm tra trong danh sách tin nhắn bên dưới.
          </span>
        </div>
      )}
      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 flex flex-col gap-3 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase tracking-wider">Chi Phí API</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
              <Coins className="w-4 h-4" />
            </div>
          </div>
          <div>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white">${stats.total_cost.toFixed(4)}</h3>
            <p className="text-[10px] text-slate-400 mt-0.5">Tích lũy theo bộ lọc</p>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 flex flex-col gap-3 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase tracking-wider">CP TB/Request</span>
            <div className="w-8 h-8 rounded-lg bg-teal-50 dark:bg-teal-950/40 text-teal-600 dark:text-teal-400 flex items-center justify-center">
              <Coins className="w-4 h-4" />
            </div>
          </div>
          <div>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white">${stats.avg_cost_per_request.toFixed(5)}</h3>
            <p className="text-[10px] text-slate-400 mt-0.5">Trung bình mỗi request</p>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 flex flex-col gap-3 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase tracking-wider">Độ trễ TB</span>
            <div className="w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 flex items-center justify-center">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white">{(stats.avg_latency_ms / 1000).toFixed(2)}s</h3>
            <p className="text-[10px] text-slate-400 mt-0.5">Không tính cuộc gọi lỗi</p>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 flex flex-col gap-3 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase tracking-wider">Số Requests</span>
            <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
              <Activity className="w-4 h-4" />
            </div>
          </div>
          <div>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white">{stats.total_requests.toLocaleString()}</h3>
            <p className="text-[10px] text-slate-400 mt-0.5">Tổng lượt gọi Agent</p>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 flex flex-col gap-3 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase tracking-wider">Conversations</span>
            <div className="w-8 h-8 rounded-lg bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400 flex items-center justify-center">
              <MessageSquare className="w-4 h-4" />
            </div>
          </div>
          <div>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white">{stats.total_sessions.toLocaleString()}</h3>
            <p className="text-[10px] text-slate-400 mt-0.5">Số chat session độc nhất</p>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 flex flex-col gap-3 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase tracking-wider">Hài Lòng (trong số đã đánh giá)</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
              <ThumbsUp className="w-4 h-4" />
            </div>
          </div>
          <div>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white">
              {stats.positive_feedback_ratio !== null ? `${(stats.positive_feedback_ratio * 100).toFixed(1)}%` : "Chưa có đánh giá"}
            </h3>
            <p className="text-[10px] text-slate-400 mt-0.5">
              {stats.helpful_count} Thích / {stats.unhelpful_count} Ghét — {(stats.feedback_rate * 100).toFixed(1)}% tin nhắn có đánh giá
            </p>
          </div>
        </div>

        <div className={`bg-white dark:bg-slate-900 border ${stats.error_rate > 0.05 ? "border-rose-300 dark:border-rose-900/60" : "border-slate-200 dark:border-slate-800"} rounded-xl p-5 flex flex-col gap-3 shadow-xs`}>
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase tracking-wider">Tỷ lệ Lỗi</span>
            <div className={`w-8 h-8 rounded-lg ${stats.error_rate > 0.05 ? "bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-450" : "bg-slate-100 dark:bg-slate-800 text-slate-500"} flex items-center justify-center`}>
              <AlertOctagon className="w-4 h-4" />
            </div>
          </div>
          <div>
            <h3 className={`text-xl font-bold ${stats.error_rate > 0.05 ? "text-rose-600 dark:text-rose-400" : "text-slate-900 dark:text-white"}`}>{(stats.error_rate * 100).toFixed(1)}%</h3>
            <p className="text-[10px] text-slate-400 mt-0.5">({stats.total_errors} thất bại / {stats.total_requests} requests)</p>
          </div>
        </div>
      </div>



      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Feedback List & Table */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 lg:col-span-2 space-y-4 shadow-xs">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">Nhật ký và Phản hồi</h3>
            
            {/* Filters */}
            <div className="flex flex-wrap items-center gap-2">
              <select 
                value={filterRating} 
                onChange={(e) => setFilterRating(e.target.value as any)}
                className="px-3 py-1.5 border border-slate-300 dark:border-slate-700 rounded-md text-xs bg-white dark:bg-slate-800 text-slate-700 dark:text-white"
              >
                <option value="all">Mọi đánh giá</option>
                <option value="helpful">Hữu ích (Thích)</option>
                <option value="unhelpful">Không hữu ích (Ghét)</option>
                <option value="unrated">Chưa đánh giá</option>
              </select>

              <select 
                value={filterProvider} 
                onChange={(e) => setFilterProvider(e.target.value as any)}
                className="px-3 py-1.5 border border-slate-300 dark:border-slate-700 rounded-md text-xs bg-white dark:bg-slate-800 text-slate-700 dark:text-white"
              >
                <option value="all">Mọi Provider</option>
                <option value="openai">OpenAI</option>
                <option value="deepseek">DeepSeek</option>
              </select>
            </div>
          </div>

          {/* Search bar */}
          <div className="relative">
            <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400">
              <Search className="w-4 h-4" />
            </span>
            <input 
              type="text" 
              placeholder="Tìm kiếm nội dung tin nhắn hoặc nhận xét phản hồi..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-4 py-2 border border-slate-300 dark:border-slate-700 rounded-md text-sm w-full bg-white dark:bg-slate-800 text-slate-700 dark:text-white focus:outline-hidden focus:border-brand"
            />
          </div>

          {/* List content */}
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-medium">
                  <th className="py-3 px-2">Thời gian</th>
                  <th className="py-3 px-2">Model</th>
                  <th className="py-3 px-2 text-center">Latency</th>
                  <th className="py-3 px-2 text-right">Cost</th>
                  <th className="py-3 px-2 text-center">Đánh giá</th>
                  <th className="py-3 px-2 text-right">Hành động</th>
                </tr>
              </thead>
              <tbody>
                {paginatedMessages.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-400">Không tìm thấy bản ghi nào khớp bộ lọc</td>
                  </tr>
                ) : (
                  paginatedMessages.map((msg) => {
                    const isError = msg.content?.startsWith("Error:") ?? false;
                    return (
                      <tr 
                        key={msg.id}
                        className={`border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors cursor-pointer ${
                          selectedMessage?.id === msg.id 
                            ? "bg-brand-50 dark:bg-brand-950/20" 
                            : isError 
                              ? "bg-rose-50/30 dark:bg-rose-950/5" 
                              : ""
                        }`}
                        onClick={() => setSelectedMessage(msg)}
                      >
                        <td className="py-3 px-2 text-slate-500 dark:text-slate-400 text-xs">
                          {new Date(msg.created_at).toLocaleString("vi-VN", {
                            month: "2-digit",
                            day: "2-digit",
                            hour: "2-digit",
                            minute: "2-digit"
                          })}
                        </td>
                        <td className="py-3 px-2 font-mono text-xs">
                          <span className="px-1.5 py-0.5 rounded-sm bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 uppercase">
                            {msg.llm_provider}
                          </span>
                          <span className="ml-1 text-slate-500 dark:text-slate-400">{msg.model_used}</span>
                          {isError && (
                            <span className="ml-1.5 px-1 py-0.5 rounded-xs bg-rose-100 dark:bg-rose-950/50 text-rose-700 dark:text-rose-400 text-[9px] font-bold">
                              LỖI
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-2 text-center text-xs">
                          {msg.latency_ms ? `${(msg.latency_ms / 1000).toFixed(2)}s` : "—"}
                        </td>
                        <td className="py-3 px-2 text-right text-xs font-mono">
                          {msg.cost ? `$${msg.cost.toFixed(5)}` : "—"}
                        </td>
                        <td className="py-3 px-2 text-center">
                          {isError ? (
                            <AlertOctagon className="w-4 h-4 text-rose-500 mx-auto" />
                          ) : (
                            <>
                              {msg.rating === 1 && <ThumbsUp className="w-4 h-4 text-emerald-600 mx-auto" />}
                              {msg.rating === -1 && <ThumbsDown className="w-4 h-4 text-rose-600 mx-auto" />}
                              {msg.rating === null && <span className="text-slate-300 dark:text-slate-700 text-xs">—</span>}
                            </>
                          )}
                        </td>
                        <td className="py-3 px-2 text-right">
                          <button className="text-brand dark:text-brand-300 hover:underline inline-flex items-center gap-0.5 text-xs font-semibold">
                            Chi tiết <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-100 dark:border-slate-800 pt-4 mt-2">
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Hiển thị {(currentPage - 1) * 10 + 1} - {Math.min(currentPage * 10, filteredMessages.length)} trong {filteredMessages.length} kết quả
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="px-2.5 py-1.5 border border-slate-300 dark:border-slate-700 rounded-md text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 transition-colors"
                >
                  Trước
                </button>
                <span className="text-xs font-medium text-slate-700 dark:text-slate-300 px-2">
                  Trang {currentPage} / {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="px-2.5 py-1.5 border border-slate-300 dark:border-slate-700 rounded-md text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 transition-colors"
                >
                  Sau
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right Sidebar containing both Pie Chart and Inspector Pane */}
        <div className="space-y-8 lg:col-span-1">
          {/* Token Breakdown Pie Chart */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 space-y-4 shadow-xs flex flex-col justify-between">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800/80 pb-3">
              <h3 className="text-base font-bold text-slate-900 dark:text-white">Cơ cấu Tokens</h3>
              <span className="text-[11px] font-semibold text-slate-400">Prompt vs Completion</span>
            </div>
            
            <div className="relative h-[160px] flex items-center justify-center">
              {stats.total_tokens === 0 ? (
                <p className="text-slate-400 text-xs italic">Không có token nào được ghi nhận</p>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={tokenPieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={68}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {tokenPieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip 
                        formatter={(value: any) => value.toLocaleString() + " tokens"}
                        contentStyle={{ backgroundColor: "#1e293b", border: "none", borderRadius: "8px", color: "#fff", fontSize: 11 }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="absolute text-center">
                    <p className="text-[9px] uppercase font-bold text-slate-400 dark:text-slate-500 tracking-wider">Tổng cộng</p>
                    <p className="text-base font-extrabold text-slate-850 dark:text-white mt-0.5">
                      {stats.total_tokens >= 1000000 
                        ? `${(stats.total_tokens / 1000000).toFixed(2)}M` 
                        : stats.total_tokens.toLocaleString()}
                    </p>
                  </div>
                </>
              )}
            </div>

            <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800/80">
              {tokenPieData.map((item, index) => (
                <div key={index} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                    <span className="text-slate-500 dark:text-slate-400 font-medium">{item.name}</span>
                  </div>
                  <div className="text-right">
                    <span className="font-bold text-slate-850 dark:text-slate-200">{item.value.toLocaleString()}</span>
                    <span className="text-slate-400 text-[10px] ml-1">
                      ({stats.total_tokens > 0 ? ((item.value / stats.total_tokens) * 100).toFixed(1) : 0}%)
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Detailed Inspector Pane */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 space-y-6 shadow-xs w-full">
          <h3 className="text-lg font-bold text-slate-900 dark:text-white border-b border-slate-200 dark:border-slate-800 pb-3 flex items-center gap-2">
            <Workflow className="w-5 h-5 text-brand" />
            Giám sát Chi Tiết
          </h3>

          {!selectedMessage ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-400 dark:text-slate-600 text-center gap-2">
              <MessageSquareCode className="w-10 h-10" />
              <p className="text-sm">Chọn một cuộc hội thoại từ danh sách để xem luồng phân tích chi tiết.</p>
            </div>
          ) : (
            <div className="space-y-6 text-sm">
              {/* Telemetry info */}
              <div className="grid grid-cols-2 gap-4 bg-slate-50 dark:bg-slate-800/40 p-4 rounded-lg border border-slate-100 dark:border-slate-800 font-mono text-xs">
                <div>
                  <p className="text-slate-400 font-sans">Provider / Model:</p>
                  <p className="text-slate-800 dark:text-slate-200 uppercase font-semibold">{selectedMessage.llm_provider} / {selectedMessage.model_used}</p>
                </div>
                <div>
                  <p className="text-slate-400 font-sans">Latency / Cost:</p>
                  <p className="text-slate-800 dark:text-slate-200 font-semibold">
                    {selectedMessage.latency_ms ? `${(selectedMessage.latency_ms / 1000).toFixed(2)}s` : "N/A"} / ${selectedMessage.cost?.toFixed(5) ?? "0.00"}
                  </p>
                </div>
                <div className="col-span-2 border-t border-slate-200 dark:border-slate-700/60 pt-2 mt-1">
                  <p className="text-slate-400 font-sans">Tokens (Input / Output / Total):</p>
                  <p className="text-slate-800 dark:text-slate-200">
                    {selectedMessage.input_token_count ?? 0} in / {selectedMessage.output_token_count ?? 0} out / {((selectedMessage.input_token_count ?? 0) + (selectedMessage.output_token_count ?? 0))} total
                  </p>
                </div>
              </div>

              {/* User evaluation */}
              <div className="space-y-1">
                <h4 className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                  Đánh giá của người dùng
                </h4>
                {selectedMessage.rating !== null ? (
                  <div className="bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 p-3 rounded-lg space-y-2">
                    <div className="flex items-center gap-2">
                      {selectedMessage.rating === 1 ? (
                        <span className="inline-flex items-center gap-1 text-xs text-emerald-600 bg-emerald-50 dark:bg-emerald-950/30 px-2 py-0.5 rounded font-semibold border border-emerald-200/50">
                          <ThumbsUp className="w-3.5 h-3.5" /> Hữu ích
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-rose-600 bg-rose-50 dark:bg-rose-950/30 px-2 py-0.5 rounded font-semibold border border-rose-200/50">
                          <ThumbsDown className="w-3.5 h-3.5" /> Không đúng/Không hữu ích
                        </span>
                      )}
                      {selectedMessage.feedback_tag && (
                        <span className="inline-flex items-center text-[11px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 px-2 py-0.5 rounded font-semibold border border-amber-200/30">
                          {selectedMessage.feedback_tag}
                        </span>
                      )}
                      <span className="text-[10px] text-slate-400">
                        {selectedMessage.feedback_at ? new Date(selectedMessage.feedback_at).toLocaleString() : ""}
                      </span>
                    </div>
                    {selectedMessage.feedback_text ? (
                      <p className="text-slate-700 dark:text-slate-300 text-xs italic">
                        &ldquo;{selectedMessage.feedback_text}&rdquo;
                      </p>
                    ) : (
                      <p className="text-slate-400 text-xs italic">(Không để lại nhận xét bằng chữ)</p>
                    )}
                  </div>
                ) : (
                  <p className="text-slate-400 text-xs italic">Người dùng chưa để lại đánh giá cho phản hồi này.</p>
                )}
              </div>

              {/* Content and code output */}
              <div className="space-y-2">
                <h4 className="font-bold text-slate-800 dark:text-slate-200">
                  {selectedMessage.content?.startsWith("Error:") ? "Thông tin lỗi hệ thống" : "Nội dung câu trả lời"}
                </h4>
                <div className={`p-4 rounded-lg overflow-y-auto max-h-[160px] text-xs whitespace-pre-wrap border ${
                  selectedMessage.content?.startsWith("Error:")
                    ? "bg-rose-50 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900/40 text-rose-700 dark:text-rose-300"
                    : "bg-slate-50 dark:bg-slate-800/40 border-slate-100 dark:border-slate-800 text-slate-700 dark:text-slate-300"
                }`}>
                  {selectedMessage.content}
                </div>
              </div>

              {/* SQL log */}
              {selectedMessage.generated_sql && (
                <div className="space-y-1">
                  <h4 className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5 text-xs">
                    <Code2 className="w-4 h-4 text-blue-600" />
                    SQL Query Thực Thi
                  </h4>
                  <pre className="bg-slate-950 text-slate-100 p-3 rounded-lg text-[10px] font-mono overflow-x-auto whitespace-pre">
                    {selectedMessage.generated_sql}
                  </pre>
                </div>
              )}

              {/* Thought Trace Timeline */}
              <div className="space-y-2">
                <h4 className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                  <Workflow className="w-4 h-4 text-purple-600" />
                  Luồng Suy Nghĩ của Agent (Thought Trace)
                </h4>
                
                {selectedMessage.thought_trace && selectedMessage.thought_trace.length > 0 ? (
                  <div className="border-l-2 border-slate-200 dark:border-slate-700 pl-4 py-2 space-y-4 max-h-[220px] overflow-y-auto">
                    {selectedMessage.thought_trace.map((log, idx) => (
                      <div key={idx} className="relative space-y-1">
                        {/* Dot indicator */}
                        <span className={`absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full border-2 border-white dark:border-slate-900 ${log.type === "status" ? "bg-blue-600" : "bg-purple-600"}`}></span>
                        
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                          {log.type === "status" ? "Trạng thái xử lý" : "Luồng suy nghĩ"}
                        </p>
                        <p className="text-xs text-slate-700 dark:text-slate-300 font-mono whitespace-pre-wrap bg-slate-50 dark:bg-slate-800/40 p-2 rounded border border-slate-100/50 dark:border-slate-800">
                          {log.content}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-400 text-xs italic">Không tìm thấy thông tin luồng suy nghĩ của Agent.</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
      </>
      )}
    </div>
  );
}

function ObservabilityHealthTab({
  health,
  loading,
  error,
  onRetry,
  history,
  historyLoading,
  historyError,
  historyDays,
  onHistoryDaysChange,
  schoolStats,
  schoolStatsLoading,
  schoolStatsError,
}: {
  health: ObservabilitySummaryResponse | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  history: ObservabilitySnapshotItem[] | null;
  historyLoading: boolean;
  historyError: string | null;
  historyDays: number;
  onHistoryDaysChange: (days: number) => void;
  schoolStats: SchoolTelemetryItem[] | null;
  schoolStatsLoading: boolean;
  schoolStatsError: string | null;
}) {
  const { theme } = useTheme();
  const gridColor = theme === "dark" ? "#1e293b" : "#e2e8f0";
  const axisColor = theme === "dark" ? "#94a3b8" : "#64748b";
  const tooltipStyle = {
    backgroundColor: theme === "dark" ? "#0f172a" : "#ffffff",
    border: `1px solid ${gridColor}`,
    borderRadius: "12px",
    color: theme === "dark" ? "#f8fafc" : "#0f172a",
  };

  const chartData = (history || []).map((s) => ({
    timestamp: new Date(s.captured_at).getTime(),
    cost: s.daily_cost_usd,
    budget: s.daily_budget_usd,
    faithfulness: s.faithfulness_avg !== null ? s.faithfulness_avg * 100 : null,
    groundedness: s.groundedness_avg !== null ? s.groundedness_avg * 100 : null,
  }));
  const latestBudget = chartData.length > 0 ? chartData[chartData.length - 1].budget : 0;

  const formatXAxisDate = (unixTime: number) => {
    const d = new Date(unixTime);
    if (historyDays === 1) return d.toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit" });
    if (historyDays === 7) return d.toLocaleString("vi-VN", { weekday: 'short', day: '2-digit' });
    return d.toLocaleString("vi-VN", { month: "2-digit", day: "2-digit" });
  };

  if (loading && !health) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[300px] gap-3">
        <div className="w-10 h-10 border-4 border-brand border-t-transparent rounded-full animate-spin"></div>
        <p className="text-slate-500 dark:text-slate-400 text-sm">Đang tải tình trạng hệ thống AI...</p>
      </div>
    );
  }

  if (error || !health) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6 text-center">
        <p className="text-red-700 dark:text-red-400 font-semibold">Đã xảy ra lỗi</p>
        <p className="text-red-600 dark:text-red-500 text-sm mt-1">{error}</p>
        <button
          onClick={onRetry}
          className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md text-sm transition-colors"
        >
          Thử lại
        </button>
      </div>
    );
  }

  const budgetPct = health.daily_budget_usd > 0 ? (health.daily_cost_usd / health.daily_budget_usd) * 100 : 0;
  const budgetBarColor = budgetPct >= 100 ? "bg-rose-500" : budgetPct >= 80 ? "bg-amber-500" : "bg-emerald-500";

  return (
    <div className="space-y-8">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xs">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
              <Coins className="w-6 h-6" />
            </div>
            <div className="min-w-0">
              <p className="text-xs text-slate-500 dark:text-slate-400 font-medium uppercase">Chi phí hôm nay</p>
              <h3 className="text-xl font-bold text-slate-900 dark:text-white mt-0.5">
                ${health.daily_cost_usd.toFixed(4)} <span className="text-sm text-slate-400 font-normal">/ ${health.daily_budget_usd.toFixed(2)}</span>
              </h3>
            </div>
          </div>
          <div className="mt-3 h-1.5 w-full rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
            <div className={`h-full rounded-full ${budgetBarColor}`} style={{ width: `${Math.min(budgetPct, 100)}%` }} />
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 flex items-center gap-4 shadow-xs">
          <div className="w-12 h-12 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
            <Gauge className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium uppercase">Latency P95</p>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white mt-0.5">
              {health.latency_p95_ms !== null ? `${(health.latency_p95_ms / 1000).toFixed(2)}s` : "—"}
            </h3>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 flex items-center gap-4 shadow-xs">
          <div className="w-12 h-12 rounded-lg bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400 flex items-center justify-center shrink-0">
            <Wrench className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium uppercase">Tool Success Rate</p>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white mt-0.5">
              {health.tool_success_rate !== null ? `${(health.tool_success_rate * 100).toFixed(1)}%` : "—"}
            </h3>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 flex items-center gap-4 shadow-xs">
          <div className="w-12 h-12 rounded-lg bg-red-50 dark:bg-red-950/40 text-brand flex items-center justify-center shrink-0">
            <BadgeCheck className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium uppercase">Faithfulness (RAG)</p>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white mt-0.5">
              {health.faithfulness_avg !== null ? `${(health.faithfulness_avg * 100).toFixed(0)}%` : "Chưa có mẫu"}
            </h3>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 flex items-center gap-4 shadow-xs">
          <div className="w-12 h-12 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 flex items-center justify-center shrink-0">
            <BadgeCheck className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium uppercase">Groundedness (Data/Stat/SQL)</p>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white mt-0.5">
              {health.groundedness_avg !== null ? `${(health.groundedness_avg * 100).toFixed(0)}%` : "Chưa có mẫu"}
            </h3>
          </div>
        </div>
      </div>

      {/* Breakdown theo từng sub-agent — soi agent nào được gọi nhiều/chậm nhất trong hệ multi-agent */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 space-y-4 shadow-xs">
        <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <Workflow className="w-5 h-5 text-brand" />
          Breakdown theo Sub-Agent
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-medium">
                <th className="py-2 px-2">Agent</th>
                <th className="py-2 px-2 text-right">Lượt được Supervisor định tuyến đến</th>
                <th className="py-2 px-2 text-right">Latency P95 / bước</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(AGENT_LABEL).map(([key, label]) => (
                <tr key={key} className="border-b border-slate-100 dark:border-slate-800">
                  <td className="py-2 px-2 font-medium text-slate-700 dark:text-slate-300">{label}</td>
                  <td className="py-2 px-2 text-right font-mono">
                    {key === "supervisor" ? "—" : (health.agent_routes?.[key] ?? 0).toLocaleString()}
                  </td>
                  <td className="py-2 px-2 text-right font-mono">
                    {health.agent_step_p95_ms?.[key] != null ? `${(health.agent_step_p95_ms[key]! / 1000).toFixed(2)}s` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-slate-400">
          SQL bị guardrail từ chối (whitelist bảng/SELECT-only): <span className="font-semibold text-slate-600 dark:text-slate-300">{health.sql_guardrail_rejections_total}</span> lượt
        </p>
      </div>

      {/* Breakdown theo trường (tenant) — trường nào đang đốt ngân sách/gặp lỗi nhiều nhất, 7 ngày gần nhất */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 space-y-4 shadow-xs">
        <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <Coins className="w-5 h-5 text-brand" />
          Breakdown theo Trường (7 ngày qua)
        </h3>
        {schoolStatsLoading && !schoolStats ? (
          <div className="flex items-center justify-center h-[100px] text-sm text-slate-400">Đang tải...</div>
        ) : schoolStatsError ? (
          <p className="text-rose-500 text-sm py-4 text-center">{schoolStatsError}</p>
        ) : !schoolStats || schoolStats.length === 0 ? (
          <p className="text-slate-400 text-sm italic py-4 text-center">Chưa có dữ liệu.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-medium">
                  <th className="py-2 px-2">Trường</th>
                  <th className="py-2 px-2 text-right">Requests</th>
                  <th className="py-2 px-2 text-right">Tỷ lệ lỗi</th>
                  <th className="py-2 px-2 text-right">Chi phí</th>
                  <th className="py-2 px-2 text-right">Latency TB</th>
                </tr>
              </thead>
              <tbody>
                {schoolStats.map((s) => (
                  <tr key={s.school_id} className="border-b border-slate-100 dark:border-slate-800">
                    <td className="py-2 px-2 font-medium text-slate-700 dark:text-slate-300">{s.school_name}</td>
                    <td className="py-2 px-2 text-right font-mono">{s.total_requests.toLocaleString()}</td>
                    <td className={`py-2 px-2 text-right font-mono ${s.error_rate > 0.05 ? "text-rose-600 dark:text-rose-400 font-bold" : ""}`}>
                      {(s.error_rate * 100).toFixed(1)}%
                    </td>
                    <td className="py-2 px-2 text-right font-mono">${s.total_cost.toFixed(4)}</td>
                    <td className="py-2 px-2 text-right font-mono">{(s.avg_latency_ms / 1000).toFixed(2)}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Trend charts */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 space-y-4 shadow-xs">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Gauge className="w-5 h-5 text-brand" />
            Xu hướng theo thời gian
          </h3>
          <select
            value={historyDays}
            onChange={(e) => onHistoryDaysChange(Number(e.target.value))}
            className="px-3 py-1.5 border border-slate-300 dark:border-slate-700 rounded-md text-xs bg-white dark:bg-slate-800 text-slate-700 dark:text-white"
          >
            <option value={1}>24 giờ qua</option>
            <option value={7}>7 ngày qua</option>
            <option value={30}>30 ngày qua</option>
          </select>
        </div>

        {historyLoading && !history ? (
          <div className="flex items-center justify-center h-[220px] text-sm text-slate-400">Đang tải dữ liệu xu hướng...</div>
        ) : historyError ? (
          <p className="text-rose-500 text-sm py-4 text-center">{historyError}</p>
        ) : chartData.length === 0 ? (
          <p className="text-slate-400 text-sm italic py-10 text-center">Chưa có đủ dữ liệu snapshot để vẽ biểu đồ xu hướng.</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2">Chi phí LLM theo ngày (USD)</p>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis 
                    dataKey="timestamp" 
                    type="number" 
                    scale="time" 
                    domain={['dataMin', 'dataMax']} 
                    tickFormatter={formatXAxisDate} 
                    tick={{ fontSize: 10, fill: axisColor }} 
                    minTickGap={30} 
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: axisColor }}
                    domain={[0, 'auto']}
                  />
                  <Tooltip 
                    contentStyle={tooltipStyle} 
                    labelFormatter={(label) => new Date(label).toLocaleString("vi-VN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}
                    formatter={(v) => `$${Number(v).toFixed(5)}`} 
                  />
                  <ReferenceLine y={latestBudget} ifOverflow="hidden" stroke="#f59e0b" strokeDasharray="4 4" label={{ value: "Ngân sách", fontSize: 10, fill: "#f59e0b" }} />
                  <Line type="monotone" dataKey="cost" stroke="#0D4D8B" strokeWidth={2} dot={false} name="Chi phí" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2">Chất lượng câu trả lời — Faithfulness (RAG) / Groundedness (Data-Stat-SQL) (%)</p>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis
                    dataKey="timestamp"
                    type="number"
                    scale="time"
                    domain={['dataMin', 'dataMax']}
                    tickFormatter={formatXAxisDate}
                    tick={{ fontSize: 10, fill: axisColor }}
                    minTickGap={30}
                  />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: axisColor }} />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    labelFormatter={(label) => new Date(label).toLocaleString("vi-VN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}
                    formatter={(v) => `${Number(v).toFixed(0)}%`}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <ReferenceLine y={80} stroke="#dc2626" strokeDasharray="4 4" label={{ value: "Ngưỡng cảnh báo", fontSize: 10, fill: "#dc2626" }} />
                  <Line type="monotone" dataKey="faithfulness" stroke="#C72127" strokeWidth={2} dot={false} connectNulls name="Faithfulness" />
                  <Line type="monotone" dataKey="groundedness" stroke="#0D4D8B" strokeWidth={2} dot={false} connectNulls name="Groundedness" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* Alert feed */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 space-y-4 shadow-xs">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
            Cảnh báo gần đây
          </h3>
        </div>

        {health.recent_alerts.length === 0 ? (
          <p className="text-slate-400 text-sm italic py-6 text-center">Chưa có cảnh báo nào được ghi nhận.</p>
        ) : (
          <div className="space-y-2">
            {health.recent_alerts.map((alert, idx) => (
              <div
                key={idx}
                className="flex items-start gap-3 bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 rounded-lg p-3"
              >
                <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-semibold text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 px-2 py-0.5 rounded border border-amber-200/30">
                      {ALERT_TYPE_LABEL[alert.type] || alert.type}
                    </span>
                    <span className="text-[11px] text-slate-400">
                      {new Date(alert.sent_at).toLocaleString("vi-VN")}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-300 mt-1">{alert.message}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
