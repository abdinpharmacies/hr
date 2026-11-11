Current changes before commit:

- Document that branch native sales use central snapshots without a local inventory ledger.
- Keep central sale allocations in canonical product reference units.

Files changed:

- ab_central_sync/models/inventory_units.py
- ab_central_sync/workflow.md
- ab_central_sync/changelog.d/2026-11-05-canonical-product-uom.md
- ab_central_sync/changelog.d/2026-11-08-branch-ledger-removal.md

Recent relevant commit:

- Commit: 71560c29
- Author: Hossam Elsheikh
- Date: 2026-11-05
- Original subject: feat(ab_central_sync): authenticate inventory sync with user API keys and post product-UoM stock
- User-facing change: central accepts branch inventory requests through an Inventory Writer API key.

Files changed:

- ab_central_sync/AGENTS.md
- ab_central_sync/README.md
- ab_central_sync/__init__.py
- ab_central_sync/__manifest__.py
- ab_central_sync/changelog.d/2026-11-05-api-key-retry.md
- ab_central_sync/changelog.d/2026-11-05-cache-and-reconciliation.md
- ab_central_sync/changelog.d/2026-11-05-enrollment-diagnostics.md
- ab_central_sync/changelog.d/2026-11-05-inventory-authority.md
- ab_central_sync/changelog.d/2026-11-05-offline-pos-balance.md
- ab_central_sync/changelog.d/2026-11-05-optional-service-user.md
- ab_central_sync/changelog.d/2026-11-05-pairing-button.md
- ab_central_sync/changelog.d/2026-11-05-pos-connection.md
- ab_central_sync/changelog.d/2026-11-05-product-packaging.md
- ab_central_sync/changelog.d/2026-11-05-product-units-timer.md
- ab_central_sync/changelog.d/2026-11-05-role-split.md
- ab_central_sync/controllers/main.py
- ab_central_sync/data/cron.xml
- ab_central_sync/guide.md
- ab_central_sync/i18n/ar.po
- ab_central_sync/i18n/ar_001.po
- ab_central_sync/models/__init__.py
- ab_central_sync/models/cache.py
- ab_central_sync/models/enrollment.py
- ab_central_sync/models/inventory_units.py
- ab_central_sync/models/operation.py
- ab_central_sync/models/product.py
- ab_central_sync/models/replication.py
- ab_central_sync/models/sales.py
- ab_central_sync/security/ir.model.access.csv
- ab_central_sync/security/record_rules.xml
- ab_central_sync/security/security_groups.xml
- ab_central_sync/views/enrollment.xml
- ab_central_sync/views/operations.xml
- ab_central_sync/views/reconciliation.xml
- ab_central_sync/wizard/__init__.py
- ab_central_sync/wizard/sale_reconciliation.py
- ab_central_sync/workflow.md
