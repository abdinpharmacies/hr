## bf8bb1f32b2c5c4718a3640a0eac2dd54082b26f — emadco88 — 2026-10-17

Original commit subject: ab_sales/  refactor POS draft storage and clean invalid cache on upgrade

User-facing changes:
- Store POS drafts by token with revision and ownership checks.
- Retain local drafts when server backup is unavailable.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-17-draft-records.md
- ab_sales/data/pos_draft_cleanup.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_draft_cache.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/security/ir.model.access.csv
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml

## Current changes before commit:

- Resolve staged stash-application conflicts in inventory, POS refresh, search metadata, JavaScript and both Arabic catalogs. Conflict markers caused a Python SyntaxError and prevented the POS19 registry from loading.
- Retain the existing inventory constraint identifier and English/Arabic strings. Preserve the pending validated snapshot, concurrency, authorization and metadata changes while keeping both search helper methods used by the merged callers.
- Remove the newly staged duplicate age-label template; retain the existing PosSearchBalanceAge extension and ProductCard integration.
- Preserve the separately staged invoice-notification and draft changes.

Files changed by this repair, relative to the supplied staged files:
- ab_sales/changelog.d/2026-10-18-pos19-log-repair.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_inventory.py
- ab_sales/models/ab_sales_pos_balance_refresh.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/static/src/pos/pos_balance_refresh.js
- ab_sales/static/src/pos/pos_product_card.xml (removed duplicate staged addition)

Validation on 2026-10-18:
- POS19 abdin_pos recovered without a restart: login HTTP 200, websocket HTTP 101 and successful queue-job requests after registry reload at 06:18 UTC.
- Targeted ab_sales upgrade passed in the existing isolated ab_sales_sync_validation_20261015 database, with HTTP and cron disabled and ports 5069/5072 explicitly selected. No live database upgrade was performed.
- Passed 17 ORM regression tests, six concurrent-transaction tests and seven frontend test groups. External SQL reads were mocked.
- Compiled 1,164 backend JavaScript assets and 512 template assets; generated JavaScript passes Node syntax checks. Exactly one POS age-label extension remains.
- Parsed 633 repository Python files. Both Arabic catalogs pass msgfmt --check-format. Exported a fresh module POT; runtime Arabic menu/field and all eight JavaScript age translations passed.
- Preserved the user's staged index. Repair originals and external test harnesses/logs are under /tmp/pos19-log-repair-originals and /tmp/pos19-repair-*.

Remaining operational issues:
- A fresh POS request after registry recovery exposed an unapplied draft schema upgrade: abdin_pos still reports ab_sales 19.0.1.0.0, lacks ab_sales_pos_draft_cache.pos_client_token and the draft-scope table. Eleven legacy cache rows contain sixteen bill entries, four with line items. The module's existing cleanup would delete the legacy records on upgrade. A backup and bounded preservation migration require explicit authorization before the live targeted upgrade; the code repair alone does not fix draft backup/restore.
- Keep integrations active as requested. Configured remote B-Connect and replication TCP endpoints time out; the configured local branch SQL endpoint also times out. The host network interface and default route are present.
- Replication host 192.168.1.170 also has failed local neighbor resolution. Local SQL host 192.168.1.150 has a known neighbor address but its SQL port times out. Endpoint confirmation is pending; no network configuration was changed.
- The stored replication password is not in the Fernet token format expected by ab_odoo_connect and cannot be decrypted with the configured key. No credential values were logged or changed.
- Read-only inspection confirms no live inventory uniqueness constraint. Earlier validation recorded duplicate branch/product rows; this repair does not reconcile or delete inventory records.
- Existing manifest/schema warnings remain. Live external SQL execution and invoice posting were not tested.
