import { Suspense } from "react";
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import { InlineScript } from "@/components/InlineScript";
import GlobalLoadingBar from "@/components/GlobalLoadingBar";
import { PageTransition } from "@/components/PageTransition";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "SchoolAI Analytics — Trợ Lý Phân Tích Học Tập",
  description: "Hệ thống phân tích kết quả học tập toàn trường cho Ban Giám Hiệu",
};

// Đặt class .dark trước khi paint để tránh nháy theme (FOUC) — pattern chuẩn của Next/next-themes.
// AN TOÀN XSS: chuỗi này là HẰNG SỐ do lập trình viên kiểm soát, KHÔNG nội suy dữ liệu người dùng.
// Giá trị localStorage 'theme' chỉ được so sánh với 'dark' để bật/tắt class, KHÔNG bao giờ
// được ghi (inject) vào DOM dưới dạng HTML. Tuyệt đối không đưa input người dùng vào chuỗi này.
const themeScript = `(function(){try{var t=localStorage.getItem('theme');if(!t){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}if(t==='dark'){document.documentElement.classList.add('dark');}}catch(e){}})();`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="vi"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased bg-slate-100 dark:bg-slate-950`}
      suppressHydrationWarning
    >
      <head>
        <InlineScript html={themeScript} />
      </head>
      <body className="min-h-full font-sans bg-slate-100 dark:bg-slate-950" suppressHydrationWarning>
        <Suspense fallback={null}>
          <PageTransition />
        </Suspense>
        <GlobalLoadingBar />
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
