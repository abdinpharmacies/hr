"""Shared migration primitives. No Odoo import and no implicit database writes."""
import ast
import base64
import configparser
import datetime
import decimal
import hashlib
import json
import os
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
AUDIT = {'create_uid', 'write_uid', 'create_date', 'write_date'}
TECHNICAL = {'id', 'display_name', '__last_update', 'parent_path'}
EXCLUDED = {'mail.message', 'mail.followers', 'mail.activity', 'mail.notification',
            'mail.mail', 'mail.channel', 'discuss.channel', 'bus.bus', 'queue.job', 'ir.logging', 'ir.cron',
            'ir.config_parameter', 'res.users.apikeys', 'res.users.log'}
LOOKUPS = {'res.groups', 'ir.model', 'ir.model.fields', 'ir.ui.view', 'ir.actions.act_window',
           'ir.actions.report', 'ir.actions.actions', 'ir.ui.menu'}
NATIVE = {'res.users', 'res.partner', 'res.company', 'res.currency', 'res.currency.rate',
          'res.country', 'res.country.state', 'res.country.group', 'res.partner.category',
          'res.partner.industry', 'res.partner.title', 'report.paperformat', 'res.lang', 'res.bank', 'res.partner.bank',
          'ir.attachment', 'ir.sequence', 'ir.sequence.date_range', 'resource.calendar',
          'resource.calendar.attendance', 'resource.calendar.leaves', 'resource.resource'}


class MigrationError(Exception):
    pass


def settings(path):
    c = configparser.ConfigParser(interpolation=None)
    if not c.read(path):
        raise MigrationError(f'Cannot read configuration: {path}')
    return dict(c['options'])


def connect(config, database, readonly=True):
    opts = settings(config)
    args = {k[3:]: opts[k] for k in ('db_host', 'db_port', 'db_user', 'db_password')
            if opts.get(k) not in (None, '', 'False', 'false')}
    con = psycopg2.connect(dbname=database, connect_timeout=10, **args)
    con.set_session(readonly=readonly, isolation_level='REPEATABLE READ' if readonly else 'READ COMMITTED')
    return con


def json_default(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat(sep=' ') if isinstance(value, datetime.datetime) else value.isoformat()
    if isinstance(value, decimal.Decimal):
        return {'$decimal': str(value)}
    if isinstance(value, (bytes, memoryview)):
        return {'$bytes': base64.b64encode(bytes(value)).decode()}
    raise TypeError(type(value).__name__)


def json_hook(value):
    if set(value) == {'$decimal'}:
        return decimal.Decimal(value['$decimal'])
    if set(value) == {'$bytes'}:
        return base64.b64decode(value['$bytes'])
    return value


def dumps(value):
    return json.dumps(value, default=json_default, ensure_ascii=False, sort_keys=True)


def loads(value):
    return json.loads(value, object_hook=json_hook)


def private_dir(path):
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_mode & 0o077:
        raise MigrationError(f'Directory must be private (chmod 700): {path}')
    return path


def save_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    with open(temp, 'w', encoding='utf-8', opener=lambda p, f: os.open(p, f, 0o600)) as out:
        out.write(dumps(value) + '\n')
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, path)


def manifests(root=ROOT):
    return {p.parent.name: ast.literal_eval(p.read_text()) for p in Path(root).glob('*/__manifest__.py')}


def downstream(dependencies, root='ab_accounting'):
    found = {root}
    while True:
        more = found | {m for m, ds in dependencies.items() if found.intersection(ds)}
        if more == found:
            return sorted(found)
        found = more


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_attachment_path(root, name):
    path = (Path(root) / name).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise MigrationError('Attachment path escapes filestore')
    return path


def schema_digest(schema):
    """Fingerprint structure, not data-dependent choices such as active languages."""
    structural = {
        model: {**meta, 'fields': {
            name: {key: value for key, value in field.items() if key != 'selection'}
            for name, field in meta['fields'].items()}}
        for model, meta in schema.items()}
    return hashlib.sha256(dumps(structural).encode()).hexdigest()


def property_blockers(con, models):
    """Odoo 15 company-dependent values live outside their model's table."""
    with con.cursor() as cr:
        cr.execute('SELECT DISTINCT f.model,f.name FROM ir_property p '
                   'JOIN ir_model_fields f ON f.id=p.fields_id WHERE f.model=ANY(%s)', [list(models)])
        return {f'Company-dependent property needs an explicit adapter: {model}.{name}' for model, name in cr}


def ensure_backup(config, database, stage, progress=None):
    """Backup the owned initialized destination before the isolated worker starts."""
    import subprocess
    path = Path(stage) / 'before_import.dump'
    if path.exists():
        if progress:
            progress.begin('backup',operation='Verify existing backup checksum',file_path=str(path))
        expected = loads((Path(stage) / 'backup.json').read_text())
        if expected['database'] != database or digest(path) != expected['sha256']:
            raise MigrationError('Destination backup identity/checksum mismatch')
        if progress:
            progress.finish('existing backup verified')
        return
    if progress:
        progress.begin('backup',operation='Create target backup',file_path=str(path))
    options = settings(config)
    environ = os.environ.copy()
    for name, key in [('PGHOST','db_host'), ('PGPORT','db_port'), ('PGUSER','db_user'), ('PGPASSWORD','db_password')]:
        if options.get(key) not in (None, '', 'False'):
            environ[name] = options[key]
    path.touch(mode=0o600)
    proc = subprocess.run(['pg_dump', '-Fc', '--no-owner', '-d', database, '-f', str(path)], env=environ, capture_output=True)
    if proc.returncode:
        path.unlink(missing_ok=True)
        raise MigrationError('Destination backup failed; no import started')
    save_json(Path(stage) / 'backup.json', {'database': database, 'sha256': digest(path)})
    if progress:
        progress.update(bytes=path.stat().st_size)
        progress.finish('backup complete and verified')
