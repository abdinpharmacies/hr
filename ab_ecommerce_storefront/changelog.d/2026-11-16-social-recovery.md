# Verified social contacts and password recovery

Recent relevant commit:

- 0ac9fffe | Mohamed Fawzy | 2026-11-15 | ab_ecommerce_storefront/IMP: support flexible storefront offers

Current changes before commit:

- Author: Alhassan Hossny
- Date: 2026-11-16
- Route the login reset link and profile password changes through one extensible account lookup and channel chooser.
- Show independent social contact status, preserve profile phones and store Telegram verified phone numbers separately.
- Enforce browser, customer, website/company, channel and destination checks; preserve email-link recovery and native token resets.
- Update Arabic catalogs and the POT references used by Odoo imports; add focused HTTP and model regressions.

Validation:

- Targeted fresh setup and upgrades on isolated `social_recovery_20261116`; final source-checkout run: **122 tests, 0 failures, 0 errors, 0 skips** (`final-result.log`).
- Included WhatsApp authentication/transport HTTP and model tests, storefront authentication HTTP and model tests, trusted-browser model tests and signup OTP model tests. Real Chrome verified English/Arabic mobile layouts and translations.
- Two independent transaction races passed: one signup completion and one password-reset completion succeeded; duplicate completions were rejected.
- Python/XML syntax, four Arabic PO format checks, preserved original translations and production package checks passed.
- Adjacent existing `TestSignupOtpHTTP.test_email_registration_and_later_login_work_without_otp` homepage-403 failure reproduced using original committed addons on `social_recovery_baseline_20261116`; excluded from the focused final suite.
- HTTP/gevent ports `5069/5072`; baseline `5070/5073`; workers and cron workers disabled. No user-process restarts or live OTP sends.
- Command: `PYTHONPATH=/tmp/social-recovery/browser-deps /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin -c /tmp/social-recovery/validation.conf -d social_recovery_20261116 --addons-path=/opt/odoo19/server/addons,/opt/odoo19/worktrees/e_commerce -u ab_ecommerce_storefront,ab_storefront_whatsapp_auth --test-tags /ab_storefront_whatsapp_auth,/ab_ecommerce_storefront:TestStorefrontAuthentication,/ab_ecommerce_storefront:TestStorefrontAuthHTTP,/ab_ecommerce_storefront:TestStorefrontAuthDevice,/ab_ecommerce_storefront:TestSignupOtp --stop-after-init --workers=0 --max-cron-threads=0 --http-interface=127.0.0.1 --http-port=5069 --gevent-port=5072 --without-demo=all --logfile=/tmp/social-recovery/final-result.log`.


Follow-up changes before commit (2026-11-16):

- Replace profile verification text with accessible green check icons and use compact channel-colored change icons for verified social contacts.
- Match WhatsApp and Telegram Authentication cards to the existing Phone/Email card, value, status badge and action design in English and Arabic RTL.
- Color signup actions by channel and export the existing Egyptian-phone validator for the optional WhatsApp signup interaction.
- Update both Arabic catalogs and the POT references for the new card and accessible icon labels.

Follow-up validation:

- Final focused suite: **101 tests, 0 failures, 0 errors, 0 skips**, from the ecommerce checkout on `social_recovery_20261116` at `5069/5072`; log `/tmp/social-recovery-followup/final-cards-tests.log`.
- Real Chrome verified signup channel colors and enabled/disabled states, profile icons, verified Authentication badges and four matching channel cards in English/Arabic mobile layouts.
- Both server modules upgraded successfully on `e_commerce`; log `/tmp/social-recovery-followup/server-upgrade.log`. Existing server Python code needs a PyCharm restart to load changed methods.
- Four Arabic PO format checks passed; all ten exported security-card terms are translated in both catalogs. No live OTP sends or cron activation were performed during validation.

Recovery-label and Telegram-token follow-up (2026-11-16):

- Scope New password / Confirm new password labels and placeholders to recovery, including native reset-token forms; keep account-creation wording unchanged.
- Read the Telegram bot API token only from `ab_storefront_auth.telegram_bot_token`, retaining the explicit enable flag and native administrator-only System Parameters access.
- Preserve bot deep-link → own-contact sharing → signup OTP verification. Explain disabled Telegram verification before submission instead of implying an initial message send.
- Retire token-file provisioning; keep the separate inbound webhook secret configuration intact and document manual parameter setup.
- Validation: **106 tests, 0 failures, 0 errors, 0 skips** on isolated `social_recovery_20261116`, HTTP/gevent `5069/5072`; log `/tmp/reset-labels-telegram/final-tests.log`. Includes Arabic recovery rendering, unchanged signup labels, browser availability, parameter ACLs, mocked token/API selection and no-send bot-link startup.
- Python/XML/JS syntax and both Arabic catalog format checks passed. Provisioning smoke check created only the private webhook-secret file. No live provider calls, token entry or Telegram enablement were performed.

Files changed:

- `__manifest__.py`
- `changelog.d/2026-11-16-social-recovery.md`
- `controllers/auth.py`
- `controllers/auth_security.py`
- `controllers/portal.py`
- `docs/social-contact-recovery.md`
- `i18n/ab_ecommerce_storefront.pot`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/auth_channels.py`
- `models/auth_device.py`
- `models/auth_identity.py`
- `models/auth_service.py`
- `static/src/scss/social_contacts.scss`
- `tests/test_auth_http.py`
- `tests/test_authentication.py`
- `views/auth_security_templates.xml`
- `views/portal.xml`
- `static/src/js/auth.js`
- `views/auth.xml`
- `tools/provision_auth_secrets.py`
- `docs/authentication.md`

Telegram reset delivery follow-up (2026-11-16):

- Wake the existing authentication delivery cron when a recovery request is queued; keep provider calls outside the HTTP request.
- Diagnose local reset delivery blocked by inactive authentication cron and `max_cron_threads = 0`; document scoped development delivery without changing bot webhooks or unrelated jobs.
- Add regression coverage for immediate scheduling, queued delivery and cooldown rejection.
- Validation: **67 tests, 0 failures, 0 errors** on isolated `social_recovery_20261116`, targeted storefront/WhatsApp upgrade at `5069/5072`; log `/tmp/telegram-reset-fix/tests.log`. Includes recovery scheduling, OTP binding/expiry/replay, password/session invalidation and WhatsApp permissions/company isolation.
- Live test: user completed Telegram OTP and password reset; consumed OTP and reset grant confirmed server-side. The bounded send-only worker stopped after success; shared callcenter services and webhooks were unchanged. Local ongoing delivery still requires an authentication worker because cron is disabled.
