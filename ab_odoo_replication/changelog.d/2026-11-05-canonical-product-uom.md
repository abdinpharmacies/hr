Current changes before commit:

- Replicate canonical product unit categories and units and remove old override records.

Files changed:

- ab_odoo_replication/changelog.d/2026-11-05-canonical-product-uom.md
- ab_odoo_replication/data/models_to_override.xml
- ab_odoo_replication/models/ab_odoo_replication_run.py
- ab_odoo_replication/tests/test_replication_override.py
- ab_odoo_replication/views/cron_ab_odoo_replication.xml

commit cfa7bb706c230af6ee87e5f6f3ec253b605c621a
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-26T19:11:26+03:00

    ab_odoo_replication/ FIX many2many flush

- ab_odoo_replication/ FIX many2many flush.

Files changed:

- ab_odoo_replication/changelog.d/2026-09-03-report-server-passive-cleanup.md
- ab_odoo_replication/models/ab_odoo_replication.py
