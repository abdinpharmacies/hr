# Callcenter dual-channel runbook

Source preparation: 9 November 2026. This is the current operational reference for the PostgreSQL callcenter gateway and WhatsApp companion. Old planning handoffs and SQLite deployment instructions do not describe this deployment. Source readiness is separate from installation and live provider approval.

## Ownership and live-state boundaries

- Runtime source: `/opt/odoo19/worktrees/callcenter19`; Odoo database `callcenter`; user-managed HTTP `4092`.
- The separate PostgreSQL queue and gateway stay on loopback `5088`. Telegram retains polling and its existing account settings.
- `ab_whatsapp_api` retains canonical records, templates and its admin dashboard; its source is unchanged. Installing `ab_crm_whatsapp_workspace` returns HTTP 410 on both legacy webhook methods and refuses public ORM ingestion for every caller. Dashboard sends must queue or fail for every account. There is no direct-send fallback, including unprepared or archived accounts.
- `crm_messaging_gateway` owns signature verification, account routing, durable reception and the only live provider-send path. `/crm/messaging/v1/<operation>` remains the authenticated Odoo contract.
- Customer grouping does not merge conversations or change order destinations. OMS submission, invoicing, payment and stock remain outside this release.

## Prepared behavior

`workspace_customer_inbox(query='', offset=0, limit=50)` paginates customer/company/intake groups before expanding authorized streams. Unlinked conversations have individual group keys. Each stream supplies account/channel and unread counts; the frontend retains the selected stream per employee/company and otherwise opens the latest active stream. `workspace_inbox()` remains available for older callers. Search/pagination and timelines retain original imported timestamps. Chatter drafts, attachments and quotes remain keyed by conversation. Shared orders are filtered by authorized streams and fulfillment stores, and retain their original conversation, revision and accepted snapshot.

A manager with a valid Chatter session previews a link with `action_preview_customer_link(customer_id)` on the conversation and submits its fingerprint to `action_confirm_customer_link(customer_id, fingerprint, reason, resolve_conflict=False)`. Pass the session in `ab_chatter_session_token`, as for other workspace operations. The server validates role, session, customer, account, company and intake. A stale preview fails. A conflicting existing identity needs an explicit reviewed resolution. The protected Chatter audit records both previous links, the new customer, reason, actor, employee and time. Manual association does not populate confirmed-phone evidence. Never link by name, by digit-stripping an opaque ID, or by pairing channel contact lists.

History linking uses `action_link_whatsapp_history(limit=200, after_id=0)` on the account. Continue with `next_after_id` while `has_more` is true. Results include `linked_ids`, `skipped_ids`, `conflicting_ids` and `examined`; skipped/conflicting records advance the cursor. Restart at zero for a deliberate later review. Repeated imports do not resend. Imports retain canonical IDs, source payloads, reply/reaction references and original timestamps. They are explicitly historical/unverified, create no outgoing operations or read receipts, do not open the service window and do not appear in fresh alerts or unread counts. Unmapped history remains administrator-only.

Unknown WhatsApp sender/destination formats are stored verbatim in queue review with `unsupported_identity`; they create no guessed contact and are never digit-stripped. Numeric WhatsApp destinations are compatibility identifiers, not proof of a phone number. Telegram's existing numeric handling stays unchanged. BSUID/phone-hidden forms require verified account-specific fixtures before enabling. Inbound media, reply/profile/contact normalization and reaction increments remain gated on the later bounded pilot; unsupported content is visible for review. Outgoing media/reactions have the explicit, default-off **Validated WhatsApp Media and Reactions** account control.

## Isolated development and verification

Use `/opt/odoo19/venv19/bin/python` for Odoo runtime dependencies. Restore gateway test tooling separately:

```bash
python3 -m venv /tmp/callcenter-dual-test-venv
/tmp/callcenter-dual-test-venv/bin/pip install -r crm_messaging_gateway/requirements-dev.txt
cd crm_messaging_gateway
MESSAGING_TEST_DSN_FILE=/path/to/private-test-dsn /tmp/callcenter-dual-test-venv/bin/python -m pytest tests -q
```

The DSN must reference a dedicated PostgreSQL test database. Storage tests reset only that database. Odoo/browser tests use a neutral configuration, isolated database/filestore, `--http-port=5069 --gevent-port=5072 --workers=0 --max-cron-threads=0 --stop-after-init`. Check occupancy first. Never stop the user's process or use ports 4091/4092. Browser testing additionally requires `websocket-client==1.8.0` in an isolated test environment and Chrome. Test the lower-level messaging addon separately without workspace extensions whose fixture requirements differ. Do not upgrade the live database for validation.

## Deployment gates, in order

