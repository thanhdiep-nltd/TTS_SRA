"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Loader2, Plus, X } from "lucide-react";

import SearchableSelect from "@/components/SearchableSelect";
import { api, ApiError } from "@/lib/api";
import {
  ALL_ROLES, CONTEXT_FIELDS, ROLE_CONTEXTS, ROLE_LABELS, SCHOOL_LEVELS,
  type AssignmentOptions, type AssignmentRow, type RoleContext, type User, type UserRole,
} from "@/lib/types";

const inputCls =
  "w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 " +
  "text-slate-900 dark:text-slate-100 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none";

interface Props {
  /** null = drawer đóng; "new" = tạo mới; ngược lại là user đang xem. */
  target: User | "new" | null;
  readOnly: boolean;
  schoolOptions: { value: string; label: string }[];
  defaultSchoolId: string;
  onClose: () => void;
  /** Gọi sau khi tạo/sửa thành công để trang reload bảng. */
  onSaved: () => void;
}

export default function UserDrawer({ target, readOnly, schoolOptions, defaultSchoolId, onClose, onSaved }: Props) {
  const [user, setUser] = useState<User | null>(null);
  useEffect(() => {
    setUser(target === "new" ? null : target);
  }, [target]);

  if (target === null) return null;
  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <aside className="absolute right-0 top-0 h-full w-full max-w-xl bg-white dark:bg-slate-900 shadow-2xl overflow-y-auto">
        <div className="sticky top-0 z-10 flex items-center justify-between px-5 py-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
          <h3 className="font-bold text-slate-900 dark:text-white">
            {user ? user.full_name : "Thêm tài khoản"}
          </h3>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-5 space-y-6">
          <ProfileSection user={user} readOnly={readOnly} schoolOptions={schoolOptions}
            defaultSchoolId={defaultSchoolId}
            onSaved={(u) => { setUser(u); onSaved(); }} />
          {user && <AssignmentSection user={user} readOnly={readOnly} />}
        </div>
      </aside>
    </div>
  );
}

// ===== Hồ sơ =====

function ProfileSection({ user, readOnly, schoolOptions, defaultSchoolId, onSaved }: {
  user: User | null; readOnly: boolean; schoolOptions: { value: string; label: string }[];
  defaultSchoolId: string; onSaved: (u: User) => void;
}) {
  const isCreate = user === null;
  const [form, setForm] = useState<Record<string, string>>({});
  const [subjects, setSubjects] = useState<{ value: string; label: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [hasAssignments, setHasAssignments] = useState(false);

  useEffect(() => {
    setForm(user ? {
      email: user.email, full_name: user.full_name, role: user.role,
      subject_id: user.subject_id ?? "", school_level: user.school_level ?? "ALL",
      phone: user.phone ?? "", school_id: user.school_id,
    } : { role: "SUBJECT_TEACHER", school_level: "ALL", school_id: defaultSchoolId });
    setError(null);
    setNotice(null);
  }, [user, defaultSchoolId]);

  // Môn phụ trách: dùng /subjects (trường của admin) — đủ cho MVP một trường chính.
  useEffect(() => {
    api.get<{ id: string; name: string }[]>("/subjects?limit=200")
      .then((s) => setSubjects(s.map((x) => ({ value: x.id, label: x.name }))))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!user) { setHasAssignments(false); return; }
    api.get<AssignmentRow[]>(`/users/${user.id}/assignments`)
      .then((rows) => setHasAssignments(rows.some((r) => r.is_active)))
      .catch(() => {});
  }, [user]);

  const set = (k: string) => (v: string) => setForm((s) => ({ ...s, [k]: v }));
  const roleChanged = !isCreate && user !== null && form.role !== user.role;

  const submit = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (isCreate) {
        const created = await api.post<User>("/users", {
          school_id: form.school_id, email: form.email, password: form.password,
          full_name: form.full_name, role: form.role, school_level: form.school_level,
          phone: form.phone || null, subject_id: form.subject_id || null,
        });
        onSaved(created);
      } else if (user) {
        const updated = await api.patch<User & { deactivated_assignments: number }>(`/users/${user.id}`, {
          full_name: form.full_name, role: form.role, school_level: form.school_level,
          phone: form.phone || null, subject_id: form.subject_id || null,
        });
        if (updated.deactivated_assignments > 0) {
          setNotice(`Đã vô hiệu ${updated.deactivated_assignments} phân công không còn phù hợp với vai trò mới.`);
        }
        onSaved(updated);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Lưu thất bại");
    } finally {
      setBusy(false);
    }
  };

  const canSubmit = isCreate
    ? !!(form.email && form.password && form.full_name && form.role && form.school_id)
    : !!form.full_name;

  return (
    <section className="space-y-3">
      <h4 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Hồ sơ</h4>
      {error && <Alert kind="error">{error}</Alert>}
      {notice && <Alert kind="info">{notice}</Alert>}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {isCreate && (
          <>
            <Field label="Email *"><input className={inputCls} value={form.email ?? ""} onChange={(e) => set("email")(e.target.value)} /></Field>
            <Field label="Mật khẩu *"><input type="password" className={inputCls} value={form.password ?? ""} onChange={(e) => set("password")(e.target.value)} /></Field>
          </>
        )}
        <Field label="Họ và tên *"><input className={inputCls} disabled={readOnly} value={form.full_name ?? ""} onChange={(e) => set("full_name")(e.target.value)} /></Field>
        <SearchableSelect label="Vai trò *" value={form.role ?? ""} onChange={set("role")} options={ALL_ROLES} disabled={readOnly} />
        {isCreate && schoolOptions.length > 1 && (
          <SearchableSelect label="Trường *" value={form.school_id ?? ""} onChange={set("school_id")} options={schoolOptions} />
        )}
        <SearchableSelect label="Môn phụ trách (GV)" value={form.subject_id ?? ""} onChange={set("subject_id")} options={subjects} disabled={readOnly} />
        <SearchableSelect label="Cấp phụ trách" value={form.school_level ?? "ALL"} onChange={set("school_level")} options={SCHOOL_LEVELS} disabled={readOnly} />
        <Field label="Điện thoại"><input className={inputCls} disabled={readOnly} value={form.phone ?? ""} onChange={(e) => set("phone")(e.target.value)} /></Field>
      </div>
      {roleChanged && hasAssignments && (
        <Alert kind="warn">
          <AlertTriangle className="w-4 h-4 inline mr-1" />
          Đổi vai trò sẽ tự vô hiệu các phân công không còn phù hợp với vai trò mới.
        </Alert>
      )}
      {!readOnly && (
        <button onClick={submit} disabled={busy || !canSubmit}
          className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-semibold flex items-center gap-2">
          {busy && <Loader2 className="w-4 h-4 animate-spin" />} {isCreate ? "Tạo tài khoản" : "Lưu thay đổi"}
        </button>
      )}
    </section>
  );
}

