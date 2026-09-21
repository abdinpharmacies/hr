# Delivery tracking recent changes

## dbd2737e47b61c7e786352a3c8ffa25a3d7c1491 - hager yasser - 2026-09-02

Original commit subject: ab_sales_delivery_tracking/FIX: Make Telegram long polling script standalone

- Made the Telegram long-polling receiver standalone and documented its activation.
- Removed Odoo-side reception tracking from delivery requests.

Files changed:
- ab_sales_delivery_tracking/DELIVERY_TELEGRAM_ACTIVATION_GUIDE.md
- ab_sales_delivery_tracking/changelog.d/2026-09-01-initial-delivery-requests.md
- ab_sales_delivery_tracking/models/ab_delivery_request.py
- ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh
- ab_sales_delivery_tracking/views/ab_delivery_request_views.xml

Current changes before commit:
- Fixed receiver activation for escaped instance names such as `abdin_replica(POS)` by installing a required, unquoted environment-file override with glob and systemd-specifier escaping.
- Kept existing SQLite reception history and documented the per-instance override.
- Added the module-owned `root.delivery_tracking` queue channel and assigned queued Telegram delivery sends to it.
- Preserved the existing enqueue calls, XML retry configuration, and direct/manual sending behavior.
- Replaced stale changelog entries with module-only commit references and the current channel change.

Files changed:
- ab_sales_delivery_tracking/data/queue_jobs.xml
- ab_sales_delivery_tracking/changelog.d/2026-09-01-initial-delivery-requests.md
- ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh
- ab_sales_delivery_tracking/DELIVERY_TELEGRAM_ACTIVATION_GUIDE.md

Validation:
- Shell syntax and isolated installer checks passed for plain, parenthesized, and wildcard/percent-containing instance names. Generated environment paths matched through libc glob; repeated installation preserved SQLite state and mode 0600 credential files.
- Live systemd activation requires running the prepared privileged repair; no Odoo user-facing strings were changed.
- Verified with real user-level systemd services using dummy credentials: the original escaped path failed to load the environment, while the corrected path loaded it. The generated directive also passed the actual systemd unit parser.
