'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/hooks/useTheme';
import { api, errorMessage } from '@/lib/api';
import { BrandMark } from '@/components/Brand';

interface SearchProject {
  id: string;
  name: string;
  tender_number?: string;
  customer_name?: string;
  status: string;
}
interface AppNotification {
  id: string;
  type: string;
  title: string;
  message?: string;
  link_url?: string;
  is_read: boolean;
  created_at?: string;
}
interface SearchResult {
  query: string;
  projects: SearchProject[];
  error: string;
}

const QUICK_LINKS = [
  {
    label: 'Быстрая проверка PDF и Word',
    description: 'Найти товары и продавцов по ТЗ',
    href: '/quick-check',
    icon: 'travel_explore',
  },
  {
    label: 'Создать новый тендер',
    description: 'Документы, анализ и расчёты',
    href: '/dashboard?new=1',
    icon: 'add_box',
  },
  {
    label: 'Настройки и команда',
    description: 'Профиль и данные организации',
    href: '/settings',
    icon: 'corporate_fare',
  },
];
const NOTIF_ICONS: Record<string, string> = {
  tender_status: 'swap_vert',
  tender_deadline: 'schedule',
  analysis_ready: 'analytics',
  document_ready: 'description',
};
const PAGE_NAMES: Record<string, string> = {
  '/dashboard': 'Обзор',
  '/tenders': 'Тендеры',
  '/quick-check': 'Быстрая проверка',
  '/settings': 'Настройки',
  '/admin': 'Управление доступом',
};

