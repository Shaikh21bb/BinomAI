'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { api, asError, errorMessage } from '@/lib/api';
import { InfoBanner, SeverityBadge, Spinner } from '@/components/ui';

const DEMO_ANALYSIS: Analysis = {
  tender_type: 'СМР / Строительно-монтажные работы',
  complexity_level: 'Высокая',
  estimated_duration_days: 210,
  llm_model: 'demo',
  executive_summary:
    'Тендер предполагает выполнение полного комплекса строительно-монтажных работ по объекту. Ключевые требования: наличие лицензии I категории, опыт аналогичных работ не менее 5 лет, обеспечение заявки 1% от суммы, жёсткий дедлайн подачи предложений. Наибольшие риски связаны со сроками поставки материалов и подтверждением кадрового состава.',
  technical_requirements: [
    { text: 'Наличие лицензии на строительно-монтажные работы I категории', is_mandatory: true, source_section: '4.1', source_page: 3 },
    { text: 'Опыт выполнения аналогичных работ за последние 5 лет суммарно от 450 млн тенге', is_mandatory: true, source_section: '4.2', source_page: 4 },
    { text: 'Обеспечение заявки в размере 1% от суммы тендера', is_mandatory: true, source_section: '6', source_page: 7 },
  ],
  commercial_requirements: [
    { text: 'Цена предложения не должна превышать плановую сумму 500 млн тенге', is_mandatory: true, source_section: '7.1', source_page: 8 },
    { text: 'Допускается снижение цены, но не ниже себестоимости', source_section: '7.2', source_page: 8 },
  ],
  legal_requirements: [
    { text: 'Отсутствие задолженности по налоговым обязательствам', is_mandatory: true, source_section: '5', source_page: 5 },
  ],
  required_documents: [
    { name: 'Заявка на участие', is_mandatory: true },
    { name: 'Коммерческое предложение', is_mandatory: true },
    { name: 'Лицензия I категории', is_mandatory: true },
    { name: 'Справка о налоговой задолженности', is_mandatory: true },
    { name: 'Справка о наличии кадровых ресурсов' },
  ],
  key_deadlines: [
    { event: 'Конечный срок подачи заявок', date: '2026-09-30', is_hard_deadline: true, source_section: '8' },
    { event: 'Подведение итогов', date: '2026-10-15', source_section: '8' },
  ],
  risks: [
    {
      severity: 'high',
      risk_type: 'safety',
      description: 'Требование лицензии I категории — без неё заявка отклоняется автоматически.',
      mitigation: 'Проверить срок действия лицензии и подтвердить её наличие до подачи.',
    },
    {
      severity: 'medium',
      risk_type: 'deadline',
      description: 'Жёсткий дедлайн 30.09 — подача в последний день не рекомендуется.',
      mitigation: 'Подать заявку за 3–5 дней до дедлайна.',
    },
    {
      severity: 'low',
      risk_type: 'price',
      description: 'Ограничение цены сверху требует точного расчёта себестоимости.',
      mitigation: 'Подготовить сметный расчёт с резервом не менее 5%.',
    },
  ],
  missing_info_from_tender: [
    {
      description: 'Не указана точная дата начала работ',
      clarification_question: 'Уточните плановую дату начала работ',
    },
    {
      description: 'Не определён порядок сдачи-приёмки этапов',
      clarification_question: 'Уточните порядок приёмки этапов работ',
    },
  ],
  missing_company_data: ['Финансовая отчётность за последние 2 года', 'Подтверждение опыта аналогичных работ'],
  created_at: new Date().toISOString(),
};

interface Requirement {
  id?: string;
  text: string;
  category?: string;
  is_mandatory?: boolean;
  source_section?: string;
  source_page?: number;
}

interface Risk {
  id?: string;
  description: string;
  severity: string;
  risk_type?: string;
  mitigation?: string;
  source_section?: string;
}

interface KeyDeadline {
  event: string;
  date?: string;
  is_hard_deadline?: boolean;
  source_section?: string;
}

interface DocumentRequirement {
  name: string;
  is_mandatory?: boolean;
  notes?: string;
}

interface MissingInfo {
  description?: string;
  impact?: string;
  clarification_question?: string;
}

