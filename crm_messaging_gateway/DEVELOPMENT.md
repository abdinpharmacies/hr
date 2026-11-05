# Telegram Sales Chatter development pilot

Telegram reception has been verified live after explicit activation approval. The independent service migration and remaining staff/pilot checks are tracked in `VALIDATION.md`. No public hostname, tunnel or inbound port is required. WhatsApp remains owned by `ab_whatsapp_api`; Website is deferred.

## Verified development scope

- Checkout: `/opt/odoo19/worktrees/callcenter19`; database: `callcenter`.
- User-managed Odoo: `http://127.0.0.1:4092`; never stop it automatically.
- Requested bot: `@abdin_callcenter_bot`; its numeric identity must come from verified `getMe`.
- Intake: replica serial 102, `فرع العتبة القاهرة`; default store **code 140**, `مخزن افتراضي`.
- Permitted fulfillment store codes: **29** (`فرع العتبة القاهرة`) and **140** (`مخزن افتراضي`), further restricted by each user's and employee's permissions.
- Intake branch code: `telegram-callcenter-intake`; messaging account code: `tg-callcenter`.
- Call Center Odoo users sign in through the separate Chatter employee/PIN popup. Chatter tokens are independent of POS sessions. No employee PIN is reset by setup.
- Dedicated service identity XML ID: `ab_crm_sales_workspace.user_telegram_development`. Its provisioning XML is `security/telegram_development_user.xml`, loaded by the module manifest. It is initially inactive; preparing Telegram Connection activates the service login for token retrieval, while its messaging account stays disabled. The service has no CRM staff/admin role.

## Odoo token setup

After the targeted upgrade and user-managed Odoo reload:

1. Sign in as an administrator and enable developer mode from Settings.
2. Open **Settings → Technical → Parameters → System Parameters**.
3. Create or edit `ab_crm_sales_workspace.telegram_token.<company_id>.tg-callcenter` and paste the BotFather token into **Value**. The exact company-specific key is also displayed in **Sales → Configurations → Telegram Connection**. For the configured callcenter company it is `ab_crm_sales_workspace.telegram_token.1.tg-callcenter`.
4. Save. Do not put the token in chat, source control or a gateway JSON field.
5. Open **Sales → Configurations → Telegram Connection**, keep `tg-callcenter` and `abdin_callcenter_bot`, and click **Prepare connection**. This reads the parameter and prepares a disabled account using the existing company mapping. No Intake selector or token field is shown. Telegram configuration is not exposed in the Chatter screen.

System parameters are administrator-readable database values, not an encrypted secret vault. Preparing the connection activates the dedicated service login for credential retrieval, but does not activate messaging.

The gateway fetches the token at process startup through the authenticated account-bound `get_provider_credentials` operation. It remains in process memory and is not copied to gateway JSON. After token rotation, restart the supervised gateway processes.

## Local protected setup

The prepared `/home/abdin_04/.config/crm-messaging/bootstrap.json` contains the dedicated Odoo API key, expires seven days after preparation, and has mode 0600. Never print or copy it into a ticket, shell argument or source control. The directory has mode 0700. Preparing Telegram Connection activates only the service login, not reception or sending.

The Odoo PostgreSQL role can create databases but cannot create roles. A local administrator must create the dedicated queue role; no sudo password is supplied to the agent:

```bash
sudo -u postgres createuser --no-createdb --no-createrole --no-superuser --pwprompt crm_messaging_callcenter
sudo -u postgres createdb --owner=crm_messaging_callcenter crm_messaging_callcenter
cd /opt/odoo19/worktrees/callcenter19/crm_messaging_gateway
/tmp/crm_gateway_venv/bin/python -m app.local_setup /home/abdin_04/.config/crm-messaging/config.json --username abdin_callcenter_bot --from-odoo --bootstrap /home/abdin_04/.config/crm-messaging/bootstrap.json
```

Run in a terminal. The helper refuses noninteractive input, prompts for the nonsecret Bot ID displayed in Telegram Connection and masks the queue DSN, checks `getMe` and `getWebhookInfo`, and creates the config atomically with mode 0600. Enter the queue DSN using the new role/password, with a URL-encoded password. It does not create an Odoo messaging account, activate reception/sending, remove a webhook or send messages. A username alone cannot authenticate the bot.

The existing `/tmp/crm_gateway_venv` contains the pinned dependencies for supervised development. For a persistent environment create a private venv and install `requirements.lock`; substitute that interpreter in these commands. Use the same protected configuration directory, not another bot credential store.

