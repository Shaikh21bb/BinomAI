# BINOM AI — System Architecture v1.0

**Документ:** System Architecture  
**Версия:** 1.0  
**Дата:** 2026-07-09  
**Статус:** ✅ Утверждён  
**Автор:** CTO / Solution Architect  
**Связанные документы:** [PRD.md](../01_Product/PRD.md), [AI Architecture.md](./AI%20Architecture.md), [Database Schema.md](./Database%20Schema.md)

---

## 1. Обзор архитектуры

BINOM AI построен по принципу **Layered Monolith с Service Decomposition** — это золотая середина между монолитом (быстро на MVP) и микросервисами (масштабируемо в будущем).

### Архитектурный стиль

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BINOM AI Platform                           │
│                                                                     │
│  ┌─────────────────┐    ┌──────────────────┐   ┌────────────────┐  │
│  │   Frontend       │    │   Backend API    │   │  AI Services   │  │
│  │   (Next.js)      │───▶│   (FastAPI)      │──▶│  (LLM Layer)  │  │
│  │   [Fixed UI]     │    │                  │   │               │  │
│  └─────────────────┘    └──────┬───────────┘   └───────────────┘  │
│                                │                                    │
│                    ┌───────────┼───────────────┐                   │
│                    │           │               │                   │
│             ┌──────▼──┐  ┌────▼────┐  ┌───────▼──┐               │
│             │Supabase  │  │  Redis  │  │  Storage  │               │
│             │(PostgreSQL│  │ (Cache) │  │(S3/Files) │               │
│             │+ Auth)   │  │         │  │           │               │
│             └─────────┘  └─────────┘  └───────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Компоненты системы

### 2.1 Frontend Layer (Зафиксирован)

> ⚠️ **КРИТИЧНО: Frontend не изменяется. Только интеграция через API.**

| Компонент | Технология | Описание |
|-----------|-----------|----------|
| Web Application | Next.js 14 (App Router) | Основное SPA-приложение |
| Language | TypeScript | Типизация |
| Styling | Tailwind CSS | Стилизация |
| State Management | Zustand / React Query | Глобальный стейт и серверный кэш |
| HTTP Client | Axios / fetch | Запросы к Backend API |
| WebSocket | native WS / socket.io-client | Real-time обновления |
| File Upload | React Dropzone | Загрузка PDF/DOCX |
| Rich Text Editor | TipTap / Quill | Редактирование документов |
| PDF Viewer | react-pdf | Просмотр загруженных ТЗ |

**Взаимодействие Frontend ↔ Backend:**
- REST API для CRUD операций
- WebSocket для статуса AI-анализа (real-time)
- Server-Sent Events (SSE) для стриминга AI-ответов в чате

---

### 2.2 Backend API Layer

**Технология:** Python 3.11 + FastAPI 0.110+

#### Структура FastAPI Application

