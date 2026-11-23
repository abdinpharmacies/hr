"""Explicit local PostgreSQL administrator launcher; never edits service configs."""
import os
from pathlib import Path
import pwd
import stat
import sys

ENV = 'ACCOUNTING_MIGRATION_LOCAL_PEER'
HERE = Path(__file__).resolve().parent


def enabled():
    if os.environ.get(ENV) != '1':
        return False
    from common import MigrationError
    if pwd.getpwuid(os.geteuid()).pw_name != 'postgres':
        raise MigrationError('Local peer mode must run as the Linux postgres account; use --local-peer with sudo.')
    return True


def run_root(default):
    return Path(default) / 'local-peer' if enabled() else Path(default)


def connection_settings(options):
    """Keep the configured socket/port; use the matching peer administrator."""
    if not enabled():
        return options
    from common import MigrationError
    host = options.get('db_host', '')
    if host not in ('', 'False', 'false') and not host.startswith('/'):
        raise MigrationError('--local-peer only supports local Unix-socket configurations; TCP hosts are refused.')
    return {**options, 'db_user': 'postgres', 'db_password': 'False'}


def prepare_workspace(path, account):
    """Create only our own directory; never chown existing migration artifacts."""
    from common import MigrationError
    path = Path(path)
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
    except FileExistsError:
        pass
    else:
        os.chown(path, account.pw_uid, account.pw_gid)
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != account.pw_uid
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise MigrationError('Local peer workspace must be a real directory owned by postgres with mode 0700: ' + str(path))
    return path


def runtime_groups(paths, account):
    """Grant this process group traversal of its runtime, not global membership."""
    from common import MigrationError
    groups = set(os.getgrouplist(account.pw_name, account.pw_gid))
    directories = {parent for path in paths for parent in (Path(path), *Path(path).parents)}
    for directory in directories:
        info = directory.stat()
        mode = info.st_mode
        if info.st_uid == account.pw_uid:
            accessible = bool(mode & stat.S_IXUSR)
        elif info.st_gid in groups:
            accessible = bool(mode & stat.S_IXGRP)
        else:
            accessible = bool(mode & stat.S_IXOTH)
            if not accessible and mode & stat.S_IXGRP:
                groups.add(info.st_gid)
                accessible = True
        if not accessible:
            raise MigrationError('Local peer runtime directory is not traversable by postgres: ' + str(directory)
                                 + '. Grant narrowly scoped access; do not use chmod 777.')
    return sorted(groups)


def launch(argv, default_root):
    from common import MigrationError
    flags = {value.split('=', 1)[0] for value in argv}
    if argv and not flags.intersection({'--export-table-plan', '--table-plan'}):
        raise MigrationError('--local-peer supports the CSV menu, CSV export/import, and menu database fixes only.')
    if '--extra-actions' in argv or any(value.startswith('--extra-actions=') for value in argv):
        raise MigrationError('Local peer mode does not support filestore actions; use the normal migration workflow for file copying.')
    try:
        account = pwd.getpwnam('postgres')
    except KeyError:
        raise MigrationError('The Linux postgres account is missing; local peer mode requires a local PostgreSQL installation.') from None
    if os.geteuid() not in (0, account.pw_uid):
        raise MigrationError('Run --local-peer with sudo, or as the Linux postgres account.')
    workspace = prepare_workspace(Path(default_root) / 'local-peer', account)
    groups = runtime_groups((HERE, Path(sys.executable).parent, workspace), account)
    environ = os.environ.copy()
    # Prevent inherited libpq environment settings from redirecting local access.
    for key in ('PGHOST', 'PGHOSTADDR', 'PGPORT', 'PGUSER', 'PGPASSWORD',
                'PGPASSFILE', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS', 'PGDATABASE'):
        environ.pop(key, None)
    environ.update({ENV: '1', 'HOME': account.pw_dir, 'USER': account.pw_name,
                    'LOGNAME': account.pw_name, 'PYTHONDONTWRITEBYTECODE': '1'})
    print('Local peer mode: running as PostgreSQL administrator postgres.\n'
          'Service configurations remain unchanged. Private workspace: ' + str(workspace), flush=True)
    os.umask(0o077)
    os.chdir(HERE)
    if os.geteuid() == 0:
        # Retain only groups needed by this runtime (e.g. /opt/odoo19 is 0750).
        # This never changes /etc/group or grants access to other processes.
        os.setgroups(groups)
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    for directory in (HERE, Path(sys.executable).parent, workspace):
        if not os.access(directory, os.X_OK):
            raise MigrationError('Local peer runtime directory is not traversable by postgres: ' + str(directory))
    os.execve(sys.executable, [sys.executable, '-B', str(HERE / 'migrate.py'), *argv], environ)
