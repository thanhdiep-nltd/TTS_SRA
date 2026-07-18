"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, FilePlus2, Sparkles, Trash2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import SearchableSelect from "@/components/SearchableSelect";
import ConfirmModal from "@/components/ConfirmModal";
import MatrixEditor from "@/components/exam-builder/MatrixEditor";
import ExamAssemblyPanel from "@/components/exam-builder/ExamAssemblyPanel";
import BloomCountGrid from "@/components/exam-builder/BloomCountGrid";
import { useCurriculumTree } from "@/lib/useCurriculumUnits";
import {
  DEFAULT_POINTS_EACH,
  EXAM_FORMAT_LABELS,
  QUESTION_BANK_ROLES,
  QUESTION_REVIEW_ROLES,
  SCORE_CATEGORY_LABELS,
  type AcademicYear,
  type BlueprintCell,
  type BlueprintCreate,
  type BlueprintDraft,
  type BlueprintRead,
  type ExamFormat,
  type Grade,
  type RecommendBlueprintRequest,
  type ScoreCategory,
  type Semester,
  type Subject,
} from "@/lib/types";

type Step = 1 | 2 | 3;
type MatrixMode = "AI" | "MANUAL";
const EXAM_CATEGORIES: ScoreCategory[] = ["MIDTERM", "FINAL"];
const EXAM_FORMATS: ExamFormat[] = ["MCQ_ONLY", "ESSAY_ONLY", "MIXED"];

