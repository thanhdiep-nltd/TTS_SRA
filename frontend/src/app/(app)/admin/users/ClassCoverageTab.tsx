"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";

import AssignCell from "@/components/admin/AssignCell";
import SearchableSelect from "@/components/SearchableSelect";
import { api, ApiError } from "@/lib/api";
import type { ClassCoverage, CoverageFilter, TeacherOption } from "@/lib/types";

export default function ClassCoverageTab({ filters, readOnly }: { filters: CoverageFilter[]; readOnly: boolean }) {
  const [schoolId, setSchoolId] = useState("");
  const [yearId, setYearId] = useState("");
  const [rows, setRows] = useState<ClassCoverage[]>([]);
  const [teachers, setTeachers] = useState<TeacherOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Mặc định: trường đầu tiên + niên khóa hiện tại của trường đó.
  useEffect(() => {
    if (filters.length === 0 || schoolId) return;
    const first = filters[0];
    setSchoolId(first.school_id);
    setYearId(first.years.find((y) => y.is_current)?.id ?? first.years[0]?.id ?? "");
  }, [filters, schoolId]);

  const years = useMemo(
    () => filters.find((f) => f.school_id === schoolId)?.years ?? [], [filters, schoolId]);

  useEffect(() => {
    if (!schoolId) return;
    api.get<TeacherOption[]>(`/users/assignments/teachers?school_id=${schoolId}`)
      .then(setTeachers)
      .catch(() => setTeachers([]));
  }, [schoolId]);

  const load = useCallback(async () => {
    if (!yearId) return;
    setLoading(true);
    try {
      setRows(await api.get<ClassCoverage[]>(`/users/assignments/coverage?academic_year_id=${yearId}`));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không tải được dữ liệu");
    } finally {
      setLoading(false);
    }
  }, [yearId]);

  useEffect(() => { load(); }, [load]);

  const assign = useCallback(async (
    userId: string, classId: string, roleContext: "HOMEROOM_PRIMARY" | "HOMEROOM_SECONDARY" | "SUBJECT_TEACHER", subjectId?: string,
  ) => {
    await api.put("/users/assignments/reassign", {
      user_id: userId, academic_year_id: yearId, role_context: roleContext,
      class_id: classId, subject_id: subjectId ?? null,
    });
    await load();
  }, [yearId, load]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        {filters.length > 1 && (
          <SearchableSelect label="Trường" value={schoolId} className="min-w-[220px]"
            onChange={(v) => {
              setSchoolId(v);
              const f = filters.find((x) => x.school_id === v);
              setYearId(f?.years.find((y) => y.is_current)?.id ?? f?.years[0]?.id ?? "");
            }}
            options={filters.map((f) => ({ value: f.school_id, label: f.school_name }))} />
        )}
        <SearchableSelect label="Niên khóa" value={yearId} onChange={setYearId} className="min-w-[180px]"
          options={years.map((y) => ({ value: y.id, label: y.name + (y.is_current ? " (hiện tại)" : "") }))} />
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
          {error}
        </div>
      )}

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-8 flex justify-center"><Loader2 className="w-6 h-6 text-brand-500 animate-spin" /></div>
        ) : rows.length === 0 ? (
          <p className="p-6 text-center text-sm text-slate-500 dark:text-slate-400">Niên khóa chưa có lớp nào.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 dark:text-slate-400 text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left px-4 py-3">Lớp</th>
                <th className="text-left px-4 py-3">Khối</th>
                <th className="text-left px-4 py-3">Chủ nhiệm</th>
                <th className="text-left px-4 py-3">GV bộ môn</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {rows.map((r) => (
                <CoverageRow key={r.class_id} row={r} readOnly={readOnly} teachers={teachers} onAssign={assign} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function CoverageRow({ row, readOnly, teachers, onAssign }: {
  row: ClassCoverage; readOnly: boolean; teachers: TeacherOption[];
  onAssign: (userId: string, classId: string, roleContext: "HOMEROOM_PRIMARY" | "HOMEROOM_SECONDARY" | "SUBJECT_TEACHER", subjectId?: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const assigned = row.subjects.filter((s) => s.teacher_name).length;
  const missing = row.subjects.filter((s) => !s.teacher_name);
  const full = missing.length === 0;

  return (
    <>
      <tr onClick={() => setOpen((o) => !o)}
        className="text-slate-700 dark:text-slate-200 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40">
        <td className="px-4 py-3 font-medium">
          <span className="inline-flex items-center gap-1.5">
            {open ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
            {row.name}
          </span>
        </td>
        <td className="px-4 py-3">{row.grade_name}</td>
        <td className="px-4 py-3">
          <AssignCell label={row.homeroom_teacher} emptyLabel="Thiếu chủ nhiệm" readOnly={readOnly} teachers={teachers}
            onAssign={(userId) => onAssign(userId, row.class_id, "HOMEROOM_SECONDARY")} />
        </td>
        <td className="px-4 py-3">
          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
            full
              ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
              : "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400"
          }`}>
            {assigned}/{row.subjects.length} môn
          </span>
        </td>
      </tr>
      {open && (
        <tr className="bg-slate-50/60 dark:bg-slate-800/20">
          <td colSpan={4} className="px-4 py-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2 text-xs">
              {row.subjects.map((s) => (
                <div key={s.subject_id} className="flex items-center justify-between gap-2">
                  <span className="text-slate-500 dark:text-slate-400 shrink-0">{s.name}</span>
                  <AssignCell label={s.teacher_name} emptyLabel="Chưa có GV" readOnly={readOnly} teachers={teachers}
                    preferredSubjectId={s.subject_id}
                    onAssign={(userId) => onAssign(userId, row.class_id, "SUBJECT_TEACHER", s.subject_id)} />
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
