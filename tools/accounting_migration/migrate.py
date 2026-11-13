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
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--reset',action='store_true',help='Confirm deletion of private pre-import schemas and matching run directories, then exit. Deletes contained backups/logs/extraction; preserves public records.')
    mode.add_argument('--export-table-plan', metavar='PATH', help='Export read-only CSV table selections and metadata, then exit.')
    mode.add_argument('--table-plan', metavar='PATH', help='Replicate tables using a reviewed CSV plan, without PostgreSQL staging.')
    p.add_argument('--extra-actions', choices=('menu', 'copy-filestore'), help='Opt-in CSV extra action; requires --table-plan.')
    backup = p.add_mutually_exclusive_group()
    backup.add_argument('--backup', dest='backup', action='store_true', default=None,
                        help='Explicitly authorize creating or verifying a target backup for this import.')
    backup.add_argument('--no-backup', dest='backup', action='store_false',
                        help='Explicitly continue this import without creating or verifying a backup.')
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        if not sys.stdin.isatty():
            parser().print_help()
            return 2
        from migration_menu import run_menu
        return run_menu(main, RUN_ROOT)
    p=parser()
    args = p.parse_args(argv)
    if args.extra_actions and not args.table_plan:
        p.error('--extra-actions requires --table-plan')
    if not args.reset and not args.export_table_plan:
        from backup_policy import require_choice
        try:
            require_choice(args.backup)
        except MigrationError as exc:
            p.error(str(exc))
    p.print_help()
    sys.stdout.flush()
    try:
        if args.reset:
            from reset_migration import reset
            return reset(args,RUN_ROOT)
        if args.export_table_plan:
            from csv_plan import export_plan
            return export_plan(args)
        if args.table_plan:
            from csv_replicator import run
            return run(args, RUN_ROOT)
        from prepared import run
        return run(args, RUN_ROOT)
    except Exception:
        recovery_help(args)
        raise


def recovery_help(args):
    if getattr(args, 'table_plan', None) or getattr(args, 'export_table_plan', None):
        print('CSV mode: fix the reported operation and rerun the same command. Retain the CSV sidecar and run extraction; --reset does not manage CSV runs.', file=sys.stderr)
        return
    command=[sys.executable,str(HERE/'migrate.py')]
    for name in ('source_config','source_db','target_config','target_db'):
        command+=['--'+name.replace('_','-'),getattr(args,name)]
    command.append('--reset')
    print('Rerun the same command to skip committed operations and retry failed or unfinished work using the saved extraction.',file=sys.stderr)
    print('For pre-import schema/rule changes only, use optional --reset.',file=sys.stderr)
    print('--reset asks before deleting private schemas and matching run directories (including backups). It refuses committed imports.',file=sys.stderr)
    print(shlex.join(command),file=sys.stderr)


if __name__ == '__main__':
    try:
        result = main()
        if isinstance(result, int):
            sys.exit(result)
        if isinstance(result, dict) and result.get("status") == "finished_with_errors":
            sys.exit(2)
    except (MigrationError, KeyboardInterrupt) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f'ERROR: {type(exc).__name__}; SQL/config values are not logged.', file=sys.stderr)
        sys.exit(2)
