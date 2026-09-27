Current changes before commit:

- Remove the invalid Odoo 19 `default_period="today"` from the movement search date filter while keeping the date filter available.
- Add required Odoo module comments to both Arabic PO files so inventory translations import under Odoo 19 without changing existing translations.
- Convert README Python examples from Markdown fences to docutils-friendly literal blocks so module activation output stays clean.
- Preserve the branch-scoped Pending/Saved inventory flow from the plan; this fix only unblocks activation and translation loading.

Files changed:

- ab_inventory/changelog.d
- ab_inventory/README.md
- ab_inventory/i18n/ar.po
- ab_inventory/i18n/ar_001.po
- ab_inventory/views/ab_inventory_movements.xml

Validation:

- `msgfmt --check-format` passed for `ab_inventory/i18n/ar.po` and `ab_inventory/i18n/ar_001.po`.
- `git diff --check -- ab_taxes ab_inventory ab_purchase` passed.
- Targeted Odoo 19 activation passed with `-i ab_inventory --without-demo --stop-after-init --no-http`.
- Final targeted Odoo 19 upgrade passed cleanly with `-u ab_taxes,ab_inventory,ab_purchase --without-demo --stop-after-init --no-http`.

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
