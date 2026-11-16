# Simple notifications and WhatsApp branch locations

## Behavior

- Notifications show only “You have n unread messages”; each conversation button says “Open”. Customer names, phone numbers, provider labels and message previews are omitted from notification text. Counts use the displayed conversations’ unread totals. Existing grouping, captured message IDs, navigation and dismissal behavior are preserved.
- Shared location cards show a clickable Google Maps URL instead of raw coordinates. URLs stay left-to-right and wrap within Arabic and narrow layouts; Copy location and delivery actions remain available.
- WhatsApp’s attachment menu now includes Location and the existing reviewed branch picker. It queues a native location plus optional branch details, preserves immutable snapshots and uses the normal account/company/employee authorization and reply window.
- Location sending requires both the manager-controlled Odoo account flag and the matching gateway `location_enabled` flag. Gates are rechecked before dispatch. No synthetic customer message is sent for validation.
- Native payload structure follows [Meta’s WhatsApp location reference](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/messages/location/).

## Validation

- Isolated database: `callcenter_retirement_fresh_20261111`, ports 5069/5072, workers and cron disabled. Targeted three-module upgrade completed.
- Final workspace and WhatsApp bridge run: 133 tests passed, zero failures/errors. Includes Telegram branch regression, WhatsApp history and deduplication, company/employee/session isolation, expired reply window and dispatch-gate revocation.
- Browser suites: 72 Sales Chatter and 13 WhatsApp tests passed; mobile combined channel suite also passed. Notification and location-card assertions were updated and the WhatsApp attachment menu is covered.
- Gateway/provider checks: 73 passed, one existing real-codec test skipped. Provider HTTP uses mocked transports; there were no customer sends.
- Changed Python/XML/JavaScript syntax and Arabic catalog format checks passed. Odoo extracted both new notification terms; both Arabic catalogs passed runtime loader assertions.
- The populated clone’s browser run initially hit an unrelated POS contract asset dependency. The clean-install database passed. An existing English receipt-diagnostic assertion was made explicit about its language and passed on rerun.

Logs: `/tmp/callcenter-simple-notifications-fresh.log`, `/tmp/callcenter-simple-location-browser.log`, `/tmp/callcenter-whatsapp-branch-validation.log`, `/tmp/callcenter-whatsapp-branch-final.log`.

## Rollout

The user opened the maintenance window and stopped Callcenter Odoo. Protected database, filestore, gateway queue, configuration and previous-source backups were created and hash-verified in `/home/abdin_04/.config/crm-messaging/backups/callcenter-ui-locations-20261111/`.

The targeted upgrade of `ab_crm_messaging,ab_crm_sales_workspace,ab_crm_whatsapp_workspace` completed successfully. The existing `wa-callcenter` account was matched against gateway configuration before enabling its Odoo and gateway location flags; no Telegram or other sending flags were changed. Only Sales Chatter's Arabic catalogs were refreshed with overwrite to replace the old Telegram-only account label. All ten preservation counts and full-row hashes for historical orders/audits, CRM data, branch locations, native sales and POS handoffs stayed unchanged.

The user authenticated the worker restart and resumed Odoo in PyCharm. The worker is active with the new process; its first startup while Odoo was unavailable retried automatically and recovered. Live assets expose the simplified notification, map URL and WhatsApp Location menu. The live Arabic (`ar_001`) translation endpoint returns both new notification terms; the separate `ar` catalog is validated by the loader because that language code is not installed live. Both account location gates are enabled and the directory contains reviewed branch profiles. The live browser connector has no authenticated session, so final UI interaction is covered by the isolated browser suites rather than a live send.

The final queue contains 47 completed Telegram events, 64 completed WhatsApp events and 12 ignored WhatsApp events, with no pending/review items. Completed outgoing counts remain 33 Telegram and 14 WhatsApp. Polling heartbeat is healthy and validation ports are released. No synthetic customer messages were sent. Do not rewind the live queue for rollback; preserve completed sends and receipt evidence.
