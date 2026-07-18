"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, KeyRound, Loader2, Lock, LockOpen, Plus, Search } from "lucide-react";

import ResetPasswordDialog from "@/components/admin/ResetPasswordDialog";
import Tabs from "@/components/admin/Tabs";
import UserDrawer from "@/components/admin/UserDrawer";
import SearchableSelect from "@/components/SearchableSelect";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  ALL_ROLES, ROLE_LABELS,
  type CoverageFilter, type User, type UserListResponse, type UserRole,
} from "@/lib/types";
import ClassCoverageTab from "./ClassCoverageTab";

const inputCls =
  "w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 " +
  "text-slate-900 dark:text-slate-100 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none";
const PAGE_SIZE = 20;

export default function UsersAdminPage() {
  const { user: me } = useAuth();
  const readOnly = me?.role !== "ADMIN";
  const [filters, setFilters] = useState<CoverageFilter[]>([]);
  useEffect(() => {
    api.get<CoverageFilter[]>("/users/assignments/coverage-filters").then(setFilters).catch(() => {});
  }, []);
  const schoolOptions = useMemo(
    () => filters.map((f) => ({ value: f.school_id, label: f.school_name })), [filters]);

  return (
    <div className="p-8 max-w-6xl mx-auto w-full space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Tài khoản & Phân công</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          {readOnly ? "Xem danh sách tài khoản và phân công giảng dạy." : "Tạo tài khoản, gán vai trò và phân công giảng dạy."}
        </p>
      </div>
      <Tabs
        tabs={[
          { label: "Tài khoản", content: <UsersTable readOnly={readOnly} schoolOptions={schoolOptions} defaultSchoolId={me?.school_id ?? ""} /> },
          { label: "Theo lớp", content: <ClassCoverageTab filters={filters} readOnly={readOnly} /> },
        ]}
      />
    </div>
  );
}

function UsersTable({ readOnly, schoolOptions, defaultSchoolId }: {
  readOnly: boolean; schoolOptions: { value: string; label: string }[]; defaultSchoolId: string;
}) {
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [role, setRole] = useState("");
  const [active, setActive] = useState("");
  const [schoolId, setSchoolId] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<UserListResponse>({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drawerTarget, setDrawerTarget] = useState<User | "new" | null>(null);
  const [resetTarget, setResetTarget] = useState<User | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { setDebouncedQ(q); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [q]);

  const load = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), limit: String(PAGE_SIZE) });
    if (debouncedQ) params.set("q", debouncedQ);
    if (role) params.set("role", role);
    if (active) params.set("is_active", active);
    if (schoolId) params.set("school_id", schoolId);
    try {
      setData(await api.get<UserListResponse>(`/users?${params}`));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không tải được danh sách");
    } finally {
      setLoading(false);
    }
  }, [page, debouncedQ, role, active, schoolId]);

  useEffect(() => { load(); }, [load]);

  const toggleActive = async (u: User) => {
    try {
      await api.patch(`/users/${u.id}`, { is_active: !u.is_active });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Cập nhật thất bại");
    }
  };

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm theo tên hoặc email…"
            className={`${inputCls} pl-9`} />
        </div>
        <SearchableSelect label="Vai trò" value={role} onChange={(v) => { setRole(v); setPage(1); }}
          options={ALL_ROLES} placeholder="Tất cả vai trò" className="min-w-[180px]" />
        <SearchableSelect label="Trạng thái" value={active} onChange={(v) => { setActive(v); setPage(1); }}
          options={[{ value: "true", label: "Đang hoạt động" }, { value: "false", label: "Đã khóa" }]}
          placeholder="Tất cả" className="min-w-[150px]" />
        {schoolOptions.length > 1 && (
          <SearchableSelect label="Trường" value={schoolId} onChange={(v) => { setSchoolId(v); setPage(1); }}
            options={schoolOptions} placeholder="Tất cả trường" className="min-w-[180px]" />
        )}
        {!readOnly && (
          <button onClick={() => setDrawerTarget("new")}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold">
            <Plus className="w-4 h-4" /> Thêm tài khoản
          </button>
        )}
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
          {error}
        </div>
      )}

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-8 flex justify-center"><Loader2 className="w-6 h-6 text-brand-500 animate-spin" /></div>
        ) : data.items.length === 0 ? (
          <p className="p-6 text-center text-sm text-slate-500 dark:text-slate-400">Không có tài khoản phù hợp.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 dark:text-slate-400 text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left px-4 py-3">Họ và tên</th>
                <th className="text-left px-4 py-3">Email</th>
                <th className="text-left px-4 py-3">Vai trò</th>
                <th className="text-left px-4 py-3">Trạng thái</th>
                {!readOnly && <th className="text-right px-4 py-3">Thao tác</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {data.items.map((u) => (
                <tr key={u.id} onClick={() => setDrawerTarget(u)}
                  className="text-slate-700 dark:text-slate-200 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40">
                  <td className="px-4 py-3 font-medium">{u.full_name}</td>
                  <td className="px-4 py-3">{u.email}</td>
                  <td className="px-4 py-3">{ROLE_LABELS[u.role as UserRole] ?? u.role}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${
                      u.is_active
                        ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                        : "bg-slate-100 dark:bg-slate-800 text-slate-500"
                    }`}>
                      {u.is_active ? "Hoạt động" : "Đã khóa"}
                    </span>
                  </td>
                  {!readOnly && (
                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="inline-flex items-center gap-1.5">
                        <button title="Reset mật khẩu" onClick={() => setResetTarget(u)}
                          className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
                          <KeyRound className="w-4 h-4" />
                        </button>
                        <ToggleLock user={u} onToggle={() => toggleActive(u)} />
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="flex items-center justify-between text-sm text-slate-500 dark:text-slate-400">
        <span>{data.total} tài khoản</span>
        <div className="flex items-center gap-2">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
            className="p-1.5 rounded-lg disabled:opacity-40 hover:bg-slate-100 dark:hover:bg-slate-800">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span>Trang {page}/{totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}
            className="p-1.5 rounded-lg disabled:opacity-40 hover:bg-slate-100 dark:hover:bg-slate-800">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      <UserDrawer target={drawerTarget} readOnly={readOnly} schoolOptions={schoolOptions}
        defaultSchoolId={defaultSchoolId} onClose={() => setDrawerTarget(null)} onSaved={load} />
      {resetTarget && <ResetPasswordDialog user={resetTarget} onClose={() => setResetTarget(null)} />}
    </div>
  );
}

function ToggleLock({ user, onToggle }: { user: User; onToggle: () => void }) {
  const [confirming, setConfirming] = useState(false);
  if (confirming) {
    return (
      <span className="inline-flex items-center gap-1 text-xs">
        <button onClick={() => { onToggle(); setConfirming(false); }}
          className="px-2 py-1 rounded bg-brand-600 text-white font-semibold">
          {user.is_active ? "Khóa" : "Mở"}
        </button>
        <button onClick={() => setConfirming(false)}
          className="px-2 py-1 rounded text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">Hủy</button>
      </span>
    );
  }
  return (
    <button title={user.is_active ? "Khóa tài khoản" : "Mở khóa"} onClick={() => setConfirming(true)}
      className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
      {user.is_active ? <Lock className="w-4 h-4" /> : <LockOpen className="w-4 h-4 text-amber-500" />}
    </button>
  );
}
