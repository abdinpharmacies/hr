## 016a81e6b34a70a2ff382fa06ad076004ced9004 — Alhassan Hossny — 2026-10-18

Original commit subject: ab_sales/Fix: restore POS19 loading and harden inventory refresh

User-facing changes:
- Restore POS loading and retain inventory synchronization metadata in product search.
- Preserve cached balances when live refresh is unavailable.

Files changed:
- ab_sales/changelog.d/2026-10-15-inventory-sync.md
- ab_sales/changelog.d/2026-10-18-pos19-log-repair.md
- ab_sales/models/ab_sales_inventory.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_balance_refresh.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/pos_balance_refresh.js

## Current changes before commit:

- Treat an empty replica Allowed Sales Stores list as unrestricted for otherwise permitted active sales stores, including search timestamp lookup and balance refresh.
- Remove the extra department-assignment rejection from the shared search/refresh store check. Retain Odoo access checks and existing employee-profile and service-user controls.
- Keep configured replica restrictions even when every configured store is disabled; reject inactive or non-sales stores in balance validation and sales constraints.
- Share the sales-store domain with the draft selector. Return authoritative eligible store IDs to the POS and use them in both store selectors, intersecting draft employee permissions as before.
- Surface settings failures instead of silently offering all stores. Ignore defaults outside the eligible list.
- Append missing Arabic translations for the affected existing messages using an Odoo 19 POT export; preserve all existing translations.

Files changed:
- ab_sales/changelog.d/2026-10-18-empty-sales-store-access.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_header.py
- ab_sales/models/ab_sales_pos_balance_refresh.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/static/src/pos/pos_action.js

Validation:
- Read-only local Odoo checks: actual product search as user r, empty and populated replica lists, disabled-only lists, sales validation, API resolution, existing superuser exception, and missing local replica behavior.
- All four replica/employee list combinations verified through the draft selector; service-user restrictions remain effective when both lists are empty.
- Frontend method checks: eligible ID domains, empty eligibility, employee intersection, default fallback, and settings failures.
- Both Arabic catalogs pass msgfmt --check-format; Odoo runtime Python translation lookup resolves the affected messages in ar and ar_001.
- Test harnesses remain outside the addon in /tmp. No remote deployment, module upgrade, external database write, or persisted test data.
