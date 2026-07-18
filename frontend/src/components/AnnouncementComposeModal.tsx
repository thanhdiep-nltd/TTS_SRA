"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  SCHOOL_WIDE_ANNOUNCEMENT_ROLES,
  type AnnouncementScope,
  type RecipientOption,
  type Subject,
} from "@/lib/types";
import SearchableSelect from "./SearchableSelect";

const SCOPE_LABELS: Record<AnnouncementScope, string> = {
  SCHOOL: "Toàn trường",
  SUBJECT: "Theo bộ môn",
  INDIVIDUAL: "Cá nhân cụ thể",
};

// Soạn thông báo chủ động: BGH chọn Toàn trường/Bộ môn bất kỳ/Cá nhân bất kỳ;
// Trưởng bộ môn chỉ gửi Bộ môn của mình hoặc Cá nhân trong bộ môn mình (ép buộc ở backend).
export default function AnnouncementComposeModal({ onClose }: { onClose: () => void }) {
  const { user } = useAuth();
  const canSchoolWide = !!user && SCHOOL_WIDE_ANNOUNCEMENT_ROLES.includes(user.role);
  const isSubjectHead = user?.role === "SUBJECT_HEAD";

  const scopeOptions: AnnouncementScope[] = canSchoolWide
    ? ["SCHOOL", "SUBJECT", "INDIVIDUAL"]
    : ["SUBJECT", "INDIVIDUAL"];

  const [scope, setScope] = useState<AnnouncementScope>(canSchoolWide ? "SCHOOL" : "SUBJECT");
  const [titleText, setTitleText] = useState("");
  const [message, setMessage] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [recipientUserId, setRecipientUserId] = useState("");
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [recipients, setRecipients] = useState<RecipientOption[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // BGH cần danh sách bộ môn để chọn (Trưởng BM không cần — backend ép về môn mình).
  useEffect(() => {
    if (!canSchoolWide) return;
    api.get<Subject[]>("/subjects?limit=200").then(setSubjects).catch(() => {});
  }, [canSchoolWide]);

  // Trưởng bộ môn: tự điền môn phụ trách của mình khi chọn phạm vi "Bộ môn" (server vẫn ép buộc lại).
  useEffect(() => {
    if (isSubjectHead && scope === "SUBJECT" && user?.subject_id) {
      setSubjectId(user.subject_id);
    }
  }, [isSubjectHead, scope, user?.subject_id]);

  // Danh sách người nhận khi chọn phạm vi cá nhân (BGH có thể lọc theo bộ môn để dễ tìm).
  useEffect(() => {
    if (scope !== "INDIVIDUAL") return;
    const query = canSchoolWide && subjectId ? `?subject_id=${subjectId}` : "";
    api.get<RecipientOption[]>(`/notifications/recipients${query}`).then(setRecipients).catch(() => setRecipients([]));
  }, [scope, subjectId, canSchoolWide]);

  const subjectHeadMissingSubject = isSubjectHead && scope === "SUBJECT" && !subjectId;
  const canSubmit =
    titleText.trim().length > 0 &&
    message.trim().length > 0 &&
    (scope !== "SUBJECT" || !!subjectId) &&
    (scope !== "INDIVIDUAL" || !!recipientUserId);

  const handleSubmit = async () => {
    setError(null);
    setBusy(true);
    try {
      const result = await api.post<{ recipients_count: number }>("/notifications/announcements", {
        scope,
        title: titleText.trim(),
        message: message.trim(),
        subject_id: scope === "SUBJECT" ? subjectId : undefined,
        recipient_user_id: scope === "INDIVIDUAL" ? recipientUserId : undefined,
      });
      setSuccess(`Đã gửi đến ${result.recipients_count} người.`);
      setTimeout(onClose, 1200);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Gửi thông báo thất bại");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <h3 className="font-bold text-slate-900 dark:text-white">Soạn thông báo</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
              {error}
            </div>
          )}
          {success && (
            <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 text-emerald-700 dark:text-emerald-300 text-sm">
              {success}
            </div>
          )}

          <div>
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Phạm vi</label>
            <div className="flex gap-2 mt-1.5 flex-wrap">
              {scopeOptions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setScope(s)}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition ${
                    scope === s
                      ? "bg-brand-600 text-white border-brand-600"
                      : "border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-brand-400"
                  }`}
                >
                  {s === "SUBJECT" && isSubjectHead ? "Bộ môn của tôi" : SCOPE_LABELS[s]}
                </button>
              ))}
            </div>
            {subjectHeadMissingSubject && (
              <p className="text-xs text-rose-600 dark:text-rose-400 mt-1.5">
                Bạn chưa được gán môn phụ trách trong hồ sơ — không thể gửi theo phạm vi này.
              </p>
            )}
          </div>

          {scope === "SUBJECT" && canSchoolWide && (
            <SearchableSelect
              label="Bộ môn"
              value={subjectId}
              onChange={setSubjectId}
              options={subjects.map((s) => ({ value: s.id, label: s.name }))}
              placeholder="— Chọn bộ môn —"
            />
          )}

          {scope === "INDIVIDUAL" && (
            <>
              {canSchoolWide && (
                <SearchableSelect
                  label="Thu hẹp theo bộ môn (tùy chọn)"
                  value={subjectId}
                  onChange={setSubjectId}
                  options={subjects.map((s) => ({ value: s.id, label: s.name }))}
                  placeholder="— Toàn trường —"
                />
              )}
              <SearchableSelect
                label="Người nhận"
                value={recipientUserId}
                onChange={setRecipientUserId}
                options={recipients.map((r) => ({ value: r.id, label: r.full_name }))}
                placeholder={recipients.length === 0 ? "— Không có ai trong phạm vi —" : "— Chọn người nhận —"}
              />
            </>
          )}

          <div>
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Tiêu đề</label>
            <input
              value={titleText}
              onChange={(e) => setTitleText(e.target.value)}
              className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 text-sm outline-none focus:border-brand"
              placeholder="Vd: Thông báo họp chuyên môn"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Nội dung</label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 text-sm outline-none focus:border-brand resize-none"
              placeholder="Nội dung thông báo..."
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-slate-200 dark:border-slate-800">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            Hủy
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || busy}
            className="px-4 py-2 rounded-lg text-sm font-semibold bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {busy ? "Đang gửi…" : "Gửi thông báo"}
          </button>
        </div>
      </div>
    </div>
  );
}
