Commit: 73fc86056317141a0a261486554c08201fca1cdd
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-21T12:33:07+03:00
Subject: ab_sales_prevent/refactor: drop cashier dependency and guards

User-facing changes:
- Remove cashier dependencies and guards from the callcenter sales restriction module.

Files changed:
- ab_sales_prevent/__manifest__.py
- ab_sales_prevent/changelog.d/2026-10-21-remove-callcenter-cashier.md
- ab_sales_prevent/models/__init__.py
- ab_sales_prevent/models/ab_sales_cashier_guards.py
- ab_sales_prevent/models/ir_ui_menu.py
- ab_sales_prevent/tests/test_ab_sales_prevent.py

Current changes before commit:
- Forward customer/contract preview options and stock-refresh metadata through the existing sales access guards.

Files changed:
- ab_sales_prevent/__manifest__.py
- ab_sales_prevent/changelog.d/2026-10-21-rejected-bill-corrections.md
- ab_sales_prevent/models/ab_sales_api_guards.py
