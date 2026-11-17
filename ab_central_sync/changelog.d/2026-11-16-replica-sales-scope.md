Current changes before commit:

- Use the replica's Allowed Sales Stores as the sole transport store assignment, filtered to active sale-enabled stores in the API user's companies. Keep API-key validation and the active Inventory Writer role; stop requiring personal Inventory Stores assignments for transport.
- Restrict authenticated replay to its selected store through the inventory helper, sales rules and record rules. The API user remains the ORM actor; no users, groups or permanent store assignments are modified during replay.
- Isolate record-rule caches with the server-owned replay store; client RPC context cannot enable replay scope. Recheck current replica membership before using cached domains, including for administrator API users.
- Use the originating replica's selected store for central sale validation and retain the existing stock, pricing, totals, employee and return business methods. Always clear trusted replay state even when replay-session cleanup fails.
- Add both Arabic translations for new messages, update the central/branch workflow documentation, and bump central to 19.0.5.1.1.

Files changed:

- ab_central_sync/README.md
- ab_central_sync/__manifest__.py
- ab_central_sync/controllers/main.py
- ab_central_sync/models/__init__.py
- ab_central_sync/models/access.py
- ab_central_sync/models/cache.py
- ab_central_sync/models/enrollment.py
- ab_central_sync/models/sales.py
- ab_central_sync/security/record_rules.xml
- ab_central_sync/i18n/ar.po
- ab_central_sync/i18n/ar_001.po
- ab_central_sync/workflow.md
- ab_central_sync/changelog.d/2026-11-16-replica-sales-scope.md

Verification:

- Transactional checks in /tmp/test_central_replica_scope.py passed using a non-admin Inventory Writer with no personal inventory stores: complete sale posting and protocol-3 settlement, normal UI denial, selected-store isolation, administrator transport isolation, forged RPC-context denial, cache isolation across stores, assignment revocation, invalid totals, invalid credentials, inactive user and company restrictions. All test users, operations, bills, movements and configuration changes rolled back.
- Exported the Odoo module POT before updating translations; both msgfmt --check-format checks and Python/XML parsing passed. Targeted ab_central_sync upgrade exited 0, followed by a graceful central reload.
- Runtime version 19.0.5.1.1, Arabic action text and the new Arabic Python error were verified.
- Live connection returned stores 29, 140 and 175 for replica 102 despite the API user's personal stores remaining 29 and 141. The branch POS preparation RPC for store 140 completed its full authorized-scope snapshot and returned online/ready/synced. The initial shell-only attempt hit a concurrent update; the normal Odoo RPC transaction-retry wrapper completed successfully.
- No new sales were committed by the validation. Live stock-cache initialization used the existing authenticated snapshot workflow. Existing historical journal failures and unrelated database warnings were not modified.

Recent relevant commit:

- Commit: ff8b0da3729e30690addf06a3b1c2c3ada2af19f
- Author: hager yasser <hageryasser2002@gmail.com>
- Date: 2026-11-10T16:31:11+02:00
- Original subject: docs(ab_central_sync): document inventory workflow
- Document the central inventory workflow and branch replication independence.

Files changed:

- ab_central_sync/changelog.d/2026-11-10-branch-replication-independence.md
- ab_central_sync/changelog.d/2026-11-10-inventory-workflow-and-uom-proposal.md
- ab_central_sync/workflow.md
