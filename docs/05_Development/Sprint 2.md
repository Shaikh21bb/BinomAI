# BINOM AI — Sprint 2: AI Chat & Document Generation v1.0

**Документ:** Sprint 2 Plan  
**Версия:** 1.0  
**Дата:** 2026-07-09  
**Статус:** ✅ Утверждён  
**Sprint Duration:** 2 недели (14 дней)  
**Sprint Goal:** AI-диалог, генерация КП/ТС/Письма, редактор и экспорт документов

---

## 1. Sprint Goal

> **"К концу Sprint 2 пользователь может пройти полный цикл: AI-диалог → генерация всех 3 документов → редактирование → экспорт в DOCX/PDF."**

**Definition of Done:**
- AI чат задаёт вопросы и собирает данные
- Все 3 типа документов генерируются корректно
- Rich-text редактор работает с автосохранением
- Перегенерация секций работает
- Экспорт DOCX и PDF работает
- Пользователь может оставить оценку документа

---

## 2. Backend Tasks — Sprint 2

### 2.1 Chat Agent API

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| C2.1 | Создать таблицы `chat_sessions` + `chat_messages` (если не в Sprint 1) | Backend Dev | 2h |
| C2.2 | `GET /projects/{id}/chat` — история + сессия | Backend Dev | 3h |
| C2.3 | `POST /projects/{id}/chat/message` — отправка сообщения | Backend Dev | 3h |
| C2.4 | `GET /projects/{id}/chat/status` — готовность к генерации | Backend Dev | 2h |
| C2.5 | Chat Session создаётся автоматически при первом обращении | Backend Dev | 2h |
| C2.6 | Обновление `clarification_context` в JSONB | Backend Dev | 2h |
| C2.7 | Логирование AI usage для chat_messages | Backend Dev | 1h |

**Итого Chat API:** ~15 часов

---

### 2.2 Chat Agent (AI)

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| CA2.1 | PROMPT-02: Генерация уточняющих вопросов | AI Dev | 5h |
| CA2.2 | PROMPT-03: Free Q&A по ТЗ | AI Dev | 4h |
| CA2.3 | PROMPT-04: Обработка ответа + обновление контекста | AI Dev | 5h |
| CA2.4 | PROMPT-09: Оценка готовности к генерации | AI Dev | 3h |
| CA2.5 | Chat Agent: `process_message()` метод | AI Dev | 8h |
| CA2.6 | Определение mode (structured_questioning / free_qa / clarification) | AI Dev | 3h |
| CA2.7 | ClarificationContext: полная Pydantic схема | AI Dev | 2h |
| CA2.8 | Логика накопления ответов в контексте | AI Dev | 4h |
| CA2.9 | SSE Streaming для ответов AI (`GET /chat/stream`) | Backend Dev | 5h |

**Итого Chat Agent:** ~39 часов

---

### 2.3 Document Generation API

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| GEN2.1 | Создать таблицу `generated_documents` (если не создана) | Backend Dev | 1h |
| GEN2.2 | `POST /projects/{id}/generate` — запуск генерации | Backend Dev | 3h |
| GEN2.3 | `GET /projects/{id}/documents/generated` — список генераций | Backend Dev | 2h |
| GEN2.4 | `GET /projects/{id}/documents/generated/{doc_id}` — контент | Backend Dev | 2h |
| GEN2.5 | `PUT /projects/{id}/documents/generated/{doc_id}` — сохранение правок | Backend Dev | 2h |
| GEN2.6 | `POST /.../regenerate-section` — регенерация секции | Backend Dev | 3h |
| GEN2.7 | `POST /.../feedback` — оценка документа | Backend Dev | 2h |

**Итого Generation API:** ~15 часов

---

### 2.4 Document Generation Agent (AI)

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| GA2.1 | PROMPT-05: Генерация КП (все секции) | AI Dev | 12h |
| GA2.2 | PROMPT-06: Генерация ТС (все секции) | AI Dev | 10h |
| GA2.3 | PROMPT-07: Генерация сопроводительного письма | AI Dev | 5h |
| GA2.4 | PROMPT-08: Регенерация отдельной секции | AI Dev | 5h |
| GA2.5 | Generation Agent: `generate()` метод с параллельными секциями | AI Dev | 8h |
| GA2.6 | Document Assembler: сборка HTML из секций | AI Dev | 5h |
| GA2.7 | Celery Tasks: `generate_commercial_proposal_task`, etc. | AI Dev | 5h |
| GA2.8 | Валидация HTML-контента (sanitize XSS) | AI Dev | 3h |
| GA2.9 | Логирование AI usage для каждой генерации | AI Dev | 2h |

**Итого Generation Agent:** ~55 часов

---