function formatNotifTime(value?: string) {
  if (!value) return '';
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return '';
  const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60_000));
  if (minutes < 1) return 'только что';
  if (minutes < 60) return `${minutes} мин назад`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)} ч назад`;
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' });
}

export function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const { user } = useAuth();
  const { theme, toggle } = useTheme();
  const [query, setQuery] = useState('');
  const [searchResult, setSearchResult] = useState<SearchResult>({
    query: '',
    projects: [],
    error: '',
  });
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifError, setNotifError] = useState('');
  const [notifLoading, setNotifLoading] = useState(true);
  const [markingRead, setMarkingRead] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const notifRootRef = useRef<HTMLDivElement>(null);
  const normalizedQuery = query.trim();
  const hasQuery = normalizedQuery.length >= 2;
  const loading = hasQuery && searchResult.query !== normalizedQuery;
  const projects = loading ? [] : searchResult.projects;
  const optionCount = hasQuery ? projects.length : QUICK_LINKS.length;
  const pageName =
    PAGE_NAMES[pathname] ||
    (pathname.startsWith('/projects/') ? 'Работа с тендером' : 'Рабочая область');
  const initials = (user?.full_name?.trim() || 'Пользователь')
    .split(/\s+/)
    .map((word) => word[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  const navigate = (href: string) => {
    setOpen(false);
    setQuery('');
    setActiveIndex(-1);
    if (pathname === '/dashboard' && href === '/dashboard?new=1') {
      window.dispatchEvent(new Event('binom:new-tender'));
    } else {
      router.push(href);
    }
  };

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
      if (!notifRootRef.current?.contains(event.target as Node)) setNotifOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
        setNotifOpen(false);
      }
      if (event.key === 'Escape') {
        setOpen(false);
        setNotifOpen(false);
        inputRef.current?.blur();
      }
    };
    window.addEventListener('mousedown', onClick);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('mousedown', onClick);
      window.removeEventListener('keydown', onKey);
    };
  }, []);

  useEffect(() => {
    if (!open || !hasQuery) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const response = await api.get(
          `/projects/?page_size=8&search=${encodeURIComponent(normalizedQuery)}`,
          { signal: controller.signal }
        );
        if (!controller.signal.aborted)
          setSearchResult({ query: normalizedQuery, projects: response?.data ?? [], error: '' });
      } catch (error) {
        if (!controller.signal.aborted)
          setSearchResult({
            query: normalizedQuery,
            projects: [],
            error: errorMessage(error, 'Поиск временно недоступен'),
          });
      }
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [normalizedQuery, open, hasQuery]);

  const loadNotifications = useCallback(async () => {
    if (!user) return;
    try {
      const response = await api.get('/users/me/notifications?limit=15');
      // This endpoint returns the list directly, unlike paginated projects.
      setNotifications(response?.items ?? []);
      setUnreadCount(response?.unread_count ?? 0);
      setNotifError('');
    } catch (error) {
      setNotifError(errorMessage(error, 'Не удалось загрузить уведомления'));
    } finally {
      setNotifLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void (async () => {
      await loadNotifications();
    })();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void loadNotifications();
    }, 60_000);
    return () => window.clearInterval(timer);
  }, [loadNotifications]);

  async function markAllRead() {
    if (markingRead) return;
    setMarkingRead(true);
    try {
      await api.post('/users/me/notifications/read-all', {});
      setUnreadCount(0);
      setNotifications((current) => current.map((item) => ({ ...item, is_read: true })));
      setNotifError('');
    } catch (error) {
      setNotifError(errorMessage(error, 'Не удалось отметить уведомления'));
    } finally {
      setMarkingRead(false);
    }
  }

  async function openNotification(notification: AppNotification) {
    if (!notification.is_read) {
      try {
        await api.post(`/users/me/notifications/${notification.id}/read`, {});
        setUnreadCount((count) => Math.max(0, count - 1));
        setNotifications((current) =>
          current.map((item) => (item.id === notification.id ? { ...item, is_read: true } : item))
        );
      } catch {
        /* Opening a result remains available if the read receipt fails. */
      }
    }
    setNotifOpen(false);
    const href = notification.link_url;
    router.push(
      href?.startsWith('/') && !href.startsWith('//') && !href.includes('\\') ? href : '/tenders'
    );
  }

  return (
    <header className="sticky top-0 z-40 flex min-h-[76px] w-full items-center justify-between gap-3 border-b border-outline-variant bg-surface-container-lowest/95 px-4 backdrop-blur-xl md:px-margin-page">
      <Link href="/dashboard" className="shrink-0 md:hidden" aria-label="BINOM AI — рабочий стол">
        <BrandMark className="h-9 w-9 text-[#3976ed]" />
      </Link>
      <div className="hidden shrink-0 items-center gap-2 text-xs xl:flex">
        <span className="text-on-surface-variant">Рабочая область</span>
        <span className="material-symbols-outlined text-[14px] text-outline" aria-hidden="true">
          chevron_right
        </span>
        <span className="font-semibold text-on-surface">{pageName}</span>
      </div>
      <div ref={rootRef} onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }} className="relative min-w-0 flex-1 xl:ml-auto xl:max-w-[390px]">
        <span
          className="material-symbols-outlined pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[19px] text-on-surface-variant"
          aria-hidden="true"
        >
          search
        </span>
        <input
          ref={inputRef}
          type="search"
          role="combobox"
          aria-label="Поиск тендеров"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={open ? 'workspace-search-results' : undefined}
          aria-activedescendant={
            open && activeIndex >= 0 && activeIndex < optionCount
              ? `workspace-option-${activeIndex}`
              : undefined
          }
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            setActiveIndex(-1);
          }}
          onFocus={() => {
            setOpen(true);
            setNotifOpen(false);
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
              event.preventDefault();
              setOpen(true);
              if (optionCount)
                setActiveIndex((index) =>
                  event.key === 'ArrowDown'
                    ? (index + 1) % optionCount
                    : index <= 0
                      ? optionCount - 1
                      : index - 1
                );
            }
            if (event.key === 'Enter' && open && activeIndex >= 0 && activeIndex < optionCount) {
              event.preventDefault();
              navigate(
                hasQuery
                  ? `/projects/${projects[activeIndex].id}/document`
                  : QUICK_LINKS[activeIndex].href
              );
            }
          }}
          placeholder="Поиск тендеров…"
          className="h-10 w-full rounded-xl border border-outline-variant/80 bg-surface-container-low pl-10 pr-4 text-xs text-on-surface placeholder:text-on-surface-variant/75 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/10 sm:pr-14"
        />
        <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded-md border border-outline-variant bg-surface-container-lowest px-1.5 py-0.5 font-mono-sm text-[10px] text-on-surface-variant sm:block">
          ⌘ K
        </kbd>
        {open && (
          <div className="fixed left-3 right-3 top-[68px] z-50 mt-2 overflow-hidden rounded-2xl border border-outline-variant bg-surface-container-lowest shadow-[0_16px_50px_#152c4e1c] md:absolute md:left-0 md:right-0 md:top-full">
            <p className="border-b border-outline-variant px-4 py-2.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-on-surface-variant">
              {hasQuery ? 'Тендеры компании' : 'Быстрый переход'}
            </p>
            <ul
              id="workspace-search-results"
              role="listbox"
              aria-label="Результаты поиска"
              className="max-h-80 overflow-y-auto p-1.5"
            >
              {!hasQuery &&
                QUICK_LINKS.map((item, index) => (
                  <li
                    key={item.href}
                    role="option"
                    id={`workspace-option-${index}`}
                    aria-selected={activeIndex === index}
                  >
                    <button
                      type="button"
                      tabIndex={-1}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => navigate(item.href)}
                      className={`flex w-full items-center gap-3 rounded-lg p-3 text-left hover:bg-surface-container-low ${activeIndex === index ? 'bg-primary/8' : ''}`}
                    >
                      <span
                        className="material-symbols-outlined text-[20px] text-primary"
                        aria-hidden="true"
                      >
                        {item.icon}
                      </span>
                      <span>
                        <span className="block text-xs font-semibold text-on-surface">
                          {item.label}
                        </span>
                        <span className="mt-1 block text-[11px] text-on-surface-variant">
                          {item.description}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              {hasQuery &&
                projects.map((project, index) => (
                  <li
                    key={project.id}
                    role="option"
                    id={`workspace-option-${index}`}
                    aria-selected={activeIndex === index}
                  >
                    <button
                      type="button"
                      tabIndex={-1}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => navigate(`/projects/${project.id}/document`)}
                      className={`flex w-full items-center gap-3 rounded-lg p-3 text-left hover:bg-surface-container-low ${activeIndex === index ? 'bg-primary/8' : ''}`}
                    >
                      <span
                        className="material-symbols-outlined text-[20px] text-primary"
                        aria-hidden="true"
                      >
                        work_outline
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-xs font-semibold text-on-surface">
                          {project.name}
                        </span>
                        <span className="mt-1 block truncate text-[11px] text-on-surface-variant">
                          {[project.tender_number, project.customer_name]
                            .filter(Boolean)
                            .join(' · ') || 'Открыть тендер'}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
            </ul>
            {hasQuery && (
              <div
                role="status"
                aria-live="polite"
                className="px-4 pb-3 text-xs text-on-surface-variant"
              >
                {loading
                  ? 'Ищем тендеры…'
                  : searchResult.error ||
                    (projects.length
                      ? `Показано: ${projects.length}`
                      : 'Совпадений нет. Попробуйте название, номер или заказчика.')}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-1 sm:gap-2">
        <button
          type="button"
          onClick={toggle}
          aria-label={theme === 'dark' ? 'Включить светлую тему' : 'Включить тёмную тему'}
          title="Цветовая тема"
          className="flex h-9 w-9 items-center justify-center rounded-xl text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-primary"
        >
          <span className="material-symbols-outlined text-[20px]" aria-hidden="true">
            {theme === 'dark' ? 'light_mode' : 'dark_mode'}
          </span>
        </button>
        <div ref={notifRootRef} className="relative">
          <button
            type="button"
            aria-label={unreadCount ? `Уведомления: ${unreadCount} непрочитанных` : 'Уведомления'}
            aria-expanded={notifOpen}
            aria-controls="workspace-notifications"
            onClick={() => {
              setNotifOpen(!notifOpen);
              setOpen(false);
              if (!notifOpen) void loadNotifications();
            }}
            className="relative flex h-9 w-9 items-center justify-center rounded-xl text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-primary"
          >
            <span className="material-symbols-outlined text-[20px]" aria-hidden="true">
              notifications
            </span>
            {unreadCount > 0 && (
              <span className="absolute right-0 top-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-error px-1 text-[9px] font-bold text-on-error">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>
          {notifOpen && (
            <section
              id="workspace-notifications"
              aria-label="Уведомления"
              className="fixed left-3 right-3 top-[68px] z-50 mt-3 overflow-hidden rounded-2xl border border-outline-variant bg-surface-container-lowest shadow-[0_16px_50px_#152c4e1c] md:absolute md:left-auto md:right-0 md:top-full md:w-[360px]"
            >
              <div className="flex items-center justify-between border-b border-outline-variant px-4 py-3.5">
                <h2 className="text-sm font-semibold text-on-surface">Уведомления</h2>
                {unreadCount > 0 && (
                  <button
                    type="button"
                    disabled={markingRead}
                    onClick={() => void markAllRead()}
                    className="text-[11px] font-medium text-primary hover:underline disabled:opacity-50"
                  >
                    {markingRead ? 'Сохраняем…' : 'Прочитать все'}
                  </button>
                )}
              </div>
              {notifError && (
                <div
                  role="alert"
                  className="border-b border-outline-variant px-4 py-3 text-xs text-error"
                >
                  {notifError}
                  <button
                    type="button"
                    onClick={() => void loadNotifications()}
                    className="ml-2 underline"
                  >
                    Повторить
                  </button>
                </div>
              )}
              <ul className="max-h-96 overflow-y-auto">
                {notifications.length ? (
                  notifications.map((notification) => (
                    <li key={notification.id}>
                      <button
                        type="button"
                        onClick={() => void openNotification(notification)}
                        className={`flex w-full gap-3 border-b border-outline-variant/60 px-4 py-3.5 text-left hover:bg-surface-container-low ${notification.is_read ? '' : 'bg-primary/[0.04]'}`}
                      >
                        <span
                          className="material-symbols-outlined mt-0.5 text-[20px] text-primary"
                          aria-hidden="true"
                        >
                          {NOTIF_ICONS[notification.type] || 'notifications'}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-xs font-semibold text-on-surface">
                            {notification.title}
                          </span>
                          {notification.message && (
                            <span className="mt-1 block text-xs leading-relaxed text-on-surface-variant">
                              {notification.message}
                            </span>
                          )}
                          <span className="mt-2 block text-[10px] text-on-surface-variant">
                            {formatNotifTime(notification.created_at)}
                          </span>
                        </span>
                        {!notification.is_read && (
                          <span
                            className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary"
                            aria-label="Не прочитано"
                          />
                        )}
                      </button>
                    </li>
                  ))
                ) : (
                  <li className="px-6 py-9 text-center">
                    <span
                      className="material-symbols-outlined mb-2 text-[28px] text-outline"
                      aria-hidden="true"
                    >
                      notifications_none
                    </span>
                    <p className="text-xs text-on-surface-variant">
                      {notifLoading
                        ? 'Загружаем уведомления…'
                        : notifError
                          ? 'Список временно недоступен'
                          : 'Новых событий пока нет'}
                    </p>
                  </li>
                )}
              </ul>
            </section>
          )}
        </div>
        <span className="mx-1 hidden h-6 w-px bg-outline-variant sm:block" aria-hidden="true" />
        <Link
          href="/settings"
          aria-label="Открыть профиль"
          title={user?.full_name || 'Профиль'}
          className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/15 bg-primary/8 text-[11px] font-bold text-primary transition-colors hover:bg-primary/15"
        >
          {initials}
        </Link>
      </div>
    </header>
  );
}
