'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { api, downloadBlob, downloadBlobPost, errorMessage } from '@/lib/api';

const DOC_TYPES: Record<string, { label: string; icon: string }> = {
  commercial_proposal: { label: 'Коммерческое предложение', icon: 'request_quote' },
  tech_spec: { label: 'Техническая спецификация', icon: 'build' },
  cover_letter: { label: 'Сопроводительное письмо', icon: 'mail' },
};

interface GeneratedDoc {
  id: string;
  doc_type: string;
  version: number;
  title: string;
  generation_status: 'ready' | 'processing' | 'error' | 'failed' | string;
  error_message?: string | null;
  exported_formats: string[];
}

const STATUS_META: Record<string, { label: string; cls: string }> = {
  ready: { label: 'Готов', cls: 'bg-emerald-50 text-emerald-700' },
  generating: { label: 'Генерируется…', cls: 'bg-amber-50 text-amber-700' },
  processing: { label: 'Генерируется…', cls: 'bg-amber-50 text-amber-700' },
  pending: { label: 'В очереди', cls: 'bg-amber-50 text-amber-700' },
  error: { label: 'Ошибка', cls: 'bg-red-50 text-red-700' },
  failed: { label: 'Ошибка', cls: 'bg-red-50 text-red-700' },
};

const NON_TERMINAL = new Set(['generating', 'processing', 'pending']);

function safeFileName(value: string): string {
  const cleaned = value
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_')
    .replace(/\s+/g, '_')
    .replace(/_+/g, '_')
    .trim();
  return cleaned || 'document';
}

