# Module changelog

b92d300 | Alhassan Hossny | 2026-09-30 | ab_purchase_accounting/Update: post journals for financial purchase notices

- Financial debit/credit notice posting was added and is retained.

Files changed:
- ab_purchase_accounting/changelog.d
- ab_purchase_accounting/i18n/ar.po
- ab_purchase_accounting/i18n/ar_001.po
- ab_purchase_accounting/models/purchase.py

Current changes before commit:

- Map purchase receipts and notices into first-copy journal/header/line fields.
- Validate supplier/payable, inventory and tax mappings, active dimensions and authorized posting users.
- Preserve source journal linkage and remove dependencies on the replacement accounting schema.
- Update Arabic catalogs and adapter workflow documentation.

Files changed:
- ab_purchase_accounting/PLAN3_OPERATION_FLOW.md
- ab_purchase_accounting/i18n/ar.po
- ab_purchase_accounting/i18n/ar_001.po
- ab_purchase_accounting/models/configuration.py
- ab_purchase_accounting/models/opening_balance.py
- ab_purchase_accounting/models/purchase.py
- ab_purchase_accounting/security/ir.model.access.csv
- ab_purchase_accounting/views/configuration.xml
- ab_purchase_accounting/views/purchase_views.xml
- ab_purchase_accounting/changelog.d
