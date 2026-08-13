# BINOM AI — Deployment Guide v1.0

**Документ:** Deployment Guide  
**Версия:** 1.0  
**Дата:** 2026-07-09  
**Статус:** ✅ Утверждён  
**Автор:** DevOps / CTO  
**Связанные документы:** [System Architecture.md](../02_Architecture/System%20Architecture.md), [Test Plan.md](./Test%20Plan.md)

---

## 1. Обзор архитектуры развёртывания

```
┌──────────────────────────────────────────────────────────────────────┐
│                     PRODUCTION ENVIRONMENT                           │
│                                                                      │
│  ┌──────────────────┐   ┌────────────────────┐                      │
│  │   FRONTEND       │   │   BACKEND (API)     │                      │
│  │   Vercel         │   │   Railway.app        │                      │
│  │   binom.ai       │◄──►  api.binom.ai:8000  │                      │
│  └──────────────────┘   └─────────┬──────────┘                      │
│                                    │                                  │
│                    ┌───────────────┼───────────────┐                 │
│                    │               │               │                 │
│             ┌──────▼──────┐ ┌──────▼───────┐  ┌───▼──────────┐      │
│             │   Supabase  │ │    Redis      │  │  Celery      │      │
│             │   (DB+Auth+ │ │   Railway     │  │  Workers     │      │
│             │   Storage)  │ │   6379        │  │  Railway     │      │
│             └─────────────┘ └──────────────┘  └──────────────┘      │
│                                                                      │
│  External APIs:                                                      │
│  ├── Google AI Studio (Gemini 1.5 Pro)                              │
│  └── OpenAI (GPT-4o fallback)                                        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Требования к инфраструктуре

### 2.1 Production Stack

| Компонент | Сервис | Tier | Стоимость/мес |
|---------|--------|------|--------------|
| **Frontend** | Vercel | Pro | $20 |
| **Backend API** | Railway | Starter | $20 |
| **Celery Workers** | Railway | Starter | $20 |
| **Redis** | Railway | Starter | $10 |
| **Database + Auth + Storage** | Supabase | Pro | $25 |
| **Monitoring** | Sentry | Free | $0 |
| **Domain** | GoDaddy/Namecheap | — | $15/год |
| **Email** | Resend.com | Free (100/день) | $0–$20 |
| **ИТОГО** | | | ~$95–$115/мес |

### 2.2 Минимальные требования (MVP)

| Ресурс | Minimum | Recommended |
|--------|---------|-------------|
| CPU (API) | 0.5 vCPU | 1 vCPU |
| RAM (API) | 512 MB | 1 GB |
| CPU (Worker) | 0.5 vCPU | 1 vCPU |
| RAM (Worker) | 512 MB | 1 GB |
| Storage | 50 GB | 200 GB |
| Redis Memory | 100 MB | 500 MB |

---

## 3. Environments

### 3.1 Конфигурация окружений

| Параметр | Development | Staging | Production |
|---------|------------|---------|-----------|
| Backend URL | localhost:8000 | staging.api.binom.ai | api.binom.ai |
| Frontend URL | localhost:3000 | staging.binom.ai | binom.ai |
| Database | Supabase Dev project | Supabase Staging project | Supabase Prod project |
| Redis | localhost:6379 | Railway Redis (staging) | Railway Redis (prod) |
| LLM | Gemini/GPT-4o (лимиты) | Gemini/GPT-4o (лимиты) | Gemini/GPT-4o (production keys) |
| Log Level | DEBUG | INFO | WARNING |
| Celery concurrency | 1 | 2 | 4 |

---

## 4. Environment Variables

### 4.1 Backend `.env`

```bash
# === APP SETTINGS ===
APP_NAME=BINOM AI
APP_ENV=production                    # development | staging | production
APP_VERSION=1.0.0
DEBUG=false

# === DATABASE (Supabase) ===
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIs...     # Только для backend (service role)
DATABASE_URL=postgresql+asyncpg://postgres:password@db.xxxx.supabase.co:5432/postgres

# === AUTH ===
JWT_SECRET=your-super-secret-jwt-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440        # 24 часа
REFRESH_TOKEN_EXPIRE_DAYS=30

# === REDIS ===
REDIS_URL=redis://default:password@railway.internal:6379/1

# === CELERY ===
CELERY_BROKER_URL=redis://default:password@railway.internal:6379/0
CELERY_RESULT_BACKEND=redis://default:password@railway.internal:6379/0
CELERY_WORKER_CONCURRENCY=4

