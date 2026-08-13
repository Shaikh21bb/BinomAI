# BINOM AI — User Stories v1.0

**Документ:** User Stories  
**Версия:** 1.0  
**Дата:** 2026-07-09  
**Статус:** ✅ Утверждён  
**Автор:** Product Manager  
**Связанные документы:** [PRD.md](./PRD.md), [Product Vision.md](./Product%20Vision.md)

---

## Соглашения по формату

### Структура User Story

```
As a [persona]
I want to [action/capability]
So that [business value/benefit]

Acceptance Criteria:
GIVEN [precondition]
WHEN [action]
THEN [expected outcome]
AND [additional condition]

Priority: Must Have | Should Have | Could Have
Sprint: S1 | S2 | S3 | Post-MVP
Story Points: [1 | 2 | 3 | 5 | 8 | 13]
```

### Персоны

| Код | Персона | Описание |
|-----|---------|----------|
| **TM** | Тендерный менеджер | Руководитель тендерного отдела |
| **TE** | Тендерный инженер | Специалист по подготовке документов |
| **CD** | Директор компании | Малая компания, сам занимается тендерами |
| **ADM** | Администратор | IT-администратор / владелец аккаунта |

---

## EPIC 1: Аутентификация и Онбординг

### US-001: Регистрация нового пользователя

```
As a TE (тендерный инженер)
I want to register in BINOM AI using my email and password
So that I can access the platform and start preparing tender documents

Acceptance Criteria:

GIVEN I am a new user on the registration page
WHEN I enter valid email, password (8+ chars), and company name
AND click "Register"
THEN my account is created successfully
AND I receive a confirmation email
AND I am redirected to the onboarding flow

GIVEN I enter an already registered email
WHEN I click "Register"
THEN I see the error: «Пользователь с таким email уже существует»
AND I am prompted to log in

GIVEN I enter invalid email format
WHEN I click "Register"
THEN I see inline validation error immediately
AND the form is not submitted

Priority: Must Have
Sprint: S1
Story Points: 3
```

---

### US-002: Авторизация существующего пользователя

```
As a TM (тендерный менеджер)
I want to log in with my email and password
So that I can access my projects and continue my work

Acceptance Criteria:

GIVEN I am a registered user on the login page
WHEN I enter correct email and password
THEN I am authenticated
AND redirected to the main dashboard

GIVEN I enter incorrect password
WHEN I click "Login"
THEN I see: «Неверный email или пароль»
AND after 5 failed attempts my account is locked for 15 minutes

GIVEN I am already logged in
WHEN I open the app in a new tab
THEN I am directed to dashboard without re-authentication

Priority: Must Have
Sprint: S1
Story Points: 2
```

---

### US-003: Сброс пароля

```
As a TM
I want to reset my password if I forgot it
So that I can regain access to my account

Acceptance Criteria:

GIVEN I am on the login page
WHEN I click "Забыли пароль?"
THEN I am redirected to the password reset page

GIVEN I enter my registered email
WHEN I click "Отправить ссылку"
THEN I receive an email with a reset link within 2 minutes

GIVEN I click the reset link (valid for 1 hour)
WHEN I enter and confirm a new password
THEN my password is updated
AND I am redirected to login

GIVEN the reset link has expired (> 1 hour)
WHEN I click it
THEN I see: «Ссылка истекла. Запросите новую.»

Priority: Must Have
Sprint: S1
Story Points: 2
```

---

### US-004: Заполнение профиля компании

```
As a ADM (администратор)
I want to fill in my company's profile (name, IIN/BIN, address, logo)
So that this information is automatically included in all generated documents

Acceptance Criteria:

GIVEN I am logged in for the first time
WHEN I am on the company profile setup screen
THEN I see fields: Название компании, ИИН/БИН, Адрес, Телефон, Email, Логотип

GIVEN I fill in all required fields and upload a logo (PNG/SVG, < 5 MB)
WHEN I click "Сохранить"
THEN the profile is saved
AND the logo is displayed in the header of the app

GIVEN I view a generated document after profile setup
THEN the company name, IIN, address and logo appear in the document header

GIVEN I update the company profile
WHEN I save changes
THEN all future generated documents use the updated information

Priority: Must Have
Sprint: S1
Story Points: 3
```

