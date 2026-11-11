## 1d71a1367d4c093091ccaebf4d6d416d9105f697 — emadco88 — 2026-08-11

Original commit subject: ab_sales_channel/ UPDs make field required

User-facing changes:
- Update sales-channel field configuration.

Files changed:
- ab_sales_channel/changelog.d/2026-08-11-sales-channel.md
- ab_sales_channel/i18n/ar.po
- ab_sales_channel/i18n/ar_001.po
- ab_sales_channel/models/ab_sales_channel.py
- ab_sales_channel/models/ab_sales_header.py
- ab_sales_channel/views/ab_sales_header_views.xml

## Current changes before commit:

- Explicitly allow POS sales-channel selection through a module-owned header allowlist extension.

Files changed:
- ab_sales_channel/changelog.d/2026-10-22-pos-field-allowlists.md
- ab_sales_channel/models/__init__.py
- ab_sales_channel/models/ab_sales_pos_api.py
