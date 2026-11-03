58703b03 — yahyazakaria22 — 2026-11-03
feat: add Odoo web_progress addon

- Add the Odoo 19 Dynamic Progress Bar addon for visible progress in ETA retrieval loops.
- Keep the upstream author and LGPL-3 declaration, and record the current repository developer.
- Exclude test files and generated Python bytecode from the production addon package.

Files changed:

- web_progress/.gitignore
- web_progress/README.rst
- web_progress/__init__.py
- web_progress/__manifest__.py
- web_progress/changelog.d
- web_progress/controllers/__init__.py
- web_progress/controllers/main.py
- web_progress/doc/index.rst
- web_progress/i18n/fr.po
- web_progress/i18n/pl.po
- web_progress/models/__init__.py
- web_progress/models/base.py
- web_progress/models/base_import.py
- web_progress/models/ir_actions_report.py
- web_progress/models/ir_cron.py
- web_progress/models/web_progress.py
- web_progress/security/ir.model.access.csv
- web_progress/static/description/icon.png
- web_progress/static/description/index.html
- web_progress/static/description/progress_bar_loading_cancelling.gif
- web_progress/static/description/progress_bar_loading_compact.gif
- web_progress/static/description/progress_bar_loading_systray.gif
- web_progress/static/src/img/nyanimated.gif
- web_progress/static/src/img/nyancat_bckgr.gif
- web_progress/static/src/img/nyancat_rainbow.gif
- web_progress/static/src/js/block_ui_patch.js
- web_progress/static/src/js/import_block_ui_patch.js
- web_progress/static/src/js/progress_bar.js
- web_progress/static/src/js/progress_bar_body.js
- web_progress/static/src/js/progress_bar_header.js
- web_progress/static/src/js/progress_bar_sub_item.js
- web_progress/static/src/js/progress_bar_sub_list.js
- web_progress/static/src/js/progress_bar_sub_list.js
- web_progress/static/src/js/progress_menu.js
- web_progress/static/src/js/progress_service.js
- web_progress/static/src/js/rpc_service.js
- web_progress/static/src/scss/views.scss
- web_progress/static/src/scss/views_styles.scss
- web_progress/static/src/xml/block_ui.xml
- web_progress/static/src/xml/progress_bar.xml
- web_progress/static/src/xml/web_progress_menu.xml