interface Analysis {
  id?: string;
  status?: string;
  error_message?: string;
  executive_summary?: string;
  tender_type?: string;
  complexity_level?: string;
  estimated_duration_days?: number;
  technical_requirements?: Requirement[];
  commercial_requirements?: Requirement[];
  legal_requirements?: Requirement[];
  required_documents?: DocumentRequirement[];
  key_deadlines?: KeyDeadline[];
  risks?: Risk[];
  missing_info_from_tender?: MissingInfo[];
  missing_company_data?: string[];
  llm_model?: string;
  processing_time_ms?: number;
  created_at?: string;
}

function parseList<T>(value: T[] | string | null | undefined): T[] {
  if (Array.isArray(value)) return value;
  if (typeof value === 'string' && value) {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }
  return [];
}

function RequirementSection({ title, items }: { title: string; items: Requirement[] }) {
  if (!items.length) return null;
  return (
    <section>
      <h3 className="text-label-md font-label-md uppercase tracking-wider text-on-surface-variant mb-3">
        {title} ({items.length})
      </h3>
      <div className="flex flex-col gap-2">
        {items.map((req, i) => (
          <div key={req.id ?? i} className="bg-surface-bright border border-outline-variant rounded-lg px-4 py-3 flex gap-3 items-start">
            <span
              className={`material-symbols-outlined text-[18px] mt-0.5 shrink-0 ${
                req.is_mandatory ? 'text-primary' : 'text-on-surface-variant/50'
              }`}
            >
              {req.is_mandatory ? 'check_circle' : 'check'}
            </span>
            <div className="min-w-0">
              <p className="text-body-md font-body-md text-on-surface leading-relaxed">{req.text}</p>
              <p className="text-mono-sm font-mono-sm text-on-surface-variant mt-1">
                {req.source_section ? `Раздел ${req.source_section}` : 'Раздел не указан'}
                {req.source_page ? ` • Стр. ${req.source_page}` : ''}
                {req.is_mandatory && <span className="text-error"> • обязательно</span>}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function ProjectAnalysisPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState('');
  const [isRetrying, setIsRetrying] = useState(false);
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`/analysis/${projectId}`);
        if (!cancelled) {
          setAnalysis(res);
          setNotFound(false);
        }
      } catch (err) {
        if (!cancelled) {
          if (asError(err).status === 404) {
            setNotFound(true);
            setAnalysis(null);
          } else if (asError(err).status === 401 || asError(err).status === 403) {
            setError(errorMessage(err, 'Не удалось загрузить анализ'));
          } else {
            setNotFound(true);
            setAnalysis(null);
          }
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const handleRetry = async () => {
    setIsRetrying(true);
    setError('');
    try {
      await api.post(`/analysis/${projectId}/retry`, {});
      setNotFound(false);
      setIsLoading(true);
      setTimeout(() => {
        window.location.reload();
      }, 2500);
    } catch (err) {
      setError(errorMessage(err, 'Не удалось запустить анализ'));
    } finally {
      setIsRetrying(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-4 md:p-margin-page">
        <Spinner label="Анализирую техническое задание..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 md:p-margin-page max-w-2xl mx-auto flex-1">
        <div className="bg-error-container text-on-error-container rounded-lg p-4 text-body-md font-body-md">{error}</div>
        <div className="mt-4 flex gap-3">
          <button
            onClick={handleRetry}
            disabled={isRetrying}
            className="px-4 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md disabled:opacity-50"
          >
            {isRetrying ? 'Запуск...' : 'Повторить анализ'}
          </button>
          <Link href={`/projects/${projectId}/document`} className="px-4 py-2 bg-surface-bright border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface">
            Назад к ТЗ
          </Link>
        </div>
      </div>
    );
  }

  if (notFound || !analysis) {
    return (
      <div className="p-4 md:p-margin-page max-w-2xl mx-auto flex-1">
        {!demoMode && (
          <InfoBanner className="mb-4">
            Сервер анализа сейчас не подключён. {!error && 'Анализ ещё не выполнен.'}
          </InfoBanner>
        )}
        <div className="bg-surface-container-lowest border border-outline-variant rounded-lg p-10 flex flex-col items-center text-center gap-4">
          <div className="w-16 h-16 rounded-full bg-surface-container-high flex items-center justify-center">
            <span className="material-symbols-outlined text-3xl text-primary">psychology</span>
          </div>
          <div>
            <h3 className="text-headline-md font-headline-md text-on-surface mb-1">
              {demoMode ? 'Демо-анализ' : 'Анализ ещё не выполнен'}
            </h3>
            <p className="text-body-md font-body-md text-on-surface-variant max-w-sm">
              {demoMode
                ? 'Пример того, как будет выглядеть полный AI-анализ технического задания.'
                : 'Сначала загрузите техническое задание, затем запустите AI-анализ документа.'}
            </p>
          </div>
          <div className="flex gap-3">
            {!demoMode && (
              <button
                onClick={() => {
                  setDemoMode(true);
                  setAnalysis(DEMO_ANALYSIS);
                }}
                className="px-4 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-[18px]">science</span>
                Показать демо-анализ
              </button>
            )}
            <Link
              href={`/projects/${projectId}/document`}
              className="px-4 py-2 bg-surface-bright border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface hover:bg-surface-container-low transition-colors"
            >
              Загрузить ТЗ
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const tech = parseList<Requirement>(analysis.technical_requirements);
  const comm = parseList<Requirement>(analysis.commercial_requirements);
  const legal = parseList<Requirement>(analysis.legal_requirements);
  const risks = parseList<Risk>(analysis.risks);
  const deadlines = parseList<KeyDeadline>(analysis.key_deadlines);
  const docs = parseList<DocumentRequirement>(analysis.required_documents);
  const missing = parseList<MissingInfo>(analysis.missing_info_from_tender);
  const missingCompany = analysis.missing_company_data;

  return (
    <div className="p-4 md:p-margin-page max-w-4xl mx-auto flex-1 flex flex-col gap-stack-lg w-full">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-headline-lg font-headline-lg text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>
              assistant
            </span>
            AI Анализ технического задания
          </h2>
        </div>
        <button
          onClick={handleRetry}
          disabled={isRetrying}
          className="px-3 py-1.5 border border-outline rounded-lg text-label-md font-label-md text-on-surface-variant hover:bg-surface-container-low disabled:opacity-50 flex items-center gap-2"
        >
          <span className="material-symbols-outlined text-[16px]">refresh</span>
          {isRetrying ? 'Запуск...' : 'Обновить'}
        </button>
      </div>

      {/* Meta badges */}
      <div className="flex flex-wrap gap-2">
        {analysis.tender_type && (
          <span className="px-3 py-1 bg-surface-container-low border border-outline-variant rounded-md text-label-md font-label-md text-on-surface-variant">
            Тип: {analysis.tender_type}
          </span>
        )}
        {analysis.complexity_level && (
          <span
            className={`px-3 py-1 rounded-md text-label-md font-label-md border ${
              String(analysis.complexity_level).toLowerCase().includes('high') || String(analysis.complexity_level).toLowerCase().includes('высок')
                ? 'bg-red-50 text-red-800 border-red-200'
                : String(analysis.complexity_level).toLowerCase().includes('low') || String(analysis.complexity_level).toLowerCase().includes('низ')
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : 'bg-amber-50 text-amber-900 border-amber-200'
            }`}
          >
            Сложность: {analysis.complexity_level}
          </span>
        )}
        {typeof analysis.estimated_duration_days === 'number' && analysis.estimated_duration_days > 0 && (
          <span className="px-3 py-1 bg-surface-container-low border border-outline-variant rounded-md text-label-md font-label-md text-on-surface-variant">
            Срок: ≈ {analysis.estimated_duration_days} дн.
          </span>
        )}
        {analysis.llm_model && (
          <span className="px-3 py-1 bg-surface-container-low border border-outline-variant rounded-md text-mono-sm font-mono-sm text-on-surface-variant">
            {analysis.llm_model}
          </span>
        )}
      </div>

      {/* Executive summary */}
      {analysis.executive_summary && (
        <section className="bg-surface-container-lowest border border-outline-variant rounded-lg p-stack-md">
          <h3 className="text-label-md font-label-md uppercase tracking-wider text-on-surface-variant mb-3">Резюме</h3>
          <p className="text-body-lg font-body-lg text-on-surface leading-relaxed">{analysis.executive_summary}</p>
        </section>
      )}

      {/* Requirements */}
      <div className="flex flex-col gap-stack-md">
        <RequirementSection title="Технические требования" items={tech} />
        <RequirementSection title="Коммерческие требования" items={comm} />
        <RequirementSection title="Юридические требования" items={legal} />
      </div>

      {/* Key deadlines */}
      {deadlines.length > 0 && (
        <section>
          <h3 className="text-label-md font-label-md uppercase tracking-wider text-on-surface-variant mb-3">
            Ключевые сроки
          </h3>
          <div className="flex flex-col gap-2">
            {deadlines.map((d, i) => (
              <div key={i} className="bg-surface-bright border border-outline-variant rounded-lg px-4 py-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="material-symbols-outlined text-on-surface-variant text-[18px] shrink-0">event</span>
                  <p className="text-body-md font-body-md text-on-surface truncate">{d.event}</p>
                </div>
                <span className="text-mono-sm font-mono-sm text-on-surface-variant shrink-0">
                  {d.date}
                  {d.is_hard_deadline && <span className="text-error ml-1">• жёсткий</span>}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Required documents */}
      {docs.length > 0 && (
        <section>
          <h3 className="text-label-md font-label-md uppercase tracking-wider text-on-surface-variant mb-3">
            Необходимые документы
          </h3>
          <div className="flex flex-wrap gap-2">
            {docs.map((doc, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-2 px-3 py-2 bg-surface-bright border border-outline-variant rounded-lg text-body-md font-body-md text-on-surface"
              >
                <span className={`material-symbols-outlined text-[18px] ${doc.is_mandatory ? 'text-primary' : 'text-on-surface-variant/50'}`}>
                  description
                </span>
                {doc.name}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Risks */}
      {risks.length > 0 && (
        <section>
          <h3 className="text-label-md font-label-md uppercase tracking-wider text-on-surface-variant mb-3">Риски</h3>
          <div className="flex flex-col gap-2">
            {risks.map((risk, i) => (
              <div key={risk.id ?? i} className="bg-surface-bright border border-outline-variant rounded-lg px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <SeverityBadge severity={risk.severity} />
                    <p className="text-body-md font-body-md text-on-surface">{risk.description}</p>
                  </div>
                </div>
                {(risk.mitigation || risk.risk_type) && (
                  <div className="mt-2 flex flex-col sm:flex-row sm:items-center gap-2 pl-0">
                    {risk.risk_type && (
                      <span className="px-2.5 py-1 bg-surface-container-low rounded text-mono-sm font-mono-sm text-on-surface-variant w-fit">
                        {risk.risk_type}
                      </span>
                    )}
                    {risk.mitigation && (
                      <p className="text-body-sm font-body-sm text-on-surface-variant flex items-center gap-2">
                        <span className="material-symbols-outlined text-[16px] text-primary shrink-0">lightbulb</span>
                        Рекомендация: {risk.mitigation}
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Gaps */}
      {(missing.length > 0 || (missingCompany ?? []).length > 0) && (
        <section>
          <h3 className="text-label-md font-label-md uppercase tracking-wider text-on-surface-variant mb-3">
            Gap Analysis
          </h3>
          <div className="flex flex-col gap-2">
            {missing.map((m, i) => (
              <div key={i} className="bg-surface-container-low border border-outline-variant rounded-lg px-4 py-3 flex flex-col gap-1">
                <p className="text-body-md font-body-md text-on-surface flex items-start gap-2">
                  <span className="material-symbols-outlined text-[18px] text-on-surface-variant shrink-0">query_stats</span>
                  {m.description ?? (typeof m === 'string' ? m : 'Недостающая информация')}
                </p>
                {m.clarification_question && (
                  <p className="text-body-sm font-body-sm text-on-surface-variant pl-8">
                    Уточняющий вопрос: {m.clarification_question}
                  </p>
                )}
              </div>
            ))}
            {(missingCompany ?? []).map((item, i) => {
              if (typeof item !== 'string') return null;
              return (
                <div key={`c-${i}`} className="bg-surface-container-low border border-outline-variant rounded-lg px-4 py-3 flex items-start gap-2">
                  <span className="material-symbols-outlined text-[18px] text-primary shrink-0">person_search</span>
                  <span className="text-body-md font-body-md text-on-surface">{item}</span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Next step */}
      <div className="sticky bottom-4 flex justify-end pt-2">
        <Link
          href={`/projects/${projectId}/chat`}
          className="flex items-center gap-2 px-5 py-2.5 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity shadow-lg"
        >
          Перейти к диалогу
          <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
        </Link>
      </div>
    </div>
  );
}