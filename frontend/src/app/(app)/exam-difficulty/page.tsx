"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Gauge,
  Layers,
  Loader2,
  ShieldAlert,
  Sparkles,
  X,
} from "lucide-react";
import SearchableSelect from "@/components/SearchableSelect";
import { api } from "@/lib/api";
import { ExamContentAnalysis, ExamValidityRow, SchoolValidityOverview } from "@/lib/types";

// Cấu hình Cờ Cảnh Báo Tam Giác Hóa
const FLAG_CONFIG: Record<string, { label: string; cls: string; desc: string; icon: any }> = {
  NORMAL: {
    label: "Bình thường",
    cls: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800",
    desc: "Độ khó thực nghiệm (EDI) tương thích tốt với độ khó nội dung (CDI).",
    icon: CheckCircle2,
  },
  INFLATION_OR_LEAK: {
    label: "Lạm phát điểm / Nghi vấn lộ đề",
    cls: "bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300 border-rose-300 dark:border-rose-800",
    desc: "Điểm thi thực tế cao bất thường so với nội dung đề thi khó.",
    icon: ShieldAlert,
  },
  LEARNING_GAP: {
    label: "Lỗ hổng kiến thức diện rộng",
    cls: "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300 border-amber-300 dark:border-amber-800",
    desc: "Điểm thi thấp bất thường dù đề thi ở mức cơ bản / dễ.",
    icon: AlertTriangle,
  },
};

