Current changes before commit:

- Resolve committed merge conflict markers in the manifest so Central Synchronization loads and registers its operation model again.
- Retain version 19.0.5.1.2 and preserve both inventory scope/origin documentation and replication independence documentation.
- No user-facing source strings changed; both Arabic catalogs remain unchanged.

Files changed:

- ab_central_sync/__manifest__.py
- ab_central_sync/README.md
- ab_central_sync/changelog.d/2026-11-17-manifest-conflict-fix.md

Verification:

- Manifest literal parsing, module Python syntax, conflict-marker scan and git diff whitespace checks passed.
- Targeted upgrade of ab_central_sync on abdin_replica_dev_central19 completed successfully on alternate ports with cron disabled.
- Runtime assertions passed for installed module state, operation model registration, list/form view loading and the operation action target.
- Existing unrelated missing-module warnings remain for ab_delivery_requests, ab_test and ab_test_sync.
- Upgrade log: /tmp/central_manifest_fix_upgrade.log. Runtime verification log: /tmp/central_manifest_fix_verify.log.

Recent relevant commit:

- Commit: 9b3d50505e0286b6dab0aaba6ed3495075de74c3
- Author: hager yasser
- Date: 2026-11-17
- Original subject: ab_central_sync/refactor: remove dependency on replication module
- User-facing changes: make replication optional and document independent installation. This commit also introduced the unresolved manifest and README conflict markers repaired here.

Files changed:

- ab_central_sync/README.md
- ab_central_sync/__manifest__.py
- ab_central_sync/changelog.d/2026-11-17-replication-decoupling.md
- ab_central_sync/models/__init__.py
- ab_central_sync/models/replication.py (removed)
- ab_central_sync/workflow.md
