"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/auth-types";

type AuthState = {
  user: User | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUser(await api<User>("/auth/me"));
    } catch (err) {
      setUser(null);
      if (err instanceof ApiError && err.status !== 401) setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
    function expired() {
      setUser(null);
      queryClient.clear();
    }
    window.addEventListener("auth:unauthorized", expired);
    return () => window.removeEventListener("auth:unauthorized", expired);
  }, [reload, queryClient]);

  async function login(email: string, password: string) {
    await api("/auth/csrf");
    const signedIn = await api<User>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    queryClient.clear();
    setUser(signedIn);
    setError(null);
  }

  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch (err) {
      if (!(err instanceof ApiError) || err.status !== 401) throw err;
    }
    queryClient.clear();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, error, reload, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("AuthProvider is required");
  return auth;
}