After setup, verify that the queue role has no SELECT privileges on Odoo business tables, migrate only the separate queue, compare the disabled Odoo account with the verified numeric bot ID and intake mapping. Check the previous worker is inactive before setting its account flag. Do not run this gateway's WhatsApp sender for the existing WhatsApp account.

```bash
export CRM_MESSAGING_CONFIG=/home/abdin_04/.config/crm-messaging/config.json
/tmp/crm_gateway_venv/bin/python -m app.ops migrate
/tmp/crm_gateway_venv/bin/python -m app.telegram_setup tg-callcenter
```

The pilot config uses `odoo_transport=controller_v1`, `reception=polling` and `allow_loopback_http=true`. HTTP is accepted only for literal `127.0.0.1` or `::1`; localhost aliases and all other hosts still require HTTPS. JSON-2 remains the compatibility default for older configs.

## Reload and explicit activation

The user-managed Odoo process needs a reload after the controller/Python changes. At preparation time its versioned route returned HTTP 404; the isolated server's route passed real bearer-authentication tests. Ask the user to reload their PyCharm process. Do not stop it or bind another process to 4091/4092.

Before activation present the verified bot identity, database, intake/default/fulfillment stores, operating employee and named Telegram participant for explicit approval. Enable only the dedicated Odoo service user/account and the corresponding protected gateway account; set `sending_enabled=true` only when the pilot sends are approved.

Verify polling readiness after approval:

```bash
/tmp/crm_gateway_venv/bin/python -m app.telegram_setup tg-callcenter --polling --activate
```

An existing webhook blocks this command unless its exact URL is supplied with `--expected-webhook` after confirming it belongs exclusively to this development bot. That approved operation calls `deleteWebhook` with `drop_pending_updates=false`. Never claim a bot serving another deployment. The receiver itself never removes webhooks and stops on HTTP 409, invalid credentials or loss of its database lock.

## Independent persistent callcenter services

The callcenter installation uses three independent system services. FastAPI starts without contacting Odoo or PostgreSQL and stays running when either dependency is unavailable. The receiver and worker have separate process lifecycles; neither can stop or restart FastAPI.

| Unit | Responsibility | Startup behavior |
| --- | --- | --- |
| `crm-messaging-callcenter.service` | FastAPI on `127.0.0.1:5088` | Local protected configuration only; automatically restarts after any unexpected exit |
| `crm-messaging-callcenter-receiver.service` | One Telegram poller, durable queue ingestion | Retrieves the Odoo-managed token into memory; retries startup when Odoo is unavailable |
| `crm-messaging-callcenter-worker.service` | Queue delivery to Odoo | Starts without provider-token retrieval when sending is disabled; defers incoming events during Odoo outages |

Install or migrate the previously installed combined supervisor from the checkout:

```bash
sudo bash crm_messaging_gateway/scripts/install-callcenter-service.sh --start
```

The installer validates all three units, enables them at boot and starts/restarts them. It recognizes the exact previously installed supervisor definition and stops only that gateway before replacing it; unrelated or modified unit files are not overwritten. It never stops Odoo, discards pending updates or changes sending/reception flags. Without `--start`, it installs and enables units without starting them, and refuses to replace a running combined supervisor. These system services run as `abdin_04` and require no desktop login or user lingering.

Status and health:

```bash
systemctl status crm-messaging-callcenter{,-receiver,-worker}.service --no-pager
systemctl is-enabled crm-messaging-callcenter{,-receiver,-worker}.service
curl --fail http://127.0.0.1:5088/health
curl --fail http://127.0.0.1:5088/ready
journalctl -u crm-messaging-callcenter.service -u crm-messaging-callcenter-receiver.service -u crm-messaging-callcenter-worker.service -n 50 --no-pager
```

`/health` reports API liveness without external calls. `/ready` checks the durable queue and returns 503 when unavailable. Webhooks return 503 rather than acknowledge a message that was not durably queued. Both endpoints are independent of Odoo. Port 5088 remains loopback-only.

Each service can be stopped or restarted independently, for example:

```bash
sudo systemctl restart crm-messaging-callcenter-worker.service
sudo systemctl stop crm-messaging-callcenter{,-receiver,-worker}.service
```

`stop` retains boot enablement. To prevent future startup too, use `sudo systemctl disable --now crm-messaging-callcenter{,-receiver,-worker}.service`. Do not run the foreground launcher alongside these services.

