## ce0201f - emadco88 - 2026-08-03

Original commit subject: ab_sales/ UPD add only_default_sales_uom logic

User-facing changes:
- Added default-sales-UoM handling to POS product search and price display flows.
- Added coverage for POS price badge behavior with default sales UoM products.

Files changed:
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/tests/test_pos_price_badges.py
- ab_sales/views/ab_product_inherit.xml

## e455a15 - hager yasser - 2026-08-30

Original commit subject: ab_sales/FEAT(#2418): Add doctor and item-type filters

User-facing changes:
- Added All, Medicine, and Non-medicine filters to the Bill Wizard without changing fixed 20-record pagination.
- Added the same session-local item-type filter to the POS product search row.
- Applied item-type filtering to Bill Wizard sales/return searches, POS code/name searches, partial barcode fallback, customer recommendations, and balance-filtered product searches.
- Preserved the raw SQL product-search fast path when item type is All.
- Added Arabic translation entries for the new item-type labels.
- Added backend regression tests for item-type filtering.
- Improved the Bill Wizard filter bar wrapping so Search and Reset stay inside the header.
- Added titles to icon-only balance buttons to satisfy Odoo 19 view validation.

Files changed:
- ab_sales/changelog.d/2026-08-30-item-type-filters.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/models/ab_sales_ui_api_bill_wizard_inherit.py
- ab_sales/static/src/bill_wizard/bill_wizard_action.js
- ab_sales/static/src/bill_wizard/bill_wizard_action.scss
- ab_sales/static/src/bill_wizard/bill_wizard_action.xml
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.scss
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/zz_product_search_arabic_keymap_patch.js
- ab_sales/tests/__init__.py
- ab_sales/tests/test_item_type_filters.py
- ab_sales/views/ab_product_inherit.xml
- ab_sales/views/sales_header.xml

## 0a157d1 - hager yasser - 2026-09-08

Original commit subject: ab_sales/FEAT(#19590): Fix Contract Bill Gross Total(part2)

User-facing changes:
- Calculate base bill Total Price from quantity times sell price, independently of discounted line net amounts.
- Refresh totals when line sell prices or net amounts change.
- Preserve the existing Net Amount and product-count calculations.

Files changed:
- ab_sales/models/ab_sales_header.py
- ab_sales/changelog.d/2026-08-30-item-type-filters.md

## 2c8d7db - hager yasser - 2026-09-13

Original commit subject: ab_sales/FEAT(#19780): Add an immediate “Remove All” button to the ab_sales POS sidebar

User-facing changes:
- Added a Remove All control below New Bill in the POS cached-bills sidebar.
- Clear all cached prepending POS bills for the current browser/user/employee cache without creating a replacement bill.
- Reset selected bill state, bill-dependent inputs, customer insight state, product search results, and pending POS refresh timers after bulk removal.
- Persist the empty draft cache to browser storage and the employee-scoped server cache immediately.
- Added Arabic translation entries for the new Remove All label.

Validation:
- JavaScript syntax check passed for the POS action file.
- XML parse check passed for the POS OWL template.
- Arabic PO format checks passed for both language catalogs.
- Whitespace diff check passed for the module changes.

Files changed:
- ab_sales/changelog.d/2026-08-30-item-type-filters.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.scss
- ab_sales/static/src/pos/pos_action.xml

## ff8a1acd7dd3d5cd6e08abaaeb15a9eb097956ba - hager yasser - 2026-10-01

Original commit subject: ab_sales/FEAT(#20447): POS Product Search by Sales Price

User-facing changes:
- Added compact Minimum Price and Maximum Price controls below POS product search. A minimum alone matches the exact rounded price; both inputs match an inclusive range.
- Search only the product master sales price, using two-decimal half-up normalization, validated decimal strings, and indexed price bounds.
- Apply price criteria to name, code, partial barcode, price-only, item-type, balance, current-store balance, and customer-ranked results, including keyboard-language fallback.
- Disable Maximum until Minimum is valid; clear Maximum when Minimum is cleared or invalid, debounce for 200 ms, and reject stale search responses.
- Add an active-product price index through Odoo's declarative index support, with no lifecycle hooks or dependency changes.
- Append Arabic translations for both supported catalogs. Product-card layout, displayed prices, stock, posting, and accounting behavior remain unchanged.

Validation:
- Targeted module upgrade succeeded in isolated database `codex_pos_price_20261001`.
- The combined Sales/Doctor suite ran 51 tests: 50 passed; one existing doctor-creation ACL test also fails against unchanged HEAD in the isolated database. Focused price-search tests and executable frontend checks passed, including keyboard-language and doctor merges.
- Existing regression fixtures use installation context in the standalone test runner to allow fixture creation under replica restrictions; production security is unchanged.
- Odoo backend JavaScript, XML, and CSS assets compile successfully. The shared product-card file is byte-for-byte unchanged.
- Both PO catalogs pass `msgfmt --check-format`; runtime `ar_001` validation messages and the Bills action differ from `en_US`.
- PostgreSQL confirms that the partial index can serve the price candidate query; production-scale latency has not been benchmarked.
- Browser verification is unavailable because no browser surface is connected.
- The doctor-prescription result merge now reuses the same price criteria through the separately authorized ab_sales_doctor integration.

Files changed:
- ab_sales/changelog.d/2026-08-30-item-type-filters.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_product_inherit.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.scss
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/zz_product_search_arabic_keymap_patch.js


## 162e2b984911584da7f2041f535da8f83934e18f - emadco88 - 2026-10-01

Original commit subject: ab_sales/ UPD is_delivery if bill has item starts with 00 like 003 0015 0017

User-facing changes:
- Recalculate the delivery checkbox whenever Before Submit opens: require a selected customer and at least one current sales line whose trimmed product code starts with `00`.
- Preserve leading zeros and treat missing codes or empty bills as nonmatching. Previously saved delivery choices no longer determine the opening default.
- Keep manual checkbox changes effective for the current submission and retain the selected-customer validation for delivery.

Validation:
- Executed 108 combinations of customer selection, saved delivery value, and product code across the base dialog and its delivery-tracking subclass.
- Verified reopening after adding/removing matching items or changing the customer, and manual unchecking for the current submission.
- JavaScript syntax and combined backend asset compilation passed. No new or modified user-facing strings require translation.
- No live bill submission was performed; full browser interaction was not exercised.

Files changed:
- ab_sales/changelog.d/2026-08-30-item-type-filters.md
- ab_sales/static/src/pos/pos_action.js

## d464c5f2436daea9cf993c9b5e5e14ea425730d9 - hager yasser - 2026-10-01

Original commit subject: ab_sales/FIX: Update price placeholders in ab_sales

User-facing changes:
- Change POS price input placeholders to From and To, with Arabic من and إلى in both language catalogs.
- Preserve accessible labels, validation, and exact-price/range search behavior.

Files changed:
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-08-30-item-type-filters.md

## 9976c13d3fcb90a8bebf025fe79f530a376ace5f - emadco88 - 2026-10-01

Original commit subject: Merge team/pos19 into pos19; preserve sales changelog entries

User-facing changes:
- Merge the From/To POS price placeholders and Arabic translations while preserving the customer-and-product-code delivery default.
- Retain the original authors and descriptions of both incoming sales changes.

Files changed:
- ab_sales/changelog.d/2026-08-30-item-type-filters.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/static/src/pos/pos_action.xml


## 84512db554063f558cd311e392cc461763b578e1 - emadco88 - 2026-10-07

Original commit subject: ab_sales/FIX: preserve invoice identity and recover uncertain E-Plus submissions

User-facing changes:
- Add Unknown and Rejected invoice statuses while preserving the original Odoo record, ID, POS token, and branch across retries.
- Save Unknown before contacting E-Plus. Recover an existing branch-scoped invoice serial without replaying invoice lines, delivery updates, or inventory consumption.
- Allow corrected Rejected bills to replace their saved invoice data and submit again on the same identity; never archive a failed bill or clear its token.
- Lock Unknown headers and lines in Python and POS controls, including quantities, prices, customers, promotions, unavailable reasons, barcode additions, and delayed callbacks. Prevent deletion, copying, and branch/token changes for submitted POS identities.
- Serialize attempts across durable commits and detect concurrent line edits before using a stale invoice snapshot.
- Reuse the connector factory for a dedicated transaction connection with automatic statement replay disabled; preserve Unknown when commit or rollback outcomes are uncertain.
- Add Retry and diagnostic messages in POS and backend views. Reconcile cached bills on reload and cross-tab changes; keep unresolved bills when using Remove All.
- Require the updated POS response contract for failed submissions so an older browser cannot mistake an unresolved invoice for success.
- Declare the existing HR model dependency and maintain English source strings with Arabic translations in both catalogs.

Validation:
- Isolated backend scenarios passed for lost commit acknowledgements before and after commit, confirmed rejection with corrected data, offline recovery, failed rollback, ambiguous matches, concurrent retries and line edits, ordinary-user/RPC guards, branch scope, token mismatch, and transaction connection isolation.
- Executable frontend scenarios passed for locked edits, cached-state reconciliation, lost RPC responses, preserved tokens, corrected-data retry, delayed product responses, retained unresolved bills, and correction after a completed local validation error with no saved invoice.
- Both Arabic catalogs pass `msgfmt --check-format`; runtime `ar_001` status labels, Retry button, validation text, and form view differ from English. Combined Odoo backend JavaScript, OWL template assets, and CSS compile successfully.
- Targeted `ab_sales` upgrades passed in isolated database `codex_sales_recovery_20261007`; E-Plus calls were simulated and no production invoice or stock was changed.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-08-30-item-type-filters.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_header.py
- ab_sales/models/ab_sales_line.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_unavailable_reason_required.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/zz_pos_unavailable_reason.xml
- ab_sales/static/src/pos/zz_pos_unavailable_reason_patch.js
- ab_sales/views/sales_header.xml


## Current changes before commit:

User-facing changes:
- Add Unknown/Rejected return states, durable submission tokens, diagnostic messages, and Retry in the return dialog and backend form.
- Recover committed returns using a branch-scoped token in the existing financial note without repeating invoice-line updates, stock refunds, cash adjustments, payments, or replication entries.
- Commit return posting, promotion/contract return-value corrections, and replication entries in one dedicated E-Plus transaction with reconnect/replay disabled.
- Preserve current full/partial return pricing and unit conversions. Keep ab_sales_promo and ab_sales_contract unchanged and use their existing repricing helpers.
- Lock uncertain and saved returns in ORM and UI; preserve attempted returns on close and prevent changing their branch/source identity, copying, or deletion.
- Serialize attempts per branch/source invoice, refresh returnable quantities in the posting transaction, and reject another return while the source invoice has an Unknown return.
- Reopen unresolved returns, reconcile lost RPC responses, and ignore stale state responses, including when the employee-session UI extension is loaded.
- Import the return window's focus listener from OWL so opening Return from the Bill Wizard does not crash component setup.
- Validate recovery-marker note capacity before posting and skip bulk replication replay for returns handled by the atomic workflow.
- Merge new Arabic entries and references into both catalogs while preserving every existing translation.

Validation:
- Isolated Odoo backend scenarios verify lost commit acknowledgements, confirmed/unconfirmed rollback, offline retry, ambiguous/inconsistent recovery, corrected rejection, duplicate retry, branch/source guards, and PostgreSQL submission serialization.
- Actual promotion/contract repricing helpers verify partial/full return posting, copay rules, caps, and both invoice-discount sources with simulated E-Plus calls.
- Frontend scenarios verify immutable uncertain returns, corrected rejection, lost-RPC reconciliation, stale-response protection, and compatibility with the employee-session extension.
- Import-aware checks validate all return component named imports against actual Odoo exports and detect the original invalid focus-hook import.
- Headless Chrome checks with real OWL, real web hooks, return templates, and mocked RPCs verify component mount/render, focus reload, and listener cleanup both with and without the employee-session extension; the browser rejects the original incorrect import.
- Targeted ab_sales upgrades and combined backend asset compilation passed in codex_sales_recovery_20261007. Runtime ar_001 labels, Retry, fields, validation, and form translation were verified; both catalogs pass msgfmt --check-format.
- No live E-Plus posting or production stock/financial changes were performed. Development test harnesses remain outside the runtime addon.

Files changed:
- ab_sales/changelog.d/2026-08-30-item-type-filters.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_header.py
- ab_sales/models/ab_sales_return_header.py
- ab_sales/models/ab_sales_return_header_replication_trans_inherit.py
- ab_sales/models/ab_sales_return_line.py
- ab_sales/models/ab_sales_return_router.py
- ab_sales/models/ab_sales_return_ui_api.py
- ab_sales/static/src/sales_return/ab_sales_return_ui_api.js
- ab_sales/static/src/sales_return/ab_sales_return_ui_api.xml
- ab_sales/views/ab_sales_return.xml