---

## EPIC 2: Управление проектами

### US-005: Создание нового тендерного проекта

```
As a TE
I want to create a new tender project
So that I can start working on a specific tender

Acceptance Criteria:

GIVEN I am on the dashboard
WHEN I click "Новый тендер"
THEN a dialog opens asking for: Название тендера, Заказчик (опционально), Дедлайн (опционально)

GIVEN I fill in at least the project name
WHEN I click "Создать"
THEN the project is created with status "Draft"
AND I am redirected to the project workspace

GIVEN I try to create a project with an empty name
WHEN I click "Создать"
THEN I see: «Название тендера обязательно»

Priority: Must Have
Sprint: S1
Story Points: 2
```

---

### US-006: Просмотр списка проектов

```
As a TM
I want to see all my tender projects in a structured list
So that I can quickly navigate to any project and track their statuses

Acceptance Criteria:

GIVEN I am on the dashboard
THEN I see a list of all my projects with:
  - Название проекта
  - Статус (Draft / In Progress / Done / Submitted)
  - Дата создания
  - Дедлайн (если указан)
  - Последнее изменение

GIVEN I have more than 10 projects
THEN the list is paginated (10 per page) or scrollable
AND I can search projects by name

GIVEN I have no projects yet
THEN I see an empty state with a call-to-action "Создать первый тендер"

Priority: Must Have
Sprint: S1
Story Points: 2
```

---

### US-007: Смена статуса проекта

```
As a TM
I want to update the status of a tender project
So that my team knows the current stage of each tender

Acceptance Criteria:

GIVEN I am in a project
WHEN I click on the status badge
THEN I see a dropdown with statuses: Draft, In Progress, Review, Done, Submitted

GIVEN I select a new status
THEN the status updates immediately
AND the change is reflected in the project list

Priority: Must Have
Sprint: S1
Story Points: 1
```

---

### US-008: Удаление проекта

```
As a TM
I want to delete a tender project
So that I can clean up old or irrelevant projects

Acceptance Criteria:

GIVEN I am in the project list or inside a project
WHEN I click "Удалить" and confirm in a confirmation dialog
THEN the project and all its data are permanently deleted
AND I see a success notification

GIVEN I click "Удалить" accidentally
WHEN I see the confirmation dialog and click "Отмена"
THEN nothing is deleted

Priority: Must Have
Sprint: S1
Story Points: 1
```

---

## EPIC 3: Загрузка и обработка документов

### US-009: Загрузка PDF-файла с техническим заданием

```
As a TE
I want to upload a PDF file with the technical specification (ТЗ)
So that BINOM AI can analyze it automatically

Acceptance Criteria:

GIVEN I am in the project workspace
WHEN I drag-and-drop or click to upload a PDF file (< 50 MB)
THEN the upload starts immediately
AND I see a progress bar
AND upload completes in < 10 seconds for a 10 MB file

GIVEN the upload is complete
THEN I see the filename and file size displayed
AND the AI analysis starts automatically
AND I see a loading indicator: «AI анализирует документ...»

GIVEN I try to upload a file > 50 MB
THEN I see: «Файл слишком большой. Максимум: 50 МБ»
AND the upload is rejected

GIVEN I try to upload an unsupported format (e.g., .xlsx)
THEN I see: «Поддерживаются только PDF и DOCX»

Priority: Must Have
Sprint: S1
Story Points: 3
```

---

### US-010: Загрузка DOCX-файла с техническим заданием

