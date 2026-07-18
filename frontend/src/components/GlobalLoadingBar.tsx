"use client";

import { useApiBusy } from "@/lib/useApiBusy";

/**
 * Thanh tải mảnh ở đỉnh trang, tự hiện khi có bất kỳ request API nào đang chạy
 * (đọc bộ đếm in-flight toàn cục từ lib/api) — báo người dùng "ứng dụng đang xử lý".
 */
export default function GlobalLoadingBar() {
  const busy = useApiBusy();
  if (!busy) return null;
  return <div className="global-loading-bar" role="progressbar" aria-label="Đang tải" aria-busy="true" />;
}
