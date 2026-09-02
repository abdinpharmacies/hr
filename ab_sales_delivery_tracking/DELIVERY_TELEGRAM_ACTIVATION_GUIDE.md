# Delivery Telegram Activation Guide

This guide explains the current delivery Telegram workflow, branch activation, supervisor long-polling setup, testing, verification, and troubleshooting.

Use placeholders in every command. Never paste real Telegram tokens into documentation.

## What The System Does

The system connects branch delivery sales to a shared Telegram delivery group. A branch sends a delivery request message to Telegram. A supervisor presses `تم الاستلام`. The standalone long-polling service receives that Telegram button callback and updates the matching Odoo `ab_delivery_request` record through the Odoo ORM.

```text
Telegram Bot
    |
    v
Delivery Telegram Group
    |
    v
Odoo Branch
    |
    v
ab_sales_delivery_tracking
    |
    v
ab_delivery_request
    |
    v
Telegram message with "تم الاستلام"
    |
    v
Supervisor presses "تم الاستلام"
    |
    v
delivery_longpoll/run_longpoll_service.py
    |
    v
SQLite polling_state and telegram_updates
    |
    v
Odoo ORM
    |
    v
ab_delivery_request updated to received
```

## Current Architecture

Branch-side sending is handled by the Odoo module:

```text
ab_sales_delivery_tracking
```

Supervisor-side receiving is handled by a standalone Python service installed by the setup script:

```text
delivery_longpoll/run_longpoll_service.py
```

The standalone service is managed by a systemd template installed by the setup script:

```text
/etc/systemd/system/ab-delivery-longpoll@.service
```

The setup helper for the standalone service is:

```text
ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh
```

The setup helper embeds and installs the runner and systemd unit. It does not require manually copied `delivery_longpoll/` or `deploy/` files.

## Branch Setup

### Branch Requirements

```text
Odoo config: /opt/odoo19/odoo19.conf
Python: /opt/odoo19/venv19/bin/python
Odoo bin: /opt/odoo19/server/odoo-bin
Module: ab_sales_delivery_tracking
Required dependency: queue_job
Branch database: <BRANCH_DB>
Telegram bot token: <TELEGRAM_BOT_TOKEN>
Telegram group chat ID: <TELEGRAM_GROUP_CHAT_ID>
```

The Telegram bot must be added to the delivery group before branch sending can work.

### Install Or Upgrade The Branch Module

Run from `/opt/odoo19/custom-addons`:

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin \
  -c /opt/odoo19/odoo19.conf \
  -d '<BRANCH_DB>' \
  -i ab_sales_delivery_tracking \
  -u ab_sales_delivery_tracking \
  --stop-after-init \
  --no-http
```

### Configure Telegram Sending In Odoo

Store the bot token and group chat ID in the branch Odoo database:

```bash
AB_DELIVERY_BOT_TOKEN='<TELEGRAM_BOT_TOKEN>' \
AB_DELIVERY_CHAT_ID='<TELEGRAM_GROUP_CHAT_ID>' \
printf "import os\nParam = env['ir.config_parameter'].sudo()\nParam.set_param('ab_sales_delivery_tracking.telegram_bot_token', os.environ['AB_DELIVERY_BOT_TOKEN'])\nParam.set_param('ab_sales_delivery_tracking.telegram_chat_id', os.environ['AB_DELIVERY_CHAT_ID'])\nenv.cr.commit()\nprint('telegram_configured', env.cr.dbname)\n" \
  | /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin shell \
      -c /opt/odoo19/odoo19.conf \
      -d '<BRANCH_DB>' \
      --no-http
```

### Branch Sending Mechanism

The current branch code sends after a delivery sale is pushed:

```text
ab_sales_header.action_push_to_eplus()
    |
    v
delivery sale has eplus_serial
    |
    v
ab_delivery_request.create_from_sale_header()
    |
    v
ab_delivery_request.queue_send_to_telegram()
    |
    v
queue_job + immediate safe send + branch retry cron
    |
    v
Telegram Bot API sendMessage
```

The branch retry cron is named:

```text
Delivery Requests: Send Pending Telegram Messages
```

That cron is only for branch-side Telegram sending retries. It is not used for Telegram long polling.

Enable the cron if needed:

```bash
printf "cron = env['ir.cron'].sudo().search([('name','=','Delivery Requests: Send Pending Telegram Messages')], limit=1)\ncron.write({'active': True}) if cron else None\nenv.cr.commit()\nprint(cron.read(['id','active','nextcall','lastcall']) if cron else [])\n" \
  | /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin shell \
      -c /opt/odoo19/odoo19.conf \
      -d '<BRANCH_DB>' \
      --no-http
