'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { TenderProSidebar } from '@/components/TenderProSidebar';
import { ProjectTabs } from '@/components/ProjectTabs';
import { Header } from '@/components/Header';
import { useTheme } from '@/hooks/useTheme';

const MOBILE_NAV: { label: string; icon: string; href: (id: string) => string }[] = [
  { href: (id: string) => `/projects/${id}/document`, label: 'ТЗ', icon: 'description' },
  { href: (id: string) => `/projects/${id}/chat`, label: 'Диалог', icon: 'forum' },
  { href: (id: string) => `/projects/${id}/generate`, label: 'Документы', icon: 'edit_document' },
  { href: () => '/dashboard', label: 'Тендеры', icon: 'work' },
];

export default function ProjectLayout({ children }: { children: ReactNode }) {
  const params = useParams();
  const projectId = params.id as string;
  const pathname = usePathname();
  const { toggle, theme } = useTheme();

  return (
    <div className="workspace-shell theme-tenderpro min-h-screen flex flex-col text-body-md bg-background w-full overflow-x-clip pb-20 md:pb-0">
      <a href="#workspace-content" className="skip-link">
        Перейти к содержимому
      </a>
      <TenderProSidebar />
      <main className="ml-0 md:ml-64 min-h-screen min-w-0 flex flex-col w-full md:w-[calc(100%_-_256px)]">
        <Header />
        <ProjectTabs projectId={projectId} />
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
          const href = item.href(projectId);
          const active = pathname === href;
          return (
            <Link
              key={item.label}
              href={href}
              aria-current={active ? 'page' : undefined}
              className={`flex min-w-0 flex-1 flex-col items-center gap-1 px-1 py-1.5 rounded-xl text-[10px] font-medium transition-colors ${
                active ? 'text-primary font-bold' : 'text-on-surface-variant'
              }`}
            >
              <span className="material-symbols-outlined text-[22px]">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
        <button
          onClick={toggle}
          aria-label="Переключить тему"
          className="flex min-w-0 flex-1 flex-col items-center gap-1 px-1 py-1.5 rounded-xl text-[10px] font-medium text-on-surface-variant transition-colors"
        >
          <span className="material-symbols-outlined text-[22px]">
            {theme === 'dark' ? 'light_mode' : 'dark_mode'}
          </span>
          Тема
        </button>
      </nav>
    </div>
  );
}
