"""Target checkpoint availability gates and crash recovery."""
import argparse
import contextlib
from pathlib import Path
import subprocess
import sys
import time
import select

from psycopg2 import sql
from common import MigrationError, connect, loads, save_json


def lock_key(database):
    return 'prepared_custom_migration:' + database


def terminate_saved(cursor, oid, sessions):
    for session in sessions:
        cursor.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity '
                       'WHERE datid=%s AND pid=%s AND backend_start=%s::timestamptz',
                       [oid, session['pid'], session['started']])
    for _ in range(40):
        remaining=False
        for session in sessions:
            cursor.execute('SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datid=%s AND pid=%s '
                           'AND backend_start=%s::timestamptz)',[oid,session['pid'],session['started']])
            remaining=cursor.fetchone()[0] or remaining
        if not remaining:
            return
        time.sleep(.1)
    raise MigrationError('Abandoned migration sessions have not exited; target remains blocked for recovery')


class DatabaseGate:
    def __init__(self, config, database):
        self.config, self.database = config, database
        self.control = connect(config, 'postgres', readonly=False)
        self.control.autocommit = True
        with self.control.cursor() as cr:
            cr.execute('SELECT oid,datallowconn,pg_get_userbyid(datdba)=current_user '
                       'OR (SELECT rolsuper FROM pg_roles WHERE rolname=current_user) '
                       'FROM pg_database WHERE datname=%s', [database])
            row = cr.fetchone()
            if not row:
                self.control.close()
                raise MigrationError(f'Database does not exist: {database}')
            self.oid, self.initial_online, owner = row
            if not owner:
                self.control.close()
                raise MigrationError(f'Database ownership is required: {database}')
            cr.execute('SELECT pg_try_advisory_lock(hashtext(%s))', [lock_key(database)])
            if not cr.fetchone()[0]:
                self.control.close()
                raise MigrationError(f'Another migration/recovery owns {database}')

    def online(self):
        with self.control.cursor() as cr:
            cr.execute('SELECT datallowconn FROM pg_database WHERE oid=%s AND datname=%s',
                       [self.oid, self.database])
            row = cr.fetchone()
            if row is None:
                raise MigrationError('Database identity changed')
            return row[0]

    def set_online(self, enabled):
        # Identity must be checked before ALTER; never affect a replacement DB.
        self.online()
        with self.control.cursor() as cr:
            cr.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS {}').format(
                sql.Identifier(self.database), sql.SQL('true' if enabled else 'false')))
        if self.online() != enabled:
            raise MigrationError(f'Could not verify availability: {self.database}')

    def sessions(self, allowed=()):
        with self.control.cursor() as cr:
            cr.execute('SELECT pid,backend_start,usename,backend_type FROM pg_stat_activity '
                       'WHERE datid=%s AND NOT (pid=ANY(%s))', [self.oid, list(allowed)])
            return cr.fetchall()

    def check_sessions(self, allowed=()):
        with self.control.cursor() as cr:
            cr.execute("SELECT rolsuper OR pg_has_role(current_user,'pg_signal_backend','MEMBER') "
                       'FROM pg_roles WHERE rolname=current_user')
            elevated = cr.fetchone()[0]
            cr.execute('SELECT current_user')
            user = cr.fetchone()[0]
        for _, _, owner, kind in self.sessions(allowed):
            if kind not in ('client backend', 'autovacuum worker') or (owner != user and not elevated):
                raise MigrationError(f'Cannot safely exclude every writer from {self.database}; '
                                     'close other-role/background writer sessions manually')

    def exclude(self, allowed=()):
        self.check_sessions(allowed)
        self.set_online(False)
        for _ in range(40):
            others = [r for r in self.sessions(allowed) if r[3] != 'autovacuum worker']
            if not others:
                return
            with self.control.cursor() as cr:
                for pid, started, _, _ in others:
                    cr.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity '
                               'WHERE datid=%s AND pid=%s AND backend_start=%s',
                               [self.oid, pid, started])
            time.sleep(.1)
        raise MigrationError(f'Exclusive access not established: {self.database}')

    def close(self):
        self.control.close()


