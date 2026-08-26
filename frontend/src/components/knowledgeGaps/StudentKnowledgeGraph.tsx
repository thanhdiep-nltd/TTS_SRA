"use client";

import React, { useMemo, useState, useCallback } from "react";
import Link from "next/link";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  Node,
  Edge,
  applyNodeChanges,
  applyEdgeChanges,
  NodeChange,
  EdgeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Award,
  BookOpen,
  Brain,
  CheckCircle2,
  FileText,
  Filter,
  GraduationCap,
  Info,
  Laptop,
  Lightbulb,
  Maximize2,
  ShieldAlert,
  Sparkles,
  Target,
  User,
  X,
} from "lucide-react";
import type { KnowledgeGapItem } from "@/lib/types";

const GAP_THRESHOLD = 0.6;
const fmtPct = (v: number | null | undefined): string =>
  v === null || v === undefined || isNaN(v) ? "—" : `${(v * 100).toFixed(1)}%`;

// ——— CUSTOM NODE: ROOT (Môn học & Học sinh — Trung tâm) ———
function RootNode({ data }: { data: { title: string; subtitle: string; overallMastery: number } }) {
  const isGood = data.overallMastery >= GAP_THRESHOLD;
  return (
    <div className="px-5 py-4 rounded-2xl bg-gradient-to-br from-brand-900 to-slate-900 text-white border-2 border-brand-500 shadow-2xl min-w-[240px] text-center relative group">
      {/* Handle sang cánh Trái */}
      <Handle
        type="source"
        id="left"
        position={Position.Left}
        className="w-3 h-3 bg-brand-400 border-2 border-slate-900"
      />

      <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-2.5 py-0.5 rounded-full bg-brand-500 text-[10px] font-black uppercase tracking-wider shadow-sm flex items-center gap-1 text-white">
        <GraduationCap className="w-3 h-3" />
        <span>Gốc Tri Thức</span>
      </div>
      <h3 className="font-extrabold text-sm text-white pt-1">{data.title}</h3>
      <p className="text-xs text-brand-200 mt-0.5">{data.subtitle}</p>
      <div className="mt-2.5 pt-2 border-t border-brand-700/50 flex items-center justify-between text-xs">
        <span className="text-brand-300 text-[11px]">Năng lực tổng thể:</span>
        <span className={`font-black font-mono ${isGood ? "text-emerald-400" : "text-rose-400"}`}>
          {fmtPct(data.overallMastery)}
        </span>
      </div>

      {/* Handle sang cánh Phải */}
      <Handle
        type="source"
        id="right"
        position={Position.Right}
        className="w-3 h-3 bg-brand-400 border-2 border-slate-900"
      />
    </div>
  );
}

