Commit: 0f4423a56a50ba48ea623cf33876e8b5cd13e3b3
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date: 2026-08-26 15:02:29 +0300
Subject: ab_sales/What changed:

User-facing changes:
- Added the Phase 3 option to push call-center branch invoices to E-Plus immediately after remote invoice creation.
- Recorded whether each call-center RPC submit requested the E-Plus push.

Files changed:
- ab_sales/changelog.d/2026-08-26-callcenter-branch-rpc-phase3.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/models/ab_sales_callcenter_rpc_log.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/views/ab_sales_branch_rpc_config_views.xml
- ab_sales/views/ab_sales_callcenter_rpc_log_views.xml

Current changes before commit:
- Make E-Plus detail insertion idempotent when retrying a push that already reused an existing `sales_trans_h` header.
- Skip duplicate `sales_trans_d` inserts and `Item_Class_Store` stock writes when the reused E-Plus invoice already has detail rows.
- Keep the existing B-Connect total guard active so partial or mismatched existing details still block the push.
- Preserve call-center branch invoice tokens after E-Plus push errors so the next call-center retry can reuse the same branch invoice.
- Wrap POS-created header creation in a savepoint so failed creates do not poison the transaction before duplicate-token recovery.
- Add Arabic translations for the reused E-Plus invoice success message.

Files changed:
- ab_sales/changelog.d/2026-08-26-eplus-detail-idempotency.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_header.py
- ab_sales/models/ab_sales_pos_api.py
