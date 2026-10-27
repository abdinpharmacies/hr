# Backend login regressions

## Current changes before commit:

- Verify administrator and internal developer backend logins over HTTP, including legacy redirects, native MFA, and rejected passwords.
- Verify storefront redirects still require HTTPS and pre-authentication device checks do not expose user fields to the public user.

Validation: Seven targeted tests passed on isolated `ecom19_cart_hold_20261018` with the checkout worktree selected as the addons path and a database filter set for HTTP tests.

Files changed:

- `ab_ecommerce_storefront/tests/test_auth_device.py`
- `ab_ecommerce_storefront/changelog.d/2026-10-27-backend-login-regressions.md`

## Recent relevant commit

- Commit: `fae66caa829ecbcdb8e275ca81a7496ac7b3cdac`
- Author: Mohamed Fawzy
- Date: 2026-10-22
- Original subject: `ab_ecommerce_storefront/FIX: preserve pre-authentication device checks`
- Preserved device policy checks before authentication.

Files changed:

- `ab_ecommerce_storefront/changelog.d/2026-10-21-backend-login-policy.md`
- `ab_ecommerce_storefront/models/auth_device.py`
