Current changes before commit:

- Fix Central Synchronization upgrades in XML development mode by adding leading whitespace to the four compact view architectures.
- Preserve view XML IDs, fields, permissions, and translated source strings.

Files changed:

- ab_central_sync/views/enrollment.xml
- ab_central_sync/views/operations.xml
- ab_central_sync/changelog.d/2026-11-04-xml-upgrade.md

Recent relevant commit:

- Commit: 03678bcc
- Author: Hossam Elsheikh
- Date: 2026-11-03
- Original subject: ab_central_sync/feat: add one-time branch pairing and durable central inventory synchronization
- Add branch pairing, synchronization status views, and durable central inventory synchronization.
- Files changed: ab_central_sync/README.md, __manifest__.py, changelog.d/2026-11-03-central-sync-v2.md, controllers/main.py, i18n/ar.po, i18n/ar_001.po, models/__init__.py, models/cache.py, models/enrollment.py, models/operation.py, models/replication.py, models/sales.py, security/record_rules.xml, views/enrollment.xml (all paths within ab_central_sync).
