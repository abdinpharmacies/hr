# WhatsApp Sales Chatter companion

The [current callcenter runbook](../docs/omnichannel-callcenter-runbook.md) covers setup, reviewed customer linking, history import, PostgreSQL recovery and staged activation. Fresh verification is recorded in [the validation report](../docs/omnichannel-callcenter-validation.md).

Install explicitly from the callcenter checkout. This addon preserves `ab_whatsapp_api` source and canonical models. Supported inheritance closes both legacy webhook methods and public ORM ingestion. Every dashboard send queues through a configured migrated account or fails; no account falls back to direct sending.

The preparation method creates disabled `wa-callcenter` using Telegram's current intake/company and an inactive dedicated service identity. Gateway and host target Graph v26.0, with masked consistency checks and no version fallback. Runtime/provider activation is separate from installation.

History linking is bounded and resumable, reporting linked, skipped and conflicting IDs. Imports are historical/unverified, retain original timestamps/source references and create no fresh alerts, read evidence, reply eligibility or sends. Administrators retain access to unmapped canonical history; staff see only authorized mapped records.

Chatter groups customer streams while preserving each conversation's drafts, attachments, replies, unread state and destination. Authorized orders span those streams and retain their original conversation/revision. Explicit manager preview/confirm linking records manual review without asserting phone verification.

Approved templates queue outside the service window. Text replies require authenticated fresh inbound evidence and are checked again at dispatch. Outgoing media/reactions require the default-off validation control; inbound media/context/contact expansions and opaque identity support remain pilot gates. Unknown outcomes are reviewed without automatic resend. Telegram retains acceptance-only status semantics.

Production packages exclude tests, test assets, caches and secrets. Installation, live backfill, linking, tunnel configuration, reception and pilot sending were not performed by this source preparation.
