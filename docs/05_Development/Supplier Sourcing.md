# Supplier sourcing and price comparison

## Scope

The sourcing workspace extends the existing project-level product extraction flow. `product_search_items` remain the tender line items produced from the latest processed specification, while `supplier_offers` store user-entered or imported commercial offers. Re-running extraction preserves existing line-item IDs and linked offers.

When an uploaded PDF or DOCX reaches `ready`, the document worker automatically queues both tender analysis and product discovery. Kazakhstan technical specifications represented as repeated label/value fields are supported in Russian and Kazakh; when both language versions are present, the Russian section is used as the canonical copy to avoid duplicate line items. The Products / Снабжение page keeps polling while extracted items are still being searched.

Web search first opens concrete public product pages and reads their Product JSON-LD, published description, characteristics, photo and price. Category/search pages remain secondary links. Each product card compares every extracted technical requirement with source evidence and distinguishes full evidence, partial evidence, conflicts and unknown facts. A bounded AI pass may resolve semantic descriptions, but only when its quoted evidence occurs in the source page; unavailable AI leaves conservative deterministic results. Published product data still needs user confirmation and never becomes a supplier quote or enters price totals or recommendations. The application does not send RFQs or place orders; it only prepares a draft that a user can review and copy.

## Quick PDF check

The dashboard's **Быстро проверить PDF** button opens `/quick-check`, a flow that does not create a tender or retain the uploaded PDF. `POST /api/v1/quick-check/parse` validates a PDF (20 MB / 60 pages), keeps native text where available, and uses local Poppler/Tesseract OCR only for pages without a meaningful text layer (at most 12 scanned pages and 90 seconds per request). OCR supports Russian, Kazakh, and English, reports how many pages it processed, and asks users to verify recognized values. It extracts up to 20 product positions and their requested quantities. The extracted positions and search results are saved in `quick_check_reports` for the authenticated user and company. After committing the report, the API queues a Celery task to search each position sequentially, persisting progress and requirement-by-requirement matches after each item. The browser polls the saved report, so closing it does not cancel the check. `POST /api/v1/quick-check/reports/{id}/run` resumes an interrupted check without re-uploading the PDF, preserving already checked positions. The existing `POST /api/v1/quick-check/search` remains available for a manual single-position retry. `GET /api/v1/quick-check/reports` provides the owner-scoped history in 20-report cursor pages and lifetime totals for reports, extracted positions, and checked positions; `GET /api/v1/quick-check/reports/{id}` reopens one saved report, and `DELETE /api/v1/quick-check/reports/{id}` permanently removes an owner-scoped result. All routes require authentication and owner/company scope. The OCR binaries and language data are installed in both backend Docker images. Checks made before server-side history was introduced cannot be recovered because the earlier flow did not persist results.

The background worker checks positions sequentially to avoid flooding public product sites. The client can retry a single position or resume all unfinished positions without re-uploading the PDF, including after reopening a saved report. The view highlights a source-linked evidence matrix for the best verified product and lets users download a CSV report of requirements, match statuses, source evidence, and published stock. Product cards compare an explicitly published stock count against the requested quantity only when their units are compatible; otherwise sufficiency remains unknown. The PDF view summarizes enough, shortage, and unconfirmed-stock candidate counts separately from specification compliance.

A card shows an exact stock count only when the product page publishes one (for example Product JSON-LD `inventoryLevel` or an explicit stock line). An `InStock` flag without a number is displayed as availability with unknown quantity, never as a fabricated count.

## Data entry

- Manual tender item and supplier-offer entry is available in the project’s **Товары** tab.
- CSV and XLSX imports accept up to 1,000 rows and 5 MB. Download the in-product CSV template for canonical columns. The same template is checked in as [`supplier_quotes_template.csv`](supplier_quotes_template.csv) for development and onboarding use.
- Russian and English column aliases are supported. Required values are supplier name, item name, and unit price.
- Ambiguous name matches are held for human review. Imported source names and units are retained alongside normalized values.
- PDF and image quote ingestion is intentionally disabled because the repository does not contain reliable table OCR for commercial prices.

## Comparison rules

The backend uses deterministic calculations rather than an LLM:

1. Units are converted only within known compatible dimensions (for example tonnes to kilograms). Unknown or cross-dimensional conversions block recommendation.
2. Non-KZT offers require a user-supplied exchange rate. Unknown VAT treatment prevents a confirmed landed-cost calculation.
3. Landed cost includes the required quantity, price basis, minimum order quantity, delivery, currency conversion, and VAT.
4. Recommendations exclude noncompliant offers, unsafe conversions, expired quotes, insufficient availability, missing exchange rates, and deadline failures.
5. Eligible offers are scored using compliance (45%), economics (30%), delivery (15%), and assurance/freshness evidence (10%). Lowest price alone cannot make an offer eligible.
6. The UI flags stale or unknown prices, suspiciously cheap offers, missing characteristics, certificates and warranty, unknown availability, and delivery risk.
7. A user can override the recommendation. The chosen sourcing combination and target margin feed the estimated bid and profit; incomplete positions remain clearly marked.

## API and deployment

All routes are below `/api/v1/projects/{project_id}/sourcing` and enforce project plus company scope through the authenticated user. The migration `20260923000000_supplier_sourcing.sql` creates the tenant-scoped tables, indexes, triggers, and RLS policies. XLSX import requires `openpyxl`, included in `backend/requirements.txt`.

Apply Supabase migrations before deployment, then deploy the backend and frontend together. The backend still calls `create_all` for development environments, but production should treat the SQL migration as authoritative.
