
Current changes before commit:

- Add branch-only enrollment, outgoing journal, cached reservations and retry delivery; keep v2 wire compatibility and the initialized-cache zero-stock correction.
- Maintain workflow.md for the split, API ownership, enrollment, transaction lifecycle, recovery and clean-pilot rollout.
- Maintain Arabic catalogs and existing security boundaries.

Files changed:

- ab_branch_sync/AGENTS.md
- ab_branch_sync/README.md
- ab_branch_sync/__init__.py
- ab_branch_sync/__manifest__.py
- ab_branch_sync/changelog.d/2026-11-05-role-split.md
- ab_branch_sync/data/cron.xml
- ab_branch_sync/i18n/ar.po
- ab_branch_sync/i18n/ar_001.po
- ab_branch_sync/models/__init__.py
- ab_branch_sync/models/cache.py
- ab_branch_sync/models/enrollment.py
- ab_branch_sync/models/operation.py
- ab_branch_sync/models/replication.py
- ab_branch_sync/models/sales.py
- ab_branch_sync/security/ir.model.access.csv
- ab_branch_sync/security/record_rules.xml
- ab_branch_sync/security/security_groups.xml
- ab_branch_sync/views/enrollment.xml
- ab_branch_sync/views/operations.xml
- ab_branch_sync/workflow.md

Validation: fresh isolated central/branch installation; isolated callcenter upgrade; split role registry checks; native API sale/settlement/pending return without local stock movements; HTTP authentication, scope, ordering, duplicate and changed-content checks; callcenter native/legacy identity checks; snapshot watermark/cache-zero regression. Test harnesses are retained under /tmp/split_* and are not shipped in addons. Live databases were not upgraded.
