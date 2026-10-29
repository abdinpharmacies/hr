# Resolve selected callcenter customers by E-Plus serial

Recent relevant commit:
- Commit: `6edf28d4b23732c962190efb021642f9a0d67dc6`
- Author: Hossam Elsheikh
- Date: 2026-10-29
- Original commit subject: ab_branch_api/authorize callcenter source identity and preserve promotion origin
- Added callcenter source identity authorization and preserved promotion origin during submission.

Files changed in that commit:
- ab_branch_api/__manifest__.py
- ab_branch_api/changelog.d/2026-10-29-submission-source-identity.md
- ab_branch_api/i18n/ar.po
- ab_branch_api/i18n/ar_001.po
- ab_branch_api/models/__init__.py
- ab_branch_api/models/branch_api.py
- ab_branch_api/models/guarded_sales.py
- ab_branch_api/models/sale_metadata.py
- ab_branch_api/models/source_identity.py

Current changes before commit:
- Accept existing inactive customer matches for authenticated API E-Plus serial references.
- Select the lowest Odoo record ID when the serial is duplicated, then enforce caller read access without falling back to another duplicate.
- Preserve customer masters, existing missing-customer import validation, invoice snapshots, contract posting, and immutable submission retries.
- Document deployment before callcenter commit `f9aaae6f707e21d813dce02b554c68d3f4b136a7`; bump version to `19.0.5.5.9`.
- No user-facing strings added or changed; existing Arabic translation entries remain intact.

Files changed:
- ab_branch_api/models/customer_sync.py
- ab_branch_api/__manifest__.py
- ab_branch_api/README.md
- ab_branch_api/changelog.d/2026-10-29-callcenter-customer-resolution.md

Validation:
- Targeted `ab_branch_api` upgrade passed in isolated database `codex_pos19_customer_resolution_20261029`, with HTTP and cron disabled.
- 17 Odoo-backed checks passed: active/inactive/duplicate resolution, serial validation, model and record access rejection, unauthorized store rejection, missing-customer import success/failure, unchanged customer masters, legacy reference behavior, and the original inactive `spare653952` case.
- Invoice snapshot and mocked SQL checks confirmed ordinary header/delivery customer serials and contact details; contract header/delivery queries retained their contract account override.
- Retry protocol files are unchanged; no live retry or external invoice posting was performed.
- Scripts and logs are outside the addon at `/tmp/pos19_customer_resolution_validation/`.
- No production deployment, customer correction, migration, or external database write was performed.
