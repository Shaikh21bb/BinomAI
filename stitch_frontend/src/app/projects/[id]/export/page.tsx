'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api';
import { InfoBanner } from '@/components/ui';

const DOC_TYPES = [
  { key: 'commercial_proposal', label: 'Коммерческое предложение', icon: 'request_quote' },
  { key: 'tech_spec', label: 'Техническая спецификация', icon: 'build' },
  { key: 'cover_letter', label: 'Сопроводительное письмо', icon: 'mail' },
];

function downloadDemo(format: 'docx' | 'pdf', label: string) {
  const isDocx = format === 'docx';
  const content = [
    `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word">`,
    `<head><meta charset="utf-8"><title>${label}</title></head>`,
    `<body>`,
    `<h1 style="font-family: Arial; text-align:center">${label}</h1>`,
    `<hr>`,
    `<p style="font-family: Arial; font-size:12pt">Демо-версия документа BINOM AI.<br>После подключения бэкенда файл формируется сервером автоматически.</p>`,
    `</body></html>`,
  ].join('\n');

  const blob = new Blob(['\ufeff', content], { type: isDocx ? 'application/msword' : 'application/pdf' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${label.replace(/\s+/g, '_')}.${format}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function ProjectExportPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [exporting, setExporting] = useState<Record<string, 'docx' | 'pdf'>>({});
  const [backendUnavailable, setBackendUnavailable] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Probe availability of the export API. If listing fails, fall back to client-side demo export.
        await api.get(`/projects/${projectId}/documents/generated`);
      } catch {
        if (!cancelled) setBackendUnavailable(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

const handleExport = async (docType: string, format: 'docx' | 'pdf') => {
    const doc = DOC_TYPES.find((d) => d.key === docType);
    setExporting({ [docType]: format });
    setDone(null);
    try {
      await api.post(`/projects/${projectId}/documents/generated/${docType}/export`, { format });
      setBackendUnavailable(true);
    } catch {
      setBackendUnavailable(true);
      downloadDemo(format, doc?.label ?? docType);
    } finally {
      setExporting({});
      setDone(`${doc?.label ?? docType} · ${format.toUpperCase()}`);
    }
  };

  return (
    <div className="p-4 md:p-margin-page max-w-3xl mx-auto flex-1 flex flex-col gap-stack-lg w-full">
      <div>
        <h2 className="text-headline-lg font-headline-lg text-on-surface">Экспорт документов</h2>
        <p className="text-body-md font-body-md text-on-surface-variant">
          Скачайте финальные документы в формате DOCX или PDF для подачи заявки.
        </p>
      </div>

      {backendUnavailable && (
        <InfoBanner>
          Сервер экспорта сейчас не подключён. Скачивание выполняется в демо-режиме — после подключения бэкенда файлы
          формируются автоматически.
        </InfoBanner>
      )}

      <div className="flex flex-col gap-3">
        {DOC_TYPES.map((doc) => {
          const busy = exporting[doc.key];
          return (
            <div
              key={doc.key}
              className="bg-surface-container-lowest border border-outline-variant rounded-lg px-stack-md py-stack-md flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:border-on-background/20 transition-colors"
            >
              <div className="flex items-center gap-stack-md">
                <div className="w-10 h-10 rounded-lg bg-surface-container-high flex items-center justify-center text-primary">
                  <span className="material-symbols-outlined text-[22px]">{doc.icon}</span>
                </div>
                <div>
                  <h3 className="text-headline-md font-headline-md text-on-surface">{doc.label}</h3>
                  <p className="text-label-md font-label-md text-on-surface-variant">Версия 1 • ГОСТ РК</p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {busy && (
                  <span className="flex items-center gap-2 text-label-md font-label-md text-on-surface-variant w-28">
                    <span className="material-symbols-outlined animate-spin text-[16px] text-primary">sync</span>
                    Подготовка...
                  </span>
                )}
                <button
                  onClick={() => handleExport(doc.key, 'docx')}
                  disabled={Boolean(busy)}
                  className="px-4 py-2 bg-surface-bright border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface-variant hover:bg-surface-container-low disabled:opacity-50 transition-colors flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-[16px]">download</span>
                  DOCX
                </button>
                <button
                  onClick={() => handleExport(doc.key, 'pdf')}
                  disabled={Boolean(busy)}
                  className="px-4 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md disabled:opacity-50 hover:opacity-90 transition-opacity flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-[16px]">picture_as_pdf</span>
                  PDF
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-2 px-4 py-3 bg-surface-container-low border border-outline-variant rounded-lg text-body-sm font-body-sm text-on-surface-variant">
        <span className="material-symbols-outlined text-[18px] text-primary">check_circle</span>
        После экспорта рекомендуется пометить тендер статусом «Подан» в списке тендеров.
      </div>

      {done && (
        <div className="bg-surface-container-lowest border border-outline-variant rounded-lg p-stack-md flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="w-9 h-9 rounded-full bg-emerald-50 text-emerald-700 flex items-center justify-center">
              <span className="material-symbols-outlined text-[20px]" style={{ fontVariationSettings: "'FILL' 1" }}>check</span>
            </span>
            <div>
              <p className="text-body-md font-body-md text-on-surface font-medium">Файл скачан: {done}</p>
              <p className="text-body-sm font-body-sm text-on-surface-variant">Проверьте документы перед подачей заявки.</p>
            </div>
          </div>
          <div className="flex gap-2 shrink-0">
            <Link
              href={`/projects/${projectId}/generate`}
              className="px-4 py-2 bg-surface-bright border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface-variant hover:bg-surface-container-low transition-colors flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-[16px]">description</span>
              К документам
            </Link>
            <Link
              href="/dashboard"
              className="px-4 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-[16px]">folder_open</span>
              К списку тендеров
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}