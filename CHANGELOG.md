# Changelog

## 1.4.3 — 2026-10-05

### Added

- Quick Check accepts modern Word documents (`.docx`) in addition to text PDFs and scans.
- DOCX extraction includes both normal paragraphs and table cells before product discovery begins.

### Safety

- Word uploads are validated as real DOCX packages and rejected when encrypted, malformed, or excessively expanded.
- Legacy `.doc` files receive an explicit instruction to be saved as `.docx`; uploaded source files are still not retained.

### Verification

- Real in-memory Word documents, invalid packages, and legacy-format guidance are covered by backend tests.
- Frontend lint, TypeScript checks, and the production build pass with the combined PDF/DOCX upload flow.

## 1.4.2 — 2026-10-04

### Fixed

- Quick Check now extracts concrete product pages directly from Satu search results when a general search engine returns only categories.
- Long procurement descriptions now prefer an embedded manufacturer and model, such as `Philips FC9734/01`, as the product-search query.
- Product cards show the published seller name and phone numbers, and CSV exports include both fields.

### Safety

- Seller contacts are displayed only when they are explicitly published on the product page.
- Search/category pages still cannot become product cards or contribute unverified prices to comparisons.

### Verification

- 244 backend tests, frontend lint, TypeScript checks, and a live public search for `Philips FC9734/01` pass.

## 1.4.1 — 2026-09-30

### Fixed

- Quick Check now recognizes numbered Satu product URLs as concrete product pages instead of catalog pages.
- Direct product links remain visible as clearly marked unverified candidates when a seller blocks automated page reads.
- Targeted fallback search now checks both Kaspi and Satu for concrete product pages.

### Safety

- Unverified candidates never contribute prices, photos, or specifications to automatic supplier comparisons.
- Automatic comparison still accepts only verified product pages with a valid price.

### Verification

- 241 backend tests, frontend lint, TypeScript checks, and the production Webpack build pass.

## 1.4.0 — 2026-09-28

### Added

- Project financial summary with separate goods, delivery, other costs, and risk-reserve amounts.
- Full-cost, bid-price, planned-profit, gross-margin, and markup calculations based on selected supplier offers.
- Persistent project-level assumptions for other costs and contingency percentage.

### Changed

- Supplier comparison now shows an explicit completeness status and warns when uncovered positions are excluded from the estimate.
- Financial inputs are validated in the UI, API, and PostgreSQL schema.

### Verification

- 239 backend tests, frontend lint, TypeScript checks, production build, migration validation, and browser-to-database verification pass.

## 1.3.1 — 2026-09-27

### Added

- Safe request correlation IDs across response headers, structured logs, and API error metadata.
- Application-version headers and versioned health responses for reliable production verification.
- User-visible support codes for server-side failures.

### Changed

- Exposed tracing headers through CORS while rejecting unsafe client-supplied request IDs.

### Verification

- Added coverage for normal, unsafe-ID, 404, and unhandled-error request paths.

## 1.3.0 — 2026-09-27

### Added

- SHA-256 PDF fingerprinting that reuses the newest matching Quick Check report without retaining the uploaded file.
- Fresh Quick Check reruns from saved positions while preserving previous reports in history.
- Accessible loading, route-not-found, segment-error, and global-error screens for the Next.js application.

### Changed

- Updated project status and deployment documentation to match the live production architecture.

### Verification

- Backend tests, frontend lint, TypeScript checks, production build, and Supabase migration dry run pass.

## 1.2.0 — 2026-09-27

### Added

- Private Quick Check history with cursor pagination, lifetime totals, and report reopening.
- Saved evidence and product-search results without retaining uploaded PDF files.
- Background item-by-item product checks that continue after the browser closes and can resume safely.
- CSV exports and owner-scoped report deletion.
- Automatic supplier comparison from discovered product offers, including the best-option recommendation.
- Vendor product photos and richer public-page evidence on product cards.

### Changed

- Raised the Supabase Auth minimum password length from 6 to 8 characters.
- Replaced hard browser redirects with Next.js navigation where component routing is available.

## 1.1.0 — 2026-09-27

### Added

- Supplier quote import, normalization, comparison, margin planning, and RFQ drafts.
- Stateless PDF quick check with verified product cards, stock sufficiency, and bounded parallel search.
- Product-page evidence extraction, SSRF protections, and evidence-backed requirement matching.
- Redis rate limits for authentication, PDF uploads, and AI-assisted search.

### Changed

- Hardened production health endpoints, error responses, TLS handling, and Supabase table access.
- Improved background processing visibility, polling, product extraction, and tender monitoring.
- Reconciled legacy production sourcing tables with the current additive migration model.

### Verification

- Backend test suite, frontend lint, TypeScript checks, and production build pass.
