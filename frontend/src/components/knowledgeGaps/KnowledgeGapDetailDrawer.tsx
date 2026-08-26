"use client";

// Drawer giải thích "TẠI SAO có kết quả lỗ hổng kiến thức này" — Cây Thành thạo (Mastery Tree) theo Bài học & Chương.
// Cho phép giáo viên xem tổng quan theo Chương và mở rộng từng Bài học con bên trong.

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Award,
  BookOpen,
  Brain,
  ChevronDown,
  ChevronRight,
  FileText,
  Info,
  Laptop,
  Lightbulb,
  List,
  Network,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Target,
  User,
  X,
} from "lucide-react";
import type { KnowledgeGapItem } from "@/lib/types";
import StudentKnowledgeGraph from "./StudentKnowledgeGraph";

interface Props {
  studentCode: string;
  studentName: string | null;
  className: string | null;
  subjectName: string;
  gaps: KnowledgeGapItem[];
  onClose: () => void;
}

const CONFIDENCE_META: Record<string, { label: string; cls: string; dotCls: string }> = {
  HIGH: {
    label: "Tin cậy cao",
    cls: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/20",
    dotCls: "bg-emerald-500",
  },
  MEDIUM: {
    label: "Tin cậy TB",
    cls: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/20",
    dotCls: "bg-amber-500",
  },
  LOW: {
    label: "Tin cậy thấp",
    cls: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-500/20",
    dotCls: "bg-rose-500",
  },
  INSUFFICIENT: {
    label: "Chưa đủ dữ liệu",
    cls: "bg-slate-50 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700",
    dotCls: "bg-slate-400",
  },
};

const GAP_THRESHOLD = 0.6;

const fmtPct = (v: number | null | undefined): string =>
  v === null || v === undefined || isNaN(v) ? "—" : `${(v * 100).toFixed(1)}%`;

// Khuyến nghị sư phạm thiết thực cho giáo viên (dựa trên năng lực LMS theo bài)
function getPedagogicalAdvice(g: KnowledgeGapItem, isGap: boolean): { diagnosis: string; recommendation: string } {
  const raw = g.raw_mastery ?? 0;

  if (isGap) {
    if (g.n_items && g.n_items > 0 && g.n_correct !== undefined) {
      return {
        diagnosis: `Học sinh gặp khó khăn ở bài/chương này (chỉ đúng ${g.n_correct}/${g.n_items} câu LMS → năng lực ${fmtPct(raw)}).`,
        recommendation: "Cần xếp vào nhóm phụ đạo chuyên đề. Hướng dẫn ôn tập lại các khái niệm cơ bản và làm các bài tập mức Nhận biết - Thông hiểu trước.",
      };
    }
    return {
      diagnosis: `Năng lực LMS bài/chương này chưa đạt yêu cầu (${fmtPct(raw)}).`,
      recommendation: "Đề xuất giao phiếu bài tập củng cố và hướng dẫn học sinh xem lại lý thuyết trong SGK.",
    };
  }

  return {
    diagnosis: `Học sinh nắm kiến thức tốt trên LMS (${fmtPct(raw)}).`,
    recommendation: "Khuyến khích học sinh thử sức với các bài tập vận dụng cao hoặc hỗ trợ các bạn còn yếu trong nhóm.",
  };
}

