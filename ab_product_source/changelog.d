Current changes before commit:

- Convert source prices and costs through canonical product UoM factors.

Files changed:

- ab_product_source/changelog.d
- ab_product_source/models/ab_product_source.py

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