### 2.5 Export API (DOCX и PDF)

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| EXP2.1 | Создать таблицу `document_exports` | Backend Dev | 1h |
| EXP2.2 | `POST /documents/generated/{id}/export` — запуск экспорта | Backend Dev | 3h |
| EXP2.3 | `GET /projects/{id}/exports/{export_id}/download` — download URL | Backend Dev | 2h |
| EXP2.4 | DOCX Generation: python-docx из HTML | Backend Dev | 6h |
| EXP2.5 | PDF Generation: WeasyPrint из HTML | Backend Dev | 5h |
| EXP2.6 | Celery Tasks: `export_docx_task`, `export_pdf_task` | Backend Dev | 3h |
| EXP2.7 | Загрузка готового файла в Supabase Storage | Backend Dev | 2h |
| EXP2.8 | Генерация signed download URL (1 час действия) | Backend Dev | 2h |
| EXP2.9 | Брендинг документа: логотип компании + стили | Backend Dev | 4h |

**Итого Export:** ~28 часов

---

### 2.6 Templates API

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| TMPL2.1 | Создать таблицу `document_templates` + seed data | Backend Dev | 2h |
| TMPL2.2 | `GET /templates?doc_type=...` — список шаблонов | Backend Dev | 2h |
| TMPL2.3 | Template Renderer: заполнение шаблона переменными | Backend Dev | 4h |

**Итого Templates:** ~8 часов

---

### 2.7 Расширение WebSocket (Sprint 2 события)

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| WS2.1 | Events: generation_started, generation_progress, generation_completed | Backend Dev | 2h |
| WS2.2 | Events: export_started, export_completed, export_failed | Backend Dev | 2h |
| WS2.3 | Chat completion event: chat_completed (готов к генерации) | Backend Dev | 1h |

**Итого WebSocket Sprint 2:** ~5 часов

---

## 3. Frontend Tasks — Sprint 2

> Работа только с существующим Frontend. Подключение новых API.

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| FE2.1 | Интеграция ChatPanel с `POST /chat/message` + SSE | Frontend Dev | 6h |
| FE2.2 | Typing indicator + StreamingText компонент | Frontend Dev | 3h |
| FE2.3 | Интеграция DocumentGeneratorPanel с `POST /generate` | Frontend Dev | 4h |
| FE2.4 | Progress отображение генерации через WebSocket | Frontend Dev | 3h |
| FE2.5 | Интеграция DocumentEditor с `GET/PUT /generated/{id}` | Frontend Dev | 4h |
| FE2.6 | Автосохранение (debounce 30 сек) | Frontend Dev | 3h |
| FE2.7 | Интеграция ExportButtons с `POST /export` | Frontend Dev | 3h |
| FE2.8 | Скачивание файла по signed URL | Frontend Dev | 2h |
| FE2.9 | FeedbackWidget интеграция | Frontend Dev | 2h |

**Итого Frontend Sprint 2:** ~30 часов

---

## 4. Testing Tasks — Sprint 2

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| T2.1 | Unit tests: Chat message processing | QA / Dev | 4h |
| T2.2 | Unit tests: Clarification context update logic | QA / Dev | 3h |
| T2.3 | Unit tests: Generation prompts (JSON schema validation) | QA / Dev | 4h |
| T2.4 | Unit tests: DOCX export | QA / Dev | 3h |
| T2.5 | Unit tests: PDF export | QA / Dev | 3h |
| T2.6 | Integration test: Full flow (Chat → Generate → Export) | QA | 6h |
| T2.7 | Test: Hallucination check (нет выдуманных данных в КП) | AI Dev | 4h |
| T2.8 | Test: Document quality (ручная проверка экспертом) | Domain Expert | 4h |
| T2.9 | Test: SSE streaming (обрывы соединения, retry) | QA | 3h |
| T2.10 | Нагрузочный тест: 5 параллельных генераций | QA | 3h |

**Итого Testing Sprint 2:** ~37 часов

---

## 5. Sprint 2 — Временная шкала

```
НЕДЕЛЯ 3 (Дни 15-21):
──────────────────────────────────────────────────────────
Пн  │ C2.1-C2.7: Chat Session API
    │ CA2.1-CA2.3: Промпты для чата
──────────────────────────────────────────────────────────
Вт  │ CA2.4-CA2.9: Chat Agent + SSE
──────────────────────────────────────────────────────────
Ср  │ GEN2.1-GEN2.7: Generation API
    │ TMPL2.1-TMPL2.3: Templates
──────────────────────────────────────────────────────────
Чт  │ GA2.1-GA2.4: Промпты генерации (КП, ТС, Письмо)
──────────────────────────────────────────────────────────
Пт  │ GA2.5-GA2.9: Generation Agent + Celery
──────────────────────────────────────────────────────────
Сб  │ CODE REVIEW + Buffer
──────────────────────────────────────────────────────────

НЕДЕЛЯ 4 (Дни 22-28):
──────────────────────────────────────────────────────────
Пн  │ EXP2.1-EXP2.6: Export (DOCX + PDF)
──────────────────────────────────────────────────────────
Вт  │ EXP2.7-EXP2.9 + WS2.1-WS2.3: Export finish + WS
──────────────────────────────────────────────────────────
Ср  │ FE2.1-FE2.9: Frontend Integration
──────────────────────────────────────────────────────────
Чт  │ T2.1-T2.7: Testing
──────────────────────────────────────────────────────────
Пт  │ T2.8-T2.10 + Bugfixes
    │ Expert document review
──────────────────────────────────────────────────────────
Сб  │ SPRINT DEMO + Retrospective
──────────────────────────────────────────────────────────
```

