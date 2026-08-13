# BINOM AI — UI Components v1.0

**Документ:** UI Components  
**Версия:** 1.0  
**Дата:** 2026-07-09  
**Статус:** ✅ Утверждён  
**Автор:** Frontend Lead / Designer  
**Важно:** Документирует существующие UI-компоненты Frontend. Не предполагает изменений.

---

## 1. Обзор компонентного состава

BINOM AI использует компонентную архитектуру на основе React/Next.js. Все компоненты соответствуют Design System v1.0.

### Иерархия компонентов

```
Atoms (базовые)
  → Molecules (составные)
    → Organisms (сложные)
      → Templates (шаблоны страниц)
        → Pages (страницы)
```

---

## 2. ATOMS — Базовые компоненты

### 2.1 Button

**Расположение:** `components/ui/Button.tsx`

```typescript
interface ButtonProps {
  variant: 'primary' | 'secondary' | 'ghost' | 'danger' | 'ai';
  size: 'sm' | 'md' | 'lg' | 'xl';
  loading?: boolean;      // Спиннер + disabled
  icon?: ReactNode;       // Иконка слева
  iconRight?: ReactNode;  // Иконка справа
  fullWidth?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  type?: 'button' | 'submit';
  children: ReactNode;
}
```

**Состояния:** default, hover, active, loading, disabled  
**Специальный variant `ai`:** использует gradient-ai + AI glow

---

### 2.2 Input

**Расположение:** `components/ui/Input.tsx`

```typescript
interface InputProps {
  label?: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  type?: 'text' | 'email' | 'password' | 'number' | 'search';
  error?: string;          // Сообщение об ошибке
  hint?: string;           // Подсказка под полем
  icon?: ReactNode;        // Иконка слева
  iconRight?: ReactNode;   // Иконка справа (например, eye для пароля)
  disabled?: boolean;
  required?: boolean;
  size?: 'sm' | 'md' | 'lg';
}
```

**Состояния:** default, focus (border: primary), error (border: red), disabled

---

### 2.3 Textarea

```typescript
interface TextareaProps {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  maxLength?: number;
  showCount?: boolean;   // Счётчик символов
  error?: string;
  disabled?: boolean;
  autoResize?: boolean;  // Авторасширение по контенту
}
```

---

### 2.4 Badge

```typescript
interface BadgeProps {
  variant: 'default' | 'primary' | 'success' | 'warning' | 'error' | 'info';
  size?: 'sm' | 'md';
  dot?: boolean;        // Цветная точка перед текстом
  children: ReactNode;
}
```

---

### 2.5 Status Badge

Специализированный Badge для статусов проектов.

```typescript
interface StatusBadgeProps {
  status: 'draft' | 'analyzing' | 'clarifying' | 'generating' | 
          'review' | 'done' | 'submitted' | 'archived';
  animated?: boolean;   // Мигающая точка для активных статусов
}
```

Пример отображения:
```
🔵 Draft      🟡 Analyzing...    🔷 Clarifying
🟣 Generating  🟠 Review         ✅ Done
📤 Submitted   📁 Archived
```

---

### 2.6 Risk Badge

```typescript
interface RiskBadgeProps {
  severity: 'High' | 'Medium' | 'Low';
  showIcon?: boolean;
}
```

Отображение:
```
🔴 High Risk     🟡 Medium Risk     🟢 Low Risk
```

---

### 2.7 Avatar

```typescript
interface AvatarProps {
  name: string;           // Генерирует инициалы если нет image
  src?: string;           // URL изображения
  size?: 'sm' | 'md' | 'lg' | 'xl';
  online?: boolean;       // Индикатор онлайн
}
```

---

### 2.8 Spinner / Loader

```typescript
interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'ai';   // 'ai' — градиентный спиннер
  label?: string;                // Текст под спиннером
}
```

---

### 2.9 Progress Bar

```typescript
interface ProgressBarProps {
  value: number;           // 0–100
  variant?: 'default' | 'ai';
  size?: 'sm' | 'md' | 'lg';
  animated?: boolean;      // Shimmer анимация
  label?: string;          // Подпись
  showValue?: boolean;     // Показывать процент
}
```

---

### 2.10 Tooltip

```typescript
interface TooltipProps {
  content: string | ReactNode;
  position?: 'top' | 'bottom' | 'left' | 'right';
  delay?: number;
  children: ReactNode;
}
```