```
binom-backend/
├── app/
│   ├── main.py                    # FastAPI app, middleware, routers
│   ├── config.py                  # Settings, env vars (Pydantic Settings)
│   │
│   ├── api/                       # API Routes (Routers)
│   │   ├── v1/
│   │   │   ├── auth.py            # POST /auth/register, /auth/login, /auth/logout
│   │   │   ├── users.py           # GET/PUT /users/me, /users/me/company
│   │   │   ├── projects.py        # CRUD /projects
│   │   │   ├── documents.py       # POST /documents/upload, GET /documents/{id}
│   │   │   ├── analysis.py        # GET /analysis/{project_id}
│   │   │   ├── chat.py            # POST /chat/{project_id}/message
│   │   │   ├── generation.py      # POST /generate/{project_id}/{doc_type}
│   │   │   ├── export.py          # GET /export/{doc_id}/docx, /pdf
│   │   │   └── websocket.py       # WS /ws/{project_id}
│   │   └── admin/
│   │       └── stats.py           # Admin statistics
│   │
│   ├── core/                      # Core infrastructure
│   │   ├── security.py            # JWT, password hashing
│   │   ├── middleware.py          # Auth, CORS, Rate Limiting
│   │   ├── exceptions.py          # Custom exception handlers
│   │   └── logging.py             # Structured logging
│   │
│   ├── services/                  # Business Logic Layer
│   │   ├── auth_service.py        # Authentication logic
│   │   ├── user_service.py        # User management
│   │   ├── project_service.py     # Project management
│   │   ├── document_service.py    # File processing, storage
│   │   ├── analysis_service.py    # Coordinates AI analysis
│   │   ├── chat_service.py        # Chat session management
│   │   ├── generation_service.py  # Document generation
│   │   ├── export_service.py      # DOCX/PDF export
│   │   └── notification_service.py # Internal notifications
│   │
│   ├── repositories/              # Data Access Layer
│   │   ├── user_repository.py
│   │   ├── project_repository.py
│   │   ├── document_repository.py
│   │   ├── analysis_repository.py
│   │   ├── chat_repository.py
│   │   └── generated_doc_repository.py
│   │
│   ├── models/                    # Pydantic models
│   │   ├── request/               # Input schemas
│   │   └── response/              # Output schemas
│   │
│   ├── ai/                        # AI Integration Layer
│   │   ├── llm_client.py          # LLM client (Gemini + OpenAI fallback)
│   │   ├── document_parser.py     # PDF/DOCX text extraction
│   │   ├── analysis_agent.py      # ТЗ analysis AI agent
│   │   ├── chat_agent.py          # Clarification chat AI agent
│   │   ├── generation_agent.py    # Document generation AI agent
│   │   └── prompt_manager.py      # Prompt templates management
│   │
│   ├── tasks/                     # Celery tasks
│   │   ├── analysis_tasks.py      # Async AI analysis
│   │   ├── generation_tasks.py    # Async document generation
│   │   └── export_tasks.py        # Async file export
│   │
│   └── db/
│       ├── supabase_client.py     # Supabase client singleton
│       └── migrations/            # SQL migrations
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── alembic.ini
```

---

### 2.3 AI Services Layer

Детальное описание в [AI Architecture.md](./AI%20Architecture.md).

**Краткий обзор:**

```
┌──────────────────────────────────────────────┐
│              AI Services Layer               │
│                                              │
│  ┌──────────────┐    ┌─────────────────────┐ │
│  │ Document     │    │  LLM Orchestrator   │ │
│  │ Parser       │───▶│  (LangChain)        │ │
│  │ (PDF/DOCX)   │    │                     │ │
│  └──────────────┘    └──────┬──────────────┘ │
│                             │                 │
│                  ┌──────────┼──────────┐      │
│                  │          │          │      │
│           ┌──────▼──┐ ┌────▼────┐ ┌───▼───┐  │
│           │Analysis │ │ Chat    │ │ Gen   │  │
│           │ Agent   │ │ Agent   │ │ Agent │  │
│           └─────────┘ └─────────┘ └───────┘  │
│                                              │
│  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Gemini 1.5 Pro  │  │   GPT-4o         │  │
│  │  (Primary LLM)   │  │   (Fallback LLM) │  │
│  └──────────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────┘
```

---

### 2.4 Data Layer

#### Supabase (Primary Database)

- **PostgreSQL 15** — основная реляционная БД
- **Supabase Auth** — управление пользователями, JWT
- **Supabase Storage** — хранение PDF/DOCX файлов
- **Row Level Security (RLS)** — изоляция данных компаний
- **Supabase Realtime** — WebSocket события (если нужно)

#### Redis

- **Кэш**: результаты AI-анализа, сессии
- **Celery Broker**: очередь AI-задач
- **Rate Limiting**: подсчёт запросов пользователей

#### File Storage

MVP: **Supabase Storage** (простота)  
Scale: **AWS S3** + **CloudFront CDN**

---

### 2.5 Background Tasks (Celery + Redis)

```
Запрос → FastAPI → Celery Task → Redis Queue → Worker → Суpabase/Storage
```

**AI-задачи выполняются асинхронно:**

