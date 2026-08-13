# BINOM AI — API Specification v1.0

**Документ:** API Specification  
**Версия:** 1.0  
**Дата:** 2026-07-09  
**Статус:** ✅ Утверждён  
**Автор:** Backend Lead / CTO  
**Связанные документы:** [System Architecture.md](./System%20Architecture.md), [Database Schema.md](./Database%20Schema.md)

---

## 1. Общие принципы API

### 1.1 Базовые параметры

| Параметр | Значение |
|---------|----------|
| **Base URL (Dev)** | `http://localhost:8000/api/v1` |
| **Base URL (Prod)** | `https://api.binom.ai/api/v1` |
| **Protocol** | HTTPS (обязательно в production) |
| **Format** | JSON (application/json) |
| **Version** | v1 |
| **Authentication** | Bearer JWT Token |
| **Documentation** | Swagger UI: `/docs`, ReDoc: `/redoc` |
| **OpenAPI Schema** | `/openapi.json` |

### 1.2 Authentication Header

Все защищённые эндпоинты требуют:

```http
Authorization: Bearer <access_token>
```

### 1.3 Стандартный формат ответа

**Успешный ответ:**
```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-07-09T10:00:00Z"
  }
}
```

**Ошибка:**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Поле 'name' обязательно",
    "details": [
      {
        "field": "name",
        "message": "Field required"
      }
    ]
  },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-07-09T10:00:00Z"
  }
}
```

### 1.4 Стандартные коды ошибок

| HTTP Code | Error Code | Описание |
|-----------|-----------|----------|
| 400 | VALIDATION_ERROR | Ошибка валидации входных данных |
| 401 | UNAUTHORIZED | Не авторизован (нет/истёк токен) |
| 403 | FORBIDDEN | Нет прав на ресурс |
| 404 | NOT_FOUND | Ресурс не найден |
| 409 | CONFLICT | Конфликт (дубль email и т.д.) |
| 413 | FILE_TOO_LARGE | Файл превышает 50 МБ |
| 415 | UNSUPPORTED_MEDIA | Неподдерживаемый тип файла |
| 422 | UNPROCESSABLE | Невозможно обработать |
| 429 | RATE_LIMIT_EXCEEDED | Превышен лимит запросов |
| 500 | INTERNAL_ERROR | Внутренняя ошибка сервера |
| 503 | AI_UNAVAILABLE | AI-сервис временно недоступен |
| 503 | AI_FALLBACK_UNAVAILABLE | Документ слишком большой для резервного AI (>120k токенов) |

### 1.5 Пагинация

**FIX #15 — Cursor-based pagination** (вместо offset-based).

Offset-based (`OFFSET 80 LIMIT 20`) линейно деградирует при росте данных: PostgreSQL сканирует и выбрасывает первые 80 строк. При 500+ проектах на компанию — заметная деградация.

Cursor-based использует один индекс-seek:

```json
// Первый запрос (без cursor)
GET /api/v1/projects?page_size=20

// Ответ:
{
  "data": [...],
  "pagination": {
    "page_size": 20,
    "has_next": true,
    "next_cursor": "2026-07-01T10:00:00Z__550e8400-uuid",
    "total": null
  }
}

// Следующая страница:
GET /api/v1/projects?page_size=20&cursor=2026-07-01T10:00:00Z__550e8400-uuid
```

**Формат cursor:** `{created_at_iso}__{id_uuid}` — уникально идентифицирует позицию.

**SQL реализация:**
```sql
-- Декодировать cursor → created_at, id
-- Затем:
SELECT * FROM projects
WHERE company_id = $1
  AND (created_at, id) < ($cursor_created_at, $cursor_id)  -- keyset pagination
