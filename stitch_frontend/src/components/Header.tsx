'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';

function formatNotifTime(value?: string): string {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'только что';
  if (mins < 60) return `${mins} мин назад`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} ч назад`;
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' });
}

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

const NOTIF_STYLE: Record<string, { icon: string; cls: string }> = {
  tender_status: { icon: 'swap_vert', cls: 'text-primary' },
  tender_deadline: { icon: 'schedule', cls: 'text-red-600' },
  analysis_ready: { icon: 'analytics', cls: 'text-primary' },
  document_ready: { icon: 'description', cls: 'text-emerald-600' },
};

export function Header() {
  const router = useRouter();
  const { user } = useAuth();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchProject[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const notifRootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (notifRootRef.current && !notifRootRef.current.contains(e.target as Node)) setNotifOpen(false);
    };
    window.addEventListener('mousedown', onClick);
    return () => window.removeEventListener('mousedown', onClick);
  }, []);

  const loadNotifications = useCallback(async () => {
    try {
      const res = await api.get('/users/me/notifications?limit=15');
      setNotifications(res?.data?.items ?? []);
      setUnreadCount(res?.data?.unread_count ?? 0);
    } catch {
      // silent — notifications are non-critical
    }
  }, []);

  useEffect(() => {
    loadNotifications();
    const timer = setInterval(loadNotifications, 60_000);
    return () => clearInterval(timer);
  }, [loadNotifications]);

  const handleOpenNotifications = async () => {
    const next = !notifOpen;
    setNotifOpen(next);
    if (next) await loadNotifications();
  };

  const markAllRead = async () => {
    try {
      await api.post('/users/me/notifications/read-all', {});
      setUnreadCount(0);
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch {
      // silent
    }
  };

  const openNotification = async (n: AppNotification) => {
    if (!n.is_read) {
      try {
        await api.post(`/users/me/notifications/${n.id}/read`, {});
      } catch {
        // silent
      }
    }
    setNotifOpen(false);
    router.push(n.link_url || '/tenders');
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
      if (e.key === 'Escape') {
        setOpen(false);
        inputRef.current?.blur();
      }
    };
    const onClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('mousedown', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('mousedown', onClick);
    };
  }, []);

  useEffect(() => {
    if (!open || query.trim().length < 2) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get('/projects/?page_size=100');
        const all: SearchProject[] = res?.data ?? [];
        const q = query.trim().toLowerCase();
        const filtered = all.filter(
          (p) =>
            p.name.toLowerCase().includes(q) ||
            (p.tender_number ?? '').toLowerCase().includes(q) ||
            (p.customer_name ?? '').toLowerCase().includes(q)
        );
        if (!cancelled) {
          setResults(filtered.slice(0, 8));
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setResults([]);
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [query, open]);

  const clearResults = () => {
    setResults([]);
    setLoading(false);
  };

  const initials = (user?.full_name ?? 'U')
    .split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <header className="w-full px-4 md:px-margin-page pt-stack-md pb-stack-md flex items-center justify-between gap-3 sticky top-0 bg-surface/80 backdrop-blur-md z-40 border-b border-outline-variant">
      {/* Command-K Search */}
      <div ref={rootRef} className="relative flex-1 min-w-0 max-w-md">
        <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]">
          search
        </span>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder="Поиск по тендерам, документам, контрагентам..."
          className="w-full pl-9 pr-12 py-2 bg-surface-container-lowest border border-outline-variant rounded-lg font-body-sm text-body-sm text-on-surface placeholder-on-surface-variant focus:outline-none focus:border-on-background focus:ring-2 focus:ring-on-background/5 transition-colors shadow-sm"
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1 border border-outline-variant px-1.5 py-0.5 rounded text-on-surface-variant font-mono-sm text-mono-sm bg-surface opacity-70">
          <span className="material-symbols-outlined text-[12px]">keyboard_command_key</span>
          <span>K</span>
        </div>

        {open && query.trim().length >= 2 && (
          <div className="absolute left-0 right-0 top-full mt-2 bg-surface-container-lowest border border-outline-variant rounded-lg shadow-xl overflow-hidden z-50">
            {loading ? (
              <div className="px-4 py-3 flex items-center gap-2 text-body-sm font-body-sm text-on-surface-variant">
                <span className="material-symbols-outlined animate-spin text-[16px]">sync</span>
                Поиск...
              </div>
            ) : results.length === 0 ? (
              <div className="px-4 py-3 text-body-sm font-body-sm text-on-surface-variant">
                Ничего не найдено
              </div>
            ) : (
              <ul className="max-h-80 overflow-y-auto">
                {results.map((p) => (
                  <li key={p.id}>
                    <button
                      onClick={() => {
                        setOpen(false);
                        setQuery('');
                        clearResults();
                        router.push(`/projects/${p.id}/document`);
                      }}
                      className="w-full text-left px-4 py-2.5 hover:bg-surface-container-low transition-colors flex items-center justify-between gap-3"
                    >
                      <span className="flex flex-col min-w-0">
                        <span className="text-body-md font-body-md text-on-surface truncate">{p.name}</span>
                        {(p.tender_number || p.customer_name) && (
                          <span className="text-body-sm font-body-sm text-on-surface-variant truncate">
                            {[p.tender_number, p.customer_name].filter(Boolean).join(' • ')}
                          </span>
                        )}
                      </span>
                      <span className="material-symbols-outlined text-on-surface-variant text-[16px] shrink-0">
                        arrow_forward
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* Utilities */}
      <div className="flex items-center gap-4 shrink-0">
        <div ref={notifRootRef} className="relative">
          <button
            className="w-8 h-8 flex items-center justify-center rounded border border-outline-variant bg-surface-container-lowest text-on-surface-variant hover:text-on-surface hover:border-on-background/30 transition-colors relative"
            aria-label="Уведомления"
            onClick={handleOpenNotifications}
          >
            <span className="material-symbols-outlined text-[18px]">notifications</span>
            {unreadCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] px-1 rounded-full bg-red-600 text-white text-[11px] font-bold flex items-center justify-center">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          {notifOpen && (
            <div className="absolute right-0 top-full mt-2 w-96 max-w-[calc(100vw-2rem)] bg-surface-container-lowest border border-outline-variant rounded-lg shadow-xl overflow-hidden z-50">
              <div className="flex items-center justify-between px-4 py-3 border-b border-outline-variant">
                <span className="text-title-sm font-title-sm text-on-surface">Уведомления</span>
                {unreadCount > 0 && (
                  <button
                    onClick={markAllRead}
                    className="text-label-sm font-label-sm text-primary hover:underline"
                  >
                    Прочитать все
                  </button>
                )}
              </div>
              <ul className="max-h-96 overflow-y-auto">
                {notifications.length === 0 ? (
                  <li className="px-4 py-8 text-center text-body-sm font-body-sm text-on-surface-variant">
                    Уведомлений пока нет
                  </li>
                ) : (
                  notifications.map((n) => (
                    <li key={n.id}>
                      <button
                        onClick={() => openNotification(n)}
                        className={`w-full text-left px-4 py-3 hover:bg-surface-container-low transition-colors flex gap-3 ${
                          !n.is_read ? 'bg-surface-container-low/60' : ''
                        }`}
                      >
                        <span
                          className={`material-symbols-outlined text-[18px] mt-0.5 shrink-0 ${
                            NOTIF_STYLE[n.type]?.cls ?? 'text-amber-600'
                          }`}
                        >
                          {NOTIF_STYLE[n.type]?.icon ?? 'notifications'}
                        </span>
                        <span className="flex flex-col min-w-0">
                          <span className="text-body-md font-body-md text-on-surface">{n.title}</span>
                          {n.message && (
                            <span className="text-body-sm font-body-sm text-on-surface-variant mt-0.5 line-clamp-2">
                              {n.message}
                            </span>
                          )}
                          <span className="text-mono-sm text-on-surface-variant mt-1 opacity-70">
                            {formatNotifTime(n.created_at)}
                          </span>
                        </span>
                        {!n.is_read && (
                          <span className="w-2 h-2 rounded-full bg-primary shrink-0 mt-1.5" />
                        )}
                      </button>
                    </li>
                  ))
                )}
              </ul>
            </div>
          )}
        </div>
        <div
          className="w-8 h-8 rounded-full border border-outline-variant overflow-hidden bg-on-background text-on-primary flex items-center justify-center text-label-md font-label-md font-bold"
          title={user?.full_name ?? ''}
        >
          {initials}
        </div>
      </div>
    </header>
  );
}
