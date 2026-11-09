import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path('/home/abdin_04/.config/crm-messaging')
PYTHON = PRIVATE / 'venv/bin/python'
CONFIG = PRIVATE / 'config.json'
RUNTIME = PRIVATE / 'run'
STATE = RUNTIME / 'services.json'
ACCOUNT = 'tg-callcenter'


class StartupBlocked(RuntimeError):
    pass


class StartupUnavailable(RuntimeError):
    pass


def boot_identity():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def process_state(pid):
    return {'pid': pid, 'identity': process_identity(pid), 'boot': boot_identity()}


def process_identity(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def running(state):
    identity = process_identity(state['pid'])
    return (
        state.get('boot') == boot_identity()
        and identity is not None
        and identity == state['identity']
    )


def read_state():
    try:
        return json.loads(STATE.read_text())
    except FileNotFoundError:
        return None


def preflight():
    import httpx
    from app.config import Settings, load_odoo_tokens
    from app.odoo import Odoo
    from app.storage import Store, Conflict
    from app.telegram_setup import configure

    try:
        if CONFIG.stat().st_mode & 0o077:
            raise ValueError('Configuration is not private')
        config = Settings.model_validate(json.loads(CONFIG.read_text()))
    except (OSError, ValueError, TypeError):
        raise StartupBlocked(
            'A valid protected configuration with mode 0600 is required.'
        ) from None
    if (
        config.odoo_url != 'http://127.0.0.1:4092'
        or config.odoo_database != 'callcenter'
        or config.odoo_transport != 'controller_v1'
        or not config.allow_loopback_http
        or config.sending_enabled
        or set(config.accounts) != {ACCOUNT}
    ):
        raise StartupBlocked('Expected the callcenter reception-only configuration.')
    account = config.accounts[ACCOUNT]
    if (
        not account.enabled
        or account.provider != 'telegram'
        or account.provider_account != '8933526980'
        or account.token_source != 'odoo'
        or account.reception != 'polling'
    ):
        raise StartupBlocked(
            'Reception must be explicitly enabled in the protected configuration first.'
        )
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        response = client.post(
            config.odoo_url + '/json/2/ab_crm_messaging_account/search_read',
            headers={
                'Authorization': 'Bearer ' + config.odoo_key.get_secret_value(),
                'X-Odoo-Database': config.odoo_database,
            },
            json={
                'domain': [['code', '=', ACCOUNT]],
                'fields': [
                    'provider_account',
                    'enabled',
                    'legacy_worker_disabled',
                    'active',
                ],
                'limit': 2,
            },
        )
        if response.status_code >= 500 or response.status_code == 429:
            raise StartupUnavailable('Odoo is temporarily unavailable.')
        if response.status_code != 200:
            raise StartupBlocked(
                'Odoo account authentication failed; check the service API key and permissions.'
            )
        rows = response.json()
        if (
            len(rows) != 1
            or rows[0]['provider_account'] != account.provider_account
            or not all(
                rows[0][key] for key in ('enabled', 'legacy_worker_disabled', 'active')
            )
        ):
            raise StartupBlocked(
                'The Odoo account must be explicitly enabled after checking the previous worker is inactive.'
            )
        load_odoo_tokens(config, Odoo(config, client))
        identity = configure(client, account)
        if (
            identity['webhook_present']
            or identity['username'].lower() != 'abdin_callcenter_bot'
        ):
            raise StartupBlocked('Bot identity or webhook ownership prevents polling.')
    store = Store(config.database_url.get_secret_value())
    with store.connect() as conn:
        if not config.database_url.get_secret_value().startswith('sqlite:'):
            row = conn.execute(
                'SELECT current_database() AS db,current_user AS role'
            ).fetchone()
            if row != {
                'db': 'crm_messaging_callcenter',
                'role': 'crm_messaging_callcenter',
            }:
                raise StartupBlocked('Expected the dedicated queue database and role.')
        if not conn.execute(
            'SELECT version FROM messaging_schema WHERE version=1'
        ).fetchone():
            raise StartupBlocked('Queue migration is required.')
    try:
        with store.receiver(account.provider_account):
            pass
    except Conflict:
        raise StartupBlocked(
            'Another receiver owns this bot; operator review is required.'
        ) from None
    try:
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 5088))
    except OSError:
        raise StartupBlocked(
            'Port 5088 is unavailable; no existing process was stopped.'
        ) from None


