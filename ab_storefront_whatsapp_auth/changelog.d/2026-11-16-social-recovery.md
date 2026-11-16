# Verified social contacts and password recovery

Recent relevant commit:

- d15b1a19 | Alhassan Hossny | 2026-11-16 | ab_storefront_whatsapp_auth/feat: add WhatsApp phone verification and password recovery

Current changes before commit:

- Author: Alhassan Hossny
- Date: 2026-11-16
- Create a distinct verified WhatsApp identity at signup and after password-confirmed contact linking.
- Deliver recovery to the verified WhatsApp number through the existing encrypted transport and shared limits.
- Support unambiguous completed signup evidence conservatively and require reverification otherwise.
- Delegate the compatibility recovery URL to the shared flow and test no-Telegram signup-to-reset, ownership, channel switching and concurrent completion.

Validation:

- Targeted fresh setup and upgrades on isolated `social_recovery_20261116`; final source-checkout run: **122 tests, 0 failures, 0 errors, 0 skips** (`final-result.log`).
- Included WhatsApp authentication/transport HTTP and model tests, storefront authentication HTTP and model tests, trusted-browser model tests and signup OTP model tests. Real Chrome verified English/Arabic mobile layouts and translations.
- Two independent transaction races passed: one signup completion and one password-reset completion succeeded; duplicate completions were rejected.
- Python/XML syntax, four Arabic PO format checks, preserved original translations and production package checks passed.
- Adjacent existing `TestSignupOtpHTTP.test_email_registration_and_later_login_work_without_otp` homepage-403 failure reproduced using original committed addons on `social_recovery_baseline_20261116`; excluded from the focused final suite.
- HTTP/gevent ports `5069/5072`; baseline `5070/5073`; workers and cron workers disabled. No user-process restarts or live OTP sends.
- Command: `PYTHONPATH=/tmp/social-recovery/browser-deps /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin -c /tmp/social-recovery/validation.conf -d social_recovery_20261116 --addons-path=/opt/odoo19/server/addons,/opt/odoo19/worktrees/e_commerce -u ab_ecommerce_storefront,ab_storefront_whatsapp_auth --test-tags /ab_storefront_whatsapp_auth,/ab_ecommerce_storefront:TestStorefrontAuthentication,/ab_ecommerce_storefront:TestStorefrontAuthHTTP,/ab_ecommerce_storefront:TestStorefrontAuthDevice,/ab_ecommerce_storefront:TestSignupOtp --stop-after-init --workers=0 --max-cron-threads=0 --http-interface=127.0.0.1 --http-port=5069 --gevent-port=5072 --without-demo=all --logfile=/tmp/social-recovery/final-result.log`.


Follow-up changes before commit (2026-11-16):

- Process WhatsApp recovery preparation immediately into the existing encrypted gateway queue, removing the dependency on a disabled authentication cron without making provider calls in the HTTP request.
- Disable WhatsApp signup for incomplete/invalid numbers using the same phone validator as Telegram, retaining email-mode visibility and submit guards.
- Cover disabled-cron recovery handoff, profile icons, matching Authentication cards, channel colors, Arabic numerals and keyboard/mobile behavior.

Follow-up validation:

- Final focused suite: **101 tests, 0 failures, 0 errors, 0 skips**, from the ecommerce checkout on `social_recovery_20261116` at `5069/5072`; log `/tmp/social-recovery-followup/final-cards-tests.log`.
- Real Chrome verified signup channel colors and enabled/disabled states, profile icons, verified Authentication badges and four matching channel cards in English/Arabic mobile layouts.
- Both server modules upgraded successfully on `e_commerce`; log `/tmp/social-recovery-followup/server-upgrade.log`. Existing server Python code needs a PyCharm restart to load changed methods.
- Four Arabic PO format checks passed; all ten exported security-card terms are translated in both catalogs. No live OTP sends or cron activation were performed during validation.

WhatsApp Authentication Settings fix (2026-11-16):

- Fix the list/form XML declarations so Odoo 19 can read them from source with `--dev=xml`; compact `<field name="arch">` declarations previously left `field_arch.text` empty and raised a TypeError when opening Settings.
- Preserve the action, menus, view XML IDs, fields, translations and access controls.
- Add a regression calling `get_views` as the Settings administrator with `read_arch_from_file=True` for both views.
- Validation: **32 model/security tests, 0 failures, 0 errors** on isolated `social_recovery_20261116`; log `/tmp/whatsapp-settings-fix/tests.log`. Both Arabic catalogs pass format checks; no user-facing strings changed.
- Targeted `ab_storefront_whatsapp_auth` upgrade completed on `e_commerce`; log `/tmp/whatsapp-settings-fix/server-upgrade.log`. English and Arabic list/form source loading verified as the Settings administrator on that database. No user-process restart or provider calls required.

Files changed:

- `changelog.d/2026-11-16-social-recovery.md`
- `controllers/auth.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/identity.py`
- `models/service.py`
- `tests/check_concurrency.py`
- `tests/test_http.py`
- `tests/test_whatsapp.py`
- `views/auth.xml`
- `static/src/js/signup.js`
- `views/transport.xml`
