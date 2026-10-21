Commit: 4de83ba7e2159bea134478b924ebc070ca924171
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-21T12:32:06+03:00
Subject: ab_sales/refactor: remove cashier security group

User-facing changes:
- Remove the former cashier security group.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-21-remove-callcenter-cashier.md
- ab_sales/security/groups_sales.xml

Current changes before commit:
- Complete missing Arabic labels and messages using Odoo-exported terms; preserve existing translations and keep ar/ar_001 coverage aligned.
- Translate dynamic screen labels, component properties and notifications at runtime, including interpolated values where applicable.
- Retain the current rejected-bill correction and promotion validation changes; show the promotion warning once as a rounded red tag.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-21-arabic-completion.md
- ab_sales/changelog.d/2026-10-21-rejected-bill-corrections.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/bill_corrections.py
- ab_sales/models/local_bills.py
- ab_sales/static/src/add_products/add_products_action.js
- ab_sales/static/src/add_products/add_products_action.xml
- ab_sales/static/src/add_products/barcode_scan_form.js
- ab_sales/static/src/add_products/barcode_select_dialog.xml
- ab_sales/static/src/bill_wizard/bill_wizard_action.js
- ab_sales/static/src/bill_wizard/bill_wizard_action.xml
- ab_sales/static/src/bill_wizard/print_dialog.js
- ab_sales/static/src/bill_wizard/print_preview.js
- ab_sales/static/src/invoice_exclusions/invoice_exclusion_text_field.js
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.scss
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/pos_barcode_link.xml
- ab_sales/static/src/pos/pos_printer.js
- ab_sales/static/src/pos/pos_printer.xml
- ab_sales/static/src/pos/return_form_buttons.xml
- ab_sales/static/src/pos/zz_pos_replication_manual.xml
- ab_sales/static/src/pos/zz_pos_replication_manual_patch.js
- ab_sales/static/src/pos/zz_pos_settings_extension.xml
- ab_sales/static/src/sales_return/ab_sales_return_ui_api.js
