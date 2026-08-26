Commit: eda41b713435810b06c641a6aea64ad1a8468afd
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date: 2026-08-26 14:04:18 +0300
Subject: ab_sales/fix: avoid XML-RPC None response in branch connection test

User-facing changes:
- Fixed the branch RPC connection test for Odoo 19 by avoiding XML-RPC `None` responses.
- Kept the Phase 1 test read-only and unchanged for invoice/E-Plus behavior.
- Updated Arabic translations for the new connection-test error message.

Files changed:
- ab_sales/changelog.d/2026-08-26-callcenter-branch-rpc-phase1.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_branch_rpc_config.py

Current changes before commit:
- Add Phase 2 call-center POS routing so users in `group_call_center` submit the selected store invoice to that store's branch Odoo through XML-RPC instead of creating and pushing locally.
- Add branch-side `pos_submit_from_callcenter()` to create a prepending `ab_sales_header` and `ab_sales_line` rows using synced record IDs, without calling `action_push_to_eplus()`.
- Add local call-center RPC attempt logs for target store, POS token, remote header ID, remote status, remote E-Plus serial, response message, and error message.
- Add a system-only Call-Center RPC Logs menu for traceability.
- Show the remote branch header ID in the call-center POS submit success notification for Phase 2.
- Add Arabic translations for the Phase 2 routing and log UI.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-08-26-callcenter-branch-rpc-phase1.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_callcenter_rpc_log.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/security/ir.model.access.csv
- ab_sales/static/src/pos/pos_action.js
- ab_sales/views/ab_sales_callcenter_rpc_log_views.xml
