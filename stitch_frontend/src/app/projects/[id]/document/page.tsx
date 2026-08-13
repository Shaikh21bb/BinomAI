'use client';

import { ChangeEvent, DragEvent, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { api, asError, errorMessage } from '@/lib/api';
import { InfoBanner } from '@/components/ui';

interface Document {
  id: string;
  filename: string;
  file_size_bytes?: number;
  page_count?: number;
  processing_status: string;
  error_message?: string;
  created_at?: string;
}

const STATUS_LABEL: Record<string, string> = {
  upload: 'Загрузка',
  uploading: 'Загрузка',
  processing: 'Обработка',
  pending: 'В очереди',
  ready: 'Готово',
  completed: 'Готово',
  error: 'Ошибка',
  failed: 'Ошибка',
};

function formatBytes(bytes: number) {
  if (!bytes) return '';
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

export default function ProjectDocumentPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [documents, setDocuments] = useState<Document[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState('');
  const [demoMode, setDemoMode] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const downloadDoc = async (doc: Document) => {
    setError('');
    try {
      const res = await api.get(`/projects/${projectId}/documents/${doc.id}/download`);
      if (res?.url) {
        window.open(res.url, '_blank', 'noopener');
      } else {
        setError('Не удалось получить ссылку на файл');
      }
    } catch (err) {
      setError(errorMessage(err, 'Не удалось скачать документ'));
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`/projects/${projectId}/documents/current`);
        if (!cancelled) setDocuments(Array.isArray(res) ? res : []);
      } catch {
        if (!cancelled) {
          setDemoMode(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    const processing = documents.filter(
      (d) => d.processing_status === 'processing' || d.processing_status === 'pending' || d.processing_status === 'uploading'
    );
    if (processing.length === 0) return;

    const interval = setInterval(async () => {
      for (const doc of processing) {
        try {
          const statusRes = await api.get(`/projects/${projectId}/documents/${doc.id}/status`);
          setDocuments((prev) =>
            prev.map((d) =>
              d.id === doc.id
                ? {
                    ...d,
                    processing_status: statusRes.processing_status,
                    error_message: statusRes.error_message,
                  }
                : d
            )
          );
        } catch {
          /* ignore transient poll errors */
        }
      }
    }, 4000);

    return () => clearInterval(interval);
  }, [documents, projectId]);

  const uploadFile = async (file: File) => {
    if (!projectId) {
      setError('Проект не выбран');
      return;
    }
    const allowed = ['.pdf', '.doc', '.docx'];
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
    if (!allowed.includes(ext)) {
      setError('Поддерживаются только файлы PDF и DOCX');
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setError('Файл слишком большой. Максимальный размер: 50 МБ');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    setIsUploading(true);
    setUploadProgress(0);
    setError('');

    const progressInterval = setInterval(() => {
      setUploadProgress((p) => Math.min(p + 8, 90));
    }, 400);

    const addLocal = (newDoc: Document, status?: string) => {
      setDocuments((prev) => [
        ...prev.filter((d) => d.id !== newDoc.id),
        { ...newDoc, processing_status: status ?? newDoc.processing_status },
      ]);
    };

    try {
      const newDoc = await api.post(`/projects/${projectId}/documents`, formData);
      clearInterval(progressInterval);
      setUploadProgress(100);
      addLocal(
        {
          id: newDoc.id ?? newDoc.document_id,
          filename: newDoc.filename,
          file_size_bytes: newDoc.file_size_bytes,
          processing_status: newDoc.processing_status ?? 'processing',
        }
      );
    } catch (err) {
      clearInterval(progressInterval);
      if (asError(err).status === 404 || asError(err).status === 405) {
        setDemoMode(true);
        setUploadProgress(100);
        addLocal(
          {
            id: `local-${Date.now()}`,
            filename: file.name,
            file_size_bytes: file.size,
            processing_status: 'ready',
          },
          'ready'
        );
      } else {
        setError(errorMessage(err, 'Не удалось загрузить файл'));
      }
    } finally {
      setIsUploading(false);
      setTimeout(() => setUploadProgress(0), 1000);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  };

  const ready = documents.some((d) => d.processing_status === 'ready' || d.processing_status === 'completed');

  return (
    <div className="p-4 md:p-margin-page max-w-3xl mx-auto flex-1 flex flex-col gap-stack-lg w-full">
      <div>
        <h2 className="text-headline-lg font-headline-lg text-on-surface">Техническое задание</h2>
        <p className="text-body-md font-body-md text-on-surface-variant">
          Загрузите PDF или DOCX с тендерным техническим заданием — AI автоматически проанализирует его.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-error-container text-on-error-container rounded-lg text-body-md font-body-md">
          {error}
        </div>
      )}

      {demoMode && (
        <InfoBanner>
          Сервер документов сейчас не подключён — работает демо-режим. Файл добавляется локально, AI-анализ и вся
          обработка будут выполняться после подключения бэкенда.
        </InfoBanner>
      )}

      {/* Upload zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`upload-dashed rounded-xl p-stack-lg bg-surface-container-lowest hover:bg-surface-container transition-colors cursor-pointer group flex flex-col items-center justify-center text-center min-h-[260px] ${
          dragOver ? 'bg-surface-container-high' : ''
        }`}
      >
        <div className="w-16 h-16 rounded-full bg-surface-container-high flex items-center justify-center mb-stack-md group-hover:scale-110 transition-transform duration-300 ai-pulse-border">
          <span className="material-symbols-outlined text-3xl text-primary">cloud_upload</span>
        </div>
        <h3 className="text-headline-md font-headline-md text-on-surface mb-stack-sm">
          {dragOver ? 'Отпустите файл для загрузки' : 'Загрузить техническое задание'}
        </h3>
        <p className="text-body-md font-body-md text-on-surface-variant mb-stack-md">
          Перетащите PDF или DOCX сюда или нажмите для выбора файла
        </p>
        <div className="flex gap-unit items-center text-mono-sm font-mono-sm text-outline">
          <span className="material-symbols-outlined text-[14px]">picture_as_pdf</span>
          <span className="material-symbols-outlined text-[14px]">description</span>
          <span>PDF, DOCX до 50 МБ</span>
        </div>
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          accept=".pdf,.doc,.docx"
          onChange={handleFileSelect}
        />
      </div>

      {isUploading && (
        <div className="bg-surface-bright border border-outline-variant rounded-lg p-stack-md flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-stack-md flex-1">
            <span className="material-symbols-outlined text-primary">upload_file</span>
            <div className="flex-1">
              <p className="text-body-md font-body-md text-on-surface font-medium">Загрузка файла...</p>
            </div>
          </div>
          <div className="flex items-center gap-stack-md w-1/3">
            <div className="flex-1 h-1.5 bg-surface-container-high rounded-full overflow-hidden">
              <div className="h-full bg-primary rounded-full transition-all duration-300" style={{ width: `${uploadProgress}%` }} />
            </div>
            <span className="text-mono-sm font-mono-sm text-on-surface-variant">{uploadProgress}%</span>
          </div>
        </div>
      )}

      {/* Documents list */}
      <div className="space-y-stack-sm">
        <h4 className="text-label-md font-label-md uppercase text-on-surface-variant tracking-wider">
          Прикреплённые документы
        </h4>

        {documents.length === 0 && !isUploading && (
          <p className="text-body-md font-body-md text-on-surface-variant">Документы ещё не загружены</p>
        )}

        {documents.map((doc) => (
          <div
            key={doc.id}
            className="bg-surface-container-lowest border border-outline-variant rounded-lg p-stack-md flex items-center justify-between"
          >
            <div className="flex items-center gap-stack-md min-w-0">
              <span className="material-symbols-outlined text-on-surface-variant shrink-0">description</span>
              <div className="min-w-0">
                <p className="text-body-md font-body-md text-on-surface truncate">{doc.filename}</p>
                <p className="text-mono-sm font-mono-sm text-on-surface-variant">
                  {formatBytes(doc.file_size_bytes ?? 0)}
                  {doc.page_count ? ` • ${doc.page_count} стр.` : ''}
                </p>
              </div>
            </div>
            <div className="shrink-0 flex items-center gap-2">
              <button
                onClick={() => downloadDoc(doc)}
                className="flex items-center gap-1.5 text-label-md font-label-md text-on-surface-variant bg-surface-container-high hover:bg-on-background hover:text-on-primary rounded-md px-2.5 py-1 transition-colors"
                title="Скачать файл"
              >
                <span className="material-symbols-outlined text-[16px]">download</span>
                Скачать
              </button>
              {doc.processing_status === 'ready' || doc.processing_status === 'completed' ? (
                <span className="flex items-center gap-1.5 text-label-md font-label-md text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-md px-2.5 py-1">
                  <span className="material-symbols-outlined text-[16px]">check_circle</span>
                  Обработан
                </span>
              ) : doc.processing_status === 'error' || doc.processing_status === 'failed' ? (
                <span className="flex items-center gap-1.5 text-label-md font-label-md text-red-700 bg-red-50 border border-red-200 rounded-md px-2.5 py-1" title={doc.error_message}>
                  <span className="material-symbols-outlined text-[16px]">error</span>
                  Ошибка
                </span>
              ) : (
                <span className="flex items-center gap-2 text-label-md font-label-md text-on-surface-variant">
                  <span className="material-symbols-outlined animate-spin text-[16px] text-primary">sync</span>
                  {STATUS_LABEL[doc.processing_status] ?? doc.processing_status}...
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      <InfoBanner>
        AI сопоставляет спецификацию с техническими требованиями, выявляет риски и недостающие документы. После
        обработки вы сможете перейти к анализу.
      </InfoBanner>

      {/* Next step */}
      {ready && (
        <div className="sticky bottom-4 flex justify-end">
          <Link
            href={`/projects/${projectId}/analysis`}
            className="flex items-center gap-2 px-5 py-2.5 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity shadow-lg"
          >
            Перейти к анализу
            <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
          </Link>
        </div>
      )}
    </div>
  );
}