---

### 2.11 Divider

```typescript
interface DividerProps {
  orientation?: 'horizontal' | 'vertical';
  label?: string;   // Текст посередине
  spacing?: 'sm' | 'md' | 'lg';
}
```

---

## 3. MOLECULES — Составные компоненты

### 3.1 FileUploadZone

**Расположение:** `components/molecules/FileUploadZone.tsx`

**Описание:** Зона drag-and-drop для загрузки ТЗ.

```typescript
interface FileUploadZoneProps {
  onFileSelect: (file: File) => void;
  accept?: string[];        // ['application/pdf', 'application/docx']
  maxSizeMB?: number;       // default: 50
  currentFile?: {           // Уже загруженный файл
    filename: string;
    size_bytes: number;
    status: 'processing' | 'ready' | 'error';
  };
  onReplace?: () => void;   // Кнопка "Заменить"
}
```

**Состояния:**
- **Empty:** Иконка загрузки + текст «Перетащите PDF или DOCX сюда»
- **Drag Over:** Граница подсвечивается primary цветом, анимация
- **Uploading:** Progress bar + имя файла
- **Processing:** AI spinner + «Документ обрабатывается»
- **Ready:** Имя файла + размер + кнопка «Заменить»
- **Error:** Красный border + сообщение об ошибке

**UI:**
```
┌─────────────────────────────────────────────┐
│                                             │
│         ☁ Загрузить ТЗ                     │
│                                             │
│    Перетащите PDF или DOCX сюда,            │
│    или нажмите для выбора файла             │
│                                             │
│         До 50 МБ • PDF • DOCX              │
│                                             │
└─────────────────────────────────────────────┘
```

---

### 3.2 SearchInput

```typescript
interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  onClear?: () => void;
}
```

---

### 3.3 SelectMenu

```typescript
interface SelectMenuProps {
  options: { value: string; label: string; icon?: ReactNode }[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  error?: string;
}
```

---

### 3.4 ContextMenu

```typescript
interface ContextMenuProps {
  trigger: ReactNode;     // Элемент, на который кликают
  items: {
    label: string;
    icon?: ReactNode;
    onClick: () => void;
    variant?: 'default' | 'danger';
    divider?: boolean;    // Разделитель перед этим пунктом
  }[];
}
```

---

### 3.5 ConfirmDialog

```typescript
interface ConfirmDialogProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'danger';
}
```

---

### 3.6 Toast / Notification

```typescript
type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastProps {
  type: ToastType;
  title: string;
  description?: string;
  duration?: number;     // ms, default: 4000
  action?: {
    label: string;
    onClick: () => void;
  };
}
```

**Позиция:** Bottom-right corner  
**Стэкинг:** До 5 уведомлений одновременно

---

### 3.7 EmptyState

```typescript
interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
    variant?: 'primary' | 'secondary';
  };
}
```

Пример использования: пустой список проектов, отсутствие данных анализа.

---

### 3.8 ChatMessage

```typescript
interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  messageType?: 'question' | 'answer' | 'info' | 'completion';
  isLoading?: boolean;   // AI typing indicator
}
```

**UI:**
```
AI Message (left-aligned):
┌──────────────────────────────────────────────┐
│ 🤖 BINOM AI                         12:08   │
│                                              │
│ Для подготовки КП нам нужно уточнить:       │
│ Какой опыт в строительстве НПЗ у вашей      │
│ компании? Укажите количество проектов.       │
└──────────────────────────────────────────────┘

User Message (right-aligned):
                   ┌───────────────────────────┐
              12:09│                           │
                   │ У нас 3 проекта за 7 лет  │
                   │ суммарной мощностью 800к  │
                   └───────────────────────────┘
```

---

### 3.9 RequirementItem

Компонент для отображения одного требования из анализа.

```typescript
interface RequirementItemProps {
  requirement: {
    id: string;
    text: string;
    category: string;
    is_mandatory: boolean;
    source_section: string;
    source_page?: number;
  };
  onSourceClick?: (section: string, page?: number) => void;
}
```

---

### 3.10 RiskItem

```typescript
interface RiskItemProps {
  risk: {
    id: string;
    description: string;
    severity: 'High' | 'Medium' | 'Low';
    risk_type: string;
    mitigation: string;
  };
  expanded?: boolean;
  onToggle?: () => void;
}
```

