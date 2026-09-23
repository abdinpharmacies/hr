Current changes before commit:

- Standardize Odoo 19 manifest version, company author, developer, and explicit application/install/auto-install flags; preserve active data-file order and remaining dependencies.
- Remove the web_progress dependency and use ordinary iteration for tax-invoice import and PDF retrieval.
- Preserve the user-supplied untracked addon; this pass modifies only its manifest, tax-invoice iteration, and this changelog.

Files changed:

- ab_taxes/__init__.py
- ab_taxes/__manifest__.py
- ab_taxes/changelog.d
- ab_taxes/data/taxes.xml
- ab_taxes/models/__init__.py
- ab_taxes/models/ab_purchase_tax_invoices.py
- ab_taxes/models/ab_taxes.py
- ab_taxes/security/ir.model.access.csv
- ab_taxes/security/security_groups.xml
- ab_taxes/static/description/icon.png
- ab_taxes/views/ab_taxes.xml
- ab_taxes/views/cron_taxes_supplier_invoices.xml
- ab_taxes/views/purchase_tax_invoices.xml
- ab_taxes/wizard/__init__.py
- ab_taxes/wizard/download_tax_invoices_pdf.py
- ab_taxes/wizard/download_tax_invoices_pdf.xml

Validation:

- Manifest metadata/data-file checks, Python parsing, and remaining dependency resolution passed without database or external-service access.
- AST comparison confirmed that progress-wrapper removal preserves loop bodies and surrounding behavior.
- No new or edited user-facing source strings; existing translation entries were preserved. Installation and UI validation remain pending the separate Odoo 19 port.

Reference history from origin/abdin15 (the current branch has no committed ab_taxes files):

commit 53a8387f7cd325e3339e30d23daa20f1d25b58b8
Author: emadco88 <emadco88@gmail.com>
Date:   2024-05-30T03:22:31+03:00

    ab_taxes/ delete old files

- Remove legacy tax/purchase integration files from the reference branch. This historical change was not applied by this cleanup.

Files changed:

- ab_taxes/models/join_tax_eplus_purchase.py
- ab_taxes/models/pur_trans_h_inherit.py
- ab_taxes/views/cron_taxes_vendor_invoices.xml
- ab_taxes/views/pur_trans_h_inherit.xml
