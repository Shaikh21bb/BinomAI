export default function Loading() {
  return (
    <main
      className="flex min-h-screen items-center justify-center bg-background px-4"
      aria-busy="true"
      aria-label="Загрузка страницы"
    >
      <div className="w-full max-w-xl rounded-2xl border border-outline-variant bg-surface-container-lowest p-6 shadow-sm md:p-8">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 animate-pulse rounded-xl bg-primary/15" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-32 animate-pulse rounded bg-surface-container-highest" />
            <div className="h-3 w-52 max-w-full animate-pulse rounded bg-surface-container-high" />
          </div>
        </div>
        <div className="mt-7 space-y-3">
          <div className="h-20 animate-pulse rounded-xl bg-surface-container-low" />
          <div className="h-20 animate-pulse rounded-xl bg-surface-container-low" />
          <div className="h-20 animate-pulse rounded-xl bg-surface-container-low" />
        </div>
        <p className="sr-only" role="status">Загружаем страницу…</p>
      </div>
    </main>
  );
}
