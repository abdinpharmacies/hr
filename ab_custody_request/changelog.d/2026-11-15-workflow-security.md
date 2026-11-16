# Custody workflow and access fixes

## Current changes before commit:

- Restrict request headers and lines to the user's employee or department branches, with explicit Settings administrator and HR Manager exemptions.
- Match payer line visibility to Cash and Visa role membership.
- Validate the caller, current stage, payment type, branch access, and approval window before status transitions; protect direct status writes as well as button calls.
- Recompute the current actor for the current user and request status.
- Clear the unused email template recipient expression referencing the removed `emails_to` field so targeted upgrades succeed without inventing recipients.
- Maintain the new authorization and success messages in both Arabic language files.
- Identify the previous layout changes by their original commit in the historical changelog.

Files changed:
- `models/ab_custody_request_header.py`
- `security/record_rules_ab_custody_request_header.xml`
- `security/record_rules_ab_custody_request_line.xml`
- `data/template_custody_request_email.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-12-custody-form-layout.md`
- `changelog.d/2026-11-15-workflow-security.md`

## ba264998 — hager yasser — 2026-11-12

Original commit subject: `ab_custody_request/FIX: repair form layouts and contain detail table scrolling`

- Repair custody form layouts and keep wide detail tables inside their screens.

Files changed:
- `views/ab_custody_employee_data.xml`
- `views/ab_custody_request_account.xml`
- `views/ab_custody_request_config.xml`
- `views/ab_custody_request_header.xml`
- `changelog.d/2026-11-12-custody-form-layout.md`