| Задача | Триггер | Ожидаемое время |
|--------|---------|-----------------|
| `analyze_document` | Upload завершён | 15–30 сек |
| `generate_document` | Пользователь нажал "Generate" | 30–60 сек |
| `export_to_docx` | Пользователь нажал "Export DOCX" | 5–10 сек |
| `export_to_pdf` | Пользователь нажал "Export PDF" | 5–10 сек |

**FIX #13 — Celery Task Signature Versioning:**

Celery Worker работает в отдельном процессе. При деплое с изменением сигнатуры task — задачи в очереди (ещё сериализованные со старыми аргументами) упадут с TypeError:

```python
# ПРАВИЛЬНО: payload через Pydantic-модель (version-толерантно)

from pydantic import BaseModel
from typing import Optional

class AnalyzeDocumentPayload(BaseModel):
    analysis_id: str
    document_path: str       # FIX #6: путь в Storage, не текст
    company_profile: dict
    prompt_version: str = "v1"
    # Новые поля добавляются с Optional + default
    extra_context: Optional[str] = None  # будущие поля

@celery_app.task(name="analyze_document_v1")
def analyze_document_task(payload_dict: dict):
    payload = AnalyzeDocumentPayload(**payload_dict)  # толерантно к дополнительным полям
    ...

# Правило: при breaking change создавать новый task name:
# analyze_document_v2 — и оставлять v1 работать до истощения очереди
```

**WebSocket обновления:**
- `task:started` — задача начата
- `task:progress` — % выполнения (если есть)
- `task:completed` — задача завершена, данные доступны
- `task:failed` — ошибка, код и сообщение

**⚠️ FIX #1 — Celery → WebSocket Bridge через Redis Pub/Sub:**

Celery Worker работает в отдельном процессе и не имеет доступа к WebSocket-менеджеру FastAPI. Прямой вызов `ws_manager.send()` из Worker — невозможен в production. Решение — Redis Pub/Sub как шина событий:

```
Celery Worker
    │
    │ redis.publish(f"project:{project_id}:events", event_json)
    ▼
Redis Pub/Sub Channel
    │
    │ subscribe
    ▼
FastAPI WebSocket Handler
    │
    │ await websocket.send_json(event)
    ▼
Client
```

```python
# В Celery Worker (tasks/analysis_tasks.py)
import redis.asyncio as aioredis

async def _notify_ws(project_id: str, event: dict):
    """Публикует событие в Redis Pub/Sub — FastAPI WebSocket его получит"""
    r = aioredis.from_url(settings.REDIS_URL, db=2)  # db=2 для Pub/Sub
    await r.publish(f"project:{project_id}:events", json.dumps(event))

# В FastAPI WebSocket handler (api/v1/websocket.py)
async def websocket_endpoint(ws: WebSocket, project_id: str):
    await ws.accept()
    r = aioredis.from_url(settings.REDIS_URL, db=2)
    async with r.pubsub() as pubsub:
        await pubsub.subscribe(f"project:{project_id}:events")
        async for message in pubsub.listen():
            if message["type"] == "message":
                await ws.send_text(message["data"])
```

**Redis DB распределение (изоляция):**
- `db=0` — Celery broker (task queue)
- `db=1` — Cache (AI результаты, сессии)
- `db=2` — Pub/Sub (WebSocket события)
- `db=3` — Rate limiting counters

---

## 3. Архитектурные паттерны

### 3.1 Request-Response Flow

```
Browser (Next.js)
      │
      │ HTTPS REST / WebSocket
      ▼
FastAPI App
      │
      ├── Middleware Stack:
      │     [CORS] → [Auth/JWT] → [Rate Limit] → [Logging]
      │
      ▼
Router → Service → Repository → Supabase (DB/Storage)
                │
                └── AI Service → LLM API (Gemini/OpenAI)
                              → Celery Task Queue
```

### 3.2 Authentication Flow

