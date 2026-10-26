Commit: 7760b63d436c02d9a6adce5fcc141f8ea28bc7c1
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-26T15:02:40+03:00
Subject: ab_sales/send typed metadata and auto-refresh scoped stock balances

User-facing changes:
- Send typed branch metadata and refresh branch-scoped product stock balances automatically.

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

Current changes before commit:
- Automatically restore confirmed editable branch rejections as normal drafts, preserving the contents, correction edits, selected slot and validation feedback.
- Restore normal product, quantity, customer, contract, branch and promotion editing, draft removal and Submit controls without requiring correction mode.
- Preserve failed invoices and RPC history; atomically retire the attempted cache identity and create one replacement token with an audit link.
- Prevent retries of superseded attempts, resolve replacement chains on reload/backup, and preserve revision-conflict, employee-session and branch-access checks.
- Keep unknown, in-progress and accepted submissions protected. Historical rejections require confirmed branch edit permission before recovery.
- Pause draft backup during recovery to avoid racing its revision check.
- Add exported-reference translations in both Arabic catalogs and bump the module version to 19.0.4.1.12.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-26-rejected-draft-recovery.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/local_bills.py
- ab_sales/static/src/pos/pos_action.js

Verification:
- Targeted ab_sales upgrade on callcenter19 passed using isolated ports 5069/5072, no cron workers, and stop-after-init.
- 30 Odoo ORM checks passed, covering editable recovery, repeated rejection, stale backup/retry, retired/accepted successors, revision conflicts, competing submission locks, protected metadata and employee/branch/session isolation. All test records were rolled back; branch network calls were blocked.
- 7 frontend scenarios passed against the actual POS methods, including rejection-to-draft, edited resubmission, historical correction recovery, reload, concurrent recovery, unknown/accepted protection and session changes.
- Both Arabic catalogs passed msgfmt --check-format; field and menu translations differed from English at runtime with ar_001.
- Python/JavaScript syntax and git diff --check passed. No test files were added to the production addon.
- Development checks: /tmp/test_ab_sales_rejected_drafts.py and /tmp/test_ab_sales_recovery_frontend.cjs.

Activation:
- Restart the existing callcenter Odoo process to load the Python changes, then hard-refresh the POS browser. The module upgrade has already been applied to callcenter19.
