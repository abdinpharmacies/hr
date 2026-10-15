## b84b51e96616b2b6f20482e207fdbf78686e41ba - emadco88 - 2026-10-14

Original commit subject: ab_sales/ FIX preserve balances on refresh failure and add per-product retry controls

User-facing changes:
- Retain cached branch balances after failed refreshes and offer per-product retry buttons.

Files changed:
- ab_sales/changelog.d/2026-10-14-balance-refresh.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_pos_balance_refresh.py
- ab_sales/static/src/add_products/add_products_action.js
- ab_sales/static/src/add_products/add_products_action.xml
- ab_sales/static/src/add_products/product_card.xml
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/pos_action_sales_line_balance.xml
- ab_sales/static/src/pos/pos_balance_refresh.js

## Current changes before commit:

- Timestamp successful branch reads and reject older/equal snapshots, including their prices; advance timestamps even when quantities are unchanged.
- Share validated, atomic cache updates between both branch crons and POS; zero only eligible records within the completed query scope. Missing configuration and failed reads preserve cached data.
- Lock branches and inventory rows after external reads, recheck timestamps, bound creation contention, and enforce one inventory row per branch/product. Serialization conflicts roll back safely.
- Include selected-branch timestamps in search/barcode responses and offer optional refresh metadata while retaining the numeric response for existing callers.
- Display a frozen English/Arabic age before failed POS search-card balances; recalculate on manual failure and clear on recovery. Keep invoice lines and Add Products unchanged.
- Clear branch-specific search state and discard obsolete refresh responses.
- Preserve the original ProductCard call used by Sales Lead XPath extensions; enable age labels through a POS-only flag so Lead&Report and Doctor card extensions remain compatible.

Files changed:
- ab_sales/changelog.d/2026-10-15-inventory-sync-timestamps.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_inventory.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_balance_refresh.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/pos_balance_refresh.js
- ab_sales/static/src/pos/pos_search_product_card.xml

Verification:
- Clean installation and targeted ab_sales upgrade passed in isolated database codex_sales_sync_clean_oct15; verified the database uniqueness constraint.
- 13 ORM tests passed, including real concurrent transactions, competing creation, bounded unique-index waits, serialization rollback, branch isolation, malformed/suppressed read failures, empty snapshots, retained prices, search/barcode timestamps, and numeric API compatibility.
- JavaScript harness passed unit boundaries, missing/future timestamps, frozen labels, manual retries, cached failure responses, recovery, stale responses, branch/product changes, and legacy callers.
- Exported Odoo POT references; both PO catalogs pass msgfmt --check-format. Runtime ar_001 field/menu translations and JavaScript age translations verified. Backend XML and JavaScript asset bundles built successfully.
- External development harnesses: /tmp/test_inventory_sync.py, /tmp/test_balance_age.mjs, /tmp/check_sync_runtime.py. No harnesses added to the runtime addon.

Upgrade blockers:
- Read-only preflight found 2,510 duplicate branch/product groups in each of abdin_pos and abdin_old_pos19. Neither database was upgraded; no duplicates were merged or deleted. Reports: /tmp/abdin_pos_inventory_duplicates.json and /tmp/abdin_old_pos19_inventory_duplicates.json. Resolve duplicates explicitly and repeat preflight before upgrading either database.
- An older isolated clone could not upgrade because an existing inherited return view references a missing active field; clean installation and subsequent targeted upgrade passed without altering that view.
- Visual browser verification remains pending: this session exposes no browser.

POS opening regression verification:
- Reproduced the missing ProductCard XPath using the previous renamed call.
- Applied all four Sales Lead hooks, the age-label extension, and the Doctor card extension successfully with Odoo inheritance processing. Verified the lead button remains and only POS search supplies the age-label flag. Harness: /tmp/check_pos_card_inheritance.py.
