# Product units and configurable POS resync

Reference commit: 235b12bb — hager yasser — 2026-11-04
Original subject: feat(ab_central_sync): add store-scoped enrollment and custom CA trust

Current changes before commit:

- Apply ab_product_uom factors directly to new synchronized sales, without legacy packaging or explicit mapping multipliers. New central allocations store the product UoM and leave the historical legacy UoM empty.
- Preserve existing posted bills, allocations, movements, quantities and factors. No stock adjustment or data migration is performed.
- Require a fresh snapshot in the product reference-unit basis before the new branch conversion can sell.
- Run POS connection check and resync through setInterval, default 10 seconds. Read ab_branch_sync.pos_sync_interval_seconds from system parameters; prevent overlapping work, replace changed timers and clean up on scope changes/destruction.
- Keep legacy purchase/receipt paths outside this synchronization change.
- Update workflow and Arabic translations. Verification covers new one-unit deduction/reversal, historical record equality, offline immediate balances, configurable timers, and syntax/translation checks.

Files changed:
- `ab_central_sync/__manifest__.py`
- `ab_central_sync/models/product.py`
- `ab_central_sync/models/inventory_units.py`
- `ab_central_sync/models/__init__.py`
- `ab_central_sync/models/operation.py`
- `ab_central_sync/i18n/ar.po`
- `ab_central_sync/i18n/ar_001.po`
- `ab_central_sync/workflow.md`
- `ab_central_sync/README.md`
- `ab_central_sync/guide.md`
- `ab_central_sync/changelog.d/2026-11-05-product-units-timer.md`
