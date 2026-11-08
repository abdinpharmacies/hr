# Corrected customer review and CSV export

Commit: `47990e2025713ff0dd0191be2ef8e41912491356`
Author: Mohamed Fawzy
Date: 2026-11-08
Original subject: `ab_website_sale_product/IMP: add reviewed legacy customer imports and activation codes`

- Apply deterministic customer formatting corrections, quarantine damaged records, and exclude duplicate identities, including phones identified in damaged rows.
- Display eligibility counts and percentage; exclude existing customers from eligibility for new codes. Require older previews to be rechecked before processing.
- Download a private, translated CSV retaining source columns and values with corrected values and reasons, sorted with eligible customers first. Keep activation code generation separate.

Files changed in that commit:

- `__init__.py`, `__manifest__.py`
- `models/__init__.py`, `models/legacy_activation_batch.py`, `models/legacy_customer.py`, `models/legacy_import_issue.py`
- `services/legacy_activation.py`, `services/legacy_csv.py`
- `controllers/__init__.py`, `controllers/legacy_export.py`
- `security/ir.model.access.csv`, `security/legacy_customer_rules.xml`
- `static/src/js/legacy_process_batch.js`
- `views/legacy_customer_button.xml`, `views/legacy_customer_views.xml`
- `i18n/ab_website_sale_product.pot`, `i18n/ar.po`, `i18n/ar_001.po`
- `docs/legacy-customers.md`
- `changelog.d/2026-11-04-csv-column-review.md`, `changelog.d/2026-11-04-legacy-customer-codes.md`

Commit: `7d595050`
Author: Mohamed Fawzy
Date: 2026-11-08
Original subject: `ab_website_sale_product/IMP: clarify customer review workflow and warning feedback`

- Document safe correction, report columns, eligibility denominator, and separate review/code generation. Use the supported status role for the batch warning.

Files changed in that commit:

- `docs/legacy-customers.md`
- `views/legacy_customer_views.xml`

## Current changes before commit:

- Record the final customer review export validation evidence and distinguish isolated tests from live operations.

Files changed:

- `changelog.d/2026-11-08-customer-review-export.md`

Validation:

- Dedicated DB `codex_legacy_inline_20261104`, HTTP/gevent ports 5069/5072, cron disabled: 39 backend and HTTP/browser tests passed with zero failures/errors. Log: `/tmp/legacy-review-complete-tests.log`.
- Included private attachment access, owner/company isolation, malformed row quarantine, correction output, valid-first sorting, duplicate rejection, zero denominator, existing-customer exclusion, outdated-preview rejection, CSV formula escaping, Arabic HTTP export, activation and SMS export regression checks.
- Uploaded, previewed and exported a synthetic 89,438,937-byte CSV with 450,000 customer rows. The report retained 450,000 data rows plus one file-information row. Peak RSS across the test run: 1,023,512 KiB. This is isolated test evidence, not live worker measurement.
- Both Arabic catalogs passed `msgfmt --check-format`; terms were merged from an Odoo-exported POT. Arabic report headers/status and backend review controls were checked at runtime.
- Original source was additionally scanned read-only through the parser: 476,967 scanned records, 343,334 candidates, 88,350 excluded, 45,283 inactive, and no fatal scan block. These are parser diagnostics, not generated accounts/codes or an applied live preview.
- No original-file edits, real customer generation, code generation, SMS sending, loyalty changes, live database upgrade, or server restart were performed for this change.
