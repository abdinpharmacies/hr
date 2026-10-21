Commit: 3db5d596c9429ff082c3fe9b0466692b945f788f
Author: emadco88 <emadco88@gmail.com>
Date: 2026-07-28T15:21:42+03:00
Subject: INIT commit pos19

User-facing changes:
- Introduce sales dashboard reporting, synchronization and archived reports.

Files changed:
- ab_sales_dashboard/README.md
- ab_sales_dashboard/__init__.py
- ab_sales_dashboard/__manifest__.py
- ab_sales_dashboard/data/sales_dashboard_sequence.xml
- ab_sales_dashboard/data/sales_dashboard_sync_cron.xml
- ab_sales_dashboard/data/sales_dashboard_telemetry_cron.xml
- ab_sales_dashboard/docs/PERFORMANCE_ARCHITECTURE.md
- ab_sales_dashboard/i18n/ar.po
- ab_sales_dashboard/i18n/ar_001.po
- ab_sales_dashboard/models/__init__.py
- ab_sales_dashboard/models/sales_dashboard_config.py
- ab_sales_dashboard/models/sales_dashboard_reconciliation.py
- ab_sales_dashboard/models/sales_dashboard_service.py
- ab_sales_dashboard/models/sales_dashboard_snapshot.py
- ab_sales_dashboard/models/sales_dashboard_sync_wizard.py
- ab_sales_dashboard/models/sales_dashboard_telemetry.py
- ab_sales_dashboard/security/ir.model.access.csv
- ab_sales_dashboard/security/record_rules.xml
- ab_sales_dashboard/security/security_groups.xml
- ab_sales_dashboard/static/description/icon.png
- ab_sales_dashboard/static/src/js/sales_dashboard_action.js
- ab_sales_dashboard/static/src/scss/sales_dashboard.scss
- ab_sales_dashboard/tests/__init__.py
- ab_sales_dashboard/tests/test_sales_dashboard.py
- ab_sales_dashboard/views/menus.xml
- ab_sales_dashboard/views/sales_dashboard_sync_views.xml
- ab_sales_dashboard/views/sales_dashboard_views.xml

Current changes before commit:
- Complete missing Arabic labels and messages using Odoo-exported terms; preserve existing translations and keep ar/ar_001 coverage aligned.

Files changed:
- ab_sales_dashboard/__manifest__.py
- ab_sales_dashboard/changelog.d/2026-10-21-arabic-completion.md
- ab_sales_dashboard/i18n/ar.po
- ab_sales_dashboard/i18n/ar_001.po