```

## Supervisor Long-Polling Setup

The setup script is only for the standalone long-polling service:

```text
ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh
```

It does this:

- Gets the Odoo database name.
- Gets the Telegram bot token.
- Gets the Telegram group chat ID.
- Validates the Odoo Python runtime, Odoo server path, Odoo config, target database, `ab_delivery_request` model, and systemd tooling.
- Installs or upgrades `ab_sales_delivery_tracking` in the selected Odoo database with a targeted module operation.
- Installs or updates `/opt/odoo19/custom-addons/delivery_longpoll/run_longpoll_service.py`.
- Installs or updates `/etc/systemd/system/ab-delivery-longpoll@.service`.
- Creates `/etc/ab-delivery-longpoll/<ESCAPED_ODOO_DB>.env`.
- Creates and prepares `/var/lib/ab-delivery-longpoll`.
- Runs `systemctl daemon-reload`.
- Enables and restarts `ab-delivery-longpoll@<ESCAPED_ODOO_DB>.service` unless `--no-start` is used.
- Verifies the service is active and prints status/log details if startup fails.
- Prints status, log, restart, manual foreground run, and SQLite verification commands.

It does not do this:

- It does not write Odoo `ir.config_parameter` values.
- It does not create delivery requests.
- It does not send Telegram messages from branches.
- It does not handle branch business workflow.

### Exact Long-Polling Setup Command

Run from `/opt/odoo19/custom-addons` on the supervisor server:

```bash
bash ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh \
  --db '<ODOO_DB>' \
  --bot-token '<TELEGRAM_BOT_TOKEN>' \
  --chat-id '<TELEGRAM_GROUP_CHAT_ID>'
```

The same values can be supplied through environment variables:

```bash
AB_DELIVERY_DB='<ODOO_DB>' \
AB_DELIVERY_BOT_TOKEN='<TELEGRAM_BOT_TOKEN>' \
AB_DELIVERY_CHAT_ID='<TELEGRAM_GROUP_CHAT_ID>' \
bash ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh
```

For local validation only, `AB_DELIVERY_RUNNER_DEST`, `AB_DELIVERY_SYSTEMD_UNIT_DEST`, `AB_DELIVERY_ENV_DIR`, `AB_DELIVERY_STATE_DIR`, `AB_DELIVERY_SYSTEMCTL`, `AB_DELIVERY_SKIP_MODULE_UPGRADE=1`, and `AB_DELIVERY_SKIP_ODOO_DB_CHECK=1` can point to temporary paths/tools. Production deployment should use the defaults and keep the module upgrade and database check enabled.

### systemd Details

The setup script installs a unit with these default paths:

```text
WorkingDirectory=/opt/odoo19/custom-addons
EnvironmentFile=-/etc/ab-delivery-longpoll/%i.env
ExecStart=/opt/odoo19/venv19/bin/python /opt/odoo19/custom-addons/delivery_longpoll/run_longpoll_service.py --odoo-server-path /opt/odoo19/server --config /opt/odoo19/odoo19.conf --database %I --sqlite-path /var/lib/ab-delivery-longpoll/%i.sqlite
Restart=always
RestartSec=10
```

Use `systemd-escape` for database names:

```bash
DB_INSTANCE="$(systemd-escape -- '<ODOO_DB>')"
```

Resulting paths:

```text
Service: ab-delivery-longpoll@<ESCAPED_ODOO_DB>.service
Environment file: /etc/ab-delivery-longpoll/<ESCAPED_ODOO_DB>.env
SQLite: /var/lib/ab-delivery-longpoll/<ESCAPED_ODOO_DB>.sqlite
```

### Status And Logs

```bash
DB_INSTANCE="$(systemd-escape -- '<ODOO_DB>')"

sudo systemctl status "ab-delivery-longpoll@${DB_INSTANCE}.service"
sudo journalctl -u "ab-delivery-longpoll@${DB_INSTANCE}.service" -f
sudo systemctl restart "ab-delivery-longpoll@${DB_INSTANCE}.service"
```

## SQLite

SQLite is used by the long-polling service for Telegram offset and callback audit data. It is not the Odoo business database.

The systemd SQLite path is:

```text
/var/lib/ab-delivery-longpoll/<ESCAPED_ODOO_DB>.sqlite
```

The runner creates:

```text
polling_state
telegram_updates
```

Verify SQLite:

```bash
DB_INSTANCE="$(systemd-escape -- '<ODOO_DB>')"
SQLITE_PATH="/var/lib/ab-delivery-longpoll/${DB_INSTANCE}.sqlite"

