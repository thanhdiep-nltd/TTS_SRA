"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown, Search } from "lucide-react";

export interface Option {
  value: string;
  label: string;
}

interface Props {
  value: string;
  onChange: (v: string) => void;
  options: Option[];
  label?: string;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  /** Ngưỡng bật ô tìm kiếm: danh sách dài hơn mức này sẽ hiện input lọc. */
  searchThreshold?: number;
}

// Bỏ dấu tiếng Việt để tìm kiếm "không dấu" cũng khớp.
function normalize(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
}

const FIELD =
  "w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 text-sm outline-none focus:border-brand";

/**
 * Dropdown chọn 1 mục. Khi số mục > searchThreshold (mặc định 5) tự hiện ô tìm kiếm.
 * Với danh sách ngắn, render như <select> thường để giữ giao diện/hành vi quen thuộc.
 */
export default function SearchableSelect({
  value, onChange, options, label, placeholder = "— Chọn —", className = "", disabled = false, searchThreshold = 5,
}: Props) {
  const searchable = options.length > searchThreshold;

  if (!searchable) {
    return (
      <Wrap label={label} className={className}>
        <select className={FIELD} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          <option value="">{placeholder}</option>
          {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </Wrap>
    );
  }

  return (
    <Wrap label={label} className={className}>
      <Combobox value={value} onChange={onChange} options={options} placeholder={placeholder} disabled={disabled} />
    </Wrap>
  );
}

function Wrap({ label, className, children }: { label?: string; className?: string; children: React.ReactNode }) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {label && <label className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</label>}
      {children}
    </div>
  );
}

// Chiều cao ước lượng của panel (ô tìm + list) — dùng để quyết định mở lên hay xuống.
const PANEL_ESTIMATE_PX = 320;

function Combobox({ value, onChange, options, placeholder, disabled }: {
  value: string; onChange: (v: string) => void; options: Option[]; placeholder: string; disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [pos, setPos] = useState<{ top: number; bottom: number; left: number; width: number; openUp: boolean } | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const selected = options.find((o) => o.value === value);
  const filtered = useMemo(() => {
    const q = normalize(query.trim());
    return q ? options.filter((o) => normalize(o.label).includes(q)) : options;
  }, [options, query]);

  // Panel render qua portal (document.body) với position:fixed theo toạ độ nút bấm — tránh bị
  // ancestor có overflow-hidden/overflow-x-auto (vd bảng ma trận đề) cắt mất khi hàng ở gần
  // cuối container. Tự chọn mở lên nếu khoảng trống phía dưới không đủ và phía trên rộng hơn.
  const computePosition = () => {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const spaceBelow = window.innerHeight - rect.bottom;
    const openUp = spaceBelow < PANEL_ESTIMATE_PX && rect.top > spaceBelow;
    setPos({ top: rect.top, bottom: rect.bottom, left: rect.left, width: rect.width, openUp });
  };

  useEffect(() => {
    if (!open) return;
    computePosition();
    const onDoc = (e: MouseEvent) => {
      const target = e.target as Node;
      if (!boxRef.current?.contains(target) && !panelRef.current?.contains(target)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    // Đóng khi cuộn (kể cả cuộn trong container lồng nhau, capture:true) thay vì bám theo vị
    // trí — đơn giản và tránh panel bị lệch/kẹt vị trí cũ.
    const onScrollOrResize = () => setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [open]);

  const pick = (v: string) => { onChange(v); setOpen(false); setQuery(""); };

  return (
    <div ref={boxRef} className="relative">
      <button ref={triggerRef} type="button" disabled={disabled} onClick={() => setOpen((o) => !o)}
        className={`${FIELD} flex items-center justify-between gap-2 text-left disabled:opacity-50`}>
        <span className={selected ? "" : "text-slate-400"}>{selected?.label ?? placeholder}</span>
        <ChevronDown className="w-4 h-4 shrink-0 text-slate-400" />
      </button>

      {open && pos && createPortal(
        <div
          ref={panelRef}
          style={{
            position: "fixed",
            left: pos.left,
            width: pos.width,
            ...(pos.openUp
              ? { bottom: window.innerHeight - pos.top + 4 }
              : { top: pos.bottom + 4 }),
          }}
          className="z-50 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg"
        >
          <div className="p-2 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-slate-100 dark:bg-slate-800">
              <Search className="w-4 h-4 text-slate-400 shrink-0" />
              <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm nhanh…"
                className="w-full bg-transparent text-sm outline-none text-slate-900 dark:text-slate-100" />
            </div>
          </div>
          <ul className="max-h-60 overflow-y-auto py-1">
            <li>
              <Item active={!value} label={placeholder} muted onClick={() => pick("")} />
            </li>
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-slate-400">Không tìm thấy.</li>
            ) : (
              filtered.map((o) => (
                <li key={o.value}>
                  <Item active={o.value === value} label={o.label} onClick={() => pick(o.value)} />
                </li>
              ))
            )}
          </ul>
        </div>,
        document.body
      )}
    </div>
  );
}

function Item({ label, active, muted, onClick }: { label: string; active: boolean; muted?: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick}
      className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-brand-50 dark:hover:bg-slate-800 ${
        active ? "text-brand font-semibold" : muted ? "text-slate-400" : "text-slate-700 dark:text-slate-200"
      }`}>
      <span className="truncate">{label}</span>
      {active && <Check className="w-4 h-4 shrink-0 text-brand" />}
    </button>
  );
}
