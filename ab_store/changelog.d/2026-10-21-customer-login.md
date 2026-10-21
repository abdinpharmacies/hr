# Customer login IP restrictions

## Current changes before commit:

- Apply branch IP restrictions only to internal users after successful credential verification.
- Allow portal customers to sign in and finish signup from their own internet connections without granting employee permissions.
- Preserve administrator, Login From Anywhere, trusted-network and configured-IP behavior for employees.
- No user-facing strings changed; existing English and Arabic messages are preserved.

Files changed:

- `ab_store/models/res_users_inherit.py`
- `ab_store/changelog.d/2026-10-21-customer-login.md`

Validation:

- Fresh installation of `ab_store` and `auth_signup` on isolated local database `codex_ab_store_ip_20261021` succeeded.
- All 11 Odoo transaction tests passed: portal external/missing IP, invalid password, signup then login, denied portal allowlist access, employee external/missing IP denial, employee trusted/allowlisted IP, disabled allowlist entry, administrator and Login From Anywhere access.
- Development-only test copy and installation log retained under `/tmp/ab_store_login_validation`; no test fixtures added to the runtime addon.
- Existing `i18n/ar_001.po` passed `msgfmt --check-format`; `i18n/ar.po` is absent in the existing module. No translation additions are required because this change adds no UI strings.
- Demo deployment requires a service restart only; no database upgrade.

## Relevant authentication history

Commit: `e91f6412dc0f3ebcce931927ba57703dbe46d271`
Author: emadco88
Date: 2026-03-30
Original commit subject: `Initial commit`

- Introduce credential verification followed by IP restrictions, with administrator and Login From Anywhere exceptions.

Files changed (authentication scope):

- `ab_store/models/res_users_inherit.py`
