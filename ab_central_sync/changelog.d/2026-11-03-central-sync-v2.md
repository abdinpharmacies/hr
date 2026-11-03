Current changes before commit:

- Transfer this module from the isolated development copy without changing other modules, upgrading databases, restarting services or changing enrollment settings. The required inventory hooks were subsequently transferred into both worktrees; callcenter adapters remain isolated.

- Pair each branch installation once using an expiring code and generated credential; reuse replica identities and store assignments.
- Keep branch stock as validated JSON snapshots plus durable pending reservations; post accepted sales, returns, settlements and reversals on central through existing methods.
- Preserve duplicate protection, serial-gap recovery, actor/store permissions, contract and promotion validation, and 15-minute retries.
- Exclude credentials and installation state from master replication, protect branch cache visibility, and retain actual snapshot timestamps.
- Provide enrollment/status screens and both Arabic catalogs. Existing v1 roles require a coordinated v2 cutover; this module and its required inventory hooks have been copied into branch19 and dev-central19; runtime activation is pending.

Validation: Fresh central installation without Branch API; targeted upgrade; HTTP duplicate/concurrent replay, store scope and serial failures; offline restart; sale/return/cancellation, contract and promotion lifecycles; pairing recovery; cache access and freshness checks.

Files changed:

- ab_central_sync/README.md
- ab_central_sync/__manifest__.py
- ab_central_sync/changelog.d/2026-11-03-central-sync-v2.md
- ab_central_sync/controllers/main.py
- ab_central_sync/i18n/ar.po
- ab_central_sync/i18n/ar_001.po
- ab_central_sync/models/__init__.py
- ab_central_sync/models/cache.py
- ab_central_sync/models/enrollment.py
- ab_central_sync/models/operation.py
- ab_central_sync/models/replication.py
- ab_central_sync/models/sales.py
- ab_central_sync/security/record_rules.xml
- ab_central_sync/views/enrollment.xml

Recent relevant commit:

- Commit: 801dcf4d
- Author: Hossam Elsheikh
- Date: 2026-11-03
- Original subject: ab_central_sync/some fixes
