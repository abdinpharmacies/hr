Current changes before commit:

- Let existing internal sales users use enrolled central inventory without assigning Native Sales Operator or personal Inventory Stores.
- Add automatic record-rule scope only for the intersection of the current replica's stores and the central-authorized store codes, with configured credentials and the connected database UUID. Preserve explicit inventory assignments and existing manager/admin behavior.
- Apply the same scope to bills, lines, returns, stock cache, backend and related native inventory rules. Keep cashier payment ownership, employee session/profile checks, sales prevention, enrollment/readiness and journal-management restrictions.
- Give existing internal sales users access to the return-screen API without an additional inventory role.
- Invalidate evaluated rule domains after replica assignments or connection authorization/scope changes.
- Append three Arabic error translations from an exported Odoo POT in both language catalogs; document the setup and permissions in the workflow.
- Upgrade Branch Synchronization to 19.0.5.1.1 on local abdin_pos and gracefully reload the service on port 4097.

Files changed:

- ab_branch_sync/__manifest__.py
- ab_branch_sync/models/__init__.py
- ab_branch_sync/models/access.py
- ab_branch_sync/models/cache.py
- ab_branch_sync/models/ir_config_parameter.py
- ab_branch_sync/security/ir.model.access.csv
- ab_branch_sync/security/record_rules.xml
- ab_branch_sync/i18n/ar.po
- ab_branch_sync/i18n/ar_001.po
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-16-shared-branch-inventory-access.md

Verification:

- Transactional Odoo checks in `/tmp/test_branch_shared_access.py` passed for a real ordinary sales user without native-inventory membership or inventory-store assignments.
- Verified other-branch denial; stock-cache read and write protection; sale/line/return/backend/cache rule domains; public-user, cashier, employee-session and connection-management guards; administrator access; cashier own-payment/balance scope; replica-reassignment and credential-change invalidation.
- The temporary cashier fixture was loaded through XML and rolled back. No test sale, stock posting, permission assignment or connection change was committed.
- Targeted upgrade exited 0: `/tmp/branch-shared-access-upgrade.log`. Persisted-rule and live-data checks passed afterward; configured but unenrolled stores remain denied and connection authorization/readiness are preserved.
- Both PO catalogs passed `msgfmt --check-format`. Runtime `ar_001` action and cashier-denial text differ from `en_US`.
- Python/XML parsing and `git diff --check` passed. The reloaded branch returned HTTP 200; temporary validation ports were released.
- Existing database warnings remain: duplicate stock-cache rows prevent the pre-existing store/product unique index, and installed `ab_web_error_guard` is absent from the addons path. Both appeared in the earlier Settings upgrade log before this change; no data cleanup was attempted.

Recent relevant commit:

- Commit: d640ec240c3fbee8dd8afa2905ba1454b5b6fbb5
- Author: hager yasser
- Date: 2026-11-11
- Original subject: ab_branch_sync/FEAT: rename central connection parameters to ab_central_branch_connection
- Read the connection and synchronization state from the current parameter namespace.

Files changed:

- ab_branch_sync/README.md
- ab_branch_sync/changelog.d/2026-11-11-connection-parameter-namespace.md
- ab_branch_sync/data/config.xml
- ab_branch_sync/models/enrollment.py
- ab_branch_sync/models/ir_config_parameter.py
- ab_branch_sync/models/operation.py
- ab_branch_sync/models/pos.py
- ab_branch_sync/workflow.md