export default function ProjectExportPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [docs, setDocs] = useState<GeneratedDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [exporting, setExporting] = useState<Record<string, 'docx' | 'pdf'>>({});
  const [packageBusy, setPackageBusy] = useState(false);
  const [packageError, setPackageError] = useState('');
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = (await api.get(`/projects/${projectId}/documents/generated`)) as GeneratedDoc[];
        if (!cancelled) setDocs(list);
      } catch (err) {
        if (!cancelled) setLoadError(errorMessage(err, 'Не удалось загрузить документы'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    if (loading || docs.length === 0 || !docs.some((d) => NON_TERMINAL.has(d.generation_status))) return;
    const timer = setInterval(async () => {
      try {
        const list = (await api.get(`/projects/${projectId}/documents/generated`)) as GeneratedDoc[];
        setDocs(list);
        if (!list.some((d) => NON_TERMINAL.has(d.generation_status))) {
          clearInterval(timer);
        }
      } catch {
        clearInterval(timer);
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [projectId, docs, loading]);

  const readyDocs = docs.filter((d) => d.generation_status === 'ready');

  const handleDownloadPackage = async () => {
    setPackageBusy(true);
    setPackageError('');
    setDone(null);
    try {
      await downloadBlob(
        `/projects/${projectId}/documents/export-package?format=pdf`,
        `binom_package_${new Date().toISOString().slice(0, 10)}.zip`
      );
      setDone(`Пакет документов (${readyDocs.length} файл.)`);
    } catch (err) {
      setPackageError(errorMessage(err, 'Не удалось скачать пакет'));
    } finally {
      setPackageBusy(false);
    }
  };

  const handleExport = async (doc: GeneratedDoc, format: 'docx' | 'pdf') => {
    setExporting((prev) => ({ ...prev, [doc.id]: format }));
    setDone(null);
    const base = `${safeFileName(doc.title)}_v${doc.version}.${format}`;
    try {
      await downloadBlobPost(
        `/projects/${projectId}/documents/generated/${doc.doc_type}/export`,
        { format },
        base
      );
      setDone(`${doc.title} · v${doc.version} · ${format.toUpperCase()}`);
      setDocs((prev) =>
        prev.map((d) =>
          d.id === doc.id && !d.exported_formats.includes(format)
            ? { ...d, exported_formats: [...d.exported_formats, format] }
            : d
        )
      );
    } catch (err) {
      setPackageError(errorMessage(err, 'Не удалось скачать документ'));
    } finally {
      setExporting((prev) => {
        const next = { ...prev };
        delete next[doc.id];
        return next;
      });
    }
  };

  return (
    <div className="p-4 md:p-margin-page max-w-3xl mx-auto flex-1 flex flex-col gap-stack-lg w-full">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-headline-lg font-headline-lg text-on-surface">Экспорт документов</h2>
          <p className="text-body-md font-body-md text-on-surface-variant">
            Скачайте финальные документы в формате DOCX или PDF для подачи заявки.
          </p>
        </div>
        <button
          onClick={handleDownloadPackage}
          disabled={packageBusy || readyDocs.length === 0}
          className="px-4 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md disabled:opacity-40 hover:opacity-90 transition-opacity flex items-center gap-2"
          title={readyDocs.length === 0 ? 'Нет готовых документов' : undefined}
        >
          {packageBusy ? (
            <span className="flex items-center gap-2">
              <span className="material-symbols-outlined animate-spin text-[16px]">sync</span>
              Подготовка пакета…
            </span>
          ) : (
            <>
              <span className="material-symbols-outlined text-[16px]">folder_zip</span>
              Скачать весь пакет (ZIP)
            </>
          )}
        </button>
      </div>

      {(packageError || loadError) && (
        <div className="px-4 py-3 bg-red-50 text-red-800 border border-red-200 rounded-lg text-body-md font-body-md">
          {packageError || loadError}
        </div>
      )}

      {done && (
        <div className="px-4 py-3 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg text-body-md font-body-md">
          Файл скачан: {done}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-label-md font-label-md text-on-surface-variant">
          <span className="material-symbols-outlined animate-spin text-[16px] text-primary">sync</span>
          Загрузка документов…
        </div>
      )}

      {!loading && docs.length === 0 && (
        <div className="flex flex-col items-center gap-3 px-6 py-10 bg-surface-container-lowest border border-outline-variant rounded-lg text-center">
          <span className="material-symbols-outlined text-[40px] text-on-surface-variant">description</span>
          <div>
            <p className="text-body-md font-body-md text-on-surface">Документы ещё не сгенерированы</p>
            <p className="text-body-sm font-body-sm text-on-surface-variant">
              Сгенерируйте коммерческое предложение, спецификацию или сопроводительное письмо, чтобы экспортировать их.
            </p>
          </div>
          <Link
            href={`/projects/${projectId}/generate`}
            className="px-4 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity"
          >
            Перейти к генерации
          </Link>
        </div>
      )}

      {!loading && docs.length > 0 && (
        <div className="flex flex-col gap-3">
          {docs.map((doc) => {
            const meta = DOC_TYPES[doc.doc_type];
            const status = STATUS_META[doc.generation_status] ?? { label: doc.generation_status, cls: 'bg-surface-container-high text-on-surface-variant' };
            const busy = exporting[doc.id];
            const isReady = doc.generation_status === 'ready';
            return (
              <div
                key={doc.id}
                className="bg-surface-container-lowest border border-outline-variant rounded-lg px-stack-md py-stack-md flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:border-on-background/20 transition-colors"
              >
                <div className="flex items-center gap-stack-md min-w-0">
                  <div className="w-10 h-10 rounded-lg bg-surface-container-high flex items-center justify-center text-primary shrink-0">
                    <span className="material-symbols-outlined text-[22px]">{meta?.icon ?? 'description'}</span>
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-headline-md font-headline-md text-on-surface truncate">
                      {meta?.label ?? doc.title}
                    </h3>
                    <p className="text-label-md font-label-md text-on-surface-variant flex items-center gap-2 flex-wrap">
                      Версия {doc.version}
                      <span className={`px-2 py-0.5 rounded-full text-label-sm font-label-sm ${status.cls}`}>
                        {status.label}
                      </span>
                      {doc.exported_formats.length > 0 && (
                        <span className="text-on-surface-variant/70">
                          Экспортирован: {doc.exported_formats.map((f) => f.toUpperCase()).join(', ')}
                        </span>
                      )}
                    </p>
                    {doc.generation_status === 'error' && doc.error_message && (
                      <p className="text-label-sm font-label-sm text-red-600 mt-1 truncate">{doc.error_message}</p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {busy && (
                    <span className="flex items-center gap-2 text-label-md font-label-md text-on-surface-variant w-28">
                      <span className="material-symbols-outlined animate-spin text-[16px] text-primary">sync</span>
                      Подготовка...
                    </span>
                  )}
                  {isReady ? (
                    <>
                      <button
                        onClick={() => handleExport(doc, 'docx')}
                        disabled={Boolean(busy)}
                        className="px-4 py-2 bg-surface-bright border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface-variant hover:bg-surface-container-low disabled:opacity-50 transition-colors flex items-center gap-2"
                      >
                        <span className="material-symbols-outlined text-[16px]">download</span>
                        DOCX
                      </button>
                      <button
                        onClick={() => handleExport(doc, 'pdf')}
                        disabled={Boolean(busy)}
                        className="px-4 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md disabled:opacity-50 hover:opacity-90 transition-opacity flex items-center gap-2"
                      >
                        <span className="material-symbols-outlined text-[16px]">picture_as_pdf</span>
                        PDF
                      </button>
                    </>
                  ) : (
                    <Link
                      href={`/projects/${projectId}/generate`}
                      className="px-4 py-2 bg-surface-bright border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface-variant hover:bg-surface-container-low transition-colors flex items-center gap-2"
                    >
                      <span className="material-symbols-outlined text-[16px]">refresh</span>
                      К генерации
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {docs.length > 0 && readyDocs.length > 0 && (
        <div className="flex items-center gap-2 px-4 py-3 bg-surface-container-low border border-outline-variant rounded-lg text-body-sm font-body-sm text-on-surface-variant">
          <span className="material-symbols-outlined text-[18px] text-primary">check_circle</span>
          После экспорта рекомендуется пометить тендер статусом «Подан» в списке тендеров.
        </div>
      )}
    </div>
  );
}