export default function ExamBuilderPage() {
  const { user } = useAuth();
  const canManage = !!user && QUESTION_BANK_ROLES.includes(user.role);
  const canReview = !!user && QUESTION_REVIEW_ROLES.includes(user.role);
  const isAdmin = user?.role === "ADMIN";

  const [step, setStep] = useState<Step>(1);
  const [error, setError] = useState<string | null>(null);

  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [grades, setGrades] = useState<Grade[]>([]);
  const [years, setYears] = useState<AcademicYear[]>([]);
  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [existingBlueprints, setExistingBlueprints] = useState<BlueprintRead[]>([]);

  const [subjectId, setSubjectId] = useState("");
  const [gradeId, setGradeId] = useState("");
  const [yearId, setYearId] = useState("");
  const [semesterId, setSemesterId] = useState("");
  const [scoreCategory, setScoreCategory] = useState<ScoreCategory>("MIDTERM");
  const [selectedUnitIds, setSelectedUnitIds] = useState<string[]>([]);
  const [totalPoints, setTotalPoints] = useState("10");
  const [loadingRecommend, setLoadingRecommend] = useState(false);
  const [examFormat, setExamFormat] = useState<ExamFormat>("MIXED");
  const [totalQuestions, setTotalQuestions] = useState("20");
  const [mixRatioPct, setMixRatioPct] = useState("70");
  const [matrixMode, setMatrixMode] = useState<MatrixMode>("AI");
  // Luồng thủ công: số câu theo (unit, loại câu, Bloom) — khóa "unitId|qtype|bloom" -> số câu.
  const [manualCounts, setManualCounts] = useState<Record<string, number>>({});

  const [activeBlueprint, setActiveBlueprint] = useState<BlueprintRead | null>(null);
  // Ma trận CHƯA LƯU (tạo mới, đang ở bước ráp đề) — chỉ thật sự ghi DB khi ráp đề lần đầu
  // thành công (xem ExamAssemblyPanel.onBlueprintSaved), tránh để lại ma trận rác chưa ai dùng.
  const [pendingBlueprint, setPendingBlueprint] = useState<BlueprintCreate | null>(null);
  const [draftCells, setDraftCells] = useState<BlueprintCell[]>([]);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftTargetDifficulty, setDraftTargetDifficulty] = useState<number | null>(null);
  const [draftRationale, setDraftRationale] = useState<string[]>([]);
  const [deletingBlueprintId, setDeletingBlueprintId] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<Subject[]>("/subjects?limit=200"),
      api.get<Grade[]>("/grades?limit=200"),
      api.get<AcademicYear[]>("/academic-years?limit=200"),
      api.get<Semester[]>("/semesters?limit=50"),
    ])
      .then(([sub, g, y, sem]) => {
        setSubjects(sub);
        setGrades(g);
        setYears(y);
        setSemesters(sem);
        setYearId((y.find((yr) => yr.is_current) ?? y[0])?.id ?? "");
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Lỗi tải dữ liệu tham chiếu"));
  }, []);

  // GV bộ môn/Trưởng bộ môn khóa về môn phụ trách — chỉ ADMIN được chọn môn khác.
  useEffect(() => {
    if (!isAdmin && user?.subject_id) setSubjectId(user.subject_id);
  }, [isAdmin, user?.subject_id]);

  const loadBlueprints = () => {
    if (!subjectId) {
      setExistingBlueprints([]);
      return;
    }
    api
      .get<BlueprintRead[]>(`/exam-blueprints?subject_id=${subjectId}`)
      .then(setExistingBlueprints)
      .catch(() => setExistingBlueprints([]));
  };

  useEffect(loadBlueprints, [subjectId]);

  const semestersOfYear = useMemo(
    () => semesters.filter((s) => s.academic_year_id === yearId).sort((a, b) => a.number - b.number),
    [semesters, yearId]
  );
  const selectedGrade = useMemo(() => grades.find((g) => g.id === gradeId) ?? null, [grades, gradeId]);
  const gradeNumber = selectedGrade?.grade_number ?? null;
  const selectedSemesterNumber = useMemo(
    () => semesters.find((s) => s.id === semesterId)?.number ?? null,
    [semesters, semesterId]
  );

  // Cây chương/bài học ĐÚNG môn+khối (server-side, is_active). Lọc CHƯƠNG theo học kỳ đã chọn;
  // semester_number=null (SGK không tách tập, dạy cả năm — vd KHTN) luôn hiện bất kể học kỳ nào.
  // Bài học kế thừa semester_number của chương cha nên lọc cùng công thức là đủ.
  const tree = useCurriculumTree(subjectId, gradeNumber ? String(gradeNumber) : "");
  const scopedChapters = useMemo(
    () => tree.chapters.filter((c) => c.semester_number === null || c.semester_number === selectedSemesterNumber),
    [tree.chapters, selectedSemesterNumber]
  );
  const hiddenByOtherSemester = tree.chapters.length - scopedChapters.length;

  // Danh sách phẳng (chương + bài học đã lọc) cho MatrixEditor chọn unit ở từng ô ma trận.
  const unitOptions = useMemo(() => {
    const opts: { value: string; label: string }[] = [];
    for (const c of scopedChapters) {
      const lessons = tree.lessonsByChapter.get(c.id) ?? [];
      if (lessons.length === 0) opts.push({ value: c.id, label: c.name });
      else for (const l of lessons) opts.push({ value: l.id, label: `${c.name} · ${l.name}` });
    }
    return opts;
  }, [scopedChapters, tree.lessonsByChapter]);

  const [expandedChapters, setExpandedChapters] = useState<Set<string>>(new Set());
  const toggleExpanded = (id: string) => {
    setExpandedChapters((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  useEffect(() => {
    setSelectedUnitIds([]);
    setManualCounts({});
  }, [subjectId, gradeId]);

  const toggleUnit = (id: string) => {
    setSelectedUnitIds((prev) => (prev.includes(id) ? prev.filter((u) => u !== id) : [...prev, id]));
  };

  const manualKey = (unitId: string, qtype: "MCQ" | "ESSAY", bloom: number) => `${unitId}|${qtype}|${bloom}`;
  const getManualCount = (unitId: string, qtype: "MCQ" | "ESSAY", bloom: number) =>
    manualCounts[manualKey(unitId, qtype, bloom)] ?? 0;
  const setManualCount = (unitId: string, qtype: "MCQ" | "ESSAY", bloom: number, value: number) => {
    const key = manualKey(unitId, qtype, bloom);
    setManualCounts((prev) => {
      if (value <= 0) {
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: value };
    });
  };
  const manualTotalEntered = useMemo(
    () => Object.values(manualCounts).reduce((sum, n) => sum + n, 0),
    [manualCounts]
  );

  const readyForScope = !!subjectId && !!gradeId && !!semesterId;

  const defaultTitle = (): string => {
    const subjName = subjects.find((s) => s.id === subjectId)?.name ?? "";
    return `Đề ${SCORE_CATEGORY_LABELS[scoreCategory]} ${subjName} - Khối ${gradeNumber ?? ""}`.trim();
  };

  const handleRecommend = async () => {
    if (!gradeId || !gradeNumber || selectedUnitIds.length === 0) return;
    setLoadingRecommend(true);
    setError(null);
    try {
      const req: RecommendBlueprintRequest = {
        subject_id: subjectId,
        grade_number: gradeNumber,
        grade_id: gradeId,
        semester_id: semesterId,
        score_category: scoreCategory,
        unit_ids: selectedUnitIds,
        total_points: Number(totalPoints) || 10,
        exam_format: examFormat,
        total_questions: Number(totalQuestions) || 20,
        ...(examFormat === "MIXED" ? { mix_mcq_ratio: (Number(mixRatioPct) || 70) / 100 } : {}),
      };
      const draft = await api.post<BlueprintDraft>("/exam-blueprints/recommend", req);
      setActiveBlueprint(null);
      setPendingBlueprint(null);
      setDraftCells(
        draft.cells.map((c) => ({
          unit_id: c.unit_id,
          bloom_level: c.bloom_level,
          question_type: c.question_type,
          num_questions: c.num_questions,
          points_each: c.points_each,
        }))
      );
      setDraftTitle(defaultTitle());
      setDraftTargetDifficulty(draft.target_difficulty);
      setDraftRationale(draft.rationale);
      setStep(2);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Gợi ý ma trận thất bại");
    } finally {
      setLoadingRecommend(false);
    }
  };

  const handleManualContinue = () => {
    const cells: BlueprintCell[] = [];
    for (const [key, count] of Object.entries(manualCounts)) {
      if (count <= 0) continue;
      const [unitId, qtype, bloomStr] = key.split("|") as [string, "MCQ" | "ESSAY", string];
      const bloom = Number(bloomStr);
      cells.push({
        unit_id: unitId,
        bloom_level: bloom,
        question_type: qtype,
        num_questions: count,
        points_each: DEFAULT_POINTS_EACH[qtype][bloom] ?? 0.5,
      });
    }
    setActiveBlueprint(null);
    setPendingBlueprint(null);
    setDraftCells(cells);
    setDraftTitle(defaultTitle());
    setDraftTargetDifficulty(null);
    setDraftRationale([]);
    setStep(2);
  };

  const handlePickExisting = (bp: BlueprintRead) => {
    setActiveBlueprint(bp);
    setPendingBlueprint(null);
    setDraftCells(bp.cells);
    setDraftTitle(bp.title);
    setDraftTargetDifficulty(bp.target_difficulty);
    setDraftRationale([]);
    setScoreCategory(bp.score_category);
    setStep(2);
  };

  const handleSaved = (bp: BlueprintRead) => {
    setActiveBlueprint(bp);
    setStep(3);
  };

  // Ma trận MỚI (blueprint=null) — MatrixEditor không lưu ngay, chỉ chuyển dữ liệu sang bước
  // ráp đề; ma trận thật sự được ghi DB khi ráp đề lần đầu thành công (handleBlueprintSaved).
  const handleContinueUnsaved = (draft: BlueprintCreate) => {
    setPendingBlueprint(draft);
    setStep(3);
  };

  const handleBlueprintSaved = (bp: BlueprintRead) => {
    setActiveBlueprint(bp);
    setPendingBlueprint(null);
    loadBlueprints();
  };

  const handleDeleteBlueprint = async () => {
    if (!deletingBlueprintId) return;
    try {
      await api.del(`/exam-blueprints/${deletingBlueprintId}`);
      setExistingBlueprints((prev) => prev.filter((b) => b.id !== deletingBlueprintId));
      if (activeBlueprint?.id === deletingBlueprintId) {
        setActiveBlueprint(null);
        setStep(1);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Xóa ma trận thất bại");
    } finally {
      setDeletingBlueprintId(null);
    }
  };

  if (!canManage) {
    return (
      <div className="p-8">
        <div className="max-w-md mx-auto text-center py-16 text-slate-500 dark:text-slate-400">
          Bạn không có quyền tạo đề thi.
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-900 dark:text-white">Tạo đề thi từ ngân hàng câu hỏi</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
          Chọn phạm vi → tinh chỉnh ma trận → ráp đề nhiều mã, gắn liền vào luồng chấm.
        </p>
      </div>

      <StepIndicator step={step} setStep={setStep} canGoStep3={!!activeBlueprint || !!pendingBlueprint} />

      {error && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
          {error}
        </div>
      )}

      {step === 1 && (
        <div className="space-y-4">
          {existingBlueprints.length > 0 && (
            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-2">Hoặc mở ma trận đã có</p>
              <div className="flex flex-wrap gap-2">
                {existingBlueprints.map((bp) => (
                  <div
                    key={bp.id}
                    className="flex items-center rounded-lg border border-slate-200 dark:border-slate-700 hover:border-brand-400 overflow-hidden"
                  >
                    <button
                      onClick={() => handlePickExisting(bp)}
                      className="px-3 py-1.5 text-sm text-slate-600 dark:text-slate-300 hover:text-brand-600"
                    >
                      {bp.title}
                      {bp.exam_format && (
                        <span className="ml-1.5 text-xs text-slate-400">({EXAM_FORMAT_LABELS[bp.exam_format]})</span>
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeletingBlueprintId(bp.id)}
                      title="Xóa ma trận"
                      className="px-2 py-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-500/10 border-l border-slate-200 dark:border-slate-700"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
            {isAdmin ? (
              <SearchableSelect
                label="Môn"
                value={subjectId}
                onChange={setSubjectId}
                options={subjects.map((s) => ({ value: s.id, label: s.name }))}
              />
            ) : (
              <div className="flex flex-col gap-1">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Môn</span>
                <span className="px-3 py-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                  {subjects.find((s) => s.id === subjectId)?.name ?? "—"}
                </span>
              </div>
            )}
            <SearchableSelect
              label="Khối"
              value={gradeId}
              onChange={setGradeId}
              options={grades.map((g) => ({ value: g.id, label: g.name }))}
            />
            <SearchableSelect
              label="Niên khóa"
              value={yearId}
              onChange={(v) => {
                setYearId(v);
                setSemesterId("");
              }}
              options={years.map((y) => ({ value: y.id, label: y.name }))}
            />
            <SearchableSelect
              label="Học kỳ"
              value={semesterId}
              onChange={setSemesterId}
              options={semestersOfYear.map((s) => ({ value: s.id, label: s.name }))}
            />
            <SearchableSelect
              label="Loại đề"
              value={scoreCategory}
              onChange={(v) => setScoreCategory(v as ScoreCategory)}
              options={EXAM_CATEGORIES.map((c) => ({ value: c, label: SCORE_CATEGORY_LABELS[c] }))}
            />
            <div>
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Tổng điểm</label>
              <input
                type="number"
                min={1}
                value={totalPoints}
                onChange={(e) => setTotalPoints(e.target.value)}
                className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
              />
            </div>
          </div>

          {readyForScope && (
            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-3">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Cấu hình đề</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-2">
                  <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Loại đề</span>
                  <div className="mt-1.5 grid grid-cols-3 gap-1.5">
                    {EXAM_FORMATS.map((f) => (
                      <button
                        key={f}
                        type="button"
                        onClick={() => setExamFormat(f)}
                        className={`px-2 py-2 rounded-lg text-xs font-semibold border ${
                          examFormat === f
                            ? "bg-brand-600 border-brand-600 text-white"
                            : "border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-brand-400"
                        }`}
                      >
                        {EXAM_FORMAT_LABELS[f]}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Tổng số câu</label>
                  <input
                    type="number"
                    min={1}
                    value={totalQuestions}
                    onChange={(e) => setTotalQuestions(e.target.value)}
                    className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
                  />
                </div>
              </div>
              {examFormat === "MIXED" && (
                <div className="max-w-xs">
                  <label className="text-xs font-medium text-slate-500 dark:text-slate-400">
                    Tỉ lệ điểm Trắc nghiệm (%) — phần còn lại là Tự luận
                  </label>
                  <input
                    type="number"
                    min={30}
                    max={90}
                    value={mixRatioPct}
                    onChange={(e) => setMixRatioPct(e.target.value)}
                    className="mt-1.5 w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-sm outline-none focus:border-brand"
                  />
                </div>
              )}
            </div>
          )}

          {readyForScope && (
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setMatrixMode("AI")}
                className={`flex-1 text-left p-4 rounded-2xl border transition ${
                  matrixMode === "AI"
                    ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10"
                    : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-brand-300"
                }`}
              >
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-accent-600" /> AI gợi ý theo năng lực trường
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  Chọn chương đã dạy — hệ tự tính số câu, mức Bloom mỗi chương theo năng lực thực tế của khối.
                </p>
              </button>
              <button
                type="button"
                onClick={() => setMatrixMode("MANUAL")}
                className={`flex-1 text-left p-4 rounded-2xl border transition ${
                  matrixMode === "MANUAL"
                    ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10"
                    : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-brand-300"
                }`}
              >
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
                  <FilePlus2 className="w-4 h-4 text-brand-600" /> Tự soạn ma trận thủ công
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  Tự nhập số câu theo từng mức Bloom cho mỗi chương/bài học đã chọn.
                </p>
              </button>
            </div>
          )}

          {readyForScope && (
            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-1">
                Chọn chương/bài học đã dạy
              </p>
              <p className="text-xs text-slate-400 mb-3">
                Chỉ hiện chương thuộc Học kỳ {selectedSemesterNumber ?? "?"} (chương SGK không tách tập luôn hiện).
                {hiddenByOtherSemester > 0 && ` Đang ẩn ${hiddenByOtherSemester} chương thuộc học kỳ khác.`}{" "}
                {matrixMode === "AI"
                  ? "Tick cả chương nếu muốn phủ toàn chương, hoặc mở rộng để chọn đúng bài học cụ thể."
                  : "Tick chương/bài rồi nhập số câu theo từng mức Bloom (1-6) ngay bên dưới."}
              </p>
              {tree.chapters.length === 0 ? (
                <p className="text-sm text-slate-400">Môn/khối này chưa có chuẩn chương trình trong hệ thống.</p>
              ) : scopedChapters.length === 0 ? (
                <p className="text-sm text-slate-400">
                  Không có chương nào thuộc Học kỳ {selectedSemesterNumber ?? "?"} — đổi học kỳ khác.
                </p>
              ) : (
                <div className="space-y-1">
                  {scopedChapters.map((c) => {
                    const lessons = tree.lessonsByChapter.get(c.id) ?? [];
                    const expanded = expandedChapters.has(c.id);
                    return (
                      <div key={c.id}>
                        <div className="flex items-center gap-1.5">
                          {lessons.length > 0 ? (
                            <button
                              type="button"
                              onClick={() => toggleExpanded(c.id)}
                              className="p-0.5 rounded text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 shrink-0"
                            >
                              {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                            </button>
                          ) : (
                            <span className="w-5 shrink-0" />
                          )}
                          <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                            <input
                              type="checkbox"
                              checked={selectedUnitIds.includes(c.id)}
                              onChange={() => toggleUnit(c.id)}
                              className="rounded border-slate-300 dark:border-slate-600 text-brand-600 focus:ring-brand-500"
                            />
                            {c.name}
                            {lessons.length > 0 && (
                              <span className="text-xs font-normal text-slate-400">({lessons.length} bài)</span>
                            )}
                          </label>
                        </div>
                        {/* Loại trừ lẫn nhau: đang mở xem bài học thì ẩn lưới cấp-chương, tránh nhập trùng 2 cấp độ. */}
                        {matrixMode === "MANUAL" && selectedUnitIds.includes(c.id) && !expanded && (
                          <div className="ml-9">
                            <BloomCountGrid
                              examFormat={examFormat}
                              getCount={(qtype, bloom) => getManualCount(c.id, qtype, bloom)}
                              setCount={(qtype, bloom, value) => setManualCount(c.id, qtype, bloom, value)}
                            />
                          </div>
                        )}
                        {expanded && (
                          <div
                            className={`ml-9 mt-1 mb-2 gap-1.5 ${
                              matrixMode === "MANUAL" ? "flex flex-col" : "grid grid-cols-1 sm:grid-cols-2"
                            }`}
                          >
                            {lessons.map((l) => (
                              <div key={l.id}>
                                <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                                  <input
                                    type="checkbox"
                                    checked={selectedUnitIds.includes(l.id)}
                                    onChange={() => toggleUnit(l.id)}
                                    className="rounded border-slate-300 dark:border-slate-600 text-brand-600 focus:ring-brand-500"
                                  />
                                  {l.name}
                                </label>
                                {matrixMode === "MANUAL" && selectedUnitIds.includes(l.id) && (
                                  <BloomCountGrid
                                    examFormat={examFormat}
                                    getCount={(qtype, bloom) => getManualCount(l.id, qtype, bloom)}
                                    setCount={(qtype, bloom, value) => setManualCount(l.id, qtype, bloom, value)}
                                  />
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {matrixMode === "AI" ? (
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleRecommend}
                disabled={!readyForScope || selectedUnitIds.length === 0 || loadingRecommend}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold bg-accent-600 text-white hover:bg-accent-700 disabled:opacity-50"
              >
                <Sparkles className="w-4 h-4" />
                {loadingRecommend ? "Đang phân tích…" : "Gợi ý ma trận từ dữ liệu trường"}
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <span className="text-sm text-slate-500 dark:text-slate-400">
                Đã nhập: <b className="text-slate-800 dark:text-slate-100">{manualTotalEntered}</b>/{totalQuestions || 0} câu
              </span>
              <button
                type="button"
                onClick={handleManualContinue}
                disabled={!readyForScope || manualTotalEntered === 0}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
              >
                <FilePlus2 className="w-4 h-4" /> Tiếp tục
              </button>
            </div>
          )}
        </div>
      )}

      {step === 2 && gradeNumber && (
        <MatrixEditor
          subjectId={subjectId}
          gradeNumber={gradeNumber}
          scoreCategory={scoreCategory}
          unitOptions={unitOptions}
          blueprint={activeBlueprint}
          initialCells={draftCells}
          initialTitle={draftTitle}
          initialTargetDifficulty={draftTargetDifficulty}
          rationale={draftRationale}
          targetTotalPoints={Number(totalPoints) || null}
          targetTotalQuestions={Number(totalQuestions) || null}
          onSaved={handleSaved}
          onContinueUnsaved={handleContinueUnsaved}
        />
      )}

      {step === 3 && (activeBlueprint || pendingBlueprint) && (
        <ExamAssemblyPanel
          key={activeBlueprint?.id ?? "new-draft"}
          blueprint={activeBlueprint}
          draft={activeBlueprint ? null : pendingBlueprint}
          semesterId={semesterId}
          gradeId={gradeId}
          canReview={canReview}
          onBlueprintSaved={handleBlueprintSaved}
        />
      )}

      <ConfirmModal
        isOpen={!!deletingBlueprintId}
        title="Xóa ma trận đề"
        message="Ma trận này sẽ bị xóa vĩnh viễn. Nếu đã dùng để ráp đề, hệ thống sẽ từ chối xóa để bảo toàn đề đã tạo."
        onConfirm={handleDeleteBlueprint}
        onCancel={() => setDeletingBlueprintId(null)}
      />
    </div>
  );
}

function StepIndicator({
  step,
  setStep,
  canGoStep3,
}: {
  step: Step;
  setStep: (s: Step) => void;
  canGoStep3: boolean;
}) {
  const steps: { key: Step; label: string; enabled: boolean }[] = [
    { key: 1, label: "1. Phạm vi", enabled: true },
    { key: 2, label: "2. Ma trận", enabled: step >= 2 },
    { key: 3, label: "3. Ráp & chốt đề", enabled: step >= 3 || canGoStep3 },
  ];
  return (
    <div className="flex items-center gap-2">
      {steps.map((s, i) => (
        <div key={s.key} className="flex items-center gap-2">
          <button
            type="button"
            disabled={!s.enabled}
            onClick={() => setStep(s.key)}
            className={`px-3 py-1.5 rounded-full text-sm font-semibold disabled:cursor-not-allowed ${
              step === s.key
                ? "bg-brand-600 text-white"
                : s.enabled
                  ? "bg-brand-50 dark:bg-brand-500/10 text-brand-700 dark:text-brand-400"
                  : "bg-slate-100 dark:bg-slate-800 text-slate-400"
            }`}
          >
            {s.label}
          </button>
          {i < steps.length - 1 && <div className="w-6 h-px bg-slate-300 dark:bg-slate-700" />}
        </div>
      ))}
    </div>
  );
}