// ——— CUSTOM NODE: CHAPTER (Chương — 2 bên Trái / Phải) ———
function ChapterNode({
  data,
}: {
  data: {
    title: string;
    mastery: number;
    lessonCount: number;
    gapCount: number;
    isGap: boolean;
    side: "left" | "right";
  };
}) {
  const isLeft = data.side === "left";

  return (
    <div
      className={`px-4 py-3.5 rounded-2xl border-2 transition-all min-w-[220px] max-w-[250px] shadow-md bg-white dark:bg-slate-900 ${
        data.isGap || data.gapCount > 0
          ? "border-rose-300 dark:border-rose-800/80 shadow-rose-500/10"
          : "border-emerald-300 dark:border-emerald-800/80 shadow-emerald-500/10"
      }`}
    >
      {/* Target handle nhận từ Root */}
      <Handle
        type="target"
        id={isLeft ? "target-right" : "target-left"}
        position={isLeft ? Position.Right : Position.Left}
        className="w-3 h-3 bg-slate-400 border-2 border-white dark:border-slate-900"
      />

      <div className="flex items-start gap-2.5">
        <div
          className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 text-xs font-bold ${
            data.isGap || data.gapCount > 0
              ? "bg-rose-100 text-rose-600 dark:bg-rose-950 dark:text-rose-400"
              : "bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400"
          }`}
        >
          <BookOpen className="w-4 h-4" />
        </div>
        <div className="min-w-0 flex-1">
          <h4 className="font-bold text-xs text-slate-900 dark:text-white line-clamp-2 leading-tight">
            {data.title}
          </h4>
          <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-slate-100 dark:border-slate-800 text-[11px]">
            <span className="text-slate-400">
              {data.lessonCount} bài {data.gapCount > 0 ? `· ` : ""}
              {data.gapCount > 0 && <strong className="text-rose-600 dark:text-rose-400">({data.gapCount} hổng)</strong>}
            </span>
            <span
              className={`font-black font-mono ${
                data.mastery >= 0.8
                  ? "text-emerald-600 dark:text-emerald-400"
                  : data.mastery >= GAP_THRESHOLD
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-rose-600 dark:text-rose-400"
              }`}
            >
              {fmtPct(data.mastery)}
            </span>
          </div>
        </div>
      </div>

      {/* Source handle phát sang Bài học con */}
      <Handle
        type="source"
        id={isLeft ? "source-left" : "source-right"}
        position={isLeft ? Position.Left : Position.Right}
        className="w-3 h-3 bg-slate-400 border-2 border-white dark:border-slate-900"
      />
    </div>
  );
}

// ——— CUSTOM NODE: LESSON (Bài học con — 2 bên Trái / Phải) ———
function LessonNode({
  data,
}: {
  data: {
    lesson: KnowledgeGapItem;
    title: string;
    mastery: number;
    isGap: boolean;
    side: "left" | "right";
    nCorrect?: number;
    nItems?: number;
  };
}) {
  const isHigh = data.mastery >= 0.8;
  const isMed = data.mastery >= GAP_THRESHOLD && data.mastery < 0.8;
  const isLeft = data.side === "left";

  return (
    <div
      className={`px-3.5 py-2.5 rounded-xl border-2 transition-all min-w-[190px] max-w-[230px] shadow-sm cursor-pointer hover:scale-105 group bg-white dark:bg-slate-900 ${
        data.isGap
          ? "border-rose-400 dark:border-rose-600 hover:border-rose-500 ring-2 ring-rose-500/10"
          : isMed
          ? "border-amber-300 dark:border-amber-700 hover:border-amber-400"
          : "border-emerald-300 dark:border-emerald-700 hover:border-emerald-400"
      }`}
    >
      {/* Target handle nhận từ Chương */}
      <Handle
        type="target"
        position={isLeft ? Position.Right : Position.Left}
        className="w-2.5 h-2.5 bg-slate-400 border-2 border-white dark:border-slate-900"
      />

      <div className="flex items-start justify-between gap-1.5">
        <div className="min-w-0 flex-1">
          <span className="font-bold text-xs text-slate-800 dark:text-slate-100 line-clamp-2 leading-tight group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors">
            {data.title}
          </span>
          {data.nItems ? (
            <span className="text-[10px] text-slate-400 block mt-0.5">
              Đúng {data.nCorrect ?? 0}/{data.nItems} câu LMS
            </span>
          ) : null}
        </div>
        <div className="text-right shrink-0">
          <span
            className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-black font-mono ${
              data.isGap
                ? "bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
                : isMed
                ? "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
                : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
            }`}
          >
            {fmtPct(data.mastery)}
          </span>
          <span className="block text-[9px] font-semibold mt-0.5 text-slate-400">
            {data.isGap ? "🔴 Hổng" : isMed ? "🟡 Cần ôn" : "🟢 Vững"}
          </span>
        </div>
      </div>
    </div>
  );
}

const nodeTypes = {
  rootNode: RootNode,
  chapterNode: ChapterNode,
  lessonNode: LessonNode,
};

interface StudentKnowledgeGraphProps {
  subjectName: string;
  studentName: string | null;
  studentCode: string;
  gaps: KnowledgeGapItem[];
}

