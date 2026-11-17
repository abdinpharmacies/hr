Current changes before commit:

- 2026-11-17: Hide the Inventory Stores user-form extension without altering its field, assignments, ACLs or record rules.
- Select new movement database serials through a server-owned method. Ordinary posting keeps the configured database serial; central synchronization can provide the authenticated originating replica serial before creation.
- Keep the existing immutable-serial guard; no historic movements or quantities are rewritten. Bump to 19.0.1.0.1 and document the behavior.

- Document the 2026-11-16 central database repair: the deployed inventory code expected db_serial, but the database column was missing, causing central sale delivery to fail with HTTP 500.
- Back up central and run a targeted ab_inventory upgrade to apply the existing field definition. No new runtime code or migration was required.
- Verify pending branch operations 61 and 62 were automatically accepted with their original identities and hashes, each with exactly one posted sale stock allocation and one matching store-29 ledger movement.
- Confirm no inventory model columns are missing, branch readiness is restored, and the existing Arabic field and list-view translations load correctly.
- Existing duplicate stock-cache and nullable allocation-unit warnings remain outside this repair. Historical protocol-2 retries and previously rejected operations were not forced through.

Files changed:

- ab_inventory/README.md
- ab_inventory/__manifest__.py
- ab_inventory/changelog.d
- ab_inventory/models/ab_inventory.py
- ab_inventory/views/res_users_inventory.xml

commit 71fcb23d369409906d5b04497e721570cf1b6477
Author: hager yasser <hageryasser2002@gmail.com>
Date: 2026-11-09T13:19:41+02:00

    ab_inventory/FEAT: Add db_serial column for inventory table

- Show DB Serial beside Store in the Movement Schedule table.
- Capture the configured database serial for new movements and prevent later changes through ORM calls; retain zero for existing movements.
- Translate the column label and validation message into Arabic.

Files changed:

- ab_inventory/changelog.d
- ab_inventory/models/ab_inventory.py
- ab_inventory/views/ab_inventory_movements.xml
- ab_inventory/i18n/ar.po
- ab_inventory/i18n/ar_001.po

commit 2635e17870fc0afc45f464ab17f9c1ca0fb035e3
Author: hossam elsheikh
Date: 2026-11-08T11:20:03+02:00

    refactor(ab_inventory): use product reference units for stock ledger

- Store fractional reference-unit movements and lock canonical unit definitions.

Files changed:

- ab_inventory/INTEGRATION.md
- ab_inventory/README.md
- ab_inventory/changelog.d
- ab_inventory/i18n/ar.po
- ab_inventory/i18n/ar_001.po
- ab_inventory/models/__init__.py
- ab_inventory/models/ab_inventory.py
- ab_inventory/models/ab_inventory_process.py
- ab_inventory/models/ab_product.py
- ab_inventory/models/ab_product_uom.py
- ab_inventory/models/ab_product_uom.py

commit 063998a08a6b6229331d583049bccd79c54b5c75
Author: yahyazakaria22 <yahyazakaria.soskty@gmail.com>
Date:   2026-10-19T02:58:26+03:00

    ab_inventory: guard stock effects and add shared operation checks

- Compute historical closing balances from saved movement quantities and include pending outgoing reservations in current availability.
- Guard linked movements, stock posting, product and unit definitions, and provide a shared operation preflight.
- Add stock query indexes, update integration guidance, and translate new validation messages.

Files changed:

- ab_inventory/INTEGRATION.md
- ab_inventory/README.md
- ab_inventory/changelog.d
- ab_inventory/i18n/ar.po
- ab_inventory/i18n/ar_001.po
- ab_inventory/models/__init__.py
- ab_inventory/models/ab_inventory.py
- ab_inventory/models/ab_inventory_process.py
- ab_inventory/models/ab_product.py
- ab_inventory/models/ab_product_source.py
- ab_inventory/models/ab_uom.py
- ab_inventory/report/ab_inventory_period_report.py

commit b68b8b34aba74df72104cd1a3117c32f83589251
Author: yahyazakaria22 <yahyazakaria.soskty@gmail.com>
Date:   2026-10-19T00:36:34+03:00

    Preserve inventory, purchase, product source and tax addons after sync

- Restore the inventory ledger, reports, translations, and security to their pre-pull contents.
- Remove the incoming balance projection, reservation, shortage, and integrity-review additions from this module.

Files changed:

- ab_inventory/INTEGRATION.md
- ab_inventory/README.md
- ab_inventory/__manifest__.py
- ab_inventory/changelog.d
- ab_inventory/i18n/ar.po
- ab_inventory/i18n/ar_001.po
- ab_inventory/models/__init__.py
- ab_inventory/models/ab_inventory.py
- ab_inventory/models/ab_inventory_process.py
- ab_inventory/models/ab_product_source.py
- ab_inventory/models/integrity_review.py
- ab_inventory/models/res_users.py
- ab_inventory/models/stock_state.py
- ab_inventory/report/ab_inventory_balance_report.py
- ab_inventory/report/ab_inventory_period_report.py
- ab_inventory/security/ir.model.access.csv
- ab_inventory/security/record_rules.xml
- ab_inventory/security/security_groups.xml
- ab_inventory/views/menus.xml
- ab_inventory/views/stock_state.xml

commit da3754e09c65e74b83715008e7033c51cefa948d
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T16:34:09+03:00

    ab_inventory/ FIX Odoo 19 manifest metadata

- Standardize the Odoo 19 manifest metadata while preserving dependencies and data-file order.

Files changed:

- ab_inventory/__manifest__.py
- ab_inventory/changelog.d

commit 65e0c40e3b7ed38f689cc908fa689beee3eecb63
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T15:56:26+03:00

    ab_inventory/ NEED FIX , STILL ODOO15

- Import the existing Odoo 15 module as a foundation; full Odoo 19 compatibility remains pending.

Files changed:

- ab_inventory/__init__.py
- ab_inventory/__manifest__.py
- ab_inventory/models/__init__.py
- ab_inventory/models/ab_inventory.py
- ab_inventory/models/ab_inventory_header.py
- ab_inventory/models/ab_inventory_process.py
- ab_inventory/models/ab_product_inherit.py
- ab_inventory/models/ab_product_source_inherit.py
- ab_inventory/models/ab_product_source_pending.py
- ab_inventory/security/ir.model.access.csv
- ab_inventory/static/description/icon.png
- ab_inventory/views/ab_inventory_header.xml
- ab_inventory/views/ab_product_source_inherit.xml
- ab_inventory/views/ab_product_source_pending.xml
- ab_inventory/views/menus.xml