1. Review source and verification evidence; back up Odoo and the PostgreSQL queue. Arrange a user-managed Odoo reload after the targeted companion install and workspace/messaging upgrades. Do not use `-u base`.
2. Pin `whatsapp_api_version = v26.0` explicitly in the existing protected host configuration and the same version in gateway config. No version fallback is permitted. Confirm the app/account supports v26.0 with Meta before activation; a syntactic check is not provider validation.
3. As an administrator, call `ab_crm_messaging_account.action_prepare_whatsapp_pilot()`. It reuses the existing `tg-callcenter` intake/company, the host business-number ID and module-owned inactive service identity `ab_crm_whatsapp_workspace.user_whatsapp_gateway`. It creates `wa-callcenter` with reception, sending and extended media off. Existing mappings are validated, never overwritten. Activate that identity and provision its scoped credential only during the separately approved deployment. Group membership is module-owned XML.
4. The gateway currently uses one Odoo credential for all accounts. Keep the existing Telegram key as the default; configure a dedicated protected `odoo_key` on the WhatsApp account before activating it. The transport must use that override for every WhatsApp operation. Do not give Telegram's service identity access to WhatsApp merely to reuse its key.
5. Add `wa-callcenter` to the existing protected gateway config. Retain the PostgreSQL DSN, Telegram polling/enabled flags and global send flag. Set WhatsApp `sending_enabled=false`, `enabled=false`, `reception=disabled`; add protected Meta token, app secret and verification token. The per-account switch defaults true for legacy Telegram configs and false for WhatsApp. Host/gateway token copies must match and be rotated together.
6. Run the masked check from the gateway directory with `CRM_MESSAGING_CONFIG` pointing at the existing private file:

   ```bash
   python -m app.whatsapp_check --odoo-config /opt/odoo19/conf/callcenter19.conf --account wa-callcenter
   ```

   It prints booleans only for business number, explicit API version, token consistency, required secrets and paused state. It neither contacts Meta nor enables anything.
7. Before signed reception, backfill the six known outgoing messages using the bounded importer and verify one canonical/projection per eligible record and zero outgoing operations. Reconcile actual current counts; the diagnosis count is not a permanent invariant. Review the one phone-match candidate using independent evidence and the preview/confirm operation. Leave the other WhatsApp contact and unmatched Telegram conversation separate.
8. Configure exactly `https://<domain>/webhooks/whatsapp/wa-callcenter` to the existing loopback gateway. `deploy/nginx.conf` demonstrates the exact allowed path. Preserve raw body bytes, signature headers and GET query parameters. No access/body/token logging; no Odoo RPC, legacy webhooks, health or readiness endpoints through this rule. Do not acknowledge a POST unless ingestion commits durably.
9. In a bounded reception-only pilot, validate Meta GET challenge separately from signed POST authentication, forged/modified signatures, wrong business number, duplicate replay and conflicting replay. Enable gateway reception and Odoo **Signed WhatsApp Reception** only after configuration validation. Keep both WhatsApp outgoing switches off during inbound checks.
10. Obtain explicit pilot-send authorization for a named participant. Enable Odoo outgoing plus the gateway WhatsApp send switch without changing Telegram. Prove one explicit text reply from each interface creates one canonical record, projection and operation; test delivered/read callbacks, reordering, expired windows, revoked PIN/role/company and unknown outcomes. Template pickers show only the user's preference language (Arabic variants share Arabic content). Approved templates remain explicit sends outside the service window. Old outgoing history never opens it. Add media, reply context, reactions and contact information only in separately validated increments.

## PostgreSQL backup, recovery and monitoring

`python -m app.ops backup --file /private/directory/queue.dump` creates a private PostgreSQL custom-format archive using `pg_dump`; credentials are passed through the child environment, never arguments or output. `pg_restore --list` validates the archive directory, not a full recovery. `python -m app.backup` also supports PostgreSQL and stores timestamped archives in `backups/` alongside the existing protected config. Do not install or change service timers without the deployment step.

Restore drills use a fresh isolated PostgreSQL database and `pg_restore --exit-on-error --no-owner --no-acl`. Compare counts and canonical digests of `incoming_event`, `outgoing_operation`, `operator_audit`, and `telegram_polling`; verify review records remain in review and polling offsets survive. Never restore into the active queue. After an actual crash, keep sending paused until Odoo receipts, tokens/attempts and provider evidence are reconciled. Recover `sending` operations into uncertain review; never reset them to ready or automatically replay them.

`python -m app.ops status` reports per-account states, backlog ages, polling freshness and uncertain sends for PostgreSQL. `python -m app.ops review` reports IDs and sanitized errors/review reasons without message bodies. Monitor oldest backlog, increasing review counts, stale polling and provider failures. Protect backups and access to queue review data.

Rollback pauses only WhatsApp reception/sending and preserves canonical history, links, audit and queue evidence. It never restores direct sending. Telegram remains operational. Odoo/POS processes remain user-managed.

## Evidence

See `docs/omnichannel-callcenter-validation.md` for fresh checks, actual counts and remaining deployment gates. Earlier reports are historical evidence only. No live Meta validation, live backfill/link, tunnel configuration or customer send is implied by source tests.
