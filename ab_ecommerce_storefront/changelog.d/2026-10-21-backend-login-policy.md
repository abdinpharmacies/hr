# Backend login device-policy access

## Current changes before commit:

Author: Mohamed Fawzy
Date: 2026-10-21

- Fix a pre-authentication access error when the public request evaluates
  whether the authenticated account needs storefront device approval.
- Read only the target account's device-policy inputs in a private elevated
  helper that returns a boolean; do not grant public access to user records.
- Preserve HTTP backend login for `/odoo` and `/web` redirects, including
  internal users in developer mode, without weakening storefront HTTPS checks.
- Preserve native administrator MFA, customer device approval, wrong-password
  rejection and private-model ACLs.
- Validate regression coverage for administrator/internal-user login and policy
  evaluation from the public environment.

Files changed:

- `ab_ecommerce_storefront/models/auth_device.py`
- `ab_ecommerce_storefront/changelog.d/2026-10-21-backend-login-policy.md`

## Relevant prior commit

Commit: `a52fb67eb99e5a8886f79dfd27b48efec04839cc`
Author: Mohamed Fawzy
Date: 2026-10-20
Original subject: `ab_ecommerce_storefront/IMP: require approval for untrusted browser sign-in`

- Added Telegram-linked customer device approval and recovery-code workflows.

Relevant files changed:

- `ab_ecommerce_storefront/models/auth_device.py`
- `ab_ecommerce_storefront/tests/test_auth_device.py`
