## 1b3b207f4653b6a267ca8bc8dc2641c5df24143f - hager yasser - 2026-10-15 12:31:10 +0300

Original commit subject: ab_sales_contract/FEAT(#21055): Enforce Allowed Customers for Promotions(part2)

- Carry the selected customer into contract POS and draft-preview promotion evaluation.
- Reject stale contract pricing responses after customer changes while retaining saved invoice pricing.

Files changed:

- ab_sales_contract/changelog.d/2026-10-15-promotion-customer-context.md
- ab_sales_contract/models/ab_sales_pos_api_contract.py
- ab_sales_contract/models/ab_sales_ui_api_contract.py
- ab_sales_contract/static/src/pos/pos_action_contract_patch.js

Current changes before commit:

- Keep automatic promotions for invoices that have never had a contract during the open POS action.
- Clear selected/applied promotions and discount totals after successful contract selection or change, then load eligible promotions for manual selection.
- Keep affected invoice IDs in an in-memory set independent of cached promotion data. Removing a contract retains manual-only behavior through recalculation and invoice switching; reopening the POS resets this history.
- Retain an explicitly selected eligible promotion when removing a contract, without choosing a replacement for an unavailable selection.
- Install the module-owned refresh handler after POS setup so either promotion/contract asset order works. Send manual_clear=True for affected invoices and enforce suppression in contract pricing, including removal of implicit fallback selections.
- Preserve disabled-contract eligibility, explicit selections, existing employee clear behavior, pricing formulas, saved invoice rendering, and existing API signatures.
- Invalidate pending pricing on contract and promotion changes; reject stale responses and errors using request counters and complete pricing-input snapshots.

Files changed:

- ab_sales_contract/changelog.d/2026-10-15-pos-manual-promotions.md
- ab_sales_contract/models/ab_sales_pos_api_contract.py
- ab_sales_contract/static/src/pos/pos_action_contract_patch.js

Verification:

- Reviewed git show for b28b327a, 1b3b207f, and 8f14c16f and the current module diff before documenting this change. Existing ownership metadata is untouched.
- Passed 78 isolated JavaScript checks across both asset orders and contract-only assets, covering manual selection, deselection/clear, contract selection/change/removal, invoice switching, cache reload, item/quantity/price/store edits, unavailable/disabled promotions, rapid contract reads, delayed pricing/errors, and locked invoices.
- Passed nine grouped rollback-only Odoo checks with real pricing, sale creation, and draft rendering: both payers, explicit/absent/invalid selections, minimum quantities, existing customer/store eligibility, ordinary automatic behavior, both preview formats, matching sale totals, saved invoice rendering, and store validation. Employee-session validation, inventory reads, and external posting were mocked for the sale-creation checks.
- Passed three additional rollback-only contract API and draft-preview checks without ab_sales_promo installed.
- Upgraded only ab_sales_contract in isolated database codex_promo_customers_20261015; the process exited successfully. Existing missing development-filestore attachment and unrelated module warnings remain.
- Python syntax, JavaScript syntax, and git diff whitespace checks passed. No user-facing strings were added or changed, so both Arabic catalogs remain unchanged.
- Verification scripts and logs remain in /tmp, outside production addon packages. External connections were blocked, fixture changes were rolled back, and no production upgrade or external database writes were performed.
