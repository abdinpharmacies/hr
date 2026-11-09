import os
from pathlib import Path
import subprocess
import time

from psycopg.conninfo import conninfo_to_dict


def database_environment(dsn):
    values = conninfo_to_dict(dsn)
    mapping = {'host': 'PGHOST', 'port': 'PGPORT', 'user': 'PGUSER',
               'password': 'PGPASSWORD', 'dbname': 'PGDATABASE', 'sslmode': 'PGSSLMODE'}
    if values.keys() - mapping.keys():
        raise ValueError('Unsupported PostgreSQL backup connection options')
    env = {key: value for key, value in os.environ.items() if not key.startswith('PG')}
    env.update({mapping[key]: value for key, value in values.items()})
    env['PGCONNECT_TIMEOUT'] = '5'
    return env


def backup_postgres(store, destination):
    path = Path(destination)
    if path.parent.stat().st_mode & 0o077:
        raise ValueError('Backup directory must be private (0700)')
    env = database_environment(store.database_url)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    started = time.monotonic()
    try:
        with os.fdopen(descriptor, 'wb') as output:
            result = subprocess.run(['pg_dump', '--format=custom', '--no-owner', '--no-acl'],
                                    env=env, stdout=output, stderr=subprocess.DEVNULL, timeout=120)
            if result.returncode:
                raise RuntimeError('PostgreSQL backup failed')
            output.flush()
            os.fsync(output.fileno())
        result = subprocess.run(['pg_restore', '--list', str(path)], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=30)
        if result.returncode:
            raise RuntimeError('PostgreSQL backup archive is invalid')
        from .queue_transfer import sync_directory
        sync_directory(path.parent)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return {'seconds': time.monotonic() - started, 'bytes': path.stat().st_size}
