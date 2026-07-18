import { useState, useRef } from "react";
import { Upload, X, FileDown, Loader2, CheckCircle2, AlertTriangle, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";

interface PreviewError {
  row: number;
  student_code: string;
  student_name: string;
  column: string;
  value_received: string;
  error_message: string;
}

interface PreviewRow {
  student_id: string;
  student_code: string;
  student_name: string;
  scores: Record<string, number | null>;
}

interface PreviewResponse {
  success: boolean;
  total_rows: number;
  valid_rows_count: number;
  invalid_rows_count: number;
  errors: PreviewError[];
  preview_data: PreviewRow[];
}

interface ImportScoreModalProps {
  classId: string;
  subjectId: string;
  semesterId: string;
  className: string;
  subjectName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function ImportScoreModal({
  classId,
  subjectId,
  semesterId,
  className,
  subjectName,
  onClose,
  onSuccess,
}: ImportScoreModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDownloadTemplate = async () => {
    try {
      setLoading(true);
      setError(null);
      const blob = await api.blob(`/scores/import/template?class_id=${classId}&subject_id=${subjectId}&semester_id=${semesterId}`);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Mau_nhap_diem_Lop_${className}_Mon_${subjectName}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Không thể tải file mẫu.");
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setPreview(null);
      setError(null);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
      setPreview(null);
      setError(null);
    }
  };

  const handlePreview = async () => {
    if (!file) return;
    try {
      setLoading(true);
      setError(null);
      const formData = new FormData();
      formData.append("class_id", classId);
      formData.append("subject_id", subjectId);
      formData.append("semester_id", semesterId);
      formData.append("file", file);

      const res = await api.upload<PreviewResponse>("/scores/import/preview", formData);
      setPreview(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Không thể phân tích dữ liệu tệp.");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!preview) return;
    try {
      setLoading(true);
      setError(null);

      // Chuyển đổi dữ liệu scores: { "REGULAR_1": 9.5 } thành mảng record phẳng
      interface ConfirmRecord {
        student_id: string;
        score_category: string;
        column_index: number;
        value: number | null;
      }
      const records: ConfirmRecord[] = [];
      preview.preview_data.forEach((row) => {
        Object.entries(row.scores).forEach(([key, val]) => {
          const lastUnderscore = key.lastIndexOf("_");
          const score_category = key.substring(0, lastUnderscore);
          const column_index = parseInt(key.substring(lastUnderscore + 1), 10);

          records.push({
            student_id: row.student_id,
            score_category,
            column_index,
            value: val,
          });
        });
      });

      const payload = {
        class_id: classId,
        subject_id: subjectId,
        semester_id: semesterId,
        records,
      };

      const res = await api.post<{ success: boolean; message: string }>("/scores/import/confirm", payload);
      if (res.success) {
        onSuccess();
        onClose();
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi khi lưu điểm vào cơ sở dữ liệu.");
    } finally {
      setLoading(false);
    }
  };

  const hasErrors = preview && preview.errors.length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div 
        className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h3 className="font-bold text-lg text-slate-900 dark:text-white">Nhập điểm từ file Excel</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Lớp {className} · Môn {subjectName}
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 flex-1 overflow-y-auto space-y-5">
          {error && (
            <div className="flex items-start gap-2.5 p-3.5 rounded-xl bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Step 1: Download Template */}
          <div className="bg-slate-50 dark:bg-slate-800/40 p-4 rounded-xl border border-slate-100 dark:border-slate-800 flex items-center justify-between gap-4">
            <div>
              <h4 className="text-sm font-semibold text-slate-900 dark:text-white">1. Tải tệp tin Excel mẫu</h4>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Nhận tệp tin Excel điền sẵn thông tin học sinh và định dạng của lớp {className}.
              </p>
            </div>
            <button
              type="button"
              onClick={handleDownloadTemplate}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-750 text-xs font-semibold text-slate-700 dark:text-slate-200 shadow-sm transition-all disabled:opacity-50 cursor-pointer"
            >
              <FileDown className="w-4 h-4 text-brand-500" />
              <span>Tải file mẫu</span>
            </button>
          </div>

          {/* Step 2: Upload Area */}
          <div className="space-y-2.5">
            <h4 className="text-sm font-semibold text-slate-900 dark:text-white">2. Tải lên tệp Excel đã nhập điểm</h4>
            <div
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl p-8 text-center hover:border-brand-500 dark:hover:border-brand-500 transition-colors cursor-pointer bg-slate-50/50 dark:bg-slate-950/20"
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept=".xlsx"
                className="hidden"
              />
              <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2.5" />
              {file ? (
                <div>
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{file.name}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    {(file.size / 1024).toFixed(1)} KB · Nhấp để thay đổi
                  </p>
                </div>
              ) : (
                <div>
                  <p className="text-sm text-slate-600 dark:text-slate-300 font-medium">
                    Kéo thả file Excel vào đây, hoặc click để chọn
                  </p>
                  <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                    Chỉ hỗ trợ định dạng Excel (.xlsx) tiêu chuẩn.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Preview Panel */}
          {preview && (
            <div className="space-y-3.5 border-t border-slate-100 dark:border-slate-800 pt-5">
              {/* Summary Stats */}
              <div className="flex items-center gap-3">
                <h4 className="text-sm font-semibold text-slate-900 dark:text-white">Kết quả kiểm tra tệp:</h4>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400 border border-emerald-250 dark:border-emerald-500/20">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>Hợp lệ: {preview.valid_rows_count}/{preview.total_rows} dòng</span>
                  </span>
                  {hasErrors && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-450 border border-rose-250 dark:border-rose-500/20">
                      <AlertTriangle className="w-3 h-3" />
                      <span>Lỗi: {preview.invalid_rows_count} dòng</span>
                    </span>
                  )}
                </div>
              </div>

              {/* Error list */}
              {hasErrors ? (
                <div className="border border-rose-100 dark:border-rose-550/20 rounded-xl overflow-hidden">
                  <div className="bg-rose-50/50 dark:bg-rose-500/5 px-4 py-2 border-b border-rose-100 dark:border-rose-550/20 text-rose-700 dark:text-rose-350 text-xs font-semibold flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>Phát hiện lỗi nhập liệu. Giáo viên cần sửa lại các dòng này trong Excel để lưu.</span>
                  </div>
                  <div className="overflow-x-auto max-h-48 scrollbar-thin">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-bold sticky top-0">
                        <tr>
                          <th className="px-4 py-2 border-b border-slate-100 dark:border-slate-800">Dòng</th>
                          <th className="px-4 py-2 border-b border-slate-100 dark:border-slate-800">Học sinh</th>
                          <th className="px-4 py-2 border-b border-slate-100 dark:border-slate-800 font-medium">Mã HS</th>
                          <th className="px-4 py-2 border-b border-slate-100 dark:border-slate-800">Cột điểm</th>
                          <th className="px-4 py-2 border-b border-slate-100 dark:border-slate-800 text-center">Giá trị</th>
                          <th className="px-4 py-2 border-b border-slate-100 dark:border-slate-800 text-rose-600 dark:text-rose-400">Lỗi chi tiết</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {preview.errors.map((err, i) => (
                          <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                            <td className="px-4 py-2 font-semibold text-slate-500">{err.row}</td>
                            <td className="px-4 py-2 font-medium text-slate-900 dark:text-slate-100">{err.student_name}</td>
                            <td className="px-4 py-2 text-slate-500">{err.student_code}</td>
                            <td className="px-4 py-2 text-slate-600 dark:text-slate-350">{err.column}</td>
                            <td className="px-4 py-2 text-center font-mono font-medium text-slate-600 dark:text-slate-350">{err.value_received}</td>
                            <td className="px-4 py-2 text-rose-600 dark:text-rose-400 font-medium">{err.error_message}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-emerald-50/50 dark:bg-emerald-500/5 border border-emerald-100 dark:border-emerald-500/20 text-emerald-800 dark:text-emerald-450 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 flex-shrink-0 text-emerald-550" />
                  <span className="font-medium">
                    Tệp Excel của bạn hoàn toàn hợp lệ! Sẵn sàng cập nhật điểm số cho {preview.valid_rows_count} học sinh.
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 rounded-b-2xl flex items-center justify-between">
          <div className="text-xs text-slate-400 dark:text-slate-500">
            * Chỉ ghi đè lên các đầu điểm đã điền.
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm font-semibold rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 cursor-pointer"
            >
              Hủy bỏ
            </button>

            {!preview ? (
              <button
                type="button"
                onClick={handlePreview}
                disabled={loading || !file}
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold rounded-lg bg-brand-600 hover:bg-brand-500 text-white shadow-sm transition-all disabled:opacity-50 cursor-pointer"
              >
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                <span>Kiểm tra dữ liệu</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={handleConfirm}
                disabled={loading || hasErrors || preview.valid_rows_count === 0}
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm transition-all disabled:opacity-50 cursor-pointer"
              >
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                <span>Xác nhận lưu</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
