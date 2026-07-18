"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Loader2, Pencil, Plus, Search, Trash2, X } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import SearchableSelect from "@/components/SearchableSelect";

// Bỏ dấu tiếng Việt để tìm kiếm "không dấu" cũng khớp.
function normalize(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
}

export interface FilterDef {
  key: string;
  label: string;
  options: { value: string; label: string }[];
}

export type FieldType = "text" | "password" | "number" | "date" | "select" | "checkbox";

export interface FormField {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  options?: { value: string; label: string }[];
  step?: number;
  min?: number;
  max?: number;
}

export interface Column {
  key: string;
  label: string;
  render?: (row: Record<string, unknown>) => React.ReactNode;
}

interface Props {
  title: string;
  endpoint: string;
  columns: Column[];
  fields: FormField[];
  editFields?: FormField[];
  staticValues?: Record<string, unknown>;
  deletable?: boolean;
  editable?: boolean;
  onChange?: () => void;
  /** Các cột để tìm kiếm (substring, không dấu). Có giá trị → hiện ô tìm kiếm. */
  searchKeys?: string[];
  searchPlaceholder?: string;
  /** Bộ lọc dạng dropdown theo giá trị cột (vd vai trò, môn phụ trách). */
  filters?: FilterDef[];
}

const inputCls =
  "w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none";

type Row = Record<string, unknown>;

function buildPayload(fields: FormField[], form: Row, base: Row, isEdit: boolean): Row {
  const out: Row = { ...base };
  for (const f of fields) {
    const v = form[f.name];
    if (f.type === "checkbox") {
      out[f.name] = !!v;
    } else if (v === "" || v === undefined || v === null) {
      if (f.required && !isEdit) out[f.name] = v; // để backend báo lỗi rõ ràng
    } else {
      out[f.name] = f.type === "number" ? Number(v) : v;
    }
  }
  return out;
}

