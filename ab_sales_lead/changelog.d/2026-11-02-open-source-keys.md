## 62098cd085458996eb554621cc44c5b512bb092d

- Author: emadco88 <emadco88@gmail.com>
- Date: 2026-09-30T18:11:45+03:00
- Subject: ab_sales_lead/ FIX

User-facing changes:

- Removed source POS lead behavior from the reporting module.

Files changed:

- `ab_sales_lead/__manifest__.py`
- `ab_sales_lead/models/ab_sales_lead.py`
- `ab_sales_lead/static/src/pos/pos_lead.scss`
- `ab_sales_lead/static/src/pos/pos_lead_patch.js`
- `ab_sales_lead/static/src/pos/pos_lead_templates.xml`
- `ab_sales_lead/views/ab_sales_lead_views.xml`

## Current changes before commit:

User-facing changes:

- Store five source-owned lead fields as open-ended keys.
- Updated the module version.

Files changed:

- `ab_sales_lead/__manifest__.py`
- `ab_sales_lead/models/ab_sales_lead.py`
- `ab_sales_lead/changelog.d/2026-11-02-open-source-keys.md`
