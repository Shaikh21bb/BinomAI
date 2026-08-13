'use client';

import { FormEvent, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { api, errorMessage } from '@/lib/api';

export default function RegisterPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

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
      const response = await api.post('/auth/register', {
        email,
        password,
        full_name: fullName,
        company_name: companyName,
        invite_code: inviteCode.trim() || undefined,
      });
      login(response.access_token ?? '', response.refresh_token, response.user);
      router.push('/dashboard');
      router.refresh();
    } catch (err) {
      setError(errorMessage(err, 'Не удалось создать аккаунт'));
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
              assistant
            </span>
          </div>
          <h1 className="text-headline-lg font-headline-lg text-on-surface mb-2">Создать аккаунт</h1>
          <p className="text-body-md font-body-md text-on-surface-variant">Ваш AI-копайлот для тендерной документации</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-error-container text-on-error-container rounded-lg text-body-sm font-body-md">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <label className="block text-label-md font-label-md text-on-surface" htmlFor="reg-name">
              Полное имя
            </label>
            <input
              id="reg-name"
              type="text"
              required
              className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
              placeholder="Асель Нурова"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <label className="block text-label-md font-label-md text-on-surface" htmlFor="reg-email">
              Email
            </label>
            <input
              id="reg-email"
              type="email"
              required
              className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
              placeholder="asel@company.kz"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <label className="block text-label-md font-label-md text-on-surface" htmlFor="reg-company">
              Название компании
            </label>
            <input
              id="reg-company"
              type="text"
              required
              className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
              placeholder="ТОО «КазСтройПроект»"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <label className="block text-label-md font-label-md text-on-surface" htmlFor="reg-invite">
              Инвайт-код <span className="text-on-surface-variant font-normal">(если есть)</span>
            </label>
            <input
              id="reg-invite"
              type="text"
              autoCapitalize="characters"
              className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface uppercase"
              placeholder="Например: MGZ4WNY3"
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value)}
            />
            <p className="text-body-sm font-body-sm text-on-surface-variant">
              Без кода доступ ограничен: до 2 проектов. Полный доступ выдаёт владелец платформы.
            </p>
          </div>

          <div className="space-y-2">
            <label className="block text-label-md font-label-md text-on-surface" htmlFor="reg-password">
              Пароль
            </label>
            <input
              id="reg-password"
              type="password"
              required
              className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
              placeholder="Минимум 8 символов"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <label className="block text-label-md font-label-md text-on-surface" htmlFor="reg-confirm">
              Подтвердите пароль
            </label>
            <input
              id="reg-confirm"
              type="password"
              required
              className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface"
              placeholder="••••••••"
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
                Создание аккаунта...
              </>
            ) : (
              'Создать аккаунт'
            )}
          </button>
        </form>

        <p className="text-center text-body-md font-body-md text-on-surface-variant mt-6">
          Уже есть аккаунт?{' '}
          <Link href="/login" className="text-primary font-medium hover:underline">
            Войти →
          </Link>
        </p>
      </div>
    </div>
  );
}