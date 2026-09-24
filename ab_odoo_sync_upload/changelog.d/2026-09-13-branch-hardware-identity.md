# Branch Hardware Identity

## Recent relevant commit

- Commit: `a696d33c0af724ea6fac5a66b71038a7279fa8c7`
- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: 2026-09-14
- Original subject: ab_odoo_sync_upload: send hardware identity with report uploads
- User-facing changes:
  - Added branch hardware serial identity to report health and upload payloads.
  - Added loopback-only hardware serial override support for development.
  - Required HTTPS report URLs while allowing loopback HTTP for local testing.

Files changed:

- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/changelog.d/2026-09-13-branch-hardware-identity.md`
- `ab_odoo_sync_upload/data/system_parameters.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/models/ab_odoo_sync_outbox.py`
- `ab_odoo_sync_upload/models/__init__.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_hardware.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/views/configuration_views.xml`

## Current changes before commit

User-facing changes:

- Replaced configured `/dev/disk/by-id/...` hardware path lookup with automatic first eligible internal disk serial discovery from `lsblk`.
- Kept the top-level `hdd_serial` upload payload and loopback-only `ab_odoo_sync.hdd_serial` development override unchanged.
- Removed `ab_odoo_sync.hdd_device_path` from branch upload configuration defaults and the configuration action domain; existing database values are ignored.
- Added Arabic translations for automatic disk discovery errors.
- Bumped the module version to `19.0.1.5.0`.

Files changed:

- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/changelog.d/2026-09-13-branch-hardware-identity.md`
- `ab_odoo_sync_upload/data/system_parameters.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/models/ab_odoo_sync_hardware.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/views/configuration_views.xml`
