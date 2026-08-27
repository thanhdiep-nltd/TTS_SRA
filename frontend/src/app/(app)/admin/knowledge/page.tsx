"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Clock,
  Database,
  FileUp,
  HardDrive,
  Loader2,
  RefreshCw,
  Sparkles,
  UploadCloud,
  X,
} from "lucide-react";
import SearchableSelect from "@/components/SearchableSelect";
import { api } from "@/lib/api";

interface IngestResponse {
  dag_run_id: string;
  s3_key: string;
  state: string;
}

interface IngestItem {
  id: string;
  filename: string;
  mon: string;
  lop: string;
  chuong: string;
  state: "queued" | "running" | "success" | "failed";
  uploadedAt: string;
}

const MON_OPTIONS = [
  { value: "toan", label: "Toán học (TOAN)" },
  { value: "van", label: "Ngữ văn (VAN)" },
  { value: "khtn", label: "Khoa học tự nhiên (KHTN)" },
  { value: "su_dia", label: "Lịch sử & Địa lí (SU_DIA)" },
  { value: "tieng_anh", label: "Tiếng Anh (TIENG_ANH)" },
  { value: "tin_hoc", label: "Tin học (TIN_HOC)" },
  { value: "gdcd", label: "Giáo dục công dân (GDCD)" },
];

const LOP_OPTIONS = [
  { value: "6", label: "Khối 6" },
  { value: "7", label: "Khối 7" },
  { value: "8", label: "Khối 8" },
  { value: "9", label: "Khối 9" },
  { value: "10", label: "Khối 10" },
  { value: "11", label: "Khối 11" },
  { value: "12", label: "Khối 12" },
];

