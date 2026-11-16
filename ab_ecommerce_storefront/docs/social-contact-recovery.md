# Verified social contacts and password recovery

The profile and account-security pages show Phone, Email, WhatsApp and Telegram with explicit contact status. Adding or replacing a social recovery contact requires the current password and proof through that channel. Pending numbers remain on challenges. Verified linking fills an empty profile phone and preserves an existing phone and login.

WhatsApp owns its `whatsapp` verified identity. Telegram stores its verified number in `phone_value` alongside its account/private-chat identity. A generic verified phone does not enable WhatsApp recovery. Email retains its existing link-based recovery behavior, including proving an existing email address through the recovery link; native token reset links remain supported. SMS verification is outside this change.

The standard login reset link redirects to the extensible recovery route. Signed-out customers identify an account by login, email or linked phone, then choose among its available recovery channels. The chooser exposes channel names, with no delivery destinations. Lookups are limited per IP and browser; ambiguous and out-of-scope customers are rejected. Signed-in recovery always targets the current customer.

Recovery challenges retain the selected destination: a WhatsApp number or Telegram account/private chat. Verification checks current ownership and transport availability. Switching invalidates the preceding attempt and password grant. Resend uses the session-selected channel and rejects a changed destination, retaining cooldowns and attempt limits. Proofs expire, are single use and are bound to the browser where required. Password changes invalidate existing sessions and outstanding authentication challenges.

The former WhatsApp recovery URL delegates to the same flow. The channel adapter contract remains optional; no gateway or unused authentication modules are installed by Python.

Existing WhatsApp signup compatibility is conservative and lazy. A completed, verified signup challenge must match the customer's current verified phone identity, login, company, website and signup timestamps unambiguously. Ambiguous evidence logs the customer ID for reverification. Missing or expired evidence requires verification again. No bulk verification updates or migration hooks are included. Live reconciliation and provider pilots remain rollout actions.

## Validation

Validation uses the isolated `social_recovery_20261116` database, HTTP/gevent ports `5069/5072`, no cron workers and mocked provider delivery. Fresh dependency setup required activating `ar_001` before the existing `ab_website` setup function. The final targeted upgrade and authentication suites run directly from `/opt/odoo19/worktrees/e_commerce`.

The final source-checkout run passed 122 tests with no failures, errors or skips. Commands are recorded in the module changelogs. Tests cover the actual login reset link after WhatsApp signup, old/new password login, Telegram recovery, different social numbers, legacy email links, native reset tokens, linking and replacement, forged targets/channels, company/website scope, unavailable transports, expiry, replay, browser binding, cooldowns, encrypted queue/exchange operations and session invalidation. Real Chrome checks cover English and Arabic RTL at a 390 × 844 mobile viewport, translated actions, icons, keyboard focus and viewport fit. Both Arabic catalogs are checked with `msgfmt --check-format`; the storefront POT is updated because Odoo merges its references when importing PO files.

Independent concurrent transactions verified that signup creates one customer and password recovery consumes one grant, rejecting the second completion.

One adjacent existing test fails independently of these changes: `TestSignupOtpHTTP.test_email_registration_and_later_login_work_without_otp` receives a homepage access error after the existing login redirect. The same failure was reproduced using the original committed addons on `social_recovery_baseline_20261116` at `5070/5073`. The focused final suite excludes that existing failing class; its signup OTP model tests remain included.

Production packaging excludes tests, fixtures, demos, Python caches and local provisioning/development tools. Deployment, live database reconciliation, user-process restarts and provider sends were not performed.

## Profile, signup and delivery follow-up

The profile displays accessible green verified-check icons and compact channel-colored change actions. On Authentication, WhatsApp and Telegram use the same method cards, contact values and status badges as Phone/Email, with green/blue channel actions. Signup follows those channel colors; WhatsApp shares Telegram's existing phone validator and stays disabled for incomplete or invalid numbers.

On this server, the authentication delivery cron was disabled while the WhatsApp gateway was polling normally. Recovery requests therefore remained at the intermediate `recovery_request` stage. WhatsApp recovery now processes that preparation event immediately into `wa_pending`, preserving encrypted delivery and worker authorization. It does not call the provider in the browser request and does not enable the disabled cron or flush old requests.

The follow-up source-checkout suite passed 101 tests, including a cron-disabled gateway handoff regression and real Chrome checks for channel colors, phone validation, profile icons, verified badges and English/Arabic mobile cards. All ten exported card terms are covered by both Arabic catalogs. Both modules were upgraded on `e_commerce`. Restart the managed PyCharm Odoo process after Python changes to activate the delivery fix; refreshing a page alone reloads frontend assets but not cached Python methods.

## Recovery labels and Telegram token configuration

After a recovery proof succeeds, the password fields say **New password** and **Confirm new password**, translated as **كلمة المرور الجديدة** and **تأكيد كلمة المرور الجديدة**. Native password-reset links use the same wording; account registration retains its existing labels.

Telegram's bot API token is configured manually in the administrator-only system parameter `ab_storefront_auth.telegram_bot_token`. The existing `ab_storefront_auth.telegram_enabled=True` switch is still required. The initial Telegram signup action creates a bot deep link without sending an OTP. The customer opens the bot and shares their own matching contact before the existing signup OTP step. Missing configuration disables the Telegram action with a verification-availability explanation; it does not bypass contact proof or fall back to token files/environment variables. The independent inbound webhook secret and webhook/polling receiver remain part of the existing deployment setup.

This follow-up passed 106 focused tests with mocked providers, including token parameter privacy, API token selection, bot/contact sequencing, Arabic labels and browser behavior. Actual token entry and enabling Telegram remain the administrator's manual setup actions. Restart the PyCharm Odoo process once after loading these Python changes.
