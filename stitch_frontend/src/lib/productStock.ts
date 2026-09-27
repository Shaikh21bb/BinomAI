export type StockVerdict = 'enough' | 'shortage' | 'unknown';

export interface StockAssessment {
  verdict: StockVerdict;
  missing?: number;
}

export function displayUnit(raw?: string | null): string {
  const value = (raw || '').trim();
  return /^(штука|штуки|штук|шт\.?)$/i.test(value) ? 'шт.' : value || 'ед.';
}

function unitKind(raw?: string | null): string | null {
  const unit = (raw || '').trim().toLocaleLowerCase('ru-RU').replace(/[.\s]/g, '');
  if (/^(шт|штук[а-яё]*|ед|единиц[а-яё]*)$/.test(unit)) return 'piece';
  if (/^упак[а-яё]*$/.test(unit)) return 'pack';
  if (/^(кг|килограмм[а-яё]*)$/.test(unit)) return 'kg';
  if (/^(г|гр|грамм[а-яё]*)$/.test(unit)) return 'g';
  if (/^(л|литр[а-яё]*)$/.test(unit)) return 'l';
  if (/^(мл|миллилитр[а-яё]*)$/.test(unit)) return 'ml';
  return null;
}

/** Never infer sufficient stock from an InStock flag or incompatible units. */
export function assessStock(
  requestedQuantity?: number | string | null,
  requestedUnit?: string | null,
  stockQuantity?: number | null,
  stockUnit?: string | null,
  availability?: string | null,
): StockAssessment {
  const requested = Number(requestedQuantity);
  if (requestedQuantity == null || !Number.isFinite(requested) || requested <= 0 ||
      stockQuantity == null || !Number.isFinite(stockQuantity) || stockQuantity < 0 ||
      !unitKind(requestedUnit) || unitKind(requestedUnit) !== unitKind(stockUnit) ||
      (availability === 'OutOfStock' && stockQuantity > 0)) {
    return { verdict: 'unknown' };
  }
  if (stockQuantity < requested) {
    return { verdict: 'shortage', missing: requested - stockQuantity };
  }
  return { verdict: 'enough' };
}
