Current changes before commit:

- Keep branch bills/cashier behavior; expose inventory status and central reference.
- Refresh connected sale stock and fall back on cached stock only for transport outages.
- Add hourly full snapshots, minute retries, atomic cache replacement, omitted-stock clearing, and sparse acknowledgments.
- Hold v2 outgoing operations for explicit pilot review.

Files changed:

- ab_branch_sync/__manifest__.py
- ab_branch_sync/models/operation.py
- ab_branch_sync/models/cache.py
- ab_branch_sync/models/sales.py
- ab_branch_sync/data/cron.xml
- ab_branch_sync/views/enrollment.xml
- ab_branch_sync/i18n/ar.po
- ab_branch_sync/i18n/ar_001.po
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-05-inventory-authority.md

Recent relevant baseline: 7b07927 — hager yasser — 2026-11-04 — feat(ab_central_sync): add store-scoped enrollment and custom CA trust. The branch module remains an uncommitted role split; see its role-split changelog.

Validation: isolated targeted upgrades, actual v3 HTTP authentication/idempotency/scope/dependency checks, central status-only settlement, offline branch approval with unchanged cashier payment, snapshot omission/rollback/sparse acknowledgment checks, and runtime Arabic bill labels. Live service-identity setup and existing-bill recovery were deferred at the user’s request. Live databases were not upgraded in this change; access checks remain enforced.
