'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

function Reveal({
  children,
  delay = 0,
  className = '',
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { threshold: 0.08 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`transition-all duration-700 ease-out will-change-transform ${className} ${
        visible ? 'reveal-visible' : 'reveal-init'
      }`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}

function SlideButton({
  href,
  children,
  primary = false,
  className = '',
}: {
  href: string;
  children: React.ReactNode;
  primary?: boolean;
  className?: string;
}) {
  return (
    <Link
      href={href}
      className={`group relative overflow-hidden rounded-full text-[15px] font-medium transition-all duration-300 ${
        primary
          ? 'bg-[#0071e3] text-white hover:scale-[1.03] hover:shadow-[0_10px_30px_-10px_rgba(0,113,227,0.6)]'
          : 'bg-white/70 text-[#1d1d1f] border border-black/10 backdrop-blur-xl hover:bg-white'
      } ${className}`}
    >
      <span
        className={`absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-700 ${
          primary ? 'bg-gradient-to-r from-transparent via-white/25 to-transparent' : 'bg-black/5'
        }`}
      />
      <span className="relative flex items-center justify-center gap-2 px-8 py-3">
        {children}
        <span className="material-symbols-outlined text-[18px] transition-transform duration-300 group-hover:translate-x-1">
          arrow_forward
        </span>
      </span>
    </Link>
  );
}

const GLASS = 'bg-white/70 backdrop-blur-2xl border border-white/60 shadow-[0_8px_40px_-20px_rgba(0,0,0,0.25)]';

const FEATURES = [
  {
    icon: 'description',
    title: 'Автоматический разбор ТЗ',
    text: 'PDF и DOCX тендерной документации превращаются в структуру: реквизиты, требования, предмет закупки.',
  },
  {
    icon: 'insights',
    title: 'Анализ за несколько секунд',
    text: 'Сроки, коммерческие условия, риски и недостающие данные — всё выделено и готово к проверке.',
  },
  {
    icon: 'chat_bubble',
    title: 'Уточняющие вопросы',
    text: 'Ассистент спрашивает только то, чего не хватает: опыт, цену, сроки, лицензии.',
  },
  {
    icon: 'document_scanner',
    title: 'Готовые документы',
    text: 'КП, ТЗ и сопроводительное письмо формируются на русском и казахском.',
  },
  {
    icon: 'trending_up',
    title: 'Обоснованная цена',
    text: 'Ориентир рыночной стоимости для коммерческого предложения.',
  },
  {
    icon: 'download',
    title: 'Экспорт в DOCX и PDF',
    text: 'Готовые файлы в один клик, история версий сохраняется.',
  },
];

const STEPS = [
  { n: '01', title: 'Создайте тендер', text: 'Название, заказчик, дедлайн — рабочее пространство компании готово.' },
  { n: '02', title: 'Загрузите документацию', text: 'ТЗ разбирается автоматически: реквизиты, требования, предмет закупки.' },
  { n: '03', title: 'Проверьте анализ', text: 'Сроки, риски и список недостающих данных. Уточняющие вопросы — по делу.' },
  { n: '04', title: 'Скачайте пакет заявки', text: 'КП и ТЗ на двух языках. Экспорт в DOCX или PDF — в один клик.' },
];

const PLANS = [
  {
    key: 'trial',
    name: 'Пробный',
    price: '0 ₸',
    period: '',
    features: ['2 активных проекта', '3 пользователя', '20 документов', 'Анализ и генерация документов'],
    featured: false,
  },
  {
    key: 'pro',
    name: 'Про',
    price: '149 000 ₸',
    period: '/месяц',
    features: ['50 активных проектов', '50 пользователей', 'Документы без лимита', 'Анализ и генерация документов', 'Приоритетная поддержка'],
    featured: true,
  },
  {
    key: 'enterprise',
    name: 'Enterprise',
    price: 'По запросу',
    period: '',
    features: ['Без лимитов', 'Интеграция с вашими системами', 'Персональный менеджер', 'SLA и обучение команды'],
    featured: false,
  },
];

export default function LandingPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    if (user) {
      router.replace('/dashboard');
    }
  }, [user, router]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div className="w-full min-h-screen bg-[#f5f5f7] text-[#1d1d1f] theme-tenderpro antialiased overflow-x-hidden">
      {/* Dynamic Island header */}
      <header
        className={`fixed top-3 md:top-5 left-1/2 -translate-x-1/2 z-40 transition-all duration-300 ${
          scrolled
            ? 'shadow-[0_16px_50px_-20px_rgba(0,0,0,0.35)]'
            : 'shadow-[0_8px_30px_-18px_rgba(0,0,0,0.2)]'
        }`}
      >
        <div className="flex items-center gap-1.5 md:gap-2 rounded-full bg-white/70 backdrop-blur-2xl border border-white/70 px-2.5 md:px-3 py-2">
          {/* Logo island */}
          <a
            href="#top"
            className="flex items-center gap-1.5 pl-3 pr-3.5 rounded-full bg-white/0 hover:bg-white transition-colors"
          >
            <span className="text-[13px] font-semibold tracking-tight">
              BINOM <span className="text-[#0a84ff]">AI</span>
            </span>
          </a>

          {/* Nav islands */}
          <nav className="hidden md:flex items-center gap-1">
            {[
              ['#features', 'Возможности'],
              ['#how', 'Как работает'],
              ['#pricing', 'Тарифы'],
            ].map(([href, label]) => (
              <a
                key={href}
                href={href}
                className="rounded-full px-4 py-2 text-[13px] font-medium text-[#424245] bg-transparent hover:bg-white hover:text-[#1d1d1f] hover:shadow-[0_4px_20px_-8px_rgba(0,0,0,0.25)] transition-all"
              >
                {label}
              </a>
            ))}
          </nav>

          {/* Action islands */}
          <div className="flex items-center gap-1.5 md:gap-2 pl-0.5 md:pl-0">
            <Link
              href="/login"
              className="hidden sm:block rounded-full px-4 py-2 text-[13px] font-medium text-[#424245] bg-transparent hover:bg-white hover:text-[#1d1d1f] hover:shadow-[0_4px_20px_-8px_rgba(0,0,0,0.25)] transition-all"
            >
              Войти
            </Link>
            <Link
              href="/register"
              className="group relative overflow-hidden rounded-full bg-[#0071e3] text-white text-[13px] font-medium hover:bg-[#0077ed] hover:shadow-[0_6px_24px_-8px_rgba(0,113,227,0.7)] transition-all"
            >
              <span className="absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-700 bg-gradient-to-r from-transparent via-white/25 to-transparent" />
              <span className="relative block px-5 py-2">Начать</span>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section id="top" className="relative pt-36 md:pt-44 pb-16 md:pb-24">
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
          <div className="absolute -top-20 left-[8%] w-[420px] h-[420px] rounded-full bg-[#a8c8ff]/50 blur-[110px]" />
          <div className="absolute top-10 right-[5%] w-[380px] h-[380px] rounded-full bg-[#e3d0ff]/50 blur-[110px]" />
          <div className="absolute bottom-0 left-1/3 w-[400px] h-[300px] rounded-full bg-[#bfe3ff]/40 blur-[110px]" />
        </div>

        <div className="relative max-w-6xl mx-auto px-4 md:px-6 text-center">
          <Reveal>
            <p className="text-[14px] font-medium text-[#6e6e73]">
              Платформа для участников государственных и коммерческих закупок
            </p>
          </Reveal>
          <Reveal delay={80}>
            <h1 className="mt-5 mx-auto max-w-4xl text-[42px] leading-[1.05] md:text-[68px] md:leading-[1.02] font-bold tracking-[-0.03em]">
              Подготовка заявки.
              <br />
              <span className="text-[#6e6e73]">За минуты, а не дни.</span>
            </h1>
          </Reveal>
          <Reveal delay={160}>
            <p className="mt-6 mx-auto max-w-2xl text-[17px] md:text-[19px] leading-relaxed text-[#424245]">
              BINOM AI разбирает тендерную документацию, собирает недостающие данные
              и готовит коммерческое предложение с техническим заданием — на русском и казахском.
            </p>
          </Reveal>
          <Reveal delay={240}>
            <div className="mt-9 flex flex-col sm:flex-row items-center justify-center gap-3">
              <SlideButton href="/register" primary>
                Начать бесплатно
              </SlideButton>
              <a
                href="#how"
                className="group relative overflow-hidden rounded-full bg-white/70 text-[#1d1d1f] border border-black/10 backdrop-blur-xl text-[15px] font-medium hover:bg-white transition-colors"
              >
                <span className="absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-700 bg-black/5" />
                <span className="relative flex items-center justify-center gap-2 px-8 py-3">
                  Как это работает
                  <span className="material-symbols-outlined text-[18px] transition-transform duration-300 group-hover:translate-y-0.5">
                    expand_more
                  </span>
                </span>
              </a>
            </div>
            <p className="mt-4 text-[12px] text-[#86868b]">Бесплатный тариф. Без карты. Без обязательств.</p>
          </Reveal>
        </div>

        {/* Glass product mockup */}
        <Reveal delay={320}>
          <div className="mt-16 md:mt-20 max-w-5xl mx-auto px-4 md:px-6">
            <div className={`${GLASS} rounded-3xl overflow-hidden`}>
              <div className="flex items-center gap-1.5 px-4 py-3 border-b border-white/60 bg-white/50">
                <span className="w-3 h-3 rounded-full bg-[#ff5f57]" />
                <span className="w-3 h-3 rounded-full bg-[#febc2e]" />
                <span className="w-3 h-3 rounded-full bg-[#28c840]" />
              </div>
              <div className="grid grid-cols-[64px_1fr] md:grid-cols-[220px_1fr]">
                <div className="hidden md:flex flex-col gap-1 p-4 border-r border-white/60 bg-white/30">
                  {['dashboard', 'description', 'forum', 'tune'].map((icon, i) => (
                    <div
                      key={icon}
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-[12px] ${
                        i === 1 ? 'bg-[#0071e3]/10 text-[#0071e3]' : 'text-[#86868b]'
                      }`}
                    >
                      <span className="material-symbols-outlined text-[16px]">{icon}</span>
                      {['Обзор', 'Тендеры', 'Чат', 'Настройки'][i]}
                    </div>
                  ))}
                </div>
                <div className="p-4 md:p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <div className="h-3 w-28 rounded bg-black/10" />
                      <div className="h-2 w-40 rounded bg-black/5 mt-1.5" />
                    </div>
                    <div className="h-7 w-24 rounded-full bg-[#0071e3]" />
                  </div>
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    {[72, 48, 96].map((w, i) => (
                      <div key={i} className="rounded-xl bg-white/60 border border-white/60 p-3">
                        <div className="h-2 w-12 rounded bg-black/20" />
                        <div className="h-4 rounded bg-black/10 mt-2" style={{ width: `${w}%` }} />
                      </div>
                    ))}
                  </div>
                  <div className="space-y-2.5">
                    {[
                      ['Тендер: Поставка медоборудования', true],
                      ['Тендер: Строительство склада', false],
                      ['Тендер: IT-оборудование', false],
                    ].map(([t, active]) => (
                      <div
                        key={t as string}
                        className={`flex items-center justify-between rounded-xl border p-3 ${
                          active ? 'border-[#0071e3]/40 bg-[#0071e3]/5' : 'border-black/5 bg-white/50'
                        }`}
                      >
                        <div>
                          <div className="h-2.5 w-52 max-w-[60vw] rounded bg-black/15" />
                          <div className="h-2 w-32 rounded bg-black/5 mt-1.5" />
                        </div>
                        <div className={`h-2 w-14 rounded ${active ? 'bg-[#0071e3]/60' : 'bg-black/10'}`} />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      {/* Stats */}
      <section className="relative">
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
          <div className="absolute -top-24 right-[15%] w-[340px] h-[340px] rounded-full bg-[#cde3ff]/50 blur-[100px]" />
        </div>
        <Reveal>
          <div className="relative max-w-6xl mx-auto px-4 md:px-6 py-12">
            <div className={`${GLASS} rounded-3xl grid grid-cols-2 md:grid-cols-4 gap-8 px-6 py-10 md:py-12 text-center`}>
              {[
                ['минуты', 'от ТЗ до черновика КП'],
                ['2 языка', 'русский и казахский'],
                ['100%', 'документы под вашу заявку'],
                ['24/7', 'ассистент в рабочем пространстве'],
              ].map(([stat, label]) => (
                <div key={stat}>
                  <p className="text-[30px] md:text-[36px] font-bold tracking-tight">{stat}</p>
                  <p className="mt-1 text-[13px] text-[#6e6e73]">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </section>

      {/* Features */}
      <section id="features" className="relative py-20 md:py-28">
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
          <div className="absolute top-1/4 left-0 w-[380px] h-[380px] rounded-full bg-[#ffd9e8]/40 blur-[110px]" />
          <div className="absolute bottom-10 right-0 w-[380px] h-[380px] rounded-full bg-[#c9e6ff]/50 blur-[110px]" />
        </div>
        <div className="relative max-w-6xl mx-auto px-4 md:px-6">
          <Reveal>
            <div className="text-center max-w-2xl mx-auto">
              <h2 className="text-[30px] md:text-[44px] font-bold tracking-[-0.02em] leading-tight">
                Всё, что нужно для заявки.
              </h2>
              <p className="mt-4 text-[16px] md:text-[18px] text-[#6e6e73]">
                От тендерной документации до готового пакета документов — в одном рабочем пространстве.
              </p>
            </div>
          </Reveal>
          <div className="mt-14 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={(i % 3) * 90}>
                <div
                  className={`${GLASS} h-full rounded-3xl p-8 transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_20px_50px_-20px_rgba(0,0,0,0.3)]`}
                >
                  <div className="w-12 h-12 rounded-2xl bg-[#0071e3]/10 text-[#0071e3] flex items-center justify-center">
                    <span className="material-symbols-outlined text-[24px]">{f.icon}</span>
                  </div>
                  <h3 className="mt-5 text-[19px] font-semibold tracking-tight">{f.title}</h3>
                  <p className="mt-2.5 text-[14.5px] leading-relaxed text-[#6e6e73]">{f.text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="relative py-20 md:py-28">
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
          <div className="absolute top-0 left-1/4 w-[400px] h-[400px] rounded-full bg-[#cfe6ff]/45 blur-[110px]" />
          <div className="absolute bottom-0 right-1/4 w-[400px] h-[300px] rounded-full bg-[#efd9ff]/40 blur-[110px]" />
        </div>
        <div className="relative max-w-6xl mx-auto px-4 md:px-6">
          <Reveal>
            <div className="text-center max-w-2xl mx-auto">
              <h2 className="text-[30px] md:text-[44px] font-bold tracking-[-0.02em] leading-tight">
                Четыре шага до заявки.
              </h2>
              <p className="mt-4 text-[16px] md:text-[18px] text-[#6e6e73]">
                Никакой рутины: систему не нужно учить, она работает сразу после регистрации.
              </p>
            </div>
          </Reveal>
          <div className="mt-14 grid grid-cols-1 md:grid-cols-4 gap-4">
            {STEPS.map((s, i) => (
              <Reveal key={s.n} delay={i * 100}>
                <div className={`${GLASS} relative h-full rounded-3xl p-7`}>
                  <p className="text-[14px] font-bold text-[#0071e3] tabular-nums">{s.n}</p>
                  <h3 className="mt-3 text-[19px] font-semibold tracking-tight">{s.title}</h3>
                  <p className="mt-2 text-[14px] leading-relaxed text-[#6e6e73]">{s.text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="relative py-20 md:py-28">
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
          <div className="absolute top-10 left-[10%] w-[360px] h-[360px] rounded-full bg-[#ffd9c7]/40 blur-[110px]" />
          <div className="absolute bottom-10 right-[10%] w-[360px] h-[360px] rounded-full bg-[#c9e6ff]/45 blur-[110px]" />
        </div>
        <div className="relative max-w-6xl mx-auto px-4 md:px-6">
          <Reveal>
            <div className="text-center max-w-2xl mx-auto">
              <h2 className="text-[30px] md:text-[44px] font-bold tracking-[-0.02em] leading-tight">
                Простые тарифы.
              </h2>
              <p className="mt-4 text-[16px] md:text-[18px] text-[#6e6e73]">
                Начните бесплатно, растите вместе с компанией.
              </p>
            </div>
          </Reveal>
          <div className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-4">
            {PLANS.map((p, i) => (
              <Reveal key={p.key} delay={i * 100}>
                <div
                  className={`h-full rounded-3xl p-8 flex flex-col transition-all duration-300 hover:-translate-y-1 ${
                    p.featured
                      ? 'bg-[#1d1d1f] text-white shadow-[0_30px_60px_-20px_rgba(0,0,0,0.5)]'
                      : `${GLASS} hover:shadow-[0_20px_50px_-20px_rgba(0,0,0,0.3)]`
                  }`}
                >
                  {p.featured && (
                    <span className="self-start px-2.5 py-1 rounded-full bg-[#0071e3] text-white text-[11px] font-semibold mb-4">
                      Популярный
                    </span>
                  )}
                  <h3 className={`text-[17px] font-semibold ${p.featured ? 'text-white' : 'text-[#1d1d1f]'}`}>{p.name}</h3>
                  <div className="mt-3 flex items-baseline gap-1">
                    <span className="text-[32px] font-bold tracking-tight">{p.price}</span>
                    {p.period && (
                      <span className={`text-[13px] ${p.featured ? 'text-white/60' : 'text-[#86868b]'}`}>{p.period}</span>
                    )}
                  </div>
                  <ul className="mt-6 space-y-3 flex-1">
                    {p.features.map((f) => (
                      <li key={f} className="flex items-start gap-2.5 text-[14px]">
                        <span className="material-symbols-outlined text-[16px] mt-px text-[#0071e3]">check</span>
                        <span className={p.featured ? 'text-white/85' : 'text-[#424245]'}>{f}</span>
                      </li>
                    ))}
                  </ul>
                  <Link
                    href="/register"
                    className={`group mt-8 relative overflow-hidden rounded-full py-2.5 text-center text-[14px] font-medium transition-all ${
                      p.featured
                        ? 'bg-[#0071e3] text-white hover:bg-[#0077ed]'
                        : 'bg-black/5 text-[#1d1d1f] hover:bg-black/10'
                    }`}
                  >
                    <span className="absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-700 bg-gradient-to-r from-transparent via-white/20 to-transparent" />
                    <span className="relative">Выбрать тариф</span>
                  </Link>
                </div>
              </Reveal>
            ))}
          </div>
          <Reveal delay={200}>
            <p className="mt-8 text-center text-[13px] text-[#86868b]">
              Нужен другой набор опций? Напишите нам —{' '}
              <a href="mailto:sales@binom.ai" className="text-[#0071e3] hover:underline">
                sales@binom.ai
              </a>
            </p>
          </Reveal>
        </div>
      </section>

      {/* CTA */}
      <section className="relative pb-20 md:pb-28">
        <div className="pointer-events-none absolute inset-x-0 bottom-0 overflow-hidden" aria-hidden>
          <div className="absolute bottom-[-10%] left-1/2 -translate-x-1/2 w-[600px] h-[300px] rounded-full bg-[#0071e3]/15 blur-[120px]" />
        </div>
        <div className="relative max-w-6xl mx-auto px-4 md:px-6">
          <Reveal>
            <div className="rounded-3xl bg-[#1d1d1f]/85 backdrop-blur-2xl border border-white/10 text-white px-6 py-16 md:py-20 text-center">
              <h2 className="max-w-2xl mx-auto text-[30px] md:text-[44px] font-bold tracking-[-0.02em] leading-tight">
                Первая заявка уже сегодня.
              </h2>
              <p className="max-w-xl mx-auto mt-4 text-[16px] md:text-[18px] text-white/60">
                Регистрация занимает две минуты. Загрузите первое техническое задание и посмотрите,
                как меняется подготовка документов.
              </p>
              <div className="flex justify-center mt-9">
                <SlideButton href="/register" primary>
                  Зарегистрироваться
                </SlideButton>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative">
        <div className="max-w-6xl mx-auto px-4 md:px-6 py-12 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-baseline gap-1 text-[15px] font-semibold tracking-tight">
            <span>BINOM</span>
            <span className="text-[#0071e3] font-bold">AI</span>
          </div>
          <p className="text-[12px] text-[#86868b]">
            © {new Date().getFullYear()} BINOM AI. Платформа для участников закупок.
          </p>
          <div className="flex items-center gap-6 text-[12px] text-[#86868b]">
            <a href="mailto:sales@binom.ai" className="hover:text-[#1d1d1f] transition-colors">
              sales@binom.ai
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
