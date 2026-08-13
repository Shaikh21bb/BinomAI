'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, errorMessage } from '@/lib/api';
import { StatusBadge, EmptyState, formatDate } from '@/components/ui';
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

const STATUS_OPTIONS: { value: string; label: string }[] = [
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
  { value: 'error', label: 'Ошибка' },
];

interface Props {
  pageLabel?: string;
  pageDescription?: string;
}

export function ProjectsDashboard({ pageLabel = 'Мои тендеры', pageDescription }: Props) {
  const router = useRouter();
  const { user } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [pagination, setPagination] = useState<{ has_next: boolean; next_cursor?: string | null }>({
    has_next: false,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [editTarget, setEditTarget] = useState<Project | null>(null);
  const [editDraft, setEditDraft] = useState<Partial<Project> | null>(null);
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  const loadProjects = async (cursor?: string) => {
    try {
      const params = new URLSearchParams({ page_size: '20' });
      if (cursor) params.set('cursor', cursor);
      if (search.trim()) params.set('search', search.trim());
      if (statusFilter !== 'all') params.set('status', statusFilter);
      const url = `/projects/?${params.toString()}`;
      if (!cursor) setIsLoading(true);
      const res = await api.get(url);
      const list = res?.data ?? [];
      const meta = res?.pagination ?? {};
      if (cursor) {
        setProjects((prev) => {
          const seen = new Set(prev.map((p) => p.id));
          return [...prev, ...list.filter((p: Project) => !seen.has(p.id))];
        });
      } else {
        setProjects(list);
      }
      setPagination({
        has_next: Boolean(meta.has_next),
        next_cursor: meta.next_cursor ?? null,
      });
    } catch (err) {
      setError(errorMessage(err, 'Не удалось загрузить тендеры'));
    } finally {
      if (!cursor) setIsLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      loadProjects();
    }, 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, statusFilter]);

  useEffect(() => {
    if (dialogOpen) return;
    const timer = setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      if (params.get('new') === '1') {
        setDialogOpen(true);
        const url = new URL(window.location.href);
        url.searchParams.delete('new');
        window.history.replaceState(null, '', url.toString());
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [dialogOpen]);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await api.delete(`/projects/${deleteTarget.id}`);
      setProjects((prev) => prev.filter((p) => p.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err) {
      setError(errorMessage(err, 'Не удалось удалить тендер'));
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editTarget || !editDraft) return;
    if (!editDraft.name?.trim()) {
      setError('Название тендера обязательно');
      return;
    }
    setIsSavingEdit(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        name: editDraft.name.trim(),
        status: editDraft.status || 'draft',
      };
      if (editDraft.customer_name) body.customer_name = editDraft.customer_name;
      if (editDraft.tender_number) body.tender_number = editDraft.tender_number;
      if (editDraft.tender_type) body.tender_type = editDraft.tender_type;
      if (editDraft.complexity) body.complexity = editDraft.complexity;
      if (editDraft.notes) body.notes = editDraft.notes;
      if (editDraft.deadline_at) body.deadline_at = new Date(editDraft.deadline_at).toISOString();
      const updated = await api.patch(`/projects/${editTarget.id}`, body);
      setProjects((prev) => prev.map((p) => (p.id === editTarget.id ? { ...p, ...updated } : p)));
      setEditTarget(null);
      setEditDraft(null);
    } catch (err) {
      setError(errorMessage(err, 'Не удалось сохранить изменения'));
    } finally {
      setIsSavingEdit(false);
    }
  };

  const stats = useMemo(() => {
    const active = new Set(['draft', 'processing', 'analyzing', 'clarifying', 'generating', 'searching']);
    const finished = new Set(['ready', 'done', 'submitted', 'review', 'archived']);
    return {
      total: projects.length,
      inProgress: projects.filter((p) => active.has(p.status)).length,
      finished: projects.filter((p) => finished.has(p.status)).length,
    };
  }, [projects]);

  const STAT_CARDS = [
    { label: 'Всего тендеров', value: stats.total, icon: 'folder_open' },
    { label: 'В работе', value: stats.inProgress, icon: 'hourglass_top' },
    { label: 'Завершено / подано', value: stats.finished, icon: 'task_alt' },
  ];

  return (
    <div className="p-4 md:p-margin-page max-w-container-max w-full mx-auto flex-1 theme-tenderpro">
      {/* Page header */}
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div>
          <h2 className="text-display font-display text-on-surface tracking-tight">{pageLabel}</h2>
          {pageDescription && (
            <p className="text-body-lg font-body-lg text-on-surface-variant mt-1">{pageDescription}</p>
          )}
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity shadow-sm active:scale-[0.98] duration-150"
        >
          <span className="material-symbols-outlined text-[18px]">add</span>
          Новый тендер
        </button>
      </div>

      {/* Limited access banner */}
      {user?.role === 'limited' && (
        <div className="mb-6 p-4 bg-primary/5 border border-primary/20 rounded-lg flex flex-wrap items-center gap-3">
          <span className="material-symbols-outlined text-[20px] text-primary shrink-0">lock</span>
          <p className="flex-1 min-w-[200px] text-body-sm font-body-sm text-on-surface">
            Ограниченный доступ: использовано {projects.length} из 2 доступных тендеров.
            Для полного доступа запросите инвайт-код у владельца платформы.
          </p>
        </div>
      )}

      {/* Stats */}
      {!isLoading && projects.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          {STAT_CARDS.map((card) => (
            <div
              key={card.label}
              className="flex items-center gap-4 bg-surface-container-lowest border border-outline-variant rounded-lg p-stack-md"
            >
              <div className="w-10 h-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
                <span className="material-symbols-outlined text-[22px]">{card.icon}</span>
              </div>
              <div>
                <div className="text-headline-lg font-headline-lg text-on-surface leading-none">{card.value}</div>
                <div className="text-label-md font-label-md text-on-surface-variant mt-1">{card.label}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="relative flex-1 min-w-[220px] max-w-sm">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]">
            search
          </span>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по названию, заказчику, номеру..."
            className="w-full pl-9 pr-9 py-2 bg-surface-bright border border-outline-variant rounded-lg text-body-md font-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-on-surface-variant hover:text-on-surface"
              aria-label="Очистить поиск"
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>
          )}
        </div>

        <div className="relative">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="appearance-none pl-9 pr-9 py-2 bg-surface-bright border border-outline-variant rounded-lg text-body-md font-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors cursor-pointer"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px] pointer-events-none">
            filter_list
          </span>
          <span className="material-symbols-outlined absolute right-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px] pointer-events-none">
            expand_more
          </span>
        </div>

        <span className="ml-auto text-mono-sm font-mono-sm text-on-surface-variant">
          Показано {projects.length}
          {pagination.has_next ? ' · загрузить ещё' : ''}
        </span>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-error-container text-on-error-container rounded-lg text-body-md font-body-md">
          {error}
          <button
            onClick={() => loadProjects()}
            className="ml-3 underline font-medium"
          >
            Повторить
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="flex flex-col gap-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="shimmer rounded-lg p-stack-md border border-outline-variant">
              <div className="w-1/3 h-5 bg-surface-container-high rounded mb-3" />
              <div className="w-2/3 h-4 bg-surface-container rounded mb-2" />
              <div className="w-1/4 h-3 bg-surface-container rounded" />
            </div>
          ))}
        </div>
      ) : projects.length === 0 ? (
        !search.trim() && statusFilter === 'all' ? (
          <EmptyState
            icon="folder_open"
            title="Нет активных тендеров"
            description="Создайте первый тендер, загрузите техническое задание — и AI сформирует для вас полный тендерный пакет."
            action={{ label: 'Создать тендер', onClick: () => setDialogOpen(true) }}
          />
        ) : (
          <EmptyState
            icon="search_off"
            title="Ничего не найдено"
            description="Попробуйте изменить поисковый запрос или сбросить фильтр."
            action={{ label: 'Сбросить фильтры', onClick: () => { setSearch(''); setStatusFilter('all'); } }}
          />
        )
      ) : (
        <div className="flex flex-col gap-4">
          {projects.map((project) => (
            <article
              key={project.id}
              onClick={() => router.push(`/projects/${project.id}/document`)}
              className="group w-full bg-surface-container-lowest border border-outline-variant rounded-lg p-stack-md hover:border-on-background/20 hover:shadow-[0_4px_16px_rgba(0,0,0,0.04)] transition-all cursor-pointer"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex flex-col gap-1 min-w-0">
                  <h3 className="text-headline-md font-headline-md text-on-surface group-hover:text-primary transition-colors truncate">
                    {project.name}
                  </h3>
                  <div className="flex items-center gap-3 text-body-md font-body-md text-on-surface-variant">
                    {project.customer_name && (
                      <span className="flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-[16px]">domain</span>
                        {project.customer_name}
                      </span>
                    )}
                    {project.tender_number && (
                      <span className="flex items-center gap-1 text-mono-sm font-mono-sm text-secondary">
                        <span className="material-symbols-outlined text-[16px]">tag</span>
                        {project.tender_number}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-col sm:items-end gap-2 shrink-0">
                  <div className="flex items-center gap-3">
                    <StatusBadge status={project.status} />
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditTarget(project);
                        setEditDraft({
                          name: project.name,
                          customer_name: project.customer_name ?? '',
                          tender_number: project.tender_number ?? '',
                          tender_type: project.tender_type ?? '',
                          complexity: project.complexity ?? '',
                          status: project.status,
                          deadline_at: project.deadline_at ?? '',
                          notes: project.notes ?? '',
                        });
                      }}
                      className="w-8 h-8 flex items-center justify-center rounded-lg text-on-surface-variant hover:text-primary hover:bg-primary/10 transition-colors"
                      aria-label="Редактировать тендер"
                      title="Редактировать"
                    >
                      <span className="material-symbols-outlined text-[18px]">edit</span>
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteTarget(project);
                      }}
                      className="w-8 h-8 flex items-center justify-center rounded-lg text-on-surface-variant hover:text-error hover:bg-error-container transition-colors"
                      aria-label="Удалить тендер"
                      title="Удалить"
                    >
                      <span className="material-symbols-outlined text-[18px]">delete</span>
                    </button>
                  </div>
                  <div className="text-mono-sm font-mono-sm text-on-surface-variant flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px]">event</span>
                    Дедлайн: {formatDate(project.deadline_at)}
                  </div>
                </div>
              </div>

              {project.notes && (
                <p className="mt-3 pt-3 border-t border-outline-variant/60 text-body-md font-body-md text-on-surface-variant">
                  {project.notes}
                </p>
              )}
            </article>
          ))}

          {pagination.has_next && (
            <button
              onClick={() => loadProjects(pagination.next_cursor ?? undefined)}
              className="mx-auto mt-2 px-4 py-2 bg-surface-bright border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface hover:bg-surface-container-low transition-colors"
            >
              Загрузить ещё
            </button>
          )}
        </div>
      )}

      <NewTenderDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />

      {/* Edit dialog */}
      {editTarget && editDraft && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) {
              setEditTarget(null);
              setEditDraft(null);
            }
          }}
        >
          <div className="w-full max-w-lg bg-surface-bright rounded-lg shadow-xl border border-outline-variant overflow-hidden">
            <div className="px-6 pt-5 pb-4">
              <h2 className="text-headline-md font-headline-md text-on-surface mb-1">Редактировать тендер</h2>
              <p className="text-body-sm font-body-sm text-on-surface-variant">
                Измените данные и нажмите «Сохранить».
              </p>
            </div>
            <div className="px-6 pb-4 space-y-4 max-h-[60vh] overflow-y-auto">
              <div className="space-y-1.5">
                <label className="block text-label-md font-label-md text-on-surface-variant">Название *</label>
                <input
                  className="w-full bg-surface-container-lowest border border-outline-variant rounded-md px-3 py-2 text-body-md font-body-md text-on-surface focus:outline-none focus:border-on-background"
                  value={editDraft.name ?? ''}
                  onChange={(e) => setEditDraft({ ...editDraft, name: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="block text-label-md font-label-md text-on-surface-variant">Заказчик</label>
                  <input
                    className="w-full bg-surface-container-lowest border border-outline-variant rounded-md px-3 py-2 text-body-md font-body-md text-on-surface focus:outline-none focus:border-on-background"
                    value={editDraft.customer_name ?? ''}
                    onChange={(e) => setEditDraft({ ...editDraft, customer_name: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block text-label-md font-label-md text-on-surface-variant">Номер тендера</label>
                  <input
                    className="w-full bg-surface-container-lowest border border-outline-variant rounded-md px-3 py-2 text-body-md font-body-md text-on-surface focus:outline-none focus:border-on-background font-mono-sm font-mono-sm"
                    value={editDraft.tender_number ?? ''}
                    onChange={(e) => setEditDraft({ ...editDraft, tender_number: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block text-label-md font-label-md text-on-surface-variant">Тип</label>
                  <input
                    className="w-full bg-surface-container-lowest border border-outline-variant rounded-md px-3 py-2 text-body-md font-body-md text-on-surface focus:outline-none focus:border-on-background"
                    placeholder="Например: Госзакупки"
                    value={editDraft.tender_type ?? ''}
                    onChange={(e) => setEditDraft({ ...editDraft, tender_type: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block text-label-md font-label-md text-on-surface-variant">Сложность</label>
                  <select
                    className="w-full bg-surface-container-lowest border border-outline-variant rounded-md px-3 py-2 text-body-md font-body-md text-on-surface focus:outline-none focus:border-on-background"
                    value={editDraft.complexity ?? ''}
                    onChange={(e) => setEditDraft({ ...editDraft, complexity: e.target.value })}
                  >
                    <option value="">—</option>
                    <option value="low">Низкая</option>
                    <option value="medium">Средняя</option>
                    <option value="high">Высокая</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="block text-label-md font-label-md text-on-surface-variant">Дедлайн</label>
                  <input
                    type="datetime-local"
                    className="w-full bg-surface-container-lowest border border-outline-variant rounded-md px-3 py-2 text-body-md font-body-md text-on-surface focus:outline-none focus:border-on-background"
                    value={editDraft.deadline_at ? new Date(editDraft.deadline_at).toISOString().slice(0, 16) : ''}
                    onChange={(e) =>
                      setEditDraft({ ...editDraft, deadline_at: e.target.value ? new Date(e.target.value).toISOString() : '' })
                    }
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block text-label-md font-label-md text-on-surface-variant">Статус</label>
                  <select
                    className="w-full bg-surface-container-lowest border border-outline-variant rounded-md px-3 py-2 text-body-md font-body-md text-on-surface focus:outline-none focus:border-on-background"
                    value={editDraft.status ?? 'draft'}
                    onChange={(e) => setEditDraft({ ...editDraft, status: e.target.value })}
                  >
                    {STATUS_OPTIONS.filter((s) => s.value !== 'all').map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="block text-label-md font-label-md text-on-surface-variant">Заметки</label>
                <textarea
                  rows={3}
                  className="w-full bg-surface-container-lowest border border-outline-variant rounded-md px-3 py-2 text-body-md font-body-md text-on-surface focus:outline-none focus:border-on-background resize-none"
                  value={editDraft.notes ?? ''}
                  onChange={(e) => setEditDraft({ ...editDraft, notes: e.target.value })}
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 bg-surface-container-low border-t border-outline-variant/60">
              <button
                onClick={() => {
                  setEditTarget(null);
                  setEditDraft(null);
                }}
                className="px-4 py-2 bg-surface-bright border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface-variant hover:bg-surface-container transition-colors"
              >
                Отмена
              </button>
              <button
                onClick={handleSaveEdit}
                disabled={isSavingEdit}
                className="px-5 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
              >
                {isSavingEdit && <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>}
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {deleteTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setDeleteTarget(null);
          }}
        >
          <div className="w-full max-w-md bg-surface-bright rounded-lg shadow-xl border border-outline-variant overflow-hidden">
            <div className="px-6 pt-5 pb-4">
              <h2 className="text-headline-md font-headline-md text-on-surface mb-1">Удалить тендер?</h2>
              <p className="text-body-md font-body-md text-on-surface-variant">
                Тендер «{deleteTarget.name}» и все связанные данные (ТЗ, анализ, документы) будут удалены безвозвратно.
              </p>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 bg-surface-container-low border-t border-outline-variant/60">
              <button
                onClick={() => setDeleteTarget(null)}
                className="px-4 py-2 bg-surface-bright border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface-variant hover:bg-surface-container transition-colors"
              >
                Отмена
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="px-4 py-2 bg-red-600 text-white rounded-lg text-label-md font-label-md hover:bg-red-700 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                {isDeleting && <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>}
                Удалить навсегда
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}