ORDER BY created_at DESC, id DESC
LIMIT $page_size;
```

**Исключение:** для коллекций с гарантированно малым объёмом (chat_messages в одной сессии < 100 записей) допустим offset.

### 1.6 Rate Limiting

| Эндпоинт | Лимит |
|---------|-------|
| Публичные (регистрация, логин) | 20 req/min |
| Обычные API | 100 req/min на пользователя |
| AI-операции (анализ, генерация) | 10 req/min на компанию |
| Загрузка файлов | 5 req/min на пользователя |

Заголовки в ответе:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1720519200
```

---

## 2. AUTH — Аутентификация

### POST /auth/register

Регистрация нового пользователя и компании.

**Request:**
```http
POST /api/v1/auth/register
Content-Type: application/json
```

```json
{
  "email": "asel@constructor.kz",
  "password": "SecurePass123!",
  "full_name": "Асель Нурова",
  "company_name": "ТОО «КазСтройПроект»"
}
```

**Validation:**
- `email`: valid email format, unique
- `password`: min 8 chars, at least 1 uppercase, 1 number
- `full_name`: 2-255 chars
- `company_name`: 2-255 chars

**Response 201:**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "asel@constructor.kz",
      "full_name": "Асель Нурова",
      "company_id": "660e8400-e29b-41d4-a716-446655440001"
    },
    "company": {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "name": "ТОО «КазСтройПроект»",
      "plan": "trial"
    },
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 86400
  }
}
```

---

### POST /auth/login

```http
POST /api/v1/auth/login
Content-Type: application/json
```

```json
{
  "email": "asel@constructor.kz",
  "password": "SecurePass123!"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": {
      "id": "...",
      "email": "asel@constructor.kz",
      "full_name": "Асель Нурова",
      "role": "owner",
      "company_id": "...",
      "company_name": "ТОО «КазСтройПроект»"
    }
  }
}
```

---

### POST /auth/logout

```http
POST /api/v1/auth/logout
Authorization: Bearer <token>
```

**Response 200:**
```json
{ "success": true, "data": { "message": "Вы успешно вышли из системы" } }
```

---

### POST /auth/refresh

```http
POST /api/v1/auth/refresh
Content-Type: application/json
```

```json
{ "refresh_token": "eyJhbGciOiJIUzI1NiIs..." }
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 86400
  }
}
```

---

### POST /auth/forgot-password

```json
{ "email": "asel@constructor.kz" }
```

**Response 200:** `{ "success": true, "data": { "message": "Письмо отправлено" } }`

---

### POST /auth/reset-password

```json
{
  "token": "reset_token_from_email",
  "new_password": "NewSecurePass456!"
}
```

**Response 200:** `{ "success": true, "data": { "message": "Пароль успешно изменён" } }`

---

## 3. USERS — Пользователи

### GET /users/me

Получить профиль текущего пользователя.

```http
GET /api/v1/users/me
Authorization: Bearer <token>
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "...",
    "email": "asel@constructor.kz",
    "full_name": "Асель Нурова",
    "job_title": "Руководитель тендерного отдела",
    "phone": "+7 700 123 4567",
    "avatar_url": null,
    "role": "owner",
    "language": "ru",
    "onboarding_completed": true,
    "company_id": "...",
    "created_at": "2026-07-09T10:00:00Z"
  }
}
```

---

### PUT /users/me

Обновить профиль пользователя.

```json
{
  "full_name": "Асель Мухамедова",
  "job_title": "Директор по тендерам",
  "phone": "+7 707 987 6543",
  "language": "ru"
}
```

**Response 200:** Обновлённый объект пользователя.

---

### GET /users/me/company

Получить профиль компании.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "...",
    "name": "ТОО «КазСтройПроект»",
    "bin_iin": "180340012345",
    "legal_address": "г. Алматы, ул. Абая 150",
    "phone": "+7 727 123 4567",
    "email": "info@kazstroyproject.kz",
    "logo_url": "https://storage.supabase.co/...",
    "specialization": "Строительство промышленных объектов",
    "director_name": "Нурлан Касымов",
    "director_title": "Директор",
    "plan": "trial",
    "plan_expires_at": "2026-08-09T00:00:00Z"
  }
}
```

