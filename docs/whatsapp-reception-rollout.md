> Historical feature and validation record. The [2026-11-11 retirement report](messaging-legacy-retirement.md) records the completed rollout and supersedes earlier pending-maintenance and historical-receipt backlog statements below.

# WhatsApp reception, contacts and templates — 2026-11-09

Source versions: CRM Messaging 19.0.1.9.0, Sales Chatter 19.0.1.16.0,
WhatsApp Sales Chatter 19.0.1.4.0, gateway 1.5.0.

## Delivered behavior

- Signed WhatsApp events retain profile display names, captions, reply references,
  provider timestamps and original message types. Images (including WebP sent as
  image/document), WebP stickers, documents, audio/voice, video, reactions and
  multiple shared contact cards use the durable incoming workflow.
- Media retrieval requests a fresh authenticated Meta URL for each attempt,
  constrains the request to the sender phone-number ID, validates the download
  host, MIME, size, digest and content, and does not follow redirects. The worker
  probes audio/video duration and codecs. Limits: 5 MB images, 16 MB audio/video,
  20 MB documents, five minutes for audio/video; stickers 100 KB static/500 KB
  animated. Original bytes remain in private CRM media behind authorized routes.
- Pending, failed and unsupported events remain distinguishable. Failures retain
  a diagnostic category; HTTP retrieval retries use the existing eight-attempt
  incoming queue bound. Legacy unsupported digests cannot reconstruct lost
  attachments: resend those examples after rollout.
- Incoming reactions render on their target, with deterministic provider-time
  ordering, replacement/removal and replay deduplication. Reaction events do not
  become separate message alerts. Contact cards never identify or rename senders;
  their Create contact button is an explicit, separate save action.
- Saved human names take precedence over catalog/provider names and valid phones.
  Editing the active saved contact pre-fills effective details and keeps the
  selected conversation. Contact edits retain existing audit records and do not
  write external catalog records. Shared customer streams retain channel-specific
  drafts, reply targets, attachments, history and unread counts.
- Agents may preview/confirm only a unique verified-phone match with no previous
  ownership conflict, in their authorized branch/company. Managers may review
  ambiguous matches and explicitly resolve ownership conflicts. Both roles use
  the existing fingerprint confirmation and audit workflow.
- Saved replies insert ordinary editable text. WhatsApp templates display all
  approved languages, with a language filter. Manager/admin refresh verifies
  sender membership in the configured WABA and atomically synchronizes the full
  inventory. Failed refreshes retain the previous inventory and a visible error;
  removed/unapproved records remain historical. Manual inventory reassignment is
  blocked. Unsupported layouts explain why sending is unavailable. Queued sends
  recheck approval and ownership.
- Existing Telegram credentials, configuration, polling and provider-send code
  are unchanged. The original sender-branch dispatch fix remains present.

## Verified evidence

Evidence directory: `/tmp/whatsapp-reception-validation/`.

- Gateway suite: 191 passed, one skipped. The skip is the existing real audio
  conversion test: FFmpeg/ffprobe are not installed in this environment. Codec
  and duration rejection tests use mocked probes; real codec acceptance remains
  a deployment prerequisite.
- Combined isolated Odoo workspace suite: 121 tests, zero failures/errors.
  Final focused WhatsApp bridge suite after inventory protection: 32 tests,
  zero failures/errors. Final focused link-lock checks: 2 tests, zero failures/errors (`link-final.log`).
- Final desktop browser suite: 59 tests / 351 assertions. Mobile channel suite:
  10 tests / 40 assertions. Both passed; the full browser driver additionally
  exercised an actual 390×844 mobile viewport.
- Full synthetic UI: English contact edit, saved-name persistence, separate
  channel drafts, private WebP thumbnail, contact-card fields, target reaction,
  both reply menus and all template languages. Arabic contact editing retained
  the active WhatsApp conversation and the edited name after reload; 390×844 RTL
  had no horizontal overflow or page error. Screenshots are in the evidence
  directory. Translation metadata corrections were checked through Odoo's code
  translation loaders for both `ar` and `ar_001`; existing translations retained.
- Databases: `callcenter_whatsapp_dispatch_test_20261109` for regressions and
  neutralized `callcenter_whatsapp_reception_ui_test_20261109` for synthetic UI.
  Temporary ports: 5069/5072 and 5085/5086, zero workers/cron threads. The copied
  fixture database has missing legacy avatar files; generated web assets were
  rebuilt only in isolated databases. All temporary servers were stopped and
  ports released. Live Odoo remained PID 303232; the Telegram polling receiver
  remained PID 156203. No live data, provider messages or service configuration
  changed during this source verification.

## Runtime rollout sequence

The source checks do not establish live Meta delivery or authorize bypassing the
user-managed Odoo maintenance window.

1. Keep the Telegram polling receiver running. Verify runtime paths and back up
   the `callcenter` database/filestore, gateway queue database and protected
   configuration, plus source versions. Store backups privately; never print
   credentials. Preserve operation IDs, receipts and history.
2. Verify FFmpeg/ffprobe availability for the gateway service user. Install the
   approved system package if absent, then validate real Ogg/Opus and H.264/AAC
   samples before declaring voice/video acceptance.
3. During the user-managed maintenance window, target only
   `ab_crm_messaging,ab_crm_sales_workspace,ab_crm_whatsapp_workspace` for upgrade,
   using alternate ports and `--stop-after-init`. Never use `-u base`, and never
   stop/restart the user's PyCharm process. The user resumes it after upgrade.
4. Deploy the compatible receiver/worker source after Odoo is upgraded. Reload
   only the required WhatsApp webhook process and shared delivery worker; do not
   restart or reconfigure the dedicated Telegram polling receiver. Do not change
   Telegram flags, credentials or sending policy. Preserve all queues.
5. Use Refresh WhatsApp Templates on the authorized WhatsApp account. Confirm
   sender/WABA ownership, successful timestamp, and approved `apology_unavailable`
   (Arabic) and `hello_world` (English), if still approved by Meta. Do not submit
   saved replies to Meta or create new templates.
6. For the reported test identities, preview the link against the saved contact
   using their verified normalized phone; confirm the exact fingerprint and an
   audit reason. Do not rename the contact without the agent's chosen name.
7. Restrict live provider tests to **+201014763233**. Resend supported inbound
   types, static/animated WebP, multiple cards, reply/caption examples and successive
   reactions including removal. Verify one CRM/history projection per event,
   authorized downloads, ordinary queued replies and one suitable approved
   template. Inspect queue attempts, receipts and delivered/read status.
8. Hard-refresh clients after the asset/translation upgrade. Check English and
   Arabic contact editing, switching, independent drafts/replies and media preview.

## Rollback

Disable only the changed WhatsApp reception/sending gates if acceptance fails;
retain raw events, media, history, receipts and queue evidence. Restore the prior
compatible source package with the dispatch fix preserved. Do not delete new
history, reset uncertain operations, enable legacy direct sending, or downgrade
schema by deleting fields/data. Reconcile an in-flight provider operation before
any separately approved retry. Telegram polling/configuration remain unchanged.
