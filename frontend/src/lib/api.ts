// Client API: gắn Bearer token, chuẩn hóa lỗi. Dùng trong Client Components.

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN_KEY = "ai20k_access_token";
const REFRESH_KEY = "ai20k_refresh_token";

export function getToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
}
export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}
export function getRefresh(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem(REFRESH_KEY) : null;
}
export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Đếm số request đang chạy + phát sự kiện để thanh tải toàn cục (GlobalLoadingBar) hiển thị.
export const API_INFLIGHT_EVENT = "api:inflight";
let inFlight = 0;
function notifyInflight(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(API_INFLIGHT_EVENT, { detail: inFlight }));
  }
}
function startRequest(): void { inFlight += 1; notifyInflight(); }
function endRequest(): void { inFlight = Math.max(0, inFlight - 1); notifyInflight(); }

// Cho phép component đọc trạng thái "đang có request" qua useSyncExternalStore.
export function subscribeInflight(cb: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(API_INFLIGHT_EVENT, cb);
  return () => window.removeEventListener(API_INFLIGHT_EVENT, cb);
}
export function getInflightCount(): number {
  return inFlight;
}

// Nếu access token hết hạn (401), thử refresh 1 lần rồi phát lại request gốc. Nhiều request
// 401 cùng lúc chỉ trigger 1 lần gọi /auth/refresh (dùng chung promise) để tránh xoay vòng token.
let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  const refresh = getRefresh();
  if (!refresh) return false;
  if (!refreshPromise) {
    refreshPromise = fetch(`${BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    })
      .then(async (res) => {
        if (!res.ok) return false;
        const data = await res.json().catch(() => null);
        if (!data?.access_token || !data?.refresh_token) return false;
        setTokens(data.access_token, data.refresh_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

function redirectToLogin(): void {
  clearTokens();
  if (typeof window !== "undefined") window.location.href = "/login";
}

async function apiFetch<T>(path: string, options: RequestInit = {}, isRetry = false): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  startRequest();
  try {
    const res = await fetch(`${BASE}/api/v1${path}`, { ...options, headers });

    if (res.status === 401 && !isRetry && getRefresh()) {
      const refreshed = await tryRefreshToken();
      if (refreshed) return apiFetch<T>(path, options, true);
      redirectToLogin();
      throw new ApiError(401, "Phiên đăng nhập đã hết hạn");
    }

    if (res.status === 204) return undefined as T;

    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = data?.detail ?? `Lỗi kết nối (${res.status})`;
      throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data as T;
  } finally {
    endRequest();
  }
}

// Upload multipart (KHÔNG set Content-Type — browser tự thêm boundary).
async function apiUpload<T>(path: string, form: FormData, isRetry = false): Promise<T> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  startRequest();
  try {
    const res = await fetch(`${BASE}/api/v1${path}`, { method: "POST", body: form, headers });

    if (res.status === 401 && !isRetry && getRefresh()) {
      const refreshed = await tryRefreshToken();
      if (refreshed) return apiUpload<T>(path, form, true);
      redirectToLogin();
      throw new ApiError(401, "Phiên đăng nhập đã hết hạn");
    }

    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = data?.detail ?? `Lỗi tải lên (${res.status})`;
      throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data as T;
  } finally {
    endRequest();
  }
}

// Tải file (preview) có kèm Bearer — trả Blob để mở object URL.
async function apiBlob(path: string, isRetry = false): Promise<Blob> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  startRequest();
  try {
    const res = await fetch(`${BASE}/api/v1${path}`, { headers });

    if (res.status === 401 && !isRetry && getRefresh()) {
      const refreshed = await tryRefreshToken();
      if (refreshed) return apiBlob(path, true);
      redirectToLogin();
      throw new ApiError(401, "Phiên đăng nhập đã hết hạn");
    }

    if (!res.ok) {
      const data = await res.json().catch(() => null);
      const detail = data?.detail ?? `Không tải được file (${res.status})`;
      throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return res.blob();
  } finally {
    endRequest();
  }
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  patch: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
  put: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "PUT", body: JSON.stringify(body ?? {}) }),
  del: (path: string) => apiFetch<void>(path, { method: "DELETE" }),
  upload: apiUpload,
  blob: apiBlob,
};