---

### PUT /users/me/company

Обновить профиль компании.

```json
{
  "name": "ТОО «КазСтройПроект»",
  "bin_iin": "180340012345",
  "legal_address": "г. Алматы, ул. Абая 150",
  "phone": "+7 727 123 4567",
  "email": "info@kazstroyproject.kz",
  "specialization": "Строительство промышленных объектов",
  "director_name": "Нурлан Касымов",
  "director_title": "Директор",
  "bank_name": "АО «Казкоммерцбанк»",
  "bank_account": "KZ12345678901234567890",
  "bank_bik": "KCJBKZKX"
}
```

**Response 200:** Обновлённый объект компании.

---

### POST /users/me/company/logo

Загрузить логотип компании.

```http
POST /api/v1/users/me/company/logo
Content-Type: multipart/form-data

file: [binary logo file (PNG/SVG/JPG, max 5MB)]
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "logo_url": "https://storage.supabase.co/company-assets/660e.../logo.png"
  }
}
```

---

## 4. PROJECTS — Проекты

### GET /projects

Получить список проектов компании.

```http
GET /api/v1/projects?page=1&page_size=20&status=draft&search=завод
Authorization: Bearer <token>
```

**Query Parameters:**

| Параметр | Тип | Описание |
|---------|-----|----------|
| `page` | int | Страница (default: 1) |
| `page_size` | int | Размер страницы (default: 20, max: 100) |
| `status` | string | Фильтр по статусу |
| `search` | string | Поиск по названию |
| `sort_by` | string | `created_at` \| `updated_at` \| `deadline_at` |
| `sort_order` | string | `asc` \| `desc` (default: `desc`) |

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "...",
      "name": "Тендер на строительство завода, г. Шымкент",
      "customer_name": "АО «НефтеХимПроект»",
      "status": "analyzing",
      "tender_type": "EPC",
      "complexity": "high",
      "deadline_at": "2026-08-15T00:00:00Z",
      "document_status": "ready",
      "analysis_status": "completed",
      "risk_count": 3,
      "requirement_count": 47,
      "has_commercial_proposal": true,
      "has_tech_spec": false,
      "has_cover_letter": false,
      "chat_complete": false,
      "created_by_name": "Асель Нурова",
      "created_at": "2026-07-09T10:00:00Z",
      "updated_at": "2026-07-09T11:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 45,
    "total_pages": 3
  }
}
```

---

### POST /projects

Создать новый проект.

```json
{
  "name": "Тендер на строительство завода, г. Шымкент",
  "customer_name": "АО «НефтеХимПроект»",
  "deadline_at": "2026-08-15T00:00:00Z",
  "notes": "Важный тендер, приоритет!"
}
```

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "770e8400-e29b-41d4-a716-446655440002",
    "name": "Тендер на строительство завода, г. Шымкент",
    "status": "draft",
    "created_at": "2026-07-09T12:00:00Z"
  }
}
```

---

### GET /projects/{project_id}

Получить детали проекта.

**Response 200:** Полный объект проекта (project_summary view).

---

### PUT /projects/{project_id}

Обновить проект.

```json
{
  "name": "Новое название тендера",
  "status": "review",
  "deadline_at": "2026-08-20T00:00:00Z"
}
```

---

### DELETE /projects/{project_id}

Удалить проект (и все связанные данные).

**Response 200:** `{ "success": true, "data": { "message": "Проект удалён" } }`

---

## 5. DOCUMENTS — Документы (ТЗ)

### POST /projects/{project_id}/documents

Загрузить ТЗ в проект.

```http
POST /api/v1/projects/{project_id}/documents
Content-Type: multipart/form-data
Authorization: Bearer <token>

file: [binary PDF or DOCX file, max 50MB]
```

