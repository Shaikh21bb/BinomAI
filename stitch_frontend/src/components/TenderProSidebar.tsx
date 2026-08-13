'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/hooks/useTheme';

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Рабочий стол', icon: 'dashboard' },
  { href: '/tenders', label: 'Активные тендеры', icon: 'work' },
];

export function TenderProSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();

  return (
    <aside
      aria-label="Sidebar Navigation"
      className="hidden md:flex flex-col h-screen p-stack-md bg-surface fixed left-0 top-0 w-[280px] border-r border-outline-variant z-50"
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-stack-lg px-2">
        <div className="w-10 h-10 rounded-lg bg-on-background text-on-primary flex items-center justify-center font-bold shrink-0">
          <span className="material-symbols-outlined text-[22px]" style={{ fontVariationSettings: "'FILL' 1" }}>
            assistant
          </span>
        </div>
        <div>
          <h1 className="text-headline-md font-headline-md font-bold text-on-surface">BINOM AI</h1>
          <p className="text-label-md font-label-md text-on-surface-variant truncate w-48">
            {user?.full_name ?? 'Рабочее пространство'}
          </p>
        </div>
      </div>

      {/* CTA Button */}
      <Link
        href="/dashboard?new=1"
        className="w-full bg-on-background text-on-primary rounded-md py-2 px-4 mb-stack-md text-label-md font-label-md flex items-center justify-center gap-2 hover:opacity-90 transition-opacity active:scale-[0.98] duration-150"
      >
        <span className="material-symbols-outlined text-[18px]">add</span>
        Новый тендер
      </Link>

      {/* Navigation Links */}
      <nav className="flex-1 flex flex-col gap-1">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`) || (item.href === '/dashboard' && pathname.startsWith('/projects/'));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all ${
                active
                  ? 'bg-primary/10 text-primary font-bold'
                  : 'text-on-surface-variant hover:bg-surface-container-high'
              }`}
            >
              <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
              <span className="font-label-md">{item.label}</span>
            </Link>
          );
        })}

        <Link
          href="/settings"
          className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all ${
            pathname.startsWith('/settings')
              ? 'bg-primary/10 text-primary font-bold'
              : 'text-on-surface-variant hover:bg-surface-container-high'
          }`}
        >
          <span className="material-symbols-outlined text-[20px]">settings</span>
          <span className="font-label-md">Настройки</span>
        </Link>
        {user?.role === 'owner' && (
          <Link
            href="/admin"
            className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all ${
              pathname.startsWith('/admin')
                ? 'bg-primary/10 text-primary font-bold'
                : 'text-on-surface-variant hover:bg-surface-container-high'
            }`}
          >
          <span className="material-symbols-outlined text-[20px]">shield_person</span>
          <span className="font-label-md">Доступ</span>
        </Link>
      )}
      </nav>

      {/* Footer */}
      <div className="mt-auto border-t border-outline-variant pt-stack-sm">
        <button
          onClick={toggle}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-all mb-1"
        >
          <span className="material-symbols-outlined text-[20px]">
            {theme === 'dark' ? 'light_mode' : 'dark_mode'}
          </span>
          <span className="font-label-md">
            {theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
          </span>
        </button>
        <div className="flex items-center gap-3 px-3 py-2">
          <div className="w-8 h-8 rounded-full bg-primary/15 text-primary flex items-center justify-center font-label-md font-bold">
            {(user?.full_name ?? 'U')
              .split(' ')
              .map((w) => w[0])
              .slice(0, 2)
              .join('')
              .toUpperCase()}
          </div>
          <div className="flex flex-col items-start">
            <div className="flex items-center gap-2">
              <span className="text-label-md font-label-md text-on-surface truncate max-w-[110px]">
                {user?.full_name ?? 'Пользователь'}
              </span>
              {user?.role === 'limited' && (
                <span className="px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface-variant text-label-sm font-label-sm whitespace-nowrap">
                  Limited
                </span>
              )}
            </div>
            <button
              onClick={logout}
              className="text-label-md font-label-md text-on-surface-variant hover:text-primary transition-colors"
            >
              Выйти
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}