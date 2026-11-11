Current changes before commit:

- Rename all nine Central–branch connection parameters from `ab_branch_sync.*` to `ab_central_branch_connection.*`: URL, database, API key, authorization, stock readiness, origin, stores, connection status and POS synchronization interval.
- Use the new namespace for requests, enrollment, stock snapshots, recovery status, connection resets and POS polling; retain credential-only invalidation and the existing interval default.
- Document existing-development-installation credential/interval key renaming and reconnection to regenerate internal state; add no migration or legacy fallback.
- Preserve module/model names, routes, XML IDs, sequence codes, database UUIDs, replica serials and master-data replication settings.

Files changed:

- ab_branch_sync/README.md
- ab_branch_sync/data/config.xml
- ab_branch_sync/models/enrollment.py
- ab_branch_sync/models/ir_config_parameter.py
- ab_branch_sync/models/operation.py
- ab_branch_sync/models/pos.py
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-11-connection-parameter-namespace.md

Verification:

- Eight focused checks passed against methods loaded with installed Odoo 19 and mocked database/network services: namespace reads, request headers, credential resets, unchanged values, parameter creation/deletion/renaming, internal-state isolation, snapshot/recovery status and POS interval handling.
- Four existing button RPC tests passed, including administrator denial and connection prerequisites.
- Python syntax, XML parsing, legacy runtime key search and git diff whitespace checks passed.
- Development-only scripts: /tmp/test_central_branch_parameters.py and /tmp/test_branch_sync_button_rpc.py.
- No user-facing source labels or messages changed; both Arabic catalogs remain unchanged.
- No database upgrade, live connection, server restart or database parameter edit performed.
- Matching Central workflow updates are prepared in /tmp/central-branch-connection-docs.patch; the Central checkout is not writable by this session.

Recent relevant commit:

- Commit: 7de282deba0152168f1235803dd0d50690ca6510
- Author: hager yasser
- Date: 2026-11-11
- Original subject: ab_branch_sync/feat: move connection controls to operations and reset authorization when settings change
- User-facing change: manage Central connection from Operations and reset authorization when connection settings change.

Files changed:

- ab_branch_sync/README.md
- ab_branch_sync/changelog.d/2026-11-10-connection-controls.md
- ab_branch_sync/changelog.d/2026-11-11-button-rpc.md
- ab_branch_sync/changelog.d/2026-11-11-enrollment-reconciliation.md
- ab_branch_sync/i18n/ar.po
- ab_branch_sync/i18n/ar_001.po
- ab_branch_sync/models/__init__.py
- ab_branch_sync/models/enrollment.py
- ab_branch_sync/models/ir_config_parameter.py
- ab_branch_sync/models/operation.py
- ab_branch_sync/views/enrollment.xml
- ab_branch_sync/views/operations.xml
- ab_branch_sync/workflow.md
