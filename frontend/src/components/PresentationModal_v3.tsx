"use client";

import React, { useState, useEffect } from "react";
import {
  X, ChevronLeft, ChevronRight, Cpu, BarChart2, ShieldAlert, Sparkles, BookOpen,
  Database, FileText, Clock, AlertTriangle, MessageSquare, Video, ArrowRight,
  Maximize2, Minimize2, Play, Pause, ArrowDown, Mic, Target, Tag, Settings, CheckCircle2,
  GraduationCap, Shield, Star, Rocket, Layout, Calendar, Layers, Network, Lock,
  RefreshCw, BarChart3, Search, Activity, GitBranch, Terminal, Zap, TrendingUp, Laptop, Brain, ExternalLink
} from "lucide-react";

interface PresentationModalProps {
  isOpen: boolean;
  onClose: () => void;
  theme: string;
}

// =============================================================================
// COMPONENT 1: SOLUTION DIAGRAM (BÁO CÁO 01 — MULTI-AGENT CHAT & TOÀN CẢNH)
// =============================================================================
function SolutionDiagram({ isDark }: { isDark: boolean }) {
  const [activeFlow, setActiveFlow] = useState<number>(0);
  const nodeInactiveClass = isDark
    ? "opacity-30 bg-[#070e1a]/60 border-[#263750] text-[#8f9cae] hover:opacity-80"
    : "opacity-35 bg-white/60 border-[#dcd7cc] text-[#4a5568] hover:opacity-80";

  const nodeActiveClass = isDark
    ? "bg-[#2d6a4f]/20 border-[#52b788] text-[#52b788] shadow-[0_0_10px_rgba(82,183,136,0.25)]"
    : "bg-[#f0faf4] border-[#2d6a4f] text-[#2d6a4f] shadow-[0_0_10px_rgba(45,106,79,0.2)]";

  const flows = [
    {
      id: 0,
      title: "1. Multi-Agent Chatbot (LangGraph)",
      desc: "Người dùng hỏi tự nhiên qua Chatbot. Supervisor Orchestrator tiếp nhận, phân tích intent và điều phối 4 Sub-Agents chuyên biệt (Data & SQL, Stat, Knowledge RAG, Report) truy xuất CSDL PostgreSQL và Qdrant để trả về câu trả lời chính xác kèm trích dẫn dữ liệu.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["input_chat", "super", "data_agent", "stat_agent", "knowledge_agent", "report_agent", "school_db", "qdrant_db", "chat_response"],
      activeLines: ["chat-super", "super-data", "super-stat", "stat-know", "super-report", "data-db", "know-qdrant", "db-chat"]
    },
    {
      id: 1,
      title: "2. EWS Pipeline (CatBoost ML & SHAP)",
      desc: "Admin/BGH kích hoạt EWS Job. Worker chạy FIFO, trích xuất 22 Features từ 4 nguồn DWH (Điểm, LMS, Chuyên cần, Hạnh kiểm) bằng Materialized SQL trong < 5s, suy luận qua 5-Fold CatBoost Ensemble, tính SHAP drivers giải trình nguyên nhân và lưu bảng cảnh báo rủi ro.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["input_ews", "ews_engine", "dwh_db", "school_db", "ews_output"],
      activeLines: ["ews-engine", "dwh-engine", "engine-db", "engine-ews-out"]
    },
    {
      id: 2,
      title: "3. Curriculum Ingest & RAG SGK (VLM)",
      desc: "Admin tải PDF/DOCX SGK. Pipeline VLM 2 lượt quét chống bịa (Lượt A lấy NEO mục lục 15 trang đầu, Lượt B duyệt từng trang và bắt buộc neo vào bài học), trích xuất tóm tắt/từ khóa và embedding vector chunks vào Qdrant để Knowledge Agent tra cứu có trích dẫn.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["input_pdf_curriculum", "vlm_pipeline", "qdrant_db", "school_db", "curriculum_output"],
      activeLines: ["curriculum-vlm", "vlm-qdrant", "vlm-db", "qdrant-curriculum-out"]
    },
    {
      id: 3,
      title: "4. Pass/Fail Forecast (Math & CDI)",
      desc: "Hệ thống lấy ma trận đề thi cuối kỳ (trọng số bài học) và năng lực LMS học sinh, giải quyết qua chuỗi 4 tầng fallback, áp dụng hệ số điều chỉnh độ khó đề thi CDI thuần toán học để dự báo điểm số chính xác và cảnh báo học sinh nguy cơ trượt thi.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["input_exam_forecast", "forecast_engine", "school_db", "forecast_output"],
      activeLines: ["forecast-in-engine", "db-forecast-engine", "engine-forecast-out"]
    },
    {
      id: 4,
      title: "5. TEVI (Độ Khó & Công Bằng Điểm)",
      desc: "Đối soát chéo giữa độ khó thiết kế đề thi (CDI từ ma trận Bloom) và độ khó thực nghiệm (EDI từ phổ điểm học sinh thật). Tự động phát hiện đề ra quá khó (HAMMER), lạm phát điểm (INFLATED) và các dấu hiệu bất thường như nghi ưu ái hoặc chèn ép điểm số.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["input_exam_validity", "tevi_engine", "school_db", "tevi_output"],
      activeLines: ["tevi-in-engine", "db-tevi-engine", "engine-tevi-out"]
    },
    {
      id: 5,
      title: "6. Chẩn Đoán Lỗ Hổng Kiến Thức",
      desc: "Tổng hợp toàn bộ câu trả lời LMS của học sinh, nhân hệ số bao phủ Bloom (Breadth Ratio) & Vận dụng cao (Depth Factor), đối soát chéo với điểm thi thật (Δ = LMS - Exam), áp dụng Majority Rule gộp trạng thái cấp học sinh và xuất bảng Roster lỗ hổng chi tiết.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["input_knowledge_gaps", "gap_engine", "school_db", "gap_output"],
      activeLines: ["gap-in-engine", "db-gap-engine", "engine-gap-out"]
    }
  ];

  const current = flows[activeFlow];
  const isNodeActive = (nodeId: string) => current.activeNodes.includes(nodeId);

  const allPaths = [
    { id: "chat-super", d: "M 180 77.5 L 215 77.5" },
    { id: "super-data", d: "M 335 77.5 L 345 77.5" },
    { id: "super-stat", d: "M 275 97.5 L 275 110" },
    { id: "stat-know", d: "M 335 127.5 L 345 127.5" },
    { id: "super-report", d: "M 275 97.5 L 275 155" },
    { id: "data-db", d: "M 455 77.5 L 485 77.5" },
    { id: "know-qdrant", d: "M 455 127.5 L 485 185" },
    { id: "db-chat", d: "M 555 77.5 L 590 77.5" },
    { id: "ews-engine", d: "M 180 140 L 215 222.5" },
    { id: "dwh-engine", d: "M 485 300 L 465 222.5" },
    { id: "engine-db", d: "M 465 222.5 L 485 100" },
    { id: "engine-ews-out", d: "M 465 222.5 L 590 140" },
    { id: "curriculum-vlm", d: "M 180 200 L 215 267.5" },
    { id: "vlm-qdrant", d: "M 465 267.5 L 485 200" },
    { id: "vlm-db", d: "M 465 267.5 L 485 120" },
    { id: "qdrant-curriculum-out", d: "M 555 200 L 590 200" },
    { id: "forecast-in-engine", d: "M 180 260 L 215 312.5" },
    { id: "db-forecast-engine", d: "M 485 130 L 465 312.5" },
    { id: "engine-forecast-out", d: "M 465 312.5 L 590 260" },
    { id: "tevi-in-engine", d: "M 180 320 L 215 357.5" },
    { id: "db-tevi-engine", d: "M 485 140 L 465 357.5" },
    { id: "engine-tevi-out", d: "M 465 357.5 L 590 320" },
    { id: "gap-in-engine", d: "M 180 380 L 215 402.5" },
    { id: "db-gap-engine", d: "M 485 150 L 465 402.5" },
    { id: "engine-gap-out", d: "M 465 402.5 L 590 380" }
  ];

  return (
    <div className="w-full h-full max-w-none relative overflow-hidden flex flex-col lg:flex-row gap-6 p-0 bg-transparent border-none shadow-none">
      <style>{`
        @keyframes stroke-flow { to { stroke-dashoffset: -20; } }
        .animated-flow-line { stroke-dasharray: 6, 4; animation: stroke-flow 1.2s linear infinite; }
      `}</style>

      {/* LEFT SIDE: DIAGRAM CANVAS */}
      <div className="flex-1 min-w-0 h-full relative flex items-center justify-center">
        <div className="relative w-full h-full select-none">
          <svg className="absolute inset-0 w-full h-full pointer-events-none z-10" viewBox="0 0 800 430" fill="none">
            {allPaths.map((p) => (
              <path key={`bg-${p.id}`} d={p.d} stroke={isDark ? "#1b1d26" : "#e2e8f0"} strokeWidth="1.25" />
            ))}

            {/* Multi-Agent Box */}
            <rect
              x="205"
              y="40"
              width="265"
              height="155"
              rx="12"
              stroke={current.id === 0 ? (isDark ? "#52b788" : "#2d6a4f") : (isDark ? "#263750" : "#dcd7cc")}
              strokeWidth={current.id === 0 ? "2.5" : "1.25"}
              fill={isDark ? "#070e1a" : "#f5f1e6"}
              fillOpacity="0.85"
              className={current.id === 0 ? "transition-all duration-300 shadow-[0_0_15px_rgba(82,183,136,0.15)]" : "transition-all duration-300"}
            />
            <text x="337" y="55" fill={isDark ? "#c2ae78" : "#8c763e"} fontSize="7" fontFamily="monospace" letterSpacing="1" fontWeight="bold" textAnchor="middle">BỘ XỬ LÝ MULTI-AGENT (LANGGRAPH)</text>

            {/* Data Layer Box */}
            <rect
              x="480"
              y="40"
              width="80"
              height="375"
              rx="12"
              stroke={isNodeActive("school_db") || isNodeActive("qdrant_db") || isNodeActive("dwh_db") ? (isDark ? "#52b788" : "#2d6a4f") : (isDark ? "#263750" : "#dcd7cc")}
              strokeWidth="1.25"
              strokeDasharray="3,3"
              fill={isDark ? "#070e1a" : "#f5f1e6"}
              fillOpacity="0.4"
              className="transition-all duration-300"
            />
            <text x="520" y="55" fill={isDark ? "#c2ae78" : "#8c763e"} fontSize="6.5" fontFamily="monospace" letterSpacing="0.5" fontWeight="bold" textAnchor="middle">DATA LAYER</text>

            <text x="30" y="30" fill={isDark ? "#c2ae78" : "#8c763e"} fontSize="8.5" fontFamily="monospace" letterSpacing="1.5" fontWeight="bold">DỮ LIỆU ĐẦU VÀO / TRIGGER</text>
            <text x="590" y="30" fill={isDark ? "#c2ae78" : "#8c763e"} fontSize="8.5" fontFamily="monospace" letterSpacing="1.5" fontWeight="bold">KẾT QUẢ ĐẦU RA / INSIGHTS</text>

            {/* Active flow lines */}
            {allPaths.map((p) => {
              if (current.activeLines.includes(p.id)) {
                return (
                  <path
                    key={`active-${p.id}`}
                    d={p.d}
                    stroke={current.stroke}
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    className="animated-flow-line"
                  />
                );
              }
              return null;
            })}

            {/* LEFT NODES (6 Real Technical Inputs) */}
            {/* Input 1: Chatbot Input */}
            <foreignObject x="30" y="55" width="150" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("input_chat") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(0)}>
                <MessageSquare className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-bold truncate">Câu hỏi Chatbot AI</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Ngôn ngữ tự nhiên</div>
                </div>
              </div>
            </foreignObject>

            {/* Input 2: EWS Job Trigger */}
            <foreignObject x="30" y="117" width="150" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("input_ews") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(1)}>
                <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-bold truncate">Kích hoạt EWS Job</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Admin / Hiệu trưởng</div>
                </div>
              </div>
            </foreignObject>

            {/* Input 3: PDF Sách Giáo Khoa */}
            <foreignObject x="30" y="177" width="150" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-2 rounded-xl border flex items-center gap-2 cursor-pointer transition-all duration-300 ${isNodeActive("input_pdf_curriculum") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(2)}>
                <BookOpen className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-bold truncate">PDF Sách Giáo Khoa</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">File scan/in ấn gốc</div>
                </div>
              </div>
            </foreignObject>

            {/* Input 4: Đề thi & LMS */}
            <foreignObject x="30" y="237" width="150" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("input_exam_forecast") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(3)}>
                <TrendingUp className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-bold truncate">Đề Thi & LMS Mastery</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Ma trận & Điểm LMS</div>
                </div>
              </div>
            </foreignObject>

            {/* Input 5: Sổ điểm & Đề kiểm tra */}
            <foreignObject x="30" y="297" width="150" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("input_exam_validity") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(4)}>
                <Target className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-bold truncate">Sổ Điểm & Đề Thi</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Điểm TX, GK, CK</div>
                </div>
              </div>
            </foreignObject>

            {/* Input 6: Hàng ngàn câu làm bài LMS */}
            <foreignObject x="30" y="357" width="150" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("input_knowledge_gaps") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(5)}>
                <Activity className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-bold truncate">LMS Items & Bài Thi</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Hàng ngàn câu trả lời</div>
                </div>
              </div>
            </foreignObject>

            {/* MIDDLE: MULTI-AGENT SUB-AGENTS */}
            {/* Supervisor */}
            <foreignObject x="215" y="62" width="115" height="35" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("super") ? nodeActiveClass : nodeInactiveClass}`}>
                <Cpu className="w-3 h-3 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[7.5px] font-bold truncate">Supervisor Router</div>
                  <div className="text-[6px] font-mono text-slate-500 truncate">Điều phối hệ thống</div>
                </div>
              </div>
            </foreignObject>

            {/* Data & SQL Agent */}
            <foreignObject x="345" y="62" width="115" height="35" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("data_agent") ? nodeActiveClass : nodeInactiveClass}`}>
                <Cpu className="w-3 h-3 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[7.5px] font-bold truncate">Data & SQL Agent</div>
                  <div className="text-[6px] font-mono text-slate-500 truncate">Truy vấn điểm số & RLS</div>
                </div>
              </div>
            </foreignObject>

            {/* Stat Agent */}
            <foreignObject x="215" y="105" width="115" height="35" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("stat_agent") ? nodeActiveClass : nodeInactiveClass}`}>
                <Cpu className="w-3 h-3 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[7.5px] font-bold truncate">Stat Agent</div>
                  <div className="text-[6px] font-mono text-slate-500 truncate">GDI & Momentum</div>
                </div>
              </div>
            </foreignObject>

            {/* Knowledge Agent */}
            <foreignObject x="345" y="105" width="115" height="35" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("knowledge_agent") ? nodeActiveClass : nodeInactiveClass}`}>
                <Cpu className="w-3 h-3 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[7.5px] font-bold truncate">Knowledge Agent</div>
                  <div className="text-[6px] font-mono text-slate-500 truncate">RAG Sách giáo khoa</div>
                </div>
              </div>
            </foreignObject>

            {/* Report Agent */}
            <foreignObject x="280" y="148" width="115" height="35" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("report_agent") ? nodeActiveClass : nodeInactiveClass}`}>
                <Cpu className="w-3 h-3 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[7.5px] font-bold truncate">Report Agent</div>
                  <div className="text-[6px] font-mono text-slate-500 truncate">Biên soạn Word/PDF</div>
                </div>
              </div>
            </foreignObject>

            {/* MIDDLE: 5 TECHNICAL PIPELINE ENGINES */}
            {/* EWS Engine */}
            <foreignObject x="215" y="205" width="245" height="35" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-2 cursor-pointer transition-all duration-300 ${isNodeActive("ews_engine") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(1)}>
                <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate">EWS Engine (CatBoost 5-Fold Ensemble + SHAP)</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">22 Features DWH · DB FIFO Queue Worker</div>
                </div>
              </div>
            </foreignObject>

            {/* VLM Pipeline */}
            <foreignObject x="215" y="250" width="245" height="35" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-2 cursor-pointer transition-all duration-300 ${isNodeActive("vlm_pipeline") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(2)}>
                <BookOpen className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate">VLM Pipeline 2 Lượt Quét (Mục Lục & NEO)</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">Chống bịa 100% · Qdrant Vector Chunking</div>
                </div>
              </div>
            </foreignObject>

            {/* Forecast Engine */}
            <foreignObject x="215" y="295" width="245" height="35" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-2 cursor-pointer transition-all duration-300 ${isNodeActive("forecast_engine") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(3)}>
                <TrendingUp className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate">Pass/Fail Forecast (Thuần Toán Học & CDI Adj)</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">4 Tầng Fallback Ability · Điều chỉnh độ khó đề</div>
                </div>
              </div>
            </foreignObject>

            {/* TEVI Engine */}
            <foreignObject x="215" y="340" width="245" height="35" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-2 cursor-pointer transition-all duration-300 ${isNodeActive("tevi_engine") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(4)}>
                <Target className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate">TEVI Triangulation (EDI vs CDI & Cảnh Báo)</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">Divergence CDI−EDI · Nghi Ưu Ái / Chèn Ép Điểm</div>
                </div>
              </div>
            </foreignObject>

            {/* Gap Cross-Validation Engine */}
            <foreignObject x="215" y="385" width="245" height="35" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-2 cursor-pointer transition-all duration-300 ${isNodeActive("gap_engine") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(5)}>
                <Activity className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate">Knowledge Gap Engine (Bloom & Cross-Val)</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">Đối soát đa nguồn Δ=LMS−Exam · Majority Rule</div>
                </div>
              </div>
            </foreignObject>

            {/* DATA LAYER: 3 STACKS */}
            {/* 1. Postgres */}
            <foreignObject x="485" y="65" width="70" height="95" className="pointer-events-auto">
              <div className={`w-full h-full rounded-xl border flex flex-col items-center justify-center p-1.5 text-center transition-all duration-300 ${isNodeActive("school_db") ? nodeActiveClass : nodeInactiveClass}`}>
                <Database className="w-4 h-4 mb-1 text-emerald-500" />
                <div className="text-[7.5px] font-bold leading-tight">PostgreSQL<br />CSDL Trường</div>
                <span className="text-[6px] text-slate-400 mt-1">RLS & Tenant</span>
              </div>
            </foreignObject>

            {/* 2. Qdrant */}
            <foreignObject x="485" y="168" width="70" height="95" className="pointer-events-auto">
              <div className={`w-full h-full rounded-xl border flex flex-col items-center justify-center p-1.5 text-center transition-all duration-300 ${isNodeActive("qdrant_db") ? nodeActiveClass : nodeInactiveClass}`}>
                <Layers className="w-4 h-4 mb-1 text-blue-500" />
                <div className="text-[7.5px] font-bold leading-tight">Qdrant<br />Vector DB</div>
                <span className="text-[6px] text-slate-400 mt-1">Curriculum RAG</span>
              </div>
            </foreignObject>

            {/* 3. DWH */}
            <foreignObject x="485" y="271" width="70" height="95" className="pointer-events-auto">
              <div className={`w-full h-full rounded-xl border flex flex-col items-center justify-center p-1.5 text-center transition-all duration-300 ${isNodeActive("dwh_db") ? nodeActiveClass : nodeInactiveClass}`}>
                <BarChart3 className="w-4 h-4 mb-1 text-amber-500" />
                <div className="text-[7.5px] font-bold leading-tight">DWH s360<br />Analytics</div>
                <span className="text-[6px] text-slate-400 mt-1">22 Features SQL</span>
              </div>
            </foreignObject>

            {/* RIGHT OUTPUT NODES (6 Real Technical Outputs) */}
            {/* Output 1: Chat Response */}
            <foreignObject x="590" y="55" width="165" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("chat_response") ? nodeActiveClass : nodeInactiveClass}`}>
                <MessageSquare className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-bold truncate">Câu Trả Lời & Báo Cáo</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Trích dẫn nguồn & Dữ liệu chuẩn</div>
                </div>
              </div>
            </foreignObject>

            {/* Output 2: EWS Warnings */}
            <foreignObject x="590" y="117" width="165" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("ews_output") ? nodeActiveClass : nodeInactiveClass}`}>
                <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-bold truncate">Cảnh Báo EWS & SHAP</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Mức Rủi Ro & Top Căn Nguyên</div>
                </div>
              </div>
            </foreignObject>

            {/* Output 3: Curriculum Chunks */}
            <foreignObject x="590" y="177" width="165" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("curriculum_output") ? nodeActiveClass : nodeInactiveClass}`}>
                <BookOpen className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-bold truncate">Cây Tri Thức & Chunks</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Tra cứu RAG có trích dẫn</div>
                </div>
              </div>
            </foreignObject>

            {/* Output 4: Pass/Fail Output */}
            <foreignObject x="590" y="237" width="165" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("forecast_output") ? nodeActiveClass : nodeInactiveClass}`}>
                <TrendingUp className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-bold truncate">Dự Báo PASS/FAIL & Điểm</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Điểm thi & Top 2 bài yếu</div>
                </div>
              </div>
            </foreignObject>

            {/* Output 5: TEVI Validity */}
            <foreignObject x="590" y="297" width="165" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("tevi_output") ? nodeActiveClass : nodeInactiveClass}`}>
                <Target className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-bold truncate">Cảnh Báo TEVI & Công Bằng</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">HAMMER / INFLATED / Ưu ái</div>
                </div>
              </div>
            </foreignObject>

            {/* Output 6: Knowledge Gaps */}
            <foreignObject x="590" y="357" width="165" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("gap_output") ? nodeActiveClass : nodeInactiveClass}`}>
                <Activity className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-bold truncate">Chẩn Đoán Lỗ Hổng & Roster</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Đồng thuận & Độ tin cậy %</div>
                </div>
              </div>
            </foreignObject>
          </svg>
        </div>
      </div>

      {/* RIGHT SIDE: BUSINESS FLOW SELECTOR */}
      <div className="w-full lg:w-72 shrink-0 flex flex-col justify-between py-2 text-left space-y-4">
        <div>
          <div className={`text-[10px] font-mono font-bold tracking-wider uppercase mb-3 ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"}`}>
            CHỌN LUỒNG KỸ THUẬT:
          </div>
          <div className="space-y-2">
            {flows.map((f, idx) => (
              <button
                key={f.id}
                onClick={() => setActiveFlow(idx)}
                className={`w-full p-2.5 rounded-xl border text-left transition-all duration-200 flex items-center justify-between text-xs font-bold ${
                  activeFlow === idx
                    ? isDark
                      ? "bg-[#070e1a] border-[#52b788] text-[#52b788] shadow-[0_0_10px_rgba(82,183,136,0.2)]"
                      : "bg-[#0f1e36] text-white border-[#0f1e36] shadow-sm"
                    : isDark
                    ? "bg-[#070e1a]/40 border-[#263750] text-[#8f9cae] hover:border-slate-600 hover:text-white"
                    : "bg-white border-[#dcd7cc] text-[#4a5568] hover:border-[#8c763e] hover:text-[#0f1e36]"
                }`}
              >
                <span className="truncate">{f.title}</span>
                {activeFlow === idx && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />}
              </button>
            ))}
          </div>
        </div>

        {/* Dynamic Detail Card */}
        <div className={`p-4 rounded-2xl border ${isDark ? "bg-[#070e1a]/90 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
          <div className={`text-xs font-bold mb-1.5 uppercase tracking-wider ${isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}`}>
            {current.title}
          </div>
          <div className={`text-[11px] leading-relaxed ${isDark ? "text-slate-300" : "text-[#4a5568]"}`}>
            {current.desc}
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// COMPONENT 2: PRESENTATION MODAL V3 COMPONENT
// =============================================================================
export default function PresentationModalV3({ isOpen, onClose, theme }: PresentationModalProps) {
  const [currentSlide, setCurrentSlide] = useState(0);
  const isDark = theme === "dark";

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight" || e.key === " ") {
        setCurrentSlide((prev) => Math.min(prev + 1, slides.length - 1));
      }
      if (e.key === "ArrowLeft") {
        setCurrentSlide((prev) => Math.max(prev - 1, 0));
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  if (!isOpen) return null;

  const slides = [
    // =========================================================================
    // SLIDE 1: TIÊU ĐỀ DỰ ÁN (COVER)
    // =========================================================================
    {
      title: "VSF Student Risk Alert — Hệ Thống AI Phân Tích & Quản Trị Giáo Dục",
      subtitle: "Nền tảng EdTech toàn diện: AI Agent, ML, VLM, RAG & Phân tích học tập",
      type: "cover",
      content: (
        <div className="flex flex-col items-center justify-center text-center max-w-4xl mx-auto space-y-4 animate-fade-in py-3">
          <div className="relative">
            <div className={`absolute inset-0 ${isDark ? "bg-[#c2ae78]/10" : "bg-[#8c763e]/5"} blur-3xl rounded-full scale-150 animate-pulse`} />
            <div className={`relative w-16 h-16 rounded-2xl ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-white border-[#dcd7cc]"} flex items-center justify-center shadow-lg border shrink-0`}>
              <Brain className="w-10 h-10 text-[#2d6a4f] dark:text-[#52b788] animate-pulse" />
            </div>
          </div>
          <div className="space-y-2">
            <span className={`inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${isDark ? "bg-[#c2ae78]/10 text-[#c2ae78] border-[#c2ae78]/25" : "bg-white border-[#dcd7cc] text-[#8c763e]"} border`}>
              <Sparkles className="w-3 h-3 text-[#8c763e] dark:text-[#c2ae78]" /> Nền tảng EdTech AI Sư Phạm Thế Hệ Mới
            </span>
            <h1 className={`text-2xl md:text-3xl font-extrabold tracking-tight leading-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
              VSF Student Risk Alert
            </h1>
            <p className={`text-xs md:text-base max-w-2xl mx-auto leading-relaxed font-bold ${isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}`}>
              Hệ Thống Trợ Lý AI Phân Tích Kết Quả Học Tập &<br />
              Quản Trị Chất Lượng Giáo Dục Toàn Trường
            </p>
            <p className={`text-[11px] md:text-xs max-w-xl mx-auto leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
              Báo cáo kiến trúc 6 trục công nghệ: Multi-Agent Chat, EWS CatBoost ML, VLM Curriculum Ingest, Pass/Fail Forecast, TEVI Validity & Chẩn đoán Lỗ hổng Kiến thức.
            </p>
          </div>
          <div className="pt-2 text-[11px] text-slate-400 flex items-center gap-2">
            <span>Dùng phím</span>
            <kbd className="px-2 py-0.5 rounded bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-[10px] font-mono">←</kbd>
            <kbd className="px-2 py-0.5 rounded bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-[10px] font-mono">→</kbd>
            <span>hoặc click nút điều hướng để bắt đầu duyệt Báo cáo</span>
          </div>
        </div>
      )
    },

    // =========================================================================
    // SLIDE 2: TÀI LIỆU BÁO CÁO KIẾN TRÚC HỆ THỐNG (FULL REPORTS)
    // =========================================================================
    {
      title: "Hồ Sơ Kiến Trúc & Tài Liệu Báo Cáo Kỹ Thuật Chi Tiết",
      subtitle: "Tổng hợp 5 bộ tài liệu đặc tả kiến trúc, công thức toán học và thực nghiệm dành cho Hội đồng / Mentor",
      type: "reports_index",
      content: (
        <div className="w-full text-left flex flex-col justify-center h-full max-w-5xl mx-auto space-y-2.5">
          {/* Banner Top */}
          <div className={`p-2.5 rounded-xl border flex items-center justify-between ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-[#8c763e] dark:text-[#c2ae78]" />
              <div>
                <h3 className={`text-xs font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Kho Tài Liệu Báo Cáo Chuyên Sâu Của Dự Án</h3>
                <p className="text-[10px] text-slate-400">Nhấp vào từng báo cáo bên dưới để mở toàn văn tài liệu trên Google Drive</p>
              </div>
            </div>
            <span className={`text-[9px] font-mono px-2.5 py-0.5 rounded-full font-bold ${isDark ? "bg-[#2d6a4f]/20 text-[#52b788]" : "bg-[#f0faf4] text-[#2d6a4f]"}`}>
              5 Báo Cáo Kỹ Thuật
            </span>
          </div>

          {/* HÀNG 1: 3 BÁO CÁO (01, 02, 03) */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            {/* Report 1 */}
            <a
              href="https://drive.google.com/file/d/1OsMIFQXG3SH_UJzvI40TEzFCpRata2fv/view?usp=sharing"
              target="_blank"
              rel="noopener noreferrer"
              className={`p-2.5 rounded-xl border flex flex-col justify-between transition-all duration-200 group hover:scale-[1.01] hover:shadow-md ${isDark ? "bg-[#070e1a]/80 border-[#263750] hover:border-[#52b788]" : "bg-white border-[#dcd7cc] hover:border-[#2d6a4f]"}`}
            >
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <Cpu className="w-3.5 h-3.5 text-[#2d6a4f] dark:text-[#52b788]" />
                    <span className="text-[9.5px] font-bold text-slate-400 font-mono">01_multi_agent_chat</span>
                  </div>
                  <ExternalLink className="w-3 h-3 text-slate-400 group-hover:text-[#52b788] transition" />
                </div>
                <h4 className={`text-[11px] font-bold mb-1 leading-snug ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
                  Multi-Agent Chatbot & Điều Phối LangGraph
                </h4>
                <p className={`text-[9.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                  Supervisor Router, 4 Sub-Agents (SQL, Stat, RAG, Report), Truy xuất CSDL & Trích dẫn chuẩn.
                </p>
              </div>
              <div className="mt-2 pt-1 border-t border-slate-200 dark:border-slate-800/60 flex items-center justify-between text-[9px] font-bold text-[#2d6a4f] dark:text-[#52b788]">
                <span>Xem tài liệu đầy đủ</span>
                <span>↗</span>
              </div>
            </a>

            {/* Report 2 */}
            <a
              href="https://drive.google.com/file/d/1NVlBB15pJyc2IyHE5XbYCJWeQAIDzBNp/view?usp=drive_link"
              target="_blank"
              rel="noopener noreferrer"
              className={`p-2.5 rounded-xl border flex flex-col justify-between transition-all duration-200 group hover:scale-[1.01] hover:shadow-md ${isDark ? "bg-[#070e1a]/80 border-[#263750] hover:border-[#52b788]" : "bg-white border-[#dcd7cc] hover:border-[#2d6a4f]"}`}
            >
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />
                    <span className="text-[9.5px] font-bold text-slate-400 font-mono">02_ews_pipeline</span>
                  </div>
                  <ExternalLink className="w-3 h-3 text-slate-400 group-hover:text-[#52b788] transition" />
                </div>
                <h4 className={`text-[11px] font-bold mb-1 leading-snug ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
                  Hệ Thống Cảnh Báo Sớm EWS & SHAP
                </h4>
                <p className={`text-[9.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                  22 Features DWH, 5-Fold CatBoost Ensemble, Softmax Dynamic Risk Score & SHAP Drivers.
                </p>
              </div>
              <div className="mt-2 pt-1 border-t border-slate-200 dark:border-slate-800/60 flex items-center justify-between text-[9px] font-bold text-[#2d6a4f] dark:text-[#52b788]">
                <span>Xem tài liệu đầy đủ</span>
                <span>↗</span>
              </div>
            </a>

            {/* Report 3 */}
            <a
              href="https://drive.google.com/file/d/1bnP6lF0ooftsJY1M_NOslz70YqDFpnGE/view?usp=drive_link"
              target="_blank"
              rel="noopener noreferrer"
              className={`p-2.5 rounded-xl border flex flex-col justify-between transition-all duration-200 group hover:scale-[1.01] hover:shadow-md ${isDark ? "bg-[#070e1a]/80 border-[#263750] hover:border-[#52b788]" : "bg-white border-[#dcd7cc] hover:border-[#2d6a4f]"}`}
            >
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5 text-blue-500" />
                    <span className="text-[9.5px] font-bold text-slate-400 font-mono">03_curriculum_rag</span>
                  </div>
                  <ExternalLink className="w-3 h-3 text-slate-400 group-hover:text-[#52b788] transition" />
                </div>
                <h4 className={`text-[11px] font-bold mb-1 leading-snug ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
                  Curriculum Ingestion & RAG SGK
                </h4>
                <p className={`text-[9.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                  VLM 2 lượt quét TOC/NEO chống bịa, Node phẳng, Qdrant Vector Chunking & Semantic Lookup.
                </p>
              </div>
              <div className="mt-2 pt-1 border-t border-slate-200 dark:border-slate-800/60 flex items-center justify-between text-[9px] font-bold text-[#2d6a4f] dark:text-[#52b788]">
                <span>Xem tài liệu đầy đủ</span>
                <span>↗</span>
              </div>
            </a>
          </div>

          {/* HÀNG 2: 2 BÁO CÁO (04, 05) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {/* Report 4 */}
            <a
              href="https://drive.google.com/file/d/11t-9IEdfNNmp7xjBkdlchjoCHHvoBLev/view?usp=drive_link"
              target="_blank"
              rel="noopener noreferrer"
              className={`p-2.5 rounded-xl border flex flex-col justify-between transition-all duration-200 group hover:scale-[1.01] hover:shadow-md ${isDark ? "bg-[#070e1a]/80 border-[#263750] hover:border-[#52b788]" : "bg-white border-[#dcd7cc] hover:border-[#2d6a4f]"}`}
            >
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <TrendingUp className="w-3.5 h-3.5 text-[#8c763e] dark:text-[#c2ae78]" />
                    <span className="text-[9.5px] font-bold text-slate-400 font-mono">04_pass_fail_forecast</span>
                  </div>
                  <ExternalLink className="w-3 h-3 text-slate-400 group-hover:text-[#52b788] transition" />
                </div>
                <h4 className={`text-[11px] font-bold mb-1 leading-snug ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
                  Dự Báo Pass/Fail & Phân Tích Đề Thi Cuối Kỳ
                </h4>
                <p className={`text-[9.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                  Test Blueprint Domain Sampling, CDI Adjustment Heuristic (Cold-Start), 4 Tầng Fallback & Weak Units.
                </p>
              </div>
              <div className="mt-2 pt-1 border-t border-slate-200 dark:border-slate-800/60 flex items-center justify-between text-[9px] font-bold text-[#2d6a4f] dark:text-[#52b788]">
                <span>Xem tài liệu đầy đủ</span>
                <span>↗</span>
              </div>
            </a>

            {/* Report 5 */}
            <a
              href="https://drive.google.com/file/d/1CrIF1EBG4EWYHKFT416O-OPvClfzZ5Cx/view?usp=drive_link"
              target="_blank"
              rel="noopener noreferrer"
              className={`p-2.5 rounded-xl border flex flex-col justify-between transition-all duration-200 group hover:scale-[1.01] hover:shadow-md ${isDark ? "bg-[#070e1a]/80 border-[#263750] hover:border-[#52b788]" : "bg-white border-[#dcd7cc] hover:border-[#2d6a4f]"}`}
            >
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-purple-500" />
                    <span className="text-[9.5px] font-bold text-slate-400 font-mono">05_knowledge_gaps</span>
                  </div>
                  <ExternalLink className="w-3 h-3 text-slate-400 group-hover:text-[#52b788] transition" />
                </div>
                <h4 className={`text-[11px] font-bold mb-1 leading-snug ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
                  Chẩn Đoán Lỗ Hổng Kiến Thức & Item Mastery
                </h4>
                <p className={`text-[9.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                  Item Mastery × Bloom Factor, Cross-Validation (Δ = LMS − Exam), Majority Rule & Báo cáo Roster.
                </p>
              </div>
              <div className="mt-2 pt-1 border-t border-slate-200 dark:border-slate-800/60 flex items-center justify-between text-[9px] font-bold text-[#2d6a4f] dark:text-[#52b788]">
                <span>Xem tài liệu đầy đủ</span>
                <span>↗</span>
              </div>
            </a>
          </div>
        </div>
      )
    },

    // =========================================================================
    // SLIDE 3: MULTI-AGENT CHAT & SƠ ĐỒ TOÀN CẢNH (BÁO CÁO 01)
    // =========================================================================
    {
      title: "Báo Cáo 01: Multi-Agent Chat & Sơ Đồ Toàn Cảnh Hệ Thống",
      subtitle: "LangGraph StateGraph, Supervisor Router, 4 Sub-Agents Chuyên Biệt & Cô Lập Dữ Liệu Trường Học",
      type: "report_01",
      content: <SolutionDiagram isDark={isDark} />
    },

    // =========================================================================
    // SLIDE 3: EWS — MỤC ĐÍCH + FLOW + 22 FEATURES (BÁO CÁO 02A)
    // =========================================================================
    {
      title: "Báo Cáo 02A: EWS Pipeline — Mục Đích, Flow & 22 Đặc Trưng",
      subtitle: "Phát hiện sớm học sinh nguy cơ rớt môn qua CatBoost ML trên 22 features từ 4 nguồn dữ liệu",
      type: "report_02a",
      content: (
        <div className="w-full text-left flex flex-col justify-center h-full max-w-5xl mx-auto space-y-2.5">
          {/* HÀNG 1: MỤC ĐÍCH + FLOW 4 BƯỚC */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-2.5">
            <div className={`md:col-span-4 p-2.5 rounded-xl border flex flex-col justify-center ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div className="flex items-center gap-1.5 mb-1">
                <ShieldAlert className="w-4 h-4 text-rose-500 shrink-0" />
                <h3 className={`text-xs font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Mục Đích EWS</h3>
              </div>
              <p className={`text-[10.5px] leading-relaxed ${isDark ? "text-slate-300" : "text-[#4a5568]"}`}>
                Dùng <strong>CatBoost GBDT</strong> phát hiện nguy cơ học sinh rớt môn qua <strong>22 đặc trưng</strong> từ 4 nguồn DWH. Hỗ trợ BGH/GV can thiệp kịp thời trước kỳ thi.
              </p>
            </div>

            <div className={`md:col-span-8 p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div className="flex items-center gap-1.5 mb-1.5">
                <GitBranch className="w-3.5 h-3.5 text-[#8c763e] dark:text-[#c2ae78]" />
                <h3 className={`text-xs font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Flow Tổng Quan 4 Bước</h3>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                {[
                  { num: "1", label: "Kích hoạt", desc: "POST /ews/predict → FIFO Job", color: "text-[#8c763e] dark:text-[#c2ae78]" },
                  { num: "2", label: "22 Features", desc: "Materialized SQL (<5s)", color: "text-blue-500" },
                  { num: "3", label: "CatBoost", desc: "5-Fold Ensemble", color: "text-purple-500" },
                  { num: "4", label: "SHAP", desc: "Giải trình + UPSERT", color: "text-emerald-500" }
                ].map((item, idx) => (
                  <div key={idx} className={`flex items-center gap-1.5 p-1.5 rounded-lg border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                    <span className={`text-sm font-black font-mono ${item.color}`}>{item.num}</span>
                    <div className="min-w-0">
                      <div className={`text-[10px] font-bold truncate ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>{item.label}</div>
                      <div className="text-[8.5px] text-slate-400 truncate">{item.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* HÀNG 2: 22 FEATURES 4 NHÓM */}
          <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="flex items-center gap-1.5 mb-1.5">
              <Database className="w-3.5 h-3.5 text-[#2d6a4f] dark:text-[#52b788]" />
              <h3 className={`text-xs font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>22 Đặc Trưng Trích Xuất Từ 4 Nguồn DWH</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
              {[
                { name: "Điểm Số", count: "9 features", items: ["TB sớm / muộn", "Độ dốc (Slope)", "Biến thiên & sụt giảm", "Điểm hệ số cao nhất"], color: "text-emerald-500" },
                { name: "LMS", count: "5 features", items: ["TB bài tập LMS", "Lệch LMS vs sổ điểm", "Tỷ lệ nộp bài", "Nộp bài 4 tuần gần"], color: "text-blue-500" },
                { name: "Chuyên Cần", count: "4 features", items: ["Nghỉ chung", "Nghỉ không phép", "Nghỉ có phép", "Đi muộn"], color: "text-amber-500" },
                { name: "Hạnh Kiểm", count: "4 features", items: ["Điểm trừ hành vi", "Tái phạm", "Kỷ luật nặng", "Loại môn & khối"], color: "text-rose-500" }
              ].map((group, idx) => (
                <div key={idx} className={`p-2 rounded-lg border ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc]"}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-[10px] font-bold ${group.color}`}>{group.name}</span>
                    <span className="text-[8px] font-mono text-slate-400">{group.count}</span>
                  </div>
                  <ul className="space-y-0.5">
                    {group.items.map((item, i) => (
                      <li key={i} className="text-[9px] text-slate-400 flex items-center gap-1">
                        <span className="w-1 h-1 rounded-full bg-slate-500 shrink-0" />
                        <span className="truncate">{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </div>
      )
    },

    // =========================================================================
    // SLIDE 4: EWS — CÔNG THỨC & MÔ HÌNH (BÁO CÁO 02B)
    // =========================================================================
    {
      title: "Báo Cáo 02B: EWS Pipeline — Công Thức Risk Score & Mô Hình",
      subtitle: "Công thức Risk Score động, Ensemble 5-Fold averaging, SHAP giải trình & Phân loại rủi ro",
      type: "report_02b",
      content: (
        <div className="w-full text-left flex flex-col justify-center h-full max-w-5xl mx-auto space-y-2.5">
          {/* CÔNG THỨC RISK SCORE */}
          <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-1.5">
                <BarChart2 className="w-3.5 h-3.5 text-[#8c763e] dark:text-[#c2ae78]" />
                <h3 className={`text-xs font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Công Thức Risk Score (Trọng Số Động Softmax)</h3>
              </div>
              <span className={`text-[8.5px] font-mono px-2 py-0.5 rounded-full font-bold ${isDark ? "bg-[#2d6a4f]/20 text-[#52b788]" : "bg-[#f0faf4] text-[#2d6a4f]"}`}>CatBoost output → Risk Aggregation</span>
            </div>
            <div className={`p-2 rounded-lg border font-mono text-[10px] mb-1.5 ${isDark ? "bg-[#070e1a] border-[#263750] text-[#52b788]" : "bg-[#f0faf4] border-[#cbdcd0] text-[#2d6a4f]"}`}>
              <strong className="text-[11px]">Risk Score = (1 − β) × Σ(w<sub>k</sub> × S<sub>k</sub>) + β × max(S)</strong>
              <div className="text-[9px] text-slate-400 mt-0.5 font-normal leading-relaxed">
                • w<sub>k</sub> = base<sub>k</sub>·e<sup>α<sub>k</sub>·S<sub>k</sub></sup> / Σ base<sub>j</sub>·e<sup>α<sub>j</sub>·S<sub>j</sub></sup> (trọng số động Softmax) · S<sub>k</sub>: điểm rủi ro CatBoost · β: worst bias (0.0)
              </div>
            </div>
            <p className={`text-[9.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
              <strong className="text-rose-500">Ý nghĩa:</strong> Yếu tố nguy hiểm tự động tăng trọng số (ví dụ HS nghỉ nhiều → tỷ trọng chuyên cần nâng từ 0.15 lên 0.42).
            </p>
          </div>

          {/* ENSEMBLE + SHAP */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <h4 className={`text-[10.5px] font-bold mb-1 flex items-center gap-1.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>
                <Layers className="w-3.5 h-3.5 text-purple-500" /> Ensemble 5-Fold Averaging
              </h4>
              <div className={`p-1.5 rounded-lg border font-mono text-[9.5px] mb-1 ${isDark ? "bg-[#070e1a] border-[#263750] text-purple-400" : "bg-[#faf8f5] border-[#ebdcb0] text-purple-700"}`}>
                risk_score = (p<sub>1</sub> + p<sub>2</sub> + ... + p<sub>5</sub>) / 5
              </div>
              <p className={`text-[9.5px] ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                Huấn luyện 5 CatBoost folds trên 5 tập phân chia dữ liệu khác nhau, lấy trung bình xác suất nhằm triệt tiêu phương sai.
              </p>
            </div>
            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <h4 className={`text-[10.5px] font-bold mb-1 flex items-center gap-1.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>
                <Activity className="w-3.5 h-3.5 text-[#2d6a4f] dark:text-[#52b788]" /> SHAP Local Drivers
              </h4>
              <p className={`text-[9.5px] mb-1 ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                <code>compute_shap_drivers()</code> bóc tách Top các căn nguyên trực tiếp làm tăng hoặc giảm điểm rủi ro của từng em.
              </p>
              <div className="flex flex-wrap gap-1">
                <span className="text-[8.5px] font-mono px-1.5 py-0.2 rounded-full bg-rose-950/20 border border-rose-800/40 text-rose-400">score_slope: -0.32</span>
                <span className="text-[8.5px] font-mono px-1.5 py-0.2 rounded-full bg-rose-950/20 border border-rose-800/40 text-rose-400">absent_rate: +0.28</span>
                <span className="text-[8.5px] font-mono px-1.5 py-0.2 rounded-full bg-amber-950/20 border border-amber-800/40 text-amber-400">lms_drop: -0.15</span>
              </div>
            </div>
          </div>

          {/* PHÂN LOẠI 4 MỨC RỦI RO */}
          <div className={`p-2 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div className={`p-1.5 rounded-lg border text-center ${isDark ? "bg-[#2d6a4f]/10 border-[#52b788]/30" : "bg-[#f0faf4] border-[#cbdcd0]"}`}>
                <div className={`text-xs font-black ${isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}`}>LOW</div>
                <div className="text-[10px] font-bold text-slate-400">{'<'} 0.3 · An toàn</div>
              </div>
              <div className={`p-1.5 rounded-lg border text-center ${isDark ? "bg-sky-950/20 border-sky-800/40" : "bg-sky-50 border-sky-200"}`}>
                <div className="text-xs font-black text-sky-500">MODERATE</div>
                <div className="text-[10px] font-bold text-slate-400">0.3 – 0.5 · Theo dõi</div>
              </div>
              <div className={`p-1.5 rounded-lg border text-center ${isDark ? "bg-amber-950/20 border-amber-800/40" : "bg-amber-50 border-amber-200"}`}>
                <div className="text-xs font-black text-amber-500">HIGH</div>
                <div className="text-[10px] font-bold text-slate-400">0.5 – 0.7 · Cảnh báo</div>
              </div>
              <div className={`p-1.5 rounded-lg border text-center ${isDark ? "bg-rose-950/20 border-rose-800/40" : "bg-rose-50 border-rose-200"}`}>
                <div className="text-xs font-black text-rose-500">CRITICAL</div>
                <div className="text-[10px] font-bold text-slate-400">≥ 0.7 · Can thiệp gấp</div>
              </div>
            </div>
          </div>
        </div>
      )
    },

    // =========================================================================
    // SLIDE 5: CURRICULUM + RAG (BÁO CÁO 03)
    // =========================================================================
    {
      title: "Báo Cáo 03: Curriculum Ingestion & RAG Knowledge",
      subtitle: "VLM 2 lượt quét tìm TOC → khớp trang → node phẳng → chunking → Qdrant → RAG trong phân tách đề thi",
      type: "report_03",
      content: (
        <div className="w-full text-left flex flex-col justify-center h-full max-w-5xl mx-auto space-y-2.5">
          {/* HÀNG 1: MỤC ĐÍCH + RAG PHÂN TÁCH ĐỀ THI */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div className="flex items-center gap-1.5 mb-1">
                <BookOpen className="w-3.5 h-3.5 text-[#2d6a4f] dark:text-[#52b788]" />
                <h3 className={`text-xs font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Mục Đích Ingestion</h3>
              </div>
              <p className={`text-[10px] leading-relaxed ${isDark ? "text-slate-300" : "text-[#4a5568]"}`}>
                Biến PDF SGK thành <strong>cây tri thức có cấu trúc</strong> (Chương → Bài). Xuất node phẳng <code>curriculum_units</code>, chunk text và embedding vector vào <strong>Qdrant</strong> để phục vụ truy vấn RAG có trích dẫn.
              </p>
            </div>

            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div className="flex items-center gap-1.5 mb-1">
                <Search className="w-3.5 h-3.5 text-[#8c763e] dark:text-[#c2ae78]" />
                <h3 className={`text-xs font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>RAG Trong Phân Tách Đề Thi</h3>
              </div>
              <p className={`text-[10px] leading-relaxed ${isDark ? "text-slate-300" : "text-[#4a5568]"}`}>
                Đề thi được trích xuất competency → Embed tìm chunks SGK tương ứng trong Qdrant → Map chính xác <code>unit_id</code> làm trọng số cho dự báo Pass/Fail (Semantic Lookup chuẩn xác).
              </p>
            </div>
          </div>

          {/* HÀNG 2: LƯỢT A + LƯỢT B */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <Search className="w-3.5 h-3.5 text-blue-500" />
                  <h3 className={`text-xs font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Lượt A: VLM Tìm Mục Lục (TOC)</h3>
                </div>
                <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded-full font-bold ${isDark ? "bg-blue-950/30 text-blue-400" : "bg-blue-50 text-blue-600"}`}>~15 trang đầu</span>
              </div>
              <p className={`text-[9.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                PyMuPDF crop ảnh trang → Qwen-VL phân tích cấu trúc cây Chương→Bài → Xuất JSON danh sách NEO cố định.
              </p>
            </div>

            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-[#2d6a4f] dark:text-[#52b788]" />
                  <h3 className={`text-xs font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Lượt B: Phân Loại & Khớp Từng Trang</h3>
                </div>
                <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded-full font-bold ${isDark ? "bg-[#2d6a4f]/20 text-[#52b788]" : "bg-[#f0faf4] text-[#2d6a4f]"}`}>NEO constraint</span>
              </div>
              <p className={`text-[9.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                VLM duyệt từng trang, khóa cứng vào danh sách NEO id có sẵn. <strong>Constrained decoding:</strong> chống bịa bài học 100%.
              </p>
            </div>
          </div>

          {/* HÀNG 3: NODE PHẲNG + CHUNKING QDRANT */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div className="flex items-center gap-1.5 mb-1">
                <GitBranch className="w-3 h-3 text-purple-500" />
                <h4 className={`text-[10.5px] font-bold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Node Phẳng (curriculum_units)</h4>
              </div>
              <p className={`text-[9.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                Sinh tóm tắt, từ khóa, mục con. Bảng quan hệ phẳng: <code>subject_id | chapter | lesson | summary | keywords</code>.
              </p>
            </div>
            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div className="flex items-center gap-1.5 mb-1">
                <Database className="w-3 h-3 text-amber-500" />
                <h4 className={`text-[10.5px] font-bold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Data Chunking → Qdrant</h4>
              </div>
              <p className={`text-[9.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                Chunks 256–512 tokens kèm metadata mục SGK. Embedding vector → Qdrant phục vụ tìm kiếm ngữ nghĩa siêu tốc.
              </p>
            </div>
          </div>
        </div>
      )
    },

    // =========================================================================
    // SLIDE 6: PASS/FAIL 04A — PHÂN TÁCH ĐỀ THI (BÁO CÁO 04A)
    // =========================================================================
    {
      title: "Báo Cáo 04A: Pass/Fail — Phân Tách Đề Thi & Định Vị Bài Học",
      subtitle: "Upload đề → LLM tách câu → Qdrant semantic lookup → map competency→unit_id",
      type: "report_04a",
      content: (
        <div className="w-full text-left flex flex-col justify-center h-full max-w-5xl mx-auto space-y-2.5">
          {/* MỤC ĐÍCH */}
          <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="flex items-center gap-1.5 mb-1">
              <TrendingUp className="w-3.5 h-3.5 text-[#2d6a4f] dark:text-[#52b788]" />
              <h3 className={`text-xs font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Mục Đích Phân Tách Đề</h3>
            </div>
            <p className={`text-[10px] leading-relaxed ${isDark ? "text-slate-300" : "text-[#4a5568]"}`}>
              Biến file PDF/DOCX đề thi thành Ma trận Trọng số từng bài học <code>competency → unit_id</code> để tính điểm dự báo theo chuẩn kiến thức thực tế.
            </p>
          </div>

          {/* QUY TRÌNH 3 BƯỚC */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <div className={`p-2 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div className="flex items-center gap-1.5 mb-1">
                <FileText className="w-3.5 h-3.5 text-blue-500" />
                <h4 className={`text-[10.5px] font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>B1: Tách Đề Thành Câu</h4>
              </div>
              <p className={`text-[9.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                VLM / Layout Detector tách từng câu hỏi, cắt hình minh họa, đọc điểm số từng câu.
              </p>
            </div>

            <div className={`p-2 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div className="flex items-center gap-1.5 mb-1">
                <Search className="w-3.5 h-3.5 text-purple-500" />
                <h4 className={`text-[10.5px] font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>B2: Semantic Lookup</h4>
              </div>
              <p className={`text-[9.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                Embedding câu hỏi → Tìm chunks SGK trong pgvector/Qdrant → Lấy bằng chứng thực tế.
              </p>
            </div>

            <div className={`p-2 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div className="flex items-center gap-1.5 mb-1">
                <GitBranch className="w-3.5 h-3.5 text-amber-500" />
                <h4 className={`text-[10.5px] font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>B3: Map & Tính CDI Đề</h4>
              </div>
              <p className={`text-[9.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                Phân rã bài con (Σw = 100%). Tính <strong>CDI = Σ(Bloom<sub>i</sub> × w<sub>i</sub>) / (6 × Σw<sub>i</sub>)</strong>.
              </p>
            </div>
          </div>

          {/* CÔNG THỨC CDI & SO SÁNH PHƯƠNG PHÁP */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-2.5">
            {/* BOX CÔNG THỨC CDI */}
            <div className={`md:col-span-6 p-2.5 rounded-xl border flex flex-col justify-between ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <Target className="w-3.5 h-3.5 text-[#8c763e] dark:text-[#c2ae78]" />
                    <h4 className={`text-[10.5px] font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Cách Tính Chỉ Số Độ Khó Đề (CDI)</h4>
                  </div>
                  <span className={`text-[8px] font-mono px-1.5 py-0.2 rounded font-bold ${isDark ? "bg-[#2d6a4f]/20 text-[#52b788]" : "bg-[#f0faf4] text-[#2d6a4f]"}`}>Bloom Scale 1..6</span>
                </div>
                <div className={`p-1.5 rounded-lg border font-mono text-[9.5px] mb-1 ${isDark ? "bg-[#070e1a] border-[#263750] text-[#52b788]" : "bg-[#f0faf4] border-[#cbdcd0] text-[#2d6a4f]"}`}>
                  <strong>CDI = Σ(Bloom<sub>i</sub> × w<sub>i</sub>) / (6 × Σw<sub>i</sub>) ∈ [0.0, 1.0]</strong>
                </div>
                <p className={`text-[8.5px] leading-relaxed ${isDark ? "text-slate-300" : "text-[#4a5568]"}`}>
                  • <strong>Bloom<sub>i</sub> (1..6):</strong> Bậc nhận thức câu <em>i</em> (1: Biết, 2: Hiểu, 3: Vận dụng, 4–6: Vận dụng cao).<br />
                  • <strong>w<sub>i</sub>:</strong> Điểm số câu <em>i</em> · <strong>Σw<sub>i</sub>:</strong> Tổng điểm toàn bài (dùng tính TB gia quyền theo điểm câu).<br />
                  • <strong>Số 6:</strong> Bậc Bloom tối đa để chuẩn hóa CDI về thang [0, 1]. (CDI=0.50: Đề chuẩn Bộ GD&ĐT).
                </p>
              </div>
            </div>

            {/* SO SÁNH LLM VS SEMANTIC LOOKUP */}
            <div className={`md:col-span-6 p-2.5 rounded-xl border flex flex-col justify-between ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div>
                <div className="flex items-center gap-1.5 mb-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#2d6a4f] dark:text-[#52b788]" />
                  <h4 className={`text-[10.5px] font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Định Vị Bằng Semantic Lookup</h4>
                </div>
                <p className={`text-[9px] leading-relaxed mb-1 ${isDark ? "text-slate-300" : "text-[#4a5568]"}`}>
                  <strong>Tại sao không hỏi LLM trực tiếp?</strong> LLM dễ ảo giác tự bịa tên bài không có trong SGK.
                </p>
                <p className={`text-[8.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                  👉 Vector hóa câu hỏi → So khớp top-1 chunk SGK chuẩn trong pgvector/Qdrant → Đảm bảo 100% mã <code>unit_id</code> thuộc SGK thực tế.
                </p>
              </div>
            </div>
          </div>
        </div>
      )
    },

    // =========================================================================
    // SLIDE 7: PASS/FAIL 04B — CÔNG THỨC DỰ BÁO (BÁO CÁO 04B)
    // =========================================================================
    {
      title: "Báo Cáo 04B: Pass/Fail Forecast — Công Thức Dự Báo & Phân Loại",
      subtitle: "Weighted Ability × CDI Adjustment, 4 tầng fallback, verdict PASS/BORDER/FAIL & Weak Units",
      type: "report_04b",
      content: (
        <div className="w-full text-left flex flex-col justify-center h-full max-w-5xl mx-auto space-y-2.5">
          {/* HÀNG 1: CÔNG THỨC & CƠ SỞ KHẢO THÍ HỌC */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-2.5">
            <div className={`md:col-span-6 p-2.5 rounded-xl border flex flex-col justify-between ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <TrendingUp className="w-3.5 h-3.5 text-[#2d6a4f] dark:text-[#52b788]" />
                    <h3 className={`text-xs font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>1. Weighted Ability (Test Blueprint)</h3>
                  </div>
                  <span className={`text-[8px] font-mono px-1.5 py-0.2 rounded font-bold ${isDark ? "bg-emerald-950/30 text-[#52b788]" : "bg-emerald-50 text-emerald-700"}`}>Domain Sampling</span>
                </div>
                <div className={`p-1.5 rounded-lg border font-mono text-[9.5px] mb-1 ${isDark ? "bg-[#070e1a] border-[#263750] text-[#52b788]" : "bg-[#f0faf4] border-[#cbdcd0] text-[#2d6a4f]"}`}>
                  <strong>Weighted Ability = Σ(w<sub>u</sub> × Ability<sub>u</sub>) / Σ(w<sub>u</sub>)</strong>
                </div>
                <p className={`text-[9px] leading-relaxed ${isDark ? "text-slate-300" : "text-[#4a5568]"}`}>
                  <strong>Cơ sở Khảo thí:</strong> Mô hình <em>Composite Score</em> chuẩn dựa trên lý thuyết <em>Test Blueprint</em> (Ma trận đặc tả) & <em>Domain Sampling</em>: khi đề thi tập trung vào mục tiêu nào thì năng lực tổng hợp phải được ánh xạ theo tỷ trọng của mục tiêu đó.
                </p>
              </div>
            </div>

            <div className={`md:col-span-6 p-2.5 rounded-xl border flex flex-col justify-between ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <BarChart2 className="w-3.5 h-3.5 text-[#8c763e] dark:text-[#c2ae78]" />
                    <h3 className={`text-xs font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>2. CDI Adjustment (Empirical Heuristic)</h3>
                  </div>
                  <span className={`text-[8px] font-mono px-1.5 py-0.2 rounded font-bold ${isDark ? "bg-amber-950/30 text-[#c2ae78]" : "bg-amber-50 text-amber-700"}`}>Cold-Start Forecast</span>
                </div>
                <div className={`p-1.5 rounded-lg border font-mono text-[9.5px] mb-1 ${isDark ? "bg-[#070e1a] border-[#263750] text-[#52b788]" : "bg-[#f0faf4] border-[#cbdcd0] text-[#2d6a4f]"}`}>
                  <strong>CDI Adj = 1.0 + (0.5 − CDI) × 0.5</strong> <span className="text-[8.5px] text-slate-400 font-normal">→ CDI từ Slide 04A (Scale ±25%)</span>
                </div>
                <p className={`text-[9px] leading-relaxed ${isDark ? "text-slate-300" : "text-[#4a5568]"}`}>
                  <strong>Tại sao dùng Heuristic thay IRT?</strong> IRT cần $\ge 200$ HS làm bài trước để calibrate tham số. Đề thi cuối kỳ là đề mới bảo mật, chưa có tương tác học sinh $\implies$ Dùng độ khó Bloom tiên nghiệm để dự báo sớm trước 2-3 tuần.
                </p>
              </div>
            </div>
          </div>

          {/* HÀNG 2: 4 TẦNG FALLBACK NĂNG LỰC */}
          <div className={`p-2 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <h3 className={`text-[10px] font-bold mb-1 ${isDark ? "text-white" : "text-[#0f1e36]"}`}>4 Tầng Fallback Xác Định Năng Lực Học Sinh (Ability<sub>u</sub>)</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div className={`p-1.5 rounded-lg border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className={`text-[9px] font-bold ${isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}`}>Tầng 1: Có LMS</span>
                <div className="text-[8.5px] text-slate-400">Ability = Raw × 10</div>
              </div>
              <div className={`p-1.5 rounded-lg border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-blue-500">Tầng 2: Thiếu bài</span>
                <div className="text-[8.5px] text-slate-400">Lấy TB Chương</div>
              </div>
              <div className={`p-1.5 rounded-lg border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className={`text-[9px] font-bold ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"}`}>Tầng 3: Thiếu chương</span>
                <div className="text-[8.5px] text-slate-400">Lấy TB toàn Môn</div>
              </div>
              <div className={`p-1.5 rounded-lg border ${isDark ? "bg-rose-950/20 border-rose-800/40" : "bg-rose-50 border-rose-200"}`}>
                <span className="text-[9px] font-bold text-rose-500">Tầng 4: Không LMS</span>
                <div className="text-[8.5px] text-slate-400">→ INSUFFICIENT</div>
              </div>
            </div>
          </div>

          {/* HÀNG 3: PHÂN LOẠI VERDICT + WEAK UNITS */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-2.5">
            <div className={`md:col-span-7 p-2 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <h4 className={`text-[10px] font-bold mb-1 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Phân Loại Kết Luận (Predicted = Weighted Ability × CDI Adj)</h4>
              <div className="grid grid-cols-4 gap-1.5">
                <div className={`text-center p-1 rounded-lg border ${isDark ? "bg-[#2d6a4f]/10 border-[#52b788]/30" : "bg-[#f0faf4] border-[#cbdcd0]"}`}>
                  <span className={`text-xs font-black ${isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}`}>PASS</span>
                  <div className="text-[9px] text-slate-400">≥ 5.5</div>
                </div>
                <div className={`text-center p-1 rounded-lg border ${isDark ? "bg-amber-950/20 border-amber-800/40" : "bg-amber-50 border-amber-200"}`}>
                  <span className="text-xs font-black text-amber-500">BORDER</span>
                  <div className="text-[9px] text-slate-400">4.5–5.4</div>
                </div>
                <div className={`text-center p-1 rounded-lg border ${isDark ? "bg-rose-950/20 border-rose-800/40" : "bg-rose-50 border-rose-200"}`}>
                  <span className="text-xs font-black text-rose-500">FAIL</span>
                  <div className="text-[9px] text-slate-400">{'<'} 4.5</div>
                </div>
                <div className={`text-center p-1 rounded-lg border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-white border-[#dcd7cc]"}`}>
                  <span className="text-xs font-black text-slate-400">INSUF</span>
                  <div className="text-[9px] text-slate-400">Chưa đủ</div>
                </div>
              </div>
            </div>

            <div className={`md:col-span-5 p-2 rounded-xl border flex flex-col justify-center ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <h4 className={`text-[10px] font-bold mb-0.5 flex items-center gap-1.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>
                <AlertTriangle className="w-3.5 h-3.5 text-[#8c763e] dark:text-[#c2ae78]" /> Weak Units
              </h4>
              <p className={`text-[9px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                <code>compute_weak_units()</code> bóc tách Top 2 bài yếu nhất gây mất điểm trong đề để GV lên kế hoạch phụ đạo mục tiêu.
              </p>
            </div>
          </div>
        </div>
      )
    },

    // =========================================================================
    // SLIDE 8: CHẨN ĐOÁN LỖ HỔNG KIẾN THỨC (BÁO CÁO 05)
    // =========================================================================
    {
      title: "Báo Cáo 05: Chẩn Đoán Lỗ Hổng Kiến Thức & Năng Lực Học Sinh",
      subtitle: "Đánh Giá Năng Lực Theo Cây Tri Thức, Thang Đo Bloom, Đối Soát Đa Nguồn (LMS vs Exam) & Majority Rule",
      type: "report_05",
      content: (
        <div className="w-full text-left flex flex-col justify-center h-full max-w-5xl mx-auto space-y-2.5">
          {/* MỤC ĐÍCH */}
          <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="flex items-center gap-1.5 mb-1">
              <Activity className="w-3.5 h-3.5 text-[#2d6a4f] dark:text-[#52b788]" />
              <h3 className={`text-xs font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Mục Đích Chẩn Đoán Lỗ Hổng</h3>
            </div>
            <p className={`text-[10px] leading-relaxed ${isDark ? "text-slate-300" : "text-[#4a5568]"}`}>
              Phát hiện <strong>lỗ hổng kiến thức</strong> từng học sinh ở cấp bài học bằng cách đối soát đa nguồn: năng lực LMS (Item Mastery × Bloom Factor) đối chiếu với điểm thi thật. Kết quả xuất Roster chi tiết.
            </p>
          </div>

          {/* QUY TRÌNH 4 BƯỚC */}
          <div className={`p-2 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div className={`p-1.5 rounded-lg border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-[#2d6a4f] dark:text-[#52b788]">Bước 1: Item Mastery</span>
                <div className="text-[8.5px] text-slate-400 mt-0.5">Bloom Breadth × Depth Factor</div>
              </div>
              <div className={`p-1.5 rounded-lg border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-blue-500">Bước 2: Cross-Val</span>
                <div className="text-[8.5px] text-slate-400 mt-0.5">Δ = LMS − Exam (|Δ| ≤ 30%)</div>
              </div>
              <div className={`p-1.5 rounded-lg border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-purple-500">Bước 3: Majority Rule</span>
                <div className="text-[8.5px] text-slate-400 mt-0.5">Gộp trạng thái toàn khóa học</div>
              </div>
              <div className={`p-1.5 rounded-lg border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-[#8c763e] dark:text-[#c2ae78]">Bước 4: Roster</span>
                <div className="text-[8.5px] text-slate-400 mt-0.5">Xuất bảng chẩn đoán & Drawer</div>
              </div>
            </div>
          </div>

          {/* CÔNG THỨC + 4 LOẠI KẾT LUẬN */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <h4 className={`text-[10.5px] font-bold mb-1 flex items-center gap-1.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>
                <BarChart2 className="w-3.5 h-3.5 text-[#8c763e] dark:text-[#c2ae78]" /> Công Thức Năng Lực
              </h4>
              <div className={`p-1.5 rounded-lg border font-mono text-[9.5px] ${isDark ? "bg-[#070e1a] border-[#263750] text-[#52b788]" : "bg-[#f0faf4] border-[#cbdcd0] text-[#2d6a4f]"}`}>
                Mastery<sub>bài</sub> = (đúng / tổng) × BreadthRatio × (1 + DepthFactor)
              </div>
              <p className={`text-[9px] mt-1 ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                BreadthRatio: tỷ lệ bao phủ bậc Bloom. DepthFactor: thưởng câu Vận dụng cao. HS đúng hết NB+TH nhưng thiếu VD cao → Mastery phản ánh đúng thực chất.
              </p>
            </div>

            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
              <h4 className={`text-[10.5px] font-bold mb-1 flex items-center gap-1.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>
                <CheckCircle2 className="w-3.5 h-3.5 text-[#2d6a4f] dark:text-[#52b788]" /> 4 Loại Kết Luận Đối Soát
              </h4>
              <div className="grid grid-cols-2 gap-1.5">
                <div className={`p-1 rounded-lg border ${isDark ? "bg-[#2d6a4f]/10 border-[#52b788]/30" : "bg-[#f0faf4] border-[#cbdcd0]"}`}>
                  <div className={`text-[11px] font-black ${isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}`}>OK</div>
                  <div className="text-[8px] text-slate-400">|Δ| ≤ 30% · Chuẩn xác</div>
                </div>
                <div className={`p-1 rounded-lg border ${isDark ? "bg-sky-950/20 border-sky-800/40" : "bg-sky-50 border-sky-200"}`}>
                  <div className="text-[11px] font-black text-sky-600">LMS Vượt</div>
                  <div className="text-[8px] text-slate-400">LMS ≥ 9.5, thi {'<'} 4.5</div>
                </div>
                <div className={`p-1 rounded-lg border ${isDark ? "bg-amber-950/20 border-amber-800/40" : "bg-amber-50 border-amber-200"}`}>
                  <div className={`text-[11px] font-black ${isDark ? "text-amber-400" : "text-amber-600"}`}>Ít LMS</div>
                  <div className="text-[8px] text-slate-400">N {'<'} 5 câu · Luyện ít</div>
                </div>
                <div className={`p-1 rounded-lg border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-white border-[#dcd7cc]"}`}>
                  <div className="text-[11px] font-black text-purple-600">Chỉ Thi</div>
                  <div className="text-[8px] text-slate-400">LMS = 0% · Ước lượng thi</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )
    }
  ];

  return (
    <div className={`fixed inset-0 z-[9999] flex flex-col justify-between animate-fade-in overflow-hidden font-sans ${isDark ? "bg-[#070e1a] text-[#faf9f6]" : "bg-[#f5f1e6] text-[#0f1e36]"}`}>
      {/* Background Gradients */}
      {isDark ? (
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(194,174,120,0.06),transparent_50%),radial-gradient(circle_at_bottom_left,rgba(194,174,120,0.04),transparent_50%)] pointer-events-none" />
      ) : (
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(140,118,62,0.03),transparent_50%),radial-gradient(circle_at_bottom_left,rgba(140,118,62,0.02),transparent_50%)] pointer-events-none" />
      )}

      {/* Header bar */}
      <header className={`px-6 lg:px-8 py-2.5 h-14 border-b backdrop-blur-md flex items-center justify-between shrink-0 relative z-10 ${isDark ? "border-[#263750]/60 bg-[#070e1a]/60" : "border-[#dcd7cc]/80 bg-[#f5f1e6]/80"}`}>
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-white font-bold text-sm shadow-md ${isDark ? "bg-[#2d6a4f]" : "bg-[#0f1e36]"}`}>
            <Brain className="w-4 h-4 text-[#52b788]" />
          </div>
          <div>
            <h2 className={`text-xs md:text-sm font-extrabold tracking-tight line-clamp-1 ${isDark ? "text-white" : "text-[#0f1e36]"}`}>{slides[currentSlide].title}</h2>
            <p className="text-[10px] text-slate-500 dark:text-slate-400 line-clamp-1">{slides[currentSlide].subtitle}</p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <span className={`text-[10.5px] font-mono px-3 py-1 rounded-full font-bold ${isDark ? "bg-[#0a1120] text-[#c2ae78] border border-[#263750]" : "bg-white text-[#8c763e] border border-[#dcd7cc]"}`}>
            {currentSlide + 1} / {slides.length}
          </span>
          <button
            type="button"
            onClick={onClose}
            className={`p-1.5 rounded-lg border transition active:scale-95 ${isDark ? "bg-[#070e1a] border-[#263750] text-[#c2ae78] hover:bg-slate-900 hover:text-white" : "bg-white border-[#dcd7cc] text-[#8c763e] hover:bg-slate-100 hover:text-slate-900"}`}
            title="Đóng chế độ thuyết trình (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Main Content Area — Compact & Perfectly fitted in 1 screen */}
      <main className="flex-1 flex items-center justify-center relative z-10 overflow-hidden px-4 lg:px-6 py-2">
        <div className={`w-full h-full mx-auto flex items-center justify-center ${slides[currentSlide].type === "report_01" ? "max-w-none px-0" : "max-w-5xl"}`}>
          {slides[currentSlide].content}
        </div>
      </main>

      {/* Footer - Compact Height (h-12) */}
      <footer className={`px-6 lg:px-8 py-2 h-12 border-t backdrop-blur-md flex items-center justify-between shrink-0 relative z-10 ${isDark ? "border-[#263750]/60 bg-[#070e1a]/60" : "border-[#dcd7cc]/80 bg-[#f5f1e6]/80"}`}>
        {/* Progress indicators - slim bars */}
        <div className="flex items-center gap-1.5">
          {slides.map((_, index) => (
            <button
              key={index}
              type="button"
              onClick={() => setCurrentSlide(index)}
              className={`h-1 rounded-full transition-all duration-300 ${index === currentSlide
                ? "w-6 bg-[#8c763e] dark:bg-[#c2ae78]"
                : isDark ? "w-1.5 bg-[#263750] hover:bg-slate-700" : "w-1.5 bg-[#dcd7cc] hover:bg-slate-300"
                }`}
              title={`Chuyển tới slide ${index + 1}`}
            />
          ))}
        </div>

        {/* Slide Counter */}
        <div className={`text-[9.5px] font-bold uppercase tracking-wider ${isDark ? "text-slate-500" : "text-[#8c763e]"}`}>
          {currentSlide + 1} / {slides.length}
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={currentSlide === 0}
            onClick={() => setCurrentSlide((prev) => Math.max(prev - 1, 0))}
            className={`p-1.5 rounded-lg border transition disabled:opacity-30 disabled:pointer-events-none active:scale-95 ${isDark ? "bg-[#070e1a] border-[#263750] text-[#c2ae78] hover:bg-slate-900 hover:text-white" : "bg-white border-[#dcd7cc] text-[#8c763e] hover:bg-slate-100 hover:text-slate-900"}`}
            title="Slide trước (Arrow Left)"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <button
            type="button"
            disabled={currentSlide === slides.length - 1}
            onClick={() => setCurrentSlide((prev) => Math.min(prev + 1, slides.length - 1))}
            className={`px-3 py-1 rounded-lg font-bold text-xs transition shadow-xs disabled:opacity-30 disabled:pointer-events-none active:scale-95 flex items-center gap-1 ${isDark
              ? "bg-[#c2ae78] text-[#070e1a] hover:bg-[#a38a4d]"
              : "bg-[#0f1e36] text-[#faf9f6] hover:bg-[#8c763e]"
              }`}
            title="Slide tiếp theo (Space / Arrow Right)"
          >
            <span>Tiếp theo</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>

          <button
            type="button"
            onClick={onClose}
            className={`p-1.5 rounded-lg border transition active:scale-95 ${isDark ? "bg-[#070e1a] border-[#263750] text-[#c2ae78] hover:bg-slate-900 hover:text-white" : "bg-white border-[#dcd7cc] text-[#8c763e] hover:bg-slate-100 hover:text-slate-900"}`}
            title="Đóng chế độ thuyết trình (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </footer>
    </div>
  );
}