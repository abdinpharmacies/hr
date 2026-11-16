# Read receipts, channel loading and animation attachments

Source: `callcenter19`, 2026-11-11. Existing uncommitted contact, notification and branch-location work is preserved. Versions: CRM Messaging `19.0.1.12.0`, Sales Chatter `19.0.1.29.0`, WhatsApp Sales Chatter `19.0.1.9.0`, gateway `1.8.0`.

## Behavior

An administrator can enable **Send WhatsApp Read Receipts** on an account; it defaults off. The existing focused, visible, non-history conversation acknowledgement queues the latest eligible inbound reference through the visible position. Employee/session, conversation, account, branch and company validation happens before elevation. Historical imports and references older than 30 days are excluded. There is no historical backfill. `workspace_acknowledge` still returns `True` and local unread positions are independent of provider acceptance.

Odoo owns the durable `ab_crm_read_receipt` outbox. A unique account/message pair deduplicates staff/tab reads. Authenticated `lease_read_receipt` and `report_read_receipt` endpoints reuse the dedicated service-account authorization. Two-minute leases fence stale results. Temporary failures back off until provider eligibility expires. Accepted receipts retain their acceptance timestamp. The gateway's separate `read_receipt` table persists terminal results in PostgreSQL or SQLite, so an Odoo reporting outage does not resend an accepted receipt after restart. A crash before recording provider success can repeat a read-status call; setting read status is idempotent. The global gateway sending switch also gates read-receipt delivery. Telegram read behavior is unchanged.

The provider contract uses Meta's [read-status endpoint](https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/mark-message-as-read). Read status is cumulative in the conversation, so the workflow queues the latest eligible visible reference rather than one operation per historical message. Already-issued read receipts cannot be undone.

Navigation uses its own loading flag and request generation. The old conversation retains its channel while loading, with composition and read acknowledgement disabled. Failures clear the flag and preserve the draft for retry. Superseded and replaced-session responses are ignored. History actions cannot invalidate a pending switch. Initial refresh does not immediately reload the same conversation; unchanged periodic refreshes avoid the redundant full detail request. Media and quoted-image loading do not block initial rendering. No persistent conversation cache was added.

Telegram's [animation field](https://core.telegram.org/bots/api#animation) wins over its duplicate document representation. GIFs, including documents with a missing MIME and `.gif` name, use the image path; MP4 animations use the shared video path. Outgoing GIFs use `sendAnimation`. WhatsApp converts outgoing GIFs to silent H.264/yuv420p MP4, preserves caption/reply targeting, and uses video dispatch. Odoo retains the original GIF. WhatsApp incoming animations and animated WebP stickers keep their video/sticker paths. GIF previews animate; MP4 and WebM previews use browser controls; TGS remains an original download.

GIF inputs are limited to 10 MB and video inputs/converted WhatsApp outputs to 16 MB. Existing non-GIF WhatsApp image limits remain 5 MB. Duration is limited to five minutes. Validation checks actual formats, dimensions and codecs; animation work has frame/pixel limits, subprocess timeouts, a memory-allocation cap and single-thread conversion. Missing gateway tools/codecs defer incoming work without exhausting retries. Odoo requires Pillow and `ffprobe`; the gateway requires `ffprobe`, `ffmpeg`, and H.264 encoding support.

## Validation evidence

Artifacts and private synthetic fixtures: `/tmp/callcenter-read-animation/`. These paths are local validation artifacts, not part of the runtime archive.

- Gateway regression: 265 passed, no skips, with PostgreSQL and SQLite. Includes actual GIF conversion, mocked Telegram/WhatsApp provider requests, captions/replies, duplicate metadata, unavailable codecs, receipt recovery and export/restore.
- Shared messaging: 31 tests, zero failures/errors in `callcenter_retirement_core_test`, without the WhatsApp companion.
- Final clean install and targeted workspace upgrade: **151 tests, zero failures/errors** in `callcenter_animation_final_test_20261111`. Browser suites: **77 workspace tests**, **13 WhatsApp desktop tests**, and **13 WhatsApp mobile tests**. The combined desktop run includes the workspace tests; these overlapping counts are not additional Odoo server tests. No `-u base` or live database upgrade was used.
- Concurrency: eight reads from two employees produced one receipt; four workers obtained one lease. Expired leases recovered and stale results were rejected. Only synthetic records were used; no provider request ran.
- Runtime labels: `Send WhatsApp Read Receipts` in English and `إرسال إيصالات قراءة واتساب` under both `ar` and `ar_001`.
- English/Arabic desktop/mobile browser checks: GIF loaded through the private download API; MP4 preview had controls, decoded dimensions and duration. Arabic used RTL and the 390-pixel mobile view had no page overflow. Screenshots are under the artifact directory.

