Recent relevant commit:

- Commit: `1d71a1367d4c093091ccaebf4d6d416d9105f697`
- Author: emadco88
- Date: 2026-08-11
- Original subject: ab_sales_channel/ UPDs make field required
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_sales_channel/changelog.d/2026-08-11-sales-channel.md
  - ab_sales_channel/i18n/ar.po
  - ab_sales_channel/i18n/ar_001.po
  - ab_sales_channel/models/ab_sales_channel.py
  - ab_sales_channel/models/ab_sales_header.py
  - ab_sales_channel/views/ab_sales_header_views.xml

Current changes before commit:

- User-facing changes:
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
- Files changed:
  - ab_sales_channel/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_sales_channel/models/ab_sales_channel.py
