'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { api, errorMessage } from '@/lib/api';
import { EmptyState, InfoBanner, Spinner } from '@/components/ui';

interface SearchResult {
  title?: string | null;
  snippet?: string | null;
  price?: number | null;
  currency?: string | null;
  shop?: string | null;
  city?: string | null;
  url?: string | null;
  image_url?: string | null;
}

interface ProductItem {
  id: string;
  product_name: string;
  specs?: string | null;
  unit?: string | null;
  quantity?: number | null;
  source_section?: string | null;
  status: string;
  error_message?: string | null;
  results: SearchResult[];
  best_match?: SearchResult | null;
  search_region?: string | null;
}

function formatQty(value?: number | null) {
  if (value == null) return '';
  return Number.isInteger(value) ? String(value) : value.toLocaleString('ru-RU');
}

function formatPrice(value?: number | null) {
  if (value == null) return '—';
  return new Intl.NumberFormat('ru-RU').format(value);
}

function ResultCard({ result, best }: { result: SearchResult; best?: boolean }) {
  const url = result.url ?? '#';
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={`group flex gap-3 p-3 rounded-xl border transition-colors ${
        best
          ? 'border-primary bg-primary/5 hover:bg-primary/10'
          : 'border-outline-variant bg-surface-container-lowest hover:border-primary/50'
      }`}
    >
      <div className="w-16 h-16 shrink-0 rounded-lg bg-surface-container-high overflow-hidden flex items-center justify-center">
        {result.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={result.image_url} alt={result.title ?? ''} className="w-full h-full object-cover" />
        ) : (
          <span className="material-symbols-outlined text-2xl text-primary">inventory_2</span>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p className={`text-body-md font-body-md text-on-surface line-clamp-2 group-hover:text-primary transition-colors ${best ? 'font-bold' : ''}`}>
            {result.title ?? '—'}
          </p>
          <span className="shrink-0 text-label-lg font-label-lg text-on-surface whitespace-nowrap">
            {result.price != null ? `${formatPrice(result.price)} ₸` : ''}
          </span>
        </div>
        {result.snippet && <p className="text-body-sm font-body-sm text-on-surface-variant line-clamp-2 mt-0.5">{result.snippet}</p>}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1.5">
          {result.shop && (
            <span className="flex items-center gap-1 text-label-sm font-label-sm text-on-surface-variant">
              <span className="material-symbols-outlined text-[14px]">storefront</span>
              {result.shop}
            </span>
          )}
          {result.city && (
            <span className="flex items-center gap-1 text-label-sm font-label-sm text-on-surface-variant">
              <span className="material-symbols-outlined text-[14px]">location_on</span>
              {result.city}
            </span>
          )}
          <span className="flex items-center gap-1 text-label-sm font-label-sm text-primary">
            Открыть
            <span className="material-symbols-outlined text-[14px] group-hover:translate-x-0.5 transition-transform">open_in_new</span>
          </span>
        </div>
      </div>
    </a>
  );
}

