## 3db5d596c9429ff082c3fe9b0466692b945f788f

- Author: emadco88 <emadco88@gmail.com>
- Date: Tue Jul 28 15:21:42 2026 +0300
- Subject: INIT commit pos19

User-facing changes:

- Added the MuK Web Refresh addon for Odoo 19.
- Added a control-panel refresh button and supporting web unit test.

Files changed:

- `muk_web_refresh/LICENSE`
- `muk_web_refresh/__init__.py`
- `muk_web_refresh/__manifest__.py`
- `muk_web_refresh/doc/changelog.rst`
- `muk_web_refresh/doc/index.rst`
- `muk_web_refresh/i18n/de.po`
- `muk_web_refresh/models/__init__.py`
- `muk_web_refresh/models/ir_http.py`
- `muk_web_refresh/static/description/banner.png`
- `muk_web_refresh/static/description/banner.svg`
- `muk_web_refresh/static/description/icon.png`
- `muk_web_refresh/static/description/icon.svg`
- `muk_web_refresh/static/description/index.html`
- `muk_web_refresh/static/description/logo.png`
- `muk_web_refresh/static/description/screenshot.png`
- `muk_web_refresh/static/description/service_development.png`
- `muk_web_refresh/static/description/service_infrastructure.png`
- `muk_web_refresh/static/description/service_integration.png`
- `muk_web_refresh/static/description/service_support.png`
- `muk_web_refresh/static/description/service_training.png`
- `muk_web_refresh/static/src/search/control_panel.js`
- `muk_web_refresh/static/src/search/control_panel.xml`
- `muk_web_refresh/static/tests/refresh.test.js`

## Current changes before commit

User-facing changes:

- Replaced recurring reload controls with one manual refresh button for list, kanban, and form views.
- Added a hover effect to the refresh button.
- Added an unsaved-changes warning that lets users save before refreshing or refresh anyway.
- Removed persisted reload settings and session injection that are no longer used.
- Updated addon metadata, documentation, translations, and the web unit test for one-click refresh behavior.

Files changed:

- `muk_web_refresh/__manifest__.py`
- `muk_web_refresh/changelog.d/2026-08-10-manual-refresh.md`
- `muk_web_refresh/doc/index.rst`
- `muk_web_refresh/i18n/ar.po`
- `muk_web_refresh/i18n/ar_001.po`
- `muk_web_refresh/models/__init__.py`
- `muk_web_refresh/models/ir_http.py`
- `muk_web_refresh/static/description/index.html`
- `muk_web_refresh/static/src/search/control_panel.js`
- `muk_web_refresh/static/src/search/control_panel.scss`
- `muk_web_refresh/static/src/search/control_panel.xml`
- `muk_web_refresh/static/tests/refresh.test.js`
