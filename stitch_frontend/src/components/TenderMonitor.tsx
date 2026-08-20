'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, errorMessage } from '@/lib/api';
import { StatusBadge, EmptyState, formatDate, InfoBanner, Spinner } from '@/components/ui';

export interface MonitorLot {
  id: string;
  source_url: string;
  source_host: string;
  lot_number?: string;
  name?: string;
  description?: string;
  customer_name?: string;
  customer_bin?: string;
  amount?: string | number | null;
  status?: string;
  prev_status?: string;
  status_changed_at?: string;
  start_date?: string;
  deadline_at?: string;
  last_check_at?: string;
  next_check_at?: string;
  last_error?: string;
}

interface MonitorStats {
  total: number;
  errors: number;
  deadlines_soon: MonitorLot[];
  recent_changes: MonitorLot[];
}

function deadlineLabel(deadline?: string): { text: string; urgent: boolean } {
  if (!deadline) return { text: '—', urgent: false };
  const d = new Date(deadline).getTime();
  if (Number.isNaN(d)) return { text: '—', urgent: false };
  const diff = d - Date.now();
  const days = Math.ceil(diff / 86_400_000);
  if (diff < 0) return { text: 'дедлайн прошёл', urgent: true };
  if (days <= 3) return { text: `${days} дн.`, urgent: true };
  return { text: `${days} дн.`, urgent: false };
}

function formatMoney(value?: string | number | null): string {
  if (value === null || value === undefined || value === '') return '—';
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return new Intl.NumberFormat('ru-RU', {
    maximumFractionDigits: 2,
  }).format(n) + ' ₸';
}