**Response 202 (Accepted — async processing):**
```json
{
  "success": true,
  "data": {
    "document_id": "880e8400-e29b-41d4-a716-446655440003",
    "filename": "tz_zavod_shymkent.pdf",
    "file_size_bytes": 2457600,
    "processing_status": "processing",
    "task_id": "celery-task-uuid",
    "message": "Документ загружен. AI анализ начался автоматически."
  }
}
```

*Клиент слушает WebSocket для обновлений статуса.*

---

### GET /projects/{project_id}/documents/current

Получить текущий (активный) документ проекта.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "...",
    "filename": "tz_zavod_shymkent.pdf",
    "file_size_bytes": 2457600,
    "mime_type": "application/pdf",
    "page_count": 87,
    "token_count": 68500,
    "language": "ru",
    "processing_status": "ready",
    "doc_title": "Техническое задание на строительство нефтеперерабатывающего завода",
    "doc_date": "2026-06-15",
    "version": 1,
    "created_at": "2026-07-09T12:05:00Z"
  }
}
```

---

### GET /projects/{project_id}/documents/{doc_id}/download

Получить подписанный URL для скачивания оригинального ТЗ.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "download_url": "https://storage.supabase.co/signed/...",
    "expires_at": "2026-07-09T13:00:00Z"
  }
}
```

---

## 6. ANALYSIS — AI-анализ

### GET /projects/{project_id}/analysis

Получить результаты AI-анализа проекта.

```http
GET /api/v1/projects/{project_id}/analysis
Authorization: Bearer <token>
```

**Response 200 (анализ завершён):**
```json
{
  "success": true,
  "data": {
    "id": "...",
    "project_id": "...",
    "status": "completed",
    "executive_summary": "Тендер на строительство нефтеперерабатывающего завода мощностью 500 000 т/год в г. Шымкент. Высокая сложность ввиду специфических экологических требований и жёстких сроков. Рекомендуется привлечение субподрядчиков для специализированных работ.",
    "tender_type": "EPC",
    "complexity_level": "High",
    "estimated_duration_days": 540,
    "technical_requirements": [
      {
        "id": "req_001",
        "text": "Производительность завода не менее 500 000 тонн в год",
        "category": "performance",
        "is_mandatory": true,
        "source_section": "3.1. Технические параметры",
        "source_page": 12
      }
    ],
    "commercial_requirements": [
      {
        "id": "req_c001",
        "text": "Фиксированная цена контракта (lump sum turnkey)",
        "category": "pricing",
        "is_mandatory": true,
        "source_section": "5.2. Коммерческие условия",
        "source_page": 34
      }
    ],
    "legal_requirements": [...],
    "required_documents": [
      {
        "id": "doc_req_001",
        "name": "Свидетельство о государственной регистрации",
        "is_mandatory": true,
        "format": "заверенная копия"
      }
    ],
    "key_deadlines": [
      {
        "event": "Срок подачи заявки",
        "date": "2026-08-15",
        "is_hard_deadline": true,
        "source_section": "1.4. Сроки"
      }
    ],
    "risks": [
      {
        "id": "risk_001",
        "description": "Требование о предоставлении банковской гарантии в размере 10% от суммы контракта с высоким кредитным рейтингом банка может быть сложным для малых компаний",
        "severity": "High",
        "risk_type": "financial",
        "mitigation": "Заблаговременно связаться с банком для получения гарантии",
        "source_section": "5.5. Обеспечение контракта"
      }
    ],
    "missing_info_from_tender": [
      "Не указан точный адрес строительной площадки",
      "Нет данных о геологических исследованиях"
    ],
    "missing_company_data": [
      "Требуется предоставить список аналогичных реализованных проектов",
      "Необходимо указать состав субподрядчиков"
    ],
    "llm_model": "gemini-1.5-pro",
    "processing_time_ms": 23400,
    "created_at": "2026-07-09T12:07:00Z"
  }
}
```

**Response 200 (анализ в процессе):**
```json
{
  "success": true,
  "data": {
    "status": "processing",
    "message": "AI анализирует документ...",
    "task_id": "celery-task-uuid"
  }
}
```

