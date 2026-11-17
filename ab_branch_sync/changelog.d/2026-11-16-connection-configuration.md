Current changes before commit:

- Document diagnosis and the requested local connection-parameter correction on `abdin_pos`.
- Initial values used the obsolete `ab_branch_sync.*` namespace. Database and API-key parameters were renamed externally during diagnosis; add the remaining `ab_central_branch_connection.url` with `http://127.0.0.1:5031`.
- Verify the current transport reads all three parameters, with database `central` and an API key present. Do not log the key.
- Preserve the module's automatic authorization/readiness reset after the URL change. No connection, sale, inventory push, replica change, or access grant was performed.
- Read-only central checks found no replica with serial 120, including archived records. The checked API user has inventory scope for store 29 only; store 141 has sales disabled on central.
- No runtime code or user-facing strings changed; existing English sources and both Arabic catalogs are unchanged.

Files changed:

- ab_branch_sync/changelog.d/2026-11-16-connection-configuration.md

Recent relevant commit:

- Commit: d640ec240c3fbee8dd8afa2905ba1454b5b6fbb5
- Author: hager yasser
- Date: 2026-11-11
- Original subject: ab_branch_sync/FEAT: rename central connection parameters to ab_central_branch_connection
- Read connection settings and synchronization status from the new parameter namespace.

Files changed:

- ab_branch_sync/README.md
- ab_branch_sync/changelog.d/2026-11-11-connection-parameter-namespace.md
- ab_branch_sync/data/config.xml
- ab_branch_sync/models/enrollment.py
- ab_branch_sync/models/ir_config_parameter.py
- ab_branch_sync/models/operation.py
- ab_branch_sync/models/pos.py
- ab_branch_sync/workflow.md
