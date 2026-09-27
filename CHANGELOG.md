# Changelog

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
