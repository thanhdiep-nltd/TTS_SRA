"use client";

import { useState, useEffect, useMemo, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  BookOpen,
  Search,
  ChevronRight,
  ChevronDown,
  Clock,
  Target,
  FileText,
  Copy,
  Printer,
  ListChecks,
  AlertTriangle,
  Award,
  Sparkles,
  Layers,
  BookMarked,
  CheckCircle2,
  Tag,
  ExternalLink,
  Info,
  GraduationCap,
  Book,
  ArrowRight,
} from "lucide-react";

import { api } from "@/lib/api";
import {
  CourseSummary,
  CourseTreeItem,
  GradeOption,
  LessonPlanBrief,
  LessonPlanDetail,
  SubjectOption,
  UnitTreeItem,
} from "@/lib/types";

function LessonPlansContent() {
  const searchParams = useSearchParams();
  const initialLessonId = searchParams.get("lesson_id");
  const initialUnitId = searchParams.get("unit_id"); // curriculum_units.id
  const initialCourseId = searchParams.get("course_id");
  const initialGradeId = searchParams.get("grade_id");
  const initialSubjectId = searchParams.get("subject_id");

  // Filters State
  const [grades, setGrades] = useState<GradeOption[]>([]);
  const [subjects, setSubjects] = useState<SubjectOption[]>([]);
  const [selectedGradeId, setSelectedGradeId] = useState<number>(
    initialGradeId ? parseInt(initialGradeId, 10) : 6
  );
  const [selectedSubjectId, setSelectedSubjectId] = useState<number>(
    initialSubjectId ? parseInt(initialSubjectId, 10) : 106
  );

  // Courses & Lessons State
  const [courses, setCourses] = useState<CourseSummary[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(
    initialCourseId ? parseInt(initialCourseId, 10) : null
  );
  const [treeData, setTreeData] = useState<CourseTreeItem | null>(null);
  const [selectedLessonId, setSelectedLessonId] = useState<number | null>(
    initialLessonId ? parseInt(initialLessonId, 10) : null
  );
  const [lessonDetail, setLessonDetail] = useState<LessonPlanDetail | null>(null);

  const [loadingMeta, setLoadingMeta] = useState(true);
  const [loadingCourses, setLoadingCourses] = useState(false);
  const [loadingTree, setLoadingTree] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [expandedUnits, setExpandedUnits] = useState<Record<number, boolean>>({});
  const [activeTab, setActiveTab] = useState<"content" | "targets" | "curriculum">("content");
  const [copied, setCopied] = useState(false);

  // 1. Fetch Metadata (Grades & Subjects)
  useEffect(() => {
    async function loadMeta() {
      try {
        setLoadingMeta(true);
        const res = await api.get<{ grades: GradeOption[]; subjects: SubjectOption[] }>(
          "/lesson-plans/subjects"
        );
        setGrades(res.grades || []);
        setSubjects(res.subjects || []);
      } catch (err) {
        console.error("Lỗi tải danh mục Khối & Môn học:", err);
      } finally {
        setLoadingMeta(false);
      }
    }
    loadMeta();
  }, []);

  // 2. Fetch courses list when Subject or Grade changes
  useEffect(() => {
    async function loadCourses() {
      try {
        setLoadingCourses(true);
        const queryParams = new URLSearchParams();
        if (selectedSubjectId) queryParams.append("subject_id", selectedSubjectId.toString());
        if (selectedGradeId) queryParams.append("grade_id", selectedGradeId.toString());

        const res = await api.get<CourseSummary[]>(`/lesson-plans/courses?${queryParams.toString()}`);
        setCourses(res);

        if (res.length > 0) {
          // If current selectedCourseId is not in the list, choose the first course
          const exists = res.some((c) => c.id === selectedCourseId);
          if (!exists) {
            setSelectedCourseId(res[0].id);
          }
        } else {
          setSelectedCourseId(null);
          setTreeData(null);
          setSelectedLessonId(null);
          setLessonDetail(null);
        }
      } catch (err) {
        console.error("Lỗi tải danh sách khóa học:", err);
        setCourses([]);
      } finally {
        setLoadingCourses(false);
      }
    }
    loadCourses();
  }, [selectedGradeId, selectedSubjectId]);

  // 3. Fetch course tree when selectedCourseId changes
  useEffect(() => {
    if (!selectedCourseId) return;

    async function loadTree() {
      try {
        setLoadingTree(true);
        const res = await api.get<CourseTreeItem>(
          `/lesson-plans/tree?course_id=${selectedCourseId}`
        );
        setTreeData(res);

        // Mặc định mở rộng tất cả các chương
        if (res && res.units) {
          const initExpanded: Record<number, boolean> = {};
          res.units.forEach((u) => {
            initExpanded[u.id] = true;
          });
          setExpandedUnits(initExpanded);

          // Nếu chưa chọn bài nào hoặc bài đã chọn không thuộc course này, chọn bài đầu tiên
          const allLessonIds = res.units.flatMap((u) => u.lessons.map((l) => l.id));
          if (!selectedLessonId || !allLessonIds.includes(selectedLessonId)) {
            if (res.units.length > 0 && res.units[0].lessons.length > 0) {
              setSelectedLessonId(res.units[0].lessons[0].id);
            }
          }
        }
      } catch (err) {
        console.error("Lỗi tải cây bài học:", err);
      } finally {
        setLoadingTree(false);
      }
    }
    loadTree();
  }, [selectedCourseId]);

  // 4. Handle initial unit_id (deep link from Knowledge Gaps)
  useEffect(() => {
    if (!initialUnitId) return;

    async function loadByCurriculum() {
      try {
        setLoadingDetail(true);
        const res = await api.get<LessonPlanDetail>(
          `/lesson-plans/by-curriculum/${initialUnitId}`
        );
        setSelectedGradeId(6);
        setSelectedSubjectId(106);
        setSelectedCourseId(res.course_id);
        setSelectedLessonId(res.lesson_id);
        setLessonDetail(res);
      } catch (err) {
        console.error("Lỗi tìm giáo án từ curriculum_unit:", err);
      } finally {
        setLoadingDetail(false);
      }
    }
    loadByCurriculum();
  }, [initialUnitId]);

  // 5. Fetch lesson detail when selectedLessonId changes
  useEffect(() => {
    if (!selectedLessonId) return;

    async function loadDetail() {
      try {
        setLoadingDetail(true);
        const res = await api.get<LessonPlanDetail>(`/lesson-plans/${selectedLessonId}`);
        setLessonDetail(res);
      } catch (err) {
        console.error("Lỗi tải chi tiết giáo án:", err);
      } finally {
        setLoadingDetail(false);
      }
    }
    loadDetail();
  }, [selectedLessonId]);

  // Toggle chapter accordion
  const toggleUnit = (unitId: number) => {
    setExpandedUnits((prev) => ({ ...prev, [unitId]: !prev[unitId] }));
  };

  // Filter units and lessons
  const filteredUnits = useMemo(() => {
    if (!treeData) return [];
    if (!searchQuery.trim()) return treeData.units;

    const q = searchQuery.toLowerCase().trim();
    return treeData.units
      .map((u) => {
        const matchingLessons = u.lessons.filter(
          (l) =>
            l.name.toLowerCase().includes(q) ||
            l.code.toLowerCase().includes(q) ||
            (l.curriculum_unit_name && l.curriculum_unit_name.toLowerCase().includes(q))
        );
        const isUnitMatch = u.name.toLowerCase().includes(q) || u.code.toLowerCase().includes(q);
        if (isUnitMatch || matchingLessons.length > 0) {
          return {
            ...u,
            lessons: isUnitMatch ? u.lessons : matchingLessons,
          };
        }
        return null;
      })
      .filter((u): u is UnitTreeItem => u !== null);
  }, [treeData, searchQuery]);

  // Copy Markdown content
  const handleCopyContent = () => {
    if (!lessonDetail?.content_own) return;
    navigator.clipboard.writeText(lessonDetail.content_own);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Print lesson plan
  const handlePrint = () => {
    window.print();
  };

  const selectedSubjectObj = subjects.find((s) => s.id === selectedSubjectId);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* 1. HERO HEADER */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-900 via-slate-900 to-indigo-950 p-6 sm:p-8 text-white shadow-xl">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-500/20 text-brand-300 text-xs font-semibold backdrop-blur-md mb-3 border border-brand-400/30">
              <Sparkles className="w-3.5 h-3.5" />
              Khung Kế Hoạch Bài Dạy Chuẩn Bộ GD&ĐT (CTST)
            </div>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white flex items-center gap-3">
              <BookOpen className="w-8 h-8 text-brand-400" />
              Kế Hoạch Bài Dạy (Giáo Án)
            </h1>
            <p className="mt-2 text-sm text-slate-300 max-w-2xl leading-relaxed">
              Tra cứu và quản lý giáo án chi tiết, mục tiêu kiến thức năng lực, tích hợp liên thông với Ngân hàng câu hỏi LMS và Bản đồ tri thức chẩn đoán lỗ hổng.
            </p>
          </div>

          {/* Mini KPI Cards */}
          <div className="grid grid-cols-3 gap-3 shrink-0">
            <div className="p-3.5 rounded-xl bg-white/5 border border-white/10 backdrop-blur-md text-center">
              <span className="text-xs text-slate-400 font-medium block">Toán 6 sẵn sàng</span>
              <span className="text-xl font-black text-emerald-400">65 bài</span>
            </div>
            <div className="p-3.5 rounded-xl bg-white/5 border border-white/10 backdrop-blur-md text-center">
              <span className="text-xs text-slate-400 font-medium block">Số chương</span>
              <span className="text-xl font-black text-sky-400">9 chương</span>
            </div>
            <div className="p-3.5 rounded-xl bg-white/5 border border-white/10 backdrop-blur-md text-center">
              <span className="text-xs text-slate-400 font-medium block">Mục tiêu</span>
              <span className="text-xl font-black text-amber-400">239</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. FILTER BAR: KHỐI + MÔN HỌC + HỌC KỲ + TÌM KIẾM */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl p-4 sm:p-5 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
        {/* Row 1: Selectors for Grade & Subject */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
            {/* Bộ chọn Khối */}
            <div className="flex items-center gap-2">
              <GraduationCap className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              <span className="text-xs font-bold text-slate-700 dark:text-slate-300">Khối:</span>
              <select
                value={selectedGradeId}
                onChange={(e) => setSelectedGradeId(parseInt(e.target.value, 10))}
                className="px-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-xs sm:text-sm font-semibold text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all cursor-pointer"
              >
                {grades.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name} {g.has_lesson_plans ? "⭐ (Có giáo án)" : ""}
                  </option>
                ))}
              </select>
            </div>

            {/* Bộ chọn Môn học */}
            <div className="flex items-center gap-2">
              <Book className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              <span className="text-xs font-bold text-slate-700 dark:text-slate-300">Môn học:</span>
              <select
                value={selectedSubjectId}
                onChange={(e) => setSelectedSubjectId(parseInt(e.target.value, 10))}
                className="px-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-xs sm:text-sm font-semibold text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all cursor-pointer max-w-[220px]"
              >
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} {s.has_lesson_plans ? "⭐ (Đầy đủ)" : ""}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Ô Tìm kiếm bài học */}
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Tìm bài học, chủ đề..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-1.5 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl text-xs sm:text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all text-slate-900 dark:text-white"
            />
          </div>
        </div>

        {/* Row 2: Semester tabs (if available) */}
        {courses.length > 0 && (
          <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2 overflow-x-auto pb-1">
            <span className="text-xs font-bold text-slate-500 dark:text-slate-400 shrink-0">
              Học kỳ:
            </span>
            {courses.map((c) => {
              const isActive = selectedCourseId === c.id;
              return (
                <button
                  key={c.id}
                  onClick={() => setSelectedCourseId(c.id)}
                  className={`px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all flex items-center gap-2 shrink-0 ${
                    isActive
                      ? "bg-brand-600 text-white shadow-md shadow-brand-600/20"
                      : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
                  }`}
                >
                  <Layers className="w-4 h-4" />
                  {c.name}
                  <span
                    className={`text-[11px] px-1.5 py-0.5 rounded-md ${
                      isActive
                        ? "bg-white/20 text-white"
                        : "bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300"
                    }`}
                  >
                    {c.lesson_count} bài • {c.period} tiết
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* 3. EMPTY STATE (NẾU CHƯA CÓ GIÁO ÁN CHO MÔN ĐÃ CHỌN) */}
      {courses.length === 0 && !loadingCourses && (
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-12 text-center shadow-xs space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-amber-50 dark:bg-amber-950/40 text-amber-500 flex items-center justify-center mx-auto border border-amber-200 dark:border-amber-900/50">
            <BookOpen className="w-8 h-8" />
          </div>
          <div className="max-w-md mx-auto space-y-2">
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">
              Chưa Có Dữ Liệu Giáo Án Cho Môn {selectedSubjectObj?.name || "này"} (Khối {selectedGradeId})
            </h3>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
              Hệ thống hiện tại đã nạp và chuẩn hóa đầy đủ <strong>65 bài giáo án chi tiết</strong> cho môn <strong>Toán học Khối 6</strong> (CTST). Dữ liệu các môn khác đang được số hóa và chuẩn bị đưa vào.
            </p>
          </div>
          <button
            onClick={() => {
              setSelectedGradeId(6);
              setSelectedSubjectId(106);
            }}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs sm:text-sm font-bold transition-all shadow-md shadow-brand-600/20"
          >
            Chuyển Sang Môn Toán Khối 6 (65 Bài)
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 4. MASTER-DETAIL 2-COLUMN LAYOUT */}
      {courses.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* LEFT COLUMN: LESSONS TREE (5 COLS) */}
          <div className="lg:col-span-5 space-y-4">
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-4 shadow-xs">
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center gap-2">
                  <BookMarked className="w-4 h-4 text-brand-600 dark:text-brand-400" />
                  <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                    Danh Mục Bài Học ({filteredUnits.reduce((acc, u) => acc + u.lessons.length, 0)} bài)
                  </h3>
                </div>
                <span className="text-xs text-slate-400">Chọn bài để đọc</span>
              </div>

              {loadingTree ? (
                <div className="space-y-3 p-4">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="h-16 bg-slate-100 dark:bg-slate-800 rounded-xl animate-pulse" />
                  ))}
                </div>
              ) : filteredUnits.length === 0 ? (
                <div className="py-12 text-center text-slate-400 text-xs">
                  Không tìm thấy bài học nào phù hợp với từ khóa &ldquo;{searchQuery}&rdquo;.
                </div>
              ) : (
                <div className="space-y-3 max-h-[750px] overflow-y-auto pr-1">
                  {filteredUnits.map((unit) => {
                    const isExpanded = !!expandedUnits[unit.id];
                    return (
                      <div
                        key={unit.id}
                        className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/40 overflow-hidden"
                      >
                        {/* Chapter Header */}
                        <button
                          onClick={() => toggleUnit(unit.id)}
                          className="w-full p-3.5 flex items-center justify-between gap-3 text-left hover:bg-slate-100/70 dark:hover:bg-slate-800/50 transition-colors"
                        >
                          <div className="flex items-center gap-2.5">
                            <div className="text-slate-400">
                              {isExpanded ? <ChevronDown className="w-4 h-4 text-brand-500" /> : <ChevronRight className="w-4 h-4" />}
                            </div>
                            <div>
                              <span className="font-bold text-xs sm:text-sm text-slate-900 dark:text-white block">
                                {unit.name}
                              </span>
                              <span className="text-[11px] text-slate-400">
                                {unit.lessons.length} bài học • {unit.period} tiết
                              </span>
                            </div>
                          </div>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-brand-50 text-brand-700 dark:bg-brand-950/50 dark:text-brand-300">
                            Chương {unit.order_number}
                          </span>
                        </button>

                        {/* Lesson items in chapter */}
                        {isExpanded && (
                          <div className="p-2 space-y-1.5 border-t border-slate-200/60 dark:border-slate-800/60 bg-white dark:bg-slate-900">
                            {unit.lessons.map((lesson) => {
                              const isSelected = selectedLessonId === lesson.id;
                              return (
                                <button
                                  key={`${unit.id}-${lesson.id}`}
                                  onClick={() => setSelectedLessonId(lesson.id)}
                                  className={`w-full p-2.5 rounded-lg text-left transition-all flex items-start justify-between gap-2.5 ${
                                    isSelected
                                      ? "bg-brand-50/80 dark:bg-brand-950/50 border border-brand-300 dark:border-brand-800 shadow-xs"
                                      : "hover:bg-slate-50 dark:hover:bg-slate-800/40 border border-transparent"
                                  }`}
                                >
                                  <div className="flex items-start gap-2 min-w-0">
                                    <span
                                      className={`w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 ${
                                        isSelected
                                          ? "bg-brand-600 text-white"
                                          : "bg-slate-100 dark:bg-slate-800 text-slate-500"
                                      }`}
                                    >
                                      {lesson.order_number}
                                    </span>
                                    <div className="min-w-0">
                                      <h4
                                        className={`text-xs font-semibold leading-snug line-clamp-2 ${
                                          isSelected
                                            ? "text-brand-700 dark:text-brand-300 font-bold"
                                            : "text-slate-800 dark:text-slate-200"
                                        }`}
                                      >
                                        {lesson.name}
                                      </h4>
                                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                                        <span className="text-[10px] text-slate-400 flex items-center gap-1">
                                          <Clock className="w-3 h-3 text-slate-400" />
                                          {lesson.period} tiết
                                        </span>
                                        {lesson.target_count > 0 && (
                                          <span className="text-[10px] text-slate-400 flex items-center gap-1">
                                            <Target className="w-3 h-3 text-amber-500" />
                                            {lesson.target_count} mục tiêu
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  </div>

                                  {lesson.has_plan && (
                                    <span className="shrink-0 text-emerald-500 mt-1" title="Đã có giáo án">
                                      <CheckCircle2 className="w-4 h-4" />
                                    </span>
                                  )}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* RIGHT COLUMN: LESSON PLAN DETAIL & VIEWER (7 COLS) */}
          <div className="lg:col-span-7 space-y-4">
            {loadingDetail ? (
              <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-8 space-y-6 shadow-xs">
                <div className="h-8 bg-slate-100 dark:bg-slate-800 rounded-xl w-3/4 animate-pulse" />
                <div className="h-4 bg-slate-100 dark:bg-slate-800 rounded-lg w-1/2 animate-pulse" />
                <div className="space-y-3 pt-4">
                  {[1, 2, 3, 4, 5, 6].map((i) => (
                    <div key={i} className="h-4 bg-slate-100 dark:bg-slate-800 rounded-lg animate-pulse" />
                  ))}
                </div>
              </div>
            ) : !lessonDetail ? (
              <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-12 text-center text-slate-400 shadow-xs">
                <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <p className="text-sm font-semibold">Vui lòng chọn một bài học bên danh mục để xem giáo án chi tiết.</p>
              </div>
            ) : (
              <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
                {/* Header Box */}
                <div className="p-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/40">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400 mb-2">
                    <span className="font-medium">{lessonDetail.course_name}</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                    <span className="font-medium">{lessonDetail.unit_name}</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                    <span className="font-semibold text-brand-600 dark:text-brand-400">
                      Bài {lessonDetail.order_number}
                    </span>
                  </div>

                  <h2 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white leading-tight">
                    {lessonDetail.lesson_name}
                  </h2>

                  <div className="flex flex-wrap items-center gap-2.5 mt-3.5">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-brand-50 text-brand-700 dark:bg-brand-950/50 dark:text-brand-300 border border-brand-200/60 dark:border-brand-800/60">
                      <Clock className="w-3.5 h-3.5 text-brand-500" />
                      Thời lượng: {lessonDetail.period} tiết
                    </span>

                    {lessonDetail.curriculum_unit_id && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-sky-50 text-sky-700 dark:bg-sky-950/50 dark:text-sky-300 border border-sky-200/60 dark:border-sky-800/60">
                        <BookOpen className="w-3.5 h-3.5 text-sky-500" />
                        Mỏ neo SGK: #{lessonDetail.curriculum_unit_id}
                      </span>
                    )}

                    {lessonDetail.targets.length > 0 && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300 border border-amber-200/60 dark:border-amber-800/60">
                        <Target className="w-3.5 h-3.5 text-amber-500" />
                        {lessonDetail.targets.length} mục tiêu kiến thức
                      </span>
                    )}
                  </div>

                  {/* ACTION BUTTONS BAR */}
                  <div className="flex items-center justify-between gap-3 mt-5 pt-4 border-t border-slate-200/60 dark:border-slate-800/60 flex-wrap">
                    <div className="flex items-center gap-2 flex-wrap">
                      {/* Deep-link sang Ngân hàng câu hỏi */}
                      {lessonDetail.related_lms_questions_count > 0 && (
                        <Link
                          href={`/question-bank?unit_id=${lessonDetail.curriculum_unit_id}`}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300 hover:bg-indigo-100 transition-colors border border-indigo-200/60 dark:border-indigo-800/60"
                        >
                          <ListChecks className="w-3.5 h-3.5" />
                          Xem {lessonDetail.related_lms_questions_count} câu hỏi LMS
                        </Link>
                      )}

                      {/* Deep-link sang Cây tri thức Knowledge Gaps */}
                      <Link
                        href={`/knowledge-gaps`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 hover:bg-emerald-100 transition-colors border border-emerald-200/60 dark:border-emerald-800/60"
                      >
                        <AlertTriangle className="w-3.5 h-3.5" />
                        Mức độ tiếp thu của lớp
                      </Link>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleCopyContent}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 transition-colors shadow-xs"
                      >
                        {copied ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                        {copied ? "Đã chép" : "Sao chép"}
                      </button>
                      <button
                        onClick={handlePrint}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 transition-colors shadow-xs"
                      >
                        <Printer className="w-3.5 h-3.5" />
                        In giáo án
                      </button>
                    </div>
                  </div>
                </div>

                {/* TABS NAVIGATION */}
                <div className="flex items-center gap-2 px-6 pt-3 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">
                  <button
                    onClick={() => setActiveTab("content")}
                    className={`pb-3 text-xs sm:text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${
                      activeTab === "content"
                        ? "border-brand-600 text-brand-600 dark:text-brand-400"
                        : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    <FileText className="w-4 h-4" />
                    Nội Dung Giáo Án Chi Tiết
                  </button>

                  <button
                    onClick={() => setActiveTab("targets")}
                    className={`pb-3 text-xs sm:text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${
                      activeTab === "targets"
                        ? "border-brand-600 text-brand-600 dark:text-brand-400"
                        : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    <Target className="w-4 h-4" />
                    Mục Tiêu Bài Học ({lessonDetail.targets.length})
                  </button>

                  <button
                    onClick={() => setActiveTab("curriculum")}
                    className={`pb-3 text-xs sm:text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${
                      activeTab === "curriculum"
                        ? "border-brand-600 text-brand-600 dark:text-brand-400"
                        : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    <BookOpen className="w-4 h-4" />
                    Mỏ Neo SGK & Lý Thuyết
                  </button>
                </div>

                {/* TAB 1: NỘI DUNG GIÁO ÁN (CONTENT_OWN) VỚI ĐỊNH DẠNG MARKDOWN CHUẨN ĐẸP */}
                {activeTab === "content" && (
                  <div className="p-6 sm:p-8 space-y-6">
                    {lessonDetail.content_own ? (
                      <div className="markdown-body prose prose-slate dark:prose-invert max-w-none text-xs sm:text-sm leading-relaxed font-sans">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            h2: ({ children }) => (
                              <h2 className="text-base sm:text-lg font-black text-brand-900 dark:text-brand-300 border-l-4 border-brand-500 pl-3 py-1 my-5 bg-brand-50/50 dark:bg-brand-950/30 rounded-r-lg">
                                {children}
                              </h2>
                            ),
                            h3: ({ children }) => (
                              <h3 className="text-sm sm:text-base font-bold text-slate-800 dark:text-slate-200 mt-4 mb-2 flex items-center gap-1.5 text-indigo-900 dark:text-indigo-300">
                                {children}
                              </h3>
                            ),
                            h4: ({ children }) => (
                              <h4 className="text-xs sm:text-sm font-bold text-slate-700 dark:text-slate-300 mt-3 mb-1 text-slate-900 dark:text-white">
                                {children}
                              </h4>
                            ),
                            table: ({ children }) => (
                              <div className="my-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 shadow-xs">
                                <table className="w-full text-left text-xs border-collapse divide-y divide-slate-200 dark:divide-slate-700 bg-white dark:bg-slate-900">
                                  {children}
                                </table>
                              </div>
                            ),
                            thead: ({ children }) => (
                              <thead className="bg-slate-100 dark:bg-slate-800 font-bold text-slate-900 dark:text-slate-100">
                                {children}
                              </thead>
                            ),
                            th: ({ children }) => {
                              const renderHeader = (child: React.ReactNode): React.ReactNode => {
                                if (typeof child === "string" && child.includes("<br/>")) {
                                  const parts = child.split("<br/>");
                                  return parts.map((p, idx) => (
                                    <span key={idx} className="block">
                                      {p.trim()}
                                    </span>
                                  ));
                                }
                                return child;
                              };
                              return (
                                <th className="px-3.5 py-2.5 border-r border-slate-200 dark:border-slate-700 last:border-r-0 font-bold text-xs bg-slate-100 dark:bg-slate-800">
                                  {Array.isArray(children)
                                    ? children.map((c, i) => <span key={i}>{renderHeader(c)}</span>)
                                    : renderHeader(children)}
                                </th>
                              );
                            },
                            td: ({ children }) => {
                              const renderCell = (child: React.ReactNode): React.ReactNode => {
                                if (typeof child === "string" && child.includes("<br/>")) {
                                  const parts = child.split("<br/>");
                                  return parts.map((p, idx) => (
                                    <span key={idx} className="block my-0.5">
                                      {p.trim()}
                                    </span>
                                  ));
                                }
                                return child;
                              };
                              return (
                                <td className="px-3.5 py-2.5 border-r border-b border-slate-100 dark:border-slate-800 last:border-r-0 text-slate-700 dark:text-slate-300 align-top text-xs leading-relaxed">
                                  {Array.isArray(children)
                                    ? children.map((c, i) => <span key={i}>{renderCell(c)}</span>)
                                    : renderCell(children)}
                                </td>
                              );
                            },
                            p: ({ children }) => (
                              <p className="my-1.5 leading-relaxed text-slate-700 dark:text-slate-300">
                                {children}
                              </p>
                            ),
                            ul: ({ children }) => (
                              <ul className="my-2 space-y-1 list-disc list-inside text-slate-700 dark:text-slate-300">
                                {children}
                              </ul>
                            ),
                            strong: ({ children }) => (
                              <strong className="font-bold text-slate-900 dark:text-white">
                                {children}
                              </strong>
                            ),
                          }}
                        >
                          {lessonDetail.content_own}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <div className="py-12 text-center text-slate-400 text-xs">
                        Chưa có nội dung chi tiết cho giáo án này.
                      </div>
                    )}
                  </div>
                )}

                {/* TAB 2: MỤC TIÊU BÀI DẠY (TARGETS) */}
                {activeTab === "targets" && (
                  <div className="p-6 sm:p-8 space-y-4">
                    <div className="flex items-center gap-2 text-xs text-slate-500 mb-2">
                      <Info className="w-4 h-4 text-brand-500" />
                      Các mục tiêu kiến thức, năng lực và phẩm chất cần đạt được quy định cho bài học:
                    </div>

                    {lessonDetail.targets.length === 0 ? (
                      <div className="py-8 text-center text-slate-400 text-xs">
                        Chưa có mục tiêu riêng lẻ nào được phân tách cho bài học này.
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {lessonDetail.targets.map((tgt, idx) => (
                          <div
                            key={tgt.id}
                            className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 space-y-1.5"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-brand-100 text-brand-700 dark:bg-brand-950 dark:text-brand-300">
                                Mục tiêu {idx + 1}
                              </span>
                              <span className="text-[10px] text-slate-400 font-mono">{tgt.code}</span>
                            </div>
                            <h5 className="font-bold text-sm text-slate-900 dark:text-white">
                              {tgt.name}
                            </h5>
                            {tgt.description && tgt.description !== tgt.name && (
                              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                                {tgt.description}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* TAB 3: MỎ NEO SGK & LÝ THUYẾT (CURRICULUM) */}
                {activeTab === "curriculum" && (
                  <div className="p-6 sm:p-8 space-y-6">
                    {lessonDetail.curriculum_summary ? (
                      <div className="p-4 rounded-xl border border-sky-200/80 dark:border-sky-900/60 bg-sky-50/50 dark:bg-sky-950/20 space-y-2">
                        <div className="flex items-center gap-2 font-bold text-sm text-sky-900 dark:text-sky-300">
                          <Award className="w-4 h-4 text-sky-500" />
                          Tóm Tắt Lý Thuyết Cốt Lõi SGK:
                        </div>
                        <p className="text-xs sm:text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                          {lessonDetail.curriculum_summary}
                        </p>
                      </div>
                    ) : (
                      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 text-xs text-slate-500">
                        Chưa có đoạn tóm tắt lý thuyết riêng cho đơn vị kiến thức này.
                      </div>
                    )}

                    {lessonDetail.curriculum_keywords && lessonDetail.curriculum_keywords.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="font-bold text-xs text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                          <Tag className="w-3.5 h-3.5 text-brand-500" />
                          Từ Khóa Trọng Tâm (Keywords):
                        </h4>
                        <div className="flex flex-wrap gap-2">
                          {lessonDetail.curriculum_keywords.map((kw, i) => (
                            <span
                              key={i}
                              className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
                            >
                              #{kw}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Liên kết chẩn đoán */}
                    <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 flex items-center justify-between gap-4">
                      <div>
                        <h5 className="font-bold text-sm text-slate-900 dark:text-white">
                          Chẩn Đoán Lỗ Hổng Kiến Thức Của Bài Này
                        </h5>
                        <p className="text-xs text-slate-500 mt-0.5">
                          Xem danh sách học sinh đang bị hổng kiến thức ở bài học này để lên kế hoạch phụ đạo.
                        </p>
                      </div>
                      <Link
                        href="/knowledge-gaps"
                        className="px-3 py-2 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs flex items-center gap-1.5 shrink-0 transition-colors shadow-xs"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        Mở Cây Năng Lực
                      </Link>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function LessonPlansPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-7xl mx-auto py-12 text-center space-y-3">
          <div className="w-10 h-10 border-4 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-slate-400 font-medium">Đang tải kế hoạch bài dạy...</p>
        </div>
      }
    >
      <LessonPlansContent />
    </Suspense>
  );
}
