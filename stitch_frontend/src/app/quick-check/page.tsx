'use client';

import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react';
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
  id: string;
  filename: string;
  page_count: number;
  ocr_pages: number;
  total_items: number;
  truncated: boolean;
  items: CheckItem[];
  created_at: string;
  updated_at: string;
  processing_state: 'pending' | 'queued' | 'running' | 'completed' | 'error';
  reused?: boolean;
}

interface CheckItem extends PdfItem {
  state: 'pending' | 'searching' | 'ready' | 'error';
  results: DiscoveryLead[];
  error?: string;
  checked_at?: string | null;
}

interface SavedCheck {
  id: string;
  filename: string;
  created_at: string;
  total_items: number;
  checked_items: number;
  processing_state: ParsedPdf['processing_state'];
}

interface HistoryResponse {
  reports: SavedCheck[];
  stats: { total_reports: number; total_items: number; checked_items: number };
  next_cursor: string | null;
}

function formatDate(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function csvCell(value: unknown) {
  const text = String(value ?? '');
  // Keep product names and source text from becoming formulas in spreadsheet apps.
  const safe = /^[\s]*[=+\-@]/.test(text) ? `'${text}` : text;
  return `"${safe.replaceAll('"', '""')}"`;
}

function downloadReport(report: ParsedPdf, items: CheckItem[]) {
  const rows: unknown[][] = [[
    'Проверка', 'Дата проверки', 'Позиция', 'Товар по ТЗ', 'Требуемое количество', 'Единица',
    'Найденный товар', 'Продавец', 'Телефон продавца', 'Статус соответствия', 'Характеристика', 'Статус характеристики',
    'Доказательство со страницы', 'Источник', 'Опубликованный остаток', 'Единица остатка',
  ]];
  items.forEach((item, index) => {
    const leads = item.results.filter(isVerifiedProductLead).slice(0, 8);
    if (!leads.length) {
      rows.push([report.filename, item.checked_at, index + 1, item.product_name, item.quantity, item.unit,
        '', '', '', 'Товар не подтверждён', '', '', '', '', '', '']);
    }
    leads.forEach((lead) => {
      const checks = lead.checks?.length ? lead.checks : [null];
      checks.forEach((check) => rows.push([
        report.filename, item.checked_at, index + 1, item.product_name, item.quantity, item.unit,
        lead.title, lead.seller_name || lead.shop, lead.seller_phones?.join(' / ') || lead.seller_phone,
        lead.match_status, check?.requirement, check?.status,
        check?.evidence, lead.url, lead.stock_quantity, lead.stock_unit,
      ]));
    });
  });
  const blob = new Blob([`\uFEFF${rows.map((row) => row.map(csvCell).join(';')).join('\r\n')}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `quick-check-${report.id}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
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
  const [reusedReport, setReusedReport] = useState(false);
  const [rerunningReport, setRerunningReport] = useState(false);
  const [items, setItems] = useState<CheckItem[]>([]);
  const [error, setError] = useState('');
  const [history, setHistory] = useState<SavedCheck[]>([]);
  const [historyStats, setHistoryStats] = useState<HistoryResponse['stats']>({ total_reports: 0, total_items: 0, checked_items: 0 });
  const [nextHistoryCursor, setNextHistoryCursor] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [historyError, setHistoryError] = useState('');
  const [loadingReport, setLoadingReport] = useState(false);
  const [deletingReportId, setDeletingReportId] = useState<string | null>(null);
  const busy = rerunningReport || phase === 'parsing' || (phase === 'searching' && !['queued', 'running'].includes(parsed?.processing_state ?? ''));
  const completed = items.filter((item) => item.state === 'ready').length;
  const activeReportId = parsed?.id;
  const activeReportState = parsed?.processing_state;
  const activeSearch = ['queued', 'running'].includes(activeReportState ?? '');
  const lastProgress = Date.parse(parsed?.updated_at ?? '');
  const staleSearch = activeSearch && Number.isFinite(lastProgress) && Date.now() - lastProgress > 10 * 60 * 1000;

  async function refreshHistory() {
    setLoadingHistory(true);
    try {
      const response: HistoryResponse = await api.get('/quick-check/reports');
      setHistory(response.reports ?? []);
      setHistoryStats(response.stats ?? { total_reports: 0, total_items: 0, checked_items: 0 });
      setNextHistoryCursor(response.next_cursor ?? null);
      setHistoryError('');
    } catch (loadError) {
      setHistoryError(errorMessage(loadError, 'Не удалось загрузить историю проверок'));
    } finally {
      setLoadingHistory(false);
    }
  }

  async function loadMoreHistory() {
    if (!nextHistoryCursor || loadingHistory) return;
    setLoadingHistory(true);
    try {
      const response: HistoryResponse = await api.get(`/quick-check/reports?cursor=${encodeURIComponent(nextHistoryCursor)}`);
      setHistory((current) => {
        const known = new Set(current.map((report) => report.id));
        return [...current, ...(response.reports ?? []).filter((report) => !known.has(report.id))];
      });
      setHistoryStats(response.stats ?? historyStats);
      setNextHistoryCursor(response.next_cursor ?? null);
      setHistoryError('');
    } catch (loadError) {
      setHistoryError(errorMessage(loadError, 'Не удалось загрузить остальные проверки'));
    } finally {
      setLoadingHistory(false);
    }
  }

  useEffect(() => { void refreshHistory(); }, []);

  useEffect(() => {
    if (!activeReportId || !['queued', 'running'].includes(activeReportState ?? '')) return;
    let cancelled = false;
    let fetching = false;
    let polls = 0;
    async function poll() {
      if (fetching) return;
      fetching = true;
      try {
        const report: ParsedPdf = await api.get(`/quick-check/reports/${activeReportId}`);
        if (cancelled) return;
        setParsed(report);
        setItems(report.items.map((item) => ({ ...item, results: item.results ?? [] })));
        polls += 1;
        if (polls % 3 === 0) void refreshHistory();
        if (!['queued', 'running'].includes(report.processing_state)) {
          setPhase('done');
          void refreshHistory();
        }
      } catch {
        // A temporary connection failure must not stop server-side processing.
      } finally {
        fetching = false;
      }
    }
    void poll();
    const timer = window.setInterval(() => { void poll(); }, 3000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [activeReportId, activeReportState]);

  async function openReport(id: string) {
    if (busy || loadingReport || deletingReportId) return;
    setLoadingReport(true);
    setError('');
    try {
      const document: ParsedPdf = await api.get(`/quick-check/reports/${id}`);
      setParsed(document);
      setReusedReport(false);
      setItems(document.items.map((item) => ({ ...item, results: item.results ?? [] })));
      setPhase(['queued', 'running'].includes(document.processing_state) ? 'searching' : 'done');
    } catch (loadError) {
      setError(errorMessage(loadError, 'Не удалось открыть проверку'));
    } finally {
      setLoadingReport(false);
    }
  }

  async function deleteReport(report: SavedCheck) {
    if (busy || loadingReport || deletingReportId) return;
    if (!window.confirm(`Удалить сохранённую проверку «${report.filename}»?`)) return;
    setDeletingReportId(report.id);
    setHistoryError('');
    try {
      await api.delete(`/quick-check/reports/${report.id}`);
      if (parsed?.id === report.id) {
        setParsed(null);
        setReusedReport(false);
        setItems([]);
        setPhase('idle');
      }
      await refreshHistory();
    } catch (deleteError) {
      setHistoryError(errorMessage(deleteError, 'Не удалось удалить проверку'));
    } finally {
      setDeletingReportId(null);
    }
  }

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

  async function searchOne(item: PdfItem, index: number, reportId: string): Promise<boolean> {
    setItems((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, state: 'searching', error: undefined } : row));
    try {
      const response: { results: DiscoveryLead[]; checked_at: string } = await api.post('/quick-check/search', {
        product_name: item.product_name,
        specs: item.specs ?? null,
        report_id: reportId,
        item_index: index,
      });
      setItems((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, state: 'ready', results: response.results ?? [], checked_at: response.checked_at } : row));
      return true;
    } catch (searchError) {
      setItems((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, state: 'error', error: errorMessage(searchError, 'Не удалось найти товары') } : row));
      return false;
    }
  }

  async function retry(index: number) {
    if (busy || !items[index] || !parsed || ['queued', 'running'].includes(parsed.processing_state)) return;
    setPhase('searching');
    try {
      const succeeded = await searchOne(items[index], index, parsed.id);
      if (succeeded) {
        const updated: ParsedPdf = await api.get(`/quick-check/reports/${parsed.id}`);
        setParsed(updated);
        setItems(updated.items.map((item) => ({ ...item, results: item.results ?? [] })));
      }
      await refreshHistory();
    } catch (refreshError) {
      setError(errorMessage(refreshError, 'Результат сохранён, но не удалось обновить экран'));
    } finally {
      setPhase('done');
    }
  }

  async function checkRemaining(report: ParsedPdf) {
    if (busy || (['queued', 'running'].includes(report.processing_state) && !staleSearch)) return;
    setError('');
    try {
      const updated: ParsedPdf = await api.post(`/quick-check/reports/${report.id}/run`, {});
      setParsed(updated);
      setItems(updated.items.map((item) => ({ ...item, results: item.results ?? [] })));
      setPhase(['queued', 'running'].includes(updated.processing_state) ? 'searching' : 'done');
      if (updated.processing_state === 'error') setError('Фоновый поиск пока недоступен. Попробуйте запустить его ещё раз.');
      await refreshHistory();
    } catch (runError) {
      setError(errorMessage(runError, 'Не удалось запустить проверку'));
    }
  }

  async function rerunReport(report: ParsedPdf) {
    if (busy || ['queued', 'running'].includes(report.processing_state)) return;
    setRerunningReport(true);
    setError('');
    try {
      const updated: ParsedPdf = await api.post(`/quick-check/reports/${report.id}/rerun`, {});
      setParsed(updated);
      setReusedReport(false);
      setItems(updated.items.map((item) => ({ ...item, results: item.results ?? [] })));
      setPhase(['queued', 'running'].includes(updated.processing_state) ? 'searching' : 'done');
      if (updated.processing_state === 'error') setError('Новая проверка сохранена, но поиск пока недоступен. Его можно возобновить позже.');
      await refreshHistory();
    } catch (rerunError) {
      setError(errorMessage(rerunError, 'Не удалось запустить новую проверку'));
    } finally {
      setRerunningReport(false);
    }
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
    setReusedReport(false);
    setItems([]);
    setPhase('parsing');
    try {
      const form = new FormData();
      form.append('file', file);
      const document: ParsedPdf = await api.post('/quick-check/parse', form);
      setParsed(document);
      setReusedReport(Boolean(document.reused));
      setItems(document.items.map((item) => ({ ...item, results: item.results ?? [] })));
      setPhase(['queued', 'running'].includes(document.processing_state) ? 'searching' : 'done');
      if (document.processing_state === 'error') setError('PDF сохранён, но фоновый поиск пока недоступен. Запустите его из сохранённой проверки.');
      await refreshHistory();
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
            <p className="mt-2 max-w-2xl text-body-lg text-on-surface-variant">Загрузите техспецификацию в PDF. Мы выделим товары, найдём их фото и проверим опубликованные характеристики — без создания тендера. Повторная загрузка того же файла откроет сохранённый результат сразу.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1.5 text-label-sm text-primary"><span className="material-symbols-outlined text-[17px]">bolt</span>Отдельная проверка</span>
            <a href="#quick-check-history" className="inline-flex items-center gap-1.5 rounded-full border border-outline-variant px-3 py-1.5 text-label-sm text-on-surface hover:border-primary hover:text-primary"><span className="material-symbols-outlined text-[17px]">history</span>История · {historyStats.total_reports}</a>
          </div>
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
              <p className="mt-1 text-body-sm text-on-surface-variant">Текстовый PDF или скан до 20 МБ · для скана до 12 страниц · исходный файл не хранится, сохраняется только результат проверки</p>
            </div>
            <input ref={inputRef} type="file" accept=".pdf,application/pdf" className="hidden" disabled={busy} onChange={(event) => chooseFile(event.target.files?.[0] || null)} />
            <button type="button" disabled={busy} onClick={() => inputRef.current?.click()} className="rounded-lg border border-outline-variant bg-surface-container-lowest px-4 py-2 text-label-md text-on-surface hover:border-primary disabled:opacity-50">Выбрать PDF</button>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="max-w-xl text-body-sm text-on-surface-variant">Точное наличие в штуках покажем, если продавец его указал. Статус «в наличии» без числа не считаем подтверждённым остатком.</p>
            <button type="submit" disabled={!file || busy} className="inline-flex items-center gap-2 rounded-lg bg-on-background px-5 py-2.5 text-label-md font-label-md text-on-primary shadow-sm hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50">
              <span className={`material-symbols-outlined text-[19px] ${busy ? 'animate-spin' : ''}`}>{busy ? 'sync' : 'travel_explore'}</span>
              {phase === 'parsing' ? 'Читаем PDF…' : 'Проверить PDF'}
            </button>
          </div>
          {error && <p role="alert" className="mt-4 rounded-lg bg-error-container px-4 py-3 text-body-sm text-on-error-container">{error}</p>}
        </form>

        <section id="quick-check-history" className="scroll-mt-6 rounded-2xl border border-outline-variant bg-surface-container-lowest p-5 shadow-sm md:p-6" aria-label="История проверок">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-title-lg font-title-lg text-on-surface">История всех проверок</h2>
              <p className="mt-1 text-body-sm text-on-surface-variant">Результаты хранятся в базе и доступны только вам. Исходные PDF не сохраняются.</p>
            </div>
            <button type="button" disabled={loadingHistory} onClick={() => void refreshHistory()} className="inline-flex items-center gap-1 text-label-sm text-primary hover:underline disabled:opacity-50"><span className="material-symbols-outlined text-[17px]">refresh</span>Обновить</button>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            {[
              { label: 'Всего проверок', value: historyStats.total_reports, icon: 'history' },
              { label: 'Найдено позиций', value: historyStats.total_items, icon: 'inventory_2' },
              { label: 'Товаров проверено', value: historyStats.checked_items, icon: 'task_alt' },
            ].map((stat) => (
              <div key={stat.label} className="rounded-xl bg-surface-container-low p-3">
                <span className="flex items-center gap-2 text-label-sm text-on-surface-variant"><span className="material-symbols-outlined text-[17px] text-primary">{stat.icon}</span>{stat.label}</span>
                <span className="mt-1 block text-title-lg font-title-lg text-on-surface">{stat.value}</span>
              </div>
            ))}
          </div>
          {historyError && <p role="alert" className="mt-3 text-body-sm text-error">{historyError}</p>}
          {history.length ? (
            <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {history.map((report) => (
                <div key={report.id} className={`flex items-stretch overflow-hidden rounded-xl border transition-colors hover:border-primary ${parsed?.id === report.id ? 'border-primary bg-primary/5' : 'border-outline-variant bg-surface-container-low'}`}>
                  <button type="button" disabled={busy || loadingReport || Boolean(deletingReportId)} onClick={() => void openReport(report.id)} className="min-w-0 flex-1 p-3 text-left disabled:opacity-50">
                    <span className="block truncate text-label-md font-label-md text-on-surface">{report.filename}</span>
                    <span className="mt-1 block text-label-sm text-on-surface-variant">{formatDate(report.created_at)} · проверено {report.checked_items} из {report.total_items}</span>
                    {['queued', 'running'].includes(report.processing_state) && <span className="mt-1 block text-label-sm text-primary">Проверяется в фоне</span>}
                    {report.processing_state === 'error' && <span className="mt-1 block text-label-sm text-error">Нужен повторный запуск</span>}
                  </button>
                  <button type="button" aria-label={`Удалить проверку ${report.filename}`} disabled={busy || loadingReport || Boolean(deletingReportId)} onClick={() => void deleteReport(report)} className="border-l border-outline-variant px-3 text-on-surface-variant hover:bg-error-container hover:text-on-error-container disabled:opacity-50">
                    <span className={`material-symbols-outlined text-[19px] ${deletingReportId === report.id ? 'animate-spin' : ''}`}>{deletingReportId === report.id ? 'progress_activity' : 'delete'}</span>
                  </button>
                </div>
              ))}
            </div>
          ) : !historyError && !loadingHistory && <p className="mt-4 text-body-sm text-on-surface-variant">Пока нет сохранённых проверок. Проверки, сделанные до появления истории, не сохранялись; новые появятся здесь сразу после загрузки PDF.</p>}
          {nextHistoryCursor && <button type="button" disabled={loadingHistory} onClick={() => void loadMoreHistory()} className="mt-4 w-full rounded-lg border border-outline-variant px-4 py-2 text-label-md text-on-surface hover:border-primary disabled:opacity-50">{loadingHistory ? 'Загружаем…' : 'Показать предыдущие проверки'}</button>}
        </section>

        {parsed && (
          <section className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 className="text-headline-lg font-headline-lg text-on-surface">Результаты по PDF</h2>
                <p className="mt-1 text-body-sm text-on-surface-variant">{parsed.filename} · {parsed.page_count} стр. · {parsed.total_items} позиций</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span aria-live="polite" className="rounded-full bg-primary/10 px-3 py-1.5 text-label-sm text-primary">Проверено {completed} из {items.length}</span>
                {items.some((item) => item.state !== 'ready') && (!activeSearch || staleSearch) && <button type="button" disabled={busy} onClick={() => void checkRemaining(parsed)} className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-label-sm text-on-primary hover:opacity-90 disabled:opacity-50"><span className="material-symbols-outlined text-[17px]">travel_explore</span>{staleSearch ? 'Возобновить проверку' : 'Проверить оставшиеся'}</button>}
                {!activeSearch && <button type="button" disabled={busy} onClick={() => void rerunReport(parsed)} className="inline-flex items-center gap-1.5 rounded-lg border border-primary px-3 py-1.5 text-label-sm text-primary hover:bg-primary/5 disabled:opacity-50"><span className="material-symbols-outlined text-[17px]">refresh</span>{rerunningReport ? 'Запускаем…' : 'Проверить заново'}</button>}
                <button type="button" onClick={() => downloadReport(parsed, items)} className="inline-flex items-center gap-1.5 rounded-lg border border-outline-variant px-3 py-1.5 text-label-sm text-on-surface hover:border-primary"><span className="material-symbols-outlined text-[17px]">download</span>Скачать отчёт CSV</button>
              </div>
            </div>
            {reusedReport && <p role="status" className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-body-sm text-on-surface">Этот PDF уже есть в истории: открыта проверка от {formatDate(parsed.created_at)} без повторной обработки файла. {activeSearch ? 'Поиск ещё идёт в фоне.' : 'Для свежих данных нажмите «Проверить заново» — предыдущий результат останется в истории.'}</p>}
            {activeSearch && !staleSearch && <p role="status" className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-body-sm text-on-surface">Поиск идёт в фоне. Можно закрыть страницу: готовые товары сохраняются, а прогресс виден здесь и в истории.</p>}
            {staleSearch && <p role="status" className="rounded-xl bg-amber-50 px-4 py-3 text-body-sm text-amber-900">Прогресс давно не обновлялся. Нажмите «Возобновить проверку», чтобы продолжить с сохранённого места.</p>}
            {parsed.processing_state === 'error' && <p role="alert" className="rounded-xl bg-error-container px-4 py-3 text-body-sm text-on-error-container">Поиск прервался. Уже найденные товары сохранены; нажмите «Проверить оставшиеся», чтобы продолжить.</p>}
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
                    {item.checked_at && <span className="text-label-sm text-on-surface-variant">Проверено {formatDate(item.checked_at)}</span>}
                    {item.state !== 'searching' && !['queued', 'running'].includes(parsed.processing_state) && <button type="button" disabled={busy} onClick={() => void retry(index)} className="inline-flex items-center gap-1 text-label-sm text-primary hover:underline disabled:opacity-50"><span className="material-symbols-outlined text-[16px]">{item.state === 'pending' ? 'search' : 'refresh'}</span>{item.state === 'pending' ? 'Найти товары' : 'Повторить поиск'}</button>}
                  </div>
                </div>
                {item.state === 'ready' ? <>
                  {(() => {
                    const best = item.results.find(isVerifiedProductLead);
                    if (!best) return null;
                    return <div className="border-t border-outline-variant bg-surface-container-low px-4 py-4 md:px-5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h4 className="text-title-md font-title-md text-on-surface">Доказательства по лучшему найденному товару</h4>
                        {best.url && <a href={best.url} target="_blank" rel="noopener noreferrer" className="text-label-sm text-primary hover:underline">Открыть источник ↗</a>}
                      </div>
                      <p className="mt-1 text-body-sm text-on-surface-variant">{best.title || 'Товар без названия'} · сведения с открытой страницы продавца</p>
                      <div className="mt-3 space-y-2">
                        {(best.checks ?? []).map((check, checkIndex) => (
                          <div key={`${check.id || checkIndex}-${checkIndex}`} className="grid gap-1 rounded-lg border border-outline-variant bg-surface-container-lowest p-3 text-body-sm md:grid-cols-[minmax(0,1fr)_125px_minmax(0,1fr)] md:gap-3">
                            <span className="font-medium text-on-surface">{check.requirement}</span>
                            <span className={check.status === 'matched' ? 'text-emerald-700' : check.status === 'mismatch' ? 'text-rose-700' : 'text-amber-700'}>{check.status === 'matched' ? 'Подтверждено' : check.status === 'mismatch' ? 'Расхождение' : 'Нет данных'}</span>
                            <span className="break-words text-on-surface-variant">{check.evidence || 'Доказательство на странице не найдено'}</span>
                          </div>
                        ))}
                      </div>
                    </div>;
                  })()}
                  <ProductDiscoveryCards productName={item.product_name} leads={item.results} requestedQuantity={item.quantity} requestedUnit={item.unit} />
                </> : (
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
