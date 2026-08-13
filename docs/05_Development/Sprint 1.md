# BINOM AI — Sprint 1: Foundation v1.0

**Документ:** Sprint 1 Plan  
**Версия:** 1.0  
**Дата:** 2026-07-09  
**Статус:** ✅ Утверждён  
**Sprint Duration:** 2 недели (14 дней)  
**Sprint Goal:** Рабочее ядро системы — Auth + Project + Upload + AI Analysis

---

## 1. Sprint Goal

> **"К концу Sprint 1 пользователь может зарегистрироваться, создать проект, загрузить ТЗ и получить AI-анализ с требованиями и рисками."**

**Definition of Done (Sprint Level):**
- Регистрация и вход работают
- Создание проекта работает
- Загрузка PDF/DOCX работает
- Парсинг текста из документа работает
- AI-анализ запускается автоматически
- Результаты анализа отображаются в UI

---

## 2. Backend Tasks

### 2.1 Инфраструктура и проект

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| B1.1 | Инициализация FastAPI проекта (структура папок) | Backend Dev | 2h |
| B1.2 | Настройка Supabase (БД, Storage, Auth) | Backend Dev | 3h |
| B1.3 | Настройка Redis + Celery | Backend Dev | 3h |
| B1.4 | Docker Compose для локальной разработки | DevOps | 2h |
| B1.5 | Environment variables и конфигурация | Backend Dev | 1h |
| B1.6 | Базовая структура логирования (structlog) | Backend Dev | 2h |
| B1.7 | Middleware: CORS, request logging, error handling | Backend Dev | 3h |
| B1.8 | Health check endpoint (`GET /health`) | Backend Dev | 1h |

**Итого Backend Infrastructure:** ~17 часов

---

### 2.2 Database Schema — Миграции

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| DB1.1 | Создать таблицу `companies` + RLS политики | Backend Dev | 2h |
| DB1.2 | Создать таблицу `public.users` + RLS политики | Backend Dev | 2h |
| DB1.3 | Создать таблицу `projects` + RLS политики | Backend Dev | 2h |
| DB1.4 | Создать таблицу `documents` + RLS политики | Backend Dev | 2h |
| DB1.5 | Создать таблицу `analysis_results` + RLS политики | Backend Dev | 2h |
| DB1.6 | Создать `audit_logs` + `ai_usage_logs` | Backend Dev | 2h |
| DB1.7 | Создать функции и триггеры (updated_at, etc.) | Backend Dev | 2h |
| DB1.8 | Создать Storage buckets + политики | Backend Dev | 1h |
| DB1.9 | JWT Custom Claims hook (`auth.custom_access_token_hook`) | Backend Dev | 2h |
| DB1.10 | Seed data: системные шаблоны | Backend Dev | 1h |

**Итого Database:** ~18 часов

---

### 2.3 Auth API

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| A1.1 | `POST /auth/register` — создание пользователя + компании | Backend Dev | 4h |
| A1.2 | `POST /auth/login` — получение токенов | Backend Dev | 2h |
| A1.3 | `POST /auth/logout` — инвалидация токена | Backend Dev | 1h |
| A1.4 | `POST /auth/refresh` — обновление access token | Backend Dev | 2h |
| A1.5 | JWT Middleware (проверка токена на каждый запрос) | Backend Dev | 3h |
| A1.6 | User profile resolver из JWT | Backend Dev | 2h |

**Итого Auth:** ~14 часов

---

### 2.4 Users API

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| U1.1 | `GET /users/me` — профиль пользователя | Backend Dev | 2h |
| U1.2 | `PUT /users/me` — обновление профиля | Backend Dev | 2h |
| U1.3 | `GET /users/me/company` — профиль компании | Backend Dev | 2h |
| U1.4 | `PUT /users/me/company` — обновление компании | Backend Dev | 3h |

**Итого Users:** ~9 часов

---

### 2.5 Projects API

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| P1.1 | `GET /projects` — список с пагинацией + фильтры | Backend Dev | 4h |
| P1.2 | `POST /projects` — создание проекта | Backend Dev | 2h |
| P1.3 | `GET /projects/{id}` — детали проекта | Backend Dev | 2h |
| P1.4 | `PUT /projects/{id}` — обновление | Backend Dev | 2h |
| P1.5 | `DELETE /projects/{id}` — удаление + cascade | Backend Dev | 2h |

**Итого Projects:** ~12 часов

---

### 2.6 Document Upload API

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| D1.1 | `POST /projects/{id}/documents` — загрузка файла | Backend Dev | 4h |
| D1.2 | Валидация файла (тип, размер) | Backend Dev | 2h |
| D1.3 | Загрузка в Supabase Storage | Backend Dev | 3h |
| D1.4 | Запись метаданных в `documents` таблицу | Backend Dev | 1h |
| D1.5 | `GET /projects/{id}/documents/current` | Backend Dev | 2h |
| D1.6 | `GET /documents/{doc_id}/download` — signed URL | Backend Dev | 2h |

