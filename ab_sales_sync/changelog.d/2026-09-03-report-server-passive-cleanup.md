Recent relevant commit:

- Commit: `46702f47728adfda2916e02cb4e0d5977bef8447`
- Author: emadco88
- Date: 2026-08-26
- Original subject: ab_sales_sync/ UPD connector
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_sales_sync/__manifest__.py
  - ab_sales_sync/changelog.d/2026-08-26-sales-sync-connector.md

Current changes before commit:

- User-facing changes:
  - Updated sync mapping rules so source `create_uid` and `write_uid` can target `ab_users` mirror fields.
- Files changed:
  - ab_sales_sync/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_sales_sync/data/sync_profile_updates.xml
  - ab_sales_sync/data/sync_profiles.xml