Temporary receiver initialization failures retry after 30 seconds. Competing receivers, an active webhook, revoked Telegram access, or exhausted polling retries stop the receiver with status 78 for operator review; FastAPI and the worker continue independently. Credential lock conflicts have four bounded read-only retries. Incoming Odoo transport failures, rate limits and server outages leave events pending without spending the eight validation-rejection attempts; lease timestamps prevent stale workers from completing a newer claim. Conversation ordering remains enforced. Unknown outgoing outcomes are still never automatically resent.

Odoo remains PyCharm-managed and is neither started nor restarted by these units. A poller that already has its token can keep receiving while Odoo is down. After a reboot, the receiver must obtain its token from Odoo before polling; FastAPI is already available and the worker retains queued deliveries meanwhile. The token remains exclusively Odoo-managed and is not cached on disk. The dedicated API key expires on **2026-11-11 at 12:48:59 UTC** and must be renewed for continued Odoo authentication. Sending remains disabled pending separate pilot approval.

## Foreground development startup, status and stop

The development launcher uses the persistent interpreter at `/home/abdin_04/.config/crm-messaging/venv/bin/python` and the protected `config.json` beside it. After explicit reception approval, enable the Odoo account and its protected gateway account, confirming the previous worker is inactive. Keep `sending_enabled=false`. The launcher verifies these conditions and refuses to activate accounts itself.

From this checkout, run:

```bash
/home/abdin_04/.config/crm-messaging/venv/bin/python crm_messaging_gateway/scripts/dev_services.py start
```

This foreground supervisor starts one FastAPI process on `127.0.0.1:5088`, one receiver and one worker. Ctrl+C stops its three children. In another terminal, use the same command with `status` or `stop` instead of `start`; `check` performs preflight without starting services. Private logs are under `/home/abdin_04/.config/crm-messaging/run/`. If any child exits, the supervisor stops the others without restarting or clearing queue history. Do not run the individual commands below alongside this launcher.

Check `ss -ltnp` first. Port 5088 was free during verification. Run each command in its own supervised terminal from the service directory, with `CRM_MESSAGING_CONFIG` set as above:

```bash
/tmp/crm_gateway_venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 5088 --no-access-log
/tmp/crm_gateway_venv/bin/python -m app.receiver tg-callcenter
/tmp/crm_gateway_venv/bin/python -m app.worker
```

The receiver runs independently of outgoing dispatch. A PostgreSQL advisory lock allows one receiver per bot in this queue database. Updates and the next offset commit together before a subsequent request can acknowledge them. Restarting reuses the durable offset. Polling and webhook intake are mutually exclusive per account. Eight consecutive recoverable receiver failures stop the process; review the sanitized failure before restarting it.

```bash
/tmp/crm_gateway_venv/bin/python -m app.ops status
/tmp/crm_gateway_venv/bin/python -m app.ops review
curl --fail http://127.0.0.1:5088/health
```

Status contains queue counts, bot IDs and offsets, not message text or credentials. Stop with Ctrl+C in each of these three terminals. Check port 5088 is released. Do not use broad `pkill`, restart Odoo, truncate queues or erase offsets. The supplied systemd receiver template is optional and is not installed/enabled by this checkout.

Earlier pending/review incoming events block later events in that conversation. Other conversations can proceed. Outgoing uncertain deliveries also block later sends to the same destination; they are never automatically resent. A review requires operator reconciliation, not resetting the queue to ready. Explicit rate-limit/connect failures retain the existing bounded retry behavior.

## Real pilot evidence still required

Have the named participant open the bot and send the first message, then share their own contact. An authorized employee claims it, identifies the customer, explicitly sends a reply, prepares and accepts an order. Verify returning identity, reload, retained messages/orders/revisions, a receiver restart, and unchanged sales/submission/payment/stock records. Telegram provides provider acceptance/message IDs, not delivered/read receipts. Record sanitized IDs/timestamps and outcomes; never record the bot token, API key or message bodies in logs.

Acceptance only freezes the channel order. It does not submit a sale, invoice, payment or stock operation. Synthetic browser fixtures exist only in isolated validation databases; they are not evidence of a live pilot.

Protocol references: [Telegram getUpdates](https://core.telegram.org/bots/api#getupdates), [getWebhookInfo](https://core.telegram.org/bots/api#getwebhookinfo), [deleteWebhook](https://core.telegram.org/bots/api#deletewebhook).
