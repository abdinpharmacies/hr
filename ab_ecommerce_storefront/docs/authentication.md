# Storefront authentication deployment

This addon attaches verified email, E.164 phone and private Telegram identities to the existing Odoo user. It preserves Odoo password hashing, backend login, Google OAuth, invitation tokens and the portal password-change page. Customer recovery lives at `/ab_storefront/auth/recover`; identity management lives at `/my/authentication`.

## Existing bot and secure credentials

Use the existing **Abdin Pharmacy Bot**, `@Abdin_Pharmacy_Bot`. No new bot is required. The administrator already completed BotFather creation. To retrieve or rotate its credentials, open the official [BotFather](https://t.me/BotFather), send `/mybots`, choose `@Abdin_Pharmacy_Bot`, then **API Token**. For rotation, choose **Revoke current token** and provide the replacement through the same secret provisioning process. Never paste credentials into Odoo shell, command arguments, repository files, tickets or logs.

Run this as the operating-system user that runs Odoo. The directory must be outside the repository. The command prompts privately for the existing token and creates a separate random webhook secret. It refuses to overwrite existing files.

```bash
python3 /opt/odoo19/custom-addons-ecommerce/ab_ecommerce_storefront/tools/provision_auth_secrets.py \
  --directory "$HOME/.config/odoo-storefront-auth"
```

Set these environment variables in the Odoo service environment and in administrative Odoo shell sessions. Substitute the absolute directory produced above; the environment contains paths, not credentials.

```ini
AB_STOREFRONT_TELEGRAM_TOKEN_FILE=/absolute/private/directory/telegram_token
AB_STOREFRONT_TELEGRAM_WEBHOOK_SECRET_FILE=/absolute/private/directory/telegram_webhook_secret
```

For systemd, put `Environment=AB_STOREFRONT_TELEGRAM_TOKEN_FILE=/absolute/private/directory/telegram_token` and the corresponding webhook-secret `Environment=` entry in the Odoo service override. Restart that service after installing/upgrading. For a development shell:

```bash
export AB_STOREFRONT_TELEGRAM_TOKEN_FILE="$HOME/.config/odoo-storefront-auth/telegram_token"
export AB_STOREFRONT_TELEGRAM_WEBHOOK_SECRET_FILE="$HOME/.config/odoo-storefront-auth/telegram_webhook_secret"
```

File permissions must be `0600` and ownership must match the service user. Direct environment values `AB_STOREFRONT_TELEGRAM_TOKEN` and `AB_STOREFRONT_TELEGRAM_WEBHOOK_SECRET` are supported for deployment secret managers. Neither credential is stored in `ir.config_parameter`. The existing Odoo `database.secret` protects hashes and encrypted queue payloads; retain it in protected database backups. Odoo administrators are trusted operators.

For an existing privately created token file, no provisioning command is required. It must contain only the bot token and have mode `0600`. Alternatively to environment variables, add nonsecret file paths to the deployment's private Odoo configuration under `[options]`:

```ini
ab_storefront_telegram_token_file = /absolute/private/directory/telegram_token
ab_storefront_telegram_webhook_secret_file = /absolute/private/directory/telegram_webhook_secret
```

Environment `_FILE` settings take precedence over these Odoo configuration paths. A configured missing or publicly readable file fails closed; the token itself must never be placed in the configuration file. Restart Odoo after changing deployment file paths.

## Installation and nonsecret settings

Install `phonenumbers` and `cryptography` in the deployment's Odoo virtual environment. The existing website dependencies require Arabic (`ar_001`) to be installed; use `--load-language=ar_001` when installing a fresh test environment. Upgrade only this addon, with the appropriate database/configuration and unused ports:

```bash
/opt/odoo19/venv19/bin/pip install phonenumbers cryptography
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin \
  -c /opt/odoo19/custom-addons-ecommerce/odoo19.conf -d ecom19 \
  -u ab_ecommerce_storefront --stop-after-init --workers=0 \
  --max-cron-threads=0 --http-port=5069 --gevent-port=5072
```

Settings contains a **Storefront Authentication** app. Set the public HTTPS authentication origin and webhook URL, enable Telegram, and retain the existing bot username. The equivalent exact Odoo shell configuration follows. Replace `https://shop.example.com` with the actual deployed origin. No secret appears in this command.

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin shell \
  -c /opt/odoo19/custom-addons-ecommerce/odoo19.conf -d ecom19 \
  --no-http --logfile=/tmp/storefront-auth-admin.log <<'PY'
p = env['ir.config_parameter'].sudo()
p.set_param('ab_storefront_auth.base_url', 'https://shop.example.com')
p.set_param('ab_storefront_auth.telegram_bot_username', 'Abdin_Pharmacy_Bot')
p.set_param('ab_storefront_auth.telegram_webhook_url', 'https://shop.example.com/ab_storefront/auth/telegram/webhook')
p.set_param('ab_storefront_auth.telegram_enabled', 'True')
p.set_param('ab_storefront_auth.development', 'False')
p.set_param('auth_signup.reset_password', 'True')
env.cr.commit()
PY
```

Self-registration also requires Odoo's normal `auth_signup.invitation_scope=b2c` setting. Configure Odoo's outgoing mail server and the company email address normally; Gmail, SMTP or another mail transport does not change the authentication service.

| Parameter prefix `ab_storefront_auth.` | Default | Effective bounds |
| --- | --- | --- |
| `otp_expiration` | 300 seconds | 1 to 900 |
| `token_expiration` | 900 seconds | 1 to 3600 |
| `otp_max_attempts` | 5 | 1 to 10 |
| `resend_cooldown` | 60 seconds | 1 to 3600 |
| `rate_limit` | 5 requests per identity per hour | 1 to 100 |
| `ip_rate_limit` | 20 recovery requests per IP per hour | 1 to 200 |

Reset grants last five minutes. Additional limits protect signup, identity linking, current-password confirmation, verification submissions and bot commands. Limits are PostgreSQL-backed and shared across workers. Phone input uses Egypt as the default region and accepts valid international E.164 numbers. Existing unverified phone logins continue working; they cannot recover through Telegram until linked.

## Register the production webhook

Run the following with the secret-file environment already exported. It validates the configured bot username against `getMe` and sends `setWebhook` with `secret_token`, `allowed_updates=["message"]` and `drop_pending_updates=false`. Only a success message is printed.

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin shell \
  -c /opt/odoo19/custom-addons-ecommerce/odoo19.conf -d ecom19 \
  --no-http --logfile=/tmp/storefront-auth-admin.log <<'PY'
env['ab_storefront_auth_telegram'].sudo()._configure_webhook()
env.cr.commit()
print('Telegram webhook configured.')
PY
```

The webhook is HTTPS-only in production and authenticates the `X-Telegram-Bot-Api-Secret-Token` header using constant-time comparison. Route the public hostname to exactly one Odoo database using `dbfilter`; pass the secret header through the reverse proxy. Configure Odoo `proxy_mode=True` behind a trusted proxy that overwrites forwarded headers. Block direct access to Odoo's HTTP port. Disable proxy request-body logging for authentication routes and never enable HTTP payload tracing. Email proof tokens use URL fragments so they are absent from access-log paths. Apply edge request limits and a 16 KB body limit to the webhook.

Telegram supports one webhook per bot. Do not register this bot with the existing employee Telegram webhook or run a second polling consumer for it. This addon deliberately does not depend on the employee bot modules, whose persistent PIN and credential-in-chat behavior is unsuitable for customer recovery.

Keep at least one production cron worker active. `Storefront authentication delivery` runs every minute, processes up to 100 events within a 30-second budget, and commits progress per event when invoked by cron. Webhook HTTP requests only validate and enqueue; they do not call Telegram. Linking replies and OTP delivery normally arrive in the next cron cycle at low load. Email jobs enter Odoo's mail queue, so its mail-delivery cron must also be active. Monitor pending/failed `ab_storefront_auth_event` records as an administrator; diagnostics contain event IDs, channel names and attempt counts, never credentials or codes.

## Development and live delivery testing

Use a dedicated development database and service, unused ports and the same private secret files. Set `ab_storefront_auth.development=True`, set `base_url` to the actual local origin, and enable Telegram. Development HTTP is allowed only on `localhost` or literal loopback addresses (`127.0.0.0/8` and `::1`), and the connecting client must also be loopback. This includes `127.0.0.4`; LAN/public addresses and lookalike DNS names still require HTTPS.

The main signup field accepts an email address or a phone number. Email signup uses the password fields and queues email verification. Phone input starts Telegram verification; after sharing the matching personal contact in the bot, return to the website, confirm the connection and choose a password. The entered name is retained, but no password is stored in the pending signup session. If Telegram is disabled or its secret is missing, phone signup displays an availability error and does not create an unverified account.

The signup button creates the linking request and moves the existing tab to the phone-verification page without opening Telegram. The page keeps the entered phone visible, and the customer explicitly selects **Start Telegram verification** there to open the generated deep link in a new tab. Returning from Telegram therefore leads back to the verification page rather than starting signup again. No redirect is performed for failed or unavailable linking requests.

For the local `ecom19` instance at port `4092`, run the following in an Odoo development shell, then restart the existing development process and refresh the browser:

```python
p = env['ir.config_parameter'].sudo()
p.set_param('ab_storefront_auth.development', 'True')
p.set_param('ab_storefront_auth.base_url', 'http://localhost:4092')
env.cr.commit()
```

Use a loopback origin such as `http://localhost:4092`, `http://127.0.0.1:4092` or `http://127.0.0.4:4092`, not a LAN IP address. Set `base_url` to the origin actually used for development. Production must retain `development=False` and an HTTPS `base_url`.

If no public HTTPS endpoint is available, use polling only after removing this bot's webhook. This affects the bot globally, so do not do it while production uses this bot. In a development Odoo shell:

```python
env['ab_storefront_auth_telegram'].sudo()._api('deleteWebhook', {'drop_pending_updates': False})
env.cr.commit()
```

If the bot has no webhook, a development receiver can run as a transient user service. It does not register or delete webhooks and stops polling if development mode or Telegram is disabled. Do not run a second polling consumer for this bot.

```bash
systemd-run --user --unit=ab-storefront-telegram-dev --collect \
  --property=Restart=on-failure \
  /bin/bash -c 'exec /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin shell -c /opt/odoo19/custom-addons-ecommerce/odoo19.conf -d YOUR_DEVELOPMENT_DB --no-http --logfile=/tmp/storefront-auth-poll.log < /opt/odoo19/custom-addons-ecommerce/ab_ecommerce_storefront/tools/telegram_development_poll.py'
```

Stop this development-only receiver before registering a production webhook:

```bash
systemctl --user stop ab-storefront-telegram-dev.service
```

For each development polling cycle:

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin shell \
  -c /opt/odoo19/custom-addons-ecommerce/odoo19.conf -d YOUR_DEVELOPMENT_DB \
  --no-http --logfile=/tmp/storefront-auth-poll.log <<'PY'
env['ab_storefront_auth_telegram'].sudo()._poll_once()
env['ab_storefront_auth_service'].sudo()._process_queue()
env['ab_storefront_auth_service'].sudo()._process_queue()
env.cr.commit()
print('Development polling cycle completed.')
PY
```

1. Open **Continue with phone** from signup. Enter the phone attached to your Telegram account and open the deep link.
2. Press Start in Telegram, process a polling/cron cycle, then use **Share my phone number**. The contact's user ID must equal the sender and private chat ID, and its normalized phone must match the website request. A typed phone or someone else's forwarded contact is insufficient.
3. Process another cycle, return to the website and check verification. Confirm the displayed Telegram account before creating the account. The website browser must be the one that started linking.
4. Sign in, open **Account security**, confirm the current password and add an email. Process delivery and Odoo's mail queue; open the email link and press Verify email. Both identities now resolve to the same user.
5. Sign out and request Telegram recovery with the verified phone. Process the queue, read the delivered six-digit code and submit it in the initiating browser. Set a new password, then sign in with email or phone.
6. Repeat with email recovery. Verify that expired/used links and codes fail, wrong codes exhaust attempts, rapid resend does not replace the valid code, and changing the password invalidates old sessions and challenges.
7. Unknown identifiers must show the same recovery message. Do not inspect another customer's channel availability through the anonymous UI; channel selection based on verified identities is available only while signed in.

Telegram proves control of the Telegram account and the contact Telegram reports for it. It is not a carrier/SIM verification service. A Telegram account without a usable matching contact cannot complete phone registration. Existing accounts can keep using email and ordinary password login.

## Production rollout and rotation

Back up the Odoo database, deploy code and dependencies, run the targeted upgrade, configure mail and nonsecret settings, provide the two secret files, restart the Odoo service, register the webhook, and execute the live test sequence above. Confirm HTTPS, database routing, cron capacity and Arabic rendering before opening phone registration to customers. Do not use `-u base`.

For token rotation, revoke the token in BotFather, privately provision replacement files in a new `0700` directory, update both service secret-file paths, restart all workers, then rerun webhook registration. Retain the old directory only as required by the deployment's secret-retention policy. Credential files must never enter Git or fixtures.

To disable Telegram safely, set `ab_storefront_auth.telegram_enabled=False`. New links, Telegram challenges and delivery then stop; verified identity records remain for later re-enablement. Email and existing phone/password login remain available. Remove the remote webhook using the administrator shell if retiring the bot. Ensure phone-only customers link email before planned permanent retirement; they otherwise need administrator-assisted recovery.

Odoo autovacuum removes expired challenges after one day, expired rate buckets and queue/update records after seven days. Cleanup never removes customer users or partners. Unique Telegram update IDs make duplicates idempotent during the retention window. A stale update cannot reuse an expired or already-claimed linking token.

## Architecture and extension points

The four new tables are `ab_storefront_auth_identity`, `ab_storefront_auth_challenge`, `ab_storefront_auth_rate` and `ab_storefront_auth_event`. Identities are unique by type/value and user/type. Challenges store keyed token/code digests, expiry, attempt count, optional browser binding and a credential stamp. Delivery payloads are encrypted with a key derived from Odoo's database secret and cleared on success or terminal failure. No plaintext password is stored outside Odoo's hashing implementation.

Only administrators can read these models through ORM/RPC; writes are performed through private service methods after controller validation. Portal/public users receive no model ACL. Signed-in identity changes require the current password. Narrow PostgreSQL advisory transaction locks serialize challenge use, identity claims, rate counters and queue processing; they never update business or inventory tables.

`ab_storefront_auth_channel` defines `_identity_kind`, `_recovery_purpose`, `_available_for`, `_can_recover`, `_prepare_recovery` and `_deliver`. Email uses `mail.mail`; Telegram uses the Bot API adapter. To add SMS or WhatsApp, implement that adapter, extend `_channel_registry` and add the localized UI choice and delivery-specific ownership proof. The adapter can call the existing `_generate_otp` and enqueue its own provider payload. Token, rate, attempt, reset-grant and password-writing logic remain shared; the test suite demonstrates a third OTP channel without modifying the service. Phone ownership for a new channel must be established by that channel's proof, not by entering a number.

Anonymous recovery deliberately shows globally enabled methods rather than disclosing which ones a particular identifier has. Legacy, unique portal email addresses remain eligible for email recovery until the user has a verified email identity; successful recovery verifies that email. A later edit to the partner contact email does not replace the verified recovery identity. Legacy partner phone fields are never treated as verified identities. Internal-user recovery remains available through native Odoo administration.

Telegram delivery can fail if a user blocks the bot, credentials are revoked or the API is unavailable. Failed delivery is retried a bounded number of times without exposing the reason to anonymous callers. External delivery cannot be exactly-once across a process crash after Telegram accepted a send; duplicate copies contain the same challenge and do not permit code reuse. Automated tests exercise real Odoo ORM and HTTP routes with only external Telegram delivery substituted. Final live Bot API delivery requires deployment credentials and an actual user's Telegram interaction.

References: [Telegram Bot API](https://core.telegram.org/bots/api), [OWASP password recovery guidance](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html).

## Automated validation

The release validation ran 39 tests with zero failures, errors or skips in the isolated `ab_auth_task26_test` database. It included real Odoo ORM, HTTP signup/link/recovery routes, Arabic views, access-control denials, queue retries and desktop/mobile browser checks. External Telegram transport alone was substituted; no bot credential was used. Python/XML/JavaScript syntax, Pyflakes and both Arabic PO format checks passed.

Install `websocket-client` in the test environment and provide Chrome for the browser tests. The exact repeat command is:

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin \
  -c /opt/odoo19/custom-addons-ecommerce/odoo19.conf \
  -d ab_auth_task26_test --db-filter='^ab_auth_task26_test$' \
  -u ab_ecommerce_storefront --test-enable --test-tags /ab_ecommerce_storefront \
  --stop-after-init --workers=0 --max-cron-threads=0 \
  --http-port=5069 --gevent-port=5072 \
  --data-dir=/tmp/ab-auth-odoo-data \
  --logfile=/tmp/ab-auth-tests-release.log \
  --screenshots=/tmp/ab-auth-screenshots
```

For a new isolated test database, replace `-u` with `-i` and add `--load-language=ar_001 --without-demo=all`. Keep the explicit database filter: the storefront configuration otherwise filters HTTP requests to `ecom19` even when the command selects another database.

Existing `ecom19` reported missing SEO template tables during the first targeted upgrade. Those unrelated modules were not changed. The isolated fresh install and subsequent authentication upgrades passed.
