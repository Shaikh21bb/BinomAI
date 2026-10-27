import { assessStock, compatibleUnits, type StockAssessment } from './productStock';

export interface DiscoveryCheck {
  id?: string;
  requirement: string;
  status: 'matched' | 'mismatch' | 'unknown';
  evidence?: string;
}

export interface DiscoveryLead {
  title?: string;
  url?: string;
  shop?: string;
  snippet?: string;
  description?: string;
  image_url?: string | null;
  price?: number | null;
  currency?: string | null;
  availability?: string | null;
  stock_quantity?: number | null;
  stock_unit?: string | null;
  seller_name?: string | null;
  seller_phone?: string | null;
  seller_phones?: string[];
  characteristics?: Record<string, string>;
  is_product_page?: boolean;
  page_verified?: boolean;
  match_status?: 'matched' | 'partial' | 'mismatch' | 'unknown' | 'unverified';
  checks?: DiscoveryCheck[];
  min_order_quantity?: number | null;
  min_order_unit?: string | null;
  price_quantity?: number | null;
  price_unit?: string | null;
  price_basis_status?: 'published' | 'unknown' | string | null;
  wholesale_terms?: string | null;
  variant_status?: 'single' | 'selected' | 'ambiguous' | 'unknown' | string | null;
  certificate_status?: 'missing' | 'claim_only' | 'document_linked' | null;
  certificate_documents?: { url: string; label?: string; status: 'unverified' }[];
  order_readiness?: {
    status: 'ready' | 'needs_confirmation' | 'not_suitable';
    gaps: { code: string; label: string }[];
    quantity: {
      status: 'enough' | 'shortage' | 'unknown';
      requested_quantity: number | null;
      requested_unit: string | null;
      stock_quantity: number | null;
      stock_unit: string | null;
      reason: string;
      missing?: number;
    };
  };
}

export interface DiscoveryReportItem {
  product_name: string;
  quantity?: number | null;
  unit?: string | null;
  state: 'pending' | 'searching' | 'ready' | 'error';
  results: DiscoveryLead[];
  checked_at?: string | null;
  closure_policy?: ClosurePolicy | null;
}

export type ClosurePolicy = 'source' | 'zipper_only' | 'allow_alternatives';

export const CLOSURE_POLICY_LABELS: Record<ClosurePolicy, string> = {
  source: 'По исходному ТЗ',
  zipper_only: 'Только молния',
  allow_alternatives: 'Молния, пуговицы или без застёжки',
};

export function supportsClosureClarification(item: { product_name: string; specs?: string | null }) {
  const garment = /кофт|кардиган|джемпер|свитер|жакет|куртк|жилет|толстовк|худи|пуловер|блуз|рубашк|плать|комбинезон|костюм|олимпийк|ветровк|пальто|свитшот/i.test(item.product_name);
  return garment && /молни|замок|замк|заст[её]жк/i.test(`${item.product_name} ${item.specs ?? ''}`);
}

export type ProductLeadFilter = 'all' | 'in-stock' | 'complete' | 'requirements' | 'combined';
export type DiscoveryResultFilter = 'all' | 'with-cards' | 'without-cards' | 'error' | 'in-stock' | 'complete' | 'requirements' | 'combined';

/** Keep product identity parameters; remove only non-product tracking and fragments. */
export function canonicalProductUrl(raw?: string) {
  try {
    const url = new URL(raw || '');
    if (!['http:', 'https:'].includes(url.protocol)) return null;
    url.hash = '';
    for (const key of [...url.searchParams.keys()]) {
      if (/^(utm_.+|gclid|fbclid|yclid)$/i.test(key)) url.searchParams.delete(key);
    }
    url.searchParams.sort();
    url.pathname = url.pathname.replace(/\/$/, '') || '/';
    return url.toString();
  } catch {
    return null;
  }
}

/** A found product URL is useful even when the seller blocks automated verification. */
export function isProductCardLead(lead: DiscoveryLead) {
  return Boolean(lead.is_product_page && canonicalProductUrl(lead.url));
}

