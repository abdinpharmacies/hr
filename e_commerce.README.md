# e_commerce development environment

Restored and isolated on 2026-11-03 from the user-supplied `/home/abdin_04/Documents/Share/DBs/ecom19_dev_2026-11-03.zip`. The homepage, public shop, and login page now work locally. English and Arabic homepage/shop routes return HTTP 200. See the recovery record below for the original failure and repair.

## Worktree

- Worktree: `/opt/odoo19/worktrees/e_commerce`
- Branch: `e_commerce`, tracking `origin/e_commerce`
- Verified HEAD: `824b6b841670df438b61b4a14852ea7d8e1f14b4`, matching the locally recorded upstream on 2026-11-03
- Latest commit: `ab_ecommerce_storefront/IMP: add legacy SEO import preview and queued drafts`, Mohamed Fawzy, 2026-11-02
- Origin: `git@github.com:abdinpharmacies/hr.git`
- Main checkout: `/opt/odoo19/custom-addons`; it is a separate worktree and is **not** the custom addons path for this instance.

Run Git commands from this worktree. Inspect `git status --short`, `git branch -vv`, and `git worktree list` before changing branches or transferring fixes. The existing `.codex` modification was left untouched. The recovery did not pull, switch branches, create commits, or change application source. The earlier restore report recorded `2a458f1e`; the current source is the HEAD above.

## Launch configuration

- Shared server/interpreter: `/opt/odoo19/server`, `/opt/odoo19/venv19/bin/python3`
- Addons path: `/opt/odoo19/server/addons,/opt/odoo19/worktrees/e_commerce`
- Config: `/opt/odoo19/conf/e_commerce.conf` (mode 0600)
- Launcher: `/opt/odoo19/bin/odoo19-run-e_commerce`
- PyCharm run configuration: `e_commerce`, `/opt/odoo19/.idea/runConfigurations/e_commerce.xml`
- Homepage: http://127.0.0.1:4102/
- Shop: http://127.0.0.1:4102/shop
- Login: http://127.0.0.1:4102/web/login
- HTTP port: 4102; gevent port: 4103 (reserved in config, no separate gevent worker with workers=0)
- Data: `/opt/odoo19/data/e_commerce`
- Filestore: `/opt/odoo19/data/e_commerce/filestore/e_commerce`
- Logs: `/opt/odoo19/logs/e_commerce.log`, `/opt/odoo19/logs/e_commerce-console.log`
- Verified running process during recovery: PID `879681`, using the config above and `-d e_commerce --dev=xml`. PIDs change; inspect the live process/port before any process operation. The original launcher PID file may be stale after a PyCharm launch.

Do not start a second copy while an instance owns port 4102. No systemd service was added. The recovery reloaded the running registry through Odoo signaling without stopping or restarting the process.

## Development workflow

1. Read this worktree's `AGENTS.md` and any module-specific guidance. Confirm the target database is `e_commerce` and the addons path points to this worktree.
2. Use PyCharm's existing `e_commerce` run configuration, or launch from a terminal when port 4102 is free:

   ```bash
   /opt/odoo19/bin/odoo19-run-e_commerce
   ```

   Both launch methods use `--dev=xml`, `ODOO_QUEUE_JOB_CHANNELS=root:0`, and an empty `QUEUE_JOB__NO_DELAY`. Keep those settings. XML development mode does not automatically reload Python changes.

3. Read the application log while reproducing errors:

   ```bash
   tail -n 150 /opt/odoo19/logs/e_commerce.log
   curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:4102/
   ```

4. For a module change that needs an upgrade, back up the target database and use only the affected module names. Use alternate ports and keep cron/queues disabled; do not stop the PyCharm process for validation:

   ```bash
   ODOO_QUEUE_JOB_CHANNELS=root:0 QUEUE_JOB__NO_DELAY= \
     /opt/odoo19/venv19/bin/python3 /opt/odoo19/server/odoo-bin \
     -c /opt/odoo19/conf/e_commerce.conf -d e_commerce \
     -u <affected_module> --stop-after-init \
     --workers=0 --max-cron-threads=0 \
     --http-port=5069 --gevent-port=5072 \
     --logfile=/tmp/e_commerce-module-upgrade.log
   ```

   Replace `<affected_module>` before running. Choose another unused port pair when necessary. Never use `-u base` for routine work. The alternate ports isolate listeners; the command still changes the selected `e_commerce` database. Inspect module data files for business-data side effects before upgrades.

5. Verify `/`, `/shop`, `/web/login`, `/ar`, and `/ar/shop`, relevant assets, and affected functionality. Review new log entries rather than treating historical tracebacks as new failures. Maintain both Arabic catalogs for any changed UI strings.

The shared virtual environment now includes the missing manifest dependencies `ijson==3.6.0` and `phonenumbers==9.0.42`. Keep them available in any replacement interpreter. No other packages were upgraded during this repair.

## Database and isolation

Database `e_commerce` did not exist before restoration. SQL restoration completed in a single transaction with ON_ERROR_STOP enabled. The backup is Odoo 19/PostgreSQL 16 format. The original archive remains untouched.

