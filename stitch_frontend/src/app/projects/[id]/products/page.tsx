'use client';

import { FormEvent, useCallback, useEffect, useId, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { api, downloadBlob, errorMessage } from '@/lib/api';
import { EmptyState, InfoBanner, Spinner } from '@/components/ui';

type Lead = {
  title?: string | null; snippet?: string | null; price?: number | null;
  currency?: string | null; shop?: string | null; url?: string | null;
};
type Risk = { code: string; severity: 'high' | 'medium' | 'low'; message: string };
type Calculation = {
  landed_cost_kzt?: number | string | null; score: number | string; eligible: boolean;
  risks: Risk[]; reasons: string[];
};
type Offer = {
  id: string; product_item_id?: string | null; supplier_name: string; supplier_bin?: string | null;
  supplier_contact?: string | null; product_name: string; quoted_unit?: string | null;
  offered_quantity?: number | string | null; unit_conversion_factor?: number | string | null;
  unit_price?: number | string | null; total_price?: number | string | null; currency: string;
  exchange_rate_to_kzt?: number | string | null; vat_included?: boolean | null;
  vat_rate?: number | string | null; min_order_quantity?: number | string | null;
  availability_status: string; available_quantity?: number | string | null;
  delivery_cost?: number | string | null; delivery_days?: number | null; warranty_months?: number | null;
  certificates: string[]; specification_compliant?: boolean | null; compliance_notes?: string | null;
  quote_date?: string | null; price_valid_until?: string | null; source_type: 'manual' | 'csv' | 'discovery';
  source_reference?: string | null; match_status: string; notes?: string | null; is_selected: boolean;
  is_recommended?: boolean; calculation?: Calculation;
};
type Item = {
  id: string; product_name: string; specs?: string | null; unit?: string | null; quantity?: number | null;
  required_certificates: string[]; warranty_required: boolean; desired_delivery_date?: string | null;
  status: string; error_message?: string | null; results: Lead[]; offers: Offer[];
  effective_offer_id?: string | null;
};
type Overview = {
  settings: { target_margin_percent: number | string; base_currency: string };
  summary: {
    item_count: number; covered_item_count: number; estimated_landed_cost_kzt?: number | string | null;
    estimated_bid_kzt?: number | string | null; estimated_profit_kzt?: number | string | null;
    selected_risk_count: number; complete: boolean; disclaimer: string;
  };
  items: Item[]; unmatched_offers: Offer[];
};
type OfferForm = {
  id?: string; product_item_id: string; supplier_name: string; supplier_bin: string; supplier_contact: string;
  product_name: string; quoted_unit: string; offered_quantity: string; unit_conversion_factor: string;
  unit_price: string; total_price: string; currency: string; exchange_rate_to_kzt: string;
  vat_included: string; vat_rate: string; min_order_quantity: string; availability_status: string;
  available_quantity: string; delivery_cost: string; delivery_days: string; warranty_months: string;
  certificates: string; specification_compliant: string; compliance_notes: string; quote_date: string;
  price_valid_until: string; source_type: 'manual' | 'csv' | 'discovery'; source_reference: string; notes: string;
};
type ItemForm = {
  id?: string; product_name: string; specs: string; unit: string; quantity: string;
  required_certificates: string; warranty_required: boolean; desired_delivery_date: string;
};

const EMPTY_OFFER: OfferForm = {
  product_item_id: '', supplier_name: '', supplier_bin: '', supplier_contact: '', product_name: '',
  quoted_unit: '', offered_quantity: '', unit_conversion_factor: '', unit_price: '', total_price: '',
  currency: 'KZT', exchange_rate_to_kzt: '', vat_included: '', vat_rate: '', min_order_quantity: '',
  availability_status: 'unknown', available_quantity: '', delivery_cost: '', delivery_days: '',
  warranty_months: '', certificates: '', specification_compliant: '', compliance_notes: '',
  quote_date: '', price_valid_until: '', source_type: 'manual', source_reference: '', notes: '',
};
const EMPTY_ITEM: ItemForm = {
  product_name: '', specs: '', unit: '', quantity: '', required_certificates: '',
  warranty_required: false, desired_delivery_date: '',
};

function money(value?: number | string | null) {
  if (value == null || value === '') return '—';
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(value)) + ' ₸';
}
function number(value?: number | string | null) {
  if (value == null || value === '') return '—';
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 4 }).format(Number(value));
}
function nullableNumber(value: string) {
  return value.trim() === '' ? null : Number(value.replace(',', '.'));
}
function availability(value: string) {
  return ({ available: 'В наличии', limited: 'Ограничено', unavailable: 'Нет в наличии', unknown: 'Не подтверждено' } as Record<string, string>)[value] || value;
}
function riskClass(severity: Risk['severity']) {
  return severity === 'high' ? 'bg-red-50 text-red-800 border-red-200' : severity === 'medium' ? 'bg-amber-50 text-amber-800 border-amber-200' : 'bg-blue-50 text-blue-800 border-blue-200';
}
function Modal({ title, close, children }: { title: string; close: () => void; children: React.ReactNode }) {
  const titleId = useId();
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const closeHandlerRef = useRef(close);

  useEffect(() => {
    closeHandlerRef.current = close;
  }, [close]);

  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeHandlerRef.current();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      previouslyFocused?.focus();
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 bg-black/45 flex items-end sm:items-center justify-center sm:p-4" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <div className="bg-surface w-full sm:max-w-3xl max-h-[92vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl border border-outline-variant shadow-2xl">
        <div className="sticky top-0 z-10 bg-surface/95 backdrop-blur flex justify-between items-center px-5 py-4 border-b border-outline-variant">
          <h2 id={titleId} className="text-headline-md font-headline-md">{title}</h2>
          <button ref={closeButtonRef} type="button" onClick={close} className="p-2 rounded-lg hover:bg-surface-container" aria-label="Закрыть"><span className="material-symbols-outlined">close</span></button>
        </div>
        {children}
      </div>
    </div>
  );
}
function Field({ label, value, change, type = 'text', required, placeholder }: {
  label: string; value: string; change: (value: string) => void; type?: string; required?: boolean; placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="block text-label-md font-label-md mb-1.5">{label}</span>
      <input type={type} step={type === 'number' ? 'any' : undefined} value={value} onChange={(event) => change(event.target.value)} required={required} placeholder={placeholder}
        className="w-full px-3 py-2.5 rounded-lg border border-outline-variant bg-surface-container-lowest focus:outline-none focus:border-primary" />
    </label>
  );
}

