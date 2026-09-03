#!/usr/bin/env bash
set -euo pipefail

INSTANCE_NAME="${AB_DELIVERY_INSTANCE:-}"
BOT_TOKEN="${AB_DELIVERY_BOT_TOKEN:-}"
CHAT_ID="${AB_DELIVERY_CHAT_ID:-}"
PYTHON_BIN="${AB_DELIVERY_PYTHON:-/usr/bin/python3}"
RUNNER_DEST="${AB_DELIVERY_RUNNER_DEST:-/opt/ab-delivery-longpoll/run_longpoll_service.py}"
UNIT_DEST="${AB_DELIVERY_SYSTEMD_UNIT_DEST:-/etc/systemd/system/ab-delivery-longpoll@.service}"
ENV_DIR="${AB_DELIVERY_ENV_DIR:-/etc/ab-delivery-longpoll}"
STATE_DIR="${AB_DELIVERY_STATE_DIR:-/var/lib/ab-delivery-longpoll}"
SYSTEMCTL="${AB_DELIVERY_SYSTEMCTL:-systemctl}"
JOURNALCTL="${AB_DELIVERY_JOURNALCTL:-journalctl}"
SERVICE_USER="${AB_DELIVERY_SERVICE_USER:-abdin_01}"
SERVICE_GROUP="${AB_DELIVERY_SERVICE_GROUP:-abdin_01}"
START_SERVICE=1
STARTUP_WAIT="${AB_DELIVERY_STARTUP_WAIT:-3}"
USE_SUDO=0
TMP_FILES=()

usage() {
    cat <<'EOF'
Usage:
  bash ab_sales_delivery_tracking/scripts/setup_delivery_longpoll.sh \
    --db '<SERVICE_INSTANCE>' \
    --bot-token '<TELEGRAM_BOT_TOKEN>' \
    --chat-id '<TELEGRAM_GROUP_CHAT_ID>'

This is the single deployment entry point for the standalone Telegram delivery
long-polling receiver. The --db value is only a service instance/state name for
systemd and SQLite paths. It is not an Odoo database connection.

What this script does:
  1. Validates Python, systemd tooling, service user/group, and inputs.
  2. Installs/updates the standalone Telegram-only polling runner.
  3. Installs/updates the systemd service template.
  4. Creates/updates /etc/ab-delivery-longpoll/<escaped-instance>.env.
  5. Creates/prepares the SQLite state directory.
  6. Runs systemctl daemon-reload.
  7. Enables and restarts ab-delivery-longpoll@<escaped-instance>.service unless --no-start is used.
  8. Verifies that the service is active and prints status/log output on failure.

Options:
  --db NAME             Service instance name used for systemd and SQLite paths.
  --bot-token TOKEN     Telegram bot token.
  --chat-id CHAT_ID     Telegram group chat ID guard.
  --no-start            Install/update files and reload systemd, but do not start the service.
  -h, --help            Show this help.

Environment overrides:
  AB_DELIVERY_INSTANCE
  AB_DELIVERY_BOT_TOKEN
  AB_DELIVERY_CHAT_ID
  AB_DELIVERY_PYTHON
  AB_DELIVERY_RUNNER_DEST
  AB_DELIVERY_SYSTEMD_UNIT_DEST
  AB_DELIVERY_ENV_DIR
  AB_DELIVERY_STATE_DIR
  AB_DELIVERY_SYSTEMCTL
  AB_DELIVERY_JOURNALCTL
  AB_DELIVERY_SERVICE_USER
  AB_DELIVERY_SERVICE_GROUP
  AB_DELIVERY_STARTUP_WAIT
EOF
}

die() {
    echo "ERROR: $*" >&2
    exit 1
}

info() {
    echo "==> $*"
}

cleanup() {
    local file
    for file in "${TMP_FILES[@]:-}"; do
        [[ -n "$file" && -e "$file" ]] && rm -f "$file"
    done
    return 0
}
trap cleanup EXIT

shell_quote() {
    printf "%q" "$1"
}

path_parent() {
    dirname "$1"
}

can_write_path() {
    local path parent
    path="$1"
    if [[ -e "$path" ]]; then
        [[ -w "$path" ]]
        return
    fi
    parent="$(path_parent "$path")"
    while [[ ! -e "$parent" && "$parent" != "/" ]]; do
        parent="$(path_parent "$parent")"
    done
    [[ -w "$parent" ]]
}

