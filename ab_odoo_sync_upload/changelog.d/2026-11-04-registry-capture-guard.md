# Upload capture during registry rebuilding

Recent relevant commit: `ae95657e3c8c2df8487b9955f35c13e5ec7da74d`
Author: emadco88-report-server
Date: 2026-09-27
Original subject: ab_odoo_sync_upload/ FIX expensive api auth

- Reused branch tokens and added configurable upload batching.

Files changed (recent commit):

- `__manifest__.py`
- `changelog.d/2026-09-27-token-batching.md`
- `data/crons.xml`
- `data/system_parameters.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/ab_odoo_sync_client_token.py`
- `models/ab_odoo_sync_outbox.py`
- `models/ab_odoo_sync_upload_service.py`
- `security/ir.model.access.csv`
- `views/configuration_views.xml`

Current changes before commit:

- Skip upload eligibility checks when the current registry lacks the upload source model, preventing missing-model errors during module upgrades and in other databases sharing the process.
- Return no upload capture models for unlink processing when that model is absent.
- Preserve normal capture checks and existing error reporting when the model is available.
- No user-facing strings changed; translation updates are unnecessary.

Validation:

- Isolated Python checks passed for missing/present source models, stored recomputation, excluded models, and the skip context; Python syntax parsed successfully.
- No database upgrade or live registry rebuild was performed; runtime verification remains outstanding.

Files changed:

- `models/ab_odoo_sync_orm_hook.py`
- `changelog.d/2026-11-04-registry-capture-guard.md`
