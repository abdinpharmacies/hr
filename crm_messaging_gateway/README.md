> Gateway 1.5.0 WhatsApp reception, contact cards and media: see [the reception rollout and validation record](../docs/whatsapp-reception-rollout.md). Earlier capability descriptions below describe previous releases.

> For the callcenter PostgreSQL deployment, use [the current dual-channel runbook](../docs/omnichannel-callcenter-runbook.md). SQLite instructions below describe an optional deployment, not a migration requirement. Per-account sending and dedicated WhatsApp Odoo credentials are described in that runbook.

# CRM messaging integration

SQLite storage, consistent backups and the optional WhatsApp Chatter bridge are documented in [SQLITE.md](SQLITE.md). PostgreSQL remains supported for compatibility and controlled migration.

For the callcenter Telegram polling pilot, use [DEVELOPMENT.md](DEVELOPMENT.md). It documents the versioned controller, masked local setup, literal-loopback HTTP exception and supervised receiver. The webhook instructions below are an alternative deployment mode; polling needs no public hostname or tunnel.

New Odoo 19 addons `ab_crm_messaging`, `ab_crm_whatsapp`, and `ab_crm_telegram` extend `ab_crm_core`. This service does not import the earlier gateway or OMS adapters and has no OMS submission worker. Everything ships disabled. Public webhook registration and real provider sends require explicit activation authorization.

## Delivery contract

- Each account has a unique code, provider identity, CRM channel, branch, company and dedicated service user. The gateway code and identity must exactly match Odoo. A channel belongs to one account. Mapping is immutable; archive instead of deleting.
- Give the service user **Internal User** and **Messaging Service Account**, with only the required companies, and add it to the branch's authorized users. Do not assign CRM Staff, Manager, Settings, or the previous gateway role. The API rejects mixed staff/service roles. Module-owned global rules deny messaging service users direct CRM access even if an extra ACL is accidentally granted. API methods validate the account before scoped elevation. Use one gateway process/config per service user and its account set.
- JSON-2 uses a service-user API key (`rpc` scope), `Authorization: Bearer`, and `X-Odoo-Database`. The model is `ab_crm_messaging_api`: `receive_event`, `lease_outgoing`, `acknowledge_receipt`, `authorize_send`, `report_delivery`, `receive_status`. No API accepts a staff actor or branch from the incoming event. Provider secrets never enter Odoo.
- Incoming events are committed to the gateway database before HTTP 200. Account plus event/update identity is unique, with a canonical content digest. A conflicting reuse returns 409. Odoo independently deduplicates normalized message identities. Existing identity links are consulted only inside the exact channel; no automatic customer merging occurs.
- Only Telegram `message` updates in private chats are handled. Group/channel/edited/service updates are recorded as ignored. Attachments produce a translated staff-review notice without fetching files.
- Staff approval and the immutable outgoing snapshot commit together. Actor, timestamp, body, destination and token are preserved. Core delivery becomes `unknown` while the new operation tracks queued/leased/received/accepted/delivered/read/failed/review. This also prevents the old worker from taking newly approved messages; the previous worker must still remain inactive for pilot channels.
- An Odoo lease expires after two minutes until a durable gateway receipt is acknowledged. The gateway deduplicates `(account, token, attempt)`; lease renewal never changes the snapshot. A crash between Odoo receipt acknowledgment and local readiness is recovered by replaying the receipt. One PostgreSQL `SKIP LOCKED` claim wins each operation.
- The worker commits a `sending` marker before provider HTTP. A crash after that point or an uncertain transport/server response becomes review, never an automatic resend. A late provider result after recovery cannot replace the durable review marker. A reviewer can close a review with a note; retry is unavailable for ambiguous sends. Inspect provider records before deciding whether a separately approved new message is appropriate.
- Only connect failures before submission and explicit 429 rejection are retried automatically, at most five sends. Other 4xx errors are definitive rejection, while 408, 5xx and malformed acceptance evidence are uncertain. Rate-limit delay is honored up to 24 hours. An exhausted definitive retryable failure can be retried by authorized staff with an incremented attempt, preserving approval and payload. Unknown outcomes cannot use that action.
- Provider acceptance is distinct from delivery/read. WhatsApp callbacks advance states without allowing older callbacks to regress delivered/read. Early unmatched callbacks retry and eventually enter review. Telegram stops at provider acceptance and never claims delivery/read.
- WhatsApp free-form replies need an inbound customer message within 24 hours; both approval and dispatch check the window, with a 30-second safety margin. Expired queued replies are failed rather than sent. No templates, campaigns, attachments, broadcasts, or AI replies are implemented.