export default function CrudManager({
  title, endpoint, columns, fields, editFields, staticValues = {},
  deletable = true, editable = true, onChange, searchKeys, searchPlaceholder, filters,
}: Props) {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<Row>({});
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});

  const visibleRows = useMemo(() => {
    const q = normalize(query.trim());
    return rows.filter((row) => {
      if (q && searchKeys?.length) {
        const hit = searchKeys.some((k) => normalize(String(row[k] ?? "")).includes(q));
        if (!hit) return false;
      }
      for (const [key, val] of Object.entries(filterValues)) {
        if (val && String(row[key] ?? "") !== val) return false;
      }
      return true;
    });
  }, [rows, query, searchKeys, filterValues]);
  const hasToolbar = !!searchKeys?.length || !!filters?.length;

  const reload = useCallback(async () => {
    setRows(await api.get<Row[]>(`${endpoint}?limit=500`));
    setError(null);
  }, [endpoint]);

  useEffect(() => {
    api
      .get<Row[]>(`${endpoint}?limit=500`)
      .then(setRows)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Không tải được danh sách"))
      .finally(() => setLoading(false));
  }, [endpoint]);

  const openCreate = () => {
    setEditingId(null);
    setForm({});
    setShowForm(true);
  };

  const openEdit = (row: Row) => {
    setEditingId(String(row.id));
    setForm({ ...row });
    setShowForm(true);
  };

  const activeFields = editingId && editFields ? editFields : fields;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      if (editingId) {
        await api.patch(`${endpoint}/${editingId}`, buildPayload(activeFields, form, {}, true));
      } else {
        await api.post(endpoint, buildPayload(fields, form, staticValues, false));
      }
      setShowForm(false);
      await reload();
      onChange?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Lưu thất bại");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      await api.del(`${endpoint}/${id}`);
      await reload();
      onChange?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Xóa thất bại");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-slate-900 dark:text-white">{title}</h3>
        <button onClick={openCreate}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold">
          <Plus className="w-4 h-4" /> Thêm
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
          {error}
        </div>
      )}

      {showForm && (
        <div className="bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-800 dark:text-slate-100">
              {editingId ? "Chỉnh sửa" : "Thêm mới"}
            </span>
            <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-slate-600">
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {activeFields.map((f) => (
              <div key={f.name} className="flex flex-col gap-1">
                <label className="text-xs font-medium text-slate-500 dark:text-slate-400">
                  {f.label}{f.required && !editingId ? " *" : ""}
                </label>
                {f.type === "select" ? (
                  <SearchableSelect value={String(form[f.name] ?? "")} options={f.options ?? []}
                    onChange={(v) => setForm((s) => ({ ...s, [f.name]: v }))} />
                ) : f.type === "checkbox" ? (
                  <input type="checkbox" checked={!!form[f.name]}
                    onChange={(e) => setForm((s) => ({ ...s, [f.name]: e.target.checked }))}
                    className="w-5 h-5 accent-brand-600" />
                ) : (
                  <input type={f.type} step={f.step} min={f.min} max={f.max}
                    value={String(form[f.name] ?? "")}
                    onChange={(e) => setForm((s) => ({ ...s, [f.name]: e.target.value }))}
                    className={inputCls} />
                )}
              </div>
            ))}
          </div>
          <button onClick={submit} disabled={busy}
            className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-semibold flex items-center gap-2">
            {busy && <Loader2 className="w-4 h-4 animate-spin" />} Lưu
          </button>
        </div>
      )}

      {hasToolbar && (
        <div className="flex flex-wrap items-end gap-3">
          {!!searchKeys?.length && (
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input value={query} onChange={(e) => setQuery(e.target.value)}
                placeholder={searchPlaceholder ?? "Tìm kiếm…"}
                className={`${inputCls} pl-9`} />
            </div>
          )}
          {filters?.map((f) => (
            <SearchableSelect key={f.key} label={f.label} value={filterValues[f.key] ?? ""}
              options={f.options} placeholder={`Tất cả ${f.label.toLowerCase()}`} className="min-w-[180px]"
              onChange={(v) => setFilterValues((s) => ({ ...s, [f.key]: v }))} />
          ))}
        </div>
      )}

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-8 flex justify-center"><Loader2 className="w-6 h-6 text-brand-500 animate-spin" /></div>
        ) : rows.length === 0 ? (
          <p className="p-6 text-center text-sm text-slate-500 dark:text-slate-400">Chưa có dữ liệu.</p>
        ) : visibleRows.length === 0 ? (
          <p className="p-6 text-center text-sm text-slate-500 dark:text-slate-400">Không có kết quả phù hợp với bộ lọc.</p>
        ) : (
          <div className="overflow-auto max-h-[65vh]">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 text-xs uppercase tracking-wider">
              <tr>
                {columns.map((c) => <th key={c.key} className="text-left px-4 py-3">{c.label}</th>)}
                {(editable || deletable) && <th className="text-right px-4 py-3">Thao tác</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {visibleRows.map((row) => (
                <tr key={String(row.id)} className="text-slate-700 dark:text-slate-200">
                  {columns.map((c) => (
                    <td key={c.key} className="px-4 py-3">
                      {c.render ? c.render(row) : String(row[c.key] ?? "—")}
                    </td>
                  ))}
                  {(editable || deletable) && (
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1.5">
                        {editable && (
                          <button title="Sửa" onClick={() => openEdit(row)}
                            className="p-1.5 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800">
                            <Pencil className="w-4 h-4" />
                          </button>
                        )}
                        {deletable && (
                          <DeleteButton onConfirm={() => remove(String(row.id))} />
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </div>
  );
}

function DeleteButton({ onConfirm }: { onConfirm: () => void }) {
  const [confirming, setConfirming] = useState(false);
  if (confirming) {
    return (
      <span className="flex items-center gap-1">
        <button title="Xác nhận xóa" onClick={onConfirm}
          className="p-1.5 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-500/10">
          <Check className="w-4 h-4" />
        </button>
        <button title="Hủy" onClick={() => setConfirming(false)}
          className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
          <X className="w-4 h-4" />
        </button>
      </span>
    );
  }
  return (
    <button title="Xóa" onClick={() => setConfirming(true)}
      className="p-1.5 rounded-lg text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10">
      <Trash2 className="w-4 h-4" />
    </button>
  );
}
