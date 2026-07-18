"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, clearTokens, getRefresh, getToken, setTokens } from "./api";
import type { TokenResponse, User } from "./types";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthCtx>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  // loading=true chỉ khi có token cần xác thực; tránh setState đồng bộ trong effect.
  const [loading, setLoading] = useState<boolean>(() => typeof window !== "undefined" && !!getToken());
  const router = useRouter();

  useEffect(() => {
    if (!getToken()) return;
    api
      .get<User>("/auth/me")
      .then(setUser)
      .catch(() => clearTokens())
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.post<TokenResponse>("/auth/login", { email, password });
    setTokens(tokens.access_token, tokens.refresh_token);
    const me = await api.get<User>("/auth/me");
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    const refresh = getRefresh();
    if (refresh) api.post("/auth/logout", { refresh_token: refresh }).catch(() => {});
    clearTokens();
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
