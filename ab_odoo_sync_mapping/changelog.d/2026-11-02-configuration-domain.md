## 23f83917a6d9f094d1913620639ce31044e5c959

- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: 2026-09-14T10:22:23+03:00
- Subject: ab_odoo_sync_mapping: add branch key and hardware-bound upload auth

User-facing changes:

- Changed Report Sync Configuration to open registered branches.

Files changed (configuration action):

- `ab_odoo_sync_mapping/views/configuration_views.xml`

## Current changes before commit:

User-facing changes:

- Clear the obsolete system-parameter filter when updating Report Sync Configuration so existing installations can open registered branches.

Files changed:

- `ab_odoo_sync_mapping/views/configuration_views.xml`
- `ab_odoo_sync_mapping/changelog.d/2026-11-02-configuration-domain.md`

Validation:

- Reproduced the invalid-field error in an isolated reporting database and verified that updating the XML clears it.
- Cleared only the affected action domain in the running reports database through the ORM and verified web_search_read succeeds.
