'use client';

import { useState } from 'react';
import Image, { type ImageLoaderProps } from 'next/image';
import { assessStock, displayUnit } from '@/lib/productStock';
import { canRecommendProductLead, canonicalProductUrl, hasProductPhoto, isConfirmedProductOffer, isProductCardLead, isVerifiedProductLead, productConfirmationGaps, productQuantityMessage, productVerificationScope, publishedProductPhones, visibleProductLeads, type DiscoveryLead, type ProductLeadFilter } from '@/lib/productDiscovery';

export { isProductCardLead, isVerifiedProductLead, productLeadScore } from '@/lib/productDiscovery';
export type { DiscoveryCheck, DiscoveryLead } from '@/lib/productDiscovery';

interface Props {
  productName: string;
  leads: DiscoveryLead[];
  requestedQuantity?: number | string | null;
  requestedUnit?: string | null;
  existingOfferUrls?: string[];
  addingUrl?: string | null;
  disabled?: boolean;
  onAddOffer?: (lead: DiscoveryLead) => void | Promise<void>;
  leadFilter?: ProductLeadFilter;
}

export function isAutoComparableLead(
  lead: DiscoveryLead
): lead is DiscoveryLead & { url: string; price: number } {
  return Boolean(
    isProductCardLead(lead) &&
    lead.page_verified &&
    lead.url &&
    lead.price != null &&
    Number.isFinite(Number(lead.price)) &&
    (lead.match_status === 'matched' || lead.match_status === 'partial')
  );
}

const tones = {
  matched: {
    label: 'Все выделенные требования подтверждены',
    cls: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    icon: 'verified',
  },
  partial: {
    label: 'Подтверждено частично',
    cls: 'border-amber-200 bg-amber-50 text-amber-900',
    icon: 'rule',
  },
  mismatch: {
    label: 'Есть расхождения с ТЗ',
    cls: 'border-rose-200 bg-rose-50 text-rose-800',
    icon: 'error',
  },
  unknown: {
    label: 'Данных для проверки мало',
    cls: 'border-slate-200 bg-slate-50 text-slate-700',
    icon: 'help',
  },
  unverified: {
    label: 'Источник не проверен',
    cls: 'border-slate-200 bg-slate-50 text-slate-700',
    icon: 'help',
  },
};

const checkLabels = { matched: 'Подтверждено', mismatch: 'Расхождение', unknown: 'Нет данных' };
const checkIcons = { matched: 'check_circle', mismatch: 'cancel', unknown: 'help' };
const checkColors = {
  matched: 'text-emerald-700',
  mismatch: 'text-rose-700',
  unknown: 'text-amber-700',
};
const emptyOfferUrls: string[] = [];

function directImageLoader({ src }: ImageLoaderProps) {
  return src;
}

