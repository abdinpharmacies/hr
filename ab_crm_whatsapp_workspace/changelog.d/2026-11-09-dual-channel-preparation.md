# Dual-channel preparation

Previous module commit: `e7ca6fd69333f9f3054274b80bd0c3d736e7e4ea`
Author: Alhassan Hossny
Date: 2026-11-09T10:41:10+02:00
Original subject: ab_crm_whatsapp_workspace/docs: document integration and release changes

Changes included in implementation commit `94d7f960`:

- Close legacy webhook and direct-RPC ingestion through inheritance; all sends queue or fail.
- Prepare disabled pilot mapping and a module-owned inactive service identity.
- Apply import cursors, record provenance and report skipped/conflicting records.
- Keep canonical unmapped history administrator-only and gate media/reactions on explicit validation.

Verification: see `docs/omnichannel-callcenter-validation.md` in the checkout. Live deployment is gated separately.

Files changed:
- `README.md`
- `__init__.py`
- `__manifest__.py`
- `controllers/__init__.py`
- `controllers/webhook.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/account.py`
- `models/history.py`
- `models/service.py`
- `models/workspace.py`
- `security/record_rules.xml`
- `security/whatsapp_service.xml`
- `static/tests/drafts.test.js`
- `tests/test_bridge.py`
- `tests/test_browser.py`
- `views/account.xml`
- `changelog.d/2026-11-09-dual-channel-preparation.md`
