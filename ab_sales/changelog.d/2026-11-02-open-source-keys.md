## 0d51857522df582473896d635270a8f1ed3a8b1e

- Author: emadco88 <emadco88@gmail.com>
- Date: 2026-09-30T17:58:52+03:00
- Subject: ab_sales/ FIX view

User-facing changes:

- Updated passive sales reporting views and translations.

Files changed:

- `ab_sales/changelog.d/2026-09-30-pos-reporting-views.md`
- `ab_sales/i18n/ar.po`
- `ab_sales/i18n/ar_001.po`
- `ab_sales/views/sales_mirror_extra_views.xml`
- `ab_sales/views/sales_mirror_views.xml`

## adfce7b511b81521e2c8a6f19b4988610710b836

- Author: hossam elsheikh <hossam.m.elsheikh@gmail.com>
- Date: 2026-11-02T12:41:40+02:00
- Subject: ab_sales: accept new source keys

User-facing changes:

- Store eight source-owned status, reason, rank, and printer fields as open-ended keys.
- Updated the module version.

Files changed:

- `ab_sales/__manifest__.py`
- `ab_sales/models/ab_sales_mirror_models.py`
- `ab_sales/changelog.d/2026-11-02-open-source-keys.md`

## Current changes before commit:

User-facing changes:

- Expose raw status keys in sales and return forms, including keys without ribbons.

Validation:

- Isolated fresh installation and pre-conversion upgrade; exact mirror IDs, source identities, values and existing mapping settings preserved.
- External fixtures and evidence: `/tmp/report_keys_verify/`; no live deployment or source-server writes.

Files changed:

- `ab_sales/views/sales_mirror_views.xml`
- `ab_sales/changelog.d/2026-11-02-open-source-keys.md`
