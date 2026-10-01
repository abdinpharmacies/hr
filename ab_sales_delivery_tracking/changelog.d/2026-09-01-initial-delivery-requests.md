# Delivery tracking recent changes

## cc4132fb04199ae81798de1ed52d029144a416ae - hager yasser - 2026-09-21

Original commit subject: ab_sales_delivery_tracking/FIX(#20049): Fix Delivery Queue and Longpoll Environment Setup

User-facing changes:
- Fixed long-polling environment paths for escaped instance names and preserved reception history.
- Assigned Telegram delivery jobs to the module-owned delivery queue channel.

Files changed:
- ab_sales_delivery_tracking/DELIVERY_TELEGRAM_ACTIVATION_GUIDE.md
- ab_sales_delivery_tracking/changelog.d/2026-09-01-initial-delivery-requests.md
- ab_sales_delivery_tracking/data/queue_jobs.xml
- ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh

## 5891d19c01bda5e3d177d133d97b4669663635d6 - emadco88 - 2026-09-21

Original commit subject: ab_sales_delivery_tracking/ FIX remove system params

User-facing changes:
- Disabled installation-time Telegram system parameter records.

Files changed:
- ab_sales_delivery_tracking/data/ir_config_parameter.xml

## 53122600cd8500e58433a66da8ef963951a35a45 - emadco88 - 2026-09-21

Original commit subject: ab_sales_delivery_tracking/ FIX remove 1 minute cron job

User-facing changes:
- Disabled the one-minute pending-message cron record in module data.

Files changed:
- ab_sales_delivery_tracking/data/ir_cron.xml

## Current changes before commit:

User-facing changes:
- Added a delivery-only POS dialog with multiline instructions, Push & Notify, Push Without Notification, Push Without Delivery, and Cancel; closing the dialog never submits.
- Push Without Delivery accepts optional instructions, changes the submitted bill to non-delivery, clears notification consent, and submits once through the existing path without a request or queued send. Both direct and Before Submit entry paths preserve other entered values.
- Force notification consent off for non-delivery API submissions, including payloads containing stale consent.
- Keep Before Submit mounted beneath the notification popup using a module-owned Before Submit subclass. Cancel, Escape, and close preserve its draft values and do not submit; accepting a choice submits once without a second popup.
- Ignore background Before Submit F10 events while another dialog is active.
- Omit the dedicated customer phone line from new Telegram messages, retries, and manual resends; retain stored phone values and leave previously sent Telegram messages untouched.
- Connected a module-owned POS subclass through an extension of the existing client action record, preserving the shared POS class; existing notify/skip choices retain the delivery flag.
- Require nonblank instructions in the dialog, submit API, and bill push entry point when notifying. Missing or non-boolean consent defaults to no notification in POS submissions.
- Store supplied instructions on the bill for either push choice. Create and queue a request only after an explicitly authorized successful delivery push.
- Snapshot instructions on new requests and include them once in the bot text. Notification retries preserve that snapshot and never invoke sales push.
- Preserve existing queued requests, duplicate-token handling, request uniqueness, and already-sent job checks.
- Check bill/request access before privileged request creation or sending; append English-source Arabic translations in both catalogs.

Validation:
- Installed and upgraded only this module in isolated database codex_delivery_choice_20261001.
- Thirteen backend tests passed with sales pushes and Telegram calls mocked: consent validation, skips, failed pushes, snapshot/retry behavior, duplicate tokens, denied access, branch-scoped record rules, existing queued requests, a real queue-job save/load/retry round-trip, and phone omission for new sends, retries, manual resends, legacy queued requests, and non-delivery conversion with stale consent and optional instructions.
- Executable frontend checks passed for notify/skip, whitespace rejection, cancel/close, duplicate clicks, non-delivery passthrough, delivery flags for existing choices and the new non-delivery conversion, preservation of the same Before Submit draft on Cancel/Escape/close, background F10 isolation, and exactly one submission after either accepted choice.
- Targeted upgrade, combined asset compilation, runtime en_US/ar_001 validation and view translation, both PO format checks, and Python/JavaScript/XML syntax checks passed.
- Development test harnesses are outside the production addon: /tmp/test_delivery_choice.py and /tmp/test_delivery_dialog.mjs.
- No live E-Plus push or Telegram notification was performed; the running POS database was not upgraded.

Files changed:
- ab_sales_delivery_tracking/__manifest__.py
- ab_sales_delivery_tracking/changelog.d/2026-09-01-initial-delivery-requests.md
- ab_sales_delivery_tracking/i18n/ar.po
- ab_sales_delivery_tracking/i18n/ar_001.po
- ab_sales_delivery_tracking/models/__init__.py
- ab_sales_delivery_tracking/models/ab_delivery_request.py
- ab_sales_delivery_tracking/models/ab_sales_header.py
- ab_sales_delivery_tracking/models/ab_sales_pos_api.py
- ab_sales_delivery_tracking/static/src/pos/delivery_notification.js
- ab_sales_delivery_tracking/static/src/pos/delivery_notification.xml
- ab_sales_delivery_tracking/views/pos_action.xml
