Current changes before commit:

- Add an Odoo 19 security privilege for purchase and move purchase groups from the removed `category_id` field to `privilege_id`.
- Declare the explicit `_inherits` mapping for the delegated `source_id` product-source field so purchase lines load under Odoo 19 while preserving existing source-field behavior.
- Add required Odoo module comments to both Arabic PO files and translate the existing Abdin Purchase security label.
- Preserve the Odoo-only purchase/inventory flow from the plan; this fix does not restore accounting or B-Connect behavior.

Files changed:

- ab_purchase/changelog.d
- ab_purchase/i18n/ar.po
- ab_purchase/i18n/ar_001.po
- ab_purchase/models/ab_purchase_line.py
- ab_purchase/security/security_groups.xml

Validation:

- `python3 -m py_compile ab_purchase/models/ab_purchase_line.py` passed.
- `msgfmt --check-format` passed for `ab_purchase/i18n/ar.po` and `ab_purchase/i18n/ar_001.po`.
- `git diff --check -- ab_taxes ab_inventory ab_purchase` passed.
- Targeted Odoo 19 activation passed with `-i ab_purchase --without-demo --stop-after-init --no-http`.
- Targeted Odoo 19 upgrade passed with `-u ab_taxes,ab_inventory,ab_purchase --without-demo --stop-after-init --no-http`.

commit 2489552473da4af55f186744537a0b2210ed3b4a
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T16:34:39+03:00

    ab_purchase/ FIX manifest and replace legacy progress and domain helpers

- Standardize the Odoo 19 manifest metadata and dependency declarations.
- Replace legacy progress and domain helpers while preserving purchase and claim behavior.

Files changed:

- ab_purchase/__manifest__.py
- ab_purchase/changelog.d
- ab_purchase/models/ab_product_supplier_origin.py
- ab_purchase/models/ab_purchase_notice_line.py
- ab_purchase/models_accounting/ab_purchase__notice_inherit.py
- ab_purchase/models_accounting/ab_purchase_claim.py
- ab_purchase/models_accounting/ab_purchase_report_wizard.py

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
