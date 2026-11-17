Current changes before commit:

- Align the branch workflow with central's replica sales-store authorization: the shared API user needs Inventory Writer access and compatible companies, without personal Inventory Stores assignments.
- Document the selected-store replay boundary and distinguish posting database serials from originating-branch journal identity.
- Preserve the branch's existing sales/employee rules and initial-snapshot requirement. No additional branch runtime change was needed for the central scope simplification.

Files changed:

- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-16-central-sales-scope-workflow.md

Verification:

- The live connection returned replica 102's stores 29, 140 and 175. POS preparation for store 140 completed the authorized-scope stock download and returned online/ready/synced through normal RPC transaction retry.

Recent relevant commit:

- Commit: d640ec240c3fbee8dd8afa2905ba1454b5b6fbb5
- Author: hager yasser <hageryasser2002@gmail.com>
- Date: 2026-11-11T16:22:26+02:00
- Original subject: ab_branch_sync/FEAT: rename central connection parameters to ab_central_branch_connection
- Use the current shared connection-parameter namespace.

Files changed:

- ab_branch_sync/README.md
- ab_branch_sync/changelog.d/2026-11-11-connection-parameter-namespace.md
- ab_branch_sync/data/config.xml
- ab_branch_sync/models/enrollment.py
- ab_branch_sync/models/ir_config_parameter.py
- ab_branch_sync/models/operation.py
- ab_branch_sync/models/pos.py
- ab_branch_sync/workflow.md
