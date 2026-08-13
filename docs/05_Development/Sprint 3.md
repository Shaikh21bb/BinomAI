# BINOM AI — Sprint 3: Polish, Settings & Production-Ready v1.0

**Документ:** Sprint 3 Plan  
**Версия:** 1.0  
**Дата:** 2026-07-09  
**Статус:** ✅ Утверждён  
**Sprint Duration:** 2 недели (14 дней)  
**Sprint Goal:** Доработка продукта до Production-Ready уровня для первых клиентов

---

## 1. Sprint Goal

> **"К концу Sprint 3 BINOM AI готов к запуску с первыми клиентами: settings работают, онбординг настроен, мониторинг подключён, продукт стабилен и задокументирован."**

**Definition of Done:**
- Settings (профиль компании, пользователя) полностью работают
- Онбординг-флоу завершён
- Аудит-лог записывает все ключевые действия
- Производительность оптимизирована
- CI/CD пайплайн настроен
- Система задеплоена на production
- Мониторинг и алёрты настроены

---

## 2. Backend Tasks — Sprint 3

### 2.1 Settings & Profile

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| S3.1 | `POST /users/me/company/logo` — загрузка логотипа | Backend Dev | 3h |
| S3.2 | `POST /auth/forgot-password` + `POST /auth/reset-password` | Backend Dev | 4h |
| S3.3 | Email notification: приветственное письмо при регистрации | Backend Dev | 2h |
| S3.4 | Email notification: сброс пароля | Backend Dev | 2h |
| S3.5 | Валидация БИН/ИИН (12 цифр, алгоритм Казахстана) | Backend Dev | 3h |
| S3.6 | `PUT /users/me` — обновление настроек (язык, уведомления) | Backend Dev | 2h |
| S3.7 | Onboarding state tracking в `users.onboarding_completed` | Backend Dev | 2h |

**Итого Settings:** ~18 часов

---

### 2.2 Аудит и безопасность

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| SEC3.1 | Audit Logger middleware (все ключевые actions) | Backend Dev | 5h |
| SEC3.2 | Rate Limiting middleware (slowapi) | Backend Dev | 3h |
| SEC3.3 | HTTPS принудительный редирект | DevOps | 1h |
| SEC3.4 | Security headers (HSTS, X-Frame-Options, CSP) | Backend Dev | 2h |
| SEC3.5 | Input sanitization для всех user inputs | Backend Dev | 3h |
| SEC3.6 | Prompt injection protection (PROMPT-SANITIZE) | AI Dev | 3h |
| SEC3.7 | Тестирование RLS изоляции данных (межкомпанийный доступ) | QA | 4h |
| SEC3.8 | Penetration test базовый (OWASP Top 10) | QA | 8h |
| SEC3.9 | Logs: не записывать PII в application logs | Backend Dev | 2h |

**Итого Security:** ~31 час

---

### 2.3 AI Quality Improvements

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| AIQ3.1 | Итеративное улучшение промптов на 20 реальных ТЗ | AI Dev | 12h |
| AIQ3.2 | Few-shot примеры: добавить 3 примера в каждый промпт | AI Dev | 6h |
| AIQ3.3 | Улучшение обнаружения казахских строительных норм | AI Dev | 4h |
| AIQ3.4 | Добавить retry с другой температурой при JSON parse failure | AI Dev | 3h |
| AIQ3.5 | AI Cost Optimization: кэш повторных анализов | AI Dev | 4h |
| AIQ3.6 | Metric: автоматическая проверка на галлюцинации | AI Dev | 6h |

**Итого AI Quality:** ~35 часов

---

### 2.4 Performance Optimization

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| PERF3.1 | Redis кэш для `GET /projects` (TTL 60 сек) | Backend Dev | 3h |
| PERF3.2 | Redis кэш для `GET /analysis` (TTL до изменения) | Backend Dev | 2h |
| PERF3.3 | Database indexes review (медленные запросы) | Backend Dev | 3h |
| PERF3.4 | Connection pooling настройка (asyncpg) | Backend Dev | 2h |
| PERF3.5 | Document text truncation для LLM (smart chunking) | AI Dev | 3h |
| PERF3.6 | Pre-signed URLs кэширование | Backend Dev | 2h |
| PERF3.7 | Sentry integration (error tracking) | DevOps | 2h |

