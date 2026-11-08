Current changes before commit:

- Remove the local inventory module dependency; keep central stock snapshots and durable branch sale reservations.
- Document central-only stock receipts and adjustments and the branch ledger removal.
- Preserve the pending fractional central snapshot parsing changes.

Files changed:

- ab_branch_sync/__manifest__.py
- ab_branch_sync/models/cache.py
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-08-branch-inventory-removal.md

Recent relevant commit:

- Commit: 38621cf3
- Author: Hossam Elsheikh
- Date: 2026-11-05
- Original subject: feat(ab_branch_sync): sync branch bills with cached stock and a 10-second POS interval
- User-facing change: branch bills use cached stock during outages and synchronize with central.

Files changed:

- ab_branch_sync/AGENTS.md
- ab_branch_sync/README.md
- ab_branch_sync/__init__.py
- ab_branch_sync/__manifest__.py
- ab_branch_sync/changelog.d/2026-11-05-api-key-retry.md
- ab_branch_sync/changelog.d/2026-11-05-enrollment-diagnostics.md
- ab_branch_sync/changelog.d/2026-11-05-inventory-authority.md
- ab_branch_sync/changelog.d/2026-11-05-offline-pos-balance.md
- ab_branch_sync/changelog.d/2026-11-05-optional-service-user.md
- ab_branch_sync/changelog.d/2026-11-05-optional-tls-verification.md
- ab_branch_sync/changelog.d/2026-11-05-pairing-button.md
- ab_branch_sync/changelog.d/2026-11-05-pos-connection.md
- ab_branch_sync/changelog.d/2026-11-05-product-packaging.md
- ab_branch_sync/changelog.d/2026-11-05-product-units-timer.md
- ab_branch_sync/changelog.d/2026-11-05-role-split.md
- ab_branch_sync/data/config.xml
- ab_branch_sync/data/cron.xml
- ab_branch_sync/i18n/ar.po
- ab_branch_sync/i18n/ar_001.po
- ab_branch_sync/models/__init__.py
- ab_branch_sync/models/cache.py
- ab_branch_sync/models/enrollment.py
- ab_branch_sync/models/operation.py
- ab_branch_sync/models/pos.py
- ab_branch_sync/models/product.py
- ab_branch_sync/models/replication.py
- ab_branch_sync/models/sales.py
- ab_branch_sync/security/ir.model.access.csv
- ab_branch_sync/security/record_rules.xml
- ab_branch_sync/security/security_groups.xml
- ab_branch_sync/static/src/pos/central_status.js
- ab_branch_sync/static/src/pos/central_status.scss
- ab_branch_sync/static/src/pos/central_status.xml
- ab_branch_sync/static/src/pos/submission_balance.js
- ab_branch_sync/views/enrollment.xml
- ab_branch_sync/views/operations.xml
- ab_branch_sync/workflow.md