export default function AdminKnowledgePage() {
  const [mon, setMon] = useState<string>("toan");
  const [lop, setLop] = useState<string>("6");
  const [chuong, setChuong] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [history, setHistory] = useState<IngestItem[]>([]);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      if (!f.name.toLowerCase().endsWith(".pdf")) {
        setError("Chỉ chấp nhận file PDF sách giáo khoa.");
        setSelectedFile(null);
        return;
      }
      setSelectedFile(f);
      setError(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const f = e.dataTransfer.files[0];
      if (!f.name.toLowerCase().endsWith(".pdf")) {
        setError("Chỉ chấp nhận file PDF sách giáo khoa.");
        return;
      }
      setSelectedFile(f);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError("Vui lòng chọn file PDF sách giáo khoa cần tải lên.");
      return;
    }

    setUploading(true);
    setError(null);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("mon", mon);
    formData.append("lop", lop);
    if (chuong) formData.append("chuong", chuong);

    try {
      const res = await api.upload<IngestResponse>("/knowledge/upload", formData);

      const newItem: IngestItem = {
        id: res.dag_run_id || `dag-${Date.now()}`,
        filename: selectedFile.name,
        mon,
        lop,
        chuong: chuong || "Toàn bộ sách",
        state: (res.state as any) || "queued",
        uploadedAt: new Date().toLocaleString("vi-VN"),
      };

      setHistory((prev) => [newItem, ...prev]);
      setSuccessMsg(
        `Tải lên thành công! Pipeline Airflow đã được kích hoạt (DAG Run: ${res.dag_run_id}). Dữ liệu đang được chunking & index vào Qdrant.`
      );
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (e: any) {
      setError(e?.message ?? "Lỗi khi tải lên sách giáo khoa.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-[1500px] mx-auto space-y-6">
      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-brand-50 dark:bg-brand-950/50 text-brand-600 dark:text-brand-400 border border-brand-100 dark:border-brand-900/50">
              <Database className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
              Quản lý Kho Tri Thức & Sách Giáo Khoa (RAG Ingestion)
            </h2>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Nạp tài liệu Sách Giáo Khoa chuẩn (PDF) lên MinIO & Vector Database (Qdrant) để AI tra cứu chứng cứ học thuật.
          </p>
        </div>
      </header>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Upload Form Card (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
              <FileUp className="w-4 h-4 text-brand-600" />
              <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                Tải lên Sách Giáo Khoa mới
              </h3>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1 block">
                  Môn học <span className="text-rose-500">*</span>
                </label>
                <SearchableSelect
                  options={MON_OPTIONS}
                  value={mon}
                  onChange={setMon}
                  placeholder="Chọn môn học..."
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1 block">
                  Khối lớp <span className="text-rose-500">*</span>
                </label>
                <SearchableSelect
                  options={LOP_OPTIONS}
                  value={lop}
                  onChange={setLop}
                  placeholder="Chọn khối lớp..."
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1 block">
                  Chương / Tập / Mô tả (Tùy chọn)
                </label>
                <input
                  type="text"
                  value={chuong}
                  onChange={(e) => setChuong(e.target.value)}
                  placeholder="Ví dụ: Tập 1 - Chương 1 Số học"
                  className="w-full px-3.5 py-2 rounded-xl text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-850 text-slate-800 dark:text-slate-200 focus:outline-hidden focus:ring-2 focus:ring-brand-500"
                />
              </div>

              {/* Drag Drop Zone */}
              <div>
                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1 block">
                  Tệp Sách Giáo Khoa (PDF) <span className="text-rose-500">*</span>
                </label>
                <div
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-colors ${
                    selectedFile
                      ? "border-brand-500 bg-brand-50/20 dark:bg-brand-950/20"
                      : "border-slate-200 dark:border-slate-700 hover:border-brand-400 hover:bg-slate-50 dark:hover:bg-slate-800/40"
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  {selectedFile ? (
                    <div className="space-y-1">
                      <BookOpen className="w-8 h-8 text-brand-600 mx-auto" />
                      <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate max-w-xs mx-auto">
                        {selectedFile.name}
                      </p>
                      <p className="text-xs text-slate-400">
                        {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-1.5 text-slate-500 dark:text-slate-400">
                      <UploadCloud className="w-8 h-8 text-slate-400 mx-auto" />
                      <p className="text-xs font-medium">
                        Kéo thả file PDF vào đây hoặc <span className="text-brand-600 font-semibold">chọn file</span>
                      </p>
                      <p className="text-[11px] text-slate-400">Định dạng hỗ trợ: PDF (tối đa 100MB)</p>
                    </div>
                  )}
                </div>
              </div>

              {error && (
                <div className="flex items-start gap-2 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              {successMsg && (
                <div className="flex items-start gap-2 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-700 dark:text-emerald-300">
                  <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{successMsg}</span>
                </div>
              )}

              <button
                onClick={handleUpload}
                disabled={uploading || !selectedFile}
                className="w-full py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold shadow-sm transition-all disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {uploading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Đang tải lên & nạp Vector DB...
                  </>
                ) : (
                  <>
                    <UploadCloud className="w-4 h-4" />
                    Tải lên & Kích hoạt RAG Ingest
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Guidelines Box */}
          <div className="p-4 rounded-2xl bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/40 text-xs space-y-2 text-indigo-900 dark:text-indigo-200">
            <span className="font-bold flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              Quy trình xử lý RAG tự động:
            </span>
            <ul className="list-disc list-inside space-y-1 text-slate-600 dark:text-slate-300 text-[11px]">
              <li>Tải file lên MinIO Object Storage theo đường dẫn phân cấp.</li>
              <li>Bóc tách OCR & cấu trúc mục lục (Heading 1/2/3).</li>
              <li>Cắt chunking theo từng bài học kèm metadata môn & khối.</li>
              <li>Embedding vector đa chiều và nạp vào Qdrant Collection.</li>
            </ul>
          </div>
        </div>

        {/* History / Status Table (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-slate-500" />
                <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                  Lịch sử nạp Sách Giáo Khoa vào Vector DB
                </h3>
              </div>
              <span className="text-xs text-slate-400">{history.length} tài liệu</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                    <th className="px-5 py-3">Tài liệu SGK</th>
                    <th className="px-5 py-3">Môn & Khối</th>
                    <th className="px-5 py-3">Chương / Phạm vi</th>
                    <th className="px-5 py-3">Trạng thái RAG</th>
                    <th className="px-5 py-3">Thời gian</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                  {history.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-5 py-8 text-center text-slate-400 text-xs">
                        <Database className="w-8 h-8 mx-auto text-slate-300 dark:text-slate-700 mb-2" />
                        Chưa có tài liệu nào được nạp trong phiên này. Hãy chọn môn, khối và tải lên tệp PDF ở khung bên trái.
                      </td>
                    </tr>
                  ) : (
                    history.map((item) => {
                      const monLabel = MON_OPTIONS.find((m) => m.value === item.mon)?.label || item.mon;
                      return (
                        <tr
                          key={item.id}
                          className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                        >
                          <td className="px-5 py-3.5 font-medium text-slate-800 dark:text-slate-200 max-w-[200px] truncate">
                            {item.filename}
                          </td>
                          <td className="px-5 py-3.5 text-xs text-slate-600 dark:text-slate-300">
                            {monLabel} — Khối {item.lop}
                          </td>
                          <td className="px-5 py-3.5 text-xs text-slate-500 max-w-[150px] truncate">
                            {item.chuong || "Toàn bộ"}
                          </td>
                          <td className="px-5 py-3.5">
                            {item.state === "success" ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                                <CheckCircle2 className="w-3 h-3" /> Đã Index (Sẵn sàng)
                              </span>
                            ) : item.state === "running" ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
                                <Loader2 className="w-3 h-3 animate-spin" /> Đang nhúng Vector...
                              </span>
                            ) : item.state === "queued" ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                                <Clock className="w-3 h-3" /> Đang chờ xử lý
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
                                <AlertCircle className="w-3 h-3" /> Lỗi
                              </span>
                            )}
                          </td>
                          <td className="px-5 py-3.5 text-xs text-slate-400 font-mono">
                            {item.uploadedAt}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
