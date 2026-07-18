"use client";

import { ShieldAlert } from "lucide-react";

import { useAuth } from "@/lib/auth";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();

  if (user && user.role !== "ADMIN" && user.role !== "PRINCIPAL") {
    return (
      <div className="flex h-full flex-col items-center justify-center text-center p-8">
        <ShieldAlert className="w-12 h-12 text-rose-500 mb-3" />
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Không có quyền truy cập</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Khu vực quản trị chỉ dành cho tài khoản ADMIN hoặc HIỆU TRƯỞNG.</p>
      </div>
    );
  }

  return <>{children}</>;
}