---

## 6. Acceptance Criteria

### Функциональные

```
✅ AC-2.1: AI задаёт вопросы на основе gap-анализа
✅ AC-2.2: Пользователь может ответить на вопрос, AI задаёт следующий
✅ AC-2.3: AI отвечает на произвольный вопрос по содержанию ТЗ
✅ AC-2.4: После 5-10 вопросов AI сообщает о готовности к генерации
✅ AC-2.5: Генерируется Коммерческое предложение (8-12 страниц)
✅ AC-2.6: Генерируется Техническая спецификация (6-10 страниц)
✅ AC-2.7: Генерируется Сопроводительное письмо (1-2 страницы)
✅ AC-2.8: Каждый документ содержит реальные данные из ТЗ и профиля компании
✅ AC-2.9: Нет выдуманных фактов (0 галлюцинаций на тестовом наборе)
✅ AC-2.10: Пользователь может редактировать текст в редакторе
✅ AC-2.11: Изменения автоматически сохраняются
✅ AC-2.12: Пользователь может перегенерировать отдельную секцию
✅ AC-2.13: DOCX файл скачивается и корректно открывается в MS Word
✅ AC-2.14: PDF файл скачивается и корректно отображается
✅ AC-2.15: Документы содержат логотип компании (если загружен)
✅ AC-2.16: Пользователь может оставить оценку 👍/👎
```

### Нефункциональные

```
✅ AC-NF-2.1: Первый ответ AI в чате < 5 сек
✅ AC-NF-2.2: Генерация КП завершается < 90 сек (P95)
✅ AC-NF-2.3: Генерация ТС завершается < 90 сек (P95)
✅ AC-NF-2.4: Генерация письма завершается < 30 сек (P95)
✅ AC-NF-2.5: Экспорт DOCX завершается < 15 сек
✅ AC-NF-2.6: Экспорт PDF завершается < 20 сек
✅ AC-NF-2.7: Автосохранение не блокирует UI редактора
```

---

## 7. Зависимости от Sprint 1

Sprint 2 зависит от следующих завершённых компонентов Sprint 1:

| Зависимость | Используется в |
|------------|----------------|
| Analysis results в БД | Chat Agent (gap analysis) |
| Профиль компании | Document Generation (реквизиты) |
| Document extracted_text | Chat (Free Q&A) |
| WebSocket Infrastructure | Chat SSE, Generation progress |
| LLM Client | Chat Agent, Generation Agent |

---

## 8. Риски Sprint 2

| Риск | Вероятность | Impact | Митигация |
|------|-------------|--------|-----------|
| Промпты КП дают нерелевантный контент | High | High | Итеративное улучшение на реальных ТЗ + Few-shot |
| DOCX стили некорректны (таблицы, шрифты) | Medium | Medium | Шаблонный DOCX файл как основа |
| PDF кириллица не отображается | Low | High | Встроить шрифты (Inter, Arial) в PDF |
| SSE соединение рвётся | Low | Medium | Retry логика на frontend |
| Генерация > 90 сек (timeout) | Medium | High | Прогресс-индикатор + увеличить таймаут Nginx |

---

## 9. Sprint 2 — Итоговый счётчик

| Категория | Часов |
|-----------|-------|
| Chat API | 15 |
| Chat Agent (AI) | 39 |
| Generation API | 15 |
| Generation Agent (AI) | 55 |
| Export | 28 |
| Templates | 8 |
| WebSocket (Sprint 2) | 5 |
| Frontend Integration | 30 |
| Testing | 37 |
| **ИТОГО** | **232** |
| Buffer (20%) | 46 |
| **ИТОГО с буфером** | **~278 ч (35 дней)** |

> **При команде 3 чел:** Sprint 2 занимает 2–2.5 недели. AI Dev — наиболее загружен (55+39 часов чистой AI работы).

---

*Документ подготовлен командой BINOM AI. Sprint 2 Plan v1.0 — утверждён.*  
*Следующий документ: [Sprint 3.md](./Sprint%203.md)*
