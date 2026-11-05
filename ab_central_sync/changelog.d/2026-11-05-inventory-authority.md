Current changes before commit:

- Add v3 inventory transport with independent-bill posting and dependent-event retries.
- Preserve agreed sale quantities/totals while letting central select stock batches.
- Mirror cashier status without creating v3 central payment/accounting records.
- Publish sparse snapshot acknowledgments and service-user readiness.

Files changed:

- ab_central_sync/__manifest__.py
- ab_central_sync/models/operation.py
- ab_central_sync/models/sales.py
- ab_central_sync/models/enrollment.py
- ab_central_sync/controllers/main.py
- ab_central_sync/workflow.md
- ab_central_sync/changelog.d/2026-11-05-inventory-authority.md

Recent relevant baseline: 235b12b — hager yasser — 2026-11-04 — feat(ab_central_sync): add store-scoped enrollment and custom CA trust. The branch module remains an uncommitted role split; see its role-split changelog.

Validation: isolated targeted upgrades, actual v3 HTTP authentication/idempotency/scope/dependency checks, central status-only settlement, offline branch approval with unchanged cashier payment, snapshot omission/rollback/sparse acknowledgment checks, and runtime Arabic bill labels. Live service-identity setup and existing-bill recovery were deferred at the user’s request. Live databases were not upgraded in this change; access checks remain enforced.
