Current changes before commit:

- Compute each saved movement's historical closing balance from signed saved quantities instead of storing a separate closing value.
- Sum saved movement quantities for historical reads and add pending outgoing quantities to current availability; ignore pending incoming quantities.
- Lock the store when reserving pending outgoing stock and posting; reject movements that overdraw a batch, and keep period reporting saved-only.
- Add partial covering indexes for saved source, product, and date sums and pending outgoing source and product sums.
- Enforce one linked movement per positive `(store_id, model_ref, res_id)` with a partial database unique index while allowing the same linked ID in another store and unlinked manual movements.
- Scope linked-line retries and duplicate checks to the store.
- Add a shared `check_operation()` preflight for business-module create, write, and unlink calls; account for an existing pending hold when checking a replacement.
- Invoke that preflight from `inventory_write()` while keeping movement creation and posting checks authoritative.
- Block product, source, and referenced unit-definition changes while pending or saved movements exist; lock those definitions before movement creation and unit conversion.
- Update integration guidance for the preflight API and translate the pending outgoing shortage, unit-protection, and pending-deletion messages in both Arabic catalogs.

Files changed:

- ab_inventory/changelog.d
- ab_inventory/INTEGRATION.md
- ab_inventory/README.md
- ab_inventory/i18n/ar.po
- ab_inventory/i18n/ar_001.po
- ab_inventory/models/ab_inventory.py
- ab_inventory/models/__init__.py
- ab_inventory/models/ab_inventory_process.py
- ab_inventory/models/ab_product.py
- ab_inventory/models/ab_product_source.py
- ab_inventory/models/ab_uom.py
- ab_inventory/report/ab_inventory_period_report.py

Validation:

- `git diff --check -- ab_inventory` passed.
- A read-only duplicate query is documented for existing databases; it could not be run because no Odoo/PostgreSQL database is available in this workspace.
- The latest-close helper has no remaining callers in this module.
- The new shortage and unit-protection messages are translated in both Arabic catalogs; POT export and `msgfmt` validation await an Odoo/gettext runtime.
- An Odoo database upgrade and runtime balance checks have not been run for these changes.

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
