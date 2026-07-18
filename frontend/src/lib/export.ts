import * as XLSX from "xlsx";

export type Cell = string | number | null;

function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** CSV phẳng (UTF-8 BOM để Excel đọc tiếng Việt). aoa gồm cả dòng tiêu đề. */
export function exportCSV(filename: string, aoa: Cell[][]): void {
  const esc = (v: Cell) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const content = aoa.map((row) => row.map(esc).join(",")).join("\n");
  downloadBlob(filename, new Blob(["﻿" + content], { type: "text/csv;charset=utf-8;" }));
}

/** Excel .xlsx từ array-of-arrays + danh sách ô gộp (merge). */
export function exportXLSX(filename: string, aoa: Cell[][], merges: XLSX.Range[] = []): void {
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  if (merges.length) ws["!merges"] = merges;
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "BangDiem");
  const buf = XLSX.write(wb, { bookType: "xlsx", type: "array" });
  downloadBlob(
    filename,
    new Blob([buf], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
  );
}

/** Xuất PDF = mở hộp thoại in của trình duyệt (CSS @media print lo phần trình bày). */
export function exportPDF(): void {
  window.print();
}
