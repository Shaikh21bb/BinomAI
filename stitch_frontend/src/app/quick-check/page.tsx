'use client';

import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components/AppShell';
import { ProductDiscoveryCards, isVerifiedProductLead, type DiscoveryLead } from '@/components/ProductDiscoveryCards';
import { CLOSURE_POLICY_LABELS, effectiveProductCheckStatus, isConfirmedProductOffer, orderQuantityAssessment, productDiscoveryCsv, quickCheckProgressLabel, reportConfirmationGaps, reportItemHasProductCards, reportItemMatchesFilter, supportsClosureClarification, visibleProductLeads, type ClosurePolicy, type DiscoveryResultFilter } from '@/lib/productDiscovery';
import { api, errorMessage } from '@/lib/api';
import { displayUnit } from '@/lib/productStock';

interface PdfItem {
  product_name: string;
  specs?: string | null;
  quantity?: number | null;
  unit?: string | null;
  source_section?: string | null;
  closure_policy?: ClosurePolicy | null;
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

function downloadReport(report: ParsedPdf, items: CheckItem[]) {
  // Export the policy used by the completed request, never an unapplied select draft.
  const exportItems = items.map((item, index) => ({ ...item, closure_policy: report.items[index]?.closure_policy ?? 'source' as const }));
  const blob = new Blob([productDiscoveryCsv(report.filename, exportItems)], { type: 'text/csv;charset=utf-8' });
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

function isWordDocument(filename: string) {
  return filename.toLowerCase().endsWith('.docx');
}

const MAX_DOCUMENT_BYTES = 20 * 1024 * 1024;

function validateDocument(file: File) {
  const name = file.name.toLowerCase();
  if (name.endsWith('.doc')) return 'Сохраните Word-документ в формате .docx и загрузите его снова. Старый формат .doc не поддерживается.';
  if (!name.endsWith('.pdf') && !name.endsWith('.docx')) return 'Выберите документ PDF или Word (.docx). Другие форматы пока не поддерживаются.';
  if (!file.size) return 'Этот файл пустой. Выберите документ с технической спецификацией.';
  if (file.size > MAX_DOCUMENT_BYTES) return 'Документ больше 20 МБ. Уменьшите размер файла или разделите его на несколько документов.';
  return '';
}

function formatFileSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(bytes / 1024)} КБ`
    : `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(bytes / (1024 * 1024))} МБ`;
}

function reportStatus(state: ParsedPdf['processing_state']) {
  if (state === 'queued') return 'В очереди';
  if (state === 'running') return 'Идёт поиск';
  if (state === 'error') return 'Нужен повторный запуск';
  if (state === 'completed') return 'Проверка завершена';
  return 'Ожидает проверки';
}

export default function QuickCheckPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const resultsRef = useRef<HTMLElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [reparseDocument, setReparseDocument] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [phase, setPhase] = useState<'idle' | 'parsing' | 'searching' | 'done'>('idle');
  const [parsed, setParsed] = useState<ParsedPdf | null>(null);
  const [reusedReport, setReusedReport] = useState(false);
  const [rerunningReport, setRerunningReport] = useState(false);
  const [runningReport, setRunningReport] = useState(false);
  const [items, setItems] = useState<CheckItem[]>([]);
  const [error, setError] = useState('');
  const [history, setHistory] = useState<SavedCheck[]>([]);
  const [historyStats, setHistoryStats] = useState<HistoryResponse['stats']>({ total_reports: 0, total_items: 0, checked_items: 0 });
  const [nextHistoryCursor, setNextHistoryCursor] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [historyError, setHistoryError] = useState('');
  const [loadingReport, setLoadingReport] = useState(false);
  const [deletingReportId, setDeletingReportId] = useState<string | null>(null);
  const [openingReportId, setOpeningReportId] = useState<string | null>(null);
  const [historyQuery, setHistoryQuery] = useState('');
  const [resultFilter, setResultFilter] = useState<DiscoveryResultFilter>('all');
  const [retryingIndex, setRetryingIndex] = useState<number | null>(null);
  const [retryNotice, setRetryNotice] = useState('');
  const [pollError, setPollError] = useState(false);
  const [lastPollAt, setLastPollAt] = useState(() => Date.now());
  const busy = retryingIndex != null || rerunningReport || runningReport || phase === 'parsing' || (phase === 'searching' && !['queued', 'running'].includes(parsed?.processing_state ?? ''));
  const completed = items.filter((item) => item.state === 'ready').length;
  const activeReportId = parsed?.id;
  const activeReportState = parsed?.processing_state;
  const activeSearch = ['queued', 'running'].includes(activeReportState ?? '');
  const lastProgress = Date.parse(parsed?.updated_at ?? '');
  const staleSearch = activeSearch && Number.isFinite(lastProgress) && Math.max(lastPollAt, lastProgress) - lastProgress > 10 * 60 * 1000;
  const failed = items.filter((item) => item.state === 'error').length;
  const progress = items.length ? Math.round(((completed + failed) / items.length) * 100) : 0;
  const matchedItems = items.filter(reportItemHasProductCards).length;
  const withoutCards = items.filter((item) => item.state === 'ready' && !reportItemHasProductCards(item)).length;
  const inStockItems = items.filter((item) => reportItemMatchesFilter(item, 'in-stock')).length;
  const completeItems = items.filter((item) => reportItemMatchesFilter(item, 'complete')).length;
  const requirementsItems = items.filter((item) => reportItemMatchesFilter(item, 'requirements')).length;
  const combinedItems = items.filter((item) => reportItemMatchesFilter(item, 'combined')).length;
  const combinedGaps = reportConfirmationGaps(items);
  const leadFilter = resultFilter === 'in-stock' || resultFilter === 'complete' || resultFilter === 'requirements' || resultFilter === 'combined' ? resultFilter : 'all';
  const filteredHistory = history.filter((report) => report.filename.toLocaleLowerCase('ru-RU').includes(historyQuery.trim().toLocaleLowerCase('ru-RU')));
  const visibleItems = items.map((item, index) => ({ item, index })).filter(({ item, index }) => {
    return reportItemMatchesFilter(item, resultFilter, index === retryingIndex);
  });

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
    let failures = 0;
    async function poll() {
      if (fetching) return;
      fetching = true;
      try {
        const report: ParsedPdf = await api.get(`/quick-check/reports/${activeReportId}`);
        if (cancelled) return;
        failures = 0;
        setPollError(false);
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
        failures += 1;
        if (!cancelled && failures >= 2) setPollError(true);
      } finally {
        fetching = false;
        if (!cancelled) setLastPollAt(Date.now());
      }
    }
    void poll();
    const timer = window.setInterval(() => { void poll(); }, 3000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [activeReportId, activeReportState]);

  async function openReport(id: string) {
    if (busy || loadingReport || deletingReportId) return;
    setLoadingReport(true);
    setOpeningReportId(id);
    setError('');
    setHistoryError('');
    try {
      const document: ParsedPdf = await api.get(`/quick-check/reports/${id}`);
      setParsed(document);
      setReusedReport(false);
      setRetryNotice('');
      setResultFilter('all');
      setPollError(false);
      setItems(document.items.map((item) => ({ ...item, results: item.results ?? [] })));
      setPhase(['queued', 'running'].includes(document.processing_state) ? 'searching' : 'done');
      window.requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    } catch (loadError) {
      setHistoryError(errorMessage(loadError, 'Не удалось открыть проверку. Попробуйте ещё раз.'));
    } finally {
      setLoadingReport(false);
      setOpeningReportId(null);
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
    setReparseDocument(false);
    const validationError = validateDocument(next);
    if (validationError) {
      setError(validationError);
      setFile(null);
      if (inputRef.current) inputRef.current.value = '';
      return;
    }
    setError('');
    setFile(next);
  }

  function clearFile() {
    if (busy) return;
    setFile(null);
    setReparseDocument(false);
    setError('');
    if (inputRef.current) inputRef.current.value = '';
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (busy) return;
    if (event.dataTransfer.files.length > 1) {
      setError('Загрузите один документ за раз. Остальные можно проверить отдельно.');
      return;
    }
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
        closure_policy: item.closure_policy ?? 'source',
      });
      setParsed((current) => current?.id === reportId ? { ...current, items: current.items.map((row, rowIndex) => rowIndex === index ? { ...row, closure_policy: item.closure_policy ?? 'source' } : row) } : current);
      setItems((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, state: 'ready', results: response.results ?? [], checked_at: response.checked_at } : row));
      return true;
    } catch (searchError) {
      setItems((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, state: 'error', error: errorMessage(searchError, 'Не удалось найти товары') } : row));
      return false;
    }
  }

  async function retry(index: number) {
    if (busy || !items[index] || !parsed || ['queued', 'running'].includes(parsed.processing_state)) return;
    setRetryingIndex(index);
    setRetryNotice('');
    setError('');
    setPhase('searching');
    try {
      const succeeded = await searchOne(items[index], index, parsed.id);
      if (succeeded) {
        const updated: ParsedPdf = await api.get(`/quick-check/reports/${parsed.id}`);
        setParsed(updated);
        setItems(updated.items.map((item) => ({ ...item, results: item.results ?? [] })));
        const cards = visibleProductLeads(updated.items[index]?.results ?? []).length;
        setRetryNotice(`Повторный поиск позиции ${index + 1} завершён. Найдено карточек: ${cards}.`);
      } else {
        setRetryNotice(`Не удалось повторить поиск позиции ${index + 1}. Откройте «Все позиции», чтобы увидеть ошибку и попробовать снова.`);
      }
      await refreshHistory();
    } catch (refreshError) {
      setError(errorMessage(refreshError, 'Результат сохранён, но не удалось обновить экран'));
    } finally {
      setRetryingIndex(null);
      setPhase('done');
    }
  }

  async function checkRemaining(report: ParsedPdf) {
    if (busy || (['queued', 'running'].includes(report.processing_state) && !staleSearch)) return;
    setRunningReport(true);
    setRetryNotice('');
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
    } finally {
      setRunningReport(false);
    }
  }

  async function rerunReport(report: ParsedPdf) {
    if (busy || ['queued', 'running'].includes(report.processing_state)) return;
    setRerunningReport(true);
    setRetryNotice('');
    setResultFilter('all');
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
    const validationError = validateDocument(file);
    if (validationError) {
      setError(validationError);
      return;
    }

    setError('');
    setParsed(null);
    setReusedReport(false);
    setRetryNotice('');
    setResultFilter('all');
    setPollError(false);
    setItems([]);
    setPhase('parsing');
    try {
      const form = new FormData();
      form.append('file', file);
      const document: ParsedPdf = await api.post(`/quick-check/parse${reparseDocument ? '?reparse=true' : ''}`, form);
      setParsed(document);
      setReusedReport(Boolean(document.reused));
      setItems(document.items.map((item) => ({ ...item, results: item.results ?? [] })));
      setPhase(['queued', 'running'].includes(document.processing_state) ? 'searching' : 'done');
      window.requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
      if (document.processing_state === 'error') setError('Результат сохранён, но фоновый поиск пока недоступен. Запустите его из сохранённой проверки.');
      await refreshHistory();
    } catch (uploadError) {
      setError(errorMessage(uploadError, 'Не удалось прочитать документ'));
      setPhase('idle');
    }
  }

  const summary = items.reduce((total, item) => {
    const relevant = item.state === 'ready' ? visibleProductLeads(item.results, 'all', item.quantity, item.unit) : [];
    for (const lead of relevant) {
      total.cards += 1;
      if (isConfirmedProductOffer(lead, item.quantity, item.unit)) total.orderReady += 1;
      if (isVerifiedProductLead(lead)) total.confirmedTypes += 1;
      const assessment = orderQuantityAssessment(lead, item.quantity, item.unit);
      total[assessment.verdict] += 1;
    }
    return total;
  }, { cards: 0, orderReady: 0, confirmedTypes: 0, enough: 0, shortage: 0, unknown: 0 });

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-container-max flex-1 flex-col gap-6 p-4 md:p-margin-page">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-3xl">
            <Link href="/dashboard" className="mb-4 inline-flex items-center gap-1.5 text-label-sm text-on-surface-variant transition-colors hover:text-primary">
              <span aria-hidden="true" className="material-symbols-outlined text-[16px]">arrow_back</span>Рабочий стол
            </Link>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">Аналитика закупок</p>
            <h1 className="font-display text-[clamp(1.75rem,3.2vw,2.5rem)] leading-tight font-bold tracking-[-0.04em] text-on-surface">От документа к поставщику</h1>
            <p className="mt-3 max-w-2xl text-body-lg text-on-surface-variant">Проверьте товары из технической спецификации. Получите карточки, контакты продавцов и сравнение характеристик в одном отчёте.</p>
          </div>
          <a href="#quick-check-history" className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-4 py-2 text-label-md text-on-surface transition-colors hover:border-primary hover:text-primary"><span aria-hidden="true" className="material-symbols-outlined text-[18px]">history</span>История проверок<span className="rounded bg-surface-container px-1.5 py-0.5 text-label-sm">{!history.length && (loadingHistory || historyError) ? '—' : historyStats.total_reports}</span></a>
        </div>

        <form onSubmit={(event) => void start(event)} aria-busy={phase === 'parsing'} className="overflow-hidden rounded-2xl border border-outline-variant bg-surface-container-lowest shadow-sm">
          <div className="grid lg:grid-cols-[minmax(0,1fr)_280px] xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="p-5 md:p-7">
              <div className="mb-5 flex items-center gap-3">
                <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary"><span aria-hidden="true" className="material-symbols-outlined text-[21px]">upload_file</span></span>
                <div><h2 className="text-title-lg font-semibold text-on-surface">Новая быстрая проверка</h2><p className="mt-0.5 text-body-sm text-on-surface-variant">Тендер создавать не нужно</p></div>
              </div>
              <div
                onDragOver={(event) => { event.preventDefault(); if (!busy) setDragging(true); }}
                onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false); }}
                onDrop={onDrop}
                className={`relative flex min-h-48 flex-col items-center justify-center gap-4 rounded-xl border border-dashed px-5 py-7 text-center transition-colors ${dragging ? 'border-primary bg-primary/10' : file ? 'border-primary/40 bg-primary/5' : 'border-outline bg-surface-container-low/60 hover:border-primary/60'}`}
              >
                <span aria-hidden="true" className={`material-symbols-outlined text-[34px] ${file ? 'text-primary' : 'text-on-surface-variant'}`}>{file ? 'task_alt' : 'cloud_upload'}</span>
                <div className="min-w-0 max-w-full">
                  <p className="break-words text-body-md font-semibold text-on-surface">{file ? file.name : dragging ? 'Отпустите документ здесь' : 'Перетащите техническую спецификацию'}</p>
                  <p id="quick-check-file-help" className="mt-1.5 text-body-sm text-on-surface-variant">{file ? `${isWordDocument(file.name) ? 'Word · DOCX' : 'PDF'} · ${formatFileSize(file.size)} · готов к проверке` : 'PDF или Word (.docx) · до 20 МБ'}</p>
                </div>
                <input ref={inputRef} aria-label="Выбрать техническую спецификацию" aria-describedby="quick-check-file-help" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" className="hidden" disabled={busy} onChange={(event) => chooseFile(event.target.files?.[0] || null)} />
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <button type="button" disabled={busy} onClick={() => inputRef.current?.click()} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-4 py-2 text-label-md text-on-surface transition-colors hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"><span aria-hidden="true" className="material-symbols-outlined text-[17px]">{file ? 'swap_horiz' : 'folder_open'}</span>{file ? 'Заменить файл' : 'Выбрать файл'}</button>
                  {file && <button type="button" disabled={busy} onClick={clearFile} aria-label={`Убрать файл ${file.name}`} className="flex size-10 items-center justify-center rounded-lg text-on-surface-variant transition-colors hover:bg-error-container hover:text-on-error-container disabled:opacity-50"><span aria-hidden="true" className="material-symbols-outlined text-[20px]">close</span></button>}
                </div>
              </div>
              {file && <div className="mt-4 rounded-lg border border-outline-variant bg-surface-container-low/50 p-3">
                <label className={`flex items-start gap-2.5 text-body-sm text-on-surface ${busy ? 'opacity-60' : 'cursor-pointer'}`}>
                  <input type="checkbox" checked={reparseDocument} disabled={busy} onChange={(event) => setReparseDocument(event.target.checked)} aria-describedby="quick-check-reparse-help" className="mt-0.5 size-4 shrink-0 accent-primary" />
                  <span className="font-medium">Прочитать документ заново</span>
                </label>
                <p id="quick-check-reparse-help" className="mt-1.5 pl-[26px] text-label-sm leading-relaxed text-on-surface-variant">Создаст новую проверку и заново выделит позиции. Старая проверка останется в истории.</p>
              </div>}
              {error && <div role="alert" className="mt-4 flex items-start gap-2.5 rounded-lg bg-error-container px-4 py-3 text-body-sm text-on-error-container"><span aria-hidden="true" className="material-symbols-outlined mt-0.5 text-[18px]">error</span><p>{error}</p></div>}
              <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="flex max-w-sm items-start gap-2 text-label-sm text-on-surface-variant"><span aria-hidden="true" className="material-symbols-outlined text-[16px]">lock</span>Исходный файл не хранится. Результат доступен только вам.</p>
                <button type="submit" disabled={!file || busy} className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-label-md font-semibold text-on-primary shadow-sm transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-45">
                  <span aria-hidden="true" className={`material-symbols-outlined text-[19px] ${busy ? 'animate-spin' : ''}`}>{busy ? 'progress_activity' : 'arrow_forward'}</span>
                  {phase === 'parsing' ? 'Читаем документ…' : 'Запустить проверку'}
                </button>
              </div>
            </div>
            <aside className="border-t border-outline-variant bg-surface-container-low/70 p-5 md:p-7 lg:border-t-0 lg:border-l" aria-label="Этапы проверки">
              <h3 className="text-label-md font-semibold text-on-surface">Что будет в отчёте</h3>
              <ol className="mt-5 space-y-5">
                {[
                  { icon: 'description', title: 'Позиции из документа', text: 'Названия, количество и требования из ТЗ.' },
                  { icon: 'travel_explore', title: 'Товары и продавцы', text: 'Фото, ссылки и опубликованные контакты.' },
                  { icon: 'fact_check', title: 'Сверка характеристик', text: 'Подтверждения и расхождения с источниками.' },
                ].map((step, index) => <li key={step.title} className="flex items-start gap-3"><span aria-hidden="true" className="material-symbols-outlined mt-0.5 text-[20px] text-primary">{step.icon}</span><div><p className="text-body-sm font-semibold text-on-surface"><span className="mr-1 text-on-surface-variant">0{index + 1}.</span> {step.title}</p><p className="mt-1 text-body-sm text-on-surface-variant">{step.text}</p></div></li>)}
              </ol>
              <p className="mt-6 border-t border-outline-variant pt-4 text-label-sm text-on-surface-variant">Сканы: до 12 страниц. Обрабатываем до 20 позиций за проверку. Повторный файл откроет сохранённый отчёт.</p>
            </aside>
          </div>
        </form>

        {phase === 'parsing' && <div role="status" className="flex items-center gap-4 rounded-xl border border-primary/20 bg-primary/5 p-5"><span aria-hidden="true" className="material-symbols-outlined animate-spin text-[25px] text-primary">progress_activity</span><div><p className="text-body-md font-semibold text-on-surface">Читаем техническую спецификацию</p><p className="mt-1 text-body-sm text-on-surface-variant">Выделяем товары, количество и требования. Распознавание скана может занять больше времени.</p></div></div>}

        {parsed && (
          <section ref={resultsRef} className="scroll-mt-6 space-y-4" aria-label="Результаты проверки">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">Отчёт по документу</p>
                <h2 className="text-headline-lg font-headline-lg text-on-surface">Результаты проверки</h2>
                <p className="mt-1 max-w-2xl break-words text-body-sm text-on-surface-variant">{parsed.filename} · {isWordDocument(parsed.filename) ? 'DOCX' : `${parsed.page_count} стр.`} · позиций: {parsed.total_items}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {items.some((item) => item.state !== 'ready') && (!activeSearch || staleSearch) && <button type="button" disabled={busy} onClick={() => void checkRemaining(parsed)} className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-label-sm text-on-primary hover:opacity-90 disabled:opacity-50"><span className="material-symbols-outlined text-[17px]">travel_explore</span>{staleSearch ? 'Возобновить проверку' : 'Проверить оставшиеся'}</button>}
                {!activeSearch && <button type="button" disabled={busy} onClick={() => void rerunReport(parsed)} className="inline-flex items-center gap-1.5 rounded-lg border border-primary px-3 py-1.5 text-label-sm text-primary hover:bg-primary/5 disabled:opacity-50"><span className="material-symbols-outlined text-[17px]">refresh</span>{rerunningReport ? 'Запускаем…' : 'Проверить заново'}</button>}
                <button type="button" disabled={!items.length} onClick={() => downloadReport(parsed, items)} className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 text-label-sm text-on-surface hover:border-primary disabled:opacity-50"><span aria-hidden="true" className="material-symbols-outlined text-[17px]">download</span>Скачать CSV</button>
              </div>
            </div>
            {reusedReport && <p role="status" className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-body-sm text-on-surface">Этот документ уже есть в истории: открыта проверка от {formatDate(parsed.created_at)} без повторной обработки файла. {activeSearch ? 'Поиск ещё идёт в фоне.' : 'Для свежих данных нажмите «Проверить заново» — предыдущий результат останется в истории.'}</p>}
            <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 md:p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3"><span aria-hidden="true" className={`material-symbols-outlined text-[23px] ${activeSearch || retryingIndex != null ? 'animate-spin text-primary' : failed ? 'text-error' : 'text-primary'}`}>{activeSearch || retryingIndex != null ? 'progress_activity' : failed ? 'error' : 'task_alt'}</span><div><p aria-live="polite" className="text-body-md font-semibold text-on-surface">{quickCheckProgressLabel(parsed.processing_state, retryingIndex, completed, items.length, failed)}</p><p className="mt-1 text-body-sm text-on-surface-variant">{retryingIndex != null ? `Обновляем позицию ${retryingIndex + 1}. Дождитесь завершения поиска.` : <>Проверено {completed} из {items.length}{failed ? ` · с ошибкой: ${failed}` : ''}{activeSearch ? '. Прогресс сохраняется, страницу можно закрыть.' : ` · позиций с карточками: ${matchedItems}`}</>}</p></div></div>
                <span className="font-mono-sm text-[20px] font-semibold tabular-nums text-on-surface">{progress}%</span>
              </div>
              <div role="progressbar" aria-label="Обработка позиций документа" aria-valuemin={0} aria-valuemax={items.length || 1} aria-valuenow={completed + failed} aria-valuetext={`Проверено ${completed} из ${items.length}${failed ? `, с ошибкой ${failed}` : ''}`} className="mt-4 h-1.5 overflow-hidden rounded-full bg-surface-container-high"><div className={`h-full rounded-full transition-[width] duration-500 ${failed ? 'bg-error' : 'bg-primary'}`} style={{ width: `${progress}%` }} /></div>
              {pollError && <p role="status" className="mt-3 flex items-center gap-2 text-body-sm text-on-surface-variant"><span aria-hidden="true" className="material-symbols-outlined text-[17px]">cloud_off</span>Не удаётся обновить прогресс. Повторяем запрос автоматически; сохранённые результаты доступны в истории.</p>}
            </div>
            {staleSearch && <p role="status" className="rounded-xl bg-amber-50 px-4 py-3 text-body-sm text-amber-900">Прогресс давно не обновлялся. Нажмите «Возобновить проверку», чтобы продолжить с сохранённого места.</p>}
            {parsed.processing_state === 'error' && retryingIndex == null && <p role="alert" className="rounded-xl bg-error-container px-4 py-3 text-body-sm text-on-error-container">Поиск прервался. Уже найденные товары сохранены; нажмите «Проверить оставшиеся», чтобы продолжить.</p>}
            {parsed.truncated && <p className="rounded-lg bg-amber-50 p-3 text-body-sm text-amber-900">Для быстрой проверки взяты первые 20 позиций документа.</p>}
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
            <p className="flex items-start gap-2 text-label-sm text-on-surface-variant"><span aria-hidden="true" className="material-symbols-outlined text-[16px]">info</span>Готовы к указанному в документе заказу: {summary.orderReady} из {summary.cards} карточек. Подтверждение типа товара ({summary.confirmedTypes}) и отметка «В наличии» сами по себе не подтверждают количество, оптовые условия или документы.</p>
            <div className="flex flex-wrap items-center gap-2 border-b border-outline-variant pb-4" aria-label="Фильтр позиций">
              {([
                { id: 'all', label: 'Все позиции', count: items.length },
                { id: 'with-cards', label: 'С карточками', count: matchedItems },
                { id: 'requirements', label: 'ТЗ подтверждено', count: requirementsItems },
                { id: 'combined', label: 'Готовы к заказу', count: combinedItems },
                { id: 'in-stock', label: 'В наличии', count: inStockItems },
                { id: 'complete', label: 'С фото, ценой и контактом', count: completeItems },
                { id: 'without-cards', label: 'Без карточек', count: withoutCards },
                { id: 'error', label: 'Ошибки', count: failed },
              ] as const).map((filter) => <button key={filter.id} type="button" aria-pressed={resultFilter === filter.id} onClick={() => setResultFilter(filter.id)} className={`inline-flex min-h-10 items-center gap-2 rounded-lg px-3 py-2 text-label-sm transition-colors ${resultFilter === filter.id ? 'bg-primary text-on-primary' : 'bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container'}`}>{filter.label}<span className={`rounded px-1.5 py-0.5 tabular-nums ${resultFilter === filter.id ? 'bg-on-primary/15' : 'bg-surface-container'}`}>{filter.count}</span></button>)}
            </div>
            {resultFilter === 'in-stock' && <p className="text-body-sm text-on-surface-variant">Показаны прочитанные товарные страницы с подтверждённым типом и опубликованной отметкой «В наличии». Достаточность количества для заказа проверяется отдельно.</p>}
            {resultFilter === 'complete' && <p className="text-body-sm text-on-surface-variant">Есть фото товара, положительная цена с валютой и опубликованный телефон. Эти сведения не подтверждают наличие или полное соответствие ТЗ.</p>}
            {resultFilter === 'requirements' && <p className="text-body-sm text-on-surface-variant">Все выделенные требования к товару подтверждены сведениями с прочитанной страницы, включая хотя бы одну техническую характеристику. Сверьте полноту требований с исходным ТЗ; наличие и количество проверяются отдельно.</p>}
            {resultFilter === 'combined' && <p className="text-body-sm text-on-surface-variant">Проверка сервера подтверждает именно количество и единицу этой позиции: требования ТЗ, достаточный остаток, минимальный заказ, вариант товара, основание цены и опубликованные оптовые условия. Непроверенные сертификаты и неизвестные сведения исключают готовность к заказу.</p>}
            {retryNotice && <div role="status" className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-body-sm text-on-surface"><p>{retryNotice}</p>{resultFilter !== 'all' && <button type="button" onClick={() => setResultFilter('all')} className="text-primary hover:underline">Показать все позиции</button>}</div>}
            {!visibleItems.length && <div className="rounded-xl border border-dashed border-outline-variant bg-surface-container-lowest px-5 py-10 text-center"><span aria-hidden="true" className="material-symbols-outlined text-[30px] text-on-surface-variant">filter_list_off</span><p className="mt-2 text-body-md font-semibold text-on-surface">{items.length ? resultFilter === 'combined' ? 'Подтверждённых предложений по всем условиям пока нет' : 'В этом разделе пока нет позиций' : 'В документе не найдены позиции товаров'}</p><p className="mx-auto mt-1 max-w-md text-body-sm text-on-surface-variant">{items.length ? activeSearch ? 'Поиск продолжается. Новые результаты появятся автоматически.' : resultFilter === 'combined' ? matchedItems ? 'Найденные кандидаты сохранены. Ниже показано, какие подтверждения ещё отсутствуют.' : 'Подтверждённых товарных страниц с нужными сведениями пока нет. Откройте все позиции и повторите поиск.' : 'Выберите другой фильтр, чтобы посмотреть результаты проверки.' : 'Проверьте, что документ содержит названия товаров и требования к ним, и загрузите спецификацию снова.'}</p>{resultFilter === 'combined' && combinedGaps.length > 0 && <ul className="mx-auto mt-4 max-w-xl space-y-2 text-left text-body-sm text-on-surface-variant">{combinedGaps.map((gap) => <li key={gap.code} className="flex items-start gap-2"><span aria-hidden="true" className="material-symbols-outlined mt-0.5 text-[16px] text-amber-600">info</span><span>{gap.label}</span></li>)}</ul>}{resultFilter !== 'all' && <button type="button" onClick={() => setResultFilter('all')} className="mt-4 text-label-md text-primary hover:underline">Показать все позиции и причины</button>}</div>}
            {visibleItems.map(({ item, index }) => (
              <article key={`${item.source_section || item.product_name}-${index}`} className="overflow-hidden rounded-2xl border border-outline-variant bg-surface-container-lowest shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3 p-4 md:p-5">
                  <div className="min-w-0 flex-1 basis-64">
                    <p className="text-label-sm text-primary">Позиция {index + 1}{item.source_section ? ` · ${item.source_section}` : ''}</p>
                    <h3 className="mt-1 break-words text-title-lg font-semibold text-on-surface">{item.product_name}</h3>
                    {item.specs && <details className="group mt-3 max-w-4xl"><summary className="cursor-pointer text-label-sm text-on-surface-variant transition-colors hover:text-primary">Требования из документа</summary><p className="mt-2 break-words whitespace-pre-line rounded-lg bg-surface-container-low p-3 text-body-sm text-on-surface-variant">{item.specs}</p></details>}
                  </div>
                  <div className="flex flex-col items-start gap-2 sm:items-end">
                    <span className="rounded-lg bg-surface-container-low px-3 py-2 text-label-md text-on-surface">По ТЗ: {requiredAmount(item)}</span>
                    {supportsClosureClarification(item) && <div className="w-full max-w-sm rounded-lg border border-outline-variant bg-surface-container-low/50 p-3 text-left">
                      <label htmlFor={`closure-policy-${parsed.id}-${index}`} className="mb-1.5 block text-label-sm font-medium text-on-surface">Допустимая застёжка</label>
                      <select id={`closure-policy-${parsed.id}-${index}`} value={item.closure_policy ?? 'source'} disabled={busy || activeSearch || item.state === 'searching'} aria-describedby={`closure-policy-help-${parsed.id}-${index}`} onChange={(event) => setItems((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, closure_policy: event.target.value as ClosurePolicy } : row))} className="min-h-10 w-full rounded-lg border border-outline-variant bg-surface-container-lowest px-2 py-2 text-body-sm text-on-surface focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/15 disabled:opacity-60">
                        {(Object.entries(CLOSURE_POLICY_LABELS) as [ClosurePolicy, string][]).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                      <p id={`closure-policy-help-${parsed.id}-${index}`} className="mt-2 text-label-sm leading-relaxed text-on-surface-variant">Уточнение применяется при повторном поиске; исходное ТЗ не меняется.</p>
                      {(item.closure_policy ?? 'source') !== (parsed.items[index]?.closure_policy ?? 'source') && <p className="mt-1 text-label-sm font-medium text-primary">Выбрано для следующего поиска</p>}
                    </div>}
                    {item.checked_at && item.state === 'ready' && <span className="text-label-sm text-on-surface-variant">Проверено {formatDate(item.checked_at)}</span>}
                    {item.state !== 'searching' && !['queued', 'running'].includes(parsed.processing_state) && <button type="button" disabled={busy} onClick={() => void retry(index)} className="inline-flex items-center gap-1 text-label-sm text-primary hover:underline disabled:opacity-50"><span className="material-symbols-outlined text-[16px]">{item.state === 'pending' ? 'search' : 'refresh'}</span>{item.state === 'pending' ? 'Найти товары' : 'Повторить поиск'}</button>}
                  </div>
                </div>
                {item.state === 'ready' ? <>
                  <ProductDiscoveryCards productName={item.product_name} leads={item.results} requestedQuantity={item.quantity} requestedUnit={item.unit} leadFilter={leadFilter} />
                  {(() => {
                    const best = visibleProductLeads(item.results, leadFilter, item.quantity, item.unit).find(isVerifiedProductLead);
                    if (!best?.checks?.length) return null;
                    return <details className="group border-t border-outline-variant bg-surface-container-low px-4 py-4 md:px-5">
                      <summary className="cursor-pointer text-body-sm font-semibold text-on-surface">Доказательства по первому найденному товару <span className="ml-1 text-label-sm font-normal text-on-surface-variant">({best.checks.length})</span></summary>
                      <p className="mt-1 text-body-sm text-on-surface-variant">{best.title || 'Товар без названия'} · сведения с открытой страницы продавца</p>
                      {best.url && <a href={best.url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1 text-label-sm text-primary hover:underline">Открыть источник<span aria-hidden="true" className="material-symbols-outlined text-[15px]">open_in_new</span></a>}
                      <div className="mt-3 space-y-2">
                        {(best.checks ?? []).map((check) => ({ ...check, status: effectiveProductCheckStatus(check) })).map((check, checkIndex) => (
                          <div key={`${check.id || checkIndex}-${checkIndex}`} className="grid gap-1 rounded-lg border border-outline-variant bg-surface-container-lowest p-3 text-body-sm md:grid-cols-[minmax(0,1fr)_125px_minmax(0,1fr)] md:gap-3">
                            <span className="font-medium text-on-surface">{check.requirement}</span>
                            <span className={check.status === 'matched' ? 'text-emerald-700' : check.status === 'mismatch' ? 'text-rose-700' : 'text-amber-700'}>{check.status === 'matched' ? 'Подтверждено' : check.status === 'mismatch' ? 'Расхождение' : 'Нет данных'}</span>
                            <span className="break-words text-on-surface-variant">{check.evidence || 'Доказательство на странице не найдено'}</span>
                          </div>
                        ))}
                      </div>
                    </details>;
                  })()}
                </> : (
                  <div aria-live="polite" className={`flex items-center gap-3 border-t border-outline-variant px-5 py-5 text-body-sm ${item.state === 'error' ? 'bg-error-container/30 text-error' : 'bg-surface-container-low/50 text-on-surface-variant'}`}>
                    <span aria-hidden="true" className={`material-symbols-outlined text-[20px] ${item.state === 'searching' ? 'animate-spin text-primary' : ''}`}>{item.state === 'error' ? 'error' : item.state === 'searching' ? 'progress_activity' : 'schedule'}</span>
                    {item.state === 'error' ? item.error || 'Не удалось выполнить поиск. Повторите его для этой позиции.' : item.state === 'searching' ? 'Ищем товарные страницы и сверяем характеристики…' : 'Позиция ожидает проверки. Поиск начнётся по очереди.'}
                  </div>
                )}
              </article>
            ))}
          </section>
        )}

        <section id="quick-check-history" className="scroll-mt-6 overflow-hidden rounded-2xl border border-outline-variant bg-surface-container-lowest shadow-sm" aria-label="История проверок">
          <div className="flex flex-wrap items-start justify-between gap-4 p-5 md:p-6">
            <div><p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">Личное пространство</p><h2 className="text-title-lg font-semibold text-on-surface">История проверок</h2><p className="mt-1 text-body-sm text-on-surface-variant">Возвращайтесь к результатам и обновляйте данные продавцов.</p></div>
            <button type="button" disabled={loadingHistory} onClick={() => void refreshHistory()} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-outline-variant px-3 py-2 text-label-sm text-on-surface transition-colors hover:border-primary hover:text-primary disabled:opacity-50"><span aria-hidden="true" className={`material-symbols-outlined text-[17px] ${loadingHistory ? 'animate-spin' : ''}`}>refresh</span>Обновить</button>
          </div>
          <div className="grid divide-y divide-outline-variant border-y border-outline-variant bg-surface-container-low/50 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {[
              { label: 'Сохранённых проверок', value: historyStats.total_reports, icon: 'folder' },
              { label: 'Позиций в документах', value: historyStats.total_items, icon: 'inventory_2' },
              { label: 'Позиций проверено', value: historyStats.checked_items, icon: 'task_alt' },
            ].map((stat) => <div key={stat.label} className="flex items-center justify-between gap-3 px-5 py-4 md:px-6"><span className="flex items-center gap-2 text-label-sm text-on-surface-variant"><span aria-hidden="true" className="material-symbols-outlined text-[18px] text-primary">{stat.icon}</span>{stat.label}</span><span className="text-title-lg font-semibold tabular-nums text-on-surface">{!history.length && (loadingHistory || historyError) ? '—' : stat.value}</span></div>)}
          </div>
          <div className="p-5 md:p-6">
            {history.length > 0 && <label className="mb-4 flex max-w-md items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-low px-3 py-2.5 text-on-surface-variant focus-within:border-primary"><span aria-hidden="true" className="material-symbols-outlined text-[18px]">search</span><input type="search" value={historyQuery} onChange={(event) => setHistoryQuery(event.target.value)} placeholder="Найти загруженную проверку…" aria-label="Поиск среди загруженных проверок по имени файла" className="min-w-0 flex-1 bg-transparent text-body-sm text-on-surface outline-none placeholder:text-on-surface-variant" /></label>}
            {historyError && <p role="alert" className="mb-4 flex items-start gap-2 rounded-lg bg-error-container px-4 py-3 text-body-sm text-on-error-container"><span aria-hidden="true" className="material-symbols-outlined text-[18px]">error</span>{historyError}</p>}
            {loadingHistory && !history.length ? <div role="status" aria-label="Загрузка истории проверок" className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{[0, 1, 2].map((value) => <div key={value} className="animate-pulse rounded-xl border border-outline-variant p-4"><div className="h-3 w-4/5 rounded bg-surface-container-high" /><div className="mt-3 h-2.5 w-2/3 rounded bg-surface-container" /><div className="mt-4 h-2.5 w-1/3 rounded bg-surface-container" /></div>)}</div> : filteredHistory.length ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {filteredHistory.map((report) => <div key={report.id} className={`flex items-stretch overflow-hidden rounded-xl border transition-colors hover:border-primary/60 ${parsed?.id === report.id ? 'border-primary/60 bg-primary/5' : 'border-outline-variant bg-surface-container-lowest'}`}>
                <button type="button" aria-current={parsed?.id === report.id ? 'true' : undefined} disabled={busy || loadingReport || Boolean(deletingReportId)} onClick={() => void openReport(report.id)} className="min-w-0 flex-1 p-4 text-left disabled:opacity-50">
                  <div className="flex items-center gap-2"><span aria-hidden="true" className={`material-symbols-outlined shrink-0 text-[20px] text-primary ${openingReportId === report.id ? 'animate-spin' : ''}`}>{openingReportId === report.id ? 'progress_activity' : 'description'}</span><span title={report.filename} className="truncate text-body-sm font-semibold text-on-surface">{report.filename}</span></div>
                  <span className="mt-2 block text-label-sm text-on-surface-variant">{formatDate(report.created_at)}</span>
                  <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1"><span className={`inline-flex items-center gap-1 text-label-sm ${report.processing_state === 'error' ? 'text-error' : 'text-primary'}`}><span aria-hidden="true" className="material-symbols-outlined text-[14px]">{['queued', 'running'].includes(report.processing_state) ? 'schedule' : report.processing_state === 'error' ? 'error' : report.processing_state === 'completed' ? 'check_circle' : 'pending'}</span>{reportStatus(report.processing_state)}</span><span className="text-label-sm tabular-nums text-on-surface-variant">{report.checked_items} / {report.total_items}</span></div>
                </button>
                <button type="button" title="Удалить проверку" aria-label={`Удалить проверку ${report.filename}`} disabled={busy || loadingReport || Boolean(deletingReportId)} onClick={() => void deleteReport(report)} className="flex min-w-11 items-center justify-center border-l border-outline-variant px-2 text-on-surface-variant transition-colors hover:bg-error-container hover:text-on-error-container disabled:opacity-50"><span aria-hidden="true" className={`material-symbols-outlined text-[18px] ${deletingReportId === report.id ? 'animate-spin' : ''}`}>{deletingReportId === report.id ? 'progress_activity' : 'delete'}</span></button>
              </div>)}
            </div> : !historyError && <div className="py-7 text-center"><span aria-hidden="true" className="material-symbols-outlined text-[32px] text-on-surface-variant">{historyQuery ? 'search_off' : 'folder_open'}</span><p className="mt-2 text-body-md font-semibold text-on-surface">{historyQuery ? 'По этому имени ничего не найдено' : 'Ваша первая проверка появится здесь'}</p><p className="mx-auto mt-1 max-w-md text-body-sm text-on-surface-variant">{historyQuery ? 'Попробуйте другую часть имени файла или загрузите более ранние проверки.' : 'Загрузите PDF или Word выше. Сохраним результаты, чтобы вы могли вернуться к ним в любое время.'}</p>{historyQuery && <button type="button" onClick={() => setHistoryQuery('')} className="mt-3 text-label-md text-primary hover:underline">Сбросить поиск</button>}</div>}
            {nextHistoryCursor && <button type="button" disabled={loadingHistory} onClick={() => void loadMoreHistory()} className="mt-5 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-outline-variant px-4 py-2 text-label-md text-on-surface transition-colors hover:border-primary hover:text-primary disabled:opacity-50"><span aria-hidden="true" className={`material-symbols-outlined text-[18px] ${loadingHistory ? 'animate-spin' : ''}`}>{loadingHistory ? 'progress_activity' : 'expand_more'}</span>{loadingHistory ? 'Загружаем…' : 'Загрузить более ранние проверки'}</button>}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
