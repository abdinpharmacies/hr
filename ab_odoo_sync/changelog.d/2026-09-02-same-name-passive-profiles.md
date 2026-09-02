# Same-Name Passive Profile Auto-Mapping

## Recent relevant commit

- Commit: `06d5f017d322eee60ea7509ed24d0083bff06f17`
- Author: Alhassan Hossny
- Date: 2026-09-01
- Subject: `ab_odoo_sync: document event-driven report mapping upgrade`
- Documented event-driven report mapping behavior and targeted report-side upgrade requirements.

Files changed:

- `ab_odoo_sync/changelog.d/2026-09-01-sync-setup-script.md`
- `ab_odoo_sync/readme.md`
- `ab_odoo_sync/test-guide.md`

## Current changes before commit

- Replace the report-owned master/reference model list with the updated business-model-only set, including replica, HR, product metadata, promo, employee access, and `ab_sales_channel`.
- Allow report-owned master/reference models to be branch upload sources so they can use `business_model` apply profiles.
- Make setup-script CSV profile defaults choose `business_model` for report-owned master/reference models and same-name `mirror_sync` for passive models.
- Update setup, sync rules, and validation docs to describe same-name passive mirrors instead of `__sync` default targets.

Files changed:

- `ab_odoo_sync/models/ab_odoo_sync_rules.py`
- `ab_odoo_sync/readme.md`
- `ab_odoo_sync/scripts/configure_sync.py`
- `ab_odoo_sync/sync-rules.md`
- `ab_odoo_sync/test-guide.md`