export default function StudentKnowledgeGraph({
  subjectName,
  studentName,
  studentCode,
  gaps,
}: StudentKnowledgeGraphProps) {
  const [filterMode, setFilterMode] = useState<"all" | "gaps" | "mastered">("all");
  const [selectedLesson, setSelectedLesson] = useState<KnowledgeGapItem | null>(null);

  // Tính toán Nodes & Edges theo mô hình Mindmap 2 Cánh (Bilateral Radial Tree)
  const { initialNodes, initialEdges, totalLessonsCount, gapLessonsCount } = useMemo(() => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];

    let totalLessons = 0;
    let gapLessons = 0;
    let masterySum = 0;
    let validCount = 0;

    // 1. Phân loại bài học & tính toán
    const chapterLayouts: {
      chapter: KnowledgeGapItem;
      lessons: KnowledgeGapItem[];
      chapterMastery: number;
      gapCount: number;
    }[] = [];

    gaps.forEach((ch) => {
      const allLessons = ch.lessons ?? [];
      let lessons = allLessons;
      if (filterMode === "gaps") {
        lessons = allLessons.filter((l) => (l.raw_mastery ?? l.mastery) < GAP_THRESHOLD);
      } else if (filterMode === "mastered") {
        lessons = allLessons.filter((l) => (l.raw_mastery ?? l.mastery) >= GAP_THRESHOLD);
      }

      const chLms =
        ch.raw_mastery ??
        (allLessons.length > 0
          ? allLessons.reduce((acc, l) => acc + (l.raw_mastery ?? l.mastery), 0) / allLessons.length
          : ch.mastery);

      const chGapCount = allLessons.filter((l) => (l.raw_mastery ?? l.mastery) < GAP_THRESHOLD).length;

      totalLessons += allLessons.length;
      gapLessons += chGapCount;
      if (chLms !== undefined && chLms !== null) {
        masterySum += chLms;
        validCount += 1;
      }

      chapterLayouts.push({
        chapter: ch,
        lessons,
        chapterMastery: chLms,
        gapCount: chGapCount,
      });
    });

    const overallMastery = validCount > 0 ? masterySum / validCount : 0.85;

    // 2. Chia đều Chương sang 2 Cánh (Trái / Phải)
    const midIndex = Math.ceil(chapterLayouts.length / 2);
    const leftChapters = chapterLayouts.slice(0, midIndex);
    const rightChapters = chapterLayouts.slice(midIndex);

    // Node Root ở chính giữa (x = 0, y = 0)
    nodes.push({
      id: "root",
      type: "rootNode",
      position: { x: -120, y: -45 },
      data: {
        title: subjectName,
        subtitle: `${studentName || studentCode} (${studentCode})`,
        overallMastery,
      },
    });

    const LESSON_HEIGHT = 64;
    const CHAPTER_GAP = 36;

    // --- CÁNH TRÁI (LEFT SIDE) ---
    const leftTotalLessons = leftChapters.reduce((acc, ch) => acc + Math.max(1, ch.lessons.length), 0);
    const leftTotalHeight = leftTotalLessons * LESSON_HEIGHT + (leftChapters.length - 1) * CHAPTER_GAP;
    let leftCurrentY = -leftTotalHeight / 2;

    leftChapters.forEach((chData) => {
      const chId = `chapter-${chData.chapter.unit_id}`;
      const lessonsCount = Math.max(1, chData.lessons.length);
      const branchHeight = lessonsCount * LESSON_HEIGHT;
      const chapterY = leftCurrentY + branchHeight / 2 - 32;

      // Chapter Node bên Trái (x = -360)
      nodes.push({
        id: chId,
        type: "chapterNode",
        position: { x: -360, y: chapterY },
        data: {
          title: chData.chapter.unit_name ?? `Chương ${chData.chapter.unit_id}`,
          mastery: chData.chapterMastery,
          lessonCount: chData.chapter.lessons?.length ?? 0,
          gapCount: chData.gapCount,
          isGap: chData.chapterMastery < GAP_THRESHOLD,
          side: "left",
        },
      });

      // Edge từ Root (left handle) -> Chapter (target-right handle)
      edges.push({
        id: `edge-root-${chId}`,
        source: "root",
        sourceHandle: "left",
        target: chId,
        targetHandle: "target-right",
        type: "smoothstep",
        style: {
          stroke: chData.chapterMastery < GAP_THRESHOLD || chData.gapCount > 0 ? "#f43f5e" : "#10b981",
          strokeWidth: 2,
        },
      });

      // Lesson Nodes bên Trái (x = -680)
      chData.lessons.forEach((l, lIdx) => {
        const lessonId = `lesson-${l.unit_id}`;
        const lessonY = leftCurrentY + lIdx * LESSON_HEIGHT;
        const lMastery = l.raw_mastery ?? l.mastery;
        const isLGap = lMastery < GAP_THRESHOLD;

        nodes.push({
          id: lessonId,
          type: "lessonNode",
          position: { x: -680, y: lessonY },
          data: {
            lesson: l,
            title: l.lesson || l.unit_name,
            mastery: lMastery,
            isGap: isLGap,
            side: "left",
            nCorrect: l.n_correct,
            nItems: l.n_items,
          },
        });

        // Edge từ Chapter (source-left) -> Lesson
        edges.push({
          id: `edge-${chId}-${lessonId}`,
          source: chId,
          sourceHandle: "source-left",
          target: lessonId,
          type: "smoothstep",
          style: {
            stroke: isLGap ? "#f43f5e" : "#10b981",
            strokeWidth: 1.5,
            strokeDasharray: isLGap ? "4 2" : undefined,
          },
        });
      });

      leftCurrentY += branchHeight + CHAPTER_GAP;
    });

    // --- CÁNH PHẢI (RIGHT SIDE) ---
    const rightTotalLessons = rightChapters.reduce((acc, ch) => acc + Math.max(1, ch.lessons.length), 0);
    const rightTotalHeight = rightTotalLessons * LESSON_HEIGHT + (rightChapters.length - 1) * CHAPTER_GAP;
    let rightCurrentY = -rightTotalHeight / 2;

    rightChapters.forEach((chData) => {
      const chId = `chapter-${chData.chapter.unit_id}`;
      const lessonsCount = Math.max(1, chData.lessons.length);
      const branchHeight = lessonsCount * LESSON_HEIGHT;
      const chapterY = rightCurrentY + branchHeight / 2 - 32;

      // Chapter Node bên Phải (x = 360)
      nodes.push({
        id: chId,
        type: "chapterNode",
        position: { x: 360, y: chapterY },
        data: {
          title: chData.chapter.unit_name ?? `Chương ${chData.chapter.unit_id}`,
          mastery: chData.chapterMastery,
          lessonCount: chData.chapter.lessons?.length ?? 0,
          gapCount: chData.gapCount,
          isGap: chData.chapterMastery < GAP_THRESHOLD,
          side: "right",
        },
      });

      // Edge từ Root (right handle) -> Chapter (target-left handle)
      edges.push({
        id: `edge-root-${chId}`,
        source: "root",
        sourceHandle: "right",
        target: chId,
        targetHandle: "target-left",
        type: "smoothstep",
        style: {
          stroke: chData.chapterMastery < GAP_THRESHOLD || chData.gapCount > 0 ? "#f43f5e" : "#10b981",
          strokeWidth: 2,
        },
      });

      // Lesson Nodes bên Phải (x = 680)
      chData.lessons.forEach((l, lIdx) => {
        const lessonId = `lesson-${l.unit_id}`;
        const lessonY = rightCurrentY + lIdx * LESSON_HEIGHT;
        const lMastery = l.raw_mastery ?? l.mastery;
        const isLGap = lMastery < GAP_THRESHOLD;

        nodes.push({
          id: lessonId,
          type: "lessonNode",
          position: { x: 680, y: lessonY },
          data: {
            lesson: l,
            title: l.lesson || l.unit_name,
            mastery: lMastery,
            isGap: isLGap,
            side: "right",
            nCorrect: l.n_correct,
            nItems: l.n_items,
          },
        });

        // Edge từ Chapter (source-right) -> Lesson
        edges.push({
          id: `edge-${chId}-${lessonId}`,
          source: chId,
          sourceHandle: "source-right",
          target: lessonId,
          type: "smoothstep",
          style: {
            stroke: isLGap ? "#f43f5e" : "#10b981",
            strokeWidth: 1.5,
            strokeDasharray: isLGap ? "4 2" : undefined,
          },
        });
      });

      rightCurrentY += branchHeight + CHAPTER_GAP;
    });

    return {
      initialNodes: nodes,
      initialEdges: edges,
      totalLessonsCount: totalLessons,
      gapLessonsCount: gapLessons,
    };
  }, [gaps, subjectName, studentName, studentCode, filterMode]);

  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);

  // Sync khi gaps hoặc filter thay đổi
  React.useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    if (node.type === "lessonNode" && node.data?.lesson) {
      setSelectedLesson(node.data.lesson as KnowledgeGapItem);
    }
  }, []);

  return (
    <div className="relative w-full h-[660px] rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950 overflow-hidden shadow-inner flex flex-col">
      {/* TOOLBAR BỘ LỌC CỦA GRAPH */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-1.5 p-1 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm text-xs">
        <button
          onClick={() => setFilterMode("all")}
          className={`px-3 py-1 rounded-lg font-semibold transition-all ${
            filterMode === "all"
              ? "bg-brand-600 text-white shadow-xs"
              : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
          }`}
        >
          Tất cả ({totalLessonsCount})
        </button>
        <button
          onClick={() => setFilterMode("gaps")}
          className={`px-3 py-1 rounded-lg font-semibold transition-all flex items-center gap-1 ${
            filterMode === "gaps"
              ? "bg-rose-600 text-white shadow-xs"
              : "text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40"
          }`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
          Bài hổng ({gapLessonsCount})
        </button>
        <button
          onClick={() => setFilterMode("mastered")}
          className={`px-3 py-1 rounded-lg font-semibold transition-all ${
            filterMode === "mastered"
              ? "bg-emerald-600 text-white shadow-xs"
              : "text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/40"
          }`}
        >
          Vững ({totalLessonsCount - gapLessonsCount})
        </button>
      </div>

      {/* REACT FLOW CANVAS */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        fitView
        minZoom={0.2}
        maxZoom={1.5}
        className="bg-slate-50 dark:bg-slate-950"
      >
        <Background color="#94a3b8" gap={18} size={1} />
        <Controls className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 fill-slate-700 dark:fill-slate-200 rounded-xl shadow-md" />
        <MiniMap
          nodeColor={(n) => {
            if (n.type === "rootNode") return "#6366f1";
            if (n.type === "chapterNode") return "#3b82f6";
            if (n.data?.isGap) return "#f43f5e";
            return "#10b981";
          }}
          className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-slate-900/90 shadow-md"
        />
      </ReactFlow>

      {/* FLYOUT CARD CHI TIẾT KHI CLICK VÀO 1 NODE BÀI HỌC */}
      {selectedLesson && (
        <div className="absolute bottom-4 right-4 left-4 sm:left-auto sm:w-96 z-20 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-2xl p-4 animate-in fade-in slide-in-from-bottom-3 duration-200 space-y-3">
          <div className="flex items-start justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-2.5">
            <div className="flex items-center gap-2">
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold ${
                  (selectedLesson.raw_mastery ?? selectedLesson.mastery) < GAP_THRESHOLD
                    ? "bg-rose-100 text-rose-600 dark:bg-rose-950"
                    : "bg-emerald-100 text-emerald-600 dark:bg-emerald-950"
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0">
                <h5 className="font-bold text-xs text-slate-900 dark:text-white truncate">
                  {selectedLesson.lesson || selectedLesson.unit_name}
                </h5>
                <span className="text-[10px] text-slate-400 block truncate">
                  {selectedLesson.chapter || "Chương"}
                </span>
              </div>
            </div>
            <button
              onClick={() => setSelectedLesson(null)}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Chỉ số LMS */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-500 dark:text-slate-400 flex items-center gap-1">
                <Laptop className="w-3.5 h-3.5 text-sky-500" />
                Năng lực LMS:
              </span>
              <span
                className={`font-black font-mono text-sm ${
                  (selectedLesson.raw_mastery ?? selectedLesson.mastery) < GAP_THRESHOLD
                    ? "text-rose-600 dark:text-rose-400"
                    : "text-emerald-600 dark:text-emerald-400"
                }`}
              >
                {fmtPct(selectedLesson.raw_mastery ?? selectedLesson.mastery)}
              </span>
            </div>
            {selectedLesson.n_items ? (
              <span className="text-[11px] text-slate-400 block">
                Kết quả: Đúng <strong>{selectedLesson.n_correct ?? 0}</strong> / {selectedLesson.n_items} câu LMS
              </span>
            ) : null}
          </div>

          {/* Lời khuyên sư phạm */}
          <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-xs space-y-1">
            <div className="flex items-center gap-1 font-bold text-slate-800 dark:text-slate-200 text-[11px]">
              <Lightbulb className="w-3 h-3 text-amber-500" />
              Hướng can thiệp:
            </div>
            <p className="text-slate-600 dark:text-slate-400 text-[11px] leading-relaxed">
              {(selectedLesson.raw_mastery ?? selectedLesson.mastery) < GAP_THRESHOLD
                ? "Cần xếp vào nhóm phụ đạo chuyên đề. Hướng dẫn ôn tập lý thuyết cơ bản trong SGK."
                : "Học sinh nắm vững kiến thức bài này. Khuyến khích thử sức bài tập nâng cao."}
            </p>
          </div>

          {/* Link Xem Giáo án */}
          <div className="pt-1 flex items-center justify-between text-xs">
            <Link
              href={`/lesson-plans?unit_id=${selectedLesson.unit_id}`}
              className="text-brand-600 dark:text-brand-400 font-bold hover:underline inline-flex items-center gap-1 text-[11px]"
            >
              <BookOpen className="w-3.5 h-3.5" />
              Xem Giáo Án Bài Dạy →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