```
Client                    FastAPI                  Supabase Auth
  │                          │                          │
  │──POST /auth/register────▶│                          │
  │                          │──create_user()──────────▶│
  │                          │◀────────────user_id───────│
  │                          │──create_company()────────▶│(companies table)
  │◀──{access_token, user}───│                          │
  │                          │                          │
  │──POST /auth/login───────▶│                          │
  │                          │──sign_in()──────────────▶│
  │◀──{access_token,         │◀──────────JWT────────────│
  │    refresh_token}────────│                          │
  │                          │                          │
  │──GET /projects (+ JWT)──▶│                          │
  │                          │──verify_jwt()────────────▶│
  │                          │◀──────────user_id─────────│
  │                          │──get_projects(user_id)   │
  │◀──[projects list]────────│                          │
```

### 3.3 Document Analysis Flow (Async)

```
Client                    FastAPI                   Celery Worker           Gemini API
  │                          │                            │                      │
  │──POST /documents/upload──▶│                            │                      │
  │                          │──store file (Storage)─────▶│                      │
  │                          │──create DB record──────────▶│                      │
  │                          │──enqueue analyze_task()────▶│                      │
  │◀──{task_id, status:      │                            │                      │
  │    "processing"}─────────│                            │                      │
  │                          │                            │──parse_document()    │
  │                          │                            │──chunk_text()        │
  │                          │                            │──build_prompt()      │
  │                          │                            │──call LLM()─────────▶│
  │                          │                            │◀────────────response──│
  │                          │                            │──save_analysis()     │
  │                          │                            │──update status "done"│
  │◀──WS: {task:completed}───│◀────────────────────────────│                      │
  │                          │                            │                      │
  │──GET /analysis/{proj_id}─▶│                            │                      │
  │◀──{requirements, risks, gaps}│                         │                      │
```

---

## 4. Технологический стек (полный)

### Backend

| Технология | Версия | Назначение |
|-----------|--------|------------|
| Python | 3.11 | Язык |
| FastAPI | 0.110+ | Web framework |
| Pydantic | 2.x | Валидация данных / схемы |
| Uvicorn | 0.29+ | ASGI сервер |
| Gunicorn | 22.0+ | Process manager (prod) |
| Celery | 5.3+ | Task queue |
| Redis-py | 5.0+ | Redis client |
| Supabase-py | 2.x | Supabase client |
| python-jose | 3.3+ | JWT |
| passlib | 1.7+ | Password hashing (bcrypt) |
| PyMuPDF (fitz) | 1.24+ | PDF parsing |
| python-docx | 1.1+ | DOCX parsing и генерация |
| WeasyPrint | 62+ | HTML → PDF |
| LangChain | 0.2+ | LLM orchestration |
| google-generativeai | 0.5+ | Gemini API |
| openai | 1.x | OpenAI API fallback |
| structlog | 24.x | Structured logging |
| httpx | 0.27+ | Async HTTP client |

### Frontend (только интеграция, не изменяется)

| Технология | Версия | Назначение |
|-----------|--------|------------|
| Next.js | 14 | React framework |
| TypeScript | 5.x | Types |
| Tailwind CSS | 3.x | Styling |

### Infrastructure

| Технология | Назначение |
|-----------|------------|
| Docker | Контейнеризация |
| Docker Compose | Локальная разработка |
| GitHub Actions | CI/CD |
| Supabase (managed) | DB + Auth + Storage |
| Redis (managed) | Queue + Cache |
| Nginx | Reverse proxy (prod) |

---

## 5. Сетевая архитектура

### Development Environment

```
localhost:3000  →  Next.js Dev Server
localhost:8000  →  FastAPI (Uvicorn)
localhost:6379  →  Redis
localhost:5555  →  Celery Flower (monitoring)
Supabase Cloud  →  PostgreSQL + Auth + Storage
```

### Production Environment

```
Internet
   │
   ▼
[Cloudflare CDN] (DDoS protection, SSL)
   │
   ▼
[Nginx Reverse Proxy]
   │
   ├──/api/*  ────▶  [FastAPI] (port 8000)
   │                      │
   │                      ├──▶ [Celery Workers] ←── [Redis]
   │                      │
   │                      ├──▶ [Supabase PostgreSQL]
   │                      │
   │                      └──▶ [Supabase Storage]
   │
   └──/*  ──────▶  [Next.js] (port 3000 / Vercel)
```

### Рекомендованные хостинг-провайдеры для РК

