import { ReactNode } from 'react';

const STATUS_META: Record<string, { label: string; className: string; dot: string }> = {
  draft: { label: 'Черновик', className: 'bg-slate-100 text-slate-700 border border-slate-200', dot: 'bg-slate-400' },
  processing: { label: 'Обработка', className: 'bg-blue-50 text-blue-700 border border-blue-200', dot: 'bg-blue-500' },
  analyzing: { label: 'Анализ', className: 'bg-blue-50 text-blue-700 border border-blue-200', dot: 'bg-blue-500' },
  clarifying: { label: 'Уточнение', className: 'bg-indigo-50 text-indigo-700 border border-indigo-200', dot: 'bg-indigo-500' },
  generating: { label: 'Генерация', className: 'bg-violet-50 text-violet-700 border border-violet-200', dot: 'bg-violet-500' },
  review: { label: 'На проверке', className: 'bg-amber-100 text-amber-900 border border-amber-200', dot: 'bg-amber-500' },
  ready: { label: 'Готов', className: 'bg-emerald-100 text-emerald-800 border border-emerald-200', dot: 'bg-emerald-500' },
  done: { label: 'Завершён', className: 'bg-emerald-100 text-emerald-800 border border-emerald-200', dot: 'bg-emerald-500' },
  submitted: { label: 'Подан', className: 'bg-teal-50 text-teal-800 border border-teal-200', dot: 'bg-teal-500' },
  archived: { label: 'Архив', className: 'bg-slate-100 text-slate-600 border border-slate-200', dot: 'bg-slate-400' },
};

export function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? {
    label: status,
    className: 'bg-slate-100 text-slate-700 border border-slate-200',
    dot: 'bg-slate-400',
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-label-md font-label-md w-fit capitalize ${meta.className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
      {meta.label}
    </span>
  );
}

const SEVERITY_META: Record<string, { label: string; className: string; icon: string }> = {
  critical: { label: 'Критический', className: 'bg-red-50 text-red-800 border border-red-200', icon: 'cancel' },
  high: { label: 'Высокий', className: 'bg-red-50 text-red-800 border border-red-200', icon: 'error' },
  medium: { label: 'Средний', className: 'bg-amber-50 text-amber-900 border border-amber-200', icon: 'warning' },
  low: { label: 'Низкий', className: 'bg-emerald-50 text-emerald-800 border border-emerald-200', icon: 'check_circle' },
};

export function SeverityBadge({ severity }: { severity: string }) {
  const key = String(severity || '').toLowerCase();
  const meta = SEVERITY_META[key] ?? {
    label: severity || '—',
    className: 'bg-slate-100 text-slate-700 border border-slate-200',
    icon: 'info',
  };
  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-label-md font-label-md w-fit ${meta.className}`}
    >
      <span className="material-symbols-outlined text-[14px]">{meta.icon}</span>
      {meta.label}
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3">
      <span className="material-symbols-outlined animate-spin text-3xl text-primary">sync</span>
      {label && <p className="text-body-md font-body-md text-on-surface-variant">{label}</p>}
    </div>
  );
}

export function EmptyState({
  icon = 'folder_open',
  title,
  description,
  action,
}: {
  icon?: string;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center gap-3 px-6 py-14 bg-surface-container-lowest border border-outline-variant rounded-lg">
      <div className="w-14 h-14 rounded-full bg-surface-container-high flex items-center justify-center">
        <span className="material-symbols-outlined text-2xl text-primary">{icon}</span>
      </div>
      <div>
        <h3 className="text-headline-md font-headline-md text-on-surface mb-1">{title}</h3>
        {description && <p className="text-body-md font-body-md text-on-surface-variant max-w-md">{description}</p>}
      </div>
      {action && (
        <button
          onClick={action.onClick}
          className="mt-2 px-4 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

export function InfoBanner({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`flex items-start gap-3 px-4 py-3 bg-surface-container-low border border-outline-variant rounded-lg text-body-md font-body-md text-on-surface ${className}`}>
      <span className="material-symbols-outlined text-[18px] mt-0.5 shrink-0 text-primary">info</span>
      <div className="leading-relaxed">{children}</div>
    </div>
  );
}

export function formatDate(value?: string | null) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' });
}