"use client";

import { useState } from "react";
import { Check, Pencil, X } from "lucide-react";

import SearchableSelect from "@/components/SearchableSelect";
import { ApiError } from "@/lib/api";
import type { TeacherOption } from "@/lib/types";

interface Props {
  /** Tên GV hiện tại, hoặc null nếu chưa có ai. */
  label: string | null;
  /** Nhãn hiện khi label=null (vd "Thiếu chủ nhiệm" / "Chưa có GV"). */
  emptyLabel: string;
  readOnly: boolean;
  teachers: TeacherOption[];
  /** Môn đang phân công (nếu có) — GV có subject_id khớp được gợi ý lên đầu. */
  preferredSubjectId?: string;
  onAssign: (userId: string) => Promise<void>;
}

export default function AssignCell({ label, emptyLabel, readOnly, teachers, preferredSubjectId, onAssign }: Props) {
  const [editing, setEditing] = useState(false);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openEditor = () => {
    setSelected("");
    setError(null);
    setEditing(true);
  };

  const commit = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await onAssign(selected);
      setEditing(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Phân công thất bại");
    } finally {
      setBusy(false);
    }
  };

  if (!editing) {
    return (
      <span className="inline-flex items-center gap-1.5">
        {label ? (
          <span>{label}</span>
        ) : (
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-400">
            {emptyLabel}
          </span>
        )}
        {!readOnly && (
          <button title="Phân công" onClick={openEditor}
            className="p-1 rounded text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800">
            <Pencil className="w-3.5 h-3.5" />
          </button>
        )}
      </span>
    );
  }

  const options = [...teachers]
    .sort((a, b) => {
      const aMatch = a.subject_id === preferredSubjectId ? 0 : 1;
      const bMatch = b.subject_id === preferredSubjectId ? 0 : 1;
      return aMatch - bMatch || a.full_name.localeCompare(b.full_name);
    })
    .map((t) => ({
      value: t.id,
      label: preferredSubjectId && t.subject_id === preferredSubjectId ? `${t.full_name} · đúng môn phụ trách` : t.full_name,
    }));

  return (
    <span className="inline-flex flex-col gap-1" onClick={(e) => e.stopPropagation()}>
      <span className="inline-flex items-center gap-1">
        <SearchableSelect value={selected} onChange={setSelected} options={options}
          placeholder="— Chọn GV —" className="min-w-[200px]" />
        <button title="Xác nhận" disabled={busy || !selected} onClick={commit}
          className="p-1 rounded text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 disabled:opacity-40">
          <Check className="w-4 h-4" />
        </button>
        <button title="Hủy" onClick={() => setEditing(false)}
          className="p-1 rounded text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
          <X className="w-4 h-4" />
        </button>
      </span>
      {error && <span className="text-xs text-rose-600 dark:text-rose-400">{error}</span>}
    </span>
  );
}
