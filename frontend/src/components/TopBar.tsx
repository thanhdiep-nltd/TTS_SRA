"use client";

import { LogOut, Moon, Sun } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { ROLE_LABELS } from "@/lib/types";

export default function TopBar() {
  const { theme, toggle } = useTheme();
  const { user, logout } = useAuth();

  return (
    <header className="h-16 shrink-0 border-b bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 flex items-center justify-between px-6">
      <div className="flex items-center gap-2">
        <span className="text-lg font-bold text-slate-800 dark:text-white">
          Hệ thống Phân tích Kết quả Học tập
        </span>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={toggle}
          aria-label="Đổi giao diện sáng/tối"
          className="p-2 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        >
          {theme === "dark" ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>

        <div className="hidden sm:flex flex-col items-end leading-tight">
          <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">
            {user?.full_name}
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {user ? ROLE_LABELS[user.role] : ""}
          </span>
        </div>

        <button
          onClick={logout}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-colors"
        >
          <LogOut className="w-4 h-4" /> Đăng xuất
        </button>
      </div>
    </header>
  );
}
