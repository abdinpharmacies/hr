Recent relevant commit:

- Commit: `b81cf093417b850f293feb70f1d18db599ee4b24`
- Author: Alhassan Hossny
- Date: 2026-08-25
- Original subject: ab_store: relax master fields for report sync
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_store/changelog.d/2026-08-25-report-server-master-placeholders.md
  - ab_store/models/ab_store.py

Current changes before commit:

- User-facing changes:
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
- Files changed:
  - ab_store/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_store/models/ab_replica_db.py
  - ab_store/models/ab_store_ip.py
