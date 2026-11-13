"""Interactive dispatch only; the existing import/export procedures are unchanged."""
import json
import os
from pathlib import Path
import tempfile

from common import MigrationError, settings
from csv_plan import read_plan

DEFAULTS = dict(source_config='/opt/odoo15/config/abdin15.conf', source_db='abdinpharmacies',
                target_config='/opt/odoo19/config/migrate19.conf', target_db='main19',
                csv_path='/opt/odoo19/migration-runs/main19-2.csv')
FLAGS = ('source_config', 'source_db', 'target_config', 'target_db')


def load_defaults(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(value, dict) or set(value) != set(DEFAULTS):
            raise ValueError()
        if any(not isinstance(v, str) or not v.strip() or '\x00' in v for v in value.values()):
            raise ValueError()
        return value
    except FileNotFoundError:
        return DEFAULTS.copy()
    except (OSError, ValueError):
        print('Saved menu settings are unreadable or invalid; enter settings again.')
        return DEFAULTS.copy()


def save_defaults(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.menu-defaults-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump({key: values[key] for key in DEFAULTS}, out, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def collect(defaults, choice):
    result = defaults.copy()
    for key in DEFAULTS:
        flag = ('--export-table-plan' if choice == '1' else '--table-plan') if key == 'csv_path' else '--' + key.replace('_', '-')
        while True:
            value = input(f'{flag} [{result[key]}]: ').strip() or result[key]
            try:
                if '\x00' in value:
                    raise MigrationError('NUL characters are not allowed')
                if key.endswith('_config'):
                    value = str(Path(value).expanduser().resolve())
                    if not Path(value).is_file():
                        raise MigrationError('Configuration file does not exist')
                    settings(value)
                if key == 'csv_path':
                    value = str(Path(value).expanduser().resolve())
                    if choice == '1':
                        if Path(value).exists() or Path(value + '.metadata.json').exists():
                            raise MigrationError('CSV or sidecar already exists; choose a new export path')
                        if not Path(value).parent.is_dir():
                            raise MigrationError('Export destination directory does not exist')
                    else:
                        read_plan(value)
                result[key] = value
                break
            except (MigrationError, OSError, ValueError) as exc:
                print(str(exc) if isinstance(exc, MigrationError) else 'Invalid or unreadable settings/file.')
    return result


def run_menu(dispatch, root):
    path = Path(root) / 'menu-defaults.json'
    defaults = load_defaults(path)
    while True:
        try:
            print('\n1. Export migration CSV\n2. Import migration CSV\n3. Fix database\n0. Exit script')
            choice = input('Select: ').strip()
            if choice == '0':
                return 0
            if choice not in ('1', '2', '3'):
                print('Choose 1, 2, 3, or 0.')
                continue
            values = collect(defaults, choice)
            save_defaults(path, values)
            defaults = values
            if choice == '3':
                from database_repair import run
                run(values, root)
            else:
                argv = []
                for key in FLAGS:
                    argv.extend(['--' + key.replace('_', '-'), values[key]])
                argv.extend(['--export-table-plan' if choice == '1' else '--table-plan', values['csv_path']])
                result = dispatch(argv)
                if isinstance(result, dict):
                    print('Result:', result.get('status', 'finished'))
        except EOFError:
            return 0
        except KeyboardInterrupt:
            print('\nCancelled; returning to menu.')
        except Exception as exc:
            # Native SQL details can contain passwords and business payloads.
            print(str(exc) if isinstance(exc, MigrationError) else f'Operation failed: {type(exc).__name__}.')
