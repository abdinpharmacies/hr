## Current changes before commit

User-facing changes:
- Added a manager-only Update Stock button to each mapped Odoo store.
- Added branch-to-main stock previews using the Odoo store EPlus Serial and the main Store IP mapping.
- Added transactional main stock reconciliation by class, item, and store identifiers.
- Added main stock duplicate removal with business-metadata safeguards and deleted-row recovery snapshots.
- Added missing batch insertion, zero-stock correction, live-change retries, and final reconciliation verification.
- Replaced unreliable SQL Server cursor row counts with transactional key and quantity verification after every stock write.
- Added persistent run and line audit screens with Arabic and English interface support.

Files changed:
- ab_stock_update/__init__.py
- ab_stock_update/__manifest__.py
- ab_stock_update/changelog.d/2026-08-24-stock-update.md
- ab_stock_update/i18n/ar.po
- ab_stock_update/i18n/ar_001.po
- ab_stock_update/models/__init__.py
- ab_stock_update/models/ab_stock_update_run.py
- ab_stock_update/models/ab_store.py
- ab_stock_update/security/ir.model.access.csv
- ab_stock_update/security/security_groups.xml
- ab_stock_update/views/ab_stock_update_views.xml
- ab_stock_update/views/ab_store_views.xml
- ab_stock_update/views/menus.xml
- ab_stock_update/wizard/__init__.py
- ab_stock_update/wizard/ab_stock_update_confirm.py
- ab_stock_update/wizard/ab_stock_update_confirm_views.xml