## Prepare deployment (do not activate implicitly)

1. Back up the authorized Odoo deployment and install the new addons from this checkout. Keep the previous gateway worker inactive for pilot channels, including any old queued approved replies. Review those replies separately before switching. Do not modify the existing CRM records to simulate provider receipts.
2. Provision a dedicated Linux user and PostgreSQL role/database for the gateway, without access to Odoo's database. For example, under the PostgreSQL administrator, run `createuser --pwprompt crm_messaging` and `createdb --owner=crm_messaging crm_messaging`. Enter passwords privately. No external B-Connect/E-Plus database access is used.
3. Place this service at `/opt/crm-messaging`. Create a Python 3.12 virtual environment there, then run `venv/bin/pip install -r requirements.lock`. The lock contains the tested dependency versions. CI additionally installs `requirements-dev.txt`.
4. Copy `deploy/config.example.json` to `/etc/crm-messaging/config.json`, replace all placeholders through protected host configuration, set owner `crm-messaging:crm-messaging` and mode `0600`. The loader refuses group/world-readable configuration. Configure an HTTPS Odoo origin (or the explicit literal-loopback development exception in the runbook); redirects are not followed. Never paste tokens into chat, command arguments, logs or source control. Confirm the selected Meta Graph version is supported for the provisioned app.
5. With `CRM_MESSAGING_CONFIG=/etc/crm-messaging/config.json`, run `venv/bin/python -m app.ops migrate`. This idempotent version-1 migration creates only gateway tables. It never touches the Odoo database. Keep PostgreSQL `synchronous_commit` enabled and back up this database with Odoo: losing a durable receipt database after acknowledging it requires operator reconciliation, not automatic resend.
6. Create Odoo accounts under CRM / OMS → Messaging Accounts, explicitly selecting the existing channel/branch/company and service user. Leave **Messaging Enabled** off. Check **Previous Worker Disabled** only after verifying that the old consumer is inactive. Configure the same account codes and provider IDs in the gateway.
7. Check `ss -ltnp` before choosing the loopback port. The supplied unit binds `127.0.0.1:5088`; adjust if occupied. Preserve Odoo ports 4091, 4092 and 4095. Copy the service units only during authorized deployment, run `systemctl daemon-reload`, then start the webhook and worker services when authorized. No unit is installed or enabled by the source checkout.
8. Adapt `deploy/nginx.conf` to the approved hostname/certificate and validate with `nginx -t` before an authorized reload. Only `/webhooks/` is public; `/health` stays local. Disable request-body and authorization-header logging in all proxies/APM. The supplied access log is disabled to avoid recording WhatsApp verification tokens in query strings. Limit firewall exposure to HTTPS; PostgreSQL and port 5088 remain private.

For a targeted Odoo install on an authorized database, select the correct config and DB and use:

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin \
  -c /path/to/authorized.conf -d authorized_database \
  -i ab_crm_whatsapp,ab_crm_telegram --stop-after-init \
  --http-port=5069 --gevent-port=5072 --workers=0 --max-cron-threads=0
```

Do not stop the user's PyCharm server or use `-u base`. Alternate ports do not isolate database writes. For repeat upgrades use `-u ab_crm_messaging,ab_crm_whatsapp,ab_crm_telegram` only on the authorized database.

## Authorized onboarding and pilot

Obtain hostname, certificate, WhatsApp test phone-number ID/app secret/access token, Telegram bot ID/token, random webhook secrets, and explicit branch mappings through protected configuration. Credentials are deployment inputs and are not included here.

After explicit authorization:

1. Enable the selected account in protected gateway config and restart only these gateway units. Enable the mapped Odoo account after verifying the previous worker is inactive. Keep `sending_enabled=false` until outbound testing is approved.
2. In Meta, register `https://HOST/webhooks/whatsapp/ACCOUNT_CODE`, set the matching verification token, and subscribe the app/WABA to `messages`. Verification uses the GET challenge; POSTs require HMAC-SHA256 over the original request bytes using the app secret. The phone-number ID in every batch must match the configured account. Use one registered callback/account route per pilot phone number; this release rejects mixed-number batches rather than guessing a mapping.
3. For Telegram call the official `setWebhook` method from a protected administration tool with URL `https://HOST/webhooks/telegram/ACCOUNT_CODE`, `secret_token` equal to the configured webhook secret and `allowed_updates=["message"]`. Do not put the bot token on a command line. Leave `drop_pending_updates=false` unless separately authorized to discard pending messages. Verify `getWebhookInfo`, and ensure the dedicated bot is not used by the prior gateway or any polling receiver.
4. Send one private customer text to each pilot account. Confirm exactly one incoming CRM message in the intended branch/company. Replay the same signed webhook; the CRM count must remain one. Attempt a wrong signature and wrong account mapping; each must be rejected.
5. Staff drafts and approves a reply. Enable gateway `sending_enabled` only after approval for pilot sending, restart only this worker, then verify the immutable operation reaches provider acceptance with the provider reference. For WhatsApp verify actual delivered/read callbacks when available. For Telegram compare the bot API message ID and recipient chat; do not expect read receipts.
6. Pause the gateway `sending_enabled` flag or disable the Odoo account if pilot checks fail. Keep durable queues intact. Do not reset uncertain operations or invoke another sender against the same messages.

