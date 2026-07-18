"use client";

import { usePageTransition } from "@/hooks/usePageTransition";
import Image from "next/image";
import { useEffect, useState } from "react";

export function PageTransition() {
  const { isLoading } = usePageTransition();
  const [show, setShow] = useState(true);
  const [isFadingOut, setIsFadingOut] = useState(false);

  useEffect(() => {
    if (!isLoading) {
      // Bắt đầu hiệu ứng fade out và slide up
      setIsFadingOut(true);
      
      // Chờ animation hoàn thành (500ms) trước khi unmount khỏi DOM
      const timer = setTimeout(() => {
        setShow(false);
      }, 500);
      return () => clearTimeout(timer);
    } else {
      // Khi bắt đầu tải trang mới, reset lại trạng thái hiển thị
      setShow(true);
      setIsFadingOut(false);
    }
  }, [isLoading]);

  // Giải phóng DOM khi không tải
  if (!show) return null;

  return (
    <div
      className={`fixed inset-0 z-[9999] flex items-center justify-center bg-slate-900 transition-all duration-500 ease-out
        ${isFadingOut ? "opacity-0 -translate-y-8 scale-105 pointer-events-none" : "opacity-100 translate-y-0 scale-100"}
      `}
      aria-busy="true"
      aria-label="Đang tải trang..."
    >
      <div className="relative flex flex-col items-center justify-center">
        {/* Vòng lặp loading mỏng xoay tròn bao quanh Logo */}
        <div className="absolute w-36 h-36 border-[3px] border-slate-700 border-t-blue-500 border-r-blue-500/50 rounded-full animate-spin"></div>
        
        {/* Hiệu ứng nhịp thở (pulsing) cho khu vực Logo */}
        <div className="animate-pulse flex items-center justify-center bg-slate-800 rounded-full w-28 h-28 shadow-2xl shadow-blue-500/20 z-10">
          <Image
            src="/logo.svg"
            alt="Loading..."
            width={64}
            height={64}
            className="w-16 h-16"
            priority // Đảm bảo logo preloader được tải ưu tiên
          />
        </div>
      </div>
    </div>
  );
}
