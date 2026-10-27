export type StockVerdict = 'enough' | 'shortage' | 'unknown';

export interface StockAssessment {
  verdict: StockVerdict;
  missing?: number;
}

export function displayUnit(raw?: string | null): string {
  const value = (raw || '').trim();
  return /^(штука|штуки|штук|шт\.?)$/i.test(value) ? 'шт.' : value || 'ед.';
}

export function unitKind(raw?: string | null): string | null {
  const unit = (raw || '').trim().toLocaleLowerCase('ru-RU').replace(/[.\s]/g, '');
  if (/^(шт|штука|штуки|штук|дана|h87|pce|pcs|piece|pieces)$/.test(unit)) return 'piece';
  if (/^(упак|упаковка|упаковки|упаковок|pack|packs|pkg)$/.test(unit)) return 'pack';
  if (/^(кг|килограмм|килограмма|килограммов|килограммы|kg|kgm)$/.test(unit)) return 'kg';
  if (/^(г|гр|грамм|грамма|граммов|граммы|g|grm)$/.test(unit)) return 'g';
  if (/^(л|литр|литра|литров|литры|l|ltr)$/.test(unit)) return 'l';
  if (/^(мл|миллилитр|миллилитра|миллилитров|миллилитры|ml|mlt)$/.test(unit)) return 'ml';
  if (/^(м|метр|метра|метров|метры|m|mtr)$/.test(unit)) return 'm';
  if (/^(мм|миллиметр|миллиметра|миллиметров|миллиметры|mm|mmt)$/.test(unit)) return 'mm';
  if (/^(см|сантиметр|сантиметра|сантиметров|сантиметры|cm|cmt)$/.test(unit)) return 'cm';
  if (/^(м2|м²|квм|квадратныйметр|квадратногометра|квадратныхметров|квадратныеметры|m2|m²|mtk)$/.test(unit)) return 'm2';
  if (/^(м3|м³|кубм|кубическийметр|кубическогометра|кубическихметров|кубическиеметры|m3|m³|mtq)$/.test(unit)) return 'm3';
  if (/^(компл|комплект|комплекта|комплектов|комплекты|набор|набора|наборов|наборы|set|sets)$/.test(unit)) return 'set';
  if (/^(пара|пары|пар)$/.test(unit)) return 'pair';
  if (/^(рулон|рулона|рулонов|рулоны)$/.test(unit)) return 'roll';
  if (/^(т|тонна|тонны|тонн|tonne|tne)$/.test(unit)) return 'tonne';
  return null;
}

export function compatibleUnits(first?: string | null, second?: string | null) {
  return unitKind(first) != null && unitKind(first) === unitKind(second);
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
      !compatibleUnits(requestedUnit, stockUnit) ||
      (availability === 'OutOfStock' && stockQuantity > 0)) {
    return { verdict: 'unknown' };
  }
  if (stockQuantity < requested) {
    return { verdict: 'shortage', missing: requested - stockQuantity };
  }
  return { verdict: 'enough' };
}
