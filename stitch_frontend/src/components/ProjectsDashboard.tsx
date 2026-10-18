'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { api, errorMessage } from '@/lib/api';
import { StatusBadge, formatDate } from '@/components/ui';
import { NewTenderDialog } from '@/components/NewTenderDialog';
import { useAuth } from '@/contexts/AuthContext';

export interface Project {
  id: string;
  name: string;
  customer_name?: string;
  customer_bin?: string;
  tender_number?: string;
  tender_type?: string;
  complexity?: string;
  status: string;
  deadline_at?: string;
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

const STATUS_OPTIONS = [
  { value: 'all', label: 'Все статусы' },
  { value: 'draft', label: 'Черновик' },
  { value: 'processing', label: 'Обработка' },
  { value: 'analyzing', label: 'Анализ' },
  { value: 'clarifying', label: 'Уточнение' },
  { value: 'generating', label: 'Генерация' },
  { value: 'searching', label: 'Поиск цен' },
  { value: 'review', label: 'На проверке' },
  { value: 'ready', label: 'Готово' },
  { value: 'done', label: 'Завершён' },
  { value: 'submitted', label: 'Подан' },
  { value: 'archived', label: 'Архив' },
  { value: 'error', label: 'Ошибка' },
];
const CLOSED_STATUSES = new Set(['done', 'submitted', 'archived']);
const WORK_STATUSES = new Set([
  'draft',
  'processing',
  'analyzing',
  'clarifying',
  'generating',
  'searching',
]);
const DAY_MS = 86_400_000;
const FIELD_CLASS =
  'w-full rounded-xl border border-outline-variant bg-surface-container-lowest px-3.5 py-2.5 text-sm text-on-surface outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10';

function Icon({ name, className = '' }: { name: string; className?: string }) {
  return (
    <span aria-hidden="true" className={`material-symbols-outlined ${className}`}>
      {name}
    </span>
  );
}

function toLocalInput(iso?: string): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function deadlineState(project: Project, now: number) {
  if (!project.deadline_at || CLOSED_STATUSES.has(project.status)) return 'none';
  const remaining = new Date(project.deadline_at).getTime() - now;
  if (!Number.isFinite(remaining)) return 'none';
  if (remaining < 0) return 'overdue';
  if (remaining <= 7 * DAY_MS) return 'soon';
  return 'scheduled';
}

function DashboardDialog({
  titleId,
  children,
  onClose,
}: {
  titleId: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onMouseDown={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < rect.left ||
          event.clientX > rect.right ||
          event.clientY < rect.top ||
          event.clientY > rect.bottom
        )
          onClose();
      }}
      className="fixed m-auto max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-xl overflow-y-auto rounded-2xl border border-outline-variant bg-surface-bright p-0 text-on-surface shadow-2xl backdrop:bg-slate-950/45 backdrop:backdrop-blur-sm"
    >
      {children}
    </dialog>
  );
}

interface Props {
  pageLabel?: string;
  pageDescription?: string;
}

