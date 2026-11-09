# Optional WhatsApp queue and Chatter bridge

Current changes before commit:
- New optional addon 19.0.1.0.0 inherits the existing adapters, canonical WhatsApp history and Sales Chatter.
- Explicit account migration routes dashboard and Chatter sends through durable operations; queue failures never fall back to direct sending.
- Adds scoped canonical projections, bounded historical linking, template/account eligibility, media/reactions, sender/employee permission rechecks and immutable integrated history.
- Adds disabled signed reception, accurate queued/accepted/failed/uncertain presentation, independent drafts and English/Arabic composition.
- Adds ORM/access tests and focused browser checks. No production activation or protected module edits.

Files changed:
- `__init__.py`, `__manifest__.py`
- `models/__init__.py`, `models/common.py`, `models/account.py`, `models/history.py`, `models/media.py`, `models/workspace.py`, `models/service.py`, `models/gateway.py`
- `security/ir.model.access.csv`, `security/record_rules.xml`, `views/account.xml`
- `static/src/dashboard.js`, `static/src/templates.js`, `static/src/templates.xml`, `static/description/icon.png`
- `i18n/ar.po`, `i18n/ar_001.po`
- `tests/__init__.py`, `tests/test_bridge.py`, `tests/test_browser.py`, `static/tests/drafts.test.js`
- `README.md`, `changelog.d/2026-11-08-whatsapp-queue.md`