**Итого Documents Upload:** ~14 часов

---

### 2.7 Document Parser (AI Preprocessing)

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| PARSE1.1 | Интеграция PyMuPDF для парсинга PDF | AI Dev | 4h |
| PARSE1.2 | Интеграция python-docx для парсинга DOCX | AI Dev | 4h |
| PARSE1.3 | Конвертация таблиц в Markdown | AI Dev | 3h |
| PARSE1.4 | Определение языка документа | AI Dev | 1h |
| PARSE1.5 | Подсчёт токенов (tiktoken) | AI Dev | 1h |
| PARSE1.6 | Celery Task: `parse_document_task` | AI Dev | 3h |
| PARSE1.7 | Сохранение extracted_text в БД | AI Dev | 1h |
| PARSE1.8 | Обработка ошибок парсинга | AI Dev | 2h |

**Итого Parser:** ~19 часов

---

### 2.8 AI Analysis Agent

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| AI1.1 | LLM Client: Gemini 1.5 Pro интеграция | AI Dev | 4h |
| AI1.2 | LLM Client: OpenAI GPT-4o fallback | AI Dev | 3h |
| AI1.3 | Prompt Manager: загрузка и рендеринг промптов | AI Dev | 3h |
| AI1.4 | PromptV1: PROMPT-01 (Analysis Main) | AI Dev | 4h |
| AI1.5 | Analysis Agent: `run()` метод | AI Dev | 6h |
| AI1.6 | Pydantic schemas для AnalysisOutput | AI Dev | 2h |
| AI1.7 | JSON валидация и retry логика | AI Dev | 3h |
| AI1.8 | Celery Task: `analyze_document_task` | AI Dev | 3h |
| AI1.9 | `GET /projects/{id}/analysis` endpoint | Backend Dev | 2h |
| AI1.10 | `POST /projects/{id}/analysis/retry` endpoint | Backend Dev | 2h |
| AI1.11 | Логирование AI usage в `ai_usage_logs` | AI Dev | 2h |

**Итого AI Analysis:** ~34 часа

---

### 2.9 WebSocket (Real-time)

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| WS1.1 | WebSocket endpoint `WS /ws/{project_id}` | Backend Dev | 4h |
| WS1.2 | WebSocket Connection Manager | Backend Dev | 3h |
| WS1.3 | Интеграция WS с Celery Tasks (Pub/Sub через Redis) | Backend Dev | 4h |
| WS1.4 | События: task:started, task:progress, task:completed, task:failed | Backend Dev | 2h |

**Итого WebSocket:** ~13 часов

---

## 3. Frontend Tasks

> Согласно ограничениям проекта, Frontend изменения не производятся в данной итерации. Sprint 1 Backend предоставляет API для существующего Frontend.

**Интеграционные задачи Frontend (если существующий код нуждается в подключении):**

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| FE1.1 | Настройка API клиента (axios/fetch + auth headers) | Frontend Dev | 3h |
| FE1.2 | Настройка JWT refresh interceptor | Frontend Dev | 3h |
| FE1.3 | Подключение WebSocket клиента | Frontend Dev | 4h |
| FE1.4 | Проверка и исправление API endpoints (если UI уже есть) | Frontend Dev | 4h |

---

## 4. Testing Tasks

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| T1.1 | Unit tests: Auth endpoints (register, login, refresh) | QA / Dev | 4h |
| T1.2 | Unit tests: Projects CRUD | QA / Dev | 3h |
| T1.3 | Unit tests: Document upload + validation | QA / Dev | 3h |
| T1.4 | Unit tests: DocumentParser (PDF/DOCX) | QA / Dev | 4h |
| T1.5 | Integration test: Upload → Parse → Analyze (happy path) | QA / Dev | 4h |
| T1.6 | Integration test: WebSocket events (mock Celery) | QA / Dev | 3h |
| T1.7 | Тест на prompt injection защиту | AI Dev | 2h |
| T1.8 | Нагрузочный тест: загрузка 10 документов одновременно | QA | 3h |

**Итого Testing:** ~26 часов

---

## 5. Sprint 1 — Временная шкала

