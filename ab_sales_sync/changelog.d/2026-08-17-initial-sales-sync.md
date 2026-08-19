## e6fdedbf799a0266e885039e45be819b5e8f40dd

- Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
- Date: Mon Aug 17 14:00:46 2026 +0300
- Subject: ab_sales_sync/Implemented ab_sales_sync as a new self-contained addon.

User-facing changes:

- Added MAIN-side branch sales and sales-return mirror models.
- Added upload sources and apply profiles for sales headers, lines, return headers, and return lines.
- Added manager-only read access, record rules, inspection views, menus, and Arabic translations.

Files changed:

- `ab_sales_sync/__init__.py`
- `ab_sales_sync/__manifest__.py`
- `ab_sales_sync/changelog.d/2026-08-17-initial-sales-sync.md`
- `ab_sales_sync/data/sync_profiles.xml`
- `ab_sales_sync/i18n/ar.po`
- `ab_sales_sync/i18n/ar_001.po`
- `ab_sales_sync/models/__init__.py`
- `ab_sales_sync/models/ab_sales_sync_models.py`
- `ab_sales_sync/security/ir.model.access.csv`
- `ab_sales_sync/security/record_rules.xml`
- `ab_sales_sync/security/security_groups.xml`
- `ab_sales_sync/views/ab_sales_sync_views.xml`

## 068a70ed71a14956f12a57424d52497876b6d48d

- Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
- Date: Wed Aug 19 10:11:41 2026 +0300
- Subject: ab_sales_sync/mirroring models and defining relations through stable_many2one and sync_many2one

User-facing changes:

- Added mirror models, profiles, mappings, security, and read-only menus for the remaining concrete sales storage models.
- Kept newly seeded upload sources inactive until each branch explicitly enables them.
- Switched shared product and store relations to source-ID sync resolution and added an upgrade-safe mapping update.

Files changed:

- `ab_sales_sync/__manifest__.py`
- `ab_sales_sync/changelog.d/2026-08-17-initial-sales-sync.md`
- `ab_sales_sync/data/sync_profile_updates.xml`
- `ab_sales_sync/data/sync_profiles.xml`
- `ab_sales_sync/data/sync_profiles_extra.xml`
- `ab_sales_sync/i18n/ar.po`
- `ab_sales_sync/i18n/ar_001.po`
- `ab_sales_sync/models/ab_sales_sync_models.py`
- `ab_sales_sync/security/ir.model.access.csv`
- `ab_sales_sync/security/record_rules.xml`
- `ab_sales_sync/views/ab_sales_sync_extra_views.xml`

## Current changes before commit

User-facing changes:

- Promote Sales Sync from Settings > Technical to a standalone top-level Odoo app.
- Add a dedicated Sales Sync app icon while retaining manager-only menu visibility.
- Repair the Arabic root-menu translation with its Odoo-exported source reference.
- Display every received JSON payload in a safe, pretty-printed, scrollable viewer.
- Apply the JSON viewer to raw payloads, inventory snapshots, POS settings, and draft bills without affecting other modules.
- Bump the module version to `19.0.1.2.0` for the app navigation and JSON viewer updates.

Files changed:

- `ab_sales_sync/__manifest__.py`
- `ab_sales_sync/changelog.d/2026-08-17-initial-sales-sync.md`
- `ab_sales_sync/i18n/ar.po`
- `ab_sales_sync/i18n/ar_001.po`
- `ab_sales_sync/static/description/icon.png`
- `ab_sales_sync/static/description/icon.svg`
- `ab_sales_sync/static/src/fields/pretty_json/pretty_json_field.js`
- `ab_sales_sync/static/src/fields/pretty_json/pretty_json_field.scss`
- `ab_sales_sync/static/src/fields/pretty_json/pretty_json_field.xml`
- `ab_sales_sync/views/ab_sales_sync_extra_views.xml`
- `ab_sales_sync/views/ab_sales_sync_views.xml`
