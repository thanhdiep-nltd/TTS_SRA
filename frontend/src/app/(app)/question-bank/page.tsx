"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Plus, Sparkles } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import ChapterLessonSelect from "@/components/ChapterLessonSelect";
import { LoadingState } from "@/components/Loading";
import SearchableSelect, { type Option } from "@/components/SearchableSelect";
import CalibrationPanel from "@/components/question-bank/CalibrationPanel";
import CreateQuestionModal from "@/components/question-bank/CreateQuestionModal";
import GenerateQuestionsModal from "@/components/question-bank/GenerateQuestionsModal";
import QuestionDetailDrawer from "@/components/question-bank/QuestionDetailDrawer";
import { useCurriculumTree } from "@/lib/useCurriculumUnits";
import {
  BLOOM_OPTIONS,
  ITEM_STATUS_LABELS,
  ITEM_STATUS_STYLE,
  QUESTION_BANK_ROLES,
  QUESTION_REVIEW_ROLES,
  QUESTION_TYPE_LABELS,
  type ItemStatus,
  type QuestionItemListPage,
  type QuestionItemRow,
  type QuestionProvenance,
  type Subject,
} from "@/lib/types";

type Tab = "ALL" | ItemStatus | "NEEDS_REVIEW" | "CALIBRATION";

const TABS: { key: Tab; label: string }[] = [
  { key: "ALL", label: "Tất cả" },
  { key: "DRAFT", label: "Chờ duyệt" },
  { key: "APPROVED", label: "Đã duyệt" },
  { key: "REJECTED", label: "Bị từ chối" },
  { key: "NEEDS_REVIEW", label: "⚠️ Cần rà soát kỹ" },
  { key: "CALIBRATION", label: "📈 Hiệu chỉnh kho" },
];

const GRADE_OPTIONS: Option[] = [6, 7, 8, 9, 10, 11, 12].map((g) => ({ value: String(g), label: `Khối ${g}` }));
const PAGE_SIZE = 20;
// NEEDS_REVIEW lọc client-side trên toàn bộ tập khớp filter -> lấy nguyên trang lớn nhất cho
// phép (100) thay vì phân trang thật; nếu kho > 100 câu/bộ lọc, tab này có thể bỏ sót — chấp
// nhận đánh đổi vì đây là view quét chéo, không phải trang duyệt tuần tự.
const NEEDS_REVIEW_LIMIT = 100;

// Câu cần rà soát kỹ = BẤT KỲ tín hiệu mềm nào bật: tự giải lại lệch, Bloom lệch, critic thấp, nghi trùng.
function needsReview(p?: QuestionProvenance): boolean {
  if (!p) return false;
  return (
    p.self_consistency === "mismatch" ||
    p.bloom_check === "mismatch" ||
    (p.critic != null && p.critic.score <= 6) ||
    !!p.duplicate_of
  );
}

