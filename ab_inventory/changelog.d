Current changes before commit:

- Open Movement Schedule without a default Saved filter so pending and saved movements are both visible.

Files changed:

- ab_inventory/changelog.d
- ab_inventory/views/ab_inventory_movements.xml

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
