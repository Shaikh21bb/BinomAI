'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { TenderProSidebar } from '@/components/TenderProSidebar';
import { Header } from '@/components/Header';
import { Onboarding } from '@/components/Onboarding';
import { useAuth } from '@/contexts/AuthContext';

const MOBILE_NAV = [
  { href: '/dashboard', label: 'Обзор', icon: 'space_dashboard' },
  { href: '/tenders', label: 'Тендеры', icon: 'work_outline' },
  { href: '/quick-check', label: 'Проверка', icon: 'travel_explore' },
  { href: '/settings', label: 'Настройки', icon: 'settings' },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <div className="workspace-shell theme-tenderpro min-h-screen flex flex-col text-body-md bg-background w-full overflow-x-clip pb-20 md:pb-0">
      <a href="#workspace-content" className="skip-link">
        Перейти к содержимому
      </a>
      <TenderProSidebar />
      <main className="ml-0 md:ml-64 min-h-screen min-w-0 flex flex-col w-full md:w-[calc(100%_-_256px)]">
        <Header />
        <div
          id="workspace-content"
          tabIndex={-1}
          className="workspace-content flex-1 flex flex-col min-h-0 outline-none"
        >
          {children}
        </div>
      </main>

      {/* Mobile bottom navigation */}
      <nav
        aria-label="Мобильная навигация"
        className="mobile-workspace-nav md:hidden fixed bottom-0 inset-x-0 z-50 bg-surface-container-lowest/95 backdrop-blur-xl border-t border-outline-variant flex items-center justify-around px-1 py-2"
      >
        {MOBILE_NAV.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? 'page' : undefined}
              className={`flex min-w-0 flex-1 flex-col items-center gap-1 px-1 py-1.5 rounded-xl text-[10px] font-medium transition-colors ${
                active ? 'bg-primary/8 text-primary font-bold' : 'text-on-surface-variant'
              }`}
            >
              <span className="material-symbols-outlined text-[22px]" aria-hidden="true">
                {item.icon}
              </span>
              {item.label}
            </Link>
          );
        })}
        {user?.role === 'owner' && (
          <Link
            href="/admin"
            aria-current={pathname.startsWith('/admin') ? 'page' : undefined}
            className={`flex min-w-0 flex-1 flex-col items-center gap-1 px-1 py-1.5 rounded-xl text-[10px] font-medium transition-colors ${
              pathname.startsWith('/admin') ? 'text-primary font-bold' : 'text-on-surface-variant'
            }`}
          >
            <span className="material-symbols-outlined text-[22px]" aria-hidden="true">
              shield_person
            </span>
            Доступ
          </Link>
        )}
      </nav>

      <Onboarding />
    </div>
  );
}