# === AI APIS ===
GOOGLE_AI_API_KEY=AIza...                # Gemini 1.5 Pro
OPENAI_API_KEY=sk-...                   # GPT-4o fallback

# Primary и Fallback модели
PRIMARY_LLM_MODEL=gemini-1.5-pro
FALLBACK_LLM_MODEL=gpt-4o

# LLM параметры
LLM_MAX_RETRIES=3
LLM_TIMEOUT_SECONDS=120

# === STORAGE ===
STORAGE_BUCKET_TENDER_DOCS=tender-documents
STORAGE_BUCKET_COMPANY_ASSETS=company-assets
STORAGE_BUCKET_EXPORTS=exported-documents
STORAGE_SIGNED_URL_EXPIRY=3600         # 1 час

# === FILE UPLOAD ===
MAX_UPLOAD_SIZE_MB=50
ALLOWED_MIME_TYPES=application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document

# === EMAIL (Resend) ===
RESEND_API_KEY=re_...
EMAIL_FROM=noreply@binom.ai
EMAIL_FROM_NAME=BINOM AI

# === MONITORING ===
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
SENTRY_ENVIRONMENT=production

# === RATE LIMITING ===
RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_AI_OPS=10/minute
RATE_LIMIT_UPLOADS=5/minute
RATE_LIMIT_AUTH=20/minute

# === CORS ===
CORS_ORIGINS=https://binom.ai,https://www.binom.ai,https://staging.binom.ai
```

### 4.2 Frontend `.env.local`

```bash
NEXT_PUBLIC_API_URL=https://api.binom.ai/api/v1
NEXT_PUBLIC_WS_URL=wss://api.binom.ai/api/v1/ws
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
NEXT_PUBLIC_APP_NAME=BINOM AI
NEXT_PUBLIC_SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
```

---

## 5. Docker конфигурация

### 5.1 Dockerfile (Backend)

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Системные зависимости (для PyMuPDF, WeasyPrint)
RUN apt-get update && apt-get install -y \
    libmupdf-dev \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код
COPY . .

# Не запускать от root
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### 5.2 Docker Compose (Local Development)

```yaml
# docker-compose.yml
version: "3.9"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=development
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
    env_file:
      - .env.local
    volumes:
      - ./app:/app/app    # Hot reload
    depends_on:
      - redis
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  
  celery_worker:
    build: .
    environment:
      - APP_ENV=development
      - REDIS_URL=redis://redis:6379/0
    env_file:
      - .env.local
    depends_on:
      - redis
    command: celery -A app.celery_app worker --loglevel=info --concurrency=1
  
  celery_flower:
    build: .
    ports:
      - "5555:5555"
    env_file:
      - .env.local
    depends_on:
      - redis
    command: celery -A app.celery_app flower --port=5555
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

### 5.3 Запуск локально

```bash
# Первый запуск
cp .env.example .env.local
# Заполнить .env.local своими ключами

# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps

# Применить миграции БД
docker-compose exec api python -m app.db.migrate

# Смотреть логи
docker-compose logs -f api
docker-compose logs -f celery_worker

# Доступ к Flower (Celery monitor)
open http://localhost:5555

# Swagger UI
open http://localhost:8000/docs

# Остановить
docker-compose down
```

---

## 6. Railway Deployment

### 6.1 Деплой Backend API

```bash
# Установить Railway CLI
npm install -g @railway/cli

# Логин
railway login

# Создать проект
railway init --name binom-ai-backend

# Настроить переменные окружения
railway variables set SUPABASE_URL=https://...
railway variables set SUPABASE_SERVICE_KEY=...
railway variables set GOOGLE_AI_API_KEY=...
# ... и т.д. все переменные

# Деплой
railway up

# Привязать домен
railway domain add api.binom.ai
```

### 6.2 Деплой Celery Worker

```bash
# Создать отдельный сервис для worker
railway service create --name celery-worker

# Настроить start command
railway variables set START_COMMAND="celery -A app.celery_app worker --loglevel=info --concurrency=4"

# Деплой
railway up --service celery-worker
```

### 6.3 railway.json

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "./Dockerfile"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

---

## 7. CI/CD Pipeline (GitHub Actions)

### 7.1 Полный пайплайн