run_privileged() {
    if [[ "$USE_SUDO" -eq 1 ]]; then
        sudo "$@"
    else
        "$@"
    fi
}

require_no_newline() {
    local name value
    name="$1"
    value="$2"
    [[ "$value" != *$'\n'* && "$value" != *$'\r'* ]] || die "$name cannot contain a newline"
}

require_no_spaces() {
    local name value
    name="$1"
    value="$2"
    [[ "$value" != *[[:space:]]* ]] || die "$name cannot contain whitespace: $value"
}

systemd_env_value() {
    local value
    value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '"%s"' "$value"
}

make_temp_file() {
    local file
    file="$(mktemp)"
    TMP_FILES+=("$file")
    printf '%s' "$file"
}

write_runner_template() {
    local target
    target="$1"
    cat > "$target" <<'PYEOF'
#!/usr/bin/env python3
import argparse
import json
import logging
import os
import signal
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


_logger = logging.getLogger("ab_delivery_longpoll")
_STOP_REQUESTED = False


def _handle_stop(signum, _frame):
    global _STOP_REQUESTED
    _STOP_REQUESTED = True
    _logger.info("Stop requested by signal %s", signum)


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sanitize_name(value):
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


class PollingStore:
    def __init__(self, path):
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self):
        self.conn.close()

    def _init_schema(self):
        self.conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS polling_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS telegram_receptions (
                update_id INTEGER PRIMARY KEY,
                received_at TEXT NOT NULL,
                processed_at TEXT,
                processing_status TEXT NOT NULL,
                reception_status TEXT NOT NULL,
                request_reference TEXT,
                request_id TEXT,
                branch_code TEXT,
                callback_token TEXT,
                callback_data TEXT,
                callback_query_id TEXT,
                chat_id TEXT,
                message_id TEXT,
                telegram_user_id TEXT,
                telegram_username TEXT,
                telegram_user_name TEXT,
                message_text TEXT,
                raw_json TEXT NOT NULL,
                error TEXT
            );
            """
        )
        self.conn.commit()

    def get_offset(self):
        row = self.conn.execute(
            "SELECT value FROM polling_state WHERE key = ?",
            ("telegram_update_offset",),
        ).fetchone()
        if not row:
            return 0
        try:
            return int(row["value"] or 0)
        except (TypeError, ValueError):
            return 0

    def set_offset(self, offset):
        self.conn.execute(
            """
            INSERT INTO polling_state(key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            ("telegram_update_offset", str(int(offset or 0)), _utc_now()),
        )
        self.conn.commit()

    def final_state(self, update_id):
        row = self.conn.execute(
            "SELECT processing_status FROM telegram_receptions WHERE update_id = ?",
            (int(update_id or 0),),
        ).fetchone()
        if row and row["processing_status"] in ("processed", "ignored"):
            return row["processing_status"]
        return ""

    def record_update(self, update, processing_status, reception_status="", parsed=None, error=""):
        parsed = parsed or {}
        callback = update.get("callback_query") or {}
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        telegram_user = callback.get("from") or {}
        now = _utc_now()
        self.conn.execute(
            """
            INSERT INTO telegram_receptions(
                update_id, received_at, processed_at, processing_status,
                reception_status, request_reference, request_id, branch_code,
                callback_token, callback_data, callback_query_id, chat_id,
                message_id, telegram_user_id, telegram_username,
                telegram_user_name, message_text, raw_json, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(update_id) DO UPDATE SET
                processed_at = excluded.processed_at,
                processing_status = excluded.processing_status,
                reception_status = excluded.reception_status,
                request_reference = excluded.request_reference,
                request_id = excluded.request_id,
                branch_code = excluded.branch_code,
                callback_token = excluded.callback_token,
                callback_data = excluded.callback_data,
                callback_query_id = excluded.callback_query_id,
                chat_id = excluded.chat_id,
                message_id = excluded.message_id,
                telegram_user_id = excluded.telegram_user_id,
                telegram_username = excluded.telegram_username,
                telegram_user_name = excluded.telegram_user_name,
                message_text = excluded.message_text,
                raw_json = excluded.raw_json,
                error = excluded.error
            """,
            (
                int(update.get("update_id") or 0),
                now,
                now if processing_status in ("processed", "ignored", "failed") else None,
                processing_status,
                reception_status,
                parsed.get("request_reference", ""),
                parsed.get("request_id", ""),
                parsed.get("branch_code", ""),
                parsed.get("callback_token", ""),
                callback.get("data") or "",
                callback.get("id") or "",
                str(chat.get("id") or ""),
                str(message.get("message_id") or ""),
                str(telegram_user.get("id") or ""),
                telegram_user.get("username") or "",
                telegram_user_display_name(telegram_user),
                message.get("text") or "",
                json.dumps(update, ensure_ascii=False, sort_keys=True),
                error,
            ),
        )
        self.conn.commit()


