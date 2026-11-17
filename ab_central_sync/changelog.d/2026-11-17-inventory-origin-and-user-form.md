Current changes before commit:

- Attribute new synchronized inventory movements to the authenticated originating replica db_serial instead of central's configured serial. Validate the replay actor and selected store before assigning it.
- Keep direct central movements on the local configured serial. Ignore supplied serial values and spoofed RPC context; retain the existing serial immutability guard and leave historical movements unchanged.
- Document UI-only removal of the Inventory Stores user-form section and update the shared branch workflow. Permission rules, personal assignment data, cashier and cash-shift behavior remain unchanged.
- Bump to 19.0.5.1.2 and update both Arabic source references for the reused access-error message after exporting the module POT.

Files changed:

- ab_central_sync/README.md
- ab_central_sync/__manifest__.py
- ab_central_sync/models/__init__.py
- ab_central_sync/models/inventory_origin.py
- ab_central_sync/i18n/ar.po
- ab_central_sync/i18n/ar_001.po
- ab_central_sync/workflow.md
- ab_central_sync/changelog.d/2026-11-17-inventory-origin-and-user-form.md

Verification:

- /tmp/test_central_inventory_origin.py passed: a complete native sale replay for replica 112 produced stock movements with db_serial 112; ordinary central movement batches retained local config serial 102. Fake client serials/context were ignored, serial changes and cross-store posting were denied, and the user-form selector was absent.
- Existing ordinary-user denial, replay cache isolation, admin transport restrictions, protocol-3 settlement, invalid totals/credentials, inactive users, company restrictions and replica revocation checks passed. All temporary users, transactions, ledger movements and test metadata rolled back.
- /tmp/test-branch-inventory-field-hidden.log confirms branch UI removal with every record-rule domain unchanged. Arabic format, Python/XML parsing and diff whitespace checks passed.
- Changes are confined to local worktrees as requested. No runtime module upgrade, service restart, remote deployment or historical data correction was performed. On deployment upgrade ab_inventory and ab_central_sync centrally, and ab_sales_inventory on the branch.

Recent relevant commit:

Commit: 5575088e5a901550fb964d5b5f8df672c717557c
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-11-17T09:26:25+02:00
Original subject: improve central-branch connection config

- Previous module change: improve central-branch connection config.

Files changed:

- ab_central_sync/README.md
- ab_central_sync/__manifest__.py
- ab_central_sync/changelog.d/2026-11-16-branch-access-workflow.md
- ab_central_sync/changelog.d/2026-11-16-replica-sales-scope.md
- ab_central_sync/controllers/main.py
- ab_central_sync/i18n/ar.po
- ab_central_sync/i18n/ar_001.po
- ab_central_sync/models/__init__.py
- ab_central_sync/models/access.py
- ab_central_sync/models/cache.py
- ab_central_sync/models/enrollment.py
- ab_central_sync/models/sales.py
- ab_central_sync/security/record_rules.xml
- ab_central_sync/workflow.md
