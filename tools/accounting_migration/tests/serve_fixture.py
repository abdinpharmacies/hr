"""Serve synthetic records only, for local browser acceptance testing."""
import argparse
import fcntl
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import connect, loads
from worker import isolate
from psycopg2 import sql
p = argparse.ArgumentParser()
p.add_argument('stage', type=Path)
p.add_argument('--port', type=int, default=8079)
a = p.parse_args()
lock = open(a.stage / 'worker.lock', 'a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
m = loads((a.stage / 'target.json').read_text())
assert 'fixture' in m['database'] and loads((a.stage / 'manifest.json').read_text())['synthetic']
config = '/opt/odoo19/config/migrate19.conf'
c = connect(config, 'postgres', readonly=False)
c.autocommit = True
with c.cursor() as cr:
    cr.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s", [m['database']])
    assert cr.fetchone()[0] == 'accounting_migration:' + m['ownership_token']
    cr.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS true').format(sql.Identifier(m['database'])))
try:
    isolate(config, m['database'])
    sys.path.insert(0, '/opt/odoo19/server')
    import odoo.cli
    from dev_server import prevent_database_creation, disable_bus_notifications
    prevent_database_creation(m['database'])
    sys.argv = ['odoo', 'server', '-c', config, '-d', m['database'], '--db-filter=', '--no-database-list',
                   '--http-interface=127.0.0.1', '--http-port=' + str(a.port),
                   '--workers=0', '--max-cron-threads=0', '--logfile=']
    disable_bus_notifications(sys.argv[2:])
    odoo.cli.main()
finally:
    with c.cursor() as cr:
        cr.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(m['database'])))
    c.close()
