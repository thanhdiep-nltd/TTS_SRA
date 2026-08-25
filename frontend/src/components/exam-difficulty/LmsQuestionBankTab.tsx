"use client";

// Tab "Ngân hàng câu hỏi LMS" (trang Phân tích độ khó đề thi /exam-difficulty).
// Danh sách ngắn (có phân trang) kiểu "Danh Sách Dự Báo Chi Tiết" trong Dashboard:
// hiển thị nội dung câu hỏi, map chương (kể cả multi-chapter), Bloom và độ đúng
// thống kê từ lms_question_response.

import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, ChevronLeft, ChevronRight, Database, Layers, Loader2, Search, Sparkles, X } from "lucide-react";
import SearchableSelect from "@/components/SearchableSelect";
import { api } from "@/lib/api";
import type { LmsQuestionBankItem } from "@/lib/types";

const PAGE_SIZE = 12;

const BLOOM_LABELS: Record<number, string> = {
  1: "Nhớ",
  2: "Hiểu",
  3: "Vận dụng",
  4: "Phân tích",
  5: "Đánh giá",
  6: "Sáng tạo",
};

const BLOOM_COLORS: Record<number, string> = {
  1: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  2: "bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  3: "bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300",
  4: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  5: "bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300",
  6: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300",
};

function accuracyColor(acc: number | null): string {
  if (acc === null) return "text-slate-400";
  if (acc < 0.4) return "text-rose-600 dark:text-rose-400";
  if (acc < 0.6) return "text-amber-600 dark:text-amber-400";
  return "text-emerald-600 dark:text-emerald-400";
}

