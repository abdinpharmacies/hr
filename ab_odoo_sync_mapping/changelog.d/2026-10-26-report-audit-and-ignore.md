# Source audit fields and explicit ignored-field accounting

Recent relevant commit: `1a0282cbc17619acc773e996288d9e96bc0a5d53`
Author: emadco88-report-server
Date: 2026-10-07
Original subject: ab_odoo_sync_mapping/ FIX it should not refuse to receive any authnicated payload

Current changes before commit:

- Permit the four source audit fields on targets inheriting the passive mirror mixin with access logging disabled, while retaining readonly reporting UI and protections on ordinary Odoo models.
- Include source audit dates when loading matching mappings; apply the same eligibility policy to field mappings, overrides, and execution.
- Keep user relations on the existing branch-scoped identity and ab_users source-ID placeholder scheme, without treating source IDs as local res.users IDs.
- Explicit enabled Ignore mappings count as handled for normal and archive operations, without target writes. Required Ignore configurations are rejected for profile mappings and overrides.
- Leave disabled or otherwise unwritable mappings unhandled so they cannot falsely produce Applied status.
- Configure the four audit mappings and four requested Ignore mappings on sales and returns profiles through a bounded end-stage upgrade. Suppress configuration-induced feeder jobs with skip_sync_apply_feeders.
- Preserve unrelated configuration and upload overrides; leave replication_posted and return_client_token unhandled unless separately configured.
- Bump the module to 19.0.1.7.1 and document the behavior.

Validation and deployment:

- 29 checks passed against actual sales reporting models, including source dates, user identity handling, readonly protections, overrides, archive ignores, invalid required ignores, and skipped-field accounting.
- All 53 direct-upload and 40 immediate-reapply regression checks passed (122 checks total).
- Targeted upgrade passed with persisted sales profiles, producing four audit mappings and four Ignore mappings per profile. Configuration runs at the end of upgrade, after sales models are loaded.
- Production upgrade to installed version 19.0.1.7.1 passed. Configuration backup is under /opt/odoo19/resource-tuning-backups/20261026-report-audit.
- Before/after profile snapshots matched exactly. Upload 729384 and the queue count also matched across upgrade, before resuming intake. No reapplication or backlog replay was run.
- A production calculation with relation resolution stubbed to avoid writes leaves only replication_posted and return_client_token skipped on upload 729384. Its stored Partially Applied status is unchanged until reapplication.
- Restarted Odoo and the queue runner. The runner was already active since 14:34 UTC before this task; its running state was preserved. Login endpoint returns HTTP 200.
- Python syntax, existing Arabic catalogs, and git diff --check passed. Scripts and logs remain outside the addon under /opt/odoo19/validation/sync_audit_fields and /tmp/sync-audit-*.log.

Files changed:

- `__manifest__.py`
- `README.md`
- `models/ab_odoo_sync_apply_profile.py`
- `models/ab_odoo_sync_upload_record.py`
- `models/ab_odoo_sync_upload_override.py`
- `migrations/19.0.1.7.1/end-migration.py`
- `changelog.d/2026-10-26-report-audit-and-ignore.md`
