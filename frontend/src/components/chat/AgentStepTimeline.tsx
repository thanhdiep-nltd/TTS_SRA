"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  GitFork,
  Layers,
  Search,
  Filter,
  PenTool,
  ChevronDown,
  ChevronUp,
  Loader2,
  Clock,
} from "lucide-react";

export type StepCategory =
  | "safety"
  | "routing"
  | "decomposition"
  | "retrieval"
  | "filtering"
  | "synthesis";

export type StepStatus = "pending" | "running" | "completed" | "warning" | "error";

export interface AgentStepTrace {
  id: string;
  category: StepCategory;
  title: string;
  summary: string;
  status: StepStatus;
  icon?: string;
  detail?: string;
  elapsed_ms?: number;
  timestamp?: number;
}

interface AgentStepTimelineProps {
  steps: AgentStepTrace[];
  isLiveLoading?: boolean;
}

const CATEGORY_CONFIG: Record<
  string,
  { icon: React.ComponentType<{ className?: string }>; colorClass: string }
> = {
  safety: {
    icon: ShieldCheck,
    colorClass: "text-brand-600 dark:text-brand-400",
  },
  routing: {
    icon: GitFork,
    colorClass: "text-brand-600 dark:text-brand-400",
  },
  decomposition: {
    icon: Layers,
    colorClass: "text-brand-600 dark:text-brand-400",
  },
  retrieval: {
    icon: Search,
    colorClass: "text-brand-600 dark:text-brand-400",
  },
  filtering: {
    icon: Filter,
    colorClass: "text-brand-600 dark:text-brand-400",
  },
  synthesis: {
    icon: PenTool,
    colorClass: "text-brand-600 dark:text-brand-400",
  },
};

export const AgentStepTimeline: React.FC<AgentStepTimelineProps> = ({
  steps,
  isLiveLoading = false,
}) => {
  const [expanded, setExpanded] = useState(false);
  const [activeDetailId, setActiveDetailId] = useState<string | null>(null);

  if (!steps || steps.length === 0) return null;

  // Bước đang chạy hiện tại (bước cuối có status "running" khi live loading)
  const runningStep = steps[steps.length - 1];

  // Icon + màu của bước đang chạy (fallback sang màu brand nếu không xác định)
  const runningConfig = runningStep
    ? CATEGORY_CONFIG[runningStep.category] || {
      icon: Search,
      colorClass: "text-brand-600 dark:text-brand-400",
    }
    : { icon: Search, colorClass: "text-brand-600 dark:text-brand-400" };
  const RunningIcon = runningConfig.icon;

  const isLive = isLiveLoading && !!runningStep && runningStep.status === "running";

  return (
    <div className="mt-0.5 mb-3.5 text-xs select-none">
      {/* Header Bar (1 dòng duy nhất): spinner + trạng thái live hoặc "Đã thực hiện N bước" + Toggle */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 text-xs py-1 font-normal transition-colors cursor-pointer"
      >
        {/* Chỉ 1 icon duy nhất chính giữa: spinner khi live, còn lại icon phân loại bước */}
        {isLive ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-500 shrink-0" />
        ) : (
          <RunningIcon className={`w-3.5 h-3.5 ${runningConfig.colorClass} shrink-0`} />
        )}
        <span className="font-medium text-xs truncate">
          {/* key theo steps.length để khi chuyển bước → re-mount → animation chạy lại */}
          <span
            key={`status-${steps.length}-${runningStep.id}`}
            className="step-transition"
          >
            {isLive ? `Đang thực hiện: ${runningStep.title}` : `Đã thực hiện: ${runningStep.title}`}
          </span>
        </span>
        {expanded ? (
          <ChevronUp className="w-3 h-3 text-slate-400 shrink-0" />
        ) : (
          <ChevronDown className="w-3 h-3 text-slate-400 shrink-0" />
        )}
      </button>

      {/* Expanded Timeline Steps List: Indented + Smaller font size + Fixed Elapsed MS */}
      {expanded && (
        <div className="pt-1.5 pb-1 relative space-y-2.5 ml-3 pl-1">
          {steps.map((step, index) => {
            const config = CATEGORY_CONFIG[step.category] || {
              icon: Search,
              colorClass: "text-brand-600 dark:text-brand-400",
            };
            const CategoryIcon = config.icon;
            const isLast = index === steps.length - 1;
            const isRunning = isLiveLoading && isLast && step.status === "running";
            // Backend có thể tạo NHIỀU step cùng id tĩnh trong một message
            // (vd routing ×2, retrieval_<tool> ×N, filtering ×N) → id không unique.
            // Dùng key composite `${step.id}-${index}` để đảm bảo React key luôn duy nhất
            // và activeDetailId không bị va chạm giữa các step trùng id.
            const stepKey = `${step.id}-${index}`;

            return (
              <div key={stepKey} className="relative flex items-center gap-2 group">
                {/* Column for Icon & Perfectly Centered Line */}
                <div className="relative flex items-center justify-center w-4 shrink-0 self-stretch">
                  {/* Vertical Line perfectly centered under icon */}
                  {!isLast && (
                    <div className="absolute top-1/2 bottom-[-12px] left-1/2 -translate-x-1/2 w-[1.5px] bg-slate-200 dark:bg-slate-800 pointer-events-none z-0" />
                  )}

                  {/* Pure Icon Container (bg-transparent, centered) */}
                  <div
                    className={`relative z-10 flex items-center justify-center w-4 h-4 ${config.colorClass} shrink-0 bg-transparent`}
                  >
                    {isRunning ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-500" />
                    ) : (
                      <CategoryIcon className="w-3.5 h-3.5" />
                    )}
                  </div>
                </div>

                {/* Step Content: Title & Summary inline */}
                <div className="flex-1 min-w-0 flex items-center justify-between gap-2">
                  <div className="flex items-baseline gap-1.5 min-w-0">
                    <span className="font-semibold text-slate-800 dark:text-slate-100 text-xs shrink-0">
                      {step.title}
                    </span>
                    <span className="text-slate-500 dark:text-slate-400 text-[11px] leading-relaxed truncate">
                      {step.summary}
                    </span>
                  </div>

                  {/* Fix time display error: ONLY render if elapsed_ms is a valid positive number */}
                  {typeof step.elapsed_ms === "number" && step.elapsed_ms > 0 && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-mono text-slate-400 dark:text-slate-500 shrink-0">
                      <Clock className="w-2.5 h-2.5" />
                      {step.elapsed_ms}ms
                    </span>
                  )}
                </div>

                {/* Detail Expander */}
                {step.detail && (
                  <div>
                    <button
                      type="button"
                      onClick={() =>
                        setActiveDetailId(activeDetailId === stepKey ? null : stepKey)
                      }
                      className="text-[10px] text-brand-600 dark:text-brand-400 hover:underline font-medium cursor-pointer"
                    >
                      {activeDetailId === stepKey ? "Ẩn" : "Chi tiết"}
                    </button>
                    {activeDetailId === stepKey && (
                      <pre className="mt-1 p-2 rounded-lg bg-slate-900 text-slate-200 text-[11px] font-mono overflow-x-auto whitespace-pre-wrap max-h-48 border border-slate-800">
                        {step.detail}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AgentStepTimeline;
