# Current changes before commit

- Preserve the existing administrator-only cancellation path without requiring an employee POS session.
- Fix outgoing operation identity: keep the generated UUID separate from the employee POS session token.
- Prevent session credentials entering journal payloads and prevent token reuse across operations in one employee session.
- Verified an actual native sale and settlement produce distinct UUIDs, consecutive serials and credential-free JSON in a rollback-only disposable database test.

Files changed:
- `ab_central_sync/controllers/main.py`
- `ab_central_sync/models/operation.py`
- `ab_central_sync/changelog.d/2026-11-03-central-sync.md`

# Commit fea611003da445de99457385e38689a92379cfab

Author: Hossam Elsheikh
Date: 2026-11-03T14:14:27+02:00
Commit: fea611003da445de99457385e38689a92379cfab
Original commit subject: ab_central_sync/Centralize sales and returns

- Add independent central synchronization with the approved JSON operation journal.
- Capture native sale, return, settlement and cancellation events atomically with local completion.
- Deliver after commit, retain offline JSON, and retry every 15 minutes with duplicate-safe acceptance.
- Authenticate origin/store/actor delegation and reuse existing employee permissions and business methods.
- Validate original allocations, costs, quantities, pricing, contract amounts and promotion totals.
- Expose retry, errors, acknowledgments and bounded missing-serial reconciliation to authorized managers.
- Add both Arabic catalogs and documented disabled-by-default configuration.

Validation: clean installation without ab_branch_api; targeted upgrades; authenticated API sale,
settlement, return, refund and cancellation tests; concurrent replay, hash conflict, credential/store
rejection and gap checks; durable offline JSON across process restart; physical stock allocation,
return and reversal checks; contract and promotion pricing replay; PO format checks and runtime Arabic.
All fixtures were isolated in codex_central_sync_20261103. No production database was upgraded.

Files changed:
- `ab_central_sync/README.md`
- `ab_central_sync/__init__.py`
- `ab_central_sync/__manifest__.py`
- `ab_central_sync/controllers/__init__.py`
- `ab_central_sync/controllers/main.py`
- `ab_central_sync/data/cron.xml`
- `ab_central_sync/i18n/ar.po`
- `ab_central_sync/i18n/ar_001.po`
- `ab_central_sync/models/__init__.py`
- `ab_central_sync/models/operation.py`
- `ab_central_sync/models/sales.py`
- `ab_central_sync/security/ir.model.access.csv`
- `ab_central_sync/security/record_rules.xml`
- `ab_central_sync/security/security_groups.xml`
- `ab_central_sync/views/operations.xml`
- `ab_central_sync/changelog.d/2026-11-03-central-sync.md`
