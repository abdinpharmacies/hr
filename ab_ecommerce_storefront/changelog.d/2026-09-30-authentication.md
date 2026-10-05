# Multi-channel storefront authentication

Commit: `2471a65`
Author: Mohamed Fawzy
Date: 2026-09-27
Original subject: `ab_ecommerce_storefront/feat: add google login option`

User-facing changes:

- Add Google login alongside the phone-first storefront flow.

Files changed:

- `ab_ecommerce_storefront/controllers/auth.py`
- `ab_ecommerce_storefront/static/src/js/auth.js`
- `ab_ecommerce_storefront/views/auth.xml`

## Audit and implementation plan

- Inspect core `web`, `auth_signup`, `auth_oauth`, `portal`, `res.users`, partner signup tokens and session-token generation, plus the storefront controller, templates, JavaScript, partner fields and mail overrides.
- Confirm existing phone signup uses `res.users.login` and related `res.partner.phone` with no ownership proof; email is deliberately absent on phone-first accounts, so the current native email reset cannot recover them.
- Inspect `ab_user_extra`, `ab_telegram_webhook` and `abdin_telegram`; their employee credential-in-chat and reusable PIN flows are not customer recovery providers. Keep the customer bot integration in the explicitly requested storefront module.
- Add unique verified identities on the existing user, expiring challenges, shared rate counters and an encrypted delivery/update queue. Preserve native hashing, backend login, Google OAuth, invitation/reset tokens and `/my/security`.
- Connect email and Telegram adapters, require Telegram's own contact proof before phone signup, protect authenticated linking with password confirmation, and use generic asynchronous recovery requests.
- Add private access controls, autovacuum cleanup, queue cron, deployment settings, Arabic translations, ORM/HTTP/browser tests and secure configuration documentation.

## Current changes before commit

- Name the Abdin Pharma Pharmacies Bot in the verification guidance and direct customers to the Check verification button below.
- Open every Telegram verification attempt directly in the Telegram app with the existing dynamic start token, avoiding a leftover Telegram Web tab while retaining the HTTPS link as a no-JavaScript fallback.
- Keep the Telegram-opened guidance toast visible for 15 seconds while retaining the standard duration for other verification messages.
- Preserve the mobile verification toast's full-width, capped layout without mixed-unit Sass arithmetic, so the frontend asset bundle compiles successfully.
- Show successful phone verification as a floating mobile toast that asks new customers to complete their account details, without duplicating the success alert in the card.
- Send phone-signup customers to the verification status screen first, keep the phone visible, and open Telegram only after their explicit action there.
- Show the exact remaining phone-verification cooldown as a live countdown and re-enable the action automatically when the existing rate-limit window expires.
- Use one clear Start Telegram verification action on the status screen, and return anonymous users to signup with their phone state preserved.
- Restart the local Telegram receiver after a lost database connection instead of attempting a fatal rollback on its closed cursor.
- Keep the Telegram verification action disabled until the shared signup field contains a complete valid Egyptian mobile number, including supported international formats.
- Remove the redundant standalone Continue with phone action from signup while preserving phone entry through the shared email-or-phone field.
- Accept email or phone in the same signup field and support verified email/phone login aliases on the existing account. Phone entries start Telegram proof before account creation; retain only the pending name and ask for the password after verification.
- Restore the submit button after failed requests, validate the combined identity input and explain HTTPS rejection instead of showing an unexpected-error message.
- Open the existing Telegram bot only after an explicit action on the verification screen. Accept private deployment-file paths in Odoo configuration as well as environment variables, and provide a development-only polling receiver with serialized polling and safe diagnostics.
- Show page-scoped Telegram verification toasts for opening the bot and for successful, pending, or expired status checks.
- Preserve the security-page layout when replacing the signup card before Telegram navigation, and keep the Telegram primary-link text readable after browser Back.
- Permit development HTTP for literal loopback addresses, including `127.0.0.4`, with the same policy for request security and generated links. Require a loopback client as well; reject LAN/public addresses, lookalike names and spoofed localhost hosts, and retain HTTPS-only production.
- Verify phone signup through a browser-bound Telegram deep link, private chat and matching self-shared contact; confirm the Telegram connection on the website before creating or updating an account.
- Recover through provider-independent email links or hashed Telegram OTPs with expiry, single use, attempt limits, resend cooldowns, database-backed rate limits and browser-bound reset grants.
- Require the current password before linking recovery identities; invalidate outstanding recovery challenges after identity/password changes and preserve Odoo session invalidation.
- Authenticate HTTPS webhooks using a deployment secret, deduplicate update IDs, process encrypted queued delivery in bounded cron runs and clean expired temporary records through Odoo autovacuum.
- Configure nonsecret settings in Odoo; read bot credentials from private deployment files or a secret-manager environment. Use the existing `@Abdin_Pharmacy_Bot`.
- Add Arabic translations for both locales, compact security screens and deployment/polling/rotation procedures.
- Retain the requested development tests in the repository. Test databases and screenshots stay outside the addon package; no demo records or credentials are shipped.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/changelog.d/2026-09-30-authentication.md`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/controllers/auth.py`
- `ab_ecommerce_storefront/controllers/auth_security.py`
- `ab_ecommerce_storefront/data/auth_queue.xml`
- `ab_ecommerce_storefront/docs/authentication.md`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/auth_channels.py`
- `ab_ecommerce_storefront/models/auth_identity.py`
- `ab_ecommerce_storefront/models/auth_service.py`
- `ab_ecommerce_storefront/models/auth_settings.py`
- `ab_ecommerce_storefront/models/res_users.py`
- `ab_ecommerce_storefront/security/auth_security.xml`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/static/src/js/auth_proof.js`
- `ab_ecommerce_storefront/static/src/js/auth_phone_verification.js`
- `ab_ecommerce_storefront/static/src/js/auth.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/static/src/scss/auth_security_bundle.scss`
- `ab_ecommerce_storefront/tests/__init__.py`
- `ab_ecommerce_storefront/tests/test_authentication.py`
- `ab_ecommerce_storefront/tests/test_auth_http.py`
- `ab_ecommerce_storefront/tools/provision_auth_secrets.py`
- `ab_ecommerce_storefront/tools/telegram_development_poll.py`
- `ab_ecommerce_storefront/views/auth.xml`
- `ab_ecommerce_storefront/views/auth_security_templates.xml`
- `ab_ecommerce_storefront/views/auth_settings.xml`

