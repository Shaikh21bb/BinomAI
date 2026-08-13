'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { InfoBanner } from '@/components/ui';

interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  message_type?: string;
  created_at?: string;
}

interface SessionInfo {
  is_complete?: boolean;
  message_count?: number;
  clarification_context?: Record<string, string>;
}

type BackendMode = 'connecting' | 'live' | 'demo';

const FIELD_LABELS: Record<string, string> = {
  experience: 'Опыт компании',
  price: 'Цена предложения',
  deadline_plan: 'Сроки выполнения',
  licenses: 'Лицензии и допуски',
};

const FIELD_ORDER = ['experience', 'price', 'deadline_plan', 'licenses'];

const DEMO_MESSAGES: Message[] = [
  {
    role: 'assistant',
    content:
      'Здравствуйте! Я проанализировал техническое задание. Для подготовки качественного коммерческого предложения мне нужно уточнить несколько вопросов.\n\nПервый вопрос: какой опыт в строительстве аналогичных объектов есть у вашей компании? Укажите количество реализованных проектов.',
    message_type: 'question',
  },
];

const DEMO_REPLIES = [
  'Отлично, это важная информация. Следующий вопрос — какую ориентировочную цену вы планируете предложить?',
  'Принято. Теперь уточните желаемый срок выполнения работ относительно дедлайна тендера.',
];