---

### POST /projects/{project_id}/analysis/retry

Повторить анализ (если ошибка).

**Response 202:** `{ "success": true, "data": { "task_id": "new-task-uuid" } }`

---

## 7. CHAT — AI-чат

### GET /projects/{project_id}/chat

Получить текущую сессию чата и историю сообщений.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "session": {
      "id": "...",
      "is_complete": false,
      "message_count": 6,
      "clarification_context": {
        "company_experience": "15 лет",
        "proposed_price": null,
        "is_complete": false
      }
    },
    "messages": [
      {
        "id": "...",
        "role": "assistant",
        "content": "Добрый день! Я проанализировал техническое задание. Для подготовки качественного коммерческого предложения мне нужно уточнить несколько вопросов. Первый вопрос: какой опыт в строительстве нефтеперерабатывающих объектов есть у вашей компании? Укажите количество аналогичных реализованных проектов.",
        "message_type": "question",
        "created_at": "2026-07-09T12:08:00Z"
      },
      {
        "id": "...",
        "role": "user",
        "content": "У нас есть 3 реализованных проекта НПЗ за последние 7 лет, суммарной мощностью 800 000 т/год.",
        "message_type": "answer",
        "created_at": "2026-07-09T12:08:45Z"
      }
    ]
  }
}
```

---

### POST /projects/{project_id}/chat/message

Отправить сообщение в чат.

```json
{
  "content": "У нас есть 3 реализованных проекта НПЗ за последние 7 лет."
}
```

**Response 200 (для обычных сообщений):**
```json
{
  "success": true,
  "data": {
    "user_message": {
      "id": "...",
      "role": "user",
      "content": "У нас есть 3 реализованных проекта НПЗ за последние 7 лет.",
      "created_at": "2026-07-09T12:09:00Z"
    },
    "assistant_message": {
      "id": "...",
      "role": "assistant",
      "content": "Отлично, это важная информация для КП. Следующий вопрос: какую ориентировочную стоимость вы планируете предложить? Если ещё не определились — укажите предполагаемый диапазон.",
      "message_type": "question",
      "created_at": "2026-07-09T12:09:05Z"
    },
    "session_status": {
      "is_complete": false,
      "questions_remaining": 3
    }
  }
}
```

*Для стриминга AI-ответа используется SSE (Server-Sent Events):*

```http
GET /api/v1/projects/{project_id}/chat/stream?message=<encoded_message>
Accept: text/event-stream
```

```
data: {"type": "token", "content": "Отлично"}
data: {"type": "token", "content": ", это"}
data: {"type": "token", "content": " важная информация"}
data: {"type": "done", "message_id": "..."}
```

---

### GET /projects/{project_id}/chat/status

Проверить готовность к генерации.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "is_ready_for_generation": true,
    "missing_info": [],
    "clarification_context": { ... }
  }
}
```

---

## 8. GENERATION — Генерация документов

### POST /projects/{project_id}/generate

Запустить генерацию документа.

```http
POST /api/v1/projects/{project_id}/generate
Content-Type: application/json
Authorization: Bearer <token>
```

```json
{
  "doc_type": "commercial_proposal",
  "template_id": "system-template-kp-v1"
}
```

**doc_type values:**
- `commercial_proposal` — Коммерческое предложение
- `tech_spec` — Техническая спецификация
- `cover_letter` — Сопроводительное письмо

**Response 202:**
```json
{
  "success": true,
  "data": {
    "doc_id": "990e8400-...",
    "doc_type": "commercial_proposal",
    "generation_status": "generating",
    "task_id": "celery-task-uuid",
    "estimated_seconds": 45,
    "message": "Генерация началась. Ожидайте уведомление через WebSocket."
  }
}
```

---

### GET /projects/{project_id}/documents/generated