```
As a TE
I want to upload a DOCX file with the ТЗ
So that companies using Word format can also use BINOM AI

Acceptance Criteria:

GIVEN I upload a .docx file (< 50 MB)
THEN the same flow as PDF applies
AND the text is correctly extracted from the Word document
AND tables and formatting are preserved in extraction

Priority: Must Have
Sprint: S1
Story Points: 2
```

---

### US-011: Замена документа ТЗ

```
As a TE
I want to replace the uploaded ТЗ document with a newer version
So that I can work with updated technical specifications

Acceptance Criteria:

GIVEN a ТЗ document is already uploaded in the project
WHEN I click "Заменить файл" and upload a new document
THEN a confirmation dialog appears: «Это удалит текущий анализ. Продолжить?»

GIVEN I confirm
THEN the old document is replaced
AND a new AI analysis starts from scratch

GIVEN I cancel
THEN the old document remains unchanged

Priority: Should Have
Sprint: S2
Story Points: 2
```

---

## EPIC 4: AI-анализ документа

### US-012: Просмотр результатов AI-анализа ТЗ

```
As a TE
I want to see structured analysis results after uploading the ТЗ
So that I understand all requirements without reading the full document

Acceptance Criteria:

GIVEN the AI analysis is complete (< 30 seconds after upload)
THEN I see a structured panel with sections:
  - "Технические требования" (list)
  - "Коммерческие требования" (list)
  - "Юридические требования" (list)
  - "Обязательные документы" (checklist)
  - "Оценка сложности" (Low / Medium / High badge)
  - "Краткое резюме" (2–5 sentences)

GIVEN I click on any requirement item
THEN I am shown the source paragraph from the original document

Priority: Must Have
Sprint: S2
Story Points: 5
```

---

### US-013: Просмотр рисков тендера

```
As a TM
I want to see identified risks in the tender
So that I can decide whether to participate and how to mitigate them

Acceptance Criteria:

GIVEN the AI analysis is complete
THEN I see a "Risk Radar" section with:
  - List of identified risks
  - Each risk has: description, severity (High/Medium/Low), recommended action

GIVEN there are no significant risks
THEN I see: «Критических рисков не обнаружено»

GIVEN I click on a risk item
THEN I see the relevant section from the ТЗ that triggered this risk

Priority: Must Have
Sprint: S2
Story Points: 5
```

---

### US-014: Просмотр Gap-анализа

```
As a TM
I want to see what information is missing from the ТЗ or from our company data
So that I can request missing information before submitting

Acceptance Criteria:

GIVEN the AI analysis is complete
THEN I see a "Gap Analysis" section with:
  - List of questions to ask the client (missing info in ТЗ)
  - List of company data needed (pricing, certificates, etc.)

GIVEN all required data is available
THEN I see: «Все необходимые данные присутствуют»

Priority: Must Have
Sprint: S2
Story Points: 3
```

---

## EPIC 5: AI-чат (Интерактивный диалог)

### US-015: AI задаёт уточняющие вопросы

```
As a TE
I want the AI to ask me clarifying questions about the tender
So that the generated documents are accurate and complete

Acceptance Criteria:

GIVEN the AI analysis is complete
WHEN I open the chat panel
THEN AI automatically sends the first question relevant to the loaded ТЗ

GIVEN I answer the first question
WHEN I press Send
THEN AI acknowledges the answer and asks the next question
AND the dialog continues until all critical info is gathered

GIVEN all critical questions are answered
THEN AI shows: «Достаточно информации для генерации документов»
AND the "Generate" button becomes active

Priority: Must Have
Sprint: S2
Story Points: 8
```

---

### US-016: Произвольные вопросы к AI по документу

```
As a TE
I want to ask the AI any question about the uploaded ТЗ
So that I can quickly get answers without reading the full document

Acceptance Criteria:

GIVEN I am in the chat panel
WHEN I type any question about the ТЗ (e.g., «Какой срок строительства указан?»)
AND press Send
THEN AI responds with an accurate answer within 10 seconds
AND cites the relevant section of the ТЗ

GIVEN I ask something not covered in the ТЗ
THEN AI responds: «Эта информация не указана в загруженном ТЗ»

Priority: Should Have
Sprint: S2
Story Points: 5
```

