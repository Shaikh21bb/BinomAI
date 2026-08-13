'use client';

import { FormEvent, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { api, errorMessage } from '@/lib/api';

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
  const { login } = useAuth();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await api.post('/auth/login', { email, password });
      login(response.access_token ?? '', response.refresh_token, response.user);
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
    try {
      await api.post('/auth/forgot-password', { email: resetEmail });
    } catch {
      // safe fallback: never reveal whether the account exists
    } finally {
      setResetLoading(false);
      setResetSent(true);
    }
  };

  return (
    <div className="flex h-screen w-full items-center justify-center bg-surface px-4 theme-tenderpro">
      <div className="w-full max-w-md p-8 bg-surface-container-lowest border border-outline-variant rounded-2xl shadow-sm">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-on-background text-on-primary flex items-center justify-center mx-auto mb-4">
            <span className="material-symbols-outlined text-[24px]" style={{ fontVariationSettings: "'FILL' 1" }}>
              assistant
            </span>
          </div>
          <h1 className="text-headline-lg font-headline-lg text-on-surface mb-2">Войти в BINOM AI</h1>
          <p className="text-body-md font-body-md text-on-surface-variant">Войдите, чтобы продолжить работу</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-error-container text-on-error-container rounded-lg text-body-sm font-body-md">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="block text-label-md font-label-md text-on-surface" htmlFor="login-email">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              required
              className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
              placeholder="you@company.kz"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <label className="block text-label-md font-label-md text-on-surface" htmlFor="login-password">
              Пароль
            </label>
            <input
              id="login-password"
              type="password"
              required
              className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 cursor-pointer text-body-md font-body-md text-on-surface-variant">
              <input
                type="checkbox"
                defaultChecked
                className="w-4 h-4 rounded text-primary focus:ring-primary/30"
              />
              Запомнить меня
            </label>
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
            className="w-full py-2.5 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>
                Вход...
              </>
            ) : (
              'Войти'
            )}
          </button>
        </form>

        <p className="text-center text-body-md font-body-md text-on-surface-variant mt-6">
          Нет аккаунта?{' '}
          <Link href="/register" className="text-primary font-medium hover:underline">
            Зарегистрироваться →
          </Link>
        </p>
      </div>

      {/* Reset password modal */}
      {resetOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setResetOpen(false);
          }}
        >
          <div className="w-full max-w-md bg-surface-bright rounded-2xl shadow-xl border border-outline-variant overflow-hidden">
            <div className="px-6 pt-5 pb-4">
              <div className="flex items-start justify-between mb-3">
                <h2 className="text-headline-md font-headline-md text-on-surface">Сброс пароля</h2>
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
                  <span className="material-symbols-outlined text-4xl text-primary mb-3">mark_email_read</span>
                  <p className="text-body-md font-body-md text-on-surface-variant max-w-sm mx-auto">
                    Если аккаунт с этим email существует, мы отправили на него инструкции по восстановлению доступа.
                  </p>
                </div>
              ) : (
                <form onSubmit={handleResetSubmit} className="space-y-4">
                  <p className="text-body-md font-body-md text-on-surface-variant">
                    Укажите email, привязанный к аккаунту, — мы отправим инструкцию по сбросу пароля.
                  </p>
                  <input
                    type="email"
                    required
                    className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
                    placeholder="you@company.kz"
                    value={resetEmail}
                    onChange={(e) => setResetEmail(e.target.value)}
                  />
                  <button
                    type="submit"
                    disabled={resetLoading}
                    className="w-full py-2.5 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {resetLoading && <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>}
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
        </div>
      )}
    </div>
  );
}