```yaml
# .github/workflows/deploy.yml

name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: '3.11'

jobs:
  # ─── JOB 1: Lint & Type Check ────────────────────────────────────────
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dev dependencies
        run: pip install ruff mypy
      
      - name: Ruff lint
        run: ruff check app/
      
      - name: Ruff format check
        run: ruff format --check app/
      
      - name: Mypy type check
        run: mypy app/ --ignore-missing-imports

  # ─── JOB 2: Unit Tests ───────────────────────────────────────────────
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      
      - name: Run unit tests
        run: |
          pytest tests/unit/ -v \
            --cov=app \
            --cov-report=xml \
            --cov-fail-under=70 \
            --timeout=60
        env:
          APP_ENV: testing
          SUPABASE_URL: ${{ secrets.SUPABASE_TEST_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_TEST_KEY }}
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4

  # ─── JOB 3: Integration Tests (только на PR в main) ──────────────────
  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    needs: unit-tests
    if: github.base_ref == 'main' || github.ref == 'refs/heads/main'
    services:
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v4
      
      - name: Run integration tests
        run: |
          pytest tests/integration/ -v \
            --timeout=300 \
            -m "not slow"
        env:
          APP_ENV: testing
          REDIS_URL: redis://localhost:6379/0
          SUPABASE_URL: ${{ secrets.SUPABASE_STAGING_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_STAGING_KEY }}
          GOOGLE_AI_API_KEY: ${{ secrets.GOOGLE_AI_API_KEY }}

  # ─── JOB 4: Docker Build ─────────────────────────────────────────────
  docker-build:
    name: Docker Build
    runs-on: ubuntu-latest
    needs: [unit-tests]
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_TOKEN }}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: ${{ github.ref == 'refs/heads/main' }}
          tags: |
            binomai/backend:latest
            binomai/backend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ─── JOB 5: Deploy Staging ────────────────────────────────────────────
  deploy-staging:
    name: Deploy to Staging
    runs-on: ubuntu-latest
    needs: [docker-build, integration-tests]
    if: github.ref == 'refs/heads/develop'
    environment:
      name: staging
      url: https://staging.api.binom.ai
    steps:
      - name: Deploy to Railway Staging
        uses: railway/deploy-action@v1
        with:
          railway-token: ${{ secrets.RAILWAY_TOKEN_STAGING }}
          service: binom-ai-api-staging

  # ─── JOB 6: Deploy Production ─────────────────────────────────────────
  deploy-production:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: [docker-build, integration-tests]
    if: github.ref == 'refs/heads/main'
    environment:
      name: production
      url: https://api.binom.ai
    steps:
      - name: Deploy API to Railway
        uses: railway/deploy-action@v1
        with:
          railway-token: ${{ secrets.RAILWAY_TOKEN_PROD }}
          service: binom-ai-api
      
      - name: Deploy Worker to Railway
        uses: railway/deploy-action@v1
        with:
          railway-token: ${{ secrets.RAILWAY_TOKEN_PROD }}
          service: celery-worker
      
      - name: Run Database Migrations
        run: |
          curl -X POST https://api.binom.ai/internal/migrate \
            -H "Authorization: Bearer ${{ secrets.INTERNAL_TOKEN }}"
      
      - name: Smoke Test Production
        run: |
          STATUS=$(curl -s https://api.binom.ai/health | jq -r '.status')
          if [ "$STATUS" != "healthy" ]; then
            echo "Production health check failed!"
            exit 1
          fi
          echo "Production is healthy ✅"
      
      - name: Notify Team (Telegram)
        if: always()
        run: |
          MESSAGE="🚀 BINOM AI v${{ github.sha }} deployed to Production"
          curl -X POST "https://api.telegram.org/bot${{ secrets.TG_BOT_TOKEN }}/sendMessage" \
            -d "chat_id=${{ secrets.TG_CHAT_ID }}&text=$MESSAGE"
```

---

## 8. Supabase Setup

### 8.1 Создание Production проекта

```bash
# Установить Supabase CLI
brew install supabase/tap/supabase

# Логин
supabase login

# Создать production проект (через UI: app.supabase.com)
# Регион: выбрать ближайший к Казахстану (Singapore или Frankfurt)

# Применить миграции
supabase db push --db-url "postgresql://postgres:password@db.xxxx.supabase.co:5432/postgres"

# Проверить миграции
supabase db diff

# Seed данные (системные шаблоны)
supabase db seed
```

### 8.2 Supabase Storage Buckets

