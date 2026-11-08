# Customer review export validation

Commit: `4b426831a8ab55afc02ecb26b48578befbdd529e`
Author: Mohamed Fawzy
Date: 2026-11-08
Original subject: `ab_ecommerce_storefront/IMP: activate returning customers with single-use codes`

- Integrate verified returning-customer activation into the existing storefront and cover the customer import, review, code-generation and claim workflows.

Files changed in that commit:

- `__manifest__.py`
- `controllers/__init__.py`, `controllers/legacy_activation.py`
- `models/__init__.py`, `models/legacy_customer.py`
- `views/legacy_customer_templates.xml`
- `tests/__init__.py`, `tests/test_legacy_activation.py`
- `i18n/ab_ecommerce_storefront.pot`, `i18n/ar.po`, `i18n/ar_001.po`
- `changelog.d/2026-11-04-csv-review-tests.md`, `changelog.d/2026-11-04-legacy-customer-activation.md`

## Current changes before commit:

- Assert the translated customer review CSV download button and eligibility percentage are visible on the Arabic batch form before opening the column-level issue table.

Files changed:

- `tests/test_legacy_activation.py`
- `changelog.d/2026-11-08-customer-review-validation.md`

Validation:

- Full activation/review suite: 39 tests passed, zero failures/errors on `codex_legacy_inline_20261104`, isolated ports 5069/5072. Log: `/tmp/legacy-review-complete-tests.log`.
- Includes a 450,000-row upload, preview and CSV export plus six HTTP/browser tests. The cloned validation DB has missing historical image blobs; those warnings did not fail the workflow checks.
- Final targeted upgrade and Arabic form regression: one browser test passed with zero failures/errors; verified the translated CSV download button and eligibility percentage. Log: `/tmp/legacy-review-final-ui.log`.
