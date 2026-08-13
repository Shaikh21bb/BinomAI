# BINOM AI — Design System v1.0

**Документ:** Design System  
**Версия:** 1.0  
**Дата:** 2026-07-09  
**Статус:** ✅ Утверждён  
**Автор:** Designer / Frontend Lead  
**Важно:** Этот документ описывает дизайн-систему существующего Frontend. Используется для понимания UI при интеграции API. Изменения в Frontend не производятся.

---

## 1. Принципы дизайна

### 1.1 Design Philosophy

BINOM AI использует **Enterprise Dark Design** — тёмная тема с акцентами, характерная для профессиональных B2B SaaS продуктов (Notion, Linear, Figma, Vercel).

**Пять ключевых принципов:**

| Принцип | Описание |
|---------|----------|
| **Minimal** | Нет лишних элементов. Каждый пиксель имеет смысл |
| **Professional** | Деловой стиль, Enterprise-grade |
| **AI-Native** | Визуальный язык AI: градиенты, анимации, «умные» индикаторы |
| **Information Dense** | Много информации без ощущения перегруженности |
| **Action-Oriented** | Главный призыв к действию всегда заметен |

### 1.2 Brand Identity

```
BINOM AI

Значение имени:
BINOM = Бином (математика) + AI
Символизирует точность, структуру и интеллект

Логотип: Геометрическая форма (ромб / двойной треугольник)
с градиентом от синего к фиолетовому
```

---

## 2. Цветовая палитра

### 2.1 Primary Colors

```css
/* Brand Primary */
--color-primary-50:  #EEF2FF;
--color-primary-100: #E0E7FF;
--color-primary-200: #C7D2FE;
--color-primary-300: #A5B4FC;
--color-primary-400: #818CF8;
--color-primary-500: #6366F1;  /* Primary */
--color-primary-600: #4F46E5;  /* Primary Hover */
--color-primary-700: #4338CA;
--color-primary-800: #3730A3;
--color-primary-900: #312E81;
```

### 2.2 Background Colors (Dark Theme)

```css
/* Backgrounds */
--color-bg-base:      #0A0A0F;   /* Самый тёмный фон (основа) */
--color-bg-surface:   #111118;   /* Карточки, панели */
--color-bg-elevated:  #1A1A24;   /* Elevated компоненты, modals */
--color-bg-overlay:   #22222E;   /* Hover state, dropdowns */
--color-bg-input:     #16161F;   /* Поля ввода */
```

### 2.3 Text Colors

```css
/* Text */
--color-text-primary:   #F8F8FF;   /* Основной текст */
--color-text-secondary: #A0A0B8;   /* Вторичный текст */
--color-text-muted:     #60607A;   /* Приглушённый текст */
--color-text-disabled:  #40404F;   /* Недоступный текст */
--color-text-inverse:   #0A0A0F;   /* Текст на светлом фоне */
```

### 2.4 Accent Colors

```css
/* AI / Primary Gradient */
--gradient-ai: linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #A855F7 100%);
--gradient-ai-hover: linear-gradient(135deg, #4F46E5 0%, #7C3AED 50%, #9333EA 100%);

/* Success */
--color-success-light: #D1FAE5;
--color-success:       #10B981;
--color-success-dark:  #065F46;

/* Warning */
--color-warning-light: #FEF3C7;
--color-warning:       #F59E0B;
--color-warning-dark:  #78350F;

/* Error / Danger */
--color-error-light:   #FEE2E2;
--color-error:         #EF4444;
--color-error-dark:    #7F1D1D;

/* Info */
--color-info-light:    #DBEAFE;
--color-info:          #3B82F6;
--color-info-dark:     #1E3A5F;
```

### 2.5 Risk Level Colors

```css
/* Специальные цвета для Risk Radar */
--color-risk-high:   #EF4444;   /* Красный */
--color-risk-medium: #F59E0B;   /* Жёлтый */
--color-risk-low:    #10B981;   /* Зелёный */
```

### 2.6 Border Colors

