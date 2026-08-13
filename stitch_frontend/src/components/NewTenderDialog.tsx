'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, errorMessage } from '@/lib/api';

export function NewTenderDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [name, setName] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [deadlineAt, setDeadlineAt] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  if (!open) return null;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSaving(true);
    try {
      const body: Record<string, unknown> = { name };
      if (customerName.trim()) body.customer_name = customerName.trim();
      if (deadlineAt) body.deadline_at = new Date(deadlineAt).toISOString();
      if (notes.trim()) body.notes = notes.trim();

      const project = await api.post('/projects/', body);
      const id = project?.id ?? project?.data?.id;
      onClose();
      router.push(`/projects/${id}/document`);
      router.refresh();
    } catch (err) {
      setError(errorMessage(err, 'Не удалось создать тендер'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-lg bg-surface-bright rounded-lg shadow-xl border border-outline-variant overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant/60">
          <h2 className="text-headline-md font-headline-md text-on-surface">Новый тендер</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container transition-colors"
            aria-label="Закрыть"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div className="space-y-2">
            <label htmlFor="tender-name" className="block text-label-md font-label-md text-on-surface">
              Название тендера <span className="text-error">*</span>
            </label>
            <input
              id="tender-name"
              required
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Например, Строительство ЖК «Астана»"
              className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface placeholder:text-on-surface-variant/50"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div className="space-y-2">
              <label htmlFor="tender-customer" className="block text-label-md font-label-md text-on-surface">
                Заказчик <span className="text-on-surface-variant/60">(опц.)</span>
              </label>
              <input
                id="tender-customer"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="АО «НефтеХимПроект»"
                className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface placeholder:text-on-surface-variant/50"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="tender-deadline" className="block text-label-md font-label-md text-on-surface">
                Дедлайн <span className="text-on-surface-variant/60">(опц.)</span>
              </label>
              <input
                id="tender-deadline"
                type="date"
                value={deadlineAt}
                onChange={(e) => setDeadlineAt(e.target.value)}
                className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="tender-notes" className="block text-label-md font-label-md text-on-surface">
              Заметки <span className="text-on-surface-variant/60">(опц.)</span>
            </label>
            <textarea
              id="tender-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Важный тендер, приоритет!"
              className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface placeholder:text-on-surface-variant/50 resize-none"
            />
          </div>

          {error && (
            <div className="p-3 bg-error-container text-on-error-container rounded-lg text-body-sm font-body-md">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-surface border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface-variant hover:bg-surface-container transition-colors"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-5 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md disabled:opacity-50 hover:opacity-90 transition-opacity flex items-center gap-2"
            >
              {isSaving ? (
                <>
                  <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>
                  Создание...
                </>
              ) : (
                'Создать тендер'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}