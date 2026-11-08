# Customer review download over HTTP

Commit: `47990e2025713ff0dd0191be2ef8e41912491356`
Author: Mohamed Fawzy
Date: 2026-11-08
Original subject: `ab_website_sale_product/IMP: add reviewed legacy customer imports and activation codes`

- Added customer review downloads using the same transport restriction as activation-code exports, causing HTTP review downloads to return Forbidden even for authorized staff.

Files changed relevant to this fix:

- `controllers/legacy_export.py`
- `models/legacy_activation_batch.py`
- `docs/legacy-customers.md`

## Current changes before commit:

- Allow customer review CSV downloads through the authenticated backend connection, including local/demo HTTP without a development flag.
- Preserve server-side staff, ownership, company, and preview checks, private response headers, and the HTTPS restriction for activation-code exports.
- Add seven module-local regression tests and document the separate download requirements.

Files changed:

- `controllers/legacy_export.py`
- `docs/legacy-customers.md`
- `tests/__init__.py`
- `tests/test_legacy_review_download.py`
- `changelog.d/2026-11-08-review-download-http.md`

Validation:

- Targeted upgrade of `ab_website_sale_product` on the idle isolated database `codex_legacy_inline_20261104`, ports 5069/5072, workers and cron disabled: exit 0; 10 tests, zero failures/errors. Log: `/tmp/legacy-review-http-fix-tests-final.log`.
- Seven new HTTP/workflow tests plus three existing storefront regressions verified English/Arabic CSV output, owner/admin access, anonymous/portal/other-owner/company denial, source integrity, old-preview rejection, and activation-code export behavior.
- The initial run returned the review CSV successfully but one assertion expected English in an Arabic-only test database. The test fixture now activates English and sets the test website's default language; the final run passed.
- Python syntax and `git diff --check` passed. Both existing Arabic catalogs passed `msgfmt --check-format`; no user-facing source strings changed.
- The isolated clone logged missing pre-existing attachment files; all targeted tests and the upgrade completed successfully. No live server restart, live database upgrade, or demo deployment was performed.
- Runtime change is limited to the controller; deployment requires reloading Odoo's Python workers, with no schema or translation update required for this fix. Exclude development tests from production packages.