Получить список всех сгенерированных документов проекта.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "990e8400-...",
      "doc_type": "commercial_proposal",
      "version": 1,
      "is_current": true,
      "generation_status": "completed",
      "user_rating": 5,
      "created_at": "2026-07-09T12:15:00Z"
    }
  ]
}
```

---

### GET /projects/{project_id}/documents/generated/{doc_id}

Получить контент сгенерированного документа.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "...",
    "doc_type": "commercial_proposal",
    "version": 1,
    "generation_status": "completed",
    "content_html": "<h1>Коммерческое предложение</h1>...",
    "content_json": {
      "sections": [...]
    },
    "created_at": "2026-07-09T12:15:00Z",
    "updated_at": "2026-07-09T12:15:00Z"
  }
}
```

---

### PUT /projects/{project_id}/documents/generated/{doc_id}

Сохранить отредактированный документ.

```json
{
  "content_html": "<h1>Коммерческое предложение</h1><p>Отредактированный текст...</p>",
  "content_json": { "sections": [...] }
}
```

**Response 200:** Обновлённый документ.

---

### POST /projects/{project_id}/documents/generated/{doc_id}/regenerate-section

Перегенерировать отдельную секцию.

```json
{
  "section_id": "section_4",
  "instruction": "Сделай технический раздел более детальным, добавь параметры оборудования"
}
```

**Response 202:** `{ "task_id": "..." }`

---

### POST /projects/{project_id}/documents/generated/{doc_id}/feedback

Оставить оценку документа.

```json
{
  "rating": 1,
  "feedback_reason": "irrelevant_content",
  "feedback_text": "AI не учёл специфику нефтехимического производства"
}
```

**Response 200:** `{ "success": true, "data": { "message": "Спасибо за отзыв!" } }`

---

## 9. EXPORT — Экспорт файлов

### POST /projects/{project_id}/documents/generated/{doc_id}/export

Создать экспортный файл.

```json
{
  "format": "docx"
}
```

**format values:** `docx` | `pdf`

**Response 202:**
```json
{
  "success": true,
  "data": {
    "export_id": "aaa0e8400-...",
    "format": "docx",
    "export_status": "generating",
    "task_id": "celery-task-uuid",
    "message": "Файл готовится. Ожидайте уведомление."
  }
}
```

---

### GET /projects/{project_id}/exports/{export_id}/download

Получить URL для скачивания готового файла.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "export_id": "...",
    "format": "docx",
    "filename": "КП_Тендер_НПЗ_Шымкент_2026.docx",
    "file_size_bytes": 145678,
    "download_url": "https://storage.supabase.co/signed/...",
    "url_expires_at": "2026-07-09T13:15:00Z"
  }
}
```

---

## 10. TEMPLATES — Шаблоны

### GET /templates

Получить список доступных шаблонов.

```http
GET /api/v1/templates?doc_type=commercial_proposal
```

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "system-template-kp-v1",
      "name": "Стандартный КП (РК)",
      "doc_type": "commercial_proposal",
      "description": "Стандартный шаблон коммерческого предложения по нормам Казахстана",
      "is_system": true,
      "language": "ru",
      "version": 1
    }
  ]
}
```

---

## 11. WEBSOCKET — Real-time обновления

### WS /ws/{project_id}

WebSocket соединение для real-time обновлений проекта.

```
wss://api.binom.ai/api/v1/ws/{project_id}?token=<access_token>
```

**Входящие события (Server → Client):**

```json
// Анализ документа начался
{
  "event": "task:started",
  "task_type": "document_analysis",
  "task_id": "celery-task-uuid",
  "timestamp": "2026-07-09T12:05:00Z"
}

// Прогресс (если доступен)
{
  "event": "task:progress",
  "task_type": "document_analysis",
  "task_id": "celery-task-uuid",
  "progress": 65,
  "message": "Извлечение требований...",
  "timestamp": "2026-07-09T12:05:15Z"
}

// Задача завершена
{
  "event": "task:completed",
  "task_type": "document_analysis",
  "task_id": "celery-task-uuid",
  "result": {
    "analysis_id": "..."
  },
  "timestamp": "2026-07-09T12:05:30Z"
}

// Задача завершилась с ошибкой
{
  "event": "task:failed",
  "task_type": "generation",
  "task_id": "celery-task-uuid",
  "error": {
    "code": "AI_UNAVAILABLE",
    "message": "AI сервис временно недоступен. Попробуйте снова."
  },
  "timestamp": "2026-07-09T12:05:30Z"
}
```

