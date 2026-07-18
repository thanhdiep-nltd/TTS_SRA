"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Mic,
  UploadCloud,
  History,
  Trash2,
  Play,
  Pause,
  RotateCw,
  LayoutGrid,
  Loader,
  Clock,
  ShieldCheck,
  User,
  Music,
  CheckCircle,
  AlertTriangle,
  X,
  Volume2,
  Zap,
  FileText,
  Video,
  Sliders,
  Cpu,
  Check,
  Calendar,
  ListOrdered,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApiBusy } from "@/lib/useApiBusy";
import { LoadingState } from "@/components/Loading";
import ConfirmModal from "@/components/ConfirmModal";
import { type AcademicYear, type ClassRow, type Semester, type Subject } from "@/lib/types";

// Xếp loại labels và màu sắc tương ứng
const RANK_LABELS: Record<string, string> = {
  EXCELLENT: "Xuất Sắc",
  SATISFACTORY: "Đạt Yêu Cầu",
  NEEDS_IMPROVEMENT: "Cần Cải Thiện",
};

const RANK_BADGE_CLASSES: Record<string, string> = {
  EXCELLENT: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-400 dark:border-emerald-800",
  SATISFACTORY: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/30 dark:text-sky-400 dark:border-sky-800",
  NEEDS_IMPROVEMENT: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/30 dark:text-amber-400 dark:border-amber-800",
};

const classroomMetadata: Record<string, { room: string; teacher: string; subject: string }> = {
  "10A1": { room: "Phòng 201", teacher: "Cô Lê Hoa", subject: "Tiếng Anh" },
  "10A2": { room: "Phòng 202", teacher: "Thầy Nguyễn An", subject: "Toán học" },
  "11B1": { room: "Phòng 301", teacher: "Thầy Vũ Hải", subject: "Vật lý" },
  "12C3": { room: "Phòng 403", teacher: "Cô Phạm Mai", subject: "Hóa học" },
};

