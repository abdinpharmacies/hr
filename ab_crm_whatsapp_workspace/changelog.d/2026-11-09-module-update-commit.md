# Module update committed — 625220e0

- Commit: `625220e03e15a1186bf0291af54b347ae84ca45b`
- Author: Alhassan Hossny
- Date: 2026-11-09T10:26:24+02:00
- Original subject: ab_crm_whatsapp_workspace/feat: add scoped WhatsApp chatter integration

Integrate approved templates, durable operations, canonical history, media and location snapshots with Sales Chatter. Include server-side access guards, bilingual UI and isolated regression coverage.

Validation: 16 module tests passed, including 43 shared browser tests with 247 assertions. Both Arabic catalogs pass format checks.

Files changed:
- `__init__.py`
- `__manifest__.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/account.py`
- `models/common.py`
- `models/gateway.py`
- `models/history.py`
- `models/media.py`
- `models/service.py`
- `models/workspace.py`
- `security/ir.model.access.csv`
- `security/record_rules.xml`
- `static/description/icon.png`
- `static/src/dashboard.js`
- `static/src/templates.js`
- `static/src/templates.xml`
- `static/tests/drafts.test.js`
- `tests/__init__.py`
- `tests/test_bridge.py`
- `tests/test_browser.py`
- `views/account.xml`