### Local warm-switch measurements

The same isolated database contained one linked contact, two channels and 30 text messages per channel. Each direction was measured 32 times; the first two were warm-up and the remaining 30 form each result. Browser timing runs from the channel-button click through two animation frames after the destination message list renders. Background refresh remained enabled. Before used the pre-change navigation sources in a temporary addon directory; after used the implemented source. No customer traffic or persistent chat cache was involved.

| Direction | Before median | After median | Before p95 | After p95 |
| --- | ---: | ---: | ---: | ---: |
| Telegram → WhatsApp | 683 ms | 367 ms | 783 ms | 431 ms |
| WhatsApp → Telegram | 350 ms | 350 ms | 468 ms | 434 ms |

HTTP server logs for the same 30 requests per direction show median query counts of **413 → 204** into WhatsApp and **199 → 193** into Telegram. Median SQL time was **262 → 126 ms** and **123 → 123 ms**, respectively. Median total server time was **606 → 298 ms** and **288 → 287 ms**. The main WhatsApp improvement removes repeated reaction-reference searches and uses prefetched authorized message history. Remaining work includes session/branch authorization, unread calculations, contact projection and rendering. These are local synthetic warm timings, not a production latency guarantee or a remote-network benchmark.

Raw browser samples: `browser-before.json` and `browser-after.json`; request/query evidence: `baseline-server.log` and `final-server.log`. The separate `server-profile.json` compares just the channel-lookup paths inside a warm ORM transaction and is not interchangeable with the end-to-end measurements.

## Staged rollout

The runtime archive excludes tests, test asset declarations, caches and private configuration. No live account setting has been enabled by this task and no messaging service or user-managed Odoo process has been restarted. A supplemental repeat of the already-passing core-only suite was not executed: automatic approval review failed because its authentication refresh token was revoked. This was an approval-service failure, not an unsafe-action determination. Restore approval access before privileged rollout commands. The earlier 31-test core result and final 151-test workspace result remain the executed evidence.

During the user-managed maintenance window:

1. Have the user stop their Callcenter Odoo process. Confirm the configured addons path is this checkout and the database is `callcenter`. Do not stop the user's process automatically.
2. Back up Odoo, its filestore, private configuration and the queue into a private directory. Preserve the current Telegram polling offsets and receiver ownership. Refresh backups at the actual window; old copies are not a cutover snapshot.
3. Apply only the targeted Odoo upgrade: `-u ab_crm_messaging,ab_crm_sales_workspace,ab_crm_whatsapp_workspace --stop-after-init --http-port=5069 --gevent-port=5072 --workers=0 --max-cron-threads=0`. Check port occupancy first.
4. Run `python -m app.ops migrate` using the existing private gateway configuration and runtime interpreter. This adds the durable receipt table without deleting queue state or changing polling offsets.
5. Verify media tools/H.264 support in the actual service environment. Enable the receipt setting only on the validated Callcenter WhatsApp account (`wa-callcenter`), checking its configured provider-account mapping, branch and company.
6. Restart only the affected messaging gateway, worker and Telegram receiver services, retaining the same queue and polling ownership. The user starts Odoo. Verify account capabilities, reception, queue health and private media download.
7. Ask the user to resend a GIF/animation to each channel and view the incoming WhatsApp message. Confirm provider receipt acceptance and client appearance. Any outgoing live message must be explicitly initiated by the user to their own account.

Past rejected Telegram events are preserved. They lack a retained downloadable file reference; verification requires a resend, not rewinding polling.

Rollback first disables the receipt setting and pauses affected messaging delivery during the window. Revert runtime code using the prior package while preserving attachments, receipt/outgoing queue rows and polling offsets. Do not uninstall the addons, reset offsets, delete history or replay uncertain outgoing sends. Already-accepted provider read status remains visible.