**UI:**
```
┌─────────────────────────────────────────────────────┐
│ 🔴 High  │ Финансовый риск                    [∨] │
│          │ Банковская гарантия 10% от суммы...     │
│          │ ─────────────────────────────────────── │
│          │ 💡 Рекомендация: Заблаговременно         │
│          │    связаться с банком...                │
└─────────────────────────────────────────────────────┘
```

---

## 4. ORGANISMS — Сложные компоненты

### 4.1 TopBar

**Расположение:** `components/organisms/TopBar.tsx`

```typescript
interface TopBarProps {
  project?: {
    id: string;
    name: string;
    status: string;
  };
}
```

**Структура:**
```
┌─────────────────────────────────────────────────────────┐
│ [BINOM AI Logo]  [Project Name] [Status Badge]   [User] │
└─────────────────────────────────────────────────────────┘
```

**Элементы:**
- Логотип BINOM AI (кликабельный → dashboard)
- Название текущего проекта (если открыт проект)
- Status Badge текущего проекта
- Уведомления (bell icon)
- User Menu (avatar → dropdown: профиль, настройки, выход)

---

### 4.2 Sidebar

```typescript
interface SidebarProps {
  currentProjectId?: string;
  collapsed?: boolean;
  onCollapse?: () => void;
}
```

**Структура:**
```
┌──────────────┐
│ 🏠 Dashboard │
│              │
│ ── ПРОЕКТЫ ──│
│ + Новый тендер│
│              │
│ 📁 [Проект 1]│   ← Active Project
│   ├ 📄 ТЗ   │
│   ├ 🤖 Анализ│
│   ├ 💬 Чат  │
│   └ 📝 Доки │
│              │
│ ── ─────── ──│
│ ⚙ Настройки │
│              │
└──────────────┘
```

**Navigation items:**
- Dashboard (список всех проектов)
- Новый тендер (+)
- Текущий проект — sub-items: ТЗ, Анализ, Чат, Документы
- Настройки

---

### 4.3 ProjectCard

**Расположение:** `components/organisms/ProjectCard.tsx`

```typescript
interface ProjectCardProps {
  project: ProjectSummary;
  onClick: () => void;
  onDelete: (id: string) => void;
  onStatusChange: (id: string, status: string) => void;
}
```

**UI:**
```
┌──────────────────────────────────────────────────────────┐
│  Тендер на строительство завода, г. Шымкент         [⋮] │
│                                                          │
│  АО «НефтеХимПроект»            🔴 High Complexity      │
│                                                          │
│  [● Analyzing...]  47 требований  3 риска               │
│                                                          │
│  📎 ТЗ готово   📊 Анализ: ✅   💬 Чат: 6/10   📝 КП: ✅ │
│                                                          │
│  Дедлайн: 15 Aug 2026                    Изменён вчера  │
└──────────────────────────────────────────────────────────┘
```

---

### 4.4 AnalysisPanel

**Расположение:** `components/organisms/AnalysisPanel.tsx`

Основная панель с результатами AI-анализа ТЗ.

**Структура:**
```
┌──────────────────────────────────────────────────────────┐
│ 🤖 AI Анализ                              [Обновить]    │
│                                                          │
│ ── Резюме ──────────────────────────────────────────   │
│ Тендер EPC на НПЗ мощностью 500к т/год. Высокая         │
│ сложность. Рекомендуется привлечение субподрядчиков.    │
│                                                          │
│ ── Требования (47) ─────────────────────────────────   │
│ [Технические ▾] [Коммерческие ▾] [Юридические ▾]       │
│                                                          │
│ ✅ Срок строительства не более 18 месяцев               │
│    Раздел 3.2 • Страница 12                             │
│                                                          │
│ ✅ Мощность завода 500,000 т/год                        │
│    Раздел 3.1 • Страница 10                             │
│                                                          │
│ ── Риски (3) ───────────────────────────────────────   │
│ 🔴 Банковская гарантия 10% — сложное условие           │
│ 🟡 Неточный срок проектирования                        │
│ 🟢 Стандартные экологические требования                │
│                                                          │
│ ── Gap Analysis ─────────────────────────────────────  │
│ ❓ Не указан точный адрес площадки                     │
│ ❓ Нет данных о геологии                               │
└──────────────────────────────────────────────────────────┘
```

