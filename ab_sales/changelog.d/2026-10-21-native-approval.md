Current changes before commit:

- Add local inventory as an explicit sales dependency and remove the hard E-Plus dependency.
- Route legacy external operations through an optional connector boundary while preserving existing historical fields and actions.
- Treat cancelled local invoices and their lines as read-only in sales record rules.
- Reverse the frozen discounted total when a promoted native sale is returned.
- Translate the connector boundary messages in both supported Arabic catalogs.

Validation: A fresh isolated install completed with `ab_eplus_connect` and the legacy bridge uninstalled. The backend workflow, concurrency, accounting, view, translation, asset, promotion, and contract suites passed in that database, and the Arabic unavailable message was verified through the real runtime path.

Files changed:

- ab_sales/__manifest__.py
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/external_connector.py
- ab_sales/models/ab_product_inherit.py
- ab_sales/models/ab_sales_header.py
- ab_sales/models/ab_sales_header_backend.py
- ab_sales/models/ab_sales_inventory.py
- ab_sales/models/ab_sales_per_day.py
- ab_sales/models/ab_sales_pos_backend.py
- ab_sales/models/ab_sales_pos_balance_refresh.py
- ab_sales/models/ab_sales_pos_customer.py
- ab_sales/models/ab_sales_return_backend.py
- ab_sales/models/ab_sales_return_header.py
- ab_sales/models/ab_sales_return_router.py
- ab_sales/models/ab_sales_ui_store_status.py
- ab_sales/security/rules_sales.xml

40e49a82 | Alhassan Hossny | 2026-10-18 | ab_sales/Fix: restore POS19 loading and harden inventory refresh

- Restored POS loading and hardened inventory refresh behavior.

Files changed:

- ab_sales models and frontend assets related to POS inventory refresh.