| Компонент | MVP | Production |
|-----------|-----|------------|
| Frontend (Next.js) | Vercel | Vercel / DigitalOcean |
| Backend (FastAPI) | DigitalOcean Droplet | DigitalOcean / AWS |
| PostgreSQL | Supabase (managed) | Supabase / AWS RDS |
| Redis | Upstash (managed) | AWS ElastiCache |
| File Storage | Supabase Storage | AWS S3 |
| CDN | Cloudflare Free | Cloudflare Pro |

*Примечание: Для соответствия требованиям законодательства РК о хранении данных — рассмотреть казахстанские ЦОД (Jusan, Kazinform) на стадии Scale.*

---

## 6. Безопасность архитектуры

### 6.1 Authentication & Authorization

```
┌──────────────────────────────────────────────────────┐
│                  Auth Architecture                   │
│                                                      │
│  [Client]                                            │
│     │ POST /auth/login                              │
│     ▼                                               │
│  [FastAPI] → verify credentials → [Supabase Auth]   │
│     │◀── JWT (access_token) + refresh_token ────────│
│     ▼                                               │
│  [Client stores tokens in httpOnly cookie (secure)] │
│                                                      │
│  Every request:                                      │
│  [Client] → Bearer JWT → [FastAPI]                  │
│                │                                    │
│                ▼                                    │
│  ⚠️ FIX #9 — ЛОКАЛЬНАЯ верификация JWT:             │
│  jwt.decode(token, SUPABASE_JWT_SECRET,             │
│             algorithms=["HS256"])                   │
│  → извлечь user_id, company_id, user_role           │
│  ⚠️ НЕ делать HTTP-запрос к Supabase Auth           │
│     на каждый запрос — это +50–100ms latency        │
│     и единая точка отказа при Supabase outage       │
│                │                                    │
│                ▼                                    │
│  [RLS enforced in DB]                               │
│                                                      │
│  Supabase Auth вызывается ТОЛЬКО для:               │
│  • POST /auth/login (sign_in)                       │
│  • POST /auth/refresh (refresh_token)               │
│  • POST /auth/logout (invalidate session)           │
└──────────────────────────────────────────────────────┘
```

**Реализация локальной верификации (core/security.py):**

```python
import jwt as pyjwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security_scheme = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security_scheme)) -> dict:
    """
    Верифицирует JWT локально — без обращения к Supabase Auth.
    SUPABASE_JWT_SECRET используется для подписи Supabase токенов.
    """
    try:
        payload = pyjwt.decode(
            credentials.credentials,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        return {
            "user_id": payload["sub"],
            "company_id": payload["company_id"],
            "user_role": payload.get("user_role", "user"),
            "email": payload.get("email")
        }
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### 6.2 Row Level Security (RLS) — ключевой принцип

Каждый запрос к БД автоматически фильтруется по `company_id` пользователя:

```sql
-- Пример RLS политики для таблицы projects
CREATE POLICY "Users can only see their company projects"
ON projects
FOR ALL
USING (company_id = auth.jwt() -> 'company_id');
```

Это гарантирует, что **даже при SQL-инъекции** пользователь не увидит чужие данные.

### 6.3 API Security

| Мера | Реализация |
|------|-----------|
| HTTPS only | Cloudflare SSL + HSTS |
| Rate Limiting | 100 req/min per user (Redis counter) |
| Input Validation | Pydantic strict validation |
| SQL Injection | Supabase parameterized queries |
| XSS (frontend) | Next.js автоматически экранирует |
| **XSS (AI output)** | **FIX #23: AI-generated HTML санитизируется через `bleach` (Python) перед сохранением в БД. Белый список тэгов: `p, h1-h4, table, tr, td, th, ul, ol, li, strong, em, br, span`. Блокируется: `script, iframe, object, onclick, onerror, href=javascript:`** |
| CSRF | SameSite cookies + CORS |
| File Upload | MIME type validation + size limit |
| Secrets | Environment variables + Doppler/Vault |

---

## 7. Масштабируемость

### 7.1 MVP → Scale путь

```
MVP (0–100 users):
  Single Docker Compose
  Supabase managed (up to 500MB free)
  Redis on same server or Upstash
  Celery: 2 workers

