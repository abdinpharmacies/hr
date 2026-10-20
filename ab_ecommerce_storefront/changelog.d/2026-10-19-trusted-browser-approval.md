# Trusted browsers and Telegram sign-in approval

## Recent relevant commit

Commit: `855b7dd32e7f201c8329368296e800edde2ce24c`
Author: Mohamed Fawzy
Date: 2026-10-05
Original subject: `ab_ecommerce_storefront/feat: add verified email and Telegram account recovery`

User-facing changes relevant to this feature:

- Verify phone ownership through a linked private Telegram identity.
- Recover accounts through verified identities and manage account security.

Files changed relevant to this feature:

- `ab_ecommerce_storefront/controllers/auth.py`
- `ab_ecommerce_storefront/controllers/auth_security.py`
- `ab_ecommerce_storefront/models/auth_service.py`
- `ab_ecommerce_storefront/models/auth_channels.py`
- `ab_ecommerce_storefront/security/auth_security.xml`
- `ab_ecommerce_storefront/views/auth_security_templates.xml`

## Current changes before commit:

- Require Telegram approval or a saved recovery code before an unremembered browser can access a protected customer account.
- Offer Approve/Reject buttons in the linked private Telegram chat, with session binding, five-minute expiry and single-use decisions.
- Allow customers to remember verified browsers for 30 days using a secure, HTTP-only cookie and server-side keyed digest.
- Add browser revocation and eight independently generated, single-use recovery codes shown only when generated.
- Revoke browser trust and pending approvals after password changes or recovery; preserve unused recovery codes as an independent fallback.
- Limit approval notifications and apply progressive source-specific cooldowns after rejection without disabling the account or existing sessions.
- Protect password-only RPC and alternate login redirects, retain native staff/MFA policy, and deny portal/public ORM access to private security records.
- Add English/Arabic screens and bot messages, preserving existing translation entries.
- Update existing authentication tests for the approval step, explicit test languages and current interface wording.
- Preserve the existing fixed-window limiter and delivery queue; add no cron, Redis dependency, hooks or business-data changes.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/controllers/auth.py`
- `ab_ecommerce_storefront/controllers/auth_security.py`
- `ab_ecommerce_storefront/controllers/auth_device.py`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/auth_service.py`
- `ab_ecommerce_storefront/models/auth_channels.py`
- `ab_ecommerce_storefront/models/auth_device.py`
- `ab_ecommerce_storefront/security/auth_security.xml`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/views/auth_device_templates.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/tests/__init__.py`
- `ab_ecommerce_storefront/tests/test_auth_device.py`
- `ab_ecommerce_storefront/tests/test_auth_http.py`
- `ab_ecommerce_storefront/docs/authentication.md`
- `ab_ecommerce_storefront/changelog.d/2026-10-19-trusted-browser-approval.md`

Validation:

- Fresh installation and subsequent targeted upgrades passed in dedicated database `ab_trusted_browser_test`, with HTTP/gevent ports `5169/5172` and a separate data directory under `/tmp/ab-trusted-browser-validation`.
- Final authentication run passed 76 tests with zero failures/errors. Log: `/tmp/ab-trusted-browser-validation/tests-7.log`.
- Tests cover ordinary/trusted browser login, password-first partial sessions, approval ownership, rejection, expiry, replay, recovery codes, credential changes, API/redirect bypasses, CSRF and private-model ACLs.
- Chrome checked Arabic mobile approval and English desktop browser management without horizontal overflow; screenshots were visually inspected. Existing signup and recovery browser tests also passed.
- Both Arabic catalogs passed `msgfmt --check-format`; Odoo POT references were merged and Arabic view content was verified at runtime.
- Python/XML parsing, manifest data-file references, translation coverage and `git diff --check` passed.
- External Telegram delivery was substituted in tests. No real bot messages or webhook changes were sent, and the running application database/process was not upgraded or restarted.
- Deployment requires the targeted module upgrade, worker reload and webhook registration with `message` plus `callback_query`. Existing queue latency applies to both delivery and approval processing.
- Development tests remain in the repository; runtime distributions must omit tests and generated caches as required by the project.