class DeliveryLongPollingService:
    def __init__(self, args, store):
        self.args = args
        self.store = store

    def run(self):
        _logger.info("Starting standalone Telegram long polling for instance %s", self.args.instance)
        while not _STOP_REQUESTED:
            try:
                self.poll_once()
            except Exception:
                _logger.exception("Polling cycle failed; retrying after %s seconds", self.args.sleep_on_error)
                self._sleep(self.args.sleep_on_error)
        _logger.info("Telegram long polling stopped")

    def poll_once(self):
        offset = self.store.get_offset()
        response = self._telegram_api(
            "getUpdates",
            {
                "offset": offset,
                "timeout": int(self.args.timeout),
                "allowed_updates": ["callback_query"],
            },
            timeout=int(self.args.timeout) + 10,
        )
        updates = response.get("result") or []
        max_update_id = offset - 1
        for update in updates:
            if _STOP_REQUESTED:
                break
            update_id = int(update.get("update_id") or 0)
            max_update_id = max(max_update_id, update_id)
            if self.store.final_state(update_id):
                continue
            self.store.record_update(update, "received")
            try:
                self._process_update(update)
            except Exception as ex:
                self.store.record_update(update, "failed", error=str(ex))
                raise
            self.store.set_offset(update_id + 1)
        if not updates:
            _logger.debug("No Telegram updates at offset %s", offset)
        elif max_update_id >= offset:
            self.store.set_offset(max_update_id + 1)

    def _process_update(self, update):
        callback = update.get("callback_query") or {}
        callback_id = callback.get("id") or ""
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id") or "")
        message_id = str(message.get("message_id") or "")
        original_text = message.get("text") or ""
        data = callback.get("data") or ""
        telegram_user = callback.get("from") or {}
        receiver_name = telegram_user_display_name(telegram_user)
        parsed = parse_callback_data(data)

        if not parsed:
            self._answer_callback_query(callback_id, "تعذر قراءة طلب التوصيل")
            self.store.record_update(update, "ignored", error="Unsupported callback data.")
            return

        if self.args.telegram_chat_id and chat_id != str(self.args.telegram_chat_id):
            self._answer_callback_query(callback_id, "هذه الرسالة ليست مخصصة لمجموعة التوصيل")
            self.store.record_update(
                update,
                "ignored",
                parsed=parsed,
                error="Callback came from an unexpected Telegram chat.",
            )
            return

        received_at = _utc_now()
        self._answer_callback_query(callback_id, "تم تسجيل الاستلام")
        self._edit_message_as_received(chat_id, message_id, original_text, receiver_name, received_at)
        self.store.record_update(
            update,
            "processed",
            reception_status="received",
            parsed=parsed,
        )
        _logger.info(
            "Processed Telegram update %s for delivery reference %s",
            update.get("update_id"),
            parsed.get("request_reference") or "-",
        )

    def _telegram_api(self, method, payload, timeout=60):
        url = "https://api.telegram.org/bot%s/%s" % (self.args.telegram_token, method)
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as ex:
            body = ex.read().decode("utf-8", errors="replace")
            raise ValueError("Telegram API error: %s" % body) from ex
        result = json.loads(body)
        if not result.get("ok"):
            raise ValueError("Telegram API error: %s" % result)
        return result

    def _answer_callback_query(self, callback_id, text):
        if not callback_id:
            return
        try:
            self._telegram_api(
                "answerCallbackQuery",
                {"callback_query_id": callback_id, "text": text},
                timeout=15,
            )
        except Exception:
            _logger.exception("Failed to answer Telegram callback query %s", callback_id)

    def _edit_message_as_received(self, chat_id, message_id, original_text, receiver_name, received_at):
        if not chat_id or not message_id:
            return
        clean_text = (original_text or "").split("\n\nتم الاستلام بواسطة:")[0]
        text = "%s\n\nتم الاستلام بواسطة: %s\nوقت الاستلام: %s" % (
            clean_text,
            receiver_name or "-",
            received_at,
        )
        try:
            self._telegram_api(
                "editMessageText",
                {
                    "chat_id": chat_id,
                    "message_id": int(message_id),
                    "text": text,
                    "reply_markup": {"inline_keyboard": []},
                },
                timeout=15,
            )
        except Exception:
            _logger.exception("Failed to edit Telegram message %s in chat %s", message_id, chat_id)

    @staticmethod
    def _sleep(seconds):
        deadline = time.monotonic() + max(0, seconds)
        while not _STOP_REQUESTED and time.monotonic() < deadline:
            time.sleep(min(1, deadline - time.monotonic()))