```sql
-- Создать через Supabase SQL Editor:

-- 1. Bucket для логотипов компаний
INSERT INTO storage.buckets (id, name, public)
VALUES ('company-assets', 'company-assets', true);

-- 2. Bucket для ТЗ (приватный)
INSERT INTO storage.buckets (id, name, public)
VALUES ('tender-documents', 'tender-documents', false);

-- 3. Bucket для экспортов (приватный, временные файлы)
INSERT INTO storage.buckets (id, name, public)
VALUES ('exported-documents', 'exported-documents', false);
```

### 8.3 Edge Functions (если нужно)

```bash
# Создать Edge Function для custom JWT hook
supabase functions new custom-access-token-hook

# Деплой
supabase functions deploy custom-access-token-hook
```

---

## 9. Vercel Deployment (Frontend)

### 9.1 Настройка

```bash
# Установить Vercel CLI
npm install -g vercel

# Деплой
cd frontend/
vercel --prod

# Настроить environment variables в Vercel Dashboard:
# NEXT_PUBLIC_API_URL = https://api.binom.ai/api/v1
# NEXT_PUBLIC_WS_URL = wss://api.binom.ai/api/v1/ws
# NEXT_PUBLIC_SUPABASE_URL = ...
# NEXT_PUBLIC_SUPABASE_ANON_KEY = ...
```

### 9.2 vercel.json

```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "regions": ["fra1"],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" }
      ]
    }
  ]
}
```

---

## 10. Monitoring Setup

### 10.1 Sentry (Error Tracking)

```python
# app/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    environment=settings.APP_ENV,
    integrations=[
        FastApiIntegration(transaction_style="endpoint"),
        CeleryIntegration(monitor_beat_tasks=True),
    ],
    traces_sample_rate=0.1,    # 10% трейсов
    profiles_sample_rate=0.05, # 5% профилей
    send_default_pii=False     # Не отправлять PII
)
```

### 10.2 Prometheus Metrics

```python
# app/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Счётчики
requests_total = Counter(
    "binom_requests_total",
    "Total requests",
    ["method", "endpoint", "status_code"]
)

ai_operations_total = Counter(
    "binom_ai_operations_total", 
    "Total AI operations",
    ["operation", "model", "success"]
)

# Гистограммы
request_duration = Histogram(
    "binom_request_duration_seconds",
    "Request duration",
    ["endpoint"]
)

ai_operation_duration = Histogram(
    "binom_ai_operation_duration_seconds",
    "AI operation duration",
    ["operation"],
    buckets=[5, 10, 30, 60, 90, 120, 180, 300]
)

# Gauge
active_celery_tasks = Gauge(
    "binom_celery_active_tasks",
    "Active Celery tasks",
    ["queue"]
)

ai_cost_usd_total = Counter(
    "binom_ai_cost_usd_total",
    "Total AI cost in USD",
    ["model"]
)
```

### 10.3 Telegram Alerts

```python
# app/alerts/telegram.py

async def send_alert(message: str, level: str = "warning"):
    """Отправить алёрт в Telegram"""
    
    icons = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️", "ok": "✅"}
    icon = icons.get(level, "📢")
    
    text = f"{icon} *BINOM AI Alert*\n{message}\n_Time: {datetime.utcnow()}_"
    
    await httpx.post(
        f"https://api.telegram.org/bot{settings.TG_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": settings.TG_ALERT_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }
    )
```

---

## 11. Database Migrations

### 11.1 Migration Strategy

```bash
# Supabase миграции хранятся в:
supabase/migrations/
├── 20260709000001_initial_schema.sql   # companies, users, projects
├── 20260709000002_documents.sql        # documents, analysis_results
├── 20260709000003_chat.sql             # chat_sessions, chat_messages
├── 20260709000004_generation.sql       # generated_documents, exports, templates
├── 20260709000005_logs.sql             # audit_logs, ai_usage_logs
├── 20260709000006_rls.sql              # Все RLS политики
├── 20260709000007_functions.sql        # Функции и триггеры
├── 20260709000008_storage.sql          # Storage buckets
├── 20260709000009_jwt_hook.sql         # Custom JWT hook
└── 20260709000010_seed.sql             # Системные шаблоны

# Применить новую миграцию
supabase db push

# Создать новую миграцию
supabase migration new add_new_feature

# Rollback (через SQL)
supabase db reset  # Только для разработки!
```

### 11.2 Zero-downtime Migration Rules