/** Confirms the product type only; other technical requirements can still be unknown. */
export function isVerifiedProductLead(lead: DiscoveryLead) {
  const typeCheck = lead.checks?.find((check) => check.id === 'type') ?? lead.checks?.[0];
  return Boolean(isProductCardLead(lead) && lead.page_verified && typeCheck?.status === 'matched');
}

export function productVerificationScope(lead: DiscoveryLead) {
  const checks = lead.checks ?? [];
  const typeCheck = checks.find((check) => check.id === 'type') ?? checks[0];
  const technicalChecks = checks.filter((check) => check !== typeCheck);
  const onlyType = checks.length > 0 && technicalChecks.length === 0;
  return {
    technicalCount: technicalChecks.length,
    confirmedTechnicalCount: technicalChecks.filter((check) => effectiveProductCheckStatus(check) === 'matched').length,
    label: onlyType && isVerifiedProductLead(lead) ? 'Совпадает тип товара' : null,
    explanation: onlyType ? 'Технические требования не выделены; проверьте ТЗ вручную.' : null,
  };
}

export function canRecommendProductLead(lead: DiscoveryLead, quantity?: number | string | null, unit?: string | null) {
  return isConfirmedProductOffer(lead, quantity, unit);
}

const imageNoise = /favicon|logo|sprite|placeholder|\/watch\/|portal-portable|base_satu|pixel/i;