export function ProjectsDashboard({ pageLabel = 'Рабочий стол', pageDescription }: Props) {
  const { user } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [pagination, setPagination] = useState<{ has_next: boolean; next_cursor?: string | null }>({
    has_next: false,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [mutationError, setMutationError] = useState('');
  const [notice, setNotice] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [editTarget, setEditTarget] = useState<Project | null>(null);
  const [editDraft, setEditDraft] = useState<Partial<Project> | null>(null);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const requestRef = useRef<AbortController | null>(null);

  const loadProjects = useCallback(
    async (cursor?: string) => {
      requestRef.current?.abort();
      const controller = new AbortController();
      requestRef.current = controller;
      setError('');
      setIsLoadingMore(Boolean(cursor));
      if (!cursor) setIsLoading(true);
      try {
        const params = new URLSearchParams({ page_size: '20' });
        if (cursor) params.set('cursor', cursor);
        if (search.trim()) params.set('search', search.trim());
        if (statusFilter !== 'all') params.set('status', statusFilter);
        const response = await api.get(`/projects/?${params}`, { signal: controller.signal });
        if (controller.signal.aborted) return;
        const list: Project[] = response?.data ?? [];
        setProjects((previous) => {
          if (!cursor) return list;
          const seen = new Set(previous.map((project) => project.id));
          return [...previous, ...list.filter((project) => !seen.has(project.id))];
        });
        setPagination({
          has_next: Boolean(response?.pagination?.has_next),
          next_cursor: response?.pagination?.next_cursor ?? null,
        });
        setLastUpdated(new Date());
      } catch (err) {
        if (!controller.signal.aborted) setError(errorMessage(err, 'Не удалось загрузить тендеры'));
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
          setIsLoadingMore(false);
        }
      }
    },
    [search, statusFilter]
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadProjects();
    }, 250);
    return () => {
      clearTimeout(timer);
      requestRef.current?.abort();
    };
  }, [loadProjects]);

  useEffect(() => {
    const openNewTender = () => setDialogOpen(true);
    window.addEventListener('binom:new-tender', openNewTender);
    const timer = setTimeout(() => {
      const url = new URL(window.location.href);
      if (url.searchParams.get('new') === '1') {
        setDialogOpen(true);
        url.searchParams.delete('new');
        window.history.replaceState(null, '', url.toString());
      }
    }, 0);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('binom:new-tender', openNewTender);
    };
  }, []);

  const closeEdit = () => {
    if (isSavingEdit) return;
    setEditTarget(null);
    setEditDraft(null);
    setMutationError('');
  };
  const closeDelete = () => {
    if (isDeleting) return;
    setDeleteTarget(null);
    setMutationError('');
  };
  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    setMutationError('');
    try {
      await api.delete(`/projects/${deleteTarget.id}`);
      setProjects((previous) => previous.filter((project) => project.id !== deleteTarget.id));
      setDeleteTarget(null);
      setNotice('Тендер удалён.');
    } catch (err) {
      setMutationError(errorMessage(err, 'Не удалось удалить тендер'));
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editTarget || !editDraft) return;
    if (!editDraft.name?.trim()) {
      setMutationError('Укажите название тендера.');
      return;
    }
    setIsSavingEdit(true);
    setMutationError('');
    try {
      const body: Record<string, unknown> = {
        name: editDraft.name.trim(),
        status: editDraft.status || 'draft',
        customer_name: editDraft.customer_name?.trim() || null,
        tender_number: editDraft.tender_number?.trim() || null,
        tender_type: editDraft.tender_type?.trim() || null,
        complexity: editDraft.complexity || null,
        notes: editDraft.notes?.trim() || null,
        deadline_at: editDraft.deadline_at ? new Date(editDraft.deadline_at).toISOString() : null,
      };
      const updated = await api.patch(`/projects/${editTarget.id}`, body);
      setProjects((previous) =>
        previous
          .map((project) => (project.id === editTarget.id ? { ...project, ...updated } : project))
          .filter((project) => statusFilter === 'all' || project.status === statusFilter)
      );
      setEditTarget(null);
      setEditDraft(null);
      setNotice('Изменения сохранены.');
      if (search.trim()) void loadProjects();
    } catch (err) {
      setMutationError(errorMessage(err, 'Не удалось сохранить изменения'));
    } finally {
      setIsSavingEdit(false);
    }
  };

  const stats = useMemo(() => {
    const now = lastUpdated?.getTime() ?? 0;
    const openDeadlines = projects.filter((project) =>
      ['soon', 'overdue'].includes(deadlineState(project, now))
    );
    return {
      working: projects.filter((project) => WORK_STATUSES.has(project.status)).length,
      review: projects.filter((project) => project.status === 'review').length,
      ready: projects.filter((project) => ['ready', 'done', 'submitted'].includes(project.status))
        .length,
      soon: projects.filter((project) => deadlineState(project, now) === 'soon').length,
      overdue: projects.filter((project) => deadlineState(project, now) === 'overdue').length,
      nearest: openDeadlines.sort(
        (a, b) => new Date(a.deadline_at!).getTime() - new Date(b.deadline_at!).getTime()
      )[0],
    };
  }, [projects, lastUpdated]);

  const hasFilters = Boolean(search.trim() || statusFilter !== 'all');
  const resetFilters = () => {
    setSearch('');
    setStatusFilter('all');
  };
  const now = lastUpdated?.getTime() ?? 0;
  const statCards = [
    {
      label: 'В работе',
      value: stats.working,
      icon: 'work_outline',
      note: 'Подготовка и AI-анализ',
      color: 'text-primary bg-primary/10',
    },
    {
      label: 'На проверке',
      value: stats.review,
      icon: 'fact_check',
      note: 'Нужно решение команды',
      color: 'text-violet-600 bg-violet-500/10',
    },
    {
      label: 'Срок до 7 дней',
      value: stats.soon,
      icon: 'event_upcoming',
      note: 'Ближайшие дедлайны',
      color: 'text-amber-600 bg-amber-500/10',
    },
    {
      label: 'Готово / подано',
      value: stats.ready,
      icon: 'task_alt',
      note: 'Подготовленные тендеры',
      color: 'text-emerald-600 bg-emerald-500/10',
    },
  ];

  return (
    <div className="theme-tenderpro mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 sm:px-6 lg:px-9 lg:py-8">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-on-surface-variant">
            Закупки под контролем
          </p>
          <h1 className="text-[28px] font-semibold leading-tight tracking-[-0.04em] text-on-surface sm:text-[34px]">
            {pageLabel}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-on-surface-variant">
            {pageDescription ||
              'Тендеры, поставщики и подготовка документов — в одном рабочем пространстве.'}
          </p>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-on-primary shadow-sm transition hover:opacity-90"
        >
          <Icon name="add" className="text-xl" />
          Новый тендер
        </button>
      </div>

      <div className="mb-7 grid gap-4 lg:grid-cols-[minmax(0,1.65fr)_minmax(280px,1fr)]">
        <section className="relative overflow-hidden rounded-2xl border border-blue-500/25 bg-[#122b58] px-6 py-7 text-white sm:px-8">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-14 -top-20 h-72 w-72 rounded-full border-[45px] border-white/[0.035]"
          />
          <div
            aria-hidden="true"
            className="absolute right-8 top-7 hidden h-16 w-16 rotate-6 items-center justify-center rounded-2xl border border-white/15 bg-white/5 sm:flex"
          >
            <Icon name="find_in_page" className="text-[34px] text-blue-200" />
          </div>
          <p className="mb-4 inline-flex items-center gap-2 text-xs font-medium text-blue-200">
            <Icon name="bolt" className="text-base" />
            Быстрая проверка
          </p>
          <h2 className="max-w-md text-[24px] font-semibold leading-tight tracking-[-0.03em] sm:text-[28px]">
            От технического задания
            <br />к предложениям продавцов
          </h2>
          <p className="mt-3 max-w-md text-sm leading-relaxed text-blue-100/75">
            Загрузите PDF или Word: извлеките позиции и найдите товары, цены и контакты для
            проверки.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <Link
              href="/quick-check"
              className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-white px-4 text-sm font-semibold text-[#122b58] shadow-sm transition hover:bg-blue-50"
            >
              Проверить документ
              <Icon name="arrow_forward" className="text-lg" />
            </Link>
            <span className="text-xs text-blue-100/65">PDF · DOCX</span>
          </div>
        </section>

        <section className="flex flex-col rounded-2xl border border-outline-variant bg-surface-container-lowest p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-on-surface">Следующий шаг</h2>
            <Icon name="explore" className="text-xl text-primary" />
          </div>
          {isLoading ? (
            <div className="space-y-3" aria-label="Загрузка приоритетов">
              <div className="shimmer h-5 w-3/4 rounded" />
              <div className="shimmer h-4 w-full rounded" />
              <div className="shimmer h-4 w-2/3 rounded" />
            </div>
          ) : error && !lastUpdated ? (
            <>
              <p className="text-base font-semibold text-on-surface">Обновите данные</p>
              <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
                Список тендеров недоступен. Повторите загрузку, чтобы увидеть актуальные задачи.
              </p>
              <button
                onClick={() => void loadProjects()}
                className="mt-auto inline-flex items-center gap-2 pt-5 text-sm font-semibold text-primary"
              >
                Повторить загрузку
                <Icon name="refresh" className="text-lg" />
              </button>
            </>
          ) : stats.nearest ? (
            <>
              <p
                className={`mb-2 text-xs font-semibold ${deadlineState(stats.nearest, now) === 'overdue' ? 'text-error' : 'text-amber-600'}`}
              >
                {deadlineState(stats.nearest, now) === 'overdue'
                  ? 'Срок уже прошёл'
                  : 'Приближается дедлайн'}{' '}
                · {formatDate(stats.nearest.deadline_at)}
              </p>
              <p className="line-clamp-2 text-base font-semibold leading-snug text-on-surface">
                {stats.nearest.name}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
                Проверьте готовность документов и актуальность статуса.
              </p>
              <Link
                href={`/projects/${stats.nearest.id}/document`}
                className="mt-auto inline-flex items-center gap-2 pt-5 text-sm font-semibold text-primary"
              >
                Открыть тендер
                <Icon name="arrow_forward" className="text-lg" />
              </Link>
            </>
          ) : (
            <>
              <p className="text-base font-semibold text-on-surface">
                {projects.length
                  ? 'Продолжите подготовку'
                  : hasFilters
                    ? 'Измените выборку'
                    : 'Начните с первого тендера'}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
                {projects.length
                  ? 'Откройте тендер, сравните найденные товары и рассчитайте экономику закупки.'
                  : hasFilters
                    ? 'По выбранным условиям тендеров нет. Сбросьте фильтры или выполните новый поиск.'
                    : 'Создайте тендер и загрузите техническое задание. Документы, анализ и товары будут собраны в одном проекте.'}
              </p>
              {projects.length ? (
                <Link
                  href={`/projects/${projects[0].id}/products`}
                  className="mt-auto inline-flex items-center gap-2 pt-5 text-sm font-semibold text-primary"
                >
                  Перейти к товарам
                  <Icon name="arrow_forward" className="text-lg" />
                </Link>
              ) : (
                <button
                  onClick={hasFilters ? resetFilters : () => setDialogOpen(true)}
                  className="mt-auto inline-flex items-center gap-2 pt-5 text-sm font-semibold text-primary"
                >
                  {hasFilters ? 'Сбросить фильтры' : 'Создать тендер'}
                  <Icon name="arrow_forward" className="text-lg" />
                </button>
              )}
            </>
          )}
        </section>
      </div>

      {user?.role === 'limited' && (
        <div className="mb-5 flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm text-on-surface">
          <Icon name="lock" className="text-xl text-primary" />
          <p>У вас ограниченный доступ. Полный доступ можно запросить у владельца платформы.</p>
        </div>
      )}

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-on-surface">Обзор загруженных тендеров</h2>
        <span className="text-xs text-on-surface-variant">
          {isLoading
            ? 'Загружаем данные…'
            : error && !lastUpdated
              ? 'Данные недоступны'
              : `${projects.length}${pagination.has_next ? '+' : ''} тендеров · показатели по загруженным данным`}
        </span>
      </div>
      <div className="mb-7 grid grid-cols-2 gap-3 xl:grid-cols-4">
        {statCards.map((card) => (
          <div
            key={card.label}
            className="rounded-2xl border border-outline-variant bg-surface-container-lowest p-4 sm:p-5"
          >
            <div className="mb-4 flex items-center justify-between gap-2">
              <p className="text-xs font-medium text-on-surface-variant sm:text-sm">{card.label}</p>
              <span
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${card.color}`}
              >
                <Icon name={card.icon} className="text-lg" />
              </span>
            </div>
            {isLoading ? (
              <div className="shimmer h-8 w-12 rounded" />
            ) : (
              <p className="text-[30px] font-semibold leading-none tracking-[-0.04em] text-on-surface">
                {error && !lastUpdated ? '—' : card.value}
              </p>
            )}
            <p className="mt-2 text-[11px] leading-relaxed text-on-surface-variant sm:text-xs">
              {card.note}
            </p>
          </div>
        ))}
      </div>

      <section
        className="overflow-hidden rounded-2xl border border-outline-variant bg-surface-container-lowest"
        aria-labelledby="portfolio-heading"
      >
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-outline-variant px-5 py-5 sm:px-6">
          <div>
            <h2 id="portfolio-heading" className="text-base font-semibold text-on-surface">
              Тендерный портфель
            </h2>
            <p className="mt-1 text-xs text-on-surface-variant">
              Управляйте закупками от технического задания до подачи.
            </p>
          </div>
          <button
            onClick={() => void loadProjects()}
            disabled={isLoading || isLoadingMore}
            className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-outline-variant px-3 text-xs font-medium text-on-surface-variant transition hover:bg-surface-container disabled:opacity-50"
          >
            <Icon name="refresh" className={`text-base ${isLoading ? 'animate-spin' : ''}`} />
            Обновить
          </button>
        </div>
        <div className="flex flex-col gap-3 border-b border-outline-variant bg-surface-container-low/40 px-5 py-4 sm:flex-row sm:items-center sm:px-6">
          <div className="relative flex-1">
            <Icon
              name="search"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xl text-on-surface-variant"
            />
            <input
              aria-label="Поиск тендеров"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Название, заказчик или номер тендера"
              className={`${FIELD_CLASS} pl-10 pr-10`}
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-3 top-1/2 flex -translate-y-1/2 text-on-surface-variant hover:text-on-surface"
                aria-label="Очистить поиск"
              >
                <Icon name="close" className="text-lg" />
              </button>
            )}
          </div>
          <select
            aria-label="Фильтр по статусу"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className={`${FIELD_CLASS} sm:w-48`}
          >
            {STATUS_OPTIONS.map((status) => (
              <option key={status.value} value={status.value}>
                {status.label}
              </option>
            ))}
          </select>
          {hasFilters && (
            <button
              onClick={resetFilters}
              className="min-h-10 shrink-0 rounded-lg px-2 text-xs font-medium text-primary hover:bg-primary/5"
            >
              Сбросить
            </button>
          )}
        </div>

        {notice && (
          <div
            role="status"
            className="flex items-center justify-between gap-3 border-b border-emerald-500/15 bg-emerald-500/5 px-6 py-3 text-sm text-on-surface"
          >
            <span className="flex items-center gap-2">
              <Icon name="check_circle" className="text-lg text-emerald-600" />
              {notice}
            </span>
            <button aria-label="Закрыть уведомление" onClick={() => setNotice('')}>
              <Icon name="close" className="text-lg" />
            </button>
          </div>
        )}
        {error && (
          <div
            role="alert"
            className="mx-5 my-4 rounded-xl border border-error/20 bg-error-container p-4 text-sm text-on-error-container"
          >
            <p>{error}</p>
            {lastUpdated && <p className="mt-1">Показаны последние успешно загруженные данные.</p>}
            <button
              onClick={() => void loadProjects()}
              className="mt-2 font-semibold underline underline-offset-2"
            >
              Повторить загрузку
            </button>
          </div>
        )}

        <div aria-busy={isLoading || isLoadingMore}>
          {isLoading ? (
            <div
              role="status"
              aria-label="Загрузка тендеров"
              className="divide-y divide-outline-variant px-5 sm:px-6"
            >
              {[0, 1, 2, 3].map((index) => (
                <div key={index} className="flex items-center justify-between gap-8 py-6">
                  <div className="flex-1 space-y-3">
                    <div className="shimmer h-4 w-2/3 max-w-md rounded" />
                    <div className="shimmer h-3 w-1/3 rounded" />
                  </div>
                  <div className="shimmer h-7 w-20 rounded-full" />
                </div>
              ))}
            </div>
          ) : projects.length === 0 && !error ? (
            <div className="flex flex-col items-center px-6 py-14 text-center">
              <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/8 text-primary">
                <Icon name={hasFilters ? 'search_off' : 'folder_open'} className="text-[28px]" />
              </span>
              <h3 className="text-lg font-semibold text-on-surface">
                {hasFilters ? 'Тендеры не найдены' : 'Ваш портфель начинается здесь'}
              </h3>
              <p className="mt-2 max-w-md text-sm leading-relaxed text-on-surface-variant">
                {hasFilters
                  ? 'Попробуйте другой запрос или сбросьте фильтр по статусу.'
                  : 'Создайте первый тендер, чтобы собрать техническое задание, найденные товары и расчёты в одном месте.'}
              </p>
              <button
                onClick={hasFilters ? resetFilters : () => setDialogOpen(true)}
                className="mt-6 inline-flex min-h-10 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-on-primary"
              >
                <Icon name={hasFilters ? 'filter_alt_off' : 'add'} className="text-lg" />
                {hasFilters ? 'Сбросить фильтры' : 'Создать первый тендер'}
              </button>
            </div>
          ) : projects.length > 0 ? (
            <>
              <div className="hidden grid-cols-[minmax(220px,2.2fr)_minmax(140px,1fr)_150px_140px_100px] gap-5 border-b border-outline-variant bg-surface-container-low/30 px-6 py-3 text-[10px] font-semibold uppercase tracking-[0.1em] text-on-surface-variant xl:grid">
                <span>Тендер / заказчик</span>
                <span>Статус</span>
                <span>Срок подачи</span>
                <span>Обновление</span>
                <span className="text-right">Действия</span>
              </div>
              <div className="divide-y divide-outline-variant">
                {projects.map((project) => {
                  const deadline = deadlineState(project, now);
                  return (
                    <article
                      key={project.id}
                      className="group grid gap-4 px-5 py-5 transition hover:bg-primary/[0.025] sm:px-6 xl:grid-cols-[minmax(220px,2.2fr)_minmax(140px,1fr)_150px_140px_100px] xl:items-center xl:gap-5"
                    >
                      <div className="flex min-w-0 items-start gap-3">
                        <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-outline-variant bg-surface-container-low text-primary">
                          <Icon name="description" className="text-xl" />
                        </span>
                        <div className="min-w-0">
                          <Link
                            href={`/projects/${project.id}/document`}
                            className="line-clamp-2 text-sm font-semibold leading-relaxed text-on-surface transition hover:text-primary"
                          >
                            {project.name}
                          </Link>
                          <p className="mt-1 truncate text-xs text-on-surface-variant">
                            {project.customer_name || 'Заказчик не указан'}
                          </p>
                          {project.tender_number && (
                            <p className="mt-1 font-mono text-[11px] text-on-surface-variant">
                              № {project.tender_number}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-3 xl:block">
                        <span className="text-xs text-on-surface-variant xl:hidden">Статус</span>
                        <StatusBadge status={project.status} />
                      </div>
                      <div>
                        <p
                          className={`text-xs font-medium ${deadline === 'overdue' ? 'text-error' : deadline === 'soon' ? 'text-amber-600' : 'text-on-surface'}`}
                        >
                          {project.deadline_at ? formatDate(project.deadline_at) : 'Срок не указан'}
                        </p>
                        {deadline === 'overdue' ? (
                          <p className="mt-1 text-[11px] text-error">Срок прошёл</p>
                        ) : deadline === 'soon' ? (
                          <p className="mt-1 text-[11px] text-amber-600">В ближайшие 7 дней</p>
                        ) : (
                          <p className="mt-1 text-[11px] text-on-surface-variant">Срок подачи</p>
                        )}
                      </div>
                      <div className="hidden xl:block">
                        <p className="text-xs text-on-surface">
                          {formatDate(project.updated_at || project.created_at)}
                        </p>
                        <Link
                          href={`/projects/${project.id}/products`}
                          className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
                        >
                          Товары и цены
                          <Icon name="north_east" className="text-[12px]" />
                        </Link>
                      </div>
                      <div className="flex items-center gap-1 border-t border-outline-variant/60 pt-3 xl:justify-end xl:border-0 xl:pt-0">
                        <Link
                          href={`/projects/${project.id}/products`}
                          className="mr-auto inline-flex min-h-8 items-center gap-1.5 rounded-lg bg-primary/8 px-3 text-xs font-semibold text-primary hover:bg-primary/15 xl:hidden"
                        >
                          <Icon name="inventory_2" className="text-base" />
                          Товары и цены
                        </Link>
                        <button
                          onClick={() => {
                            setMutationError('');
                            setEditTarget(project);
                            setEditDraft({
                              ...project,
                              deadline_at: toLocalInput(project.deadline_at),
                            });
                          }}
                          className="flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant transition hover:bg-primary/8 hover:text-primary"
                          aria-label={`Редактировать тендер ${project.name}`}
                          title="Редактировать"
                        >
                          <Icon name="edit" className="text-lg" />
                        </button>
                        <button
                          onClick={() => {
                            setMutationError('');
                            setDeleteTarget(project);
                          }}
                          className="flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant transition hover:bg-error-container hover:text-error"
                          aria-label={`Удалить тендер ${project.name}`}
                          title="Удалить"
                        >
                          <Icon name="delete" className="text-lg" />
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            </>
          ) : null}
        </div>

        {!isLoading && lastUpdated && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-outline-variant bg-surface-container-low/30 px-5 py-4 text-xs text-on-surface-variant sm:px-6">
            <span role="status">
              Показано {projects.length}
              {pagination.has_next ? ' · есть ещё тендеры' : ''}
              {stats.overdue > 0 ? ` · прошедших сроков: ${stats.overdue}` : ''}
            </span>
            {pagination.has_next && pagination.next_cursor ? (
              <button
                onClick={() => void loadProjects(pagination.next_cursor!)}
                disabled={isLoadingMore}
                className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 font-semibold text-on-surface transition hover:border-primary/40 disabled:opacity-50"
              >
                <Icon
                  name={isLoadingMore ? 'progress_activity' : 'expand_more'}
                  className={`text-base ${isLoadingMore ? 'animate-spin' : ''}`}
                />
                {isLoadingMore ? 'Загружаем…' : 'Загрузить ещё'}
              </button>
            ) : (
              <span>
                Обновлено в{' '}
                {lastUpdated.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
        )}
      </section>

      <NewTenderDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />

      {editTarget && editDraft && (
        <DashboardDialog titleId="edit-tender-title" onClose={closeEdit}>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleSaveEdit();
            }}
          >
            <div className="flex items-start justify-between gap-4 border-b border-outline-variant px-6 py-5">
              <div>
                <h2 id="edit-tender-title" className="text-lg font-semibold">
                  Данные тендера
                </h2>
                <p className="mt-1 text-sm text-on-surface-variant">
                  Актуальные сведения для вашей команды.
                </p>
              </div>
              <button
                type="button"
                onClick={closeEdit}
                disabled={isSavingEdit}
                aria-label="Закрыть редактирование"
                className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-surface-container disabled:opacity-50"
              >
                <Icon name="close" className="text-xl" />
              </button>
            </div>
            <fieldset disabled={isSavingEdit} className="space-y-4 px-6 py-5 disabled:opacity-60">
              <div>
                <label
                  htmlFor="edit-tender-name"
                  className="mb-1.5 block text-xs font-semibold text-on-surface-variant"
                >
                  Название *
                </label>
                <input
                  id="edit-tender-name"
                  required
                  autoFocus
                  className={FIELD_CLASS}
                  value={editDraft.name ?? ''}
                  onChange={(event) => setEditDraft({ ...editDraft, name: event.target.value })}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="edit-customer"
                    className="mb-1.5 block text-xs font-semibold text-on-surface-variant"
                  >
                    Заказчик
                  </label>
                  <input
                    id="edit-customer"
                    className={FIELD_CLASS}
                    value={editDraft.customer_name ?? ''}
                    onChange={(event) =>
                      setEditDraft({ ...editDraft, customer_name: event.target.value })
                    }
                  />
                </div>
                <div>
                  <label
                    htmlFor="edit-number"
                    className="mb-1.5 block text-xs font-semibold text-on-surface-variant"
                  >
                    Номер тендера
                  </label>
                  <input
                    id="edit-number"
                    className={FIELD_CLASS}
                    value={editDraft.tender_number ?? ''}
                    onChange={(event) =>
                      setEditDraft({ ...editDraft, tender_number: event.target.value })
                    }
                  />
                </div>
                <div>
                  <label
                    htmlFor="edit-type"
                    className="mb-1.5 block text-xs font-semibold text-on-surface-variant"
                  >
                    Тип закупки
                  </label>
                  <input
                    id="edit-type"
                    className={FIELD_CLASS}
                    placeholder="Например, госзакупки"
                    value={editDraft.tender_type ?? ''}
                    onChange={(event) =>
                      setEditDraft({ ...editDraft, tender_type: event.target.value })
                    }
                  />
                </div>
                <div>
                  <label
                    htmlFor="edit-complexity"
                    className="mb-1.5 block text-xs font-semibold text-on-surface-variant"
                  >
                    Сложность
                  </label>
                  <select
                    id="edit-complexity"
                    className={FIELD_CLASS}
                    value={editDraft.complexity ?? ''}
                    onChange={(event) =>
                      setEditDraft({ ...editDraft, complexity: event.target.value })
                    }
                  >
                    <option value="">Не указана</option>
                    <option value="low">Низкая</option>
                    <option value="medium">Средняя</option>
                    <option value="high">Высокая</option>
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="edit-deadline"
                    className="mb-1.5 block text-xs font-semibold text-on-surface-variant"
                  >
                    Срок подачи
                  </label>
                  <input
                    id="edit-deadline"
                    type="datetime-local"
                    className={FIELD_CLASS}
                    value={editDraft.deadline_at ?? ''}
                    onChange={(event) =>
                      setEditDraft({ ...editDraft, deadline_at: event.target.value })
                    }
                  />
                </div>
                <div>
                  <label
                    htmlFor="edit-status"
                    className="mb-1.5 block text-xs font-semibold text-on-surface-variant"
                  >
                    Статус
                  </label>
                  <select
                    id="edit-status"
                    className={FIELD_CLASS}
                    value={editDraft.status ?? 'draft'}
                    onChange={(event) => setEditDraft({ ...editDraft, status: event.target.value })}
                  >
                    {STATUS_OPTIONS.filter((status) => status.value !== 'all').map((status) => (
                      <option key={status.value} value={status.value}>
                        {status.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label
                  htmlFor="edit-notes"
                  className="mb-1.5 block text-xs font-semibold text-on-surface-variant"
                >
                  Заметки
                </label>
                <textarea
                  id="edit-notes"
                  rows={3}
                  className={`${FIELD_CLASS} resize-y`}
                  value={editDraft.notes ?? ''}
                  onChange={(event) => setEditDraft({ ...editDraft, notes: event.target.value })}
                />
              </div>
            </fieldset>
            {mutationError && (
              <p
                role="alert"
                className="mx-6 mb-4 rounded-xl bg-error-container p-3 text-sm text-on-error-container"
              >
                {mutationError}
              </p>
            )}
            <div className="flex justify-end gap-3 border-t border-outline-variant bg-surface-container-low px-6 py-4">
              <button
                type="button"
                onClick={closeEdit}
                disabled={isSavingEdit}
                className="rounded-xl border border-outline-variant px-4 py-2.5 text-sm font-medium disabled:opacity-50"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={isSavingEdit}
                className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-on-primary disabled:opacity-50"
              >
                {isSavingEdit && <Icon name="progress_activity" className="animate-spin text-lg" />}
                {isSavingEdit ? 'Сохраняем…' : 'Сохранить'}
              </button>
            </div>
          </form>
        </DashboardDialog>
      )}

      {deleteTarget && (
        <DashboardDialog titleId="delete-tender-title" onClose={closeDelete}>
          <div className="px-6 py-6">
            <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-error-container text-error">
              <Icon name="delete" className="text-[24px]" />
            </span>
            <h2 id="delete-tender-title" className="text-lg font-semibold">
              Удалить тендер?
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
              «{deleteTarget.name}», техническое задание, анализ и связанные документы будут удалены
              безвозвратно.
            </p>
            {mutationError && (
              <p
                role="alert"
                className="mt-4 rounded-xl bg-error-container p-3 text-sm text-on-error-container"
              >
                {mutationError}
              </p>
            )}
          </div>
          <div className="flex justify-end gap-3 border-t border-outline-variant bg-surface-container-low px-6 py-4">
            <button
              autoFocus
              onClick={closeDelete}
              disabled={isDeleting}
              className="rounded-xl border border-outline-variant px-4 py-2.5 text-sm font-medium disabled:opacity-50"
            >
              Отмена
            </button>
            <button
              onClick={() => void handleDelete()}
              disabled={isDeleting}
              className="inline-flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
            >
              {isDeleting && <Icon name="progress_activity" className="animate-spin text-lg" />}
              {isDeleting ? 'Удаляем…' : 'Удалить тендер'}
            </button>
          </div>
        </DashboardDialog>
      )}
    </div>
  );
}
