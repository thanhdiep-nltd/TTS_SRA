"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import CrudManager, { type Column, type FormField } from "@/components/admin/CrudManager";
import Tabs from "@/components/admin/Tabs";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { SCHOOL_LEVELS, type AcademicYear, type Grade } from "@/lib/types";

const yesNo = (v: unknown) => (v ? "✓" : "—");

export default function SchoolAdminPage() {
  const { user } = useAuth();
  const schoolId = user?.school_id ?? "";
  const [years, setYears] = useState<AcademicYear[]>([]);
  const [grades, setGrades] = useState<Grade[]>([]);

  const loadRefs = useCallback(async () => {
    const [y, g] = await Promise.all([
      api.get<AcademicYear[]>("/academic-years?limit=200"),
      api.get<Grade[]>("/grades?limit=200"),
    ]);
    setYears(y);
    setGrades(g);
  }, []);

  useEffect(() => {
    Promise.all([
      api.get<AcademicYear[]>("/academic-years?limit=200"),
      api.get<Grade[]>("/grades?limit=200"),
    ])
      .then(([y, g]) => { setYears(y); setGrades(g); })
      .catch(() => {});
  }, []);

  const yearOpts = years.map((y) => ({ value: y.id, label: y.name }));
  const gradeOpts = grades.map((g) => ({ value: g.id, label: g.name }));
  const levelMap = useMemo(() => Object.fromEntries(SCHOOL_LEVELS.map((l) => [l.value, l.label])), []);
  const yearMap = useMemo(() => Object.fromEntries(years.map((y) => [y.id, y.name])), [years]);
  const gradeMap = useMemo(() => Object.fromEntries(grades.map((g) => [g.id, g.name])), [grades]);

  // --- Năm học ---
  const yearFields: FormField[] = [
    { name: "name", label: "Tên (vd 2025-2026)", type: "text", required: true },
    { name: "start_date", label: "Ngày bắt đầu", type: "date", required: true },
    { name: "end_date", label: "Ngày kết thúc", type: "date", required: true },
    { name: "is_current", label: "Là năm học hiện tại", type: "checkbox" },
  ];
  const yearCols: Column[] = [
    { key: "name", label: "Niên khóa" },
    { key: "start_date", label: "Bắt đầu" },
    { key: "end_date", label: "Kết thúc" },
    { key: "is_current", label: "Hiện tại", render: (r) => yesNo(r.is_current) },
  ];

  // --- Học kỳ ---
  const semCreate: FormField[] = [
    { name: "academic_year_id", label: "Năm học", type: "select", required: true, options: yearOpts },
    { name: "name", label: "Tên (HK1/HK2)", type: "text", required: true },
    { name: "number", label: "Số (1 hoặc 2)", type: "number", required: true, min: 1, max: 2 },
    { name: "start_date", label: "Bắt đầu", type: "date", required: true },
    { name: "end_date", label: "Kết thúc", type: "date", required: true },
    { name: "is_current", label: "Hiện tại", type: "checkbox" },
  ];
  const semEdit = semCreate.filter((f) => f.name !== "academic_year_id");
  const semCols: Column[] = [
    { key: "name", label: "Học kỳ" },
    { key: "number", label: "Số" },
    { key: "academic_year_id", label: "Năm học", render: (r) => yearMap[String(r.academic_year_id)] ?? "—" },
    { key: "is_current", label: "Hiện tại", render: (r) => yesNo(r.is_current) },
  ];

  // --- Khối ---
  const gradeFields: FormField[] = [
    { name: "name", label: "Tên khối (vd Khối 6)", type: "text", required: true },
    { name: "grade_number", label: "Số khối (1–12)", type: "number", required: true, min: 1, max: 12 },
    { name: "school_level", label: "Cấp học", type: "select", required: true, options: SCHOOL_LEVELS.slice(0, 3) },
  ];
  const gradeCols: Column[] = [
    { key: "name", label: "Khối" },
    { key: "grade_number", label: "Số" },
    { key: "school_level", label: "Cấp", render: (r) => levelMap[String(r.school_level)] ?? "—" },
  ];

  // --- Lớp ---
  const classCreate: FormField[] = [
    { name: "grade_id", label: "Khối", type: "select", required: true, options: gradeOpts },
    { name: "name", label: "Tên lớp (vd 6A1)", type: "text", required: true },
    { name: "academic_year_id", label: "Năm học", type: "select", required: true, options: yearOpts },
  ];
  const classEdit: FormField[] = [
    { name: "name", label: "Tên lớp", type: "text" },
    { name: "student_count", label: "Sĩ số", type: "number", min: 0 },
  ];
  const classCols: Column[] = [
    { key: "name", label: "Lớp" },
    { key: "grade_id", label: "Khối", render: (r) => gradeMap[String(r.grade_id)] ?? "—" },
    { key: "academic_year_id", label: "Năm học", render: (r) => yearMap[String(r.academic_year_id)] ?? "—" },
  ];

  // --- Môn ---
  const subjectCreate: FormField[] = [
    { name: "name", label: "Tên môn (vd Toán)", type: "text", required: true },
    { name: "code", label: "Mã môn (vd TOAN)", type: "text", required: true },
  ];
  const subjectEdit: FormField[] = [
    { name: "name", label: "Tên môn", type: "text" },
    { name: "code", label: "Mã môn", type: "text" },
    { name: "is_active", label: "Đang dùng", type: "checkbox" },
  ];
  const subjectCols: Column[] = [
    { key: "name", label: "Môn học" },
    { key: "code", label: "Mã" },
    { key: "is_active", label: "Hoạt động", render: (r) => yesNo(r.is_active) },
  ];

  return (
    <div className="p-8 max-w-6xl mx-auto w-full space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Quản trị cơ cấu trường</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Năm học, học kỳ, khối, lớp và môn học.</p>
      </div>
      <Tabs
        tabs={[
          {
            label: "Năm học",
            content: (
              <CrudManager title="Năm học" endpoint="/academic-years" columns={yearCols} fields={yearFields}
                staticValues={{ school_id: schoolId }} onChange={loadRefs} />
            ),
          },
          {
            label: "Học kỳ",
            content: (
              <CrudManager title="Học kỳ" endpoint="/semesters" columns={semCols} fields={semCreate} editFields={semEdit} />
            ),
          },
          {
            label: "Khối",
            content: (
              <CrudManager title="Khối lớp" endpoint="/grades" columns={gradeCols} fields={gradeFields}
                staticValues={{ school_id: schoolId }} onChange={loadRefs} />
            ),
          },
          {
            label: "Lớp",
            content: (
              <CrudManager title="Lớp học" endpoint="/classes" columns={classCols} fields={classCreate} editFields={classEdit} />
            ),
          },
          {
            label: "Môn học",
            content: (
              <CrudManager title="Môn học" endpoint="/subjects" columns={subjectCols} fields={subjectCreate}
                editFields={subjectEdit} staticValues={{ school_id: schoolId }} />
            ),
          },
        ]}
      />
    </div>
  );
}
