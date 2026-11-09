# Telegram branch locations — 19.0.1.13.0

Current changes before commit:
- Add company/store branch profiles with stable directory keys, bilingual content, separate public phones/hotline, review state, revisions, archival and configuration history.
- Validate CSV imports before applying inactive profiles; provide the 42-row bilingual storefront comparison file with blank company/store mappings.
- Share the reviewed directory from CRM, OMS, channel orders and Telegram chatter. Preview native locations or separately selected details without altering composer or order drafts.
- Enforce employee/session, assignment, company/store scope, reviewed revisions, server-resolved content and idempotency. Freeze send provenance and audit the actor/employee.
- Keep location sending disabled by default, with coordinated Odoo/gateway rollout.
- Add both Arabic catalogs, targeted security/import/retry tests and browser coverage. See `docs/telegram-branch-location-validation.md` at repository root.

Files changed:
- `__manifest__.py`
- `models/__init__.py`
- `models/branch_location.py`
- `models/workspace.py`
- `security/ir.model.access.csv`
- `security/record_rules.xml`
- `views/branch_location.xml`
- `resources/branch_locations.md`
- `resources/branch_locations_staging.csv`
- `static/src/branch_widget.js`
- `static/src/branch_widget.xml`
- `static/src/composer.js`
- `static/src/composer.xml`
- `static/src/location.scss`
- `static/src/order_dialog.js`
- `static/src/order_dialog.xml`
- `static/src/workspace.js`
- `static/src/workspace.xml`
- `static/tests/composer.test.js`
- `tests/__init__.py`
- `tests/test_branch_browser.py`
- `tests/test_workspace.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-08-telegram-branch-locations.md`
