'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { api, errorMessage } from '@/lib/api';

export default function ResetPasswordPage() {
  const [accessToken, setAccessToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const id = setTimeout(() => {
      const fromHash = new URLSearchParams(window.location.hash.slice(1));
      const fromQuery = new URLSearchParams(window.location.search);
      const token =
        fromHash.get('access_token') ?? fromQuery.get('access_token') ?? '';
      if (token) {
        setAccessToken(token);
        window.history.replaceState(null, '', '/reset-password');
      } else {
        setError('Ссылка для сброса пароля недействительна или истекла.');
      }
    }, 0);
    return () => clearTimeout(id);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Пароль должен содержать минимум 8 символов');
      return;
    }
    if (!/[A-ZА-ЯЁ]/.test(password)) {
      setError('Пароль должен содержать минимум одну заглавную букву');
      return;
    }
    if (!/\d/.test(password)) {
      setError('Пароль должен содержать минимум одну цифру');
      return;
    }
    if (password !== confirmPassword) {
      setError('Пароли не совпадают');
      return;
    }

    setIsLoading(true);
    try {
      await api.post('/auth/reset-password', {
        access_token: accessToken,
        new_password: password,
      });
      setDone(true);
    } catch (err) {
      setError(errorMessage(err, 'Не удалось сбросить пароль'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full items-center justify-center bg-surface px-4 theme-tenderpro">
      <div className="w-full max-w-md p-8 bg-surface-container-lowest border border-outline-variant rounded-2xl shadow-sm">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-on-background text-on-primary flex items-center justify-center mx-auto mb-4">
            <span className="material-symbols-outlined text-[24px]" style={{ fontVariationSettings: "'FILL' 1" }}>
              lock_reset
            </span>
          </div>
          <h1 className="text-headline-lg font-headline-lg text-on-surface mb-2">Новый пароль</h1>
          <p className="text-body-md font-body-md text-on-surface-variant">Придумайте новый пароль для входа в BINOM AI</p>
        </div>

        {done ? (
          <div className="text-center py-4">
            <span className="material-symbols-outlined text-4xl text-primary mb-3">check_circle</span>
            <p className="text-body-md font-body-md text-on-surface-variant mb-6">
              Пароль успешно изменён. Теперь вы можете войти с новым паролем.
            </p>
            <Link
              href="/login"
              className="block w-full py-2.5 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity"
            >
              Войти
            </Link>
          </div>
        ) : (
          <>
            {error && (
              <div className="mb-6 p-4 bg-error-container text-on-error-container rounded-lg text-body-sm font-body-md">
                {error}
              </div>
            )}

            {accessToken && (
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-2">
                  <label className="block text-label-md font-label-md text-on-surface" htmlFor="new-password">
                    Новый пароль
                  </label>
                  <input
                    id="new-password"
                    type="password"
                    required
                    className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
                    placeholder="Минимум 8 символов"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <label className="block text-label-md font-label-md text-on-surface" htmlFor="confirm-password">
                    Повторите пароль
                  </label>
                  <input
                    id="confirm-password"
                    type="password"
                    required
                    className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
                    placeholder="Повторите новый пароль"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full py-2.5 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>
                      Сохранение...
                    </>
                  ) : (
                    'Сохранить пароль'
                  )}
                </button>
              </form>
            )}
          </>
        )}
      </div>
    </div>
  );
}
