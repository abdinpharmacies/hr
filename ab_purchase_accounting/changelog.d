# Module changelog

529f47bc | Alhassan Hossny | 2026-10-01 | ab_purchase_accounting: align posting with restored accounting contract

- Align purchase journals with the restored accounting fields and validate mappings and posting access.
- Preserve journal linkage for retries and update Arabic translations and workflow documentation.

Files changed:
- ab_purchase_accounting/PLAN3_OPERATION_FLOW.md
- ab_purchase_accounting/changelog.d
- ab_purchase_accounting/i18n/ar.po
- ab_purchase_accounting/i18n/ar_001.po
- ab_purchase_accounting/models/configuration.py
- ab_purchase_accounting/models/opening_balance.py
- ab_purchase_accounting/models/purchase.py
- ab_purchase_accounting/security/ir.model.access.csv
- ab_purchase_accounting/views/configuration.xml
- ab_purchase_accounting/views/purchase_views.xml

Current changes before commit:

- Add optional Review Logs Only configuration for newly finalized documents; preserve default journal posting.
- Capture immutable invoice snapshots and proposed accounting entries, including missing-mapping issues for manual review.
- Add branch/company-scoped review screens and server-side reviewer permissions.
- Lock finalization to prevent duplicate approval effects and keep capture failures transactional.
- Translate new screens and messages in both Arabic catalogs and document the branch 29/140 pilot.
- Validate in an isolated Odoo database with fresh synthetic receipts and returns; leave the running database unchanged.

Files changed:
- ab_purchase_accounting/PLAN3_OPERATION_FLOW.md
- ab_purchase_accounting/REVIEW_MODE.md
- ab_purchase_accounting/__manifest__.py
- ab_purchase_accounting/changelog.d
- ab_purchase_accounting/i18n/ar.po
- ab_purchase_accounting/i18n/ar_001.po
- ab_purchase_accounting/models/__init__.py
- ab_purchase_accounting/models/configuration.py
- ab_purchase_accounting/models/opening_balance.py
- ab_purchase_accounting/models/purchase.py
- ab_purchase_accounting/models/review.py
- ab_purchase_accounting/security/ir.model.access.csv
- ab_purchase_accounting/security/security_rules.xml
- ab_purchase_accounting/views/configuration.xml
- ab_purchase_accounting/views/review.xml
