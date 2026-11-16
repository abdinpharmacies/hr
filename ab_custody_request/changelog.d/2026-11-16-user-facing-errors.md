# Custody user-facing errors

## Current changes before commit:

- Show a translated Validation Error when invalid Telegram token or destination settings prevent a custody notification, so the failed action is rolled back.
- Replace the technical oversized-request traceback with a translated Custody warning recommending smaller attachments or fewer detail lines.
- Register the warning handler only for custody header/line payload errors; other models and errors retain their normal handlers.
- Repair existing translation merge markers while retaining the email-recipient, authorization and success translations; add the new messages to both Arabic language files.

Files changed:
- `__manifest__.py`
- `models/ab_custody_request_header.py`
- `static/src/js/custody_error_handler.js`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-16-user-facing-errors.md`

## a1dfa09b — emadco88 — 2026-11-14

Original commit subject: `ab_custody_request/ FIX emails_to odoo 15 migration code`

- Maintain the migrated email-recipient field and its Arabic labels.

Files changed:
- `models/ab_custody_request_header.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-12-custody-form-layout.md`
- `changelog.d/2026-11-13-email-recipients.md`

Validation:
- Targeted Custody upgrade completed successfully in the configured development database.
- Nine backend checks passed, including invalid token/destination handling, Arabic validation, mocked valid delivery, translated frontend warning data, and custody status rollback.
- Seven frontend handler scenarios passed, including Custody header/line handling and normal fallback for other models/errors.
- Both Arabic files passed `msgfmt --check-format`; JavaScript syntax and Odoo asset transpilation passed.
- Runtime fixtures were rolled back and outbound delivery was blocked or mocked. Live browser rendering was not inspected.
- Follow-up investigation found the live server was still serving a bundle without the Custody handler. Restarted only the configured development instance on port 4099 to reload its manifest assets.
- Confirmed the handler is present in the live `web.assets_web` bundle after restart. Reproduced the exact 413 JSON-RPC response using an oversized Content-Length without a large upload or business mutation.
- Three integration checks using the served JavaScript modules and actual server error response passed: Custody header and line select the translated warning; an unrelated model keeps its standard RPC error dialog. Existing browser tabs require a hard refresh.
