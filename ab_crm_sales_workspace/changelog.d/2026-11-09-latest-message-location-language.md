# Latest message and compact location picker — 19.0.1.14.3

Changes included in implementation commit `9dc09536`:
- Open CRM/OMS Sales Chatter at the latest message on initial mount and after a contact/channel response finishes loading. Preserve the reading position during ordinary updates.
- Keep branch-location content Arabic (`ar_001`), independently of the interface language, and hide the language selector.
- Open the location picker with a focused search input, without an initial directory request or selected location. Use native Odoo autocomplete for debounced suggestions, keyboard selection, Escape and outside-click dismissal. Show the location card only after explicit selection.
- Place the optional Send branch details checkbox beside Search branches, with wrapping at narrow widths. Fit the suggestions to the search input and bound the dropdown height.
- Immediately invalidate the previous location when typing; ignore stale search/preview responses and prevent sending until a current branch is selected.
- Preserve existing English strings and both Arabic catalogs; update references for labels moved from XML to JavaScript.
- Add browser regressions for initial mount, delayed conversation/channel responses, LTR/RTL scrolling, collapsed search, fixed Arabic content, keyboard selection, clearing, no matches, stale responses and narrow dropdown geometry.

Validation:
- Targeted upgrade on isolated `crm_session_fix_test_20261109`: 1 browser HttpCase passed; 48 HOOT tests / 309 assertions passed. Log: `/tmp/chatter-location-ui/final-browser.log`.
- POT export and both Arabic catalogs pass translation checks; JavaScript syntax, XML, manifest paths and whitespace checks pass.
- Validation uses ports 5069/5072 with workers and cron disabled. The user's process on 4092 and live callcenter database were not upgraded or restarted. Provider calls are mocked.
- The isolated clone reports pre-existing missing avatar files and unrelated manifest/model warnings; the browser suite completes without failures.
- Runtime package excludes Python/browser tests, test asset declarations and caches: `/tmp/chatter-location-ui/ab_crm_sales_workspace-19.0.1.14.3.tar.gz`.

Files changed:
- `__manifest__.py`
- `static/src/workspace.js`
- `static/src/composer.js`
- `static/src/composer.xml`
- `static/src/location.scss`
- `static/tests/message.test.js`
- `static/tests/composer.test.js`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-09-latest-message-location-language.md`