---

### US-017: Сохранение истории диалога

```
As a TM
I want the chat history to be saved within the project
So that I can review previous conversations when returning to the project

Acceptance Criteria:

GIVEN I had a conversation in the chat
WHEN I close the browser and reopen the project
THEN the full chat history is displayed in the correct order

Priority: Must Have
Sprint: S2
Story Points: 2
```

---

## EPIC 6: Генерация документов

### US-018: Генерация коммерческого предложения (КП)

```
As a TE
I want to generate a commercial proposal (КП) automatically
So that I save hours of manual drafting

Acceptance Criteria:

GIVEN the AI chat is complete and all required info is gathered
WHEN I click "Сгенерировать → Коммерческое предложение"
THEN a progress indicator is shown
AND the document is generated within 60 seconds

GIVEN the document is generated
THEN it contains the following sections:
  - Титульный лист (название компании, логотип, дата)
  - Вводная часть (кому, от кого, суть предложения)
  - Техническое решение (краткое описание)
  - Коммерческие условия (цена, сроки, гарантии)
  - Список документов в приложении
  - Подпись и реквизиты компании

AND all text is relevant to the requirements from the loaded ТЗ
AND the document is in Russian

Priority: Must Have
Sprint: S3
Story Points: 8
```

---

### US-019: Генерация технической спецификации

```
As a TE
I want to generate a technical specification document automatically
So that I don't need to manually write the technical section

Acceptance Criteria:

GIVEN generation conditions are met (same as US-018)
WHEN I click "Сгенерировать → Техническая спецификация"
THEN document is generated within 60 seconds

GIVEN the document is generated
THEN it contains:
  - Общие сведения о предмете тендера
  - Техническое описание предлагаемого решения
  - Технические характеристики и параметры
  - Соответствие требованиям ТЗ (таблица)
  - Нормативная база (ГОСТы, СНиПы, СП)
  - Сроки реализации

AND all technical terms and requirements from the ТЗ are addressed

Priority: Must Have
Sprint: S3
Story Points: 8
```

---

### US-020: Генерация сопроводительного письма

```
As a TM
I want to generate a professional cover letter for the tender
So that our submission looks professional and complete

Acceptance Criteria:

GIVEN generation conditions are met
WHEN I click "Сгенерировать → Сопроводительное письмо"
THEN document is generated within 30 seconds

GIVEN the document is generated
THEN it contains:
  - Правильное обращение (к заказчику тендера)
  - Краткое представление компании
  - Выражение интереса к тендеру
  - Подтверждение приложенных документов
  - Контактная информация
  - Дата и подпись

Priority: Must Have
Sprint: S3
Story Points: 5
```

---

### US-021: Онлайн-редактирование сгенерированного документа

```
As a TE
I want to edit the generated document directly in the browser
So that I can refine the text without downloading and re-uploading

Acceptance Criteria:

GIVEN a document is generated
THEN I can see it in an inline editor (rich text editor)
AND I can edit any text, heading, or paragraph
AND changes are auto-saved every 30 seconds

GIVEN I make changes and close the editor
WHEN I reopen the document
THEN all my changes are preserved

Priority: Must Have
Sprint: S3
Story Points: 5
```

---

### US-022: Регенерация отдельной секции документа

```
As a TE
I want to regenerate just one section of the document without regenerating the whole thing
So that I can improve specific parts while keeping the rest intact

Acceptance Criteria:

GIVEN I am editing a generated document
WHEN I right-click (or use a button) on a specific section
THEN I see the option "Перегенерировать эту секцию"

GIVEN I click "Перегенерировать"
THEN only that section is re-generated by AI within 20 seconds
AND the rest of the document is unchanged

Priority: Should Have
Sprint: S3
Story Points: 5
```

