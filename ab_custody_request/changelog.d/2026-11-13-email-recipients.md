# ab_custody_request

## Current changes before commit:

- Restore the nonstored `emails_to` field required by the existing custody email template, preserving the intended computed/sudo behavior.
- Collect employee and manager work emails in stable order, trim whitespace, remove duplicates, and handle missing recipients. Invalidate recipients after employee/email/manager changes and support multi-record computation.
- Add the English `Email Recipients` label and Arabic translations for both `ar` and `ar_001`, using the reference from an actual Odoo 19 module POT export. Preserve existing translations and provide explicit language/plural headers.
- Relabel the previously committed form-layout changelog section with its actual commit metadata instead of describing it as current work.

Files changed:

- `ab_custody_request/models/ab_custody_request_header.py`
- `ab_custody_request/i18n/ar.po`
- `ab_custody_request/i18n/ar_001.po`
- `ab_custody_request/changelog.d/2026-11-12-custody-form-layout.md`
- `ab_custody_request/changelog.d/2026-11-13-email-recipients.md`

Validation:

- Fresh installation of the actual custody module and its dependencies succeeded in a generated disposable Odoo 19 database. A subsequent targeted `-u ab_custody_request` also succeeded after activating Arabic and adding translations.
- Native ORM checks passed for employee-only, manager-only, two recipients, duplicate, empty, whitespace, and multi-record computations, plus cached-field invalidation after employee email, manager email, manager reassignment, and employee replacement.
- The existing template passed `_check_can_be_rendered`; its actual inline recipient expression rendered the expected address. No outgoing mail was created, and no email or Telegram send method was called.
- Runtime `ar_001` field-label and request-action checks differ correctly from `en_US`. Both PO files pass `msgfmt --check-format`; Python compilation and `git diff --check` pass.
- No production/test-addon scaffolding, hooks, schema migrations, or automatic notification sending was added. The actual source and `main19` databases were not changed; the disposable validation database was removed after verification.
