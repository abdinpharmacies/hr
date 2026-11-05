
Current changes before commit:

- Consume native branch references through the branch API, isolate legacy/native return histories, preserve pending refund status and display synchronization separately from business approval.
- Maintain workflow.md for the split, API ownership, enrollment, transaction lifecycle, recovery and clean-pilot rollout.
- Maintain Arabic catalogs and existing security boundaries.

Files changed:

- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-11-05-role-split.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/models/bill_return_status.py
- ab_sales/models/central_inventory_client.py
- ab_sales/models/local_bills.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/views/local_bill_views.xml
- ab_sales/workflow.md

Recent relevant commit:

- Commit: 2aab20dc02d38b2e854e0a8073f5d701a848ea5f
- Author: emadco88
- Date: 2026-10-30T11:41:24+02:00
- Original subject: ab_sales/ FIX select price logic
- Existing module baseline retained outside the role-split/native adapter changes.

Files changed:

- ab_sales/changelog.d/2026-10-30-submit-branch-price-validation.md
- ab_sales/models/ab_sales_pos_api.py

Validation: fresh isolated central/branch installation; isolated callcenter upgrade; split role registry checks; native API sale/settlement/pending return without local stock movements; HTTP authentication, scope, ordering, duplicate and changed-content checks; callcenter native/legacy identity checks; snapshot watermark/cache-zero regression. Test harnesses are retained under /tmp/split_* and are not shipped in addons. Live databases were not upgraded.
