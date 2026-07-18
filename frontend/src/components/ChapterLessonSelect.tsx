"use client";

import { useMemo } from "react";

import { useCurriculumTree } from "@/lib/useCurriculumUnits";
import SearchableSelect from "./SearchableSelect";

interface Props {
  subjectId: string;
  gradeNumber: string; // "" nếu chưa chọn khối
  /** Lọc chương theo học kỳ (chương SGK không tách tập luôn hiện) — bỏ qua nếu không cần lọc. */
  semesterNumber?: number | null;
  value: string; // unit_id cuối cùng đã chọn (chương HOẶC bài học con)
  onChange: (unitId: string) => void;
  className?: string;
}

const WHOLE_CHAPTER = "__CHUONG__";

/** Picker 2 bước Chương -> Bài học (tùy chọn), thay thế dropdown "Chủ đề" phẳng cũ. Chọn 1
 * chương mặc định áp dụng CẢ CHƯƠNG (unit_id = chương); nếu chương có bài học, GV có thể thu
 * hẹp xuống đúng 1 bài học cụ thể ở dropdown thứ hai. */
export default function ChapterLessonSelect({
  subjectId, gradeNumber, semesterNumber, value, onChange, className,
}: Props) {
  const tree = useCurriculumTree(subjectId, gradeNumber);

  const scopedChapters = useMemo(
    () =>
      semesterNumber == null
        ? tree.chapters
        : tree.chapters.filter((c) => c.semester_number === null || c.semester_number === semesterNumber),
    [tree.chapters, semesterNumber]
  );

  const chapterId = useMemo(() => {
    if (!value) return "";
    if (scopedChapters.some((c) => c.id === value)) return value;
    for (const c of scopedChapters) {
      if ((tree.lessonsByChapter.get(c.id) ?? []).some((l) => l.id === value)) return c.id;
    }
    return "";
  }, [value, scopedChapters, tree.lessonsByChapter]);

  const lessons = chapterId ? (tree.lessonsByChapter.get(chapterId) ?? []) : [];

  return (
    <div className={`grid grid-cols-2 gap-3 ${className ?? ""}`}>
      <SearchableSelect
        label="Chương"
        value={chapterId}
        onChange={onChange}
        options={scopedChapters.map((c) => ({ value: c.id, label: c.name }))}
      />
      {lessons.length > 0 && (
        <SearchableSelect
          label="Bài học (tùy chọn)"
          value={value !== chapterId ? value : WHOLE_CHAPTER}
          onChange={(v) => onChange(v === WHOLE_CHAPTER ? chapterId : v)}
          options={[
            { value: WHOLE_CHAPTER, label: "— Cả chương —" },
            ...lessons.map((l) => ({ value: l.id, label: l.name })),
          ]}
        />
      )}
    </div>
  );
}