@contextlib.contextmanager
def target_offline(gate, connection, stage, workers=()):
    """A watchdog owns cleanup if this process is killed, including SIGKILL."""
    state = Path(stage) / 'availability.json'
    pid = connection.get_backend_pid()
    allowed=[pid,*workers]
    gate.check_sessions(allowed)
    with gate.control.cursor() as cr:
        cr.execute('SELECT pid,backend_start::text FROM pg_stat_activity WHERE pid=ANY(%s) AND datid=%s',
                   [allowed, gate.oid])
        sessions=[dict(pid=p,started=s) for p,s in cr.fetchall()]
    if {s['pid'] for s in sessions}!=set(allowed):
        raise MigrationError('A prepared migration worker connection is missing')
    marker = dict(database=gate.database, oid=gate.oid, sessions=sessions, offline=True)
    save_json(state, marker)
    log = open(Path(stage) / 'watchdog.log', 'a')
    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
        '--watchdog', '--config', gate.config, '--database', gate.database, '--state', str(state)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
    try:
        if not select.select([proc.stdout],[],[],15)[0] or proc.stdout.readline().strip() != 'READY':
            raise MigrationError('Target recovery watchdog did not start')
        gate.exclude(allowed)
        yield
    finally:
        # Rollback is safe even after COMMIT. It must precede reopening access.
        try:
            if not connection.closed:
                connection.rollback()
            gate.set_online(True)
            marker['offline'] = False
            save_json(state, marker)
            print(f'Target online: {gate.database}', flush=True)
            if proc.poll() is None:
                proc.stdin.write('DONE\n')
                proc.stdin.flush()
        finally:
            proc.stdin.close()
            proc.stdout.close()
            log.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Do not kill recovery when availability restoration failed.
                pass


def recover_target(gate, stage):
    state = Path(stage) / 'availability.json'
    if not state.exists():
        if not gate.online():
            raise MigrationError('Target is offline without this run\'s recovery marker; reopen it manually')
        return
    marker = loads(state.read_text())
    if marker['database'] != gate.database or marker['oid'] != gate.oid:
        raise MigrationError('Availability recovery database identity mismatch')
    if marker['offline']:
        with gate.control.cursor() as cr:
            terminate_saved(cr,gate.oid,marker['sessions'])
        gate.set_online(True)
        marker['offline'] = False
        save_json(state, marker)
    elif not gate.online():
        raise MigrationError('Target was manually disabled; reopen it before retrying')


def watchdog(config, database, state):
    # Open maintenance before notifying the controller that cleanup is armed.
    con = connect(config, 'postgres', readonly=False)
    con.autocommit = True
    print('READY', flush=True)
    line = sys.stdin.readline()
    if line.strip() == 'DONE':
        con.close()
        return
    try:
        # Keep autocommit: recovery metadata must follow a committed ALTER.
        with con.cursor() as cr:
            for _ in range(300):
                cr.execute('SELECT pg_try_advisory_lock(hashtext(%s))', [lock_key(database)])
                if cr.fetchone()[0]:
                    break
                time.sleep(.1)
            else:
                return  # Another controller owns recovery; never reopen its checkpoint.
            marker = loads(Path(state).read_text())
            if not marker['offline']:
                return
            cr.execute('SELECT oid FROM pg_database WHERE datname=%s', [database])
            if cr.fetchone() != (marker['oid'],):
                raise MigrationError('Watchdog database identity changed')
            terminate_saved(cr,marker['oid'],marker['sessions'])
            cr.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS true').format(sql.Identifier(database)))
            cr.execute('SELECT datallowconn FROM pg_database WHERE oid=%s AND datname=%s',[marker['oid'],database])
            if cr.fetchone()!=(True,):
                raise MigrationError('Watchdog could not verify restored target access')
            marker['offline'] = False
            save_json(Path(state), marker)
    finally:
        con.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--watchdog', action='store_true', required=True)
    for name in ('config', 'database', 'state'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    watchdog(args.config, args.database, args.state)