def parse_callback_data(data):
    if not data.startswith("dr:"):
        return {}
    parts = data.split(":", 3)
    if len(parts) != 4:
        return {}
    branch_code = (parts[1] or "").strip()
    request_id = (parts[2] or "").strip()
    callback_token = parts[3] or ""
    if not branch_code or not request_id or not callback_token:
        return {}
    return {
        "request_reference": request_id,
        "request_id": request_id,
        "branch_code": branch_code,
        "callback_token": callback_token,
    }


def telegram_user_display_name(telegram_user):
    name = " ".join(
        part
        for part in [
            (telegram_user.get("first_name") or "").strip(),
            (telegram_user.get("last_name") or "").strip(),
        ]
        if part
    )
    username = (telegram_user.get("username") or "").strip()
    if name and username:
        return "%s (@%s)" % (name, username)
    return name or (("@%s" % username) if username else str(telegram_user.get("id") or ""))


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Run the standalone delivery Telegram long-polling service.")
    parser.add_argument("--instance", default=os.environ.get("AB_DELIVERY_INSTANCE", "default"))
    parser.add_argument(
        "--sqlite-path",
        default=os.environ.get("AB_DELIVERY_SQLITE_PATH"),
        help="SQLite file used for Telegram offset and reception audit.",
    )
    parser.add_argument(
        "--telegram-token",
        default=os.environ.get("AB_DELIVERY_BOT_TOKEN", ""),
        help="Telegram bot token.",
    )
    parser.add_argument(
        "--telegram-chat-id",
        default=os.environ.get("AB_DELIVERY_CHAT_ID", ""),
        help="Optional Telegram chat id guard.",
    )
    parser.add_argument("--timeout", type=int, default=50, help="Telegram getUpdates long-poll timeout in seconds.")
    parser.add_argument("--sleep-on-error", type=int, default=10, help="Delay before retry after recoverable errors.")
    parser.add_argument("--log-level", default=os.environ.get("AB_DELIVERY_LOG_LEVEL", "INFO"))
    args = parser.parse_args(argv)
    if not args.sqlite_path:
        args.sqlite_path = "/tmp/ab-delivery-longpoll-%s.sqlite" % _sanitize_name(args.instance)
    if not args.telegram_token:
        raise RuntimeError("Telegram bot token is not configured. Set AB_DELIVERY_BOT_TOKEN or --telegram-token.")
    return args


def main(argv=None):
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    args = parse_args(argv or sys.argv[1:])
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    store = PollingStore(args.sqlite_path)
    try:
        service = DeliveryLongPollingService(args, store)
        service.run()
    finally:
        store.close()


if __name__ == "__main__":
    main()
PYEOF
}

write_unit_template() {
    local target
    target="$1"
    cat > "$target" <<EOF
[Unit]
Description=Abdin Delivery Telegram Long Polling (%I)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$(path_parent "$RUNNER_DEST")
EnvironmentFile=-$ENV_DIR/%i.env
ExecStart=$PYTHON_BIN $RUNNER_DEST --instance %I --sqlite-path $STATE_DIR/%i.sqlite
Restart=always
RestartSec=10
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
EOF
}

