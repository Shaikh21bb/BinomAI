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
    <div className="theme-tenderpro min-h-screen flex flex-col text-body-md bg-background w-full overflow-x-clip pb-16 md:pb-0">
      <TenderProSidebar />
      <main className="ml-0 md:ml-[280px] min-h-screen flex flex-col w-full md:w-[calc(100%-280px)]">
        <Header />
        <ProjectTabs projectId={projectId} />
        <div className="flex-1 flex flex-col min-h-0">{children}</div>
      </main>

      {/* Mobile bottom navigation */}
      <nav
        aria-label="Мобильная навигация"
        className="md:hidden fixed bottom-0 inset-x-0 z-50 bg-surface-container-lowest border-t border-outline-variant flex items-center justify-around px-4 py-2"
      >
        {MOBILE_NAV.map((item) => {
          const href = item.href(projectId);
          const active = pathname === href;
          return (
            <Link
              key={item.label}
              href={href}
              className={`flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg text-label-md font-label-md transition-colors ${
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
          className="flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg text-label-md font-label-md text-on-surface-variant transition-colors"
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