export function TenderMonitor() {
  const router = useRouter();
  const [lots, setLots] = useState<MonitorLot[]>([]);
  const [stats, setStats] = useState<MonitorStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [url, setUrl] = useState('');
  const [isAdding, setIsAdding] = useState(false);
  const [refreshingId, setRefreshingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [creatingId, setCreatingId] = useState<string | null>(null);

  const load = useCallback(async (silent = false) => {
    try {
      const [lotsRes, statsRes] = await Promise.all([
        api.get('/tenders/monitor'),
        api.get('/tenders/monitor/stats'),
      ]);
      setLots((lotsRes?.data?.items ?? lotsRes?.data ?? []) as MonitorLot[]);
      setStats((statsRes?.data ?? statsRes) as MonitorStats);
    } catch (err) {
      if (!silent) setError(errorMessage(err, 'Не удалось загрузить лоты'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(() => load(true), 60_000);
    return () => clearInterval(timer);
  }, [load]);

  const handleAdd = async () => {
    const trimmed = url.trim();
    if (!trimmed) return;
    setIsAdding(true);
    setError('');
    try {
      await api.post('/tenders/monitor', { url: trimmed });
      setUrl('');
      await load();
    } catch (err) {
      setError(errorMessage(err, 'Не удалось добавить лот'));
    } finally {
      setIsAdding(false);
    }
  };

  const handleRefresh = async (id: string) => {
    setRefreshingId(id);
    setError('');
    try {
      await api.post(`/tenders/monitor/${id}/refresh`, {});
      await load();
    } catch (err) {
      setError(errorMessage(err, 'Не удалось обновить лот'));
    } finally {
      setRefreshingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    setError('');
    try {
      await api.delete(`/tenders/monitor/${id}`);
      setLots((prev) => prev.filter((l) => l.id !== id));
    } catch (err) {
      setError(errorMessage(err, 'Не удалось удалить лот'));
    } finally {
      setDeletingId(null);
    }
  };

  const handleCreateProject = async (lot: MonitorLot) => {
    setCreatingId(lot.id);
    setError('');
    try {
      const res = await api.post(`/tenders/monitor/${lot.id}/project`, {});
      const projectId = (res?.data ?? res)?.id;
      if (projectId) router.push(`/projects/${projectId}/document`);
    } catch (err) {
      setError(errorMessage(err, 'Не удалось создать проект'));
    } finally {
      setCreatingId(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1 className="text-headline-lg font-headline-lg text-on-surface mb-1">Мониторинг тендеров</h1>
        <p className="text-body-md font-body-md text-on-surface-variant">
          Отслеживание статусов и дедлайнов интересующих вас лотов на порталах закупок.
        </p>
      </div>

      <InfoBanner>
        Вставьте ссылку на страницу лота (например, <code className="text-xs">goszakup.gov.kz/ru/...</code>).
        Сервис сохранит данные лота и будет автоматически проверять его статус и дедлайн.
      </InfoBanner>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-surface-container-lowest border border-outline-variant rounded-lg p-4">
            <div className="flex items-center gap-2 text-on-surface-variant">
              <span className="material-symbols-outlined text-[18px]">radar</span>
              <span className="text-label-md font-label-md">Лоты под контролем</span>
            </div>
            <p className="text-headline-lg font-headline-lg font-bold text-on-surface mt-1.5">
              {stats.total}
            </p>
          </div>
          <div className="bg-surface-container-lowest border border-outline-variant rounded-lg p-4">
            <div className="flex items-center gap-2 text-on-surface-variant">
              <span className="material-symbols-outlined text-[18px]">hourglass_top</span>
              <span className="text-label-md font-label-md">Дедлайны ≤ 3 дней</span>
            </div>
            <p
              className={`text-headline-lg font-headline-lg font-bold mt-1.5 ${
                stats.deadlines_soon.length > 0 ? 'text-red-600' : 'text-on-surface'
              }`}
            >
              {stats.deadlines_soon.length}
            </p>
          </div>
          <div className="bg-surface-container-lowest border border-outline-variant rounded-lg p-4">
            <div className="flex items-center gap-2 text-on-surface-variant">
              <span className="material-symbols-outlined text-[18px]">swap_vert</span>
              <span className="text-label-md font-label-md">Изменения за 7 дней</span>
            </div>
            <p className="text-headline-lg font-headline-lg font-bold text-on-surface mt-1.5">
              {stats.recent_changes.length}
            </p>
          </div>
          <div className="bg-surface-container-lowest border border-outline-variant rounded-lg p-4">
            <div className="flex items-center gap-2 text-on-surface-variant">
              <span className="material-symbols-outlined text-[18px]">error_outline</span>
              <span className="text-label-md font-label-md">Ошибки проверки</span>
            </div>
            <p
              className={`text-headline-lg font-headline-lg font-bold mt-1.5 ${
                stats.errors > 0 ? 'text-amber-600' : 'text-on-surface'
              }`}
            >
              {stats.errors}
            </p>
          </div>
        </div>
      )}

      {stats && (stats.deadlines_soon.length > 0 || stats.recent_changes.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {stats.deadlines_soon.length > 0 && (
            <div className="bg-surface-container-lowest border border-outline-variant rounded-lg p-4">
              <h2 className="text-title-sm font-title-sm text-on-surface mb-3 flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-red-600">hourglass_top</span>
                Ближайшие дедлайны
              </h2>
              <ul className="space-y-2.5">
                {stats.deadlines_soon.map((lot) => {
                  const dl = deadlineLabel(lot.deadline_at);
                  return (
                    <li key={lot.id} className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-body-sm font-body-md text-on-surface truncate">
                          {lot.lot_number ? `№ ${lot.lot_number}` : ''}{' '}
                          {lot.name || lot.source_url}
                        </p>
                        {lot.customer_name && (
                          <p className="text-label-sm font-label-sm text-on-surface-variant truncate">
                            {lot.customer_name}
                          </p>
                        )}
                      </div>
                      <span
                        className={`text-label-sm font-label-sm shrink-0 ${dl.urgent ? 'text-red-600 font-bold' : 'text-on-surface-variant'}`}
                      >
                        {formatDate(lot.deadline_at)} ({dl.text})
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {stats.recent_changes.length > 0 && (
            <div className="bg-surface-container-lowest border border-outline-variant rounded-lg p-4">
              <h2 className="text-title-sm font-title-sm text-on-surface mb-3 flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-primary">swap_vert</span>
                Последние изменения статусов
              </h2>
              <ul className="space-y-2.5">
                {stats.recent_changes.map((lot) => (
                  <li key={lot.id} className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-body-sm font-body-md text-on-surface truncate">
                        {lot.lot_number ? `№ ${lot.lot_number}` : ''}{' '}
                        {lot.name || lot.source_url}
                      </p>
                      <p className="text-label-sm font-label-sm text-on-surface-variant truncate">
                        {formatDate(lot.status_changed_at)}
                      </p>
                    </div>
                    <span className="text-label-sm font-label-sm shrink-0 flex items-center gap-1.5">
                      <span className="px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant">
                        {lot.prev_status ?? '—'}
                      </span>
                      <span className="material-symbols-outlined text-[14px] text-on-surface-variant">
                        arrow_forward
                      </span>
                      <span className="px-2 py-0.5 rounded bg-primary/10 text-primary">
                        {lot.status ?? '—'}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="flex gap-2">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          placeholder="https://goszakup.gov.kz/ru/lot/view/…"
          className="flex-1 px-3.5 py-2.5 rounded-lg border border-outline-variant bg-surface-container-lowest text-body-md font-body-md text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-2 focus:ring-primary/40"
        />
        <button
          onClick={handleAdd}
          disabled={isAdding || !url.trim()}
          className="px-4 py-2.5 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {isAdding ? 'Добавление…' : 'Добавить'}
        </button>
      </div>

      {error && (
        <div className="px-4 py-3 bg-red-50 text-red-800 border border-red-200 rounded-lg text-body-md font-body-md">
          {error}
        </div>
      )}

      {isLoading ? (
        <Spinner label="Загрузка лотов…" />
      ) : lots.length === 0 ? (
        <EmptyState
          icon="radar"
          title="Лоты не отслеживаются"
          description="Добавьте первый лот по ссылке со страницы закупки, и мы будем следить за ним автоматически."
        />
      ) : (
        <div className="space-y-3">
          {lots.map((lot) => {
            const dl = deadlineLabel(lot.deadline_at);
            const changed = lot.prev_status && lot.status && lot.prev_status !== lot.status;
            return (
              <div
                key={lot.id}
                className="bg-surface-container-lowest border border-outline-variant rounded-lg p-4 flex flex-col gap-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      {lot.lot_number && (
                        <span className="text-label-sm font-label-sm text-on-surface-variant">
                          {lot.lot_number}
                        </span>
                      )}
                      {lot.status && <StatusBadge status={lot.status} />}
                      {changed && (
                        <span className="inline-flex items-center gap-1 text-label-sm font-label-sm text-emerald-700">
                          <span className="material-symbols-outlined text-[14px]">update</span>
                          статус обновился
                        </span>
                      )}
                    </div>
                    <h3 className="text-title-md font-title-md text-on-surface mt-1.5">
                      {lot.name || lot.source_url}
                    </h3>
                    <p className="text-body-sm font-body-sm text-on-surface-variant mt-0.5">
                      {lot.customer_name || 'Заказчик неизвестен'}
                      {lot.customer_bin ? ` · БИН ${lot.customer_bin}` : ''}
                    </p>
                  </div>
                  <div className="flex gap-1.5 shrink-0">
                    <button
                      onClick={() => handleCreateProject(lot)}
                      disabled={creatingId === lot.id}
                      title="Создать проект из лота"
                      className="px-3 h-9 rounded-lg bg-on-background text-on-primary text-label-md font-label-md flex items-center gap-1.5 hover:opacity-90 transition-opacity disabled:opacity-50"
                    >
                      <span className="material-symbols-outlined text-[16px]">add</span>
                      Проект
                    </button>
                    <button
                      onClick={() => handleRefresh(lot.id)}
                      disabled={refreshingId === lot.id}
                      title="Обновить сейчас"
                      className="w-9 h-9 rounded-lg border border-outline-variant flex items-center justify-center hover:bg-surface-container-high transition-colors disabled:opacity-50"
                    >
                      <span className="material-symbols-outlined text-[18px] text-on-surface-variant">
                        refresh
                      </span>
                    </button>
                    <button
                      onClick={() => handleDelete(lot.id)}
                      disabled={deletingId === lot.id}
                      title="Удалить из мониторинга"
                      className="w-9 h-9 rounded-lg border border-outline-variant flex items-center justify-center hover:bg-red-50 hover:border-red-200 transition-colors disabled:opacity-50"
                    >
                      <span className="material-symbols-outlined text-[18px] text-red-600">delete</span>
                    </button>
                  </div>
                </div>

                <div className="flex flex-wrap gap-x-6 gap-y-2 text-body-sm font-body-sm text-on-surface-variant">
                  <span>
                    Сумма: <span className="text-on-surface">{formatMoney(lot.amount)}</span>
                  </span>
                  <span>
                    Дедлайн:{' '}
                    <span className={dl.urgent ? 'text-red-600 font-label-sm' : 'text-on-surface'}>
                      {formatDate(lot.deadline_at)} {dl.text !== '—' ? `(${dl.text})` : ''}
                    </span>
                  </span>
                  <span>Проверка: {formatDate(lot.last_check_at)}</span>
                </div>

                {lot.last_error && (
                  <div className="px-3 py-2 bg-amber-50 text-amber-900 border border-amber-200 rounded-md text-body-sm font-body-sm">
                    Ошибка проверки: {lot.last_error}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
