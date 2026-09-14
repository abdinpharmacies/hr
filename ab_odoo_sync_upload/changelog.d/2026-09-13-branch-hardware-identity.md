# Branch Hardware Identity

## Recent relevant commit

- Commit: `ec812d78a0def672d32803132a88dae7bc8b0454`
- Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
- Date: 2026-09-09
- Original subject: ab_odoo_sync_upload/Implemented the bridge-based sales upload configuration.
- User-facing changes:
  - Added bridge-based sales upload source configuration before adding branch hardware identity transport.

Files changed:

- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/changelog.d/2026-09-06-source-channel-configuration.md`
- `ab_odoo_sync_upload/data/queue_jobs.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/models/ab_odoo_sync_outbox.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_source.py`
- `ab_odoo_sync_upload/views/upload_views.xml`

## Current changes before commit

User-facing changes:

- Added the `ab_odoo_sync.hdd_device_path` configuration parameter for stable `/dev/disk/by-id/...` hardware serial discovery.
- Added the `ab_odoo_sync.hdd_serial` loopback-only development fallback for hosts without `/dev/disk/by-id`.
- Included the normalized top-level `hdd_serial` in branch health and upload payloads.
- Required HTTPS report URLs before branch upload calls are sent, while allowing loopback HTTP for local POS/report testing.
- Preserved retry behavior by surfacing report authentication and hardware rejections as failed send attempts instead of marking outbox records sent.
- Added Arabic translations for the new branch-side hardware and HTTPS validation messages.
- Bumped the module version to `19.0.1.4.0` and set the developer to the current git user.

Files changed:

- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/changelog.d/2026-09-13-branch-hardware-identity.md`
- `ab_odoo_sync_upload/data/system_parameters.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/models/__init__.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_hardware.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/views/configuration_views.xml`
