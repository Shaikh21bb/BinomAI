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
}

export interface DiscoveryReportItem {
  product_name: string;
  quantity?: number | null;
  unit?: string | null;
  state: 'pending' | 'searching' | 'ready' | 'error';
  results: DiscoveryLead[];
  checked_at?: string | null;
}

/** A found product URL is useful even when the seller blocks automated verification. */
export function isProductCardLead(lead: DiscoveryLead) {
  return Boolean(lead.is_product_page);
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
    confirmedTechnicalCount: technicalChecks.filter((check) => check.status === 'matched').length,
    label: onlyType && isVerifiedProductLead(lead) ? 'Совпадает тип товара' : null,
    explanation: onlyType ? 'Технические требования не выделены; проверьте ТЗ вручную.' : null,
  };
}

export function canRecommendProductLead(lead: DiscoveryLead) {
  return isVerifiedProductLead(lead)
    && productVerificationScope(lead).confirmedTechnicalCount > 0
    && ['matched', 'partial'].includes(lead.match_status ?? '');
}

const imageNoise = /favicon|logo|sprite|placeholder|\/watch\/|portal-portable|base_satu|pixel/i;

export function productLeadScore(lead: DiscoveryLead) {
  const matchPoints = { matched: 500, partial: 350, unknown: 200, unverified: 100, mismatch: 0 };
  const checks = lead.checks ?? [];
  const validImage = Boolean(lead.image_url && /^https?:\/\//i.test(lead.image_url) && !imageNoise.test(lead.image_url));
  return (
    matchPoints[lead.match_status ?? 'unknown'] +
    checks.filter((check) => check.status === 'matched').length * 12 -
    checks.filter((check) => check.status === 'mismatch').length * 20 +
    (validImage ? 70 : 0) +
    (lead.price != null ? 55 : 0) +
    (lead.availability === 'InStock' ? 30 : 0) +
    (lead.stock_quantity != null && lead.stock_quantity > 0 ? 15 : 0)
  );
}

/** Cards, totals, filters and export all use this same ordered, bounded selection. */
export function visibleProductLeads(leads: DiscoveryLead[]) {
  return leads.filter(isProductCardLead).sort((a, b) => productLeadScore(b) - productLeadScore(a)).slice(0, 8);
}

export function reportItemHasProductCards(item: DiscoveryReportItem) {
  return item.state === 'ready' && visibleProductLeads(item.results).length > 0;
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
  ]];
  items.forEach((item, index) => {
    const leads = item.state === 'ready' ? visibleProductLeads(item.results) : [];
    if (!leads.length) {
      const status = item.state === 'ready' ? 'Товарные страницы не найдены' : item.state === 'error' ? 'Ошибка поиска' : 'Поиск не завершён';
      rows.push([filename, item.checked_at, index + 1, item.product_name, item.quantity, item.unit,
        '', '', '', status, '', '', '', '', '', '', item.state, '', '', '', '']);
    }
    leads.forEach((lead) => {
      const scope = productVerificationScope(lead);
      const checks = lead.checks?.length ? lead.checks : [null];
      checks.forEach((check) => rows.push([
        filename, item.checked_at, index + 1, item.product_name, item.quantity, item.unit,
        lead.title, lead.seller_name || lead.shop, publishedProductPhones(lead).join(' / '),
        lead.match_status ?? 'unverified', check?.requirement, check?.status,
        check?.evidence, lead.url, lead.stock_quantity, lead.stock_unit, item.state,
        lead.page_verified ? 'Да' : 'Нет', isVerifiedProductLead(lead) ? 'Да' : 'Нет',
        scope.technicalCount, scope.confirmedTechnicalCount,
      ]));
    });
  });
  return `\uFEFF${rows.map((row) => row.map(csvCell).join(';')).join('\r\n')}`;
}