Scale (100–1000 users):
  Docker Swarm или простой K8s
  Supabase Pro ($25/month)
  Redis: Upstash Pro
  Celery: 5-10 workers

Enterprise (1000+ users):
  Kubernetes (K8s)
  PostgreSQL dedicated
  Redis Cluster
  CDN для файлов (CloudFront)
  Celery: auto-scaling workers
```

### 7.2 Bottlenecks и решения

| Bottleneck | Причина | Решение |
|-----------|---------|---------|
| AI API latency | LLM вызовы занимают 5–30 сек | Async + WebSocket + Streaming |
| Large PDF parsing | 100+ страничные документы | Chunking + parallel processing |
| Concurrent generations | Много пользователей генерируют одновременно | Celery queue + rate limits |
| DB connection pool | Много одновременных запросов | Connection pooling (PgBouncer) |
| File storage I/O | Загрузка/скачивание больших файлов | CDN + S3 multipart upload |
| **RLS на hot paths** | `auth.jwt()` вызывается на каждую строку при SELECT | Backend использует `service_role` key + ручная фильтрация по `company_id`; RLS остаётся как defence-in-depth, но не как единственный guard на горячих путях |
| **PDF Export memory** | FIX #19: WeasyPrint требует системные зависимости (+300MB Docker image) и потребляет 500MB+ RAM на больших документах. Рекомендуется **Gotenberg** (Docker-сервис для PDF). Вызывать через HTTP API: `POST http://gotenberg:3000/forms/chromium/convert/html` в отдельном Celery-воркере с `concurrency=2` |
| **project_summary VIEW** | FIX #24: VIEW с 5 JOIN и GROUP BY пересчитывается на каждый `GET /projects`. До 50 проектов — не ощутимо. При 100+ — кэшировать в Redis (TTL 60 сек) или денормализовать счётчики (`risk_count`, `requirement_count`) в `analysis_results` через trigger |

---

## 8. Мониторинг и наблюдаемость

### 8.1 Logging

**Structured JSON logging** через `structlog`:

```json
{
  "timestamp": "2026-07-09T10:00:00Z",
  "level": "INFO",
  "service": "analysis_service",
  "user_id": "uuid",
  "company_id": "uuid",
  "project_id": "uuid",
  "event": "ai_analysis_started",
  "file_size_mb": 2.4,
  "duration_ms": null
}
```

### 8.2 Метрики

| Метрика | Инструмент |
|---------|-----------|
| Uptime | UptimeRobot (бесплатно) |
| Error tracking | Sentry (free tier) |
| API latency | FastAPI middleware + Grafana |
| Celery queue | Flower (Celery monitoring) |
| DB performance | Supabase Dashboard |
| AI token usage | Custom dashboard (per user/company) |

### 8.3 Alerting

| Событие | Алерт |
|---------|-------|
| Uptime < 99% | Email + Telegram |
| Error rate > 5% | Email + Telegram |
| P95 latency > 5 сек | Email |
| Celery queue > 100 tasks | Email |
| AI API error 5xx | Immediate fallback + Email |

---

## 9. CI/CD Pipeline

```
Developer → Git push → GitHub
                          │
                    GitHub Actions
                          │
          ┌───────────────┼───────────────┐
          │               │               │
     [Lint/Format]  [Run Tests]    [Build Docker]
          │               │               │
          └───────────────┼───────────────┘
                          │
                  [All passed?]
                     │        │
                    YES       NO → Notify developer
                     │
              [Deploy to Staging]
                     │
              [Smoke Tests]
                     │
              [Manual Approval]  ← Product team
                     │
              [Deploy to Production]
                     │
              [Monitor 15 min]
                     │
              [Rollback if needed]
```

---

## 10. Среды развёртывания

| Среда | Назначение | URL |
|-------|-----------|-----|
| **Development** | Локальная разработка | localhost:3000/8000 |
| **Staging** | QA, тестирование перед релизом | staging.binom.ai |
| **Production** | Коммерческая среда | app.binom.ai |

