'use client';

import { useState } from 'react';
import Image, { type ImageLoaderProps } from 'next/image';
import { assessStock, displayUnit } from '@/lib/productStock';

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
  characteristics?: Record<string, string>;
  is_product_page?: boolean;
  page_verified?: boolean;
  match_status?: 'matched' | 'partial' | 'mismatch' | 'unknown' | 'unverified';
  checks?: DiscoveryCheck[];
}

interface Props {
  productName: string;
  leads: DiscoveryLead[];
  requestedQuantity?: number | string | null;
  requestedUnit?: string | null;
  existingOfferUrls?: string[];
  addingUrl?: string | null;
  disabled?: boolean;
  onAddOffer?: (lead: DiscoveryLead) => void | Promise<void>;
}

export function isVerifiedProductLead(lead: DiscoveryLead) {
  const typeCheck = lead.checks?.find((check) => check.id === 'type') ?? lead.checks?.[0];
  return Boolean(lead.is_product_page && lead.page_verified && typeCheck?.status === 'matched');
}

export function isProductCardLead(lead: DiscoveryLead) {
  return Boolean(lead.is_product_page && lead.page_verified);
}

export function productLeadScore(lead: DiscoveryLead) {
  const matchPoints = { matched: 500, partial: 350, unknown: 200, unverified: 100, mismatch: 0 };
  const checks = lead.checks ?? [];
  const validImage = Boolean(lead.image_url && /^https?:\/\//i.test(lead.image_url) && !imageNoise.test(lead.image_url));
  return matchPoints[lead.match_status ?? 'unknown']
    + checks.filter((check) => check.status === 'matched').length * 12
    - checks.filter((check) => check.status === 'mismatch').length * 20
    + (validImage ? 70 : 0)
    + (lead.price != null ? 55 : 0)
    + (lead.availability === 'InStock' ? 30 : 0)
    + (lead.stock_quantity != null && lead.stock_quantity > 0 ? 15 : 0);
}

const tones = {
  matched: { label: 'Все требования подтверждены', cls: 'border-emerald-200 bg-emerald-50 text-emerald-800', icon: 'verified' },
  partial: { label: 'Подтверждено частично', cls: 'border-amber-200 bg-amber-50 text-amber-900', icon: 'rule' },
  mismatch: { label: 'Есть расхождения с ТЗ', cls: 'border-rose-200 bg-rose-50 text-rose-800', icon: 'error' },
  unknown: { label: 'Данных для проверки мало', cls: 'border-slate-200 bg-slate-50 text-slate-700', icon: 'help' },
  unverified: { label: 'Источник не проверен', cls: 'border-slate-200 bg-slate-50 text-slate-700', icon: 'help' },
};

const checkLabels = { matched: 'Подтверждено', mismatch: 'Расхождение', unknown: 'Нет данных' };
const checkIcons = { matched: 'check_circle', mismatch: 'cancel', unknown: 'help' };
const checkColors = { matched: 'text-emerald-700', mismatch: 'text-rose-700', unknown: 'text-amber-700' };
const emptyOfferUrls: string[] = [];

const imageNoise = /favicon|logo|sprite|placeholder|\/watch\/|portal-portable|base_satu|pixel/i;

function directImageLoader({ src }: ImageLoaderProps) {
  return src;
}

function ProductPhoto({ src, name }: { src?: string | null; name: string }) {
  const imageUrl = src && /^https?:\/\//i.test(src) && !imageNoise.test(src) ? src : null;
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const failed = imageUrl != null && imageUrl === failedSrc;
  return (
    <div className="relative flex h-44 items-center justify-center overflow-hidden rounded-xl bg-white ring-1 ring-outline-variant/70">
      {imageUrl && !failed ? (
        <Image
          loader={directImageLoader}
          unoptimized
          fill
          sizes="(max-width: 768px) 100vw, (max-width: 1280px) 50vw, 33vw"
          src={imageUrl}
          alt={`Фото товара: ${name}`}
          referrerPolicy="no-referrer"
          onError={() => setFailedSrc(imageUrl)}
          className="object-contain p-3"
        />
      ) : (
        <div className="flex flex-col items-center gap-1.5 text-on-surface-variant/70">
          <span className="material-symbols-outlined text-[46px]">inventory_2</span>
          <span className="text-label-sm">Фото не опубликовано</span>
        </div>
      )}
    </div>
  );
}

function ProductCard({ lead, requestedQuantity, requestedUnit, recommended, added, adding, disabled, onAddOffer }: { lead: DiscoveryLead; requestedQuantity?: number | string | null; requestedUnit?: string | null; recommended: boolean; added: boolean; adding: boolean; disabled: boolean; onAddOffer?: (lead: DiscoveryLead) => void | Promise<void> }) {
  const checks = [...(lead.checks ?? [])].sort((a, b) => ({ mismatch: 0, unknown: 1, matched: 2 })[a.status] - ({ mismatch: 0, unknown: 1, matched: 2 })[b.status]);
  const confirmed = checks.filter((check) => check.status === 'matched').length;
  const tone = tones[lead.match_status ?? 'unknown'];
  const name = lead.title || 'Товар без названия';
  const price = lead.price != null && lead.currency
    ? `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(lead.price)} ${lead.currency === 'KZT' ? '₸' : lead.currency}`
    : null;
  const stock = lead.stock_quantity != null
    ? lead.stock_quantity > 0
      ? `В наличии: ${new Intl.NumberFormat('ru-RU').format(lead.stock_quantity)} ${lead.stock_unit || 'ед.'}`
      : 'Нет в наличии'
    : lead.availability === 'InStock'
      ? 'В наличии · точный остаток не указан'
      : lead.availability === 'OutOfStock'
        ? 'Нет в наличии'
        : 'Остаток не опубликован';
  const stockAssessment = assessStock(requestedQuantity, requestedUnit, lead.stock_quantity, lead.stock_unit, lead.availability);
  const canAdd = Boolean(onAddOffer && lead.url && lead.price != null && Number.isFinite(Number(lead.price)));

  return (
    <article className="flex h-full flex-col gap-3 rounded-2xl border border-outline-variant bg-surface-container-lowest p-4 shadow-sm transition-shadow hover:shadow-md">
      {recommended && <span className="inline-flex w-fit items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-label-sm font-label-sm text-primary"><span className="material-symbols-outlined text-[16px]">workspace_premium</span>Лучшее совпадение</span>}
      <ProductPhoto key={lead.image_url || name} src={lead.image_url} name={name} />
      <div className="flex flex-wrap items-center justify-between gap-2 text-label-sm text-on-surface-variant">
        <span className="inline-flex items-center gap-1"><span className="material-symbols-outlined text-[15px]">storefront</span>{lead.shop || 'Открытый источник'}</span>
        {price && <span className="font-semibold text-on-surface">{price}</span>}
      </div>
      <h4 className="line-clamp-2 min-h-12 text-title-md font-title-md text-on-surface">{name}</h4>
      {lead.description && <p className="line-clamp-3 text-body-sm text-on-surface-variant">{lead.description}</p>}
      <span className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-label-sm font-label-sm ${tone.cls}`}>
        <span className="material-symbols-outlined text-[16px]">{tone.icon}</span>{tone.label}
      </span>
      <p className="flex items-center gap-1.5 text-label-sm text-on-surface-variant"><span className="material-symbols-outlined text-[16px]">inventory</span>{stock}</p>
      {requestedQuantity != null && (
        <p className={`flex items-center gap-1.5 text-label-sm ${stockAssessment.verdict === 'enough' ? 'text-emerald-700' : stockAssessment.verdict === 'shortage' ? 'text-rose-700' : 'text-on-surface-variant'}`}>
          <span className="material-symbols-outlined text-[16px]">{stockAssessment.verdict === 'enough' ? 'task_alt' : stockAssessment.verdict === 'shortage' ? 'warning' : 'help'}</span>
          {stockAssessment.verdict === 'enough'
            ? 'Хватает на весь заказ'
            : stockAssessment.verdict === 'shortage'
              ? `Не хватает ${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(stockAssessment.missing ?? 0)} ${displayUnit(requestedUnit)}`
              : 'Достаточность для заказа не подтверждена'}
        </p>
      )}
      <p className="text-label-sm text-on-surface-variant">По ТЗ подтверждено {confirmed} из {checks.length} требований</p>
      {!!checks.length && (
        <details className="rounded-xl bg-surface-container-low p-3 text-body-sm open:pb-4">
          <summary className="cursor-pointer font-medium text-on-surface">Проверка характеристик ({checks.length})</summary>
          <ul className="mt-3 space-y-3">
            {checks.map((check, index) => (
              <li key={`${check.id ?? index}-${index}`} className="border-t border-outline-variant/70 pt-2 first:border-t-0 first:pt-0">
                <div className="flex items-start gap-2">
                  <span className={`material-symbols-outlined mt-0.5 text-[17px] ${checkColors[check.status]}`}>{checkIcons[check.status]}</span>
                  <div className="min-w-0">
                    <p className="break-words font-medium text-on-surface">{check.requirement}</p>
                    <p className={`text-label-sm ${checkColors[check.status]}`}>{checkLabels[check.status]}</p>
                    {check.evidence && <p className="mt-1 break-words text-on-surface-variant">Источник: «{check.evidence}»</p>}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}
      <div className="mt-auto grid gap-2 sm:grid-cols-2">
        {canAdd && (
          <button type="button" onClick={() => void onAddOffer?.(lead)} disabled={added || disabled} className="inline-flex items-center justify-center gap-2 rounded-lg border border-primary px-3 py-2.5 text-label-md font-label-md text-primary hover:bg-primary/5 disabled:border-outline-variant disabled:bg-surface-container disabled:text-on-surface-variant">
            <span className={`material-symbols-outlined text-[17px] ${adding ? 'animate-spin' : ''}`}>{added ? 'check_circle' : adding ? 'progress_activity' : 'add_chart'}</span>
            {added ? 'В сравнении' : adding ? 'Добавляем…' : 'В сравнение'}
          </button>
        )}
        {!!lead.url && (
          <a href={lead.url} target="_blank" rel="noopener noreferrer" className={`inline-flex items-center justify-center gap-2 rounded-lg bg-on-background px-3 py-2.5 text-label-md font-label-md text-on-primary hover:opacity-90 ${canAdd ? '' : 'sm:col-span-2'}`}>
            Открыть товар <span className="material-symbols-outlined text-[17px]">open_in_new</span>
          </a>
        )}
      </div>
    </article>
  );
}

export function ProductDiscoveryCards({ productName, leads, requestedQuantity, requestedUnit, existingOfferUrls = emptyOfferUrls, addingUrl = null, disabled = false, onAddOffer }: Props) {
  const products = leads.filter(isProductCardLead).sort((a, b) => productLeadScore(b) - productLeadScore(a)).slice(0, 8);
  const searchLinks = leads.filter((lead) => !isProductCardLead(lead) && lead.url).slice(0, 6);
  const existingUrls = new Set(existingOfferUrls);

  return (
    <div className="border-t border-outline-variant px-4 py-5 md:px-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h4 className="text-title-md font-title-md text-on-surface">Товары из открытых источников</h4>
          <p className="mt-1 text-body-sm text-on-surface-variant">Фото, характеристики и ссылка для позиции «{productName}». Цветная метка показывает, насколько опубликованные данные совпадают с ТЗ.</p>
        </div>
        <span className="rounded-full bg-primary/10 px-2.5 py-1 text-label-sm text-primary">{products.length} карточек</span>
      </div>
      {products.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {products.map((lead, index) => <ProductCard key={`${lead.url}-${index}`} lead={lead} requestedQuantity={requestedQuantity} requestedUnit={requestedUnit} recommended={index === 0 && lead.match_status !== 'mismatch'} added={Boolean(lead.url && existingUrls.has(lead.url))} adding={Boolean(lead.url && addingUrl === lead.url)} disabled={disabled} onAddOffer={onAddOffer} />)}
        </div>
      ) : (
        <p className="rounded-xl bg-surface-container-low px-4 py-3 text-body-sm text-on-surface-variant">
          Конкретную карточку товара пока не удалось прочитать. Нажмите «Повторить поиск» у позиции или откройте поиск у продавца ниже.
        </p>
      )}
      {!!searchLinks.length && (
        <details className="mt-4 text-body-sm text-on-surface-variant">
          <summary className="cursor-pointer text-primary">Дополнительные ссылки для поиска ({searchLinks.length})</summary>
          <div className="mt-3 flex flex-wrap gap-2">
            {searchLinks.map((lead, index) => <a key={`${lead.url}-${index}`} href={lead.url} target="_blank" rel="noopener noreferrer" className="rounded-lg border border-outline-variant px-3 py-2 hover:border-primary hover:text-primary">{lead.shop || lead.title || 'Открыть источник'} ↗</a>)}
          </div>
        </details>
      )}
    </div>
  );
}
