"""Plain Bash rendering and idempotent remote tmux execution (no Odoo dependency)."""
import base64
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

ALIAS = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z')
KEY = re.compile(r'[0-9a-f]{32}\Z')


def _(message):
    return message


def validate_server(values):
    if not ALIAS.fullmatch(values.get('ssh_alias') or ''):
        raise ValueError(_('Enter a valid SSH alias using letters, digits, underscores, or hyphens.'))
    if not 1 <= int(values.get('monitor_timeout_seconds', 600)) <= 86400:
        raise ValueError(_('Monitoring timeout must be between 1 and 86400 seconds.'))


def render(commands):
    # Each catalog command is independent, starts in HOME and inherits fail-fast.
    # A command's explicit exit cannot skip later commands or wrapper status recording.
    return '#!/usr/bin/env bash\nset -e -o pipefail\ncd "$HOME"\n' + '\n'.join(
        '(\nset -e -o pipefail\n' + command['bash'] + '\n)\n' for command in commands)


def checksum(script):
    return hashlib.sha256(script.encode()).hexdigest()


def ssh(alias, script):
    if not ALIAS.fullmatch(alias):
        raise ValueError('Invalid SSH alias')
    return subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
                           '-o', 'ForwardX11=no', '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1',
                           '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2',
                           alias, 'bash', '-s'], input=script, text=True, capture_output=True,
                          timeout=35, check=False)


def launch_command(key, script, digest, log_settings=None):
    if not KEY.fullmatch(key) or checksum(script) != digest:
        raise ValueError('Invalid execution key or script checksum')
    encoded = base64.b64encode(script.encode()).decode()
    wrapper = r'''
set -u
umask 077
run_dir="$1"
export HOME="$2"
finish() {
    rc=$?
    trap - EXIT
    state=failed
    if (( rc == 0 )); then state=succeeded; fi
    date -u +%FT%T.%3NZ > "$run_dir/finished_at.tmp"
    mv "$run_dir/finished_at.tmp" "$run_dir/finished_at"
    printf '%s\n%s\n' "$state" "$rc" > "$run_dir/status.tmp"
    mv "$run_dir/status.tmp" "$run_dir/status"
    exit "$rc"
}
trap finish EXIT
exec > "$run_dir/log" 2>&1
exec 9>"$HOME/updates/deployment.lock"
if ! flock -n 9; then echo 'Another deployment is running for this remote account.'; exit 75; fi
printf 'running\n' > "$run_dir/status.tmp"
mv "$run_dir/status.tmp" "$run_dir/status"
__CAPTURE_START__
date -u +%FT%T.%3NZ > "$run_dir/started_at.tmp"
mv "$run_dir/started_at.tmp" "$run_dir/started_at"
# Close the lock descriptor in commands; only the wrapper owns its lifetime.
(umask 022; bash "$run_dir/script.sh") 9>&-
exit $?
'''
    setup = ''
    capture = ''
    if log_settings:
        collector = base64.b64encode(Path(__file__).with_name('log_collector.py').read_bytes()).decode()
        setup = f'printf %s {shlex.quote(collector)} | base64 -d > "$run_dir/log_collector.py"'
        python = shlex.quote(log_settings['odoo_python_path'])
        logfile = shlex.quote(log_settings['odoo_log_path'])
        capture = f'''nohup {python} "$run_dir/log_collector.py" {logfile} "$run_dir" "$$" </dev/null >"$run_dir/odoo_collector_error" 2>&1 9>&- &
collector_pid=$!
for attempt in $(seq 1 100); do
    if test -f "$run_dir/odoo_capture.ready"; then break; fi
    if ! kill -0 "$collector_pid" 2>/dev/null; then break; fi
    sleep .05
done
if ! test -f "$run_dir/odoo_capture.ready"; then
    touch "$run_dir/odoo_capture.skip"
    printf '%s' '{{"state":"error","size":0,"warnings":["Log collector could not start; check the configured Python interpreter and permissions."]}}' > "$run_dir/odoo_capture.json"
fi'''
    wrapper = wrapper.replace('__CAPTURE_START__', capture)
    return f'''set -eu
umask 077
command -v bash >/dev/null
command -v tmux >/dev/null
command -v flock >/dev/null
mkdir -p "$HOME/updates"
chmod 700 "$HOME/updates"
run_dir="$HOME/updates/{key}"
# Never overwrite or relaunch an existing job, even after an interrupted upload.
if test -e "$run_dir"; then exit 0; fi
mkdir "$run_dir" || exit 0
printf %s {shlex.quote(encoded)} | base64 -d > "$run_dir/script.sh"
test "$(sha256sum "$run_dir/script.sh" | cut -d ' ' -f 1)" = {shlex.quote(digest)}
printf '__SCRIPT_CREATED__\\n'
{setup}
printf 'queued\\n' > "$run_dir/status"
if ! tmux new-session -d -s deploy_{key} bash -c {shlex.quote(wrapper)} -- "$run_dir" "$HOME"; then
    printf 'failed\\n1\\n' > "$run_dir/status.tmp"
    mv "$run_dir/status.tmp" "$run_dir/status"
    exit 1
fi
printf '__TMUX_STARTED__\\n'
'''