```
ПРАВИЛА для production миграций:

✅ МОЖНО:
- Добавить новую таблицу
- Добавить nullable колонку
- Добавить индекс (CONCURRENTLY)
- Добавить новую RLS политику

⚠️ ОСТОРОЖНО (требует coordination):
- Переименовать колонку (двух-шаговый процесс)
- Изменить тип колонки (с конвертацией данных)
- Добавить NOT NULL колонку (сначала nullable + default)

❌ НЕЛЬЗЯ в production без downtime:
- Удалить колонку немедленно
- Добавить UNIQUE constraint без CONCURRENTLY
- Изменить RLS так, что существующие данные недоступны
```

---

## 12. Backup & Recovery

### 12.1 Стратегия резервного копирования

| Тип | Частота | Хранение | Метод |
|-----|---------|---------|-------|
| Database (full) | Ежедневно | 30 дней | Supabase Auto-backup |
| Database (point-in-time) | Непрерывно | 7 дней | Supabase PITR |
| Storage files | Еженедельно | 90 дней | Supabase Storage sync |
| Application logs | Постоянно | 30 дней | Railway logs |

### 12.2 Процедура восстановления

```bash
# Восстановление БД из backup (Supabase Dashboard):
# Settings → Database → Backups → Restore

# Или через CLI:
supabase db restore --backup-id backup_20260709_000000

# Проверка после восстановления:
psql $DATABASE_URL -c "SELECT COUNT(*) FROM companies;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM projects;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM ai_usage_logs;"
```

---

## 13. Operational Runbook

### 13.1 Алёрты и действия

| Алёрт | Причина | Действие |
|-------|---------|---------|
| `API Error Rate > 5%` | Баг в коде или внешний сервис | Проверить Sentry, rollback если нужно |
| `Celery Queue Lag > 5min` | Worker перегружен или упал | Проверить Railway Worker, перезапустить |
| `Gemini API 429` | Rate limit | Автоматический fallback на GPT-4o работает |
| `DB Connection Pool Exhausted` | Слишком много запросов | Увеличить pool size, проверить N+1 queries |
| `AI Cost > $50/day` | Неожиданный рост использования | Проверить ai_usage_logs, найти аномалию |
| `Storage > 80%` | Много загрузок | Очистить старые exports, расширить план |

### 13.2 Команды для диагностики

```bash
# Проверить статус сервиса
curl https://api.binom.ai/health | jq

# Проверить очереди Celery (через Flower)
open https://flower.binom.ai  # если настроен

# Проверить Railway логи
railway logs --service binom-ai-api --tail 100

# Проверить Redis
railway run redis-cli -u $REDIS_URL ping
railway run redis-cli -u $REDIS_URL INFO memory

# Проверить активные соединения с БД
psql $DATABASE_URL -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Топ медленных запросов
psql $DATABASE_URL -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

### 13.3 Deployment Checklist

```
ПЕРЕД ДЕПЛОЕМ:
□ Все тесты проходят (CI green)
□ Code review завершён (2 апрувала)
□ Changelog обновлён
□ Staging задеплоен и проверен
□ Новые env variables добавлены в Railway
□ Migrations не разрушают production данные

ВО ВРЕМЯ ДЕПЛОЯ:
□ Следить за логами (railway logs)
□ Следить за Sentry (новые ошибки?)
□ Мониторить response times (Grafana)

ПОСЛЕ ДЕПЛОЯ:
□ Health check прошёл ✅
□ Smoke tests прошли ✅
□ Celery workers активны ✅
□ Нет новых Sentry ошибок (5 мин наблюдения) ✅
□ Уведомление команды отправлено ✅

ЕСЛИ НУЖЕН ROLLBACK:
Railway → Deploy → Previous deployment → Rollback
Supabase → Database → Restore (если миграция)
```

---

## 14. Domain & SSL Setup

### 14.1 DNS конфигурация

```
Настройки DNS (в регистраторе домена):

binom.ai           → A record → Vercel IP (или CNAME vercel)
www.binom.ai       → CNAME → cname.vercel-dns.com
api.binom.ai       → CNAME → xxxxx.railway.app
staging.binom.ai   → CNAME → yyyyy.railway.app
staging.api.binom.ai → CNAME → zzzzz.railway.app
```

### 14.2 SSL

- **Vercel:** SSL автоматически (Let's Encrypt)
- **Railway:** SSL автоматически (Railway manages TLS)
- **Supabase:** SSL включён по умолчанию

---

*Документ подготовлен командой BINOM AI. Deployment Guide v1.0 — утверждён.*  
*Документация BINOM AI v1.0 полностью завершена. ✅*
