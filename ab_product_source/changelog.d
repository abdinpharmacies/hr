Current changes before commit:

- Standardize Odoo 19 manifest version, company author, developer, and explicit application/install/auto-install flags; preserve active data-file order and remaining dependencies.

Files changed:

- ab_product_source/__manifest__.py
- ab_product_source/changelog.d

Validation:

- Manifest metadata/data-file checks, Python parsing, and remaining dependency resolution passed without database or external-service access.
- No new or edited user-facing source strings; existing translation entries were preserved. Installation and UI validation remain pending the separate Odoo 19 port.

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
