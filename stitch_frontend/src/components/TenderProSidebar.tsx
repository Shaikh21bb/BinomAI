'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/hooks/useTheme';
import { Brand } from '@/components/Brand';

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Обзор', icon: 'space_dashboard' },
  { href: '/tenders', label: 'Тендеры', icon: 'work_outline' },
  { href: '/quick-check', label: 'Быстрая проверка', icon: 'travel_explore' },
];

const ROLE_LABELS: Record<string, string> = {
  owner: 'Владелец',
  member: 'Сотрудник',
  limited: 'Ограниченный доступ',
};

export function TenderProSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const initials = (user?.full_name?.trim() || 'Пользователь')
    .split(/\s+/)
    .map((word) => word[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <aside
      aria-label="Основная навигация"
      className="workspace-sidebar fixed inset-y-0 left-0 z-50 hidden w-64 flex-col bg-[#101c32] px-4 py-6 text-slate-300 md:flex"
    >
      <div className="px-2 pb-7">
        <Brand inverse />
      </div>
      <div className="mx-1 mb-6 flex items-center gap-2.5 rounded-xl border border-white/10 bg-white/5 px-3 py-3">
        <span className="material-symbols-outlined text-[19px] text-slate-400" aria-hidden="true">
          corporate_fare
        </span>
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-slate-100">Рабочее пространство</p>
          <p className="mt-0.5 truncate text-[11px] text-slate-400">
            {ROLE_LABELS[user?.role ?? ''] || 'Команда компании'}
          </p>
        </div>
      </div>
      <Link
        href="/dashboard?new=1"
        onClick={(event) => {
          if (pathname === '/dashboard') {
            event.preventDefault();
            window.dispatchEvent(new Event('binom:new-tender'));
          }
        }}
        className="mx-1 mb-7 flex min-h-11 items-center justify-center gap-2 rounded-xl bg-[#3976ed] px-4 py-3 text-[13px] font-semibold text-white shadow-[0_4px_16px_#0002] transition-colors hover:bg-[#4c85f4]"
      >
        <span className="material-symbols-outlined text-[19px]" aria-hidden="true">
          add
        </span>
        Новый тендер
      </Link>
      <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
        Рабочая область
      </p>
      <nav className="space-y-1" aria-label="Разделы платформы">
        {NAV_ITEMS.map((item) => {
          const active =
            pathname === item.href ||
            (item.href === '/tenders' && pathname.startsWith('/projects/'));
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? 'page' : undefined}
              className={`group flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] transition-colors ${active ? 'bg-[#3976ed]/15 font-semibold text-[#a8c7ff] ring-1 ring-inset ring-[#78a7ff]/15' : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'}`}
            >
              <span className="material-symbols-outlined text-[20px]" aria-hidden="true">
                {item.icon}
              </span>
              {item.label}
              {active && (
                <span
                  className="ml-auto h-1.5 w-1.5 rounded-full bg-[#7eabff]"
                  aria-hidden="true"
                />
              )}
            </Link>
          );
        })}
      </nav>
      <div className="mt-7 border-t border-white/[0.07] pt-5">
        <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
          Организация
        </p>
        <Link
          href="/settings"
          aria-current={pathname.startsWith('/settings') ? 'page' : undefined}
          className={`flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] transition-colors ${pathname.startsWith('/settings') ? 'bg-white/10 text-white' : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'}`}
        >
          <span className="material-symbols-outlined text-[20px]" aria-hidden="true">
            settings
          </span>
          Настройки и команда
        </Link>
        {user?.role === 'owner' && (
          <Link
            href="/admin"
            aria-current={pathname.startsWith('/admin') ? 'page' : undefined}
            className={`flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] transition-colors ${pathname.startsWith('/admin') ? 'bg-white/10 text-white' : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'}`}
          >
            <span className="material-symbols-outlined text-[20px]" aria-hidden="true">
              admin_panel_settings
            </span>
            Управление доступом
          </Link>
        )}
      </div>
      <div className="mt-auto pt-6">
        <div className="mb-4 rounded-xl border border-white/10 bg-[#172740] p-3.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
            <span
              className="material-symbols-outlined text-[17px] text-[#95baff]"
              aria-hidden="true"
            >
              auto_awesome
            </span>
            От документа к решению
          </div>
          <p className="mt-2 text-[11px] leading-[1.7] text-slate-400">
            Товары, поставщики и расчёт маржи — в одном проекте.
          </p>
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event('binom:open-onboarding'))}
            className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-[#a8c7ff] hover:text-white"
          >
            Как работать
            <span className="material-symbols-outlined text-[14px]" aria-hidden="true">
              arrow_outward
            </span>
          </button>
        </div>
        <button
          type="button"
          onClick={toggle}
          className="mb-3 flex min-h-10 w-full items-center gap-3 rounded-xl px-3 text-xs text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
        >
          <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
            {theme === 'dark' ? 'light_mode' : 'dark_mode'}
          </span>
          {theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
        </button>
        <div className="flex items-center gap-2.5 border-t border-white/10 px-1 pt-4">
          <Link
            href="/settings"
            aria-label="Открыть профиль"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/10 text-xs font-bold text-[#c7d9ff]"
          >
            {initials}
          </Link>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-slate-200">
              {user?.full_name || 'Пользователь'}
            </p>
            <p className="mt-1 truncate text-[10px] text-slate-500">
              {ROLE_LABELS[user?.role ?? ''] || 'Участник команды'}
            </p>
          </div>
          <button
            type="button"
            onClick={logout}
            title="Выйти из аккаунта"
            aria-label="Выйти из аккаунта"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-500 hover:bg-white/5 hover:text-white"
          >
            <span className="material-symbols-outlined text-[19px]" aria-hidden="true">
              logout
            </span>
          </button>
        </div>
      </div>
    </aside>
  );
}
