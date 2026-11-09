# Module update committed — 94d7f960

- Commit: `94d7f96087d0b69b93097cc123cbae6db28ff3ff`
- Author: Alhassan Hossny
- Date: 2026-11-09T14:04:35+02:00
- Original subject: ab_crm_whatsapp_workspace/feat: prepare guarded dual-channel messaging

Route reception and sending through the durable gateway, prepare an inactive scoped service identity, guard pilot capabilities, preserve historical import provenance, and filter approved templates by preference language.

Commit preparation checks: changed Python, XML, JavaScript and JSON syntax; SCSS compilation; all six Arabic catalog format checks; addon manifest paths and ownership metadata; and `git diff --check` passed. Earlier Odoo/gateway suite results remain recorded in the existing validation reports. Their temporary logs and test environment were unavailable in this session; those suites were not rerun for this commit. No live database upgrade or service restart was performed.

Files changed:
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
