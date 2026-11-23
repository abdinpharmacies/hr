# Restore the website composer layout

Current changes before commit:
- Match the Telegram composer controls with the paperclip attachment menu and emoji picker.
- Place Saved replies inside the attachment menu and remove the standalone composer button.
- Preserve website text-only sending, reply destinations, template permissions and navigation guards.
- Verify English desktop and Arabic mobile attachment-menu insertion and emoji editing.

Files changed:
- __manifest__.py
- static/src/order.xml
- i18n/ar.po
- i18n/ar_001.po
- tests/test_contact_groups.py
- changelog.d/2026-11-18-composer-attachment-menu.md

Validation:
- Four browser tests passed, zero failures/errors/skips, including English desktop and Arabic mobile.
- Isolated database: website_chat_validation_20261117; HTTP/gevent: 5075/5076.
- Evidence: /tmp/website-composer-attachment-menu-tests.log.
- Both Arabic catalogs pass gettext format checks; manifest/XML and diff checks pass.
