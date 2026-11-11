"""Local-only Odoo process for a verified, explicitly activated migration."""
import argparse
import sys
from pathlib import Path
from common import MigrationError, connect, loads
from worker import isolate


def prevent_database_creation(database):
    # The destination was already checked before isolation. Native CLI startup
    # otherwise probes postgres and tries database creation on every launch.
    from odoo.service import db
    def existing_only(name):
        if name != database:
            raise MigrationError('Development server cannot create databases')
        raise db.DatabaseExists('Verified destination already exists')
    db._create_empty_database = existing_only


def disable_bus_notifications(argv):
    # Local development needs no cross-database postgres notification channel.
    from odoo.tools import config
    import odoo.modules.module
    config.parse_config(argv)
    odoo.modules.module.initialize_sys_path()
    from odoo.addons.bus.models.bus import BusBus
    BusBus._sendone = lambda *a, **kw: None
    BusBus._sendmany = lambda *a, **kw: None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--stage', type=Path, required=True)
    p.add_argument('--server', default='/opt/odoo19/server')
    p.add_argument('--port', type=int, default=8069)
    args = p.parse_args()
    marker = loads((args.stage / 'target.json').read_text())
    if not (args.stage / 'activation.json').exists():
        raise MigrationError('Run activate-dev after successful verification first')
    activation = loads((args.stage / 'activation.json').read_text())
    if activation.get('target') != marker['database'] or not activation.get('development'):
        raise MigrationError('Run activate-dev after successful verification first')
    con = connect(args.config, marker['database'])
    try:
        with con.cursor() as cr:
            cr.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            if cr.fetchone()[0] != 'accounting_migration:' + marker['ownership_token']:
                raise MigrationError('Database ownership marker mismatch')
            cr.execute('SELECT status FROM accounting_migration.run WHERE id')
            if cr.fetchone()[0] != 'development_active':
                raise MigrationError('Database is not activated for development')
            cr.execute('SELECT count(*) FROM ir_cron WHERE active')
            if cr.fetchone()[0]: raise MigrationError('Disable scheduled jobs before local development startup')
    finally: con.close()
    isolate(args.config, marker['database'])
    sys.path.insert(0, args.server)
    import odoo.cli
    prevent_database_creation(marker['database'])
    sys.argv = ['odoo', 'server', '-c', args.config, '-d', marker['database'],
                   '--db-filter=', '--no-database-list',
                   '--http-interface=127.0.0.1', '--http-port=' + str(args.port),
                   '--workers=0', '--max-cron-threads=0', '--logfile=']
    disable_bus_notifications(sys.argv[2:])
    odoo.cli.main()


if __name__ == '__main__':
    try: main()
    except MigrationError as exc: sys.exit(str(exc))
