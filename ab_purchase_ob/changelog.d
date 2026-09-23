Current changes before commit:

- Standardize Odoo 19 manifest version, company author, developer, and explicit application/install/auto-install flags; preserve active data-file order and remaining dependencies.

Files changed:

- ab_purchase_ob/__manifest__.py
- ab_purchase_ob/changelog.d

Validation:

- Manifest metadata/data-file checks, Python parsing, and remaining dependency resolution passed without database or external-service access.
- No new or edited user-facing source strings; existing translation entries were preserved. Installation and UI validation remain pending the separate Odoo 19 port.

commit fc48a952be1fe29f411c546b3014aeef4b276e5b
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T15:55:52+03:00

    ab_purchase_ob/ NEED FIX , STILL ODOO15

- Import the existing Odoo 15 module as a foundation; full Odoo 19 compatibility remains pending.

Files changed:

- ab_purchase_ob/__init__.py
- ab_purchase_ob/__manifest__.py
- ab_purchase_ob/models/__init__.py
- ab_purchase_ob/models/ab_inventory_inherit.py
- ab_purchase_ob/models/opening_balance_header.py
- ab_purchase_ob/models/opening_balance_line.py
- ab_purchase_ob/security/ir.model.access.csv
- ab_purchase_ob/security/record_rules.xml
- ab_purchase_ob/security/security_groups.xml
- ab_purchase_ob/views/opening_balance_header.xml
