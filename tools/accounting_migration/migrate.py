#!/usr/bin/env python3
"""Copy custom Odoo 15 models into a prepared Odoo 19 target, with approval gates."""
import argparse
from pathlib import Path
import sys
import shlex
from common import MigrationError

HERE = Path(__file__).resolve().parent
RUN_ROOT = HERE.parents[2] / 'migration-runs'


def parser():
    p = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for name in ('source-config', 'source-db', 'target-config', 'target-db'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--reset',action='store_true',help='Confirm deletion of private pre-import schemas and matching run directories, then exit. Deletes contained backups/logs/extraction; preserves public records.')
    return p


def main(argv=None):
    p=parser()
    args = p.parse_args(argv)
    p.print_help()
    sys.stdout.flush()
    try:
        if args.reset:
            from reset_migration import reset
            return reset(args,RUN_ROOT)
        from prepared import run
        return run(args, RUN_ROOT)
    except Exception:
        recovery_help(args)
        raise


def recovery_help(args):
    command=[sys.executable,str(HERE/'migrate.py')]
    for name in ('source_config','source_db','target_config','target_db'):
        command+=['--'+name.replace('_','-'),getattr(args,name)]
    command.append('--reset')
    print('Recovery: rerun normally to resume. To start fresh after schema/rule changes, use optional --reset.',file=sys.stderr)
    print('--reset asks before deleting private schemas and matching run directories (including backups). It refuses committed imports.',file=sys.stderr)
    print(shlex.join(command),file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except (MigrationError, KeyboardInterrupt) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f'ERROR: {type(exc).__name__}; SQL/config values are not logged.', file=sys.stderr)
        sys.exit(2)
