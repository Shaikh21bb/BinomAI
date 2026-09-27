'use client';

import Link from 'next/link';

interface ErrorPageProps {
  error: Error & { digest?: string };
  retry: () => void;
}

export default function ErrorPage({ error, retry }: ErrorPageProps) {
  return (
    <main className="flex min-h-[70vh] items-center justify-center bg-background px-4 py-12">
      <section
        aria-labelledby="page-error-title"
        className="w-full max-w-xl rounded-2xl border border-outline-variant bg-surface-container-lowest p-6 text-center shadow-sm md:p-10"
      >
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-error-container text-on-error-container">
          <span className="material-symbols-outlined text-[30px]" aria-hidden="true">error</span>
        </div>
        <p className="mt-5 text-label-md font-label-md uppercase tracking-[0.12em] text-error">Ошибка страницы</p>
        <h1 id="page-error-title" className="mt-2 text-headline-lg font-headline-lg text-on-surface">
          Не удалось показать этот раздел
        </h1>
        <p className="mx-auto mt-3 max-w-md text-body-md text-on-surface-variant">
          Возможно, произошёл временный сбой. Повторите загрузку — сохранённые данные останутся на месте.
        </p>
        {error.digest ? (
          <p className="mt-3 text-label-sm text-on-surface-variant">
            Код обращения: <span className="font-mono">{error.digest}</span>
          </p>
        ) : null}
        <div className="mt-7 flex flex-col justify-center gap-2 sm:flex-row">
          <button
            type="button"
            onClick={retry}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-on-background px-5 py-2.5 text-label-md font-label-md text-on-primary hover:opacity-90"
          >
            <span className="material-symbols-outlined text-[18px]" aria-hidden="true">refresh</span>
            Повторить
          </button>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-outline-variant px-5 py-2.5 text-label-md font-label-md text-on-surface hover:border-primary hover:text-primary"
          >
            К тендерам
          </Link>
        </div>
      </section>
    </main>
  );
}