export default function ExamDifficultyPage() {
  const [subjects, setSubjects] = useState<{ id: string; name: string }[]>([]);
  const [subjectId, setSubjectId] = useState<string>("");
  const [gradeId, setGradeId] = useState<string>("");
  const [semester, setSemester] = useState<string>("1");
  const [flaggedOnly, setFlaggedOnly] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validityRows, setValidityRows] = useState<ExamValidityRow[]>([]);
  const [overview, setOverview] = useState<SchoolValidityOverview | null>(null);

  // Drawer chi tiết đề
  const [selectedExam, setSelectedExam] = useState<ExamValidityRow | null>(null);
  const [examDetail, setExamDetail] = useState<any | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [contentAnalysis, setContentAnalysis] = useState<ExamContentAnalysis | null>(null);

  // Load danh sách môn học
  useEffect(() => {
    api
      .get<{ subjects: { id: number; name: string }[] }>("/ews/meta")
      .then((meta) => {
        const seen = new Map<string, string>();
        for (const s of meta.subjects) {
          if (!seen.has(s.name)) seen.set(s.name, String(s.id));
        }
        setSubjects(Array.from(seen, ([name, id]) => ({ id, name })));
      })
      .catch(() => setError("Không tải được danh mục môn học."));
  }, []);

  // Fetch dữ liệu tam giác hóa
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        flagged_only: String(flaggedOnly),
      });
      if (subjectId) params.set("subject_id", subjectId);

      const [rows, ov] = await Promise.allSettled([
        api.get<ExamValidityRow[]>(`/analytics/exam-validity?${params.toString()}`),
        api.get<SchoolValidityOverview>("/analytics/exam-validity/overview"),
      ]);

      if (rows.status === "fulfilled") {
        setValidityRows(rows.value || []);
      } else {
        setValidityRows([]);
      }

      if (ov.status === "fulfilled") {
        setOverview(ov.value);
      }
    } catch (e: any) {
      setError(e?.message ?? "Lỗi khi tải bảng tam giác hóa độ khó đề.");
      setValidityRows([]);
    } finally {
      setLoading(false);
    }
  }, [subjectId, flaggedOnly]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Xem chi tiết đề
  const handleOpenDetail = async (row: ExamValidityRow) => {
    setSelectedExam(row);
    setDetailLoading(true);
    setExamDetail(null);
    setContentAnalysis(null);
    try {
      const [detail, ca] = await Promise.allSettled([
        api.get(`/exam-papers/${row.exam_paper_id}`),
        api.get<ExamContentAnalysis>(`/exam-papers/${row.exam_paper_id}/content-analysis`),
      ]);
      if (detail.status === "fulfilled") setExamDetail(detail.value);
      if (ca.status === "fulfilled") setContentAnalysis(ca.value);
    } catch {
      setExamDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-[1500px] mx-auto space-y-6">
      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-brand-50 dark:bg-brand-950/50 text-brand-600 dark:text-brand-400 border border-brand-100 dark:border-brand-900/50">
              <Gauge className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
              Phân tích độ khó đề thi (TEVI)
            </h2>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Tam giác hóa Độ khó thực nghiệm (EDI) vs Độ khó nội dung AI (CDI) để phát hiện lệch chuẩn & lỗ hổng kiến thức.
          </p>
        </div>
      </header>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-4 shadow-sm">
          <span className="text-xs font-semibold text-slate-500 block">Tổng số đề kiểm tra</span>
          <span className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            {overview?.total_checked ?? validityRows.length}
          </span>
        </div>
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-4 shadow-sm">
          <span className="text-xs font-semibold text-emerald-600 block">Chuẩn bình thường</span>
          <span className="text-2xl font-bold text-emerald-600">
            {overview?.flags_count?.NORMAL ?? validityRows.filter((r) => r.flag === "NORMAL").length}
          </span>
        </div>
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-4 shadow-sm">
          <span className="text-xs font-semibold text-rose-600 block">Cảnh báo lạm phát / Lộ đề</span>
          <span className="text-2xl font-bold text-rose-600">
            {overview?.flags_count?.INFLATION_OR_LEAK ??
              validityRows.filter((r) => r.flag === "INFLATION_OR_LEAK").length}
          </span>
        </div>
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-4 shadow-sm">
          <span className="text-xs font-semibold text-amber-600 block">Lỗ hổng diện rộng</span>
          <span className="text-2xl font-bold text-amber-600">
            {overview?.flags_count?.LEARNING_GAP ?? validityRows.filter((r) => r.flag === "LEARNING_GAP").length}
          </span>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white dark:bg-slate-900 border rounded-2xl p-4 flex flex-wrap items-end gap-3 shadow-sm">
        <div className="min-w-[180px]">
          <label className="text-xs font-semibold text-slate-500 mb-1 block">Môn học</label>
          <SearchableSelect
            options={[{ value: "", label: "Tất cả các môn" }, ...subjects.map((s) => ({ value: s.id, label: s.name }))]}
            value={subjectId}
            onChange={setSubjectId}
            placeholder="Chọn môn..."
            className="min-w-[180px]"
          />
        </div>
        <div className="min-w-[130px]">
          <label className="text-xs font-semibold text-slate-500 mb-1 block">Khối</label>
          <SearchableSelect
            options={[
              { value: "", label: "Tất cả khối" },
              { value: "6", label: "Khối 6" },
              { value: "7", label: "Khối 7" },
              { value: "8", label: "Khối 8" },
              { value: "9", label: "Khối 9" },
            ]}
            value={gradeId}
            onChange={setGradeId}
            className="min-w-[130px]"
          />
        </div>
        <div className="min-w-[120px]">
          <label className="text-xs font-semibold text-slate-500 mb-1 block">Học kỳ</label>
          <SearchableSelect
            options={[
              { value: "1", label: "Học kỳ 1" },
              { value: "2", label: "Học kỳ 2" },
            ]}
            value={semester}
            onChange={setSemester}
            className="min-w-[120px]"
          />
        </div>
        <label className="flex items-center gap-2 cursor-pointer pb-2.5 text-xs font-medium text-slate-700 dark:text-slate-300">
          <input
            type="checkbox"
            checked={flaggedOnly}
            onChange={(e) => setFlaggedOnly(e.target.checked)}
            className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          <span>Chỉ hiện đề có cờ bất thường</span>
        </label>
        <button
          onClick={fetchData}
          disabled={loading}
          className="px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 ml-auto"
        >
          {loading ? "Đang tải..." : "Làm mới"}
        </button>
      </div>

      {error && (
        <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 px-4 py-3 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </div>
      )}

      {/* Table Tam Giác Hóa */}
      <section className="bg-white dark:bg-slate-900 border rounded-2xl shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <h3 className="font-semibold text-slate-900 dark:text-slate-100">
            Bảng ma trận đối soát độ khó đề thi
          </h3>
          <span className="text-xs text-slate-400">
            Hiển thị {validityRows.length} bài kiểm tra
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                <th className="px-5 py-3">Môn & Khối</th>
                <th className="px-5 py-3">Kỳ thi</th>
                <th className="px-5 py-3 text-right">Mẫu (n)</th>
                <th className="px-5 py-3 text-right">ĐTB</th>
                <th className="px-5 py-3 text-right" title="Độ khó thực nghiệm từ điểm số (1 - p_value)">
                  EDI
                </th>
                <th className="px-5 py-3 text-right" title="Độ khó nội dung từ Bloom + RAG SGK">
                  CDI
                </th>
                <th className="px-5 py-3 text-right" title="Độ lệch (EDI - CDI)">
                  Divergence
                </th>
                <th className="px-5 py-3">Đánh giá cờ</th>
                <th className="px-5 py-3 text-center">Tin cậy</th>
                <th className="px-5 py-3 text-center">Chi tiết</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
              {validityRows.map((row, idx) => {
                const flagCfg = FLAG_CONFIG[row.flag] || FLAG_CONFIG.NORMAL;
                const FlagIcon = flagCfg.icon;
                return (
                  <tr
                    key={idx}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                  >
                    <td className="px-5 py-3.5 font-medium text-slate-900 dark:text-slate-100">
                      {row.subject_name}{" "}
                      <span className="text-xs text-slate-400 font-normal">({row.grade_name})</span>
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-600 dark:text-slate-300">
                      {row.score_category === "FINAL" ? "Cuối kỳ" : row.score_category === "MIDTERM" ? "Giữa kỳ" : "Thường xuyên"}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-xs text-slate-500">{row.n}</td>
                    <td className="px-5 py-3.5 text-right font-bold text-slate-800 dark:text-slate-200">
                      {row.mean_score.toFixed(2)}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono font-semibold text-indigo-600 dark:text-indigo-400">
                      {row.edi.toFixed(2)}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono font-semibold text-violet-600 dark:text-violet-400">
                      {row.cdi !== null ? row.cdi.toFixed(2) : "—"}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-xs">
                      {row.divergence !== null ? (
                        <span
                          className={`font-semibold ${
                            row.divergence > 0.2
                              ? "text-amber-600"
                              : row.divergence < -0.2
                              ? "text-rose-600"
                              : "text-slate-500"
                          }`}
                        >
                          {row.divergence > 0 ? `+${row.divergence.toFixed(2)}` : row.divergence.toFixed(2)}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${flagCfg.cls}`}
                        title={flagCfg.desc}
                      >
                        <FlagIcon className="w-3.5 h-3.5 shrink-0" />
                        {flagCfg.label}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                        {row.confidence}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      <button
                        onClick={() => handleOpenDetail(row)}
                        className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 hover:text-brand-600 transition-colors"
                        title="Xem phân tích chi tiết đề"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Drawer Chi Tiết Phân Tích Đề */}
      {selectedExam && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-sm flex justify-end transition-opacity">
          <div className="absolute inset-0" onClick={() => setSelectedExam(null)} />
          <div className="relative w-full max-w-xl bg-white dark:bg-slate-900 shadow-2xl h-full flex flex-col border-l border-slate-200 dark:border-slate-800 z-10 animate-in slide-in-from-right duration-300">
            {/* Drawer Header */}
            <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-start justify-between">
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                  Chi tiết phân tích đề thi
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {selectedExam.subject_name} — {selectedExam.grade_name} ({selectedExam.score_category})
                </p>
              </div>
              <button
                onClick={() => setSelectedExam(null)}
                className="p-2 rounded-xl text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              {detailLoading ? (
                <div className="flex items-center justify-center py-16 text-slate-400">
                  <Loader2 className="w-6 h-6 animate-spin mr-2" /> Đang tải phân tích đề...
                </div>
              ) : (
                <>
                  {/* Metric Box */}
                  <div className="grid grid-cols-3 gap-3 p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                    <div>
                      <span className="text-[11px] text-slate-400 block font-medium">EDI (Thực nghiệm)</span>
                      <span className="text-xl font-black text-indigo-600 dark:text-indigo-400">
                        {selectedExam.edi.toFixed(2)}
                      </span>
                    </div>
                    <div>
                      <span className="text-[11px] text-slate-400 block font-medium">CDI (Nội dung)</span>
                      <span className="text-xl font-black text-violet-600 dark:text-violet-400">
                        {selectedExam.cdi !== null ? selectedExam.cdi.toFixed(2) : "—"}
                      </span>
                    </div>
                    <div>
                      <span className="text-[11px] text-slate-400 block font-medium">Độ lệch (Divergence)</span>
                      <span
                        className={`text-xl font-black ${
                          (selectedExam.divergence ?? 0) > 0.2
                            ? "text-amber-600"
                            : (selectedExam.divergence ?? 0) < -0.2
                            ? "text-rose-600"
                            : "text-slate-700 dark:text-slate-300"
                        }`}
                      >
                        {selectedExam.divergence !== null
                          ? selectedExam.divergence > 0
                            ? `+${selectedExam.divergence.toFixed(2)}`
                            : selectedExam.divergence.toFixed(2)
                          : "—"}
                      </span>
                    </div>
                  </div>

                  {/* Phân bố Bloom */}
                  {(() => {
                    const analysis = examDetail?.ai_analysis?.content_analysis || examDetail?.ai_analysis;
                    const dist = analysis?.bloom_distribution || {
                      remember: 40,
                      understand: 30,
                      apply: 20,
                      analyze: 10,
                    };
                    const hasAnalysis = Boolean(analysis?.bloom_distribution);

                    return (
                      <div className="space-y-3 p-4 rounded-2xl border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">
                        <div className="flex items-center justify-between">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                            <Sparkles className="w-4 h-4 text-brand-500" />
                            Phân bố mức độ tư duy Bloom (Chuẩn 40/30/20/10)
                          </h4>
                          {analysis?.bloom_alignment && (
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                              analysis.bloom_alignment === "ALIGNED"
                                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
                                : analysis.bloom_alignment === "BIASED_HARD"
                                ? "bg-rose-50 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300"
                                : "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300"
                            }`}>
                              {analysis.bloom_alignment === "ALIGNED" ? "Cân đối" : analysis.bloom_alignment === "BIASED_HARD" ? "Đề lệch khó" : "Đề lệch dễ"}
                            </span>
                          )}
                        </div>

                        {!hasAnalysis && (
                          <p className="text-[11px] text-slate-400 italic">
                            (Hiển thị phổ tham chiếu chuẩn — đề thi này đang chờ AI bóc tách chi tiết)
                          </p>
                        )}

                        <div className="space-y-2 text-xs">
                          <div>
                            <div className="flex justify-between font-medium mb-1">
                              <span>Nhận biết (Nhớ)</span>
                              <span className="text-slate-500">{dist.remember}% (Chuẩn 40%)</span>
                            </div>
                            <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                              <div className="h-full bg-emerald-500 rounded-full transition-all" style={{ width: `${Math.min(100, dist.remember)}%` }} />
                            </div>
                          </div>

                          <div>
                            <div className="flex justify-between font-medium mb-1">
                              <span>Thông hiểu (Hiểu)</span>
                              <span className="text-slate-500">{dist.understand}% (Chuẩn 30%)</span>
                            </div>
                            <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                              <div className="h-full bg-sky-500 rounded-full transition-all" style={{ width: `${Math.min(100, dist.understand)}%` }} />
                            </div>
                          </div>

                          <div>
                            <div className="flex justify-between font-medium mb-1">
                              <span>Vận dụng</span>
                              <span className="text-slate-500">{dist.apply}% (Chuẩn 20%)</span>
                            </div>
                            <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                              <div className="h-full bg-amber-500 rounded-full transition-all" style={{ width: `${Math.min(100, dist.apply)}%` }} />
                            </div>
                          </div>

                          <div>
                            <div className="flex justify-between font-medium mb-1">
                              <span>Vận dụng cao</span>
                              <span className="text-slate-500">{dist.analyze}% (Chuẩn 10%)</span>
                            </div>
                            <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                              <div className="h-full bg-rose-500 rounded-full transition-all" style={{ width: `${Math.min(100, dist.analyze)}%` }} />
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Phân tích nội dung đề (5 trục — KG phẳng) */}
                  {contentAnalysis ? (
                    <div className="space-y-3 p-4 rounded-2xl border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                        <Layers className="w-4 h-4 text-indigo-500" />
                        Phân tích nội dung đề (KG phẳng)
                      </h4>

                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                          <span className="text-[11px] text-slate-400 block font-medium">Độ phủ chương trình</span>
                          <span className="font-bold text-slate-800 dark:text-slate-200">
                            {contentAnalysis.coverage.matched}/{contentAnalysis.coverage.catalog_total}
                            {contentAnalysis.coverage.ratio !== null &&
                              ` (${Math.round(contentAnalysis.coverage.ratio * 100)}%)`}
                          </span>
                        </div>
                        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                          <span className="text-[11px] text-slate-400 block font-medium">Chương tập trung nhất</span>
                          <span className="font-bold text-slate-800 dark:text-slate-200">
                            {contentAnalysis.concentration.top_unit_name ?? "—"}
                            {contentAnalysis.concentration.top_share !== null &&
                              ` (${Math.round(contentAnalysis.concentration.top_share * 100)}%)`}
                          </span>
                          {contentAnalysis.concentration.is_concentrated && (
                            <span className="ml-1.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
                              Dồn chương
                            </span>
                          )}
                        </div>
                      </div>

                      {(contentAnalysis.off_curriculum_weight ?? 0) > 0 && (
                        <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-50/70 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 text-xs text-amber-700 dark:text-amber-300">
                          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                          <span>
                            <span className="font-semibold">
                              {(contentAnalysis.off_curriculum_weight * 100).toFixed(0)}% điểm có phần ngoài chương trình
                            </span>{" "}
                            — cờ mềm, chờ giáo viên duyệt (shortlist node).
                          </span>
                        </div>
                      )}

                      {contentAnalysis.items.length > 0 && (
                        <div className="space-y-2 text-xs">
                          {contentAnalysis.items.map((it, i) => (
                            <div
                              key={i}
                              className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800"
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-semibold text-slate-800 dark:text-slate-200 truncate">
                                  {it.topic}
                                </span>
                                <span className="shrink-0 px-2 py-0.5 rounded-full bg-brand-50 dark:bg-brand-500/10 text-brand-700 dark:text-brand-300 text-[10px] font-bold">
                                  Bloom {it.bloom_level}
                                </span>
                              </div>
                              <p className="text-slate-500 dark:text-slate-400 mt-1">
                                {it.node_ref
                                  ? `${it.node_ref.chapter ?? ""}${
                                      it.node_ref.lesson ? ` › ${it.node_ref.lesson}` : ""
                                    } (${Math.round(it.weight * 100)}%)`
                                  : "Chưa khớp node — ngoài chương trình"}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    !detailLoading && (
                      <p className="text-[11px] text-slate-400 italic px-1">
                        Đề chưa có kết quả phân tích nội dung (chờ AI bóc tách).
                      </p>
                    )
                  )}
                </>
              )}
            </div>

            {/* Drawer Footer */}
            <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 flex justify-end">
              <button
                onClick={() => setSelectedExam(null)}
                className="px-4 py-2 bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-semibold rounded-xl text-xs transition-colors"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