**Итого Performance:** ~17 часов

---

### 2.5 Monitoring & Observability

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| MON3.1 | Prometheus метрики (`/metrics` endpoint) | DevOps | 3h |
| MON3.2 | Grafana dashboard: AI usage, latency, errors | DevOps | 5h |
| MON3.3 | Алёрты: Celery queue lag > 5 мин → Telegram | DevOps | 3h |
| MON3.4 | Алёрты: Error rate > 5% → Telegram | DevOps | 2h |
| MON3.5 | Алёрты: AI cost > $50/day → Telegram | DevOps | 2h |
| MON3.6 | Health check: проверка Gemini API / GPT-4o | Backend Dev | 2h |
| MON3.7 | Uptime monitoring (UptimeRobot или аналог) | DevOps | 1h |
| MON3.8 | Structured logging с correlation IDs | Backend Dev | 3h |

**Итого Monitoring:** ~21 час

---

### 2.6 API Finalization

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| API3.1 | OpenAPI документация — описания всех полей | Backend Dev | 4h |
| API3.2 | Swagger UI: примеры запросов для всех endpoints | Backend Dev | 3h |
| API3.3 | API versioning strategy (пути /api/v1/) | Backend Dev | 1h |
| API3.4 | Deprecation headers для будущих изменений | Backend Dev | 1h |
| API3.5 | Тест 100% endpoints на соответствие спецификации | QA | 6h |

**Итого API Finalization:** ~15 часов

---

## 3. DevOps & Deployment Tasks

### 3.1 CI/CD Pipeline

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| CI3.1 | GitHub Actions: lint + type check (ruff, mypy) | DevOps | 3h |
| CI3.2 | GitHub Actions: run tests on PR | DevOps | 3h |
| CI3.3 | GitHub Actions: Docker build + push | DevOps | 3h |
| CI3.4 | GitHub Actions: Auto-deploy to staging | DevOps | 4h |
| CI3.5 | GitHub Actions: Manual trigger для production deploy | DevOps | 3h |
| CI3.6 | Secrets management (GitHub Secrets / Vault) | DevOps | 2h |
| CI3.7 | Database migration в CI (supabase db push) | DevOps | 2h |

**Итого CI/CD:** ~20 часов

---

### 3.2 Production Infrastructure

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| INFRA3.1 | Railway.app или Fly.io: деплой FastAPI | DevOps | 4h |
| INFRA3.2 | Railway: Redis instance для Celery | DevOps | 2h |
| INFRA3.3 | Railway: Celery Worker instance | DevOps | 3h |
| INFRA3.4 | Supabase Production project setup | DevOps | 3h |
| INFRA3.5 | Custom domain + SSL сертификат (api.binom.ai) | DevOps | 2h |
| INFRA3.6 | Nginx reverse proxy config | DevOps | 2h |
| INFRA3.7 | Environment-specific configs (dev / staging / prod) | DevOps | 2h |
| INFRA3.8 | Database backups настройка (ежедневно) | DevOps | 2h |

**Итого Infrastructure:** ~20 часов

---

## 4. Frontend Tasks — Sprint 3

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| FE3.1 | Settings страница: профиль пользователя (интеграция API) | Frontend Dev | 4h |
| FE3.2 | Settings страница: профиль компании + логотип | Frontend Dev | 5h |
| FE3.3 | Onboarding Modal: полный флоу (4 шага) | Frontend Dev | 5h |
| FE3.4 | Forgot / Reset password страницы | Frontend Dev | 3h |
| FE3.5 | Error boundary компоненты (graceful degradation) | Frontend Dev | 3h |
| FE3.6 | Loading skeletons для всех основных компонентов | Frontend Dev | 3h |
| FE3.7 | Empty states для всех списков | Frontend Dev | 2h |
| FE3.8 | Toast notifications (global) | Frontend Dev | 2h |
| FE3.9 | Responsive: проверка на планшете (768px+) | Frontend Dev | 4h |
| FE3.10 | SEO meta tags на всех страницах | Frontend Dev | 2h |
| FE3.11 | Favicon и Open Graph изображения | Frontend Dev | 1h |

**Итого Frontend Sprint 3:** ~34 часа

---

