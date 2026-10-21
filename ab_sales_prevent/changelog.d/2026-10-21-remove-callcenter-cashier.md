Commit: 3db5d596c9429ff082c3fe9b0466692b945f788f
Author: emadco88 <emadco88@gmail.com>
Date: 2026-07-28T15:21:42+03:00
Subject: INIT commit pos19

User-facing changes:
- Introduce the database-level sales-disable switch and workflow guards.

Files changed:
- ab_sales_prevent/__init__.py
- ab_sales_prevent/__manifest__.py
- ab_sales_prevent/data/ir_config_parameter.xml
- ab_sales_prevent/models/__init__.py
- ab_sales_prevent/models/ab_sales_api_guards.py
- ab_sales_prevent/models/ab_sales_cashier_guards.py
- ab_sales_prevent/models/ab_sales_guards.py
- ab_sales_prevent/models/ab_sales_lead_guards.py
- ab_sales_prevent/models/ir_config_parameter.py
- ab_sales_prevent/models/ir_ui_menu.py
- ab_sales_prevent/models/res_config_settings.py
- ab_sales_prevent/models/sales_prevent_mixin.py
- ab_sales_prevent/tests/__init__.py
- ab_sales_prevent/tests/test_ab_sales_prevent.py
- ab_sales_prevent/views/res_config_settings.xml

Current changes before commit:
- Remove the cashier addon dependency, guards, menu reference and obsolete cashier test assertion.
- Preserve blocking of POS, bills, returns and leads; validate optional installation without cashier.

Files changed:
- ab_sales_prevent/__manifest__.py
- ab_sales_prevent/changelog.d/2026-10-21-remove-callcenter-cashier.md
- ab_sales_prevent/models/__init__.py
- ab_sales_prevent/models/ab_sales_cashier_guards.py
- ab_sales_prevent/models/ir_ui_menu.py
- ab_sales_prevent/tests/test_ab_sales_prevent.py
