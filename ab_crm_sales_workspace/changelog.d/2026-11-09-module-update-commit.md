# Module update committed — df80c7c9

- Commit: `df80c7c92f3912d3ffb87f6168d08d0a57897adb`
- Author: Alhassan Hossny
- Date: 2026-11-09T10:26:24+02:00
- Original subject: ab_crm_sales_workspace/feat: improve chatter composition and branch sharing

Add embedded media composition, message navigation, customer locations, reviewed branch sharing and bilingual saved replies. Preserve session authorization while skipping contended activity writes, and add accessible status roles to informational banners.

Validation: 83 workspace tests, 5 independent-transaction session checks, English/Arabic form browser checks, and shared browser regressions passed. Targeted upgrade passed with --dev=xml.

Files changed:
- `__manifest__.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/branch_location.py`
- `models/media.py`
- `models/orders.py`
- `models/saved_reply.py`
- `models/session.py`
- `models/workspace.py`
- `resources/branch_locations_staging.csv`
- `resources/pharmacy_cosmetics_saved_replies.csv`
- `security/ir.model.access.csv`
- `security/record_rules.xml`
- `static/src/branch_widget.js`
- `static/src/branch_widget.xml`
- `static/src/composer.js`
- `static/src/composer.xml`
- `static/src/location.js`
- `static/src/location.scss`
- `static/src/location.xml`
- `static/src/message.js`
- `static/src/message.xml`
- `static/src/order_dialog.js`
- `static/src/order_dialog.xml`
- `static/src/templates.js`
- `static/src/templates.xml`
- `static/src/workspace.js`
- `static/src/workspace.scss`
- `static/src/workspace.xml`
- `static/tests/chatter_ui.test.js`
- `static/tests/composer.test.js`
- `static/tests/location.test.js`
- `static/tests/message.test.js`
- `tests/__init__.py`
- `tests/session_concurrency.py`
- `tests/test_branch_browser.py`
- `tests/test_workspace.py`
- `views/branch_location.xml`
- `views/telegram_setup.xml`
