# Versioned Website chat transport

Baseline: 379f02d0 — Alhassan Hossny — 2026-11-16 — crm_messaging_gateway/feat: add isolated WhatsApp authentication delivery

Current changes before commit:
- Poll and acknowledge v2 chat alongside v1 orders without losing order intake on older sources.
- Route replies only to frozen typed destinations; reject historical or malformed destination operations.
- Keep source queues/account claims separate and retain commit-before-ack recovery.
- Add dual-source, v1 compatibility and blocked-historical-send regressions.

- Cache unsupported chat-v2 fetches per source after HTTP 404, keeping v1 order intake available without repeated false alarms. Preserve the original v1 durable payload so queued order retries remain compatible across worker upgrades.

Files changed:
- `crm_messaging_gateway/README.md`
- `crm_messaging_gateway/app/odoo.py`
- `crm_messaging_gateway/app/website.py`
- `crm_messaging_gateway/changelog.d/2026-11-17-native-chat.md`
- `crm_messaging_gateway/tests/test_website.py`
