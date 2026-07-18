"use client";

import { useState, useEffect, useCallback } from "react";
import { Node, Edge } from "@xyflow/react";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { AGENT_LABEL, AGENT_ROLE_DESCRIPTION, ObservabilitySummaryResponse } from "@/lib/types";
import { AlertCircle, RefreshCw } from "lucide-react";
import GraphCanvas from "./GraphCanvas";
import SidePanel from "./SidePanel";

// Vị trí cố định của từng node trong sơ đồ — khớp cấu trúc StateGraph thật ở src/agents/graph.py
// (Supervisor là entry point, 5 sub-agent đều nhận route từ Supervisor và quay lại Supervisor).
const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  supervisor: { x: 450, y: 50 },
  data_agent: { x: 50, y: 300 },
  stat_agent: { x: 250, y: 300 },
  sql_agent: { x: 450, y: 300 },
  knowledge_agent: { x: 650, y: 300 },
  report_agent: { x: 850, y: 300 },
};

const SUB_AGENTS = ["data_agent", "stat_agent", "sql_agent", "knowledge_agent", "report_agent"];

function buildNodes(health: ObservabilitySummaryResponse | null): Node[] {
  return Object.entries(NODE_POSITIONS).map(([id, position]) => {
    // "supervisor" luôn được gọi đầu tiên mỗi request nên không có trong agent_routes (chỉ đếm
    // lượt ĐỊNH TUYẾN SANG sub-agent) — hiển thị riêng, không lẫn với "0 lượt" (nghĩa là ế).
    const taskCount = id === "supervisor" ? null : (health?.agent_routes?.[id] ?? 0);
    const latencyP95Ms = health?.agent_step_p95_ms?.[id] ?? null;
    return {
      id,
      type: "customAgentNode",
      position,
      data: {
        label: AGENT_LABEL[id],
        role: AGENT_ROLE_DESCRIPTION[id],
        status: health === null ? "unknown" : taskCount === null || taskCount > 0 ? "active" : "idle",
        taskCount,
        latencyP95Ms,
      },
    };
  });
}

const EDGES: Edge[] = [
  ...SUB_AGENTS.map((id) => ({
    id: `e-sup-${id}`,
    source: "supervisor",
    target: id,
    animated: true,
    label: "Route",
    style: { stroke: "#6366f1", strokeWidth: 1.5 },
  })),
  ...SUB_AGENTS.map((id) => ({
    id: `e-${id}-sup`,
    source: id,
    target: "supervisor",
    animated: false,
    style: { stroke: "#cbd5e1", strokeWidth: 1, strokeDasharray: "5 5" },
  })),
];

export default function AgentDashboard() {
  const { user, loading } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [nodes, setNodes] = useState<Node[]>(buildNodes(null));
  const [edges, setEdges] = useState<Edge[]>(EDGES);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const loadHealth = useCallback(() => {
    setHealthLoading(true);
    api
      .get<ObservabilitySummaryResponse>("/chat/admin/observability-summary")
      .then((data) => {
        setNodes(buildNodes(data));
        setHealthError(null);
      })
      .catch((err) => {
        setHealthError(err instanceof ApiError ? err.message : "Không thể kết nối đến máy chủ");
      })
      .finally(() => setHealthLoading(false));
  }, []);

  useEffect(() => {
    if (user?.role === "ADMIN") loadHealth();
  }, [user, loadHealth]);

  useEffect(() => {
    if (selectedNode) {
      const updated = nodes.find((n) => n.id === selectedNode.id);
      if (updated) setSelectedNode(updated);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes]);

  if (!mounted || loading) return null;

  if (user?.role !== "ADMIN") {
    return (
      <div className="w-full h-full min-h-[500px] flex flex-col items-center justify-center text-slate-500">
        <AlertCircle className="w-12 h-12 text-rose-500 mb-4" />
        <h2 className="text-xl font-bold text-slate-800 dark:text-slate-200">Không có quyền truy cập</h2>
        <p className="mt-2 text-sm text-center max-w-md">
          Chức năng Giám sát Multi-Agent yêu cầu quyền Quản trị viên (ADMIN). Bạn không thể sử dụng chức năng này.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full h-full min-h-[700px] flex flex-col">
      <div className="mb-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Giám sát Multi-Agent</h1>
            <p className="text-sm text-slate-500 mt-1">
              Sơ đồ định tuyến Supervisor ↔ Sub-Agent + số liệu thật (số lượt định tuyến, độ trễ P95) từ hệ thống
              theo dõi AgentOps. Xem chi tiết ở{" "}
              <a href="/admin/ai-metrics" className="text-brand hover:underline">
                Đánh giá &amp; Thống kê AI
              </a>
              .
            </p>
          </div>
          <button
            onClick={loadHealth}
            disabled={healthLoading}
            className="inline-flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${healthLoading ? "animate-spin" : ""}`} /> Làm mới
          </button>
        </div>
        {healthError && (
          <p className="mt-2 text-sm text-rose-600 dark:text-rose-400">
            Không tải được số liệu thật ({healthError}) — sơ đồ vẫn hiển thị nhưng số liệu có thể trống.
          </p>
        )}
      </div>

      <div className="flex-1 overflow-hidden relative rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 flex">
        <GraphCanvas nodes={nodes} edges={edges} setNodes={setNodes} setEdges={setEdges} onNodeSelect={setSelectedNode} />

        <SidePanel selectedNode={selectedNode} onClose={() => setSelectedNode(null)} />
      </div>
    </div>
  );
}
