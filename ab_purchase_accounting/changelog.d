Current changes before commit:

- Depend on the shared stock integration for company ownership and current source snapshots.
- Serialize receipt/return finalization with cashier stock posting while preserving existing purchase and tax calculations.
- Treat the current purchase-notice workflow as physical supplier returns without requiring the removed notice-effect field.
- Document capture-time snapshot semantics; keep existing review/journal configuration behavior.

Validation: 59 workflow/security checks and 4 concurrency checks passed; fresh installation, targeted upgrades and Arabic runtime labels verified. Live startup repair passed without changing stock or document states.

Files changed:

- ab_purchase_accounting/REVIEW_MODE.md
- ab_purchase_accounting/__manifest__.py
- ab_purchase_accounting/changelog.d
- ab_purchase_accounting/models/opening_balance.py
- ab_purchase_accounting/models/purchase.py
- ab_purchase_accounting/models/review.py

# Module changelog

3815a24a | Alhassan Hossny | 2026-10-18 | fix(ab_purchase_accounting): use frozen source values in review snapshots

- Document review-only activation for development branches 29 and 140, including the explicitly approved branch 140 purchase setting and restored replication protection.
- Link the retained isolated pilot examples, 110-check evidence and outstanding business acceptance decisions.
- Use frozen source tax rates and unit factors in later review snapshots; include stable source identity and the explicit expiry choice.
- Preserve review-only processing and existing journal activation settings. No source UI strings changed in this module.

Files changed:
- ab_purchase_accounting/REVIEW_MODE.md
- ab_purchase_accounting/changelog.d
- ab_purchase_accounting/models/review.py

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

6b3a5673 | Alhassan Hossny | 2026-10-18 | ab_purchase_accounting/add: optional review-only accounting mode

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
