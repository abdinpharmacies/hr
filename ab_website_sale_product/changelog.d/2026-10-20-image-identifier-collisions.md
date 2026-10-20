# Product image identifier collisions

## Recent relevant commit

Commit: `1b31f7d633df95f83c966552435beecd7cf14141`
Author: Mohamed Fawzy
Date: 2026-09-27
Original commit subject: `ab_website_sale_product/feat: add product image sync preview`

- Introduce image scanning, identifier matching and preview reports.

Files changed (relevant to this fix):

- `models/product_image_sync.py`
- `README_product_image_sync.md`

## Current changes before commit:

- Remove Eplus serial fallback from image matching because a serial can equal a different product's code.
- Preserve exact product-code and barcode matching, including nested product folders.
- Keep existing images when no safe source match is found; previously assigned images are not automatically repaired.
- Add regression coverage for serial/code collisions in flat and nested layouts, correct-code selection, and barcode matching.
- Document the supported identifiers and the distinction between preventing new incorrect matches and repairing existing assignments.
- Retain the concurrent image-memory fix documented in `2026-10-20-image-sync-memory.md`.

Files changed:

- `models/product_image_sync.py`
- `tests/test_website_category_mapping.py`
- `README_product_image_sync.md`
- `changelog.d/2026-10-20-image-identifier-collisions.md`

Validation:

- Targeted Odoo 19 upgrade and `TestWebsiteCategoryMapping` on `ab_classification_test_20260930`: 21 tests, 0 failures, 0 errors; HTTP disabled, workers and cron disabled, alternate ports configured as 5069/5072.
- Read-only planning against `ecom19` scanned 32,482 products and 9,358 files: 5,244 code matches, 27,238 missing, zero ambiguous or invalid results. All 316 previously detected serial matches were rejected.
- Confirmed `62741.jpg` matches code `62741` only; code `62742` no longer receives that image via its serial.
- Python syntax, whitespace and both Arabic catalog format checks passed. No source UI strings changed.
- No live image writes, service restarts or live database upgrades were performed. Existing incorrect image assignments remain for separate remediation.