export function hasProductPhoto(lead: DiscoveryLead) {
  return Boolean(lead.page_verified && lead.image_url && /^https?:\/\//i.test(lead.image_url) && !imageNoise.test(lead.image_url));
}

/** InStock is a published availability flag, never a promise of sufficient quantity. */
export function isMatchingInStockLead(lead: DiscoveryLead) {
  return isVerifiedProductLead(lead)
    && ['matched', 'partial'].includes(lead.match_status ?? '')
    && lead.availability === 'InStock'
    && (lead.stock_quantity == null || lead.stock_quantity > 0);
}

export function isCompleteProductLead(lead: DiscoveryLead) {
  return isProductCardLead(lead) && hasProductPhoto(lead)
    && lead.price != null && Number.isFinite(Number(lead.price)) && Number(lead.price) > 0
    && Boolean(lead.currency?.trim()) && publishedProductPhones(lead).length > 0;
}

/** Confirms all extracted checks, not omitted requirements or order quantity. */
export function hasConfirmedProductRequirements(lead: DiscoveryLead) {
  return isVerifiedProductLead(lead) && lead.match_status === 'matched'
    && productVerificationScope(lead).technicalCount > 0
    && Boolean(lead.checks?.every((check) => effectiveProductCheckStatus(check) === 'matched'));
}

/** A linked certificate or a seller's certificate claim is not independent validation. */
export function isCertificateRequirement(check: DiscoveryCheck) {
  return /certificat|certificate|declarat|document/i.test(check.id ?? '')
    || /ГОСТ|\bСТ\s*РК\b|сертификат|декларац\S*\s+соответств|регистрационн\S*\s+удостоверен|certificate|declaration\s+of\s+conformity/i.test(check.requirement ?? '');
}

export function effectiveProductCheckStatus(check: DiscoveryCheck): DiscoveryCheck['status'] {
  return isCertificateRequirement(check) && check.status === 'matched' ? 'unknown' : check.status;
}

/** No legacy/local inference can substitute for the server's quantity-bound readiness. */
export function orderQuantityAssessment(lead: DiscoveryLead, quantity?: number | string | null, unit?: string | null): StockAssessment {
  const amount = Number(quantity);
  const binding = lead.order_readiness?.quantity;
  if (quantity == null || !Number.isFinite(amount) || amount <= 0 || !binding || binding.requested_quantity !== amount || !compatibleUnits(unit, binding.requested_unit)) return { verdict: 'unknown' };
  const raw = assessStock(amount, unit, lead.page_verified ? lead.stock_quantity : null, lead.stock_unit, lead.availability);
  const canonical = assessStock(amount, unit, binding.stock_quantity, binding.stock_unit, lead.availability);
  if (binding.status === 'enough' && raw.verdict === 'enough' && canonical.verdict === 'enough') return { verdict: 'enough' };
  if (binding.status === 'shortage' && raw.verdict === 'shortage' && canonical.verdict === 'shortage') return canonical;
  return { verdict: 'unknown' };
}

export function isConfirmedProductOffer(lead: DiscoveryLead, quantity?: number | string | null, unit?: string | null) {
  const amount = Number(quantity);
  const readiness = lead.order_readiness;
  if (quantity == null || !Number.isFinite(amount) || amount <= 0 || readiness?.status !== 'ready' || !Array.isArray(readiness.gaps) || readiness.gaps.length) return false;
  const binding = readiness.quantity;
  if (!binding || binding.status !== 'enough' || binding.requested_quantity !== amount || !compatibleUnits(unit, binding.requested_unit)) return false;
  if (orderQuantityAssessment(lead, amount, unit).verdict !== 'enough') return false;
  if (lead.min_order_quantity == null || !Number.isFinite(lead.min_order_quantity) || lead.min_order_quantity <= 0 || lead.min_order_quantity > amount || !compatibleUnits(unit, lead.min_order_unit)) return false;
  if (!['single', 'selected'].includes(lead.variant_status ?? '') || !lead.wholesale_terms?.trim()) return false;
  if (lead.price_basis_status !== 'published' || lead.price_quantity == null || !Number.isFinite(lead.price_quantity) || lead.price_quantity <= 0 || lead.price_quantity > amount || !compatibleUnits(unit, lead.price_unit)) return false;
  return hasConfirmedProductRequirements(lead) && isMatchingInStockLead(lead) && isCompleteProductLead(lead);
}

export interface ProductConfirmationGap {
  code: string;
  label: string;
  requirements?: string[];
}

/** Explain the existing strict predicate without turning missing evidence into a match. */
export function productConfirmationGaps(lead: DiscoveryLead, quantity?: number | string | null, unit?: string | null): ProductConfirmationGap[] {
  const gaps: ProductConfirmationGap[] = [];
  const scope = productVerificationScope(lead);
  const checks = lead.checks ?? [];
  if (!lead.page_verified) gaps.push({ code: 'page', label: 'Страницу товара не удалось прочитать.' });
  if (!isVerifiedProductLead(lead)) gaps.push({ code: 'type', label: 'Тип товара не подтверждён.' });
  if (!checks.length) gaps.push({ code: 'requirements-unchecked', label: 'Проверка технических требований по странице не выполнена.' });
  else if (!scope.technicalCount) gaps.push({ code: 'requirements-missing', label: 'Технические требования не выделены — сверьте исходное ТЗ.' });
  const mismatches = checks.filter((check) => effectiveProductCheckStatus(check) === 'mismatch').map((check) => check.requirement);
  const unknown = checks.filter((check) => effectiveProductCheckStatus(check) === 'unknown').map((check) => check.requirement);
  if (mismatches.length) gaps.push({ code: 'requirements-mismatch', label: 'Есть расхождения с выделенными требованиями.', requirements: mismatches });
  if (unknown.length) gaps.push({ code: 'requirements-unknown', label: 'Не все выделенные требования подтверждены.', requirements: unknown });
  if (scope.technicalCount && !mismatches.length && !unknown.length && !hasConfirmedProductRequirements(lead)) gaps.push({ code: 'verification', label: 'Итоговое соответствие требованиям не подтверждено.' });
  const invalidStock = lead.stock_quantity != null && (!Number.isFinite(lead.stock_quantity) || lead.stock_quantity <= 0);
  if (!lead.page_verified || lead.availability !== 'InStock' || invalidStock) {
    const label = lead.page_verified && lead.availability === 'OutOfStock'
      ? 'На странице указано: нет в наличии.'
      : lead.page_verified && lead.availability === 'InStock' && invalidStock
        ? 'Наличие противоречит опубликованному остатку.'
        : 'Наличие не подтверждено прочитанной страницей.';
    gaps.push({ code: 'availability', label });
  }
  if (!hasProductPhoto(lead)) gaps.push({ code: 'photo', label: 'Нет опубликованного фото товара с прочитанной страницы.' });
  if (!lead.page_verified || lead.price == null || !Number.isFinite(Number(lead.price)) || Number(lead.price) <= 0 || !lead.currency?.trim()) gaps.push({ code: 'price', label: 'Не подтверждена положительная цена с валютой.' });
  if (!publishedProductPhones(lead).length) gaps.push({ code: 'contact', label: 'Телефон на странице источника не найден.' });
  const amount = Number(quantity);
  const readiness = lead.order_readiness;
  if (!readiness) gaps.push({ code: 'readiness-missing', label: 'Готовность к заказу не проверялась. Повторите поиск, чтобы проверить количество и условия поставки.' });
  else for (const gap of readiness.gaps ?? []) gaps.push({ code: gap.code, label: gap.label });
  if (quantity == null || !Number.isFinite(amount) || amount <= 0) gaps.push({ code: 'quantity', label: 'В документе не подтверждено корректное количество заказа.' });
  else {
    const stock = assessStock(amount, unit, lead.page_verified ? lead.stock_quantity : null, lead.stock_unit, lead.availability);
    if (stock.verdict !== 'enough') gaps.push({ code: 'quantity', label: stock.verdict === 'shortage' ? 'Опубликованного остатка недостаточно для всего заказа.' : 'Точный остаток и его единица не подтверждают количество по заказу.' });
    if (readiness && (!readiness.quantity || readiness.quantity.requested_quantity !== amount || !compatibleUnits(unit, readiness.quantity.requested_unit))) gaps.push({ code: 'quantity-binding', label: 'Проверка готовности выполнена для другого количества или единицы. Повторите поиск.' });
    else if (readiness?.quantity && (readiness.quantity.status !== 'enough' || assessStock(amount, unit, readiness.quantity.stock_quantity, readiness.quantity.stock_unit, lead.availability).verdict !== 'enough')) gaps.push({ code: 'quantity-readiness', label: readiness.quantity.reason || 'Сервер не подтвердил достаточный остаток для этого заказа.' });
  }
  if (lead.min_order_quantity == null || !Number.isFinite(lead.min_order_quantity) || lead.min_order_quantity <= 0 || !compatibleUnits(unit, lead.min_order_unit)) gaps.push({ code: 'moq', label: 'Минимальный заказ и его единица не подтверждены.' });
  else if (Number.isFinite(amount) && lead.min_order_quantity > amount) gaps.push({ code: 'moq', label: 'Минимальный заказ продавца превышает нужное количество.' });
  if (!['single', 'selected'].includes(lead.variant_status ?? '')) gaps.push({ code: 'variant', label: 'Нужный вариант товара не выбран или не подтверждён.' });
  if (!lead.wholesale_terms?.trim()) gaps.push({ code: 'wholesale', label: 'Опубликованные условия оптовой поставки не подтверждены.' });
  if (lead.price_basis_status !== 'published' || lead.price_quantity == null || !Number.isFinite(lead.price_quantity) || lead.price_quantity <= 0 || !compatibleUnits(unit, lead.price_unit)) gaps.push({ code: 'price-basis', label: 'Не подтверждено, за какое количество и единицу указана цена.' });
  else if (Number.isFinite(amount) && lead.price_quantity > amount) gaps.push({ code: 'price-basis', label: 'Опубликованная цена относится к партии больше вашего заказа.' });
  if (readiness && readiness.status !== 'ready' && !readiness.gaps?.length) gaps.push({ code: 'readiness', label: 'Поставщик не подтверждён как готовый выполнить этот заказ.' });
  return [...new Map(gaps.map((gap) => [gap.code, gap])).values()];
}

export function productQuantityMessage(quantity: number | string | null | undefined, unit: string, verdict: 'enough' | 'shortage' | 'unknown') {
  const amount = Number(quantity);
  if (quantity == null || !Number.isFinite(amount) || amount <= 0) return 'Количество в ТЗ не указано — уточните объём заказа.';
  if (verdict !== 'unknown') return null;
  return `Количество по заказу (${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 4 }).format(amount)} ${unit}) не подтверждено. Уточните доступный остаток у продавца.`;
}

export function reportConfirmationGaps(items: DiscoveryReportItem[]) {
  const unique = new Map<string, ProductConfirmationGap>();
  for (const item of items.filter((row) => row.state === 'ready')) {
    for (const lead of visibleProductLeads(item.results, 'all', item.quantity, item.unit)) {
      for (const gap of productConfirmationGaps(lead, item.quantity, item.unit)) if (!unique.has(gap.code)) unique.set(gap.code, gap);
    }
  }
  return [...unique.values()];
}

function matchesProductFilter(lead: DiscoveryLead, filter: ProductLeadFilter, quantity?: number | string | null, unit?: string | null) {
  if (filter === 'in-stock') return isMatchingInStockLead(lead);
  if (filter === 'complete') return isCompleteProductLead(lead);
  if (filter === 'requirements') return hasConfirmedProductRequirements(lead);
  if (filter === 'combined') return isConfirmedProductOffer(lead, quantity, unit);
  return true;
}

export function productLeadScore(lead: DiscoveryLead) {
  const matchPoints = { matched: 500, partial: 350, unknown: 200, unverified: 100, mismatch: 0 };
  const checks = lead.checks ?? [];
  const matching = isVerifiedProductLead(lead) && ['matched', 'partial'].includes(lead.match_status ?? '');
  const availabilityPoints = isMatchingInStockLead(lead) ? 3000 : lead.availability === 'OutOfStock' || lead.stock_quantity === 0 ? 1000 : 2000;
  const priority = matching ? 10_000 + availabilityPoints : lead.page_verified ? lead.match_status === 'mismatch' ? 0 : 5000 : 1000;
  return (
    priority + matchPoints[lead.match_status ?? 'unknown'] +
    checks.filter((check) => check.status === 'matched').length * 12 -
    checks.filter((check) => check.status === 'mismatch').length * 20 +
    (hasProductPhoto(lead) ? 70 : 0) +
    (lead.price != null ? 55 : 0) +
    (lead.availability === 'InStock' ? 30 : 0) +
    (lead.stock_quantity != null && lead.stock_quantity > 0 ? 15 : 0)
  );
}

/** Cards, totals, filters and export all use this same ordered, bounded selection. */
export function visibleProductLeads(leads: DiscoveryLead[], filter: ProductLeadFilter = 'all', quantity?: number | string | null, unit?: string | null) {
  const byUrl = new Map<string, DiscoveryLead>();
  for (const lead of leads.filter(isProductCardLead)) {
    const key = canonicalProductUrl(lead.url)!;
    const previous = byUrl.get(key);
    if (!previous || productLeadScore(lead) > productLeadScore(previous)) byUrl.set(key, lead);
  }
  return [...byUrl.values()].sort((a, b) => Number(isConfirmedProductOffer(b, quantity, unit)) - Number(isConfirmedProductOffer(a, quantity, unit)) || productLeadScore(b) - productLeadScore(a)).slice(0, 8).filter((lead) => matchesProductFilter(lead, filter, quantity, unit));
}

export function reportItemHasProductCards(item: DiscoveryReportItem) {
  return item.state === 'ready' && visibleProductLeads(item.results, 'all', item.quantity, item.unit).length > 0;
}

export function reportItemMatchesFilter(item: DiscoveryReportItem, filter: DiscoveryResultFilter, retrying = false) {
  if (retrying || filter === 'all') return true;
  if (filter === 'error') return item.state === 'error';
  if (item.state !== 'ready') return false;
  if (filter === 'without-cards') return !reportItemHasProductCards(item);
  if (filter === 'with-cards') return reportItemHasProductCards(item);
  return visibleProductLeads(item.results, filter, item.quantity, item.unit).length > 0;
}

export function quickCheckProgressLabel(state: string, retryingIndex: number | null, completed: number, total: number, failed: number) {
  if (retryingIndex != null) return `Повторно ищем товары для позиции ${retryingIndex + 1}`;
  if (state === 'queued') return 'Документ в очереди на поиск';
  if (state === 'running') return 'Ищем товары и сверяем требования';
  if (failed) return 'Проверка требует внимания';
  return completed === total ? 'Проверка завершена' : 'Проверка готова к запуску';
}

/** Keep both current and legacy API fields; deduplicate different number formatting. */
export function publishedProductPhones(lead: DiscoveryLead) {
  const seen = new Set<string>();
  return [...(lead.seller_phones ?? []), lead.seller_phone].flatMap((raw) => {
    const phone = raw?.trim();
    const digits = phone?.replace(/\D/g, '') ?? '';
    if (!phone || !digits || seen.has(digits)) return [];
    seen.add(digits);
    return [phone];
  });
}

function csvCell(value: unknown) {
  const text = String(value ?? '');
  const safe = /^\s*[=+\-@]/.test(text) ? `'${text}` : text;
  return `"${safe.replaceAll('"', '""')}"`;
}

/** A candidate remains in the report with its actual verification status and contacts. */
export function productDiscoveryCsv(filename: string, items: DiscoveryReportItem[]) {
  const rows: unknown[][] = [[
    'Проверка', 'Дата проверки', 'Позиция', 'Товар по ТЗ', 'Требуемое количество', 'Единица',
    'Найденный товар', 'Продавец', 'Телефон на странице источника', 'Статус соответствия', 'Характеристика',
    'Статус характеристики', 'Доказательство со страницы', 'Источник', 'Опубликованный остаток',
    'Единица остатка', 'Статус проверки позиции', 'Страница прочитана', 'Тип товара подтверждён',
    'Технических требований выделено', 'Технических требований подтверждено',
    'Уточнение застёжки для выполненного поиска',
    'Готовность к этому заказу', 'Что требует подтверждения', 'Проверка количества',
    'Минимальный заказ', 'Единица минимального заказа', 'Цена за количество', 'Единица цены',
    'Основание цены', 'Условия оптовой поставки', 'Вариант товара', 'Документы — подлинность не проверена',
  ]];
  items.forEach((item, index) => {
    const leads = item.state === 'ready' ? visibleProductLeads(item.results, 'all', item.quantity, item.unit) : [];
    if (!leads.length) {
      const status = item.state === 'ready' ? 'Товарные страницы не найдены' : item.state === 'error' ? 'Ошибка поиска' : 'Поиск не завершён';
      rows.push([filename, item.checked_at, index + 1, item.product_name, item.quantity, item.unit,
        '', '', '', status, '', '', '', '', '', '', item.state, '', '', '', '', CLOSURE_POLICY_LABELS[item.closure_policy ?? 'source'],
        'Не подтверждена', '', 'unknown', '', '', '', '', '', '', '', '']);
    }
    leads.forEach((lead) => {
      const scope = productVerificationScope(lead);
      const checks = lead.checks?.length ? lead.checks : [null];
      checks.forEach((check) => rows.push([
        filename, item.checked_at, index + 1, item.product_name, item.quantity, item.unit,
        lead.title, lead.seller_name || lead.shop, publishedProductPhones(lead).join(' / '),
        lead.match_status ?? 'unverified', check?.requirement, check ? effectiveProductCheckStatus(check) : '',
        check?.evidence, lead.url, lead.stock_quantity, lead.stock_unit, item.state,
        lead.page_verified ? 'Да' : 'Нет', isVerifiedProductLead(lead) ? 'Да' : 'Нет',
        scope.technicalCount, scope.confirmedTechnicalCount,
        CLOSURE_POLICY_LABELS[item.closure_policy ?? 'source'],
        isConfirmedProductOffer(lead, item.quantity, item.unit) ? 'Готово к указанному заказу' : lead.order_readiness?.status === 'not_suitable' ? 'Не подходит' : 'Требует подтверждения',
        productConfirmationGaps(lead, item.quantity, item.unit).map((gap) => gap.label).join(' | '),
        orderQuantityAssessment(lead, item.quantity, item.unit).verdict, lead.min_order_quantity, lead.min_order_unit,
        lead.price_quantity, lead.price_unit, lead.price_basis_status, lead.wholesale_terms, lead.variant_status,
        lead.certificate_documents?.map((document) => `${document.label || 'Документ'}: ${document.url} (подлинность не проверена)`).join(' | '),
      ]));
    });
  });
  return `\uFEFF${rows.map((row) => row.map(csvCell).join(';')).join('\r\n')}`;
}
