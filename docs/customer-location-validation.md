# Customer location cards and delivery selection — 2026-11-08

Implemented in the callcenter19 source checkout. No live database upgrade, service restart, webhook activation or provider send was performed. The pre-existing worktree changes were preserved; this delivery builds on those changes.

## Behavior and ownership

- Gateway 1.2.0 normalizes Telegram locations/venues and WhatsApp locations. Zero and geographic boundaries are valid. Nonfinite, nonnumeric and out-of-range coordinates fall back to unsupported messages; optional name/address are limited to 256/1024 characters. Subsequent Telegram edited updates remain ignored.
- `ab_crm_messaging` 19.0.1.5.0 validates incoming RPC locations independently and stores an immutable message snapshot with the received point's timestamp. The existing event identity, source digest and fingerprint ledger remain authoritative. Readable location text supports previews, search and quotes.
- `ab_crm_whatsapp_workspace` 19.0.1.2.0 records canonical location history using the original provider identity, normalized raw payload and immutable CRM snapshot. Existing reception guards remain effective. `ab_whatsapp_api` is unchanged.
- `ab_crm_sales_workspace` 19.0.1.12.0 supplies one reusable card with channel colors, supplied place/address, LTR coordinates, timestamp, Maps link, copy feedback and optional delivery action. Maps is a user-initiated link; there are no embedded maps, geocoding requests or live tracking.
- Use for delivery opens the sole eligible draft, asks which draft when several exist, or offers the existing New order action. A new order is created only after that explicit action. The selection is staged alongside existing unsaved order edits; Save confirms it. Composer/channel drafts are preserved.
- `action_save_draft` accepts `values.delivery_location_message_id`: a positive source-message ID selects it, `false` removes it, omission preserves it. Client coordinates are rejected. Session, ownership, draft state, edit version, source visibility, conversation, company and branch are checked before saving.
- Selection/replacement/removal audit records contain actor, employee, timestamp and old/new immutable source snapshots. Accepted/closed orders require the existing reopening workflow. Written address, notes and customer master address are not derived from the point.

## Verification

| Check | Evidence |
| --- | --- |
| Gateway | 128 passed, 1 skipped. The existing real voice-conversion test requires FFmpeg/ffprobe, absent on this host. SQLite and PostgreSQL queue regressions passed. Provider transport mocked. `/tmp/location-validation/gateway-final.log` |
| Messaging/controller | 24 tests, zero failures/errors, on isolated `crm_location_messaging_test_20261108`. `/tmp/location-validation/messaging-regressions.log` |
| Final fresh Odoo install | 85 test methods, zero failures/errors, on isolated `crm_location_final_test_20261108`; alternate ports 5075/5076. Includes workspace, WhatsApp bridge, explicit source-scope denial, and browser execution. `/tmp/location-validation/final-install.log` |
| Targeted upgrade | Workspace/bridge business tests passed on isolated `crm_location_test_20261108`; browser dependency was then supplied from an existing temporary test directory. `/tmp/location-validation/upgrade-browser.log`, `/tmp/location-validation/browser.log` |
| Browser components | 40 tests, 229 assertions. Includes coordinate links, clipboard success/failure, no automatic maps fetch, draft chooser/new-order intent, staged selection, draft switching, Save payload, and removal cache. |
| Runtime languages | English, `ar`, `ar_001`: translated source field and actual frontend controls verified. Both Arabic catalogs pass gettext format checks, and every existing translation is preserved. `/tmp/location-validation/languages.log` |
| UI matrix | Telegram and WhatsApp, English/Arabic variants, 1440/768/390px. Checks card bounds, LTR coordinates, translated controls, clipboard, intercepted Maps navigation, delivery handoff/Save and composer draft preservation. `/tmp/location-validation/ui-results.log` |
| Protected source | All 202 baseline files in `ab_sales` and `ab_whatsapp_api` unchanged. |

Initial validation issues were test/environment issues: an unsupported tuple argument to Odoo's exception assertion, absent test dependencies, and missing provider fixtures in the standalone messaging test database. They were corrected before the passing runs. UI checks wait for the Save RPC and refresh before closing the dialog. Test statistics that include setup/teardown are not used as test-method totals. Arabic mobile screenshots initially reproduced existing resize-only webclient navbar clipping; the final matrix reloads at each viewport width and verifies the whole document width as well as the card bounds. The final captures were visually inspected.

Temporary UI/test servers were stopped. Ports 5069/5072/5073/5074/5075/5076 are released; the original user-managed process on 4092 (PID 633873) remains running.

## Rollout and limitations

Upgrade the Odoo consumers first (`ab_crm_messaging`, `ab_crm_sales_workspace`, and the optional installed WhatsApp bridge), then deploy the gateway capable of emitting `location`. Older events without location remain compatible. Rollout is a separate authorized operation.

Historical unsupported messages are unchanged. Customers normally need to resend after rollout. Recovering separately retained original payloads requires a separately authorized, bounded procedure.

Branch configuration, outgoing native locations, embedded maps, reverse geocoding and live tracking remain deferred. A future branch selector can reuse the location presentation without its customer-delivery action. Pharmacy location ownership belongs to fulfillment branches; outgoing messages must snapshot the point actually sent.

Runtime packages omit development tests, test assets and caches. The gateway retains its required queue schema migrations. Review artifacts include the task-only patch against the initial worktree, tests and validation evidence; private test configuration and credentials are excluded.
