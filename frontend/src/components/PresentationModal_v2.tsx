"use client";

import React, { useState, useEffect } from "react";
import {
  X, ChevronLeft, ChevronRight, Cpu, BarChart2, ShieldAlert, Sparkles, BookOpen,
  Database, FileText, Clock, AlertTriangle, MessageSquare, Video, ArrowRight,
  Maximize2, Minimize2, Play, Pause, ArrowDown, Mic, Target, Tag, Settings, CheckCircle2,
  GraduationCap, Shield, Star, Rocket, Layout, Calendar, Layers, Network, Lock,
  RefreshCw, BarChart3, Search, Activity, GitBranch, Terminal, Zap, TrendingUp, Laptop, Brain
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
      desc: "Người dùng hỏi tự nhiên qua Chatbot. Supervisor Orchestrator tiếp nhận, phân tích intent và điều phối 4 Sub-Agents chuyên biệt (Data & SQL, Stat, Knowledge RAG, Report) truy xuất CSDL PostgreSQL và Qdrant để trả về câu trả lời streaming SSE kèm kiểm định LLM Judge.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["input_chat", "super", "data_agent", "stat_agent", "knowledge_agent", "report_agent", "school_db", "qdrant_db", "chat_response"],
      activeLines: ["chat-super", "super-data", "super-stat", "stat-know", "super-report", "data-db", "know-qdrant", "db-chat"],
      labels: [
        { text: "1. Hỏi Chatbot", x: 195, y: 70 },
        { text: "2. Điều phối 4 Agents", x: 340, y: 130 },
        { text: "3. Streaming SSE", x: 535, y: 70 }
      ]
    },
    {
      id: 1,
      title: "2. EWS Pipeline (CatBoost ML & SHAP)",
      desc: "Admin/BGH kích hoạt EWS Job. Worker chạy FIFO, trích xuất 22 Features từ 4 nguồn DWH (Điểm, LMS, Chuyên cần, Hạnh kiểm) bằng Materialized SQL trong < 5s, suy luận qua 5-Fold CatBoost Ensemble, tính SHAP drivers giải trình nguyên nhân và lưu bảng cảnh báo rủi ro.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["input_ews", "ews_engine", "dwh_db", "school_db", "ews_output"],
      activeLines: ["ews-engine", "dwh-engine", "engine-db", "engine-ews-out"],
      labels: [
        { text: "1. Kích hoạt EWS Job", x: 195, y: 130 },
        { text: "2. 22 Features DWH", x: 340, y: 220 },
        { text: "3. Cảnh báo & SHAP", x: 535, y: 130 }
      ]
    },
    {
      id: 2,
      title: "3. Curriculum Ingest & RAG SGK (VLM)",
      desc: "Admin tải PDF/DOCX SGK. Pipeline VLM 2 lượt quét chống bịa (Lượt A lấy NEO mục lục 15 trang đầu, Lượt B duyệt từng trang và bắt buộc neo vào bài học), trích xuất tóm tắt/từ khóa và embedding vector chunks vào Qdrant để Knowledge Agent tra cứu có trích dẫn.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["input_pdf_curriculum", "vlm_pipeline", "qdrant_db", "school_db", "curriculum_output"],
      activeLines: ["curriculum-vlm", "vlm-qdrant", "vlm-db", "qdrant-curriculum-out"],
      labels: [
        { text: "1. Tải PDF SGK", x: 195, y: 190 },
        { text: "2. VLM 2 Lượt Quét", x: 340, y: 260 },
        { text: "3. Vector Chunks", x: 535, y: 190 }
      ]
    },
    {
      id: 3,
      title: "4. Pass/Fail Forecast (Math & CDI)",
      desc: "Hệ thống lấy ma trận đề thi cuối kỳ (trọng số bài học) và năng lực LMS học sinh, giải quyết qua chuỗi 4 tầng fallback, áp dụng hệ số điều chỉnh độ khó đề thi CDI thuần toán học để dự báo điểm số chính xác và cảnh báo học sinh nguy cơ trượt thi.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["input_exam_forecast", "forecast_engine", "school_db", "forecast_output"],
      activeLines: ["forecast-in-engine", "db-forecast-engine", "engine-forecast-out"],
      labels: [
        { text: "1. Đề thi & LMS", x: 195, y: 250 },
        { text: "2. CDI Adjustment", x: 340, y: 300 },
        { text: "3. Điểm thi PASS/FAIL", x: 535, y: 250 }
      ]
    },
    {
      id: 4,
      title: "5. TEVI (Độ Khó & Công Bằng Điểm)",
      desc: "Đối soát chéo giữa độ khó thiết kế đề thi (CDI từ ma trận Bloom) và độ khó thực nghiệm (EDI từ phổ điểm học sinh thật). Tự động phát hiện đề ra quá khó (HAMMER), lạm phát điểm (INFLATED) và các dấu hiệu bất thường như nghi ưu ái hoặc chèn ép điểm số.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["input_exam_validity", "tevi_engine", "school_db", "tevi_output"],
      activeLines: ["tevi-in-engine", "db-tevi-engine", "engine-tevi-out"],
      labels: [
        { text: "1. Sổ điểm & Đề thi", x: 195, y: 310 },
        { text: "2. EDI vs CDI", x: 340, y: 345 },
        { text: "3. Cảnh báo BGH", x: 535, y: 310 }
      ]
    },
    {
      id: 5,
      title: "6. Chẩn Đoán Lỗ Hổng Kiến Thức",
      desc: "Tổng hợp toàn bộ câu trả lời LMS của học sinh, nhân hệ số bao phủ Bloom (Breadth Ratio) & Vận dụng cao (Depth Factor), đối soát chéo với điểm thi thật (Δ = LMS - Exam), áp dụng Majority Rule gộp trạng thái cấp học sinh và xuất bảng Roster lỗ hổng chi tiết.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["input_knowledge_gaps", "gap_engine", "school_db", "gap_output"],
      activeLines: ["gap-in-engine", "db-gap-engine", "engine-gap-out"],
      labels: [
        { text: "1. LMS Items & Thi", x: 195, y: 370 },
        { text: "2. Bloom & Cross-Val", x: 340, y: 390 },
        { text: "3. Roster Lỗ Hổng", x: 535, y: 370 }
      ]
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

            {/* Labels on SVG */}
            {current.labels.map((lbl, idx) => (
              <g key={idx} className="transition-all duration-300">
                <rect
                  x={lbl.x - 32}
                  y={lbl.y - 10}
                  width="85"
                  height="16"
                  rx="4"
                  fill={isDark ? "#070e1a" : "#ffffff"}
                  stroke={current.stroke}
                  strokeWidth="1"
                  className="shadow-sm"
                />
                <text
                  x={lbl.x + 10}
                  y={lbl.y + 1}
                  fill={isDark ? "#faf9f6" : "#0f1e36"}
                  fontSize="6.5"
                  fontWeight="bold"
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {lbl.text}
                </text>
              </g>
            ))}

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
                  <div className="text-[7px] font-mono text-slate-500 truncate">SSE Streaming & LLM Judge</div>
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
// MAIN PRESENTATION MODAL V2 COMPONENT
// =============================================================================
export default function PresentationModalV2({ isOpen, onClose, theme }: PresentationModalProps) {
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
    // SLIDE 1: TIÊU ĐỀ DỰ ÁN
    // =========================================================================
    {
      title: "Hệ Thống AI Phân Tích Học Tập & Quản Trị Giáo Dục Toàn Trường",
      subtitle: "Giải pháp chuyển đổi số toàn diện dựa trên dữ liệu dành cho Ban Giám Hiệu & Giáo Viên",
      type: "cover",
      content: (
        <div className="flex flex-col items-center justify-center text-center max-w-4xl mx-auto space-y-6 animate-fade-in py-6">
          <div className="relative">
            <div className={`absolute inset-0 ${isDark ? "bg-[#c2ae78]/10" : "bg-[#8c763e]/5"} blur-3xl rounded-full scale-150 animate-pulse`} />
            <div className={`relative w-20 h-20 rounded-2xl ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-white border-[#dcd7cc]"} flex items-center justify-center shadow-lg border shrink-0`}>
              <Brain className="w-12 h-12 text-[#2d6a4f] dark:text-[#52b788] animate-pulse" />
            </div>
          </div>

          <div className="space-y-3">
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${isDark ? "bg-[#c2ae78]/10 text-[#c2ae78] border-[#c2ae78]/25" : "bg-white border-[#dcd7cc] text-[#8c763e]"} border`}>
              <Sparkles className="w-3 h-3 text-[#8c763e] dark:text-[#c2ae78]" /> Nền tảng EdTech AI Sư Phạm Thế Hệ Mới
            </span>
            <h1 className={`text-2xl md:text-4xl font-extrabold tracking-tight leading-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
              Hệ Thống Trợ Lý AI Phân Tích Kết Quả Học Tập & <br />
              <span className={isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}>
                Quản Trị Chất Lượng Giáo Dục Toàn Trường
              </span>
            </h1>
            <p className={`text-xs md:text-sm max-w-2xl mx-auto leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
              Báo cáo kiến trúc 7 trục công nghệ chuyên sâu: Multi-Agent Chatbot, EWS CatBoost ML, VLM Curriculum Ingest, Pass/Fail Forecast, TEVI Validity, 3-Layer RBAC & Chẩn đoán Lỗ hổng Kiến thức.
            </p>
          </div>

          {/* 7 Tech Pillars Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2.5 w-full pt-2 text-left">
            {[
              { id: "01", name: "Multi-Agent Chat", icon: MessageSquare },
              { id: "02", name: "EWS CatBoost ML", icon: ShieldAlert },
              { id: "03", name: "Curriculum RAG", icon: BookOpen },
              { id: "04", name: "Pass/Fail Forecast", icon: TrendingUp },
              { id: "05", name: "TEVI Exam Validity", icon: Target },
              { id: "06", name: "3-Layer RBAC", icon: Lock },
              { id: "07", name: "Knowledge Gaps", icon: Activity },
            ].map((p, idx) => (
              <div key={idx} className={`p-3 rounded-xl border transition-all ${isDark ? "bg-[#070e1a]/80 border-[#263750] hover:border-[#52b788]" : "bg-white border-[#dcd7cc] shadow-xs hover:border-[#2d6a4f]"}`}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[9px] font-mono font-bold text-slate-400">#{p.id}</span>
                  <p.icon className="w-3.5 h-3.5 text-[#2d6a4f] dark:text-[#52b788]" />
                </div>
                <h4 className={`text-[11px] font-bold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>{p.name}</h4>
              </div>
            ))}
          </div>

          <div className="pt-2 text-xs text-slate-400 flex items-center gap-2">
            <span>Dùng phím</span>
            <kbd className="px-2 py-0.5 rounded bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-[10px] font-mono">←</kbd>
            <kbd className="px-2 py-0.5 rounded bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-[10px] font-mono">→</kbd>
            <span>hoặc click nút điều hướng để bắt đầu duyệt các Báo cáo</span>
          </div>
        </div>
      )
    },

    // =========================================================================
    // SLIDE 2: BÁO CÁO 01 — MULTI-AGENT CHAT ARCHITECTURE (SƠ ĐỒ V1 SVG PIPELINE)
    // =========================================================================
    {
      title: "Báo Cáo 01: Multi-Agent Chat & Sơ Đồ Toàn Cảnh Hệ Thống",
      subtitle: "LangGraph StateGraph, Supervisor Router, 4 Sub-Agents Chuyên Biệt & Cô Lập Dữ Liệu Trường Học",
      type: "report_01",
      content: <SolutionDiagram isDark={isDark} />
    },

    // =========================================================================
    // SLIDE 3: BÁO CÁO 02 — EWS PIPELINE (EARLY WARNING SYSTEM)
    // =========================================================================
    {
      title: "Báo Cáo 02: EWS Pipeline — Cảnh Báo Nguy Cơ Rớt Môn",
      subtitle: "Mô Hình Machine Learning CatBoost (5-Fold Ensemble), 22 Features DWH & SHAP Local Drivers",
      type: "report_02",
      content: (
        <div className="w-full text-left space-y-5">
          {/* Top visual flow */}
          <div className={`p-4 rounded-2xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-[#8c763e] dark:text-[#c2ae78]" />
                <h3 className={`text-xs md:text-sm font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Luồng Xử Lý Pipeline EWS (DB-Backed FIFO Queue)</h3>
              </div>
              <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-bold ${isDark ? "bg-[#2d6a4f]/20 text-[#52b788]" : "bg-[#f0faf4] text-[#2d6a4f]"}`}>CatBoost GBDT + SHAP Explainer</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-2.5">
              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-[#8c763e] dark:text-[#c2ae78]">1. DB FIFO QUEUE</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Job Worker (5p Timeout)</h4>
                <p className="text-[10px] text-slate-400 mt-1">Chạy 1 job/lần, tự phục hồi khi crash, tracking tiến độ 0-100%.</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-blue-500">2. MATERIALIZED SQL</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>22 Features Extract</h4>
                <p className="text-[10px] text-slate-400 mt-1">Trích xuất 22 đặc trưng từ 4 nguồn DWH (Điểm, LMS, Chuyên cần, Hạnh kiểm) trong &lt; 5s.</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-[#2d6a4f] dark:text-[#52b788]">3. ENSEMBLE INFERENCE</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>5 CatBoost Folds</h4>
                <p className="text-[10px] text-slate-400 mt-1">Trung bình cộng xác suất từ 5 fold mô hình GBDT, triệt tiêu phương sai dự báo.</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-purple-500">4. SHAP & PERSIST</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Giải Trình Nguyên Nhân</h4>
                <p className="text-[10px] text-slate-400 mt-1">Tính SHAP drivers cho từng học sinh, UPSERT kết quả vào CSDL.</p>
              </div>
            </div>
          </div>

          {/* 22 Features Matrix Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2.5">
            <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc]"}`}>
              <span className={`text-[9px] font-bold uppercase tracking-wider ${isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}`}>Điểm Số (9 Features)</span>
              <ul className="mt-1.5 space-y-1 text-[10px] text-slate-400">
                <li>• Điểm TB sớm / muộn</li>
                <li>• Độ dốc xu hướng (Slope)</li>
                <li>• Độ biến thiên & Mức sụt giảm</li>
                <li>• Điểm hệ số cao gần nhất</li>
              </ul>
            </div>

            <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc]"}`}>
              <span className={`text-[9px] font-bold uppercase tracking-wider ${isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}`}>LMS (5 Features)</span>
              <ul className="mt-1.5 space-y-1 text-[10px] text-slate-400">
                <li>• Điểm TB bài tập LMS</li>
                <li>• Độ lệch LMS vs Sổ điểm</li>
                <li>• Tỷ lệ nộp bài lũy kế</li>
                <li>• Tỷ lệ nộp bài 4 tuần gần nhất</li>
              </ul>
            </div>

            <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc]"}`}>
              <span className={`text-[9px] font-bold uppercase tracking-wider ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"}`}>Chuyên Cần (4 Features)</span>
              <ul className="mt-1.5 space-y-1 text-[10px] text-slate-400">
                <li>• Tỷ lệ nghỉ học chung</li>
                <li>• Tỷ lệ nghỉ không phép</li>
                <li>• Số ngày nghỉ có phép</li>
                <li>• Tổng số lần đi muộn</li>
              </ul>
            </div>

            <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc]"}`}>
              <span className="text-[9px] font-bold text-rose-500 uppercase tracking-wider">Hạnh Kiểm & Ngữ Cảnh</span>
              <ul className="mt-1.5 space-y-1 text-[10px] text-slate-400">
                <li>• Tổng điểm trừ hành vi</li>
                <li>• Số lần tái phạm & kỷ luật nặng</li>
                <li>• Phân loại môn & Khối lớp</li>
              </ul>
            </div>
          </div>
        </div>
      )
    },

    // =========================================================================
    // SLIDE 4: BÁO CÁO 03 — CURRICULUM INGESTION & RAG KNOWLEDGE
    // =========================================================================
    {
      title: "Báo Cáo 03: Curriculum Ingestion & RAG Knowledge",
      subtitle: "Pipeline VLM 2 Lượt Quét Chống Bịa, Chuỗi Chuẩn Hóa Tri Thức & Vector Store Qdrant",
      type: "report_03",
      content: (
        <div className="w-full text-left space-y-5">
          <div className={`p-4 rounded-2xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-[#2d6a4f] dark:text-[#52b788]" />
                <h3 className={`text-xs md:text-sm font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Quy Trình Nạp Sách Giáo Khoa (VLM 2 Lượt Quét Chống Bịa)</h3>
              </div>
              <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-bold ${isDark ? "bg-[#2d6a4f]/20 text-[#52b788]" : "bg-[#f0faf4] text-[#2d6a4f]"}`}>Qwen-VL + Qdrant Vector Search</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-5 gap-2.5">
              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-slate-400">BƯỚC 1</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Upload PDF/DOCX</h4>
                <p className="text-[10px] text-slate-400 mt-1">Admin chọn môn/lớp/kỳ, đẩy vào `CurriculumIngestJob` (timeout 60p).</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#2d6a4f]/10 border-[#52b788]/30" : "bg-[#f0faf4] border-[#cbdcd0]"}`}>
                <span className="text-[9px] font-bold text-[#2d6a4f] dark:text-[#52b788]">BƯỚC 2: LƯỢT A</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Scan Mục Lục (NEO)</h4>
                <p className="text-[10px] text-slate-400 mt-1">VLM quét 15 trang đầu lấy cây Chương → Bài học chuẩn làm danh sách NEO cố định.</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#2d6a4f]/10 border-[#52b788]/30" : "bg-[#f0faf4] border-[#cbdcd0]"}`}>
                <span className="text-[9px] font-bold text-[#2d6a4f] dark:text-[#52b788]">BƯỚC 3: LƯỢT B</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Phân Loại Trang</h4>
                <p className="text-[10px] text-slate-400 mt-1">VLM duyệt từng trang nội dung, BẮT BUỘC chỉ gán vào các NEO đã có, chống bịa 100%.</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-slate-400">BƯỚC 4</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Làm Giàu Tri Thức</h4>
                <p className="text-[10px] text-slate-400 mt-1">VLM sinh tóm tắt, từ khóa chuyên môn và mục con theo từng bài học.</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-[#8c763e] dark:text-[#c2ae78]">BƯỚC 5</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Qdrant Vectorize</h4>
                <p className="text-[10px] text-slate-400 mt-1">Embedding và lưu chunks vào Qdrant, sẵn sàng cho Knowledge RAG Agent tra cứu.</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            <div className={`p-3.5 rounded-xl border ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc]"}`}>
              <h4 className={`text-[11px] font-bold mb-1.5 flex items-center gap-1.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>
                <Shield className="w-3.5 h-3.5 text-[#2d6a4f] dark:text-[#52b788]" /> Cơ Chế Chống Bịa (Hallucination-Proof)
              </h4>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Không dựa vào số trang in vật lý (vốn hay sai lệch giữa các bản in PDF). Hệ thống neo vị trí theo tên bài học chính thức từ mục lục, đảm bảo tính chuẩn xác dù file PDF bị cắt xén.
              </p>
            </div>

            <div className={`p-3.5 rounded-xl border ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc]"}`}>
              <h4 className={`text-[11px] font-bold mb-1.5 flex items-center gap-1.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>
                <Search className="w-3.5 h-3.5 text-[#8c763e] dark:text-[#c2ae78]" /> RAG Knowledge Agent Grounding
              </h4>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Trong Chatbot, `knowledge_agent` bắt buộc phải truy vấn vector Qdrant trước khi trả lời. Mọi câu trả lời kiến thức đều phải trích dẫn rõ: Tên sách, Chương, Bài học và Đoạn văn nguồn.
              </p>
            </div>
          </div>
        </div>
      )
    },

    // =========================================================================
    // SLIDE 5: BÁO CÁO 04 — PASS/FAIL FORECAST (DỰ ĐOÁN ĐỖ/TRƯỢT)
    // =========================================================================
    {
      title: "Báo Cáo 04: Pass/Fail Forecast — Dự Đoán Kết Quả Thi",
      subtitle: "Thuật Toán Dự Báo Điểm Thi Thuần Toán Học (Deterministic), 4 Tầng Fallback & Điều Chỉnh Độ Khó CDI",
      type: "report_04",
      content: (
        <div className="w-full text-left space-y-5">
          <div className={`p-4 rounded-2xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-[#2d6a4f] dark:text-[#52b788]" />
                <h3 className={`text-xs md:text-sm font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Công Thức Dự Báo Điểm Thi Cuối Kỳ Chuẩn Xác</h3>
              </div>
              <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-bold ${isDark ? "bg-[#2d6a4f]/20 text-[#52b788]" : "bg-[#f0faf4] text-[#2d6a4f]"}`}>Deterministic Math Formula</span>
            </div>

            <div className={`p-3 rounded-xl border mb-3 font-mono text-[11px] ${isDark ? "bg-[#070e1a] border-[#263750] text-[#52b788]" : "bg-[#f0faf4] border-[#cbdcd0] text-[#2d6a4f]"}`}>
              <div className="font-bold text-xs">Predicted Score = Weighted Ability Avg × CDI Difficulty Adjustment</div>
              <div className="text-[10px] text-slate-400 mt-1 font-normal">
                • Weighted Ability = Σ(weight_u × ability_u) / Σ(weight_u)<br />
                • CDI Adjustment = 1.0 + (0.5 - CDI) × 0.5 &nbsp;&nbsp;(CDI=0.0 → 1.25 [Đề dễ]; CDI=0.5 → 1.0; CDI=1.0 → 0.75 [Đề khó])
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-2.5">
              <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <strong className={`text-[11px] block ${isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}`}>Tầng 1: Bài Học LMS</strong>
                <span className="text-[10px] text-slate-400">Có điểm LMS bài đó → Ability = Raw Mastery × 10</span>
              </div>
              <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <strong className="text-blue-500 text-[11px] block">Tầng 2: TB Chương</strong>
                <span className="text-[10px] text-slate-400">Khuyết bài con → Dùng điểm trung bình của Chương</span>
              </div>
              <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <strong className={`text-[11px] block ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"}`}>Tầng 3: TB Môn Học</strong>
                <span className="text-[10px] text-slate-400">Khuyết cả chương → Dùng điểm trung bình toàn Môn</span>
              </div>
              <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <strong className="text-rose-500 text-[11px] block">Tầng 4: Insufficient</strong>
                <span className="text-[10px] text-slate-400">Học sinh không có LMS → Báo Chưa đủ dữ liệu</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 text-center">
            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#2d6a4f]/10 border-[#52b788]/30" : "bg-[#f0faf4] border-[#cbdcd0]"}`}>
              <h4 className={`text-[11px] font-bold ${isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}`}>PASS (Đạt)</h4>
              <p className={`text-base font-black mt-0.5 ${isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}`}>≥ 5.5 Điểm</p>
              <span className="text-[9px] text-slate-400">An toàn vượt qua kỳ thi</span>
            </div>
            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#8c763e]/10 border-[#c2ae78]/30" : "bg-[#faf6e8] border-[#ebdcb0]"}`}>
              <h4 className={`text-[11px] font-bold ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"}`}>BORDERLINE</h4>
              <p className={`text-base font-black mt-0.5 ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"}`}>4.5 – 5.4 Điểm</p>
              <span className="text-[9px] text-slate-400">Cần ôn tập gấp top 2 bài yếu</span>
            </div>
            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-rose-950/20 border-rose-800/40" : "bg-[#fdf2f2] border-rose-200"}`}>
              <h4 className="text-[11px] font-bold text-rose-600">FAIL (Trượt)</h4>
              <p className="text-base font-black text-rose-600 mt-0.5">&lt; 4.5 Điểm</p>
              <span className="text-[9px] text-slate-400">Báo động đỏ cần phụ đạo</span>
            </div>
            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-white border-[#dcd7cc]"}`}>
              <h4 className="text-[11px] font-bold text-slate-400">INSUFFICIENT</h4>
              <p className="text-base font-black text-slate-400 mt-0.5">Chưa Đủ Dữ Liệu</p>
              <span className="text-[9px] text-slate-400">Chưa nộp bài tập LMS</span>
            </div>
          </div>
        </div>
      )
    },

    // =========================================================================
    // SLIDE 6: BÁO CÁO 05 — EXAM VALIDITY & TEVI (TAM GIÁC HÓA ĐỘ KHÓ)
    // =========================================================================
    {
      title: "Báo Cáo 05: TEVI — Tam Giác Hóa Độ Khó & Công Bằng Điểm Số",
      subtitle: "Đối Chiếu Độ Khó Thực Nghiệm (EDI) vs Độ Khó Thiết Kế (CDI) & Phát Hiện Cảnh Báo Sư Phạm",
      type: "report_05",
      content: (
        <div className="w-full text-left space-y-5">
          <div className={`p-4 rounded-2xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-[#8c763e] dark:text-[#c2ae78]" />
                <h3 className={`text-xs md:text-sm font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Lý Thuyết Tam Giác Hóa TEVI (Triangulation of Exam Validity)</h3>
              </div>
              <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-bold ${isDark ? "bg-[#2d6a4f]/20 text-[#52b788]" : "bg-[#f0faf4] text-[#2d6a4f]"}`}>Materialized View v_exam_validity</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <h4 className="text-[11px] font-bold text-blue-500">EDI (Empirical Difficulty)</h4>
                <p className="text-xs font-mono mt-0.5 font-bold">EDI = 1.0 − (Mean / 10.0)</p>
                <p className="text-[10px] text-slate-400 mt-1.5">Đo độ khó thực nghiệm dựa trên phổ điểm làm bài thi thật của học sinh (0 = Dễ, 1 = Khó).</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <h4 className={`text-[11px] font-bold ${isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}`}>CDI (Content Difficulty)</h4>
                <p className="text-xs font-mono mt-0.5 font-bold">CDI = Phân tích Ma trận Bloom</p>
                <p className="text-[10px] text-slate-400 mt-1.5">Độ khó thiết kế nội dung đề thi dựa trên tỷ lệ câu hỏi 4 mức độ nhận thức.</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <h4 className={`text-[11px] font-bold ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"}`}>Divergence (Độ Phân Kỳ)</h4>
                <p className="text-xs font-mono mt-0.5 font-bold">Divergence = CDI − EDI</p>
                <p className="text-[10px] text-slate-400 mt-1.5">Đo sự bất thường: Đề ra quá khó (`HAMMER`) hay điểm số bị lạm phát (`INFLATED`).</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            <div className={`p-3.5 rounded-xl border ${isDark ? "bg-rose-950/15 border-rose-800/30" : "bg-[#fdf2f2] border-rose-200"}`}>
              <h4 className="text-[11px] font-bold text-rose-600 flex items-center gap-1.5 mb-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Cảnh Báo: Nghi Ưu Ái Điểm (SUSPECT_FAVORITISM)
              </h4>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Điểm Thường xuyên (TX) trên lớp rất cao (≥ 8.0) dù đề TX có CDI khó, nhưng khi thi Giữa kỳ/Cuối kỳ tập trung có giám thị thì điểm lại rất thấp (≤ 5.0).
              </p>
            </div>

            <div className={`p-3.5 rounded-xl border ${isDark ? "bg-[#8c763e]/10 border-[#c2ae78]/30" : "bg-[#faf6e8] border-[#ebdcb0]"}`}>
              <h4 className={`text-[11px] font-bold flex items-center gap-1.5 mb-1 ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"}`}>
                <AlertTriangle className="w-3.5 h-3.5" /> Cảnh Báo: Nghi Bị Chèn Ép (SUSPECT_SUPPRESSION)
              </h4>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Học sinh có điểm Thường xuyên rất thấp (≤ 5.0), nhưng bài thi định kỳ tập trung độc lập lại đạt điểm cao xuất sắc (≥ 8.0).
              </p>
            </div>
          </div>
        </div>
      )
    },

    // =========================================================================
    // SLIDE 7: BÁO CÁO 06 — 3-LAYER RBAC & TENANT AUTHORIZATION
    // =========================================================================
    {
      title: "Báo Cáo 06: RBAC & Tầng Bảo Mật 3 Lớp Xuyên Suốt",
      subtitle: "7 Vai Trò Người Dùng, Phân Quyền Giảng Dạy Động, Row-Level Security (RLS) & SQL Guardrail",
      type: "report_06",
      content: (
        <div className="w-full text-left space-y-5">
          <div className={`p-4 rounded-2xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Lock className="w-4 h-4 text-rose-500" />
                <h3 className={`text-xs md:text-sm font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Kiến Trúc Bảo Mật 3 Lớp Bảo Vệ (Security in Depth)</h3>
              </div>
              <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-rose-500/10 text-rose-500 font-bold">JWT + Role Check + RLS + SQL Guardrail</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-rose-500">LỚP 1: AUTHENTICATION</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>JWT Token Pair</h4>
                <p className="text-[10px] text-slate-400 mt-1">Access Token (30p) + Refresh Token (7 ngày) lưu hash chống đánh cắp trong DB.</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-amber-500">LỚP 2: AUTHORIZATION</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Role Guard Check</h4>
                <p className="text-[10px] text-slate-400 mt-1">Dependency `require_roles()` chặn 403 ngay tại API Gateway nếu không đúng vai trò.</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-[#2d6a4f] dark:text-[#52b788]">LỚP 3: DATA ISOLATION</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>RLS & SQL Guardrail</h4>
                <p className="text-[10px] text-slate-400 mt-1">Hàm `accessible_score_filter()` tự động chèn WHERE clause theo phân công và school_id.</p>
              </div>
            </div>
          </div>

          {/* 7 Roles Matrix Summary */}
          <div className={`p-3.5 rounded-xl border overflow-x-auto ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc]"}`}>
            <table className="w-full text-left text-[11px]">
              <thead>
                <tr className={`border-b text-slate-400 font-semibold ${isDark ? "border-[#263750]" : "border-[#dcd7cc]"}`}>
                  <th className="pb-1.5">Vai trò (7 Roles)</th>
                  <th className="pb-1.5">Xem Điểm</th>
                  <th className="pb-1.5">Ghi Điểm</th>
                  <th className="pb-1.5">Tạo/Duyệt Câu Hỏi</th>
                  <th className="pb-1.5">Phạm vi Chatbot AI</th>
                </tr>
              </thead>
              <tbody className={`divide-y text-slate-300 ${isDark ? "divide-slate-800/60" : "divide-slate-100 text-[#0f1e36]"}`}>
                <tr>
                  <td className="py-1.5 font-bold text-rose-500">ADMIN</td>
                  <td>Toàn trường</td>
                  <td>Toàn quyền</td>
                  <td>Tạo & Duyệt</td>
                  <td>Toàn trường</td>
                </tr>
                <tr>
                  <td className="py-1.5 font-bold text-amber-500">PRINCIPAL (Hiệu Trưởng)</td>
                  <td>Toàn trường</td>
                  <td>Read-only</td>
                  <td>Không</td>
                  <td>Toàn trường</td>
                </tr>
                <tr>
                  <td className="py-1.5 font-bold text-blue-500">SUBJECT_HEAD (Trưởng Bộ Môn)</td>
                  <td>Môn phụ trách</td>
                  <td>Read-only môn</td>
                  <td>Duyệt câu hỏi môn</td>
                  <td>Môn phụ trách</td>
                </tr>
                <tr>
                  <td className="py-1.5 font-bold text-[#2d6a4f] dark:text-[#52b788]">SUBJECT_TEACHER (GV Bộ Môn)</td>
                  <td>Môn/lớp được phân công</td>
                  <td>Ghi điểm môn/lớp</td>
                  <td>Tạo câu hỏi Draft</td>
                  <td>Lớp/môn đang dạy</td>
                </tr>
                <tr>
                  <td className="py-1.5 font-bold text-purple-500">HOMEROOM (GV Chủ Nhiệm)</td>
                  <td>Toàn bộ lớp chủ nhiệm</td>
                  <td>Nhập hạnh kiểm/NX</td>
                  <td>Không</td>
                  <td>Lớp chủ nhiệm</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )
    },

    // =========================================================================
    // SLIDE 8: BÁO CÁO 07 — CHẨN ĐOÁN LỖ HỔNG KIẾN THỨC & ITEM MASTERY
    // =========================================================================
    {
      title: "Báo Cáo 07: Chẩn Đoán Lỗ Hổng Kiến Thức & Năng Lực Học Sinh",
      subtitle: "Đánh Giá Năng Lực Theo Cây Tri Thức, Thang Đo Bloom, Đối Soát Đa Nguồn (LMS vs Exam) & Majority Rule",
      type: "report_07",
      content: (
        <div className="w-full text-left space-y-5">
          <div className={`p-4 rounded-2xl border ${isDark ? "bg-[#070e1a]/80 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-[#2d6a4f] dark:text-[#52b788]" />
                <h3 className={`text-xs md:text-sm font-bold ${isDark ? "text-white" : "text-[#0f1e36]"}`}>Quy Trình Chẩn Đoán Lỗ Hổng Kiến Thức Đa Nguồn</h3>
              </div>
              <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-bold ${isDark ? "bg-[#2d6a4f]/20 text-[#52b788]" : "bg-[#f0faf4] text-[#2d6a4f]"}`}>Item Mastery + Bloom Depth + Cross-Validation</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-2.5">
              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-[#2d6a4f] dark:text-[#52b788]">1. RAW ITEM MASTERY</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>LMS & Bloom Factor</h4>
                <p className="text-[10px] text-slate-400 mt-1">Đếm số câu đúng/tổng câu, nhân với hệ số bao phủ bậc Bloom (Breadth Ratio) & Vận dụng cao (Depth Factor).</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-blue-500">2. CROSS-VALIDATION</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Đối Soát Điểm Thi</h4>
                <p className="text-[10px] text-slate-400 mt-1">So sánh độ lệch Δ = LMS − Exam. Nếu khớp: `OK`. Nếu LMS cao vọt nhưng thi thấp: `LMS_EXCEEDS_EXAM`.</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-purple-500">3. MAJORITY RULE</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Gộp Cấp Học Sinh</h4>
                <p className="text-[10px] text-slate-400 mt-1">Áp dụng Majority Vote xác định nguồn bằng chứng và Majority Rule gộp trạng thái cho 32 bài học.</p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-[#faf8f5] border-[#ebdcb0]"}`}>
                <span className="text-[9px] font-bold text-[#8c763e] dark:text-[#c2ae78]">4. ROSTER & DRAWER</span>
                <h4 className={`text-[11px] font-bold mt-0.5 ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Báo Cáo Giáo Viên</h4>
                <p className="text-[10px] text-slate-400 mt-1">Chỉ rõ học sinh hổng bài nào, tỷ lệ thành thạo &lt; 60%, độ tin cậy % và nguyên nhân chi tiết.</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#2d6a4f]/10 border-[#52b788]/30" : "bg-[#f0faf4] border-[#cbdcd0]"}`}>
              <span className={`inline-flex items-center gap-1 text-[11px] font-bold ${isDark ? "text-[#52b788]" : "text-[#2d6a4f]"}`}>
                <CheckCircle2 className="w-3.5 h-3.5" /> Đồng thuận (OK)
              </span>
              <p className="text-[10px] text-slate-400 mt-1">LMS và Điểm thi khớp nhau (|Δ| ≤ 30%). Dữ liệu chuẩn xác tuyệt đối.</p>
            </div>

            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-sky-950/20 border-sky-800/40" : "bg-sky-50 border-sky-200"}`}>
              <span className="inline-flex items-center gap-1 text-[11px] font-bold text-sky-600">
                <TrendingUp className="w-3.5 h-3.5" /> LMS Vượt Trội
              </span>
              <p className="text-[10px] text-slate-400 mt-1">LMS rất cao (≥ 9.5) nhưng thi thật thấp (&lt; 4.5). Cảnh báo nghi nhờ người làm hộ.</p>
            </div>

            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#8c763e]/10 border-[#c2ae78]/30" : "bg-[#faf6e8] border-[#ebdcb0]"}`}>
              <span className={`inline-flex items-center gap-1 text-[11px] font-bold ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"}`}>
                <Laptop className="w-3.5 h-3.5" /> Ít Luyện Tập LMS
              </span>
              <p className="text-[10px] text-slate-400 mt-1">Học sinh bỏ bài làm LMS ở đa số các bài học (N &lt; 5 câu).</p>
            </div>

            <div className={`p-2.5 rounded-xl border ${isDark ? "bg-[#070e1a] border-[#263750]" : "bg-white border-[#dcd7cc]"}`}>
              <span className="inline-flex items-center gap-1 text-[11px] font-bold text-purple-600">
                <GraduationCap className="w-3.5 h-3.5" /> Chỉ từ Bài Thi
              </span>
              <p className="text-[10px] text-slate-400 mt-1">Học sinh không làm bài LMS (0%), ước lượng gián tiếp từ bài thi.</p>
            </div>
          </div>
        </div>
      )
    }
  ];

  return (
    <div className={`fixed inset-0 z-[9999] flex flex-col justify-between select-none animate-fade-in overflow-hidden font-sans ${isDark ? "bg-[#070e1a] text-[#faf9f6]" : "bg-[#f5f1e6] text-[#0f1e36]"}`}>
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

      {/* Main Content Area */}
      <main className="flex-1 flex items-center justify-center relative z-10 overflow-y-auto px-4 lg:px-8 py-3 lg:py-5">
        <div className={`w-full h-full mx-auto flex items-center justify-center ${slides[currentSlide].type === "report_01" ? "max-w-none px-0" : "max-w-6xl"}`}>
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
