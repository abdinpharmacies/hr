Commit: dcbc2030f8008f05328c8e8483e18e245085e355
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-25T15:56:10+03:00
Original commit subject: ab_sales:enforce callcenter submission field allowlists

User-facing changes:
- Filter editable header and line fields, rebuild session ownership, and retain frozen submission retries.

Files changed:
- ab_sales/changelog.d/2026-10-25-callcenter-pos-field-allowlists.md
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/local_bills.py
- ab_sales/static/src/pos/pos_action.js

Current changes before commit:
- Add server-derived schema version, source database UUID, field types, related models and source ID arrays to new frozen branch requests.
- Preserve native stable references while including Many2many references and final source IDs; reject mutation commands and invalid source records.
- Preserve typed scalar values and encode dates/datetimes as ISO values with UTC datetimes.
- Keep browser metadata out of the generated context and replay existing frozen requests unchanged.
- Allow the POS product-card balance button to open the existing read-only Store Balances dialog while the bill is locked; retain the lock on other card actions.
- Sum product-card and invoice-line totals only across the configured, authorized branches shown in Store Balances; exclude unrelated legacy cache rows without deleting them.
- Refresh displayed totals after closing Store Balances and after selected-branch refreshes; flush pending cache updates before aggregation and ignore obsolete frontend responses.
- Automatically refresh returned search products in batches across all configured, authorized branches and update selected-branch and total balances without opening the popup. Retain unavailable branches' cached quantities, show the existing translated cached-balance warning, and discard obsolete search timers/responses.
- Add a server-only correction extension point after rejection confirmation so a new revision can repair known transport defects without rewriting the original frozen payload.
- Document receiver-first deployment and rejected legacy-bill correction; optional sales-channel installation on branches is unnecessary.
- Add new validation messages in English and both Arabic translation files; bump Sales to 19.0.4.1.11.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-26-technical-branch-metadata.md
- ab_sales/doc/technical_branch_metadata.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/models/bill_corrections.py
- ab_sales/models/branch_services.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/pos_balance_refresh.js
- ab_sales/static/src/pos/pos_search_product_card.xml

Validation:
- 13 sender checks and 29 actual submission-pipeline checks passed, including exact replay of pre-upgrade frozen requests.
- Targeted ab_sales upgrade, Arabic PO format checks and ar_001 runtime translation checks passed on a disposable clone.
- Existing missing replication-override tables were confirmed on the original database and remain outside this change.
- Evidence: /tmp/metadata_qa_20261026/sender-test.log, pipeline-test.log and verification.json. Disposable databases/configurations removed; production unchanged.
- Delivery descriptor follow-up: 29 checks passed on a fresh disposable callcenter clone, including the actual rejected request, unchanged retries, confirmed-rejection repair, audit history and idempotent correction replay. Evidence: /tmp/delivery_metadata_fix_20261026/tests.log.
- Balance-button follow-up: isolated browser verification using the actual OWL product-card template and POS handlers passed for locked balance lookup, blocked non-balance clicks, editable product addition, and keyboard activation without adding a line. Syntax/XML checks passed. Evidence: /tmp/balance_click_qa_20261026/verification.json.
- Balance-button follow-up: targeted ab_sales upgrade and existing ar_001 action translation check passed on a disposable clone; clone/configuration removed and fixture server stopped. No new user-facing strings.
- Balance-scope follow-up: 25 backend checks and 13 frontend checks passed. Product 76200 now totals 17 across the two configured branches while all 62 legacy cache rows remain intact. Covered normal/optimized search, restricted and unconfigured branches, offline fallback, zero balances, refreshed product details, and stale-response protection.
- Balance-scope follow-up: targeted ab_sales upgrade, Python/JavaScript syntax, Arabic PO format checks and ar_001 runtime translation passed on a disposable clone. No new user-facing strings. Evidence: /tmp/balance_scope_qa_20261026/backend-results.json and frontend-results.json.
- Automatic search-refresh follow-up: 18 backend checks and 22 frontend checks passed, including the actual search/scheduled-refresh methods, per-branch request batching, partial/all branch outages, rollback of a failed branch snapshot, restricted scope, zero stock and stale-response handling. Targeted ab_sales upgrade, exported POT/reference merge, Arabic PO format checks, runtime Arabic action translation, and Python/JS/XML syntax passed on a disposable clone. Evidence: /tmp/search_balance_qa_20261026/verification.json.
