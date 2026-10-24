import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const { outputText } = ts.transpileModule(readFileSync(new URL('../src/lib/productDiscovery.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
const { canRecommendProductLead, isVerifiedProductLead, productVerificationScope, visibleProductLeads, reportItemHasProductCards, publishedProductPhones, productDiscoveryCsv } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

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
