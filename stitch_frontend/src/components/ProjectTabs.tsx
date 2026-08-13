'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { api, errorMessage } from '@/lib/api';
import { StatusBadge, formatDate } from './ui';

const TABS = [
  { key: 'document', href: (id: string) => `/projects/${id}/document`, label: 'ТЗ', icon: 'description' },
  { key: 'analysis', href: (id: string) => `/projects/${id}/analysis`, label: 'Анализ', icon: 'psychology' },
  { key: 'chat', href: (id: string) => `/projects/${id}/chat`, label: 'Диалог', icon: 'forum' },
  { key: 'generate', href: (id: string) => `/projects/${id}/generate`, label: 'Документы', icon: 'edit_document' },
  { key: 'products', href: (id: string) => `/projects/${id}/products`, label: 'Товары', icon: 'inventory_2' },
  { key: 'export', href: (id: string) => `/projects/${id}/export`, label: 'Экспорт', icon: 'download' },
] as const;

const STATUS_MAP: Record<string, string> = {
  processing: 'processing',
  analyzing: 'analyzing',
  clarifying: 'clarifying',
  generating: 'generating',
  review: 'review',
  ready: 'ready',
  done: 'done',
  submitted: 'submitted',
  archived: 'archived',
};

interface Project {
  id: string;
  name: string;
  status: string;
  customer_name?: string;
  deadline_at?: string;
}

export function ProjectTabs({ projectId }: { projectId: string }) {
  const pathname = usePathname();
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`/projects/${projectId}`);
        if (!cancelled) setProject(res?.data ?? res);
      } catch (err) {
        if (!cancelled) {
          setError(errorMessage(err, 'Проект не найден'));
          setProject(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  if (error) {
    return (
      <div className="px-margin-page py-10">
        <div className="max-w-2xl mx-auto bg-error-container border border-error-container rounded-xl p-6 text-center">
          <p className="text-body-lg font-body-lg text-on-surface mb-2">Не удалось загрузить проект</p>
          <p className="text-body-md font-body-md text-on-surface-variant mb-4">{error}</p>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 px-4 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md"
          >
            <span className="material-symbols-outlined text-[18px]">arrow_back</span>
            Вернуться к списку тендеров
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface/80 backdrop-blur border-b border-outline-variant px-4 md:px-margin-page pt-stack-md shrink-0">
      <div className="max-w-container-max mx-auto">
        {/* Breadcrumb row */}
        <div className="flex flex-wrap items-center gap-3 pb-stack-sm">
          <Link
            href="/dashboard"
            className="flex items-center gap-1.5 text-label-md font-label-md text-on-surface-variant hover:text-primary transition-colors"
          >
            <span className="material-symbols-outlined text-[16px]">arrow_back</span>
            Все тендеры
          </Link>

          {project && (
            <>
              <span className="material-symbols-outlined text-[16px] text-on-surface-variant/50">chevron_right</span>
              <h1 className="text-headline-md font-headline-md text-on-surface truncate max-w-xs sm:max-w-md">
                {project.name}
              </h1>
              <StatusBadge status={STATUS_MAP[project.status] ?? project.status} />
              {project.deadline_at && (
                <span className="hidden sm:flex items-center gap-1 text-mono-sm font-mono-sm text-on-surface-variant">
                  <span className="material-symbols-outlined text-[14px]">event</span>
                  до {formatDate(project.deadline_at)}
                </span>
              )}
            </>
          )}
        </div>

        {/* Tabs */}
        <nav className="flex items-center gap-1 overflow-x-auto" aria-label="Разделы проекта">
          {TABS.map((tab) => {
            const href = tab.href(projectId);
            const active = pathname === href;
            return (
              <Link
                key={tab.key}
                href={href}
                className={`flex items-center gap-2 px-2 sm:px-4 py-2.5 rounded-t-lg text-label-md font-label-md whitespace-nowrap transition-colors border-b-2 ${
                  active
                    ? 'border-primary text-primary bg-primary/5 font-bold'
                    : 'border-transparent text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low'
                }`}
              >
                <span className="material-symbols-outlined text-[18px]">{tab.icon}</span>
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}