'use client';

import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { api, errorMessage } from '@/lib/api';
import { AppShell } from '@/components/AppShell';

type Tab = 'profile' | 'company' | 'team' | 'security' | 'notifications' | 'learning' | 'plan';

interface ProfileData {
  id: string;
  email: string;
  full_name: string;
  job_title: string;
  phone: string;
  language: string;
  timezone: string;
  role: string;
  company_name: string;
  email_notifications: boolean;
}

interface CompanyData {
  name: string;
  bin_iin: string;
  legal_address: string;
  actual_address: string;
  phone: string;
  email: string;
  website: string;
  specialization: string;
  employee_count: number | null;
  director_name: string;
  director_title: string;
}

interface PlanData {
  plan: string;
  plan_name: string;
  plan_price_monthly_kzt: number;
  plan_expires_at: string | null;
  limits: {
    max_projects: number | null;
    max_users: number | null;
    max_documents: number | null;
    features: Record<string, boolean>;
  };
  usage: Record<string, number>;
}

interface PlanRequest {
  id: string;
  requested_plan: string;
  message: string | null;
  status: string;
  created_at: string;
}

interface MemberData {
  id: string;
  full_name: string | null;
  email: string | null;
  role: string;
  job_title: string | null;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

interface InviteData {
  id: string;
  code: string;
  max_uses: number;
  uses: number;
  expires_at: string | null;
  active: boolean;
  created_at: string;
}

const ROLE_LABELS: Record<string, string> = {
  owner: 'Владелец',
  member: 'Сотрудник',
  limited: 'Ограниченный',
};

const ROLE_COLORS: Record<string, string> = {
  owner: 'bg-on-background text-on-primary',
  member: 'bg-surface-container-high text-on-surface',
  limited: 'bg-surface-container-high text-on-surface-variant',
};

const PLAN_OPTIONS: { key: string; label: string; price: string }[] = [
  { key: 'starter', label: 'Старт', price: '49 000 ₸/мес' },
  { key: 'pro', label: 'Про', price: '149 000 ₸/мес' },
  { key: 'enterprise', label: 'Enterprise', price: 'по запросу' },
];

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'profile', label: 'Профиль', icon: 'person' },
  { key: 'company', label: 'Компания', icon: 'domain' },
  { key: 'team', label: 'Команда', icon: 'group' },
  { key: 'plan', label: 'Тариф', icon: 'workspace_premium' },
  { key: 'security', label: 'Безопасность', icon: 'lock' },
  { key: 'notifications', label: 'Уведомления', icon: 'notifications' },
  { key: 'learning', label: 'Обучение', icon: 'school' },
];

const TIMEZONES = [
  'Asia/Almaty',
  'Asia/Aqtobe',
  'Asia/Aqtau',
  'Asia/Qostanay',
  'Asia/Oral',
  'Asia/Shymkent',
  'Europe/Moscow',
];

const inputCls =
  'w-full bg-surface-bright border border-outline-variant rounded-md px-3 py-2 text-body-md font-body-md text-on-surface focus:outline-none focus:border-on-background focus:ring-2 focus:ring-on-background/5 transition-all';

const selectCls = `${inputCls} appearance-none cursor-pointer pr-10`;

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-label-md font-label-md text-on-surface-variant">
        {label}
      </label>
      {children}
    </div>
  );
}

function Flash({ kind, text }: { kind: 'ok' | 'err'; text: string }) {
  if (!text) return null;
  return (
    <div
      className={`px-4 py-2.5 rounded-md text-body-sm font-body-md border ${
        kind === 'ok'
          ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
          : 'bg-error-container text-on-error-container border-red-200'
      }`}
    >
      {text}
    </div>
  );
}

