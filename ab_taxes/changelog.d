Current changes before commit:

- Add company-scoped configurable purchase tax policies for discount timing, bonus taxation, capitalization and rounding.
- Calculate deterministic tax components and inventory unit cost; reject invalid prices, quantities, discounts and company policies.
- Keep synthetic tax examples separate from business approval and expose policy configuration in both Arabic catalogs.

Files changed:

- ab_taxes/__manifest__.py
- ab_taxes/changelog.d
- ab_taxes/i18n/ar.po
- ab_taxes/i18n/ar_001.po
- ab_taxes/models/ab_taxes.py
- ab_taxes/security/ir.model.access.csv
- ab_taxes/security/record_rules.xml
- ab_taxes/views/purchase_tax_policy.xml

Validation:

- Fresh isolated installation, targeted upgrades, behavior/security checks, translation validation and operational evidence are recorded in `ab_independence_dev_plans/13_phase_1_6_execution.md`.

commit 337728fee4b7ea0a497d80c0a04f6e0a88d4e061
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date: 2026-09-27T15:59:55+03:00

    ab_taxes/fix: Odoo 19 activation security and list view

Files changed:

- ab_taxes/changelog.d
- ab_taxes/i18n/ar.po
- ab_taxes/i18n/ar_001.po
- ab_taxes/security/security_groups.xml
- ab_taxes/views/ab_taxes.xml

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