**task_type values:**
- `document_analysis`
- `generation_commercial_proposal`
- `generation_tech_spec`
- `generation_cover_letter`
- `export_docx`
- `export_pdf`

---

## 12. HEALTH — Состояние системы

### GET /health

Проверка работоспособности (публичный эндпоинт).

**Response 200:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-07-09T12:00:00Z",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "gemini_api": "healthy",
    "openai_api": "healthy",
    "storage": "healthy"
  }
}
```

**Response 503 (если что-то не работает):**
```json
{
  "status": "degraded",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "gemini_api": "unhealthy",
    "openai_api": "healthy",
    "storage": "healthy"
  },
  "message": "AI analysis unavailable, using fallback"
}
```

---

## 13. Полная карта эндпоинтов

```
Auth:
  POST   /auth/register
  POST   /auth/login
  POST   /auth/logout
  POST   /auth/refresh
  POST   /auth/forgot-password
  POST   /auth/reset-password

Users:
  GET    /users/me
  PUT    /users/me
  GET    /users/me/company
  PUT    /users/me/company
  POST   /users/me/company/logo

Projects:
  GET    /projects
  POST   /projects
  GET    /projects/{id}
  PUT    /projects/{id}
  DELETE /projects/{id}

Documents (ТЗ):
  POST   /projects/{id}/documents              (upload)
  GET    /projects/{id}/documents/current
  GET    /projects/{id}/documents/{doc_id}/download

Analysis:
  GET    /projects/{id}/analysis
  POST   /projects/{id}/analysis/retry

Chat:
  GET    /projects/{id}/chat
  POST   /projects/{id}/chat/message
  GET    /projects/{id}/chat/stream            (SSE)
  GET    /projects/{id}/chat/status

Generation:
  POST   /projects/{id}/generate
  GET    /projects/{id}/documents/generated
  GET    /projects/{id}/documents/generated/{doc_id}
  PUT    /projects/{id}/documents/generated/{doc_id}
  POST   /projects/{id}/documents/generated/{doc_id}/regenerate-section
  POST   /projects/{id}/documents/generated/{doc_id}/feedback

Export:
  POST   /projects/{id}/documents/generated/{doc_id}/export
  GET    /projects/{id}/exports/{export_id}/download

Templates:
  GET    /templates

WebSocket:
  WS     /ws/{project_id}

System:
  GET    /health
  GET    /docs                                  (Swagger UI)
  GET    /redoc
  GET    /openapi.json
```

---

## 14. Примеры ошибок

### 401 Unauthorized

```json
{
  "success": false,
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Недействительный или истёкший токен авторизации"
  }
}
```

### 403 Forbidden

```json
{
  "success": false,
  "error": {
    "code": "FORBIDDEN",
    "message": "У вас нет доступа к этому ресурсу"
  }
}
```

### 413 File Too Large

```json
{
  "success": false,
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "Файл слишком большой. Максимальный размер: 50 МБ"
  }
}
```

### 429 Rate Limit

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Слишком много запросов. Попробуйте через 30 секунд."
  },
  "meta": {
    "retry_after": 30
  }
}
```

### 503 AI Unavailable

```json
{
  "success": false,
  "error": {
    "code": "AI_UNAVAILABLE",
    "message": "AI-сервис временно недоступен. Мы работаем над устранением. Попробуйте через несколько минут."
  }
}
```

---

*Документ подготовлен командой BINOM AI. API Specification v1.0 — утверждён.*  
*Следующий документ: [Design System.md](../03_Design/Design%20System.md)*