export default function LmsQuestionBankTab() {
  const [subjects, setSubjects] = useState<{ id: string; name: string }[]>([]);
  const [subjectId, setSubjectId] = useState<string>("106"); // mặc định Toán 6 (mock)
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const [loading, setLoading] = useState(false);
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [recalcMsg, setRecalcMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<LmsQuestionBankItem[]>([]);

  // Danh sách môn từ s360.dim_subject (khớp API knowledge-gaps)
  useEffect(() => {
    api
      .get<{ id: number; name: string }[]>("/knowledge-gaps/subject-options")
      .then((list) => setSubjects((list ?? []).map((s) => ({ id: String(s.id), name: s.name }))))
      .catch(() => setError("Không tải được danh sách môn học."));
  }, []);

  const fetchBank = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (subjectId) params.set("subject_id", subjectId);
      const data = await api.get<LmsQuestionBankItem[]>(`/knowledge-gaps/lms-question-bank?${params.toString()}`);
      setItems(data || []);
      setPage(1);
    } catch (e: any) {
      setError(e?.message ?? "Không tải được ngân hàng câu hỏi LMS.");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [subjectId]);

  const handleRecalcMastery = async () => {
    if (!subjectId) return;
    setIsRecalculating(true);
    setError(null);
    setRecalcMsg(null);
    try {
      const res = await api.post<{ success: boolean; records_calculated: number; message: string }>(
        `/knowledge-gaps/recalc-mastery?subject_id=${subjectId}&semester_index=1`
      );
      setRecalcMsg(res.message || `Đã tính toán lại năng lực thành công (${res.records_calculated} bản ghi).`);
      setTimeout(() => setRecalcMsg(null), 6000);
    } catch (e: any) {
      setError(e?.message ?? "Lỗi khi tính lại năng lực học sinh.");
    } finally {
      setIsRecalculating(false);
    }
  };

  useEffect(() => {
    fetchBank();
  }, [fetchBank]);

  // Lọc nhanh phía client theo mã câu/bài/tên chương/nội dung
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (it) =>
        String(it.question_id).includes(q) ||
        String(it.assignment_id).includes(q) ||
        (it.unit_name ?? "").toLowerCase().includes(q) ||
        (it.chapter ?? "").toLowerCase().includes(q) ||
        (it.question_text ?? "").toLowerCase().includes(q)
    );
  }, [items, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageItems = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const stats = useMemo(() => {
    const active = items.filter((i) => i.is_active === 1).length;
    const unmapped = items.filter((i) => i.unit_id === null).length;
    const multi = items.filter((i) => i.units.length > 1).length;
    const withResp = items.filter((i) => i.n_responses !== null && i.n_responses > 0);
    const avgAcc =
      withResp.length > 0
        ? withResp.reduce((s, i) => s + (i.accuracy ?? 0), 0) / withResp.length
        : null;
    return { total: items.length, active, unmapped, multi, withResp: withResp.length, avgAcc };
  }, [items]);

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-3.5 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-500 block">Tổng câu hỏi</span>
          <span className="text-xl font-bold text-slate-900 dark:text-slate-100">{stats.total}</span>
        </div>
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-3.5 shadow-sm">
          <span className="text-[11px] font-semibold text-emerald-600 block">Đang hoạt động</span>
          <span className="text-xl font-bold text-emerald-600">{stats.active}</span>
        </div>
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-3.5 shadow-sm">
          <span className="text-[11px] font-semibold text-amber-600 block">Chưa map bài</span>
          <span className="text-xl font-bold text-amber-600">{stats.unmapped}</span>
        </div>
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-3.5 shadow-sm">
          <span className="text-[11px] font-semibold text-indigo-600 block">Câu multi-bài</span>
          <span className="text-xl font-bold text-indigo-600">{stats.multi}</span>
        </div>
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-3.5 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-500 block">Câu đã có HS làm</span>
          <span className="text-xl font-bold text-slate-900 dark:text-slate-100">{stats.withResp}</span>
        </div>
        <div className="bg-white dark:bg-slate-900 border rounded-2xl p-3.5 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-500 block">Độ đúng TB</span>
          <span className={`text-xl font-bold ${accuracyColor(stats.avgAcc)}`}>
            {stats.avgAcc !== null ? `${(stats.avgAcc * 100).toFixed(0)}%` : "—"}
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
        <div className="min-w-[220px] flex-1">
          <label className="text-xs font-semibold text-slate-500 mb-1 block">Tìm nhanh</label>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Mã câu / nội dung / tên bài..."
              className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-800 dark:text-slate-200 placeholder:text-slate-400 outline-none focus:ring-2 focus:ring-brand-500/40"
            />
          </div>
        </div>
        <button
          onClick={fetchBank}
          disabled={loading}
          className="px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50"
        >
          {loading ? "Đang tải..." : "Làm mới"}
        </button>

        <button
          onClick={handleRecalcMastery}
          disabled={isRecalculating || !subjectId}
          className="px-4 py-2 rounded-xl border border-indigo-200 dark:border-indigo-800 bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/40 dark:hover:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 text-sm font-semibold disabled:opacity-50 flex items-center gap-1.5"
          title="Tính toán lại toàn bộ student_unit_mastery từ kết quả LMS mới nhất"
        >
          <Sparkles className={`w-4 h-4 text-indigo-600 dark:text-indigo-400 ${isRecalculating ? "animate-spin" : ""}`} />
          {isRecalculating ? "Đang tính..." : "Tính lại năng lực"}
        </button>
      </div>

      {recalcMsg && (
        <div className="rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300 flex items-center justify-between gap-3 animate-in fade-in duration-200">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
            <span>{recalcMsg}</span>
          </div>
          <button onClick={() => setRecalcMsg(null)} className="text-emerald-500 hover:text-emerald-700 p-1">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {error && (
        <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 px-4 py-3 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </div>
      )}

      {/* Danh sách ngắn — kiểu "Danh Sách Dự Báo Chi Tiết" */}
      <section className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden space-y-4 p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-indigo-500" />
            <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              Danh Sách Câu Hỏi LMS ({filtered.length.toLocaleString()} Kết Quả)
            </h4>
          </div>
          <span className="text-xs text-slate-400">
            Hiển thị trang {safePage} / {totalPages} ({PAGE_SIZE} bản ghi/trang)
          </span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12 text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin text-indigo-500 mr-2" /> Đang tải ngân hàng câu hỏi...
          </div>
        ) : pageItems.length === 0 ? (
          <div className="py-12 text-center text-sm text-slate-400">
            Chưa có câu hỏi LMS nào cho bộ lọc này.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-200 dark:border-slate-700">
                <tr>
                  <th className="py-3 px-4">Câu Hỏi</th>
                  <th className="py-3 px-4">Bài / Chương</th>
                  <th className="py-3 px-4 text-center">Bloom</th>
                  <th className="py-3 px-4 text-center">Trạng Thái</th>
                  <th className="py-3 px-4 text-right" title="Số học sinh đã làm (best-attempt) và số học sinh trả lời đúng">HS Làm / Đúng</th>
                  <th className="py-3 px-4 text-right">Độ Đúng</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {pageItems.map((it) => {
                  const bloomCls = BLOOM_COLORS[it.bloom_level ?? 3] ?? BLOOM_COLORS[3];
                  const acc = it.accuracy;
                  return (
                    <tr key={it.question_id} className="group hover:bg-indigo-50/60 dark:hover:bg-slate-800/80 transition-colors">
                      {/* Câu hỏi */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span className="inline-block px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-mono font-medium text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-700/80">
                            #{it.question_id}
                          </span>
                          <span className="font-mono text-[10px] text-slate-400">Bài #{it.assignment_id}</span>
                        </div>
                        <div className="mt-1 text-slate-800 dark:text-slate-200 leading-snug max-w-[420px]">
                          {it.question_text || "—"}
                        </div>
                        {it.question_type && it.question_type !== "MCQ" && (
                          <span className="inline-block mt-0.5 px-1.5 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-500 font-mono">
                            {it.question_type}
                          </span>
                        )}
                      </td>

                      {/* Bài / Chương — unit_id trỏ tới BÀI (lesson), parent_id = chương */}
                      <td className="py-3 px-4 min-w-[200px]">
                        <div className="flex items-center gap-1 flex-wrap">
                          <span className="font-semibold text-slate-800 dark:text-slate-200">
                            {it.unit_name ?? "Chưa map bài"}
                          </span>
                        </div>
                        {it.chapter && (
                          <div className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5 truncate max-w-[240px]">
                            Chương: {it.chapter}
                          </div>
                        )}
                        {/* Chip multi-bài: chỉ khi câu thật sự map >1 bài (weight < 1) */}
                        {it.units.length > 1 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {it.units
                              .filter((u) => u.weight < 1)
                              .map((u) => (
                                <span
                                  key={u.unit_id}
                                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-100 dark:border-indigo-800 text-[10px] font-semibold text-indigo-700 dark:text-indigo-300"
                                  title={`Câu này đóng góp ${Math.round(u.weight * 100)}% vào bài ${u.unit_name ?? u.unit_id} (${u.chapter ?? ""})`}
                                >
                                  {u.unit_name ?? u.unit_id} · {Math.round(u.weight * 100)}%
                                </span>
                              ))}
                          </div>
                        )}
                      </td>

                      {/* Bloom */}
                      <td className="py-3 px-4 text-center whitespace-nowrap">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${bloomCls}`}>
                          {it.bloom_level ?? "—"}
                        </span>
                        {it.bloom_level !== null && (
                          <span className="block text-[10px] text-slate-400 mt-0.5">
                            {BLOOM_LABELS[it.bloom_level] ?? ""}
                          </span>
                        )}
                      </td>

                      {/* Trạng thái */}
                      <td className="py-3 px-4 text-center">
                        {it.is_active === 1 ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                            Hoạt động
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                            Tắt
                          </span>
                        )}
                      </td>

                      {/* HS làm */}
                      <td className="py-3 px-4 text-right">
                        {it.n_responses !== null ? (
                          <div title={`${it.n_responses} học sinh đã làm câu này (best-attempt); trong đó ${it.n_correct ?? 0} học sinh trả lời đúng`}>
                            <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                              {it.n_responses}
                            </span>
                            <span className="text-slate-400 text-[10px]"> HS làm · </span>
                            <span className="font-mono text-emerald-600 dark:text-emerald-400">
                              {it.n_correct ?? 0}
                            </span>
                            <span className="text-slate-400 text-[10px]"> HS đúng</span>
                          </div>
                        ) : (
                          <span className="text-slate-300 dark:text-slate-600">—</span>
                        )}
                      </td>

                      {/* Độ đúng */}
                      <td className="py-3 px-4 text-right">
                        {acc !== null ? (
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-16 h-1.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                              <div
                                className={`h-full rounded-full ${acc < 0.4 ? "bg-rose-500" : acc < 0.6 ? "bg-amber-500" : "bg-emerald-500"}`}
                                style={{ width: `${Math.round(acc * 100)}%` }}
                              />
                            </div>
                            <span className={`font-mono font-semibold ${accuracyColor(acc)}`}>
                              {(acc * 100).toFixed(0)}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-slate-300 dark:text-slate-600">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {!loading && totalPages > 1 && (
          <div className="flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-800">
            <span className="text-[11px] text-slate-400">
              Trang {safePage}/{totalPages} — {filtered.length} câu
            </span>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage <= 1}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage >= totalPages}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </section>

      <p className="text-[11px] text-slate-400 flex items-center gap-1.5 px-1">
        <Layers className="w-3.5 h-3.5 shrink-0" />
        Nguồn: bảng <code className="font-mono">lms_question_bank</code> (nội dung + map bài) kết hợp thống kê từ{" "}
        <code className="font-mono">lms_question_response</code> (số HS trả lời best-attempt + độ đúng).
      </p>
    </div>
  );
}
