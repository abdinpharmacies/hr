# First sign-in OTP integration

## Current changes before commit:

- Deny bearer-token issuance for phone customers whose first-sign-in OTP is pending.
- Return a website verification handoff from registration and password login instead of authenticated credentials for pending customers.
- Document the handoff response; OTP submission remains a website flow.
- Allow email registration and login to issue credentials without OTP, even when an older pending flag exists.
- Add focused tests for blocked pending phone customers, allowed verified phone customers and email customers.

Files changed:

- `ab_ecommerce_api/controllers/api.py`
- `ab_ecommerce_api/models/api_session.py`
- `ab_ecommerce_api/README.md`
- `ab_ecommerce_api/tests/__init__.py`
- `ab_ecommerce_api/tests/test_signup_otp.py`
- `ab_ecommerce_api/changelog.d/2026-11-04-first-signin-otp.md`

Validation: targeted upgrade on isolated `codex_signup_otp_20261104`; all three API OTP tests passed as part of 66 successful authentication tests across the API and storefront. No new translatable UI strings were introduced in this module. Existing development tests were preserved.

## Relevant previous commit

Commit: `3ad02a45916217a813a9535b058a95b6681439c0`
Author: Mohamed Fawzy
Date: 2026-10-22
Original subject: `ab_ecommerce_api/ADD: introduce customer ecommerce API`

User-facing changes:

- Introduce customer authentication, scoped sessions and ecommerce API operations.

Relevant files changed (authentication integration):

- `ab_ecommerce_api/controllers/api.py`
- `ab_ecommerce_api/models/api_session.py`
- `ab_ecommerce_api/README.md`
