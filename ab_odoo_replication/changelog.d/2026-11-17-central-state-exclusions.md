Current changes before commit:

- Keep ab_central_sync_operation out of master-data imports before registry lookup, remote connection or checkpoint changes, independently of whether Central Synchronization is installed.
- Exclude replica-local central_* fields from ordinary field discovery and explicit extra_fields. This preserves central_last_seen, central_backlog and central_error, including the existing broader prefix protection.
- Keep ordinary replication, model write policies and existing dependencies unchanged; add no dependency on Central Synchronization and increase the module version to 19.0.1.3.2.

Files changed:

- ab_odoo_replication/__manifest__.py
- ab_odoo_replication/models/ab_odoo_replication.py
- ab_odoo_replication/changelog.d/2026-11-17-central-state-exclusions.md

Verification:

- Fresh replication-only installation and 33 existing Odoo tests passed without Central Synchronization installed.
- Standalone runtime checks confirmed Central operation imports stop before remote access and ordinary field discovery remains functional.
- Coexistence checks on a restored Central19 database confirmed normal and explicit extra-field exclusions, preservation of local Central status, unchanged caller options and no mutual uninstall cascade.
- A targeted upgrade of both modules preserved all business data across 270 addon tables and 8,453,942 rows. Only upgrade write_date timestamps changed on two existing replication rules; their configuration and all Central parameters remained unchanged.
- No user-facing source labels or messages changed; both Arabic catalogs remain unchanged. Python syntax and diff whitespace checks passed.
- Verification artifacts are retained in /tmp/central_replication_decouple; no development fixtures or new tests are shipped in the module. The original database and running services were not modified.

Recent relevant commit:

- Commit: 0ade4ddba4cc9b2020dbd7db0868df72f2d15526
- Author: hossam elsheikh
- Date: 2026-11-08
- Original subject: refactor(ab_odoo_replication): exclude retired unit models
- User-facing change: replicate canonical product units and categories instead of retired unit models.

Files changed:

- ab_odoo_replication/changelog.d/2026-11-05-canonical-product-uom.md
- ab_odoo_replication/data/models_to_override.xml
- ab_odoo_replication/models/ab_odoo_replication_run.py
- ab_odoo_replication/tests/test_replication_override.py
- ab_odoo_replication/views/cron_ab_odoo_replication.xml
