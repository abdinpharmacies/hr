## 62208e4eee55b8296c57d4486547a5886ba47bdf - emadco88 - 2026-10-27

Original commit subject: ab_sales/ FIX price tags

User-facing changes:
- Refresh invoice inventory and price badges through the selected branch API.
- Preserve cashier choices while stock display data refreshes.

Files changed:
- ab_sales/changelog.d/2026-10-27-callcenter-price-badges.md
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/branch_services.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_balance_refresh.js

## Current changes before commit:

- Fix Refresh all rejecting valid E-Plus rows: normalize SQL Server decimal product/store identifiers without truncating fractional values. Validate outside the connector context to preserve clear Odoo errors and safe failure handling.
- Use `ab_sales_inventory` for all-store product cards, search results, availability filters, product details, line totals and popup opening. Automatic search refresh calls only the selected branch API and saves its result.
- Change `btn_update_balance_per_pos()` from branch API fanout to one consolidated, parameterized E-Plus snapshot. Explicitly enable the existing cron every four hours on upgrade.
- Scope informational balances to all `allow_transfer=True` stores, including archived, unregistered and employee-unassigned stores. Exclude missing/nonpositive E-Plus IDs from queries and totals while keeping unavailable rows visible.
- Add balance source and local refresh timestamp metadata, with the existing branch timestamp as fallback. Skip scheduled overwrites younger than one hour; manual refresh bypasses age checks. Reject responses started before a newer cache save, including empty-cache concurrency under PostgreSQL repeatable read.
- Preserve branch API price handling and audit logs; central refresh changes balance metadata only. Successful zero is retained, and only complete successful snapshots clear missing existing rows. Failed/incomplete responses retain balances and timestamps.
- Persist the popup's per-branch API refresh and add Refresh all balances for an explicit E-Plus refresh of the popup product. Keep employee transaction restrictions intact while allowing the authorized fixed cross-branch informational read.
- Add local branch name/code search, source and refresh time, disabled-state explanations and retry handling. Preserve search and cached values on errors; ignore closed/superseded popup responses and prevent overlapping row/all refreshes.
- Keep the default-store scheduled updater branch-only and skip it when no default is set. Read legacy duplicate cache snapshots once per product/store instead of adding duplicate quantities.
- Preserve selected-branch stock/price payloads, numeric response compatibility, invoice submission fallback and draft comparisons. Use module-owned popup components and both Arabic translations.
- Bump `ab_sales` to 19.0.4.1.17, declare the existing connector dependency, and document cache semantics and the bounded E-Plus exception.

Files changed:
- ab_sales/BRANCH_API_WORKFLOW.md
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-27-central-transfer-balances.md
- ab_sales/data/ir_cron.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/ab_product_balance_wizard.py
- ab_sales/models/ab_product_inherit.py
- ab_sales/models/ab_sales_all_store_balance.py
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/models/branch_services.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action_sales_line_balance.xml
- ab_sales/static/src/pos/pos_balance_refresh.js
- ab_sales/static/src/pos/pos_search_product_card.xml
- ab_sales/static/src/pos/store_balance_rows.js
- ab_sales/static/src/pos/store_balance_rows.xml
- ab_sales/views/ab_product_balance_wizard.xml
- ab_sales/views/ab_product_inherit.xml

Validation:
- Targeted `ab_sales` upgrades passed on isolated database `codex_cc_eplus_balance_20261027`; the four-hour cron is enabled there.
- Passed 51 backend checks for cache-only reads, scope/access rules, persisted API/central refreshes, successful zero, failed/incomplete responses, price preservation, one-hour boundaries, response ordering and parameterized source validation.
- Passed 5 independent-transaction concurrency checks: stale writers cannot overwrite empty/existing caches, only one snapshot is retained, and a competing lock is rejected safely.
- Passed 20 Chromium/OWL checks for branch and all-store refresh, failure/retry, zero balances, local English/Arabic/code search, retained search state, unavailable branches and stale-response protection. Inspected the rendered popup screenshot.
- Passed 18 runtime checks for both Arabic catalogs, Arabic field/view translations, selected-branch live refresh and cache persistence, updated aggregate totals, numeric/stock payload compatibility, outage isolation and asset inclusion.
- Exported the Odoo POT before merging translations; both catalogs pass `msgfmt --check-format`. Python/XML/JavaScript syntax and `git diff --check` pass.
- Evidence and executable checks are outside the addon in `/tmp/cc_cache_qa/`. Tests use mocked external responses; the isolated database has no copied attachment filestore, producing non-fatal missing-file messages.
- No production upgrade/restart or external database write was performed. Live E-Plus authentication and response time remain unverified by these implementation tests.

Refresh validation correction (19.0.4.1.17):
- The reported live log points to the all-store E-Plus reader, not the per-branch API. Read-only schema and driver checks confirmed `itm_id` and `sto_id` use `decimal(18,0)` and arrive as Python `Decimal`; the prior strict `int` check rejected them.
- Passed 24 focused checks for Decimal/int compatibility, zero, normalized cache keys, fractional/nonfinite/invalid IDs, foreign product/store rows, duplicate normalized IDs, bad units/quantities and clean Odoo errors outside the connector wrapper.
- Re-ran the 51 cache backend checks successfully and completed a targeted QA upgrade. Existing error translations remain available in both Arabic catalogs; no new user-facing strings were introduced.
- A live read-only query for one product across 235 mapped stores returned 5 groups successfully with normalized identifiers. It called only `_query`, performed no cache write and rolled back the Odoo transaction. This verifies the correction against the real SQL driver without running a bulk synchronization.
- Evidence: `/tmp/cc_refresh_fix_qa/`. The running callcenter service was not restarted or upgraded by the agent; reload the Python service to use the correction.
