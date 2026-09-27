'use client';

import { useRef, useState, type DragEvent, type FormEvent } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components/AppShell';
import { ProductDiscoveryCards, isVerifiedProductLead, type DiscoveryLead } from '@/components/ProductDiscoveryCards';
import { api, errorMessage } from '@/lib/api';
import { assessStock, displayUnit } from '@/lib/productStock';

interface PdfItem {
  product_name: string;
  specs?: string | null;
  quantity?: number | null;
  unit?: string | null;
  source_section?: string | null;
}

interface ParsedPdf {
  filename: string;
  page_count: number;
  ocr_pages: number;
  total_items: number;
  truncated: boolean;
  items: PdfItem[];
}

interface CheckItem extends PdfItem {
  state: 'pending' | 'searching' | 'ready' | 'error';
  results: DiscoveryLead[];
  error?: string;
}

function requiredAmount(item: PdfItem) {
  if (item.quantity == null) return 'Количество в ТЗ не указано';
  return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 4 }).format(item.quantity)} ${displayUnit(item.unit)}`;
}

export default function QuickCheckPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [phase, setPhase] = useState<'idle' | 'parsing' | 'searching' | 'done'>('idle');
  const [parsed, setParsed] = useState<ParsedPdf | null>(null);
  const [items, setItems] = useState<CheckItem[]>([]);
  const [completed, setCompleted] = useState(0);
  const [error, setError] = useState('');
  const busy = phase === 'parsing' || phase === 'searching';

  function chooseFile(next: File | null) {
    if (!next || busy) return;
    setError('');
    setFile(next);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files[0] || null);
  }

  async function searchOne(item: PdfItem, index: number) {
    setItems((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, state: 'searching', error: undefined } : row));
    try {
      const response: { results: DiscoveryLead[] } = await api.post('/quick-check/search', {
        product_name: item.product_name,
        specs: item.specs ?? null,
      });
      setItems((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, state: 'ready', results: response.results ?? [] } : row));
    } catch (searchError) {
      setItems((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, state: 'error', error: errorMessage(searchError, 'Не удалось найти товары') } : row));
    }
  }

  async function retry(index: number) {
    if (busy || !items[index]) return;
    setPhase('searching');
    await searchOne(items[index], index);
    setPhase('done');
  }

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || busy) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Выберите PDF-файл технической спецификации.');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setError('Максимальный размер PDF — 20 МБ.');
      return;
    }

    setError('');
    setParsed(null);
    setItems([]);
    setCompleted(0);
    setPhase('parsing');
    try {
      const form = new FormData();
      form.append('file', file);
      const document: ParsedPdf = await api.post('/quick-check/parse', form);
      setParsed(document);
      setItems(document.items.map((item) => ({ ...item, state: 'pending', results: [] })));
      setPhase('searching');

      // Search two independent positions at a time so long PDFs finish faster
      // without flooding the public product sites.
      for (let startIndex = 0; startIndex < document.items.length; startIndex += 2) {
        await Promise.all(document.items.slice(startIndex, startIndex + 2).map(async (item, offset) => {
          await searchOne(item, startIndex + offset);
          setCompleted((count) => count + 1);
        }));
      }
      setPhase('done');
    } catch (uploadError) {
      setError(errorMessage(uploadError, 'Не удалось прочитать PDF'));
      setPhase('idle');
    }
  }

  const summary = items.reduce((total, item) => {
    const relevant = item.results.filter(isVerifiedProductLead).slice(0, 8);
    for (const lead of relevant) {
      total.cards += 1;
      const assessment = assessStock(item.quantity, item.unit, lead.stock_quantity, lead.stock_unit, lead.availability);
      total[assessment.verdict] += 1;
    }
    return total;
  }, { cards: 0, enough: 0, shortage: 0, unknown: 0 });

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-container-max flex-1 flex-col gap-6 p-4 md:p-margin-page">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Link href="/dashboard" className="mb-3 inline-flex items-center gap-1 text-label-sm text-on-surface-variant hover:text-primary">
              <span className="material-symbols-outlined text-[16px]">arrow_back</span>Рабочий стол
            </Link>
            <h1 className="text-display font-display tracking-tight text-on-surface">Быстрая проверка товаров</h1>
            <p className="mt-2 max-w-2xl text-body-lg text-on-surface-variant">Загрузите техспецификацию в PDF. Мы выделим товары, найдём их фото и проверим опубликованные характеристики — без создания тендера.</p>
          </div>
          <span className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1.5 text-label-sm text-primary"><span className="material-symbols-outlined text-[17px]">bolt</span>Отдельная проверка</span>
        </div>

        <form onSubmit={(event) => void start(event)} className="rounded-2xl border border-outline-variant bg-surface-container-lowest p-5 shadow-sm md:p-7">
          <div
            onDragOver={(event) => { event.preventDefault(); if (!busy) setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={`flex flex-col items-center gap-3 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors ${dragging ? 'border-primary bg-primary/5' : 'border-outline-variant bg-surface-container-low'}`}
          >
            <span className="material-symbols-outlined rounded-full bg-primary/10 p-3 text-[32px] text-primary">picture_as_pdf</span>
            <div>
              <p className="text-title-md font-title-md text-on-surface">{file ? file.name : 'Перетащите PDF сюда'}</p>
              <p className="mt-1 text-body-sm text-on-surface-variant">Текстовый PDF или скан до 20 МБ · для скана до 12 страниц · файл не добавляется в ваши тендеры</p>
            </div>
            <input ref={inputRef} type="file" accept=".pdf,application/pdf" className="hidden" disabled={busy} onChange={(event) => chooseFile(event.target.files?.[0] || null)} />
            <button type="button" disabled={busy} onClick={() => inputRef.current?.click()} className="rounded-lg border border-outline-variant bg-surface-container-lowest px-4 py-2 text-label-md text-on-surface hover:border-primary disabled:opacity-50">Выбрать PDF</button>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="max-w-xl text-body-sm text-on-surface-variant">Точное наличие в штуках покажем, если продавец его указал. Статус «в наличии» без числа не считаем подтверждённым остатком.</p>
            <button type="submit" disabled={!file || busy} className="inline-flex items-center gap-2 rounded-lg bg-on-background px-5 py-2.5 text-label-md font-label-md text-on-primary shadow-sm hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50">
              <span className={`material-symbols-outlined text-[19px] ${busy ? 'animate-spin' : ''}`}>{busy ? 'sync' : 'travel_explore'}</span>
              {phase === 'parsing' ? 'Читаем PDF…' : phase === 'searching' ? 'Проверяем товары…' : 'Проверить PDF'}
            </button>
          </div>
          {error && <p role="alert" className="mt-4 rounded-lg bg-error-container px-4 py-3 text-body-sm text-on-error-container">{error}</p>}
        </form>

        {parsed && (
          <section className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 className="text-headline-lg font-headline-lg text-on-surface">Результаты по PDF</h2>
                <p className="mt-1 text-body-sm text-on-surface-variant">{parsed.filename} · {parsed.page_count} стр. · {parsed.total_items} позиций</p>
              </div>
              <span aria-live="polite" className="rounded-full bg-primary/10 px-3 py-1.5 text-label-sm text-primary">Проверено {completed} из {items.length}</span>
            </div>
            {parsed.truncated && <p className="rounded-lg bg-amber-50 p-3 text-body-sm text-amber-900">Для быстрой проверки взяты первые 20 позиций PDF.</p>}
            {parsed.ocr_pages > 0 && <p className="rounded-lg bg-amber-50 p-3 text-body-sm text-amber-900">Распознано страниц скана: {parsed.ocr_pages}. Проверьте названия, количество и характеристики: распознавание может допускать ошибки.</p>}
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {[
                { label: 'Карточек товаров', value: summary.cards, icon: 'inventory_2' },
                { label: 'Хватает по количеству', value: summary.enough, icon: 'task_alt' },
                { label: 'Остатка не хватает', value: summary.shortage, icon: 'warning' },
                { label: 'Остаток не подтверждён', value: summary.unknown, icon: 'help' },
              ].map((stat) => (
                <div key={stat.label} className="flex items-center gap-3 rounded-xl border border-outline-variant bg-surface-container-lowest p-4">
                  <span className="material-symbols-outlined rounded-lg bg-primary/10 p-2 text-primary">{stat.icon}</span>
                  <div><p className="text-title-lg font-title-lg text-on-surface">{stat.value}</p><p className="text-label-sm text-on-surface-variant">{stat.label}</p></div>
                </div>
              ))}
            </div>
            <p className="text-label-sm text-on-surface-variant">Наличие и соответствие характеристикам — разные проверки. Даже достаточный остаток не означает полного соответствия ТЗ.</p>
            {items.map((item, index) => (
              <article key={`${item.source_section || item.product_name}-${index}`} className="overflow-hidden rounded-2xl border border-outline-variant bg-surface-container-lowest shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3 p-4 md:p-5">
                  <div className="min-w-0">
                    <p className="text-label-sm text-primary">Позиция {index + 1}{item.source_section ? ` · ${item.source_section}` : ''}</p>
                    <h3 className="mt-1 text-title-lg font-title-lg text-on-surface">{item.product_name}</h3>
                    {item.specs && <p className="mt-2 max-w-4xl text-body-sm text-on-surface-variant">{item.specs}</p>}
                  </div>
                  <div className="flex flex-col items-start gap-2 sm:items-end">
                    <span className="rounded-lg bg-surface-container-low px-3 py-2 text-label-md text-on-surface">По ТЗ: {requiredAmount(item)}</span>
                    {(item.state === 'ready' || item.state === 'error') && <button type="button" disabled={busy} onClick={() => void retry(index)} className="inline-flex items-center gap-1 text-label-sm text-primary hover:underline disabled:opacity-50"><span className="material-symbols-outlined text-[16px]">refresh</span>Повторить поиск</button>}
                  </div>
                </div>
                {item.state === 'ready' ? <ProductDiscoveryCards productName={item.product_name} leads={item.results} requestedQuantity={item.quantity} requestedUnit={item.unit} /> : (
                  <div aria-live="polite" className="border-t border-outline-variant px-5 py-4 text-body-sm text-on-surface-variant">
                    {item.state === 'error' ? item.error : item.state === 'searching' ? 'Ищем товарные страницы и сверяем характеристики…' : 'Ожидает проверки…'}
                  </div>
                )}
              </article>
            ))}
          </section>
        )}
      </div>
    </AppShell>
  );
}