sqlite3 "$SQLITE_PATH" ".tables"
sqlite3 "$SQLITE_PATH" "SELECT key, value, updated_at FROM polling_state;"
sqlite3 "$SQLITE_PATH" "SELECT update_id, state, callback_data, odoo_record_id, error FROM telegram_updates ORDER BY update_id DESC LIMIT 5;"
```

If `run_longpoll_service.py` is run manually without `--sqlite-path`, it defaults to:

```text
/tmp/ab-delivery-longpoll-<SANITIZED_ODOO_DB>.sqlite
```

## Testing And Verification

### Configuration Tests

```bash
bash -n ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh
bash ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh --help
```

### Branch Verification

Check Telegram config and recent delivery requests:

```bash
printf "Param = env['ir.config_parameter'].sudo()\nprint(bool(Param.get_param('ab_sales_delivery_tracking.telegram_bot_token')))\nprint(Param.get_param('ab_sales_delivery_tracking.telegram_chat_id'))\nprint(env['ab_delivery_request'].sudo().search_read([], ['id','branch_code','bill_number','state','telegram_message_id','last_error'], order='id desc', limit=5))\n" \
  | /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin shell \
      -c /opt/odoo19/odoo19.conf \
      -d '<BRANCH_DB>' \
      --no-http
```

### Complete Workflow Test

1. Confirm the Telegram bot is in the delivery group.
2. Install/upgrade `ab_sales_delivery_tracking` on the branch database.
3. Configure `ab_sales_delivery_tracking.telegram_bot_token`.
4. Configure `ab_sales_delivery_tracking.telegram_chat_id`.
5. Start the supervisor long-polling service with `setup_delivery_longpoll.sh`.
6. Create a test delivery sale in branch Odoo.
7. Push the delivery sale so it gets an `eplus_serial`.
8. Confirm `ab_delivery_request` is created.
9. Confirm the Telegram message appears in the group.
10. Confirm the message has the `تم الاستلام` button.
11. Press `تم الاستلام`.
12. Confirm the service log shows a processed update.
13. Confirm SQLite records the callback in `telegram_updates`.
14. Confirm the Odoo delivery request changes to `received`.

Verify received requests:

```bash
printf "print(env['ab_delivery_request'].sudo().search_read([('state','=','received')], ['id','branch_code','bill_number','state','received_date','received_by_telegram_name','telegram_update_id'], order='id desc', limit=5))\n" \
  | /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin shell \
      -c /opt/odoo19/odoo19.conf \
      -d '<ODOO_DB>' \
      --no-http
```

## Troubleshooting

### Branch Does Not Send

Check:

- `ab_sales_delivery_tracking` is installed on the branch database.
- `queue_job` is installed.
- `ab_sales_delivery_tracking.telegram_bot_token` is configured.
- `ab_sales_delivery_tracking.telegram_chat_id` is configured.
- The Telegram bot is in the group.
- The group chat ID is correct.
- The delivery sale was pushed and has `eplus_serial`.
- An `ab_delivery_request` exists.
- The request `last_error` field does not contain a Telegram API error.
- The branch retry cron is active if queued/failed messages need retries.

### Telegram Message Does Not Appear

Check:

- Bot token is valid.
- Bot can send messages to the group.
- Chat ID matches the target group.
- The request is not already `received`.
- The request has valid `branch_code`; it must not contain `:`.
- Callback data length is not longer than Telegram allows.
- Odoo logs for send failures.

### تم الاستلام Does Not Update Odoo

Check:

- `ab-delivery-longpoll@<ESCAPED_ODOO_DB>.service` is running.
- `/etc/ab-delivery-longpoll/<ESCAPED_ODOO_DB>.env` exists.
- The env file has `AB_DELIVERY_BOT_TOKEN` and `AB_DELIVERY_CHAT_ID`.
- Service logs do not show Telegram API or Odoo ORM errors.
- SQLite has the callback row in `telegram_updates`.
- `callback_data` starts with `dr:`.
- The matching Odoo request exists and has the expected branch code, request ID, and callback token.

### Long-Polling Service Is Not Running

Check:

```bash
DB_INSTANCE="$(systemd-escape -- '<ODOO_DB>')"

