# Legacy customer codes in the existing stock toolbar

Author: Mohamed Fawzy
Date: 2026-11-04

Recent module reference: `a66d053f` — Mohamed Fawzy — 2026-10-29
Original commit subject: `ab_website_sale_product/FIX: restore E-Plus stock refresh on store`

## Current changes before commit:

- Add **Legacy Customer Codes** as the fourth always-visible button after **Sync to Odoo Inventory**, opening activation batches without invoking stock actions.
- Own customer import, preview, code generation, encrypted SMS exports, export auditing, and cancellation inside this existing module. Remove the uncommitted standalone addon from the project.
- Preserve model names and activation behavior while separating backend security helpers from storefront authentication to avoid circular dependencies.
- Restrict access by staff role, batch owner, and company. Keep code digests and encrypted exports protected; require HTTPS for exports except explicitly enabled loopback testing.
- Support Arabic and English; preserve existing translation entries and existing stock/pricing changes.

Files changed:

- `__init__.py`, `__manifest__.py`
- `models/__init__.py`, `models/legacy_customer.py`, `models/legacy_activation_batch.py`
- `services/legacy_activation.py`
- `controllers/__init__.py`, `controllers/legacy_export.py`
- `security/ir.model.access.csv`, `security/legacy_customer_rules.xml`
- `views/legacy_customer_views.xml`, `views/legacy_customer_button.xml`
- `static/src/js/legacy_process_batch.js`
- `i18n/ab_website_sale_product.pot`, `i18n/ar.po`, `i18n/ar_001.po`
- `docs/legacy-customers.md`, `changelog.d/2026-11-04-legacy-customer-codes.md`

Validation:

- Targeted upgrades of `ab_website_sale_product` and `ab_ecommerce_storefront` on isolated `codex_legacy_inline_20261104`, created from a neutralized template without the former standalone addon.
- Final suite: 17 actual tests, zero failures/errors, process exit 0 (`/tmp/legacy-inline-final.log`). Covers the Arabic fourth toolbar button and navigation, batch generation/resumption, normalization, one-time claims, expiry, cancellation, permissions, company/website isolation, CSRF, and export authorization.
- Both modules' changed feature strings validated against Odoo-exported POT templates: 83 backend strings and 13 storefront strings in both Arabic catalogs. All four catalogs pass `msgfmt --check-format`; runtime translated button/action and SMS text verified.
- Arabic stock-toolbar screenshot inspected; Python/XML/JS syntax and manifest references checked. The stock refresh/synchronization buttons were not invoked.
- At initial isolated validation, no live database upgrade, customer import, external SMS, or deployment had been performed. Runtime manifests reference no development tests; exclude tests and caches from production packaging.

## Service repair — 2026-11-04 12:18 UTC

- The running `ecom19` service had reloaded the new Python code without upgrading its database. Requests failed with `UndefinedColumn: res_users.ab_signup_otp_pending`.
- Created and verified a PostgreSQL custom-format backup at `/tmp/ecom19-before-legacy-upgrade-20261104-121740.dump` before applying the already validated targeted upgrades to `ab_website_sale_product` and `ab_ecommerce_storefront`.
- Upgrade exited successfully; the existing workers reloaded the registry through Odoo's database signaling. No service stop or manual schema edits were needed.
- Verified the missing field, all four legacy tables, the Arabic fourth toolbar button, its action/form, and the storefront activation template on `ecom19`. No standalone addon is installed.
- Live HTTP checks for `/web/login` and `/` returned 200. No new application errors were logged after the upgrade at verification time.
- No real customer import, code generation, SMS send, stock refresh, or inventory synchronization was performed by this repair.

## Large upload memory repair — 2026-11-04 12:40 UTC

- Replace inline database binary storage for `source_file` with native private Odoo attachments. Check encoded upload size before ORM persistence.
- Stream CSV bytes from the scoped attachment; validate/count duplicates in a complete first pass and stage accepted rows in bounded batches during a second pass. Avoid full-file Unicode/StringIO copies and a retained list of all customer dictionaries.
- Retain the existing maximum size, full-file duplicate exclusion, owner/company restrictions, and atomic rejection of malformed CSV. No new UI strings or permissions were added.
- Isolated validation: 20 tests passed, zero failures/errors (`/tmp/legacy-upload-memory-final.log`), including native `web_save` with an 89,438,937-byte synthetic CSV, 450,000 input rows, private attachment access, cross-chunk duplicates, and all activation/browser regressions.
- Separately exercised actual HTTP JSON-RPC `web_save` and preview on an isolated prefork worker using the live limits: hard 1,677,721,600 bytes and soft 871,088,640 bytes. Save and preview succeeded; the worker recycled normally after exceeding the soft limit. No limits were increased. The synthetic batch was cancelled without generating codes, and the temporary test server was stopped.
- Backed up `ecom19` to `/tmp/ecom19-before-legacy-upgrade-20261104-123730.dump`. A bounded, one-off ORM copy preserved the one already saved 89,430,218-byte upload as a private attachment, with matching file checksum. The old inline value remains retained for recovery; no migration hook or direct SQL write was introduced.
- Applied the targeted module upgrade and Odoo's graceful reload to the ecommerce master. `/web/login` and `/` returned HTTP 200 afterward.
- Read-only inspection of the preserved real upload found malformed CSV quoting after 18,999 parsed records. It was not imported or silently repaired, and no real activation codes were generated.

Additional files changed for this repair: `models/legacy_activation_batch.py`, `docs/legacy-customers.md`, and this changelog.
