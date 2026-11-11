Current changes before commit:

- Move employee PIN and session enforcement for cashier operations into an optional bridge module.
- Keep employee POS and return access available when the cashier module is not installed.
- Add complete Arabic catalogs for both supported language codes and translate frontend messages.

Files changed:

- ab_employee_access_sales_cashier/__init__.py
- ab_employee_access_sales_cashier/__manifest__.py
- ab_employee_access_sales_cashier/changelog.d
- ab_employee_access_sales_cashier/i18n/ar.po
- ab_employee_access_sales_cashier/i18n/ar_001.po
- ab_employee_access_sales_cashier/models/__init__.py
- ab_employee_access_sales_cashier/models/ab_sales_cashier_api.py
- ab_employee_access_sales_cashier/static/src/cashier/cashier_patch.js
- ab_employee_access_sales_cashier/static/src/cashier/cashier_templates.xml
- ab_employee_access_sales_cashier/static/src/cashier/cashier.scss

Validation:

- Fresh isolated installation of the cashier bridge passed with the native sales stack.
- Both Arabic catalogs pass `msgfmt --check-format` with no untranslated entries.
