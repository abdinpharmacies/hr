Current changes before commit:

- Remove the Branch Synchronization Settings tab, including on module upgrade, while retaining existing connection parameters.
- Add administrator-only Connect to Central and Sync Now buttons above Operations, available without selecting records.
- Reset authorization and stock readiness when connection parameters are created, changed, renamed or deleted directly; preserve the connection for unchanged values and unrelated settings.
- Report connection/synchronization failures and pending outgoing operations without changing replication, stock transport or retry limits.
- Update both Arabic translations and document System Parameters setup and the separate master-data replication connection.
- Fix inline architecture formatting in the inactive replica view so Odoo's XML development-mode file loader can read it during upgrades.

Files changed:

- ab_branch_sync/README.md
- ab_branch_sync/models/__init__.py
- ab_branch_sync/models/enrollment.py
- ab_branch_sync/models/ir_config_parameter.py
- ab_branch_sync/views/enrollment.xml
- ab_branch_sync/views/operations.xml
- ab_branch_sync/i18n/ar.po
- ab_branch_sync/i18n/ar_001.po
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-10-connection-controls.md

Verification:

- Targeted ab_branch_sync upgrade on abdin_replica_branch19: passed.
- Follow-up XML development-mode regression: reproduced the original NoneType/string error with Odoo's file loader, verified all five module views after the formatting fix, and passed a targeted upgrade with --dev=xml. Regression check: /tmp/test_branch_sync_xml_loader.py.
- Ten rollback-only Odoo runtime tests: passed (parameter lifecycle/bulk operations, unchanged values, empty-list actions, administrator access and denied manager/ordinary-user RPC, branch/store rejection, request/snapshot failures, and Arabic view rendering).
- Clean install in a separate empty database, without demo data or ab_odoo_replication: passed; empty-list controls and missing-configuration handling verified.
- Exported Odoo 19 POT before merging translations; both PO files passed msgfmt --check-format. Python/XML syntax and git diff whitespace checks passed.
- Existing branch database logs report unrelated missing addons and model warnings; the clean-install database loads all declared dependencies successfully.
- Development checks remain outside the production addon in /tmp/test_branch_sync_controls.py and /tmp/branch_sync_fresh_checks.py; requests were mocked and test transactions rolled back.

Recent relevant commit:

- Commit: bea50b07bf7ddd48c6dd9d029149d1c4756d566e
- Author: hager yasser
- Date: 2026-11-10
- Original subject: refactor(ab_branch_sync): decouple branch synchronization from replication
- User-facing change: install and run Branch Synchronization independently of the master-data replication engine.

Files changed:

- ab_branch_sync/__manifest__.py
- ab_branch_sync/models/__init__.py
- ab_branch_sync/models/replication.py (removed)
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-10-replication-independence.md
