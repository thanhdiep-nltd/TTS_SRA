"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { CurriculumUnitOption } from "@/lib/types";
import type { Option } from "@/components/SearchableSelect";

// Sắp theo số cuối trong code (vd "TOAN6-C1-L10" -> 10) — tránh sort chuỗi đặt "L10" trước "L2".
function unitSortKey(code: string): number {
  const m = code.match(/(\d+)$/);
  return m ? parseInt(m[1], 10) : 0;
}

/** Fetch thô đơn vị chương trình (chương + bài học) ĐÚNG môn+khối, is_active — dùng chung cho
 * useCurriculumUnits (dropdown phẳng) và useCurriculumTree (picker phân cấp chương/bài học). */
function useCurriculumRaw(subjectId: string, gradeNumber: string): CurriculumUnitOption[] {
  const [units, setUnits] = useState<CurriculumUnitOption[]>([]);
  useEffect(() => {
    if (!subjectId) {
      setUnits([]);
      return;
    }
    let cancelled = false;
    const params = new URLSearchParams({ subject_id: subjectId });
    if (gradeNumber) params.set("grade_number", gradeNumber);
    api
      .get<CurriculumUnitOption[]>(`/curriculum-units?${params.toString()}`)
      .then((d) => {
        if (!cancelled) setUnits(d);
      })
      .catch(() => {
        if (!cancelled) setUnits([]);
      });
    return () => {
      cancelled = true;
    };
  }, [subjectId, gradeNumber]);
  return units;
}

/** Chủ đề/chương lọc server-side theo ĐÚNG (môn, khối) — dropdown phẳng (chương + bài học);
 * bài học ghi kèm tên chương cha để phân biệt (vd "Chương I: Số tự nhiên · Tập hợp"). */
export function useCurriculumUnits(subjectId: string, gradeNumber: string): Option[] {
  const units = useCurriculumRaw(subjectId, gradeNumber);
  return useMemo(() => {
    const byId = new Map(units.map((u) => [u.id, u]));
    return units
      .slice()
      .sort((a, b) => unitSortKey(a.code) - unitSortKey(b.code) || a.code.localeCompare(b.code))
      .map((u) => {
        const parent = u.parent_id ? byId.get(u.parent_id) : undefined;
        return { value: u.id, label: parent ? `${parent.name} · ${u.name}` : u.name };
      });
  }, [units]);
}

export interface CurriculumTree {
  chapters: CurriculumUnitOption[]; // chương gốc (parent_id null), đã sắp theo thứ tự
  lessonsByChapter: Map<string, CurriculumUnitOption[]>; // chapter.id -> bài học con đã sắp
}

/** Cây chương/bài học ĐÚNG môn+khối — dùng cho picker phân cấp (vd wizard tạo đề). */
export function useCurriculumTree(subjectId: string, gradeNumber: string): CurriculumTree {
  const units = useCurriculumRaw(subjectId, gradeNumber);
  return useMemo(() => {
    const chapters = units.filter((u) => !u.parent_id).sort((a, b) => unitSortKey(a.code) - unitSortKey(b.code));
    const lessonsByChapter = new Map<string, CurriculumUnitOption[]>();
    for (const u of units) {
      if (!u.parent_id) continue;
      const arr = lessonsByChapter.get(u.parent_id) ?? [];
      arr.push(u);
      lessonsByChapter.set(u.parent_id, arr);
    }
    for (const arr of lessonsByChapter.values()) {
      arr.sort((a, b) => unitSortKey(a.code) - unitSortKey(b.code));
    }
    return { chapters, lessonsByChapter };
  }, [units]);
}
