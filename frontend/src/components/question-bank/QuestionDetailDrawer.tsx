"use client";

import { useEffect, useState } from "react";
import { Ban, Check, Loader2, Pencil, Save, X } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { ITEM_STATUS_LABELS, ITEM_STATUS_STYLE, QUESTION_TYPE_LABELS, type QuestionItemDetailRow } from "@/lib/types";
import { LoadingState } from "../Loading";

interface Props {
  itemId: string;
  canReview: boolean;
  onClose: () => void;
  onChanged: () => void;
}

const EDITABLE_STATUSES = new Set(["DRAFT", "REVIEW"]);

// Drawer chi tiết câu hỏi: xem đáp án/lời giải/bằng chứng RAG, sửa (nếu còn DRAFT/REVIEW),
// duyệt/từ chối (nếu có quyền). Đáp án CHỈ hiện ở đây — không lộ ra bảng danh sách.
export default function QuestionDetailDrawer({ itemId, canReview, onClose, onChanged }: Props) {
  const [item, setItem] = useState<QuestionItemDetailRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [showReject, setShowReject] = useState(false);

  const [stem, setStem] = useState("");
  const [solution, setSolution] = useState("");

  const load = () => {
    setLoading(true);
    api
      .get<QuestionItemDetailRow>(`/question-bank/items/${itemId}`)
      .then((d) => {
        setItem(d);
        setStem(d.stem);
        setSolution(d.solution ?? "");
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Không tải được câu hỏi"))
      .finally(() => setLoading(false));
  };

  useEffect(load, [itemId]);

  const handleReview = async (approve: boolean) => {
    if (!approve && !rejectReason.trim()) {
      setShowReject(true);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post(`/question-bank/items/${itemId}/review`, {
        approve,
        reason: approve ? null : rejectReason.trim(),
      });
      onChanged();
      load();
      setShowReject(false);
      setRejectReason("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Duyệt câu hỏi thất bại");
    } finally {
      setBusy(false);
    }
  };

  const handleSave = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.patch(`/question-bank/items/${itemId}`, { stem, solution });
      onChanged();
      load();
      setEditing(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Lưu thất bại");
    } finally {
      setBusy(false);
    }
  };

  const canEdit = item ? EDITABLE_STATUSES.has(item.status) : false;

  return (
    <div className="fixed inset-0 z-50 flex items-stretch justify-end bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-lg bg-white dark:bg-slate-900 shadow-2xl flex flex-col h-full"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800 shrink-0">
          <h3 className="font-bold text-slate-900 dark:text-white">Chi tiết câu hỏi</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {loading ? (
            <LoadingState message="Đang tải…" />
          ) : !item ? (
            <p className="text-sm text-slate-400">{error ?? "Không tìm thấy câu hỏi."}</p>
          ) : (
            <>
              {error && (
                <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
                  {error}
                </div>
              )}

              <div className="flex items-center gap-2 flex-wrap">
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ITEM_STATUS_STYLE[item.status]}`}>
                  {ITEM_STATUS_LABELS[item.status]}
                </span>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {QUESTION_TYPE_LABELS[item.question_type]} · Bloom {item.bloom_level} · {item.default_points} điểm
                </span>
              </div>

              {editing ? (
                <textarea
                  value={stem}
                  onChange={(e) => setStem(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
                />
              ) : (
                <p className="text-sm font-medium text-slate-800 dark:text-slate-100 whitespace-pre-wrap">{item.stem}</p>
              )}

              {item.options && (
                <div className="space-y-1.5">
                  {item.options.map((o) => {
                    const isCorrect = item.answer_key?.correct === o.key;
                    return (
                      <div
                        key={o.key}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm ${
                          isCorrect
                            ? "border-emerald-300 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                            : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300"
                        }`}
                      >
                        <span className="font-semibold">{o.key}.</span> {o.text}
                        {o.misconception && (
                          <span className="ml-2 text-[11px] italic text-slate-400">↳ bẫy: {o.misconception}</span>
                        )}
                        {isCorrect && <Check className="w-4 h-4 ml-auto shrink-0" />}
                      </div>
                    );
                  })}
                </div>
              )}
              {!item.options && item.answer_key?.answer != null && (
                <div className="px-3 py-2 rounded-lg border border-emerald-200 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-500/10 text-sm text-emerald-700 dark:text-emerald-300">
                  <span className="font-semibold">Đáp án mẫu:</span> {String(item.answer_key.answer)}
                  {item.answer_key.rubric != null && (
                    <p className="mt-1 text-xs text-emerald-600 dark:text-emerald-400">
                      Thang chấm: {String(item.answer_key.rubric)}
                    </p>
                  )}
                </div>
              )}

              <div>
                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">Lời giải</p>
                {editing ? (
                  <textarea
                    value={solution}
                    onChange={(e) => setSolution(e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
                  />
                ) : (
                  <p className="text-sm text-slate-600 dark:text-slate-300 whitespace-pre-wrap">{item.solution || "—"}</p>
                )}
              </div>

              {item.source === "AI_GENERATED" && (
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-2">
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                    Nguồn gốc: 🤖 AI ({item.provenance?.model ?? "?"})
                    {item.provenance?.self_consistency === "match" && (
                      <span className="ml-2 text-emerald-600 dark:text-emerald-400">✅ Tự giải lại khớp</span>
                    )}
                    {item.provenance?.self_consistency === "mismatch" && (
                      <span className="ml-2 font-bold text-accent-600 dark:text-accent-400">
                        ⚠️ Tự giải lại KHÔNG khớp — cần rà soát kỹ
                      </span>
                    )}
                  </p>
                  {item.provenance?.bloom_check === "mismatch" && (
                    <p className="text-xs font-semibold text-accent-600 dark:text-accent-400">
                      ⚠️ AI phân loại độc lập ra mức Bloom KHÁC mức yêu cầu — kiểm tra lại độ khó nhận thức.
                    </p>
                  )}
                  {item.provenance?.duplicate_of && (
                    <p className="text-xs font-semibold text-accent-600 dark:text-accent-400">
                      ⚠️ Nghi TRÙNG LẶP với câu đã có trong kho (id: {item.provenance.duplicate_of.slice(0, 8)}…).
                    </p>
                  )}
                  {item.provenance?.critic && (
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      <p className="font-semibold">
                        Chấm phản biện (AI):{" "}
                        <span
                          className={
                            item.provenance.critic.score <= 6
                              ? "text-accent-600 dark:text-accent-400"
                              : "text-emerald-600 dark:text-emerald-400"
                          }
                        >
                          {item.provenance.critic.score}/10
                        </span>
                      </p>
                      {item.provenance.critic.issues.map((iss, i) => (
                        <p key={i} className="pl-2">
                          • {iss}
                        </p>
                      ))}
                    </div>
                  )}
                  {!!item.provenance?.rag_hits?.length && (
                    <div className="space-y-1">
                      <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Nguồn SGK đã dùng:</p>
                      {item.provenance.rag_hits.map((h, i) => (
                        <p key={i} className="text-xs text-slate-500 dark:text-slate-400">
                          📖 {[h.chuong, h.heading].filter(Boolean).join(" — ") || h.source_md || "?"}
                          {h.score != null && ` (độ khớp ${(h.score * 100).toFixed(0)}%)`}
                        </p>
                      ))}
                    </div>
                  )}
                  {!!item.provenance?.rag_sources?.length && (
                    <div className="space-y-1">
                      <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Trích dẫn SGK:</p>
                      {item.provenance.rag_sources.map((q, i) => (
                        <p
                          key={i}
                          className="text-xs text-slate-500 dark:text-slate-400 italic border-l-2 border-slate-300 dark:border-slate-600 pl-2"
                        >
                          “{q}”
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="text-xs text-slate-500 dark:text-slate-400 space-y-1 pt-2 border-t border-slate-100 dark:border-slate-800">
                <p>
                  Tạo bởi: <span className="font-medium text-slate-700 dark:text-slate-200">{item.created_by_name}</span> ·{" "}
                  {formatDate(item.created_at)}
                </p>
                {item.reviewed_by_name && (
                  <p>
                    Duyệt bởi:{" "}
                    <span className="font-medium text-slate-700 dark:text-slate-200">{item.reviewed_by_name}</span> ·{" "}
                    {item.reviewed_at ? formatDate(item.reviewed_at) : ""}
                  </p>
                )}
                <p>
                  Đã dùng: {item.times_used} lần
                  {item.exposure_at && (
                    <span className="ml-1 text-accent-600 dark:text-accent-400">
                      (gần nhất: {formatDate(item.exposure_at)} ⚠️)
                    </span>
                  )}
                </p>
              </div>
            </>
          )}
        </div>

        {item && (
          <div className="px-5 py-4 border-t border-slate-200 dark:border-slate-800 shrink-0 space-y-3">
            {showReject && (
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Lý do từ chối (bắt buộc)…"
                rows={2}
                className="w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-rose-300 dark:border-rose-700 text-sm outline-none"
              />
            )}
            <div className="flex items-center justify-end gap-2">
              {canEdit && !editing && (
                <button
                  onClick={() => setEditing(true)}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <Pencil className="w-4 h-4" /> Sửa
                </button>
              )}
              {editing && (
                <>
                  <button
                    onClick={() => setEditing(false)}
                    className="px-3 py-2 rounded-lg text-sm font-medium text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    Hủy
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={busy}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-semibold bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
                  >
                    {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Lưu
                  </button>
                </>
              )}
              {canReview && canEdit && !editing && (
                <>
                  <button
                    onClick={() => handleReview(true)}
                    disabled={busy}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-semibold bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
                  >
                    <Check className="w-4 h-4" /> Duyệt
                  </button>
                  <button
                    onClick={() => (showReject ? handleReview(false) : setShowReject(true))}
                    disabled={busy}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-semibold bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50"
                  >
                    <Ban className="w-4 h-4" /> {showReject ? "Xác nhận từ chối" : "Từ chối"}
                  </button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
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
