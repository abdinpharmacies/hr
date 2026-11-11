#!/usr/bin/env python3
"""Copy custom Odoo 15 models into a prepared Odoo 19 target, with approval gates."""
import argparse
from pathlib import Path
import sys
from common import MigrationError

HERE = Path(__file__).resolve().parent
RUN_ROOT = HERE.parents[2] / 'migration-runs'


def parser():
    p = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for name in ('source-config', 'source-db', 'target-config', 'target-db'):
        p.add_argument('--' + name, required=True)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    from prepared import run
    return run(args, RUN_ROOT)


if __name__ == '__main__':
    try:
        main()
    except (MigrationError, KeyboardInterrupt) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f'ERROR: {type(exc).__name__}; SQL/config values are not logged.', file=sys.stderr)
        sys.exit(2)
