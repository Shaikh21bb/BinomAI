import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const { outputText } = ts.transpileModule(readFileSync(new URL('../src/lib/productDiscovery.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
const { CLOSURE_POLICY_LABELS, canRecommendProductLead, canonicalProductUrl, hasConfirmedProductRequirements, isCompleteProductLead, isConfirmedProductOffer, isMatchingInStockLead, isVerifiedProductLead, productConfirmationGaps, productQuantityMessage, productVerificationScope, quickCheckProgressLabel, visibleProductLeads, reportConfirmationGaps, reportItemHasProductCards, reportItemMatchesFilter, supportsClosureClarification, publishedProductPhones, productDiscoveryCsv } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

const candidate = {
  title: 'ДЕМО QA — кандидат товара', url: 'https://supplier.example.test/products/qa',
  seller_name: 'ДЕМО QA — синтетический продавец', seller_phone: '+7 000 000 00 01',
  is_product_page: true, page_verified: false, match_status: 'unverified', checks: [],
};
const searchLink = { title: 'ДЕМО QA — общий поиск', url: 'https://market.example.test/search?q=qa', is_product_page: false };
const verified = {
  ...candidate, title: 'ДЕМО QA — тип подтверждён', url: 'https://supplier.example.test/products/checked',
  page_verified: true, match_status: 'partial',
  checks: [
    { id: 'type', requirement: 'Тип товара', status: 'matched', evidence: 'ДЕМО QA — свидетельство из fixture' },
    { id: 'power', requirement: 'Мощность', status: 'unknown' },
  ],
};
const item = (results, state = 'ready') => ({ product_name: 'ДЕМО QA — позиция ТЗ', quantity: 2, unit: 'шт.', state, results });

test('a blocked product page remains a visible candidate and belongs to the with-cards filter', () => {
  assert.equal(visibleProductLeads([searchLink, candidate]).length, 1);
  assert.equal(reportItemHasProductCards(item([candidate, searchLink])), true);
  assert.equal(isVerifiedProductLead(candidate), false);
  assert.equal(reportItemHasProductCards(item([searchLink])), false);
  assert.equal(reportItemHasProductCards(item([])), false);
});

test('type confirmation does not imply that every technical requirement is matched', () => {
  assert.equal(isVerifiedProductLead(verified), true);
  assert.equal(verified.match_status, 'partial');
  assert.equal(isVerifiedProductLead({ ...verified, page_verified: false }), false);
  assert.equal(isVerifiedProductLead({ ...verified, checks: [{ id: 'type', status: 'unknown' }] }), false);
});

test('unverified, unknown and mismatched candidates cannot receive a recommendation badge', () => {
  assert.equal(canRecommendProductLead(candidate), false);
  assert.equal(canRecommendProductLead({ ...verified, page_verified: false }), false);
  assert.equal(canRecommendProductLead({ ...verified, match_status: 'unknown' }), false);
  assert.equal(canRecommendProductLead({ ...verified, match_status: 'mismatch' }), false);
  assert.equal(canRecommendProductLead(verified), false, 'confirmed type with unknown technical specs is insufficient for a recommendation');
  assert.equal(canRecommendProductLead({ ...verified, checks: [...verified.checks, { id: 'certificate', status: 'matched' }] }), true);
});

test('a type-only match cannot claim complete technical compliance or receive a recommendation', () => {
  const typeOnly = { ...verified, match_status: 'matched', checks: [verified.checks[0]] };
  const scope = productVerificationScope(typeOnly);
  assert.equal(isVerifiedProductLead(typeOnly), true);
  assert.equal(scope.technicalCount, 0);
  assert.equal(scope.confirmedTechnicalCount, 0);
  assert.equal(scope.label, 'Совпадает тип товара');
  assert.equal(scope.explanation, 'Технические требования не выделены; проверьте ТЗ вручную.');
  assert.equal(canRecommendProductLead(typeOnly), false);
  const csv = productDiscoveryCsv('ДЕМО QA.docx', [item([typeOnly])]);
  assert.match(csv, /"ready";"Да";"Да";"0";"0"/);
});

test('technical evidence is counted separately from product type confirmation', () => {
  const scope = productVerificationScope(verified);
  assert.equal(scope.technicalCount, 1);
  assert.equal(scope.confirmedTechnicalCount, 0);
  assert.equal(scope.label, null);
  assert.equal(scope.explanation, null);
  const full = { ...verified, match_status: 'matched', checks: verified.checks.map((check) => ({ ...check, status: 'matched' })) };
  assert.equal(canRecommendProductLead(full), true);
  assert.equal(productVerificationScope(full).confirmedTechnicalCount, 1);
});

test('visible selection is ordered, capped at eight, and never includes generic search links', () => {
  const candidates = Array.from({ length: 12 }, (_, index) => ({ ...candidate, title: `ДЕМО QA — кандидат ${index}`, url: `https://supplier.example.test/products/${index}` }));
  const leads = [searchLink, ...candidates, verified];
  const selected = visibleProductLeads(leads);
  assert.equal(selected.length, 8);
  assert.equal(selected[0], verified);
  assert.equal(selected.includes(searchLink), false);
  assert.equal(leads[0], searchLink, 'sorting must not mutate API results');
  const csv = productDiscoveryCsv('ДЕМО QA.docx', [item(leads)]);
  for (const lead of selected) assert.ok(csv.includes(lead.url));
  assert.equal(csv.includes(candidates[11].url), false);
  assert.equal(csv.includes(searchLink.url), false);
});

test('CSV retains unverified candidates, public phone and actual verification status', () => {
  const csv = productDiscoveryCsv('ДЕМО QA.docx', [item([candidate, searchLink])]);
  assert.match(csv, /ДЕМО QA — кандидат товара/);
  assert.match(csv, /ДЕМО QA — синтетический продавец/);
  assert.match(csv, /\+7 000 000 00 01/);
  assert.match(csv, /"unverified"/);
  assert.match(csv, /"ready";"Нет";"Нет"/);
  assert.doesNotMatch(csv, /Товарные страницы не найдены/);
  assert.doesNotMatch(csv, /market\.example\.test/);
});

test('published phone fields merge without losing the legacy number or duplicating formatting', () => {
  assert.deepEqual(publishedProductPhones({ seller_phones: ['+7 (000) 000-00-01', '+7 000 000 00 02'], seller_phone: '+7 000 000 00 01' }), ['+7 (000) 000-00-01', '+7 000 000 00 02']);
  assert.deepEqual(publishedProductPhones({ seller_phones: [], seller_phone: '+7 000 000 00 01' }), ['+7 000 000 00 01']);
  assert.deepEqual(publishedProductPhones({ seller_phones: [], seller_phone: null }), []);
  const csv = productDiscoveryCsv('ДЕМО QA.pdf', [item([{ ...candidate, seller_phones: ['+7 000 000 00 02'] }])]);
  assert.match(csv, /\+7 000 000 00 02 \/ \+7 000 000 00 01/);
});

test('pending, failed and empty-ready items export honest different states', () => {
  for (const [state, label] of [['pending', 'Поиск не завершён'], ['searching', 'Поиск не завершён'], ['error', 'Ошибка поиска'], ['ready', 'Товарные страницы не найдены']]) {
    const row = item(state === 'ready' ? [searchLink] : [candidate], state);
    assert.equal(reportItemHasProductCards(row), false);
    const csv = productDiscoveryCsv('ДЕМО QA.pdf', [row]);
    assert.ok(csv.includes(label));
    assert.ok(csv.includes(`"${state}"`));
    assert.equal(csv.includes(candidate.url), false, 'stale hidden candidates must not appear as a fresh completed search');
  }
});

test('CSV protects spreadsheet formula fields and includes source/type evidence separately', () => {
  const csv = productDiscoveryCsv('=ДЕМО QA.docx', [item([{ ...verified, title: '=1+1' }])]);
  assert.ok(csv.startsWith('\uFEFF'));
  assert.match(csv, /"'=ДЕМО QA\.docx"/);
  assert.match(csv, /"'=1\+1"/);
  assert.match(csv, /ДЕМО QA — свидетельство из fixture/);
  assert.match(csv, /"ready";"Да";"Да"/);
});

test('matching read InStock pages rank before matching unavailable or unknown pages', () => {
  const inStock = { ...verified, availability: 'InStock', url: 'https://supplier.example.test/products/in-stock' };
  const outOfStock = { ...verified, match_status: 'matched', checks: verified.checks.map((check) => ({ ...check, status: 'matched' })), availability: 'OutOfStock', url: 'https://supplier.example.test/products/unavailable', image_url: 'https://supplier.example.test/image.jpg', price: 100, stock_quantity: 50 };
  const unknown = { ...verified, availability: null, url: 'https://supplier.example.test/products/unknown' };
  const selected = visibleProductLeads([outOfStock, candidate, unknown, inStock]);
  assert.equal(selected[0], inStock);
  assert.ok(selected.indexOf(unknown) < selected.indexOf(outOfStock));
  assert.deepEqual(visibleProductLeads([outOfStock, unknown, candidate, inStock], 'in-stock'), [inStock]);
});

test('InStock filter requires type match, read page, compatible overall match and no zero-stock conflict', () => {
  const inStock = { ...verified, availability: 'InStock' };
  assert.equal(isMatchingInStockLead(inStock), true, 'availability alone must not require an exact stock quantity');
  for (const excluded of [
    { ...inStock, page_verified: false },
    { ...inStock, match_status: 'mismatch' },
    { ...inStock, match_status: 'unknown' },
    { ...inStock, stock_quantity: 0 },
    { ...inStock, availability: 'OutOfStock' },
    { ...inStock, availability: null },
    { ...inStock, checks: [{ id: 'type', status: 'unknown' }] },
    { ...inStock, is_product_page: false },
  ]) assert.equal(isMatchingInStockLead(excluded), false);
  assert.equal(reportItemMatchesFilter(item([inStock]), 'in-stock'), true);
  assert.equal(reportItemMatchesFilter(item([inStock], 'searching'), 'in-stock'), false);
});

test('complete filter requires product photo, positive price with currency, and public contact without implying compliance', () => {
  const complete = { ...verified, match_status: 'unknown', checks: [{ id: 'type', status: 'unknown' }], image_url: 'https://supplier.example.test/product-photo.jpg', price: 12000, currency: 'KZT', availability: null };
  assert.equal(isCompleteProductLead(complete), true);
  assert.equal(isMatchingInStockLead(complete), false);
  assert.equal(canRecommendProductLead(complete), false);
  assert.equal(reportItemMatchesFilter(item([complete]), 'complete'), true);
  for (const excluded of [
    { ...complete, page_verified: false }, { ...complete, image_url: 'https://supplier.example.test/logo.png' },
    { ...complete, image_url: 'data:image/png;base64,none' }, { ...complete, price: 0 },
    { ...complete, price: -20 }, { ...complete, price: null }, { ...complete, price: Number.NaN },
    { ...complete, currency: null }, { ...complete, seller_phone: null, seller_phones: [] },
  ]) assert.equal(isCompleteProductLead(excluded), false);
});

test('canonical URL dedup removes tracking copies but preserves product variants and different sellers sharing a phone', () => {
  const original = { ...candidate, url: 'https://supplier.example.test/products/lamp?variant=blue&utm_source=qa#photo' };
  const richer = { ...verified, url: 'https://supplier.example.test/products/lamp/?variant=blue&fbclid=test' };
  const variant = { ...candidate, url: 'https://supplier.example.test/products/lamp?variant=red' };
  const otherSeller = { ...candidate, url: 'https://other-seller.example.test/products/lamp?variant=blue' };
  const selected = visibleProductLeads([original, richer, variant, otherSeller, searchLink]);
  assert.equal(selected.length, 3);
  assert.ok(selected.includes(richer));
  assert.ok(!selected.includes(original));
  assert.ok(selected.includes(variant));
  assert.ok(selected.includes(otherSeller));
  assert.equal(canonicalProductUrl('javascript:alert(1)'), null);
  assert.equal(visibleProductLeads([{ ...candidate, url: undefined }]).length, 0);
  const csv = productDiscoveryCsv('ДЕМО QA.pdf', [item([original, richer])]);
  assert.equal(csv.includes(original.url), false);
  assert.ok(csv.includes(richer.url));
});

test('manual retry stays visible in every result filter without treating old cards as fresh', () => {
  const searching = item([verified], 'searching');
  for (const filter of ['all', 'with-cards', 'without-cards', 'error', 'in-stock', 'complete', 'requirements', 'combined']) {
    assert.equal(reportItemMatchesFilter(searching, filter, true), true);
  }
  assert.equal(reportItemHasProductCards(searching), false);
  assert.equal(reportItemMatchesFilter(searching, 'with-cards'), false);
  assert.equal(reportItemMatchesFilter(item([], 'ready'), 'with-cards'), false);
  assert.equal(reportItemMatchesFilter(item([], 'ready'), 'without-cards'), true);
  assert.equal(quickCheckProgressLabel('completed', 2, 1, 2, 0), 'Повторно ищем товары для позиции 3');
  assert.equal(quickCheckProgressLabel('completed', null, 2, 2, 0), 'Проверка завершена');
});

test('requirements filter needs all extracted technical checks, never a type-only match or an availability flag', () => {
  const full = { ...verified, match_status: 'matched', checks: verified.checks.map((check) => ({ ...check, status: 'matched' })) };
  assert.equal(hasConfirmedProductRequirements(full), true);
  assert.equal(reportItemMatchesFilter(item([full]), 'requirements'), true);
  assert.deepEqual(visibleProductLeads([candidate, full], 'requirements'), [full]);
  for (const excluded of [
    verified, { ...full, checks: [full.checks[0]] }, { ...full, checks: [] },
    { ...full, page_verified: false }, { ...full, match_status: 'partial' },
    { ...full, checks: [...full.checks, { id: 'certificate', status: 'unknown' }] },
    { ...full, checks: [{ id: 'type', status: 'unknown' }, full.checks[1]] },
    { ...candidate, availability: 'InStock' },
  ]) assert.equal(hasConfirmedProductRequirements(excluded), false);
});

test('combined filter accepts a read in-stock card only when all extracted checks and public fields are present', () => {
  const combined = { ...verified, match_status: 'matched', checks: verified.checks.map((check) => ({ ...check, status: 'matched' })), availability: 'InStock', image_url: 'https://supplier.example.test/product-photo.jpg', price: 12000, currency: 'KZT', stock_quantity: null };
  assert.equal(reportItemMatchesFilter(item([combined]), 'combined'), true);
  assert.deepEqual(visibleProductLeads([candidate, combined], 'combined'), [combined]);
  assert.equal(combined.stock_quantity, null, 'published availability does not invent sufficient order quantity');
});

test('combined filter rejects stock-only, partial-spec, unknown-certificate and incomplete-contact cards', () => {
  const full = { ...verified, match_status: 'matched', checks: verified.checks.map((check) => ({ ...check, status: 'matched' })), availability: 'InStock', image_url: 'https://supplier.example.test/product-photo.jpg', price: 12000, currency: 'KZT' };
  for (const excluded of [
    { ...verified, availability: 'InStock' },
    { ...full, match_status: 'partial', checks: verified.checks },
    { ...full, checks: [...full.checks, { id: 'certificate', status: 'unknown' }] },
    { ...full, availability: 'OutOfStock' },
    { ...full, seller_phone: null, seller_phones: [] },
    { ...full, checks: [full.checks[0]] },
  ]) {
    assert.equal(reportItemMatchesFilter(item([excluded]), 'combined'), false);
    assert.equal(visibleProductLeads([excluded], 'combined').length, 0);
  }
});

test('strict-offer gaps identify missing published fields without weakening confirmed technical checks', () => {
  const lead = { ...verified, match_status: 'matched', checks: verified.checks.map((check) => ({ ...check, status: 'matched' })), seller_phone: null, availability: null };
  const gaps = productConfirmationGaps(lead);
  assert.deepEqual(gaps.map((gap) => gap.code), ['availability', 'photo', 'price', 'contact']);
  assert.equal(isConfirmedProductOffer(lead), false);
  assert.equal(hasConfirmedProductRequirements(lead), true);
});

test('strict-offer gaps retain the actual unknown and mismatched requirements', () => {
  const lead = { ...verified, checks: [verified.checks[0], { id: 'certificate', requirement: 'Сертификат соответствия', status: 'unknown' }, { id: 'power', requirement: 'Мощность не менее 10 Вт', status: 'mismatch' }] };
  const gaps = productConfirmationGaps(lead);
  assert.deepEqual(gaps.find((gap) => gap.code === 'requirements-unknown').requirements, ['Сертификат соответствия']);
  assert.deepEqual(gaps.find((gap) => gap.code === 'requirements-mismatch').requirements, ['Мощность не менее 10 Вт']);
  assert.equal(isConfirmedProductOffer(lead), false);
});

test('a confirmed published offer still explicitly declares unknown order quantity', () => {
  const lead = { ...verified, match_status: 'matched', checks: verified.checks.map((check) => ({ ...check, status: 'matched' })), availability: 'InStock', image_url: 'https://supplier.example.test/product-photo.jpg', price: 12000, currency: 'KZT', stock_quantity: null };
  assert.equal(isConfirmedProductOffer(lead), true);
  assert.deepEqual(productConfirmationGaps(lead), []);
  assert.match(productQuantityMessage(20, 'шт.', 'unknown'), /Количество по заказу \(20 шт\.\) не подтверждено/);
  assert.doesNotMatch(productQuantityMessage(20, 'шт.', 'unknown'), /Хватает|подтверждены/);
  assert.equal(productQuantityMessage(20, 'шт.', 'enough'), null);
  assert.match(productQuantityMessage(null, 'шт.', 'unknown'), /Количество в ТЗ не указано/);
});

test('strict empty-state reasons use only actual ready product cards and do not inflate duplicate gaps', () => {
  const ready = item([candidate, { ...candidate, url: 'https://other.example.test/products/qa' }, searchLink]);
  const gaps = reportConfirmationGaps([ready, item([verified], 'searching')]);
  assert.equal(gaps.filter((gap) => gap.code === 'page').length, 1);
  assert.equal(gaps.filter((gap) => gap.code === 'requirements-unchecked').length, 1);
  assert.equal(gaps.some((gap) => gap.code === 'requirements-missing'), false, 'an unread page does not prove that extraction missed the specification');
  assert.deepEqual(reportConfirmationGaps([item([searchLink]), item([], 'error')]), []);
  const typeOnly = { ...verified, match_status: 'matched', checks: [verified.checks[0]] };
  assert.ok(productConfirmationGaps(typeOnly).some((gap) => gap.code === 'requirements-missing'));
});

test('closure clarification is offered for garments requiring a fastening, not unrelated locks or unspecified clothing', () => {
  assert.equal(supportsClosureClarification({ product_name: 'Кофта на замке' }), true);
  assert.equal(supportsClosureClarification({ product_name: 'Кардиган', specs: 'Застёжка на молнии' }), true);
  assert.equal(supportsClosureClarification({ product_name: 'Замок навесной' }), false);
  assert.equal(supportsClosureClarification({ product_name: 'Рюкзак на молнии' }), false);
  assert.equal(supportsClosureClarification({ product_name: 'Кофта шерстяная' }), false);
});

test('CSV carries the saved per-item closure policy without inventing a global approval', () => {
  const source = item([candidate]);
  const approved = { ...item([verified]), closure_policy: 'allow_alternatives' };
  const csv = productDiscoveryCsv('ДЕМО QA.pdf', [source, approved]);
  assert.match(csv, /Уточнение застёжки для выполненного поиска/);
  assert.ok(csv.includes(CLOSURE_POLICY_LABELS.source));
  assert.ok(csv.includes(CLOSURE_POLICY_LABELS.allow_alternatives));
  assert.equal(source.closure_policy, undefined);
  assert.equal(approved.closure_policy, 'allow_alternatives');
  const strict = productDiscoveryCsv('ДЕМО QA.pdf', [{ ...source, closure_policy: 'zipper_only' }]);
  assert.ok(strict.includes(CLOSURE_POLICY_LABELS.zipper_only));
  assert.equal(strict.includes(CLOSURE_POLICY_LABELS.allow_alternatives), false);
});
