# Delivery Telegram Activation Guide

This guide describes the current delivery Telegram workflow after decoupling
the supervisor long-polling service from Odoo.

## Current Architecture

```text
Odoo
  -> sends the Telegram delivery message
Telegram
  -> supervisor clicks "تم الاستلام"
Telegram
  -> standalone long-polling service receives callback
Long-polling service
  -> updates the Telegram message
Long-polling service
  -> saves reception/audit data in SQLite
```

There is no callback path from the long-polling service back into Odoo.

```text
Telegram -> Long Polling -> Odoo
```

is intentionally not part of the design.

## Odoo Responsibility

Odoo remains responsible only for creating and sending the original delivery
message. The message callback data keeps this format:

```text
dr:<branch_code>:<delivery_reference>:<callback_token>
```

The standalone receiver treats those values as Telegram audit references only.
It does not use them to read or update Odoo records.

## Standalone Receiver Responsibility

The generated runner:

- Polls Telegram with `getUpdates`.
- Processes only `callback_query` updates.
- Parses delivery callback data.
- Guards the configured Telegram chat ID.
- Answers the Telegram callback.
- Edits the Telegram message to show who received it and when.
- Removes the inline buttons from the Telegram message.
- Stores the reception event in SQLite.

The runner does not import Odoo, does not load an Odoo config, does not open an
Odoo registry, does not query PostgreSQL, and does not call `request.write(...)`.

## Setup Command

Run from `/opt/odoo19/custom-addons`:

```bash
bash ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh \
  --db '<SERVICE_INSTANCE>' \
  --bot-token '<TELEGRAM_BOT_TOKEN>' \
  --chat-id '<TELEGRAM_GROUP_CHAT_ID>'
```

`--db` is kept for operational compatibility, but it is only a service instance
name used in the systemd service name and SQLite file path. It is not an Odoo
database.

To install/update files without starting the service:

```bash
bash ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh \
  --db '<SERVICE_INSTANCE>' \
  --bot-token '<TELEGRAM_BOT_TOKEN>' \
  --chat-id '<TELEGRAM_GROUP_CHAT_ID>' \
  --no-start
```

## Installed Files

Default paths:

```text
Runner: /opt/ab-delivery-longpoll/run_longpoll_service.py
Unit: /etc/systemd/system/ab-delivery-longpoll@.service
Environment: /etc/ab-delivery-longpoll/<ESCAPED_INSTANCE>.env
SQLite: /var/lib/ab-delivery-longpoll/<ESCAPED_INSTANCE>.sqlite
```

The setup script creates or updates these files automatically.

## systemd Commands

```bash
INSTANCE="$(systemd-escape -- '<SERVICE_INSTANCE>')"

sudo systemctl status "ab-delivery-longpoll@${INSTANCE}.service"
sudo journalctl -u "ab-delivery-longpoll@${INSTANCE}.service" -f
sudo systemctl restart "ab-delivery-longpoll@${INSTANCE}.service"
```

## SQLite Tables

`polling_state` stores Telegram polling offsets:

```text
key TEXT PRIMARY KEY
value TEXT NOT NULL
updated_at TEXT NOT NULL
```

`telegram_receptions` stores reception/audit information:

```text
update_id INTEGER PRIMARY KEY
received_at TEXT NOT NULL
processed_at TEXT
processing_status TEXT NOT NULL
reception_status TEXT NOT NULL
request_reference TEXT
request_id TEXT
branch_code TEXT
callback_token TEXT
callback_data TEXT
callback_query_id TEXT
chat_id TEXT
message_id TEXT
telegram_user_id TEXT
telegram_username TEXT
telegram_user_name TEXT
message_text TEXT
raw_json TEXT NOT NULL
error TEXT
```

Useful checks:

```bash
INSTANCE="$(systemd-escape -- '<SERVICE_INSTANCE>')"
SQLITE_PATH="/var/lib/ab-delivery-longpoll/${INSTANCE}.sqlite"

sqlite3 "$SQLITE_PATH" ".tables"
sqlite3 "$SQLITE_PATH" "SELECT key, value, updated_at FROM polling_state;"
sqlite3 "$SQLITE_PATH" "SELECT update_id, processing_status, reception_status, request_reference, branch_code, chat_id, message_id, telegram_user_name, error FROM telegram_receptions ORDER BY update_id DESC LIMIT 5;"
```

## Troubleshooting

If the service does not start, check:

- The bot token is valid.
- The Telegram bot is in the delivery group.
- The chat ID matches the delivery group.
- The service user can write to `/var/lib/ab-delivery-longpoll`.
- Network access to `api.telegram.org` is available.
- `journalctl` does not show Telegram API errors.

The long-polling service should continue running even when Odoo is stopped,
because it no longer depends on Odoo or PostgreSQL.
