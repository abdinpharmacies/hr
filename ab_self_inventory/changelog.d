# ab_self_inventory changelog

## Recent commits

### 684e50f

Author: Mohamed Fawzy
Date: 2026-08-26
Subject: ab_self_inventory/chore(#2312):Inventory Count Snapshot, Partial Progress, and Result Reporting Plan

User-facing changes:
- Save Balance at Count snapshots when exporting count sheets.
- Import Actual Qty and optional Balance at Count from partial Excel uploads.
- Calculate shortage, excess, matched, and implementation progress from saved count data.
- Require all requested products to be counted before final inventory submission.

Files changed:
- ab_self_inventory/i18n/ab_self_inventory.pot
- ab_self_inventory/i18n/ar.po
- ab_self_inventory/i18n/ar_001.po
- ab_self_inventory/models/self_inventory_process.py
- ab_self_inventory/models/self_inventory_request.py
- ab_self_inventory/reports/self_inventory_xlsx.py
- ab_self_inventory/static/src/js/self_inventory_form_widgets.js
- ab_self_inventory/static/src/scss/self_inventory_form.scss
- ab_self_inventory/views/self_inventory_process_views.xml
- ab_self_inventory/wizard/self_inventory_import_wizard.py

## Current changes before commit

User-facing changes:
- Show only one visible row result column, Difference, on active self inventory process lines.
- Color the Difference result box by row state: shortage yellow, excess red, and matched green.
- Keep the inventory progress donut, progress bar, and stat boxes on one horizontal line.
- Remove Counted and Pending stat boxes from the inventory progress panel.
- Remove the Actual Qty spinner controls and sort icon from the process count grid.
- Add a separate Inventory Implementation percentage column to the self inventory request list.

Files changed:
- ab_self_inventory/i18n/ab_self_inventory.pot
- ab_self_inventory/i18n/ar.po
- ab_self_inventory/i18n/ar_001.po
- ab_self_inventory/static/src/js/self_inventory_form_widgets.js
- ab_self_inventory/static/src/scss/self_inventory_form.scss
- ab_self_inventory/views/self_inventory_request_views.xml
- ab_self_inventory/views/self_inventory_process_views.xml
- ab_self_inventory/changelog.d
