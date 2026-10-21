Commit: 4de83ba7e2159bea134478b924ebc070ca924171
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-21T12:32:06+03:00
Subject: ab_sales/refactor: remove cashier security group

User-facing changes:
- Remove the former cashier security group.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-21-remove-callcenter-cashier.md
- ab_sales/security/groups_sales.xml

Current changes before commit:
- Keep draft quantities editable when promotion validation fails; show the allowed and selected quantities once in the promotion panel, without a duplicate message under the quantity input.
- Add an explicit correction mode for branch-confirmed rejected bills, limited to quantities and promotion changes.
- Persist corrections in employee draft slots, including while busy; preserve the prior payload and revision history, and restore it on cancellation.
- Freeze each corrected revision before sending and replay it unchanged after a timeout; preserve ownership, branch, session and concurrent-edit checks.
- Keep the submit controls visible and responsive, and provide matching English and Arabic messages.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-21-rejected-bill-corrections.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/bill_corrections.py
- ab_sales/models/local_bills.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.scss
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/zz_pos_replication_manual.xml