## Operations and verification

Run `python -m app.ops review` in the service directory with the protected config to list queue IDs and sanitized error codes, without message content. Correct the outage/mapping, then use `python -m app.ops retry-incoming --event-id ID --note 'Reason for retry'` for a reviewed incoming event. This records the local operator and timestamp. Outgoing review and authorized retry are in CRM / OMS → Messaging Delivery. No CLI action resends an uncertain operation.

Incoming delivery retries are bounded to eight claims with exponential backoff, then review. Report delivery evidence retries persistently because provider submission must never be repeated just because Odoo is down. Alert on review count, oldest pending event, unreported outcomes, or stored receipts that do not progress. Logs contain operation IDs and sanitized categories, not tokens, destinations or bodies. Database payloads contain customer text; restrict database/backups to authorized operators and apply the organization's retention policy without deleting CRM business history.

Tests:

```bash
MESSAGING_TEST_DSN_FILE=/private/path/to/test-dsn \
  python -m pytest tests -q
```

The DSN file must name an isolated PostgreSQL database containing `test` in its name; storage tests truncate only the new messaging queue tables in that database. Without it, PostgreSQL tests are explicitly skipped. All provider calls are mocked. Odoo tests run with `--test-tags=/ab_crm_messaging` after installing both provider addons on an isolated development database. See `VALIDATION.md` for the executed checks and remaining live-pilot prerequisites.

Production addon archives must omit `tests`, caches and development fixtures. Retain service migrations, runtime code, deployment templates and the dependency lock. Do not include protected configuration, databases, logs or keys in archives.

## Provider references checked during implementation

