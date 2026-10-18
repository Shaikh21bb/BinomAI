'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
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
  const dialogRef = useRef<HTMLDialogElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const submittingRef = useRef(false);
  const backdropPointerDown = useRef(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialog.showModal();
      nameRef.current?.focus();
    } else if (!open && dialog.open) {
      dialog.close();
      if (openerRef.current?.isConnected) openerRef.current.focus();
    }
  }, [open]);

  useEffect(() => {
    const dialog = dialogRef.current;
    return () => {
      if (dialog?.open) dialog.close();
    };
  }, []);

  function requestClose() {
    if (!submittingRef.current) onClose();
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submittingRef.current) return;
    setError('');
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Укажите название тендера. Одних пробелов недостаточно.');
      nameRef.current?.focus();
      return;
    }
    const deadline = deadlineAt ? new Date(deadlineAt) : null;
    if (deadline && !Number.isFinite(deadline.getTime())) {
      setError('Проверьте дату и время окончания подачи.');
      return;
    }
    submittingRef.current = true;
    setIsSaving(true);
    try {
      const body: Record<string, unknown> = { name: trimmedName };
      if (customerName.trim()) body.customer_name = customerName.trim();
      if (deadline) body.deadline_at = deadline.toISOString();
      if (notes.trim()) body.notes = notes.trim();

      const project = await api.post('/projects/', body);
      const id = project?.id ?? project?.data?.id;
      if (typeof id !== 'string' || !id.trim()) {
        throw new Error('Сервер не вернул номер созданного тендера. Обновите список тендеров перед повторной попыткой.');
      }
      onClose();
      setName('');
      setCustomerName('');
      setDeadlineAt('');
      setNotes('');
      router.push(`/projects/${encodeURIComponent(id)}/document`);
      router.refresh();
    } catch (err) {
      setError(errorMessage(err, 'Не удалось создать тендер'));
    } finally {
      submittingRef.current = false;
      setIsSaving(false);
    }
  };

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="new-tender-heading"
      aria-describedby="new-tender-description"
      aria-busy={isSaving}
      className="m-auto max-h-[calc(100dvh_-_2rem)] w-[calc(100%_-_2rem)] max-w-xl overflow-y-auto rounded-2xl border border-outline-variant bg-surface-bright p-0 text-on-surface shadow-2xl backdrop:bg-black/45 backdrop:backdrop-blur-sm"
      onCancel={(event) => {
        event.preventDefault();
        requestClose();
      }}
      onPointerDown={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        backdropPointerDown.current = event.target === event.currentTarget && (
          event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom
        );
      }}
      onClick={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        const outside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
        if (backdropPointerDown.current && event.target === event.currentTarget && outside) requestClose();
        backdropPointerDown.current = false;
      }}
    >
        <div className="flex items-start justify-between gap-4 border-b border-outline-variant/60 px-6 py-5">
          <div><p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-primary">Рабочая область</p><h2 id="new-tender-heading" className="text-headline-md font-headline-md text-on-surface">Новый тендер</h2><p id="new-tender-description" className="mt-2 text-body-sm text-on-surface-variant">Создайте проект, затем загрузите техническое задание.</p></div>
          <button
            type="button"
            onClick={requestClose}
            disabled={isSaving}
            className="flex size-9 shrink-0 items-center justify-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Закрыть создание тендера"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6">
          <fieldset disabled={isSaving} className="space-y-5 disabled:opacity-70">
          <div className="space-y-2">
            <label htmlFor="tender-name" className="block text-label-md font-label-md text-on-surface">
              Название тендера <span className="text-error">*</span>
            </label>
            <input
              id="tender-name"
              ref={nameRef}
              name="name"
              required
              maxLength={500}
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
                name="customer_name"
                maxLength={500}
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="АО «НефтеХимПроект»"
                className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface placeholder:text-on-surface-variant/50"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="tender-deadline" className="block text-label-md font-label-md text-on-surface">
                Срок подачи <span className="text-on-surface-variant/60">(опц.)</span>
              </label>
              <input
                id="tender-deadline"
                name="deadline_at"
                type="datetime-local"
                aria-describedby="tender-deadline-help"
                value={deadlineAt}
                onChange={(e) => setDeadlineAt(e.target.value)}
                className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
              />
              <p id="tender-deadline-help" className="text-[11px] leading-4 text-on-surface-variant">Дата и время в часовом поясе вашего устройства.</p>
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="tender-notes" className="block text-label-md font-label-md text-on-surface">
              Заметки <span className="text-on-surface-variant/60">(опц.)</span>
            </label>
            <textarea
              id="tender-notes"
              name="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Важный тендер, приоритет!"
              className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface placeholder:text-on-surface-variant/50 resize-none"
            />
          </div>

          {error && (
            <div role="alert" className="p-3 bg-error-container text-on-error-container rounded-lg text-body-sm font-body-md">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={requestClose}
              disabled={isSaving}
              className="px-4 py-2 bg-surface border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface-variant hover:bg-surface-container transition-colors"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-5 py-2.5 bg-primary text-on-primary rounded-lg text-label-md font-label-md disabled:opacity-50 hover:opacity-90 transition-opacity flex items-center gap-2"
            >
              {isSaving ? (
                <>
                  <span aria-hidden="true" className="material-symbols-outlined animate-spin text-[18px]">sync</span>
                  Создание...
                </>
              ) : (
                'Создать тендер'
              )}
            </button>
          </div>
          </fieldset>
        </form>
    </dialog>
  );
}