```css
--color-border-default: rgba(255, 255, 255, 0.08);
--color-border-subtle:  rgba(255, 255, 255, 0.04);
--color-border-active:  rgba(99, 102, 241, 0.5);   /* Primary с прозрачностью */
--color-border-focus:   #6366F1;
```

---

## 3. Типографика

### 3.1 Шрифты

```css
/* Primary Font: Inter — профессиональный, читаемый */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* Mono Font: JetBrains Mono — для кода и технических данных */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
```

### 3.2 Типографическая шкала

```css
/* Type Scale (основана на модульной шкале 1.25) */
--text-xs:   0.75rem;    /* 12px — метки, подсказки */
--text-sm:   0.875rem;   /* 14px — вторичный текст, статусы */
--text-base: 1rem;       /* 16px — основной текст */
--text-lg:   1.125rem;   /* 18px — заголовки карточек */
--text-xl:   1.25rem;    /* 20px — заголовки разделов */
--text-2xl:  1.5rem;     /* 24px — заголовки страниц */
--text-3xl:  1.875rem;   /* 30px — главные заголовки */
--text-4xl:  2.25rem;    /* 36px — Hero/Display */

/* Font Weights */
--font-light:    300;
--font-regular:  400;
--font-medium:   500;
--font-semibold: 600;
--font-bold:     700;
--font-extrabold: 800;

/* Line Heights */
--leading-tight:  1.25;
--leading-snug:   1.375;
--leading-normal: 1.5;
--leading-relaxed: 1.625;

/* Letter Spacing */
--tracking-tight:  -0.025em;
--tracking-normal:  0em;
--tracking-wide:    0.025em;
--tracking-wider:   0.05em;
--tracking-widest:  0.1em;
```

### 3.3 Стили текста

```css
/* Display */
.text-display {
  font-size: var(--text-4xl);
  font-weight: var(--font-extrabold);
  letter-spacing: var(--tracking-tight);
  line-height: var(--leading-tight);
}

/* Heading 1 */
.text-h1 {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  letter-spacing: var(--tracking-tight);
}

/* Heading 2 */
.text-h2 {
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
}

/* Heading 3 */
.text-h3 {
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
}

/* Body Large */
.text-body-lg {
  font-size: var(--text-lg);
  font-weight: var(--font-regular);
  line-height: var(--leading-relaxed);
}

/* Body */
.text-body {
  font-size: var(--text-base);
  font-weight: var(--font-regular);
  line-height: var(--leading-normal);
}

/* Caption */
.text-caption {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text-secondary);
}

/* Label */
.text-label {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--color-text-muted);
}
```

---

## 4. Пространство и сетка

### 4.1 Spacing Scale

```css
/* 4px base unit */
--space-0:   0;
--space-1:   0.25rem;   /* 4px */
--space-2:   0.5rem;    /* 8px */
--space-3:   0.75rem;   /* 12px */
--space-4:   1rem;      /* 16px */
--space-5:   1.25rem;   /* 20px */
--space-6:   1.5rem;    /* 24px */
--space-8:   2rem;      /* 32px */
--space-10:  2.5rem;    /* 40px */
--space-12:  3rem;      /* 48px */
--space-16:  4rem;      /* 64px */
--space-20:  5rem;      /* 80px */
--space-24:  6rem;      /* 96px */
```

### 4.2 Layout Grid

```css
/* Основная сетка — 12 колонок */
--grid-columns: 12;
--grid-gap: 1.5rem;         /* 24px */
--grid-margin: 2rem;        /* 32px по бокам */

/* Максимальная ширина */
--container-max: 1440px;
--container-wide: 1280px;
--container-default: 1024px;
--container-narrow: 768px;
```

### 4.3 Layout Structure (Application Shell)

```
┌─────────────────────────────────────────────────────────┐
│  TopBar (64px)                                          │
│  [Logo] [Project Name]           [User Menu] [Settings] │
├────────────┬────────────────────────────────────────────┤
│  Sidebar   │  Main Content Area                         │
│  (240px)   │                                            │
│            │  ┌────────────────────────────────────┐   │
│  [Nav]     │  │  Page Header                        │   │
│  [Projects]│  └────────────────────────────────────┘   │
│            │                                            │
│  [Current] │  ┌────────────────────────────────────┐   │
│  [Project] │  │  Content Area                       │   │
│            │  │                                     │   │
│  [Analysis]│  └────────────────────────────────────┘   │
│  [Chat]    │                                            │
│  [Docs]    │                                            │
└────────────┴────────────────────────────────────────────┘
```

