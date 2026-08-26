Commit: ae2ae4c0c793d2ed09ab34e9406e35bce892d612
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date: 2026-08-26 14:22:07 +0300
Subject: ab_sales/feat: route call-center POS submit to branch Odoo prepending invoice

User-facing changes:
- Routed call-center POS submit to the selected branch Odoo through XML-RPC.
- Created branch-side prepending invoices without pushing to E-Plus.
- Added local call-center RPC submit logs for traceability.

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

Current changes before commit:
- Add an opt-in branch RPC configuration flag to push call-center invoices to E-Plus immediately after remote branch invoice creation.
- Pass the push request through XML-RPC to the branch-side `pos_submit_from_callcenter()` method.
- Use the branch Odoo server's existing `action_push_to_eplus()` implementation so stock-sensitive E-Plus writes still execute in branch context.
- Record whether the call-center RPC attempt requested E-Plus push.
- Add Arabic translations for the new Phase 3 configuration, log field, and push result messages.

Files changed:
- ab_sales/changelog.d/2026-08-26-callcenter-branch-rpc-phase3.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/models/ab_sales_callcenter_rpc_log.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/views/ab_sales_branch_rpc_config_views.xml
- ab_sales/views/ab_sales_callcenter_rpc_log_views.xml