export default function ProjectProductsPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [items, setItems] = useState<ProductItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const itemsRef = useRef<ProductItem[] | null>(null);

  const loadItems = useCallback(
    async () => {
      try {
        const res = await api.get(`/projects/${projectId}/products`);
        const data = (Array.isArray(res) ? res : res?.items ?? []) as ProductItem[];
        itemsRef.current = data;
        setItems(data);
        setError('');
      } catch (err) {
        setError(errorMessage(err, 'Не удалось загрузить товары'));
      } finally {
        setLoading(false);
      }
    },
    [projectId],
  );

  const startSearch = useCallback(async () => {
    setNotice('');
    setError('');
    setSearching(true);
    try {
      await api.post(`/projects/${projectId}/products/search`, {});
      setNotice('Поиск запущен в фоне. Это может занять 1–2 минуты.');
    } catch (err) {
      setError(errorMessage(err, 'Не удалось запустить поиск'));
      setSearching(false);
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await loadItems();
    })();
  }, [loadItems]);

  const busy = searching || (items ?? []).some((it) => it.status === 'searching' || it.status === 'pending');
  const allDone = !(items ?? []).some((it) => it.status === 'searching' || it.status === 'pending');

  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (!busy) return;
    timerRef.current = setInterval(() => {
      void (async () => {
        await loadItems();
        const current = itemsRef.current;
        if (current && !current.some((it) => it.status === 'searching' || it.status === 'pending')) {
          setSearching(false);
          setNotice('Поиск завершён');
        }
      })();
    }, 5000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [busy, loadItems]);

  return (
    <div className="px-4 md:px-margin-page py-stack-lg">
      <div className="max-w-container-max mx-auto">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-stack-lg">
          <div>
            <h2 className="text-headline-lg font-headline-lg text-on-surface">Товары из технического задания</h2>
            <p className="text-body-md font-body-md text-on-surface-variant mt-1">
              Извлечение из текста ТЗ и поиск по казахстанским магазинам и рынку
            </p>
          </div>
          <button
            onClick={startSearch}
            disabled={busy}
            className="inline-flex items-center gap-2 px-4 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span className={`material-symbols-outlined text-[18px] ${busy ? 'animate-spin' : ''}`}>
              {busy ? 'sync' : 'search'}
            </span>
            {busy ? 'Поиск…' : 'Найти товары'}
          </button>
        </div>

        {notice && <div className="mb-stack-md"><InfoBanner>{notice}</InfoBanner></div>}
        {error && (
          <div className="mb-stack-md bg-error-container border border-error-container rounded-lg px-4 py-3 text-body-md font-body-md text-on-surface">
            {error}
          </div>
        )}

        {loading ? (
          <div className="py-16"><Spinner label="Загрузка товаров…" /></div>
        ) : items == null || items.length === 0 ? (
          <EmptyState
            icon="inventory_2"
            title="Товары ещё не найдены"
            description="Загрузите ТЗ с таблицей спецификации и нажмите «Найти товары» — система извлечёт наименования, количество и единицы измерения, затем найдёт предложения на рынке РК."
            action={allDone ? { label: 'Найти товары', onClick: startSearch } : undefined}
          />
        ) : (
          <div className="space-y-stack-lg">
            {items.map((item) => (
              <section key={item.id} className="bg-surface/60 border border-outline-variant rounded-xl p-4 md:p-6">
                <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
                  <div>
                    <h3 className="text-headline-md font-headline-md text-on-surface">{item.product_name}</h3>
                    {(item.specs || item.unit || item.quantity != null) && (
                      <p className="text-body-md font-body-md text-on-surface-variant mt-1">
                        {[item.specs, item.unit, item.quantity != null ? `${formatQty(item.quantity)}` : '']
                          .filter(Boolean)
                          .join(' · ') || '—'}
                      </p>
                    )}
                    {item.search_region && (
                      <p className="flex items-center gap-1 text-label-sm font-label-sm text-on-surface-variant mt-1">
                        <span className="material-symbols-outlined text-[14px]">location_on</span>
                        Регион поиска: {item.search_region}
                      </p>
                    )}
                  </div>
                  {item.status === 'searching' && (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-label-md font-label-md bg-blue-50 text-blue-700 border border-blue-200">
                      <span className="w-3 h-3 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
                      Поиск…
                    </span>
                  )}
                  {item.status === 'error' && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-label-md font-label-md bg-red-50 text-red-800 border border-red-200">
                      Ошибка: {item.error_message ?? 'неизвестно'}
                    </span>
                  )}
                </div>

                {item.status === 'ready' && (
                  <>
                    {item.best_match && (
                      <div className="mb-4">
                        <p className="text-label-md font-label-md text-primary uppercase tracking-wide mb-2">Лучшее предложение</p>
                        <ResultCard result={item.best_match} best />
                      </div>
                    )}
                    {item.results && item.results.length > 0 ? (
                      <div className="grid gap-3 sm:grid-cols-2">
                        {item.results
                          .filter((r) => r !== item.best_match)
                          .map((r, i) => (
                            <ResultCard key={`${r.url ?? ''}-${i}`} result={r} />
                          ))}
                      </div>
                    ) : (
                      <p className="text-body-md font-body-md text-on-surface-variant">Предложения не найдены.</p>
                    )}
                  </>
                )}
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
