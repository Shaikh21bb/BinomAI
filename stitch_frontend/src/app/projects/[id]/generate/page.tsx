'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { InfoBanner, Spinner } from '@/components/ui';

const DOC_TYPES = [
  {
    key: 'commercial_proposal',
    label: 'Коммерческое предложение',
    icon: 'request_quote',
    hint: 'Стоимость работ, условия оплаты, сроки',
  },
  {
    key: 'tech_spec',
    label: 'Техническая спецификация',
    icon: 'build',
    hint: 'Полный документ на русском и казахском: объект, состав работ, спецификация (таблицы), сроки',
  },
  {
    key: 'cover_letter',
    label: 'Сопроводительное письмо',
    icon: 'mail',
    hint: 'Обращение к заказчику, состав пакета',
  },
];

const DEMO_SAMPLE: Record<string, string> = {
  commercial_proposal: `КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ

Уважаемые коллеги! В ответ на ваше техническое задание направляем коммерческое предложение на выполнение полного комплекса строительно-монтажных работ.

1. Стоимость работ
Общая стоимость составляет 450 000 000 (четыреста пятьдесят миллионов) тенге с учётом НДС 12%.

2. Условия оплаты
Авансовый платёж 30% выплачивается в течение 10 рабочих дней после подписания договора. Остаток — поэтапно по актам выполненных работ.

3. Сроки выполнения
Начало работ — в течение 10 дней после подписания договора. Завершение — в соответствии с графиком производства работ.

(Демо-содержимое. После подключения бэкенда документ генерируется ИИ автоматически.)`,
  tech_spec: `ТЕХНИЧЕСКАЯ СПЕЦИФИКАЦИЯ (НА РУССКОМ ЯЗЫКЕ)

1. Общие сведения об объекте
Выполнение строительно-монтажных работ в полном соответствии с требованиями технического задания и нормами СП РК.

2. Состав работ
- Демонтаж существующих конструкций
- Устройство новых конструкций
- Монтаж кровельного покрытия

3. Спецификация материалов
| № | Наименование | Характеристика | Ед. изм. | Кол-во |
|---|---|---|---|---|
| 1 | Металлочерепица | 0,5 мм | м2 | 789,1 |
| 2 | Доска обрезная | 25х150 мм | м3 | 8,95 |

4. Сроки выполнения
Продолжительность работ — 2 месяца с момента подписания договора.

ТЕХНИКАЛЫҚ СИПАТТАМА (ҚАЗАҚ ТІЛІНДЕ)

1. Объект туралы жалпы мәліметтер
Құрылыс-монтаж жұмыстарын техникалық тапсырма талаптарына және ҚР СП нормаларына толық сәйкес орындау.

2. Жұмыс көлемі
- Қолданыстағы құрылымдарды бөлшектеу
- Жаңа құрылымдарды орнату
- Шатыр жабынын монтаждау

3. Материалдар сипаттамасы
| № | Атауы | Сипаттамасы | Өлш. бірл. | Саны |
|---|---|---|---|---|
| 1 | Металл жабын | 0,5 мм | м2 | 789,1 |
| 2 | Жақтау тақтайы | 25х150 мм | м3 | 8,95 |

4. Орындау мерзімдері
Жұмыстардың ұзақтығы — келісімшартқа қол қойылғаннан бастап 2 ай.

(Демо-содержимое.)`,
  cover_letter: `СОПРОВОДИТЕЛЬНОЕ ПИСЬМО

Уважаемые коллеги!

В соответствии с условиями тендера направляем наше предложение. В состав пакета входят:
• Коммерческое предложение
• Техническая спецификация
• Документы компании

Готовы предоставить дополнительную информацию по запросу.

С уважением,
Команда компании

(Демо-содержимое.)`,
};

interface GeneratedDoc {
  id: string;
  doc_type: string;
  version?: number;
  generation_status?: string;
  created_at?: string;
}

type DocStatus = Record<string, 'idle' | 'generating' | 'ready'>;