function ProductPhoto({ src, name }: { src?: string | null; name: string }) {
  const imageUrl = hasProductPhoto({ page_verified: true, image_url: src }) ? src : null;
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

function ProductCard({
  lead,
  requestedQuantity,
  requestedUnit,
  recommended,
  added,
  adding,
  disabled,
  onAddOffer,
}: {
  lead: DiscoveryLead;
  requestedQuantity?: number | string | null;
  requestedUnit?: string | null;
  recommended: boolean;
  added: boolean;
  adding: boolean;
  disabled: boolean;
  onAddOffer?: (lead: DiscoveryLead) => void | Promise<void>;
}) {
  const checks = [...(lead.checks ?? [])].sort(
    (a, b) =>
      ({ mismatch: 0, unknown: 1, matched: 2 })[a.status] -
      { mismatch: 0, unknown: 1, matched: 2 }[b.status]
  );
  const confirmed = checks.filter((check) => check.status === 'matched').length;
  const verification = productVerificationScope(lead);
  const tone = tones[lead.page_verified ? lead.match_status ?? 'unknown' : 'unverified'];
  const name = lead.title || 'Товар без названия';
  const price =
    lead.page_verified && lead.price != null && lead.currency
      ? `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(lead.price)} ${lead.currency === 'KZT' ? '₸' : lead.currency}`
      : null;
  const stock = !lead.page_verified
    ? 'Наличие не подтверждено: страница не прочитана'
    : lead.availability === 'InStock' && lead.stock_quantity === 0
      ? 'Данные о наличии противоречивы — уточните у продавца'
    : lead.availability === 'OutOfStock'
      ? 'Нет в наличии'
    : lead.stock_quantity != null
      ? lead.stock_quantity > 0
        ? `В наличии: ${new Intl.NumberFormat('ru-RU').format(lead.stock_quantity)} ${lead.stock_unit || 'ед.'}`
        : 'Нет в наличии'
      : lead.availability === 'InStock'
        ? 'По странице: в наличии · количество не указано'
        : lead.availability === 'OutOfStock'
          ? 'Нет в наличии'
          : 'Остаток не опубликован';
  const stockAssessment = assessStock(
    requestedQuantity,
    requestedUnit,
    lead.page_verified ? lead.stock_quantity : null,
    lead.page_verified ? lead.stock_unit : null,
    lead.page_verified ? lead.availability : null
  );
  const canAdd = Boolean(
    onAddOffer && lead.page_verified && lead.url && lead.price != null && Number.isFinite(Number(lead.price)) && Number(lead.price) > 0
  );
  const seller = lead.seller_name || lead.shop || 'Продавец не указан';
  const sellerPhones = publishedProductPhones(lead);
  const confirmationGaps = productConfirmationGaps(lead);
  const quantityMessage = productQuantityMessage(requestedQuantity, displayUnit(requestedUnit), stockAssessment.verdict);

  return (
    <article className="flex h-full flex-col gap-3 rounded-2xl border border-outline-variant bg-surface-container-lowest p-4 shadow-sm transition-shadow hover:shadow-md">
      {recommended && (
        <span className="inline-flex w-fit items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-label-sm font-label-sm text-primary">
          <span className="material-symbols-outlined text-[16px]">workspace_premium</span>Лучшее
          совпадение
        </span>
      )}
      <ProductPhoto key={lead.image_url || name} src={lead.page_verified ? lead.image_url : null} name={name} />
      <div className="flex flex-wrap items-center justify-between gap-2 text-label-sm text-on-surface-variant">
        <span className="inline-flex items-center gap-1">
          <span className="material-symbols-outlined text-[15px]">storefront</span>
          {lead.shop || 'Открытый источник'}
        </span>
        {price && <span className="font-semibold text-on-surface">{price}</span>}
      </div>
      <h4 className="line-clamp-2 min-h-12 text-title-md font-title-md text-on-surface">{name}</h4>
      <div className="rounded-xl bg-surface-container-low px-3 py-2.5 text-label-sm text-on-surface-variant">
        <p className="flex items-start gap-1.5">
          <span className="material-symbols-outlined mt-0.5 text-[16px]">storefront</span>
          <span><span className="font-medium text-on-surface">Продавец:</span> {seller}</span>
        </p>
        {sellerPhones.length ? (
          <div className="mt-1.5 flex items-start gap-1.5">
            <span className="material-symbols-outlined mt-0.5 text-[16px]">call</span>
            <span>
              <span className="font-medium text-on-surface">{lead.page_verified ? 'Телефон на странице источника:' : 'Контакт источника — проверьте:'}</span>{' '}
              {sellerPhones.map((phone, index) => (
                <span key={phone}>
                  {index > 0 && ' · '}
                  <a className="text-primary hover:underline" href={`tel:${phone.replace(/[^+\d]/g, '')}`}>
                    {phone}
                  </a>
                </span>
              ))}
            </span>
          </div>
        ) : (
          <p className="mt-1.5 flex items-center gap-1.5">
            <span className="material-symbols-outlined text-[16px]">phone_disabled</span>
            Телефон на странице не найден
          </p>
        )}
      </div>
      {lead.description && (
        <p className="line-clamp-3 text-body-sm text-on-surface-variant">{lead.description}</p>
      )}
      <span
        className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-label-sm font-label-sm ${tone.cls}`}
      >
        <span className="material-symbols-outlined text-[16px]">{tone.icon}</span>
        {verification.label || tone.label}
      </span>
      <p className="flex items-center gap-1.5 text-label-sm text-on-surface-variant">
        <span className="material-symbols-outlined text-[16px]">inventory</span>
        {stock}
      </p>
      {requestedQuantity != null && (
        <p
          className={`flex items-center gap-1.5 text-label-sm ${stockAssessment.verdict === 'enough' ? 'text-emerald-700' : stockAssessment.verdict === 'shortage' ? 'text-rose-700' : 'text-on-surface-variant'}`}
        >
          <span className="material-symbols-outlined text-[16px]">
            {stockAssessment.verdict === 'enough'
              ? 'task_alt'
              : stockAssessment.verdict === 'shortage'
                ? 'warning'
                : 'help'}
          </span>
          {stockAssessment.verdict === 'enough'
            ? 'Хватает на весь заказ'
            : stockAssessment.verdict === 'shortage'
              ? `Не хватает ${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(stockAssessment.missing ?? 0)} ${displayUnit(requestedUnit)}`
              : quantityMessage}
        </p>
      )}
      <p className="text-label-sm text-on-surface-variant">
        {verification.explanation || (checks.length ? `По ТЗ подтверждено ${confirmed} из ${checks.length} выделенных требований` : 'Характеристики кандидата ещё не подтверждены')}
      </p>
      {confirmationGaps.length > 0 && <details className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-body-sm">
        <summary className="cursor-pointer font-medium text-on-surface">Почему карточка пока не подтверждена ({confirmationGaps.length})</summary>
        <ul className="mt-2 space-y-2 text-on-surface-variant">{confirmationGaps.map((gap) => <li key={gap.code}><p>{gap.label}</p>{gap.requirements?.length ? <ul className="mt-1 list-disc space-y-1 pl-4 text-label-sm">{gap.requirements.map((requirement, index) => <li key={index} className="break-words">{requirement}</li>)}</ul> : null}</li>)}</ul>
      </details>}
      {!!checks.length && (
        <details className="rounded-xl bg-surface-container-low p-3 text-body-sm open:pb-4">
          <summary className="cursor-pointer font-medium text-on-surface">
            Проверка характеристик ({checks.length})
          </summary>
          <ul className="mt-3 space-y-3">
            {checks.map((check, index) => (
              <li
                key={`${check.id ?? index}-${index}`}
                className="border-t border-outline-variant/70 pt-2 first:border-t-0 first:pt-0"
              >
                <div className="flex items-start gap-2">
                  <span
                    className={`material-symbols-outlined mt-0.5 text-[17px] ${checkColors[check.status]}`}
                  >
                    {checkIcons[check.status]}
                  </span>
                  <div className="min-w-0">
                    <p className="break-words font-medium text-on-surface">{check.requirement}</p>
                    <p className={`text-label-sm ${checkColors[check.status]}`}>
                      {checkLabels[check.status]}
                    </p>
                    {check.evidence && (
                      <p className="mt-1 break-words text-on-surface-variant">
                        Источник: «{check.evidence}»
                      </p>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}
      <div className="mt-auto grid gap-2 sm:grid-cols-2">
        {canAdd && (
          <button
            type="button"
            onClick={() => void onAddOffer?.(lead)}
            disabled={added || disabled}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-primary px-3 py-2.5 text-label-md font-label-md text-primary hover:bg-primary/5 disabled:border-outline-variant disabled:bg-surface-container disabled:text-on-surface-variant"
          >
            <span
              className={`material-symbols-outlined text-[17px] ${adding ? 'animate-spin' : ''}`}
            >
              {added ? 'check_circle' : adding ? 'progress_activity' : 'add_chart'}
            </span>
            {added ? 'В сравнении' : adding ? 'Добавляем…' : 'В сравнение'}
          </button>
        )}
        {!!lead.url && (
          <a
            href={lead.url}
            target="_blank"
            rel="noopener noreferrer"
            className={`inline-flex items-center justify-center gap-2 rounded-lg bg-on-background px-3 py-2.5 text-label-md font-label-md text-on-primary hover:opacity-90 ${canAdd ? '' : 'sm:col-span-2'}`}
          >
            Открыть товар <span className="material-symbols-outlined text-[17px]">open_in_new</span>
          </a>
        )}
      </div>
    </article>
  );
}

export function ProductDiscoveryCards({
  productName,
  leads,
  requestedQuantity,
  requestedUnit,
  existingOfferUrls = emptyOfferUrls,
  addingUrl = null,
  disabled = false,
  onAddOffer,
  leadFilter = 'all',
}: Props) {
  const products = visibleProductLeads(leads, leadFilter);
  const confirmedProducts = products.filter(isConfirmedProductOffer);
  const readProducts = products.filter((lead) => lead.page_verified && !isConfirmedProductOffer(lead));
  const unverifiedProducts = products.filter((lead) => !lead.page_verified);
  const confirmedTypes = products.filter(isVerifiedProductLead).length;
  const searchLinks = [...new Map(leads.filter((lead) => !isProductCardLead(lead) && canonicalProductUrl(lead.url)).map((lead) => [canonicalProductUrl(lead.url), lead])).values()].slice(0, 6);
  const existingUrls = new Set(existingOfferUrls);
  const renderCard = (lead: DiscoveryLead) => (
    <ProductCard
      key={lead.url}
      lead={lead}
      requestedQuantity={requestedQuantity}
      requestedUnit={requestedUnit}
      recommended={lead === products[0] && canRecommendProductLead(lead)}
      added={Boolean(lead.url && existingUrls.has(lead.url))}
      adding={Boolean(lead.url && addingUrl === lead.url)}
      disabled={disabled}
      onAddOffer={onAddOffer}
    />
  );

  return (
    <div className="border-t border-outline-variant px-4 py-5 md:px-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h4 className="text-title-md font-title-md text-on-surface">
            Товары и кандидаты из открытых источников
          </h4>
          <p className="mt-1 text-body-sm text-on-surface-variant">
            Фото, характеристики и ссылка для позиции «{productName}». Цветная метка показывает,
            насколько опубликованные данные совпадают с ТЗ.
          </p>
        </div>
        <span className="rounded-full bg-primary/10 px-2.5 py-1 text-label-sm text-primary">
          {products.length} карточек · тип подтверждён: {confirmedTypes}
        </span>
      </div>
      {products.length ? (
        <div className="space-y-5">
          {confirmedProducts.length > 0 && <section className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-3 md:p-4" aria-label="Подтверждено по выделенным требованиям и наличию"><h5 className="text-body-md font-semibold text-on-surface">Подтверждено по выделенным требованиям и наличию · {confirmedProducts.length}</h5><p className="mb-4 mt-1 text-body-sm text-on-surface-variant">Есть фото, цена и телефон. Достаточность количества для вашего заказа проверяется отдельно в каждой карточке.</p><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{confirmedProducts.map(renderCard)}</div></section>}
          {readProducts.length > 0 && <section aria-label="Кандидаты с прочитанными страницами"><h5 className="mb-1 text-body-md font-semibold text-on-surface">Кандидаты: требуется подтверждение · {readProducts.length}</h5><p className="mb-4 text-body-sm text-on-surface-variant">Смотрите причину в карточке: требования, наличие или сведения продавца ещё не полностью подтверждены.</p><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{readProducts.map(renderCard)}</div></section>}
          {unverifiedProducts.length > 0 && <section className="rounded-xl border border-dashed border-outline-variant bg-surface-container-low/30 p-3 md:p-4" aria-label="Кандидаты без проверки страницы">
            <h5 className="text-body-md font-semibold text-on-surface">Кандидаты без проверки страницы · {unverifiedProducts.length}</h5>
            <p className="mb-4 mt-1 text-body-sm text-on-surface-variant">Ссылка на товар найдена, но страницу не удалось прочитать. Наличие, цена и соответствие ТЗ требуют проверки у продавца.</p>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{unverifiedProducts.map(renderCard)}</div>
          </section>}
        </div>
      ) : (
        <p className="rounded-xl bg-surface-container-low px-4 py-3 text-body-sm text-on-surface-variant">
          {leadFilter === 'all' ? 'Конкретную товарную ссылку пока не удалось найти. Нажмите «Повторить поиск» у позиции или откройте поиск у продавца ниже.' : 'Нет карточек с выбранными условиями. Измените фильтр или повторите поиск.'}
        </p>
      )}
      {!!searchLinks.length && (
        <details className="mt-4 text-body-sm text-on-surface-variant">
          <summary className="cursor-pointer text-primary">
            Дополнительные ссылки для поиска ({searchLinks.length})
          </summary>
          <div className="mt-3 flex flex-wrap gap-2">
            {searchLinks.map((lead, index) => (
              <a
                key={`${lead.url}-${index}`}
                href={lead.url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg border border-outline-variant px-3 py-2 hover:border-primary hover:text-primary"
              >
                {lead.shop || lead.title || 'Открыть источник'} ↗
              </a>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
