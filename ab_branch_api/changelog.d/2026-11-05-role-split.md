
Current changes before commit:

- Add optional, store-scoped native adapters, separate synchronization status and native return references; preserve cashier refund ownership and reject unsupported local-only customer creation.
- Maintain workflow.md for the split, API ownership, enrollment, transaction lifecycle, recovery and clean-pilot rollout.
- Maintain Arabic catalogs and existing security boundaries.

Files changed:

- ab_branch_api/__manifest__.py
- ab_branch_api/changelog.d/2026-11-05-role-split.md
- ab_branch_api/i18n/ar.po
- ab_branch_api/i18n/ar_001.po
- ab_branch_api/models/__init__.py
- ab_branch_api/models/branch_api.py
- ab_branch_api/models/central_inventory.py
- ab_branch_api/workflow.md

Recent relevant commit:

- Commit: 9d984093e69220072a33325a25f9c7ac7961c6d5
- Author: Hossam Elsheikh
- Date: 2026-10-29T18:50:57+03:00
- Original subject: ab_branch_api/authorize callcenter source identity and preserve promotion origin
- Existing module baseline retained outside the role-split/native adapter changes.

Files changed:

- ab_branch_api/__manifest__.py
- ab_branch_api/changelog.d/2026-10-29-submission-source-identity.md
- ab_branch_api/i18n/ar.po
- ab_branch_api/i18n/ar_001.po
- ab_branch_api/models/__init__.py
- ab_branch_api/models/branch_api.py
- ab_branch_api/models/guarded_sales.py
- ab_branch_api/models/sale_metadata.py
- ab_branch_api/models/source_identity.py

Validation: fresh isolated central/branch installation; isolated callcenter upgrade; split role registry checks; native API sale/settlement/pending return without local stock movements; HTTP authentication, scope, ordering, duplicate and changed-content checks; callcenter native/legacy identity checks; snapshot watermark/cache-zero regression. Test harnesses are retained under /tmp/split_* and are not shipped in addons. Live databases were not upgraded.
