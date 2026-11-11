
Current changes before commit:

- Keep central enrollment, incoming protocol, native replay, snapshots and audited reconciliation; remove branch sender/cache hooks, settings and cron.
- Maintain workflow.md for the split, API ownership, enrollment, transaction lifecycle, recovery and clean-pilot rollout.
- Maintain Arabic catalogs and existing security boundaries.

Files changed:

- ab_central_sync/AGENTS.md
- ab_central_sync/README.md
- ab_central_sync/__init__.py
- ab_central_sync/__manifest__.py
- ab_central_sync/changelog.d/2026-11-05-cache-and-reconciliation.md
- ab_central_sync/changelog.d/2026-11-05-role-split.md
- ab_central_sync/data/cron.xml
- ab_central_sync/i18n/ar.po
- ab_central_sync/i18n/ar_001.po
- ab_central_sync/models/cache.py
- ab_central_sync/models/enrollment.py
- ab_central_sync/models/operation.py
- ab_central_sync/models/replication.py
- ab_central_sync/models/sales.py
- ab_central_sync/security/ir.model.access.csv
- ab_central_sync/security/record_rules.xml
- ab_central_sync/views/enrollment.xml
- ab_central_sync/views/operations.xml
- ab_central_sync/views/reconciliation.xml
- ab_central_sync/wizard/__init__.py
- ab_central_sync/wizard/sale_reconciliation.py
- ab_central_sync/workflow.md

Recent relevant commit:

- Commit: 235b12bb80903a179533d5efc228d3cb336b30a3
- Author: hager yasser
- Date: 2026-11-04T18:03:14+02:00
- Original subject: feat(ab_central_sync): add store-scoped enrollment and custom CA trust
- Existing module baseline retained outside the role-split/native adapter changes.

Files changed:

- ab_central_sync/README.md
- ab_central_sync/changelog.d/2026-11-04-scoped-pilot.md
- ab_central_sync/controllers/main.py
- ab_central_sync/i18n/ar.po
- ab_central_sync/i18n/ar_001.po
- ab_central_sync/models/cache.py
- ab_central_sync/models/enrollment.py
- ab_central_sync/models/operation.py
- ab_central_sync/models/replication.py
- ab_central_sync/models/sales.py
- ab_central_sync/views/enrollment.xml

Validation: fresh isolated central/branch installation; isolated callcenter upgrade; split role registry checks; native API sale/settlement/pending return without local stock movements; HTTP authentication, scope, ordering, duplicate and changed-content checks; callcenter native/legacy identity checks; snapshot watermark/cache-zero regression. Test harnesses are retained under /tmp/split_* and are not shipped in addons. Live databases were not upgraded.
