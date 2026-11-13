"""Per-run backup consent, shared by import and explicit repair controllers."""
from pathlib import Path
import subprocess
import sys
import uuid

from common import MigrationError, digest, ensure_backup, loads, save_json


def require_choice(choice):
    if choice is not None and type(choice) is not bool:
        raise MigrationError('Backup choice must be --backup or --no-backup')
    if choice is None and not sys.stdin.isatty():
        raise MigrationError('Noninteractive imports require --backup or --no-backup; no backup was started')
    return choice


def select_backup(choice, database, stage):
    require_choice(choice)
    path = Path(stage) / 'before_import.dump'
    print(f'Target database: {database}\nBackup destination: {path}', flush=True)
    if choice is None:
        print('1. Take/verify backup\n2. Continue without backup\n0. Cancel', flush=True)
        while True:
            answer = input('Backup choice (1, 2, or 0): ').strip()
            if answer == '0':
                return None
            if answer in ('1', '2'):
                choice = answer == '1'
                break
            print('An explicit selection is required: 1, 2, or 0.')
    if choice:
        print('Existing backup will be verified and reused.' if path.exists() else 'A new backup will be created.', flush=True)
    else:
        print('Backup skipped by explicit choice.', flush=True)
    return choice


def perform_backup(config, database, stage, choice, *, ensure=ensure_backup, progress=None):
    if type(choice) is not bool:
        raise MigrationError('Explicit backup consent is required before continuing')
    stage = Path(stage)
    record = dict(database=database, requested=choice, status='skipped')
    attempt = stage / ('backup-decision-' + uuid.uuid4().hex + '.json')
    if choice:
        path = stage / 'before_import.dump'
        existed = path.exists()
        record.update(status='pending', path=str(path))
    save_json(attempt, record)
    save_json(stage / 'backup-report.json', record)
    if not choice:
        return record
    try:
        ensure(config, database, stage, **({'progress': progress} if progress is not None else {}))
        metadata = loads((stage / 'backup.json').read_text())
        if metadata['database'] != database or metadata['sha256'] != digest(path):
            raise MigrationError('Target backup checksum validation failed; operation stopped')
        checked = subprocess.run(['pg_restore', '--list', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if checked.returncode:
            raise MigrationError('Target backup archive validation failed; operation stopped')
        record['status'] = 'reused' if existed else 'created'
    except BaseException as exc:
        record.update(status='failed', error_type=type(exc).__name__)
        save_json(attempt, record)
        save_json(stage / 'backup-report.json', record)
        raise
    save_json(attempt, record)
    save_json(stage / 'backup-report.json', record)
    return record
