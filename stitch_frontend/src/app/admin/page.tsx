'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { api, errorMessage } from '@/lib/api';

interface Invite {
  id: string;
  code: string;
  max_uses: number;
  uses: number;
  expires_at: string | null;
  active: boolean;
  created_at: string;
}

interface AdminUser {
  id: string;
  email: string | null;
  full_name: string | null;
  role: string;
  company_id: string;
  company_name: string | null;
  project_count: number;
  created_at: string;
}

interface AdminCompany {
  id: string;
  name: string;
  plan: string;
  plan_expires_at: string | null;
  user_count: number;
  project_count: number;
  created_at: string;
}

interface PlanRequestItem {
  id: string;
  company_id: string;
  company_name: string | null;
  user_name: string | null;
  user_email: string | null;
  current_plan: string;
  requested_plan: string;
  message: string | null;
  status: string;
  created_at: string;
}

const PLAN_LABELS: Record<string, string> = {
  trial: 'Пробный',
  starter: 'Старт',
  pro: 'Про',
  enterprise: 'Enterprise',
};

const REQUEST_STATUS_LABELS: Record<string, string> = {
  pending: 'На рассмотрении',
  done: 'Одобрено',
  declined: 'Отклонено',
};

const ROLE_LABELS: Record<string, string> = {
  owner: 'Владелец',
  member: 'Полный доступ',
  limited: 'Ограниченный',
};

