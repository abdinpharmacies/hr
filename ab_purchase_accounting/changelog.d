Current changes before commit:

- Post financial-only purchase notices without stock movements: debit notices increase inventory/tax value against supplier balance, while financial credit notices reverse value against supplier balance.
- Preserve the existing physical purchase return journal behavior and keep opening inventory excluded from automatic accounting.
- Add the purchase-accounting adapter module with explicit branch/company configuration for receipt and return journal mappings.
- Depend on the purchase opening-balance module while deliberately leaving opening balances out of automatic accounting generation.
- Add the Plan 3 operation flow using the supplier workbook and explicit manual-test accounting setup for the missing live master data.
- Post balanced generated journals for newly saved purchase receipts and purchase returns through the accounting posting contract in the same transaction as inventory posting.
- Add non-purchase receipt offset-account mappings per adapter config and post non-purchase receipt journals from saved `ab_purchase_ob_header` documents.
- Keep opening inventory documents explicitly excluded from automatic accounting journals.
- Link generated journals back to purchase invoices and returns without hooks, migrations, or backfilling already saved documents.
- Expose accounting configuration, non-purchase receipt offset lines, and journal smart buttons with scoped security and both Arabic catalogs.

Files changed:

- ab_purchase_accounting/__init__.py
- ab_purchase_accounting/__manifest__.py
- ab_purchase_accounting/changelog.d
- ab_purchase_accounting/PLAN3_OPERATION_FLOW.md
- ab_purchase_accounting/i18n/ar.po
- ab_purchase_accounting/i18n/ar_001.po
- ab_purchase_accounting/models/__init__.py
- ab_purchase_accounting/models/configuration.py
- ab_purchase_accounting/models/opening_balance.py
- ab_purchase_accounting/models/purchase.py
- ab_purchase_accounting/security/ir.model.access.csv
- ab_purchase_accounting/security/security_rules.xml
- ab_purchase_accounting/views/configuration.xml
- ab_purchase_accounting/views/purchase_views.xml

Validation:

- Latest financial-notice accounting pass: Python AST parsing, XML parsing, manifest parsing, git diff --check, and GNU msgfmt validation passed.
- Live module upgrade was not rerun for this latest pass to avoid interfering with the active PyCharm/Odoo server; restart with the project update command to test in UI.
- Python syntax compile passed for the adapter and the touched purchase manifest.
- XML parsing passed for adapter security and view files.
- Manifest parsing passed for ab_purchase_accounting and ab_purchase.
- git diff --check passed.
- Clean Odoo install/load passed on throwaway database abpa_validation_20260929_1; ab_purchase_accounting loaded as module 40/40.
- Live rip_bconnect upgrade passed; ab_purchase_accounting is installed at version 19.0.1.0.0.
- Rollback-only Plan 3 diagnostic passed for taxed purchase receipt, purchase return, non-purchase receipt, opening-balance exclusion, and missing-config rollback.
- Persistent manual-test data was seeded on rip_bconnect: 158 suppliers, 4 accounts, 2 doctypes, 1 open period, 1 adapter config, 1 receipt type, and 1 receipt offset mapping.