export default function RecordingsPage() {
  const { user } = useAuth();
  const isBgh = user?.role === "ADMIN" || user?.role === "PRINCIPAL";

  const [recordings, setRecordings] = useState<any[]>([]);
  const [classes, setClasses] = useState<ClassRow[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [years, setYears] = useState<AcademicYear[]>([]);

  // Form states (Teacher)
  const [yearId, setYearId] = useState("");
  const [semesterId, setSemesterId] = useState("");
  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [lessonName, setLessonName] = useState("");
  const [period, setPeriod] = useState<number>(3);
  const [date, setDate] = useState(new Date().toISOString().split("T")[0]);
  const [week, setWeek] = useState<number>(1);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // Filter states (BGH)
  const [selectedWeek, setSelectedWeek] = useState("all");
  const [selectedTeacherName, setSelectedTeacherName] = useState("all");

  // BGH sub-tabs: results vs camera mock
  const [bghTab, setBghTab] = useState<"results" | "camera">("results");

  // Camera extraction states
  const [teachers, setTeachers] = useState<any[]>([]);
  const [camTeacherId, setCamTeacherId] = useState("");
  const [camClass, setCamClass] = useState("7A1");
  const [camClassId, setCamClassId] = useState("");
  const [camSubjectId, setCamSubjectId] = useState("");
  const [camSemesterId, setCamSemesterId] = useState("");
  const [camWeek, setCamWeek] = useState<number>(28);
  const [camPeriod, setCamPeriod] = useState("Tiết 3");
  const [camDate, setCamDate] = useState("2026-07-02");
  const [liveCamTime, setLiveCamTime] = useState("");

  const handleCamClassChange = (classIdVal: string) => {
    setCamClassId(classIdVal);
    const cls = classes.find(c => c.id === classIdVal);
    if (cls) {
      setCamClass(cls.name);
    }
  };

  // Timetable data structures: Rows = Periods (1 to 5), Columns = Days (T2 to T6)
  const timetable7A1 = [
    // Tiết 1
    [
      { subject: "Chào cờ", status: "locked", period: 1 },
      { subject: "Toán học", teacherIdx: 6, period: 1 },
      { subject: "Vật lý", teacherIdx: 2, period: 1 },
      { subject: "Toán học", teacherIdx: 6, period: 1 },
      { subject: "Lịch sử", teacherIdx: 4, period: 1 },
    ],
    // Tiết 2
    [
      { subject: "Ngữ văn", teacherIdx: 0, period: 2 },
      { subject: "Toán học", teacherIdx: 6, period: 2 },
      { subject: "Hóa học", teacherIdx: 3, period: 2 },
      { subject: "Toán học", teacherIdx: 6, period: 2 },
      { subject: "Địa lý", teacherIdx: 5, period: 2 },
    ],
    // Tiết 3
    [
      { subject: "Ngữ văn", teacherIdx: 0, period: 3 },
      { subject: "Hóa học", teacherIdx: 3, period: 3 },
      { subject: "Ngữ văn", teacherIdx: 0, period: 3 },
      { subject: "Địa lý", teacherIdx: 5, period: 3 },
      { subject: "Tiếng Anh", teacherIdx: 1, period: 3 },
    ],
    // Tiết 4
    [
      { subject: "Vật lý", teacherIdx: 2, period: 4 },
      { subject: "Tiếng Anh", teacherIdx: 1, period: 4 },
      { subject: "Ngữ văn", teacherIdx: 0, period: 4 },
      { subject: "Lịch sử", teacherIdx: 4, period: 4 },
      { subject: "Công nghệ", teacherIdx: 7, period: 4 },
    ],
    // Tiết 5
    [
      { subject: "Tiếng Anh", teacherIdx: 1, period: 5 },
      { subject: "Sinh học", teacherIdx: 7, period: 5 },
      { subject: "Tin học", teacherIdx: 8, period: 5 },
      { subject: "Âm nhạc", teacherIdx: 9, period: 5 },
      { subject: "Sinh hoạt lớp", status: "locked", period: 5 },
    ],
  ];

  const timetable7A2 = [
    // Tiết 1
    [
      { subject: "Chào cờ", status: "locked", period: 1 },
      { subject: "Ngữ văn", teacherIdx: 0, period: 1 },
      { subject: "Tiếng Anh", teacherIdx: 1, period: 1 },
      { subject: "Ngữ văn", teacherIdx: 0, period: 1 },
      { subject: "Hóa học", teacherIdx: 3, period: 1 },
    ],
    // Tiết 2
    [
      { subject: "Toán học", teacherIdx: 6, period: 2 },
      { subject: "Ngữ văn", teacherIdx: 0, period: 2 },
      { subject: "Vật lý", teacherIdx: 2, period: 2 },
      { subject: "Ngữ văn", teacherIdx: 0, period: 2 },
      { subject: "Lịch sử", teacherIdx: 4, period: 2 },
    ],
    // Tiết 3
    [
      { subject: "Toán học", teacherIdx: 6, period: 3 },
      { subject: "Địa lý", teacherIdx: 5, period: 3 },
      { subject: "Toán học", teacherIdx: 6, period: 3 },
      { subject: "Hóa học", teacherIdx: 3, period: 3 },
      { subject: "Tiếng Anh", teacherIdx: 1, period: 3 },
    ],
    // Tiết 4
    [
      { subject: "Tiếng Anh", teacherIdx: 1, period: 4 },
      { subject: "Lịch sử", teacherIdx: 4, period: 4 },
      { subject: "Toán học", teacherIdx: 6, period: 4 },
      { subject: "Địa lý", teacherIdx: 5, period: 4 },
      { subject: "Tin học", teacherIdx: 8, period: 4 },
    ],
    // Tiết 5
    [
      { subject: "Vật lý", teacherIdx: 2, period: 5 },
      { subject: "Công nghệ", teacherIdx: 7, period: 5 },
      { subject: "Âm nhạc", teacherIdx: 9, period: 5 },
      { subject: "Tin học", teacherIdx: 8, period: 5 },
      { subject: "Sinh hoạt lớp", status: "locked", period: 5 },
    ],
  ];

  const getSubjectAndTeacherForCell = (cell: any) => {
    if (cell.status === "locked") return { sub: null, teacher: null };

    const sub = subjects.find(s =>
      s.name.toLowerCase().includes(cell.subject.toLowerCase()) ||
      cell.subject.toLowerCase().includes(s.name.toLowerCase())
    ) ?? subjects[0];

    const tIdx = cell.teacherIdx % (teachers.length || 1);
    const teacher = teachers[tIdx] ?? { id: camTeacherId, full_name: "Cô Lê Hoa" };

    return { sub, teacher };
  };

  const handleCellClick = async (cell: any, dayIndex: number) => {
    if (cell.status === "locked") {
      showToast(`${cell.subject} không thể thực hiện trích xuất và phân tích AI.`, "info");
      return;
    }

    const datesOfWeek = [
      "2026-03-23",
      "2026-03-24",
      "2026-03-25",
      "2026-03-26",
      "2026-03-27"
    ];
    const dateStr = datesOfWeek[dayIndex];

    // Tìm kiếm trong danh sách recordings xem có bản ghi cho lớp này, ngày này, tiết này chưa
    const matchingRec = recordings.find(r =>
      r.class_name === camClass &&
      r.date?.startsWith(dateStr) &&
      r.period === cell.period
    );

    if (matchingRec) {
      if (matchingRec.status === "done") {
        // Mở popup xem báo cáo chi tiết ngay lập tức
        handleViewDetails(matchingRec);
        return;
      }
      if (matchingRec.status === "processing" || matchingRec.status === "pending") {
        showToast(`Tiết học này đang được trích xuất và xử lý AI (${matchingRec.progress}%). Vui lòng đợi.`, "info");
        return;
      }
      if (matchingRec.status === "failed") {
        askConfirmation(
          "Kích Hoạt Lại Phân Tích",
          "Tiết học này trích xuất bị lỗi. Bạn có muốn kích hoạt phân tích lại?",
          () => handleReanalyze(matchingRec.id)
        );
        return;
      }
    }

    const { sub, teacher } = getSubjectAndTeacherForCell(cell);
    if (!sub || !teacher) {
      showToast("Không tìm thấy môn học hoặc giáo viên hợp lệ.", "error");
      return;
    }

    const confirmMsg = `Bạn có muốn thực hiện trích xuất và đánh giá AI cho tiết ${cell.period} môn ${cell.subject} do ${teacher.full_name} giảng dạy?`;

    const triggerExtract = async () => {
      setCamSubjectId(sub.id);
      setCamTeacherId(teacher.id);
      setCamPeriod(`Tiết ${cell.period}`);
      setCamDate(dateStr);

      const lName = `Camera: ${sub.name} - Lớp ${camClass}`;
      try {
        const payload = {
          teacher_id: teacher.id,
          class_id: camClassId,
          subject_id: sub.id,
          semester_id: camSemesterId,
          period: cell.period,
          date: dateStr,
          week: 28,
          lesson_name: lName
        };

        showToast("Đang khởi tạo yêu cầu trích xuất camera...", "info");
        await api.post("/recordings/camera-extract", payload);
        fetchRecordings();
        showToast("Khởi tạo tiến trình trích xuất camera thành công!", "success");
      } catch (err: any) {
        showToast(err.message ?? "Lỗi khi trích xuất camera.", "error");
      }
    };

    askConfirmation("Trích Xuất Camera", confirmMsg, triggerExtract);
  };

  // Tự động đồng bộ danh sách hàng chờ và trạng thái camera từ database
  const mockCameraRequests = useMemo(() => {
    return recordings
      .filter((r) => r.lesson_name.startsWith("Camera:") || r.audio_file_url === "vms_extraction_pending")
      .map((r) => {
        let steps = [
          { name: "Kết nối Cloud Camera API", status: "pending", progress: 0 },
          { name: "Trích xuất Video MP4", status: "pending", progress: 0 },
          { name: "Tách xuất âm thanh MP3", status: "pending", progress: 0 },
          { name: "Phân tích WhisperX STT & LLM Eval", status: "pending", progress: 0 }
        ];

        const progress = r.progress;
        if (r.status === "done") {
          steps = steps.map(s => ({ ...s, status: "done", progress: 100 }));
        } else if (r.status === "failed") {
          if (progress <= 10) {
            steps[0].status = "failed";
          } else if (progress <= 20) {
            steps[0].status = "done"; steps[0].progress = 100;
            steps[1].status = "failed";
          } else if (progress <= 30) {
            steps[0].status = "done"; steps[0].progress = 100;
            steps[1].status = "done"; steps[1].progress = 100;
            steps[2].status = "failed";
          } else {
            steps[0].status = "done"; steps[0].progress = 100;
            steps[1].status = "done"; steps[1].progress = 100;
            steps[2].status = "done"; steps[2].progress = 100;
            steps[3].status = "failed";
          }
        } else if (r.status === "processing") {
          if (progress <= 15) {
            steps[0].status = "active";
            steps[0].progress = Math.min(99, progress * 7);
          } else if (progress <= 25) {
            steps[0].status = "done"; steps[0].progress = 100;
            steps[1].status = "active";
            steps[1].progress = Math.min(99, (progress - 15) * 10);
          } else if (progress <= 35) {
            steps[0].status = "done"; steps[0].progress = 100;
            steps[1].status = "done"; steps[1].progress = 100;
            steps[2].status = "active";
            steps[2].progress = Math.min(99, (progress - 25) * 10);
          } else {
            steps[0].status = "done"; steps[0].progress = 100;
            steps[1].status = "done"; steps[1].progress = 100;
            steps[2].status = "done"; steps[2].progress = 100;
            steps[3].status = "active";
            steps[3].progress = Math.min(99, (progress - 35) * 1.5);
          }
        } else {
          steps[0].status = "active";
          steps[0].progress = 10;
        }

        return {
          id: r.id,
          classVal: r.class_name || "7A1",
          room: "Phòng " + (r.class_name?.includes("10") ? "201" : r.class_name?.includes("11") ? "301" : "403"),
          teacher: r.teacher_name || "Giáo viên",
          subject: r.subject_name || "Môn học",
          period: `Tiết ${r.period}`,
          date: r.date,
          cameraSource: "Cloud Camera (Tự động)",
          status: r.status,
          progress: r.progress,
          steps: steps,
          score: r.score ? r.score.toFixed(1) : "",
          rank: r.rank === "EXCELLENT" ? "Xuất sắc" : r.rank === "SATISFACTORY" ? "Đạt" : r.rank ? "Cần cải thiện" : "",
          reportText: r.ai_report || "",
          errorReason: r.status === "failed" ? (r.ai_report || "Lỗi trích xuất từ Cloud Camera") : ""
        };
      });
  }, [recordings]);

  // UI state
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRecording, setSelectedRecording] = useState<any | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [activeTab, setActiveTab] = useState<"report" | "transcript" | "source">("report");

  // Custom Audio Player State
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.8);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const busy = useApiBusy();

  // Toast notifications state
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  // Custom confirmation modal state
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  } | null>(null);

  const showToast = (message: string, type: "success" | "error" | "info" = "success") => {
    setToast({ message, type });
  };

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => {
        setToast(null);
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const askConfirmation = (title: string, message: string, onConfirm: () => void) => {
    setConfirmModal({
      isOpen: true,
      title,
      message,
      onConfirm: () => {
        onConfirm();
        setConfirmModal(null);
      }
    });
  };

  // Tick the clock in Live Monitor
  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      setLiveCamTime(now.toLocaleTimeString("en-US", { hour12: true }));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Tải dữ liệu ban đầu
  const loadData = () => {
    setLoading(true);
    const promises: Promise<any>[] = [
      api.get<Subject[]>("/subjects?limit=200"),
      api.get<Semester[]>("/semesters?limit=50"),
      api.get<AcademicYear[]>("/academic-years?limit=200"),
    ];

    if (isBgh) {
      promises.push(api.get<any>("/users?skip=0&limit=100"));
    }

    Promise.all(promises)
      .then(([sub, sem, y, usersList]) => {
        setSubjects(sub);
        setSemesters(sem);
        setYears(y);
        if (isBgh && usersList) {
          const list = Array.isArray(usersList) ? usersList : (usersList?.items || []);
          const teacherUsers = list.filter((u: any) => u.role !== "ADMIN" && u.role !== "PRINCIPAL");
          setTeachers(teacherUsers);
          if (teacherUsers.length > 0) {
            setCamTeacherId(teacherUsers[0].id);
          }
        }
        const targetYear = y.find((yr: any) => yr.name === "2025-2026") ?? y.find((yr: any) => yr.is_current) ?? y[0];
        setYearId(targetYear?.id ?? "");

        const currentSem = sem.find((s: any) => s.is_current) ?? sem[0];
        setSemesterId(currentSem?.id ?? "");

        // Ưu tiên tìm Học kỳ II thuộc niên khóa 2025-2026
        const sem2 = sem.find((s: any) =>
          s.academic_year_id === targetYear?.id &&
          (s.name.includes("2") || s.name.includes("II") || s.name.toLowerCase().includes("hk2"))
        ) ?? sem.find((s: any) => s.name.includes("2") || s.name.includes("II") || s.name.toLowerCase().includes("hk2"));

        setCamSemesterId(sem2?.id ?? currentSem?.id ?? "");

        // Chọn sẵn môn học nếu giáo viên bộ môn
        if (user?.subject_id) {
          setSubjectId(user.subject_id);
        } else if (sub.length > 0) {
          setSubjectId(sub[0].id);
        }
        if (sub.length > 0) {
          setCamSubjectId(sub[0].id);
        }
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Lỗi tải dữ liệu tham chiếu"))
      .finally(() => setLoading(false));
  };

  const fetchRecordings = () => {
    api.get<any[]>("/recordings")
      .then((data) => setRecordings(data))
      .catch((e) => setError("Lỗi tải danh sách bài giảng ghi âm"));
  };

  useEffect(() => {
    loadData();
    fetchRecordings();
  }, []);

  // Polling khi có task đang xử lý (pending / processing)
  useEffect(() => {
    const hasActiveTask = recordings.some(r => r.status === "processing" || r.status === "pending");
    if (!hasActiveTask) return;

    const timer = setInterval(() => {
      api.get<any[]>("/recordings")
        .then((data) => setRecordings(data))
        .catch((e) => console.error("Lỗi polling danh sách:", e));
    }, 5000);

    return () => clearInterval(timer);
  }, [recordings]);

  // Lấy các lớp học được phân công khi đổi niên khóa
  useEffect(() => {
    if (!yearId) return;
    api.get<ClassRow[]>(`/classes/accessible?academic_year_id=${yearId}`)
      .then((c) => {
        setClasses(c);
        if (c.length > 0) {
          setClassId(c[0].id);
          const filtered = c.filter(x => x.name === "7A1" || x.name === "7A2");
          const initCamClass = filtered.length > 0 ? filtered[0] : c[0];
          setCamClassId(initCamClass.id);
          setCamClass(initCamClass.name);
        }
      })
      .catch((e) => setError("Lỗi tải danh sách lớp học"));
  }, [yearId]);

  // Bộ lọc dữ liệu phía Client cho BGH
  const filteredRecordings = useMemo(() => {
    return recordings.filter((rec) => {
      const matchWeek = selectedWeek === "all" || String(rec.week) === selectedWeek;
      const matchTeacher = selectedTeacherName === "all" || rec.teacher_name === selectedTeacherName;
      return matchWeek && matchTeacher;
    });
  }, [recordings, selectedWeek, selectedTeacherName]);

  // Bộ danh sách cho dropdown lọc
  const weeksList = useMemo(() => {
    const weeks = recordings.map((r) => String(r.week));
    return Array.from(new Set(weeks)).sort((a, b) => parseInt(b, 10) - parseInt(a, 10));
  }, [recordings]);

  const teachersList = useMemo(() => {
    const teachers = recordings.map((r) => r.teacher_name).filter(Boolean);
    return Array.from(new Set(teachers));
  }, [recordings]);

  // Các chỉ số BGH dựa trên dữ liệu đã lọc
  const stats = useMemo(() => {
    const total = filteredRecordings.length;
    const processing = filteredRecordings.filter((r) => r.status === "processing" || r.status === "pending").length;
    const completed = filteredRecordings.filter((r) => r.status === "done").length;
    return { total, processing, completed };
  }, [filteredRecordings]);

  // Xử lý nộp file
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      showToast("Vui lòng chọn hoặc kéo thả file âm thanh!", "error");
      return;
    }
    if (!lessonName.trim()) {
      showToast("Vui lòng nhập tên tiết dạy / bài học!", "error");
      return;
    }

    const formData = new FormData();
    formData.append("subject_id", subjectId);
    formData.append("class_id", classId);
    formData.append("semester_id", semesterId);
    formData.append("lesson_name", lessonName);
    formData.append("period", String(period));
    formData.append("date", date);
    formData.append("week", String(week));
    formData.append("file", selectedFile);

    setUploading(true);
    try {
      await api.upload("/recordings", formData);
      setLessonName("");
      setSelectedFile(null);
      fetchRecordings();
      showToast("Nộp bài giảng thành công! Hệ thống đang xử lý phân tích AI ở nền.", "success");
    } catch (err: any) {
      showToast(err.message ?? "Lỗi khi nộp file ghi âm.", "error");
    } finally {
      setUploading(false);
    }
  };

  // Xem chi tiết báo cáo AI (Chỉ BGH)
  const handleViewDetails = async (rec: any) => {
    if (!isBgh) return;
    try {
      const data = await api.get<any>(`/recordings/${rec.id}`);
      setSelectedRecording(data);
      setActiveTab("report");
      setShowModal(true);
    } catch (err: any) {
      showToast(err.message ?? "Không thể xem chi tiết.", "error");
    }
  };



  // Yêu cầu phân tích lại
  // Yêu cầu phân tích lại
  const handleReanalyze = async (recId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();

    const triggerAction = async () => {
      try {
        await api.post(`/recordings/${recId}/analyze`);
        fetchRecordings();
        showToast("Đã gửi yêu cầu phân tích lại.", "success");
      } catch (err: any) {
        showToast(err.message ?? "Lỗi yêu cầu phân tích.", "error");
      }
    };

    askConfirmation(
      "Kích Hoạt Lại Phân Tích",
      "Bạn có muốn kích hoạt lại tiến trình phân tích AI cho tiết dạy này không?",
      triggerAction
    );
  };

  // Xóa ghi âm
  const handleDelete = async (recId: string, e: React.MouseEvent) => {
    e.stopPropagation();

    const triggerAction = async () => {
      try {
        await api.del(`/recordings/${recId}`);
        fetchRecordings();
        showToast("Xóa bản ghi âm bài giảng thành công.", "success");
        if (selectedRecording?.id === recId) {
          setShowModal(false);
        }
      } catch (err: any) {
        showToast(err.message ?? "Lỗi xóa bản ghi.", "error");
      }
    };

    askConfirmation(
      "Xóa Bài Giảng Vĩnh Viễn",
      "Bạn chắc chắn muốn xóa vĩnh viễn bài giảng ghi âm này? Hành động này sẽ xóa cả trên cơ sở dữ liệu và tệp tin đám mây.",
      triggerAction
    );
  };

  // Custom Audio Player Methods
  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
        setIsPlaying(false);
      } else {
        audioRef.current.play().then(() => setIsPlaying(true));
      }
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setVolume(val);
    if (audioRef.current) {
      audioRef.current.volume = val;
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setCurrentTime(val);
    if (audioRef.current) {
      audioRef.current.currentTime = val;
    }
  };

  const formatTime = (secs: number) => {
    if (isNaN(secs)) return "00:00";
    const minutes = Math.floor(secs / 60);
    const seconds = Math.floor(secs % 60);
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  };

  // Reset player when selection changes
  useEffect(() => {
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
  }, [selectedRecording]);

  // Hàm phát lại âm thanh từ một timestamp trên dòng thời gian
  const parseTimeToSeconds = (timeStr: string) => {
    const parts = timeStr.split(":");
    if (parts.length !== 2) return 0;
    const minutes = parseInt(parts[0], 10);
    const seconds = parseInt(parts[1], 10);
    return minutes * 60 + seconds;
  };

  const playFromTime = (timeStr: string) => {
    if (audioRef.current) {
      const seconds = parseTimeToSeconds(timeStr);
      audioRef.current.currentTime = seconds;
      setCurrentTime(seconds);
      audioRef.current.play().then(() => setIsPlaying(true));
    }
  };

  // (handleCameraExtract removed because extraction is now triggered directly by clicking on weekly timetable cells)

  const selectedClassMeta = useMemo(() => {
    return classroomMetadata[camClass] || { room: "Phòng 201", teacher: "Cô Lê Hoa", subject: "Tiếng Anh" };
  }, [camClass]);

  if (loading) {
    return <LoadingState message="Đang tải thông tin cổng ghi âm..." />;
  }

  return (
    <div className="p-6 space-y-6">
      {/* Khai báo style động trực tiếp trong React để đồng bộ keyframe của Option 5 */}
      <style>{`
        @keyframes bar-dance {
          0% { height: 10px; }
          100% { height: 28px; }
        }
        .animate-live-bar {
          animation: bar-dance 1.2s ease-in-out infinite alternate;
        }
      `}</style>

      {/* Header */}
      {isBgh ? (
        <div className="bg-gradient-to-r from-brand-900 to-slate-900 dark:from-slate-900 dark:to-brand-950 p-6 rounded-xl border border-slate-200 dark:border-slate-850 text-white flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-sm animate-in fade-in duration-300">
          <div className="space-y-1.5">
            <h3 className="font-bold text-sm md:text-base flex items-center gap-2">
              <Video className="w-5 h-5 text-emerald-400" />
              Trích xuất & Chấm điểm qua Camera thông minh.
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed max-w-2xl">
              Thay vì để giáo viên tự ghi âm và nộp file thủ công, BGH có thể trực tiếp chọn tiết học đã diễn ra. Hệ thống AI sẽ tự động truy vấn Cloud Camera để lấy tệp video MP4, chuyển đổi thành file âm thanh MP3 chất lượng cao, sau đó chạy WhisperX STT dịch văn bản và phân tích chất lượng sư phạm qua LLM.
            </p>
          </div>
          <div className="shrink-0 flex flex-col items-end">
            <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider flex items-center gap-1.5 select-none">
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></span> Camera Server Online
            </span>
            <span className="text-[9px] text-slate-450 mt-1 select-none">Version: CloudCam v2.4-AI</span>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between border-b border-slate-205 dark:border-slate-800 pb-4">
          <div>
            <h2 className="text-xl font-bold text-slate-800 dark:text-white flex items-center gap-2">
              <Mic className="w-5 h-5 text-brand-600" />
              Cổng Ghi Âm & Đánh Giá Tiết Dạy AI
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Trang giáo viên: Nộp file ghi âm tiết giảng và theo dõi trạng thái xử lý.
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-50 text-red-700 text-xs rounded-lg border border-red-200 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ============================================================
          WORKSPACE CHO BAN GIÁM HIỆU (ADMIN / PRINCIPAL)
         ============================================================ */}
      {isBgh && (
        <div className="space-y-6">

          {/* BGH Sub-tabs (Xem kết quả vs Trích xuất Camera) */}
          <div className="flex border-b border-slate-200 dark:border-slate-800 shrink-0">
            <button
              onClick={() => setBghTab("results")}
              className={`py-2.5 px-4 border-b-2 font-bold text-xs transition-all flex items-center gap-1.5 focus:outline-none cursor-pointer ${bghTab === "results"
                ? "border-brand-600 text-brand-600 dark:text-brand-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
            >
              <LayoutGrid className="w-3.5 h-3.5" />
              Xem kết quả đánh giá
            </button>
            <button
              onClick={() => setBghTab("camera")}
              className={`py-2.5 px-4 border-b-2 font-bold text-xs transition-all flex items-center gap-1.5 focus:outline-none relative cursor-pointer ${bghTab === "camera"
                ? "border-brand-600 text-brand-600 dark:text-brand-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
            >
              <Video className="w-3.5 h-3.5" />
              Trích xuất từ Camera
              <span className="absolute top-1.5 right-1 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-450 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
            </button>
          </div>

          {/* TAB 1: KẾT QUẢ ĐÁNH GIÁ */}
          {bghTab === "results" && (
            <div className="space-y-6 animate-in fade-in duration-300">
              {/* Stats Bar */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 flex items-center justify-between shadow-xs">
                  <div className="space-y-1">
                    <span className="text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase tracking-wider block">Tổng Bài Giảng Đã Nộp</span>
                    <h3 className="text-2xl font-extrabold text-slate-800 dark:text-white">{stats.total} tiết</h3>
                  </div>
                  <div className="w-10 h-10 rounded-xl bg-brand-50 dark:bg-brand-950/40 text-brand-700 dark:text-brand-400 flex items-center justify-center">
                    <Music className="w-5 h-5" />
                  </div>
                </div>

                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 flex items-center justify-between shadow-xs">
                  <div className="space-y-1">
                    <span className="text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase tracking-wider block">Đã hoàn thành AI</span>
                    <h3 className="text-2xl font-extrabold text-emerald-600 dark:text-emerald-450">{stats.completed} tiết</h3>
                  </div>
                  <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-450 flex items-center justify-center">
                    <CheckCircle className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                  </div>
                </div>

                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 flex items-center justify-between shadow-xs">
                  <div className="space-y-1">
                    <span className="text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase tracking-wider block">Đang phân tích AI</span>
                    <h3 className="text-2xl font-extrabold text-amber-500">{stats.processing} tiết</h3>
                  </div>
                  <div className="w-10 h-10 rounded-xl bg-amber-50 dark:bg-amber-950/40 text-amber-600 flex items-center justify-center">
                    <Loader className="w-5 h-5 animate-spin" />
                  </div>
                </div>
              </div>


              {/* BGH Filter Bar */}
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 rounded-xl shadow-xs">
                <div>
                  <h3 className="font-bold text-slate-800 dark:text-white text-sm flex items-center gap-2">
                    <LayoutGrid className="w-4.5 h-4.5 text-brand-600" />
                    Quản Lý Đánh Giá Tiết Học
                  </h3>
                  <p className="text-[10px] text-slate-455 dark:text-slate-500 mt-0.5">Hiển thị trực quan từng bài giảng dưới dạng các Card tương tự Camera</p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] font-bold text-slate-400 uppercase">Tuần:</span>
                    <select
                      value={selectedWeek}
                      onChange={(e) => setSelectedWeek(e.target.value)}
                      className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs px-2.5 py-1.5 focus:outline-none text-slate-700 dark:text-slate-300 font-semibold"
                    >
                      <option value="all">Tất cả các tuần</option>
                      {weeksList.map(w => (
                        <option key={w} value={w}>Tuần {w}</option>
                      ))}
                    </select>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] font-bold text-slate-400 uppercase">Giáo viên:</span>
                    <select
                      value={selectedTeacherName}
                      onChange={(e) => setSelectedTeacherName(e.target.value)}
                      className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs px-2.5 py-1.5 focus:outline-none text-slate-700 dark:text-slate-300 font-semibold"
                    >
                      <option value="all">Tất cả giáo viên</option>
                      {teachersList.map(t => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {/* Grid Lưới bài giảng kiểu Option 5 (Square Camera design) */}
              {filteredRecordings.length === 0 ? (
                <div className="text-center py-16 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
                  <p className="text-sm text-slate-400">Không tìm thấy bài giảng ghi âm nào khớp với bộ lọc.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5">
                  {filteredRecordings.map((rec) => {
                    // Định hình màu sắc cho visual top area theo điểm số (sáng sủa, tươi tắn)
                    const scoreVal = rec.score || 0.0;
                    const ratingColor = scoreVal >= 8.5
                      ? 'from-emerald-400 to-teal-500'
                      : (scoreVal < 7.0 ? 'from-rose-400 to-red-500' : 'from-sky-400 to-brand-500');

                    return (
                      <div
                        key={rec.id}
                        className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/85 rounded-xl overflow-hidden shadow-xs hover:shadow-md hover:border-brand-500 dark:hover:border-brand-500 transition-all duration-200 group flex flex-col justify-between relative"
                      >
                        {/* Visual Top Area */}
                        <div className="aspect-video relative overflow-hidden shrink-0 bg-slate-950 border-b border-slate-100 dark:border-slate-850">
                          {rec.status === "done" ? (
                            <div className={`absolute inset-0 bg-gradient-to-br ${ratingColor} flex flex-col items-center justify-center`}>
                              {/* Soundwave background effect (thin, white, opacity-15) */}
                              <div className="absolute inset-x-0 bottom-0 h-10 flex items-end justify-center gap-[2.5px] opacity-15 pointer-events-none select-none z-0">
                                {Array.from({ length: 42 }).map((_, idx) => {
                                  const heights = [10, 16, 24, 32, 20, 12, 8, 14, 28, 36, 18, 10, 12, 22, 30, 26, 14, 8, 16, 24, 20, 10, 12, 26, 34, 16, 8, 18, 22, 14, 10, 28, 32, 20, 12, 16, 24, 18, 10, 12];
                                  const h = heights[idx % heights.length];
                                  return (
                                    <span
                                      key={idx}
                                      className="w-[2.5px] bg-white rounded-t-sm"
                                      style={{ height: `${h * 0.8}px` }}
                                    />
                                  );
                                })}
                              </div>

                              <span className="text-white/70 uppercase text-[9px] font-bold tracking-wider z-10">Điểm chất lượng AI</span>
                              <span className="text-white text-3xl font-extrabold tracking-tight mt-0.5 z-10">{rec.score ? rec.score.toFixed(1) : "0.0"}<span className="text-sm font-normal opacity-80">/10</span></span>
                              {rec.engagement && (
                                <span className="text-white/90 text-[10px] font-semibold px-2 py-0.5 bg-white/10 rounded-full mt-1.5 z-10">Tương tác: {rec.engagement}</span>
                              )}
                            </div>
                          ) : rec.status === "processing" ? (
                            <div className="absolute inset-0 bg-gradient-to-br from-slate-900 to-slate-950 flex flex-col items-center justify-center">
                              <div className="flex items-end gap-1 h-6 mb-2">
                                <span className="w-1 bg-amber-500 rounded-full animate-live-bar" style={{ animationDelay: '0.1s', height: '12px' }}></span>
                                <span className="w-1 bg-amber-500 rounded-full animate-live-bar" style={{ animationDelay: '0.3s', height: '24px' }}></span>
                                <span className="w-1 bg-amber-500 rounded-full animate-live-bar" style={{ animationDelay: '0.5s', height: '8px' }}></span>
                                <span className="w-1 bg-amber-500 rounded-full animate-live-bar" style={{ animationDelay: '0.2s', height: '18px' }}></span>
                              </div>
                              <span className="text-amber-500 font-mono text-[9px] font-bold tracking-wider uppercase">Đang phân tích... {rec.progress}%</span>
                            </div>
                          ) : rec.status === "failed" ? (
                            <div className="absolute inset-0 bg-rose-955/80 flex flex-col items-center justify-center text-center p-2">
                              <AlertTriangle className="w-6 h-6 text-rose-500 mb-1" />
                              <span className="text-[10px] text-rose-400 font-bold uppercase tracking-wider block">Xử Lý Thất Bại</span>
                            </div>
                          ) : (
                            <div className="absolute inset-0 bg-slate-950 flex flex-col items-center justify-center text-center">
                              <Clock className="w-6 h-6 text-slate-500 animate-pulse mb-1" />
                              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Đang Chờ Xử Lý</span>
                            </div>
                          )}
                        </div>

                        {/* Content details body */}
                        <div className="p-4 flex-1 flex flex-col justify-between gap-3">
                          <div className="space-y-1">
                            <span className="text-[9.5px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">
                              {rec.class_name} • Tiết {rec.period}
                            </span>
                            <h4 className="font-bold text-xs text-slate-800 dark:text-white line-clamp-1 group-hover:text-brand-600 transition-colors" title={rec.lesson_name}>
                              {rec.lesson_name}
                            </h4>
                            <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium">
                              GV: <strong className="text-slate-700 dark:text-slate-350 font-semibold">{rec.teacher_name}</strong> • {rec.date}
                            </p>
                          </div>

                          {/* Action button or progress bar footer */}
                          <div className="pt-2 border-t border-slate-100 dark:border-slate-800 shrink-0">
                            {rec.status === "done" ? (
                              <button
                                onClick={() => handleViewDetails(rec)}
                                className="w-full py-1.5 bg-brand-50 hover:bg-brand-100 dark:bg-brand-950 dark:hover:bg-brand-900 border border-brand-200 dark:border-brand-900/50 text-brand-700 dark:text-brand-400 rounded-lg font-bold text-[11px] transition-colors flex items-center justify-center gap-1 shadow-2xs cursor-pointer"
                              >
                                <ShieldCheck className="w-3.5 h-3.5" /> Xem báo cáo AI
                              </button>
                            ) : rec.status === "failed" ? (
                              <button
                                onClick={(e) => handleReanalyze(rec.id, e)}
                                className="w-full py-1.5 bg-rose-50 hover:bg-rose-100 dark:bg-rose-955 dark:hover:bg-rose-900 border border-rose-200 dark:border-rose-900/50 text-rose-700 dark:text-rose-400 rounded-lg font-bold text-[11px] transition-colors flex items-center justify-center gap-1 shadow-2xs cursor-pointer"
                              >
                                <RotateCw className="w-3.5 h-3.5" /> Chạy lại AI
                              </button>
                            ) : (
                              <div className="space-y-1">
                                <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-455 font-mono">
                                  <span>{rec.status === "processing" ? "Giải mã WhisperX..." : "Đang chờ hàng đợi..."}</span>
                                  <span>{rec.progress}%</span>
                                </div>
                                <div className="w-full bg-slate-200 dark:bg-slate-800 h-1 rounded-full overflow-hidden">
                                  <div className="bg-brand-500 h-full transition-all duration-300" style={{ width: `${rec.progress}%` }}></div>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Action hover buttons */}
                        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 flex items-center gap-1 bg-white/95 dark:bg-slate-900/95 p-1 rounded-lg border border-slate-200 dark:border-slate-800 shadow-xs transition-opacity duration-200 z-20">
                          <button
                            title="Đánh giá lại AI"
                            onClick={(e) => handleReanalyze(rec.id, e)}
                            className="p-1.5 text-slate-500 hover:text-brand-600 hover:bg-slate-105 dark:hover:bg-slate-800 rounded transition-colors cursor-pointer"
                          >
                            <RotateCw className="w-3.5 h-3.5" />
                          </button>
                          <button
                            title="Xóa vĩnh viễn"
                            onClick={(e) => handleDelete(rec.id, e)}
                            className="p-1.5 text-slate-500 hover:text-red-650 hover:bg-slate-105 dark:hover:bg-slate-800 rounded transition-colors cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: TRÍCH XUẤT TỪ CAMERA (MOCK UI) */}
          {bghTab === "camera" && (
            <div className="space-y-6 animate-in fade-in duration-300">
              {/* Thanh chọn thông số ngang ở trên full trang */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl py-2 px-4 flex flex-wrap items-center justify-between gap-4 shadow-xs">
                <div className="flex flex-wrap items-center gap-4">
                  {/* Lớp học */}
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider select-none shrink-0">Lớp học & Phòng:</span>
                    <select
                      value={camClassId}
                      onChange={(e) => handleCamClassChange(e.target.value)}
                      className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs py-1.5 px-2.5 font-semibold text-slate-700 dark:text-slate-200 focus:outline-none min-w-[110px]"
                    >
                      {(() => {
                        const filtered = classes.filter(c => c.name === "7A1" || c.name === "7A2");
                        const displayClasses = filtered.length > 0 ? filtered : classes;
                        return displayClasses.map((c) => (
                          <option key={c.id} value={c.id}>
                            Lớp {c.name}
                          </option>
                        ));
                      })()}
                    </select>
                  </div>

                  {/* Tuần học */}
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider select-none shrink-0">Tuần học:</span>
                    <select
                      disabled
                      value={camWeek}
                      className="bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs py-1.5 px-2.5 font-semibold text-slate-450 dark:text-slate-400 cursor-not-allowed focus:outline-none min-w-[240px]"
                    >
                      <option value={28}>Tuần 28 (23/03/2026 - 27/03/2026)</option>
                    </select>
                  </div>
                </div>

                <div className="text-[10px] text-slate-400 dark:text-slate-500 italic select-none">
                  💡 Mẹo: Click trực tiếp vào ô tiết học để trích xuất & chấm điểm AI.
                </div>
              </div>

              {/* Two-column grid layout */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Column Left: Selector + Preview Monitor (1/3 size) */}
                <div className="lg:col-span-1 flex flex-col">
                  {/* Camera Live Screen HUD Simulation (KHOONG DUOC XOA - Dùng cho các cấu trúc HUD và mock camera)
                  <div
                    className="aspect-video rounded-xl border border-slate-300 dark:border-slate-800 relative overflow-hidden flex flex-col justify-between p-3 font-mono text-[9px] text-slate-200 select-none bg-cover bg-center shadow-xs"
                    style={{ backgroundImage: `url('/camera_mock.jpg')`, backgroundColor: '#020617' }}
                  >
                    <div className="absolute inset-0 bg-slate-950/50 pointer-events-none"></div>

                    <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-black/60 px-2 py-0.5 rounded text-[9px] font-mono border border-white/10 z-20">
                      <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full"></span>
                      <span className="text-emerald-400 font-bold uppercase tracking-wider">ONLINE</span>
                    </div>

                    <div className="absolute inset-2.5 pointer-events-none border border-white/5 rounded-xs">
                      <div className="absolute -top-1 -left-1 w-2.5 h-2.5 border-t border-l border-emerald-400"></div>
                      <div className="absolute -top-1 -right-1 w-2.5 h-2.5 border-t border-r border-emerald-400"></div>
                      <div className="absolute -bottom-1 -left-1 w-2.5 h-2.5 border-b border-l border-emerald-400"></div>
                      <div className="absolute -bottom-1 -right-1 w-2.5 h-2.5 border-b border-r border-emerald-400"></div>
                    </div>

                    <div className="flex justify-between items-start z-10 text-emerald-400 font-bold">
                      <div>
                        <span className="block">CAM-CLOUD-01A</span>
                        <span className="text-white/80 font-normal">{selectedClassMeta.room.toUpperCase()} ({camClass})</span>
                      </div>
                      <div className="text-right">
                        <span className="block">1080P @ 30FPS</span>
                        <span className="block text-white/80 font-normal">BITRATE: 4.8MBPS</span>
                      </div>
                    </div>

                    <div className="flex justify-between items-end z-10 mt-auto">
                      <div className="font-bold text-white/90">
                        <span className="block">DATE: {camDate}</span>
                        <span className="block text-emerald-400">TIME: {liveCamTime || "09:20:00 AM"}</span>
                      </div>
                      <div className="flex items-end gap-0.5 h-6 bg-black/55 px-1.5 py-1 rounded border border-white/10">
                        <span className="w-[2px] bg-emerald-500 rounded-full h-2"></span>
                        <span className="w-[2px] bg-emerald-500 rounded-full h-4"></span>
                        <span className="w-[2px] bg-emerald-500 rounded-full h-1"></span>
                        <span className="w-[2px] bg-emerald-500 rounded-full h-3"></span>
                        <span className="w-[2px] bg-emerald-500 rounded-full h-2"></span>
                        <span className="w-[2px] bg-emerald-500 rounded-full h-5"></span>
                        <Mic className="w-3 h-3 text-emerald-400 ml-1 shrink-0" />
                      </div>
                    </div>
                  </div>
                  */}

                  {/* Hàng chờ trích xuất & Trạng thái xử lý */}
                  <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-xs flex flex-col flex-1 min-h-0">
                    <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-855 pb-2 mb-2 shrink-0">
                      <h3 className="font-bold text-slate-800 dark:text-white text-xs flex items-center gap-2">
                        <ListOrdered className="w-4 h-4 text-brand-600" /> Hàng chờ trích xuất
                      </h3>
                      <span className="text-[10px] text-slate-455 font-mono">Có {mockCameraRequests.length} yêu cầu</span>
                    </div>

                    <div className="space-y-3 overflow-y-auto pr-1 flex-1 min-h-0">
                      {mockCameraRequests.length === 0 ? (
                        <div className="text-center py-6 text-slate-400 text-xs">Không có yêu cầu nào trong hàng chờ</div>
                      ) : (
                        mockCameraRequests.map((req) => {
                          let statusColor = "border-slate-350 dark:border-slate-700";
                          let statusBadge: React.ReactNode = null;
                          let actionBtn: React.ReactNode = null;

                          if (req.status === "done") {
                            statusColor = "border-emerald-500 dark:border-emerald-600";
                            statusBadge = (
                              <span className="bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-455 border border-emerald-200 dark:border-emerald-900/35 text-[10px] font-bold px-2 py-0.5 rounded-lg inline-flex items-center gap-1">
                                <Check className="w-3 h-3" /> Thành công
                              </span>
                            );
                            actionBtn = (
                              <button
                                onClick={() => handleViewDetails(req)}
                                className="shrink-0 py-1 px-2 bg-brand-50 hover:bg-brand-100 dark:bg-brand-950 dark:hover:bg-brand-900 border border-brand-200 dark:border-brand-900/50 text-brand-700 dark:text-brand-400 rounded-lg font-bold text-[10px] transition-colors flex items-center gap-1 shadow-2xs cursor-pointer"
                              >
                                <FileText className="w-3.5 h-3.5" /> Báo cáo
                              </button>
                            );
                          } else if (req.status === "processing") {
                            statusColor = "border-amber-500";
                            statusBadge = (
                              <span className="bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-455 border border-amber-205 dark:border-amber-900/35 text-[10px] font-bold px-2 py-0.5 rounded-lg inline-flex items-center gap-1.5 select-none">
                                <Loader className="w-3 h-3 animate-spin" /> Đang xử lý ({req.progress}%)
                              </span>
                            );
                          } else if (req.status === "failed") {
                            statusColor = "border-rose-500";
                            statusBadge = (
                              <span className="bg-rose-50 dark:bg-rose-955/40 text-rose-600 dark:text-rose-455 border border-rose-200 dark:border-rose-900/35 text-[10px] font-bold px-2 py-0.5 rounded-lg inline-flex items-center gap-1">
                                <AlertTriangle className="w-3 h-3" /> Lỗi kết nối
                              </span>
                            );
                            actionBtn = (
                              <div className="flex gap-1 shrink-0">
                                <button
                                  onClick={(e) => handleReanalyze(req.id, e)}
                                  className="py-1 px-1.5 bg-amber-50 hover:bg-amber-100 dark:bg-amber-950/40 dark:hover:bg-amber-900 border border-amber-200 dark:border-amber-900/35 text-amber-700 dark:text-amber-450 rounded-lg font-bold text-[9px] transition-colors flex items-center gap-1 cursor-pointer"
                                  title="Thử lại"
                                >
                                  <RotateCw className="w-3 h-3" /> Thử lại
                                </button>
                                <button
                                  onClick={(e) => handleDelete(req.id, e)}
                                  className="py-1 px-1.5 bg-rose-50 hover:bg-rose-100 dark:bg-rose-955/40 dark:hover:bg-rose-900 border border-rose-200 dark:border-rose-900/35 text-rose-700 dark:text-rose-400 rounded-lg font-bold text-[9px] transition-colors flex items-center gap-1 cursor-pointer"
                                  title="Xóa"
                                >
                                  <Trash2 className="w-3 h-3" /> Xóa
                                </button>
                              </div>
                            );
                          } else {
                            statusColor = "border-slate-200 dark:border-slate-800";
                            statusBadge = (
                              <span className="bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-450 border border-slate-250 dark:border-slate-700 text-[10px] font-bold px-2 py-0.5 rounded-lg inline-flex items-center gap-1">
                                Đang chờ
                              </span>
                            );
                          }

                          return (
                            <div
                              key={req.id}
                              className={`bg-slate-50 dark:bg-slate-900/40 border-l-4 ${statusColor} border-y border-r border-slate-200 dark:border-slate-800 rounded-xl p-3 space-y-2 transition-all hover:shadow-2xs`}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="space-y-1">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span className="text-[10px] font-bold bg-brand-50 dark:bg-brand-950 text-brand-700 dark:text-brand-450 px-2 py-0.5 rounded font-mono uppercase">
                                      {req.period} • {req.room}
                                    </span>
                                  </div>
                                  <p className="text-[10px] text-slate-700 dark:text-slate-200 font-semibold leading-tight">
                                    Môn: {req.subject} • GV: {req.teacher}
                                  </p>
                                  <div className="text-[9px] text-slate-400 font-medium">
                                    Ngày: {req.date} (ID: {req.id})
                                  </div>
                                </div>
                                <div className="flex flex-col items-end gap-1.5 shrink-0">
                                  {statusBadge}
                                  {actionBtn}
                                </div>
                              </div>

                              {req.status === "failed" && (
                                <div className="bg-rose-50 dark:bg-rose-955/20 text-rose-600 dark:text-rose-450 border border-rose-100 dark:border-rose-900/40 p-2 rounded-lg text-[9px] font-medium leading-normal">
                                  <AlertTriangle className="w-3 h-3 inline mr-1 -mt-0.5 text-rose-500" />
                                  {req.errorReason}
                                </div>
                              )}

                              {req.status === "processing" && (
                                <div className="space-y-1 pt-1 border-t border-slate-100 dark:border-slate-800">
                                  <div className="w-full bg-slate-200 dark:bg-slate-850 h-1 rounded-full overflow-hidden">
                                    <div className="bg-amber-500 h-full transition-all duration-300" style={{ width: `${req.progress}%` }}></div>
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                </div>

                {/* Column Right: Timetable + Request Queues (2/3 size) */}
                <div className="lg:col-span-2 flex flex-col">
                  {/* Thời khóa biểu tuần */}
                  <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm flex flex-col flex-grow">
                    <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800/80 pb-3">
                      <h3 className="font-bold text-slate-800 dark:text-white text-sm flex items-center gap-2">
                        <Calendar className="w-4.5 h-4.5 text-blue-600 dark:text-blue-500" /> Thời khóa biểu từ 23/03/2026 đến 27/03/2026
                      </h3>
                      <span className="text-xs text-slate-400 font-semibold select-none uppercase tracking-wider">Lớp {camClass}</span>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-center border-collapse">
                        <thead>
                          <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-400 dark:text-slate-500 text-[10px]">
                            <th className="p-3 text-center font-semibold text-slate-500 w-24">Tiết</th>
                            <th className="p-3 text-center">
                              <div className="font-semibold text-slate-700 dark:text-slate-300 text-[11px]">Thứ 2</div>
                              <div className="text-[9px] text-slate-400 font-normal mt-0.5">23/03</div>
                            </th>
                            <th className="p-3 text-center">
                              <div className="font-semibold text-slate-700 dark:text-slate-300 text-[11px]">Thứ 3</div>
                              <div className="text-[9px] text-slate-400 font-normal mt-0.5">24/03</div>
                            </th>
                            <th className="p-3 text-center">
                              <div className="font-semibold text-slate-700 dark:text-slate-300 text-[11px]">Thứ 4</div>
                              <div className="text-[9px] text-slate-400 font-normal mt-0.5">25/03</div>
                            </th>
                            <th className="p-3 text-center">
                              <div className="font-semibold text-slate-700 dark:text-slate-300 text-[11px]">Thứ 5</div>
                              <div className="text-[9px] text-slate-400 font-normal mt-0.5">26/03</div>
                            </th>
                            <th className="p-3 text-center">
                              <div className="font-semibold text-slate-700 dark:text-slate-300 text-[11px]">Thứ 6</div>
                              <div className="text-[9px] text-slate-400 font-normal mt-0.5">27/03</div>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {(() => {
                            const activeTimetable = camClass === "7A2" ? timetable7A2 : timetable7A1;
                            const periodLabels = [
                              { title: "Tiết 1", time: "07:30 - 08:15" },
                              { title: "Tiết 2", time: "08:25 - 09:10" },
                              { title: "Tiết 3", time: "09:20 - 10:05" },
                              { title: "Tiết 4", time: "10:15 - 11:00" },
                              { title: "Tiết 5", time: "11:10 - 11:55" }
                            ];
                            return activeTimetable.map((row, periodIdx) => (
                              <tr key={periodIdx} className="border-b border-slate-100 dark:border-slate-800/60 last:border-0 hover:bg-slate-50/20 dark:hover:bg-slate-800/5">
                                <td className="p-3 text-center font-bold bg-slate-50/20 dark:bg-slate-850/10 text-slate-650 dark:text-slate-400 border-r border-slate-50 dark:border-slate-855">
                                  <div className="font-bold text-slate-700 dark:text-slate-300 text-[11px]">{periodLabels[periodIdx].title}</div>
                                  <div className="text-[9px] text-slate-400 font-normal mt-0.5">{periodLabels[periodIdx].time}</div>
                                </td>
                                {row.map((cell, dayIdx) => {
                                  const isLocked = cell.status === "locked";

                                  const datesOfWeek = [
                                    "2026-03-23",
                                    "2026-03-24",
                                    "2026-03-25",
                                    "2026-03-26",
                                    "2026-03-27"
                                  ];
                                  const targetDateStr = datesOfWeek[dayIdx];

                                  const matchingRec = recordings.find(r =>
                                    r.class_name === camClass &&
                                    r.date?.startsWith(targetDateStr) &&
                                    r.period === cell.period
                                  );

                                  const isDone = matchingRec?.status === "done";
                                  const isPendingVms = matchingRec?.status === "processing" || matchingRec?.status === "pending";
                                  const isFailed = matchingRec?.status === "failed";
                                  const isNone = !matchingRec;

                                  const { sub, teacher } = getSubjectAndTeacherForCell(cell);
                                  const subjectName = cell.subject;
                                  const teacherName = isLocked ? "-" : (teacher?.full_name || "Chưa phân công");

                                  // Background & border themes matching the image
                                  let bgBorderTheme = "bg-transparent border-transparent";
                                  if (isDone && matchingRec?.score) {
                                    bgBorderTheme = "bg-emerald-50/40 dark:bg-emerald-950/15 border-emerald-200/70 dark:border-emerald-900/50 shadow-3xs";
                                  } else if (isPendingVms) {
                                    bgBorderTheme = "bg-amber-50/40 dark:bg-amber-950/15 border-amber-200/75 dark:border-amber-900/50 shadow-3xs";
                                  }

                                  // Status icon / badge matching the image legend
                                  let statusIndicator = null;
                                  if (subjectName === "Chào cờ" || subjectName === "Sinh hoạt lớp") {
                                    statusIndicator = null;
                                  } else if (matchingRec) {
                                    if (isDone) {
                                      if (matchingRec.score) {
                                        statusIndicator = (
                                          <div className="mt-1.5 inline-flex items-center gap-1 bg-emerald-100/70 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-350 font-bold px-2 py-0.5 rounded-full text-[9px] w-max mx-auto shadow-4xs select-none">
                                            ✓ AI: {matchingRec.score.toFixed(1)}
                                          </div>
                                        );
                                      } else {
                                        statusIndicator = (
                                          <span className="inline-flex items-center justify-center w-4 h-4 bg-emerald-500 text-white rounded-full text-[9px] font-bold mt-1.5 mx-auto shadow-4xs select-none">
                                            ✓
                                          </span>
                                        );
                                      }
                                    } else if (isPendingVms) {
                                      statusIndicator = (
                                        <div className="flex flex-col items-center mt-1">
                                          {matchingRec.score && (
                                            <div className="inline-flex items-center gap-1 bg-amber-100/70 dark:bg-amber-900/45 text-amber-700 dark:text-amber-350 font-bold px-2 py-0.5 rounded-full text-[9px] w-max mx-auto shadow-4xs select-none">
                                              AI: {matchingRec.score.toFixed(1)}
                                            </div>
                                          )}
                                          <span className="w-3.5 h-3.5 bg-amber-500 text-white rounded-full flex items-center justify-center text-[9px] font-bold mt-1.5 mx-auto shadow-4xs">
                                            <span className="w-1.5 h-1.5 bg-white rounded-full"></span>
                                          </span>
                                        </div>
                                      );
                                    } else if (isFailed) {
                                      statusIndicator = (
                                        <div className="mt-1 text-[9px] font-bold text-rose-500 dark:text-rose-455">
                                          Lỗi / Thử lại
                                        </div>
                                      );
                                    }
                                  } else {
                                    // Chưa trích xuất
                                    statusIndicator = (
                                      <Clock className="w-3.5 h-3.5 text-slate-300 dark:text-slate-600 mt-1.5 mx-auto" />
                                    );
                                  }

                                  return (
                                    <td
                                      key={dayIdx}
                                      onClick={() => handleCellClick(cell, dayIdx)}
                                      className="p-1 text-center cursor-pointer align-middle"
                                    >
                                      <div className={`w-full h-full min-h-[82px] flex flex-col justify-center p-2 rounded-xl border transition-all hover:bg-slate-50/80 dark:hover:bg-slate-800/20 hover:scale-[1.015] ${bgBorderTheme}`}>
                                        <div className="font-bold text-slate-850 dark:text-slate-200 text-[11px] leading-snug">
                                          {subjectName}
                                        </div>
                                        <div className="text-[9px] text-slate-450 dark:text-slate-500 font-medium mt-0.5 leading-normal">
                                          {teacherName}
                                        </div>
                                        {statusIndicator}
                                      </div>
                                    </td>
                                  );
                                })}
                              </tr>
                            ));
                          })()}
                        </tbody>
                      </table>
                    </div>

                    {/* Legend bar at the bottom matching the image exactly */}
                    <div className="flex flex-wrap items-center gap-6 text-[10px] text-slate-500 dark:text-slate-400 pt-4 border-t border-slate-100 dark:border-slate-800/60 mt-2">
                      <div className="flex items-center gap-1.5">
                        <span className="inline-flex items-center justify-center w-3.5 h-3.5 bg-emerald-500 text-white rounded-full text-[8px] font-bold shadow-4xs">✓</span>
                        <span>Đã trích xuất</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="inline-flex items-center justify-center w-3.5 h-3.5 bg-amber-500 text-white rounded-full text-[8px] shadow-4xs">
                          <span className="w-1.5 h-1.5 bg-white rounded-full"></span>
                        </span>
                        <span>Đang xử lý</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" />
                        <span>Chưa trích xuất</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 font-bold px-1.5 py-0.5 rounded text-[8px] border border-emerald-200/50">AI: ✦</span>
                        <span>Điểm chất lượng AI</span>
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            </div>
          )}

        </div>
      )}

      {/* ============================================================
          WORKSPACE CHO GIÁO VIÊN
         ============================================================ */}
      {!isBgh && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Cột 1: Form upload file ghi âm */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 space-y-4 shadow-xs">
            <h3 className="font-bold text-slate-800 dark:text-white text-sm border-b border-slate-100 dark:border-slate-855 pb-2 flex items-center gap-2">
              <UploadCloud className="w-4 h-4 text-brand-600" /> Nộp Bài Giảng Ghi Âm
            </h3>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Tên Tiết dạy / Bài dạy:</label>
                <input
                  type="text"
                  required
                  value={lessonName}
                  onChange={(e) => setLessonName(e.target.value)}
                  placeholder="Ví dụ: Unit 5 - Conditional sentences"
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs p-2.5 focus:ring-1 focus:ring-brand-500 focus:outline-none text-slate-800 dark:text-slate-100"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Lớp học:</label>
                  <select
                    value={classId}
                    onChange={(e) => setClassId(e.target.value)}
                    className="w-full bg-slate-50 dark:bg-slate-855 border border-slate-200 dark:border-slate-700 rounded-lg text-xs p-2.5 focus:outline-none text-slate-700 dark:text-slate-300 font-semibold"
                  >
                    {classes.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Môn học:</label>
                  <select
                    value={subjectId}
                    onChange={(e) => setSubjectId(e.target.value)}
                    disabled={!!user?.subject_id} // Khóa nếu GV đã có môn phụ trách cố định
                    className="w-full bg-slate-50 dark:bg-slate-855 border border-slate-200 dark:border-slate-700 rounded-lg text-xs p-2.5 focus:outline-none disabled:opacity-75 text-slate-700 dark:text-slate-300 font-semibold"
                  >
                    {subjects.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Tiết giảng (Số):</label>
                  <input
                    type="number"
                    required
                    min={1}
                    max={15}
                    value={period}
                    onChange={(e) => setPeriod(parseInt(e.target.value, 10))}
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs p-2.5 focus:outline-none text-slate-750 dark:text-slate-100 font-semibold"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Tuần học (Số):</label>
                  <input
                    type="number"
                    required
                    min={1}
                    max={52}
                    value={week}
                    onChange={(e) => setWeek(parseInt(e.target.value, 10))}
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs p-2.5 focus:outline-none text-slate-750 dark:text-slate-100 font-semibold"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Ngày dạy:</label>
                <input
                  type="date"
                  required
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs p-2.5 focus:outline-none text-slate-750 dark:text-slate-100 font-semibold"
                />
              </div>

              {/* Vùng chọn file */}
              <div
                onClick={() => document.getElementById("file-select")?.click()}
                className="border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-xl p-5 text-center hover:border-brand-500 cursor-pointer transition-colors"
              >
                <input
                  type="file"
                  id="file-select"
                  accept="audio/*"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <Music className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">
                  {selectedFile ? selectedFile.name : "Chọn file ghi âm bài giảng"}
                </span>
                <span className="text-[9px] text-slate-400 dark:text-slate-500 block mt-1">
                  Chấp nhận các định dạng âm thanh (.mp3, .wav, .m4a), tối đa 100MB
                </span>
              </div>

              <button
                type="submit"
                disabled={uploading}
                className="w-full py-2.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-xs font-bold transition-all shadow-sm flex items-center justify-center gap-2 cursor-pointer"
              >
                {uploading ? (
                  <>
                    <Loader className="w-4 h-4 animate-spin" /> Đang đẩy file lên Cloud...
                  </>
                ) : (
                  "Nộp ghi âm lên hệ thống"
                )}
              </button>
            </form>
          </div>

          {/* Cột 2: Bảng lịch sử nộp file cá nhân */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 space-y-4 shadow-xs lg:col-span-2 overflow-hidden flex flex-col">
            <h3 className="font-bold text-slate-800 dark:text-white text-sm border-b border-slate-100 dark:border-slate-855 pb-2 flex items-center gap-2">
              <History className="w-4 h-4 text-brand-600" /> Lịch Sử Nộp Bài Giảng Ghi Âm (Cá nhân)
            </h3>

            <div className="overflow-x-auto flex-1">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-400 font-bold uppercase text-[9px] tracking-wider">
                    <th className="py-3 px-3">Ngày dạy</th>
                    <th className="py-3 px-3">Tên tiết dạy</th>
                    <th className="py-3 px-3">Thông tin lớp</th>
                    <th className="py-3 px-3 text-center">Trạng thái</th>
                    <th className="py-3 px-3 text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {recordings.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-slate-400 italic">
                        Bạn chưa nộp ghi âm tiết học nào.
                      </td>
                    </tr>
                  ) : (
                    recordings.map((rec) => (
                      <tr key={rec.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="py-3 px-3 whitespace-nowrap text-slate-600 dark:text-slate-400">
                          {rec.date}
                        </td>
                        <td className="py-3 px-3 font-semibold text-slate-800 dark:text-slate-200">
                          {rec.lesson_name}
                        </td>
                        <td className="py-3 px-3 text-slate-600 dark:text-slate-400 whitespace-nowrap">
                          {rec.class_name} • {rec.subject_name} (Tiết {rec.period}, Tuần {rec.week})
                        </td>
                        <td className="py-3 px-3 text-center">
                          {rec.status === "done" ? (
                            <span className="bg-emerald-50 text-emerald-700 border border-emerald-100 px-2 py-0.5 rounded text-[10px] dark:bg-emerald-950/20 dark:text-emerald-400 dark:border-emerald-800 font-medium inline-flex items-center gap-1">
                              <CheckCircle className="w-3 h-3" /> Đã xử lý
                            </span>
                          ) : rec.status === "failed" ? (
                            <span className="bg-red-50 text-red-650 border border-red-100 px-2 py-0.5 rounded text-[10px] dark:bg-red-950/20 dark:text-red-400 dark:border-red-800 font-medium">
                              Thất bại
                            </span>
                          ) : (
                            <span className="bg-amber-50 text-amber-600 border border-amber-100 px-2 py-0.5 rounded text-[10px] dark:bg-amber-950/20 dark:text-amber-400 dark:border-amber-800 font-medium inline-flex items-center gap-1">
                              <Loader className="w-3 h-3 animate-spin" /> {rec.progress}%
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-3 text-right whitespace-nowrap">
                          <div className="inline-flex items-center gap-1.5">
                            {rec.status === "failed" && (
                              <button
                                onClick={(e) => handleReanalyze(rec.id, e)}
                                title="Thử lại"
                                className="p-1 text-slate-500 hover:text-brand-600 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors cursor-pointer"
                              >
                                <RotateCw className="w-3.5 h-3.5" />
                              </button>
                            )}
                            <button
                              onClick={(e) => handleDelete(rec.id, e)}
                              title="Xóa ghi âm"
                              className="p-1 text-slate-500 hover:text-red-650 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors cursor-pointer"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================
          SIDE RIGHT DRAWER CHI TIẾT ĐÁNH GIÁ AI & TRANSCRIPT (CHỈ BGH)
         ============================================================ */}
      {showModal && selectedRecording && (
        <>
          {/* Backdrop */}
          <div
            className="fixed -inset-10 bg-black/35 z-40 animate-in fade-in duration-200 cursor-pointer"
            onClick={() => setShowModal(false)}
          />
          {/* Side Right Drawer */}
          <div className="fixed top-0 right-0 h-full w-full sm:w-[500px] md:w-[600px] bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 rounded-l-2xl overflow-hidden shadow-2xl z-50 animate-in slide-in-from-right duration-350 ease-out flex flex-col">
            {/* Drawer Header */}
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shrink-0 bg-white dark:bg-slate-900">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-950 text-brand-600 dark:text-brand-400 flex items-center justify-center shadow-xs">
                  <FileText className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-800 dark:text-white text-base">
                    Đánh Giá Tiết Học: {selectedRecording.lesson_name}
                  </h3>
                  <p className="text-[11px] text-slate-455 dark:text-slate-500 mt-0.5">
                    Giáo viên: {selectedRecording.teacher_name} • Lớp {selectedRecording.class_name} (Tiết {selectedRecording.period}) • Lịch dạy: {selectedRecording.date} (Tuần {selectedRecording.week})
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={(e) => {
                    handleReanalyze(selectedRecording.id, e);
                    setShowModal(false);
                  }}
                  className="flex items-center gap-1 px-2.5 py-1.5 bg-slate-50 hover:bg-slate-100 dark:bg-slate-800 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-lg font-bold text-[10px] transition-colors cursor-pointer shadow-3xs"
                  title="Chạy lại phân tích WhisperX + LLM"
                >
                  <RotateCw className="w-3 h-3" />
                  Đánh giá lại AI
                </button>
                <button
                  onClick={() => setShowModal(false)}
                  className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Scrollable Content Area (Option 5 structure) */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-white dark:bg-slate-900">
              {/* Custom Audio Player Card (Option 5 visual style - exact replica) */}
              <div className="bg-slate-950 rounded-xl p-4 flex flex-col gap-3 border border-slate-800">
                <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
                  <span>Trình phát âm thanh bài giảng MP3</span>
                  <span>{formatTime(duration)}</span>
                </div>

                {/* Waveform Simulation (Option 5 visual excellence) */}
                <div className="h-10 flex items-center justify-center gap-[3px] px-2 opacity-80">
                  {Array.from({ length: 35 }).map((_, i) => {
                    const heights = [12, 18, 14, 10, 16, 22, 28, 20, 14, 18, 24, 30, 26, 18, 12, 16, 22, 26, 20, 14, 16, 22, 28, 20, 12, 8, 14, 20, 18, 12, 16, 24, 20, 12, 10];
                    const height = heights[i % heights.length];
                    return (
                      <span
                        key={i}
                        className="w-[3px] bg-sky-500 rounded-full transition-all duration-300"
                        style={{ height: `${height}px` }}
                      />
                    );
                  })}
                </div>

                {/* Progress Seek Bar */}
                <div className="w-full py-1">
                  <input
                    type="range"
                    min="0"
                    max={duration || 100}
                    value={currentTime}
                    onChange={handleSeek}
                    className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-sky-500 focus:outline-none"
                    style={{
                      background: `linear-gradient(to right, #0ea5e9 0%, #0ea5e9 ${duration ? (currentTime / duration) * 100 : 0}%, #1e293b ${duration ? (currentTime / duration) * 100 : 0}%, #1e293b 100%)`
                    }}
                  />
                </div>

                {/* Native hidden audio element */}
                <audio
                  ref={audioRef}
                  src={selectedRecording.audio_file_url}
                  onTimeUpdate={handleTimeUpdate}
                  onLoadedMetadata={handleLoadedMetadata}
                  onEnded={() => setIsPlaying(false)}
                  className="hidden"
                />

                {/* Custom Player Controls */}
                <div className="flex items-center justify-between mt-1">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={togglePlay}
                      className="p-2 bg-brand-600 text-white rounded-full hover:bg-brand-700 transition-colors cursor-pointer"
                    >
                      {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
                    </button>
                    <span className="text-xs font-mono text-slate-350">
                      {formatTime(currentTime)} / {formatTime(duration)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Volume2 className="w-4 h-4 text-slate-400" />
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={volume}
                      onChange={handleVolumeChange}
                      className="w-16 h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-brand-500"
                    />
                  </div>
                </div>
              </div>

              {/* Tab Navigation & Tab Content Section */}
              <div className="space-y-4">
                <div className="flex border-b border-slate-200 dark:border-slate-800">
                  <button
                    onClick={() => setActiveTab("report")}
                    className={`py-2 px-3.5 border-b-2 -mb-[1px] font-bold text-xs transition-all cursor-pointer ${activeTab === "report"
                      ? "border-brand-600 text-brand-600 dark:text-brand-400"
                      : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                      }`}
                  >
                    Báo cáo Đánh giá AI
                  </button>
                  {/* 
                  <button
                    onClick={() => setActiveTab("transcript")}
                    className={`py-2 px-3.5 border-b-2 -mb-[1px] font-bold text-xs transition-all cursor-pointer ${activeTab === "transcript"
                      ? "border-brand-600 text-brand-600 dark:text-brand-400"
                      : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                      }`}
                  >
                    Văn bản dịch WhisperX
                  </button>
                  */}
                  <button
                    onClick={() => setActiveTab("source")}
                    className={`py-2 px-3.5 border-b-2 -mb-[1px] font-bold text-xs transition-all cursor-pointer ${activeTab === "source"
                      ? "border-brand-600 text-brand-600 dark:text-brand-400"
                      : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                      }`}
                  >
                    Nguồn File MP3
                  </button>
                </div>

                {/* TAB 1: Báo cáo Đánh giá AI */}
                {activeTab === "report" && (
                  <div className="space-y-5">
                    {/* Metrics */}
                    <div className="grid grid-cols-3 gap-4">
                      <div className="bg-slate-50 dark:bg-slate-800/40 p-3 rounded-lg border border-slate-200 dark:border-slate-800 text-center">
                        <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold">Điểm Đánh Giá</span>
                        <span className="text-xl font-extrabold text-brand-600 dark:text-brand-400 block mt-1">
                          {selectedRecording.score ? selectedRecording.score.toFixed(1) : "0.0"}<span className="text-xs text-slate-400">/10</span>
                        </span>
                      </div>
                      <div className="bg-slate-50 dark:bg-slate-800/40 p-3 rounded-lg border border-slate-200 dark:border-slate-800 text-center">
                        <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold">Mức tương tác</span>
                        <span className="text-xl font-extrabold text-emerald-600 dark:text-emerald-400 block mt-1">
                          {selectedRecording.engagement || "0%"}
                        </span>
                      </div>
                      <div className="bg-slate-50 dark:bg-slate-800/40 p-3 rounded-lg border border-slate-200 dark:border-slate-800 text-center">
                        <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold">Xếp hạng</span>
                        <span className={`text-sm font-extrabold block mt-2 ${selectedRecording.rank === "EXCELLENT"
                          ? "text-emerald-605 dark:text-emerald-450"
                          : selectedRecording.rank === "NEEDS_IMPROVEMENT"
                            ? "text-rose-500"
                            : "text-brand-600 dark:text-brand-400"
                          }`}>
                          {RANK_LABELS[selectedRecording.rank] || selectedRecording.rank}
                        </span>
                      </div>
                    </div>

                    {/* LLM Evaluation */}
                    <div className="bg-slate-50 dark:bg-slate-850 p-4 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2 text-xs leading-relaxed">
                      <strong className="font-bold text-slate-800 dark:text-slate-200 block text-xs flex items-center gap-1 select-none">
                        🏆 Nhận Xét Sư Phạm từ AI Agent:
                      </strong>
                      <div className="mt-2 text-slate-700 dark:text-slate-350 prose prose-slate dark:prose-invert max-w-none text-xs leading-relaxed prose-headings:font-bold prose-headings:text-slate-800 dark:prose-headings:text-white">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            a: ({ href, children }) => {
                              if (href && href.startsWith("#t=")) {
                                const timeStr = href.replace("#t=", "");
                                return (
                                  <button
                                    onClick={() => playFromTime(timeStr)}
                                    className="inline-flex items-center gap-0.5 px-1.5 py-0.5 mx-0.5 rounded bg-brand-50 hover:bg-brand-100 text-brand-700 dark:bg-brand-950 dark:hover:bg-brand-900 border border-brand-200 dark:border-brand-800 text-[11px] font-bold font-mono cursor-pointer transition-colors shadow-3xs"
                                    title={`Click để phát từ ${timeStr}`}
                                  >
                                    <Play className="w-2.5 h-2.5 fill-current shrink-0" />
                                    {children}
                                  </button>
                                );
                              }
                              return (
                                <a href={href} className="text-brand-600 hover:underline" target="_blank" rel="noopener noreferrer">
                                  {children}
                                </a>
                              );
                            }
                          }}
                        >
                          {preprocessMarkdownTimestamps(selectedRecording.ai_report || "*Không có nội dung đánh giá.*")}
                        </ReactMarkdown>
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 2: Văn bản dịch WhisperX (Tạm ẩn) */}
                {/* 
                {activeTab === "transcript" && (
                  <div className="space-y-4">
                    <p className="text-xs text-slate-400 italic mb-2">
                      Mẹo: Click vào nút Play hình tròn cạnh mỗi mốc thời gian để nghe đoạn thu âm tương ứng của người nói.
                    </p>

                    {!selectedRecording.transcript || selectedRecording.transcript.length === 0 ? (
                      <p className="text-xs text-slate-400 italic">Không tìm thấy dữ liệu văn bản dịch.</p>
                    ) : (
                      <div className="relative border-l-2 border-slate-200 dark:border-slate-800 ml-4 pl-6 space-y-5">
                        {selectedRecording.transcript.map((seg: any, idx: number) => (
                          <div key={idx} className="relative group/time">
                            <button
                              onClick={() => playFromTime(seg.time)}
                              className="absolute -left-[35px] top-0 w-[18px] h-[18px] rounded-full bg-white dark:bg-slate-900 border-2 border-brand-500 text-brand-600 flex items-center justify-center hover:bg-brand-600 hover:text-white transition-all cursor-pointer shadow-xs"
                            >
                              <Play className="w-2.5 h-2.5 ml-0.5 fill-current" />
                            </button>

                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span className="text-[10px] font-bold text-brand-600 dark:text-brand-400 bg-brand-50 dark:bg-brand-950/40 px-1.5 py-0.5 rounded">
                                  {seg.time}
                                </span>
                                <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                                  {seg.speaker}
                                </span>
                              </div>
                              <p className="text-xs text-slate-600 dark:text-slate-400 bg-white dark:bg-slate-950 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800/80 leading-relaxed shadow-3xs">
                                {seg.text}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                */}

                {/* TAB 3: Nguồn File MP3 */}
                {activeTab === "source" && (
                  <div className="space-y-4 py-2">
                    <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                      Thông tin tệp tin âm thanh tiết giảng gốc được tải lên và lưu trữ trên Cloud Storage:
                    </p>
                    <div className="bg-slate-50 dark:bg-slate-850 p-4 border border-slate-200 dark:border-slate-800 rounded-xl space-y-3">
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-[10px] text-slate-400 uppercase font-bold block">Tên tệp tin</span>
                          <span className="font-mono text-slate-700 dark:text-slate-350 break-all select-all block mt-0.5">
                            {selectedRecording.audio_file_url.split("/").pop()}
                          </span>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-400 uppercase font-bold block">Dung lượng tệp</span>
                          <span className="font-semibold text-slate-700 dark:text-slate-300 block mt-0.5">N/A</span>
                        </div>
                      </div>
                      <div className="text-xs border-t border-slate-200 dark:border-slate-800 pt-3">
                        <span className="text-[10px] text-slate-400 uppercase font-bold block">Đường dẫn tệp tin trên Cloud</span>
                        <span className="font-mono text-slate-700 dark:text-slate-300 break-all select-all block mt-0.5">
                          {selectedRecording.audio_file_url}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Toast Notification Component */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-[100] animate-in slide-in-from-bottom-5 duration-300">
          <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg backdrop-blur-md ${toast.type === "success"
            ? "bg-emerald-50/90 border-emerald-200 text-emerald-800 dark:bg-emerald-950/90 dark:border-emerald-800 dark:text-emerald-300"
            : toast.type === "error"
              ? "bg-rose-50/90 border-rose-200 text-rose-800 dark:bg-rose-955/90 dark:border-rose-800 dark:text-rose-300"
              : "bg-blue-50/90 border-blue-200 text-blue-800 dark:bg-blue-950/90 dark:border-blue-800 dark:text-blue-300"
            }`}>
            {toast.type === "success" ? (
              <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0" />
            ) : toast.type === "error" ? (
              <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0" />
            ) : (
              <Loader className="w-4 h-4 text-blue-500 animate-spin shrink-0" />
            )}
            <span className="text-xs font-semibold">{toast.message}</span>
            <button
              onClick={() => setToast(null)}
              className="ml-2 text-slate-400 hover:text-slate-655 p-0.5 rounded cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Reusable Confirmation Modal Component */}
      <ConfirmModal
        isOpen={!!confirmModal?.isOpen}
        title={confirmModal?.title || ""}
        message={confirmModal?.message || ""}
        onConfirm={confirmModal?.onConfirm || (() => {})}
        onCancel={() => setConfirmModal(null)}
      />
    </div>
  );
}

// Helper to pre-process timestamp patterns in markdown text to make them interactive
const preprocessMarkdownTimestamps = (text: string) => {
  if (!text) return "";

  // Sử dụng Regex loại trừ để không khớp các mốc thời gian đã nằm trong markdown link
  // Group 1: link mốc thời gian đã tạo ([00:00](#t=00:00))
  // Group 2: các link markdown thông thường ([text](url))
  // Group 3: mốc thời gian trần dạng MM:SS
  return text.replace(/(\[.*?\]\(#t=\d{2}:\d{2}\))|(\[.*?\]\(.*?\))|\b(\d{2}:\d{2})\b/g, (match, g1, g2, g3) => {
    if (g1 || g2) {
      return match; // Giữ nguyên link cũ
    }
    return `[${g3}](#t=${g3})`; // Tạo link tương tác cho mốc thời gian trần
  });
};
