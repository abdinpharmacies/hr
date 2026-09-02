# 2026-09-01 - Initial sales delivery tracking Telegram queue

Recent relevant commits:

## e455a15 - hagerYasser - 2026-08-30 - ab_sales/FEAT(#2418): Add doctor and item-type filters

User-facing changes:
- Added recent sales UI and translation changes that this module follows for menu/view structure.

Files changed:
- ab_sales/changelog.d/2026-08-30-item-type-filters.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/models/ab_sales_ui_api_bill_wizard_inherit.py
- ab_sales/static/src/bill_wizard/bill_wizard_action.js
- ab_sales/static/src/bill_wizard/bill_wizard_action.scss
- ab_sales/static/src/bill_wizard/bill_wizard_action.xml
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.scss
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/zz_product_search_arabic_keymap_patch.js
- ab_sales/tests/__init__.py
- ab_sales/tests/test_item_type_filters.py
- ab_sales/views/ab_product_inherit.xml
- ab_sales/views/sales_header.xml

Current changes before commit:
- Added the `ab_sales_delivery_tracking` addon.
- Added delivery request logging for delivery bills after successful E-Plus push.
- Added queued Telegram send jobs with an Arabic delivery message and a `تم الاستلام` inline button.
- Added `store.code` and secure callback tokens to identify the source branch request.
- Added callback-data validation so invalid branch codes fail safely before Telegram send.
- Kept branch requests local to the sending branch; supervisor button handling does not write back through XML-RPC.
- Added manager UI, security, configuration parameters, Arabic translations, and changelog.
- Fixed the Odoo 19 search view group syntax and PO entry metadata so the module installs cleanly.
- Added a normal Odoo cron worker to drain pending delivery requests when the OCA queue job runner is not active.
- Added an immediate safe drain for newly queued delivery requests so sale-created requests send without waiting for manual resend.
- Added sale-header snapshot refresh before sending so older queued records can recover missing branch data such as `store.code`.
- Added retry timing and duplicate-send protection for delivery Telegram messages.
- Made manual resend call Telegram immediately and surface API errors in the button response.
- Made send attempts use the current configured Telegram chat id, including older queued rows.
- Added a post-commit background sender fallback for new delivery bills when the queue job runner and target database cron are not active.
- Fixed background sender thread environment setup for Odoo 19.
- Added a single-entry long-polling setup helper that installs/upgrades the Odoo module, receiver runner, systemd unit, environment file, and SQLite state directory.
- Renamed the branch addon technical directory and config namespace to `ab_sales_delivery_tracking`.
- Kept Telegram callback polling out of Odoo cron; callback handling belongs to the standalone systemd long-polling service.
- Removed the dependency on manually supplied `delivery_longpoll/` and `deploy/` files for service deployment.
- Made the setup helper validate Python/Odoo dependencies, verify the target database/model, run `systemctl daemon-reload`, restart existing installations safely, and show status/log diagnostics on startup failure.
- Added the Delivery Telegram activation guide for branch setup, single-entry supervisor setup, testing, verification, and troubleshooting.

Files changed:
- ab_sales_delivery_tracking/__init__.py
- ab_sales_delivery_tracking/__manifest__.py
- ab_sales_delivery_tracking/models/__init__.py
- ab_sales_delivery_tracking/models/ab_delivery_request.py
- ab_sales_delivery_tracking/models/ab_sales_header.py
- ab_sales_delivery_tracking/security/security_groups.xml
- ab_sales_delivery_tracking/security/record_rules.xml
- ab_sales_delivery_tracking/security/ir.model.access.csv
- ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh
- ab_sales_delivery_tracking/DELIVERY_TELEGRAM_ACTIVATION_GUIDE.md
- ab_sales_delivery_tracking/data/ir_config_parameter.xml
- ab_sales_delivery_tracking/data/queue_jobs.xml
- ab_sales_delivery_tracking/data/ir_cron.xml
- ab_sales_delivery_tracking/views/ab_delivery_request_views.xml
- ab_sales_delivery_tracking/i18n/ar.po
- ab_sales_delivery_tracking/i18n/ar_001.po
- ab_sales_delivery_tracking/changelog.d/2026-09-01-initial-delivery-requests.md
