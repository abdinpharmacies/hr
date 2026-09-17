"""Streaming SSH workers. No Odoo objects, cursors or callbacks enter a thread."""
import base64
import os
import queue
import selectors
import subprocess
import time

from . import engine


class TransportError(Exception):
    pass


def stream(alias, shell, deadline, stop):
    """Read a bounded line protocol; terminate only our local SSH on timeout."""
    if not engine.ALIAS.fullmatch(alias):
        raise ValueError('Invalid SSH alias')
    # A temporary stdin file avoids a full pipe blocking large script uploads.
    import tempfile
    with tempfile.TemporaryFile() as stdin:
        stdin.write(shell.encode())
        stdin.seek(0)
        process = subprocess.Popen([
            'ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
            '-o', 'ForwardX11=no', '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1',
            '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2',
            alias, 'bash', '-s'], stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                pending = b''
                while True:
                    if stop.is_set() or time.monotonic() >= deadline:
                        raise TimeoutError('SSH observation deadline reached')
                    if not selector.select(.25):
                        continue
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        if pending:
                            yield pending.decode(errors='replace')
                        break
                    pending += chunk
                    if len(pending) > 1048576:
                        raise ValueError('Oversized SSH protocol frame')
                    while b'\n' in pending:
                        line, pending = pending.split(b'\n', 1)
                        yield line.decode(errors='replace')
            rc = process.wait(timeout=2)
            if rc == 255:
                raise TransportError('SSH connection failed')
            if rc:
                raise ValueError('Remote setup or monitoring failed')
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.stdout.close()


def monitor_shell(payload):
    key = payload['key']
    if not engine.KEY.fullmatch(key):
        raise ValueError('Invalid execution key')
    offset = int(payload['command_offset'])
    capture_offset = int(payload['odoo_offset'])
    # Status is framed independently of output. Output chunks are acknowledged
    # locally and committed before the next one is accepted by the main thread.
    return f'''set -eu
run_dir="$HOME/updates/{key}"
offset={offset}
capture_offset={capture_offset}
collect={'1' if payload['capture'] else '0'}
while :; do
    printf '__FRAME__\\n'
{engine.monitor_command(key)}
    printf 'command_offset:%s\\n' "$offset"
    chunk=
    if test -f "$run_dir/log"; then
        chunk=$(dd if="$run_dir/log" bs=65536 skip="$offset" count=4 iflag=skip_bytes status=none | base64 -w0)
    fi
    printf 'command_chunk:%s\\n' "$chunk"
    count=$(printf '%s' "$chunk" | base64 -d | wc -c)
    offset=$((offset + count))
    size=0
    if test -f "$run_dir/log"; then size=$(stat -c %s "$run_dir/log"); fi
    printf 'command_size:%s\\n' "$size"
    printf 'capture_offset:%s\\n' "$capture_offset"
    printf 'capture_meta:'
    if test "$collect" = 1 && test -f "$run_dir/odoo_capture.json"; then head -c 8192 "$run_dir/odoo_capture.json" | base64 -w0; fi
    printf '\\n'
    chunk=
    if test "$collect" = 1 && test -f "$run_dir/odoo_warnings.log"; then
        chunk=$(dd if="$run_dir/odoo_warnings.log" bs=65536 skip="$capture_offset" count=4 iflag=skip_bytes status=none | base64 -w0)
    fi
    printf 'capture_chunk:%s\\n' "$chunk"
    count=$(printf '%s' "$chunk" | base64 -d | wc -c)
    capture_offset=$((capture_offset + count))
    printf '__END__\\n'
    sleep 2
done
'''


def decode_frame(lines):
    items = dict(line.split(':', 1) for line in lines)
    report = engine.parse_monitor('\n'.join(f'{k}:{items[k]}' for k in ('status', 'started_at', 'finished_at', 'log', 'alive')))
    report.update(command_offset=int(items['command_offset']), command_size=int(items['command_size']),
                  command_chunk=base64.b64decode(items['command_chunk'], validate=True))
    if items['capture_meta']:
        report.update(engine.parse_log_chunk(
            'meta:' + items['capture_meta'] + '\nchunk:' + items['capture_chunk'] + '\n', int(items['capture_offset'])))
    if len(report['command_chunk']) > engine.LOG_CHUNK_SIZE:
        raise ValueError('Oversized log chunk')
    return report


def host(payload, events, stop, batch_deadline):
    """One thread connects, optionally launches once, then waits through SSH."""
    deadline = min(batch_deadline, time.monotonic() + payload['timeout'])
    intent = payload['intent']
    launched = intent
    diagnostics = ''

    def emit(kind, **values):
        ack = queue.Queue(maxsize=1)
        event = dict(values, id=payload['id'], kind=kind, ack=ack)
        while not stop.is_set():
            try:
                events.put(event, timeout=.25)
                break
            except queue.Full:
                continue
        while not stop.is_set():
            try:
                return ack.get(timeout=.25)
            except queue.Empty:
                continue
        return False

    try:
        if not intent:
            # This connection cannot launch anything, so a failure is retryable.
            output = list(stream(payload['alias'], "printf '__CONNECTED__\\n'", min(deadline, time.monotonic() + 35), stop))
            if '__CONNECTED__' not in output:
                raise TransportError('SSH preflight failed')
            if not emit('stage', stage='ssh_connected'):
                return
            # Commit launch intent BEFORE any command with remote side effects.
            if not emit('intent'):
                return
            intent = True
            shell = engine.launch_command(payload['key'], payload['script'], payload['digest'], payload['capture'])
            for line in stream(payload['alias'], shell, min(deadline, time.monotonic() + 35), stop):
                if line == '__SCRIPT_CREATED__':
                    if not emit('stage', stage='script_created'):
                        return
                elif line == '__TMUX_STARTED__':
                    if not emit('stage', stage='tmux_started'):
                        return
                else:
                    diagnostics = (diagnostics + line + '\n')[-16384:]
            launched = True
        frame = None
        for line in stream(payload['alias'], monitor_shell(payload), deadline, stop):
            if line == '__FRAME__':
                frame = []
            elif line == '__END__' and frame is not None:
                if not emit('report', report=decode_frame(frame)):
                    return
                frame = None
            elif frame is not None:
                frame.append(line)
                if len(frame) > 20:
                    raise ValueError('Invalid SSH protocol')
            else:
                diagnostics = (diagnostics + line + '\n')[-16384:]
        emit('failure', failure='ssh', intent=intent, detail=diagnostics)
    except TimeoutError:
        emit('failure', failure='timeout' if intent else 'ssh', intent=intent, detail=diagnostics)
    except (TransportError, OSError) as exc:
        emit('failure', failure='ssh', intent=intent, detail=(diagnostics + str(exc))[-16384:])
    except Exception as exc:
        emit('failure', failure='monitor' if launched else 'setup', intent=intent,
             detail=(diagnostics + str(exc))[-16384:])