export default function ProjectGeneratePage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [status, setStatus] = useState<DocStatus>({});
  const [generated, setGenerated] = useState<GeneratedDoc[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [backendUnavailable, setBackendUnavailable] = useState(false);
  const [preview, setPreview] = useState<{ key: string; label: string; content?: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`/projects/${projectId}/documents/generated`);
        if (!cancelled) setGenerated((res?.data ?? res ?? []) as GeneratedDoc[]);
      } catch {
        if (!cancelled) setBackendUnavailable(true);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const openPreview = async (docType: string) => {
    const label = DOC_TYPES.find((d) => d.key === docType)?.label ?? docType;
    let content: string | undefined;
    try {
      const res = await api.get(`/projects/${projectId}/documents/generated/${docType}/content`);
      const real = (res?.data ?? res ?? {}) as { content_md?: string; content_html?: string };
      content = real.content_md || real.content_html || undefined;
    } catch {
      content = undefined;
    }
    setPreview({ key: docType, label, content });
  };

  const handleGenerate = async (docType: string) => {
    setStatus((prev) => ({ ...prev, [docType]: 'generating' }));
    try {
      const res = await api.post(`/projects/${projectId}/generate`, { doc_type: docType });
      const id = res?.doc_id ?? res?.data?.doc_id;
      if (id) {
        setGenerated((prev) => [
          {
            id,
            doc_type: docType,
            generation_status: res?.generation_status ?? 'generating',
            created_at: new Date().toISOString(),
          },
          ...prev.filter((d) => d.doc_type !== docType),
        ]);
        const listRes = await api.get(`/projects/${projectId}/documents/generated`);
        setGenerated((listRes?.data ?? listRes ?? []) as GeneratedDoc[]);
      }
    } catch {
      setBackendUnavailable(true);
      const label = DOC_TYPES.find((d) => d.key === docType)?.label ?? docType;
      setTimeout(() => setPreview({ key: docType, label }), 600);
    } finally {
      setTimeout(() => {
        setStatus((prev) => ({ ...prev, [docType]: 'ready' }));
      }, 2800);
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-4 md:p-margin-page">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="p-4 md:p-margin-page max-w-4xl mx-auto flex-1 flex flex-col gap-stack-lg w-full">
      <div>
        <h2 className="text-headline-lg font-headline-lg text-on-surface">Генерация документов</h2>
        <p className="text-body-md font-body-md text-on-surface-variant">
          После завершения диалога AI формирует финальные тендерные документы на основе уточнённых данных.
        </p>
      </div>

      {backendUnavailable && (
        <InfoBanner>
          Бэкенд генерации сейчас не подключён. Вы можете просмотреть демо-примеры документов — после подключения
          сервера генерация выполняется автоматически за 10–30 секунд.
        </InfoBanner>
      )}

      {/* Document cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-gutter">
        {DOC_TYPES.map((doc) => {
          const state = status[doc.key] ?? 'idle';
          const docRecord =
            [...generated]
              .filter((g) => g.doc_type === doc.key)
              .sort((a, b) => (b.generation_status === 'ready' ? 1 : 0) - (a.generation_status === 'ready' ? 1 : 0) || (b.version ?? 0) - (a.version ?? 0))[0];
          const isReady = state === 'ready' || docRecord?.generation_status === 'ready';
          return (
            <div
              key={doc.key}
              className="bg-surface-container-lowest border border-outline-variant rounded-lg p-stack-md flex flex-col gap-3 hover:border-on-background/20 transition-colors"
            >
              <div className="w-10 h-10 rounded-lg bg-surface-container-high flex items-center justify-center text-primary">
                <span className="material-symbols-outlined text-[22px]">{doc.icon}</span>
              </div>
              <div className="flex-1">
                <h3 className="text-headline-md font-headline-md text-on-surface mb-1">{doc.label}</h3>
                <p className="text-body-sm font-body-sm text-on-surface-variant">{doc.hint}</p>
              </div>

              <div className="flex flex-col gap-2">
                {docRecord?.generation_status === 'failed' && (
                  <span className="flex items-center gap-1.5 text-label-md font-label-md text-error bg-error-container/40 border border-outline-variant rounded-md px-2.5 py-1 w-fit" title="Попробуйте ещё раз позже — AI-сервис временно недоступен">
                    <span className="material-symbols-outlined text-[16px]">error</span>
                    Ошибка генерации
                  </span>
                )}
                {docRecord && docRecord.generation_status !== 'failed' && (
                  <span className="flex items-center gap-1.5 text-label-md font-label-md text-primary bg-surface-container-high border border-outline-variant rounded-md px-2.5 py-1 w-fit">
                    <span className="material-symbols-outlined text-[16px]" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                    Версия {docRecord.version ?? 1}
                  </span>
                )}

                {state === 'generating' ? (
                  <div className="flex flex-col gap-2 bg-surface-container-low border border-outline-variant rounded-lg p-3">
                    <div className="flex items-center gap-2 text-label-md font-label-md text-on-surface">
                      <span className="material-symbols-outlined animate-spin text-[16px]">sync</span>
                      Генерация ИИ...
                    </div>
                    <div className="w-full h-1.5 bg-surface-container-high rounded-full overflow-hidden">
                      <div className="h-full bg-primary rounded-full shimmer" />
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => (isReady ? openPreview(doc.key) : handleGenerate(doc.key))}                    disabled={status[doc.key] === 'generating'}
                    className={`px-4 py-2 rounded-lg text-label-md font-label-md transition-all ${
                      isReady
                        ? 'bg-surface-bright border border-outline-variant text-on-surface hover:bg-surface-container-low'
                        : 'bg-on-background text-on-primary hover:opacity-90'
                    }`}
                  >
                    {isReady ? (
                      <span className="flex items-center justify-center gap-1.5">
                        <span className="material-symbols-outlined text-[16px]">visibility</span>
                        Просмотр
                      </span>
                    ) : (
                      <span className="flex items-center justify-center gap-1.5">
                        <span className="material-symbols-outlined text-[16px]">auto_awesome</span>
                        Сгенерировать
                      </span>
                    )}
                  </button>
                )}

                {(isReady || backendUnavailable) && (
                  <button
                    onClick={() => openPreview(doc.key)}
                    className="text-label-md font-label-md text-primary hover:underline text-left"
                  >
                    Открыть документ →
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-2 px-4 py-3 bg-surface-container-low border border-outline-variant rounded-lg text-body-sm font-body-sm text-on-surface-variant">
        <span className="material-symbols-outlined text-[18px] text-primary">bolt</span>
        Генерация обычно занимает 10–30 секунд. Если документ уже готов, он откроется без повторной генерации.
      </div>

      {/* Preview modal */}
      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setPreview(null);
          }}
        >
          <div className="w-full max-w-3xl max-h-[85vh] bg-surface-bright rounded-lg shadow-xl border border-outline-variant overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant">
              <div className="flex items-center gap-3">
                <h2 className="text-headline-md font-headline-md text-on-surface">{preview.label}</h2>
                {backendUnavailable && (
                  <span className="px-2 py-0.5 bg-surface-container-high border border-outline-variant text-on-surface-variant rounded text-label-md font-label-md">
                    демо
                  </span>
                )}
              </div>
              <button
                onClick={() => setPreview(null)}
                className="w-8 h-8 flex items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container"
                aria-label="Закрыть"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-8">
              <div
                className="max-w-[640px] mx-auto bg-surface border border-outline-variant rounded-lg p-10 whitespace-pre-line text-body-lg font-body-lg text-on-surface leading-relaxed"
                contentEditable="true"
                suppressContentEditableWarning
              >
                {preview.content ?? DEMO_SAMPLE[preview.key] ?? 'Документ не найден.'}
              </div>
            </div>

            <div className="px-6 py-4 border-t border-outline-variant flex justify-end gap-3">
              <button
                onClick={() => setPreview(null)}
                className="px-4 py-2 bg-surface-bright border border-outline-variant rounded-lg text-label-md font-label-md text-on-surface-variant hover:bg-surface-container-low transition-colors"
              >
                Закрыть
              </button>
              <button
                onClick={() => {
                  setPreview(null);
                  router.push(`/projects/${projectId}/export`);
                }}
                className="px-4 py-2 bg-on-background text-on-primary rounded-lg text-label-md font-label-md hover:opacity-90 transition-opacity flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-[18px]">download</span>
                Экспорт
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}