function SectionCard({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <section className="bg-surface-container-lowest border border-outline-variant rounded-lg p-stack-lg">
      <div className="flex items-center gap-3 mb-stack-md border-b border-outline-variant pb-4">
        <div className="w-8 h-8 rounded-md bg-surface-container-high flex items-center justify-center text-on-surface">
          <span className="material-symbols-outlined text-[18px]">{icon}</span>
        </div>
        <h2 className="text-headline-md font-headline-md text-on-surface">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function ToggleItem({
  checked,
  onChange,
  title,
  subtitle,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <p className="text-body-md font-body-md font-semibold text-on-surface">{title}</p>
        <p className="text-label-md font-label-md text-on-surface-variant">{subtitle}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-6 rounded-full transition-colors duration-200 shrink-0 ${
          checked ? 'bg-on-background' : 'bg-outline-variant'
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm border border-outline-variant transition-transform duration-200 ${
            checked ? 'translate-x-4' : ''
          }`}
        />
      </button>
    </div>
  );
}

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [tab, setTab] = useState<Tab>('profile');

  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [company, setCompany] = useState<CompanyData | null>(null);
  const [plan, setPlan] = useState<PlanData | null>(null);
  const [planRequests, setPlanRequests] = useState<PlanRequest[]>([]);
  const [members, setMembers] = useState<MemberData[]>([]);
  const [invites, setInvites] = useState<InviteData[]>([]);
  const [teamAction, setTeamAction] = useState<{ kind: 'member' | 'invite'; id: string } | null>(null);
  const [inviteUses, setInviteUses] = useState(5);
  const [inviteTtl, setInviteTtl] = useState(30);
  const [creatingInvite, setCreatingInvite] = useState(false);
  const [requestOpen, setRequestOpen] = useState(false);
  const [requestPlan, setRequestPlan] = useState('pro');
  const [requestMessage, setRequestMessage] = useState('');
  const [requestSending, setRequestSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [flash, setFlash] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  const [savingProfile, setSavingProfile] = useState(false);
  const [savingCompany, setSavingCompany] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const initials = useMemo(() => {
    const name = (profile?.full_name || user?.full_name || 'U')
      .split(' ')
      .map((w) => w[0])
      .slice(0, 2)
      .join('')
      .toUpperCase();
    return name || 'U';
  }, [profile?.full_name, user?.full_name]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [p, c, pl, reqs, mem, inv] = await Promise.all([
          api.get('/users/me'),
          api.get('/users/me/company'),
          api.get('/users/me/company/plan-usage'),
          api.get('/users/me/plan-requests').catch(() => []),
          api.get('/users/me/company/members').catch(() => []),
          api.get('/users/me/company/invites').catch(() => []),
        ]);
        if (!cancelled) {
          setProfile(p);
          setCompany(c);
          setPlan(pl);
          setPlanRequests(reqs ?? []);
          setMembers(mem ?? []);
          setInvites(inv ?? []);
        }
      } catch (err) {
        if (!cancelled) {
          setFlash({ kind: 'err', text: errorMessage(err, 'Не удалось загрузить настройки') });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const saveProfile = async () => {
    if (!profile) return;
    setSavingProfile(true);
    setFlash(null);
    try {
      const updated = await api.patch('/users/me', {
        full_name: profile.full_name,
        job_title: profile.job_title,
        phone: profile.phone,
        language: profile.language,
        timezone: profile.timezone,
      });
      setProfile(updated);
      await refreshUser();
      setFlash({ kind: 'ok', text: 'Профиль сохранён' });
    } catch (err) {
      setFlash({ kind: 'err', text: errorMessage(err, 'Не удалось сохранить профиль') });
    } finally {
      setSavingProfile(false);
    }
  };

  const saveCompany = async () => {
    if (!company) return;
    setSavingCompany(true);
    setFlash(null);
    try {
      const updated = await api.patch('/users/me/company', {
        name: company.name,
        bin_iin: company.bin_iin,
        legal_address: company.legal_address,
        actual_address: company.actual_address,
        phone: company.phone,
        email: company.email,
        website: company.website,
        specialization: company.specialization,
        employee_count: company.employee_count,
        director_name: company.director_name,
        director_title: company.director_title,
      });
      setCompany(updated);
      setFlash({ kind: 'ok', text: 'Данные компании сохранены' });
    } catch (err) {
      setFlash({ kind: 'err', text: errorMessage(err, 'Не удалось сохранить данные компании') });
    } finally {
      setSavingCompany(false);
    }
  };

  const savePassword = async () => {
    if (newPassword.length < 8) {
      setFlash({ kind: 'err', text: 'Новый пароль должен содержать минимум 8 символов' });
      return;
    }
    if (newPassword !== confirmPassword) {
      setFlash({ kind: 'err', text: 'Пароли не совпадают' });
      return;
    }
    setSavingPassword(true);
    setFlash(null);
    try {
      await api.put('/users/me/password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setFlash({ kind: 'ok', text: 'Пароль успешно изменён' });
    } catch (err) {
      setFlash({ kind: 'err', text: errorMessage(err, 'Не удалось сменить пароль') });
    } finally {
      setSavingPassword(false);
    }
  };

  const toggleNotifications = async (v: boolean) => {
    setFlash(null);
    try {
      const updated = await api.patch('/users/me/notifications', { email_notifications: v });
      setProfile((prev) => (prev ? { ...prev, email_notifications: updated.email_notifications } : prev));
      setFlash({ kind: 'ok', text: 'Настройки уведомлений сохранены' });
    } catch (err) {
      setFlash({ kind: 'err', text: errorMessage(err, 'Не удалось сохранить настройки') });
    }
  };

  const sendPlanRequest = async () => {
    setRequestSending(true);
    setFlash(null);
    try {
      const req = await api.post('/users/me/plan-requests', {
        requested_plan: requestPlan,
        message: requestMessage || null,
      });
      setPlanRequests((prev) => [req, ...prev]);
      setRequestOpen(false);
      setRequestMessage('');
      setFlash({ kind: 'ok', text: 'Заявка отправлена. Администратор свяжется с вами и активирует тариф.' });
    } catch (err) {
      setFlash({ kind: 'err', text: errorMessage(err, 'Не удалось отправить заявку') });
      setRequestOpen(false);
    } finally {
      setRequestSending(false);
    }
  };

  const changeMemberRole = async (member: MemberData, role: string) => {
    setTeamAction({ kind: 'member', id: member.id });
    setFlash(null);
    try {
      const updated = await api.patch(`/users/me/company/members/${member.id}/role`, { role });
      setMembers((prev) => prev.map((m) => (m.id === member.id ? updated : m)));
      setFlash({ kind: 'ok', text: 'Роль обновлена' });
    } catch (err) {
      setFlash({ kind: 'err', text: errorMessage(err, 'Не удалось изменить роль') });
    } finally {
      setTeamAction(null);
    }
  };

  const removeMember = async (member: MemberData) => {
    if (!window.confirm(`Удалить ${member.full_name || member.email || 'сотрудника'} из компании?`)) return;
    setTeamAction({ kind: 'member', id: member.id });
    setFlash(null);
    try {
      await api.delete(`/users/me/company/members/${member.id}`);
      setMembers((prev) => prev.filter((m) => m.id !== member.id));
      setFlash({ kind: 'ok', text: 'Сотрудник удалён из компании' });
    } catch (err) {
      setFlash({ kind: 'err', text: errorMessage(err, 'Не удалось удалить сотрудника') });
    } finally {
      setTeamAction(null);
    }
  };

  const createInvite = async () => {
    setCreatingInvite(true);
    setFlash(null);
    try {
      const inv = await api.post('/users/me/company/invites', {
        max_uses: inviteUses,
        expires_in_days: inviteTtl,
      });
      setInvites((prev) => [inv, ...prev]);
      setFlash({ kind: 'ok', text: `Код создан: ${inv.code}` });
    } catch (err) {
      setFlash({ kind: 'err', text: errorMessage(err, 'Не удалось создать код приглашения') });
    } finally {
      setCreatingInvite(false);
    }
  };

  const disableInvite = async (inv: InviteData) => {
    setTeamAction({ kind: 'invite', id: inv.id });
    setFlash(null);
    try {
      await api.delete(`/users/me/company/invites/${inv.id}`);
      setInvites((prev) => prev.map((i) => (i.id === inv.id ? { ...i, active: false } : i)));
      setFlash({ kind: 'ok', text: 'Код приглашения деактивирован' });
    } catch (err) {
      setFlash({ kind: 'err', text: errorMessage(err, 'Не удалось деактивировать код') });
    } finally {
      setTeamAction(null);
    }
  };

  const copyInvite = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setFlash({ kind: 'ok', text: 'Код скопирован' });
    } catch {
      setFlash({ kind: 'err', text: 'Не удалось скопировать код' });
    }
  };

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto p-4 md:p-margin-page">
        <div className="max-w-[860px] mx-auto flex flex-col items-center justify-center py-24 gap-3">
          <span className="material-symbols-outlined animate-spin text-3xl text-on-surface-variant">sync</span>
          <p className="text-body-md font-body-md text-on-surface-variant">Загрузка настроек…</p>
        </div>
      </div>
    );
  }

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto p-4 md:p-margin-page">
        <div className="max-w-[860px] mx-auto space-y-stack-lg">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-lg bg-on-background text-on-primary flex items-center justify-center text-headline-md font-headline-md font-bold shrink-0">
            {initials}
          </div>
          <div>
            <h1 className="text-headline-xl font-headline-xl text-on-surface">
              {profile?.full_name || 'Профиль'}
            </h1>
            <p className="text-body-md font-body-md text-on-surface-variant">
              {profile?.email}
              {profile?.company_name ? ` · ${profile.company_name}` : ''}
            </p>
          </div>
        </div>

        <div className="flex gap-1 border-b border-outline-variant overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => {
                setTab(t.key);
                setFlash(null);
              }}
              className={`flex items-center gap-2 px-4 py-2.5 -mb-px border-b-2 text-label-md font-label-md whitespace-nowrap transition-colors ${
                tab === t.key
                  ? 'border-on-background text-on-surface font-bold'
                  : 'border-transparent text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">{t.icon}</span>
              {t.label}
            </button>
          ))}
        </div>

        {flash && <Flash kind={flash.kind} text={flash.text} />}

        {tab === 'profile' && profile && (
          <SectionCard title="Личные данные" icon="person">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <Field id="p-full-name" label="ФИО">
                <input
                  id="p-full-name"
                  className={inputCls}
                  value={profile.full_name || ''}
                  onChange={(e) => setProfile({ ...profile, full_name: e.target.value })}
                />
              </Field>
              <Field id="p-job" label="Должность">
                <input
                  id="p-job"
                  className={inputCls}
                  value={profile.job_title || ''}
                  onChange={(e) => setProfile({ ...profile, job_title: e.target.value })}
                />
              </Field>
              <Field id="p-phone" label="Телефон">
                <input
                  id="p-phone"
                  className={inputCls}
                  value={profile.phone || ''}
                  onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
                />
              </Field>
              <Field id="p-language" label="Язык интерфейса">
                <select
                  id="p-language"
                  className={selectCls}
                  value={profile.language}
                  onChange={(e) => setProfile({ ...profile, language: e.target.value })}
                >
                  <option value="ru">Русский</option>
                  <option value="kk">Қазақша</option>
                </select>
              </Field>
              <Field id="p-timezone" label="Часовой пояс">
                <select
                  id="p-timezone"
                  className={selectCls}
                  value={profile.timezone}
                  onChange={(e) => setProfile({ ...profile, timezone: e.target.value })}
                >
                  {TIMEZONES.map((tz) => (
                    <option key={tz} value={tz}>
                      {tz}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="flex justify-end pt-5">
              <button
                onClick={saveProfile}
                disabled={savingProfile}
                className="px-6 py-2 bg-on-background text-on-primary rounded-md text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {savingProfile ? 'Сохранение…' : 'Сохранить профиль'}
              </button>
            </div>
          </SectionCard>
        )}

        {tab === 'company' && company && (
          <SectionCard title="Данные компании" icon="domain">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <Field id="c-name" label="Название компании">
                <input
                  id="c-name"
                  className={inputCls}
                  value={company.name || ''}
                  onChange={(e) => setCompany({ ...company, name: e.target.value })}
                />
              </Field>
              <Field id="c-bin" label="БИН / ИИН">
                <input
                  id="c-bin"
                  className={`${inputCls} font-mono-sm font-mono-sm`}
                  value={company.bin_iin || ''}
                  onChange={(e) => setCompany({ ...company, bin_iin: e.target.value })}
                />
              </Field>
              <Field id="c-legal" label="Юридический адрес">
                <input
                  id="c-legal"
                  className={inputCls}
                  value={company.legal_address || ''}
                  onChange={(e) => setCompany({ ...company, legal_address: e.target.value })}
                />
              </Field>
              <Field id="c-actual" label="Фактический адрес">
                <input
                  id="c-actual"
                  className={inputCls}
                  value={company.actual_address || ''}
                  onChange={(e) => setCompany({ ...company, actual_address: e.target.value })}
                />
              </Field>
              <Field id="c-phone" label="Телефон">
                <input
                  id="c-phone"
                  className={inputCls}
                  value={company.phone || ''}
                  onChange={(e) => setCompany({ ...company, phone: e.target.value })}
                />
              </Field>
              <Field id="c-email" label="Email">
                <input
                  id="c-email"
                  type="email"
                  className={inputCls}
                  value={company.email || ''}
                  onChange={(e) => setCompany({ ...company, email: e.target.value })}
                />
              </Field>
              <Field id="c-site" label="Сайт">
                <input
                  id="c-site"
                  className={inputCls}
                  value={company.website || ''}
                  onChange={(e) => setCompany({ ...company, website: e.target.value })}
                />
              </Field>
              <Field id="c-director" label="Руководитель">
                <input
                  id="c-director"
                  className={inputCls}
                  value={company.director_name || ''}
                  onChange={(e) => setCompany({ ...company, director_name: e.target.value })}
                />
              </Field>
              <Field id="c-spec" label="Специализация">
                <input
                  id="c-spec"
                  className={inputCls}
                  value={company.specialization || ''}
                  onChange={(e) => setCompany({ ...company, specialization: e.target.value })}
                />
              </Field>
              <Field id="c-employees" label="Численность сотрудников">
                <input
                  id="c-employees"
                  type="number"
                  className={inputCls}
                  value={company.employee_count ?? ''}
                  onChange={(e) =>
                    setCompany({
                      ...company,
                      employee_count: e.target.value === '' ? null : Number(e.target.value),
                    })
                  }
                />
              </Field>
            </div>
            <div className="flex justify-end pt-5">
              <button
                onClick={saveCompany}
                disabled={savingCompany}
                className="px-6 py-2 bg-on-background text-on-primary rounded-md text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {savingCompany ? 'Сохранение…' : 'Сохранить данные компании'}
              </button>
            </div>
          </SectionCard>
        )}

        {tab === 'team' && (
          <>
            <SectionCard title="Сотрудники компании" icon="group">
              {members.length === 0 ? (
                <p className="text-body-md font-body-md text-on-surface-variant">
                  В компании пока нет сотрудников. Создайте код приглашения, чтобы пригласить команду.
                </p>
              ) : (
                <ul className="divide-y divide-outline-variant">
                  {members.map((m) => {
                    const isMe = m.id === user?.id;
                    return (
                      <li key={m.id} className="py-3 flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-surface-container-high text-on-surface flex items-center justify-center text-label-md font-label-md font-semibold shrink-0">
                          {(m.full_name || m.email || '?')
                            .split(' ')
                            .map((w) => w[0])
                            .slice(0, 2)
                            .join('')
                            .toUpperCase()}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-body-md font-body-md font-semibold text-on-surface truncate">
                            {m.full_name || 'Без имени'} {isMe && <span className="text-on-surface-variant">(вы)</span>}
                          </p>
                          <p className="text-label-md font-label-md text-on-surface-variant truncate">
                            {m.email}
                            {m.job_title ? ` · ${m.job_title}` : ''}
                          </p>
                        </div>
                        <span
                          className={`hidden sm:inline-block px-2.5 py-1 rounded-full text-label-sm font-label-sm ${ROLE_COLORS[m.role] || ROLE_COLORS.member}`}
                        >
                          {ROLE_LABELS[m.role] || m.role}
                        </span>
                        {m.is_active === false && (
                          <span className="px-2.5 py-1 rounded-full bg-error-container text-on-error-container text-label-sm font-label-sm">
                            Деактивирован
                          </span>
                        )}
                        {user?.role === 'owner' && m.role !== 'owner' && (
                          <div className="flex items-center gap-1.5 shrink-0">
                            <select
                              className="bg-surface-bright border border-outline-variant rounded-md px-2 py-1.5 text-label-md font-label-md text-on-surface focus:outline-none"
                              value={m.role}
                              disabled={teamAction?.kind === 'member' && teamAction.id === m.id}
                              onChange={(e) => changeMemberRole(m, e.target.value)}
                            >
                              <option value="member">Сотрудник</option>
                              <option value="limited">Ограниченный</option>
                            </select>
                            <button
                              onClick={() => removeMember(m)}
                              disabled={teamAction?.kind === 'member' && teamAction.id === m.id}
                              className="w-8 h-8 rounded-md bg-surface-container-high text-on-surface hover:text-error flex items-center justify-center disabled:opacity-50 transition-colors"
                              title="Удалить из компании"
                            >
                              <span className="material-symbols-outlined text-[18px]">person_remove</span>
                            </button>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </SectionCard>

            {user?.role === 'owner' && (
              <SectionCard title="Приглашение по коду" icon="link">
                <div className="flex flex-wrap items-end gap-3">
                  <div className="w-36">
                    <Field id="inv-uses" label="Сколько раз можно использовать">
                      <input
                        id="inv-uses"
                        type="number"
                        min={1}
                        className={inputCls}
                        value={inviteUses}
                        onChange={(e) => setInviteUses(Math.max(1, Number(e.target.value || 1)))}
                      />
                    </Field>
                  </div>
                  <div className="w-40">
                    <Field id="inv-ttl" label="Действует, дней">
                      <select
                        id="inv-ttl"
                        className={selectCls}
                        value={inviteTtl}
                        onChange={(e) => setInviteTtl(Number(e.target.value))}
                      >
                        <option value={1}>1</option>
                        <option value={7}>7</option>
                        <option value={30}>30</option>
                        <option value={90}>90</option>
                        <option value={365}>365</option>
                      </select>
                    </Field>
                  </div>
                  <button
                    onClick={createInvite}
                    disabled={creatingInvite}
                    className="px-5 py-2 bg-on-background text-on-primary rounded-md text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
                  >
                    <span className="material-symbols-outlined text-[18px]">add_link</span>
                    {creatingInvite ? 'Создание…' : 'Создать код'}
                  </button>
                </div>
                <p className="mt-3 text-body-sm font-body-sm text-on-surface-variant">
                  Сотрудник вводит код при регистрации и присоединяется к вашей компании.
                </p>

                {invites.length > 0 && (
                  <ul className="mt-5 divide-y divide-outline-variant">
                    {invites.map((inv) => (
                      <li key={inv.id} className="py-2.5 flex items-center gap-3">
                        <code className="font-mono-sm font-mono-sm bg-surface-container-high px-2.5 py-1 rounded-md tracking-wider">
                          {inv.code}
                        </code>
                        <span className="text-label-md font-label-md text-on-surface-variant">
                          {inv.active ? `использовано ${inv.uses} из ${inv.max_uses}` : 'деактивирован'}
                          {inv.expires_at
                            ? ` · до ${new Date(inv.expires_at).toLocaleDateString('ru-RU')}`
                            : ' · без срока'}
                        </span>
                        <div className="ml-auto flex items-center gap-1.5">
                          <button
                            onClick={() => copyInvite(inv.code)}
                            className="px-2.5 py-1.5 rounded-md bg-surface-container-high text-on-surface text-label-md font-label-md hover:opacity-80 transition-opacity flex items-center gap-1.5"
                          >
                            <span className="material-symbols-outlined text-[16px]">content_copy</span>
                            Копировать
                          </button>
                          {inv.active && (
                            <button
                              onClick={() => disableInvite(inv)}
                              disabled={teamAction?.kind === 'invite' && teamAction.id === inv.id}
                              className="px-2.5 py-1.5 rounded-md bg-surface-container-high text-on-surface text-label-md font-label-md hover:text-error transition-colors disabled:opacity-50"
                            >
                              Отключить
                            </button>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </SectionCard>
            )}
          </>
        )}

        {tab === 'security' && (
          <SectionCard title="Смена пароля" icon="lock">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <Field id="s-current" label="Текущий пароль">
                <input
                  id="s-current"
                  type="password"
                  className={inputCls}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                />
              </Field>
              <Field id="s-new" label="Новый пароль (мин. 8 символов)">
                <input
                  id="s-new"
                  type="password"
                  className={inputCls}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
              </Field>
              <Field id="s-confirm" label="Подтверждение">
                <input
                  id="s-confirm"
                  type="password"
                  className={inputCls}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </Field>
            </div>
            <div className="flex justify-end pt-5">
              <button
                onClick={savePassword}
                disabled={savingPassword}
                className="px-6 py-2 bg-on-background text-on-primary rounded-md text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {savingPassword ? 'Смена…' : 'Сменить пароль'}
              </button>
            </div>
          </SectionCard>
        )}

        {tab === 'notifications' && profile && (
          <SectionCard title="Уведомления" icon="notifications">
            <ToggleItem
              checked={profile.email_notifications}
              onChange={toggleNotifications}
              title="Email-уведомления"
              subtitle="Получать уведомления о статусе анализа и генерации документов"
            />
            <div className="border-t border-outline-variant mt-3 pt-4">
              <p className="text-body-sm font-body-sm text-on-surface-variant">
                Уведомления приходят на {profile.email || 'ваш email'}.
              </p>
            </div>
          </SectionCard>
        )}

        {tab === 'learning' && (
          <SectionCard title="Обучение" icon="school">
            <p className="text-body-md font-body-md text-on-surface-variant mb-5">
              Интерактивный тур по платформе: рабочий стол, загрузка технического задания, AI-анализ,
              уточнения, генерация документов и экспорт.
            </p>
            <button
              onClick={() => window.dispatchEvent(new Event('binom:open-onboarding'))}
              className="px-6 py-2 bg-on-background text-on-primary rounded-md text-label-md font-label-md hover:opacity-90 transition-opacity flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-[18px]">play_lesson</span>
              Начать обучение
            </button>
          </SectionCard>
        )}

        {tab === 'plan' && plan && (
          <SectionCard title="Тариф и лимиты" icon="workspace_premium">
            <div className="flex items-center justify-between gap-4 mb-6">
              <div>
                <p className="text-body-sm font-body-sm text-on-surface-variant">Текущий тариф</p>
                <p className="text-headline-lg font-headline-lg font-bold text-on-surface">{plan.plan_name}</p>
              </div>
              <div className="text-right">
                <p className="text-body-sm font-body-sm text-on-surface-variant">Стоимость</p>
                <p className="text-headline-md font-headline-md font-bold text-on-surface">
                  {plan.plan_price_monthly_kzt > 0
                    ? new Intl.NumberFormat('ru-RU').format(plan.plan_price_monthly_kzt) + ' ₸/мес'
                    : '—'}
                </p>
              </div>
            </div>

            {plan.plan_expires_at && (
              <p className="text-body-sm font-body-sm text-on-surface-variant mb-4">
                Действует до {new Date(plan.plan_expires_at).toLocaleDateString('ru-RU')}
              </p>
            )}

            <div className="space-y-5">
              {(
                [
                  ['projects', 'Проекты', plan.limits.max_projects],
                  ['users', 'Пользователи', plan.limits.max_users],
                  ['documents', 'Документы', plan.limits.max_documents],
                ] as const
              ).map(([key, label, limit]) => {
                if (limit === null) {
                  return (
                    <div key={key}>
                      <div className="flex justify-between mb-1.5">
                        <span className="text-label-md font-label-md text-on-surface">{label}</span>
                        <span className="text-label-md font-label-md text-on-surface-variant">без лимита</span>
                      </div>
                    </div>
                  );
                }
                const current = plan.usage[key] ?? 0;
                const pct = Math.min(100, Math.round((current / Math.max(1, limit)) * 100));
                const near = current >= limit * 0.8;
                return (
                  <div key={key}>
                    <div className="flex justify-between mb-1.5">
                      <span className="text-label-md font-label-md text-on-surface">{label}</span>
                      <span className={`text-label-md font-label-md ${near ? 'text-error' : 'text-on-surface-variant'}`}>
                        {current} / {limit}
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-surface-container-high overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          pct >= 100 ? 'bg-error' : near ? 'bg-error' : 'bg-primary'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-6 p-4 bg-surface-container-low rounded-lg border border-outline-variant/60">
              <p className="text-body-sm font-body-sm text-on-surface-variant">
                Нужно больше? Отправьте заявку на смену тарифа — администратор платформы активирует его и свяжется с вами.
              </p>
              <button
                onClick={() => setRequestOpen(true)}
                disabled={planRequests.some((r) => r.status === 'pending')}
                className="mt-4 px-5 py-2 bg-on-background text-on-primary rounded-md text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-[18px]">workspace_premium</span>
                {planRequests.some((r) => r.status === 'pending') ? 'Заявка уже отправлена' : 'Запросить смену тарифа'}
              </button>
            </div>

            {planRequests.length > 0 && (
              <div className="mt-5 border-t border-outline-variant/60 pt-4">
                <p className="text-label-md font-label-md text-on-surface mb-2">Мои заявки</p>
                <ul className="space-y-2">
                  {planRequests.map((r) => (
                    <li
                      key={r.id}
                      className="flex items-center justify-between gap-3 p-3 bg-surface-container-low rounded-lg border border-outline-variant/50"
                    >
                      <div>
                        <p className="text-body-sm font-body-sm text-on-surface">
                          Запрос тарифа «{PLAN_OPTIONS.find((o) => o.key === r.requested_plan)?.label ?? r.requested_plan}»
                        </p>
                        <p className="text-label-sm font-label-sm text-on-surface-variant">
                          {new Date(r.created_at).toLocaleDateString('ru-RU')}
                          {r.message ? ` · ${r.message}` : ''}
                        </p>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded text-label-sm font-label-sm shrink-0 ${
                          r.status === 'done'
                            ? 'bg-primary/10 text-primary'
                            : r.status === 'declined'
                            ? 'bg-error-container text-on-error-container'
                            : 'bg-surface-container-high text-on-surface-variant'
                        }`}
                      >
                        {r.status === 'done' ? 'Активен' : r.status === 'declined' ? 'Отклонено' : 'На рассмотрении'}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </SectionCard>
        )}
      </div>
      </div>

      {/* Plan request modal */}
      {requestOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget && !requestSending) setRequestOpen(false);
          }}
        >
          <div className="w-full max-w-md bg-surface-bright rounded-xl shadow-xl border border-outline-variant overflow-hidden">
            <div className="px-6 pt-5 pb-4 border-b border-outline-variant/60">
              <h2 className="text-headline-md font-headline-md text-on-surface">Заявка на смену тарифа</h2>
              <p className="mt-1 text-body-sm font-body-sm text-on-surface-variant">
                Выберите тариф — администратор активирует его после подтверждения.
              </p>
            </div>

            <div className="p-6 space-y-5">
              <div className="space-y-2">
                <label className="block text-label-md font-label-md text-on-surface" htmlFor="req-plan">
                  Новый тариф
                </label>
                <div className="grid grid-cols-1 gap-2">
                  {PLAN_OPTIONS.map((opt) => (
                    <button
                      key={opt.key}
                      type="button"
                      onClick={() => setRequestPlan(opt.key)}
                      className={`flex items-center justify-between px-4 py-3 rounded-lg border text-left transition-colors ${
                        requestPlan === opt.key
                          ? 'border-primary bg-primary/5'
                          : 'border-outline-variant bg-surface hover:border-on-background/30'
                      }`}
                    >
                      <span>
                        <span className="block text-body-md font-body-md text-on-surface">{opt.label}</span>
                        <span className="block text-label-sm font-label-sm text-on-surface-variant">{opt.price}</span>
                      </span>
                      <span
                        className={`material-symbols-outlined text-[18px] ${
                          requestPlan === opt.key ? 'text-primary' : 'text-on-surface-variant/40'
                        }`}
                      >
                        {requestPlan === opt.key ? 'radio_button_checked' : 'radio_button_unchecked'}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="block text-label-md font-label-md text-on-surface" htmlFor="req-message">
                  Комментарий <span className="text-on-surface-variant/60">(опц.)</span>
                </label>
                <textarea
                  id="req-message"
                  rows={3}
                  value={requestMessage}
                  onChange={(e) => setRequestMessage(e.target.value)}
                  placeholder="Например: нужен тариф Про на 3 месяца"
                  className="w-full px-4 py-2.5 bg-surface border border-outline-variant rounded-lg focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-colors text-body-md font-body-md text-on-surface placeholder:text-on-surface-variant/50 resize-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-1">
                <button
                  type="button"
                  onClick={() => setRequestOpen(false)}
                  disabled={requestSending}
                  className="px-4 py-2 bg-surface border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface-variant hover:bg-surface-container transition-colors disabled:opacity-50"
                >
                  Отмена
                </button>
                <button
                  type="button"
                  onClick={sendPlanRequest}
                  disabled={requestSending}
                  className="px-5 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
                >
                  {requestSending ? (
                    <>
                      <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>
                      Отправка...
                    </>
                  ) : (
                    'Отправить заявку'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}