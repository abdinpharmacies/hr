No previous commits: new addon.

Current changes before commit:
Author: emadco88
Date: 2026-11-10
- Port idle logout to an Odoo 19 service and OWL countdown.
- Preserve per-user idle settings; restrict policy changes to administrators.
- Add Arabic translations and reject invalid timeouts.

Files changed:
- __init__.py
- __manifest__.py
- controllers/__init__.py
- controllers/timer.py
- i18n/ar.po
- i18n/ar_001.po
- models/__init__.py
- models/res_users.py
- static/src/timer.js
- static/src/timer.xml
- views/res_users_views.xml
