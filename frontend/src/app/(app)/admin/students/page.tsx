"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import CrudManager, { type Column, type FormField } from "@/components/admin/CrudManager";
import Tabs from "@/components/admin/Tabs";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AcademicYear, ClassRow, Student } from "@/lib/types";

const GENDERS = [
  { value: "MALE", label: "Nam" },
  { value: "FEMALE", label: "Nữ" },
  { value: "OTHER", label: "Khác" },
];

export default function StudentsAdminPage() {
  const { user } = useAuth();
  const schoolId = user?.school_id ?? "";
  const [students, setStudents] = useState<Student[]>([]);
  const [classes, setClasses] = useState<ClassRow[]>([]);
  const [years, setYears] = useState<AcademicYear[]>([]);

  const loadRefs = useCallback(async () => {
    const [st, cl, yr] = await Promise.all([
      api.get<Student[]>("/students?limit=1000"),
      api.get<ClassRow[]>("/classes?limit=500"),
      api.get<AcademicYear[]>("/academic-years?limit=200"),
    ]);
    setStudents(st);
    setClasses(cl);
    setYears(yr);
  }, []);

  useEffect(() => {
    Promise.all([
      api.get<Student[]>("/students?limit=1000"),
      api.get<ClassRow[]>("/classes?limit=500"),
      api.get<AcademicYear[]>("/academic-years?limit=200"),
    ])
      .then(([st, cl, yr]) => { setStudents(st); setClasses(cl); setYears(yr); })
      .catch(() => {});
  }, []);

  const studentMap = useMemo(() => Object.fromEntries(students.map((s) => [s.id, `${s.full_name} (${s.student_code})`])), [students]);
  const classMap = useMemo(() => Object.fromEntries(classes.map((c) => [c.id, c.name])), [classes]);
  const yearMap = useMemo(() => Object.fromEntries(years.map((y) => [y.id, y.name])), [years]);

  const studentFields: FormField[] = [
    { name: "student_code", label: "Mã học sinh", type: "text", required: true },
    { name: "full_name", label: "Họ và tên", type: "text", required: true },
    { name: "date_of_birth", label: "Ngày sinh", type: "date" },
    { name: "gender", label: "Giới tính", type: "select", options: GENDERS },
  ];
  const studentEdit: FormField[] = [...studentFields, { name: "is_active", label: "Đang học", type: "checkbox" }];
  const studentCols: Column[] = [
    { key: "student_code", label: "Mã HS" },
    { key: "full_name", label: "Họ và tên" },
    { key: "date_of_birth", label: "Ngày sinh" },
    { key: "gender", label: "Giới tính", render: (r) => GENDERS.find((g) => g.value === r.gender)?.label ?? "—" },
  ];

  const enrollCreate: FormField[] = [
    { name: "student_id", label: "Học sinh", type: "select", required: true, options: students.map((s) => ({ value: s.id, label: studentMap[s.id] })) },
    { name: "class_id", label: "Lớp", type: "select", required: true, options: classes.map((c) => ({ value: c.id, label: c.name })) },
    { name: "academic_year_id", label: "Năm học", type: "select", required: true, options: years.map((y) => ({ value: y.id, label: y.name })) },
  ];
  const enrollEdit: FormField[] = [{ name: "is_active", label: "Đang học", type: "checkbox" }];
  const enrollCols: Column[] = [
    { key: "student_id", label: "Học sinh", render: (r) => studentMap[String(r.student_id)] ?? "—" },
    { key: "class_id", label: "Lớp", render: (r) => classMap[String(r.class_id)] ?? "—" },
    { key: "academic_year_id", label: "Năm học", render: (r) => yearMap[String(r.academic_year_id)] ?? "—" },
  ];

  return (
    <div className="p-8 max-w-6xl mx-auto w-full space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Quản trị học sinh</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Hồ sơ học sinh và ghi danh vào lớp theo năm học.</p>
      </div>
      <Tabs
        tabs={[
          {
            label: "Học sinh",
            content: (
              <CrudManager title="Học sinh" endpoint="/students" columns={studentCols} fields={studentFields}
                editFields={studentEdit} staticValues={{ school_id: schoolId }} onChange={loadRefs}
                searchKeys={["full_name", "student_code"]} searchPlaceholder="Tìm theo tên hoặc mã học sinh…" />
            ),
          },
          {
            label: "Ghi danh",
            content: (
              <CrudManager title="Ghi danh lớp" endpoint="/enrollments" columns={enrollCols} fields={enrollCreate}
                editFields={enrollEdit} />
            ),
          },
        ]}
      />
    </div>
  );
}
