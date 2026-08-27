"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  X, ChevronLeft, ChevronRight, Cpu, BarChart2, ShieldAlert, Sparkles, BookOpen,
  Database, FileText, Clock, AlertTriangle, MessageSquare, Video, ArrowRight,
  Maximize2, Minimize2, Play, Pause, ArrowDown, Mic, Target, Tag, Settings, CheckCircle2,
  GraduationCap, Shield, Star, Rocket, Layout, Calendar
} from "lucide-react";

interface PresentationModalProps {
  isOpen: boolean;
  onClose: () => void;
  theme: string;
}

function SolutionDiagram({ isDark }: { isDark: boolean }) {
  const [activeFlow, setActiveFlow] = useState<number>(0);
  const nodeInactiveClass = isDark
    ? "opacity-30 bg-[#070e1a]/60 border-[#263750] text-[#4a5568] hover:opacity-80"
    : "opacity-35 bg-white/60 border-[#dcd7cc] text-[#4a5568] hover:opacity-80";

  const nodeActiveClass = isDark
    ? "bg-[#2d6a4f]/20 border-[#52b788] text-[#52b788] shadow-[0_0_10px_rgba(82,183,136,0.25)]"
    : "bg-[#f0faf4] border-[#2d6a4f] text-[#2d6a4f] shadow-[0_0_10px_rgba(45,106,79,0.2)]";

  const flows = [
    {
      id: 0,
      title: "1. Chatbot Đa Nhiệm (Multi-Agent)",
      desc: "Người dùng hỏi tự nhiên qua Chatbot. Supervisor Orchestrator tiếp nhận, điều phối Data & SQL Agent truy vấn, Stat Agent tính toán, Report Agent soạn thảo và lưu Database để trả về báo cáo.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["user_query", "super", "sql_data", "stat", "knowledge", "report_agent_inner", "exam_eval_agent", "school_db", "chat_response"],
      activeLines: ["db-super-box", "box-db", "box-chat"],
      labels: [
        { text: "1. Nhập câu hỏi", x: 195, y: 70 },
        { text: "2. Điều phối đa tác nhân", x: 340, y: 148 },
        { text: "3. Trả câu trả lời", x: 530, y: 70 }
      ]
    },
    {
      id: 1,
      title: "2.1. Chatbot Thẩm Định Đề (Multi-Agent)",
      desc: "Người dùng nộp đề kiểm tra qua Chatbot. Supervisor gọi Knowledge Agent đối soát RAG Sách giáo khoa, Exam Agent chấm điểm độ khó thiết kế (CDI), lưu Database và trả kết quả chatbot.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["user_upload_exam", "super", "knowledge", "exam_eval_agent", "school_db", "exam_difficulty_res"],
      activeLines: ["upload-super", "super-knowledge", "knowledge-exam", "exam-db", "db-difficulty"],
      labels: [
        { text: "1. Nộp đề qua Chatbot", x: 202, y: 150 },
        { text: "2. RAG đối soát SGK", x: 405, y: 118 },
        { text: "3. Đánh giá độ khó", x: 405, y: 178 },
        { text: "4. Lưu trữ", x: 470, y: 185 },
        { text: "5. Trả kết quả", x: 565, y: 175 }
      ]
    },
    {
      id: 2,
      title: "2.2. Liên Kết Đề & Điểm (Single Agent)",
      desc: "Giáo viên liên kết đề thi vào cột điểm trên bảng điểm UI. Hệ thống dùng Single Agent (LLM + RAG Sách giáo khoa) kiểm chéo độ lệch CDI vs EDI, tự động lưu Database và gắn nhãn cảnh báo độ phân kỳ cho BGH.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["teacher_link", "single_llm_rag", "school_db", "bgh_warning"],
      activeLines: ["link-single", "single-db", "db-warning"],
      labels: [
        { text: "1. Thầy cô liên kết đề", x: 202, y: 210 },
        { text: "2. LLM+RAG kiểm chéo", x: 342, y: 248 },
        { text: "3. Cảnh báo BGH", x: 565, y: 145 }
      ]
    },
    {
      id: 3,
      title: "3. Xuất Báo Cáo Mẫu (Single Report Agent)",
      desc: "Người dùng chọn mẫu báo cáo. Report Agent chạy độc lập (không qua Supervisor) tự tìm dữ liệu trong Database, điền mẫu và viết nhận xét/đề xuất để xuất file Word/PDF.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["select_template", "single_report_agent", "school_db", "formatted_report"],
      activeLines: ["template-report", "single-report-db", "single-report-out"],
      labels: [
        { text: "1. Chọn mẫu", x: 300, y: 275 },
        { text: "2. Tự tìm dữ liệu", x: 510, y: 245 },
        { text: "3. Xuất file Word/PDF", x: 587, y: 276 }
      ]
    },
    {
      id: 4,
      title: "4. Đánh giá Tiết học qua Camera (Pipeline)",
      desc: "Nộp file MP3 hoặc trích xuất camera. Whisper dịch thoại bài giảng sang transcript, LLM chuyên sư phạm đánh giá điểm chất lượng/tương tác, lưu Database (sau này Multi-Agent có thể truy xuất).",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["camera_audio", "whisper_stt", "llm_pedagogical", "school_db", "bgh_classroom_report"],
      activeLines: ["cam-whisper", "whisper-llm", "llm-db", "db-classroom"],
      labels: [
        { text: "1. Ghi bài giảng", x: 202, y: 330 },
        { text: "2. Whisper dịch thoại", x: 280, y: 298 },
        { text: "3. LLM đánh giá", x: 405, y: 298 },
        { text: "4. Lưu trữ", x: 485, y: 295 },
        { text: "5. Xem báo cáo", x: 565, y: 240 }
      ]
    },
    {
      id: 5,
      title: "5. Tạo Ma Trận Đề (Single Agent)",
      desc: "Giáo viên chọn chương trình giảng dạy. Single Agent (LLM + RAG Sách giáo khoa) phân tích mục tiêu bài học, tự động thiết kế ma trận kiểm tra và đề xuất khung đề thi lưu vào Database.",
      color: "text-[#2d6a4f] dark:text-[#52b788]",
      stroke: isDark ? "#52b788" : "#2d6a4f",
      activeNodes: ["syllabus_input", "matrix_agent", "school_db", "matrix_output"],
      activeLines: ["syllabus-single", "matrix-db", "db-matrix"],
      labels: [
        { text: "1. Chọn CT dạy", x: 195, y: 375 },
        { text: "2. Tạo ma trận", x: 342, y: 353 },
        { text: "3. Xuất ma trận", x: 565, y: 270 }
      ]
    }
  ];

  const current = flows[activeFlow];

  const isNodeActive = (nodeId: string) => current.activeNodes.includes(nodeId);
  const isLineActive = (lineId: string) => current.activeLines.includes(lineId);

  const allPaths = [
    { id: "db-super-box", d: "M 180 77.5 L 210 77.5" },
    { id: "super-sql", d: "M 335 90 L 350 90" },
    { id: "sql-stat", d: "M 405 110 C 405 125, 280 115, 280 130" },
    { id: "stat-report", d: "M 280 170 L 280 190" },
    { id: "report-db", d: "M 335 210 C 400 210, 430 150, 490 150" },
    { id: "box-db", d: "M 470 145 L 490 145" },
    { id: "box-chat", d: "M 470 77.5 L 590 77.5" },
    { id: "link-single", d: "M 180 207 C 200 207, 210 280, 225 280" },
    { id: "single-db", d: "M 342 260 C 342 150, 440 150, 490 150" },
    { id: "db-warning", d: "M 550 150 C 560 150, 570 207, 590 207" },
    { id: "upload-super", d: "M 180 142 C 200 142, 210 90, 225 90" },
    { id: "super-knowledge", d: "M 335 90 C 340 90, 345 150, 350 150" },
    { id: "knowledge-exam", d: "M 405 170 L 405 190" },
    { id: "exam-db", d: "M 460 210 C 470 210, 480 150, 490 150" },
    { id: "db-difficulty", d: "M 550 150 C 560 150, 570 142, 590 142" },
    { id: "template-report", d: "M 180 272 L 475 280" },
    { id: "single-report-db", d: "M 540 230 C 530 230, 510 245, 510 260" },
    { id: "single-report-out", d: "M 585 280 L 590 272" },
    { id: "cam-whisper", d: "M 180 330 L 225 330" },
    { id: "whisper-llm", d: "M 335 330 L 350 330" },
    { id: "llm-db", d: "M 460 330 C 500 330, 490 280, 490 230" },
    { id: "db-classroom", d: "M 550 150 C 560 150, 570 330, 590 330" },
    { id: "syllabus-single", d: "M 180 387.5 L 225 385" },
    { id: "matrix-db", d: "M 460 385 C 475 385, 490 280, 490 230" },
    { id: "db-matrix", d: "M 550 150 C 560 150, 570 387.5, 590 387.5" }
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
          {/* Single SVG Canvas for Lines and Nodes */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none z-10" viewBox="0 0 800 430" fill="none">
            {/* Background connection lines */}
            {allPaths.map((p) => (
              <path key={`bg-${p.id}`} d={p.d} stroke={isDark ? "#1b1d26" : "#e2e8f0"} strokeWidth="1.25" />
            ))}

            {/* Group: Multi-Agent Box */}
            <rect
              x="210"
              y="40"
              width="260"
              height="210"
              rx="12"
              stroke={current.id === 0 ? (isDark ? "#52b788" : "#2d6a4f") : (isDark ? "#263750" : "#dcd7cc")}
              strokeWidth={current.id === 0 ? "2.5" : "1.25"}
              fill={isDark ? "#070e1a" : "#f5f1e6"}
              fillOpacity="0.85"
              className={current.id === 0 ? "transition-all duration-300 shadow-[0_0_15px_rgba(82,183,136,0.15)]" : "transition-all duration-300"}
            />
            <text x="340" y="55" fill={isDark ? "#c2ae78" : "#8c763e"} fontSize="7" fontFamily="monospace" letterSpacing="1" fontWeight="bold" textAnchor="middle">BỘ XỬ LÝ MULTI-AGENT</text>

            {/* Group: Data Layer Box */}
            <rect
              x="484"
              y="40"
              width="72"
              height="210"
              rx="12"
              stroke={isNodeActive("school_db") ? (isDark ? "#52b788" : "#2d6a4f") : (isDark ? "#263750" : "#dcd7cc")}
              strokeWidth="1.25"
              strokeDasharray="3,3"
              fill={isDark ? "#070e1a" : "#f5f1e6"}
              fillOpacity="0.4"
              className="transition-all duration-300"
            />
            <text x="520" y="55" fill={isDark ? "#c2ae78" : "#8c763e"} fontSize="6.5" fontFamily="monospace" letterSpacing="0.5" fontWeight="bold" textAnchor="middle">DATA LAYER</text>

            {/* left column text */}
            <text x="30" y="30" fill={isDark ? "#c2ae78" : "#8c763e"} fontSize="8.5" fontFamily="monospace" letterSpacing="1.5" fontWeight="bold">DỮ LIỆU ĐẦU VÀO / THAO TÁC</text>

            {/* right column text */}
            <text x="590" y="30" fill={isDark ? "#c2ae78" : "#8c763e"} fontSize="8.5" fontFamily="monospace" letterSpacing="1.5" fontWeight="bold">KẾT QUẢ ĐẦU RA</text>

            {/* LEFT COLUMN NODES */}
            {/* Node 1: Người dùng nhập câu hỏi */}
            <foreignObject x="30" y="55" width="150" height="45" className="pointer-events-auto">
              <div
                className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("user_query") ? nodeActiveClass : nodeInactiveClass
                  }`}
                onMouseEnter={() => setActiveFlow(0)}
              >
                <MessageSquare className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className={`text-[8.5px] font-bold truncate ${isNodeActive("user_query") ? "" : isDark ? "text-slate-200" : "text-slate-800"}`}>Nhập câu hỏi Chatbot</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Ngôn ngữ tự nhiên</div>
                </div>
              </div>
            </foreignObject>

            {/* Node 2: Nộp đề ở chatbot */}
            <foreignObject x="30" y="120" width="150" height="45" className="pointer-events-auto">
              <div
                className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("user_upload_exam") ? nodeActiveClass : nodeInactiveClass
                  }`}
                onMouseEnter={() => setActiveFlow(1)}
              >
                <FileText className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className={`text-[8.5px] font-bold truncate ${isNodeActive("user_upload_exam") ? "" : isDark ? "text-slate-200" : "text-slate-800"}`}>Nộp đề thi ở Chatbot</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Tải tệp PDF lên chatbot</div>
                </div>
              </div>
            </foreignObject>

            {/* Node 3: Giáo viên liên kết đề với điểm */}
            <foreignObject x="30" y="185" width="150" height="45" className="pointer-events-auto">
              <div
                className={`w-full h-full p-2 rounded-xl border flex items-center gap-2 cursor-pointer transition-all duration-300 ${isNodeActive("teacher_link") ? nodeActiveClass : nodeInactiveClass}`}
                onMouseEnter={() => setActiveFlow(2)}
              >
                <FileText className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className={`text-[8.5px] font-bold truncate ${isNodeActive("teacher_link") ? "" : isDark ? "text-slate-200" : "text-slate-800"}`}>Liên kết đề với điểm</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Thao tác trên bảng điểm</div>
                </div>
              </div>
            </foreignObject>

            {/* Node 4: Chọn mẫu báo cáo */}
            <foreignObject x="30" y="250" width="150" height="45" className="pointer-events-auto">
              <div
                className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("select_template") ? nodeActiveClass : nodeInactiveClass
                  }`}
                onMouseEnter={() => setActiveFlow(3)}
              >
                <FileText className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className={`text-[8.5px] font-bold truncate ${isNodeActive("select_template") ? "" : isDark ? "text-slate-200" : "text-slate-800"}`}>Chọn mẫu báo cáo</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Template có sẵn</div>
                </div>
              </div>
            </foreignObject>

            {/* Node 5: Camera bài giảng / File MP3 */}
            <foreignObject x="30" y="310" width="150" height="40" className="pointer-events-auto">
              <div
                className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("camera_audio") ? nodeActiveClass : nodeInactiveClass
                  }`}
                onMouseEnter={() => setActiveFlow(4)}
              >
                <Video className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className={`text-[8.5px] font-bold truncate ${isNodeActive("camera_audio") ? "" : isDark ? "text-slate-200" : "text-slate-800"}`}>Bài giảng: Camera/MP3</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Lịch camera / Nộp MP3</div>
                </div>
              </div>
            </foreignObject>

            {/* Node 6: Chương trình giảng dạy */}
            <foreignObject x="30" y="365" width="150" height="45" className="pointer-events-auto">
              <div
                className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("syllabus_input") ? nodeActiveClass : nodeInactiveClass
                  }`}
                onMouseEnter={() => setActiveFlow(5)}
              >
                <BookOpen className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className={`text-[8.5px] font-bold truncate ${isNodeActive("syllabus_input") ? "" : isDark ? "text-slate-200" : "text-slate-800"}`}>Chương trình giảng dạy</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Chọn CT đã dạy</div>
                </div>
              </div>
            </foreignObject>


            {/* MIDDLE COLUMN - PROCESSORS & ENGINES */}

            {/* Node: Supervisor Agent (Inside Multi-Agent) */}
            <foreignObject x="225" y="70" width="110" height="40" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("super") ? nodeActiveClass : nodeInactiveClass}`}>
                <Cpu className={`w-3.5 h-3.5 shrink-0 ${isNodeActive("super") ? "text-inherit" : "text-slate-400"}`} />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate text-[#0f1e36] dark:text-[#faf9f6]">Supervisor Agent</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">Điều phối hệ thống</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: Data & SQL Agent (Inside Multi-Agent) */}
            <foreignObject x="350" y="70" width="110" height="40" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("sql_data") ? nodeActiveClass : nodeInactiveClass}`}>
                <Cpu className={`w-3.5 h-3.5 shrink-0 ${isNodeActive("sql_data") ? "text-inherit" : "text-slate-400"}`} />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate text-[#0f1e36] dark:text-[#faf9f6]">Data & SQL Agent</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">Truy vấn điểm số</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: Stat Agent (Inside Multi-Agent) */}
            <foreignObject x="225" y="130" width="110" height="40" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("stat") ? nodeActiveClass : nodeInactiveClass}`}>
                <Cpu className={`w-3.5 h-3.5 shrink-0 ${isNodeActive("stat") ? "text-inherit" : "text-slate-400"}`} />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate text-[#0f1e36] dark:text-[#faf9f6]">Stat Agent</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">Tính toán thống kê</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: Knowledge Agent (Inside Multi-Agent) */}
            <foreignObject x="350" y="130" width="110" height="40" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("knowledge") ? nodeActiveClass : nodeInactiveClass}`}>
                <Cpu className={`w-3.5 h-3.5 shrink-0 ${isNodeActive("knowledge") ? "text-inherit" : "text-slate-400"}`} />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate text-[#0f1e36] dark:text-[#faf9f6]">Knowledge Agent</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">RAG Sách giáo khoa</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: Report Agent Inner (Inside Multi-Agent) */}
            <foreignObject x="225" y="190" width="110" height="40" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("report_agent_inner") ? nodeActiveClass : nodeInactiveClass}`}>
                <Cpu className={`w-3.5 h-3.5 shrink-0 ${isNodeActive("report_agent_inner") ? "text-inherit" : "text-slate-400"}`} />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate text-[#0f1e36] dark:text-[#faf9f6]">Report Agent</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">Biên soạn Word/PDF</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: Exam Eval Agent (Inside Multi-Agent) */}
            <foreignObject x="350" y="190" width="110" height="40" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("exam_eval_agent") ? nodeActiveClass : nodeInactiveClass}`}>
                <Cpu className={`w-3.5 h-3.5 shrink-0 ${isNodeActive("exam_eval_agent") ? "text-inherit" : "text-slate-400"}`} />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate text-[#0f1e36] dark:text-[#faf9f6]">Exam Eval Agent</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">Đo độ khó đề thi</div>
                </div>
              </div>
            </foreignObject>

            {/* Database Trường Học (Sử dụng chung) */}
            <foreignObject x="490" y="70" width="60" height="160" className="pointer-events-auto">
              <div className={`w-full h-full rounded-xl border flex flex-col items-center justify-center p-2 text-center transition-all duration-300 ${isNodeActive("school_db") ? nodeActiveClass : nodeInactiveClass}`}>
                <Database className={`w-5 h-5 mb-1.5 ${isNodeActive("school_db") ? "text-inherit animate-bounce" : "text-slate-400"}`} />
                <div className="text-[8px] font-bold text-[#0f1e36] dark:text-[#faf9f6] leading-tight">Database<br />Trường Học</div>

                {/* Server Rack Stack Effect */}
                <div className="space-y-1 w-full flex flex-col items-center mt-2.5">
                  <div className={`w-10 h-2 rounded-xs flex items-center justify-between px-1 border ${isNodeActive("school_db") ? "bg-[#2d6a4f]/10 border-[#52b788]/30" : "bg-slate-500/5 border-slate-500/10"}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${isNodeActive("school_db") ? "bg-emerald-500 animate-pulse" : "bg-slate-400"} shrink-0`} />
                    <span className="w-5 h-0.5 rounded-xs bg-slate-500/30 dark:bg-slate-700/50" />
                  </div>
                  <div className={`w-10 h-2 rounded-xs flex items-center justify-between px-1 border ${isNodeActive("school_db") ? "bg-[#2d6a4f]/10 border-[#52b788]/30" : "bg-slate-500/5 border-slate-500/10"}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${isNodeActive("school_db") ? "bg-emerald-500 animate-pulse" : "bg-slate-400"} shrink-0`} />
                    <span className="w-5 h-0.5 rounded-xs bg-slate-500/30 dark:bg-slate-700/50" />
                  </div>
                  <div className={`w-10 h-2 rounded-xs flex items-center justify-between px-1 border ${isNodeActive("school_db") ? "bg-[#2d6a4f]/10 border-[#52b788]/30" : "bg-slate-500/5 border-slate-500/10"}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${isNodeActive("school_db") ? "bg-emerald-500 animate-pulse" : "bg-slate-400"} shrink-0`} />
                    <span className="w-5 h-0.5 rounded-xs bg-slate-500/30 dark:bg-slate-700/50" />
                  </div>
                </div>

                <div className="text-[6px] font-mono text-slate-500 mt-2">Dữ liệu tập trung</div>
              </div>
            </foreignObject>


            {/* SINGLE AGENTS & PIPELINES (OUTSIDE THE BOX) */}

            {/* Node: Single Agent LLM + R */}
            <foreignObject x="225" y="260" width="235" height="40" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-2 cursor-pointer transition-all duration-300 ${isNodeActive("single_llm_rag") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(1)}>
                <Cpu className={`w-4 h-4 shrink-0 ${isNodeActive("single_llm_rag") ? "text-inherit" : "text-slate-400"}`} />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-extrabold truncate text-[#0f1e36] dark:text-[#faf9f6]">Single Agent (LLM + RAG Sách giáo khoa)</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">Chạy độc lập kiểm tra chéo ma trận Bloom đề thi</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: Single Report Agent */}
            <foreignObject x="475" y="260" width="110" height="40" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("single_report_agent") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(3)}>
                <Cpu className={`w-3.5 h-3.5 shrink-0 ${isNodeActive("single_report_agent") ? "text-inherit" : "text-slate-400"}`} />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate text-[#0f1e36] dark:text-[#faf9f6]">Report Agent</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">Tự điền mẫu & Nhận xét</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: Whisper STT */}
            <foreignObject x="225" y="310" width="110" height="40" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("whisper_stt") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(4)}>
                <Cpu className={`w-3.5 h-3.5 shrink-0 ${isNodeActive("whisper_stt") ? "text-inherit" : "text-slate-400"}`} />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate text-[#0f1e36] dark:text-[#faf9f6]">Whisper STT</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">Dịch thoại bài giảng</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: LLM Pedagogical */}
            <foreignObject x="350" y="310" width="110" height="40" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-1 cursor-pointer transition-all duration-300 ${isNodeActive("llm_pedagogical") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(4)}>
                <Cpu className={`w-3.5 h-3.5 shrink-0 ${isNodeActive("llm_pedagogical") ? "text-inherit" : "text-slate-400"}`} />
                <div className="text-left min-w-0">
                  <div className="text-[8px] font-bold truncate text-[#0f1e36] dark:text-[#faf9f6]">LLM Sư Phạm</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">Chấm điểm chất lượng</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: Matrix Agent (Single Agent for syllabus matrix) */}
            <foreignObject x="225" y="365" width="235" height="40" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-lg border flex items-center gap-2 cursor-pointer transition-all duration-300 ${isNodeActive("matrix_agent") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(5)}>
                <Cpu className={`w-4 h-4 shrink-0 ${isNodeActive("matrix_agent") ? "text-inherit" : "text-slate-400"}`} />
                <div className="text-left min-w-0">
                  <div className="text-[8.5px] font-extrabold truncate text-[#0f1e36] dark:text-[#faf9f6]">Matrix Agent (Single Agent)</div>
                  <div className="text-[6.5px] font-mono text-slate-500 truncate">Tự động thiết kế ma trận từ CT dạy</div>
                </div>
              </div>
            </foreignObject>


            {/* RIGHT COLUMN - OUTPUT RESULTS */}

            {/* Node: Chatbot Response */}
            <foreignObject x="590" y="55" width="180" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("chat_response") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(0)}>
                <MessageSquare className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className={`text-[8.5px] font-bold truncate ${isNodeActive("chat_response") ? "" : isDark ? "text-slate-200" : "text-slate-800"}`}>Câu Trả Lời & Báo Cáo</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Hiển thị kết quả / Xuất Word</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: Exam Difficulty Res */}
            <foreignObject x="590" y="120" width="180" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("exam_difficulty_res") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(1)}>
                <BarChart2 className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className={`text-[8.5px] font-bold truncate ${isNodeActive("exam_difficulty_res") ? "" : isDark ? "text-slate-200" : "text-slate-800"}`}>Xác Nhận Độ Khó & SGK</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Chỉ số CDI, đối soát RAG</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: BGH Warning */}
            <foreignObject x="590" y="185" width="180" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("bgh_warning") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(2)}>
                <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className={`text-[8.5px] font-bold truncate ${isNodeActive("bgh_warning") ? "" : isDark ? "text-slate-200" : "text-slate-800"}`}>Nhãn Cảnh Báo cho BGH</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Cảnh báo lạm phát / Gap</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: Formatted Report */}
            <foreignObject x="590" y="250" width="180" height="45" className="pointer-events-auto">
              <div
                className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("formatted_report") ? nodeActiveClass : nodeInactiveClass}`}
                onMouseEnter={() => setActiveFlow(3)}
              >
                <FileText className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className={`text-[8.5px] font-bold truncate ${isNodeActive("formatted_report") ? "" : isDark ? "text-slate-200" : "text-slate-800"}`}>Báo Cáo Mẫu (Word/PDF)</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Đầy đủ nhận xét & kiến nghị</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: BGH Classroom Report */}
            <foreignObject x="590" y="310" width="180" height="40" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("bgh_classroom_report") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(4)}>
                <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className={`text-[8.5px] font-bold truncate ${isNodeActive("bgh_classroom_report") ? "" : isDark ? "text-slate-200" : "text-slate-800"}`}>Báo cáo Tiết học BGH</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Xem biểu đồ tương tác/chất lượng</div>
                </div>
              </div>
            </foreignObject>

            {/* Node: Ma trận đề thi chuẩn Bloom */}
            <foreignObject x="590" y="365" width="180" height="45" className="pointer-events-auto">
              <div className={`w-full h-full p-1.5 rounded-xl border flex items-center gap-1.5 cursor-pointer transition-all duration-300 ${isNodeActive("matrix_output") ? nodeActiveClass : nodeInactiveClass}`} onMouseEnter={() => setActiveFlow(5)}>
                <Target className="w-3.5 h-3.5 shrink-0" />
                <div className="text-left min-w-0">
                  <div className={`text-[8.5px] font-bold truncate ${isNodeActive("matrix_output") ? "" : isDark ? "text-slate-200" : "text-slate-800"}`}>Ma trận đề thi chi tiết</div>
                  <div className="text-[7px] font-mono text-slate-500 truncate">Ma trận & Khung câu hỏi gợi ý</div>
                </div>
              </div>
            </foreignObject>

            {/* Active connection lines (Drawn on top of base layers and nodes) */}
            {allPaths.map((p) => {
              const active = isLineActive(p.id);
              if (!active) return null;
              return <path key={`active-${p.id}`} d={p.d} stroke={current.stroke} strokeWidth="2.5" className="animated-flow-line" />;
            })}

            {/* Active Flow Line Labels */}
            {current.labels.map((lbl, idx) => (
              <g key={idx}>
                <rect
                  x={lbl.x - 42}
                  y={lbl.y - 7}
                  width="84"
                  height="13"
                  rx="4"
                  fill={isDark ? "#070e1a" : "#f5f1e6"}
                  stroke={current.stroke}
                  strokeWidth="0.5"
                  opacity="0.95"
                />
                <text
                  x={lbl.x}
                  y={lbl.y}
                  fill={isDark ? "#faf9f6" : "#0f1e36"}
                  fontSize="7"
                  fontFamily="monospace"
                  fontWeight="bold"
                  textAnchor="middle"
                  dominantBaseline="central"
                >
                  {lbl.text}
                </text>
              </g>
            ))}
          </svg>

        </div>
      </div>

      {/* RIGHT SIDE: SELECTORS & EXPLANATION SIDEBAR */}
      <div className="w-full lg:w-80 shrink-0 flex flex-col gap-3.5 justify-center border-t lg:border-t-0 lg:border-l pt-4 lg:pt-0 lg:pl-4 border-[#dcd7cc]/60 dark:border-[#263750]/60 text-left relative z-20">
        <div className="text-[10px] font-bold tracking-wider uppercase text-[#8c763e] dark:text-[#c2ae78]">
          Chọn luồng nghiệp vụ:
        </div>

        {/* Vertical Flow Selector Tabs */}
        <div className="flex flex-col gap-2">
          {flows.map((flow) => (
            <button
              key={flow.id}
              type="button"
              onClick={() => setActiveFlow(flow.id)}
              className={`w-full px-3 py-2 rounded-xl text-[10px] font-mono font-bold tracking-tight border transition-all cursor-pointer text-left flex items-center justify-between group ${activeFlow === flow.id
                ? isDark
                  ? "bg-slate-900 border-[#c2ae78] text-[#faf9f6] shadow-sm"
                  : "bg-[#0f1e36] border-[#8c763e] text-[#faf9f6] shadow-sm"
                : isDark
                  ? "bg-[#070e1a]/40 border-transparent text-slate-400 hover:bg-[#263750]/60 hover:text-[#c2ae78]"
                  : "bg-[#dcd7cc]/25 border-transparent text-[#4a5568] hover:bg-[#dcd7cc]/60 hover:text-[#0f1e36]"
                }`}
            >
              <span>{flow.title}</span>
              <span
                className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${activeFlow === flow.id ? "scale-125 opacity-100" : "bg-transparent opacity-0 scale-50"
                  }`}
                style={{ backgroundColor: flow.stroke }}
              />
            </button>
          ))}
        </div>

        {/* Explanation Card */}
        <div className={`p-4 rounded-xl border text-[11px] leading-relaxed transition-all duration-300 text-left flex flex-col gap-2 ${isDark ? "bg-[#070e1a] border-[#263750] text-[#faf9f6]" : "bg-white border-[#dcd7cc] text-[#0f1e36] shadow-xs"
          }`}>
          <div className={`font-extrabold uppercase text-[10px] tracking-wider ${current.color}`}>
            {current.title}:
          </div>
          <div className="text-[10.5px] font-normal leading-relaxed text-slate-650 dark:text-slate-300">
            {current.desc}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PresentationModal({ isOpen, onClose, theme }: PresentationModalProps) {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [hoveredCardIndex, setHoveredCardIndex] = useState<number | null>(null);
  const [isVideoMaximized, setIsVideoMaximized] = useState(false);
  const [activeDemoTab, setActiveDemoTab] = useState<number>(0);
  const [activePath, setActivePath] = useState<"upload" | "camera">("upload");
  const [isMp4Playing, setIsMp4Playing] = useState(false);
  const mp4VideoRef = useRef<HTMLVideoElement>(null);
  const [matrixStep, setMatrixStep] = useState<number>(1);
  const [matrixDifficulty, setMatrixDifficulty] = useState<"standard" | "hard" | "easy">("standard");
  const [selectedLessons, setSelectedLessons] = useState<number[]>([0, 1, 2]);
  const [matrixLoadingLog, setMatrixLoadingLog] = useState<string>("Đang phân tích chương trình đã dạy...");
  const isDark = theme === "dark";

  const slides = [
    // SLIDE 1: EWS - TRỌNG SỐ ĐỘNG SOFTMAX (VÍ DỤ MINH HỌA)
    {
      title: "Tính Năng 3.6: Cảnh Báo Sớm Rủi Ro Học Tập (EWS)",
      subtitle: "Trọng số động Softmax — ví dụ minh họa cách hệ thống phát hiện học sinh nguy cơ",
      type: "ews_softmax",
      content: (
        <div className="w-full">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start text-left w-full">
            {/* Left: concept + formula */}
            <div className="lg:col-span-5 space-y-4">
              <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold ${isDark ? "bg-[#2d6a4f]/20 text-[#52b788] border-[#2d6a4f]/40" : "bg-[#f0f4f0] text-[#2d6a4f] border-[#cbdcd0]"} border`}>
                <ShieldAlert className="w-3 h-3 text-[#2d6a4f] dark:text-[#52b788]" /> Cảnh báo sớm rủi ro
              </div>
              <h2 className={`text-2xl md:text-3xl font-extrabold tracking-tight leading-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
                Trọng Số Động Softmax
              </h2>
              <p className={`leading-relaxed text-xs md:text-sm ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                Thay vì dùng trọng số cố định cho mọi học sinh, hệ thống tự điều chỉnh trọng số theo từng học sinh: yếu tố nào đang rủi ro cao sẽ được "phóng đại" để ảnh hưởng mạnh hơn đến điểm rủi ro cuối cùng.
              </p>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-slate-900/50 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-xs"}`}>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                  <strong className={`text-xs md:text-[13px] font-extrabold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Công thức Softmax động</strong>
                </div>
                <p className={`text-[10px] md:text-[11.5px] leading-relaxed font-mono ${isDark ? "text-slate-300" : "text-[#0f1e36]"}`}>
                  w<sub>k</sub> = base<sub>k</sub>·e<sup>α<sub>k</sub>·S<sub>k</sub></sup> / Σ base<sub>j</sub>·e<sup>α<sub>j</sub>·S<sub>j</sub></sup>
                </p>
                <p className={`text-[9.5px] md:text-[10.5px] leading-relaxed mt-1.5 ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                  S<sub>k</sub>: điểm rủi ro yếu tố k · α<sub>k</sub>: độ nhạy riêng từng yếu tố · base<sub>k</sub>: trọng số gốc
                </p>
              </div>

              <div className={`p-3 rounded-xl border ${isDark ? "bg-[#8c763e]/5 border-[#8c763e]/15" : "bg-[#faf6e8] border-[#ebdcb0]/80 shadow-xs"}`}>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                  <strong className={`text-xs md:text-[13px] font-extrabold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Điểm rủi ro cuối</strong>
                </div>
                <p className={`text-[10px] md:text-[11.5px] leading-relaxed font-mono ${isDark ? "text-slate-300" : "text-[#0f1e36]"}`}>
                  final = (1−β)·Σ(w·S) + β·max(S)
                </p>
                <p className={`text-[9.5px] md:text-[10.5px] leading-relaxed mt-1.5 ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                  β = worst_factor_beta (mặc định 0 → chỉ dùng trung bình có trọng số động).
                </p>
              </div>
            </div>

            {/* Right: worked example */}
            <div className="lg:col-span-7 space-y-3">
              <div className={`p-3 rounded-2xl border ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-md"}`}>
                <div className="flex items-center justify-between mb-2">
                  <strong className={`text-xs md:text-[13px] font-extrabold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Ví dụ: học sinh nghỉ học nhiều</strong>
                  <span className={`text-[9.5px] font-bold px-2 py-0.5 rounded-full ${isDark ? "bg-red-500/20 text-[#c97575]" : "bg-[#fdf2f2] text-red-700"}`}>Kết quả: HIGH</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-[10px] md:text-[11px]">
                    <thead>
                      <tr className={`border-b ${isDark ? "border-[#263750] text-slate-400" : "border-[#dcd7cc] text-[#4a5568]"}`}>
                        <th className="py-1.5 pr-2 font-semibold">Yếu tố</th>
                        <th className="py-1.5 pr-2 font-semibold">Rủi ro S</th>
                        <th className="py-1.5 pr-2 font-semibold">Trọng số gốc</th>
                        <th className="py-1.5 pr-2 font-semibold">Trọng số động</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className={`border-b ${isDark ? "border-[#1a2740]" : "border-[#f0ece0]"}`}>
                        <td className="py-1.5 pr-2">Điểm</td>
                        <td className="py-1.5 pr-2">30</td>
                        <td className="py-1.5 pr-2">0.55</td>
                        <td className="py-1.5 pr-2">0.29</td>
                      </tr>
                      <tr className={`border-b ${isDark ? "border-[#1a2740]" : "border-[#f0ece0]"}`}>
                        <td className="py-1.5 pr-2">Học tập (LMS)</td>
                        <td className="py-1.5 pr-2">70</td>
                        <td className="py-1.5 pr-2">0.15</td>
                        <td className="py-1.5 pr-2">0.21</td>
                      </tr>
                      <tr className={`border-b ${isDark ? "border-[#1a2740]" : "border-[#f0ece0]"}`}>
                        <td className="py-1.5 pr-2">Chuyên cần</td>
                        <td className="py-1.5 pr-2 font-bold text-red-500">90</td>
                        <td className="py-1.5 pr-2">0.15</td>
                        <td className="py-1.5 pr-2 font-bold text-red-500">0.42</td>
                      </tr>
                      <tr>
                        <td className="py-1.5 pr-2">Hạnh kiểm</td>
                        <td className="py-1.5 pr-2">20</td>
                        <td className="py-1.5 pr-2">0.15</td>
                        <td className="py-1.5 pr-2">0.08</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div className={`mt-2.5 pt-2.5 border-t text-[10px] md:text-[11px] leading-relaxed ${isDark ? "border-[#263750] text-slate-400" : "border-[#dcd7cc] text-[#4a5568]"}`}>
                  <strong className={isDark ? "text-slate-200" : "text-[#0f1e36]"}>Điểm cuối = 62.7 → HIGH.</strong> Yếu tố "Chuyên cần" rủi ro cao (90) được nâng từ 0.15 lên 0.42, giúp hệ thống bắt đúng học sinh nguy cơ thực sự.
                </div>
              </div>

              <div className={`p-3 rounded-2xl border ${isDark ? "bg-slate-900/50 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-xs"}`}>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
                  <strong className={`text-xs md:text-[13px] font-extrabold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>So sánh: tắt trọng số động</strong>
                </div>
                <p className={`text-[10px] md:text-[11.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                  Cùng học sinh, nếu dùng trọng số tĩnh: <span className="font-mono">0.55×30 + 0.15×70 + 0.15×90 + 0.15×20 = 43.5 → MODERATE</span>. Trọng số động giúp phát hiện sớm hơn một bậc rủi ro.
                </p>
              </div>
            </div>
          </div>
        </div>
      )
    },
    // SLIDE 2: TIÊU ĐỀ & MỞ ĐẦU
    // SLIDE 2: TIÊU ĐỀ & MỞ ĐẦU
    {
      title: "AI Trợ Lý Phân Tích Kết Quả Học Tập Toàn Trường Cho Ban Giám Hiệu",
      subtitle: "Giải pháp quản trị chất lượng giáo dục dựa trên dữ liệu dành cho Ban Giám Hiệu",
      type: "intro",
      content: (
        <div className="flex flex-col items-center justify-center text-center max-w-4xl mx-auto space-y-6 animate-fade-in">
          <div className="relative">
            <div className={`absolute inset-0 ${isDark ? "bg-[#c2ae78]/10" : "bg-[#8c763e]/5"} blur-3xl rounded-full scale-150 animate-pulse`} />
            <div className={`relative w-20 h-20 rounded-2xl ${isDark ? "bg-slate-900 border-[#263750]" : "bg-white border-[#dcd7cc]"} flex items-center justify-center shadow-lg border shrink-0 animate-in fade-in duration-200`}>
              <img src="/logo.svg" className="w-12 h-12 object-contain animate-bounce" alt="Owl Logo" />
            </div>
          </div>

          <div className="space-y-3">
            <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${isDark ? "bg-[#c2ae78]/10 text-[#c2ae78] border-[#c2ae78]/25" : "bg-white border-[#dcd7cc] text-[#8c763e]"} border`}>
              <Sparkles className="w-3 h-3 text-[#8c763e] dark:text-[#c2ae78]" /> Báo cáo Nghiên cứu
            </span>
            <h1 className={`text-3xl md:text-4xl lg:text-5xl font-extrabold tracking-tight leading-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
              AI Trợ Lý Phân Tích Kết Quả Học Tập Toàn Trường Cho Ban Giám Hiệu
            </h1>
            <p className={`text-sm md:text-base max-w-2xl mx-auto ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
              Giải pháp đo lường giáo dục hiện đại giúp tối ưu hóa công tác quản lý, giám sát công bằng học thuật và nâng cao chất lượng giảng dạy.
            </p>
          </div>

          <div className={`pt-4 flex items-center gap-4 text-xs font-bold ${isDark ? "text-slate-500" : "text-[#8c763e]/80"}`}>
            <span className="flex items-center gap-1">Multi-Agent AI</span>
            <span className={`w-1 h-1 rounded-full ${isDark ? "bg-[#263750]" : "bg-[#dcd7cc]"}`} />
            <span>Phân Tích Đo Lường Sâu</span>
            <span className={`w-1 h-1 rounded-full ${isDark ? "bg-[#263750]" : "bg-[#dcd7cc]"}`} />
            <span>Tự Động Hóa Báo Cáo</span>
          </div>
        </div>
      )
    },
    // SLIDE 2: THỰC TRẠNG & ĐIỂM NGHẼN TRÊN CASE STUDY (THE PROBLEM)
    {
      title: "Thực Trạng & Điểm Nghẽn Trong Báo Cáo Truyền Thống",
      subtitle: "Áp lực thời gian và rào cản từ dữ liệu phân tán trong quản lý học thuật",
      type: "pain_points",
      content: (
        <div className="w-full flex flex-col gap-6 max-w-6xl mx-auto text-left">
          {/* Section Indicator at the top of slide content area */}
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider ${isDark ? "bg-[#c97575]/15 text-[#c97575] border-[#c97575]/25" : "bg-[#faf2f0] text-[#9c4141] border-[#ecdcd8]"} border shadow-xs`}>
              <AlertTriangle className="w-4 h-4" /> 4 ĐIỂM NGHẼN VẬN HÀNH THỦ CÔNG ĐANG GẶP PHẢI
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-stretch">
            {[
              {
                badge: "Case Study 1: Báo Cáo Tổng Kết Chất Lượng Học Kỳ (Khối/Lớp)",
                metric: "3 - 5 NGÀY",
                metricDesc: "mỗi đợt tổng kết kỳ",
                problem: "Giáo viên và Tổ trưởng phải thu gom điểm Excel từ hàng chục lớp, tự viết công thức tỷ lệ xếp loại, thống kê phổ điểm lệch và biên soạn thủ công văn bản Word nộp BGH."
              },
              {
                badge: "Case Study 2: Thẩm Định Đề Kiểm Tra (BGH Kiểm Duyệt)",
                metric: "3 - 4 GIỜ",
                metricDesc: "cho mỗi đề kiểm duyệt",
                problem: "BGH mất nhiều thời gian kiểm duyệt thủ công từng ma trận Bloom, đối soát xem câu hỏi có bám sát chuẩn kiến thức SGK hay không và độ khó có bị lệch."
              },
              {
                badge: "Case Study 3: Giám Sát Tiết Học",
                metric: "< 1%",
                metricDesc: "tiết học được đánh giá dưới dạng dự giờ",
                problem: "BGH không thể đi từng lớp để kiểm soát xem lớp đó đang làm cái gì, dẫn đến không thể đánh giá được chất lượng giảng dạy thực tế của giáo viên."
              },
              {
                badge: "Case Study 4: Tra Cứu Lịch Sử Học Tập Học Sinh",
                metric: "15 - 30 PHÚT",
                metricDesc: "mỗi học sinh",
                problem: "Muốn xem lịch sử học bạ, so sánh tiến độ phải mở và tìm kiếm thủ công trên nhiều tệp Excel của các năm học/học kỳ khác nhau."
              }
            ].map((cs, idx) => {
              const isAnyHovered = hoveredCardIndex !== null;
              const isSelfHovered = hoveredCardIndex === idx;
              return (
                <div
                  key={idx}
                  onMouseEnter={() => setHoveredCardIndex(idx)}
                  onMouseLeave={() => setHoveredCardIndex(null)}
                  className={`p-6 rounded-xl border flex flex-col justify-between space-y-4 transition-all duration-300 cursor-default ${isSelfHovered
                    ? "scale-[1.03] shadow-md z-10"
                    : isAnyHovered
                      ? "scale-[0.98] opacity-80"
                      : "scale-100 opacity-100"
                    } ${isDark
                      ? `bg-[#faf2f0]/5 border-[#c97575]/15 ${isSelfHovered ? "border-[#c2ae78] bg-[#faf2f0]/10" : ""}`
                      : `bg-[#faf2f0]/60 border-[#ecdcd8] shadow-xs ${isSelfHovered ? "border-[#8c763e] bg-white/90" : ""}`
                    }`}
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className={`text-[10px] md:text-xs font-extrabold uppercase tracking-wider ${isDark ? "text-slate-400" : "text-slate-500"}`}>{cs.badge}</span>
                    </div>
                    <div className="flex items-baseline gap-2 mt-1.5">
                      <span className="text-3xl md:text-4xl font-black tracking-tight text-[#9c4141] dark:text-[#c97575]">{cs.metric}</span>
                      <span className="text-xs md:text-sm text-slate-400 font-semibold">{cs.metricDesc}</span>
                    </div>
                    <p className={`text-xs md:text-[13px] leading-relaxed mt-2 ${isDark ? "text-slate-300" : "text-[#4a5568]"}`}>
                      {cs.problem}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )
    },
    // SLIDE 2.5: GIẢI PHÁP ĐỀ XUẤT (PROPOSED SOLUTION)
    {
      title: "Giải Pháp Đề Xuất: Hệ Thống AI EduOwl",
      subtitle: "Mô hình quản trị giáo dục thông minh ứng dụng đa tác nhân tự động hóa",
      type: "proposed_solution",
      content: (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 max-w-6xl mx-auto items-center text-left w-full animate-fade-in">
          {/* CỘT TRÁI: GIỚI THIỆU VỀ EDUOWL */}
          <div className="lg:col-span-5 space-y-5">
            <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold ${isDark ? "bg-[#2d6a4f]/20 text-[#52b788] border-[#2d6a4f]/40" : "bg-[#f0faf4] text-[#2d6a4f] border-[#d0ecd8]"} border`}>
              <Sparkles className="w-3 h-3 text-[#2d6a4f] dark:text-[#52b788]" /> Định Hướng Giải Pháp
            </div>
            <h2 className={`text-2xl font-extrabold tracking-tight leading-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
              EduOwl - AI Trợ Lý Phân Tích Kết Quả Học Tập Toàn Trường Cho Ban Giám Hiệu
            </h2>
            <p className={`leading-relaxed text-xs md:text-sm ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
              EduOwl đề xuất giải pháp tích hợp đa tác nhân kết nối trực tiếp với Cơ sở dữ liệu trường học, tri thức sách giáo khoa và camera bài giảng nhằm số hóa và giải phóng hoàn toàn sức lao động hành chính:
            </p>

            <div className="space-y-3.5 text-xs">
              <div className="flex items-start gap-2.5">
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold mt-0.5 shrink-0 ${isDark ? "bg-[#52b788]/20 text-[#52b788]" : "bg-[#2d6a4f]/10 text-[#2d6a4f]"}`}>1</span>
                <div>
                  <strong className={isDark ? "text-white" : "text-[#0f1e36]"}>Tập trung hóa dữ liệu:</strong> Nơi để tổng hợp tệp Excel điểm số, tệp đề thi PDF và dữ liệu camera bài giảng về CSDL chung.
                </div>
              </div>
              <div className="flex items-start gap-2.5">
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold mt-0.5 shrink-0 ${isDark ? "bg-[#52b788]/20 text-[#52b788]" : "bg-[#2d6a4f]/10 text-[#2d6a4f]"}`}>2</span>
                <div>
                  <strong className={isDark ? "text-white" : "text-[#0f1e36]"}>Kiến trúc AI tối ưu:</strong> Sử dụng Supervisor Agent đa tác nhân cho các yêu cầu tìm kiếm tự do, song song với các Agent đơn lẻ (Single Agent/Pipeline) chạy độc lập để xử lý tác vụ chuyên môn.
                </div>
              </div>
            </div>
          </div>

          {/* CỘT PHẢI: 4 CARDS NẰM DỌC */}
          <div className="lg:col-span-7 flex flex-col gap-3">
            {[
              {
                badge: "Giải Pháp 1: Báo Cáo Chất Lượng Tự Động (Report Agent)",
                metric: "< 2 phút",
                metricDesc: "hoàn thành xuất báo cáo",
                problem: "Hệ thống tự động thống kê phổ điểm, xếp loại học lực, so sánh lớp học và xuất báo cáo Word/PDF hoàn chỉnh tức thì thay vì tốn 3-5 ngày ròng rã chuẩn bị thủ công."
              },
              {
                badge: "Giải Pháp 2: Thẩm Định Đề Bằng AI (Single Agent & RAG)",
                metric: "< 1 PHÚT",
                metricDesc: "kiểm định đề kiểm tra",
                problem: "AI đối soát tức thì câu hỏi đề thi với chuẩn kiến thức SGK và tam giác hóa đối sánh độ khó Bloom thiết kế (CDI) với điểm số thực tế (EDI) thay vì mất 3-4 giờ."
              },
              {
                badge: "Giải Pháp 3: Giám Sát Tiết Học Kỹ Thuật Số (Audio & Camera Pipeline)",
                metric: "100% TIẾT HỌC",
                metricDesc: "được tự động phân tích & đánh giá",
                problem: "BGH không cần dự giờ trực tiếp, AI phân tích âm thanh lớp học (Whisper STT) và hình ảnh camera để đánh giá chất lượng dạy một cách khách quan sư phạm."
              },
              {
                badge: "Giải Pháp 4: Tra Cứu Lịch Sử Học Tập Toàn Diện",
                metric: "< 25",
                metricDesc: "truy xuất lịch sử học bạ học sinh",
                problem: "Tra cứu tức thì biểu đồ tiến độ học tập, điểm số học sinh qua nhiều năm học bằng Chatbot thông qua CSDL tập trung thay vì lục tìm nhiều tệp Excel lẻ tẻ trong 15-30 phút."
              }
            ].map((cs, idx) => {
              const isAnyHovered = hoveredCardIndex !== null;
              const isSelfHovered = hoveredCardIndex === idx;
              return (
                <div
                  key={idx}
                  onMouseEnter={() => setHoveredCardIndex(idx)}
                  onMouseLeave={() => setHoveredCardIndex(null)}
                  className={`p-3 md:p-3.5 rounded-xl border flex flex-col justify-between space-y-1 transition-all duration-300 cursor-default ${isSelfHovered
                    ? "scale-[1.02] shadow-sm z-10"
                    : isAnyHovered
                      ? "scale-[0.99] opacity-80"
                      : "scale-100 opacity-100"
                    } ${isDark
                      ? `bg-[#102a1e]/15 border-[#2d6a4f]/30 ${isSelfHovered ? "border-[#52b788] bg-[#102a1e]/30" : ""}`
                      : `bg-[#f0faf4]/60 border-[#d0ecd8] shadow-xs ${isSelfHovered ? "border-[#2d6a4f] bg-white/95" : ""}`
                    }`}
                >
                  <div className="space-y-1 text-left">
                    <div className="flex items-center justify-between">
                      <span className={`text-[8.5px] md:text-[9.5px] font-extrabold uppercase tracking-wider ${isDark ? "text-slate-400" : "text-slate-500"}`}>{cs.badge}</span>
                    </div>
                    <div className="flex items-baseline gap-2 mt-0.5">
                      <span className="text-xl md:text-2xl font-black tracking-tight text-[#2d6a4f] dark:text-[#52b788]">{cs.metric}</span>
                      <span className={`text-[9.5px] md:text-[10.5px] font-semibold ${isDark ? "text-slate-400" : "text-slate-500"}`}>{cs.metricDesc}</span>
                    </div>
                    <p className={`text-[10px] md:text-[11px] leading-relaxed mt-0.5 ${isDark ? "text-slate-300" : "text-[#4a5568]"}`}>
                      {cs.problem}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )
    },

    // SLIDE 3: GIẢI PHÁP - TRỢ LÝ AI THÔNG MINH (THE SOLUTION)
    {
      title: "Giải Pháp Trợ Lý AI EduOwl",
      subtitle: "Kiến trúc Multi-Agent tự động kết nối và trực quan hóa các luồng nghiệp vụ học thuật",
      type: "solution",
      content: (
        <div className="w-full h-full flex flex-col items-center justify-center text-center max-w-none">
          <div className="w-full h-full">
            {/* Coded Dynamic Diagram */}
            <SolutionDiagram isDark={isDark} />
          </div>
        </div>
      )
    },
    // SLIDE 5: TÍNH NĂNG 1 - BÁO CÁO THEO MẪU
    {
      title: "Tính Năng 1: Báo Cáo Theo Mẫu",
      subtitle: "Kịch bản demo: Đồng hành cùng thầy Triết (BGH trường THCS Nguyễn Du) giải quyết báo cáo cuối năm",
      type: "auto_reports",
      content: (
        <div className="w-full h-full relative flex items-center justify-center">
          {/* Normal Layout */}
          <div className={`grid grid-cols-1 lg:grid-cols-12 gap-8 items-center text-left w-full transition-opacity duration-300 ${isVideoMaximized ? "opacity-0 pointer-events-none" : "opacity-100"}`}>
            <div className="lg:col-span-4 space-y-4">
              <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold ${isDark ? "bg-[#2a4d9c]/20 text-[#6366f1] border-[#2a4d9c]/40" : "bg-[#eff2fc] text-[#2a4d9c] border-[#dce0f5]"} border`}>
                <FileText className="w-3 h-3 text-[#2a4d9c] dark:text-[#6366f1]" /> Tự động hóa thủ tục
              </div>
              <h2 className={`text-2xl md:text-3xl font-extrabold tracking-tight leading-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
                Báo Cáo Theo Mẫu
              </h2>
              <p className={`leading-relaxed text-xs md:text-sm ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                Tới cuối năm học, thầy Triết (BGH trường THCS Nguyễn Du) cần xuất báo cáo học thuật toàn trường.
              </p>

              <div className="space-y-3 relative">
                {/* Card 1 */}
                <div className={`p-2.5 md:p-3 rounded-xl border relative ${isDark ? "bg-[#2a4d9c]/5 border-[#2a4d9c]/15" : "bg-[#eff2fc]/60 border-[#dce0f5] shadow-xs"} transition-all duration-200 hover:border-[#8c763e] dark:hover:border-[#c2ae78]`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold shrink-0 ${isDark ? "bg-[#6366f1]/20 text-[#6366f1]" : "bg-[#2a4d9c]/10 text-[#2a4d9c]"}`}>1</span>
                    <strong className={`text-xs md:text-[13px] font-bold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Tự Động Tổng Hợp Dữ Liệu</strong>
                  </div>
                  <p className={`text-[10.5px] md:text-[11.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                    Tổng hợp kết quả học lực, phổ điểm toàn bộ các lớp trong trường tự động chỉ từ <span className="text-emerald-600 dark:text-[#52b788] font-extrabold px-1.5 py-0.5 rounded bg-emerald-500/10 dark:bg-emerald-500/20">15 - 30 giây</span>.
                  </p>
                </div>

                {/* Card 2 */}
                <div className={`p-2.5 md:p-3 rounded-xl border relative ${isDark ? "bg-[#2d6a4f]/5 border-[#2d6a4f]/15" : "bg-[#f0faf4]/60 border-[#d0ecd8] shadow-xs"} transition-all duration-200 hover:border-[#8c763e] dark:hover:border-[#c2ae78]`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold shrink-0 ${isDark ? "bg-[#52b788]/20 text-[#52b788]" : "bg-[#2d6a4f]/10 text-[#2d6a4f]"}`}>2</span>
                    <strong className={`text-xs md:text-[13px] font-bold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Đề Xuất & Nhận Xét Sư Phạm</strong>
                  </div>
                  <p className={`text-[10.5px] md:text-[11.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                    Trợ lý tự động viết các nhận xét sư phạm chi tiết và lập kế hoạch cải thiện cụ thể để BGH xuất tệp Word/PDF chính thống.
                  </p>
                </div>
              </div>
            </div>

            <div className="lg:col-span-8 space-y-3">
              <div className="relative group">
                <div className={`p-2 rounded-2xl border ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-md"} overflow-hidden`}>
                  <video
                    src="https://jmrjohuhxvywhipncyij.supabase.co/storage/v1/object/public/lectures/slide_tao_bao_cao_theo_mau.mp4"
                    controls
                    loop
                    playsInline
                    className="w-full rounded-xl aspect-video object-cover"
                  />
                  {/* Zoom overlay button */}
                  <button
                    type="button"
                    onClick={() => setIsVideoMaximized(true)}
                    className="absolute top-4 right-4 bg-black/60 hover:bg-[#8c763e] text-white p-2 rounded-full opacity-0 group-hover:opacity-100 transition duration-200 cursor-pointer"
                    title="Phóng to video ra toàn slide"
                  >
                    <Maximize2 className="w-4 h-4" />
                  </button>
                </div>
                <div className={`text-[10px] text-center italic mt-1.5 ${isDark ? "text-slate-500" : "text-[#8c763e]"}`}>
                  Hình ảnh thực tế: AI tự động báo cáo trong 15s. (Rà chuột và click nút kính lúp ở góc để Phóng to toàn slide)
                </div>
              </div>
            </div>
          </div>

          {/* Maximized Overlay (Full Slide) */}
          {isVideoMaximized && (
            <div className={`absolute inset-0 z-50 flex flex-col justify-between p-6 ${isDark ? "bg-[#070e1a]" : "bg-[#f5f1e6]"} animate-in zoom-in-95 duration-200`}>
              <div className="w-full flex items-center justify-between pb-2 border-b border-slate-500/20 mb-4">
                <span className={`text-[11px] font-extrabold uppercase tracking-wider ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"}`}>Trình chiếu demo xuất báo cáo</span>
                <button
                  type="button"
                  onClick={() => setIsVideoMaximized(false)}
                  className={`px-3 py-1.5 rounded-lg border transition active:scale-95 flex items-center gap-1.5 text-xs font-bold cursor-pointer ${isDark ? "bg-[#263750]/30 border-[#263750] text-[#c2ae78] hover:bg-slate-900" : "bg-white border-[#dcd7cc] text-[#8c763e] hover:bg-slate-100"}`}
                >
                  <Minimize2 className="w-3.5 h-3.5" />
                  <span>Thu nhỏ</span>
                </button>
              </div>
              <div className="flex-1 w-full flex items-center justify-center overflow-hidden">
                <video
                  src="https://jmrjohuhxvywhipncyij.supabase.co/storage/v1/object/public/lectures/slide_tao_bao_cao_theo_mau.mp4"
                  controls
                  autoPlay
                  loop
                  muted
                  playsInline
                  className="w-full max-h-[82vh] rounded-xl border border-slate-500/20 object-contain shadow-lg"
                />
              </div>
            </div>
          )}
        </div>
      )
    },
    // SLIDE 6: TÍNH NĂNG 2 - TRỢ LÝ CHATBOT ĐA NHIỆM
    {
      title: "Tính Năng 2: Trợ Lý Chatbot Đa Nhiệm",
      subtitle: "Kịch bản demo: Đồng hành cùng thầy Triết (BGH trường THCS Nguyễn Du) đàm thoại với dữ liệu",
      type: "chatbot_rag",
      content: (
        <div className="w-full h-full relative flex items-center justify-center">
          {/* Normal Layout */}
          <div className={`grid grid-cols-1 lg:grid-cols-12 gap-8 items-center text-left w-full transition-opacity duration-300 ${isVideoMaximized ? "opacity-0 pointer-events-none" : "opacity-100"}`}>
            <div className="lg:col-span-4 space-y-4">
              <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold ${isDark ? "bg-[#2a4d9c]/20 text-[#6366f1] border-[#2a4d9c]/40" : "bg-[#eff2fc] text-[#2a4d9c] border-[#dce0f5]"} border`}>
                <MessageSquare className="w-3 h-3 text-[#2a4d9c] dark:text-[#6366f1]" /> Trải nghiệm đàm thoại
              </div>
              <h2 className={`text-2xl md:text-3xl font-extrabold tracking-tight leading-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
                Trợ Lý Chatbot Đa Nhiệm
              </h2>
              <p className={`leading-relaxed text-xs md:text-sm ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                Trợ lý thông minh hỗ trợ thầy Triết giải quyết tức thì 3 nhu cầu quản lý học thuật cốt lõi bằng hội thoại tự nhiên:
              </p>

              {/* Vertical Sub-tabs for the 3 Demo Cases */}
              <div className="flex flex-col gap-3 pt-1">
                {[
                  {
                    id: 0,
                    title: "Thầy Triết hỏi đáp & tóm tắt học vụ",
                    desc: "Xem nhanh kết quả Toán Khối 8 HK2 trường THCS Nguyễn Du",
                    saved: (
                      <>
                        ⚡ Xử lý trong <span className="text-emerald-600 dark:text-[#52b788] font-extrabold px-1 py-0.5 rounded bg-emerald-500/10 dark:bg-emerald-500/20">30 giây</span> (thay vì thầy Triết tốn 15-30 phút tra cứu Excel)
                      </>
                    )
                  },
                  {
                    id: 1,
                    title: "Thầy Triết kiểm duyệt đề thi",
                    desc: "Tải lên tệp đề thi PDF, check độ khó CDI & đối soát SGK",
                    saved: (
                      <>
                        ⚡ Thẩm định dưới <span className="text-emerald-600 dark:text-[#52b788] font-extrabold px-1 py-0.5 rounded bg-emerald-500/10 dark:bg-emerald-500/20">1 phút</span> (thay vì thầy Triết tốn 3-4 giờ đối soát với đề thi và ma trận đề)
                      </>
                    )
                  },
                  {
                    id: 2,
                    title: "Thầy Triết soạn báo cáo tự do",
                    desc: "Biên soạn và tải xuống báo cáo tương quan điểm số giữa hai môn Tiếng Anh và Ngữ văn của học sinh => Dùng để hướng nghiệp",
                    saved: (
                      <>
                        ⚡ Soạn thảo trong <span className="text-emerald-600 dark:text-[#52b788] font-extrabold px-1 py-0.5 rounded bg-emerald-500/10 dark:bg-emerald-500/20">45 giây</span> (thay vì thầy Triết tốn 3-4 giờ tổng hợp báo cáo)
                      </>
                    )
                  }
                ].map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveDemoTab(tab.id)}
                    className={`relative w-full p-2.5 md:p-3 rounded-xl border transition-all duration-200 text-left flex flex-col gap-1 cursor-pointer ${activeDemoTab === tab.id
                      ? isDark
                        ? "bg-[#2a4d9c]/15 border-[#6366f1] text-[#6366f1] scale-[1.01] shadow-sm"
                        : "bg-[#eff2fc]/90 border-[#2a4d9c] text-[#2a4d9c] scale-[1.01] shadow-xs"
                      : isDark
                        ? "bg-[#2a4d9c]/5 border-transparent text-slate-400 hover:bg-[#2a4d9c]/10 hover:border-[#6366f1]/40"
                        : "bg-white/80 border-[#dcd7cc]/60 text-[#4a5568] hover:bg-[#eff2fc]/60 hover:border-[#2a4d9c]/40"
                      }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold shrink-0 ${activeDemoTab === tab.id
                        ? (isDark ? "bg-[#6366f1]/25 text-[#6366f1]" : "bg-[#2a4d9c]/15 text-[#2a4d9c]")
                        : (isDark ? "bg-[#6366f1]/10 text-[#6366f1]/60" : "bg-[#2a4d9c]/5 text-[#2a4d9c]/60")
                        }`}>
                        {tab.id + 1}
                      </span>
                      <strong className={`text-xs md:text-[13px] font-bold ${activeDemoTab === tab.id
                        ? (isDark ? "text-slate-100" : "text-[#2a4d9c]")
                        : (isDark ? "text-slate-300" : "text-[#0f1e36]")
                        }`}>
                        {tab.title}
                      </strong>
                    </div>
                    <p className={`text-[10.5px] md:text-[11.5px] leading-relaxed ${activeDemoTab === tab.id ? (isDark ? "text-indigo-300" : "text-slate-600") : "text-slate-500 dark:text-slate-400"}`}>
                      {tab.desc}
                    </p>
                    <p className={`text-[9.5px] md:text-[10.5px] leading-relaxed mt-1 ${activeDemoTab === tab.id ? (isDark ? "text-slate-300" : "text-[#4a5568]") : "text-slate-500 dark:text-slate-400"}`}>
                      {tab.saved}
                    </p>

                    {/* Pulsing indicator arrow pointing to the video */}
                    {activeDemoTab === tab.id && (
                      <div className="absolute right-[-24px] top-1/2 -translate-y-1/2 z-20 hidden lg:block animate-pulse">
                        <ArrowRight className="w-5 h-5 text-[#2a4d9c] dark:text-[#6366f1]" />
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>

            <div className="lg:col-span-8 space-y-3">
              {/* Real Demo Video Player */}
              <div className="relative group">
                <div className={`p-2 rounded-2xl border ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-md"} overflow-hidden`}>
                  <div className="relative w-full aspect-video overflow-hidden rounded-xl bg-black animate-fade-in">
                    <video
                      key={activeDemoTab}
                      ref={mp4VideoRef}
                      src={
                        activeDemoTab === 0
                          ? "https://jmrjohuhxvywhipncyij.supabase.co/storage/v1/object/public/lectures/slide_chatbot_case_1.mp4"
                          : activeDemoTab === 1
                            ? "https://jmrjohuhxvywhipncyij.supabase.co/storage/v1/object/public/lectures/slide_chatbot_case_2.mp4"
                            : "https://jmrjohuhxvywhipncyij.supabase.co/storage/v1/object/public/lectures/slide_chatbot_case_3.mp4?t=1720521420"
                      }
                      controls
                      playsInline
                      onPlay={() => setIsMp4Playing(true)}
                      onPause={() => setIsMp4Playing(false)}
                      className="w-full h-full object-contain pointer-events-auto"
                    />
                  </div>
                  {/* Zoom overlay button */}
                  <button
                    type="button"
                    onClick={() => setIsVideoMaximized(true)}
                    className="absolute top-4 right-4 bg-black/60 hover:bg-[#8c763e] text-white p-2 rounded-full opacity-0 group-hover:opacity-100 transition duration-200 cursor-pointer z-10"
                    title="Phóng to video ra toàn slide"
                  >
                    <Maximize2 className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex items-center justify-between mt-1.5 gap-4">
                  <div className={`text-[10px] italic ${isDark ? "text-slate-500" : "text-[#8c763e]"}`}>
                    Hình ảnh thực tế: Trình diễn tác vụ hội thoại của thầy Triết. (Click nút kính lúp ở góc để Phóng to)
                  </div>
                  {activeDemoTab === 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        if (mp4VideoRef.current) {
                          if (mp4VideoRef.current.paused) {
                            mp4VideoRef.current.play();
                            setIsMp4Playing(true);
                          } else {
                            mp4VideoRef.current.pause();
                            setIsMp4Playing(false);
                          }
                        }
                      }}
                      className={`px-3.5 py-1.5 rounded-lg border flex items-center gap-1.5 text-[10.5px] font-extrabold transition duration-200 cursor-pointer shrink-0 ${isMp4Playing
                        ? "bg-red-500/10 border-red-500/20 text-red-650 hover:bg-red-500/20"
                        : isDark
                          ? "bg-[#c2ae78] text-[#070e1a] hover:bg-[#a38a4d]"
                          : "bg-[#0f1e36] text-[#faf9f6] hover:bg-[#8c763e]"
                        }`}
                    >
                      {isMp4Playing ? (
                        <>
                          <Pause className="w-3.5 h-3.5 fill-current" />
                          <span>Tạm dừng</span>
                        </>
                      ) : (
                        <>
                          <Play className="w-3.5 h-3.5 fill-current" />
                          <span>Phát video Demo</span>
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Maximized Overlay (Full Slide) */}
          {isVideoMaximized && (
            <div className={`absolute inset-0 z-50 flex flex-col justify-between p-6 ${isDark ? "bg-[#070e1a]" : "bg-[#f5f1e6]"} animate-in zoom-in-95 duration-200`}>
              <div className="w-full flex items-center justify-between pb-2 border-b border-slate-500/20 mb-4">
                <span className={`text-[11px] font-extrabold uppercase tracking-wider ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"}`}>
                  {activeDemoTab === 0
                    ? "Trình chiếu demo: Hỏi đáp & Tóm tắt học vụ"
                    : activeDemoTab === 1
                      ? "Trình chiếu: Thầy Triết kiểm duyệt độ khó đề thi"
                      : "Trình chiếu: Thầy Triết soạn báo cáo học tập tự do"}
                </span>
                <button
                  type="button"
                  onClick={() => setIsVideoMaximized(false)}
                  className={`px-3 py-1.5 rounded-lg border transition active:scale-95 flex items-center gap-1.5 text-xs font-bold cursor-pointer ${isDark ? "bg-[#263750]/30 border-[#263750] text-[#c2ae78] hover:bg-slate-900" : "bg-white border-[#dcd7cc] text-[#8c763e] hover:bg-slate-100"}`}
                >
                  <Minimize2 className="w-3.5 h-3.5" />
                  <span>Thu nhỏ</span>
                </button>
              </div>
              <div className="flex-1 w-full flex items-center justify-center overflow-hidden">
                <div className="relative w-full max-h-[82vh] aspect-video overflow-hidden rounded-xl border border-slate-500/20 shadow-lg bg-black">
                  <video
                    key={`max-${activeDemoTab}`}
                    src={
                      activeDemoTab === 0
                        ? "https://jmrjohuhxvywhipncyij.supabase.co/storage/v1/object/public/lectures/slide_chatbot_case_1.mp4"
                        : activeDemoTab === 1
                          ? "https://jmrjohuhxvywhipncyij.supabase.co/storage/v1/object/public/lectures/slide_chatbot_case_2.mp4"
                          : "https://jmrjohuhxvywhipncyij.supabase.co/storage/v1/object/public/lectures/slide_chatbot_case_3.mp4?t=1720521420"
                    }
                    controls
                    autoPlay
                    playsInline
                    className="w-full h-full object-contain pointer-events-auto"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      )
    },
    // SLIDE 7: TÍNH NĂNG 3 - LIÊN KẾT ĐỀ THI & CỘT ĐIỂM
    {
      title: "Tính Năng 3: Liên Kết Đề Thi & Cột Điểm Độc Đáo",
      subtitle: "Kịch bản demo: Đồng hành cùng thầy Triết (BGH trường THCS Nguyễn Du) đối soát và liên kết đề thi",
      type: "linking_exams",
      content: (
        <div className="w-full">
          {/* Normal Layout */}
          <div className={`grid grid-cols-1 lg:grid-cols-12 gap-8 items-start text-left w-full transition-opacity duration-300 ${isVideoMaximized ? "opacity-0 pointer-events-none" : "opacity-100"}`}>
            <div className="lg:col-span-4 space-y-4">
              <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold ${isDark ? "bg-[#2d6a4f]/20 text-[#52b788] border-[#2d6a4f]/40" : "bg-[#f0f4f0] text-[#2d6a4f] border-[#cbdcd0]"} border`}>
                <BarChart2 className="w-3 h-3 text-[#2d6a4f] dark:text-[#52b788]" /> Tam giác hóa học thuật
              </div>
              <h2 className={`text-2xl md:text-3xl font-extrabold tracking-tight leading-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
                Liên Kết Đề Thi & Cột Điểm
              </h2>
              <p className={`leading-relaxed text-xs md:text-sm ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                Đối soát độ khó đề thi thực tế (EDI) với độ khó thiết kế Bloom (CDI) để phát hiện bất thường học thuật.
              </p>

              <div className="space-y-3.5 relative pl-4 border-l border-slate-200 dark:border-slate-800 ml-2 py-0.5">
                {/* Step 1 */}
                <div className="relative">
                  <div className="absolute left-[-22px] top-0.5 w-4.5 h-4.5 rounded-full bg-[#2a4d9c] text-white flex items-center justify-center text-[9.5px] font-extrabold shadow-xs">1</div>
                  <div className="text-left">
                    <strong className={`text-[11.5px] md:text-[12.5px] font-extrabold block ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Gắn Đề Vào Cột Điểm</strong>
                    <p className={`text-[10px] md:text-[11px] leading-tight ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                      Bắt buộc thầy/cô bộ môn tải đề PDF và gắn trực tiếp vào cột điểm.
                    </p>
                  </div>
                </div>

                {/* Step 2 */}
                <div className="relative">
                  <div className="absolute left-[-22px] top-0.5 w-4.5 h-4.5 rounded-full bg-[#2d6a4f] text-white flex items-center justify-center text-[9.5px] font-extrabold shadow-xs">2</div>
                  <div className="text-left">
                    <strong className={`text-[11.5px] md:text-[12.5px] font-extrabold block ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>AI Phân Tích & Đối Soát</strong>
                    <p className={`text-[10px] md:text-[11px] leading-tight ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                      AI đối soát ma trận Bloom (CDI) và phổ điểm thực tế (EDI) để tìm bất thường.
                    </p>
                  </div>
                </div>

                {/* Step 3 */}
                <div className="relative">
                  <div className="absolute left-[-22px] top-0.5 w-4.5 h-4.5 rounded-full bg-[#9c4141] text-white flex items-center justify-center text-[9.5px] font-extrabold shadow-xs">3</div>
                  <div className="text-left">
                    <strong className={`text-[11.5px] md:text-[12.5px] font-extrabold block ${isDark ? "text-[#c97575]" : "text-[#9c4141]"}`}>BGH Dashboard Cảnh Báo</strong>
                    <p className={`text-[10px] md:text-[11px] leading-tight ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                      Thầy Triết (BGH) nhận cảnh báo phân kỳ nếu có dấu hiệu bất thường học thuật.
                    </p>
                  </div>
                </div>
              </div>

              {/* Ghi chú CDI, EDI & Bloom */}
              <div className={`p-2.5 rounded-xl border text-[9px] leading-relaxed ${isDark ? "bg-[#070e1a]/60 border-[#263750] text-slate-400" : "bg-[#fcfaf5] border-[#dcd7cc] text-[#4a5568]"}`}>
                <div className="flex flex-col gap-1.5">
                  <div>
                    <strong className="text-amber-600 dark:text-amber-450">● Ma trận Bloom:</strong> Phân loại câu hỏi thành 4 cấp độ tư duy: Nhận biết, Thông hiểu, Vận dụng, Vận dụng cao (xác định trọng số độ khó thiết kế).
                  </div>
                  <div>
                    <strong className="text-[#2a4d9c] dark:text-[#6366f1]">● CDI (Độ khó thiết kế):</strong> Đánh giá từ ma trận Bloom của đề (Thang 0 - 1, càng gần 1 đề càng khó).
                  </div>
                  <div>
                    <strong className="text-emerald-600 dark:text-emerald-450">● EDI (Độ khó thực nghiệm):</strong> Đo lường từ phổ điểm học sinh: <code className="bg-slate-500/10 px-1 py-0.5 rounded text-[8px] font-mono">1 - (Điểm TB / 10)</code> (Thang 0 - 1).
                  </div>
                  <div className="border-t pt-1 border-slate-500/10 text-[8.5px] italic text-slate-550 flex items-center justify-between">
                    <span>💡 Ngưỡng an toàn phân kỳ: <strong className="text-red-650 dark:text-[#c97575]">|CDI - EDI| &le; 0.15</strong> (Vượt ngưỡng sẽ kích hoạt cờ cảnh báo bất thường).</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="lg:col-span-8 space-y-3">
              <div className="relative group">
                <div className={`p-2 rounded-2xl border ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-md"} overflow-hidden relative aspect-video bg-black`}>
                  <video
                    src="https://jmrjohuhxvywhipncyij.supabase.co/storage/v1/object/public/lectures/slide_lien_ket_de_thi_va_cot_diem%20(1).mp4"
                    controls
                    playsInline
                    className="absolute inset-0 w-full h-full object-contain pointer-events-auto"
                  />
                  {/* Zoom overlay button */}
                  <button
                    type="button"
                    onClick={() => setIsVideoMaximized(true)}
                    className="absolute top-4 right-4 bg-black/60 hover:bg-[#8c763e] text-white p-2 rounded-full opacity-0 group-hover:opacity-100 transition duration-200 cursor-pointer z-10"
                    title="Phóng to video ra toàn slide"
                  >
                    <Maximize2 className="w-4 h-4" />
                  </button>
                </div>
                <div className={`text-[9px] text-center italic mt-1 ${isDark ? "text-slate-500" : "text-[#8c763e]"}`}>
                  Hình ảnh thực tế: AI đối soát độ khó đề thi (CDI vs EDI) & cảnh báo BGH.
                </div>
              </div>
            </div>
          </div>

          {/* Maximized Overlay (Full Slide) */}
          {isVideoMaximized && (
            <div className={`absolute inset-0 z-50 flex flex-col justify-between p-6 ${isDark ? "bg-[#070e1a]" : "bg-[#f5f1e6]"} animate-in zoom-in-95 duration-200`}>
              <div className="w-full flex items-center justify-between pb-2 border-b border-slate-500/20 mb-4">
                <span className={`text-[11px] font-extrabold uppercase tracking-wider ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"}`}>Trình chiếu demo kiểm duyệt đề thi</span>
                <button
                  type="button"
                  onClick={() => setIsVideoMaximized(false)}
                  className={`px-3 py-1.5 rounded-lg border transition active:scale-95 flex items-center gap-1.5 text-xs font-bold cursor-pointer ${isDark ? "bg-[#263750]/30 border-[#263750] text-[#c2ae78] hover:bg-slate-900" : "bg-white border-[#dcd7cc] text-[#8c763e] hover:bg-slate-100"}`}
                >
                  <Minimize2 className="w-3.5 h-3.5" />
                  <span>Thu nhỏ</span>
                </button>
              </div>
              <div className="flex-1 w-full flex items-center justify-center overflow-hidden">
                <div className="relative w-full max-h-[82vh] aspect-video overflow-hidden rounded-xl border border-slate-500/20 shadow-lg bg-black">
                  <iframe
                    src="https://www.youtube.com/embed/k_jbxOH0-uc?autoplay=1&mute=1&loop=1&playlist=k_jbxOH0-uc&modestbranding=1&rel=0&iv_load_policy=3&controls=1"
                    title="Demo Video Exam Validation Full"
                    frameBorder="0"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    allowFullScreen
                    className="absolute top-[-5%] left-[-5%] w-[110%] h-[110%] pointer-events-auto"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      )
    },
    // SLIDE 7.5: TÍNH NĂNG 3.1 - CẢNH BÁO BẤT THƯỜNG & CHÈN ÉP
    {
      title: "Tính Năng 3.5: Cảnh Báo Bất Thường Học Thuật & Chèn Ép",
      subtitle: "Hệ thống tự động phát hiện và cảnh báo các dấu hiệu chèn ép điểm số học sinh hoặc lệch pha chất lượng dạy học",
      type: "fairness_alert",
      content: (
        <div className="w-full">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center text-left w-full">
            <div className="lg:col-span-5 space-y-4">
              <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold ${isDark ? "bg-red-500/20 text-[#c97575] border-red-500/40" : "bg-[#fdf2f2] text-red-700 border-[#fbd5d5]"} border`}>
                <ShieldAlert className="w-3 h-3 text-red-650" /> Đảm bảo công bằng học thuật
              </div>
              <h2 className={`text-2xl md:text-3xl font-extrabold tracking-tight leading-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
                Cảnh Báo Chèn Ép & Gap Điểm
              </h2>
              <p className={`leading-relaxed text-xs md:text-sm ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                Hỗ trợ Ban giám hiệu phát hiện kịp thời các hiện tượng lệch pha nghiêm trọng giữa chất lượng đề thi của giáo viên bộ môn và kết quả làm bài thực tế của học sinh.
              </p>

              <div className="space-y-3.5">
                <div className={`p-3 rounded-xl border transition-all duration-200 ${isDark ? "bg-red-950/10 border-red-900/30" : "bg-red-50/50 border-red-100 shadow-xs"}`}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="w-2 h-2 rounded-full bg-red-500 shrink-0" />
                    <strong className={`text-xs md:text-[13px] font-extrabold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Cảnh báo chèn ép điểm số</strong>
                  </div>
                  <p className={`text-[10px] md:text-[11.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                    Phát hiện các trường hợp đề thi được AI đánh giá là ở mức Nhận biết - Thông hiểu (dễ) nhưng phổ điểm lớp học bị chèn ép rất thấp bất thường (lệch pha EDI lớn).
                  </p>
                </div>

                <div className={`p-3 rounded-xl border transition-all duration-200 ${isDark ? "bg-[#8c763e]/5 border-[#8c763e]/15" : "bg-[#faf6e8] border-[#ebdcb0]/80 shadow-xs"}`}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                    <strong className={`text-xs md:text-[13px] font-extrabold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Can thiệp và Đối soát tức thời</strong>
                  </div>
                  <p className={`text-[10px] md:text-[11.5px] leading-relaxed ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                    Giúp Ban giám hiệu có số liệu đối chứng khoa học để chất vấn chuyên môn bộ môn, đảm bảo quyền lợi và sự công bằng học tập cho học sinh toàn trường.
                  </p>
                </div>
              </div>
            </div>

            <div className="lg:col-span-7 space-y-3">
              <div className="relative group">
                <div className={`p-2 rounded-2xl border ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-md"} overflow-hidden bg-black/5`}>
                  <img
                    src="/img/canh_bao_cong_bang.png"
                    alt="Cảnh báo công bằng học thuật"
                    className="w-full rounded-xl aspect-video object-contain"
                  />
                </div>
                <div className={`text-[9.5px] text-center italic mt-1.5 ${isDark ? "text-slate-500" : "text-[#8c763e]"}`}>
                  Hình ảnh thực tế: Dashboard BGH nhận nhãn cảnh báo lệch pha và nguy cơ chèn ép điểm số.
                </div>
              </div>
            </div>
          </div>
        </div>
      )
    },
    // SLIDE 8: TÍNH NĂNG 3.8 - TẠO MA TRẬN & ĐỀ THI TỰ ĐỘNG
    {
      title: "Tính Năng 3.8: Tạo Ma Trận & Thiết Kế Đề Thi Tự Động",
      subtitle: "Xây dựng ma trận phân bố câu hỏi và đề thi gợi ý chuẩn hóa từ chương trình dạy học thực tế",
      type: "matrix_generation",
      content: (
        <div className="w-full">
          {/* Normal Layout */}
          <div className={`grid grid-cols-1 lg:grid-cols-12 gap-8 items-center text-left w-full transition-opacity duration-300 ${isVideoMaximized ? "opacity-0 pointer-events-none" : "opacity-100"}`}>
            <div className="lg:col-span-4 space-y-4">
              <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold ${isDark ? "bg-[#2d6a4f]/20 text-[#52b788] border-[#2d6a4f]/40" : "bg-[#f0f4f0] text-[#2d6a4f] border-[#cbdcd0]"} border`}>
                <Target className="w-3 h-3 text-[#2d6a4f] dark:text-[#52b788]" /> Thiết kế học thuật
              </div>
              <h2 className={`text-2xl md:text-3xl font-extrabold tracking-tight leading-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
                Tạo Ma Trận & Đề Thi
              </h2>
              <p className={`leading-relaxed text-xs md:text-sm ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                Tự động hóa quy trình thiết kế học thuật. Hệ thống đối chiếu chương trình dạy học thực tế để giáo viên chọn bài giảng cần kiểm tra, tự động tính toán ma trận độ khó và sinh đề thi gợi ý chuẩn hóa.
              </p>

              <div className="space-y-3.5">
                <div className={`p-3 rounded-xl border flex gap-3 items-start transition-all duration-200 ${isDark ? "bg-slate-900/50 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-xs"}`}>
                  <div className="w-6 h-6 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center shrink-0">
                    <span className="text-[10px] font-black">1</span>
                  </div>
                  <div>
                    <strong className={`text-xs md:text-[13px] font-bold block ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Đối chiếu Chương trình dạy</strong>
                    <span className="text-[9.5px] md:text-[10.5px] text-slate-550 dark:text-slate-400 block leading-tight mt-1">
                      Hệ thống quét CSDL lịch sử dạy thực tế để giáo viên chọn chính xác các bài giảng cần kiểm tra.
                    </span>
                  </div>
                </div>

                <div className={`p-3 rounded-xl border flex gap-3 items-start transition-all duration-200 ${isDark ? "bg-slate-900/50 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-xs"}`}>
                  <div className="w-6 h-6 rounded-full bg-blue-500/10 text-blue-500 flex items-center justify-center shrink-0">
                    <span className="text-[10px] font-black">2</span>
                  </div>
                  <div>
                    <strong className={`text-xs md:text-[13px] font-bold block ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Matrix Agent tự động hóa</strong>
                    <span className="text-[9.5px] md:text-[10.5px] text-slate-550 dark:text-slate-400 block leading-tight mt-1">
                      Tính toán số lượng câu hỏi Nhận biết/Thông hiểu/Vận dụng cân đối theo chuẩn phân bố độ khó và tự sinh đề kiểm tra gợi ý.
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="lg:col-span-8 space-y-3">
              <div className="relative group">
                <div className={`p-2 rounded-2xl border ${isDark ? "bg-[#070e1a]/50 border-[#263750]" : "bg-white border-[#dcd7cc] shadow-md"} overflow-hidden relative aspect-video bg-black`}>
                  <video
                    src="https://jmrjohuhxvywhipncyij.supabase.co/storage/v1/object/public/lectures/Demo_build_exam.mp4"
                    controls
                    playsInline
                    className="absolute inset-0 w-full h-full object-contain pointer-events-auto"
                  />
                  {/* Zoom overlay button */}
                  <button
                    type="button"
                    onClick={() => setIsVideoMaximized(true)}
                    className="absolute top-4 right-4 bg-black/60 hover:bg-[#8c763e] text-white p-2 rounded-full opacity-0 group-hover:opacity-100 transition duration-200 cursor-pointer z-10"
                    title="Phóng to video ra toàn slide"
                  >
                    <Maximize2 className="w-4 h-4" />
                  </button>
                </div>
                <div className={`text-[9.5px] text-center italic mt-1.5 ${isDark ? "text-slate-500" : "text-[#8c763e]"}`}>
                  Hình ảnh thực tế: AI tự động thiết lập ma trận kiểm tra và sinh đề thi tương ứng từ bài giảng đã dạy.
                </div>
              </div>
            </div>
          </div>

          {/* Maximized Overlay (Full Slide) */}
          {isVideoMaximized && (
            <div className={`absolute inset-0 z-50 flex flex-col justify-between p-6 ${isDark ? "bg-[#070e1a]" : "bg-[#f5f1e6]"} animate-in zoom-in-95 duration-200`}>
              <div className="w-full flex items-center justify-between pb-2 border-b border-slate-500/20 mb-4">
                <span className={`text-[11px] font-extrabold uppercase tracking-wider ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"}`}>Trình chiếu demo tạo ma trận & đề thi</span>
                <button
                  type="button"
                  onClick={() => setIsVideoMaximized(false)}
                  className={`px-3 py-1.5 rounded-lg border transition active:scale-95 flex items-center gap-1.5 text-xs font-bold cursor-pointer ${isDark ? "bg-[#263750]/30 border-[#263750] text-[#c2ae78] hover:bg-slate-900" : "bg-white border-[#dcd7cc] text-[#8c763e] hover:bg-slate-100"}`}
                >
                  <Minimize2 className="w-3.5 h-3.5" />
                  <span>Thu nhỏ</span>
                </button>
              </div>
              <div className="flex-1 w-full flex items-center justify-center overflow-hidden">
                <div className="relative w-full max-h-[82vh] aspect-video overflow-hidden rounded-xl border border-slate-500/20 shadow-lg bg-black">
                  <video
                    src="https://jmrjohuhxvywhipncyij.supabase.co/storage/v1/object/public/lectures/Demo_build_exam.mp4"
                    controls
                    autoPlay
                    playsInline
                    className="w-full h-full object-contain pointer-events-auto"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      )
    },
    // SLIDE 9: TÍNH NĂNG 4 - ĐÁNH GIÁ TIẾT DẠY QUA CAMERA & AI
    {
      title: "Tính Năng 4: Đánh Giá Tiết Dạy Qua Camera & AI",
      subtitle: "Giải pháp khách quan hóa chất lượng bài giảng lớp học không cần dự giờ thủ công",
      type: "camera_assessment",
      content: (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center text-left w-full">
          <div className="lg:col-span-5 space-y-4">
            <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold ${isDark ? "bg-[#8c763e]/20 text-[#c2ae78] border-[#8c763e]/40" : "bg-[#faf6e8] text-[#8c763e] border-[#ebdcb0]"} border`}>
              <Video className="w-3 h-3 text-[#8c763e] dark:text-[#c2ae78]" /> Giám sát lớp học
            </div>
            <h2 className={`text-2xl md:text-3xl font-extrabold tracking-tight leading-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
              Đánh giá tiết dạy
            </h2>
            <p className={`leading-relaxed text-xs md:text-sm ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
              Hệ thống xử lý âm thanh tự động, tối ưu hóa thời gian và nguồn lực quản lý cho thầy Triết (BGH).
            </p>

            <div className="space-y-3.5">
              {/* Metric 1 - Clock Capsule */}
              <div className={`p-2 pl-2 pr-5 rounded-full border flex items-center justify-between transition-all duration-200 hover:border-[#10b981] ${isDark ? "bg-[#10b981]/5 border-[#10b981]/15" : "bg-[#f0faf4] border-[#d0ecd8]/80 shadow-xs"}`}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center bg-white dark:bg-slate-800 shadow-[0_4px_12px_rgba(0,0,0,0.06)] shrink-0 border border-slate-100 dark:border-slate-850">
                    <Clock className="w-5 h-5 text-emerald-500" />
                  </div>
                  <strong className={`text-xs md:text-sm font-extrabold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Tốc độ & Độ chính xác</strong>
                </div>
                <div className="text-right">
                  <span className="text-xs md:text-sm font-black text-emerald-600 dark:text-emerald-450 block">1 phút (Độ chính xác 92%)</span>
                  <span className="text-[9px] md:text-[10px] text-slate-550 font-medium block">Thay vì 20 giây (Độ chính xác 89%)</span>
                </div>
              </div>

              {/* Metric 2 - Target Capsule */}
              <div className={`p-2 pl-2 pr-5 rounded-full border flex items-center justify-between transition-all duration-200 hover:border-[#8c763e] ${isDark ? "bg-[#8c763e]/5 border-[#8c763e]/15" : "bg-[#faf6e8] border-[#ebdcb0]/80 shadow-xs"}`}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center bg-white dark:bg-slate-800 shadow-[0_4px_12px_rgba(0,0,0,0.06)] shrink-0 border border-slate-100 dark:border-slate-850">
                    <Target className="w-5 h-5 text-amber-550" />
                  </div>
                  <strong className={`text-xs md:text-sm font-extrabold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Kiểm thử & Độ tin cậy</strong>
                </div>
                <div className="text-right">
                  <span className="text-xs md:text-sm font-black text-[#8c763e] dark:text-[#c2ae78] block">3 loại tệp MP3</span>
                  <span className="text-[9px] md:text-[10px] text-slate-550 font-medium block">Chất lượng cao, chất lượng thấp và chất lượng thấp và bị nén</span>
                </div>
              </div>

              {/* Metric 3 - Tag Capsule */}
              <div className={`p-2 pl-2 pr-5 rounded-full border flex items-center justify-between transition-all duration-200 hover:border-[#a855f7] ${isDark ? "bg-[#a855f7]/5 border-[#a855f7]/15" : "bg-[#f4effa] border-[#ecdcf2]/80 shadow-xs"}`}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center bg-white dark:bg-slate-800 shadow-[0_4px_12px_rgba(0,0,0,0.06)] shrink-0 border border-slate-100 dark:border-slate-850">
                    <Tag className="w-5 h-5 text-purple-500" />
                  </div>
                  <strong className={`text-xs md:text-sm font-extrabold ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Tối ưu hóa chi phí</strong>
                </div>
                <div className="text-right">
                  <span className="text-xs md:text-sm font-black text-purple-600 dark:text-[#a855f7] block">488đ - 2.248đ</span>
                  <span className="text-[9px] md:text-[10px] text-slate-550 font-medium block">Cho mỗi tiết dạy (tiết kiệm vượt trội)</span>
                </div>
              </div>
            </div>
          </div>

          <div className="lg:col-span-7 flex flex-col items-center">
            {/* Interactive Luồng Workflow Diagram - Borderless */}
            <div className="w-full relative">
              <div className="relative w-full h-[300px]">
                <svg width="100%" height="100%" viewBox="0 0 620 300" preserveAspectRatio="xMidYMid meet" className="overflow-visible">
                  {/* Default lines */}
                  <path
                    d="M 180,90 C 220,90 220,135 250,135"
                    fill="none"
                    stroke={isDark ? "#263750" : "#dcd7cc"}
                    strokeWidth="2"
                  />
                  <path
                    d="M 180,210 C 220,210 220,165 250,165"
                    fill="none"
                    stroke={isDark ? "#263750" : "#dcd7cc"}
                    strokeWidth="2"
                  />
                  <path
                    d="M 380,150 L 415,150"
                    fill="none"
                    stroke={isDark ? "#263750" : "#dcd7cc"}
                    strokeWidth="2"
                  />
                  <path
                    d="M 415,150 C 420,150 420,90 425,90"
                    fill="none"
                    stroke={isDark ? "#263750" : "#dcd7cc"}
                    strokeWidth="2"
                  />
                  <path
                    d="M 415,150 C 420,150 420,210 425,210"
                    fill="none"
                    stroke={isDark ? "#263750" : "#dcd7cc"}
                    strokeWidth="2"
                  />

                  {/* Translucent Gold Arrow Head pointing right */}
                  <path
                    d="M 378,140 L 405,150 L 378,160 Z"
                    fill={isDark ? "#c2ae78" : "#8c763e"}
                    opacity="0.15"
                  />

                  {/* Entry and Exit Connection Dots */}
                  <circle cx="250" cy="135" r="3.5" fill="#3b82f6" />
                  <circle cx="250" cy="165" r="3.5" fill="#d97706" />
                  <circle cx="415" cy="150" r="3.5" fill="#10b981" />
                  <circle cx="425" cy="90" r="3.5" fill="#10b981" />
                  <circle cx="425" cy="210" r="3.5" fill="#10b981" />

                  {/* Active glowing flow lines */}
                  {activePath === "upload" && (
                    <>
                      <path
                        d="M 180,90 C 220,90 220,135 250,135"
                        fill="none"
                        stroke={isDark ? "#6366f1" : "#2a4d9c"}
                        strokeWidth="3.5"
                        className="animated-flow-line"
                        strokeDasharray="6,4"
                      />
                      <path
                        d="M 380,150 L 415,150"
                        fill="none"
                        stroke={isDark ? "#34d399" : "#10b981"}
                        strokeWidth="3.5"
                        className="animated-flow-line"
                        strokeDasharray="6,4"
                      />
                      <path
                        d="M 415,150 C 420,150 420,90 425,90"
                        fill="none"
                        stroke={isDark ? "#34d399" : "#10b981"}
                        strokeWidth="3.5"
                        className="animated-flow-line"
                        strokeDasharray="6,4"
                      />
                      <path
                        d="M 415,150 C 420,150 420,210 425,210"
                        fill="none"
                        stroke={isDark ? "#34d399" : "#10b981"}
                        strokeWidth="3.5"
                        className="animated-flow-line"
                        strokeDasharray="6,4"
                      />
                    </>
                  )}
                  {activePath === "camera" && (
                    <>
                      <path
                        d="M 180,210 C 220,210 220,165 250,165"
                        fill="none"
                        stroke={isDark ? "#c2ae78" : "#8c763e"}
                        strokeWidth="3.5"
                        className="animated-flow-line"
                        strokeDasharray="6,4"
                      />
                      <path
                        d="M 380,150 L 415,150"
                        fill="none"
                        stroke={isDark ? "#34d399" : "#10b981"}
                        strokeWidth="3.5"
                        className="animated-flow-line"
                        strokeDasharray="6,4"
                      />
                      <path
                        d="M 415,150 C 420,150 420,90 425,90"
                        fill="none"
                        stroke={isDark ? "#34d399" : "#10b981"}
                        strokeWidth="3.5"
                        className="animated-flow-line"
                        strokeDasharray="6,4"
                      />
                      <path
                        d="M 415,150 C 420,150 420,210 425,210"
                        fill="none"
                        stroke={isDark ? "#34d399" : "#10b981"}
                        strokeWidth="3.5"
                        className="animated-flow-line"
                        strokeDasharray="6,4"
                      />
                    </>
                  )}

                  {/* Flow labels inside diagram */}
                  {activePath === "upload" && (
                    <g transform="translate(192, 85)">
                      <rect x="0" y="0" width="60" height="15" rx="4" fill={isDark ? "#1e1b4b" : "#eff2fc"} stroke={isDark ? "#6366f1" : "#2a4d9c"} strokeWidth="1" />
                      <text x="30" y="10" textAnchor="middle" fontSize="8" fontWeight="bold" fill={isDark ? "#a5b4fc" : "#2a4d9c"}>Tải MP3</text>
                    </g>
                  )}
                  {activePath === "camera" && (
                    <g transform="translate(182, 175)">
                      <rect x="0" y="0" width="80" height="15" rx="4" fill={isDark ? "#451a03" : "#faf6e8"} stroke={isDark ? "#c2ae78" : "#8c763e"} strokeWidth="1" />
                      <text x="40" y="10" textAnchor="middle" fontSize="7" fontWeight="bold" fill={isDark ? "#fde047" : "#8c763e"}>Cắt MP4 &rarr; MP3</text>
                    </g>
                  )}

                  {/* Node 1.1: GV Up MP3 */}
                  <foreignObject x="10" y="40" width="200" height="100" className="pointer-events-auto">
                    <div
                      onMouseEnter={() => setActivePath("upload")}
                      className="flex items-center gap-3 text-left cursor-pointer h-full"
                    >
                      <div className={`w-12 h-12 rounded-full flex items-center justify-center bg-white dark:bg-slate-800 shadow-[0_8px_20px_rgba(0,0,0,0.06)] border ${activePath === "upload" ? "border-blue-500 scale-105" : "border-slate-100 dark:border-slate-800"} transition-all duration-200`}>
                        <Mic className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                      </div>
                      <div>
                        <strong className="text-[11px] font-extrabold text-[#0f1e36] dark:text-slate-100 block leading-tight">GV Chủ Động<br />Up MP3</strong>
                        <span className="text-[9px] text-slate-500 dark:text-slate-400 block mt-0.5 leading-tight">Ghi âm &amp;<br />âm thoại</span>
                      </div>
                    </div>
                  </foreignObject>

                  {/* Node 1.2: BGH Lịch học */}
                  <foreignObject x="10" y="160" width="200" height="100" className="pointer-events-auto">
                    <div
                      onMouseEnter={() => setActivePath("camera")}
                      className="flex items-center gap-3 text-left cursor-pointer h-full"
                    >
                      <div className={`w-12 h-12 rounded-full flex items-center justify-center bg-white dark:bg-slate-800 shadow-[0_8px_20px_rgba(0,0,0,0.06)] border ${activePath === "camera" ? "border-[#c2ae78] scale-105" : "border-slate-100 dark:border-slate-800"} transition-all duration-200`}>
                        <Video className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                      </div>
                      <div>
                        <strong className="text-[11px] font-extrabold text-[#0f1e36] dark:text-slate-100 block leading-tight">Lịch Học &amp;<br />Camera MP4</strong>
                        <span className="text-[9px] text-slate-550 dark:text-slate-400 block mt-0.5 leading-tight">Trích xuất MP3<br />bài giảng</span>
                      </div>
                    </div>
                  </foreignObject>

                  {/* Node 2: AI Engine - Glowing Concentric Circles */}
                  <foreignObject x="220" y="50" width="200" height="200" className="pointer-events-none">
                    <div className="w-full h-full flex items-center justify-center relative">
                      {/* Ambient glow circles */}
                      <div className="absolute w-44 h-44 rounded-full border border-purple-500/10 dark:border-purple-400/5 animate-pulse" />
                      <div className="absolute w-38 h-38 rounded-full border border-purple-500/20 dark:border-purple-400/10" />
                      <div className="absolute w-32 h-32 rounded-full border border-purple-500/30 dark:border-purple-400/20 shadow-[0_0_20px_rgba(168,85,247,0.12)] bg-white/5 dark:bg-purple-950/5" />

                      {/* Center core */}
                      <div className="absolute w-26 h-26 rounded-full bg-white dark:bg-slate-900 shadow-[0_10px_25px_rgba(109,48,160,0.12)] border border-purple-500/30 flex flex-col items-center justify-center p-2 text-center z-10">
                        <div className="flex items-center gap-0.5 text-purple-600 dark:text-[#a855f7] mb-1">
                          <span className="w-[2px] h-3 bg-purple-500 rounded-full animate-bounce delay-75" />
                          <span className="w-[2px] h-5 bg-purple-600 rounded-full animate-bounce delay-150" />
                          <span className="w-[2px] h-2 bg-purple-400 rounded-full animate-bounce" />
                          <span className="w-[2px] h-4 bg-purple-500 rounded-full animate-bounce delay-300" />
                        </div>
                        <strong className="text-[9.5px] md:text-[10.5px] font-black text-purple-600 dark:text-[#a855f7] tracking-wider block">EDUOWL AI ENGINE</strong>
                        <span className="text-[8px] text-slate-550 dark:text-slate-400 block mt-1 leading-none font-medium">Xử lý thông minh<br />&amp; tự động</span>
                      </div>
                    </div>
                  </foreignObject>

                  {/* Node 3.1: Brain Output */}
                  <foreignObject x="425" y="40" width="200" height="100" className="pointer-events-auto">
                    <div className="flex items-center gap-3 text-left h-full">
                      <div className="w-12 h-12 rounded-full flex items-center justify-center bg-white dark:bg-slate-800 shadow-[0_8px_20px_rgba(0,0,0,0.06)] border border-emerald-100 dark:border-slate-800">
                        <Cpu className="w-5 h-5 text-emerald-500" />
                      </div>
                      <div>
                        <strong className="text-[11px] font-extrabold text-[#0f1e36] dark:text-slate-100 block leading-tight">Báo cáo thông minh</strong>
                        <span className="text-[9px] text-slate-550 dark:text-slate-400 block mt-0.5 leading-tight">điểm số &amp; phân tích<br />tự động</span>
                      </div>
                    </div>
                  </foreignObject>

                  {/* Node 3.2: Shield Output */}
                  <foreignObject x="425" y="160" width="200" height="100" className="pointer-events-auto">
                    <div className="flex items-center gap-3 text-left h-full">
                      <div className="w-12 h-12 rounded-full flex items-center justify-center bg-white dark:bg-slate-800 shadow-[0_8px_20px_rgba(0,0,0,0.06)] border border-emerald-100 dark:border-slate-800">
                        <ShieldAlert className="w-5 h-5 text-emerald-500" />
                      </div>
                      <div>
                        <strong className="text-[11px] font-extrabold text-[#0f1e36] dark:text-slate-100 block leading-tight">Tối ưu vận hành</strong>
                        <span className="text-[9px] text-slate-550 dark:text-slate-400 block mt-0.5 leading-tight">tiết kiệm thời gian<br />&amp; chi phí</span>
                      </div>
                    </div>
                  </foreignObject>
                </svg>
              </div>
            </div>
          </div>
        </div>
      )
    },
    // SLIDE 9: LỘ TRÌNH TRIỂN KHAI (ROADMAP)
    {
      title: "", // Hidden to use custom header layout
      subtitle: "",
      type: "roadmap",
      content: (
        <div className="w-full flex flex-col justify-between py-2 text-left relative max-w-5xl mx-auto">
          <style>{`
            @keyframes float-owl {
              0%, 100% { transform: translateY(0px); }
              50% { transform: translateY(-6px); }
            }
          `}</style>
          {/* Custom Header Layout with Owl Brand */}
          <div className="flex justify-between items-start mb-6">
            <div className="space-y-1 md:space-y-2">
              {/* Badge */}
              <div className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-wider ${isDark ? "bg-[#c2ae78]/10 text-[#c2ae78] border-[#c2ae78]/25" : "bg-[#8c763e]/10 text-[#8c763e] border-[#8c763e]/20"} border`}>
                <Calendar className="w-3 h-3" /> Roadmap
              </div>
              <h2 className={`text-2xl md:text-3xl font-extrabold tracking-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
                Lộ Trình Phát Triển
              </h2>
              <p className={`text-xs md:text-sm ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                Hành trình từng bước xây dựng hệ thống thông minh cho trường học
              </p>
            </div>
            
            {/* Cute EduOwl floating logo illustration */}
            <div className="shrink-0 -mt-2">
              <img
                src="/logo.svg"
                className="w-16 h-16 md:w-20 md:h-20 object-contain drop-shadow-[0_8px_16px_rgba(59,130,246,0.15)] animate-[float-owl_4s_ease-in-out_infinite]"
                alt="EduOwl Logo"
              />
            </div>
          </div>

          {/* Dotted curve connecting the steps (L165 top is alignment height for the numbers) */}
          <div className="absolute top-[170px] left-[8%] right-[8%] h-[30px] pointer-events-none z-0 hidden lg:block">
            <svg className="w-full h-full" viewBox="0 0 800 40" fill="none" preserveAspectRatio="none">
              <path
                d="M 10,20 C 130,-5 270,45 400,20 C 530,-5 670,45 790,20"
                stroke={isDark ? "rgba(148,163,184,0.2)" : "rgba(107,114,128,0.15)"}
                strokeWidth="2.5"
                strokeDasharray="6 8"
                fill="none"
              />
            </svg>
          </div>

          {/* Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 relative z-10 w-full">
            {[
              {
                step: "01",
                title: "Trợ Lý Học Thuật AI",
                desc: "Triển khai hệ thống đối soát dữ liệu, liên kết bảng điểm và tự động hóa biên soạn báo cáo mẫu cho BGH.",
                status: "⚡ Nền tảng khởi đầu",
                color: "blue",
                bgGrad: "from-blue-500/5 to-blue-500/0",
                icon: (
                  <div className="relative">
                    <Cpu className="w-10 h-10 text-blue-650 dark:text-blue-400" />
                    <GraduationCap className="w-6 h-6 text-indigo-500 absolute -top-4 -right-3 rotate-12" />
                  </div>
                ),
                cardStyle: isDark ? "bg-[#070e1a]/85 border-blue-500/30 hover:border-blue-500 hover:shadow-blue-950/20" : "bg-white border-blue-100 hover:border-blue-300 hover:shadow-blue-100/40",
                badgeStyle: "bg-blue-600 text-white border-white dark:border-[#070e1a]",
                pillStyle: "bg-blue-50 text-blue-600 dark:bg-blue-950/30 dark:text-blue-400"
              },
              {
                step: "02",
                title: "Sổ Đầu Bài A.I",
                desc: "Tự động số hóa, nhận xét tiết học, đánh giá chuyên cần và mức độ tương tác học tập của học sinh.",
                status: "🌐 Phân tích thông minh",
                color: "purple",
                bgGrad: "from-purple-500/5 to-purple-500/0",
                icon: (
                  <div className="relative">
                    <FileText className="w-10 h-10 text-purple-600 dark:text-purple-400" />
                    <span className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-purple-500 text-white text-[8px] font-black flex items-center justify-center border border-white dark:border-[#070e1a]">AI</span>
                  </div>
                ),
                cardStyle: isDark ? "bg-[#070e1a]/85 border-purple-500/30 hover:border-purple-500 hover:shadow-purple-950/20" : "bg-white border-purple-100 hover:border-purple-300 hover:shadow-purple-100/40",
                badgeStyle: "bg-purple-600 text-white border-white dark:border-[#070e1a]",
                pillStyle: "bg-purple-50 text-purple-650 dark:bg-purple-950/30 dark:text-purple-400"
              },
              {
                step: "03",
                title: "Giám Sát An Ninh AI",
                desc: "Tích hợp hệ thống camera nhận diện và cảnh báo sớm các hành vi xô xát, hút thuốc trong trường học.",
                status: "🛡️ An toàn - Chủ động",
                color: "amber",
                bgGrad: "from-amber-500/5 to-amber-500/0",
                icon: (
                  <div className="relative">
                    <Video className="w-10 h-10 text-amber-600 dark:text-amber-400" />
                    <Shield className="w-6 h-6 text-amber-550 absolute -top-3 -right-3" />
                  </div>
                ),
                cardStyle: isDark ? "bg-[#070e1a]/85 border-amber-500/30 hover:border-amber-500 hover:shadow-amber-950/20" : "bg-white border-amber-100 hover:border-amber-300 hover:shadow-amber-100/40",
                badgeStyle: "bg-amber-600 text-white border-white dark:border-[#070e1a]",
                pillStyle: "bg-amber-50 text-amber-650 dark:bg-amber-950/30 dark:text-amber-400"
              },
              {
                step: "04",
                title: "Smart School Hub",
                desc: "Dự báo kết quả học tập sớm, đề xuất lộ trình ôn tập cá nhân hóa và quản lý vận hành toàn diện.",
                status: "🌱 Toàn diện - Bền vững",
                color: "emerald",
                bgGrad: "from-emerald-500/5 to-emerald-500/0",
                icon: (
                  <div className="relative">
                    <Layout className="w-10 h-10 text-emerald-650 dark:text-emerald-450" />
                    <Sparkles className="w-5 h-5 text-emerald-500 absolute -top-3 -right-3 animate-pulse" />
                  </div>
                ),
                cardStyle: isDark ? "bg-[#070e1a]/85 border-emerald-500/30 hover:border-emerald-500 hover:shadow-emerald-950/20" : "bg-white border-emerald-100 hover:border-emerald-300 hover:shadow-emerald-100/40",
                badgeStyle: "bg-emerald-600 text-white border-white dark:border-[#070e1a]",
                pillStyle: "bg-emerald-50 text-emerald-650 dark:bg-emerald-950/30 dark:text-emerald-400"
              }
            ].map((road, index) => (
              <div key={index} className="relative group">
                <div className={`p-5 rounded-3xl border text-center flex flex-col justify-between items-center h-[280px] transition-all duration-300 transform relative z-10 ${road.cardStyle}`}>
                  {/* Circular Number Badge */}
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center font-extrabold text-[12px] absolute -top-4 left-1/2 -translate-x-1/2 border-4 shadow-sm z-20 ${road.badgeStyle}`}>
                    {road.step}
                  </div>

                  {/* Illustration Container */}
                  <div className={`w-full h-24 rounded-2xl flex items-center justify-center relative overflow-hidden bg-slate-50/50 dark:bg-slate-900/50 mb-3`}>
                    <div className={`absolute inset-0 bg-gradient-to-b ${road.bgGrad} opacity-30`} />
                    {road.icon}
                  </div>

                  {/* Details */}
                  <div className="flex-1 flex flex-col justify-center">
                    <h3 className={`font-extrabold text-xs mb-1.5 leading-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
                      {road.title}
                    </h3>
                    <p className={`text-[9.5px] leading-normal flex-1 px-1 line-clamp-3 ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
                      {road.desc}
                    </p>
                  </div>

                  {/* Bottom Pill Badge */}
                  <div className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-[8.5px] font-bold mt-2 ${road.pillStyle}`}>
                    {road.status}
                  </div>
                </div>

                {/* Chevron pointing to next card (hidden on last card and small screens) */}
                {index < 3 && (
                  <div className="hidden lg:flex absolute top-[125px] -right-4.5 transform -translate-y-1/2 z-30 pointer-events-none items-center justify-center">
                    <ChevronRight className={`w-5 h-5 font-black ${
                      index === 0 ? "text-blue-500" : index === 1 ? "text-purple-500" : "text-amber-500"
                    }`} />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Bottom Common Goal Bar */}
          <div className={`w-full mt-6 p-3 rounded-2xl border flex flex-col sm:flex-row items-center justify-between gap-4 relative overflow-hidden ${isDark ? "bg-[#070e1a]/85 border-[#263750] shadow-md" : "bg-white border-[#dcd7cc] shadow-sm"}`}>
            <div className="flex items-center gap-3 w-full sm:w-auto">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${isDark ? "bg-amber-500/10 text-amber-500" : "bg-amber-500/10 text-amber-600"}`}>
                <Star className="w-4 h-4 fill-amber-500" />
              </div>
              <div className="text-left">
                <strong className={`text-[11px] font-extrabold block leading-tight ${isDark ? "text-slate-200" : "text-[#0f1e36]"}`}>Mục tiêu chung</strong>
                <span className="text-[9.5px] text-slate-500 dark:text-slate-400 block mt-0.5 leading-none font-medium">Ứng dụng AI toàn diện – Hỗ trợ hiệu quả – Nâng tầm giáo dục số</span>
              </div>
            </div>
            
            {/* Rocket Timeline Animation */}
            <div className="flex items-center gap-2 pr-1 shrink-0 self-end sm:self-auto">
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                <div className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                <div className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span className="text-slate-300 dark:text-slate-700 font-mono text-[8px] tracking-tighter">- - - - -</span>
              </div>
              <Rocket className="w-4 h-4 text-rose-500 animate-pulse" />
            </div>
          </div>
        </div>
      )
    },
    // SLIDE 9: LỜI KẾT & HỎI ĐÁP (Q&A)
    // SLIDE 12: LỜI KẾT & HỎI ĐÁP (Q&A)
    {
      title: "",
      subtitle: "",
      type: "outro",
      content: (
        <div className="flex flex-col items-center justify-center text-center max-w-3xl mx-auto space-y-8 animate-fade-in py-6">
          <style>{`
            @keyframes pulse-ring {
              0% { transform: scale(0.95); opacity: 0.5; }
              50% { transform: scale(1.08); opacity: 0.15; }
              100% { transform: scale(0.95); opacity: 0.5; }
            }
          `}</style>
          
          {/* Logo & Glow effects */}
          <div className="relative">
            {/* Concentric pulsing glow rings */}
            <div className={`absolute -inset-6 rounded-full blur-xl scale-125 opacity-20 ${isDark ? "bg-[#c2ae78]" : "bg-[#8c763e]"} animate-pulse`} />
            <div className={`absolute -inset-4 rounded-full border-2 ${isDark ? "border-[#c2ae78]/20" : "border-[#8c763e]/10"} pointer-events-none`} style={{ animation: "pulse-ring 3s infinite ease-in-out" }} />
            
            <div className={`relative w-24 h-24 rounded-full border-2 flex items-center justify-center ${isDark ? "bg-[#070e1a] border-[#c2ae78]/40" : "bg-white border-[#8c763e]/20"} shadow-xl`}>
              <img src="/logo.svg" className="w-16 h-16 object-contain animate-[float-owl_4s_ease-in-out_infinite]" alt="EduOwl Logo" />
            </div>
          </div>

          <div className="space-y-4 max-w-2xl">
            <h1 className={`text-3xl md:text-4xl font-extrabold tracking-tight leading-tight ${isDark ? "text-white" : "text-[#0f1e36]"}`}>
              Xin Chân Thành Cảm Ơn!
            </h1>
            <p className={`text-sm md:text-base leading-relaxed ${isDark ? "text-[#c2ae78]" : "text-[#8c763e]"} font-extrabold`}>
              EduOwl - Người đồng hành đo lường đáng tin cậy của Ban Giám Hiệu
            </p>
            <p className={`text-xs md:text-sm leading-relaxed max-w-lg mx-auto ${isDark ? "text-slate-400" : "text-[#4a5568]"}`}>
              Hệ thống AI tiên phong hỗ trợ kiến tạo văn hóa học thuật công bằng, nâng tầm chất lượng dạy học và đồng hành chuyển đổi số toàn diện cùng nhà trường.
            </p>
          </div>

          {/* Core Values Badges */}
          <div className="flex flex-wrap items-center justify-center gap-3.5 pt-2">
            {[
              { label: "Khách Quan", bg: isDark ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-emerald-50 text-emerald-700 border-emerald-200" },
              { label: "Minh Bạch", bg: isDark ? "bg-blue-500/10 text-blue-400 border-blue-500/20" : "bg-blue-50 text-blue-700 border-blue-200" },
              { label: "Tối Ưu Vận Hành", bg: isDark ? "bg-purple-500/10 text-purple-400 border-purple-500/20" : "bg-purple-50 text-purple-700 border-purple-200" }
            ].map((val, idx) => (
              <span key={idx} className={`px-4 py-1.5 rounded-full border text-xs font-extrabold tracking-wide uppercase ${val.bg}`}>
                ✦ {val.label}
              </span>
            ))}
          </div>

          {/* Q&A Footer Section */}
          <div className={`pt-6 border-t w-full max-w-lg mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] font-bold ${isDark ? "border-[#263750] text-slate-500" : "border-[#dcd7cc] text-[#8c763e]/85"}`}>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
              Phiên thảo luận Q&A & Giải đáp câu hỏi
            </span>
            <span className="hidden sm:inline-block w-1.5 h-1.5 rounded-full bg-slate-400" />
            <span>Dự án EduOwl 2026</span>
          </div>

          <button
            type="button"
            onClick={onClose}
            className={`px-8 py-3 rounded-full font-black text-xs uppercase tracking-wider transition active:scale-95 cursor-pointer shadow-md ${isDark
              ? "bg-[#c2ae78] text-[#070e1a] hover:bg-[#a38a4d] hover:shadow-[#c2ae78]/10"
              : "bg-[#0f1e36] text-[#faf9f6] hover:bg-[#8c763e] hover:shadow-slate-300"
              }`}
          >
            Kết thúc trình bày
          </button>
        </div>
      )
    }
  ];

  // Reset states on slide change
  useEffect(() => {
    setHoveredCardIndex(null);
    setIsVideoMaximized(false);
    setActiveDemoTab(0);
    setIsMp4Playing(false);
  }, [currentSlide]);

  // Reset play state on demo tab change
  useEffect(() => {
    setIsMp4Playing(false);
  }, [activeDemoTab]);

  // Handle Keyboard Arrows Navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        if (currentSlide < slides.length - 1) {
          setCurrentSlide(prev => prev + 1);
        }
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        if (currentSlide > 0) {
          setCurrentSlide(prev => prev - 1);
        }
      } else if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, currentSlide, slides.length, onClose]);

  if (!isOpen) return null;

  return (
    <div className={`fixed inset-0 z-[9999] flex flex-col justify-between select-none animate-fade-in overflow-hidden font-sans ${isDark ? "bg-[#070e1a] text-[#faf9f6]" : "bg-[#f5f1e6] text-[#0f1e36]"}`}>
      {/* Background Gradients */}
      {isDark ? (
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(194,174,120,0.06),transparent_50%),radial-gradient(circle_at_bottom_left,rgba(194,174,120,0.04),transparent_50%)] pointer-events-none" />
      ) : (
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(140,118,62,0.03),transparent_50%),radial-gradient(circle_at_bottom_left,rgba(140,118,62,0.02),transparent_50%)] pointer-events-none" />
      )}

      <main className={`flex-1 flex items-center justify-center relative z-10 overflow-y-auto ${(slides[currentSlide].type === "solution" || isVideoMaximized)
        ? "p-0"
        : (slides[currentSlide].type === "auto_reports" || slides[currentSlide].type === "chatbot_rag" || slides[currentSlide].type === "linking_exams" || slides[currentSlide].type === "camera_assessment" || slides[currentSlide].type === "matrix_generation")
          ? "px-4 lg:px-8 py-4 lg:py-6"
          : "px-6 py-8"
        }`}>
        <div className={`w-full h-full mx-auto flex items-center justify-center ${(slides[currentSlide].type === "solution" || isVideoMaximized)
          ? "max-w-none px-0"
          : (slides[currentSlide].type === "auto_reports" || slides[currentSlide].type === "chatbot_rag" || slides[currentSlide].type === "linking_exams" || slides[currentSlide].type === "camera_assessment" || slides[currentSlide].type === "matrix_generation")
            ? "max-w-7xl"
            : "max-w-6xl"
          }`}>
          {slides[currentSlide].content}
        </div>
      </main>

      {/* Footer - Compact Height (h-12) */}
      <footer className={`px-6 py-2 h-12 border-t backdrop-blur-md flex items-center justify-between shrink-0 relative z-10 ${isDark ? "border-[#263750]/60 bg-[#070e1a]/45" : "border-[#dcd7cc]/80 bg-[#f5f1e6]/75"}`}>
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
            onClick={() => setCurrentSlide(prev => prev - 1)}
            className={`p-1.5 rounded-lg border transition disabled:opacity-30 disabled:pointer-events-none active:scale-95 ${isDark ? "bg-[#070e1a] border-[#263750] text-[#c2ae78] hover:bg-slate-900 hover:text-white" : "bg-white border-[#dcd7cc] text-[#8c763e] hover:bg-slate-100 hover:text-slate-900"}`}
            title="Slide trước (Arrow Left)"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <button
            type="button"
            disabled={currentSlide === slides.length - 1}
            onClick={() => setCurrentSlide(prev => prev + 1)}
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