---

## EPIC 7: Экспорт документов

### US-023: Экспорт документа в DOCX

```
As a TM
I want to export the generated document as a .docx file
So that I can submit it as part of the tender package or review it in Word

Acceptance Criteria:

GIVEN a document is generated (and optionally edited)
WHEN I click "Экспорт → DOCX"
THEN a .docx file downloads within 10 seconds

GIVEN the file downloads
THEN it opens in Microsoft Word without errors
AND all formatting is preserved (headings, tables, bold text)
AND company logo is present in the header (if uploaded)
AND company name and IIN appear in the footer

Priority: Must Have
Sprint: S3
Story Points: 5
```

---

### US-024: Экспорт документа в PDF

```
As a TM
I want to export the generated document as a .pdf file
So that I can submit it officially (PDF is often required for tenders)

Acceptance Criteria:

GIVEN a document is generated
WHEN I click "Экспорт → PDF"
THEN a .pdf file downloads within 10 seconds

GIVEN the PDF downloads
THEN it is text-searchable (not a scan)
AND formatting matches the DOCX version
AND all pages are numbered

Priority: Must Have
Sprint: S3
Story Points: 3
```

---

## EPIC 8: Настройки и профиль

### US-025: Редактирование профиля пользователя

```
As a TE
I want to update my name, job title and contact info
So that the generated documents reflect my correct information

Acceptance Criteria:

GIVEN I am on the Profile Settings page
WHEN I update name, job title, or phone
AND click "Сохранить"
THEN changes are saved and reflected in the user menu

Priority: Must Have
Sprint: S1
Story Points: 2
```

---

### US-026: Обновление профиля компании

```
As a ADM
I want to update company information (logo, IIN, address)
So that all documents reflect the latest company data

Acceptance Criteria:

GIVEN I am on Company Settings
WHEN I change any field and save
THEN all future generated documents use the updated data

GIVEN I upload a new logo
THEN the new logo appears in the app header and in all new documents

Priority: Must Have
Sprint: S1
Story Points: 2
```

---

## EPIC 9: Безопасность и доступ

### US-027: Изоляция данных компании

```
As a ADM
I want to ensure that only users from my company can see our projects and documents
So that our sensitive tender data is not accessible to other companies

Acceptance Criteria:

GIVEN I log in as User A (Company A)
THEN I can only see projects belonging to Company A
AND I cannot access any URL or API endpoint to view Company B's data

GIVEN I manually try to access another company's project by URL
THEN I receive a 403 Forbidden error
AND no data is exposed

Priority: Must Have
Sprint: S1
Story Points: 3
```

---

### US-028: Управление сессиями

```
As a TE
I want my session to be valid for 24 hours
So that I don't need to re-login every time during the workday

Acceptance Criteria:

GIVEN I logged in
THEN my session is valid for 24 hours of inactivity
AND is renewed automatically on each active use

GIVEN my session expires
WHEN I try to perform any action
THEN I am redirected to the login page
AND see: «Ваша сессия истекла. Войдите снова.»

Priority: Must Have
Sprint: S1
Story Points: 2
```

---

## EPIC 10: Уведомления и обратная связь

### US-029: Уведомление об успешной генерации

```
As a TE
I want to receive a visual notification when document generation is complete
So that I know when to proceed to the next step

Acceptance Criteria:

GIVEN I triggered document generation
WHEN generation completes successfully
THEN I see a success toast notification: «Документ готов!»
AND the document appears in the editor immediately

GIVEN generation fails due to an AI error
THEN I see an error notification: «Ошибка генерации. Попробуйте снова.»
AND I can click "Retry"

Priority: Must Have
Sprint: S3
Story Points: 2
```

---

### US-030: Оценка качества сгенерированного документа