def monitor_command(key):
    if not KEY.fullmatch(key):
        raise ValueError('Invalid execution key')
    return f'''set -eu
run_dir="$HOME/updates/{key}"
for field in status started_at finished_at; do
    printf '%s:' "$field"
    if test -f "$run_dir/$field"; then head -c 8192 "$run_dir/$field" | base64 -w0; fi
    printf '\\n'
done
printf 'log:'
if test -f "$run_dir/log"; then tail -c 65536 "$run_dir/log" | base64 -w0; fi
printf '\\n'
if tmux has-session -t '=deploy_{key}' 2>/dev/null; then printf 'alive:1\\n'; else printf 'alive:0\\n'; fi
'''


def parse_monitor(output):
    result = {}
    for line in output.splitlines():
        key, sep, value = line.partition(':')
        if not sep or key not in {'status', 'started_at', 'finished_at', 'log', 'alive'} or key in result:
            raise ValueError('Invalid remote status response')
        result[key] = value == '1' if key == 'alive' else base64.b64decode(value, validate=True).decode(errors='replace')
    if set(result) != {'status', 'started_at', 'finished_at', 'log', 'alive'}:
        raise ValueError('Incomplete remote status response')
    status = result['status'].splitlines()
    rc = int(status[1]) if len(status) == 2 and status[1].isdigit() else None
    if status and status[0] in ('succeeded', 'failed') and rc is not None and 0 <= rc <= 255:
        result.update(state='succeeded' if status[0] == 'succeeded' and rc == 0 else 'failed', exit_code=rc)
    else:
        result['state'] = 'running' if result['alive'] else 'unknown'
    return result



LOG_CHUNK_SIZE = 262144


def log_chunk_command(key, offset):
    if not KEY.fullmatch(key) or not isinstance(offset, int) or offset < 0:
        raise ValueError('Invalid log chunk request')
    return f'''set -eu
run_dir="$HOME/updates/{key}"
printf 'meta:'
if test -f "$run_dir/odoo_capture.json"; then head -c 8192 "$run_dir/odoo_capture.json" | base64 -w0; fi
printf '\\nchunk:'
if test -f "$run_dir/odoo_warnings.log"; then dd if="$run_dir/odoo_warnings.log" bs=65536 skip={offset} count=4 iflag=skip_bytes status=none | base64 -w0; fi
printf '\\n'
'''


def parse_log_chunk(output, offset):
    parts = {}
    for line in output.splitlines():
        key, sep, value = line.partition(':')
        if not sep or key not in ('meta', 'chunk') or key in parts:
            raise ValueError('Invalid Odoo log response')
        parts[key] = base64.b64decode(value, validate=True)
    if set(parts) != {'meta', 'chunk'} or len(parts['chunk']) > LOG_CHUNK_SIZE or len(parts['meta']) > 8192:
        raise ValueError('Invalid Odoo log response size')
    if not parts['meta']:
        return {'capture_error': True}
    meta = json.loads(parts['meta'])
    if not isinstance(meta, dict) or meta.get('state') not in ('collecting', 'done', 'warning', 'error'):
        raise ValueError('Invalid Odoo log metadata')
    if not isinstance(meta.get('size'), int) or meta['size'] < 0:
        raise ValueError('Invalid Odoo log size')
    return {'capture_meta': meta, 'capture_chunk': parts['chunk'], 'capture_offset': offset}