// ===== Phân công =====

function AssignmentSection({ user, readOnly }: { user: User; readOnly: boolean }) {
  const [options, setOptions] = useState<AssignmentOptions | null>(null);
  const [rows, setRows] = useState<AssignmentRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ academic_year_id: "", role_context: "" as RoleContext | "", class_id: "", grade_id: "", subject_id: "" });

  const load = useCallback(async () => {
    try {
      const [opts, assignments] = await Promise.all([
        api.get<AssignmentOptions>(`/users/${user.id}/assignment-options`),
        api.get<AssignmentRow[]>(`/users/${user.id}/assignments`),
      ]);
      setOptions(opts);
      setRows(assignments);
      const current = opts.years.find((y) => y.is_current);
      setForm((s) => ({ ...s, academic_year_id: s.academic_year_id || current?.id || "" }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Lỗi tải phân công");
    }
  }, [user.id]);

  useEffect(() => { load(); }, [load]);

  const nameOf = useMemo(() => {
    const m = new Map<string, string>();
    options?.years.forEach((y) => m.set(y.id, y.name));
    options?.classes.forEach((c) => m.set(c.id, c.name));
    options?.grades.forEach((g) => m.set(g.id, g.name));
    options?.subjects.forEach((s) => m.set(s.id, s.name));
    return (id: string | null) => (id ? m.get(id) ?? "—" : "—");
  }, [options]);

  if (options && options.allowed_contexts.length === 0) {
    return (
      <section className="space-y-2">
        <h4 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Phân công</h4>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Vai trò {ROLE_LABELS[user.role as UserRole]} không nhận phân công giảng dạy.
        </p>
      </section>
    );
  }

  const fields = form.role_context ? CONTEXT_FIELDS[form.role_context] : null;
  const classChoices = (options?.classes ?? []).filter((c) => c.academic_year_id === form.academic_year_id);
  const valid = !!(form.academic_year_id && form.role_context && fields
    && (!fields.class || form.class_id) && (!fields.grade || form.grade_id) && (!fields.subject || form.subject_id));

  const submit = async () => {
    if (!valid || !fields) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/users/assignments", {
        user_id: user.id, academic_year_id: form.academic_year_id, role_context: form.role_context,
        class_id: fields.class ? form.class_id : null,
        grade_id: fields.grade ? form.grade_id : null,
        subject_id: fields.subject ? form.subject_id : null,
      });
      setForm((s) => ({ ...s, class_id: "", grade_id: "", subject_id: "" }));
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Phân công thất bại");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    setError(null);
    try {
      await api.del(`/users/assignments/${id}`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Gỡ phân công thất bại");
    }
  };

  const contextOptions = ROLE_CONTEXTS.filter((c) => options?.allowed_contexts.includes(c.value));
  const toOpts = (xs: { id: string; name: string }[]) => xs.map((x) => ({ value: x.id, label: x.name }));

  return (
    <section className="space-y-3">
      <h4 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Phân công</h4>
      {error && <Alert kind="error">{error}</Alert>}

      {!readOnly && (
        <div className="bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 rounded-xl p-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <SearchableSelect label="Năm học *" value={form.academic_year_id}
              onChange={(v) => setForm((s) => ({ ...s, academic_year_id: v, class_id: "" }))}
              options={toOpts(options?.years ?? [])} />
            <SearchableSelect label="Vai trò phân công *" value={form.role_context}
              onChange={(v) => setForm((s) => ({ ...s, role_context: v as RoleContext, class_id: "", grade_id: "", subject_id: "" }))}
              options={contextOptions} />
            {fields?.class && (
              <SearchableSelect label="Lớp *" value={form.class_id}
                onChange={(v) => setForm((s) => ({ ...s, class_id: v }))} options={toOpts(classChoices)} />
            )}
            {fields?.grade && (
              <SearchableSelect label="Khối *" value={form.grade_id}
                onChange={(v) => setForm((s) => ({ ...s, grade_id: v }))} options={toOpts(options?.grades ?? [])} />
            )}
            {fields?.subject && (
              <SearchableSelect label="Môn *" value={form.subject_id}
                onChange={(v) => setForm((s) => ({ ...s, subject_id: v }))} options={toOpts(options?.subjects ?? [])} />
            )}
          </div>
          {form.role_context.startsWith("HOMEROOM") && (
            <p className="text-xs text-brand-600 dark:text-brand-400">
              ℹ️ Nhận chủ nhiệm sẽ tự thêm phân công dạy <b>môn phụ trách</b> của GV cho lớp đó.
            </p>
          )}
          <button onClick={submit} disabled={busy || !valid}
            className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-semibold flex items-center gap-2">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Phân công
          </button>
        </div>
      )}

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
        {rows.length === 0 ? (
          <p className="p-5 text-center text-sm text-slate-500 dark:text-slate-400">Chưa có phân công.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 dark:text-slate-400 text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left px-3 py-2.5">Năm học</th>
                <th className="text-left px-3 py-2.5">Vai trò</th>
                <th className="text-left px-3 py-2.5">Lớp/Khối/Môn</th>
                <th className="text-left px-3 py-2.5">Trạng thái</th>
                {!readOnly && <th className="text-right px-3 py-2.5" />}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {rows.map((a) => (
                <tr key={a.id} className={`text-slate-700 dark:text-slate-200 ${a.is_active ? "" : "opacity-50"}`}>
                  <td className="px-3 py-2.5">{nameOf(a.academic_year_id)}</td>
                  <td className="px-3 py-2.5">{ROLE_CONTEXTS.find((r) => r.value === a.role_context)?.label ?? a.role_context}</td>
                  <td className="px-3 py-2.5">
                    {[nameOf(a.class_id), nameOf(a.grade_id), nameOf(a.subject_id)].filter((x) => x !== "—").join(" · ") || "—"}
                  </td>
                  <td className="px-3 py-2.5">{a.is_active ? "Hoạt động" : "Đã vô hiệu"}</td>
                  {!readOnly && (
                    <td className="px-3 py-2.5 text-right">
                      <ConfirmDelete onConfirm={() => remove(a.id)} />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

// ===== Tiện ích nhỏ =====

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</label>
      {children}
    </div>
  );
}

function Alert({ kind, children }: { kind: "error" | "info" | "warn"; children: React.ReactNode }) {
  const cls = {
    error: "bg-rose-50 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300",
    info: "bg-brand-50 dark:bg-brand-500/10 border-brand-200 dark:border-brand-500/20 text-brand-700 dark:text-brand-300",
    warn: "bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20 text-amber-700 dark:text-amber-300",
  }[kind];
  return <div className={`p-3 rounded-lg border text-sm ${cls}`}>{children}</div>;
}

function ConfirmDelete({ onConfirm }: { onConfirm: () => void }) {
  const [confirming, setConfirming] = useState(false);
  if (confirming) {
    return (
      <span className="inline-flex items-center gap-1 text-xs">
        <button onClick={onConfirm} className="px-2 py-1 rounded bg-rose-600 text-white font-semibold">Gỡ</button>
        <button onClick={() => setConfirming(false)} className="px-2 py-1 rounded text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">Hủy</button>
      </span>
    );
  }
  return (
    <button onClick={() => setConfirming(true)}
      className="text-xs px-2 py-1 rounded text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10">
      Gỡ phân công
    </button>
  );
}
