# Chatter performance release

Upgrade `ab_crm_sales_workspace` to 19.0.1.43.0 together with `ab_crm_website`
to 19.0.1.17.0. Activate the receiver modules together during an approved
maintenance window. The gateway worker changes are packaged separately. Pilot/production templates are not activated automatically.

## Manual activation

1. Verify the intended receiver configuration, database, addon path and current
   package checksums. Preserve a database/filestore backup and both prior runtime
   packages. Keep the current integration flags and destination mappings.
2. Stop the intended receiver using its normal operator procedure. Never stop the
   POS or another Odoo process to free a port.
3. Replace only these two receiver addon directories with the runtime packages.
4. Run the targeted upgrade against the intended database:

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin \
  -c <receiver-config> -d <receiver-db> \
  -u ab_crm_sales_workspace,ab_crm_website \
  --stop-after-init --no-http --workers=0 --max-cron-threads=0 \
  --http-port=5069 --gevent-port=5072 --logfile=<upgrade-log>
```

5. Review the log, start the intended receiver, reload backend assets and verify
   separate order/Support entries, one Support departure notice, exact notification
   focus, independent drafts, English/Arabic labels and backlog drainage.

Complete the private bounded ORM contact search-key backfill documented in Sales Chatter's README before enabling the indexed search path. No historical message movement, storage migration, recovery or replay is included.
Existing order/payment/stock/identity transport rules and historical cutoff remain.
Fresh synthetic QA is separate from production end-to-end acceptance. Existing
production dispatch/media flags must be reviewed by the operator before promising
those capabilities; this release does not enable them.

## Manual rollback

Stop the intended receiver, restore both previous runtime packages, run the same
targeted two-module upgrade, and restart the intended receiver. Keep preference,
alert, customer, order, session, receipt and mapping records. No row deletion or
history replay is required. If a separate production incident requires a database
restore, coordinate it with order/queue recovery rather than overwriting newer
business transactions automatically.

## Deferred storefront work

The separate storefront Refresh TODO affects the button in
`ab_storefront_callcenter_adapter/static/src/portal_refresh.xml` and the
`data-chat-refresh` order-chat control in `views/views.xml`.
`portal_refresh.js` already recovers every five seconds; `chat.js` polls every
five seconds and on online, pageshow and visibility changes; `native_history.js`
also catches up every five seconds and on those recovery events. Their removal
requires a separate user decision. Keep Callcenter's general Inbox Refresh.
