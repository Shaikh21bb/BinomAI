'use client';

import { useEffect, useRef, useState } from 'react';

const STEPS = [
  {
    icon: 'dashboard',
    title: 'Рабочий стол',
    description: 'Все тендеры компании в одном месте: статусы, номера, контрагенты. Начните с создания нового тендера.',
    hint: 'Совет: нажмите ⌘K, чтобы найти тендер по названию или номеру.',
  },
  {
    icon: 'upload_file',
    title: 'Техническое задание',
    description: 'Загрузите PDF или DOCX с условиями тендера. Документ будет разобран автоматически: реквизиты, требования, предмет закупки.',
  },
  {
    icon: 'psychology',
    title: 'AI-анализ',
    description: 'Искусственный интеллект выделит сроки, требования и риски, а также составит список недостающих данных.',
  },
  {
    icon: 'forum',
    title: 'Уточнения',
    description: 'Ответьте на несколько вопросов в чате. Стоимость, сроки и опыт — всё будет учтено в документах автоматически.',
  },
  {
    icon: 'edit_document',
    title: 'Документы',
    description: 'КП, техническое задание и сопроводительное письмо формируются автоматически — на русском и казахском языках.',
  },
  {
    icon: 'download',
    title: 'Экспорт',
    description: 'Скачайте готовые документы в формате DOCX или PDF. Версии документов сохраняются в проекте.',
  },
];

const STORAGE_KEY = 'binom_onboarding_done';

export function Onboarding() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [auto, setAuto] = useState(false);
  const touchX = useRef<number | null>(null);
  const nextRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const fromStorage = () => {
      try {
        return window.localStorage.getItem(STORAGE_KEY) === '1';
      } catch {
        return true;
      }
    };

    if (!fromStorage()) {
      setAuto(true);
      setOpen(true);
    }

    const onRequest = () => {
      setAuto(false);
      setStep(0);
      setOpen(true);
    };
    window.addEventListener('binom:open-onboarding', onRequest);
    return () => window.removeEventListener('binom:open-onboarding', onRequest);
  }, []);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    nextRef.current?.focus();
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        finish();
      }
      if (e.key === 'ArrowRight') next();
      if (e.key === 'ArrowLeft') prev();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, step, auto]);

  const finish = () => {
    if (auto) {
      try {
        window.localStorage.setItem(STORAGE_KEY, '1');
      } catch {
        /* ignore */
      }
    }
    setOpen(false);
  };

  const next = () => {
    if (step < STEPS.length - 1) setStep((s) => s + 1);
    else finish();
  };

  const prev = () => {
    if (step > 0) setStep((s) => s - 1);
  };

  if (!open) return null;

  const s = STEPS[step];
  const isLast = step === STEPS.length - 1;

  return (
    <div className="fixed inset-0 z-[100] flex items-end md:items-center justify-center">
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-[2px] animate-fade-in"
        onClick={finish}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Обучение"
        onTouchStart={(e) => {
          touchX.current = e.touches[0].clientX;
        }}
        onTouchEnd={(e) => {
          if (touchX.current === null) return;
          const dx = e.changedTouches[0].clientX - touchX.current;
          if (Math.abs(dx) > 50) {
            if (dx < 0) next();
            else prev();
          }
          touchX.current = null;
        }}
        className="relative w-full md:max-w-[480px] bg-surface-container-lowest rounded-t-2xl md:rounded-2xl border-t md:border border-outline-variant shadow-2xl animate-slide-up md:animate-fade-up overflow-hidden"
      >
        {/* Progress */}
        <div className="flex gap-1 px-6 pt-4">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
                i <= step ? 'bg-primary' : 'bg-outline-variant'
              }`}
            />
          ))}
        </div>

        <div className="px-6 pt-6 pb-6 md:pb-8">
          <div key={step} className="animate-fade-up">
            <div className="w-12 h-12 rounded-lg bg-primary/10 text-primary flex items-center justify-center mb-5">
              <span className="material-symbols-outlined text-[24px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                {s.icon}
              </span>
            </div>
            <h2 className="text-headline-md font-headline-md font-bold text-on-surface">{s.title}</h2>
            <p className="mt-3 text-body-md font-body-md text-on-surface-variant leading-relaxed">{s.description}</p>
            {s.hint && (
              <p className="mt-4 flex items-start gap-2 text-body-sm font-body-sm text-on-surface-variant/80">
                <span className="material-symbols-outlined text-[16px] mt-px shrink-0">info</span>
                {s.hint}
              </p>
            )}
          </div>

          {/* Controls */}
          <div className="mt-8 flex items-center justify-between gap-3">
            <button
              onClick={finish}
              className="text-label-md font-label-md text-on-surface-variant hover:text-on-surface transition-colors py-2"
            >
              Пропустить
            </button>
            <div className="flex items-center gap-2">
              <span className="text-label-md font-label-md text-on-surface-variant tabular-nums mr-1">
                {step + 1} / {STEPS.length}
              </span>
              <button
                onClick={prev}
                disabled={step === 0}
                aria-label="Назад"
                className="w-9 h-9 flex items-center justify-center rounded-md border border-outline-variant bg-surface text-on-surface hover:border-on-background/30 transition-colors disabled:opacity-40 disabled:pointer-events-none"
              >
                <span className="material-symbols-outlined text-[18px]">arrow_back</span>
              </button>
              <button
                ref={nextRef}
                onClick={next}
                className="h-9 flex items-center gap-1.5 rounded-md bg-on-background text-on-primary px-4 text-label-md font-label-md hover:opacity-90 transition-opacity"
              >
                {isLast ? 'Завершить' : 'Далее'}
                <span className="material-symbols-outlined text-[18px]">{isLast ? 'check' : 'arrow_forward'}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}