export default function ProjectProductsPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [searching, setSearching] = useState(false);
  const [margin, setMargin] = useState('15');
  const [offerForm, setOfferForm] = useState<OfferForm | null>(null);
  const [offerToDelete, setOfferToDelete] = useState<Offer | null>(null);
  const [itemForm, setItemForm] = useState<ItemForm | null>(null);
  const [rfq, setRfq] = useState<{ subject: string; body: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.get('/projects/' + projectId + '/sourcing') as Overview;
      setOverview(data);
      setMargin(String(data.settings.target_margin_percent));
      setError('');
      return data;
    } catch (err) {
      setError(errorMessage(err, 'Не удалось загрузить сравнение поставщиков'));
      return null;
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => { await load(); })();
  }, [load]);
  useEffect(() => {
    if (!searching) return;
    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      void load().then((data) => {
        const active = data?.items.some((item) => item.status === 'searching' || item.status === 'pending');
        if ((!active && data && data.items.length > 0) || attempts >= 24) {
          window.clearInterval(timer);
          setSearching(false);
          setNotice(active ? 'Поиск продолжается в фоне. Обновите страницу позже.' : 'Позиции и потенциальные поставщики обновлены.');
        }
      });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [load, searching]);

  async function run(key: string, action: () => Promise<void>, fallback: string) {
    setBusy(key); setError(''); setNotice('');
    try { await action(); } catch (err) { setError(errorMessage(err, fallback)); } finally { setBusy(''); }
  }
  function startSearch() {
    void run('search', async () => {
      await api.post('/projects/' + projectId + '/products/search', {});
      setSearching(true);
      setNotice('Идёт извлечение позиций и поиск потенциальных поставщиков. Найденные цены потребуют подтверждения.');
    }, 'Не удалось запустить поиск');
  }
  function importCsv(file?: File) {
    if (!file) return;
    void run('import', async () => {
      const body = new FormData(); body.append('file', file);
      const result = await api.post('/projects/' + projectId + '/supplier-offers/import', body);
      const errors = Array.isArray(result?.errors) ? result.errors.length : 0;
      const details = errors ? result.errors.slice(0, 3).map((entry: { row: number; message: string }) => 'строка ' + entry.row + ': ' + entry.message).join('; ') : '';
      setNotice('Импортировано: ' + (result?.created || 0) + '. Требуют сопоставления: ' + (result?.needs_review || 0) + (errors ? '. Ошибок: ' + errors + ' (' + details + ')' : ''));
      await load();
    }, 'Не удалось импортировать CSV');
  }
  function downloadCsv(kind: 'template' | 'comparison') {
    const template = kind === 'template';
    void run('download-' + kind, async () => {
      await downloadBlob(
        '/projects/' + projectId + (template ? '/supplier-offers/template.csv' : '/sourcing/export.csv'),
        template ? 'supplier-offers-template.csv' : 'supplier-comparison.csv',
      );
      setNotice(template ? 'Шаблон CSV скачан. Заполните поставщиков и цены.' : 'Сравнение поставщиков экспортировано.');
    }, template ? 'Не удалось скачать шаблон CSV' : 'Не удалось экспортировать сравнение');
  }
  function openNewOffer(item: Item, lead?: Lead) {
    setOfferForm({
      ...EMPTY_OFFER, product_item_id: item.id, product_name: lead?.title || item.product_name,
      supplier_name: lead?.shop || '', quoted_unit: item.unit || '',
      offered_quantity: item.quantity == null ? '' : String(item.quantity),
      unit_price: lead?.price == null ? '' : String(lead.price),
      currency: lead?.currency === '₸' ? 'KZT' : lead?.currency || 'KZT',
      source_type: lead ? 'discovery' : 'manual', source_reference: lead?.url || '',
    });
  }
  function openEditOffer(offer: Offer) {
    const str = (value: unknown) => value == null ? '' : String(value);
    setOfferForm({
      id: offer.id, product_item_id: offer.product_item_id || '', supplier_name: offer.supplier_name,
      supplier_bin: offer.supplier_bin || '', supplier_contact: offer.supplier_contact || '',
      product_name: offer.product_name, quoted_unit: offer.quoted_unit || '',
      offered_quantity: str(offer.offered_quantity), unit_conversion_factor: str(offer.unit_conversion_factor),
      unit_price: str(offer.unit_price), total_price: str(offer.total_price), currency: offer.currency,
      exchange_rate_to_kzt: str(offer.exchange_rate_to_kzt), vat_included: str(offer.vat_included),
      vat_rate: str(offer.vat_rate), min_order_quantity: str(offer.min_order_quantity),
      availability_status: offer.availability_status, available_quantity: str(offer.available_quantity),
      delivery_cost: str(offer.delivery_cost), delivery_days: str(offer.delivery_days),
      warranty_months: str(offer.warranty_months), certificates: offer.certificates.join('; '),
      specification_compliant: str(offer.specification_compliant), compliance_notes: offer.compliance_notes || '',
      quote_date: offer.quote_date || '', price_valid_until: offer.price_valid_until || '',
      source_type: offer.source_type, source_reference: offer.source_reference || '', notes: offer.notes || '',
    });
  }
  function saveOffer(event: FormEvent) {
    event.preventDefault(); if (!offerForm) return;
    void run('offer', async () => {
      const payload = {
        product_item_id: offerForm.product_item_id || null, supplier_name: offerForm.supplier_name,
        supplier_bin: offerForm.supplier_bin || null, supplier_contact: offerForm.supplier_contact || null,
        product_name: offerForm.product_name, quoted_unit: offerForm.quoted_unit || null,
        offered_quantity: nullableNumber(offerForm.offered_quantity), unit_conversion_factor: nullableNumber(offerForm.unit_conversion_factor),
        unit_price: nullableNumber(offerForm.unit_price), total_price: nullableNumber(offerForm.total_price),
        currency: offerForm.currency, exchange_rate_to_kzt: nullableNumber(offerForm.exchange_rate_to_kzt),
        vat_included: offerForm.vat_included === '' ? null : offerForm.vat_included === 'true',
        vat_rate: nullableNumber(offerForm.vat_rate), min_order_quantity: nullableNumber(offerForm.min_order_quantity),
        availability_status: offerForm.availability_status, available_quantity: nullableNumber(offerForm.available_quantity),
        delivery_cost: nullableNumber(offerForm.delivery_cost), delivery_days: nullableNumber(offerForm.delivery_days),
        warranty_months: nullableNumber(offerForm.warranty_months),
        certificates: offerForm.certificates.split(';').map((x) => x.trim()).filter(Boolean),
        specification_compliant: offerForm.specification_compliant === '' ? null : offerForm.specification_compliant === 'true',
        compliance_notes: offerForm.compliance_notes || null, quote_date: offerForm.quote_date || null,
        price_valid_until: offerForm.price_valid_until || null, source_type: offerForm.source_type,
        source_reference: offerForm.source_reference || null, match_status: offerForm.product_item_id ? 'confirmed' : 'review',
        notes: offerForm.notes || null,
      };
      if (offerForm.id) await api.patch('/projects/' + projectId + '/supplier-offers/' + offerForm.id, payload);
      else await api.post('/projects/' + projectId + '/supplier-offers', payload);
      setOfferForm(null); setNotice('Предложение сохранено. Риски и рекомендация пересчитаны.'); await load();
    }, 'Не удалось сохранить предложение');
  }
  function saveItem(event: FormEvent) {
    event.preventDefault(); if (!itemForm) return;
    void run('item', async () => {
      const payload = {
        product_name: itemForm.product_name, specs: itemForm.specs || null, unit: itemForm.unit || null,
        quantity: nullableNumber(itemForm.quantity),
        required_certificates: itemForm.required_certificates.split(';').map((x) => x.trim()).filter(Boolean),
        warranty_required: itemForm.warranty_required, desired_delivery_date: itemForm.desired_delivery_date || null,
      };
      if (itemForm.id) await api.patch('/projects/' + projectId + '/products/' + itemForm.id, payload);
      else await api.post('/projects/' + projectId + '/products', payload);
      setItemForm(null); await load();
    }, 'Не удалось сохранить позицию');
  }
  function selectOffer(itemId: string, offerId: string | null) {
    void run('select-' + itemId, async () => {
      await api.put('/projects/' + projectId + '/sourcing/items/' + itemId + '/selection', { offer_id: offerId });
      await load();
    }, 'Не удалось изменить выбор');
  }
  function deleteOffer() {
    if (!offerToDelete) return;
    void run('delete-offer', async () => {
      await api.delete('/projects/' + projectId + '/supplier-offers/' + offerToDelete.id);
      setOfferToDelete(null);
      setNotice('Предложение удалено. Сравнение пересчитано.');
      await load();
    }, 'Не удалось удалить предложение');
  }

  if (loading) return <div className="py-20"><Spinner label="Загрузка предложений…" /></div>;

  return (
    <div className="px-4 md:px-margin-page py-stack-lg">
      <div className="max-w-container-max mx-auto space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-headline-lg font-headline-lg">Поставщики и себестоимость</h1>
            <p className="text-body-md text-on-surface-variant mt-1 max-w-3xl">Сравнение КП по соответствию ТЗ, наличию, срокам, документам и итоговой стоимости.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(event) => { importCsv(event.target.files?.[0]); event.target.value = ''; }} />
            <button type="button" onClick={() => downloadCsv('template')} disabled={Boolean(busy)} className="px-3 py-2 border border-outline-variant rounded-lg text-label-md disabled:opacity-50">Шаблон CSV</button>
            <button type="button" onClick={() => fileRef.current?.click()} disabled={Boolean(busy)} className="px-3 py-2 border border-outline-variant rounded-lg text-label-md disabled:opacity-50">Импорт CSV</button>
            <button type="button" onClick={() => downloadCsv('comparison')} disabled={!overview?.items.length || Boolean(busy)} className="px-3 py-2 border border-outline-variant rounded-lg text-label-md disabled:opacity-50">Экспорт сравнения</button>
            <button type="button" onClick={() => setItemForm({ ...EMPTY_ITEM })} className="px-3 py-2 border border-outline-variant rounded-lg text-label-md">Добавить позицию</button>
            <button type="button" onClick={() => void run('rfq', async () => setRfq(await api.post('/projects/' + projectId + '/sourcing/rfq-draft', {})), 'Не удалось сформировать запрос')} disabled={!overview?.items.length || Boolean(busy)} className="px-3 py-2 border border-outline-variant rounded-lg text-label-md disabled:opacity-50">Черновик запроса</button>
            <button type="button" onClick={startSearch} disabled={searching || Boolean(busy)} className="px-4 py-2 bg-on-background text-on-primary rounded-lg text-label-md disabled:opacity-50">{searching ? 'Поиск…' : 'Найти поставщиков'}</button>
          </div>
        </div>
        <div aria-live="polite">{notice && <InfoBanner>{notice}</InfoBanner>}</div>
        {error && <div role="alert" className="bg-error-container border border-red-200 rounded-lg px-4 py-3">{error}</div>}

        {overview && overview.summary.item_count > 0 && (
          <>
            <section className="grid sm:grid-cols-2 xl:grid-cols-5 gap-3" aria-label="Сводка расчёта">
              {[
                ['Покрыто позиций', overview.summary.covered_item_count + ' из ' + overview.summary.item_count],
                ['Оценочная себестоимость', money(overview.summary.estimated_landed_cost_kzt)],
                ['Оценочная цена заявки', money(overview.summary.estimated_bid_kzt)],
                ['Оценочная прибыль', money(overview.summary.estimated_profit_kzt)],
                ['Риски выбранной схемы', String(overview.summary.selected_risk_count)],
              ].map(([label, value]) => <div key={label} className="bg-surface border border-outline-variant rounded-xl p-4"><p className="text-label-md text-on-surface-variant">{label}</p><p className="text-headline-md font-headline-md mt-2">{value}</p></div>)}
            </section>
            <section className="bg-surface-container-low border border-outline-variant rounded-xl p-4 flex flex-wrap items-end gap-3">
              <Field label="Целевая маржа, %" value={margin} change={setMargin} type="number" />
              <button type="button" onClick={() => void run('margin', async () => { await api.put('/projects/' + projectId + '/sourcing/settings', { target_margin_percent: Number(margin.replace(',', '.')) }); await load(); }, 'Не удалось сохранить маржу')} className="px-4 py-2.5 bg-primary text-on-primary rounded-lg">Сохранить</button>
              <p className="text-body-sm text-on-surface-variant flex-1 min-w-64">{overview.summary.disclaimer}</p>
            </section>
          </>
        )}

        {overview?.unmatched_offers.length ? (
          <section className="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <h2 className="text-headline-md font-headline-md text-amber-950">Нужно сопоставить: {overview.unmatched_offers.length}</h2>
            <div className="mt-3 space-y-2">
              {overview.unmatched_offers.map((offer) => (
                <div key={offer.id} className="bg-white/70 rounded-lg p-3 flex flex-wrap items-center gap-3">
                  <div className="flex-1 min-w-52"><p className="font-bold">{offer.supplier_name}</p><p className="text-body-sm text-on-surface-variant">{offer.product_name}</p></div>
                  <select aria-label="Позиция ТЗ" value={offer.product_item_id || ''} onChange={(event) => {
                    const itemId = event.target.value; if (!itemId) return;
                    void run('match', async () => { await api.patch('/projects/' + projectId + '/supplier-offers/' + offer.id, { product_item_id: itemId, match_status: 'confirmed' }); await load(); }, 'Не удалось сопоставить строку');
                  }} className="px-3 py-2 rounded-lg border border-amber-300 bg-white">
                    <option value="">Выберите позицию…</option>
                    {overview.items.map((item) => <option key={item.id} value={item.id}>{item.product_name}</option>)}
                  </select>
                  <button type="button" onClick={() => openEditOffer(offer)} className="px-3 py-2 border border-amber-300 rounded-lg">Проверить</button>
                  <button type="button" onClick={() => setOfferToDelete(offer)} className="px-3 py-2 border border-red-200 text-red-700 rounded-lg">Удалить</button>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {!overview || overview.items.length === 0 ? (
          <EmptyState icon="manage_search" title="Позиции ТЗ ещё не подготовлены" description="Извлеките позиции из загруженного ТЗ или добавьте их вручную, затем внесите КП или импортируйте CSV." action={{ label: 'Извлечь позиции и найти поставщиков', onClick: startSearch }} />
        ) : (
          <div className="space-y-5">
            {overview.items.map((item, index) => (
              <section key={item.id} className="bg-surface border border-outline-variant rounded-2xl overflow-hidden">
                <div className="p-4 md:p-5 border-b border-outline-variant bg-surface-container-low/50 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-label-sm text-on-surface-variant uppercase">Позиция {index + 1}</p>
                    <h2 className="text-headline-md font-headline-md mt-1">{item.product_name}</h2>
                    <p className="text-body-md text-on-surface-variant mt-1">{[item.specs, item.quantity == null ? null : number(item.quantity) + ' ' + (item.unit || '')].filter(Boolean).join(' · ') || 'Характеристики не указаны'}</p>
                    {(item.required_certificates.length > 0 || item.warranty_required || item.desired_delivery_date) && <p className="text-body-sm text-on-surface-variant mt-2">{item.required_certificates.length ? 'Сертификаты: ' + item.required_certificates.join(', ') + '. ' : ''}{item.warranty_required ? 'Гарантия обязательна. ' : ''}{item.desired_delivery_date ? 'Поставка до ' + item.desired_delivery_date + '.' : ''}</p>}
                  </div>
                  <div className="flex gap-2">
                    <button type="button" onClick={() => setItemForm({ id: item.id, product_name: item.product_name, specs: item.specs || '', unit: item.unit || '', quantity: item.quantity == null ? '' : String(item.quantity), required_certificates: item.required_certificates.join('; '), warranty_required: item.warranty_required, desired_delivery_date: item.desired_delivery_date || '' })} className="px-3 py-2 border border-outline-variant rounded-lg">Требования</button>
                    <button type="button" onClick={() => openNewOffer(item)} className="px-3 py-2 bg-primary text-on-primary rounded-lg">Добавить КП</button>
                  </div>
                </div>
                <div className="p-4 md:p-5">
                  {item.offers.length === 0 ? <div className="border border-dashed border-outline-variant rounded-xl p-5 text-center"><p>Нет подтверждённых предложений</p><p className="text-body-sm text-on-surface-variant mt-1">Добавьте КП или импортируйте таблицу.</p></div> : (
                    <div className="grid xl:grid-cols-2 gap-3">
                      {item.offers.map((offer) => {
                        const effective = item.effective_offer_id === offer.id;
                        return (
                          <article key={offer.id} className={'rounded-xl border p-4 ' + (effective ? 'border-primary bg-primary/5' : 'border-outline-variant')}>
                            <div className="flex justify-between gap-3">
                              <div><div className="flex flex-wrap items-center gap-2"><h3 className="font-bold">{offer.supplier_name}</h3>{offer.is_selected && <span className="px-2 py-0.5 text-label-sm rounded bg-primary text-on-primary">Выбрано вручную</span>}{!offer.is_selected && offer.is_recommended && <span className="px-2 py-0.5 text-label-sm rounded bg-emerald-100 text-emerald-800">Рекомендуется</span>}{offer.source_type === 'discovery' && <span className="px-2 py-0.5 text-label-sm rounded bg-amber-100 text-amber-800">Из поиска</span>}</div><p className="text-body-sm text-on-surface-variant mt-1">{offer.product_name}</p></div>
                              <div className="text-right"><p className="text-headline-md font-headline-md">{money(offer.calculation?.landed_cost_kzt)}</p><p className="text-label-sm text-on-surface-variant">с доставкой</p></div>
                            </div>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-4 text-body-sm">
                              <div><p className="text-on-surface-variant">Цена</p><p>{offer.unit_price != null ? number(offer.unit_price) + ' ' + offer.currency + '/' + (offer.quoted_unit || 'ед.') : money(offer.total_price)}</p></div>
                              <div><p className="text-on-surface-variant">НДС</p><p>{offer.vat_included == null ? 'Не указан' : offer.vat_included ? 'Включён' : '+' + (offer.vat_rate ?? '?') + '%'}</p></div>
                              <div><p className="text-on-surface-variant">Наличие</p><p>{availability(offer.availability_status)}</p></div>
                              <div><p className="text-on-surface-variant">Доставка</p><p>{offer.delivery_days == null ? 'Не указана' : offer.delivery_days + ' дн.'}</p></div>
                            </div>
                            <div className="flex flex-wrap gap-1.5 mt-4">{offer.calculation?.risks.map((risk) => <span key={risk.code} className={'px-2 py-1 border rounded-md text-label-sm ' + riskClass(risk.severity)}>{risk.message}</span>)}</div>
                            {offer.calculation?.reasons.length ? <ul className="mt-3 space-y-1 text-body-sm text-on-surface-variant">{offer.calculation.reasons.map((reason) => <li key={reason} className="flex gap-1.5"><span className="text-emerald-600">✓</span>{reason}</li>)}</ul> : null}
                            <div className="flex flex-wrap justify-between items-center gap-2 mt-4 pt-3 border-t border-outline-variant">
                              <span className="text-label-md text-on-surface-variant">Оценка: {number(offer.calculation?.score)} / 100</span>
                              <div className="flex gap-2"><button type="button" onClick={() => openEditOffer(offer)} className="px-3 py-1.5 border border-outline-variant rounded-lg">Проверить</button><button type="button" onClick={() => setOfferToDelete(offer)} className="px-3 py-1.5 border border-red-200 text-red-700 rounded-lg" aria-label={'Удалить предложение ' + offer.supplier_name}>Удалить</button><button type="button" onClick={() => selectOffer(item.id, offer.is_selected ? null : offer.id)} className="px-3 py-1.5 bg-on-background text-on-primary rounded-lg">{offer.is_selected ? 'Сбросить' : 'Выбрать'}</button></div>
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  )}
                  {item.results.length > 0 && <details className="mt-4"><summary className="cursor-pointer text-label-md text-primary">Потенциальные поставщики из поиска ({item.results.length})</summary><div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg p-3 text-body-sm text-amber-900">Это поисковые ссылки, а не подтверждённые КП. Они не участвуют в рекомендации до проверки.</div><div className="grid md:grid-cols-2 gap-3 mt-3">{item.results.map((lead, leadIndex) => <div key={(lead.url || lead.title || '') + leadIndex} className="border border-outline-variant rounded-xl p-3"><p className="font-bold line-clamp-2">{lead.title || 'Без названия'}</p><p className="text-body-sm text-on-surface-variant mt-1">{lead.shop || 'Источник не определён'}{lead.price == null ? '' : ' · ' + money(lead.price)}</p><div className="flex gap-3 mt-2">{lead.url && <a href={lead.url} target="_blank" rel="noopener noreferrer" className="text-label-md text-primary">Открыть</a>}<button type="button" onClick={() => openNewOffer(item, lead)} className="text-label-md text-primary">Внести как КП</button></div></div>)}</div></details>}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>

      {offerForm && <Modal title={offerForm.id ? 'Проверка предложения' : 'Новое предложение'} close={() => setOfferForm(null)}>
        <form onSubmit={saveOffer} className="p-5 space-y-5">
          {offerForm.source_type === 'discovery' && <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-body-sm text-amber-900">Данные предзаполнены из поиска. Подтвердите их по официальному КП.</div>}
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Поставщик" value={offerForm.supplier_name} change={(x) => setOfferForm({ ...offerForm, supplier_name: x })} required />
            <Field label="БИН поставщика" value={offerForm.supplier_bin} change={(x) => setOfferForm({ ...offerForm, supplier_bin: x })} placeholder="12 цифр" />
            <Field label="Контакт" value={offerForm.supplier_contact} change={(x) => setOfferForm({ ...offerForm, supplier_contact: x })} />
            <Field label="Товар в КП" value={offerForm.product_name} change={(x) => setOfferForm({ ...offerForm, product_name: x })} required />
            <Field label="Количество в КП" value={offerForm.offered_quantity} change={(x) => setOfferForm({ ...offerForm, offered_quantity: x })} type="number" />
            <Field label="Единица поставщика" value={offerForm.quoted_unit} change={(x) => setOfferForm({ ...offerForm, quoted_unit: x })} />
            <Field label="Коэффициент к единице ТЗ" value={offerForm.unit_conversion_factor} change={(x) => setOfferForm({ ...offerForm, unit_conversion_factor: x })} type="number" placeholder="20 для упаковки 20 шт" />
            <Field label="Цена за единицу" value={offerForm.unit_price} change={(x) => setOfferForm({ ...offerForm, unit_price: x })} type="number" />
            <Field label="Общая сумма" value={offerForm.total_price} change={(x) => setOfferForm({ ...offerForm, total_price: x })} type="number" />
            <Field label="Валюта" value={offerForm.currency} change={(x) => setOfferForm({ ...offerForm, currency: x.toUpperCase() })} required />
            {offerForm.currency !== 'KZT' && <Field label="Курс в KZT" value={offerForm.exchange_rate_to_kzt} change={(x) => setOfferForm({ ...offerForm, exchange_rate_to_kzt: x })} type="number" />}
            <label><span className="block text-label-md mb-1.5">НДС</span><select value={offerForm.vat_included} onChange={(event) => setOfferForm({ ...offerForm, vat_included: event.target.value })} className="w-full px-3 py-2.5 border border-outline-variant rounded-lg bg-surface"><option value="">Не указано</option><option value="true">Включён</option><option value="false">Не включён</option></select></label>
            <Field label="Ставка НДС, %" value={offerForm.vat_rate} change={(x) => setOfferForm({ ...offerForm, vat_rate: x })} type="number" />
            <Field label="Минимальный заказ" value={offerForm.min_order_quantity} change={(x) => setOfferForm({ ...offerForm, min_order_quantity: x })} type="number" />
            <label><span className="block text-label-md mb-1.5">Наличие</span><select value={offerForm.availability_status} onChange={(event) => setOfferForm({ ...offerForm, availability_status: event.target.value })} className="w-full px-3 py-2.5 border border-outline-variant rounded-lg bg-surface"><option value="unknown">Не подтверждено</option><option value="available">В наличии</option><option value="limited">Ограничено</option><option value="unavailable">Нет в наличии</option></select></label>
            <Field label="Доступное количество" value={offerForm.available_quantity} change={(x) => setOfferForm({ ...offerForm, available_quantity: x })} type="number" />
            <Field label="Стоимость доставки" value={offerForm.delivery_cost} change={(x) => setOfferForm({ ...offerForm, delivery_cost: x })} type="number" />
            <Field label="Срок доставки, дней" value={offerForm.delivery_days} change={(x) => setOfferForm({ ...offerForm, delivery_days: x })} type="number" />
            <Field label="Гарантия, месяцев" value={offerForm.warranty_months} change={(x) => setOfferForm({ ...offerForm, warranty_months: x })} type="number" />
            <Field label="Сертификаты через ;" value={offerForm.certificates} change={(x) => setOfferForm({ ...offerForm, certificates: x })} />
            <label><span className="block text-label-md mb-1.5">Соответствие ТЗ</span><select value={offerForm.specification_compliant} onChange={(event) => setOfferForm({ ...offerForm, specification_compliant: event.target.value })} className="w-full px-3 py-2.5 border border-outline-variant rounded-lg bg-surface"><option value="">Не проверено</option><option value="true">Соответствует</option><option value="false">Не соответствует</option></select></label>
            <Field label="Дата КП" value={offerForm.quote_date} change={(x) => setOfferForm({ ...offerForm, quote_date: x })} type="date" />
            <Field label="Цена действует до" value={offerForm.price_valid_until} change={(x) => setOfferForm({ ...offerForm, price_valid_until: x })} type="date" />
          </div>
          <label><span className="block text-label-md mb-1.5">Комментарий по соответствию</span><textarea value={offerForm.compliance_notes} onChange={(event) => setOfferForm({ ...offerForm, compliance_notes: event.target.value })} rows={3} className="w-full px-3 py-2.5 border border-outline-variant rounded-lg bg-surface" /></label>
          <div className="flex justify-end gap-2"><button type="button" onClick={() => setOfferForm(null)} className="px-4 py-2.5 border border-outline-variant rounded-lg">Отмена</button><button type="submit" disabled={busy === 'offer'} className="px-4 py-2.5 bg-primary text-on-primary rounded-lg disabled:opacity-50">Сохранить и пересчитать</button></div>
        </form>
      </Modal>}

      {offerToDelete && <Modal title="Удалить предложение?" close={() => setOfferToDelete(null)}>
        <div className="p-5 space-y-4">
          <p>КП поставщика <strong>{offerToDelete.supplier_name}</strong> по товару «{offerToDelete.product_name}» будет удалено без возможности восстановления.</p>
          {offerToDelete.is_selected && <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-body-sm text-amber-900">Это предложение выбрано вручную. После удаления система вернётся к лучшей допустимой рекомендации.</div>}
          <div className="flex justify-end gap-2"><button type="button" onClick={() => setOfferToDelete(null)} className="px-4 py-2.5 border border-outline-variant rounded-lg">Отмена</button><button type="button" onClick={deleteOffer} disabled={busy === 'delete-offer'} className="px-4 py-2.5 bg-red-700 text-white rounded-lg disabled:opacity-50">{busy === 'delete-offer' ? 'Удаление…' : 'Удалить КП'}</button></div>
        </div>
      </Modal>}

      {itemForm && <Modal title={itemForm.id ? 'Требования к позиции' : 'Новая позиция ТЗ'} close={() => setItemForm(null)}>
        <form onSubmit={saveItem} className="p-5 space-y-4">
          <Field label="Наименование" value={itemForm.product_name} change={(x) => setItemForm({ ...itemForm, product_name: x })} required />
          <label><span className="block text-label-md mb-1.5">Характеристики</span><textarea value={itemForm.specs} onChange={(event) => setItemForm({ ...itemForm, specs: event.target.value })} rows={4} className="w-full px-3 py-2.5 border border-outline-variant rounded-lg bg-surface" /></label>
          <div className="grid sm:grid-cols-2 gap-4"><Field label="Количество" value={itemForm.quantity} change={(x) => setItemForm({ ...itemForm, quantity: x })} type="number" /><Field label="Единица" value={itemForm.unit} change={(x) => setItemForm({ ...itemForm, unit: x })} /><Field label="Сертификаты через ;" value={itemForm.required_certificates} change={(x) => setItemForm({ ...itemForm, required_certificates: x })} /><Field label="Дата поставки" value={itemForm.desired_delivery_date} change={(x) => setItemForm({ ...itemForm, desired_delivery_date: x })} type="date" /></div>
          <label className="flex items-center gap-2"><input type="checkbox" checked={itemForm.warranty_required} onChange={(event) => setItemForm({ ...itemForm, warranty_required: event.target.checked })} />Гарантия обязательна</label>
          <div className="flex justify-end gap-2"><button type="button" onClick={() => setItemForm(null)} className="px-4 py-2.5 border border-outline-variant rounded-lg">Отмена</button><button type="submit" className="px-4 py-2.5 bg-primary text-on-primary rounded-lg">Сохранить</button></div>
        </form>
      </Modal>}

      {rfq && <Modal title="Черновик запроса коммерческого предложения" close={() => setRfq(null)}>
        <div className="p-5 space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-body-sm text-blue-900">Черновик не отправляется автоматически. Проверьте адресата и условия.</div>
          <Field label="Тема" value={rfq.subject} change={(x) => setRfq({ ...rfq, subject: x })} />
          <label><span className="block text-label-md mb-1.5">Текст</span><textarea value={rfq.body} onChange={(event) => setRfq({ ...rfq, body: event.target.value })} rows={16} className="w-full px-3 py-2.5 border border-outline-variant rounded-lg bg-surface font-mono text-body-sm" /></label>
          <div className="flex justify-end"><button type="button" onClick={() => void navigator.clipboard.writeText('Тема: ' + rfq.subject + '\\n\\n' + rfq.body).then(() => setNotice('Черновик скопирован.'))} className="px-4 py-2.5 bg-primary text-on-primary rounded-lg">Скопировать</button></div>
        </div>
      </Modal>}
    </div>
  );
}