The config uses local PostgreSQL access through the existing `odoo19` login, `db_name=e_commerce`, `dbfilter=^e_commerce$`, and `list_db=False`. This is application-level database isolation, not a dedicated PostgreSQL role. PUBLIC connection access was revoked on the new database. Credentials remain private in the config; none are included here. Odoo database UUID, database secret, and database-manager master password were regenerated. Existing user login passwords were preserved.

Native Odoo neutralization ran for auth_oauth, base, delivery, google_recaptcha, iap, mail, payment, payment_paypal, web, and website. Additional development isolation:

- All scheduled jobs disabled; workers=0 and max_cron_threads=0.
- Queue runner disabled via `ODOO_QUEUE_JOB_CHANNELS=root:0` and config channels=root:0; immediate job execution environment setting cleared. One pending job cancelled, retaining its record.
- 182 queued/error emails cancelled. SMTP endpoints redirected to 127.0.0.1:1 and mail credentials cleared. Incoming mail disabled.
- All 24 payment providers and five delivery carriers disabled; PayPal credentials cleared.
- 31 AI assistant configurations deactivated and credentials cleared.
- Ten external connector parameter values cleared, covering B-Connect, MSSQL, external Odoo, and Telegram settings.
- OAuth disabled, IAP tokens neutralized, website analytics/custom injected tracking code disabled, website domain/CDN cleared, and base URL set to localhost.
- Native neutralization banners enabled. No external B-Connect or E-Plus connection or write was made.

## Module recovery

The initial restore disabled eight modules whose sources were unavailable at that time, preserving their tables and stored records. The matching worktree sources are now available for the three modules needed by the storefront. Their original installed states were recovered:

- ab_core_ui
- ab_ecommerce_storefront
- ab_website_admin_content

These five modules remain disabled; restoring them is separate work:

- ab_ecommerce_api
- ab_ecommerce_editor
- ab_navigation_performance
- ab_queue_monitor
- report_xlsx

The initial exclusion deactivated 272 views and detached 35 menu actions. Recovery compared the original archive's metadata with the restored database and restored 261 view states and 19 menu actions for the three required modules and their applicable descendants. Original inactive view choices were preserved. Other excluded modules were not enabled.

This was a one-time recovery of previously installed metadata, not a fresh module installation or upgrade. Product/catalog XML was not replayed. Do not reuse this approach for new module installation or ordinary upgrades; use Odoo's normal module lifecycle. No migration or hook was added to the addons.

The original HTTP 500 came from the saved `website.homepage` customization calling `website._ab_storefront_home_catalog` while `ab_ecommerce_storefront` was disabled. Disabled `ab_core_ui` also prevented `ab_website_sale_product`, `ab_website_seo_optimization`, and `ab_product_seo_enhancement` from loading. Restoring the dependencies and installing the two missing Python packages resolved registry loading. The current source already contains the stock helper access fix needed by public visitors; no field permissions were changed.

## Verification

Initial restoration checks:

- Archive path and CRC checks; all 21,901 content blobs matched their SHA-1 filenames. The archive also contained 87 filestore checklist entries.
- All 21,836 distinct database attachment blob references resolve to restored files.
- Registry startup with no HTTP and no module upgrades; normal localhost server startup.
- Login page HTTP 200; three sampled published-product images returned HTTP 200 and exactly matched their filestore content.
- Database listing denied; a request naming central19 did not switch away from e_commerce.
- No active cron, incoming mail, payment provider, carrier, AI assistant, or pending queue job; cleared connector values verified.
- Counts unchanged: 32,525 product templates, 32,525 product variants, 103,492 Abdin products, 67 sales orders, 23,879 stock moves, 47,695 stock quants, and 107,824 attachments.
- Private config permissions and valid PyCharm XML.

Recovery checks on 2026-11-03:

- The running registry loaded all 123 selected modules without missing-module errors.
- `/`, `/shop`, `/web/login`, `/en`, `/ar`, `/en/shop`, and `/ar/shop` returned HTTP 200 after redirects where applicable.
- English rendered as `en-US`; Arabic rendered as `ar-001` with a different, translated homepage title.
- Frontend CSS and JavaScript bundles, three sampled homepage images, and a product detail page returned HTTP 200. Odoo regenerated its asset attachments normally.
- Full-row comparisons against the pre-recovery backup matched for all 12 checked tables: `product_template`, `product_product`, `ab_product`, `sale_order`, `sale_order_line`, `stock_move`, `stock_move_line`, `stock_quant`, `product_pricelist`, `product_pricelist_item`, `product_category`, and `stock_warehouse`.
- Scheduled jobs, incoming mail, payment providers, delivery carriers, pending queue jobs, and AI assistants remained disabled. External connector credentials remained cleared.
- No application source or UI strings changed, so no translation export or targeted module upgrade was needed for this recovery.

Authenticated sign-in, checkout/order submission, and external integrations were not tested. Existing non-blocking view/accessibility and deprecated-route warnings remain outside this repair. No medical content was generated or published.

Original private restoration reports: `/opt/odoo19/data/e_commerce/restore-audit/`.

Recovery backup and evidence: `/opt/odoo19/data/e_commerce/recovery-audit/2026-11-03/`. `before-recovery.backup` is the dedicated pre-repair PostgreSQL backup; metadata snapshots and HTTP/data verification reports document the changes. Keep this directory private and out of Git. A database rollback is a separate, deliberate operation; do not overwrite the running database casually.
