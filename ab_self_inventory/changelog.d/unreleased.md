# ab_self_inventory changelog

## Recent commits

### 2c7f876

Author: Hossam Elsheikh
Date: 2026-08-10
Subject: ab_self_inventory/added readonly role

User-facing changes:
- Add a read-only self inventory role.
- Restrict read-only users to view access across requests, batches, processes, and lines.
- Update menus, process/request views, and Arabic translations for the role.

Files changed:
- ab_self_inventory/i18n/ab_self_inventory.pot
- ab_self_inventory/i18n/ar.po
- ab_self_inventory/i18n/ar_001.po
- ab_self_inventory/security/ir.model.access.csv
- ab_self_inventory/security/record_rules.xml
- ab_self_inventory/security/security_groups.xml
- ab_self_inventory/views/menus.xml
- ab_self_inventory/views/self_inventory_kanban_views.xml
- ab_self_inventory/views/self_inventory_process_views.xml
- ab_self_inventory/views/self_inventory_request_batch_views.xml
- ab_self_inventory/views/self_inventory_request_views.xml

### d415ced

Author: Alhassan Hossny
Date: 2026-07-30
Subject: ab_self_inventory/Feat:Adding a new line in process of self inventory request for branch reciever

User-facing changes:
- Allow branch receivers to add manual product lines during active self inventory processes.
- Keep requested lines protected while allowing manual line removal.
- Update import/add-line wizard views and translations for the branch receiver workflow.

Files changed:
- ab_self_inventory/i18n/ar.po
- ab_self_inventory/i18n/ar_001.po
- ab_self_inventory/models/self_inventory_process.py
- ab_self_inventory/models/self_inventory_request.py
- ab_self_inventory/security/ir.model.access.csv
- ab_self_inventory/static/src/js/self_inventory_form_widgets.js
- ab_self_inventory/views/self_inventory_process_views.xml
- ab_self_inventory/wizard/self_inventory_import_wizard.py
- ab_self_inventory/wizard/self_inventory_import_wizard_views.xml

### ae543f1

Author: Alhassan Hossny
Date: 2026-07-19
Subject: ab_self_inventory/Feat: add branch progress dashboard and requested cost tracking

User-facing changes:
- Add branch response and implementation progress tracking.
- Add requested products cost metrics to requests, batches, and processes.
- Improve process/request dashboards and Arabic translations.

Files changed:
- ab_self_inventory/i18n/ab_self_inventory.pot
- ab_self_inventory/i18n/ar.po
- ab_self_inventory/i18n/ar_001.po
- ab_self_inventory/models/self_inventory_process.py
- ab_self_inventory/models/self_inventory_request.py
- ab_self_inventory/security/record_rules.xml
- ab_self_inventory/static/src/js/self_inventory_form_widgets.js
- ab_self_inventory/static/src/js/self_inventory_widgets.js
- ab_self_inventory/static/src/scss/self_inventory_form.scss
- ab_self_inventory/views/self_inventory_kanban_views.xml
- ab_self_inventory/views/self_inventory_process_views.xml
- ab_self_inventory/views/self_inventory_request_batch_views.xml
- ab_self_inventory/views/self_inventory_request_views.xml

## Current changes before commit

User-facing changes:
- Add a floating self inventory process button for refreshing current System/E-stock quantities from B-Connect.
- Allow administrators, managers, and assigned branch receivers to refresh system stock quantities.
- Update process line system quantities for all current process products with identifiers, then recalculate differences, shortage, and extra values.
- Show non-blocking Arabic success toast notifications for changed and unchanged refresh results.
- Compare refreshed stock at the stored 3-decimal quantity precision so unchanged rows are not reported as updated repeatedly.
- Add Arabic translations for the button label and refresh notifications.

Files changed:
- ab_self_inventory/i18n/ab_self_inventory.pot
- ab_self_inventory/i18n/ar.po
- ab_self_inventory/i18n/ar_001.po
- ab_self_inventory/models/self_inventory_process.py
- ab_self_inventory/static/src/js/self_inventory_action_loader.js
- ab_self_inventory/static/src/scss/self_inventory_form.scss
- ab_self_inventory/views/self_inventory_process_views.xml
- ab_self_inventory/changelog.d/unreleased.md
