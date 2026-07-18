"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, BookOpen, Loader2, RefreshCw, X } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { ExamAnalysisItem, ExamContentAnalysis, ExamPaperDetail } from "@/lib/types";
import { LoadingState } from "@/components/Loading";

interface Props {
  paperId: string;
  onClose: () => void;
}

export default function ExamAnalysisDrawer({ paperId, onClose }: Props) {
  const [paper, setPaper] = useState<ExamPaperDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analysis = paper?.ai_analysis?.content_analysis;

  const load = () => {
    setLoading(true);
    setError(null);
    api
      .get<ExamPaperDetail>(`/exam-papers/${paperId}`)
      .then(setPaper)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Không tải được phân tích đề"))
      .finally(() => setLoading(false));
  };

  useEffect(load, [paperId]);

  const triggerAnalyze = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/exam-papers/${paperId}/analyze`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không gửi được yêu cầu phân tích lại");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-stretch justify-end bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-3xl bg-white dark:bg-slate-900 shadow-2xl flex flex-col h-full"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800 shrink-0">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-white">Phân tích nội dung đề</h3>
            {paper && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{paper.title}</p>}
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {loading ? (
            <LoadingState message="Đang tải phân tích đề..." />
          ) : !paper ? (
            <EmptyAnalysis error={error} onAnalyze={triggerAnalyze} busy={busy} />
          ) : !analysis || analysis.version !== 1 ? (
            <EmptyAnalysis error={error} onAnalyze={triggerAnalyze} busy={busy} />
          ) : (
            <AnalysisBody paper={paper} analysis={analysis} error={error} />
          )}
        </div>
      </div>
    </div>
  );
}

function EmptyAnalysis({ error, onAnalyze, busy }: { error: string | null; onAnalyze: () => void; busy: boolean }) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center gap-3 text-slate-500 dark:text-slate-400">
      <BookOpen className="w-10 h-10 text-brand-500" />
      <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Đề chưa được phân tích nội dung chi tiết</p>
      {error && <p className="text-xs text-rose-600 dark:text-rose-300">{error}</p>}
      <button
        onClick={onAnalyze}
        disabled={busy}
        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
      >
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
        Phân tích lại
      </button>
    </div>
  );
}

function AnalysisBody({
  paper,
  analysis,
  error,
}: {
  paper: ExamPaperDetail;
  analysis: ExamContentAnalysis;
  error: string | null;
}) {
  return (
    <>
      {error && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
          {error}
        </div>
      )}
      <HeaderSummary paper={paper} analysis={analysis} />
      <RiskBadges analysis={analysis} />
      <CoverageBar analysis={analysis} />
      <ItemsTable items={analysis.items} />
    </>
  );
}

function HeaderSummary({ paper, analysis }: { paper: ExamPaperDetail; analysis: ExamContentAnalysis }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">CDI nội dung</p>
        <p className="text-3xl font-bold text-slate-900 dark:text-white">{analysis.cdi.toFixed(2)}</p>
      </div>
      <div className="text-right text-xs text-slate-500 dark:text-slate-400">
        <p>{paper.content_analyzed_at ? formatDate(paper.content_analyzed_at) : "Chưa có thời điểm phân tích"}</p>
        {analysis.model && <p>Model: {analysis.model}</p>}
      </div>
    </div>
  );
}

function RiskBadges({ analysis }: { analysis: ExamContentAnalysis }) {
  const offRatio = analysis.off_curriculum_weight == null ? 0 : analysis.off_curriculum_weight * 100;
  return (
    <div className="flex flex-wrap gap-2">
      {analysis.concentration.is_concentrated && (
        <Badge tone="amber" title={`${analysis.concentration.top_unit_name ?? "Chủ đề chính"} chiếm ${formatPct(analysis.concentration.top_share)}`}>
          Lệch tủ
        </Badge>
      )}
      {analysis.rag_available && analysis.off_curriculum_weight != null && analysis.off_curriculum_weight > 0 && (
        <Badge tone="rose">Ngoài chương trình {offRatio.toFixed(0)}%</Badge>
      )}
      {!analysis.rag_available && <Badge tone="slate">Chưa đối chiếu SGK</Badge>}
    </div>
  );
}

function CoverageBar({ analysis }: { analysis: ExamContentAnalysis }) {
  const totalWeight = useMemo(() => analysis.coverage_units.reduce((sum, unit) => sum + unit.weight, 0), [analysis]);
  if (analysis.coverage.catalog_total === 0) return null;
  return (
    <div className="space-y-2">
      <div className="flex h-5 w-full overflow-hidden rounded bg-slate-100 dark:bg-slate-800">
        {analysis.coverage_units.map((unit) => {
          const basis = totalWeight > 0 && unit.weight > 0 ? `${(unit.weight / totalWeight) * 100}%` : "24px";
          return (
            <div
              key={unit.unit_code}
              title={`${unit.unit_name}: ${(unit.weight * 100).toFixed(0)}%`}
              className={unit.weight > 0 ? "bg-brand-500 border-r border-white/50" : "bg-slate-200 dark:bg-slate-700 border-r border-white/20"}
              style={{ flex: `0 0 ${basis}` }}
            />
          );
        })}
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Phủ {analysis.coverage.matched}/{analysis.coverage.catalog_total} chủ đề ({formatPct(analysis.coverage.ratio)})
      </p>
    </div>
  );
}

function ItemsTable({ items }: { items: ExamAnalysisItem[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
            <th className="py-2 px-3">Chủ đề</th>
            <th className="py-2 px-3 text-right">Bloom</th>
            <th className="py-2 px-3 text-right">Trọng số</th>
            <th className="py-2 px-3">Nguồn SGK</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={`${item.topic}-${index}`} className="border-b border-slate-100 dark:border-slate-800/60 align-top">
              <td className="py-3 px-3 min-w-56">
                <p className="font-medium text-slate-800 dark:text-slate-100">{item.topic}</p>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {item.unit_code && <span className="px-1.5 py-0.5 rounded bg-brand-50 dark:bg-brand-500/10 text-[11px] text-brand-700 dark:text-brand-300">{item.unit_code}</span>}
                  {!item.matched_catalog && <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[11px] text-slate-500">ngoài catalog</span>}
                </div>
                {item.excerpt && <p className="mt-1 text-xs italic text-slate-500 dark:text-slate-400">{item.excerpt}</p>}
              </td>
              <td className="py-3 px-3 text-right text-slate-700 dark:text-slate-300">{item.bloom_level}</td>
              <td className="py-3 px-3 text-right text-slate-700 dark:text-slate-300">{(item.weight * 100).toFixed(0)}%</td>
              <td className="py-3 px-3 text-slate-600 dark:text-slate-300 min-w-52">
                <EvidenceCell item={item} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EvidenceCell({ item }: { item: ExamAnalysisItem }) {
  if (item.evidence) {
    return (
      <span className="text-xs">
        <BookOpen className="inline w-3.5 h-3.5 mr-1 text-brand-500" />
        {[item.evidence.heading, item.evidence.source_md].filter(Boolean).join(" - ") || "Nguồn SGK"}
        {` (${(item.evidence.score * 100).toFixed(0)}%)`}
      </span>
    );
  }
  if (item.off_curriculum === true) {
    return <span className="text-xs font-medium text-amber-600 dark:text-amber-300">Không tìm thấy trong SGK</span>;
  }
  return <span className="text-xs text-slate-400">-</span>;
}

function Badge({ children, tone, title }: { children: React.ReactNode; tone: "amber" | "rose" | "slate"; title?: string }) {
  const cls = {
    amber: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
    rose: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300",
    slate: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  }[tone];
  return (
    <span title={title} className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-semibold ${cls}`}>
      {(tone === "amber" || tone === "rose") && <AlertTriangle className="w-3.5 h-3.5" />}
      {children}
    </span>
  );
}

function formatPct(value: number | null): string {
  return value == null ? "-" : `${(value * 100).toFixed(0)}%`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
