import Link from 'next/link';

export function BrandMark({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" fill="none" aria-hidden="true" className={className}>
      <rect width="40" height="40" rx="12" fill="currentColor" />
      <path
        d="M11 11h11.4a5.6 5.6 0 0 1 3.5 10 5.3 5.3 0 0 1-3.5 9H11V11Z"
        fill="white"
        fillOpacity=".96"
      />
      <path
        d="M17 16h5.1a1.5 1.5 0 1 1 0 3H17v-3Zm0 8h5.1a1.5 1.5 0 1 1 0 3H17v-3Z"
        fill="currentColor"
      />
      <path d="m29 8 1.2 3.3L34 13l-3.8 1.7L29 18l-1.2-3.3L24 13l3.8-1.7L29 8Z" fill="#99C6FF" />
    </svg>
  );
}

export function Brand({
  inverse = false,
  compact = false,
  href = '/dashboard',
}: {
  inverse?: boolean;
  compact?: boolean;
  href?: string;
}) {
  return (
    <Link
      href={href}
      aria-label="BINOM AI — главная"
      className="inline-flex min-w-0 items-center gap-3"
    >
      <BrandMark className="h-10 w-10 shrink-0 text-[#3976ed]" />
      {!compact && (
        <span className="min-w-0">
          <span
            className={`block font-display text-[19px] font-extrabold tracking-[-0.045em] ${inverse ? 'text-white' : 'text-on-surface'}`}
          >
            BINOM<span className={inverse ? 'text-[#9abaff]' : 'text-primary'}> AI</span>
          </span>
          <span
              className={`block whitespace-nowrap text-[9px] font-medium tracking-[0.09em] uppercase ${inverse ? 'text-slate-400' : 'text-on-surface-variant'}`}
          >
            Управление закупками
          </span>
        </span>
      )}
    </Link>
  );
}