---

### 4.5 ChatPanel

**Расположение:** `components/organisms/ChatPanel.tsx`

```typescript
interface ChatPanelProps {
  projectId: string;
  messages: ChatMessage[];
  sessionStatus: {
    is_complete: boolean;
    questions_remaining: number;
  };
  onSendMessage: (content: string) => void;
  isLoading: boolean;
}
```

**UI:**
```
┌──────────────────────────────────────────────────────────┐
│ 💬 AI Диалог                     [3 вопроса осталось]   │
│                                                          │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ 🤖 BINOM AI                              12:08      │ │
│ │ Какой опыт в строительстве НПЗ у вашей компании?    │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│         ┌──────────────────────────────────────────┐     │
│         │ У нас 3 проекта НПЗ за последние 7 лет  │     │
│         │                                    12:09 │     │
│         └──────────────────────────────────────────┘     │
│                                                          │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ 🤖 ● ● ●  (typing...)                               │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│ ┌──────────────────────────────────────────────────┐ [▶] │
│ │ Введите ответ...                                 │     │
│ └──────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────┘
```

---

### 4.6 DocumentGeneratorPanel

**Расположение:** `components/organisms/DocumentGeneratorPanel.tsx`

```typescript
interface DocumentGeneratorPanelProps {
  projectId: string;
  isReadyForGeneration: boolean;
  generatedDocs: GeneratedDocumentSummary[];
  onGenerate: (docType: string) => void;
  onViewDocument: (docId: string) => void;
}
```

**UI:**
```
┌──────────────────────────────────────────────────────────┐
│ 📝 Генерация документов                                  │
│                                                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Коммерческое предложение              ✅ Готово [▶]  │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Техническая спецификация                [Создать]   │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Сопроводительное письмо                [Создать]    │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ ⚡ Генерация занимает около 45–60 секунд                 │
└──────────────────────────────────────────────────────────┘
```

---

### 4.7 DocumentEditor

**Расположение:** `components/organisms/DocumentEditor.tsx`

Rich-text редактор для сгенерированных документов.

```typescript
interface DocumentEditorProps {
  document: GeneratedDocument;
  onSave: (content: { html: string; json: any }) => void;
  onExport: (format: 'docx' | 'pdf') => void;
  onRegenerate: (sectionId: string) => void;
  isAutoSaving?: boolean;
}
```

**UI:**
```
┌──────────────────────────────────────────────────────────┐
│ [B] [I] [U] [H1] [H2] [•] [1.] [─]   [💾 Сохранено] [×] │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ                               │
│  ─────────────────────────────────                     │
│                                                          │
│  ТОО «КазСтройПроект»                                  │
│  Дата: 09.07.2026 | КП № 2026-001                      │
│                                                          │
│  1. ВВОДНАЯ ЧАСТЬ                                        │
│  ─────────────────                                      │
│  Уважаемые коллеги из АО «НефтеХимПроект»!             │
│  В ответ на ваше техническое задание от 15.06.2026...   │
│                  [↻ Перегенерировать раздел]            │
│                                                          │
│  2. О КОМПАНИИ                                          │
│  ────────────                                           │
│  ТОО «КазСтройПроект» — ведущая строительная...       │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ [📥 Скачать DOCX]    [📄 Скачать PDF]    [👍] [👎]       │
└──────────────────────────────────────────────────────────┘
```

**Toolbar actions:**
- Форматирование: Bold, Italic, Underline
- Заголовки: H1, H2, H3
- Списки: маркированный, нумерованный
- Горизонтальная линия
- Авто-сохранение (каждые 30 сек)

---

### 4.8 ExportButtons

```typescript
interface ExportButtonsProps {
  docId: string;
  projectId: string;
  onExport: (format: 'docx' | 'pdf') => void;
  isExporting?: { docx: boolean; pdf: boolean };
}
```

---

### 4.9 FeedbackWidget

```typescript
interface FeedbackWidgetProps {
  docId: string;
  onSubmit: (rating: 1 | 5, reason?: string, text?: string) => void;
}
```