write_env_file() {
    local target
    target="$1"
    {
        printf 'AB_DELIVERY_INSTANCE='
        systemd_env_value "$INSTANCE_NAME"
        printf '\nAB_DELIVERY_BOT_TOKEN='
        systemd_env_value "$BOT_TOKEN"
        printf '\nAB_DELIVERY_CHAT_ID='
        systemd_env_value "$CHAT_ID"
        printf '\nAB_DELIVERY_LOG_LEVEL='
        systemd_env_value "${AB_DELIVERY_LOG_LEVEL:-INFO}"
        printf '\n'
    } > "$target"
}

validate_inputs() {
    [[ -n "$INSTANCE_NAME" ]] || die "--db or AB_DELIVERY_INSTANCE is required"
    [[ -n "$BOT_TOKEN" ]] || die "--bot-token or AB_DELIVERY_BOT_TOKEN is required"
    [[ -n "$CHAT_ID" ]] || die "--chat-id or AB_DELIVERY_CHAT_ID is required"

    require_no_newline "Service instance name" "$INSTANCE_NAME"
    require_no_newline "Telegram bot token" "$BOT_TOKEN"
    require_no_newline "Telegram chat ID" "$CHAT_ID"
    require_no_spaces "Python path" "$PYTHON_BIN"
    require_no_spaces "Runner path" "$RUNNER_DEST"
    require_no_spaces "Unit path" "$UNIT_DEST"
    require_no_spaces "Environment directory" "$ENV_DIR"
    require_no_spaces "State directory" "$STATE_DIR"

    command -v systemd-escape >/dev/null 2>&1 || die "systemd-escape is required"
    command -v install >/dev/null 2>&1 || die "install is required"
    command -v mktemp >/dev/null 2>&1 || die "mktemp is required"
    command -v "$SYSTEMCTL" >/dev/null 2>&1 || die "$SYSTEMCTL is required"
    [[ -x "$PYTHON_BIN" ]] || die "Python executable not found or not executable: $PYTHON_BIN"
    id "$SERVICE_USER" >/dev/null 2>&1 || die "Service user does not exist: $SERVICE_USER"
    getent group "$SERVICE_GROUP" >/dev/null 2>&1 || die "Service group does not exist: $SERVICE_GROUP"
}

validate_python_runtime() {
    info "Checking standalone Python runtime dependencies"
    "$PYTHON_BIN" - <<'PYEOF'
import argparse
import json
import logging
import os
import signal
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timezone
PYEOF
}

configure_sudo() {
    local current_user current_group
    current_user="$(id -un)"
    current_group="$(id -gn)"
    USE_SUDO=0
    if [[ "$(id -u)" -ne 0 ]]; then
        if ! can_write_path "$RUNNER_DEST" || ! can_write_path "$UNIT_DEST" || ! can_write_path "$ENV_DIR" || ! can_write_path "$STATE_DIR"; then
            USE_SUDO=1
        elif [[ "$SERVICE_USER" != "$current_user" || "$SERVICE_GROUP" != "$current_group" ]]; then
            USE_SUDO=1
        fi
        if [[ "$USE_SUDO" -eq 1 ]]; then
            command -v sudo >/dev/null 2>&1 || die "sudo is required for installing service files or preparing $STATE_DIR"
        fi
    fi
}

install_runner() {
    local runner_tmp
    runner_tmp="$(make_temp_file)"
    write_runner_template "$runner_tmp"
    "$PYTHON_BIN" -m py_compile "$runner_tmp" || die "Generated long-polling runner failed Python compilation"

    info "Installing standalone long-polling runner: $RUNNER_DEST"
    run_privileged install -D -m 0755 "$runner_tmp" "$RUNNER_DEST"
}

install_unit() {
    local unit_tmp
    unit_tmp="$(make_temp_file)"
    write_unit_template "$unit_tmp"

    info "Installing systemd unit: $UNIT_DEST"
    run_privileged install -D -m 0644 "$unit_tmp" "$UNIT_DEST"
}

