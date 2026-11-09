# Callcenter gateway development

Use the [current dual-channel runbook](../docs/omnichannel-callcenter-runbook.md) for PostgreSQL setup, isolated environments, credentials, Telegram polling, WhatsApp preparation, validation and staged activation.

The gateway, receiver and worker remain independent services on the existing callcenter host. Odoo stays user-managed. Do not reuse old temporary environment paths, historical API-key expiry dates or stale pending-activation statements from earlier versions of this document.

`VALIDATION.md` retains historical reports; [the current validation report](../docs/omnichannel-callcenter-validation.md) identifies checks executed for this change. SQLite documents apply only to separately chosen SQLite deployments, not this PostgreSQL callcenter deployment.
