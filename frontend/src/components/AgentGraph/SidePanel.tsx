"use client";

import { Node } from "@xyflow/react";
import { X, Cpu, CheckCircle2, CircleDashed, HelpCircle } from "lucide-react";

interface SidePanelProps {
  selectedNode: Node | null;
  onClose: () => void;
}

interface AgentNodeData {
  label: string;
  role: string;
  status: "active" | "idle" | "unknown";
  taskCount: number | null;
  latencyP95Ms: number | null;
}

export default function SidePanel({ selectedNode, onClose }: SidePanelProps) {
  if (!selectedNode) return null;

  const data = selectedNode.data as unknown as AgentNodeData;

  const renderStatusIcon = () => {
    switch (data.status) {
      case "active":
        return <CheckCircle2 className="w-5 h-5 text-green-500" />;
      case "idle":
        return <CircleDashed className="w-5 h-5 text-slate-400" />;
      default:
        return <HelpCircle className="w-5 h-5 text-amber-500" />;
    }
  };

  const statusLabel = { active: "Đang hoạt động", idle: "Rảnh (chưa có lượt gọi)", unknown: "Chưa tải được số liệu" }[
    data.status
  ];

  return (
    <div className="absolute top-0 right-0 h-full w-80 bg-white dark:bg-slate-950 border-l border-slate-200 dark:border-slate-800 shadow-2xl transition-transform transform translate-x-0 flex flex-col z-10">
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-50 dark:bg-slate-900/50">
        <h2 className="font-semibold text-lg flex items-center gap-2 text-slate-800 dark:text-slate-100">
          <Cpu className="w-5 h-5 text-indigo-500" />
          {data.label}
        </h2>
        <button onClick={onClose} className="p-1.5 hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500 rounded-md transition-colors">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="p-5 flex-1 overflow-y-auto space-y-6 text-sm">
        <div className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg border border-slate-100 dark:border-slate-800">
          <span className="text-slate-500 font-medium">Trạng thái</span>
          <div className="flex items-center gap-2 font-semibold text-slate-700 dark:text-slate-200">
            {renderStatusIcon()} {statusLabel}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white dark:bg-slate-950 p-3 rounded-lg border border-slate-200 dark:border-slate-800 shadow-sm">
            <p className="text-xs text-slate-500 mb-1 font-semibold uppercase tracking-wide">Vai trò</p>
            <p className="font-semibold text-slate-800 dark:text-slate-200" title={data.role}>{data.role}</p>
          </div>
          <div className="bg-white dark:bg-slate-950 p-3 rounded-lg border border-slate-200 dark:border-slate-800 shadow-sm">
            <p className="text-xs text-slate-500 mb-1 font-semibold uppercase tracking-wide">Lượt định tuyến</p>
            <p className="font-semibold text-indigo-600 dark:text-indigo-400">
              {data.taskCount === null ? "Entry point (mọi lượt hỏi)" : data.taskCount.toLocaleString()}
            </p>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-950 p-3 rounded-lg border border-slate-200 dark:border-slate-800 shadow-sm">
          <p className="text-xs text-slate-500 mb-1 font-semibold uppercase tracking-wide">Độ trễ P95 / bước</p>
          <p className="font-semibold text-slate-800 dark:text-slate-200">
            {data.latencyP95Ms != null ? `${(data.latencyP95Ms / 1000).toFixed(2)}s` : "Chưa có mẫu"}
          </p>
        </div>

        <div className="pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed space-y-1">
          <p>
            Toàn bộ agent dùng chung 1 LLM provider, cấu hình qua biến môi trường phía server (không đổi được theo
            từng agent riêng lẻ).
          </p>
          <p>Số liệu lấy từ AgentOps (bấm &quot;Làm mới&quot; để cập nhật) — không phải trạng thái real-time.</p>
        </div>
      </div>
    </div>
  );
}