install_environment() {
    local env_tmp env_file
    env_tmp="$(make_temp_file)"
    env_file="$ENV_DIR/${ESCAPED_INSTANCE}.env"
    write_env_file "$env_tmp"

    info "Creating environment file: $env_file"
    run_privileged install -d -m 0750 "$ENV_DIR"
    run_privileged install -m 0600 "$env_tmp" "$env_file"
}

prepare_state_directory() {
    info "Preparing SQLite state directory: $STATE_DIR"
    run_privileged install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$STATE_DIR"
}

show_failure_details() {
    local service_name
    service_name="$1"
    echo
    echo "Service failed to become active: $service_name" >&2
    echo "Status:" >&2
    run_privileged "$SYSTEMCTL" status "$service_name" --no-pager -l || true
    if command -v "$JOURNALCTL" >/dev/null 2>&1; then
        echo
        echo "Recent logs:" >&2
        run_privileged "$JOURNALCTL" -u "$service_name" -n 80 --no-pager || true
    fi
}

reload_and_start_service() {
    info "Reloading systemd"
    run_privileged "$SYSTEMCTL" daemon-reload

    if [[ "$START_SERVICE" -ne 1 ]]; then
        info "Skipping service start because --no-start was used"
        return
    fi

    info "Enabling $SERVICE_NAME"
    run_privileged "$SYSTEMCTL" enable "$SERVICE_NAME"

    info "Starting or restarting $SERVICE_NAME"
    run_privileged "$SYSTEMCTL" restart "$SERVICE_NAME"

    sleep "$STARTUP_WAIT"
    if ! run_privileged "$SYSTEMCTL" is-active --quiet "$SERVICE_NAME"; then
        show_failure_details "$SERVICE_NAME"
        exit 1
    fi

    info "Service is active: $SERVICE_NAME"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --db|--instance)
            [[ $# -ge 2 ]] || die "$1 requires a value"
            INSTANCE_NAME="${2:-}"
            shift 2
            ;;
        --bot-token)
            [[ $# -ge 2 ]] || die "$1 requires a value"
            BOT_TOKEN="${2:-}"
            shift 2
            ;;
        --chat-id)
            [[ $# -ge 2 ]] || die "$1 requires a value"
            CHAT_ID="${2:-}"
            shift 2
            ;;
        --no-start)
            START_SERVICE=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Unknown argument: $1"
            ;;
    esac
done

validate_inputs
validate_python_runtime
configure_sudo

ESCAPED_INSTANCE="$(systemd-escape -- "$INSTANCE_NAME")"
ENV_FILE="$ENV_DIR/${ESCAPED_INSTANCE}.env"
SERVICE_NAME="ab-delivery-longpoll@${ESCAPED_INSTANCE}.service"
SQLITE_PATH="$STATE_DIR/${ESCAPED_INSTANCE}.sqlite"

install_runner
install_unit
install_environment
prepare_state_directory
reload_and_start_service

env_file_q="$(shell_quote "$ENV_FILE")"
service_name_q="$(shell_quote "$SERVICE_NAME")"
sqlite_path_q="$(shell_quote "$SQLITE_PATH")"
runner_dest_q="$(shell_quote "$RUNNER_DEST")"

cat <<EOF

Standalone Telegram long-polling service configured.

Instance: $INSTANCE_NAME
Service: $SERVICE_NAME
Runner: $RUNNER_DEST
Environment file: $ENV_FILE
SQLite: $SQLITE_PATH

Status and logs:
  sudo systemctl status $service_name_q
  sudo journalctl -u $service_name_q -f
  sudo systemctl restart $service_name_q

Manual foreground run:
  sudo -u $SERVICE_USER AB_DELIVERY_BOT_TOKEN='<TELEGRAM_BOT_TOKEN>' AB_DELIVERY_CHAT_ID='<TELEGRAM_GROUP_CHAT_ID>' $PYTHON_BIN $runner_dest_q --instance '$INSTANCE_NAME' --sqlite-path $sqlite_path_q

SQLite checks:
  sqlite3 $sqlite_path_q ".tables"
  sqlite3 $sqlite_path_q "SELECT key, value, updated_at FROM polling_state;"
  sqlite3 $sqlite_path_q "SELECT update_id, processing_status, reception_status, request_reference, branch_code, chat_id, message_id, telegram_user_name, error FROM telegram_receptions ORDER BY update_id DESC LIMIT 5;"

EOF
