import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const { outputText } = ts.transpileModule(readFileSync(new URL('../src/lib/productStock.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
const { assessStock, compatibleUnits, unitKind } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('explicit stock supports the requested quantity only with safely compatible units', () => {
  assert.equal(assessStock(20, 'Штука', 25, 'шт.', 'InStock').verdict, 'enough');
  assert.equal(assessStock(20, 'кг', 15, 'килограмм', 'InStock').verdict, 'shortage');
  assert.equal(assessStock(20, 'м', 25, 'метров', 'InStock').verdict, 'enough');
  assert.equal(assessStock(20, 'комплект', 25, 'компл.', 'InStock').verdict, 'enough');
  assert.equal(assessStock(20, 'дана', 25, 'H87', 'InStock').verdict, 'enough');
  assert.equal(assessStock(20, 'шт.', 25, 'pcs', 'InStock').verdict, 'enough');
  assert.equal(assessStock(20, 'мм', 25, 'MMT', 'InStock').verdict, 'enough');
});

test('availability, generic units, packs and conversion guesses never prove enough stock', () => {
  for (const [requestedUnit, stockUnit] of [['шт.', 'ед.'], ['единица', 'шт.'], ['ед.', 'ед.'], ['шт.', 'упаковка'], ['кг', 'г'], ['л', 'мл'], ['м2', 'м']]) {
    assert.equal(compatibleUnits(requestedUnit, stockUnit), false);
    assert.equal(assessStock(20, requestedUnit, 1000, stockUnit, 'InStock').verdict, 'unknown');
  }
  assert.equal(assessStock(20, 'шт.', null, 'шт.', 'InStock').verdict, 'unknown');
  assert.equal(assessStock(null, 'шт.', 100, 'шт.', 'InStock').verdict, 'unknown');
  assert.equal(assessStock(20, 'шт.', 100, 'шт.', 'OutOfStock').verdict, 'unknown');
});

test('штукатурка cannot be interpreted as штука', () => {
  assert.equal(unitKind('штукатурка'), null);
  assert.equal(compatibleUnits('шт.', 'штукатурка'), false);
  assert.equal(assessStock(20, 'шт.', 25, 'штукатурка', 'InStock').verdict, 'unknown');
  assert.equal(compatibleUnits('штуки', 'штук'), true);
});

test('комплектующие cannot be interpreted as комплект', () => {
  assert.equal(unitKind('комплектующие'), null);
  assert.equal(compatibleUnits('комплект', 'комплектующие'), false);
  assert.equal(assessStock(20, 'комплект', 25, 'комплектующие', 'InStock').verdict, 'unknown');
  assert.equal(compatibleUnits('комплекта', 'комплектов'), true);
});

test('грамматика cannot be interpreted as грамм', () => {
  assert.equal(unitKind('грамматика'), null);
  assert.equal(compatibleUnits('г', 'грамматика'), false);
  assert.equal(assessStock(20, 'г', 25, 'грамматика', 'InStock').verdict, 'unknown');
  assert.equal(compatibleUnits('грамма', 'граммов'), true);
});