## 5. Testing Tasks — Sprint 3

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| T3.1 | E2E test: Регистрация → первый проект → анализ → генерация → экспорт | QA | 8h |
| T3.2 | Security test: межкомпанийная изоляция данных | QA | 4h |
| T3.3 | Security test: Rate limiting проверка | QA | 2h |
| T3.4 | Performance test: 10 одновременных пользователей | QA | 4h |
| T3.5 | AI test: ручная проверка 10 генераций КП экспертом | Domain Expert | 6h |
| T3.6 | Cross-browser test: Chrome, Firefox, Safari | QA | 4h |
| T3.7 | Тест на больших PDF (87+ страниц) | QA | 3h |
| T3.8 | Тест на минимальных PDF (5 страниц) | QA | 2h |
| T3.9 | Тест: русский язык в DOCX корректно | QA | 2h |
| T3.10 | Regression: все Sprint 1 и Sprint 2 AC | QA | 6h |

**Итого Testing Sprint 3:** ~41 час

---

## 6. Documentation Tasks

| ID | Задача | Исполнитель | Оценка |
|----|--------|------------|--------|
| DOC3.1 | README.md с инструкцией запуска (dev + production) | Backend Dev | 3h |
| DOC3.2 | Swagger OpenAPI документация (финальная) | Backend Dev | 3h |
| DOC3.3 | Runbook: действия при инцидентах | DevOps | 4h |
| DOC3.4 | Архитектурная схема (актуальная, после Sprint 3) | Backend Dev | 2h |

**Итого Documentation:** ~12 часов

---

## 7. Sprint 3 — Временная шкала

```
НЕДЕЛЯ 5 (Дни 29-35):
──────────────────────────────────────────────────────────
Пн  │ S3.1-S3.7: Settings & Profile
    │ SEC3.1-SEC3.4: Security Setup
──────────────────────────────────────────────────────────
Вт  │ SEC3.5-SEC3.9: Security (finish)
    │ PERF3.1-PERF3.4: Performance
──────────────────────────────────────────────────────────
Ср  │ PERF3.5-PERF3.7 + AIQ3.1-AIQ3.3: AI Quality
──────────────────────────────────────────────────────────
Чт  │ AIQ3.4-AIQ3.6 + FE3.1-FE3.5: Frontend Sprint 3
──────────────────────────────────────────────────────────
Пт  │ FE3.6-FE3.11: Frontend (finish)
    │ CI3.1-CI3.4: CI/CD setup
──────────────────────────────────────────────────────────
Сб  │ CI3.5-CI3.7 + INFRA3.1-INFRA3.4: Deploy Start
──────────────────────────────────────────────────────────

НЕДЕЛЯ 6 (Дни 36-42):
──────────────────────────────────────────────────────────
Пн  │ INFRA3.5-INFRA3.8: Production Infra
    │ MON3.1-MON3.4: Monitoring
──────────────────────────────────────────────────────────
Вт  │ MON3.5-MON3.8 + API3.1-API3.5: API Docs
──────────────────────────────────────────────────────────
Ср  │ T3.1-T3.5: Testing (основное)
──────────────────────────────────────────────────────────
Чт  │ T3.6-T3.10: Testing (регрессия)
    │ DOC3.1-DOC3.4: Documentation
──────────────────────────────────────────────────────────
Пт  │ BUGFIXES + Final Review
    │ Production Deploy
──────────────────────────────────────────────────────────
Сб  │ SPRINT 3 DEMO — v1.0 MVP LAUNCH READY 🚀
──────────────────────────────────────────────────────────
```

---

## 8. Acceptance Criteria

### Функциональные

```
✅ AC-3.1: Пользователь может загрузить логотип компании
✅ AC-3.2: Логотип отображается в сгенерированных документах
✅ AC-3.3: Пользователь может изменить пароль через forgot/reset
✅ AC-3.4: Онбординг показывается при первом входе
✅ AC-3.5: После онбординга флаг is_onboarding_complete = true
✅ AC-3.6: Rate limiting блокирует > 100 req/min
✅ AC-3.7: Аудит-лог записывает: login, project create/delete, generate, export
✅ AC-3.8: Один пользователь не видит данные другой компании (RLS)
✅ AC-3.9: Swagger документация полная и актуальная
✅ AC-3.10: Все API возвращают корректные HTTP коды
```

### Production-Ready