```
НЕДЕЛЯ 1 (Дни 1-7):
────────────────────────────────────────────────────────
Пн  │ B1.1-B1.8: Infrastructure Setup + Docker
    │ DB1.1-DB1.5: Таблицы БД, RLS
────────────────────────────────────────────────────────
Вт  │ DB1.6-DB1.10: Доп. таблицы, seed data
    │ A1.1-A1.6: Auth API
────────────────────────────────────────────────────────
Ср  │ U1.1-U1.4: Users API
    │ P1.1-P1.5: Projects API
────────────────────────────────────────────────────────
Чт  │ D1.1-D1.6: Document Upload API
    │ PARSE1.1-PARSE1.4: Parser (PDF/DOCX начало)
────────────────────────────────────────────────────────
Пт  │ PARSE1.5-PARSE1.8: Parser (завершение)
    │ AI1.1-AI1.3: LLM Client + Prompt Manager
────────────────────────────────────────────────────────
Сб  │ CODE REVIEW + Buffer
────────────────────────────────────────────────────────

НЕДЕЛЯ 2 (Дни 8-14):
────────────────────────────────────────────────────────
Пн  │ AI1.4-AI1.7: Analysis Prompts + Agent
────────────────────────────────────────────────────────
Вт  │ AI1.8-AI1.11: Celery Task + API Endpoints
────────────────────────────────────────────────────────
Ср  │ WS1.1-WS1.4: WebSocket
────────────────────────────────────────────────────────
Чт  │ T1.1-T1.6: Testing
────────────────────────────────────────────────────────
Пт  │ T1.7-T1.8 + Bugfixes + Code Review
    │ Sprint Demo Preparation
────────────────────────────────────────────────────────
Сб  │ SPRINT DEMO + Retrospective
────────────────────────────────────────────────────────
```

---

## 6. Acceptance Criteria

### Функциональные

```
✅ AC-1: Пользователь может зарегистрироваться с email и паролем
✅ AC-2: Пользователь может войти и получить JWT токен
✅ AC-3: Токен автоматически обновляется через refresh
✅ AC-4: Пользователь может создать проект
✅ AC-5: Пользователь может загрузить PDF (< 50 МБ) в проект
✅ AC-6: Пользователь может загрузить DOCX (< 50 МБ) в проект
✅ AC-7: Файл больше 50 МБ отклоняется с понятной ошибкой
✅ AC-8: Файл неправильного типа отклоняется с понятной ошибкой
✅ AC-9: После загрузки автоматически запускается парсинг (< 30 сек)
✅ AC-10: После парсинга автоматически запускается AI анализ
✅ AC-11: WebSocket отправляет события прогресса в реальном времени
✅ AC-12: Результаты анализа содержат summary, requirements, risks
✅ AC-13: Каждое требование имеет ссылку на раздел ТЗ
✅ AC-14: Пользователь видит только проекты своей компании (RLS)
✅ AC-15: API возвращает стандартный JSON формат ошибки
```

### Нефункциональные

```
✅ AC-NF-1: Парсинг PDF 50 МБ завершается < 60 сек
✅ AC-NF-2: AI анализ завершается < 120 сек (P95)
✅ AC-NF-3: API endpoints отвечают < 500ms (без AI задач)
✅ AC-NF-4: Все данные компании изолированы (RLS проверен)
✅ AC-NF-5: Swagger документация доступна на /docs
```

---

## 7. Риски Sprint 1

| Риск | Вероятность | Impact | Митигация |
|------|-------------|--------|-----------|
| Gemini API лимиты (rate limit) | Medium | High | Настроить fallback на GPT-4o + exponential backoff |
| Очень большой PDF > 1M токенов | Low | Medium | Реализовать chunking fallback |
| Суpabase RLS баги при сложных запросах | Medium | High | Тщательное тестирование RLS политик |
| PyMuPDF проблемы с кириллицей | Low | High | Тестировать на 10 реальных ТЗ с кириллицей |
| Celery/Redis не настроен локально | Low | Medium | Docker Compose включает Redis |

---

## 8. Sprint 1 — Итоговый счётчик

| Категория | Часов | Дни (8h) |
|-----------|-------|---------|
| Backend Infrastructure | 17 | 2.1 |
| Database | 18 | 2.3 |
| Auth API | 14 | 1.8 |
| Users API | 9 | 1.1 |
| Projects API | 12 | 1.5 |
| Document Upload | 14 | 1.8 |
| Document Parser | 19 | 2.4 |
| AI Analysis Agent | 34 | 4.3 |
| WebSocket | 13 | 1.6 |
| Testing | 26 | 3.3 |
| **ИТОГО** | **176** | **22** |
| Buffer (20%) | 35 | 4.4 |
| **ИТОГО с буфером** | **211** | **~26 дней** |

> **Примечание:** При команде из 3 разработчиков (1 Backend + 1 AI Dev + 1 QA) — 2 недели реалистичны.

---

*Документ подготовлен командой BINOM AI. Sprint 1 Plan v1.0 — утверждён.*  
*Следующий документ: [Sprint 2.md](./Sprint%202.md)*
