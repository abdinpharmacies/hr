# Chat and order notification reliability release

> Historical record: versions, deployment state and validation results below describe the dated work only. Temporary QA scripts/evidence may have been removed. For the current order-status button and login-return behavior, use [the current guide](website-order-status-links.md). This record does not establish a current production rollout.

Release receiver `ab_crm_website` **19.0.1.15.1**, gateway source from this change,
then storefront `ab_storefront_callcenter_adapter` **19.0.1.5.3**.
Production upgrades, service restarts and customer-facing acceptance are manual.
The validation dependency versions are `ab_crm_sales_workspace` 19.0.1.41.0 and
`ab_ecommerce_storefront` 19.0.1.0.1. They are not included in these packages; the
package manifest records their tested file hashes, including existing local work.
Stop if deployed dependency versions or required behavior differ; resolve that
separate dependency release before activation.
Checkout stock validation, endpoint cutoff, account enablement and historical
orders/comments are unchanged. Do not recover or replay `NO-231126-DN43HM`.

## Read-only preflight

Before activation, back up each database, filestore, addon tree and gateway
configuration/queue using the deployment's established backup procedure. Preserve
matching backups together. Quiesce only the intended deployment services manually.
Do not expose private configurations or backup credentials in terminal output.

The temporary `qa/chat_reliability/preflight.py` runner was removed during cleanup. Its read-only deployment checklist remains applicable: verify the exact database, addon path, file/database versions, source/account UUID mapping, company/branch scope, feature flags, source cutoff, service identity and bridge membership through existing administrative tools. Record the reviewed inventory privately. Do not change flags or rewrite mappings merely to make a check pass. Any expected old-version mismatch must be resolved only through the intended targeted upgrade.

In the intended gateway environment, verify the deployed app files and
`requirements.lock` hashes against the package manifest, and privately compare
`website_database`, HTTPS website origin, provider source UUID, receiver database,
account code and existing enablement/sending flags with this inventory. Run:

```bash
"$GATEWAY_PYTHON" -m app.ops status --account "$ACCOUNT_CODE"
```

Run from the deployed gateway directory with its existing private configuration.
Unknown accounts fail before opening the queue. Counts, pending ages, uncertain
outcomes, Website backlog and reception health are account filtered. SQLite disk,
DB and WAL sizes remain storage-wide. Omitting `--account` retains existing output.
Do not migrate, import, retry or edit the live queue as part of preflight.

## Manual activation

After verified backups and file-path checks, install the receiver and gateway
packages first. Run the exact targeted receiver upgrade using the deployment's
reviewed absolute paths and database variables:

```bash
"$ODOO_PYTHON" "$ODOO_BIN" -c "$RECEIVER_CONFIG" -d "$RECEIVER_DB" \
  -u ab_crm_website --stop-after-init --no-http --workers=0 --max-cron-threads=0
```

Require the receiver inventory checks to pass, activate the packaged gateway app with its
existing configuration and manually restart only its intended services. Install
the source package and run:

```bash
"$ODOO_PYTHON" "$ODOO_BIN" -c "$SOURCE_CONFIG" -d "$SOURCE_DB" \
  -u ab_storefront_callcenter_adapter --stop-after-init --no-http \
  --workers=0 --max-cron-threads=0
```

Require the source inventory checks to pass. Manually restart only the intended source
service and refresh browser assets. Never use `-u base`. Do not automatically
activate accounts or change cutoff, operator, membership or stock settings.

## Acceptance and diagnosis

Use approved new eligible orders after the preserved cutoff. Confirm order intake
before its chat/lifecycle events, exact-once delivery and destination ownership.
Use two Callcenter tabs while incoming messages arrive and read acknowledgements
run. Confirm separate employee preferences for shared logins, no preference popup,
read positions never decreasing, draft preservation, guest/account chat, image and
document round trips, and recovery after an approved connectivity interruption.
Native order chatter must remain available during a Callcenter outage.

A bridge fault must leave capabilities, queued fetches, incoming media download
and acknowledgements working. New replies, outbound media and operator selection
must reject; exact previously accepted replies/media retain receipts. Restore
membership or activity only through the normal authorized configuration workflow.
Logs identify `account`, `phase`, protocol `version`, HTTP `status` when available
and classified `cause`, without exception text, credentials or message bodies.

An order before the preserved cutoff is historically excluded, not a delivery
failure. An eligible new order with pending events is a delivery investigation:
check the account mapping, flags, queue age and classified transport phase. Never
reset acknowledgements or replay old comments to diagnose a new-order failure.

## Rollback

Manually stop the intended source and gateway delivery first. Restore the previous
verified addon and gateway packages, keeping their private configurations and queue
intact. These patches add no schema, migration or hook. Run the same targeted
upgrades against the restored packages, source first then receiver, and verify
previous file/database versions and mappings before restarting receiver/gateway,
then source. Do not run the new-version preflight unchanged against old packages.

Preserve queue IDs, fingerprints, receipts and cutoff. Do not restore an older live
queue or replay acknowledged events. If a database/filestore restore is necessary,
use the paired backups under a separately approved recovery procedure that
reconciles events accepted after the backup. Do not silently discard those events.
