# Optional WhatsApp Sales Chatter bridge

Install this addon explicitly from the callcenter checkout. It inherits `ab_whatsapp_api`, `ab_crm_whatsapp` and Sales Chatter; it changes no protected addon files and no order, stock, pricing or customer-matching workflow. The existing dashboard and Chatter remain the entry points.

Configure a WhatsApp messaging account with an explicit provider phone-number ID, CRM channel, authorized branch/company and dedicated service identity. A manager must confirm the previous direct sender is disabled, then enable **WhatsApp Queue Ownership**. This flag cannot be switched back casually: reconciliation is required before a rollback. Archive/pause accounts with the existing supported controls. Outgoing sending additionally requires the existing account and gateway sending flags.

Both dashboard and Chatter sends create one canonical `ab.whatsapp.message`, one scoped CRM projection and one immutable outgoing operation. A queue error is an error; it never falls back to direct sending. Archived or disabled migrated accounts also never fall back. Nonmigrated accounts retain their original direct-send implementation.

Use **Authorized WhatsApp Templates** to explicitly associate the existing approved templates with an account. Chatter's approved-template button sends through the queue even outside the 24-hour reply window. Body template parameters, template approval and account authorization are checked at approval and again before dispatch. Ordinary text, replies, files and reactions require the reply window. Reaction targets must belong to the same conversation, be undeleted, not themselves be reactions and be within 30 days.

The gateway supports text, approved templates, JPEG/PNG images (5 MiB), audio/voice (16 MiB), documents (20 MiB), and existing dashboard MP4/3GP video uploads (16 MiB; H.264/AAC). It validates media before submitting a message; FFmpeg/FFprobe are required for audio/voice and video checks. Existing Chatter file/voice controls retain their current supported selection. Provider eligibility and current account policy still apply.

Dispatch rechecks the original Odoo user, active company, branch access, account flags and current content. Chatter-originated sends also recheck the originating employee profile and session. A definitive authorization rejection is durably reported as failed without calling the provider. Ambiguous provider outcomes stay uncertain and block automatic resend.

Canonical history and projections are immutable. Global record rules restrict canonical reads to explicitly mapped company/branch accounts; service users cannot browse that history directly. The existing service API only returns scoped history, and signed gateway reception is the sole reception path for migrated accounts. The old unsigned webhook path rejects migrated accounts.

**Link WhatsApp History** links a bounded batch without approving or resending it. For controlled pagination, managers may call `action_link_whatsapp_history(limit=200, after_id=...)`; the result includes `next_after_id`. Only exact provider-account mappings are accepted. Missing account IDs and duplicate provider identities remain unexposed for review. Existing confirmed CRM identity links are reused; this addon performs no customer matching. Legacy incoming provider IDs are reused on later webhook replay rather than creating a duplicate projection. Existing historical media remains canonical and available through the existing authorized dashboard media endpoint; no bulk media download runs during linking.

Telegram and WhatsApp conversations retain independent histories, drafts, attachments and reply targets. Dashboard and Chatter display queued/accepted/failed/uncertain states. Accepted means provider acceptance; delivered/read evidence requires webhook activation. Integrated messages cannot be edited or deleted locally.

Signed reception is disabled in both the default gateway WhatsApp configuration and the Odoo account. Outgoing-only operation is supported now. Customer replies and delivered/read updates require separate approved activation and provider integration tests; this release's prepared webhook normalizer handles text and status events, while unsupported incoming content remains a staff-review notice.

Production cutover, webhook activation, live sends and measured-peak capacity approval were not performed. See the gateway's `SQLITE.md` and `SQLITE_VALIDATION.md` for migration, backup, rollback and verification evidence. Runtime packages omit tests and test asset declarations; source tests remain available for CI.


## Template UI (19.0.1.1.0)

Approved templates use a searchable, channel-colored list and parameter preview, stacked on narrow screens. The first available template is selected automatically. Blank or whitespace-only required values disable Queue template; populated values appear in the preview. Queue remains an explicit authorized action. Saved replies use their separate composer-insertion workflow. This UI release does not activate WhatsApp accounts, reception or live sends.

Validation for this UI release is recorded in [Sales Chatter validation](../ab_crm_sales_workspace/VALIDATION.md): 79 Odoo tests and 32 browser tests pass on isolated databases, with English and both Arabic catalogs checked.
