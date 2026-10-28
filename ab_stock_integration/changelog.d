Current changes before commit:

- Allow the native sales workflow to use explicit branch scope across active companies while preserving normal company checks for every other inventory operation.

Files changed:

- ab_stock_integration/changelog.d
- ab_stock_integration/models/inventory.py
- ab_stock_integration/models/store.py

Previous current changes:

- Add a shared boundary for current cumulative inventory, store company checks, source metadata and explicit sales-to-stock unit mapping.
- Preserve current inventory sums and tax outputs; validate quantities and posting scope before using existing business APIs.
- Invalidate cached branch rules after inventory-store reassignment and serialize adapter stock posting.
- Support exact reference-unit stock conversion and freeze mappings after inventory activity.
- Keep concurrency revisions local without updating replicated branch master timestamps.
- Translate new fields and validation messages in both Arabic catalogs.

Validation: 59 workflow/security checks and 4 concurrency checks passed; fresh installation, targeted upgrades and Arabic runtime labels verified. Live startup repair passed. The subsequent authorized opening-stock cutover posted receipts for stores 29 and 140; 46 live-cycle checks and 4 local-lock concurrency checks passed.

Files changed:

- ab_stock_integration/README.md
- ab_stock_integration/__init__.py
- ab_stock_integration/__manifest__.py
- ab_stock_integration/changelog.d
- ab_stock_integration/i18n/ar.po
- ab_stock_integration/i18n/ar_001.po
- ab_stock_integration/models/__init__.py
- ab_stock_integration/models/inventory.py
- ab_stock_integration/models/product.py
- ab_stock_integration/models/res_users.py
- ab_stock_integration/models/source.py
- ab_stock_integration/models/store.py
- ab_stock_integration/security/ir.model.access.csv
- ab_stock_integration/security/record_rules.xml
- ab_stock_integration/views/integration.xml
