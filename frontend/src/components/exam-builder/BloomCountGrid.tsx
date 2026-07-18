"use client";

import type { ExamFormat } from "@/lib/types";

interface Props {
  examFormat: ExamFormat;
  getCount: (qtype: "MCQ" | "ESSAY", bloom: number) => number;
  setCount: (qtype: "MCQ" | "ESSAY", bloom: number, value: number) => void;
}

const BLOOMS = [1, 2, 3, 4, 5, 6];
const ROW_LABEL: Record<"MCQ" | "ESSAY", string> = { MCQ: "TN", ESSAY: "TL" };

// Lưới nhập nhanh số câu theo mức Bloom (1-6) cho 1 chương/bài học — dùng ở luồng "Tự soạn
// ma trận thủ công" (exam-builder Step 1). 1 hàng nếu đề 100% TN/TL, 2 hàng (TN+TL) nếu Mix.
export default function BloomCountGrid({ examFormat, getCount, setCount }: Props) {
  const rows: Array<"MCQ" | "ESSAY"> =
    examFormat === "MCQ_ONLY" ? ["MCQ"] : examFormat === "ESSAY_ONLY" ? ["ESSAY"] : ["MCQ", "ESSAY"];

  return (
    <div className="flex flex-col gap-1 mt-1.5 mb-2">
      {rows.map((qtype) => (
        <div key={qtype} className="flex items-center gap-1">
          <span className="w-6 shrink-0 text-xs font-semibold text-slate-500 dark:text-slate-400">
            {ROW_LABEL[qtype]}
          </span>
          {BLOOMS.map((bloom) => (
            <input
              key={bloom}
              type="number"
              min={0}
              title={`Bloom ${bloom}`}
              value={getCount(qtype, bloom) || ""}
              onChange={(e) => setCount(qtype, bloom, Math.max(0, Number(e.target.value) || 0))}
              placeholder="0"
              className="w-9 px-1 py-1 rounded border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-xs text-center outline-none focus:border-brand"
            />
          ))}
        </div>
      ))}
    </div>
  );
}
