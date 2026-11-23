# Callcenter adapter merge repair

## Current changes before commit:

- Restore Odoo's module metadata comments before two entries in each Arabic catalog after the conflict merge.

Files changed:

- `ab_storefront_callcenter_adapter/i18n/ar.po`
- `ab_storefront_callcenter_adapter/i18n/ar_001.po`
- `ab_storefront_callcenter_adapter/changelog.d/2026-11-23-merge-markers.md`

Validation:

- Odoo `PoFileReader` parsed both Arabic catalogs successfully (151 translation rows each); `msgfmt --check-format` passed.

## Recent commits

Commit: `d43689d3`
Author: Mohamed Fawzy
Date: 2026-11-23
Original subject: `ab_storefront_callcenter_adapter/FIX: resolve committed merge markers`

User-facing changes:

- Resolve merge markers while keeping the updated chat behavior, endpoint validation, and Arabic translations.

Files changed:

- `ab_storefront_callcenter_adapter/__manifest__.py`
- `ab_storefront_callcenter_adapter/models/adapter.py`
- `ab_storefront_callcenter_adapter/i18n/ar.po`
- `ab_storefront_callcenter_adapter/i18n/ar_001.po`
- `ab_storefront_callcenter_adapter/changelog.d/2026-11-23-merge-markers.md`

Commit: `eba33c7e`
Author: Alhassan Hossny
Date: 2026-11-23
Original subject: `ab_storefront_callcenter_adapter/fix: preserve chat submissions during history polling`

User-facing changes:

- Preserve chat submissions during history polling and add the accompanying native chat, media, identity, and lifecycle work.

Files changed:

- `ab_storefront_callcenter_adapter/README.md`
- `ab_storefront_callcenter_adapter/__manifest__.py`
- `ab_storefront_callcenter_adapter/changelog.d/`
- `ab_storefront_callcenter_adapter/controllers/`
- `ab_storefront_callcenter_adapter/i18n/ar.po`
- `ab_storefront_callcenter_adapter/i18n/ar_001.po`
- `ab_storefront_callcenter_adapter/media_protocol.py`
- `ab_storefront_callcenter_adapter/models/`
- `ab_storefront_callcenter_adapter/security/`
- `ab_storefront_callcenter_adapter/static/src/`
- `ab_storefront_callcenter_adapter/tests/`
- `ab_storefront_callcenter_adapter/views/views.xml`
