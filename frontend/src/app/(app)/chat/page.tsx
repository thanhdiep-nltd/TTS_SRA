"use client";

import { Suspense, useEffect, useRef, useState, useMemo } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Copy,
  Eye,
  FileText,
  HelpCircle,
  Loader2,
  Send,
  Sparkles,
  Terminal,
  User,
  Play,
  Plus,
  Trash2,
  Edit2,
  Check,
  X,
  MessageSquare,
  FolderOpen,
  History,
  Search,
  ThumbsUp,
  ThumbsDown,
  Paperclip,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { api, ApiError, getToken } from "@/lib/api";
import AgentStepTimeline, { AgentStepTrace } from "@/components/chat/AgentStepTimeline";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  analysis?: string;
  rating?: number | null;
  feedback_tag?: string | null;
  feedback_text?: string | null;
  attachmentNames?: string[];
  step_traces?: AgentStepTrace[];
}

interface ChatSession {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

interface SessionAttachment {
  id: string;
  session_id: string;
  file_name: string;
  file_type: string;
  char_count: number;
  truncated: boolean;
  created_at: string;
}

const ATTACHMENT_ACCEPT = ".pdf,.doc,.docx,.jpg,.jpeg,.png";

const SUGGESTIONS = [
  "Tìm học sinh có điểm trung bình học kì 1 cao nhất môn Toán lớp 8A1, năm học 2025-2026",
  "So sánh GPA trung bình khối 8 trong 3 kỳ gần đây",
  "So sánh điểm trung bình môn Toán giữa các lớp khối 8 học kỳ 1 năm 2025-2026",
  "Học kỳ 1 năm học 2025-2026 có bao nhiêu học sinh đạt mức Tốt và mức Khá",
];

const PRESET_SUGGESTIONS = [
  {
    title: "Đối Sánh Học Lực",
    desc: "So sánh kết quả học tập kỳ 1 Lớp 6A1 và lớp 6A2.",
    prompt: "So sánh kết quả học tập kỳ 1 Lớp 6A1 và lớp 6A2 năm học 2025-2026",
  },
  {
    title: "Phân tích thống kê",
    desc: "Thống kê bảng điểm Toán lớp 8A1.",
    prompt: "Thống kê bảng điểm Toán lớp 8A1 HKI năm học 2025-2026",
  },
  {
    title: "Cảnh Báo Yếu Kém",
    desc: "Danh sách học sinh có kết quả trung bình cần phụ đạo gấp.",
    prompt: "Danh sách học sinh có kết quả trung bình cần phụ đạo học kì HK2 năm học 2025-2026",
  },
  {
    title: "Báo cáo theo môn",
    desc: "Báo cáo chuyên sâu về môn Toán lớp 8A1.",
    prompt: "Báo cáo chuyên sâu về môn Toán lớp 8A1 HK1 năm học 2025-2026",
  },
];

const LONG_RUNNING_EXPLANATIONS: Record<string, string> = {
  "Đang phân tích yêu cầu của bạn...": "Yêu cầu của bạn khá phức tạp, hệ thống đang lập kế hoạch chi tiết để xử lý...",
  "Đang tra cứu hồ sơ học sinh và điểm số...": "Hệ thống đang quét qua cơ sở dữ liệu lớn để trích xuất các học bạ và điểm số liên quan...",
  "Đang tính toán thống kê và phân tích...": "Quá trình tính toán đối sánh và tổng hợp số liệu diện rộng thường mất nhiều thời gian hơn (có thể lên đến 1-2 phút).",
  "Đang truy vấn dữ liệu từ PostgreSQL...": "Cơ sở dữ liệu đang thực thi các truy vấn phức tạp để tính toán số liệu chính xác...",
  "Đang lập dữ liệu cho báo cáo...": "Đang định dạng số liệu thô thành cấu trúc báo cáo chuẩn mực...",
  "Đang tổng hợp kết quả trả về...": "Hệ thống đang soạn thảo câu trả lời và tạo biểu đồ tổng hợp...",
};

// Helper to generate unique message IDs outside the component to keep the component pure
const generateMessageId = (prefix: string) =>
  `${prefix}-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

const timeAgo = (dateString: string) => {
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 60) return "Vừa xong";
  const diffInMinutes = Math.floor(diffInSeconds / 60);
  if (diffInMinutes < 60) return `${diffInMinutes} phút trước`;
  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) return `${diffInHours} giờ trước`;
  const diffInDays = Math.floor(diffInHours / 24);
  if (diffInDays < 7) return `${diffInDays} ngày trước`;
  const diffInWeeks = Math.floor(diffInDays / 7);
  if (diffInWeeks < 4) return `${diffInWeeks} tuần trước`;
  const diffInMonths = Math.floor(diffInDays / 30);
  if (diffInMonths < 12) return `${diffInMonths} tháng trước`;
  return `${Math.floor(diffInDays / 365)} năm trước`;
};

interface ReportFileGroup {
  id: string;
  title: string;
  docxUrl?: string;
  pdfUrl?: string;
  htmlUrl?: string;
}

const parseReportFiles = (content: string): ReportFileGroup[] => {
  const groups: Record<string, ReportFileGroup> = {};
  const mdLinkRegex = /\[([^\]]+)\]\((https?:\/\/[^\s)]+\/reports\/download\/([a-zA-Z0-9_\-\.]+))\)/g;
  let match;

  while ((match = mdLinkRegex.exec(content)) !== null) {
    const [_, text, url, filename] = match;
    const fileId = filename.replace(/\.(docx|pdf|html)$/, "");

    let title = "Báo cáo học đường";
    if (filename.includes("academic_conduct")) {
      title = "Báo cáo Tổng kết Học tập & Rèn luyện";
    } else if (filename.includes("subject_quality")) {
      title = "Báo cáo Phổ điểm & Chất lượng Bộ môn";
    } else if (filename.includes("at_risk")) {
      title = "Báo cáo Sàng lọc Học sinh cần Hỗ trợ";
    } else if (filename.includes("subject_report")) {
      title = "Báo cáo Chuyên sâu Môn học";
    } else if (filename.includes("tu_do")) {
      title = "Báo cáo Phân tích Tự do";
    }

    if (!groups[fileId]) {
      groups[fileId] = {
        id: fileId,
        title,
      };
    }

    if (filename.endsWith(".docx")) {
      groups[fileId].docxUrl = url;
    } else if (filename.endsWith(".pdf")) {
      groups[fileId].pdfUrl = url;
    } else if (filename.endsWith(".html")) {
      groups[fileId].htmlUrl = url;
    }
  }

  return Object.values(groups);
};

const cleanMessageContent = (content: string): string => {
  const lines = content.split("\n");
  const cleanedLines = lines.filter(line => {
    const trimmed = line.trim();
    if (trimmed.includes("/reports/download/")) return false;
    if (trimmed.includes("Đường liên kết tải báo cáo")) return false;
    if (trimmed.startsWith("- 👉") || trimmed.startsWith("👉") || trimmed.startsWith("|")) return false;
    return true;
  });
  return cleanedLines.join("\n").trim();
};

function ChatContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const sessionParam = searchParams.get("session");

  const isCreatingSessionRef = useRef(false);

  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);

  const [attachments, setAttachments] = useState<SessionAttachment[]>([]);
  const [uploadingAttachment, setUploadingAttachment] = useState(false);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Xin chào! Tôi là **Trợ lý AI Phân tích Học tập**. Tôi đã kết nối trực tiếp với cơ sở dữ liệu của trường.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [processingSteps, setProcessingSteps] = useState<string[]>([]);
  const [longRunningStepIdx, setLongRunningStepIdx] = useState<number | null>(null);
  const [openAnalysis, setOpenAnalysis] = useState<Record<string, boolean>>({});

  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitleInput, setEditTitleInput] = useState("");
  const [previewModalUrl, setPreviewModalUrl] = useState<string | null>(null);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewFileName, setPreviewFileName] = useState<string>("");

  const [showHistoryPalette, setShowHistoryPalette] = useState(false);
  const [showFilesPalette, setShowFilesPalette] = useState(false);
  const [searchHistoryQuery, setSearchHistoryQuery] = useState("");
  const [showDownloadDropdown, setShowDownloadDropdown] = useState(false);

  // States for AI Message Rating & Feedback Form
  const [activeFeedbackMsgId, setActiveFeedbackMsgId] = useState<string | null>(null);
  const [feedbackForm, setFeedbackForm] = useState({ tag: "", text: "" });
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);

  const handleCopyMessage = (id: string, text: string) => {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text);
    } else {
      const textArea = document.createElement("textarea");
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
    }
    setCopiedMsgId(id);
    setTimeout(() => setCopiedMsgId(null), 2000);
  };

  const handleRatePositive = async (messageId: string) => {
    try {
      const data = await api.post<Message>(`/chat/messages/${messageId}/feedback`, {
        rating: 1,
        feedback_tag: null,
        feedback_text: null,
      });
      // Cập nhật trạng thái tin nhắn
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? { ...m, rating: data.rating, feedback_tag: data.feedback_tag, feedback_text: data.feedback_text }
            : m
        )
      );
    } catch (err) {
      console.error("Lỗi khi gửi đánh giá:", err);
      alert(err instanceof ApiError ? err.message : "Không thể gửi đánh giá.");
    }
  };

  const handleSubmitFeedback = async (messageId: string) => {
    if (!feedbackForm.tag) {
      setFeedbackError("Vui lòng chọn một nhãn lỗi.");
      return;
    }
    if (feedbackForm.tag === "Khác" && !feedbackForm.text.trim()) {
      setFeedbackError("Vui lòng nhập ý kiến đóng góp chi tiết khi chọn nhãn Khác.");
      return;
    }

    setSubmittingFeedback(true);
    setFeedbackError(null);
    try {
      const data = await api.post<Message>(`/chat/messages/${messageId}/feedback`, {
        rating: -1,
        feedback_tag: feedbackForm.tag,
        feedback_text: feedbackForm.text.trim() || null,
      });
      // Cập nhật trạng thái tin nhắn
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? { ...m, rating: data.rating, feedback_tag: data.feedback_tag, feedback_text: data.feedback_text }
            : m
        )
      );
      setActiveFeedbackMsgId(null);
    } catch (err) {
      console.error("Lỗi khi gửi phản hồi:", err);
      setFeedbackError(err instanceof ApiError ? err.message : "Không thể gửi phản hồi.");
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const handleResetRate = async (messageId: string, currentRating: number) => {
    // Reset cục bộ để người dùng có thể đánh giá lại
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId
          ? { ...m, rating: null, feedback_tag: null, feedback_text: null }
          : m
      )
    );
    if (currentRating === -1) {
      setActiveFeedbackMsgId(messageId);
      const msg = messages.find((m) => m.id === messageId);
      setFeedbackForm({
        tag: msg?.feedback_tag || "",
        text: msg?.feedback_text || "",
      });
    }
  };

  // Lọc lịch sử hội thoại trong Command Palette
  const filteredSessions = useMemo(() => {
    if (!searchHistoryQuery.trim()) return sessions;
    const q = searchHistoryQuery.toLowerCase();
    return sessions.filter((s) => (s.title || "Không có tiêu đề").toLowerCase().includes(q));
  }, [sessions, searchHistoryQuery]);

  // Gom toàn bộ tài liệu đã được sinh ra trong phiên chat hiện tại
  const allFilesInSession = useMemo(() => {
    const files: ReportFileGroup[] = [];
    const ids = new Set<string>();

    messages.forEach((msg) => {
      if (msg.role === "user") return;
      const parsed = parseReportFiles(msg.content);
      parsed.forEach((file) => {
        if (!ids.has(file.id)) {
          ids.add(file.id);
          files.push(file);
        }
      });
    });

    return files;
  }, [messages]);

  // Theo dõi thời gian xử lý từng bước để hiện giải thích nếu quá lâu (30 giây)
  useEffect(() => {
    if (processingSteps.length === 0 || !isLoading) {
      setLongRunningStepIdx(null);
      return;
    }

    setLongRunningStepIdx(null);
    const timeout = setTimeout(() => {
      setLongRunningStepIdx(processingSteps.length - 1);
    }, 30000);

    return () => clearTimeout(timeout);
  }, [processingSteps, isLoading]);

  // Đóng nhanh các popup khi nhấn phím Esc
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setShowHistoryPalette(false);
        setShowFilesPalette(false);
        setShowDownloadDropdown(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleOpenPreview = async (url: string) => {
    setPreviewModalUrl(url);
    const filename = url.substring(url.lastIndexOf("/") + 1).replace(/\.html$/, ".docx");
    setPreviewFileName(filename);
    setLoadingPreview(true);
    setPreviewHtml(null);
    try {
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const response = await fetch(url, { headers });
      if (!response.ok) {
        throw new Error(`Failed to load preview: ${response.statusText}`);
      }
      const htmlText = await response.text();
      setPreviewHtml(htmlText);
    } catch (err) {
      console.error("Lỗi khi tải bản xem trước:", err);
      setPreviewHtml(`<p style="color:red;padding:20px;text-align:center;font-family:sans-serif;">Không thể tải bản xem trước. Vui lòng tải file Word (.docx) để xem.</p>`);
    } finally {
      setLoadingPreview(false);
    }
  };

  const renderedMessages = messages.filter(
    (msg, index) =>
      msg.role === "user" ||
      !!msg.content ||
      !!msg.analysis ||
      (isLoading && index === messages.length - 1)
  );

  const endRef = useRef<HTMLDivElement>(null);

  // Cuộn xuống cuối khung chat
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, loadingMessages]);

  // Đồng bộ active session từ query param của URL
  useEffect(() => {
    if (sessionParam) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setActiveSessionId(sessionParam);
    } else {
      setActiveSessionId(null);
      setMessages([
        {
          id: "welcome",
          role: "assistant",
          content:
            "Xin chào! Tôi là **Trợ lý AI Phân tích Học tập**. Tôi đã kết nối trực tiếp với cơ sở dữ liệu của trường.",
        },
      ]);
    }
  }, [sessionParam]);

  // Tải danh sách phiên chat
  const loadSessions = async () => {
    setLoadingSessions(true);
    try {
      const data = await api.get<ChatSession[]>("/chat/sessions");
      setSessions(data);
    } catch (e) {
      console.error("Lỗi khi tải danh sách phiên chat:", e);
    } finally {
      setLoadingSessions(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadSessions();
  }, []);

  // Tải lịch sử tin nhắn khi activeSessionId thay đổi
  useEffect(() => {
    if (!activeSessionId) return;

    if (isCreatingSessionRef.current) {
      isCreatingSessionRef.current = false;
      return;
    }

    interface DBMessage {
      id: string;
      role: string;
      content: string;
      generated_sql?: string | null;
      rating?: number | null;
      feedback_tag?: string | null;
      feedback_text?: string | null;
      step_trace?: AgentStepTrace[] | null;
    }

    const loadMessages = async () => {
      setLoadingMessages(true);
      setError(null);
      try {
        const data = await api.get<DBMessage[]>(`/chat/sessions/${activeSessionId}/messages`);
        const mapped = data.map((msg) => ({
          id: msg.id,
          role: msg.role as "user" | "assistant",
          content: msg.content,
          analysis: msg.generated_sql
            ? `Generated SQL Query:\n\`\`\`sql\n${msg.generated_sql}\n\`\`\``
            : undefined,
          rating: msg.rating,
          feedback_tag: msg.feedback_tag,
          feedback_text: msg.feedback_text,
          step_traces: msg.step_trace && Array.isArray(msg.step_trace) ? msg.step_trace : undefined,
        }));

        if (mapped.length === 0) {
          setMessages([
            {
              id: "welcome",
              role: "assistant",
              content: "Phiên chat này chưa có tin nhắn nào. Hãy bắt đầu đặt câu hỏi phân tích!",
            },
          ]);
        } else {
          setMessages(mapped);
        }
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Đã xảy ra lỗi khi lấy lịch sử tin nhắn.");
      } finally {
        setLoadingMessages(false);
      }
    };

    loadMessages();
  }, [activeSessionId]);

  // Đổi session: dọn khu vực soạn tin — file đính kèm chỉ "ở chờ" cho tới lượt gửi tiếp theo,
  // không hiện lại file của các lượt cũ (đã được gửi kèm tin nhắn trong lịch sử, vẫn được AI
  // dùng xuyên suốt cuộc trò chuyện ở backend dù không còn hiện trong ô soạn tin).
  useEffect(() => {
    setAttachmentError(null);
    setAttachments([]);
  }, [activeSessionId]);

  // Chọn file để đính kèm: tạo session trống trước nếu chưa có, rồi upload + trích xuất nội dung
  const handleAttachFile = async (file: File) => {
    setAttachmentError(null);
    setUploadingAttachment(true);
    try {
      let sessId = activeSessionId;
      if (!sessId) {
        isCreatingSessionRef.current = true;
        const created = await api.post<ChatSession>("/chat/sessions");
        sessId = created.id;
        setActiveSessionId(sessId);
        router.push(`/chat?session=${sessId}`);
        loadSessions();
      }

      const form = new FormData();
      form.append("file", file);
      const uploaded = await api.upload<SessionAttachment>(`/chat/sessions/${sessId}/attachments`, form);
      setAttachments((prev) => [...prev, uploaded]);
    } catch (e) {
      setAttachmentError(e instanceof ApiError ? e.message : "Không thể đính kèm file. Vui lòng thử lại.");
    } finally {
      setUploadingAttachment(false);
    }
  };

  const handleRemoveAttachment = async (attachmentId: string) => {
    if (!activeSessionId) return;
    try {
      await api.del(`/chat/sessions/${activeSessionId}/attachments/${attachmentId}`);
      setAttachments((prev) => prev.filter((a) => a.id !== attachmentId));
    } catch (e) {
      setAttachmentError(e instanceof ApiError ? e.message : "Không thể xoá file đính kèm.");
    }
  };

  // Tạo cuộc hội thoại mới
  const startNewChat = () => {
    router.push("/chat");
  };

  // Đổi tên phiên chat
  const handleRename = async (sessionId: string) => {
    if (!editTitleInput.trim()) return;
    try {
      await api.patch(`/chat/sessions/${sessionId}`, { title: editTitleInput.trim() });
      setEditingSessionId(null);
      loadSessions();
    } catch {
      alert("Không thể đổi tên phiên chat.");
    }
  };

  // Xóa/Ẩn phiên chat
  const handleDelete = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Bạn có chắc chắn muốn xóa phiên chat này không?")) return;
    try {
      await api.del(`/chat/sessions/${sessionId}`);
      if (activeSessionId === sessionId) {
        router.push("/chat");
      }
      loadSessions();
    } catch {
      alert("Không thể xóa phiên chat.");
    }
  };

  // Gửi tin nhắn
  const send = async (text?: string) => {
    const query = (text ?? input).trim();
    if (!query || isLoading) return;
    if (!text) setInput("");
    setError(null);
    setProcessingSteps(["AI Agent đang chuẩn bị xử lý..."]);

    if (!activeSessionId) {
      isCreatingSessionRef.current = true;
    }

    // File đính kèm đang chờ ở ô soạn tin được "gửi kèm" tin nhắn này: hiện badge trên bong bóng
    // chat rồi dọn khỏi ô soạn tin — nội dung file vẫn được AI dùng xuyên suốt cuộc trò chuyện
    // (backend tự chèn lại từ DB ở mọi lượt hỏi tiếp theo trong cùng session).
    const sentAttachmentNames = attachments.map((a) => a.file_name);
    if (sentAttachmentNames.length > 0) {
      setAttachments([]);
    }

    // Thêm tin nhắn của User
    const userMessageId = generateMessageId("u");
    setMessages((prev) => [
      ...prev,
      {
        id: userMessageId,
        role: "user",
        content: query,
        attachmentNames: sentAttachmentNames.length > 0 ? sentAttachmentNames : undefined,
      },
    ]);

    // Thêm tin nhắn trống của Assistant để chuẩn bị hứng stream
    const assistantMessageId = generateMessageId("a");
    setMessages((prev) => [
      ...prev,
      { id: assistantMessageId, role: "assistant", content: "", analysis: "", step_traces: [] },
    ]);

    setIsLoading(true);

    try {
      const token = getToken();
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      // Gọi API trực tiếp dùng fetch để nhận stream
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${baseUrl}/api/v1/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          message: query,
          session_id: activeSessionId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail ?? `Lỗi kết nối (${response.status})`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("Không thể khởi tạo luồng dữ liệu stream.");
      }

      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Phân tách các sự kiện SSE
        const lines = buffer.split("\n\n");
        // Giữ lại phần dư chưa hoàn thành ở cuối buffer
        buffer = lines.pop() || "";

        for (const line of lines) {
          const cleanedLine = line.trim();
          if (!cleanedLine.startsWith("data: ")) continue;

          try {
            const jsonStr = cleanedLine.slice(6);
            const data = JSON.parse(jsonStr);

            if (data.type === "session_id") {
              const newSessId = data.content;
              // Cập nhật activeSessionId và URL query param nếu là session mới
              if (!activeSessionId) {
                setActiveSessionId(newSessId);
                router.push(`/chat?session=${newSessId}`);
                loadSessions();
              }
            } else if (data.type === "step_trace") {
              const newStep: AgentStepTrace = data.step;
              setMessages((prev) =>
                prev.map((msg) => {
                  if (msg.id === assistantMessageId) {
                    const existing = msg.step_traces || [];
                    const exists = existing.some((s) => s.id === newStep.id);
                    const updated = exists
                      ? existing.map((s) => (s.id === newStep.id ? newStep : s))
                      : [...existing, newStep];
                    return { ...msg, step_traces: updated };
                  }
                  return msg;
                })
              );
            } else if (data.type === "thought") {
              // Cập nhật Thought Trace log suy luận
              setMessages((prev) =>
                prev.map((msg) => {
                  if (msg.id === assistantMessageId) {
                    const currentAnalysis = msg.analysis || "";
                    const newAnalysis = currentAnalysis
                      ? `${currentAnalysis}\n\n${data.content}`
                      : data.content;
                    return { ...msg, analysis: newAnalysis };
                  }
                  return msg;
                })
              );
            } else if (data.type === "status") {
              // Thêm tiến trình mới vào mảng (nếu chưa có ở phần tử cuối)
              setProcessingSteps((prev) => {
                if (prev[prev.length - 1] !== data.content) {
                  return [...prev, data.content];
                }
                return prev;
              });
            } else if (data.type === "token") {
              // Cập nhật token nội dung câu trả lời
              setMessages((prev) =>
                prev.map((msg) => {
                  if (msg.id === assistantMessageId) {
                    return { ...msg, content: msg.content + data.content };
                  }
                  return msg;
                })
              );
            } else if (data.type === "message_id") {
              // Cập nhật ID tạm thời của assistant thành UUID thực tế từ CSDL để phục vụ rating/feedback
              const realMessageId = data.content;
              setMessages((prev) =>
                prev.map((msg) => {
                  if (msg.id === assistantMessageId) {
                    return { ...msg, id: realMessageId };
                  }
                  return msg;
                })
              );
            } else if (data.type === "error") {
              throw new Error(data.content);
            }
          } catch (err) {
            console.error("Lỗi parse SSE chunk:", err);
          }
        }
      }
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : "Đã xảy ra lỗi khi trao đổi với AI Agent.";
      setError(errMsg);
      // Xóa tin nhắn trống của assistant nếu lỗi xảy ra ngay từ đầu
      setMessages((prev) => prev.filter((msg) => msg.id !== assistantMessageId || msg.content.length > 0));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950/30 overflow-hidden w-full relative">

      {/* Split screen content wrapper */}
      <div className="flex-1 flex overflow-hidden h-full relative w-full">

        {/* Cột 1: Khung chat chính */}
        <div
          className={`flex-1 flex flex-col h-full min-w-0 transition-standard ${previewModalUrl ? "max-w-[35%]" : "max-w-full"
            }`}
        >
          {loadingMessages ? (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-slate-500">
              <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-2" />
              <span className="text-sm">Đang tải lịch sử tin nhắn...</span>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto w-full">
              <div className={`max-w-3xl mx-auto w-full px-4 sm:px-6 py-4 space-y-4 flex flex-col min-h-full ${renderedMessages.length <= 1 && !loadingMessages ? "justify-center" : ""}`}>
                {renderedMessages.length <= 1 && !loadingMessages ? (
                  <div className="flex flex-col items-center justify-center max-w-2xl mx-auto text-center space-y-6 py-10">
                    <h2 className="text-3xl font-extrabold tracking-tight text-slate-800 dark:text-slate-100">
                      Xin chào, Thầy/Cô!
                    </h2>
                    <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed max-w-lg">
                      Tôi là trợ lý AI học vụ liên kết sổ điểm. Hãy chọn gợi ý bên dưới hoặc gửi yêu cầu tổng hợp đối sánh điểm số.
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full pt-4">
                      {PRESET_SUGGESTIONS.map((preset, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => send(preset.prompt)}
                          disabled={isLoading}
                          className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 text-left transition shadow-sm hover:shadow-md hover:border-brand-500 dark:hover:border-brand-500/50 hover:-translate-y-0.5 cursor-pointer space-y-2 group animate-in fade-in duration-200"
                        >
                          <h4 className="font-bold text-slate-800 dark:text-slate-100 text-sm group-hover:text-brand-600 dark:group-hover:text-brand-400">
                            {preset.title}
                          </h4>
                          <p className="text-xs text-slate-500 dark:text-slate-450 leading-normal">
                            {preset.desc}
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  renderedMessages.map((msg) => {
                    const isUser = msg.role === "user";
                    const isCurrentGeneratingAssistant = !isUser && isLoading && msg.id === messages[messages.length - 1]?.id;
                    const reportFiles = isUser ? [] : parseReportFiles(msg.content);
                    const rawDisplayContent = isUser
                      ? msg.content
                      : (reportFiles.length > 0 ? (cleanMessageContent(msg.content) || "Dưới đây là tệp báo cáo của bạn:") : msg.content);
                    const displayContent = rawDisplayContent
                      ? rawDisplayContent.replace(/(?<=\S)\r?\n(---|___|\*\*\*)(?=\s|$)/g, "\n\n$1\n\n")
                      : "";
                    return (
                      <div key={msg.id} className={`flex gap-4 ${isUser ? "justify-end" : "justify-start"}`}>
                        <div className={`${isUser ? "max-w-[85%]" : "w-full"} flex flex-col space-y-1.5`}>
                          {isUser && msg.attachmentNames && msg.attachmentNames.length > 0 && (
                            <div className="flex flex-wrap justify-end gap-1.5">
                              {msg.attachmentNames.map((name, idx) => (
                                <span
                                  key={idx}
                                  className="inline-flex items-center gap-1.5 text-xs bg-brand-50 dark:bg-brand-950/30 text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-900/50 rounded-full px-3 py-1"
                                >
                                  <FileText className="w-3.5 h-3.5 shrink-0" />
                                  <span className="max-w-[160px] truncate">{name}</span>
                                </span>
                              ))}
                            </div>
                          )}
                          {(isUser || !!displayContent || (isCurrentGeneratingAssistant && !msg.content) || (!isUser && msg.step_traces && msg.step_traces.length > 0)) && (
                            <div
                              className={isUser
                                ? "rounded-2xl px-4 py-2.5 text-sm leading-relaxed border shadow-sm bg-brand-600 border-brand-500 text-white rounded-br-none"
                                : "text-sm leading-relaxed text-slate-800 dark:text-slate-100 py-0.5"
                              }
                            >
                              {isCurrentGeneratingAssistant && (!msg.step_traces || msg.step_traces.length === 0) ? (
                                <div className="flex flex-col gap-2.5 min-w-[240px]">
                                  {processingSteps.map((step, index) => {
                                    const isLast = index === processingSteps.length - 1;
                                    return (
                                      <div key={index} className="flex flex-col gap-1.5 animate-in fade-in duration-200">
                                        <div className={`flex items-center gap-3 text-xs sm:text-sm ${isLast ? 'text-brand-700 dark:text-brand-300 font-medium' : 'text-slate-450 dark:text-slate-500'}`}>
                                          {isLast ? (
                                            <Loader2 className="w-3.5 h-3.5 text-brand-500 animate-spin shrink-0" />
                                          ) : (
                                            <Check className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                                          )}
                                          <span>{step}</span>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              ) : (
                                <>
                                  {!isUser && msg.step_traces && msg.step_traces.length > 0 && (
                                    <AgentStepTimeline steps={msg.step_traces} isLiveLoading={isCurrentGeneratingAssistant} />
                                  )}
                                  {displayContent && (
                                    <div className="prose prose-sm dark:prose-invert max-w-none">
                                      <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        components={{
                                          table: ({ node, ...props }: React.ComponentPropsWithoutRef<"table"> & { node?: any }) => (
                                            <div className="my-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                                              <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800 text-left text-sm" {...props} />
                                            </div>
                                          ),
                                          thead: ({ node, ...props }: React.ComponentPropsWithoutRef<"thead"> & { node?: any }) => (
                                            <thead className="bg-slate-50 dark:bg-slate-900/50" {...props} />
                                          ),
                                          tbody: ({ node, ...props }: React.ComponentPropsWithoutRef<"tbody"> & { node?: any }) => (
                                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 bg-white dark:bg-slate-950" {...props} />
                                          ),
                                          tr: ({ node, ...props }: React.ComponentPropsWithoutRef<"tr"> & { node?: any }) => (
                                            <tr className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30 transition-colors" {...props} />
                                          ),
                                          th: ({ node, ...props }: React.ComponentPropsWithoutRef<"th"> & { node?: any }) => (
                                            <th className="px-4 py-3 font-semibold text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider" {...props} />
                                          ),
                                          td: ({ node, ...props }: React.ComponentPropsWithoutRef<"td"> & { node?: any }) => (
                                            <td className="px-4 py-3 text-slate-600 dark:text-slate-400 whitespace-nowrap align-middle" {...props} />
                                          ),
                                          a: ({ node, href, children, ...props }: React.ComponentPropsWithoutRef<"a"> & { node?: any }) => {
                                            const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                                            const resolvedHref = href ? href.replace("http://localhost:8000", baseUrl) : href;
                                            const isDownloadOrPreview = resolvedHref && resolvedHref.includes("/reports/download/");
                                            if (isDownloadOrPreview) {
                                              const isHtmlPreview = resolvedHref.endsWith(".html");
                                              if (isHtmlPreview) {
                                                return (
                                                  <button
                                                    type="button"
                                                    onClick={(e) => {
                                                      e.preventDefault();
                                                      handleOpenPreview(resolvedHref);
                                                    }}
                                                    className="inline-flex items-center gap-1.5 px-3 py-1.5 mx-1 my-0.5 rounded-lg bg-brand-50 hover:bg-brand-100 dark:bg-brand-950/40 dark:hover:bg-brand-900/50 text-brand-700 dark:text-brand-300 text-xs font-semibold border border-brand-200/50 dark:border-brand-900/30 transition shadow-sm cursor-pointer align-middle"
                                                  >
                                                    <Eye className="w-3.5 h-3.5" />
                                                    {children}
                                                  </button>
                                                );
                                              } else {
                                                return (
                                                  <button
                                                    type="button"
                                                    onClick={(e) => {
                                                      e.preventDefault();
                                                      const a = document.createElement("a");
                                                      a.href = resolvedHref;
                                                      a.target = "_blank";
                                                      a.click();
                                                    }}
                                                    className="text-brand-600 hover:text-brand-500 font-semibold underline dark:text-brand-400 cursor-pointer bg-transparent border-0 p-0 align-baseline"
                                                  >
                                                    {children}
                                                  </button>
                                                );
                                              }
                                            }
                                            return (
                                              <a
                                                href={resolvedHref}
                                                className="text-brand-600 hover:text-brand-500 font-semibold underline dark:text-brand-400"
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                {...props}
                                              >
                                                {children}
                                              </a>
                                            );
                                          },
                                        }}
                                      >
                                        {displayContent}
                                      </ReactMarkdown>
                                    </div>
                                  )}
                                </>
                              )}
                            </div>
                          )}

                          {/* Render file cards if present */}
                          {!isUser && reportFiles.map((file) => {
                            const isCurrentlyPreviewed = previewModalUrl === file.htmlUrl;
                            return (
                              <div
                                key={file.id}
                                className={`flex items-center justify-between p-4 rounded-2xl shadow-sm transition duration-200 max-w-xl w-full border ${isCurrentlyPreviewed
                                  ? "bg-brand-50/40 dark:bg-brand-950/20 border-brand-500 dark:border-brand-500/50 shadow-md ring-1 ring-brand-500/20"
                                  : "bg-slate-50 dark:bg-slate-900/60 border-slate-200 dark:border-slate-800 hover:shadow-md"
                                  }`}
                              >
                                <div className="flex items-center gap-3.5 min-w-0">
                                  {/* Premium Icon Container */}
                                  <div className={`p-3 rounded-xl border shrink-0 transition-colors ${isCurrentlyPreviewed
                                    ? "bg-brand-600 text-white border-brand-600"
                                    : "bg-brand-50 dark:bg-brand-950/40 text-brand-600 dark:text-brand-400 border-brand-100 dark:border-brand-900/30"
                                    }`}>
                                    <FileText className="w-5 h-5" />
                                  </div>
                                  {/* Document Information */}
                                  <div className="min-w-0">
                                    <h4 className={`font-bold text-xs sm:text-sm truncate transition-colors ${isCurrentlyPreviewed ? "text-brand-700 dark:text-brand-400" : "text-slate-800 dark:text-slate-100"
                                      }`}>
                                      {file.title}
                                    </h4>
                                    <p className="text-[10px] sm:text-xs text-slate-500 dark:text-slate-450 mt-1">
                                      Định dạng: {[file.docxUrl && "Word (.docx)", file.pdfUrl && "PDF (.pdf)", file.htmlUrl && "Xem trước"].filter(Boolean).join(" • ")}
                                    </p>
                                  </div>
                                </div>

                                {/* File Action Buttons */}
                                <div className="flex items-center gap-2 shrink-0 ml-3">
                                  {file.htmlUrl && !isCurrentlyPreviewed && (
                                    <button
                                      type="button"
                                      onClick={() => handleOpenPreview(file.htmlUrl!)}
                                      className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-xl text-xs font-bold transition shadow-sm hover:shadow cursor-pointer"
                                    >
                                      Open
                                    </button>
                                  )}
                                  {file.htmlUrl && isCurrentlyPreviewed && (
                                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-brand-100/80 dark:bg-brand-950/60 text-brand-700 dark:text-brand-350 text-xs font-bold border border-brand-200/30 animate-in fade-in duration-150">
                                      <span className="w-1.5 h-1.5 rounded-full bg-brand-600 dark:bg-brand-400 animate-pulse" />
                                      Đang mở
                                    </span>
                                  )}
                                </div>
                              </div>
                            );
                          })}

                          {/* Sleek Terminal Thought Trace Console */}
                          {!isUser && msg.analysis && (
                            <div className="border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
                              {/* Header Bar with Top Controls */}
                              <div className="w-full px-5 py-2.5 bg-slate-100 dark:bg-slate-900 text-xs font-semibold text-slate-600 dark:text-slate-400 flex items-center justify-between transition">
                                <button
                                  type="button"
                                  onClick={() => setOpenAnalysis((p) => ({ ...p, [msg.id]: !p[msg.id] }))}
                                  className="flex items-center gap-2 hover:text-slate-900 dark:hover:text-slate-100 cursor-pointer"
                                >
                                  <Terminal className="w-4 h-4 text-brand-500" />
                                  <span>Nhật ký suy luận & Trace Logs của AI Agent</span>
                                  {openAnalysis[msg.id] ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                </button>

                                <div className="flex items-center gap-2">
                                  {/* Top Copy Button */}
                                  <button
                                    type="button"
                                    onClick={() => handleCopyMessage(`trace-${msg.id}`, msg.analysis || "")}
                                    title="Sao chép Nhật ký suy luận & Trace Logs"
                                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-200 dark:bg-slate-800 hover:bg-brand-600 hover:text-white dark:hover:bg-brand-600 text-slate-700 dark:text-slate-300 text-[11px] transition cursor-pointer"
                                  >
                                    {copiedMsgId === `trace-${msg.id}` ? (
                                      <>
                                        <Check className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400" />
                                        <span>Đã sao chép</span>
                                      </>
                                    ) : (
                                      <>
                                        <Copy className="w-3.5 h-3.5" />
                                        <span>Sao chép log</span>
                                      </>
                                    )}
                                  </button>

                                  {/* Top Close / Toggle Button */}
                                  <button
                                    type="button"
                                    onClick={() => setOpenAnalysis((p) => ({ ...p, [msg.id]: !p[msg.id] }))}
                                    title={openAnalysis[msg.id] ? "Đóng / Thu gọn" : "Xem chi tiết"}
                                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-[11px] transition cursor-pointer"
                                  >
                                    {openAnalysis[msg.id] ? (
                                      <>
                                        <ChevronUp className="w-3.5 h-3.5" />
                                        <span>Đóng</span>
                                      </>
                                    ) : (
                                      <>
                                        <ChevronDown className="w-3.5 h-3.5" />
                                        <span>Xem</span>
                                      </>
                                    )}
                                  </button>
                                </div>
                              </div>

                              {/* Expanded Terminal Content Area */}
                              {openAnalysis[msg.id] && (
                                <div className="bg-slate-950 p-4 border-t border-slate-900 font-mono text-xs text-slate-300 overflow-x-auto">
                                  {/* Terminal Header dots */}
                                  <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
                                    <div className="flex items-center gap-1.5">
                                      <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" />
                                      <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" />
                                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
                                      <span className="text-[10px] text-slate-500 ml-2">antigravity_agent@neon_db</span>
                                    </div>
                                  </div>

                                  <pre className="whitespace-pre-wrap leading-relaxed text-slate-300 select-text font-mono mb-4">
                                    {msg.analysis}
                                  </pre>

                                  {/* Bottom Actions Bar (Quick Copy & Close at bottom) */}
                                  <div className="flex items-center justify-between border-t border-slate-800/80 pt-3 mt-2">
                                    <span className="text-[10px] text-slate-500">AI Agent Trace Engine v2.0</span>
                                    <div className="flex items-center gap-2">
                                      {/* Bottom Copy Button */}
                                      <button
                                        type="button"
                                        onClick={() => handleCopyMessage(`trace-${msg.id}`, msg.analysis || "")}
                                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-brand-600 text-slate-200 text-xs font-semibold transition cursor-pointer"
                                      >
                                        {copiedMsgId === `trace-${msg.id}` ? (
                                          <>
                                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                                            <span>Đã sao chép log</span>
                                          </>
                                        ) : (
                                          <>
                                            <Copy className="w-3.5 h-3.5" />
                                            <span>Sao chép toàn bộ log</span>
                                          </>
                                        )}
                                      </button>

                                      {/* Bottom Close Button (Quick Close without scrolling up) */}
                                      <button
                                        type="button"
                                        onClick={() => setOpenAnalysis((p) => ({ ...p, [msg.id]: false }))}
                                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-rose-600 text-slate-200 text-xs font-semibold transition cursor-pointer"
                                      >
                                        <X className="w-3.5 h-3.5" />
                                        <span>Đóng nhanh</span>
                                      </button>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Rating & Feedback Section */}
                          {!isUser && msg.id !== "welcome" && !isCurrentGeneratingAssistant && (
                            <div className="flex flex-col space-y-2 mt-1">
                              {msg.rating === undefined || msg.rating === null ? (
                                activeFeedbackMsgId === msg.id ? (
                                  <div className="bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800/80 rounded-xl p-4 space-y-4 max-w-md animate-in slide-in-from-top-2 duration-150 shadow-sm">
                                    <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
                                      <span className="text-xs font-bold text-slate-700 dark:text-slate-350 flex items-center gap-1.5">
                                        <ThumbsDown className="w-3.5 h-3.5 text-rose-500" /> Báo cáo lỗi / Phản hồi
                                      </span>
                                      <button
                                        type="button"
                                        onClick={() => setActiveFeedbackMsgId(null)}
                                        className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 p-0.5 rounded cursor-pointer"
                                      >
                                        <X className="w-3.5 h-3.5" />
                                      </button>
                                    </div>

                                    {feedbackError && (
                                      <p className="text-[11px] text-rose-600 dark:text-rose-455 font-semibold leading-relaxed">{feedbackError}</p>
                                    )}

                                    <div className="space-y-2">
                                      <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Chọn nhãn phân loại lỗi:</label>
                                      <div className="grid grid-cols-2 gap-2">
                                        {[
                                          "Phản cảm/Không an toàn",
                                          "Không đúng sự thật",
                                          "Không tuân theo chỉ dẫn",
                                          "Vấn đề về tính năng cá nhân hoá",
                                          "Sai ngôn ngữ",
                                          "Vấn đề với một ứng dụng",
                                          "Truy xuất không chính xác các mục",
                                          "Đã thực hiện một hành động có hại",
                                          "Khác"
                                        ].map((tag) => {
                                          const isActive = feedbackForm.tag === tag;
                                          return (
                                            <button
                                              key={tag}
                                              type="button"
                                              onClick={() => {
                                                setFeedbackForm(prev => ({ ...prev, tag }));
                                                setFeedbackError(null);
                                              }}
                                              className={`px-2.5 py-2 text-[11px] font-medium rounded-lg border text-left leading-normal cursor-pointer transition-all duration-150 ${isActive
                                                ? "bg-brand-600 border-brand-600 text-white shadow-xs"
                                                : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-705 dark:text-slate-250 hover:bg-slate-100 dark:hover:bg-slate-750"
                                                }`}
                                            >
                                              {tag}
                                            </button>
                                          );
                                        })}
                                      </div>
                                    </div>

                                    {feedbackForm.tag === "Khác" && (
                                      <div className="space-y-1.5 animate-in fade-in duration-200">
                                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                                          Ý kiến đóng góp <span className="text-rose-500">*</span>:
                                        </label>
                                        <textarea
                                          rows={2}
                                          placeholder="Hãy mô tả chi tiết lỗi hoặc ý kiến đóng góp của bạn để admin cải thiện Agent..."
                                          value={feedbackForm.text}
                                          onChange={(e) => {
                                            setFeedbackForm(prev => ({ ...prev, text: e.target.value }));
                                            setFeedbackError(null);
                                          }}
                                          className="w-full text-xs p-2.5 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-700 dark:text-white focus:outline-hidden focus:border-brand-500"
                                        />
                                      </div>
                                    )}

                                    <div className="flex items-center justify-end gap-2 pt-1 border-t border-slate-200/60 dark:border-slate-800/80 mt-1">
                                      <button
                                        type="button"
                                        disabled={submittingFeedback}
                                        onClick={() => setActiveFeedbackMsgId(null)}
                                        className="px-3.5 py-2 rounded-lg text-xs font-semibold text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-205 hover:bg-slate-100 dark:hover:bg-slate-800 bg-transparent cursor-pointer transition"
                                      >
                                        Hủy
                                      </button>
                                      <button
                                        type="button"
                                        disabled={submittingFeedback}
                                        onClick={() => handleSubmitFeedback(msg.id)}
                                        className="px-3.5 py-2 bg-brand-600 hover:bg-brand-505 disabled:bg-slate-300 dark:disabled:bg-slate-800 disabled:text-slate-500 text-white rounded-lg text-xs font-bold shadow-xs flex items-center gap-1.5 cursor-pointer disabled:cursor-not-allowed transition"
                                      >
                                        {submittingFeedback ? (
                                          <>
                                            <Loader2 className="w-3 h-3 animate-spin" /> Đang lưu...
                                          </>
                                        ) : (
                                          "Gửi phản hồi"
                                        )}
                                      </button>
                                    </div>
                                  </div>
                                ) : (
                                  <div className="flex items-center gap-2.5 text-slate-400 animate-in fade-in duration-100">
                                    <button
                                      type="button"
                                      onClick={() => handleRatePositive(msg.id)}
                                      className="p-1 hover:text-emerald-600 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition cursor-pointer"
                                      title="Hữu ích"
                                    >
                                      <ThumbsUp className="w-3.5 h-3.5" />
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setActiveFeedbackMsgId(msg.id);
                                        setFeedbackForm({ tag: "", text: "" });
                                        setFeedbackError(null);
                                      }}
                                      className="p-1 hover:text-rose-600 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition cursor-pointer"
                                      title="Không hữu ích"
                                    >
                                      <ThumbsDown className="w-3.5 h-3.5" />
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handleCopyMessage(msg.id, msg.content)}
                                      className="p-1 hover:text-brand-600 dark:hover:text-brand-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition cursor-pointer flex items-center gap-1"
                                      title="Sao chép câu trả lời"
                                    >
                                      {copiedMsgId === msg.id ? (
                                        <>
                                          <Check className="w-3.5 h-3.5 text-emerald-500" />
                                          <span className="text-[10px] text-emerald-500 font-medium">Đã chép</span>
                                        </>
                                      ) : (
                                        <Copy className="w-3.5 h-3.5" />
                                      )}
                                    </button>
                                  </div>
                                )
                              ) : (
                                <div className="flex flex-col space-y-2 animate-in fade-in duration-150">
                                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                                    {msg.rating === 1 ? (
                                      <span className="inline-flex items-center gap-1.5 text-emerald-650 dark:text-emerald-400 font-semibold bg-emerald-50 dark:bg-emerald-950/20 px-2 py-0.5 rounded border border-emerald-250/25">
                                        <ThumbsUp className="w-3.5 h-3.5" /> Hữu ích
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center gap-1.5 text-rose-650 dark:text-rose-455 font-semibold bg-rose-50 dark:bg-rose-950/20 px-2 py-0.5 rounded border border-rose-250/25">
                                        <ThumbsDown className="w-3.5 h-3.5" /> Không hữu ích
                                      </span>
                                    )}

                                    {msg.feedback_tag && (
                                      <span className="bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400 px-2 py-0.5 rounded border border-amber-250/25 font-semibold text-[11px]">
                                        Nhãn lỗi: {msg.feedback_tag}
                                      </span>
                                    )}

                                    <button
                                      type="button"
                                      onClick={() => handleResetRate(msg.id, msg.rating!)}
                                      className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-350 hover:underline text-[10px] ml-2 cursor-pointer"
                                    >
                                      Đánh giá lại
                                    </button>

                                    <button
                                      type="button"
                                      onClick={() => handleCopyMessage(msg.id, msg.content)}
                                      className="inline-flex items-center gap-1 text-slate-400 hover:text-brand-600 dark:hover:text-brand-400 text-xs ml-3 cursor-pointer transition"
                                      title="Sao chép câu trả lời"
                                    >
                                      {copiedMsgId === msg.id ? (
                                        <>
                                          <Check className="w-3.5 h-3.5 text-emerald-500" />
                                          <span className="text-[10px] text-emerald-500 font-medium">Đã chép</span>
                                        </>
                                      ) : (
                                        <>
                                          <Copy className="w-3.5 h-3.5" />
                                          <span className="text-[11px]">Sao chép</span>
                                        </>
                                      )}
                                    </button>
                                  </div>

                                  {msg.feedback_text && (
                                    <p className="text-xs text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/40 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 italic max-w-xl">
                                      &ldquo;{msg.feedback_text}&rdquo;
                                    </p>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}


                {error && (
                  <div className="bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-350 p-4 rounded-xl flex items-start gap-3 text-sm">
                    <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                    <p>{error}</p>
                  </div>
                )}
                <div ref={endRef} />
              </div>
            </div>
          )}

          {/* Bottom Chat Input Form v20 */}
          <div className="pb-6 px-6 pt-2 shrink-0 flex justify-center w-full bg-transparent">
            <div className="w-full max-w-3xl">
              {/* Chip danh sách file đính kèm trong session */}
              {(attachments.length > 0 || uploadingAttachment || attachmentError) && (
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  {attachments.map((a) => (
                    <span
                      key={a.id}
                      className="inline-flex items-center gap-1.5 text-xs bg-brand-50 dark:bg-brand-950/30 text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-900/50 rounded-full pl-3 pr-1.5 py-1"
                      title={a.truncated ? `Nội dung đã bị cắt ngắn (${a.char_count} ký tự)` : undefined}
                    >
                      <FileText className="w-3.5 h-3.5 shrink-0" />
                      <span className="max-w-[160px] truncate">{a.file_name}</span>
                      {a.truncated && <span className="text-amber-600 dark:text-amber-400">⚠</span>}
                      <button
                        type="button"
                        onClick={() => handleRemoveAttachment(a.id)}
                        className="p-0.5 rounded-full hover:bg-brand-100 dark:hover:bg-brand-900/40"
                        title="Xoá file đính kèm"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                  {uploadingAttachment && (
                    <span className="inline-flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> Đang đính kèm...
                    </span>
                  )}
                  {attachmentError && (
                    <span className="text-xs text-rose-600 dark:text-rose-400">{attachmentError}</span>
                  )}
                </div>
              )}

              {/* Input Capsule with 3 Buttons */}
              <div className="flex items-center gap-3 w-full">
                <button
                  type="button"
                  onClick={startNewChat}
                  className="p-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/80 hover:border-brand-500 dark:hover:border-brand-500/50 text-slate-550 hover:text-brand-600 dark:text-slate-400 dark:hover:text-brand-400 rounded-full transition shadow-sm hover:shadow cursor-pointer shrink-0"
                  title="Tạo cuộc trò chuyện mới"
                >
                  <Plus className="w-5 h-5" />
                </button>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ATTACHMENT_ACCEPT}
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleAttachFile(file);
                    e.target.value = "";
                  }}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadingAttachment}
                  className="p-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/80 hover:border-brand-500 dark:hover:border-brand-500/50 text-slate-550 hover:text-brand-600 dark:text-slate-400 dark:hover:text-brand-400 rounded-full transition shadow-sm hover:shadow cursor-pointer shrink-0 disabled:opacity-50"
                  title="Đính kèm file (PDF/DOC/DOCX/ảnh) cho AI đọc"
                >
                  <Paperclip className="w-5 h-5" />
                </button>

                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    send();
                  }}
                  className="flex-1 relative flex items-center"
                >
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    disabled={isLoading || loadingMessages}
                    placeholder="Nhập câu hỏi phân tích học lực..."
                    className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 focus:border-brand-500 dark:focus:border-brand-500 text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-550 text-sm pl-5 pr-14 py-3.5 rounded-full outline-none transition shadow-inner"
                  />
                  <button
                    type="submit"
                    disabled={isLoading || loadingMessages || !input.trim()}
                    className="absolute right-2 p-2 bg-brand-600 hover:bg-brand-505 disabled:bg-slate-200 dark:disabled:bg-slate-800 disabled:text-slate-400 text-white rounded-full transition cursor-pointer"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>

                <button
                  type="button"
                  onClick={() => setShowFilesPalette(true)}
                  className="p-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/80 hover:border-brand-500 dark:hover:border-brand-500/50 text-slate-500 hover:text-brand-600 dark:text-slate-400 dark:hover:text-brand-400 rounded-full transition shadow-sm hover:shadow cursor-pointer shrink-0"
                  title="Tài liệu trong đoạn chat"
                >
                  <FolderOpen className="w-5 h-5" />
                </button>

                <button
                  type="button"
                  onClick={() => setShowHistoryPalette(true)}
                  className="p-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/80 hover:border-brand-500 dark:hover:border-brand-500/50 text-slate-500 hover:text-brand-600 dark:text-slate-400 dark:hover:text-brand-400 rounded-full transition shadow-sm hover:shadow cursor-pointer shrink-0"
                  title="Lịch sử hội thoại"
                >
                  <History className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Cột 2: Right side document preview split screen */}
        <div
          className={`h-full flex flex-col overflow-hidden shrink-0 z-10 transition-standard bg-slate-50 dark:bg-slate-950/30 ${previewModalUrl
            ? "w-[65%] p-4 pl-2 opacity-100 translate-x-0"
            : "w-0 p-0 opacity-0 translate-x-full pointer-events-none"
            }`}
        >
          {previewFileName && (
            <div className="flex-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-[24px] shadow-lg flex flex-col overflow-hidden">
              {/* Split Screen Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 flex-shrink-0">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="font-bold text-slate-850 dark:text-slate-100 text-sm truncate">
                    {previewFileName}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {/* Download Dropdown button */}
                  <div className="relative">
                    <button
                      onClick={() => setShowDownloadDropdown(!showDownloadDropdown)}
                      className="px-3.5 py-1.5 bg-brand-50 hover:bg-brand-100 dark:bg-brand-950/40 dark:hover:bg-brand-900/50 text-brand-700 dark:text-brand-350 rounded-full text-xs font-bold flex items-center gap-1 transition cursor-pointer"
                    >
                      <span>Tải về</span>
                      <ChevronDown className="w-3 h-3" />
                    </button>

                    {showDownloadDropdown && (
                      <>
                        <div className="fixed inset-0 z-10" onClick={() => setShowDownloadDropdown(false)} />
                        <div className="absolute right-0 mt-1.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg min-w-[190px] flex flex-col py-1.5 z-20 animate-in zoom-in-95 duration-100">
                          <button
                            onClick={() => {
                              // Tải Word
                              const docxUrl = previewModalUrl?.replace(/\.html$/, ".docx") || "";
                              const a = document.createElement("a");
                              a.href = docxUrl;
                              a.target = "_blank";
                              a.click();
                              setShowDownloadDropdown(false);
                            }}
                            className="px-4 py-2 text-left text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 flex items-center gap-2.5 transition"
                          >
                            <FileText className="w-4 h-4 text-brand-600" />
                            <span>Tải xuống Word (.docx)</span>
                          </button>
                          <button
                            onClick={() => {
                              // Tải PDF
                              const pdfUrl = previewModalUrl?.replace(/\.html$/, ".pdf") || "";
                              const a = document.createElement("a");
                              a.href = pdfUrl;
                              a.target = "_blank";
                              a.click();
                              setShowDownloadDropdown(false);
                            }}
                            className="px-4 py-2 text-left text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 flex items-center gap-2.5 transition"
                          >
                            <FileText className="w-4 h-4 text-rose-505" />
                            <span>Tải xuống PDF (.pdf)</span>
                          </button>
                        </div>
                      </>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => setPreviewModalUrl(null)}
                    className="p-1.5 rounded-full hover:bg-slate-100 dark:hover:bg-slate-850 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 transition cursor-pointer"
                    title="Đóng bản xem trước"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Split Screen Content - iframe */}
              <div className="flex-1 bg-slate-100 dark:bg-slate-950 p-4 md:p-6 overflow-hidden flex justify-center items-center">
                {loadingPreview ? (
                  <div className="flex flex-col items-center gap-3">
                    <Loader2 className="w-7 h-7 text-brand-500 animate-spin" />
                    <span className="text-xs text-slate-500 dark:text-slate-400">Đang tải bản xem trước...</span>
                  </div>
                ) : previewHtml ? (
                  <iframe
                    srcDoc={previewHtml}
                    className="w-full h-full border-0 bg-white rounded-xl shadow-md overflow-hidden"
                    title="Bản xem trước báo cáo tự do"
                  />
                ) : (
                  <span className="text-xs text-slate-500">Không có dữ liệu hiển thị.</span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* History Command Palette Search Modal */}
      {showHistoryPalette && (
        <div
          className="fixed inset-0 bg-slate-950/50 backdrop-blur-sm z-50 flex justify-center pt-[15vh] px-4 animate-in fade-in duration-150"
          onClick={() => setShowHistoryPalette(false)}
        >
          <div
            className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden h-fit max-h-[480px] flex flex-col animate-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Search Input Box */}
            <div className="flex items-center gap-3 px-4 py-3.5 border-b border-slate-100 dark:border-slate-800">
              <Search className="w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Tìm kiếm hội thoại..."
                value={searchHistoryQuery}
                onChange={(e) => setSearchHistoryQuery(e.target.value)}
                className="w-full bg-transparent border-0 text-sm text-slate-800 dark:text-slate-100 outline-none placeholder-slate-400"
                autoFocus
              />
            </div>

            {/* Results List */}
            <div className="flex-1 overflow-y-auto p-2 space-y-1 max-h-[300px]">
              <div className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase px-3 py-2 tracking-wider">
                Hội thoại gần đây
              </div>
              {filteredSessions.length === 0 ? (
                <div className="p-8 text-center text-sm text-slate-500 dark:text-slate-400">
                  Không tìm thấy hội thoại nào
                </div>
              ) : (
                filteredSessions.map((s) => (
                  <div
                    key={s.id}
                    onClick={() => {
                      setActiveSessionId(s.id);
                      router.push(`/chat?session=${s.id}`);
                      setShowHistoryPalette(false);
                    }}
                    className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium transition cursor-pointer group ${activeSessionId === s.id
                      ? "bg-brand-50 dark:bg-brand-950/40 text-brand-600 dark:text-brand-400"
                      : "text-slate-650 dark:text-slate-350 hover:bg-slate-50 dark:hover:bg-slate-850 hover:text-slate-900 dark:hover:text-slate-100"
                      }`}
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <MessageSquare className="w-4 h-4 text-slate-400 shrink-0 group-hover:text-brand-500" />
                      {editingSessionId === s.id ? (
                        <input
                          type="text"
                          value={editTitleInput}
                          onChange={(e) => setEditTitleInput(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleRename(s.id);
                            else if (e.key === "Escape") setEditingSessionId(null);
                          }}
                          onClick={(e) => e.stopPropagation()}
                          className="flex-1 bg-white dark:bg-slate-800 border border-slate-350 dark:border-slate-700 px-2 py-0.5 rounded outline-none text-sm text-slate-800 dark:text-slate-100"
                          autoFocus
                        />
                      ) : (
                        <div className="flex flex-col min-w-0">
                          <span className="truncate">{s.title || "Cuộc trò chuyện mới"}</span>
                          <span className="text-[10px] text-slate-400 dark:text-slate-500 font-normal">
                            {timeAgo(s.updated_at || s.created_at)}
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity ml-2 shrink-0">
                      {editingSessionId === s.id ? (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRename(s.id);
                          }}
                          className="p-1 hover:bg-slate-105 dark:hover:bg-slate-700 rounded text-emerald-600"
                          title="Lưu"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingSessionId(s.id);
                            setEditTitleInput(s.title || "");
                          }}
                          className="p-1 hover:bg-slate-100 dark:hover:bg-slate-750 rounded text-slate-400 hover:text-slate-650"
                          title="Đổi tên"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(s.id, e);
                        }}
                        className="p-1 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded text-slate-400 hover:text-rose-600"
                        title="Xóa"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Palette Footer */}
            <div className="px-4 py-2.5 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30 text-[10px] text-slate-450 dark:text-slate-500 flex justify-between">
              <span>Nhấn Esc để đóng</span>
              <span>Chọn cuộc hội thoại để xem lại</span>
            </div>
          </div>
        </div>
      )}

      {/* Files Popup Overlay Modal */}
      {showFilesPalette && (
        <div
          className="fixed inset-0 bg-slate-950/50 backdrop-blur-sm z-50 flex justify-center pt-[15vh] px-4 animate-in fade-in duration-150"
          onClick={() => setShowFilesPalette(false)}
        >
          <div
            className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden h-fit max-h-[480px] flex flex-col animate-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Files Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-800">
              <h3 className="font-bold text-slate-900 dark:text-white text-sm flex items-center gap-2">
                <FolderOpen className="w-5 h-5 text-brand-600 dark:text-brand-400" />
                <span>Tài liệu trong đoạn chat</span>
              </h3>
              <button
                type="button"
                onClick={() => setShowFilesPalette(false)}
                className="p-1.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Files List Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-[350px]">
              {allFilesInSession.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center text-slate-500">
                  <FolderOpen className="w-10 h-10 text-slate-350 stroke-1.5 mb-2" />
                  <span className="text-sm">Không có tài liệu nào trong đoạn chat này</span>
                </div>
              ) : (
                allFilesInSession.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm hover:shadow-md transition duration-200"
                  >
                    <div className="flex items-center gap-3.5 min-w-0">
                      <div className="p-3 rounded-xl bg-brand-50 dark:bg-brand-950/40 text-brand-600 dark:text-brand-400 border border-brand-100 dark:border-brand-900/30 shrink-0">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div className="min-w-0">
                        <h4 className="font-bold text-slate-800 dark:text-slate-100 text-xs sm:text-sm truncate">
                          {file.title}
                        </h4>
                        <p className="text-[10px] sm:text-xs text-slate-500 dark:text-slate-450 mt-1">
                          Định dạng: {[file.docxUrl && "Word (.docx)", file.pdfUrl && "PDF (.pdf)", file.htmlUrl && "Xem trước"].filter(Boolean).join(" • ")}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 ml-3">
                      {file.htmlUrl && (
                        <button
                          type="button"
                          onClick={() => {
                            handleOpenPreview(file.htmlUrl!);
                            setShowFilesPalette(false);
                          }}
                          className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-xl text-xs font-bold transition shadow-sm cursor-pointer"
                        >
                          Open
                        </button>
                      )}

                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Files Footer */}
            <div className="px-4 py-2.5 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30 text-[10px] text-slate-400 dark:text-slate-500 text-right">
              <span>Tổng số: {allFilesInSession.length} tài liệu</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center bg-slate-50 dark:bg-slate-950/30">
          <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
        </div>
      }
    >
      <ChatContent />
    </Suspense>
  );
}
