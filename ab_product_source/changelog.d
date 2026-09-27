Current changes before commit:

- Replace the Odoo 15 tree view and action mode with the Odoo 19 list view type.
- Replace legacy `name_get` behavior with an Odoo 19 computed display name.
- Update product-source name search to the Odoo 19 signature and compose its filters with `fields.Domain`.
- Preserve existing price, cost, tax, expiry, and unit-conversion behavior.
- Preserve existing English source strings; no user-facing text required translation updates.

Files changed:

- ab_product_source/changelog.d
- ab_product_source/models/ab_product_source.py
- ab_product_source/views/ab_product_source.xml

Validation:

- All module XML files parse successfully.
- Legacy Odoo 15 view/API scans pass.
- `git diff --check` passes.
- Python compilation and an Odoo database upgrade remain pending because a working Python/Odoo runtime is unavailable in this shell.

commit 4786f546e25101fcf835b0d15e032b177343258e
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T16:34:25+03:00

    ab_product_source/ FIX Odoo 19 manifest metadata

- Standardize the Odoo 19 manifest metadata while preserving dependencies and data-file order.

Files changed:

- ab_product_source/__manifest__.py
- ab_product_source/changelog.d

commit 3600e7503ecc50ab89eb8b48ead075cb9d3287fc
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T15:56:48+03:00

    ab_product_source/ NEED FIX , STILL ODOO15

- Import the existing Odoo 15 module as a foundation; full Odoo 19 compatibility remains pending.

Files changed:

- ab_product_source/__init__.py
- ab_product_source/__manifest__.py
- ab_product_source/models/__init__.py
- ab_product_source/models/ab_product_source.py
- ab_product_source/security/ir.model.access.csv
- ab_product_source/static/description/icon.png
- ab_product_source/views/ab_product_source.xml
- ab_product_source/views/menus.xml
- ab_product_source/views/sql_source_id.txt
