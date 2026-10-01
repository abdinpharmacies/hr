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

## 2adebc46dd66efb9188aed91337c8bda52f9cb9f - hager yasser - 2026-10-01

Original commit subject: ab_sales_delivery_tracking/FEAT(#20487): Optional delivery bot notification

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


## 25bbfaca233e28afdb4ed8f930c43e196f25a1e9 - emadco88 - 2026-10-01

Original commit subject: ab_sales_delivery_tracking/ UPD force user to reload the POS UI

User-facing changes:
- Remove Push Without Delivery and its conversion-only dialog logic. The remaining Notify and Without Notification choices preserve the bill delivery flag; Cancel keeps Before Submit open. Existing translation entries are preserved.
- Save delivery notification choices and instructions to the draft cache before submitting, including manual non-delivery submissions; update the draft timestamp so cache restoration keeps the latest choice.
- Snapshot the bill description on new delivery requests, display it on the request form, and include nonblank descriptions in bot messages without changing them during refreshes, retries, or resends. Existing requests without a snapshot remain unchanged.
- Require interface version `1` for every POS submission, including non-delivery bills. Reject missing or outdated versions before the parent submission logic with a translated save-and-reload message, and remove the marker before ORM field processing.
- Stamp the version from the loaded module-owned JavaScript on every submission rather than trusting cached bill data.
- Append Arabic translations in both catalogs using references exported from Odoo 19.

Validation:
- Installed and targeted-upgraded this module in the isolated database `codex_delivery_followup_20261001`, with HTTP and cron workers disabled.
- Backend checks passed for missing/outdated versions on both bill types, accepted payload/keyword submissions, marker removal, consent normalization, and required instructions. Rejected calls never reached the mocked parent submit method.
- Real Odoo request checks passed for description/instructions snapshots, refresh preservation, mocked Telegram send/resend, empty description omission, and phone omission. Test business records were rolled back.
- Frontend checks passed for the two retained notification choices preserving delivery state, cache-before-submit ordering, required instructions, and Cancel preserving Before Submit. The inherited dialog uses the new base delivery default; all 108 customer/code/saved-choice combinations passed across both dialogs.
- Confirmed the XML contains exactly Push & Notify, Push Without Notification, and Cancel, with existing translations in both Arabic catalogs.
- Exported the module POT, checked both PO formats, and verified Arabic error/message/field translations plus differing English/Arabic form views at runtime.
- Backend JavaScript asset compilation passed. Full browser interaction was not exercised.
- Test harnesses remain outside the addon in `/tmp/test_delivery_followup.py`, `/tmp/test_delivery_followup.mjs`, and `/tmp/test_delivery_followup_i18n.py`.
- No live E-Plus pushes or Telegram sends were performed. The running POS database was not upgraded.

Deployment:
- Deploy the Python and JavaScript changes together, target-upgrade `ab_sales_delivery_tracking`, and restart all Odoo workers consistently. Existing tabs must reload before their next successful submission.
- Any integration calling `ab_sales_pos_api.pos_submit` must provide `header.delivery_ui_version = "1"`. Increment the frontend/backend constants together for future incompatible interface updates.

Files changed:
- ab_sales_delivery_tracking/changelog.d/2026-09-01-initial-delivery-requests.md
- ab_sales_delivery_tracking/i18n/ar.po
- ab_sales_delivery_tracking/i18n/ar_001.po
- ab_sales_delivery_tracking/models/ab_delivery_request.py
- ab_sales_delivery_tracking/models/ab_sales_pos_api.py
- ab_sales_delivery_tracking/static/src/pos/delivery_notification.js
- ab_sales_delivery_tracking/static/src/pos/delivery_notification.xml
- ab_sales_delivery_tracking/views/pos_action.xml


## Current changes before commit:

User-facing changes:
- Repair the saved POS client-action tag during webclient startup so reloading an existing tab opens the delivery-aware interface and supplies its required version marker.
- Change only a saved client action tagged `ab_sales.pos`; preserve its ID, context, parameters, other actions, and draft storage. Missing, malformed, or unavailable browser storage does not interrupt service startup.
- Preserve the original POS registry entry and inherited promotion, contract, and sales-lead extensions. Keep the backend version guard enabled.

Validation:
- Reproduced the old-action restore loop using Odoo's actual action-restoration function, then verified the startup service selects the updated tag.
- Checked repeat startup, unrelated/non-client actions, malformed JSON, missing storage, storage errors, and preservation of draft/context/state data.
- Loaded the actual promotion, contract, and sales-lead patches with the base and delivery POS classes; verified inherited promo behavior/component registration, lead dialog opening, and contract fields plus version marker on both bill types.
- Targeted upgrade and backend JavaScript asset compilation passed in isolated database `codex_delivery_followup_20261001`; JavaScript syntax and whitespace checks passed.
- No user-facing strings were added or changed. No live sales push or Telegram send was used for testing.
- Deployed the three changed files to `proxmox-2`, targeted-upgraded `ab_sales_delivery_tracking` in `abdin_replica19`, and restarted the Odoo web and queue-runner services; both are active. Verified the compiled `web.assets_web` includes the repair service and the database POS action selects the delivery interface. Original manifest/changelog backups are in `/tmp/ab_delivery_restore_backup_20261001` on that server.
- Changes remain uncommitted in both workspaces. The affected browser is not connected for direct UI verification.

Files changed:
- ab_sales_delivery_tracking/__manifest__.py
- ab_sales_delivery_tracking/changelog.d/2026-09-01-initial-delivery-requests.md
- ab_sales_delivery_tracking/static/src/pos/restore_delivery_action_service.js