## Database and routes

New persistent models: `ab_storefront_auth_identity`, `ab_storefront_auth_challenge`, `ab_storefront_auth_rate`, `ab_storefront_auth_event`. New columns also extend the existing transient settings model. No changes to stock, prices, branches or external databases.

New routes:

- `GET/POST /ab_storefront/auth/recover`
- `GET/POST /ab_storefront/auth/confirm`
- `GET/POST /ab_storefront/auth/phone`
- `GET/POST /my/authentication`
- `POST /ab_storefront/auth/telegram/webhook`

Existing routes: preserve `/web/login`, add email signup to `/web/signup`, and route tokenless `/web/reset_password` requests to generic recovery while retaining native token handling.

## Deployment

See `../docs/authentication.md` for the exact secret provisioning, environment, webhook registration, local polling, production rollout, token rotation and disablement commands. No new BotFather account is required. Live Telegram delivery remains dependent on securely configured credentials and a user's actual Telegram contact-sharing interaction.

## Validation

- Release suite: 48 Odoo tests passed, zero failures or errors, on isolated database `ab_auth_task26_test` and ports `5069`/`5072`.
- Cover email signup/verification/recovery, invalid/expired/used tokens, generic account responses, verified identity collisions, phone signup, matching private Telegram contact proof, one-time deep links, OTP attempts/reuse/expiry/cooldown, recovery channel selection, encrypted delivery cleanup, retries, duplicate updates, access denials, password/session invalidation and a third OTP adapter.
- HTTP tests exercise email signup/reset and phone signup/Telegram recovery. Desktop `1366x900` and mobile `390x844` browser checks validate proof transfer, URL clearing and viewport fit; screenshots were visually inspected.
- Shared-field HTTP tests cover email signup, phone deep linking, no account before contact proof, missing Telegram configuration, invalid identity and HTTPS rejection. Desktop/mobile browser tests cover input switching and submit-button recovery after 503/403 responses.
- Test secret-file loading from Odoo configuration, environment-file precedence, unreadable permissions and fail-closed missing files. Live `getMe` validated the existing bot using the administrator's private file without printing credentials; confirm no webhook is registered before starting the transient development receiver.
- Live desktop/mobile navigation checks verify that signup opens the existing bot with a one-time token and browser Back returns to the phone-verification page without viewport overflow. Telegram navigation is intercepted in the QA browser; real Telegram contact-sharing and OTP delivery require the administrator/user's manual interaction.
- Apply localhost-only development mode and the `http://localhost:4092` authentication origin on `ecom19` with user approval; gracefully reload the existing process without rerunning unrelated module upgrades. Live Arabic desktop/mobile checks confirm the combined field, phone/password switching and viewport fit.
- Arabic runtime view checks passed. Both `ar.po` and `ar_001.po` passed `msgfmt --check-format` after merging references from Odoo's exported POT.
- Python syntax, XML parsing, Pyflakes, JavaScript syntax and `git diff --check` passed.
- Live Arabic status checks render translated success, pending, and expired result toasts. Fresh LTR and RTL frontend bundles compile and serve the scoped toast at HTTP 200, and the backend `web.assets_web` bundle also compiles at HTTP 200.
- Test output: `/tmp/ab-auth-bot-connect-tests.log`; proof screenshots: `/tmp/ab-auth-shared-screenshots/ab_auth_task26_test/screenshots/`; live shared-signup screenshots: `/tmp/ab-auth-email-390.png`, `/tmp/ab-auth-phone-390.png`, `/tmp/ab-auth-bot-return-390.png` and corresponding desktop files.
- The initial targeted upgrade of existing `ecom19` loaded the auth integration but reported pre-existing missing `ab_seo_template`/`ab_seo_template_section` tables. The isolated install/upgrade and release tests passed; unrelated SEO modules were not changed.