---

## 5. Компоненты (Design Tokens)

### 5.1 Радиус (Border Radius)

```css
--radius-sm:   0.25rem;   /* 4px — кнопки, badges */
--radius-md:   0.5rem;    /* 8px — карточки, inputs */
--radius-lg:   0.75rem;   /* 12px — панели */
--radius-xl:   1rem;      /* 16px — modals */
--radius-2xl:  1.5rem;    /* 24px — крупные карточки */
--radius-full: 9999px;    /* Pill buttons, avatars */
```

### 5.2 Тени

```css
/* Dark mode shadows — используем цветные тени для глубины */
--shadow-sm:  0 1px 2px rgba(0, 0, 0, 0.4);
--shadow-md:  0 4px 12px rgba(0, 0, 0, 0.5);
--shadow-lg:  0 12px 32px rgba(0, 0, 0, 0.6);
--shadow-xl:  0 24px 48px rgba(0, 0, 0, 0.7);

/* AI Glow effect */
--shadow-ai:  0 0 20px rgba(99, 102, 241, 0.3),
              0 0 40px rgba(99, 102, 241, 0.1);

--shadow-ai-strong: 0 0 30px rgba(99, 102, 241, 0.5),
                    0 0 60px rgba(99, 102, 241, 0.2);
```

### 5.3 Анимации и переходы

```css
/* Duration */
--duration-fast:   100ms;
--duration-normal: 200ms;
--duration-slow:   300ms;
--duration-slower: 500ms;

/* Easing */
--ease-default:  cubic-bezier(0.4, 0, 0.2, 1);   /* Материальный ease */
--ease-in:       cubic-bezier(0.4, 0, 1, 1);
--ease-out:      cubic-bezier(0, 0, 0.2, 1);
--ease-bounce:   cubic-bezier(0.34, 1.56, 0.64, 1);

/* Standard transitions */
--transition-default: all var(--duration-normal) var(--ease-default);
--transition-fast:    all var(--duration-fast) var(--ease-default);
--transition-color:   color var(--duration-fast), background-color var(--duration-fast), border-color var(--duration-fast);
```

### 5.4 Z-Index Scale

```css
--z-base:      0;
--z-raised:    10;
--z-dropdown:  100;
--z-sticky:    200;
--z-overlay:   300;
--z-modal:     400;
--z-toast:     500;
--z-tooltip:   600;
```

---

## 6. Стили кнопок

### 6.1 Button Variants

```css
/* Primary — основной CTA */
.btn-primary {
  background: var(--gradient-ai);
  color: white;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-weight: var(--font-semibold);
  font-size: var(--text-sm);
  transition: var(--transition-default);
  box-shadow: 0 0 20px rgba(99, 102, 241, 0.25);
}
.btn-primary:hover {
  background: var(--gradient-ai-hover);
  box-shadow: var(--shadow-ai);
  transform: translateY(-1px);
}
.btn-primary:active {
  transform: translateY(0);
}

/* Secondary — второстепенный */
.btn-secondary {
  background: var(--color-bg-elevated);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-default);
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-weight: var(--font-medium);
}
.btn-secondary:hover {
  background: var(--color-bg-overlay);
  border-color: var(--color-border-active);
}

/* Ghost — прозрачный */
.btn-ghost {
  background: transparent;
  color: var(--color-text-secondary);
  padding: 10px 20px;
}
.btn-ghost:hover {
  background: var(--color-bg-elevated);
  color: var(--color-text-primary);
}

/* Danger */
.btn-danger {
  background: var(--color-error);
  color: white;
}
.btn-danger:hover {
  background: #DC2626;
}

/* Button Sizes */
.btn-sm { padding: 6px 12px; font-size: var(--text-xs); }
.btn-md { padding: 10px 20px; font-size: var(--text-sm); }   /* Default */
.btn-lg { padding: 14px 28px; font-size: var(--text-base); }
.btn-xl { padding: 18px 36px; font-size: var(--text-lg); }
```