**UI:**
```
┌──────────────────────────────────────────┐
│ Оцените качество документа:              │
│                                          │
│    [👍 Отлично]     [👎 Плохо]           │
└──────────────────────────────────────────┘

После нажатия 👎:
┌──────────────────────────────────────────┐
│ Что не так с документом?                │
│                                          │
│ ○ Нерелевантный контент                 │
│ ○ Неправильная структура                │
│ ○ Ошибки в тексте                       │
│ ○ Другое                               │
│                                          │
│ [Написать комментарий...]               │
│                                          │
│                          [Отправить]    │
└──────────────────────────────────────────┘
```

---

### 4.10 OnboardingModal

```typescript
interface OnboardingModalProps {
  isOpen: boolean;
  onComplete: () => void;
  currentStep: number;
}
```

**Шаги онбординга:**
1. Добро пожаловать в BINOM AI
2. Заполните профиль компании
3. Создайте первый тендер
4. Загрузите техническое задание
5. Готово! Первый тендер создан

---

## 5. TEMPLATES — Шаблоны страниц

### 5.1 AuthLayout

```typescript
// Обёртка для страниц аутентификации
interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  description?: string;
}
```

**Структура:**
```
┌─────────────────────────────────────────────────────────┐
│                 [BINOM AI Logo]                         │
│                                                         │
│       ┌───────────────────────────────┐                │
│       │  {title}                      │                │
│       │  {description}                │                │
│       │                               │                │
│       │  {children (form)}            │                │
│       └───────────────────────────────┘                │
│                                                         │
│       © 2026 BINOM AI • Kazakhstan                      │
└─────────────────────────────────────────────────────────┘
```

---

### 5.2 AppLayout

```typescript
// Основной shell приложения (после логина)
interface AppLayoutProps {
  children: ReactNode;
}
```

**Структура:**
```
┌─────────────────────────────────────────────────────────┐
│                     TopBar (64px)                       │
├────────────┬────────────────────────────────────────────┤
│ Sidebar    │                                            │
│ (240px)    │           Page Content                     │
│            │           (children)                       │
│            │                                            │
└────────────┴────────────────────────────────────────────┘
```

---

### 5.3 ProjectLayout

```typescript
// Обёртка для страниц внутри проекта
interface ProjectLayoutProps {
  children: ReactNode;
  projectId: string;
  activeTab: 'document' | 'analysis' | 'chat' | 'generate' | 'export';
}
```

**Структура (горизонтальные вкладки):**
```
┌─────────────────────────────────────────────────────────┐
│  ← Все проекты   |   Тендер НПЗ Шымкент   [● Analyzing]│
├────────────────────────────────────────────────────────-┤
│ [📄 ТЗ] [🤖 Анализ] [💬 Диалог] [📝 Документы] [📥 Экспорт]│
├─────────────────────────────────────────────────────────┤
│                                                         │
│                   {children}                            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 6. PAGES — Страницы

### 6.1 /login — Страница входа

**Компоненты:** AuthLayout, Input, Button, Logo  
**API:** POST /auth/login

```
[Логотип]

Войти в BINOM AI

[Email] ______________________

[Пароль] _____________________  [👁]

[✓] Запомнить меня

[     Войти     ]

Нет аккаунта? Зарегистрироваться →
Забыли пароль? →
```

---

### 6.2 /register — Страница регистрации

**API:** POST /auth/register

```
[Логотип]

Создать аккаунт

[Полное имя] _________________________

[Email] ______________________________

[Название компании] __________________

[Пароль] ___________________________

[Подтвердите пароль] ________________

[   Создать аккаунт   ]