export default function QuestionBankPage() {
  const { user } = useAuth();
  const canManage = !!user && QUESTION_BANK_ROLES.includes(user.role);
  const canReview = !!user && QUESTION_REVIEW_ROLES.includes(user.role);
  const isAdmin = user?.role === "ADMIN";

  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [items, setItems] = useState<QuestionItemRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [subjectId, setSubjectId] = useState("");
  const [gradeNumber, setGradeNumber] = useState("");
  const [unitId, setUnitId] = useState("");
  const [bloomLevel, setBloomLevel] = useState("");
  const [tab, setTab] = useState<Tab>("ALL");

  // Đổi bộ lọc/tab -> về trang 1 (trang cũ có thể không còn hợp lệ với tập kết quả mới).
  useEffect(() => setPage(1), [subjectId, gradeNumber, unitId, bloomLevel, tab]);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showGenerate, setShowGenerate] = useState(false);

  useEffect(() => {
    api.get<Subject[]>("/subjects?limit=200").then(setSubjects).catch(() => {});
  }, []);

  // GV bộ môn/Trưởng bộ môn khóa về môn phụ trách của mình — chỉ ADMIN được chọn môn khác.
  useEffect(() => {
    if (!isAdmin && user?.subject_id) setSubjectId(user.subject_id);
  }, [isAdmin, user?.subject_id]);

  // Chương/bài học PHẢI lọc theo ĐÚNG môn + khối đang chọn (server-side) — tránh lặp lại bug
  // "Trưởng BM Toán thấy lẫn chủ đề của KHTN".
  const tree = useCurriculumTree(subjectId, gradeNumber);

  // Chủ đề đã chọn có thể không còn hợp lệ khi đổi môn/khối.
  useEffect(() => setUnitId(""), [subjectId, gradeNumber]);

  const unitNameMap = useMemo(() => {
    const m = new Map<string, string>();
    tree.chapters.forEach((c) => m.set(c.id, c.name));
    tree.lessonsByChapter.forEach((lessons) => lessons.forEach((l) => m.set(l.id, l.name)));
    return m;
  }, [tree]);

  const loadItems = useCallback(() => {
    if (tab === "CALIBRATION") return; // tab này tự fetch riêng (xem CalibrationPanel)
    if (!subjectId) return;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ subject_id: subjectId });
    if (gradeNumber) params.set("grade_number", gradeNumber);
    if (unitId) params.set("unit_id", unitId);
    if (bloomLevel) params.set("bloom_level", bloomLevel);
    if (tab !== "ALL" && tab !== "NEEDS_REVIEW") params.set("status", tab);
    if (tab === "NEEDS_REVIEW") {
      params.set("limit", String(NEEDS_REVIEW_LIMIT));
    } else {
      params.set("page", String(page));
      params.set("limit", String(PAGE_SIZE));
    }
    api
      .get<QuestionItemListPage>(`/question-bank/items?${params.toString()}`)
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Không tải được ngân hàng câu hỏi"))
      .finally(() => setLoading(false));
  }, [subjectId, gradeNumber, unitId, bloomLevel, tab, page]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  // Sau khi bấm "Sinh câu hỏi" (dù đóng modal ngay), tự dò câu mới ở CẤP TRANG mỗi 5s — nhưng
  // CHỈ kiểm tra nhẹ (không setLoading, không đụng UI), và CHỈ cập nhật list ĐÚNG 1 LẦN ngay khi
  // thật sự thấy câu mới (so với ảnh chụp id lúc bắt đầu chờ), rồi dừng poll ngay — không phải
  // load lại liên tục suốt 2 phút như bản trước.
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startPendingCheck = useCallback(() => {
    if (!subjectId) return;
    if (pollRef.current) clearInterval(pollRef.current); // huỷ lượt chờ trước đó nếu có (sinh tiếp lần 2)
    const since = Date.now();
    const knownIds = new Set(items.map((i) => i.id));
    // Luôn dò ở trang 1 (câu mới sắp theo created_at DESC nên luôn nổi lên đầu) — phát hiện xong
    // gọi loadItems() để nạp lại ĐÚNG trang GV đang xem, không ghi đè bằng dữ liệu trang 1 sai lệch.
    const params = new URLSearchParams({ subject_id: subjectId, page: "1", limit: String(PAGE_SIZE) });
    if (gradeNumber) params.set("grade_number", gradeNumber);
    if (unitId) params.set("unit_id", unitId);
    if (bloomLevel) params.set("bloom_level", bloomLevel);
    if (tab !== "ALL" && tab !== "NEEDS_REVIEW") params.set("status", tab);
    const url = `/question-bank/items?${params.toString()}`;

    pollRef.current = setInterval(async () => {
      if (Date.now() - since > 120_000) {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
        return;
      }
      try {
        const fresh = await api.get<QuestionItemListPage>(url);
        if (fresh.items.some((it) => !knownIds.has(it.id))) {
          loadItems(); // cập nhật DUY NHẤT 1 lần, đúng lúc có câu mới
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch {
        // lỗi tạm thời — thử lại lượt sau, không báo ồn ào
      }
    }, 5000);
  }, [subjectId, gradeNumber, unitId, bloomLevel, tab, items, loadItems]);

  useEffect(() => () => {
    if (pollRef.current) clearInterval(pollRef.current);
  }, []);

  const visibleItems = useMemo(() => {
    if (tab !== "NEEDS_REVIEW") return items;
    return items.filter((i) => needsReview(i.provenance));
  }, [items, tab]);

  if (!canManage) {
    return (
      <div className="p-8">
        <div className="max-w-md mx-auto text-center py-16 text-slate-500 dark:text-slate-400">
          Bạn không có quyền truy cập ngân hàng câu hỏi.
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white">Ngân hàng câu hỏi</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Soạn, duyệt và quản lý câu hỏi dùng để ráp đề thi chính thức.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowGenerate(true)}
            disabled={!subjectId}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-semibold bg-accent-600 text-white hover:bg-accent-700 disabled:opacity-50"
          >
            <Sparkles className="w-4 h-4" /> Sinh câu AI
          </button>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            disabled={!subjectId}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-semibold bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
          >
            <Plus className="w-4 h-4" /> Tạo câu thủ công
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
        {isAdmin ? (
          <SearchableSelect
            label="Môn"
            value={subjectId}
            onChange={setSubjectId}
            options={subjects.map((s) => ({ value: s.id, label: s.name }))}
            className="w-48"
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
          value={gradeNumber}
          onChange={setGradeNumber}
          options={GRADE_OPTIONS}
          className="w-32"
        />
        <ChapterLessonSelect
          subjectId={subjectId}
          gradeNumber={gradeNumber}
          value={unitId}
          onChange={setUnitId}
          className="w-[26rem]"
        />
        <SearchableSelect
          label="Mức Bloom"
          value={bloomLevel}
          onChange={setBloomLevel}
          options={BLOOM_OPTIONS}
          className="w-40"
        />
      </div>

      <div className="flex gap-1.5 border-b border-slate-200 dark:border-slate-800">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3.5 py-2 text-sm font-medium border-b-2 -mb-px transition ${
              tab === t.key
                ? "border-brand-600 text-brand-600 dark:text-brand-400"
                : "border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
          {error}
        </div>
      )}

      {tab === "CALIBRATION" && subjectId ? (
        <CalibrationPanel subjectId={subjectId} gradeNumber={gradeNumber || undefined} canReview={canReview} />
      ) : !subjectId ? (
        <div className="text-center py-16 text-slate-400 text-sm">Chọn môn để xem ngân hàng câu hỏi.</div>
      ) : loading ? (
        <LoadingState message="Đang tải ngân hàng câu hỏi…" />
      ) : visibleItems.length === 0 ? (
        <div className="text-center py-16 text-slate-400 text-sm">
          Chưa có câu hỏi nào — Sinh câu bằng AI hoặc tạo thủ công.
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium">Câu hỏi</th>
                <th className="text-left px-4 py-2.5 font-medium">Chủ đề</th>
                <th className="text-left px-4 py-2.5 font-medium">Bloom</th>
                <th className="text-left px-4 py-2.5 font-medium">Loại</th>
                <th className="text-left px-4 py-2.5 font-medium">Nguồn</th>
                <th className="text-left px-4 py-2.5 font-medium">Trạng thái</th>
                <th className="text-left px-4 py-2.5 font-medium">Đã dùng</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {visibleItems.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => setSelectedId(item.id)}
                  className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40"
                >
                  <td className="px-4 py-2.5 max-w-[320px]">
                    <p className="truncate text-slate-800 dark:text-slate-100">{item.stem}</p>
                    {needsReview(item.provenance) && (
                      <span className="inline-flex items-center gap-1 mt-1 text-[11px] font-semibold text-accent-600 dark:text-accent-400">
                        ⚠️ Cần rà soát kỹ
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400">
                    {unitNameMap.get(item.unit_id) ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400">{item.bloom_level}</td>
                  <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400">
                    {QUESTION_TYPE_LABELS[item.question_type]}
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400">
                    {item.source === "AI_GENERATED" ? "🤖 AI" : item.source === "MANUAL" ? "Thủ công" : "Nhập"}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ITEM_STATUS_STYLE[item.status]}`}>
                      {ITEM_STATUS_LABELS[item.status]}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400">
                    {item.times_used} lần
                    {item.exposure_at && <span className="ml-1 text-accent-600 dark:text-accent-400">⚠️</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab !== "CALIBRATION" && tab !== "NEEDS_REVIEW" && subjectId && total > 0 && (
        <div className="flex items-center justify-between text-sm text-slate-500 dark:text-slate-400">
          <span>{total} câu hỏi</span>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="p-1.5 rounded-lg disabled:opacity-40 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span>
              Trang {page}/{Math.max(1, Math.ceil(total / PAGE_SIZE))}
            </span>
            <button
              disabled={page >= Math.max(1, Math.ceil(total / PAGE_SIZE))}
              onClick={() => setPage((p) => p + 1)}
              className="p-1.5 rounded-lg disabled:opacity-40 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {selectedId && (
        <QuestionDetailDrawer
          itemId={selectedId}
          canReview={canReview}
          onClose={() => setSelectedId(null)}
          onChanged={loadItems}
        />
      )}
      {showCreate && subjectId && (
        <CreateQuestionModal
          subjectId={subjectId}
          gradeNumber={gradeNumber ? Number(gradeNumber) : undefined}
          onClose={() => setShowCreate(false)}
          onCreated={loadItems}
        />
      )}
      {showGenerate && subjectId && (
        <GenerateQuestionsModal
          subjectId={subjectId}
          gradeNumber={gradeNumber ? Number(gradeNumber) : undefined}
          onClose={() => setShowGenerate(false)}
          onSubmitted={startPendingCheck}
          onGenerated={loadItems}
        />
      )}
    </div>
  );
}
