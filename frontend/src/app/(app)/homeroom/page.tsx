"use client";

import { useEffect, useMemo, useState } from "react";
import { FileDown, Link2, Loader2, Replace, Unlink, Upload, X } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useApiBusy } from "@/lib/useApiBusy";
import { useAuth } from "@/lib/auth";
import { exportCSV, exportXLSX, type Cell } from "@/lib/export";
import MapExamModal from "@/components/gradebook/MapExamModal";
import ImportScoreModal from "@/components/gradebook/ImportScoreModal";
import SearchableSelect from "@/components/SearchableSelect";
import { LoadingOverlay, LoadingState } from "@/components/Loading";
import {
  APPROVE_ROLES, canMapCategory, CONDUCT_LABELS, CONDUCT_OPTIONS, PASS_FAIL_LABELS, PASS_FAIL_OPTIONS, SCORE_WRITE_ROLES,
  type AcademicYear, type ClassRow, type ClassSummaryResponse, type ExamRef, type GradebookColumn,
  type GradeCell, type GradebookResponse, type Grade, type PassFail, type Semester, type Subject,
} from "@/lib/types";

const SCHOOL_HEADER = ["SỞ GIÁO DỤC VÀ ĐÀO TẠO", "TRƯỜNG THCS MẪU"];
const GROUP_LABELS: Record<string, string> = {
  ORAL: "Kiểm tra miệng", REGULAR: "ĐĐGtx (Thường xuyên)",
  MIDTERM: "ĐĐGgk (Giữa kỳ)", FINAL: "ĐĐGck (Cuối kỳ)",
};
const fmt = (v: number | null | undefined) => (v == null ? "" : String(v));

function buildGroups(columns: GradebookColumn[]) {
  const groups: { category: string; label: string; cols: GradebookColumn[] }[] = [];
  for (const c of columns) {
    let g = groups.find((x) => x.category === c.category);
    if (!g) {
      g = { category: c.category, label: GROUP_LABELS[c.category] ?? c.category, cols: [] };
      groups.push(g);
    }
    g.cols.push(c);
  }
  return groups;
}

