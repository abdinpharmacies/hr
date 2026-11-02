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

## d311efdd86c29fa10c70bc43f0018872b5f8a928

- Author: hossam elsheikh <hossam.m.elsheikh@gmail.com>
- Date: 2026-11-02T12:41:40+02:00
- Subject: ab_sales_lead: accept new source keys

User-facing changes:

- Store five source-owned lead fields as open-ended keys.
- Updated the module version.

Files changed:

- `ab_sales_lead/__manifest__.py`
- `ab_sales_lead/models/ab_sales_lead.py`
- `ab_sales_lead/changelog.d/2026-11-02-open-source-keys.md`

## Current changes before commit:

User-facing changes:

- Add the missing unique branch/source identity constraint required for mirror profiles and idempotent application.
- Show state in the form and retain populated reasons for new lead types.
- Add both Arabic catalogs for reporting captions and the new constraint message.

Validation:

- Isolated fresh installation and pre-conversion upgrade; exact mirror IDs, source identities, values and existing mapping settings preserved.
- External fixtures and evidence: `/tmp/report_keys_verify/`; no live deployment or source-server writes.

Files changed:

- `ab_sales_lead/models/ab_sales_lead.py`
- `ab_sales_lead/views/ab_sales_lead_views.xml`
- `ab_sales_lead/i18n/ar.po`
- `ab_sales_lead/i18n/ar_001.po`
- `ab_sales_lead/changelog.d/2026-11-02-open-source-keys.md`