Уже есть аккаунт? Войти →
```

---

### 6.3 /dashboard — Главная страница

**API:** GET /projects

```
┌──────────────────────────────────────────────────────────┐
│  Мои тендеры                         [+ Новый тендер]   │
│                                                          │
│  [🔍 Поиск...]  [Статус: Все ▾]  [Сортировка ▾]        │
│                                                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │
│  │ ProjectCard │ │ ProjectCard │ │ ProjectCard │        │
│  └─────────────┘ └─────────────┘ └─────────────┘        │
│                                                          │
│  ┌─────────────┐ ┌─────────────┐                        │
│  │ ProjectCard │ │ ProjectCard │                        │
│  └─────────────┘ └─────────────┘                        │
│                                                          │
│  Показано 5 из 12 проектов        [Загрузить ещё]       │
└──────────────────────────────────────────────────────────┘
```

---

### 6.4 /projects/{id}/document — Страница ТЗ

```
┌──────────────────────────────────────────────────────────┐
│ 📄 Техническое задание                                   │
│                                                          │
│ [Зона загрузки FileUploadZone]                          │
│                                                          │
│ ─────── После загрузки ────────────────                 │
│                                                          │
│ tz_zavod_shymkent.pdf  |  2.3 МБ  |  87 страниц        │
│ [✅ Обработан]                    [Заменить файл]       │
│                                                          │
│ Следующий шаг → [Перейти к анализу →]                   │
└──────────────────────────────────────────────────────────┘
```

---

### 6.5 /projects/{id}/analysis — Страница анализа

```
┌──────────────────────────────────────────────────────────┐
│ 🤖 AI Анализ ТЗ                                          │
│                                                          │
│ [AnalysisPanel — полный результат анализа]               │
│                                                          │
│ ─────────────────────────────────────────               │
│ Следующий шаг → [Перейти к диалогу →]                   │
└──────────────────────────────────────────────────────────┘
```

---

### 6.6 /projects/{id}/chat — Страница диалога

**Двухколоночный layout:**

```
┌────────────────────────────────────────────────────────┐
│ 💬 AI Диалог                                           │
├──────────────────────────┬─────────────────────────────┤
│   ChatPanel (основной)   │  Контекст (sidebar)         │
│                          │                             │
│  [Сообщения...]          │  ✅ Опыт: 3 проекта НПЗ    │
│                          │  ❓ Цена: не указана        │
│                          │  ❓ Сроки: не указаны       │
│  [Input + Send]          │                             │
│                          │  Готовность: 40%            │
│                          │  [████░░░░░░]               │
└──────────────────────────┴─────────────────────────────┘
```

---

### 6.7 /projects/{id}/generate — Страница генерации

**Трёхколоночный layout:**

```
┌──────────────────────────────────────────────────────────┐
│ 📝 Документы                                             │
├──────────────┬────────────────────────────────┬─────────-┤
│  Выбор       │  Редактор                      │ Экспорт │
│  документа   │                                │         │
│              │  [DocumentEditor]              │ [DOCX]  │
│  [КП] ←      │                                │ [PDF]   │
│  [ТС]        │                                │         │
│  [Письмо]    │  [Toolbar]                     │ [👍👎]  │
│              │  [Content]                     │         │
│  [Generate]  │  [Save indicator]              │         │
└──────────────┴────────────────────────────────┴─────────-┘
```

---

### 6.8 /settings — Страница настроек

**Tabbed layout:**

```
┌──────────────────────────────────────────────────────────┐
│ ⚙️ Настройки                                             │
│                                                          │
│ [Профиль] [Компания] [Безопасность] [Уведомления]       │
│ ─────────────────────────────────────                   │
│                                                          │
│ Профиль пользователя:                                    │
│ FullName: [Асель Нурова              ]                   │
│ Title:    [Руководитель тендерного...]                   │
│ Phone:    [+7 700 123 4567           ]                   │
│                                                          │
│                               [Сохранить изменения]     │
└──────────────────────────────────────────────────────────┘
```

---

## 7. Responsive Breakpoints

| Компонент | Mobile (<768) | Tablet (768–1024) | Desktop (>1024) |
|-----------|--------------|-------------------|-----------------|
| Sidebar | Slide-out drawer | Collapsed (icons) | Full (240px) |
| ProjectCard | Stack single col | 2 columns | 3 columns |
| DocumentEditor | Full screen | Full screen | 2/3 width |
| ChatPanel | Full screen | Full screen | Side-by-side |
| AnalysisPanel | Accordion | Accordion | Expanded |

---

## 8. Состояния компонентов (States Matrix)

| Компонент | Loading | Empty | Error | Success | Disabled |
|-----------|---------|-------|-------|---------|----------|
| FileUploadZone | ✅ | ✅ | ✅ | ✅ | ✅ |
| AnalysisPanel | ✅ | ✅ | ✅ | ✅ | — |
| ChatPanel | ✅ | ✅ | ✅ | ✅ | — |
| DocumentEditor | ✅ | — | ✅ | ✅ | — |
| Button | ✅ | — | — | — | ✅ |
| Input | — | — | ✅ | — | ✅ |
| ProjectCard | ✅ | — | ✅ | ✅ | — |

---

*Документ подготовлен командой BINOM AI. UI Components v1.0 — утверждён.*  
*Следующий документ: [UX Flow.md](./UX%20Flow.md)*
