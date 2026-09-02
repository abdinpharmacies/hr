## Current changes before commit:

User-facing changes:

- Connected branch test source models to `ab_odoo_sync_upload`.
- Moved all test upload-source declarations into the branch-side test module so
  report-side mirror installation does not activate capture behavior.

Files changed:

- `ab_test/__manifest__.py`
- `ab_test/data/sync_upload_sources.xml`
- `ab_test/changelog.d/2026-08-20-customer-reference-force-id.md`
