Current changes before commit:

- Accept fractional central stock snapshots in the product reference unit.

Files changed:

- ab_branch_sync/changelog.d/2026-11-05-canonical-product-uom.md
- ab_branch_sync/models/cache.py
- ab_branch_sync/workflow.md

commit 38621cf3a576795e6d66a29de401b58d1a4c1e46
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date:   2026-11-05T16:38:22+02:00

    feat(ab_branch_sync): sync branch bills with cached stock and a 10-second POS interval

- feat(ab_branch_sync): sync branch bills with cached stock and a 10-second POS interval.

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