export default function KnowledgeGapDetailDrawer({
  studentCode,
  studentName,
  className,
  subjectName,
  gaps,
  onClose,
}: Props) {
  // Chế độ xem: "list" (Danh sách) hoặc "graph" (Cây Node Graph)
  const [viewMode, setViewMode] = useState<"graph" | "list">("graph");

  // Trạng thái mở rộng các chương (mặc định mở các chương có bài hổng)
  const [expandedChapters, setExpandedChapters] = useState<Record<number, boolean>>(() => {
    const init: Record<number, boolean> = {};
    gaps.forEach((g) => {
      // Mở sẵn nếu chương đó có bài hổng hoặc bản thân chương < 60%
      if ((g.gap_lessons_count ?? 0) > 0 || g.mastery < GAP_THRESHOLD) {
        init[g.unit_id] = true;
      }
    });
    return init;
  });

  const [openAccordion, setOpenAccordion] = useState<Record<number, boolean>>({});

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const toggleChapter = (unitId: number) => {
    setExpandedChapters((prev) => ({ ...prev, [unitId]: !prev[unitId] }));
  };

  const toggleAccordion = (unitId: number) => {
    setOpenAccordion((prev) => ({ ...prev, [unitId]: !prev[unitId] }));
  };

  // Đếm tổng số bài hổng trên toàn bộ các chương
  let totalGapLessons = 0;
  let totalLessons = 0;
  gaps.forEach((ch) => {
    if (ch.lessons && ch.lessons.length > 0) {
      totalLessons += ch.lessons.length;
      totalGapLessons += ch.lessons.filter((l) => (l.raw_mastery ?? l.mastery) < GAP_THRESHOLD).length;
    } else {
      totalLessons += 1;
      if (ch.mastery < GAP_THRESHOLD) totalGapLessons += 1;
    }
  });

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-sm flex justify-end transition-opacity">
      {/* Backdrop */}
      <div className="absolute inset-0" onClick={onClose} />

      {/* Drawer Panel */}
      <div className="relative w-full max-w-4xl lg:max-w-5xl bg-white dark:bg-slate-900 shadow-2xl h-full flex flex-col border-l border-slate-200 dark:border-slate-800 z-10 animate-in slide-in-from-right duration-300">
        {/* HEADER */}
        <div className="p-5 sm:p-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/70 flex items-start justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-500 to-brand-600 flex items-center justify-center text-white shrink-0 shadow-md">
              <User className="w-6 h-6" />
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2.5 flex-wrap">
                <h3 className="text-xl font-bold text-slate-900 dark:text-white">
                  {studentName || studentCode}
                </h3>
                <span className="px-2 py-0.5 text-xs font-mono font-semibold rounded-md bg-slate-200/70 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                  {studentCode}
                </span>
                {totalGapLessons > 0 ? (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-500/20">
                    <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />
                    {totalGapLessons} bài cần củng cố
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/20">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                    Đạt chuẩn toàn bộ bài học
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2 flex-wrap">
                <span>
                  Lớp: <strong className="text-slate-700 dark:text-slate-200">{className || "—"}</strong>
                </span>
                <span className="text-slate-300 dark:text-slate-600">•</span>
                <span>
                  Môn: <strong className="text-brand-600 dark:text-brand-400">{subjectName}</strong>
                </span>
                <span className="text-slate-300 dark:text-slate-600">•</span>
                <span>
                  Cây tri thức: <strong>{gaps.length} chương ({totalLessons} bài học)</strong>
                </span>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800 transition-colors"
            title="Đóng (Esc)"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* BODY */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-5 flex flex-col">
          {/* TOOLBAR CHUYỂN ĐỔI VIEW: GRAPH VS LIST */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-slate-100 dark:border-slate-800 shrink-0">
            <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-100 dark:bg-slate-800/80 text-xs font-semibold">
              <button
                onClick={() => setViewMode("graph")}
                className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
                  viewMode === "graph"
                    ? "bg-white dark:bg-slate-900 text-brand-600 dark:text-brand-400 shadow-xs font-bold"
                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
              >
                <Network className="w-3.5 h-3.5" />
                <span>🕸️ Cây Node Graph</span>
              </button>
              <button
                onClick={() => setViewMode("list")}
                className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
                  viewMode === "list"
                    ? "bg-white dark:bg-slate-900 text-brand-600 dark:text-brand-400 shadow-xs font-bold"
                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
              >
                <List className="w-3.5 h-3.5" />
                <span>📋 Danh Sách Phân Cấp</span>
              </button>
            </div>

            <span className="text-xs text-slate-400">
              {viewMode === "graph" ? "Kéo chuột & nhấp vào node để xem chi tiết" : `${totalGapLessons} bài cần củng cố • ${totalLessons - totalGapLessons} bài vững vàng`}
            </span>
          </div>

          {/* VIEW 1: CÂY NODE GRAPH (REACT FLOW) */}
          {viewMode === "graph" && (
            <div className="flex-1 min-h-[580px]">
              <StudentKnowledgeGraph
                subjectName={subjectName}
                studentName={studentName}
                studentCode={studentCode}
                gaps={gaps}
              />
            </div>
          )}

          {/* VIEW 2: DANH SÁCH PHÂN CẤP (LIST ACCORDION) */}
          {viewMode === "list" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-2">
                  <Brain className="w-4 h-4 text-brand-500" />
                  Cây Năng Lực theo Chương & Bài Học ({gaps.length} chương)
                </h4>
                <span className="text-xs text-slate-400">
                  {totalGapLessons} bài cần củng cố • {totalLessons - totalGapLessons} bài vững vàng
                </span>
              </div>

            {gaps.map((chapter) => {
              const childLessons = chapter.lessons ?? [];
              const chapterLms = chapter.raw_mastery ?? (childLessons.length > 0
                ? childLessons.reduce((acc, l) => acc + (l.raw_mastery ?? l.mastery), 0) / childLessons.length
                : chapter.mastery);
              const rawGapLessonsCount = childLessons.length > 0
                ? childLessons.filter((l) => (l.raw_mastery ?? l.mastery) < GAP_THRESHOLD).length
                : (chapterLms < GAP_THRESHOLD ? 1 : 0);
              const isChGap = chapterLms < GAP_THRESHOLD;
              const hasWeakLessons = rawGapLessonsCount > 0;
              const isExpanded = !!expandedChapters[chapter.unit_id];

              return (
                <div
                  key={chapter.unit_id}
                  className={`rounded-2xl border transition-all duration-200 overflow-hidden ${
                    hasWeakLessons || isChGap
                      ? "border-rose-200/80 dark:border-rose-900/50 bg-white dark:bg-slate-900 shadow-sm"
                      : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs"
                  }`}
                >
                  {/* CHAPTER HEADER (NODE CHA) */}
                  <div
                    onClick={() => toggleChapter(chapter.unit_id)}
                    className="p-4 sm:p-5 border-b border-slate-100 dark:border-slate-800/80 flex items-center justify-between gap-3 bg-slate-50/70 dark:bg-slate-950/50 cursor-pointer hover:bg-slate-100/60 dark:hover:bg-slate-900/80 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="text-slate-400 hover:text-slate-600 transition-colors">
                        {isExpanded ? (
                          <ChevronDown className="w-5 h-5 text-brand-600 dark:text-brand-400" />
                        ) : (
                          <ChevronRight className="w-5 h-5" />
                        )}
                      </div>
                      <div
                        className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                          hasWeakLessons || isChGap
                            ? "bg-rose-100 text-rose-600 dark:bg-rose-500/20 dark:text-rose-400"
                            : "bg-emerald-100 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400"
                        }`}
                      >
                        {hasWeakLessons || isChGap ? (
                          <Target className="w-5 h-5" />
                        ) : (
                          <Award className="w-5 h-5" />
                        )}
                      </div>
                      <div>
                        <h5 className="font-bold text-sm sm:text-base text-slate-900 dark:text-white flex items-center gap-2">
                          {chapter.unit_name ?? `Chương ${chapter.unit_id}`}
                        </h5>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                          {childLessons.length > 0
                            ? `${childLessons.length} bài học • ${rawGapLessonsCount > 0 ? `${rawGapLessonsCount} bài cần củng cố` : "Đạt chuẩn LMS"}`
                            : "Đánh giá cấp chương"}
                        </p>
                      </div>
                    </div>

                    {/* Chương Mastery Badge & Progress */}
                    <div className="flex items-center gap-4">
                      <div className="hidden sm:block text-right">
                        <span className="text-xs text-slate-400 block font-medium">Năng lực LMS:</span>
                        <div className="flex items-baseline gap-1.5 justify-end">
                          <span
                            className={`font-black text-sm sm:text-base ${
                              chapterLms >= 0.7
                                ? "text-emerald-600 dark:text-emerald-400"
                                : chapterLms >= 0.5
                                ? "text-amber-600 dark:text-amber-400"
                                : "text-rose-600 dark:text-rose-400"
                            }`}
                          >
                            {fmtPct(chapterLms)}
                          </span>
                          {chapter.mastery !== undefined && chapter.mastery !== null && (
                            <span className="text-[11px] text-slate-400 dark:text-slate-500 font-normal">
                              (Tham chiếu thi: {fmtPct(chapter.mastery)})
                            </span>
                          )}
                        </div>
                      </div>
                      <span
                        className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                          hasWeakLessons || isChGap
                            ? "bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300"
                            : "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300"
                        }`}
                      >
                        {hasWeakLessons ? `Hổng ${rawGapLessonsCount} bài LMS` : "Đạt chuẩn LMS"}
                      </span>
                    </div>
                  </div>

                  {/* EXPANDED CONTENT: DANH SÁCH BÀI HỌC CON */}
                  {isExpanded && (
                    <div className="p-4 sm:p-5 space-y-4 bg-slate-50/20 dark:bg-slate-950/20">
                      {childLessons.length > 0 ? (
                        <div className="space-y-3">
                          {childLessons.map((lesson) => {
                            const isLessonGap = (lesson.raw_mastery ?? lesson.mastery) < GAP_THRESHOLD;
                            const conf = CONFIDENCE_META[lesson.confidence ?? "LOW"] ?? CONFIDENCE_META.LOW;
                            const advice = getPedagogicalAdvice(lesson, isLessonGap);
                            const isAccOpen = !!openAccordion[lesson.unit_id];

                            return (
                              <div
                                key={lesson.unit_id}
                                className={`p-4 rounded-xl border transition-all ${
                                  isLessonGap
                                    ? "bg-white dark:bg-slate-900 border-rose-200 dark:border-rose-900/60 shadow-xs"
                                    : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800"
                                }`}
                              >
                                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
                                  <div className="flex items-start gap-2.5">
                                    <FileText className={`w-4 h-4 mt-0.5 shrink-0 ${isLessonGap ? "text-rose-500" : "text-emerald-500"}`} />
                                    <div>
                                      <h6 className="font-bold text-sm text-slate-900 dark:text-slate-100">
                                        {lesson.lesson || lesson.unit_name}
                                      </h6>
                                      {lesson.summary && (
                                        <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">
                                          {lesson.summary}
                                        </p>
                                      )}
                                    </div>
                                  </div>

                                  <div className="flex items-center gap-2 flex-wrap sm:justify-end">
                                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${conf.cls}`}>
                                      <span className={`w-1.5 h-1.5 rounded-full ${conf.dotCls}`} />
                                      {conf.label}
                                    </span>
                                    <span className={`px-2 py-0.5 rounded-md text-xs font-bold ${isLessonGap ? "bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300"}`}>
                                      {fmtPct(lesson.raw_mastery ?? lesson.mastery)}
                                    </span>
                                  </div>
                                </div>

                                {/* Năng lực LMS (theo bài) — số chính */}
                                <div className="pt-3 space-y-2.5">
                                    <div className="flex items-center justify-between text-xs">
                                      <span className="flex items-center gap-1.5 text-slate-700 dark:text-slate-200 font-semibold">
                                        <Laptop className="w-3.5 h-3.5 text-sky-500" />
                                        Năng lực LMS (theo bài): {lesson.n_items ? `(Đúng ${lesson.n_correct ?? 0}/${lesson.n_items} câu)` : "(Chưa có câu hỏi)"}
                                      </span>
                                      <span className={`font-black text-sm ${isLessonGap ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                                        {fmtPct(lesson.raw_mastery ?? lesson.mastery)}
                                      </span>
                                    </div>
                                    <div className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                      <div
                                        className={`h-full rounded-full ${isLessonGap ? "bg-gradient-to-r from-rose-500 to-amber-500" : "bg-emerald-500"}`}
                                        style={{ width: `${Math.min(100, Math.max(5, (lesson.raw_mastery ?? lesson.mastery ?? 0) * 100))}%` }}
                                      />
                                    </div>
                                    {/* Tham chiếu sau đối soát điểm thi */}
                                    {lesson.mastery !== undefined && lesson.mastery !== null && (
                                      <div className="text-[11px] text-slate-400 dark:text-slate-500 flex items-center justify-between pt-0.5">
                                        <span>Tham chiếu sau đối soát điểm thi: <strong className="text-slate-600 dark:text-slate-300 font-semibold">{fmtPct(lesson.mastery)}</strong></span>
                                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">Chỉ tham khảo</span>
                                      </div>
                                    )}
                                </div>

                                {/* Khuyến nghị sư phạm */}
                                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 text-xs space-y-1 mt-3">
                                  <div className="flex items-center gap-1.5 font-bold text-slate-800 dark:text-slate-200">
                                    <Lightbulb className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                                    Hướng can thiệp sư phạm:
                                  </div>
                                  <p className="text-slate-600 dark:text-slate-400 leading-relaxed pl-5">
                                    {advice.recommendation}
                                  </p>
                                </div>

                                {/* Nút xem giáo án & Accordion công thức */}
                                <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800/60 mt-3">
                                  <Link
                                    href={`/lesson-plans?unit_id=${lesson.unit_id}`}
                                    className="text-[11px] font-bold text-brand-600 dark:text-brand-400 hover:underline inline-flex items-center gap-1.5"
                                  >
                                    <BookOpen className="w-3.5 h-3.5" />
                                    Xem Giáo Án Bài Dạy
                                  </Link>

                                  <button
                                    onClick={() => toggleAccordion(lesson.unit_id)}
                                    className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 hover:underline flex items-center gap-1"
                                  >
                                    <Info className="w-3 h-3" />
                                    {isAccOpen ? "Ẩn công thức" : "Xem công thức"}
                                  </button>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        /* Nếu chương chưa có bài con (fallback) */
                        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-3">
                          <div className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="font-bold text-slate-700 dark:text-slate-200">
                                Độ thành thạo chương:
                              </span>
                              <span className={`font-black ${isChGap ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                                {fmtPct(chapter.mastery)}
                              </span>
                            </div>
                            <div className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${isChGap ? "bg-rose-500" : "bg-emerald-500"}`}
                                style={{ width: `${Math.min(100, Math.max(5, chapter.mastery * 100))}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
