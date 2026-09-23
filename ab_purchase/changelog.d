Current changes before commit:

- Standardize Odoo 19 manifest version, company author, developer, and explicit application/install/auto-install flags; preserve active data-file order and remaining dependencies.
- Keep supplier-origin updates, notice journal adjustments, and supplier reporting working without the progress addon.
- Use native Odoo Binary domain helpers for purchase notice sources and supplier claims; keep existing selector field names and filtering intent.
- Compute each notice domain independently and refresh it when invoice sources or entered notice sources change.

Files changed:

- ab_purchase/__manifest__.py
- ab_purchase/changelog.d
- ab_purchase/models/ab_product_supplier_origin.py
- ab_purchase/models/ab_purchase_notice_line.py
- ab_purchase/models_accounting/ab_purchase__notice_inherit.py
- ab_purchase/models_accounting/ab_purchase_claim.py
- ab_purchase/models_accounting/ab_purchase_report_wizard.py

Validation:

- Manifest metadata/data-file checks, Python parsing, and remaining dependency resolution passed without database or external-service access.
- Database-free tests with Odoo 19 fields.Domain passed for multiple notice records, changed source selections, normal/instant-cash claims, and empty supplier results. ORM cache invalidation and UI behavior still require the later runtime port.
- AST comparison confirmed that progress-wrapper removal preserves loop bodies and surrounding behavior.
- No new or edited user-facing source strings; existing translation entries were preserved. Installation and UI validation remain pending the separate Odoo 19 port.

commit 5aa34f6d2e03f9710c018e0fe7b154c8fdaa568a
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T15:55:32+03:00

    ab_purchase/ NEED FIX , STILL ODOO15

- Import the existing Odoo 15 module as a foundation; full Odoo 19 compatibility remains pending.

Files changed:

- ab_purchase/__init__.py
- ab_purchase/__manifest__.py
- ab_purchase/models/__init__.py
- ab_purchase/models/ab_inventory_inherit.py
- ab_purchase/models/ab_product_supplier_origin.py
- ab_purchase/models/ab_purchase_header.py
- ab_purchase/models/ab_purchase_je_header_delegate_common.py
- ab_purchase/models/ab_purchase_line.py
- ab_purchase/models/ab_purchase_notice_header.py
- ab_purchase/models/ab_purchase_notice_line.py
- ab_purchase/models/xxx_ab_purchase_reject_wizard.py
- ab_purchase/models_accounting/__init__.py
- ab_purchase/models_accounting/ab_accounting_je_inherit.py
- ab_purchase/models_accounting/ab_purchase__header_inherit.py
- ab_purchase/models_accounting/ab_purchase__notice_inherit.py
- ab_purchase/models_accounting/ab_purchase_claim.py
- ab_purchase/models_accounting/ab_purchase_claim_dist_line.py
- ab_purchase/models_accounting/ab_purchase_claim_line.py
- ab_purchase/models_accounting/ab_purchase_je_line_data.py
- ab_purchase/models_accounting/ab_purchase_report_wizard.py
- ab_purchase/models_accounting/ab_supplier_inherit.py
- ab_purchase/models_accounting/export_xlsx.py
- ab_purchase/security/ir.model.access.csv
- ab_purchase/security/record_rules_purchase_claim.xml
- ab_purchase/security/record_rules_purchase_header.xml
- ab_purchase/security/record_rules_purchase_notice_header.xml
- ab_purchase/security/security_groups.xml
- ab_purchase/static/description/icon.png
- ab_purchase/views/ab_product_supplier_origin.xml
- ab_purchase/views/ab_purchase_header.xml
- ab_purchase/views/ab_purchase_line.xml
- ab_purchase/views/ab_purchase_notice_header.xml
- ab_purchase/views/ab_purchase_notice_line.xml
- ab_purchase/views/menus.xml
- ab_purchase/views_accounting/ab_accounting_je_inherit.xml
- ab_purchase/views_accounting/ab_purchase_claim.xml
- ab_purchase/views_accounting/ab_purchase_claim_dist_line.xml
- ab_purchase/views_accounting/ab_purchase_claim_line.xml
- ab_purchase/views_accounting/ab_purchase_report_wizard.xml
- ab_purchase/views_accounting/ab_supplier_inherit.xml
- ab_purchase/views_accounting/pdf_supplier_balances.xml
- ab_purchase/views_accounting/templates_balance_dist.xml
- ab_purchase/views_accounting/xlsx_supplier_balances.xml