export default function ProjectChatPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [messages, setMessages] = useState<Message[]>([]);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [mode, setMode] = useState<BackendMode>('connecting');
  const [banner, setBanner] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`/projects/${projectId}/chat`);
        if (!cancelled) {
          setMessages(res?.messages ?? []);
          setSession(res?.session ?? null);
          setMode('live');
        }
      } catch {
        if (!cancelled) {
          setMessages(DEMO_MESSAGES);
          setSession({ is_complete: false, message_count: 1, clarification_context: {} });
          setMode('demo');
          setBanner('Сервер диалога не подключён — показывается демо-режим. Возможности ИИ будут работать после подключения бэкенда.');
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    const content = input.trim();
    if (!content || isSending) return;

    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content }]);
    setIsSending(true);

    try {
      const res = await api.post(`/projects/${projectId}/chat/message`, { content });
      if (res?.assistant_message) {
        setMessages((prev) => [...prev, res.assistant_message]);
        setSession(res?.session_status ?? null);
        setMode('live');
      } else {
        throw new Error('no reply');
      }
    } catch {
      if (mode !== 'demo') {
        setMode('demo');
        setBanner('Сервер диалога не подключён — показывается демо-режим.');
      }
      const reply = DEMO_REPLIES[messages.filter((m) => m.role === 'user').length % DEMO_REPLIES.length];
      setTimeout(() => {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: reply,
            message_type: 'question',
          },
        ]);
        setIsSending(false);
      }, 900);
      return;
    }
    setIsSending(false);
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-4 md:p-margin-page">
        <span className="material-symbols-outlined animate-spin text-4xl text-primary">sync</span>
      </div>
    );
  }

  const context = session?.clarification_context ?? {};
  const filledCount = FIELD_ORDER.filter((f) => context[f]).length;
  const progress = session?.is_complete ? 100 : Math.round((filledCount / FIELD_ORDER.length) * 100);

  return (
    <div className="flex-1 flex flex-col lg:flex-row min-h-0">
      {/* Chat panel */}
      <div className="flex-1 flex flex-col min-h-0 p-4 md:p-margin-page">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-headline-lg font-headline-lg text-on-surface">AI Диалог</h2>
            {session && (
              <p className="text-label-md font-label-md text-on-surface-variant">
                {session.is_complete
                  ? 'Сбор информации завершён — можно генерировать документы'
                  : `Собрано данных: ${filledCount} из ${FIELD_ORDER.length}`}
              </p>
            )}
          </div>
          {mode === 'demo' && (
            <span className="px-2.5 py-1 bg-surface-container-high border border-outline-variant text-on-surface-variant rounded-md text-label-md font-label-md flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[16px]">science</span>
              Демо
            </span>
          )}
        </div>

        {banner && <div className="mb-4"><InfoBanner>{banner}</InfoBanner></div>}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto flex flex-col gap-4 pr-1 min-h-[280px]">
          {messages.length === 0 && (
            <p className="text-body-md font-body-md text-on-surface-variant text-center mt-10">
              Уточняющие вопросы появятся здесь после загрузки ТЗ.
            </p>
          )}

          {messages.map((msg, i) => {
            const isUser = msg.role === 'user';
            return (
              <div key={msg.id ?? i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                <div className={`flex gap-3 max-w-[85%] sm:max-w-[70%] ${isUser ? 'flex-row-reverse' : ''}`}>
                  {!isUser && (
                    <div className="w-8 h-8 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center shrink-0 ai-pulse-border">
                      <span className="material-symbols-outlined text-[16px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                        assistant
                      </span>
                    </div>
                  )}
                  <div
                    className={`px-4 py-3 rounded-2xl text-body-md font-body-md leading-relaxed whitespace-pre-line shadow-sm ${
                      isUser
                        ? 'bg-on-background text-on-primary rounded-tr-none'
                        : 'bg-surface-container-low text-on-surface border border-outline-variant rounded-tl-none'
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              </div>
            );
          })}

          {isSending && (
            <div className="flex justify-start">
              <div className="flex gap-3 max-w-[85%]">
                <div className="w-8 h-8 rounded-full bg-primary-container flex items-center justify-center shrink-0">
                  <span className="material-symbols-outlined text-[16px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                    assistant
                  </span>
                </div>
                <div className="px-4 py-3 bg-surface-container-low border border-outline-variant rounded-2xl rounded-tl-none flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 bg-on-surface-variant rounded-full animate-bounce" />
                  <span className="w-1.5 h-1.5 bg-on-surface-variant rounded-full animate-bounce [animation-delay:0.15s]" />
                  <span className="w-1.5 h-1.5 bg-on-surface-variant rounded-full animate-bounce [animation-delay:0.3s]" />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSend} className="flex items-center gap-3 mt-4">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Введите ответ или задайте вопрос по ТЗ..."
            className="flex-1 px-4 py-2.5 bg-surface-bright border border-outline-variant rounded-md text-body-md font-body-md text-on-surface focus:outline-none focus:border-on-background focus:ring-2 focus:ring-on-background/5 transition-colors"
          />
          <button
            type="submit"
            disabled={isSending || !input.trim()}
            className="w-11 h-11 flex items-center justify-center bg-on-background text-on-primary rounded-full disabled:opacity-40 hover:opacity-90 transition-opacity"
            aria-label="Отправить"
          >
            <span className="material-symbols-outlined text-[20px]">send</span>
          </button>
        </form>
      </div>

      {/* Context sidebar */}
      <aside className="w-full lg:w-80 border-t lg:border-t-0 lg:border-l border-outline-variant bg-surface-container-low/50 p-4 md:p-margin-page lg:p-6 shrink-0">
        <h3 className="text-label-md font-label-md uppercase tracking-wider text-on-surface-variant mb-4">
          Контекст для генерации
        </h3>

        {FIELD_ORDER.map((key) => {
          const value = context[key];
          const filled = Boolean(value);
          return (
            <div key={key} className="flex items-start justify-between gap-2 mb-2">
              <span
                className={`flex items-center gap-1.5 text-body-md font-body-md ${
                  filled ? 'text-on-surface' : 'text-on-surface-variant'
                }`}
              >
                {filled ? (
                  <span className="material-symbols-outlined text-[16px] text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>
                    check_circle
                  </span>
                ) : (
                  <span className="w-4 h-4 rounded-full border border-outline shrink-0" />
                )}
                {FIELD_LABELS[key]}
              </span>
              <span className="text-body-md font-body-md text-on-surface text-right max-w-[55%]">
                {filled ? value : <span className="text-on-surface-variant">—</span>}
              </span>
            </div>
          );
        })}

        <div className="my-4 h-px bg-outline-variant/60" />

        <div className="flex items-center justify-between mb-2">
          <span className="text-label-md font-label-md text-on-surface-variant">Готовность</span>
          <span className="text-mono-sm font-mono-sm text-on-surface font-medium">{progress}%</span>
        </div>
        <div className="w-full h-1.5 bg-surface-container-high rounded-full overflow-hidden">
          <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
        </div>

        <button
          disabled={!session?.is_complete}
          onClick={() => router.push(`/projects/${projectId}/generate`)}
          className="mt-5 w-full px-4 py-2.5 bg-on-background text-on-primary rounded-lg text-label-md font-label-md disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
        >
          {!session?.is_complete ? 'Продолжайте диалог' : 'Перейти к генерации →'}
        </button>
      </aside>
    </div>
  );
}