export default function AdminPage() {
  const router = useRouter();
  const { user } = useAuth();

  const [invites, setInvites] = useState<Invite[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [planRequests, setPlanRequests] = useState<PlanRequestItem[]>([]);
  const [changingPlan, setChangingPlan] = useState<string | null>(null);
  const [changingRequest, setChangingRequest] = useState<string | null>(null);
  const [maxUses, setMaxUses] = useState(1);
  const [expiresDays, setExpiresDays] = useState(30);
  const [creating, setCreating] = useState(false);
  const [newCode, setNewCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const [accEmail, setAccEmail] = useState('');
  const [accPassword, setAccPassword] = useState('');
  const [accFullName, setAccFullName] = useState('');
  const [accCompanyName, setAccCompanyName] = useState('');
  const [accRole, setAccRole] = useState<'member' | 'limited'>('member');
  const [creatingAccount, setCreatingAccount] = useState(false);
  const [accountCreated, setAccountCreated] = useState<AdminUser | null>(null);

  const load = async () => {
    try {
      const [inv, usr, comp, reqs] = await Promise.all([
        api.get('/admin/invites'),
        api.get('/admin/users'),
        api.get('/admin/companies'),
        api.get('/admin/plan-requests').catch(() => []),
      ]);
      setInvites(inv ?? []);
      setUsers(usr ?? []);
      setCompanies(comp ?? []);
      setPlanRequests(reqs ?? []);
    } catch (e) {
      setError(errorMessage(e, 'Не удалось загрузить данные'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.role !== 'owner') return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.role]);

  if (!user) return null;
  if (user.role !== 'owner') {
    router.replace('/dashboard');
    return null;
  }

  const createInvite = async () => {
    setCreating(true);
    setError('');
    setNewCode(null);
    try {
      const inv = await api.post('/admin/invites', { max_uses: maxUses, expires_in_days: expiresDays });
      setNewCode(inv.code);
      await load();
    } catch (e) {
      setError(errorMessage(e, 'Не удалось создать приглашение'));
    } finally {
      setCreating(false);
    }
  };

  const createAccount = async () => {
    setCreatingAccount(true);
    setError('');
    setAccountCreated(null);
    try {
      const acc = await api.post('/admin/accounts', {
        email: accEmail,
        password: accPassword,
        full_name: accFullName || null,
        company_name: accCompanyName || null,
        role: accRole,
      });
      setAccountCreated(acc);
      setAccEmail('');
      setAccPassword('');
      setAccFullName('');
      setAccCompanyName('');
      await load();
    } catch (e) {
      setError(errorMessage(e, 'Не удалось создать аккаунт'));
    } finally {
      setCreatingAccount(false);
    }
  };

  const changePlan = async (id: string, plan: string) => {
    setChangingPlan(id);
    setError('');
    try {
      await api.patch(`/admin/companies/${id}/plan`, { plan });
      await load();
    } catch (e) {
      setError(errorMessage(e, 'Не удалось изменить тариф'));
    } finally {
      setChangingPlan(null);
    }
  };

  const resolveRequest = async (id: string, status: 'done' | 'declined') => {
    setChangingRequest(id);
    setError('');
    try {
      await api.patch(`/admin/plan-requests/${id}/status`, { status });
      await load();
    } catch (e) {
      setError(errorMessage(e, 'Не удалось обработать заявку'));
    } finally {
      setChangingRequest(null);
    }
  };

  const disableInvite = async (id: string) => {
    try {
      await api.delete(`/admin/invites/${id}`);
      await load();
    } catch (e) {
      setError(errorMessage(e, 'Не удалось отключить приглашение'));
    }
  };

  const setRole = async (id: string, role: string) => {
    try {
      await api.patch(`/admin/users/${id}/role`, { role });
      await load();
    } catch (e) {
      setError(errorMessage(e, 'Не удалось изменить роль'));
    }
  };

  const copy = async () => {
    if (!newCode) return;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(newCode);
      } else {
        const ta = document.createElement('textarea');
        ta.value = newCode;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  };

  const fmtDate = (iso: string | null) =>
    iso ? new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '—';

  const inviteStatus = (inv: Invite): { label: string; ok: boolean } => {
    if (!inv.active) return { label: 'Отключено', ok: false };
    if (inv.expires_at && new Date(inv.expires_at) < new Date()) return { label: 'Истёк', ok: false };
    if (inv.uses >= inv.max_uses) return { label: 'Исчерпан', ok: false };
    return { label: 'Активен', ok: true };
  };

  return (
    <div className="w-full max-w-5xl mx-auto px-4 md:px-margin-page py-stack-lg space-y-8 theme-tenderpro">
      <div>
        <h1 className="text-headline-lg font-headline-lg font-bold text-on-surface">Доступ к платформе</h1>
        <p className="mt-1 text-body-md font-body-md text-on-surface-variant">
          Создавайте аккаунты напрямую — укажите email и пароль, и пользователь сможет войти сразу. Также доступны инвайт-коды.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-error-container text-on-error-container rounded-lg text-body-sm font-body-md">{error}</div>
      )}

      {/* Create account */}
      <section className="bg-surface-container-lowest border border-outline-variant rounded-xl p-6">
        <h2 className="text-headline-md font-headline-md font-bold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-[22px] text-primary">how_to_reg</span>
          Создать аккаунт
        </h2>
        <p className="mt-1 text-body-sm font-body-sm text-on-surface-variant">
          Введите email и пароль — аккаунт создастся мгновенно, пользователь сможет войти сразу.
        </p>

        <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1 md:col-span-2">
            <label className="block text-label-md font-label-md text-on-surface-variant" htmlFor="acc-email">
              Email
            </label>
            <input
              id="acc-email"
              type="email"
              value={accEmail}
              onChange={(e) => setAccEmail(e.target.value)}
              placeholder="user@company.kz"
              className="w-full px-3 py-2 bg-surface border border-outline-variant rounded-lg text-body-md font-body-md text-on-surface focus:outline-none focus:border-primary"
            />
          </div>
          <div className="space-y-1">
            <label className="block text-label-md font-label-md text-on-surface-variant" htmlFor="acc-password">
              Пароль
            </label>
            <input
              id="acc-password"
              type="text"
              value={accPassword}
              onChange={(e) => setAccPassword(e.target.value)}
              placeholder="Минимум 8 символов"
              className="w-full px-3 py-2 bg-surface border border-outline-variant rounded-lg text-body-md font-body-md text-on-surface focus:outline-none focus:border-primary"
            />
          </div>
          <div className="space-y-1">
            <label className="block text-label-md font-label-md text-on-surface-variant" htmlFor="acc-full-name">
              ФИО
            </label>
            <input
              id="acc-full-name"
              type="text"
              value={accFullName}
              onChange={(e) => setAccFullName(e.target.value)}
              placeholder="Имя Фамилия"
              className="w-full px-3 py-2 bg-surface border border-outline-variant rounded-lg text-body-md font-body-md text-on-surface focus:outline-none focus:border-primary"
            />
          </div>
          <div className="space-y-1">
            <label className="block text-label-md font-label-md text-on-surface-variant" htmlFor="acc-company">
              Компания
            </label>
            <input
              id="acc-company"
              type="text"
              value={accCompanyName}
              onChange={(e) => setAccCompanyName(e.target.value)}
              placeholder="Оставьте пустым — присоединится к вашей"
              className="w-full px-3 py-2 bg-surface border border-outline-variant rounded-lg text-body-md font-body-md text-on-surface focus:outline-none focus:border-primary"
            />
          </div>
          <div className="space-y-1">
            <label className="block text-label-md font-label-md text-on-surface-variant" htmlFor="acc-role">
              Роль
            </label>
            <select
              id="acc-role"
              value={accRole}
              onChange={(e) => setAccRole(e.target.value as 'member' | 'limited')}
              className="w-full px-3 py-2 bg-surface border border-outline-variant rounded-lg text-body-md font-body-md text-on-surface focus:outline-none focus:border-primary"
            >
              <option value="member">Полный доступ</option>
              <option value="limited">Ограниченный (до 2 проектов)</option>
            </select>
          </div>
        </div>

        <button
          onClick={createAccount}
          disabled={creatingAccount || !accEmail || !accPassword}
          className="mt-5 h-10 px-5 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
        >
          {creatingAccount ? (
            <>
              <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>
              Создание...
            </>
          ) : (
            <>
              <span className="material-symbols-outlined text-[18px]">person_add</span>
              Создать аккаунт
            </>
          )}
        </button>

        {accountCreated && (
          <div className="mt-4 p-4 bg-success-container/40 border border-success rounded-lg">
            <p className="text-body-sm font-body-md text-on-surface flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-success">check_circle</span>
              Аккаунт создан: {accountCreated.email}. Пользователь может войти сразу.
            </p>
          </div>
        )}
      </section>

      {/* Invites */}
      <section className="bg-surface-container-lowest border border-outline-variant rounded-xl p-6">
        <h2 className="text-headline-md font-headline-md font-bold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-[22px] text-primary">person_add</span>
          Приглашения
        </h2>

        <div className="mt-5 flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label className="block text-label-md font-label-md text-on-surface-variant" htmlFor="inv-max-uses">
              Использований
            </label>
            <input
              id="inv-max-uses"
              type="number"
              min={1}
              max={100}
              value={maxUses}
              onChange={(e) => setMaxUses(Number(e.target.value))}
              className="w-28 px-3 py-2 bg-surface border border-outline-variant rounded-lg text-body-md font-body-md text-on-surface focus:outline-none focus:border-primary"
            />
          </div>
          <div className="space-y-1">
            <label className="block text-label-md font-label-md text-on-surface-variant" htmlFor="inv-days">
              Срок, дней
            </label>
            <input
              id="inv-days"
              type="number"
              min={1}
              max={365}
              value={expiresDays}
              onChange={(e) => setExpiresDays(Number(e.target.value))}
              className="w-28 px-3 py-2 bg-surface border border-outline-variant rounded-lg text-body-md font-body-md text-on-surface focus:outline-none focus:border-primary"
            />
          </div>
          <button
            onClick={createInvite}
            disabled={creating}
            className="h-10 px-5 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
          >
            {creating ? (
              <>
                <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>
                Создание...
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-[18px]">add</span>
                Создать приглашение
              </>
            )}
          </button>
        </div>

        {newCode && (
          <div className="mt-5 p-4 bg-primary/5 border border-primary/20 rounded-lg flex items-center justify-between gap-4">
            <div>
              <p className="text-label-md font-label-md text-on-surface-variant">Код приглашения</p>
              <p className="text-headline-md font-headline-md font-bold text-primary tracking-[0.2em]">{newCode}</p>
            </div>
            <button
              onClick={copy}
              className="h-9 px-4 border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface hover:border-on-background/30 transition-colors flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-[16px]">
                {copied ? 'check' : 'content_copy'}
              </span>
              {copied ? 'Скопировано' : 'Скопировать'}
            </button>
          </div>
        )}

        {invites.length > 0 && (
          <ul className="mt-5 divide-y divide-outline-variant/60">
            {invites.map((inv) => {
              const st = inviteStatus(inv);
              return (
                <li key={inv.id} className="py-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono-sm text-mono-sm text-on-surface font-bold tracking-widest">{inv.code}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-label-sm font-label-sm ${
                          st.ok ? 'bg-primary/10 text-primary' : 'bg-surface-container-high text-on-surface-variant'
                        }`}
                      >
                        {st.label}
                      </span>
                    </div>
                    <p className="mt-0.5 text-body-sm font-body-sm text-on-surface-variant">
                      {inv.uses} / {inv.max_uses} использовано · до {fmtDate(inv.expires_at)}
                    </p>
                  </div>
                  {inv.active && st.ok && (
                    <button
                      onClick={() => disableInvite(inv.id)}
                      className="text-label-md font-label-md text-on-surface-variant hover:text-error transition-colors shrink-0"
                    >
                      Отключить
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* Users */}
      <section className="bg-surface-container-lowest border border-outline-variant rounded-xl p-6">
        <h2 className="text-headline-md font-headline-md font-bold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-[22px] text-primary">group</span>
          Пользователи
        </h2>

        {loading ? (
          <div className="mt-5 flex items-center gap-2 text-body-sm font-body-sm text-on-surface-variant">
            <span className="material-symbols-outlined animate-spin text-[16px]">sync</span>
            Загрузка...
          </div>
        ) : (
          <div className="mt-5 overflow-x-auto">
            <table className="w-full text-left min-w-[640px]">
              <thead>
                <tr className="border-b border-outline-variant text-label-md font-label-md text-on-surface-variant">
                  <th className="py-2 pr-4 font-medium">Пользователь</th>
                  <th className="py-2 pr-4 font-medium">Роль</th>
                  <th className="py-2 pr-4 font-medium">Компания</th>
                  <th className="py-2 pr-4 font-medium">Проектов</th>
                  <th className="py-2 pr-4 font-medium">Регистрация</th>
                  <th className="py-2 font-medium">Действие</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-outline-variant/50">
                    <td className="py-3 pr-4">
                      <p className="text-body-md font-body-md text-on-surface">{u.full_name ?? '—'}</p>
                      <p className="text-body-sm font-body-sm text-on-surface-variant">{u.email ?? 'email неизвестен'}</p>
                    </td>
                    <td className="py-3 pr-4">
                      <span
                        className={`px-2 py-0.5 rounded text-label-sm font-label-sm ${
                          u.role === 'owner'
                            ? 'bg-on-background text-on-primary'
                            : u.role === 'member'
                            ? 'bg-primary/10 text-primary'
                            : 'bg-surface-container-high text-on-surface-variant'
                        }`}
                      >
                        {ROLE_LABELS[u.role] ?? u.role}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-body-md font-body-md text-on-surface">{u.company_name ?? '—'}</td>
                    <td className="py-3 pr-4 text-body-md font-body-md text-on-surface tabular-nums">{u.project_count}</td>
                    <td className="py-3 pr-4 text-body-md font-body-md text-on-surface-variant whitespace-nowrap">
                      {fmtDate(u.created_at)}
                    </td>
                    <td className="py-3">
                      {u.role === 'owner' ? (
                        <span className="text-label-md font-label-md text-on-surface-variant">—</span>
                      ) : (
                        <button
                          onClick={() => setRole(u.id, u.role === 'member' ? 'limited' : 'member')}
                          className="text-label-md font-label-md text-primary hover:underline"
                        >
                          {u.role === 'member' ? 'Ограничить' : 'Дать полный доступ'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Plan requests */}
      <section className="bg-surface-container-lowest border border-outline-variant rounded-xl p-6">
        <h2 className="text-headline-md font-headline-md font-bold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-[22px] text-primary">workspace_premium</span>
          Заявки на смену тарифа
          {planRequests.filter((r) => r.status === 'pending').length > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-error-container text-on-error-container text-label-sm font-label-sm">
              {planRequests.filter((r) => r.status === 'pending').length} новых
            </span>
          )}
        </h2>

        {planRequests.length === 0 ? (
          <p className="mt-4 text-body-sm font-body-sm text-on-surface-variant">Пока нет заявок.</p>
        ) : (
          <ul className="mt-5 space-y-3">
            {planRequests.map((r) => (
              <li
                key={r.id}
                className="p-4 bg-surface-bright border border-outline-variant rounded-lg flex flex-wrap items-center justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-body-md font-body-md text-on-surface font-semibold">{r.company_name ?? '—'}</p>
                    <span
                      className={`px-2 py-0.5 rounded text-label-sm font-label-sm ${
                        r.status === 'pending'
                          ? 'bg-surface-container-high text-on-surface-variant'
                          : r.status === 'done'
                          ? 'bg-primary/10 text-primary'
                          : 'bg-error-container text-on-error-container'
                      }`}
                    >
                      {REQUEST_STATUS_LABELS[r.status] ?? r.status}
                    </span>
                  </div>
                  <p className="mt-1 text-body-sm font-body-sm text-on-surface-variant">
                    {PLAN_LABELS[r.current_plan] ?? r.current_plan} →{' '}
                    <span className="font-semibold text-on-surface">{PLAN_LABELS[r.requested_plan] ?? r.requested_plan}</span>
                    {' · '}
                    {new Date(r.created_at).toLocaleDateString('ru-RU')}
                  </p>
                  {(r.user_name || r.user_email) && (
                    <p className="mt-0.5 text-label-sm font-label-sm text-on-surface-variant">
                      {r.user_name ? `${r.user_name} · ` : ''}
                      {r.user_email}
                    </p>
                  )}
                  {r.message && (
                    <p className="mt-1 text-body-sm font-body-sm text-on-surface-variant italic">«{r.message}»</p>
                  )}
                </div>
                {r.status === 'pending' && (
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => resolveRequest(r.id, 'declined')}
                      disabled={changingRequest === r.id}
                      className="h-9 px-4 border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface-variant hover:text-error hover:border-error/40 transition-colors disabled:opacity-50"
                    >
                      Отклонить
                    </button>
                    <button
                      onClick={() => resolveRequest(r.id, 'done')}
                      disabled={changingRequest === r.id}
                      className="h-9 px-4 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-1.5"
                    >
                      {changingRequest === r.id && (
                        <span className="material-symbols-outlined animate-spin text-[16px]">sync</span>
                      )}
                      Одобрить и активировать
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Companies & plans */}
      <section className="bg-surface-container-lowest border border-outline-variant rounded-xl p-6">
        <h2 className="text-headline-md font-headline-md font-bold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-[22px] text-primary">domain</span>
          Компании и тарифы
        </h2>

        <div className="mt-5 overflow-x-auto">
          <table className="w-full text-left min-w-[720px]">
            <thead>
              <tr className="border-b border-outline-variant text-label-md font-label-md text-on-surface-variant">
                <th className="py-2 pr-4 font-medium">Компания</th>
                <th className="py-2 pr-4 font-medium">Тариф</th>
                <th className="py-2 pr-4 font-medium">Пользователей</th>
                <th className="py-2 pr-4 font-medium">Проектов</th>
                <th className="py-2 pr-4 font-medium">Регистрация</th>
                <th className="py-2 font-medium">Действие</th>
              </tr>
            </thead>
            <tbody>
              {companies.map((c) => (
                <tr key={c.id} className="border-b border-outline-variant/50">
                  <td className="py-3 pr-4 text-body-md font-body-md text-on-surface">{c.name}</td>
                  <td className="py-3 pr-4">
                    <span
                      className={`px-2 py-0.5 rounded text-label-sm font-label-sm ${
                        c.plan === 'enterprise'
                          ? 'bg-on-background text-on-primary'
                          : c.plan === 'pro'
                          ? 'bg-primary/10 text-primary'
                          : 'bg-surface-container-high text-on-surface-variant'
                      }`}
                    >
                      {PLAN_LABELS[c.plan] ?? c.plan}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-body-md font-body-md text-on-surface tabular-nums">{c.user_count}</td>
                  <td className="py-3 pr-4 text-body-md font-body-md text-on-surface tabular-nums">{c.project_count}</td>
                  <td className="py-3 pr-4 text-body-md font-body-md text-on-surface-variant whitespace-nowrap">
                    {fmtDate(c.created_at)}
                  </td>
                  <td className="py-3">
                    <select
                      value={c.plan}
                      disabled={changingPlan === c.id}
                      onChange={(e) => changePlan(c.id, e.target.value)}
                      className="px-2 py-1.5 bg-surface border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface focus:outline-none focus:border-primary disabled:opacity-50"
                    >
                      {Object.entries(PLAN_LABELS).map(([key, label]) => (
                        <option key={key} value={key}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}