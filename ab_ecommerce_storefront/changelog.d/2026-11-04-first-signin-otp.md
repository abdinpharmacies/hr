# First sign-in OTP

## Current changes before commit:

- Require new phone customers to enter a six-digit OTP before their first authenticated session.
- Deliver phone codes through the linked private Telegram chat.
- Allow email registration and login without OTP, including accounts with an earlier pending flag; preserve separate, non-blocking email confirmation.
- Keep incomplete phone registrations pending across later login attempts; existing customers, invitations and Google registration retain their existing behavior.
- Bind verification to the password-authenticated account and browser, with expiry, attempt limits, resend cooldown and single use.
- Prevent contact verification, password recovery and trusted-browser approval from replacing the first-sign-in OTP.
- Preserve existing Telegram browser protection after successful first-sign-in verification.
- Add the verification screen and its English/Arabic translations.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/controllers/auth_security.py`
- `ab_ecommerce_storefront/controllers/auth_signup_otp.py`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/auth_device.py`
- `ab_ecommerce_storefront/models/auth_service.py`
- `ab_ecommerce_storefront/models/auth_signup_otp.py`
- `ab_ecommerce_storefront/views/auth_signup_otp_templates.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/tests/__init__.py`
- `ab_ecommerce_storefront/tests/test_auth_http.py`
- `ab_ecommerce_storefront/tests/test_signup_otp.py`
- `ab_ecommerce_storefront/docs/authentication.md`
- `ab_ecommerce_storefront/changelog.d/2026-11-04-first-signin-otp.md`

## Validation

- Isolated database: `codex_signup_otp_20261104`, copied from the idle authentication test database `ab_trusted_browser_test`; HTTP/gevent ports `5069/5072`, cron workers disabled.
- Targeted storefront and API upgrades completed. Selected authentication, trusted-browser, OTP service, HTTP registration and API issuance checks: **66 tests, 0 failures, 0 errors** across the two modules.
- Pending-session state is copied before saving so the OTP token persists between requests. The HTTP tests verify phone account access is blocked before OTP and succeeds after OTP, while email registration and later login succeed directly without an OTP challenge.
- Exported current Odoo POT terms, appended nine terms to both Arabic catalogs, and passed `msgfmt --check-format` for both. Runtime `ar_001` verification view differs from English and contains the translated verification button.
- Final phone-only validation log: `/tmp/signup-otp-phone-only-final.log`. Email tests cover direct registration, later login with an earlier pending flag and API token issuance without OTP; phone tests retain blocked-before-verification behavior.
- External delivery was mocked; no actual email or Telegram messages were sent. The copied database lacks some historical attachment files, producing missing-file informational logs without test failures.
- Development tests remain in the repository and must be excluded from runtime production packaging. No live database upgrade, service restart or deployment was performed.

## Relevant previous commit

Commit: `fae66caa829ecbcdb8e275ca81a7496ac7b3cdac`
Author: Mohamed Fawzy
Date: 2026-10-22
Original subject: `ab_ecommerce_storefront/FIX: preserve pre-authentication device checks`

User-facing changes:

- Preserve trusted-browser checks before authentication without exposing private user records.

Files changed:

- `ab_ecommerce_storefront/models/auth_device.py`
- `ab_ecommerce_storefront/changelog.d/2026-10-21-backend-login-policy.md`
