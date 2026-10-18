# BINOM AI 1.5.0 — workspace quality verification

Date: 2026-10-18 (Asia/Almaty).

## Shipped scope

The existing procurement workflow remains the basis of the product. This release improves the workspace shell, dashboard, Quick Check, login, project creation, notifications, and session reliability. It does not add fabricated suppliers, prices, inventory, commercial metrics, or enterprise certifications.

Dashboard counters describe the loaded project selection. The projects endpoint uses cursor pagination with no company-wide total; a `+` indicates that more projects can be loaded. Source availability and specification compliance remain separate checks. Approximate project economics still depend on entered or imported supplier offers.

## Automated checks

- `cd stitch_frontend && npm test`: real API-client code is compiled with the installed TypeScript compiler; tests cover shared refresh, refresh rotation, transient failures, cross-tab changes, logout/login races, cancellation, binary export, validation details, and request IDs.
- `cd stitch_frontend && npm run lint`.
- `cd stitch_frontend && npx tsc --noEmit`.
- `cd stitch_frontend && npm run build -- --webpack`.
- Backend Python 3.11: `pytest -q` (256 tests). External providers and persistence are mocked by the test suite; this does not exercise live Supabase authentication or real supplier websites.

## Browser checks

The actual Next.js application was exercised against an isolated local fixture API. Every company, project, report, and product is explicitly marked `ДЕМО QA`. Fixture credentials are test-only; no production credentials or supplier data are used. The fixture server lives outside the repository and is never part of the deployment. `NEXT_PUBLIC_API_URL` was overridden only for the local development process.

Verified flows:

- Login reaches the protected workspace using the normal form and API contract.
- Server search finds project 24 although only the first 20 projects are initially loaded; arrow keys select a result and Tab dismisses the combobox.
- Pagination grows the project selection from 20 to 24; an unmatched query displays an actionable empty state.
- A project edit can clear an optional customer field and persist the update.
- Notifications consume `{ items, unread_count }`; marking all read clears the badge.
- A saved DOCX report renders its positions and product card before collapsed source requirements and evidence. Card/no-card filters use the actual report rows.
- Theme controls update together; the document uses the loaded Manrope/Inter fonts.
- Password-reset and tender dialogs use native modal focus management and Escape handling.
- At 375px the workspace has no horizontal overflow and the notification panel remains within the viewport. Mobile navigation exposes Quick Check directly.

## Production boundary

A production rollout must be verified against the current Git commit, a successful deployment status, and `/api/v1/health/ready` returning `1.5.0`. A published JavaScript bundle alone does not establish backend rollout. Production login with an existing user and fresh real PDF/DOCX supplier searches require their own authenticated smoke checks; they must not be inferred from the fixture UI checks or unit tests.

No database schema migration is required by this release. Session tokens remain server-authorized; the local session identifier only prevents old browser requests from applying to a new login.