export default function HomeroomPage() {
  const { user } = useAuth();
  const classId = user?.homeroom_class_id ?? "";

  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [grades, setGrades] = useState<Grade[]>([]);
  const [years, setYears] = useState<AcademicYear[]>([]);
  const [homeroomClass, setHomeroomClass] = useState<ClassRow | null>(null);

  const [mode, setMode] = useState<"detail" | "summary">("detail");
  const [yearId, setYearId] = useState("");
  const [gradeId, setGradeId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [semesterId, setSemesterId] = useState("");

  const [detail, setDetail] = useState<GradebookResponse | null>(null);
  const [summary, setSummary] = useState<ClassSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const busy = useApiBusy();
  const [loading, setLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [mapTarget, setMapTarget] = useState<GradebookColumn | null>(null);
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportFilename, setExportFilename] = useState("");
  const [exportFormat, setExportFormat] = useState<"pdf" | "xlsx" | "csv">("xlsx");
  const [showImportModal, setShowImportModal] = useState(false);

  // Quyền ghi điểm cho môn hiện tại (chỉ được sửa môn phụ trách của mình, còn lại chỉ xem)
  const canWriteThisSubject = useMemo(() => {
    if (!user) return false;
    if (user.role === "ADMIN" || user.role === "HOMEROOM_TEACHER_PRIMARY") return true;
    if (user.role === "SUBJECT_TEACHER") {
      return subjectId === user.subject_id;
    }
    return false;
  }, [user, subjectId]);

  // Tải chi tiết lớp chủ nhiệm
  useEffect(() => {
    if (!classId) return;
    api.get<ClassRow>(`/classes/${classId}`)
      .then((c) => {
        setHomeroomClass(c);
        setYearId(c.academic_year_id);
        setGradeId(c.grade_id);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Lỗi tải chi tiết lớp chủ nhiệm"));
  }, [classId]);

  // Tải dữ liệu tham chiếu
  useEffect(() => {
    Promise.all([
      api.get<Subject[]>("/subjects?limit=200"),
      api.get<Semester[]>("/semesters?limit=50"),
      api.get<Grade[]>("/grades?limit=200"),
      api.get<AcademicYear[]>("/academic-years?limit=200"),
    ])
      .then(([sub, sem, g, y]) => {
        setSubjects(sub); setSemesters(sem); setGrades(g); setYears(y);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Lỗi tải dữ liệu tham chiếu"));
  }, []);

  // Tải bảng điểm/tổng hợp
  useEffect(() => {
    const ready = mode === "detail" ? classId && subjectId && semesterId : classId && semesterId;
    if (!ready) return;
    let active = true;
    Promise.resolve().then(() => {
      if (active) setLoading(true);
    });
    const url = mode === "detail"
      ? `/scores/gradebook?class_id=${classId}&subject_id=${subjectId}&semester_id=${semesterId}`
      : `/scores/class-summary?class_id=${classId}&semester_id=${semesterId}`;
    api.get<GradebookResponse | ClassSummaryResponse>(url)
      .then((d) => {
        if (!active) return;
        setError(null);
        if (mode === "detail") setDetail(d as GradebookResponse);
        else setSummary(d as ClassSummaryResponse);
      })
      .catch((e) => active && setError(e instanceof ApiError ? e.message : "Lỗi tải bảng điểm"))
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [mode, classId, subjectId, semesterId, reloadKey]);

  const gradeMap = useMemo(() => new Map(grades.map((g) => [g.id, g])), [grades]);
  const subjectMap = useMemo(() => new Map(subjects.map((s) => [s.id, s])), [subjects]);
  const semMap = useMemo(() => new Map(semesters.map((s) => [s.id, s])), [semesters]);

  const semestersOfYear = useMemo(
    () => semesters.filter((s) => s.academic_year_id === yearId).sort((a, b) => a.number - b.number),
    [semesters, yearId]);

  useEffect(() => {
    if (yearId && semestersOfYear.length > 0 && !semesterId) {
      setSemesterId(semestersOfYear[0].id);
    }
  }, [yearId, semestersOfYear, semesterId]);

  const selectedLevel = useMemo(() => {
    const g = gradeId ? gradeMap.get(gradeId) : undefined;
    return g?.school_level ?? "";
  }, [gradeId, gradeMap]);

  const subjectsOfLevel = useMemo(
    () => subjects.filter((s) => !selectedLevel || !s.applicable_level || s.applicable_level === selectedLevel || s.applicable_level === "ALL"),
    [subjects, selectedLevel]);

  useEffect(() => {
    if (subjectsOfLevel.length > 0 && !subjectId) {
      setSubjectId(subjectsOfLevel[0].id);
    }
  }, [subjectsOfLevel, subjectId]);

  const yearName = years.find((y) => y.id === yearId)?.name ?? "";
  const semName = semMap.get(semesterId)?.name ?? "";
  const subjName = subjectMap.get(subjectId)?.name ?? "";
  const title = mode === "detail"
    ? `BẢNG ĐIỂM CHI TIẾT - MÔN ${subjName.toUpperCase()} - HỌC KỲ ${semName} - NĂM HỌC ${yearName}`
    : `BẢNG ĐIỂM TỔNG HỢP - HỌC KỲ ${semName} - NĂM HỌC ${yearName}`;
  const subtitle = homeroomClass ? `Khối ${gradeMap.get(gradeId)?.grade_number ?? ""} - Lớp ${homeroomClass.name}` : "";

  const saveCell = async (studentId: string, col: GradebookColumn, cell: GradeCell | undefined, val: number | null) => {
    setError(null);
    try {
      if (val === null) {
        if (cell?.id) await api.del(`/scores/${cell.id}`);
        else return;
      } else if (cell?.id) {
        await api.patch(`/scores/${cell.id}`, { value: val });
      } else {
        await api.post("/scores", {
          student_id: studentId, subject_id: subjectId, class_id: classId, semester_id: semesterId,
          score_category: col.category, column_index: col.index, value: val,
        });
      }
      setReloadKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Lưu điểm thất bại");
    }
  };

  const previewExam = async (examPaperId: string) => {
    setError(null);
    try {
      const blob = await api.blob(`/exam-papers/${examPaperId}/file`);
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không mở được file đề");
    }
  };

  const removeMapping = async (ref: ExamRef) => {
    if (!confirm(`Hủy liên kết đề "${ref.title}" khỏi cột này?`)) return;
    setError(null);
    try {
      await api.del(`/scores/mappings/${ref.mapping_id}`);
      setReloadKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Hủy liên kết thất bại");
    }
  };

  const reloadGradebook = () => setReloadKey((k) => k + 1);

  const saveEval = async (studentId: string, patch: { comment?: string | null; result?: string | null }) => {
    setError(null);
    try {
      await api.put("/scores/subject-eval", {
        student_id: studentId, subject_id: subjectId, class_id: classId, semester_id: semesterId, ...patch,
      });
      setReloadKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Lưu đánh giá thất bại");
    }
  };

  const saveReport = async (
    studentId: string,
    patch: { conduct?: string | null; general_comment?: string | null; absent_days?: number | null }
  ) => {
    setError(null);
    try {
      await api.put("/scores/term-report", {
        student_id: studentId, class_id: classId, semester_id: semesterId, ...patch,
      });
      setReloadKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Lưu hạnh kiểm/đánh giá/ngày nghỉ thất bại");
    }
  };

  if (!classId) {
    return (
      <div className="p-8">
        <div className="max-w-md mx-auto text-center py-16 text-slate-500 dark:text-slate-400">
          Bạn không được phân công chủ nhiệm lớp nào.
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-[1500px] mx-auto w-full space-y-5 print-area">
      <div className="print-only text-center mb-4">
        {SCHOOL_HEADER.map((l) => <div key={l} className="text-sm">{l}</div>)}
        <div className="font-bold uppercase mt-2">{title}</div>
        <div className="font-bold">{subtitle}</div>
      </div>

      <div className="no-print">
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          Quản lý lớp chủ nhiệm
        </h2>
        <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
          Lớp: <b>{homeroomClass?.name ?? "..."}</b> (Niên khóa: {yearName})
        </p>
      </div>

      <div className="no-print bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 flex flex-wrap items-end gap-3 shadow-sm">
        <div className="flex rounded-lg overflow-hidden border border-slate-300 dark:border-slate-700">
          {(["detail", "summary"] as const).map((m) => (
            <button key={m} onClick={() => setMode(m)}
              className={`px-3 py-2 text-sm font-medium ${mode === m ? "bg-brand-600 text-white" : "bg-transparent text-slate-600 dark:text-slate-300"}`}>
              {m === "detail" ? "Chi tiết môn" : "Tổng hợp lớp"}
            </button>
          ))}
        </div>
        
        {mode === "detail" && (
          <SearchableSelect label="Môn" value={subjectId} onChange={setSubjectId} className="min-w-[160px]"
            options={subjectsOfLevel.map((s) => ({ value: s.id, label: s.name }))} />
        )}
        <SearchableSelect label="Học kỳ" value={semesterId} onChange={setSemesterId} className="min-w-[120px]"
          options={semestersOfYear.map((s) => ({ value: s.id, label: s.name }))} />

        <div className="ml-auto flex items-center gap-2">
          {busy && <Loader2 className="w-4 h-4 text-brand-500 animate-spin" />}
          
          {mode === "detail" && canWriteThisSubject && detail && (
            <button
              type="button"
              onClick={() => setShowImportModal(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-355 dark:border-slate-700 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-sm cursor-pointer"
            >
              <Upload className="w-4 h-4 text-brand-550 dark:text-brand-400" />
              <span>Nhập Excel</span>
            </button>
          )}

          <button 
            type="button"
            onClick={() => {
              const defaultName = getDefaultFilename("xlsx");
              setExportFormat("xlsx");
              setExportFilename(defaultName);
              setShowExportModal(true);
            }}
            disabled={mode === "detail" ? !detail : !summary}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            <FileDown className="w-4 h-4" />
            <span>Xuất báo cáo</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="no-print p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
          {error}
        </div>
      )}

      {(() => {
        const current = mode === "detail" ? detail : summary;
        const ready = mode === "detail" ? !!(classId && subjectId && semesterId) : !!(classId && semesterId);
        if (ready && loading && !current) {
          return (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm">
              <LoadingState message="Đang tải bảng điểm…" />
            </div>
          );
        }
        return (
          <div className="relative">
            {ready && loading && current && <LoadingOverlay message="Đang cập nhật bảng điểm…" />}
            {mode === "detail" ? renderDetail() : renderSummary()}
          </div>
        );
      })()}

      {mapTarget && (
        <MapExamModal
          column={mapTarget}
          subjectId={subjectId}
          semesterId={semesterId}
          classId={classId}
          gradeId={gradeId}
          existing={detail?.mappings[mapTarget.key]}
          onClose={() => setMapTarget(null)}
          onChanged={reloadGradebook}
        />
      )}

      {showExportModal && (
        <ExportReportModal
          filename={exportFilename}
          format={exportFormat}
          onChangeFilename={setExportFilename}
          onChangeFormat={(f) => {
            setExportFormat(f);
            setExportFilename((prev) => {
              const base = prev.replace(/\.(pdf|xlsx|csv)$/i, "");
              const ext = f === "pdf" ? ".pdf" : (f === "xlsx" ? ".xlsx" : ".csv");
              return base + ext;
            });
          }}
          onConfirm={() => {
            handleExport(exportFormat, exportFilename);
            setShowExportModal(false);
          }}
          onClose={() => setShowExportModal(false)}
        />
      )}

      {showImportModal && (
        <ImportScoreModal
          classId={classId}
          subjectId={subjectId}
          semesterId={semesterId}
          className={homeroomClass?.name ?? ""}
          subjectName={subjName || ""}
          onClose={() => setShowImportModal(false)}
          onSuccess={reloadGradebook}
        />
      )}
    </div>
  );

  function renderDetail() {
    if (!detail) return <EmptyState mode={mode} />;
    if (detail.rows.length === 0) return <EmptyHint text="Lớp chưa có học sinh được ghi danh." />;
    if (detail.assessment_type === "REMARK") return renderRemarkDetail();
    const groups = buildGroups(detail.columns);
    return (
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto overflow-y-auto max-h-[70vh]">
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-0 z-10 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200">
              <tr>
                <Th rowSpan={2}>STT</Th>
                <Th rowSpan={2} className="text-left min-w-[200px]">Họ và tên</Th>
                {groups.map((g) => <Th key={g.category} colSpan={g.cols.length}>{g.label}</Th>)}
                <Th rowSpan={2}>ĐTB mhk</Th>
                <Th rowSpan={2} className="min-w-[200px]">Đánh giá học tập</Th>
                <Th rowSpan={2}>HKI</Th>
                <Th rowSpan={2}>HKII</Th>
                <Th rowSpan={2}>CN</Th>
              </tr>
              <tr>{detail.columns.map((c) => (
                <Th key={c.key}>
                  <div className="flex flex-col items-center gap-0.5">
                    <span>{c.label}</span>
                    {c.mappable && (
                      <ColMapControls
                        col={c} ref_={detail.mappings[c.key]}
                        canMap={!!user && canMapCategory(user.role, c.category)}
                        onMap={() => setMapTarget(c)}
                        onPreview={previewExam}
                        onRemove={removeMapping}
                      />
                    )}
                  </div>
                </Th>
              ))}</tr>
            </thead>
            <tbody>
              {detail.rows.map((r, i) => (
                <tr key={r.student_id} className="border-t border-slate-100 dark:border-slate-800">
                  <Td center>{i + 1}</Td>
                  <Td className="text-left font-medium">{r.full_name}</Td>
                  {detail.columns.map((c) => (
                    <Td center key={c.key} className="p-0">
                      {canWriteThisSubject ? (
                        <CellInput key={`${r.student_id}:${c.key}:${r.cells[c.key]?.id ?? ""}:${r.cells[c.key]?.value ?? ""}`}
                          cell={r.cells[c.key]} onSave={(v) => saveCell(r.student_id, c, r.cells[c.key], v)} />
                      ) : fmt(r.cells[c.key]?.value)}
                    </Td>
                  ))}
                  <Td center className="font-semibold text-brand-700 dark:text-brand-400">{fmt(r.dtb_hk)}</Td>
                  <Td className="p-0 min-w-[200px]">
                    {canWriteThisSubject ? (
                      <TextInput key={`ev:${r.student_id}:${r.evaluation ?? ""}`} value={r.evaluation}
                        placeholder="Nhận xét…" onSave={(v) => saveEval(r.student_id, { comment: v })} />
                    ) : (r.evaluation ?? "")}
                  </Td>
                  <Td center>{fmt(r.dtb_hk1)}</Td>
                  <Td center>{fmt(r.dtb_hk2)}</Td>
                  <Td center className="font-semibold">{fmt(r.dtb_cn)}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <StatsFooter total={detail.total_students} stats={detail.stats} sem={semName} />
      </div>
    );
  }

  function renderRemarkDetail() {
    if (!detail) return null;
    return (
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto overflow-y-auto max-h-[70vh]">
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-0 z-10 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200">
              <tr>
                <Th>STT</Th>
                <Th className="text-left min-w-[200px]">Họ và tên</Th>
                <Th className="min-w-[140px]">Kết quả</Th>
                <Th className="text-left min-w-[260px]">Đánh giá học tập</Th>
              </tr>
            </thead>
            <tbody>
              {detail.rows.map((r, i) => (
                <tr key={r.student_id} className="border-t border-slate-100 dark:border-slate-800">
                  <Td center>{i + 1}</Td>
                  <Td className="text-left font-medium">{r.full_name}</Td>
                  <Td center className="p-0">
                    {canWriteThisSubject ? (
                      <SelectInput key={`res:${r.student_id}:${r.result ?? ""}`} value={r.result}
                        options={PASS_FAIL_OPTIONS} onSave={(v) => saveEval(r.student_id, { result: v || null })} />
                    ) : (r.result ? PASS_FAIL_LABELS[r.result] : "")}
                  </Td>
                  <Td className="p-0">
                    {canWriteThisSubject ? (
                      <TextInput key={`ev:${r.student_id}:${r.evaluation ?? ""}`} value={r.evaluation}
                        placeholder="Nhận xét…" onSave={(v) => saveEval(r.student_id, { comment: v })} />
                    ) : (r.evaluation ?? "")}
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 px-4 py-3 text-xs text-slate-600 dark:text-slate-300">
          Môn đánh giá bằng nhận xét (Đạt/Chưa đạt) — không tính vào điểm trung bình.
        </div>
      </div>
    );
  }

  function renderSummary() {
    if (!summary) return <EmptyState mode={mode} />;
    if (summary.rows.length === 0) return <EmptyHint text="Lớp chưa có học sinh được ghi danh." />;
    return (
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto overflow-y-auto max-h-[70vh]">
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-0 z-10 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200">
              <tr>
                <Th>STT</Th>
                <Th className="text-left min-w-[200px]">Họ và tên</Th>
                {summary.subjects.map((s) => (
                  <Th key={s.id} className="min-w-[64px]" title={s.assessment_type === "REMARK" ? `${s.name} (nhận xét)` : s.name}>
                    {s.code}{s.assessment_type === "REMARK" ? "*" : ""}
                  </Th>
                ))}
                <Th>ĐTB</Th>
                <Th>Học lực</Th>
                <Th className="min-w-[120px]">Hạnh kiểm</Th>
                <Th className="min-w-[80px]">Vắng (ngày)</Th>
                <Th className="text-left min-w-[220px]">Đánh giá chung</Th>
              </tr>
            </thead>
            <tbody>
              {summary.rows.map((r, i) => (
                <tr key={r.student_id} className="border-t border-slate-100 dark:border-slate-800">
                  <Td center>{i + 1}</Td>
                  <Td className="text-left font-medium">{r.full_name}</Td>
                  {summary.subjects.map((s) => (
                    <Td center key={s.id}>
                      {s.assessment_type === "REMARK"
                        ? (r.remarks[s.id] ? PASS_FAIL_LABELS[r.remarks[s.id] as PassFail] ?? r.remarks[s.id] : "")
                        : fmt(r.averages[s.id])}
                    </Td>
                  ))}
                  <Td center className="font-semibold text-brand-700 dark:text-brand-400">{fmt(r.overall)}</Td>
                  <Td center>{r.hoc_luc ?? ""}</Td>
                  <Td center className="p-0">
                    {summary.can_edit_report ? (
                      <SelectInput key={`hk:${r.student_id}:${r.conduct ?? ""}`} value={r.conduct}
                        options={CONDUCT_OPTIONS} onSave={(v) => saveReport(r.student_id, { conduct: v || null })} />
                    ) : (r.conduct ? CONDUCT_LABELS[r.conduct] : "")}
                  </Td>
                  <Td center className="p-0">
                    {summary.can_edit_report ? (
                      <NumberInput key={`ab:${r.student_id}:${r.absent_days ?? 0}`} value={r.absent_days ?? 0}
                        onSave={(v) => saveReport(r.student_id, { absent_days: v })} />
                    ) : (r.absent_days ?? 0)}
                  </Td>
                  <Td className="p-0">
                    {summary.can_edit_report ? (
                      <TextInput key={`gc:${r.student_id}:${r.general_comment ?? ""}`} value={r.general_comment}
                        placeholder="Đánh giá chung…" onSave={(v) => saveReport(r.student_id, { general_comment: v })} />
                    ) : (r.general_comment ?? "")}
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <StatsFooter total={summary.total_students} stats={summary.stats} sem={semName} />
      </div>
    );
  }

  function getDefaultFilename(format: "pdf" | "xlsx" | "csv") {
    const className = homeroomClass?.name || "";
    const subjectClean = mode === "detail" && subjName ? ` - Môn ${subjName}` : "";
    
    let semClean = semName || "";
    if (semClean.includes("1") || semClean.includes("I")) semClean = "HK1";
    else if (semClean.includes("2") || semClean.includes("II")) semClean = "HK2";
    
    const yearClean = yearName ? yearName.replace(/\//g, "-") : "";
    const typeLabel = mode === "detail" ? "Bảng điểm chi tiết" : "Bảng điểm tổng hợp";
    const extension = format === "pdf" ? ".pdf" : (format === "xlsx" ? ".xlsx" : ".csv");
    
    return `${typeLabel} - Lớp ${className}${subjectClean} - ${semClean} - Năm học ${yearClean}${extension}`;
  }

  function handleExport(format: "pdf" | "xlsx" | "csv", filename: string) {
    if (format === "pdf") {
      const originalTitle = document.title;
      const printTitle = filename.replace(/\.pdf$/i, "");
      document.title = printTitle;
      window.print();
      setTimeout(() => {
        document.title = originalTitle;
      }, 100);
    } else if (format === "csv") {
      if (mode === "detail" && detail) {
        const header = ["STT", "Họ tên", "Mã HS", ...detail.columns.map((c) => c.label), "ĐTB mhk", "HKI", "HKII", "CN"];
        const rows: Cell[][] = detail.rows.map((r, i) => [
          i + 1, r.full_name, r.student_code,
          ...detail.columns.map((c) => r.cells[c.key]?.value ?? ""),
          r.dtb_hk ?? "", r.dtb_hk1 ?? "", r.dtb_hk2 ?? "", r.dtb_cn ?? "",
        ]);
        exportCSV(filename, [header, ...rows]);
      } else if (summary) {
        const header = ["STT", "Họ tên", "Mã HS", ...summary.subjects.map((s) => s.name), "ĐTB", "Học lực", "Hạnh kiểm", "Vắng (ngày)", "Đánh giá chung"];
        const rows: Cell[][] = summary.rows.map((r, i) => [
          i + 1, r.full_name, r.student_code,
          ...summary.subjects.map((s) => s.assessment_type === "REMARK" 
            ? (r.remarks[s.id] ? PASS_FAIL_LABELS[r.remarks[s.id] as PassFail] ?? r.remarks[s.id] : "")
            : r.averages[s.id] ?? ""
          ), 
          r.overall ?? "", r.hoc_luc ?? "", r.conduct ? CONDUCT_LABELS[r.conduct] : "", r.absent_days ?? 0, r.general_comment ?? "",
        ]);
        exportCSV(filename, [header, ...rows]);
      }
    } else if (format === "xlsx") {
      const admin = [...SCHOOL_HEADER, title, subtitle];
      if (mode === "detail" && detail) {
        const groups = buildGroups(detail.columns);
        const nCols = detail.columns.length;
        const width = 2 + nCols + 5; // STT, HoTen, [cols], ĐTB, NhậnXét, HKI, HKII, CN
        const aoa: Cell[][] = admin.map((l) => [l, ...Array(width - 1).fill(null)]);
        aoa.push(Array(width).fill(null));
        const top = aoa.length;
        const row1: Cell[] = ["STT", "Họ và tên"];
        groups.forEach((g) => { row1.push(g.label); for (let k = 1; k < g.cols.length; k++) row1.push(null); });
        row1.push("ĐTB mhk", "Nhận xét", "HKI", "HKII", "CN");
        aoa.push(row1);
        aoa.push([null, null, ...detail.columns.map((c) => c.label), null, null, null, null, null]);
        detail.rows.forEach((r, i) => aoa.push([
          i + 1, r.full_name, ...detail.columns.map((c) => r.cells[c.key]?.value ?? null),
          r.dtb_hk, "", r.dtb_hk1, r.dtb_hk2, r.dtb_cn,
        ]));
        const merges = [
          ...admin.map((_, i) => ({ s: { r: i, c: 0 }, e: { r: i, c: width - 1 } })),
          { s: { r: top, c: 0 }, e: { r: top + 1, c: 0 } }, { s: { r: top, c: 1 }, e: { r: top + 1, c: 1 } },
        ];
        let col = 2;
        groups.forEach((g) => { merges.push({ s: { r: top, c: col }, e: { r: top, c: col + g.cols.length - 1 } }); col += g.cols.length; });
        for (let k = 0; k < 5; k++) merges.push({ s: { r: top, c: col + k }, e: { r: top + 1, c: col + k } });
        exportXLSX(filename, aoa, merges);
      } else if (summary) {
        const width = 7 + summary.subjects.length;
        const aoa: Cell[][] = admin.map((l) => [l, ...Array(width - 1).fill(null)]);
        aoa.push(Array(width).fill(null));
        aoa.push(["STT", "Họ và tên", ...summary.subjects.map((s) => s.name), "ĐTB", "Học lực", "Hạnh kiểm", "Vắng (ngày)", "Đánh giá chung"]);
        summary.rows.forEach((r, i) => aoa.push([
          i + 1, r.full_name,
          ...summary.subjects.map((s) => s.assessment_type === "REMARK" 
            ? (r.remarks[s.id] ? PASS_FAIL_LABELS[r.remarks[s.id] as PassFail] ?? r.remarks[s.id] : "")
            : r.averages[s.id] ?? null
          ),
          r.overall, r.hoc_luc ?? "", r.conduct ? CONDUCT_LABELS[r.conduct] : "", r.absent_days ?? 0, r.general_comment ?? "",
        ]));
        const merges = admin.map((_, i) => ({ s: { r: i, c: 0 }, e: { r: i, c: width - 1 } }));
        exportXLSX(filename, aoa, merges);
      }
    }
  }
}

function Th({ children, rowSpan, colSpan, className = "", title }: {
  children: React.ReactNode; rowSpan?: number; colSpan?: number; className?: string; title?: string;
}) {
  return (
    <th rowSpan={rowSpan} colSpan={colSpan} title={title}
      className={`px-4 py-3 text-xs font-bold text-center border border-slate-250 dark:border-slate-700 ${className}`}>
      {children}
    </th>
  );
}

function Td({ children, center, className = "" }: {
  children: React.ReactNode; center?: boolean; className?: string;
}) {
  return (
    <td className={`px-4 py-2 border border-slate-100 dark:border-slate-800 ${center ? "text-center" : "text-left"} ${className}`}>
      {children}
    </td>
  );
}

function ColMapControls({ col, ref_, canMap, onMap, onPreview, onRemove }: {
  col: GradebookColumn; ref_?: ExamRef; canMap: boolean; onMap: () => void; onPreview: (id: string) => void; onRemove: (ref: ExamRef) => void;
}) {
  if (ref_) {
    return (
      <div className="flex items-center gap-1.5 mt-1 no-print">
        <button type="button" onClick={() => onPreview(ref_.exam_paper_id)}
          className="text-brand-600 hover:text-brand-500 font-medium text-[11px] underline truncate max-w-[80px]" title={ref_.title}>
          {ref_.title}
        </button>
        {canMap && (
          <button type="button" onClick={() => onRemove(ref_)} className="text-rose-500 hover:text-rose-400 p-0.5">
            <Unlink className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    );
  }
  if (canMap) {
    return (
      <button type="button" onClick={onMap}
        className="flex items-center gap-1 mt-1 text-brand-600 hover:text-brand-500 font-semibold text-[11px] no-print">
        <Link2 className="w-3 h-3" />
        <span>Gắn đề</span>
      </button>
    );
  }
  return null;
}

function CellInput({ cell, onSave }: { cell: GradeCell | undefined; onSave: (v: number | null) => void }) {
  const [v, setV] = useState(cell?.value != null ? String(cell.value) : "");
  const original = cell?.value != null ? String(cell.value) : "";
  const commit = () => {
    if (v === original) return;
    if (v.trim() === "") { onSave(null); return; }
    const num = parseFloat(v);
    if (isNaN(num) || num < 0 || num > 10) { setV(original); return; }
    onSave(num);
  };
  return (
    <input type="number" min={0} max={10} step={0.1} value={v}
      onChange={(e) => setV(e.target.value)} onBlur={commit}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
      className="w-14 text-center bg-transparent py-1.5 focus:bg-brand-55 dark:focus:bg-brand-500/10 focus:outline-none rounded" />
  );
}

function TextInput({ value, placeholder, onSave }: {
  value: string | null; placeholder?: string; onSave: (v: string) => void;
}) {
  const [v, setV] = useState(value ?? "");
  const original = value ?? "";
  return (
    <input type="text" value={v} placeholder={placeholder}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => { if (v !== original) onSave(v.trim()); }}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
      className="w-full min-w-[180px] px-2 py-1.5 bg-transparent focus:bg-brand-50 dark:focus:bg-brand-500/10 focus:outline-none rounded text-sm" />
  );
}

function SelectInput({ value, options, onSave }: {
  value: string | null; options: { value: string; label: string }[]; onSave: (v: string) => void;
}) {
  return (
    <select value={value ?? ""} onChange={(e) => onSave(e.target.value)}
      className="w-full px-2 py-1.5 bg-transparent focus:bg-brand-50 dark:focus:bg-brand-500/10 focus:outline-none rounded text-sm text-center">
      <option value="">—</option>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

function NumberInput({ value, onSave }: {
  value: number | null; onSave: (v: number) => void;
}) {
  const [v, setV] = useState(value == null ? "" : String(value));
  const original = value == null ? "" : String(value);
  return (
    <input type="number" min="0" value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => {
        const parsed = parseInt(v, 10);
        const val = isNaN(parsed) ? 0 : parsed;
        if (String(val) !== original) onSave(val);
      }}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
      className="w-16 px-1 py-1.5 bg-transparent focus:bg-brand-50 dark:focus:bg-brand-500/10 focus:outline-none rounded text-sm text-center" />
  );
}

function EmptyState({ mode }: { mode: string }) {
  return (
    <div className="no-print bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-12 text-center text-slate-500 dark:text-slate-400">
      Chọn {mode === "detail" ? "môn và học kỳ" : "học kỳ"} để xem bảng điểm.
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 text-center text-sm text-slate-500 dark:text-slate-400">
      {text}
    </div>
  );
}

function StatsFooter({ total, stats, sem }: { total: number; stats: { label: string; count: number; ratio: number }[]; sem: string }) {
  return (
    <div className="border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 px-4 py-3 text-xs text-slate-600 dark:text-slate-300 flex flex-wrap items-center gap-x-4 gap-y-1">
      <span className="font-bold uppercase">Thống kê {sem || ""} · Sĩ số {total}</span>
      {stats.map((s) => (
        <span key={s.label}>{s.label}: <b>{s.count}</b> ({s.ratio}%)</span>
      ))}
    </div>
  );
}

interface ExportModalProps {
  filename: string;
  format: "pdf" | "xlsx" | "csv";
  onChangeFilename: (v: string) => void;
  onChangeFormat: (f: "pdf" | "xlsx" | "csv") => void;
  onConfirm: () => void;
  onClose: () => void;
}

function ExportReportModal({ filename, format, onChangeFilename, onChangeFormat, onConfirm, onClose }: ExportModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 no-print" onClick={onClose}>
      <div 
        className="w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <h3 className="font-bold text-slate-900 dark:text-white">Xuất báo cáo bảng điểm</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>
        
        <div className="p-5 space-y-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Định dạng file</label>
            <div className="grid grid-cols-3 gap-2">
              {(["xlsx", "pdf", "csv"] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => onChangeFormat(f)}
                  className={`px-3 py-2 rounded-lg border text-xs font-semibold uppercase transition-all cursor-pointer ${
                    format === f
                      ? "border-brand-600 bg-brand-50 text-brand-700 dark:border-brand-500 dark:bg-brand-500/10 dark:text-brand-400"
                      : "border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  }`}
                >
                  {f === "xlsx" ? "Excel (.xlsx)" : f === "pdf" ? "PDF (.pdf)" : "CSV (.csv)"}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Tên file lưu trữ</label>
            <input
              type="text"
              value={filename}
              onChange={(e) => onChangeFilename(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 text-sm outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
            />
          </div>
        </div>
        
        <div className="flex justify-end gap-2 px-5 py-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 rounded-b-2xl">
          <button onClick={onClose} className="px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-750 dark:text-slate-300 text-sm font-semibold hover:bg-slate-100 dark:hover:bg-slate-800">
            Hủy
          </button>
          <button onClick={onConfirm} className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-semibold hover:bg-brand-550 shadow-sm">
            Xuất file
          </button>
        </div>
      </div>
    </div>
  );
}