- [WhatsApp Business Messaging Policy](https://business.whatsapp.com/policy): customer messages open/reset the 24-hour window; templates are needed outside it. The policy was accessible on 2026-11-03; current developer send/webhook pages returned HTTP 429.
- [Meta's WhatsApp SDK webhook reference](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/webhooks/start/): signature validation and rejection behavior. This is reference material, not a runtime dependency.
- [Telegram Bot API: setWebhook](https://core.telegram.org/bots/api#setwebhook) and [sendMessage](https://core.telegram.org/bots/api#sendmessage): secret-token header, update delivery and message acceptance.

## Telegram Sales Operations contact sharing

Telegram private contact updates now retain the sender and contact user IDs separately. Odoo verifies ownership before phone matching. Message identities include chat ID and message ID, because Telegram message IDs are scoped to chats. Contact prompts use the same durable queue and uncertain-send handling as ordinary approved replies.

`python -m app.telegram_setup ACCOUNT` verifies the configured bot identity and inspects webhook status without registering or removing a webhook. The same helper accepts `--webhook-url HTTPS_URL --activate` only after explicit operator activation approval, verifies identity first, and preserves pending updates. It reads the existing protected `CRM_MESSAGING_CONFIG`; it does not create another credential directory or send customer messages. Provider HTTP errors are sanitized.

Canonical WhatsApp history remains owned by `ab_whatsapp_api`. The optional `ab_crm_whatsapp_workspace` bridge queues both entry points only for explicitly migrated accounts. See [SQLite migration and WhatsApp integration](SQLITE.md); production cutover and webhook activation remain separate.

## Odoo-managed Telegram token

With Sales Chatter installed, save the bot token directly in **Settings → Technical → Parameters → System Parameters**, then use **Sales → Configurations → Telegram Connection** to prepare the disabled connection. No token field is provided outside System Parameters. Set the Telegram account to `token_source: "odoo"` and omit `token` from gateway JSON. The gateway authenticates with its dedicated Odoo key and retrieves only that account token at startup. Credentials remain in memory; restart supervised workers after rotation. `app.local_setup --from-odoo` prepares this mode and verifies `getMe` without copying the fetched token into the protected config. See [DEVELOPMENT.md](DEVELOPMENT.md) for the callcenter setup and remaining queue/reload/activation steps.


## Media and voice prerequisites

The independent worker downloads incoming Telegram media after the message and provider reference are committed in Odoo. The receiver only persists metadata. Private media stays in authorized CRM records; no public attachment URL is created. Images are limited to 10 MB, other supported files to 20 MB, and recordings to five minutes.

Install the operating system `ffmpeg` package on the worker host before enabling audio/voice sending. The worker uses `ffprobe` to verify actual duration and `ffmpeg` to convert recordings to Ogg/Opus. Missing tools or invalid recordings produce a definitive local rejection before provider submission. The web recorder never sends automatically.

Outgoing Telegram requires both the Odoo account's **Outgoing Sending Enabled** and the gateway's `sending_enabled`. **Automatic Contact Request** is a separate, default-off Odoo account option. Receiving remains independent of these outbound controls. Keep all outbound switches off until the separately approved pilot.

The embedded Chatter composer can queue outgoing MP4 video through Telegram `sendVideo`. This shares the existing bounded video validation with WhatsApp: up to 16 MB, H.264 video and optional AAC audio. The worker's FFmpeg package (`ffprobe`) is required for video validation as well as audio processing. Invalid or unsupported video fails locally before submission. Location menu entries insert an ordinary map link into the draft; there is no new gateway location operation.

## Telegram branch venues

Gateway 1.3.0 accepts optional outgoing `location` containing only `latitude`,
`longitude`, `name` and `address`. It sends one native Telegram `sendVenue`
request, preserving reply parameters and the existing durable receipt/retry
workflow. Location content cannot be combined with media, reactions, contact
buttons or templates. WhatsApp location sending is rejected.

`accounts.<code>.location_enabled` defaults to `false`. Upgrade Odoo consumers
(`ab_crm_messaging` 19.0.1.6.0 and `ab_crm_sales_workspace` 19.0.1.13.0) first,
then deploy the gateway. During a separately authorized rollout, enable this
flag and the matching Odoo account's **Telegram Branch Locations Enabled**.
Existing global/account sending gates remain required. Until both sides are
ready, keep location sending disabled. No webhook setup is required by this
feature. See `docs/telegram-branch-location-validation.md` in the repository root.

### Reception health and historical receipt reconciliation

`python -m app.ops status` retains its existing fields and adds `reception_health`,
keyed by configured account. Enabled Telegram polling becomes unhealthy when its
heartbeat is missing or older than 120 seconds. This is independent of HTTP
liveness and queue readiness. Per-account backlog age covers unfinished inbound
messages and status receipts.

The existing Telegram receiver preserves its offset and exclusive lock. Temporary
network/provider/queue failures back off up to eight attempts and exit 75 for
systemd recovery. Invalid credentials, ownership conflicts, active webhooks and
malformed events stop explicitly; diagnostics omit provider responses and tokens.
No webhook is automatically removed and no second poller is started.

After deploying the WhatsApp companion, preview explicitly selected historical
status events (the command does not collect or dispatch outgoing operations):

```sh
python -m app.reconcile wa-callcenter --event-id 101 --event-id 102
python -m app.reconcile wa-callcenter --event-id 101 --event-id 102 --apply retry --digest PREVIEW_DIGEST --note 'Verified unique historical outgoing matches'
python -m app.reconcile wa-callcenter --event-id 103 --apply ignore --digest PREVIEW_DIGEST --note 'Confirmed orphan after historical and operation lookup'
```

Use the IDs from the reviewed queue, not these examples. A preview digest binds
account, event IDs, fingerprints, queue states and current Odoo match results.
Only unique verified historical/operation matches can be retried. Only confirmed
orphans can be ignored; ambiguous and unverified records remain for review.
Application rechecks the preview and records actor, action, reason and digest in
`operator_audit`. Payloads and fingerprints are preserved. Normal unmatched new
callbacks keep their existing bounded retry/review behavior. Queue ordering
continues to serialize receipts for each account, destination and reference.

### WhatsApp branch locations

Gateway 1.7.0 supports native WhatsApp branch locations through the same durable
queue as replies. Enable **Branch Locations Enabled** on the authorized Odoo
account and `location_enabled` on its matching gateway account. Existing sending
gates and the WhatsApp reply window still apply. Reviewed branch snapshots remain
immutable and uncertain deliveries require review. See
[the update record](../docs/simple-notifications-whatsapp-locations.md).

### Recording codecs and contact extensions

Install the distribution `ffmpeg` package so both `ffmpeg` and `ffprobe` are
available to the gateway worker. Audio/video validation uses restricted file/pipe
protocols and bounded subprocess timeouts. Missing tools leave incoming media in
the retry/review path and prevent outgoing provider calls; they are not treated
as proof of malformed customer content. Supported audio sent as a WhatsApp
document is normalized as audio.

Native shared contacts are projected onto the supported contact fields before
validation. Extra top-level provider metadata is ignored; supported-field types
and size limits remain enforced. The original provider message digest is retained.
Rejected contact callbacks log only fixed schema categories, never contact values.
See [the recovery record](../docs/whatsapp-contact-audio-recovery.md).

## Read receipts and animation attachments

Gateway 1.8.0 adds a separate durable read-receipt result table for PostgreSQL and
SQLite. Run the existing `python -m app.ops migrate` command during rollout before
restarting the worker. Odoo's administrator-only account setting defaults off;
the gateway's global sending switch also gates read-receipt delivery.

Telegram animation metadata takes precedence over duplicate documents. GIFs use
`sendAnimation`; WhatsApp GIFs are converted to silent H.264 MP4 before video
upload. Retain `ffprobe`, `ffmpeg`, and H.264 encoding support in the service
environment. Missing media codecs defer incoming events without exhausting retries.
The original GIF stays in Odoo; captions and reply references stay on the normal
outgoing operation. See the [implementation, validation and rollout report](../docs/read-receipts-channel-loading-animations.md).

## Website adapter and scoped workers

The optional Website transport runs with `python -m app.website`. Its Odoo companions capture confirmed website orders and supply text chat without using the customer API. See [Website adapter setup and rollout](../docs/website-callcenter-adapter.md).

Use `python -m app.worker --provider telegram` and `--provider whatsapp` for separate durable provider workers. Incoming claims, expired-send recovery, stored receipts and delivery reporting are filtered by assigned accounts on PostgreSQL and SQLite. Replace the previous shared worker before enabling these service templates; keep one Telegram receiver per bot. HTTP/Uvicorn workers remain independent of channel workers. Existing ambiguous-send review behavior is preserved.

Website chat v2 is delivered by the existing dedicated Website worker alongside v1 order events. The consumer must support `receive_website_chat` and `/crm/website/v2/receive`; the source exposes `/storefront-callcenter/v2/fetch`, `acknowledge` and `receive`. Replies require a frozen `website_destination` with `kind` (`order` or `livechat`) and a canonical UUID. Historical untyped replies are never sent. Source/account queues and credentials remain separate. See `../docs/website-chat-rollout.md` for activation and rollback.

When a source returns 404 for the v2 chat fetch, the worker keeps v1 intake running and stops probing that source for v2 until its next restart. Restart the Website worker after upgrading an older source to enable chat there. Other source accounts keep their own capability state.

Website recovery and verified identity are described in `docs/website-reliable-conversations.md` in the callcenter checkout. Version 3 producers require the receiver and gateway upgrade first; the endpoint lifecycle switch defaults to disabled. Pending sends retain their original UUID and destination. A website acknowledgement proves acceptance, never customer reading.


### Website media exchange v4

Website messages may carry up to four private files of 20 MB each. The queue stores immutable descriptors (stable ID, name, MIME type, byte length, SHA-256 digest, kind and available recording duration). Incoming bytes stream from the authenticated storefront media endpoint and upload to callcenter staging before the message is received. Acknowledgement follows durable storage of every attachment and the complete message. Partial uploads are safe to retry.

Outgoing files use authenticated binary uploads before the small v4 receive request. The submission token, destination and complete descriptor list protect retries; an unsupported peer produces a media review result. Text-only v1/v2 and lifecycle v3 remain independent. Upgrade both adapters and this worker together, validate the round trip, then enable the storefront endpoint's v4 media flag. This change does not activate endpoints or restart services.

## Bounded backlog cycles and website account isolation

Workers now report completed progress and schedule at most 25 operations or
250 ms between operations before yielding. A blocking network operation retains
its existing timeout; the quantum does not preempt an in-flight send. Eligible
work continues immediately. Idle messaging/website loops retain their respective
one/two-second waits and existing failure backoff. Stored receipts and delivery
reports rotate through their current bounded windows after a failure.

Run website workers with repeated `--account CODE` arguments to select enabled
website accounts explicitly. Unknown, disabled, duplicate and non-website account
codes fail validation. The pilot and production `crm-messaging-website-*@.service`
templates use separate private configuration files and conflict for the same
instance. They are prepared templates, not installed/enabled services. Do not run
one alongside an existing worker owning the same accounts. Both configurations
retain the current storage backend, protocol and scoped credentials; they do not
establish PostgreSQL independence. Validate disjoint account ownership before
any separately approved rollout.