sudo systemctl status "ab-delivery-longpoll@${DB_INSTANCE}.service"
sudo journalctl -u "ab-delivery-longpoll@${DB_INSTANCE}.service" -n 100
```

Common causes:

- The unit was not installed to `/etc/systemd/system/ab-delivery-longpoll@.service`.
- `systemctl daemon-reload` was not run.
- The database instance name was not escaped with `systemd-escape`.
- The target database is not reachable or does not have `ab_sales_delivery_tracking` installed.
- The environment file is missing or named incorrectly.
- Bot token or chat ID is missing.
- `/opt/odoo19/server` is missing.
- `/opt/odoo19/odoo19.conf` is missing.
- `/opt/odoo19/venv19/bin/python` is missing.
- The service user cannot reach PostgreSQL.
- Network access to Telegram Bot API is blocked.

### SQLite Problems

Check:

```bash
DB_INSTANCE="$(systemd-escape -- '<ODOO_DB>')"

sudo ls -ld /var/lib/ab-delivery-longpoll
sudo ls -l "/var/lib/ab-delivery-longpoll/${DB_INSTANCE}.sqlite"*
sqlite3 "/var/lib/ab-delivery-longpoll/${DB_INSTANCE}.sqlite" ".tables"
```

The setup script creates `/var/lib/ab-delivery-longpoll` and grants the service user write access.

## Branch Activation Checklist

```text
[ ] Telegram bot exists.
[ ] Telegram delivery group exists.
[ ] Bot is added to the delivery group.
[ ] Group chat ID is verified.
[ ] Branch Odoo database is identified.
[ ] queue_job is available.
[ ] ab_sales_delivery_tracking is installed/upgraded.
[ ] Telegram bot token is configured in Odoo system parameters.
[ ] Telegram group chat ID is configured in Odoo system parameters.
[ ] Odoo workers/cron or queue processing for branch sending is available.
[ ] Test delivery sale is pushed.
[ ] ab_delivery_request is created.
[ ] Telegram message appears in the group.
[ ] Telegram message includes the تم الاستلام button.
```

## Supervisor Activation Checklist

```text
[ ] Supervisor server has the custom addons checkout.
[ ] Odoo config /opt/odoo19/odoo19.conf exists.
[ ] Odoo server path /opt/odoo19/server exists.
[ ] Python /opt/odoo19/venv19/bin/python exists.
[ ] Odoo database containing ab_delivery_request is identified.
[ ] setup_delivery_longpoll.sh is run with DB, bot token, and chat ID.
[ ] ab_sales_delivery_tracking is installed/upgraded by the setup script.
[ ] Runner is installed under /opt/odoo19/custom-addons/delivery_longpoll.
[ ] Unit is installed under /etc/systemd/system.
[ ] Environment file exists under /etc/ab-delivery-longpoll.
[ ] Service ab-delivery-longpoll@<ESCAPED_ODOO_DB>.service is enabled.
[ ] Service is running.
[ ] SQLite file exists under /var/lib/ab-delivery-longpoll.
[ ] Service logs are clean.
[ ] Test callback updates Odoo request to received.
```

## Important Rules

- Branches send delivery requests to Telegram.
- Supervisors receive requests in the Telegram group.
- Pressing `تم الاستلام` is processed by the standalone long-polling service.
- Long polling is not implemented through an Odoo scheduled action.
- `setup_delivery_longpoll.sh` is only for installing and starting the standalone long-polling service.
- SQLite stores polling state and audit data only.
- Odoo PostgreSQL remains the business database.
- Do not put real Telegram tokens or secrets in this guide.

## Current Validation Status

Passed in this repository:

- `bash -n ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh`
- `bash ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh --help`
- Safe single-entry setup-helper run from a clean temporary install root, with temporary runner/unit/env/state paths and mocked systemctl.
- Safe setup-helper update run with `--no-start`.
- Generated runner compiled successfully with `/opt/odoo19/venv19/bin/python`.
- Generated unit verified successfully with `systemd-analyze verify`.
- Failure-path test confirmed the setup helper exits non-zero and prints service status/log diagnostics when startup verification fails.
- Disposable Odoo database module install for `ab_sales_delivery_tracking`.
- Local full-cycle test with simulated Telegram API:
  - Created a branch store.
  - Created a delivery sales header.
  - Created `ab_delivery_request` from the bill.
  - Verified the Telegram `sendMessage` payload and `تم الاستلام` button callback data.
  - Processed a simulated Telegram `getUpdates` callback through the standalone long-polling runner.
  - Verified SQLite `polling_state` offset and `telegram_updates` audit row.
  - Verified the Odoo delivery request was updated to `received` through the real Odoo ORM.

Not performed in this pass:

- Actual `setup_delivery_longpoll.sh` service installation into `/etc/systemd/system/`.
- Actual `systemctl enable --now` start.
- Actual systemd restart behavior.
- Live Telegram send to a real group.
- Live Telegram callback processing.

Reason: this environment cannot connect to the systemd bus, and no safe test Telegram bot/group credentials were supplied.
