'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { api, errorMessage } from '@/lib/api';
import { Brand } from '@/components/Brand';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetEmail, setResetEmail] = useState('');
  const [resetSent, setResetSent] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetError, setResetError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const resetDialogRef = useRef<HTMLDialogElement>(null);
  const { login } = useAuth();

  useEffect(() => {
    if (!resetOpen) return;
    const dialog = resetDialogRef.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, [resetOpen]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await api.post('/auth/login', { email: email.trim(), password });
      if (!response.access_token || !response.refresh_token)
        throw new Error('Сервер не подтвердил вход. Повторите попытку.');
      login(response.access_token, response.refresh_token, response.user);
      router.push('/dashboard');
      router.refresh();
    } catch (err) {
      setError(errorMessage(err, 'Не удалось войти'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setResetLoading(true);
    setResetError('');
    try {
      await api.post('/auth/forgot-password', { email: resetEmail.trim() });
      setResetSent(true);
    } catch (err) {
      setResetError(errorMessage(err, 'Не удалось отправить запрос. Повторите попытку.'));
    } finally {
      setResetLoading(false);
    }
  };

  return (
    <div className="theme-tenderpro grid min-h-screen w-full bg-background lg:grid-cols-[1fr_1fr]">
      <aside className="relative hidden min-h-screen flex-col overflow-hidden bg-[#101c32] px-10 py-8 text-white lg:flex xl:px-12">
        <div className="relative z-10">
          <Brand inverse href="/" />
        </div>
        <div
          className="pointer-events-none absolute -right-32 top-1/4 h-[500px] w-[500px] rounded-full bg-[#2e65ce]/10 blur-3xl"
          aria-hidden="true"
        />
        <div className="relative z-10 my-auto max-w-lg py-8">
          <span className="inline-flex items-center gap-2 rounded-full border border-[#8ab4ff]/20 bg-[#8ab4ff]/5 px-3 py-1.5 text-[11px] font-semibold tracking-wide text-[#a9c8ff]">
            <span className="material-symbols-outlined text-[15px]" aria-hidden="true">
              auto_awesome
            </span>
            Рабочее пространство закупщика
          </span>
          <h2 className="mt-5 font-display text-[38px] font-bold leading-[1.15] tracking-[-0.045em] 2xl:text-[48px]">
            Все решения по тендеру.
            <br />
            <span className="text-[#99baff]">В одном месте.</span>
          </h2>
          <p className="mt-4 max-w-md text-sm leading-6 text-slate-400">
            Превращайте техническое задание в понятный план: товары, предложения поставщиков,
            расчёты и документы для заявки.
          </p>
          <div className="mt-6 space-y-3">
            {[
              {
                number: '01',
                icon: 'description',
                title: 'Загрузите техническое задание',
                detail: 'PDF, скан или документ Word',
              },
              {
                number: '02',
                icon: 'travel_explore',
                title: 'Сопоставьте товары и предложения',
                detail: 'Характеристики, источники и контакты',
              },
              {
                number: '03',
                icon: 'calculate',
                title: 'Оцените экономику проекта',
                detail: 'Закупка, расходы и плановая маржа',
              },
            ].map((step) => (
              <div
                key={step.number}
                className="flex items-center gap-4 rounded-2xl border border-white/[0.07] bg-white/[0.035] p-4"
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#83abff]/10 text-[#a8c7ff]">
                  <span className="material-symbols-outlined text-[21px]" aria-hidden="true">
                    {step.icon}
                  </span>
                </span>
                <div>
                  <p className="text-xs font-semibold text-slate-100">{step.title}</p>
                  <p className="mt-1.5 text-[11px] text-slate-400">{step.detail}</p>
                </div>
                <span className="ml-auto font-mono-sm text-[11px] text-slate-600">
                  {step.number}
                </span>
              </div>
            ))}
          </div>
        </div>
        <p className="relative z-10 text-[11px] text-slate-500">
          BINOM AI · Для команд, которые участвуют в закупках
        </p>
      </aside>
      <main className="flex min-h-screen flex-col items-center justify-center px-5 py-10 sm:px-10">
        <div className="mb-10 lg:hidden">
          <Brand href="/" />
        </div>
        <div className="w-full max-w-[400px]">
          <div className="mb-8">
            <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
              С возвращением
            </p>
            <h1 className="mb-3 font-display text-[32px] font-bold tracking-[-0.04em] text-on-surface">
              Вход в рабочую область
            </h1>
            <p className="text-sm leading-6 text-on-surface-variant">
              Продолжите работу с тендерами и документами вашей компании.
            </p>
          </div>

          {error && (
            <div
              role="alert"
              className="mb-6 p-4 bg-error-container text-on-error-container rounded-xl text-body-sm font-body-md"
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label
                className="block text-label-md font-label-md text-on-surface"
                htmlFor="login-email"
              >
                Email
              </label>
              <input
                id="login-email"
                type="email"
                autoComplete="username"
                required
                className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
                placeholder="you@company.kz"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <label
                className="block text-label-md font-label-md text-on-surface"
                htmlFor="login-password"
              >
                Пароль
              </label>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  className="w-full pl-4 pr-12 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                  aria-pressed={showPassword}
                  className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-lg text-on-surface-variant hover:text-primary"
                >
                  <span className="material-symbols-outlined text-[20px]" aria-hidden="true">
                    {showPassword ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>
            </div>

            <div className="flex items-center justify-end">
              <button
                type="button"
                onClick={() => setResetOpen(true)}
                className="text-label-md font-label-md text-primary hover:underline"
              >
                Забыли пароль?
              </button>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 bg-primary text-on-primary rounded-xl text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>
                  Вход...
                </>
              ) : (
                <>
                  Войти в BINOM AI
                  <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
                    arrow_forward
                  </span>
                </>
              )}
            </button>
          </form>

          <p className="text-center text-body-md font-body-md text-on-surface-variant mt-6">
            Нет аккаунта?{' '}
            <Link href="/register" className="text-primary font-medium hover:underline">
              Зарегистрироваться →
            </Link>
          </p>
          <Link
            href="/"
            className="mt-10 flex items-center justify-center gap-1.5 text-xs text-on-surface-variant hover:text-primary"
          >
            <span className="material-symbols-outlined text-[14px]" aria-hidden="true">
              arrow_back
            </span>
            О платформе BINOM AI
          </Link>
        </div>
      </main>

      {/* Reset password modal */}
      {resetOpen && (
        <dialog
          ref={resetDialogRef}
          aria-labelledby="reset-heading"
          onCancel={() => setResetOpen(false)}
          className="fixed m-auto max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-md overflow-y-auto rounded-2xl border border-outline-variant bg-surface-bright p-0 text-on-surface shadow-2xl backdrop:bg-slate-950/45 backdrop:backdrop-blur-sm"
          onMouseDown={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) setResetOpen(false);
          }}
        >
          <div
            className="w-full max-w-md bg-surface-bright rounded-2xl shadow-xl border border-outline-variant overflow-hidden"
          >
            <div className="px-6 pt-5 pb-4">
              <div className="flex items-start justify-between mb-3">
                <h2
                  id="reset-heading"
                  className="text-headline-md font-headline-md text-on-surface"
                >
                  Сброс пароля
                </h2>
                <button
                  onClick={() => setResetOpen(false)}
                  className="text-on-surface-variant hover:text-on-surface transition-colors"
                  aria-label="Закрыть"
                >
                  <span className="material-symbols-outlined">close</span>
                </button>
              </div>
              {resetSent ? (
                <div className="py-6 text-center">
                  <span className="material-symbols-outlined text-4xl text-primary mb-3">
                    mark_email_read
                  </span>
                  <p className="text-body-md font-body-md text-on-surface-variant max-w-sm mx-auto">
                    Если аккаунт с этим email существует, мы отправили на него инструкции по
                    восстановлению доступа.
                  </p>
                </div>
              ) : (
                <form onSubmit={handleResetSubmit} className="space-y-4">
                  <p className="text-body-md font-body-md text-on-surface-variant">
                    Укажите email, привязанный к аккаунту, — мы отправим инструкцию по сбросу
                    пароля.
                  </p>
                  <input
                    type="email"
                    aria-label="Email для восстановления"
                    autoComplete="email"
                    required
                    className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
                    placeholder="you@company.kz"
                    value={resetEmail}
                    onChange={(e) => setResetEmail(e.target.value)}
                  />
                  {resetError && (
                    <p
                      role="alert"
                      className="rounded-lg bg-error-container p-3 text-xs text-on-error-container"
                    >
                      {resetError}
                    </p>
                  )}
                  <button
                    type="submit"
                    disabled={resetLoading}
                    className="w-full py-2.5 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {resetLoading && (
                      <span className="material-symbols-outlined animate-spin text-[18px]">
                        sync
                      </span>
                    )}
                    Отправить инструкцию
                  </button>
                </form>
              )}
            </div>
            {resetSent && (
              <div className="flex justify-end px-6 py-4 bg-surface-container-low border-t border-outline-variant/60">
                <button
                  onClick={() => {
                    setResetOpen(false);
                    setResetSent(false);
                    setResetEmail('');
                  }}
                  className="px-4 py-2 bg-surface-bright border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface-variant hover:bg-surface-container transition-colors"
                >
                  Понятно
                </button>
              </div>
            )}
          </div>
        </dialog>
      )}
    </div>
  );
}
