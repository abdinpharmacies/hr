# Product units and configurable POS resync

Reference commit: 7b07927c — hager yasser — 2026-11-04
Original subject: feat(ab_central_sync): add store-scoped enrollment and custom CA trust

Current changes before commit:

- Apply ab_product_uom factors directly to new synchronized sales, without legacy packaging or explicit mapping multipliers. New central allocations store the product UoM and leave the historical legacy UoM empty.
- Preserve existing posted bills, allocations, movements, quantities and factors. No stock adjustment or data migration is performed.
- Require a fresh snapshot in the product reference-unit basis before the new branch conversion can sell.
- Run POS connection check and resync through setInterval, default 10 seconds. Read ab_branch_sync.pos_sync_interval_seconds from system parameters; prevent overlapping work, replace changed timers and clean up on scope changes/destruction.
- Keep legacy purchase/receipt paths outside this synchronization change.
- Update workflow and Arabic translations. Verification covers new one-unit deduction/reversal, historical record equality, offline immediate balances, configurable timers, and syntax/translation checks.

Files changed:
- `ab_branch_sync/__manifest__.py`
- `ab_branch_sync/models/product.py`
- `ab_branch_sync/models/cache.py`
- `ab_branch_sync/models/sales.py`
- `ab_branch_sync/models/pos.py`
- `ab_branch_sync/static/src/pos/central_status.js`
- `ab_branch_sync/data/config.xml`
- `ab_branch_sync/i18n/ar.po`
- `ab_branch_sync/i18n/ar_001.po`
- `ab_branch_sync/workflow.md`
- `ab_branch_sync/README.md`
- `ab_branch_sync/changelog.d/2026-11-05-product-units-timer.md`