### Environment Variables

```bash
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx  # Backend only, never in Frontend
SUPABASE_JWT_SECRET=xxx        # Fix #9: для локальной JWT верификации без roundtrip к Supabase Auth
                                # Найти в: Supabase Dashboard → Settings → API → JWT Secret

# AI APIs
GEMINI_API_KEY=xxx
OPENAI_API_KEY=xxx

# Redis (Fix #1: раздельные DB по назначению)
REDIS_URL=redis://localhost:6379
REDIS_BROKER_DB=0              # Celery task queue
REDIS_CACHE_DB=1               # AI results cache, sessions
REDIS_PUBSUB_DB=2              # WebSocket event bridge (Celery → FastAPI)
REDIS_RATELIMIT_DB=3           # Rate limiting counters

# Auth
ACCESS_TOKEN_EXPIRE_MINUTES=60  # Fix #9: было 1440 (24ч) — сокращено до 60 мин
REFRESH_TOKEN_EXPIRE_DAYS=30

# App
APP_ENV=production  # development | staging | production
DEBUG=false
LOG_LEVEL=INFO
ALLOWED_ORIGINS=https://app.binom.ai

# File limits
MAX_FILE_SIZE_MB=50
SUPPORTED_FORMATS=pdf,docx
```

---

## 11. Disaster Recovery

### Backup Strategy

| Данные | Частота | Хранение | Метод |
|--------|---------|----------|-------|
| PostgreSQL | Ежедневно | 30 дней | Supabase automated backup |
| Supabase Storage (files) | Еженедельно | 90 дней | AWS S3 versioning |
| Redis | Нет (кэш, не критично) | — | — |
| Конфиг и секреты | Синхронно | Всегда | Vault / GitHub Secrets |

### Recovery Procedure

1. **RTO (Recovery Time Objective):** < 1 час
2. **RPO (Recovery Point Objective):** < 24 часа

При полном падении:
1. Переключить DNS на резервный сервер
2. Восстановить последний backup PostgreSQL
3. Перезапустить Docker containers
4. Проверить AI API доступность
5. Notify клиентов через email

---

## 12. ADR (Architecture Decision Records)

### ADR-001: Почему FastAPI, а не Django/Node.js

**Решение:** FastAPI  
**Причина:** 
- Нативная async поддержка (критично для AI-вызовов)
- Pydantic validation из коробки
- Автогенерация OpenAPI документации
- Быстрее Django для high-throughput API
- Лучшая экосистема для Python AI библиотек

### ADR-002: Почему Supabase, а не чистый PostgreSQL

**Решение:** Supabase  
**Причина:**
- Auth из коробки (экономит 2 недели разработки)
- Storage из коробки
- RLS из коробки
- Realtime из коробки
- Managed = нет DevOps overhead
- Бесплатный tier достаточен для MVP

### ADR-003: Почему Gemini Primary + OpenAI Fallback

**Решение:** Gemini 1.5 Pro primary, GPT-4o fallback  
**Причина:**
- Gemini 1.5 Pro: 1M context window (идеально для больших ТЗ)
- Лучшее соотношение цена/качество у Gemini
- GPT-4o как fallback = надёжность при сбоях Google API
- Многомодальность Gemini (в будущем — анализ чертежей)

### ADR-004: Почему Celery + Redis для async задач

**Решение:** Celery + Redis  
**Причина:**
- AI-задачи занимают 30–60 сек — нельзя блокировать HTTP-запрос
- Celery — проверенное решение для Python
- Redis — простой managed broker
- Visibility через Celery Flower
- Retry механизм из коробки

### ADR-005: Почему Layered Monolith, а не Microservices

**Решение:** Layered Monolith  
**Причина:**
- MVP команда 2–4 человека — микросервисы слишком сложны
- Deployment проще (один Docker image)
- Debugging проще
- Можно вынести в микросервисы позже (AI service в первую очередь)

---

*Документ подготовлен командой BINOM AI. System Architecture v1.0 — утверждён.*  
*Следующий документ: [AI Architecture.md](./AI%20Architecture.md)*
