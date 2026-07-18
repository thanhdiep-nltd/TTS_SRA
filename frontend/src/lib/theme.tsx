"use client";

import { useCallback, useSyncExternalStore } from "react";

type Theme = "light" | "dark";

// Nguồn sự thật của theme là class .dark trên <html> (do inline script ở layout áp trước paint).
// Dùng useSyncExternalStore để: (1) SSR + lần hydrate đầu luôn trả "light" (khớp nhau, không
// hydration mismatch); (2) sau hydrate đọc DOM thật và cập nhật. Không setState-trong-effect.
const listeners = new Set<() => void>();

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
}

function getSnapshot(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

function getServerSnapshot(): Theme {
  return "light";
}

function applyTheme(next: Theme): void {
  document.documentElement.classList.toggle("dark", next === "dark");
  localStorage.setItem("theme", next);
  listeners.forEach((l) => l());
}

// Giữ nguyên API cũ: layout vẫn bọc <ThemeProvider> (nay chỉ là passthrough).
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function useTheme(): { theme: Theme; toggle: () => void } {
  const theme = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const toggle = useCallback(() => {
    applyTheme(document.documentElement.classList.contains("dark") ? "light" : "dark");
  }, []);
  return { theme, toggle };
}
