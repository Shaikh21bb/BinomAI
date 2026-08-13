'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { TenderProSidebar } from '@/components/TenderProSidebar';
import { Header } from '@/components/Header';
import { Onboarding } from '@/components/Onboarding';
import { useTheme } from '@/hooks/useTheme';
import { useAuth } from '@/contexts/AuthContext';

const MOBILE_NAV = [
  { href: '/dashboard', label: 'Тендеры', icon: 'work' },
  { href: '/settings', label: 'Настройки', icon: 'settings' },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const { user } = useAuth();

  return (
    <div className="theme-tenderpro min-h-screen flex flex-col text-body-md bg-background w-full overflow-x-clip pb-16 md:pb-0">
      <TenderProSidebar />
      <main className="ml-0 md:ml-[280px] min-h-screen flex flex-col w-full md:w-[calc(100%-280px)]">
        <Header />
        <div className="flex-1 flex flex-col min-h-0">{children}</div>
      </main>

      {/* Mobile bottom navigation */}
      <nav
        aria-label="Мобильная навигация"
        className="md:hidden fixed bottom-0 inset-x-0 z-50 bg-surface-container-lowest border-t border-outline-variant flex items-center justify-around px-4 py-2"
      >
        {MOBILE_NAV.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center gap-0.5 px-4 py-1.5 rounded-lg text-label-md font-label-md transition-colors ${
                active ? 'text-primary font-bold' : 'text-on-surface-variant'
              }`}
            >
              <span className="material-symbols-outlined text-[22px]">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
        {user?.role === 'owner' && (
          <Link
            href="/admin"
            className={`flex flex-col items-center gap-0.5 px-4 py-1.5 rounded-lg text-label-md font-label-md transition-colors ${
              pathname.startsWith('/admin') ? 'text-primary font-bold' : 'text-on-surface-variant'
            }`}
          >
            <span className="material-symbols-outlined text-[22px]">shield_person</span>
            Доступ
          </Link>
        )}
          <button
            onClick={toggle}
            aria-label="Переключить тему"
          className="flex flex-col items-center gap-0.5 px-4 py-1.5 rounded-lg text-label-md font-label-md text-on-surface-variant transition-colors"
        >
          <span className="material-symbols-outlined text-[22px]">
            {theme === 'dark' ? 'light_mode' : 'dark_mode'}
          </span>
          Тема
        </button>
      </nav>

      <Onboarding />
    </div>
  );
}
