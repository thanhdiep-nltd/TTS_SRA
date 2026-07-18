import { Loader2 } from "lucide-react";

// Spinner cơ bản dùng chung (màu thương hiệu).
export function Spinner({ className = "w-5 h-5" }: { className?: string }) {
  return <Loader2 className={`animate-spin text-brand-500 ${className}`} />;
}

// Khối "đang tải" toàn vùng kèm thông điệp — dùng khi chưa có dữ liệu để hiển thị.
export function LoadingState({ message = "Đang tải dữ liệu…", className = "" }: {
  message?: string; className?: string;
}) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 py-16 text-slate-500 dark:text-slate-400 ${className}`}>
      <Spinner className="w-8 h-8" />
      <p className="text-sm font-medium">{message}</p>
    </div>
  );
}

// Lớp phủ mờ lên nội dung đang có (khi tải lại) — giữ dữ liệu cũ, báo đang xử lý.
// Đặt trong một phần tử cha có class "relative".
export function LoadingOverlay({ message = "Đang tải…" }: { message?: string }) {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-white/55 dark:bg-slate-950/55 backdrop-blur-[1px]">
      <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-md text-sm font-medium text-slate-600 dark:text-slate-300">
        <Spinner className="w-4 h-4" /> {message}
      </div>
    </div>
  );
}
