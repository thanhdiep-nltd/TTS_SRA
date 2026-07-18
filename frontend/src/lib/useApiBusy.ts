"use client";

import { useSyncExternalStore } from "react";

import { getInflightCount, subscribeInflight } from "@/lib/api";

/** True khi đang có ít nhất một request API chạy (đọc từ bộ đếm in-flight toàn cục). */
export function useApiBusy(): boolean {
  return useSyncExternalStore(
    subscribeInflight,
    () => getInflightCount() > 0,
    () => false,
  );
}
