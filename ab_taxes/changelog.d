Current changes before commit:

- Add an Odoo 19 security privilege for taxes and move tax groups from the removed `category_id` field to `privilege_id`.
- Convert the active tax list view and action from legacy `tree` to Odoo 19 `list`.
- Add minimal Arabic catalogs for the active tax labels touched in this activation fix.
- Keep the inactive government tax-invoice screens untouched; the active tax setup still avoids requiring the tax-invoice service during purchase or inventory activation.

Files changed:

- ab_taxes/changelog.d
- ab_taxes/i18n/ar.po
- ab_taxes/i18n/ar_001.po
- ab_taxes/security/security_groups.xml
- ab_taxes/views/ab_taxes.xml

Validation:

- XML parsing passed for the edited security and view files.
- `msgfmt --check-format` passed for `ab_taxes/i18n/ar.po` and `ab_taxes/i18n/ar_001.po`.
- `git diff --check -- ab_taxes ab_inventory ab_purchase` passed.
- Targeted Odoo 19 activation/upgrade passed with `-u ab_taxes,ab_inventory,ab_purchase --without-demo --stop-after-init --no-http`.

commit e2bca1f
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23

    ab_taxes/ ADD legacy module with updated manifest and no web_progress dependency

- Add the legacy taxes module with an Odoo 19 manifest, security, tax data, tax configuration views, and purchase-tax invoice helpers.
- Remove the legacy `web_progress` dependency while preserving tax-invoice iteration behavior.

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
