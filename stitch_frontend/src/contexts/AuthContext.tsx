"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { api, asError, AUTH_SESSION_KEY, clearSessionTokens, errorMessage, saveSessionTokens } from '@/lib/api';

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  company_id: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  authError: string | null;
  login: (access_token: string, refresh_token: string, user?: User) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const requestVersion = useRef(0);

  const fetchUser = useCallback(async (signal?: AbortSignal) => {
    const version = ++requestVersion.current;
    try {
      if (typeof window !== 'undefined' && localStorage.getItem('access_token')) {
        const userData = await api.get('/auth/me', { signal });
        if (version !== requestVersion.current || signal?.aborted) return;
        setUser(userData);
        setAuthError(null);
      } else if (version === requestVersion.current) {
        setUser(null);
        setAuthError(null);
      }
    } catch (error) {
      if (version !== requestVersion.current || signal?.aborted) return;
      const status = asError(error).status;
      if (status === 401 || status === 403 || !localStorage.getItem('access_token')) {
        setUser(null);
        setAuthError(null);
      } else {
        // Keep the session during an outage and let the user retry profile loading.
        setAuthError(errorMessage(error, 'Не удалось загрузить профиль. Повторите попытку.'));
      }
    } finally {
      if (version === requestVersion.current && !signal?.aborted) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) void fetchUser(controller.signal);
    });
    const onStorage = (event: StorageEvent) => {
      const isLogout = event.key === 'access_token' && event.newValue === null;
      if (event.key !== AUTH_SESSION_KEY && event.key !== null && !isLogout) return;
      requestVersion.current += 1;
      setUser(null);
      setAuthError(null);
      setIsLoading(!!localStorage.getItem('access_token'));
      void fetchUser();
    };
    window.addEventListener('storage', onStorage);
    return () => {
      controller.abort();
      requestVersion.current += 1;
      window.removeEventListener('storage', onStorage);
    };
  }, [fetchUser]);

  const login = (access_token: string, refresh_token: string, user?: User) => {
    requestVersion.current += 1;
    saveSessionTokens(access_token, refresh_token);
    setAuthError(null);
    setUser(user ?? null);
    setIsLoading(!user);
    if (!user) void fetchUser();
  };

  const logout = () => {
    requestVersion.current += 1;
    clearSessionTokens();
    setUser(null);
    setAuthError(null);
    setIsLoading(false);
    router.replace('/login');
  };

  const refreshUser = async () => {
    if (!user) setIsLoading(true);
    setAuthError(null);
    await fetchUser();
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, authError, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
