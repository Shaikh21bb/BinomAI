'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';

interface SearchProject {
  id: string;
  name: string;
  tender_number?: string;
  customer_name?: string;
  status: string;
}

export function Header() {
  const router = useRouter();
  const { user } = useAuth();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchProject[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

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
        <button
          className="w-8 h-8 flex items-center justify-center rounded border border-outline-variant bg-surface-container-lowest text-on-surface-variant hover:text-on-surface hover:border-on-background/30 transition-colors"
          aria-label="Уведомления"
          onClick={() => router.push('/settings')}
        >
          <span className="material-symbols-outlined text-[18px]">notifications</span>
        </button>
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
