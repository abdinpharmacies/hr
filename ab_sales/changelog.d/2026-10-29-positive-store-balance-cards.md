# Positive Store Balances with POS card styling

Recent relevant commit:
- Commit: `401abf8e1ef361a453bcf637eef4f350e4f16022`
- Author: Alhassan Hossny
- Date: 2026-10-29
- Original commit subject: ab_sales/fix: preserve descending Store Balances opening order
- Established descending opening order and retained branch positions during refresh and search.

Current changes before commit:
- Filter nonpositive aggregate balances in the popup's live SQL query, retaining negative batch offsets and invalid-data detection. Shared inventory refresh queries remain unchanged.
- Exclude zero/missing balances from live and saved fallback payloads; retain latest-snapshot selection before fallback filtering.
- Hide cards refreshed to zero while preserving other cards' opening positions, search, branch counts, and responsive two-column layout.
- Apply popup-scoped POS-style rounded cards, subtle shadows, and teal balance badges.
- Add a positive-balance empty state with Arabic translations for both language codes.

Files changed:
- ab_sales/models/ab_sales_all_store_balance.py
- ab_sales/models/ab_product_balance_wizard.py
- ab_sales/static/src/pos/store_balance_rows.js
- ab_sales/static/src/pos/store_balance_rows.xml
- ab_sales/static/src/pos/store_balance_rows.scss
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-10-29-positive-store-balance-cards.md

Validation:
- Executed the actual query method against a SQLite fixture: aggregate filtering, negative offsets, branch scope, absent stock, unchanged shared query, and invalid-group rejection passed. External SQL Server was not queried by this test.
- Odoo runtime checks with mocked external reads passed for live filtering, saved fallback, wizard payload, and Arabic action translation; transaction rolled back.
- Actual OWL component harness passed filtering, opening/stable refresh order, failed refresh, refresh-to-zero, search, empty state, and ten LTR/RTL viewport checks (320/375/767/768/1024px), including 44px controls. This is an isolated component harness, not an authenticated end-to-end sales flow.
- Targeted ab_sales upgrade, SCSS compilation, and both msgfmt format checks passed.
- Test scripts: /opt/playwright/tasks/callcenter19/positive-balances/
- Screenshots: /opt/playwright/artifacts/callcenter19/positive-balances/
