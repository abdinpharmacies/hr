# Custody approval window drafts

## Current changes before commit:

- Allow administrators and Accounting users to open a new approval window with empty dates and enter either date first without a display-name error.
- Preserve the existing date-range label for complete windows and keep both dates required when saving.

Files changed:
- `models/ab_custody_request_config.py`
- `changelog.d/2026-11-18-approval-window-drafts.md`

Validation:
- Targeted `ab_custody_request` upgrade passed on development database `abdin_replica_migrate19(2)` with isolated ports 5069/5072.
- Real ORM checks passed for empty, start-only, end-only, complete, and multi-record display names.
- Administrator New-form and partial-date onchange checks passed in `en_US` and `ar_001`.
- Odoo Form opened with empty dates, rejected an empty save, and saved a complete window; the test transaction was rolled back.
- No translatable text was added or changed; both Arabic translation files remain unchanged.
- Browser rendering was not inspected. The existing development server must reload the Python change before browser retesting; its process was left running.

## 43af8349 — emadco88 — 2026-11-09

Original commit subject: `migrate19 INIT`

- Introduce the custody configuration date-range label through the Odoo 19 display-name API.

Files changed (approval-window display names):
- `models/ab_custody_request_config.py`
