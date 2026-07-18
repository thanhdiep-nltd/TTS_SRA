"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, TrendingDown } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { CalibrationRow } from "@/lib/types";
import { LoadingOverlay, LoadingState } from "../Loading";

interface Props {
  subjectId: string;
  gradeNumber?: string;
  canReview: boolean;
}

const FLAG_LABELS: Record<string, string> = {
  NEGATIVE_DISCRIMINATION: "Phân biệt ÂM (HS giỏi sai nhiều hơn)",
  LOW_DISCRIMINATION: "Phân biệt thấp",
  DIFFICULTY_DRIFT: "Độ khó lệch xa dự đoán Bloom",
};

// Vòng hiệu chỉnh kho câu: thống kê thực tế sau mỗi lần câu được dùng trong đề — câu "bệnh"
// được tự gắn cờ + khuyến nghị RETIRE/REVIEW. (Demo: thống kê mock, xem scripts/seed_item_stats_toan.py)
export default function CalibrationPanel({ subjectId, gradeNumber, canReview }: Props) {
  const [rows, setRows] = useState<CalibrationRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  // Trả về promise (không chỉ fire-and-forget) để handleRetire có thể `await` xong hẳn lượt tải
  // lại rồi mới quyết định hiện lỗi gì — tránh setError(null) ở đầu hàm này đè mất lỗi vừa set.
  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ subject_id: subjectId });
    if (gradeNumber) params.set("grade_number", gradeNumber);
    return api
      .get<CalibrationRow[]>(`/question-bank/calibration?${params.toString()}`)
      .then(setRows)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Không tải được dữ liệu hiệu chỉnh"))
      .finally(() => setLoading(false));
  }, [subjectId, gradeNumber]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRetire = async (id: string) => {
    setBusyId(id);
    try {
      await api.post(`/question-bank/items/${id}/retire`, {});
      load();
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Không ngừng dùng được câu hỏi";
      // Luôn tải lại để bảng phản ánh đúng trạng thái thật (vd: câu đã bị người khác ngừng dùng ở
      // nơi khác nên nút "Ngừng dùng" phải tự ẩn) — chờ tải xong RỒI mới hiện lỗi, vì load() tự
      // setError(null) lúc bắt đầu, nếu hiện lỗi trước sẽ bị xóa mất trước khi người dùng kịp thấy.
      await load();
      setError(message);
    } finally {
      setBusyId(null);
    }
  };

  if (loading && rows.length === 0) return <LoadingState message="Đang tải dữ liệu hiệu chỉnh…" />;

  return (
    <div className="relative space-y-3">
      {loading && rows.length > 0 && <LoadingOverlay message="Đang tải lại dữ liệu hiệu chỉnh…" />}
      {error && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
          {error}
        </div>
      )}
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Thống kê thực nghiệm sau mỗi lần câu được dùng trong đề: <b>p-value</b> = tỉ lệ làm đúng,{" "}
        <b>D</b> = độ phân biệt (âm = học sinh giỏi sai nhiều hơn học sinh yếu → nghi đáp án sai).
      </p>
      {rows.length === 0 ? (
        <div className="text-center py-16 text-slate-400 text-sm">Chưa có câu nào được dùng trong đề.</div>
      ) : (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium">Câu hỏi</th>
                <th className="text-left px-4 py-2.5 font-medium">Bloom</th>
                <th className="text-left px-4 py-2.5 font-medium">Dùng</th>
                <th className="text-left px-4 py-2.5 font-medium">p-value</th>
                <th className="text-left px-4 py-2.5 font-medium">D</th>
                <th className="text-left px-4 py-2.5 font-medium">Chẩn đoán</th>
                <th className="text-left px-4 py-2.5 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {rows.map((r) => (
                <tr key={r.item_id} className={r.recommendation === "RETIRE" ? "bg-rose-50/50 dark:bg-rose-500/5" : ""}>
                  <td className="px-4 py-2.5 max-w-[320px]">
                    <p className="truncate text-slate-800 dark:text-slate-100">{r.stem}</p>
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400">{r.bloom_level}</td>
                  <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400">{r.times_used}×</td>
                  <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400">{r.p_value ?? "—"}</td>
                  <td className={`px-4 py-2.5 font-medium ${
                    r.discrimination != null && r.discrimination < 0
                      ? "text-rose-600 dark:text-rose-400"
                      : "text-slate-500 dark:text-slate-400"
                  }`}>
                    {r.discrimination ?? "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    {r.flags.length === 0 ? (
                      <span className="text-xs text-emerald-600 dark:text-emerald-400">✓ Khỏe mạnh</span>
                    ) : (
                      <div className="space-y-0.5">
                        {r.flags.map((f) => (
                          <p key={f} className="text-xs text-accent-600 dark:text-accent-400">⚠ {FLAG_LABELS[f] ?? f}</p>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    {canReview && r.recommendation === "RETIRE" && r.status === "APPROVED" && (
                      <button
                        onClick={() => handleRetire(r.item_id)}
                        disabled={busyId === r.item_id}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50"
                      >
                        {busyId === r.item_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <TrendingDown className="w-3.5 h-3.5" />}
                        Ngừng dùng
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