```
✅ AC-PROD-1: Сервис задеплоен на production URL (api.binom.ai)
✅ AC-PROD-2: HTTPS + SSL сертификат активен
✅ AC-PROD-3: GitHub Actions CI прогоняет тесты на каждый PR
✅ AC-PROD-4: Ошибки логируются в Sentry
✅ AC-PROD-5: Latency p95 < 500ms для non-AI endpoints
✅ AC-PROD-6: Uptime monitor настроен
✅ AC-PROD-7: Database backup работает ежедневно
✅ AC-PROD-8: Celery worker stable (нет memory leaks за 24ч)
```

### Нефункциональные

```
✅ AC-NF-3.1: 10 одновременных пользователей без деградации
✅ AC-NF-3.2: 0 P1 (critical) багов в production
✅ AC-NF-3.3: Код покрыт тестами > 70%
✅ AC-NF-3.4: Нет SQL injection уязвимостей
✅ AC-NF-3.5: Нет XSS уязвимостей в редакторе
```

---

## 9. MVP Launch Checklist

После завершения Sprint 3 — финальный чеклист перед приёмом первых клиентов:

```
ТЕХНИЧЕСКИЙ:
□ Все 3 спринта закрыты и задеплоены
□ Все Acceptance Criteria Sprint 1-3 выполнены
□ Sentry настроен и получает ошибки
□ Grafana dashboard активен
□ Telegram алёрты работают
□ Database backup верифицирован (тест восстановления)
□ Нагрузочный тест: 20 конкурентных пользователей ОК

ПРОДУКТОВЫЙ:
□ Онбординг протестирован на 3 реальных пользователях
□ Документы проверены строительным экспертом
□ AI Quality: < 5% галлюцинаций на тест-наборе
□ DOCX и PDF выглядят профессионально
□ Email уведомления работают

БИЗНЕС:
□ Условия подписки настроены (trial = 14 дней)
□ Support@binom.ai настроен
□ Privacy Policy и Terms of Service опубликованы
□ GDPR / данные пользователей: соответствие законодательству РК

КОММУНИКАЦИЯ:
□ Первые 3 клиента получили доступ (pilot)
□ Feedback-механизм работает (👍/👎 + форма)
□ Slack/Telegram канал для уведомлений команды
```

---

## 10. Post-Sprint 3: Roadmap Phase 2

После успешного MVP Launch:

```
Фаза 2 (Sprint 4-6):
├── Двуязычность (казахский язык)
├── RAG Vector Store (нормативная база)
├── Многопользовательский доступ (команда в компании)
├── Система подписок и биллинг (Stripe)
├── Интеграция с goszakup.gov.kz (парсинг тендеров)
└── Аналитика компании (статистика проектов)

Фаза 3 (Sprint 7-10):
├── Мобильное приложение (React Native)
├── Кастомные шаблоны (компания загружает свой стиль)
├── Версионирование документов
├── Экспорт в кастомный DOCX (brandbook)
└── AI обучение на обратной связи (RLHF)
```

---

## 11. Sprint 3 — Итоговый счётчик

| Категория | Часов |
|-----------|-------|
| Settings & Profile | 18 |
| Security | 31 |
| AI Quality | 35 |
| Performance | 17 |
| Monitoring | 21 |
| API Finalization | 15 |
| CI/CD | 20 |
| Infrastructure | 20 |
| Frontend Sprint 3 | 34 |
| Testing | 41 |
| Documentation | 12 |
| **ИТОГО** | **264** |
| Buffer (20%) | 53 |
| **ИТОГО с буфером** | **~317 ч** |

> **При команде 4 чел (+ DevOps):** Sprint 3 занимает 2 недели.

---

## 12. Общий итог: MVP (Sprint 1–3)

| Sprint | Фокус | Длительность | Ключевой результат |
|--------|-------|-------------|-------------------|
| Sprint 1 | Foundation | 2 недели | Auth + Upload + AI Analysis |
| Sprint 2 | Core AI | 2 недели | Chat + Generation + Export |
| Sprint 3 | Polish | 2 недели | Production-ready MVP |
| **ИТОГО** | **Full MVP** | **6 недель** | **Продукт готов к продаже** |

---

*Документ подготовлен командой BINOM AI. Sprint 3 Plan v1.0 — утверждён.*  
*Следующий документ: [Test Plan.md](./Test%20Plan.md)*
