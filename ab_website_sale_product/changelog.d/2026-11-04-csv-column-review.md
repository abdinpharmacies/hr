# CSV column validation and import review

Commit: `a66d053feb106a3f41b08d22bc44ec785fde7686`
Author: Mohamed Fawzy
Date: 2026-10-29
Original subject: `ab_website_sale_product/FIX: restore E-Plus stock refresh on store`

- Restored the stock screen used to access the existing Legacy Customer Codes toolbar action.

Files changed in that commit:

- `models/eplus_stock_snapshot.py`
- `changelog.d/current.md`

## Current changes before commit:

- Replace the first-error-only CSV preview with a streamed diagnostic pass and a paginated, read-only column review table. Show source record/file lines, column name/number, original and normalized values, reason, severity, and import status; report multiple problems per record.
- Detect supported delimiters and UTF BOMs, offer explicit Windows Arabic decoding, and record safe formatting corrections. Validate relevant identifiers, phones, active flags, duplicate values, existing customers, encoding, structure, control characters, and size limits.
- Continue collecting diagnostics after malformed quoting without trusting uncertain record boundaries for import. Block generation and stage no customer chunks for structurally ambiguous files. Exclude identifiable invalid records individually when boundaries are reliable.
- Retain source uploads for review until completion/cancellation. Allow resetting an unprocessed preview and replacing its file. Reports cannot be edited through the UI or ORM to bypass validation.
- Apply owner/company record rules and read-only ACLs to diagnostics. Keep internal writes scoped to validated batch operations. Preserve customer/code generation, single-use activation, and export authorization.
- Maintain English sources and both Arabic catalogs. Keep unrelated translations and existing working-tree changes.

Files changed:

- `models/__init__.py`
- `models/legacy_activation_batch.py`
- `models/legacy_import_issue.py`
- `services/legacy_activation.py`
- `services/legacy_csv.py`
- `security/ir.model.access.csv`
- `security/legacy_customer_rules.xml`
- `views/legacy_customer_views.xml`
- `i18n/ab_website_sale_product.pot`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `docs/legacy-customers.md`
- `changelog.d/2026-11-04-csv-column-review.md`

Validation:

- Isolated database: `codex_csv_review_20261104`, cloned from an idle validation database, with this checkout ahead of other custom addons; ports 5269/5272, workers 0, cron threads 0.
- Targeted upgrade of `ab_website_sale_product,ab_ecommerce_storefront`; 27 backend tests passed, zero failures/errors. Includes a 450,000-row, 89,438,937-byte upload and preview; logged peak RSS 1,009,644 KiB in the first run. Final backend log: `/tmp/csv-review-validation-2.log`.
- Five HTTP/browser tests passed, zero failures/errors, including Arabic review-table navigation, column reasons, read-only controls, generation, and activation/export regression checks. Log: `/tmp/csv-review-browser.log`. Arabic form/table screenshots were inspected in `/tmp/csv-review-screenshots/`.
- Real saved upload scanned read-only; isolated full preview scanned 476,969 records and retained 167,591 diagnostics, including all 258 reported quote errors. Candidate/excluded/inactive counts: 343,371 / 88,310 / 45,288. The ambiguous file staged no chunks and created no customers/codes; all test database changes were rolled back.
- Measured full real-file review: 75.63 seconds and peak RSS 262,432 KiB (about 256 MiB), below the configured 1.6 GiB hard worker limit. This was an isolated shell measurement, not a live HTTP import. Log: `/tmp/csv-review-real-memory.log`.
- Both Arabic catalogs passed `msgfmt --check-format`; translations were merged against an Odoo-exported POT without mass regeneration.
- Final runtime translation verification passed for all 34 diagnostic reasons, the customer-specific review state, review button, and updated instructions (`/tmp/csv-review-translation-final.log`). The final targeted label upgrade passed (`/tmp/csv-review-final-labels.log`).
- Python/XML parsing and whitespace checks passed. The cloned database logs missing historical filestore images; these do not affect CSV validation. No live upgrade, original-file repair, customer generation, external SMS, stock mutation, or deployment was performed.
