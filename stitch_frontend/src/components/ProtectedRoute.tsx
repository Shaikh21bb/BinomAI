"use client";

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

const PUBLIC_PATHS = ['/', '/login', '/register', '/reset-password'];

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading, authError, refreshUser, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const isPublic = PUBLIC_PATHS.includes(pathname);

  useEffect(() => {
    if (!isLoading && !user && !authError && !isPublic) {
      router.replace('/login');
    }
  }, [user, isLoading, authError, router, pathname, isPublic]);

  if (isLoading && !isPublic) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-surface theme-tenderpro">
        <div className="flex flex-col items-center gap-4" role="status" aria-live="polite">
          <span className="material-symbols-outlined text-4xl animate-spin text-primary" aria-hidden="true">sync</span>
          <p className="text-body-md text-on-surface-variant">Открываем рабочее пространство…</p>
        </div>
      </div>
    );
  }

  if (!user && authError && !isPublic) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center bg-surface px-6 theme-tenderpro">
        <div className="w-full max-w-md rounded-2xl border border-outline-variant bg-surface-container-lowest p-8 text-center">
          <span className="material-symbols-outlined mb-4 text-4xl text-primary" aria-hidden="true">cloud_off</span>
          <h1 className="mb-2 text-xl font-semibold text-on-surface">Не удалось открыть рабочее пространство</h1>
          <p className="text-body-md text-on-surface-variant" role="alert">{authError}</p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button type="button" onClick={() => void refreshUser()} className="rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-on-primary">
              Повторить попытку
            </button>
            <button type="button" onClick={logout} className="rounded-lg border border-outline-variant px-5 py-2.5 text-sm font-medium text-on-surface">
              Вернуться ко входу
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!user && !isPublic) {
    return null;
  }

  return <>{children}</>;
}
