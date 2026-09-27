import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Страница не найдена — BINOM AI',
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <section className="w-full max-w-xl rounded-2xl border border-outline-variant bg-surface-container-lowest p-6 text-center shadow-sm md:p-10">
        <p className="text-display font-display text-primary" aria-hidden="true">404</p>
        <h1 className="mt-2 text-headline-lg font-headline-lg text-on-surface">Страница не найдена</h1>
        <p className="mx-auto mt-3 max-w-md text-body-md text-on-surface-variant">
          Возможно, адрес изменился или ссылка устарела. Вернитесь в рабочее пространство и продолжите работу.
        </p>
        <div className="mt-7 flex flex-col justify-center gap-2 sm:flex-row">
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-on-background px-5 py-2.5 text-label-md font-label-md text-on-primary hover:opacity-90"
          >
            <span className="material-symbols-outlined text-[18px]" aria-hidden="true">work</span>
            К тендерам
          </Link>
          <Link
            href="/"
            className="inline-flex items-center justify-center rounded-lg border border-outline-variant px-5 py-2.5 text-label-md font-label-md text-on-surface hover:border-primary hover:text-primary"
          >
            На главную
          </Link>
        </div>
      </section>
    </main>
  );
}
