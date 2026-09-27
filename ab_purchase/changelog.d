Current changes before commit:

- Replace Odoo 15 tree view architecture and action modes with Odoo 19 list views.
- Replace removed `attrs` modifiers with Odoo 19 Python-expression modifiers, including compound purchase-line visibility rules.
- Replace legacy `_sql_constraints` with `models.Constraint` declarations for purchase and notice serial uniqueness.
- Replace legacy `name_get` and `_name_search` overrides with computed display names and `_rec_names_search`.
- Replace active direct cursor aliases with `env.cr` and use the Odoo 19 list view type in returned actions.
- Fix frozen-claim write protection so creators cannot edit frozen claims.
- Add a module-scoped OWL purchase overview with pending observed inbound lines, saved invoice counts, and saved inventory receipt-movement counts.
- Scope dashboard reads and invoice shortcuts to the user's assigned stores, while allowing purchase managers and administrators to see all stores.
- Add English dashboard strings and Arabic translations in `ar.po` and `ar_001.po`.
- Move purchase accounting models, views, claim rules, journal-entry helper, and costcenter-based supplier-origin helper to the recoverable repository-level `temp_accounting/ab_purchase/` folder.
- Disable accounting imports, manifest data, the direct `ab_accounting` dependency, accounting groups/ACLs/menus, and active claim/journal-entry fields and view references.
- Keep invoice commercial totals and taxes while removing automatic purchase accounting behavior; no database records were deleted by this source move.
- Submit purchase invoices as pending observed movements, then save receipts into on-hand through a manager-only action using rebuilt `inventory_write()`.
- Post purchase credit/debit notices through signed saved movements only after the linked receipt is saved; remove obsolete pending-source and `pending_main` lookups.
- Protect saved purchase and notice lines from editing, block direct status transitions, and require exact, non-negative stock quantities.
- Remove obsolete notice-line examples of the retired pending-store inventory workflow.
- Call the inventory process service directly from purchase invoices, lines, notices, and notice balance displays instead of inheriting its forwarding mixin.

Files changed:

- ab_purchase/changelog.d
- ab_purchase/__manifest__.py
- ab_purchase/__init__.py
- ab_purchase/i18n/ar.po
- ab_purchase/i18n/ar_001.po
- ab_purchase/models/__init__.py
- ab_purchase/models/ab_product_supplier_origin.py (moved)
- ab_purchase/models/ab_purchase_je_header_delegate_common.py (moved)
- ab_purchase/models/ab_purchase_dashboard.py
- ab_purchase/models/ab_purchase_header.py
- ab_purchase/models/ab_purchase_je_header_delegate_common.py
- ab_purchase/models/ab_purchase_line.py
- ab_purchase/models/ab_purchase_notice_header.py
- ab_purchase/models/ab_purchase_notice_line.py
- ab_purchase/models_accounting/ab_purchase_claim.py
- ab_purchase/models_accounting/ab_purchase_report_wizard.py
- ab_purchase/views/ab_product_supplier_origin.xml
- ab_purchase/views/ab_purchase_header.xml
- ab_purchase/views/ab_purchase_line.xml
- ab_purchase/views/ab_purchase_notice_header.xml
- ab_purchase/views/ab_purchase_notice_line.xml
- ab_purchase/views/ab_product_supplier_origin.xml (moved)
- ab_purchase/views/ab_purchase_dashboard.xml
- ab_purchase/views/menus.xml
- ab_purchase/security/ir.model.access.csv
- ab_purchase/security/security_groups.xml
- ab_purchase/security/record_rules_purchase_claim.xml (moved)
- ab_purchase/models_accounting/ (moved to temp_accounting/ab_purchase/models_accounting/)
- ab_purchase/views_accounting/ (moved to temp_accounting/ab_purchase/views_accounting/)
- ab_purchase/static/src/dashboard/purchase_dashboard.js
- ab_purchase/static/src/dashboard/purchase_dashboard.xml
- ab_purchase/static/src/dashboard/purchase_dashboard.scss
- ab_purchase/views_accounting/ab_accounting_je_inherit.xml
- ab_purchase/views_accounting/ab_purchase_claim.xml
- ab_purchase/views_accounting/ab_purchase_claim_dist_line.xml
- ab_purchase/views_accounting/ab_purchase_claim_line.xml

Validation:

- All module XML files parse successfully.
- All active manifest paths exist; no active Python, XML, CSV, or manifest reference to the disabled purchase accounting models, journal-entry fields, or `ab_accounting` remains.
- New OWL JavaScript parses as an ES module, and the two Arabic dashboard catalogs contain matching, non-duplicate entries.
- Legacy Odoo 15 view/API scans pass for active code; only historical direct-cursor examples remain in comments.
- `git diff --check` passes.
- Python compilation, POT export, `msgfmt`, an Odoo database upgrade, and Arabic runtime checks remain pending because the required Python/Odoo/gettext tools are unavailable in this shell.

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
