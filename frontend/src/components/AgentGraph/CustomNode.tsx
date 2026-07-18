"use client";

import { Handle, Position } from "@xyflow/react";
import { Cpu } from "lucide-react";

interface AgentNodeData {
  label: string;
  role: string;
  status: "active" | "idle" | "unknown";
  taskCount: number | null;
  latencyP95Ms: number | null;
}

export default function CustomNode({ data }: { data: AgentNodeData }) {
  const renderStatusDot = () => {
    switch (data.status) {
      case "active":
        return <span className="absolute -top-1.5 -right-1.5 h-4 w-4 rounded-full bg-green-500 border-2 border-white dark:border-slate-900 shadow-sm"></span>;
      case "unknown":
        return <span className="absolute -top-1.5 -right-1.5 h-4 w-4 rounded-full bg-amber-400 border-2 border-white dark:border-slate-900 shadow-sm"></span>;
      default: // idle
        return <span className="absolute -top-1.5 -right-1.5 h-4 w-4 rounded-full bg-slate-300 dark:bg-slate-600 border-2 border-white dark:border-slate-900 shadow-sm"></span>;
    }
  };

  return (
    <div className="relative flex flex-col items-center justify-center p-4 bg-white dark:bg-slate-950 border-2 border-slate-200 dark:border-slate-800 rounded-2xl shadow-md min-w-[160px] hover:border-indigo-400 transition-colors cursor-pointer group">
      <Handle type="target" position={Position.Top} className="w-3 h-3 bg-slate-300 dark:bg-slate-700" />

      {renderStatusDot()}

      <div className="p-2.5 bg-indigo-50 dark:bg-indigo-900/40 rounded-xl text-indigo-600 dark:text-indigo-400 mb-3 group-hover:scale-110 transition-transform">
        <Cpu className="w-7 h-7" />
      </div>

      <div className="text-center w-full">
        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 leading-tight">{data.label}</h3>
        <p className="text-[10px] font-semibold text-slate-500 dark:text-slate-400 tracking-wide mt-1.5 px-2 py-0.5 bg-slate-100 dark:bg-slate-800 rounded-full inline-block">
          {data.taskCount === null ? "Entry point" : `${data.taskCount.toLocaleString()} lượt`}
          {data.latencyP95Ms != null ? ` · ${(data.latencyP95Ms / 1000).toFixed(2)}s` : ""}
        </p>
      </div>

      <Handle type="source" position={Position.Bottom} className="w-3 h-3 bg-slate-300 dark:bg-slate-700" />
    </div>
  );
}