def supervise():
    import httpx

    processes = {}
    logs = []
    stopping = False

    def stop_requested(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop_requested)
    signal.signal(signal.SIGINT, stop_requested)
    commands = {
        'api': [
            '-m',
            'uvicorn',
            'app.main:create_app',
            '--factory',
            '--host',
            '127.0.0.1',
            '--port',
            '5088',
            '--workers',
            '1',
            '--no-access-log',
            '--no-proxy-headers',
        ],
        'receiver': ['-m', 'app.receiver', ACCOUNT],
        'worker': ['-m', 'app.worker'],
    }
    try:
        for name, arguments in commands.items():
            if stopping:
                return
            log = (RUNTIME / f'{name}.log').open('ab')
            logs.append(log)
            processes[name] = subprocess.Popen(
                [str(PYTHON), *arguments],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        state = process_state(os.getpid())
        state['children'] = {
            name: process_state(child.pid) for name, child in processes.items()
        }
        STATE.write_text(json.dumps(state))
        deadline = time.monotonic() + 30
        healthy = False
        with httpx.Client(timeout=1, follow_redirects=False, trust_env=False) as client:
            while not stopping:
                if processes['receiver'].poll() == 75:
                    raise StartupUnavailable(
                        'Receiver initialization is temporarily unavailable; all task-owned services are stopping.'
                    )
                if processes['receiver'].poll() is not None:
                    raise StartupBlocked(
                        'Receiver exited. All task-owned services are stopping; review private logs before restarting.'
                    )
                if any(child.poll() is not None for child in processes.values()):
                    raise StartupUnavailable(
                        'An API or worker process exited. All task-owned services are stopping.'
                    )
                if not healthy:
                    try:
                        response = client.get('http://127.0.0.1:5088/health')
                        healthy = response.status_code == 200 and response.json() == {
                            'status': 'ok'
                        }
                    except (httpx.HTTPError, ValueError):
                        pass
                    if healthy:
                        print(
                            'FastAPI, one receiver and one worker started. Sending is disabled. Ctrl+C stops all three.',
                            flush=True,
                        )
                    elif time.monotonic() >= deadline:
                        raise StartupUnavailable('FastAPI health check timed out.')
                time.sleep(0.5)
    finally:
        for child in processes.values():
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 10
        for child in processes.values():
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        STATE.unlink(missing_ok=True)
        for log in logs:
            log.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'command', choices=['start', 'serve', 'check', 'status', 'stop']
    )
    args = parser.parse_args()
    os.umask(0o077)
    os.environ['CRM_MESSAGING_CONFIG'] = str(CONFIG)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.path.insert(0, str(ROOT))
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    if args.command in ('status', 'stop'):
        state = read_state()
        if not state or not running(state):
            print('Launcher is not running.')
            return
        if args.command == 'status':
            print(
                json.dumps(
                    {
                        'supervisor': state['pid'],
                        'services': {
                            name: running(child)
                            for name, child in state['children'].items()
                        },
                    }
                )
            )
            return
        descriptor = os.pidfd_open(state['pid'])
        try:
            if not running(state):
                raise RuntimeError('Supervisor identity changed; no signal was sent.')
            signal.pidfd_send_signal(descriptor, signal.SIGTERM)
        finally:
            os.close(descriptor)
        for attempt in range(60):
            if not STATE.exists():
                print('Task-owned services stopped. Queue history retained.')
                return
            time.sleep(0.25)
        raise RuntimeError('Stop has not completed; inspect private logs.')
    else:
        with (RUNTIME / 'launcher.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise StartupBlocked('This launcher is already running.') from None
            preflight()
            if args.command == 'check':
                print('Preflight passed. No services started.')
                return
            supervise()


if __name__ == '__main__':
    try:
        main()
    except StartupBlocked as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(78) from None
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(75) from None
    except Exception:
        print(
            'A gateway dependency is unavailable. Check the private configuration and service logs.',
            file=sys.stderr,
        )
        raise SystemExit(75) from None
