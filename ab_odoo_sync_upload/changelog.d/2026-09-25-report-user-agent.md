# Report API User-Agent

## Recent relevant commit

- Commit: `75bc34208eb5d209b7b7ec4b321ab3662173ac14`
- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: 2026-09-24
- Original subject: `ab_odoo_sync_upload: auto-discover branch disk serial \Body if you want a fuller commit:`
- User-facing changes: Automatically discover the branch disk serial used in report API payloads and retain the loopback-only development override.

Files changed:

- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/changelog.d/2026-09-13-branch-hardware-identity.md`
- `ab_odoo_sync_upload/data/system_parameters.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/models/ab_odoo_sync_hardware.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/views/configuration_views.xml`

## Current changes before commit:

- Send `User-Agent: AB-Odoo-Sync/19.0` on report health and upload requests instead of the default Python urllib identity, to address the observed Cloudflare signature rejection.
- Keep the existing authentication headers, JSON payload, and timeout unchanged.
- This client identity change does not resolve the separately observed report host HTTP 502 response.

Files changed:

- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/changelog.d/2026-09-25-report-user-agent.md`
