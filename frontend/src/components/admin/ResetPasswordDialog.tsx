"use client";

import { useState } from "react";
import { Dices, Loader2, X } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";

const inputCls =
  "w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 " +
  "text-slate-900 dark:text-slate-100 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none";

function randomPassword(): string {
  const chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789";
  return Array.from(crypto.getRandomValues(new Uint32Array(10)), (n) => chars[n % chars.length]).join("");
}

export default function ResetPasswordDialog({ user, onClose }: { user: User; onClose: () => void }) {
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/users/${user.id}/reset-password`, { new_password: password });
      setDone(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Đặt lại mật khẩu thất bại");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white dark:bg-slate-900 rounded-xl shadow-2xl w-full max-w-sm p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="font-bold text-slate-900 dark:text-white">Reset mật khẩu — {user.full_name}</h4>
          <button onClick={onClose} className="p-1 rounded text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>
        {done ? (
          <div className="space-y-3">
            <p className="text-sm text-emerald-600 dark:text-emerald-400">Đã đặt lại mật khẩu. Gửi mật khẩu mới cho giáo viên:</p>
            <code className="block p-3 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white font-mono text-center select-all">
              {password}
            </code>
            <button onClick={onClose} className="w-full px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold">
              Đóng
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {error && <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>}
            <div className="flex gap-2">
              <input className={inputCls} value={password} placeholder="Mật khẩu mới (≥6 ký tự)"
                onChange={(e) => setPassword(e.target.value)} />
              <button title="Tạo ngẫu nhiên" onClick={() => setPassword(randomPassword())}
                className="px-3 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
                <Dices className="w-4 h-4" />
              </button>
            </div>
            <button onClick={submit} disabled={busy || password.length < 6}
              className="w-full px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-semibold flex items-center justify-center gap-2">
              {busy && <Loader2 className="w-4 h-4 animate-spin" />} Đặt lại mật khẩu
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