---

## 7. Специальные паттерны

### 7.1 AI Processing State

Когда AI выполняет задачу, используется специальный визуальный паттерн:

```css
/* AI Typing Indicator */
.ai-thinking {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  background: var(--color-bg-elevated);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: var(--radius-lg);
  border-left: 3px solid var(--color-primary-500);
}

/* Animated dots */
.ai-dots span {
  display: inline-block;
  width: 6px;
  height: 6px;
  background: var(--color-primary-400);
  border-radius: 50%;
  animation: ai-pulse 1.4s ease-in-out infinite;
}

.ai-dots span:nth-child(2) { animation-delay: 0.2s; }
.ai-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes ai-pulse {
  0%, 80%, 100% { transform: scale(0.8); opacity: 0.4; }
  40%           { transform: scale(1.2); opacity: 1; }
}
```

### 7.2 AI Gradient Border (для активных AI-компонентов)

```css
.ai-active-border {
  position: relative;
  border-radius: var(--radius-lg);
}

.ai-active-border::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  background: var(--gradient-ai);
  z-index: -1;
  opacity: 0.6;
}
```

### 7.3 Risk Badge

```css
.risk-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
}

.risk-badge.high   { background: rgba(239, 68, 68, 0.15);  color: #FCA5A5; }
.risk-badge.medium { background: rgba(245, 158, 11, 0.15); color: #FCD34D; }
.risk-badge.low    { background: rgba(16, 185, 129, 0.15); color: #6EE7B7; }
```

### 7.4 Status Badge

```css
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

/* Статусы проекта */
.status-badge.draft       { background: rgba(99, 102, 241, 0.1);  color: #A5B4FC; }
.status-badge.analyzing   { background: rgba(245, 158, 11, 0.1);  color: #FCD34D; }
.status-badge.clarifying  { background: rgba(59, 130, 246, 0.1);  color: #93C5FD; }
.status-badge.generating  { background: rgba(168, 85, 247, 0.1);  color: #D8B4FE; }
.status-badge.review      { background: rgba(245, 158, 11, 0.1);  color: #FDE68A; }
.status-badge.done        { background: rgba(16, 185, 129, 0.1);  color: #6EE7B7; }
.status-badge.submitted   { background: rgba(16, 185, 129, 0.2);  color: #34D399; }
.status-badge.archived    { background: rgba(96, 96, 122, 0.1);   color: #9CA3AF; }

/* Dot indicator */
.status-badge::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

/* Animated dot for active states */
.status-badge.analyzing::before,
.status-badge.generating::before {
  animation: status-pulse 1.5s ease infinite;
}

@keyframes status-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}
```

---

## 8. Иконки

**Библиотека:** Lucide React (+ Heroicons как дополнение)

### Стандартные размеры

| Размер | px | Использование |
|-------|----|--------------|
| `size-3` | 12px | Мини-иконки в badges |
| `size-4` | 16px | Inline иконки в тексте |
| `size-5` | 20px | Кнопки, навигация |
| `size-6` | 24px | Заголовки |
| `size-8` | 32px | Пустые состояния |
| `size-12` | 48px | Hero / Feature иконки |

### Ключевые иконки

```
Upload:          UploadCloud / FileUp
Document:        FileText / File
AI / Analysis:   Sparkles / Brain / Zap
Chat:            MessageCircle / MessageSquare
Generate:        Wand2 / PenTool
Export DOCX:     FileDown / FileType
Export PDF:      Download
Risk:            AlertTriangle / ShieldAlert
Success:         CheckCircle / Check
Settings:        Settings / SlidersHorizontal
Project:         FolderOpen / Briefcase
User:            User / UserCircle
Company:         Building2 / Landmark
```

---

## 9. Анимации (микроанимации)

### 9.1 Page Transitions

```css
/* Fade in при загрузке страницы */
@keyframes page-fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

.page-enter {
  animation: page-fade-in 0.3s var(--ease-out) forwards;
}
```

### 9.2 Card Hover

