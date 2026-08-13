"use client";

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

const PUBLIC_PATHS = ['/', '/login', '/register', '/reset-password'];

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const isPublic = PUBLIC_PATHS.includes(pathname);

  useEffect(() => {
    if (!isLoading && !user && !isPublic) {
      router.push('/login');
    }
  }, [user, isLoading, router, pathname, isPublic]);

  if (isLoading && !isPublic) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-surface theme-tenderpro">
        <div className="flex flex-col items-center gap-4">
          <span className="material-symbols-outlined text-4xl animate-spin text-primary">sync</span>
          <p className="text-body-md text-on-surface-variant">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user && !isPublic) {
    return null;
  }

  return <>{children}</>;
}
