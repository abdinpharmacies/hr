#!/usr/bin/env bash

set -Eeuo pipefail

BACKUP_FILE="${BACKUP_FILE:-/home/abdin_02/Mohamed_tips/work/website_ecommerce/releases/1/ecom19_2026-10-20_10-56-21.zip}"
CONFIG_FILE="${CONFIG_FILE:-/opt/odoo19/custom-addons-ecommerce/odoo19.conf}"
DATABASE_NAME="${DATABASE_NAME:-ecom19}"
PYTHON_BIN="${PYTHON_BIN:-/opt/odoo19/venv19/bin/python}"
ODOO_BIN="${ODOO_BIN:-/opt/odoo19/server/odoo-bin}"
MODE="${1:-restore}"

if [[ ! "$DATABASE_NAME" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]+$ ]]; then
    echo "Invalid database name: $DATABASE_NAME" >&2
    exit 2
fi

for path in "$BACKUP_FILE" "$CONFIG_FILE" "$PYTHON_BIN" "$ODOO_BIN"; do
    if [[ ! -r "$path" ]]; then
        echo "Required file is not readable: $path" >&2
        exit 3
    fi
done

if ! unzip -tq "$BACKUP_FILE" >/dev/null; then
    echo "Backup archive validation failed: $BACKUP_FILE" >&2
    exit 4
fi

manifest_version="$(unzip -p "$BACKUP_FILE" manifest.json | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("major_version", ""))')"
if [[ "$manifest_version" != "19.0" ]]; then
    echo "Expected an Odoo 19.0 backup, found: ${manifest_version:-unknown}" >&2
    exit 5
fi

command=(
    "$PYTHON_BIN"
    "$ODOO_BIN"
    db
    -c "$CONFIG_FILE"
    load
    "$DATABASE_NAME"
    "$BACKUP_FILE"
)

echo "Backup: $BACKUP_FILE"
echo "Config: $CONFIG_FILE"
echo "Database: $DATABASE_NAME"
echo "Odoo backup version: $manifest_version"

if [[ "$MODE" == "check" ]]; then
    printf 'Command:'
    printf ' %q' "${command[@]}"
    printf '\n'
    exit 0
fi

if [[ "$MODE" != "restore" ]]; then
    echo "Usage: $0 [check|restore]" >&2
    exit 6
fi

echo "Starting database restore. Existing databases are never overwritten by this script."
"${command[@]}"
echo "Database restore completed: $DATABASE_NAME"
