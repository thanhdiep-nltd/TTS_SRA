"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Sliders,
  Eye,
  DownloadCloud,
  Database,
  Cpu,
  Image as ImageIcon,
  FileCheck,
  CheckCircle2,
  Sparkles,
  LineChart as LineChartIcon,
  GraduationCap,
  Calendar,
  Users,
  Check,
  FileText,
  Info,
  Loader2,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

import { api, getToken } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import { useAuth } from "@/lib/auth";
import SearchableSelect from "@/components/SearchableSelect";
import type { Semester, AcademicYear, ClassRow, DashboardOverview, Grade } from "@/lib/types";

export default function ReportsPage() {
  const { theme } = useTheme();
  const { user } = useAuth();

  const isSubjectRestricted = useMemo(() => {
    return !!user && (user.role === "SUBJECT_HEAD" || user.role === "SUBJECT_TEACHER") && !!user.subject_id;
  }, [user]);

  // Filter & Form States
  const [reportType, setReportType] = useState<"academic_conduct" | "subject_quality" | "at_risk" | "subject_report">("academic_conduct");
  const [format, setFormat] = useState<"pdf" | "docx">("pdf");
  const [selectedYear, setSelectedYear] = useState<string>("");
  const [selectedGrade, setSelectedGrade] = useState<string>("all");
  const [grades, setGrades] = useState<Grade[]>([]);
  const [selectedClass, setSelectedClass] = useState<string>("all");
  const [selectedSemester, setSelectedSemester] = useState<string>("");
  const [subjects, setSubjects] = useState<any[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string>("");

  // Checkbox Configs
  const [includeCharts, setIncludeCharts] = useState(true);
  const [includeTables, setIncludeTables] = useState(true);
  const [includeAiInsights, setIncludeAiInsights] = useState(true);
  const [includeSignature, setIncludeSignature] = useState(true);

  // Data Fetching States
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [classes, setClasses] = useState<ClassRow[]>([]);
  const [overviewData, setOverviewData] = useState<DashboardOverview | null>(null);

  // Progress States
  const [exportStatus, setExportStatus] = useState<"idle" | "exporting" | "completed">("idle");
  const [generatedHtml, setGeneratedHtml] = useState<string>("");
  const [isDownloading, setIsDownloading] = useState(false);
  const [exportPercent, setExportPercent] = useState(0);
  const [activeStep, setActiveStep] = useState(1);
  const [toast, setToast] = useState<{ title: string; message: string } | null>(null);

  // Colors based on theme
  const gridColor = theme === "dark" ? "#1e293b" : "#e2e8f0";
  const axisColor = theme === "dark" ? "#94a3b8" : "#64748b";
  const tooltipStyle = {
    backgroundColor: theme === "dark" ? "#0f172a" : "#ffffff",
    border: `1px solid ${gridColor}`,
    borderRadius: "12px",
    color: theme === "dark" ? "#f8fafc" : "#0f172a",
  };

  // Fetch baseline dynamic data
  useEffect(() => {
    // Fetch academic years
    api.get<AcademicYear[]>("/academic-years?limit=100")
      .then((data) => {
        setAcademicYears(data);
        const currentYear = data.find((y) => y.is_current) || data[0];
        if (currentYear) {
          setSelectedYear(currentYear.id);
        }
      })
      .catch(console.error);

    // Fetch semesters
    api.get<Semester[]>("/semesters?limit=100")
      .then(setSemesters)
      .catch(console.error);

    // Fetch classes
    api.get<ClassRow[]>("/classes/accessible")
      .then(setClasses)
      .catch(console.error);

    // Fetch grades
    api.get<Grade[]>("/grades")
      .then(setGrades)
      .catch(console.error);

    // Fetch subjects
    api.get<any[]>("/subjects?limit=200")
      .then((data) => {
        setSubjects(data);
        if (isSubjectRestricted && user?.subject_id) {
          setSelectedSubject(user.subject_id);
        } else if (data.length > 0) {
          setSelectedSubject(data[0].id);
        }
      })
      .catch(console.error);

    // Fetch overview statistics for real chart display in preview
    api.get<DashboardOverview>("/analytics/overview")
      .then(setOverviewData)
      .catch(console.error);
  }, [isSubjectRestricted, user?.subject_id]);

  useEffect(() => {
    if (isSubjectRestricted && user?.subject_id) {
      setSelectedSubject(user.subject_id);
    }
  }, [isSubjectRestricted, user?.subject_id]);

  // Filter semesters based on selected year
  const semestersOfYear = useMemo(() => {
    return semesters.filter((sem) => sem.academic_year_id === selectedYear);
  }, [semesters, selectedYear]);

  // Filter grades to show only those containing classes in the selected year
  const gradeOptions = useMemo(() => {
    const classesOfYear = classes.filter((c) => c.academic_year_id === selectedYear);
    const presentGradeIds = new Set(classesOfYear.map((c) => c.grade_id));
    return grades
      .filter((g) => presentGradeIds.has(g.id))
      .sort((a, b) => a.grade_number - b.grade_number);
  }, [classes, grades, selectedYear]);

  // Auto-select first or current semester and reset grade/class when academic year changes
  useEffect(() => {
    if (!selectedYear) return;
    const yearSemesters = semesters.filter((sem) => sem.academic_year_id === selectedYear);
    const currentSem = yearSemesters.find((sem) => sem.is_current) || yearSemesters[0];
    if (currentSem) {
      setSelectedSemester(currentSem.id);
    } else {
      setSelectedSemester("");
    }
    setSelectedGrade("all");
    setSelectedClass("all");
  }, [selectedYear, semesters]);

  // Filter classes based on selected grade and selected year
  const filteredClasses = useMemo(() => {
    return classes.filter((cls) => {
      const matchesGrade = selectedGrade === "all" || cls.grade_id === selectedGrade;
      const matchesYear = cls.academic_year_id === selectedYear;
      return matchesGrade && matchesYear;
    });
  }, [classes, selectedGrade, selectedYear]);

  // Reset preview status when filter configs change
  useEffect(() => {
    setExportStatus("idle");
    setGeneratedHtml("");
  }, [
    reportType,
    format,
    selectedYear,
    selectedGrade,
    selectedClass,
    selectedSemester,
    selectedSubject,
    includeCharts,
    includeTables,
    includeAiInsights,
    includeSignature
  ]);
  // Handle Export API Trigger & Progress Animation
  const handleExport = async () => {
    setExportStatus("exporting");
    setGeneratedHtml("");
    setExportPercent(0);
    setActiveStep(1);

    const duration = 2400; // 2.4s simulation
    const intervalTime = 40;
    const stepIncrement = 100 / (duration / intervalTime);
    let currentPercent = 0;

    const interval = setInterval(() => {
      currentPercent += stepIncrement;
      if (currentPercent >= 100) {
        currentPercent = 100;
        clearInterval(interval);
        setActiveStep(4);

        // Trigger preview generation
        triggerApiDownload().then(() => {
          setTimeout(() => {
            setExportStatus("completed");
            showToastMessage(
              "Khởi tạo thành công",
              `Bản xem trước báo cáo đã sẵn sàng.`
            );
          }, 400);
        }).catch((err) => {
          console.error(err);
          setExportStatus("idle");
          alert("Không thể kết nối đến server để khởi tạo dữ liệu báo cáo. Vui lòng thử lại!");
        });
      }

      setExportPercent(Math.round(currentPercent));

      if (currentPercent < 25) {
        setActiveStep(1);
      } else if (currentPercent < 50) {
        setActiveStep(2);
      } else if (currentPercent < 75) {
        setActiveStep(3);
      } else {
        setActiveStep(4);
      }
    }, intervalTime);
  };

  const triggerApiDownload = async () => {
    const token = getToken();
    const endpoint = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/reports/export`;

    const gradeObj = grades.find((g) => g.id === selectedGrade);
    const gradeLevelParam = gradeObj ? gradeObj.grade_number.toString() : "all";

    // format is either "pdf" or "docx", HTML preview is generated first

    // For PDF and DOCX: Always fetch the HTML format first to retrieve the HTML for preview
    const previewResponse = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        report_type: reportType,
        format: "html", // HTML format returns HTML from backend
        grade_level: gradeLevelParam,
        class_id: selectedClass === "all" ? null : selectedClass,
        semester_id: selectedSemester || null,
        subject_id: reportType === "subject_report" ? (selectedSubject || null) : null,
        include_charts: includeCharts,
        include_tables: includeTables,
        include_ai_insights: includeAiInsights,
        include_signature: includeSignature,
      }),
    });

    if (!previewResponse.ok) {
      throw new Error("Lỗi tải bản xem trước báo cáo");
    }

    const htmlText = await previewResponse.text();
    setGeneratedHtml(htmlText);
  };

  const handleDownloadFile = async () => {
    const token = getToken();
    const endpoint = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/reports/export`;

    const gradeObj = grades.find((g) => g.id === selectedGrade);
    const gradeLevelParam = gradeObj ? gradeObj.grade_number.toString() : "all";

    // If selected format is PDF, trigger the download for the PDF document generated by Gotenberg
    if (format === "pdf") {
      setIsDownloading(true);
      try {
        const response = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            report_type: reportType,
            format: "pdf",
            grade_level: gradeLevelParam,
            class_id: selectedClass === "all" ? null : selectedClass,
            semester_id: selectedSemester || null,
            subject_id: reportType === "subject_report" ? (selectedSubject || null) : null,
            include_charts: includeCharts,
            include_tables: includeTables,
            include_ai_insights: includeAiInsights,
            include_signature: includeSignature,
          }),
        });

        if (!response.ok) {
          throw new Error("Lỗi tải tệp PDF");
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;

        const semObj = semesters.find((s) => s.id === selectedSemester);
        const yearObj = academicYears.find((y) => y.id === selectedYear);
        const semName = semObj ? semObj.name.replace(/\s+/g, "") : "Ky1";
        const yearName = yearObj ? yearObj.name.replace(/\s+/g, "-") : "2025-2026";
        link.download = `Bao_Cao_${reportType}_${gradeLevelParam}_${semName}_NamHoc_${yearName}.pdf`;

        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        showToastMessage("Tải PDF thành công", "Báo cáo PDF đã được tải xuống máy của bạn.");
      } catch (err) {
        console.error(err);
        alert("Không thể tải PDF. Vui lòng thử lại!");
      } finally {
        setIsDownloading(false);
      }
      return;
    }

    // If selected format is DOCX, trigger the download for the binary document
    if (format === "docx") {
      setIsDownloading(true);
      try {
        const docxResponse = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            report_type: reportType,
            format: "docx",
            grade_level: gradeLevelParam,
            class_id: selectedClass === "all" ? null : selectedClass,
            semester_id: selectedSemester || null,
            subject_id: reportType === "subject_report" ? (selectedSubject || null) : null,
            include_charts: includeCharts,
            include_tables: includeTables,
            include_ai_insights: includeAiInsights,
            include_signature: includeSignature,
          }),
        });

        if (!docxResponse.ok) {
          throw new Error("Lỗi tải tệp DOCX");
        }

        const blob = await docxResponse.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;

        const semObj = semesters.find((s) => s.id === selectedSemester);
        const yearObj = academicYears.find((y) => y.id === selectedYear);
        const semName = semObj ? semObj.name.replace(/\s+/g, "") : "Ky2";
        const yearName = yearObj ? yearObj.name.replace(/\s+/g, "-") : "2025-2026";
        link.download = `Bao_Cao_${reportType}_${gradeLevelParam}_${semName}_NamHoc_${yearName}.docx`;

        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        showToastMessage(
          "Tải tệp thành công",
          "Tài liệu Word đã được tải về máy của bạn."
        );
      } catch (err) {
        console.error(err);
        alert("Không thể kết nối đến server để tải tài liệu DOCX. Vui lòng thử lại!");
      } finally {
        setIsDownloading(false);
      }
    }
  };

  const showToastMessage = (title: string, message: string) => {
    setToast({ title, message });
    setTimeout(() => {
      setToast(null);
    }, 4000);
  };

  // Label helpers for Preview
  const selectedGradeObj = grades.find((g) => g.id === selectedGrade);
  const selectedGradeLabel = selectedGrade === "all" ? "Toàn trường" : (selectedGradeObj?.name || "Khối");
  const selectedClassLabel = selectedClass === "all" ? "" : ` - Lớp ${classes.find(c => c.id === selectedClass)?.name || ""}`;
  const selectedSemObj = semesters.find(s => s.id === selectedSemester);
  const selectedSemLabel = selectedSemObj?.name || "Học Kỳ 2";
  const selectedYearObj = academicYears.find((y) => y.id === selectedYear);
  const selectedYearLabel = selectedYearObj?.name || "";

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto w-full">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-6">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">
            Bộ Tạo Báo Cáo Theo Mẫu
          </h2>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Cấu hình, xem trước trực quan và tải xuống các báo cáo học tập định dạng PDF, Excel, Word.
          </p>
        </div>
      </div>

      {/* Info bar */}
      <div className="bg-blue-50 dark:bg-slate-900 border border-blue-200 dark:border-slate-800 p-4 rounded-xl flex gap-3 text-sm text-blue-700 dark:text-blue-400">
        <Info className="w-5 h-5 shrink-0" />
        <p>
          Thiết lập các bộ lọc và tham số cấu hình ở cột trái. Hệ thống sẽ tự động tổng hợp số liệu thực tế từ cơ sở dữ liệu và hiển thị bản xem trước trực quan ở cột phải.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left config panel */}
        <div className="lg:col-span-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm space-y-6">
          <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-4">
            <Sliders className="w-5 h-5 text-brand-600 dark:text-brand-400" />
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">Cấu hình thông số báo cáo</h3>
          </div>

          {/* 1. Report Type */}
          <div className="space-y-3">
            <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider block">
              1. Chọn loại báo cáo
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                onClick={() => setReportType("academic_conduct")}
                className={`p-4 rounded-xl border text-left transition relative flex flex-col justify-between h-28 ${reportType === "academic_conduct"
                  ? "border-brand-600 bg-brand-50/50 dark:bg-brand-950/20 dark:border-brand-500"
                  : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-transparent"
                  }`}
              >
                <div className="flex justify-between items-center w-full">
                  <div className={`p-2 rounded-lg ${reportType === "academic_conduct" ? "bg-brand-500 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-500"}`}>
                    <LineChartIcon className="w-5 h-5" />
                  </div>
                  {reportType === "academic_conduct" && <CheckCircle2 className="w-5 h-5 text-brand-600 dark:text-brand-400" />}
                </div>
                <div>
                  <h4 className="font-bold text-sm text-slate-900 dark:text-white">Báo cáo tổng kết học tập</h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">GPA, hạnh kiểm học sinh theo TT22</p>
                </div>
              </button>

              <button
                onClick={() => setReportType("subject_quality")}
                className={`p-4 rounded-xl border text-left transition relative flex flex-col justify-between h-28 ${reportType === "subject_quality"
                  ? "border-brand-600 bg-brand-50/50 dark:bg-brand-950/20 dark:border-brand-500"
                  : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-transparent"
                  }`}
              >
                <div className="flex justify-between items-center w-full">
                  <div className={`p-2 rounded-lg ${reportType === "subject_quality" ? "bg-brand-500 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-500"}`}>
                    <GraduationCap className="w-5 h-5" />
                  </div>
                  {reportType === "subject_quality" && <CheckCircle2 className="w-5 h-5 text-brand-600 dark:text-brand-400" />}
                </div>
                <div>
                  <h4 className="font-bold text-sm text-slate-900 dark:text-white">Phân tích Phổ điểm & Bộ môn</h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">Chỉ số z-score, độ khó đề, độ lệch</p>
                </div>
              </button>

              <button
                onClick={() => setReportType("at_risk")}
                className={`p-4 rounded-xl border text-left transition relative flex flex-col justify-between h-28 ${reportType === "at_risk"
                  ? "border-brand-600 bg-brand-50/50 dark:bg-brand-950/20 dark:border-brand-500"
                  : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-transparent"
                  }`}
              >
                <div className="flex justify-between items-center w-full">
                  <div className={`p-2 rounded-lg ${reportType === "at_risk" ? "bg-brand-500 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-500"}`}>
                    <Calendar className="w-5 h-5" />
                  </div>
                  {reportType === "at_risk" && <CheckCircle2 className="w-5 h-5 text-brand-600 dark:text-brand-400" />}
                </div>
                <div>
                  <h4 className="font-bold text-sm text-slate-900 dark:text-white">Sàng lọc Học sinh Nguy cơ</h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">Học lực yếu, vắng học nhiều</p>
                </div>
              </button>

              <button
                onClick={() => setReportType("subject_report")}
                className={`p-4 rounded-xl border text-left transition relative flex flex-col justify-between h-28 ${reportType === "subject_report"
                  ? "border-brand-600 bg-brand-50/50 dark:bg-brand-950/20 dark:border-brand-500"
                  : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-transparent"
                  }`}
              >
                <div className="flex justify-between items-center w-full">
                  <div className={`p-2 rounded-lg ${reportType === "subject_report" ? "bg-brand-500 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-500"}`}>
                    <Users className="w-5 h-5" />
                  </div>
                  {reportType === "subject_report" && <CheckCircle2 className="w-5 h-5 text-brand-600 dark:text-brand-400" />}
                </div>
                <div>
                  <h4 className="font-bold text-sm text-slate-900 dark:text-white">Báo cáo theo môn học</h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">ĐTB môn, thi đua lớp, học sinh đột biến</p>
                </div>
              </button>
            </div>
          </div>

          {/* 2. Format Selector */}
          <div className="space-y-3">
            <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider block">
              2. Định dạng file xuất
            </span>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setFormat("pdf")}
                className={`py-3 px-4 rounded-xl border font-semibold text-sm transition flex items-center justify-center gap-2 ${format === "pdf"
                  ? "bg-brand-600 text-white border-brand-600 shadow-sm"
                  : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 text-slate-700 dark:text-slate-300"
                  }`}
              >
                <FileText className="w-4 h-4" /> Tệp văn bản PDF
              </button>

              <button
                onClick={() => setFormat("docx")}
                className={`py-3 px-4 rounded-xl border font-semibold text-sm transition flex items-center justify-center gap-2 ${format === "docx"
                  ? "bg-brand-600 text-white border-brand-600 shadow-sm"
                  : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 text-slate-700 dark:text-slate-300"
                  }`}
              >
                <FileText className="w-4 h-4" /> Tài liệu Word (DOCX)
              </button>
            </div>
          </div>

          {/* 3. Data Scope Selectors */}
          <div className="space-y-3">
            <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider block">
              3. Phạm vi dữ liệu & Thời gian
            </span>
            <div className={`grid grid-cols-1 sm:grid-cols-2 ${reportType === "subject_report" ? "lg:grid-cols-5 md:grid-cols-3" : "md:grid-cols-4"} gap-3`}>
              {/* Year Select */}
              <SearchableSelect
                label="Năm học"
                value={selectedYear}
                onChange={(v) => {
                  setSelectedYear(v);
                  setSelectedClass("all");
                }}
                options={academicYears.map((y) => ({ value: y.id, label: y.name }))}
                placeholder="— Chọn năm học —"
              />

              {/* Grade Level */}
              <SearchableSelect
                label="Khối lớp"
                value={selectedGrade}
                onChange={(v) => {
                  setSelectedGrade(v);
                  setSelectedClass("all");
                }}
                options={[
                  { value: "all", label: "Tất cả khối" },
                  ...gradeOptions.map((g) => ({ value: g.id, label: g.name }))
                ]}
                placeholder="— Chọn khối lớp —"
              />

              {/* Class Select */}
              <SearchableSelect
                label="Lớp học"
                value={selectedClass}
                onChange={setSelectedClass}
                options={[
                  { value: "all", label: "Tất cả các lớp" },
                  ...filteredClasses.map((cls) => ({ value: cls.id, label: cls.name }))
                ]}
                placeholder="— Chọn lớp học —"
              />

              {/* Semester */}
              <SearchableSelect
                label="Học kỳ"
                value={selectedSemester}
                onChange={setSelectedSemester}
                options={semestersOfYear.map((sem) => ({ value: sem.id, label: sem.name }))}
                placeholder="— Chọn học kỳ —"
              />

              {/* Subject Select */}
              {reportType === "subject_report" && (
                isSubjectRestricted ? (
                  <div className="flex flex-col gap-1 w-full">
                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Môn học</span>
                    <span className="px-3 py-2 text-sm font-semibold text-slate-800 dark:text-slate-100 border border-slate-350 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800/40">
                      {subjects.find((sub) => sub.id === selectedSubject)?.name ?? "—"}
                    </span>
                  </div>
                ) : (
                  <SearchableSelect
                    label="Môn học"
                    value={selectedSubject}
                    onChange={setSelectedSubject}
                    options={subjects.map((sub) => ({ value: sub.id, label: sub.name }))}
                    placeholder="— Chọn môn học —"
                  />
                )
              )}
            </div>
          </div>

          {/* 4. Formatting Option Checkboxes */}
          <div className="space-y-3">
            <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider block">
              4. Tùy chọn hiển thị nội dung
            </span>
            <div className="space-y-2.5">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeCharts}
                  onChange={(e) => setIncludeCharts(e.target.checked)}
                  className="w-4 h-4 rounded text-brand-600 focus:ring-brand-500 accent-brand-600 cursor-pointer"
                />
                <span className="text-sm text-slate-700 dark:text-slate-350">
                  Bao gồm các biểu đồ thống kê trực quan
                </span>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeTables}
                  onChange={(e) => setIncludeTables(e.target.checked)}
                  className="w-4 h-4 rounded text-brand-600 focus:ring-brand-500 accent-brand-600 cursor-pointer"
                />
                <span className="text-sm text-slate-700 dark:text-slate-350">
                  Bao gồm bảng số liệu chi tiết học lực/KPI
                </span>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeAiInsights}
                  onChange={(e) => setIncludeAiInsights(e.target.checked)}
                  className="w-4 h-4 rounded text-brand-600 focus:ring-brand-500 accent-brand-600 cursor-pointer"
                />
                <span className="text-sm text-slate-700 dark:text-slate-350">
                  Tích hợp nhận xét phân tích & đề xuất bằng AI
                </span>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeSignature}
                  onChange={(e) => setIncludeSignature(e.target.checked)}
                  className="w-4 h-4 rounded text-brand-600 focus:ring-brand-500 accent-brand-600 cursor-pointer"
                />
                <span className="text-sm text-slate-700 dark:text-slate-350">
                  Chèn khung ký tên & đóng dấu của Hiệu trưởng
                </span>
              </label>
            </div>
          </div>

          {/* Export Button */}
          <button
            onClick={handleExport}
            disabled={exportStatus === "exporting"}
            className={`w-full py-3.5 font-bold rounded-xl flex items-center justify-center gap-2 shadow-sm transition hover:shadow-md cursor-pointer ${exportStatus === "exporting"
              ? "bg-slate-300 dark:bg-slate-800 text-slate-500 dark:text-slate-400 cursor-not-allowed"
              : "bg-brand-600 hover:bg-brand-700 dark:bg-brand-700 dark:hover:bg-brand-600 text-white"
              }`}
          >
            <DownloadCloud className="w-5 h-5 animate-bounce" />
            {exportStatus === "exporting" ? "Đang xuất báo cáo..." : "Tiến hành xuất báo cáo"}
          </button>
        </div>

        {/* Right live preview panel */}
        <div className="lg:col-span-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-800 dark:text-white">
              <Eye className="w-5 h-5" />
              <h3 className="font-bold text-sm uppercase tracking-wider">Bản xem trước báo cáo</h3>
            </div>

            <div className="flex items-center gap-2">
              {exportStatus === "completed" && (
                <button
                  onClick={handleDownloadFile}
                  disabled={isDownloading}
                  className={`flex items-center gap-1.5 px-3 py-1 text-xs font-bold rounded-lg shadow-sm transition-all duration-150 cursor-pointer ${isDownloading
                    ? "bg-slate-300 dark:bg-slate-800 text-slate-500 dark:text-slate-400 cursor-not-allowed"
                    : "bg-emerald-600 hover:bg-emerald-700 text-white"
                    }`}
                >
                  {isDownloading ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <DownloadCloud className="w-3.5 h-3.5" />
                  )}
                  {format === "pdf"
                    ? (isDownloading ? "Đang chuẩn bị PDF..." : "Tải xuống PDF")
                    : isDownloading
                      ? "Đang chuẩn bị tệp..."
                      : "Tải tệp Word"}
                </button>
              )}

              <span className="text-[11px] font-bold bg-brand-50 dark:bg-brand-950/40 text-brand-700 dark:text-brand-400 px-3 py-1 rounded-full border border-brand-200/50 dark:border-brand-900/30">
                Định dạng: {format.toUpperCase()}
              </span>
            </div>
          </div>

          <div className={`bg-slate-200 dark:bg-slate-950 border border-slate-300 dark:border-slate-900 rounded-2xl ${exportStatus === "completed" ? "p-0" : "p-6"} min-h-[580px] flex ${exportStatus === "completed" ? "items-start" : "items-center"} justify-center shadow-inner overflow-hidden w-full`}>
            {exportStatus === "idle" && (
              <div className="w-full h-full min-h-[480px] border-2 border-dashed border-slate-300 dark:border-slate-800 rounded-xl flex flex-col items-center justify-center p-8 text-center bg-slate-50/20 dark:bg-slate-900/10 transition-colors duration-200 hover:bg-slate-100/30 dark:hover:bg-slate-900/20">
                <div className="p-4 rounded-full bg-brand-50 dark:bg-slate-900 text-brand-600 dark:text-brand-400 mb-4 shadow-sm animate-pulse">
                  <FileText className="w-8 h-8" />
                </div>
                <h4 className="font-bold text-lg text-slate-800 dark:text-slate-200 mb-2">
                  Đây là nơi hiển thị báo cáo
                </h4>
                <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm">
                  Thiết lập cấu hình ở bảng bên trái và nhấn <strong className="text-brand-600 dark:text-brand-400">"Tiến hành xuất báo cáo"</strong> để hiển thị bản xem trước trực quan tại đây.
                </p>
              </div>
            )}

            {exportStatus === "exporting" && (
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 max-w-md w-full shadow-lg flex flex-col items-center gap-6 text-center animate-in fade-in zoom-in-95">
                <h3 className="font-bold text-lg text-slate-900 dark:text-white">
                  Đang khởi tạo tài liệu...
                </h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 -mt-3">
                  Vui lòng không đóng cửa sổ này khi hệ thống đang xử lý dữ liệu.
                </p>

                {/* Circular Progress Gauge */}
                <div className="relative w-28 h-28 flex items-center justify-center">
                  <svg className="w-full h-full transform -rotate-90">
                    <circle
                      cx="56"
                      cy="56"
                      r="48"
                      className="stroke-slate-100 dark:stroke-slate-800 fill-none"
                      strokeWidth="6"
                    />
                    <circle
                      cx="56"
                      cy="56"
                      r="48"
                      className="stroke-brand-600 dark:stroke-brand-500 fill-none transition-all duration-100 ease-linear"
                      strokeWidth="6"
                      strokeDasharray={301.6}
                      strokeDashoffset={301.6 - (301.6 * exportPercent) / 100}
                      strokeLinecap="round"
                    />
                  </svg>
                  <div className="absolute font-bold text-xl text-slate-800 dark:text-slate-100">
                    {exportPercent}%
                  </div>
                </div>

                {/* Steps indicator */}
                <div className="w-full space-y-3.5 text-left border-t border-slate-100 dark:border-slate-800 pt-5">
                  <div className="flex items-center gap-3 text-sm">
                    <Database className={`w-4 h-4 ${activeStep >= 1 ? "text-brand-500" : "text-slate-400"}`} />
                    <span className={activeStep === 1 ? "text-slate-900 dark:text-white font-semibold animate-pulse" : activeStep > 1 ? "text-slate-600 dark:text-slate-350" : "text-slate-400"}>
                      Kết nối máy chủ cơ sở dữ liệu học sinh...
                    </span>
                    {activeStep > 1 && <Check className="w-4 h-4 text-emerald-500 ml-auto font-bold" />}
                  </div>

                  <div className="flex items-center gap-3 text-sm">
                    <Cpu className={`w-4 h-4 ${activeStep >= 2 ? "text-brand-500" : "text-slate-400"}`} />
                    <span className={activeStep === 2 ? "text-slate-900 dark:text-white font-semibold animate-pulse" : activeStep > 2 ? "text-slate-600 dark:text-slate-350" : "text-slate-400"}>
                      Xử lý và tổng hợp số liệu thống kê...
                    </span>
                    {activeStep > 2 && <Check className="w-4 h-4 text-emerald-500 ml-auto font-bold" />}
                  </div>

                  <div className="flex items-center gap-3 text-sm">
                    <ImageIcon className={`w-4 h-4 ${activeStep >= 3 ? "text-brand-500" : "text-slate-400"}`} />
                    <span className={activeStep === 3 ? "text-slate-900 dark:text-white font-semibold animate-pulse" : activeStep > 3 ? "text-slate-600 dark:text-slate-350" : "text-slate-400"}>
                      Xuất đồ thị trực quan & xây dựng layout...
                    </span>
                    {activeStep > 3 && <Check className="w-4 h-4 text-emerald-500 ml-auto font-bold" />}
                  </div>

                  <div className="flex items-center gap-3 text-sm">
                    <FileCheck className={`w-4 h-4 ${activeStep >= 4 ? "text-brand-500" : "text-slate-400"}`} />
                    <span className={activeStep === 4 ? "text-slate-900 dark:text-white font-semibold animate-pulse" : "text-slate-400"}>
                      Đóng gói dữ liệu & tải xuống máy khách...
                    </span>
                    {activeStep > 4 && <Check className="w-4 h-4 text-emerald-500 ml-auto font-bold" />}
                  </div>
                </div>
              </div>
            )}

            {exportStatus === "completed" && (
              generatedHtml ? (
                /* Actual Generated HTML document inside an iframe */
                <iframe
                  srcDoc={generatedHtml}
                  className="w-full h-full min-h-[580px] bg-white border-0"
                  title="Bản xem trước báo cáo"
                />
              ) : (
                /* Fallback A4 Paper Document Preview if generatedHtml is missing */
                <div className="w-full bg-white text-slate-800 p-6 flex flex-col font-sans text-[11px] shadow-lg max-w-md aspect-[1/1.414] overflow-hidden border-t-4 relative"
                  style={{ borderColor: format === "pdf" ? "#0d4d8b" : "#2b579a" }}>

                  {/* Administrative Header */}
                  <div className="flex justify-between border-b border-slate-200 pb-2 mb-4 text-[9px] text-slate-400">
                    <span className="font-semibold uppercase tracking-wider text-brand-600">SchoolAI Portal</span>
                    <span>{user?.school_name || "Trường học"} | 21/06/2026</span>
                  </div>

                  {/* Report Title */}
                  <div className="text-center my-3">
                    <h4 className="font-extrabold text-sm tracking-wide text-slate-900 uppercase">
                      BÁO CÁO THỐNG KÊ {reportType === "academic_conduct" ? "TỔNG KẾT HỌC TẬP VÀ RÈN LUYỆN" : reportType === "subject_quality" ? "PHÂN TÍCH PHỔ ĐIỂM & BỘ MÔN" : reportType === "at_risk" ? "SÀNG LỌC HỌC SINH NGUY CƠ" : "THEO MÔN HỌC"}
                    </h4>
                    <p className="text-[9px] text-slate-500 mt-0.5">
                      Phạm vi: {selectedGradeLabel} {selectedClassLabel} | Kỳ: {selectedSemLabel} | Năm học: {selectedYearLabel}
                    </p>
                  </div>

                  {/* Main KPI Stats blocks */}
                  <div className={`grid ${selectedClass && selectedClass !== "all" ? "grid-cols-3" : "grid-cols-4"} gap-2 my-3`}>
                    <div className="border border-slate-100 bg-slate-50/50 p-2 rounded text-center">
                      <span className="text-[8px] text-slate-400 uppercase tracking-wider block">Học sinh</span>
                      <span className="text-xs font-bold text-brand-700 block">
                        {overviewData?.total_students ?? 1245}
                      </span>
                    </div>

                    <div className="border border-slate-100 bg-slate-50/50 p-2 rounded text-center">
                      <span className="text-[8px] text-slate-400 uppercase tracking-wider block">
                        {selectedClass && selectedClass !== "all" ? "GPA Lớp" : "GPA Trường"}
                      </span>
                      <span className="text-xs font-bold text-emerald-600 block">
                        {overviewData?.average_gpa ? `${overviewData.average_gpa}/10` : "7.82"}
                      </span>
                    </div>

                    {!(selectedClass && selectedClass !== "all") && (
                      <div className="border border-slate-100 bg-slate-50/50 p-2 rounded text-center">
                        <span className="text-[8px] text-slate-400 uppercase tracking-wider block">Số Lớp</span>
                        <span className="text-xs font-bold text-slate-700 block">
                          {overviewData?.total_classes ?? 32}
                        </span>
                      </div>
                    )}

                    <div className="border border-slate-100 bg-slate-50/50 p-2 rounded text-center">
                      <span className="text-[8px] text-slate-400 uppercase tracking-wider block">Học Kỳ</span>
                      <span className="text-xs font-bold text-indigo-600 block">Kỳ II</span>
                    </div>
                  </div>

                  {/* Dynamic Recharts Chart Section in Preview */}
                  {includeCharts && overviewData && (
                    <div className="space-y-1.5 my-3">
                      <span className="text-[9px] font-bold text-brand-700 border-l-2 border-brand-500 pl-1.5 block">
                        BIỂU ĐỒ THỐNG KÊ
                      </span>
                      <div className="h-28 w-full border border-slate-100 bg-slate-50/20 rounded p-1.5">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={overviewData.grade_distribution}
                            margin={{ top: 5, right: 5, left: -30, bottom: 0 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                            <XAxis dataKey="name" fontSize={8} stroke="#94a3b8" />
                            <YAxis fontSize={8} stroke="#94a3b8" />
                            <Tooltip contentStyle={{ fontSize: 9 }} />
                            <Bar dataKey="gioi" name="Tốt" fill="#10b981" stackId="a" />
                            <Bar dataKey="kha" name="Khá" fill="#3b82f6" stackId="a" />
                            <Bar dataKey="yeu" name="Chưa đạt" fill="#ef4444" stackId="a" />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  )}

                  {/* Table Data Preview */}
                  {includeTables && (
                    <div className="space-y-1.5 my-3">
                      <span className="text-[9px] font-bold text-brand-700 border-l-2 border-brand-500 pl-1.5 block">
                        BẢNG SỐ LIỆU CHI TIẾT
                      </span>
                      <table className="w-full border-collapse border border-slate-100 text-[8px] text-left">
                        <thead>
                          <tr className="bg-slate-50 text-slate-600 border-b border-slate-100 font-bold">
                            <th className="p-1">Hạng mục</th>
                            <th className="p-1 text-right">Học sinh</th>
                            <th className="p-1 text-right">GPA TB</th>
                            <th className="p-1 text-right">Đạt chuẩn</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr className="border-b border-slate-100">
                            <td className="p-1 font-semibold text-slate-700">Khối 10</td>
                            <td className="p-1 text-right">425</td>
                            <td className="p-1 text-right">7.65</td>
                            <td className="p-1 text-right text-emerald-600">97.8%</td>
                          </tr>
                          <tr className="border-b border-slate-100">
                            <td className="p-1 font-semibold text-slate-700">Khối 11</td>
                            <td className="p-1 text-right">410</td>
                            <td className="p-1 text-right">7.78</td>
                            <td className="p-1 text-right text-emerald-600">97.2%</td>
                          </tr>
                          <tr className="border-b border-slate-100">
                            <td className="p-1 font-semibold text-slate-700">Khối 12</td>
                            <td className="p-1 text-right">410</td>
                            <td className="p-1 text-right">8.03</td>
                            <td className="p-1 text-right text-emerald-600">98.1%</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* AI Insights block */}
                  {includeAiInsights && (
                    <div className="bg-indigo-50 border border-indigo-100 p-2.5 rounded text-left space-y-1 my-2">
                      <h5 className="text-[9px] font-bold text-indigo-700 flex items-center gap-1">
                        <Sparkles className="w-3 h-3" /> AI Insights & Khuyến Nghị
                      </h5>
                      <p className="text-[8px] text-indigo-850 leading-relaxed">
                        Phát hiện xu hướng GPA tăng trưởng nhẹ (+0.15). Cần tập trung cải thiện môn Toán khối 10 để giảm tỷ lệ dưới trung bình ở học kỳ tới.
                      </p>
                    </div>
                  )}

                  {/* Signature box */}
                  {includeSignature && (
                    <div className="flex flex-col items-end text-right ml-auto mt-auto pr-3">
                      <span className="text-[8px] text-slate-400 uppercase tracking-wider block font-bold">
                        Hiệu trưởng phê duyệt
                      </span>
                      <span className="text-[9px] font-bold italic text-brand-700 mt-2 block">
                        Thầy {user?.principal_name || "Nguyễn Minh Triết"}
                      </span>
                      <div className="w-20 border-t border-slate-200 mt-2"></div>
                    </div>
                  )}
                </div>
              )
            )}
          </div>
        </div>
      </div>

      {/* Toast Alert */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xl flex items-center gap-3 text-slate-850 dark:text-slate-200 animate-in slide-in-from-bottom-5">
          <div className="p-1.5 rounded-lg bg-emerald-100 dark:bg-emerald-950/20 text-emerald-600 dark:text-emerald-400">
            <Check className="w-5 h-5" />
          </div>
          <div>
            <h4 className="font-bold text-sm">{toast.title}</h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{toast.message}</p>
          </div>
        </div>
      )}
    </div>
  );
}