```css
.card {
  transition: var(--transition-default);
  border: 1px solid var(--color-border-default);
}

.card:hover {
  border-color: var(--color-border-active);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
```

### 9.3 Skeleton Loading

```css
.skeleton {
  background: linear-gradient(
    90deg,
    var(--color-bg-elevated) 25%,
    var(--color-bg-overlay) 50%,
    var(--color-bg-elevated) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s ease infinite;
}

@keyframes skeleton-shimmer {
  from { background-position: 200% 0; }
  to   { background-position: -200% 0; }
}
```

### 9.4 Progress Bar (AI Generation)

```css
.ai-progress-bar {
  height: 3px;
  background: var(--color-bg-elevated);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.ai-progress-bar-fill {
  height: 100%;
  background: var(--gradient-ai);
  border-radius: var(--radius-full);
  transition: width 0.5s var(--ease-out);
  position: relative;
}

/* Shimmer effect на прогресс-баре */
.ai-progress-bar-fill::after {
  content: '';
  position: absolute;
  top: 0; right: 0; bottom: 0; left: 0;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
  animation: progress-shimmer 1.5s ease infinite;
}

@keyframes progress-shimmer {
  from { transform: translateX(-100%); }
  to   { transform: translateX(100%); }
}
```

---

## 10. Dark Mode — глобальные CSS Variables

```css
:root {
  color-scheme: dark;
  
  /* Colors */
  --color-primary-500: #6366F1;
  --color-primary-600: #4F46E5;
  
  --color-bg-base:      #0A0A0F;
  --color-bg-surface:   #111118;
  --color-bg-elevated:  #1A1A24;
  --color-bg-overlay:   #22222E;
  --color-bg-input:     #16161F;
  
  --color-text-primary:   #F8F8FF;
  --color-text-secondary: #A0A0B8;
  --color-text-muted:     #60607A;
  
  --color-border-default: rgba(255, 255, 255, 0.08);
  --color-border-active:  rgba(99, 102, 241, 0.5);
  
  --color-success:  #10B981;
  --color-warning:  #F59E0B;
  --color-error:    #EF4444;
  --color-info:     #3B82F6;
  
  /* Gradients */
  --gradient-ai: linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #A855F7 100%);
  
  /* Shadows */
  --shadow-ai: 0 0 20px rgba(99, 102, 241, 0.3), 0 0 40px rgba(99, 102, 241, 0.1);
  
  /* Spacing */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  
  /* Typography */
  --font-sans: 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  
  /* Border Radius */
  --radius-sm: 0.25rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-xl: 1rem;
  --radius-full: 9999px;
  
  /* Transitions */
  --duration-normal: 200ms;
  --ease-default: cubic-bezier(0.4, 0, 0.2, 1);
  --transition-default: all var(--duration-normal) var(--ease-default);
}
```

---

## 11. Адаптивность

### Breakpoints

```css
/* Tailwind-совместимые breakpoints */
--bp-sm:  640px;    /* Small tablets */
--bp-md:  768px;    /* Tablets */
--bp-lg:  1024px;   /* Laptops (Desktop First target) */
--bp-xl:  1280px;   /* Desktops */
--bp-2xl: 1536px;   /* Large screens */
```

### Adaptive Layout

| Экран | Sidebar | Main Content | Notes |
|-------|---------|-------------|-------|
| < 768px | Скрыт (slide-out) | Полная ширина | Mobile: hamburger menu |
| 768–1024px | Collapsed (icons only, 64px) | — | Tablet |
| > 1024px | Full (240px) | — | Desktop (primary target) |

---

## 12. Accessibility

| Требование | Реализация |
|-----------|-----------|
| Цветовой контраст | AA+ (4.5:1 для текста) |
| Фокус-индикаторы | Видимые focus rings с primary цветом |
| ARIA-labels | На всех интерактивных элементах |
| Keyboard navigation | Tab, Enter, Space, Escape |
| Screen reader | Семантические HTML5 элементы |
| Motion reduce | `prefers-reduced-motion` медиа-запрос |

---

*Документ подготовлен командой BINOM AI. Design System v1.0 — утверждён.*  
*Следующий документ: [UI Components.md](./UI%20Components.md)*