```
As a TM
I want to rate the quality of the generated document (thumbs up/down)
So that the team can track AI quality and improve over time

Acceptance Criteria:

GIVEN a document is generated
WHEN I see the document in the editor
THEN I see a feedback section: 👍 / 👎 + optional comment field

GIVEN I click 👎 (thumbs down)
THEN I am prompted to select the reason:
  - «Нерелевантный контент»
  - «Неправильная структура»
  - «Ошибки в тексте»
  - «Другое»

GIVEN I submit feedback
THEN feedback is saved
AND I see: «Спасибо за отзыв! Мы улучшим качество.»

Priority: Should Have
Sprint: S3
Story Points: 3
```

---

## EPIC 11: Административные функции

### US-031: Просмотр статистики использования (Admin)

```
As a ADM
I want to see how many projects are created and documents generated per month
So that I can track usage and plan our subscription

Acceptance Criteria:

GIVEN I am on the Admin dashboard
THEN I see statistics:
  - Всего проектов
  - Созданных за последние 30 дней
  - Сгенерированных документов
  - Использовано AI-запросов (токенов)

Priority: Could Have
Sprint: Post-MVP
Story Points: 5
```

---

## Story Map (Визуальная карта историй)

```
BINOM AI — User Story Map

╔══════════════╦═══════════════╦═══════════════╦═══════════════╦═══════════════╗
║  Sprint 1    ║   Sprint 2    ║   Sprint 3    ║   Sprint 4    ║  Post-MVP     ║
╠══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╣
║ US-001 Рег.  ║ US-012 Анализ ║ US-018 Ген КП ║ US-008 Multi  ║ US-031 Admin  ║
║ US-002 Вход  ║ US-013 Риски  ║ US-019 Ген ТС ║ user          ║ Dashboard     ║
║ US-003 Пароль║ US-014 Gaps   ║ US-020 Письмо ║               ║               ║
║ US-004 Профиль║ US-015 AI ❓  ║ US-021 Редакт ║               ║               ║
║ US-005 Проект║ US-016 Вопрос ║ US-022 Регенер║               ║               ║
║ US-006 Список║ US-017 История║ US-023 DOCX   ║               ║               ║
║ US-007 Статус║               ║ US-024 PDF    ║               ║               ║
║ US-008 Удал  ║               ║ US-029 Нотиф  ║               ║               ║
║ US-009 PDF↑  ║               ║ US-030 Оценка ║               ║               ║
║ US-010 DOCX↑ ║               ║               ║               ║               ║
║ US-025 Профиль║              ║               ║               ║               ║
║ US-026 Компания║             ║               ║               ║               ║
║ US-027 Изоляц║               ║               ║               ║               ║
║ US-028 Сессия║               ║               ║               ║               ║
╚══════════════╩═══════════════╩═══════════════╩═══════════════╩═══════════════╝
```

---

## Backlog приоритизация (MoSCoW)

### Must Have (критично для MVP)
US-001, US-002, US-003, US-004, US-005, US-006, US-007, US-008, US-009, US-010, US-012, US-013, US-014, US-015, US-017, US-018, US-019, US-020, US-021, US-023, US-024, US-025, US-026, US-027, US-028, US-029

### Should Have (важно, но не блокирует)
US-011, US-016, US-022, US-030

### Could Have (желательно)
US-031

### Won't Have (в MVP)
Multi-user invitation, SSO, billing, OCR, mobile app

---

## Общий счёт Story Points

| Sprint | Stories | Total Points |
|--------|---------|-------------|
| Sprint 1 | 14 stories | 27 SP |
| Sprint 2 | 6 stories | 28 SP |
| Sprint 3 | 7 stories | 34 SP |
| Post-MVP | 4 stories | 18 SP |
| **Итого MVP** | **27 stories** | **89 SP** |

---

*Документ подготовлен командой BINOM AI. User Stories v1.0 — утверждён.*  
*Следующий документ: [Roadmap.md](./Roadmap.md)*
