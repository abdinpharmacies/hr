# Returning-customer activation in the existing storefront

Author: Mohamed Fawzy
Date: 2026-11-04

Recent module reference: `824b6b84` — Mohamed Fawzy — 2026-11-02
Original commit subject: `ab_ecommerce_storefront/IMP: add legacy SEO import preview and queued drafts`

## Current changes before commit:

- Integrate customer activation into the existing storefront, extending the historical customer registry owned by `ab_website_sale_product`; no separate addon is required.
- Show a matching verified-phone account its activation prompt, accept a single-use SMS code, and show the returning-customer welcome after successful verification.
- Preserve website/company isolation, rate and attempt limits, expiry, and one-time claims. Email login and loyalty points remain unaffected.
- Maintain both Arabic catalogs and integration tests, including the product module's fourth toolbar button and export authorization.

Files changed:

- `__manifest__.py`, `models/__init__.py`, `controllers/__init__.py`
- `models/legacy_customer.py`, `controllers/legacy_activation.py`
- `views/legacy_customer_templates.xml`
- `i18n/ab_ecommerce_storefront.pot`, `i18n/ar.po`, `i18n/ar_001.po`
- `tests/__init__.py`, `tests/test_legacy_activation.py` (development only)
- `changelog.d/2026-11-04-legacy-customer-activation.md`

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

## Large upload regression coverage — 2026-11-04

- Extend `tests/test_legacy_activation.py` to verify private attachment ownership/access, rejection of malformed CSV before chunk creation, full-file duplicate handling across chunk boundaries, and native `web_save` plus streamed preview for an 89,438,937-byte / 450,000-row synthetic upload.
- Final isolated suite: 20 tests, zero failures/errors (`/tmp/legacy-upload-memory-final.log`). Existing activation, Arabic browser, toolbar, and permission checks remain passing.
- Actual HTTP upload/preview also passed with the live worker memory limits; no memory-limit increase was needed. This is development-only test code and remains excluded from runtime packages.
