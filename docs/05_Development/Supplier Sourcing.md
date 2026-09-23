# Supplier sourcing and price comparison

## Scope

The sourcing workspace extends the existing project-level product extraction flow. `product_search_items` remain the tender line items produced from the latest processed specification, while `supplier_offers` store user-entered or imported commercial offers. Re-running extraction preserves existing line-item IDs and linked offers.

Web search results are discovery leads only. They are not treated as verified supplier quotes and never participate in price totals or recommendations. The application does not send RFQs or place orders; it only prepares a draft that a user can review and copy.

## Data entry

- Manual tender item and supplier-offer entry is available in the project’s **Products / Снабжение** tab.
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
