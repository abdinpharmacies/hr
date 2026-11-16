# Change record

New addon; no prior commits.

Current changes before commit:

- Add independent WhatsApp phone signup and password recovery with encrypted delivery leases, scoped native Bearer exchange and English/Arabic screens.
- Author: Alhassan Hossny
- Date: 2026-11-15
- Keep activation disabled pending approved templates and an authorized pilot.

Files changed:

- `__init__.py`
- `__manifest__.py`
- `controllers/__init__.py`
- `controllers/auth.py`
- `controllers/exchange.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/service.py`
- `models/transport.py`
- `security/ir.model.access.csv`
- `security/security.xml`
- `static/src/js/signup.js`
- `tests/__init__.py`
- `tests/check_concurrency.py`
- `tests/test_http.py`
- `tests/test_whatsapp.py`
- `views/auth.xml`
- `views/transport.xml`
- `changelog.d/current.md`

Activation preparation (2026-11-16):

- Provision the dedicated service account through module-owned security XML with stable XML ID and minimal groups.
- Files changed: `security/service_user.xml`, `__manifest__.py`.

Signup navigation correction (2026-11-16):

- Keep WhatsApp visibility and click handling active when login/signup cards are replaced by the existing animated navigation.
- Delegate only WhatsApp controls from the persistent authentication page and observe inserted form content.
- Preserve existing storefront and Telegram source files. No new user-facing strings.
- Added browser coverage for navigation, keyboard focus and intercepted WhatsApp submission without a live send.
- Validation: 26 addon tests passed on `wa_auth_test_20261115`; log `/tmp/wa-auth-signup-navigation-final.log`.
- Files changed: `static/src/js/signup.js`, `tests/test_http.py`, `changelog.d/current.md`.
