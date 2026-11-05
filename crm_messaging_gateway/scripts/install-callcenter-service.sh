set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    printf '%s\n' 'Run this installer with sudo bash.' >&2
    exit 1
fi

if [[ $# -gt 1 || (${1:-} != '' && ${1:-} != '--start') ]]; then
    printf '%s\n' 'Usage: sudo bash install-callcenter-service.sh [--start]' >&2
    exit 1
fi

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../deploy" && pwd)
units=(crm-messaging-callcenter.service crm-messaging-callcenter-receiver.service crm-messaging-callcenter-worker.service)
private_dir=/home/abdin_04/.config/crm-messaging
legacy_supervisor=false

test -x "$private_dir/venv/bin/python"
test -f "$private_dir/config.json"
for unit in "${units[@]}"; do
    destination=/etc/systemd/system/$unit
    if [[ -e $destination ]] && ! cmp -s "$source_dir/$unit" "$destination"; then
        installed_hash=$(sha256sum "$destination")
        if [[ $unit == crm-messaging-callcenter.service && ${installed_hash%% *} == 9e744cca1fd1ca285bc0160acadeecef1ed99d328cdbc53bfab36c38e8bb7084 ]]; then
            legacy_supervisor=true
        else
            printf '%s\n' "A different definition exists for $unit; review it before replacing it." >&2
            exit 1
        fi
    fi
done

if $legacy_supervisor && systemctl is-active --quiet crm-messaging-callcenter.service && [[ ${1:-} != '--start' ]]; then
    printf '%s\n' 'Use --start to replace the running gateway supervisor with independent services.' >&2
    exit 1
fi

systemd-analyze verify "${units[@]/#/$source_dir/}"
install -d -m 0700 -o abdin_04 -g abdin_04 "$private_dir/run"
if $legacy_supervisor; then
    systemctl stop crm-messaging-callcenter.service
fi
for unit in "${units[@]}"; do
    install -m 0644 "$source_dir/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable "${units[@]}"
if [[ ${1:-} == '--start' ]]; then
    systemctl restart "${units[@]}"
    printf '%s\n' 'Independent API, receiver and worker services are enabled for boot and started.'
else
    printf '%s\n' 'Independent services installed and enabled for boot; they have not been started.'
fi
printf '%s\n' 'FastAPI starts without Odoo. Receiver credential loading and queued delivery wait for Odoo when needed.'
