# Legacy customer CSV review integration tests

Commit: `667c36d0129bb79da460d90d2db7d9238d27e1b3`
Author: Mohamed Fawzy
Date: 2026-10-15
Original subject: `ab_ecommerce_storefront/IMP: add storefront gift and price offer management`

- Existing storefront integration baseline; CSV review runtime ownership remains in `ab_website_sale_product`.

Files changed in that commit relevant to this reference:

- `__manifest__.py`, `models/__init__.py`

## Current changes before commit:

- Extend existing legacy activation integration tests for per-column diagnostics, multiple errors per row, safe normalizations, malformed/multiline quoting, encodings, duplicates, private reports, retained uploads, preview reset, and existing-customer reporting.
- Verify the Arabic review table, navigation, original value, translated reason, required columns, and read-only controls in the browser.
- Adapt existing preview expectations to retained uploads and reviewable row-level failures. Preserve generation, activation, export, and large-file regressions.

Files changed:

- `tests/test_legacy_activation.py`
- `changelog.d/2026-11-04-csv-review-tests.md`

Validation: 27 backend and five HTTP/browser tests passed on isolated `codex_csv_review_20261104`; logs `/tmp/csv-review-validation-2.log` and `/tmp/csv-review-browser.log`. These tests are development/CI assets and must be excluded from production runtime packages.
