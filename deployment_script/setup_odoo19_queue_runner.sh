#!/usr/bin/env bash
# Run with sudo after removing queue_job from the main service's --load option
# and removing [queue_job] from /opt/odoo19/odoo19.conf.
# Reload systemd and restart the main service before running this script.
# Starting this service can execute existing pending jobs in deploy19.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run this script with sudo."
    exit 1
fi

SOURCE=/opt/odoo19/odoo19.conf
CONFIG=/opt/odoo19/odoo19-queue-runner.conf
UNIT=/etc/systemd/system/odoo19-queue-runner.service
PYTHON=/opt/odoo19/venv19/bin/python3

test -f "$SOURCE"
test -x "$PYTHON"
test -f /opt/odoo19/server/odoo-bin
id odoo19 >/dev/null

if [[ -e "$CONFIG" || -e "$UNIT" ]]; then
    echo "Queue configuration or service already exists. Inspect it before replacing."
    exit 1
fi

for port in 4091 4092; do
    if [[ -n "$(ss -H -ltn "sport = :$port")" ]]; then
        echo "Port $port is already in use."
        exit 1
    fi
done

# Preserve connection credentials and addon paths without printing secrets.
umask 077
"$PYTHON" <<'PY'
import configparser
import os
import pwd

source = "/opt/odoo19/odoo19.conf"
destination = "/opt/odoo19/odoo19-queue-runner.conf"
config = configparser.RawConfigParser()
with open(source) as stream:
    config.read_file(stream)

settings = {
    "db_name": "deploy19",
    "dbfilter": "^deploy19$",
    "list_db": "False",
    "http_enable": "True",
    "http_interface": "127.0.0.1",
    "http_port": "4091",
    "gevent_port": "4092",
    "proxy_mode": "False",
    "workers": "2",
    "max_cron_threads": "0",
    "limit_time_real": "3900",
    "server_wide_modules": "base,web,queue_job",
    "logfile": "/opt/odoo19/odoo19-queue-runner.log",
    "log_level": "info",
    "pidfile": "/run/odoo19-queue-runner/odoo.pid",
}
for name, value in settings.items():
    config.set("options", name, value)

if config.has_section("queue_job"):
    config.remove_section("queue_job")
config.add_section("queue_job")
for name, value in {
    "channels": "root:2,root.deployment:1",
    "scheme": "http",
    "host": "127.0.0.1",
    "port": "4091",
}.items():
    config.set("queue_job", name, value)

with open(destination, "x") as stream:
    config.write(stream)
account = pwd.getpwnam("odoo19")
os.chown(destination, 0, account.pw_gid)
os.chmod(destination, 0o640)
PY

cat > "$UNIT" <<'UNIT'
[Unit]
Description=Odoo 19 Queue Runner and Job Workers
Requires=postgresql.service
Wants=network-online.target
After=postgresql.service network-online.target

[Service]
Type=simple
User=odoo19
Group=odoo19
WorkingDirectory=/opt/odoo19
RuntimeDirectory=odoo19-queue-runner
RuntimeDirectoryMode=0750
ExecStart=/opt/odoo19/venv19/bin/python3 /opt/odoo19/server/odoo-bin -c /opt/odoo19/odoo19-queue-runner.conf --load=base,web,queue_job
Restart=on-failure
RestartSec=5
TimeoutStopSec=120
SyslogIdentifier=odoo19-queue-runner
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

chmod 644 "$UNIT"
systemctl daemon-reload
systemctl enable --now odoo19-queue-runner.service
systemctl --no-pager --full status odoo19-queue-runner.service

echo "Check startup: sudo tail -n 80 /opt/odoo19/odoo19-queue-runner.log"
echo "If the obsolete custom runner is installed, disable it:"
echo "sudo systemctl disable --now ab-deploy-runner.service"
