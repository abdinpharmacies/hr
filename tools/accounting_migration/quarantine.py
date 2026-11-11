"""Explicit, snapshot-bound quarantine; immutable extraction remains untouched."""
import shutil
from pathlib import Path
from psycopg2 import sql
from common import MigrationError, loads, save_json, safe_attachment_path, digest
from resume import fingerprint, BUSINESS_VERSION

ALLOWED = {'abdin_eplus.pur_trans_d', 'ir.attachment'}


def validate_policy(policy, snapshot):
    if policy.get('version') != 1 or policy.get('snapshot') != snapshot:
        raise MigrationError('Quarantine approval does not match this extraction snapshot')
    records = policy.get('records', {})
    if not records or set(records) - ALLOWED:
        raise MigrationError('Unsupported quarantine scope')
    for model, rows in records.items():
        ids = [r.get('source_id') for r in rows]
        if not ids or any(type(i) is not int or i <= 0 for i in ids) or len(set(ids)) != len(ids):
            raise MigrationError('Invalid or duplicate quarantine source IDs')
        if any(type(r.get('missing_id')) is not int or not isinstance(r.get('missing_model'), str) for r in rows):
            raise MigrationError('Quarantine entries require original missing references')
    return policy


class Quarantine:
    def load_quarantine_policy(self):
        path = self.stage / 'quarantine-policy.json'
        self.quarantine_policy = validate_policy(loads(path.read_text()), self.manifest_id) if path.exists() else None
        self.quarantine_models = set()

    def business_identity(self):
        contract = dict(version=BUSINESS_VERSION, mapping=self.mapping_identity())
        if getattr(self, 'quarantine_policy', None):
            contract['quarantine'] = fingerprint(self.quarantine_policy)
        return fingerprint(contract)

    def prepare_quarantine(self):
        policy = getattr(self, 'quarantine_policy', None)
        if not policy:
            return
        self.execute('CREATE SCHEMA accounting_migration_quarantine')
        self.execute('REVOKE ALL ON SCHEMA accounting_migration_quarantine FROM PUBLIC')
        self.execute('CREATE TABLE accounting_migration_quarantine.records '
                     '(model text NOT NULL,source_id bigint NOT NULL,missing_model text NOT NULL,missing_id bigint NOT NULL,'
                     'snapshot text NOT NULL,payload jsonb NOT NULL,PRIMARY KEY(model,source_id))')
        self.execute('REVOKE ALL ON accounting_migration_quarantine.records FROM PUBLIC')
        report = {'policy_identity': fingerprint(policy), 'records': {}, 'files': [], 'committed': False}
        for model, entries in policy['records'].items():
            table = self.models[model]['table']
            source = sql.Identifier('accounting_migration_source', table)
            ids = sorted(r['source_id'] for r in entries)
            expected = sorted((r['source_id'], r['missing_model'], r['missing_id']) for r in entries)
            if model == 'ir.attachment':
                query = sql.SQL('SELECT id,res_model,res_id FROM {} WHERE id=ANY(%s) ORDER BY id').format(source)
            else:
                query = sql.SQL("SELECT id,'abdin_eplus.pur_trans_h',pth_id FROM {} WHERE id=ANY(%s) ORDER BY id").format(source)
            self.execute(query, [ids])
            if self.cr.fetchall() != expected:
                raise MigrationError(f'Quarantine rows/references differ from approval: {model}')
            for related in sorted({r['missing_model'] for r in entries}):
                if related not in self.models:
                    raise MigrationError(f'Unknown quarantine parent model: {related}')
                parent = sql.Identifier('accounting_migration_source', self.models[related]['table'])
                parent_ids = sorted({r['missing_id'] for r in entries if r['missing_model'] == related})
                self.fail_if(sql.SQL('SELECT count(*) FROM {} WHERE id=ANY(%s)').format(parent), [parent_ids],
                             f'Quarantine parent now exists; review approval: {related}')
            for entry in entries:
                self.execute(sql.SQL('INSERT INTO accounting_migration_quarantine.records '
                    'SELECT %s,id,%s,%s,%s,to_jsonb(s) FROM {} s WHERE id=%s').format(source),
                    [model, entry['missing_model'], entry['missing_id'], self.manifest_id, entry['source_id']])
            # A filtered view preserves the source payload and IDs without copying
            # or deleting the immutable staging rows.
            self.execute(sql.SQL('CREATE VIEW {} AS SELECT s.* FROM {} s WHERE NOT EXISTS '
                '(SELECT 1 FROM accounting_migration_quarantine.records q WHERE q.model={} AND q.source_id=s.id)').format(
                sql.Identifier('accounting_migration_work', table), source, sql.Literal(model)))
            self.working_models.add(model)
            self.quarantine_models.add(model)
            report['records'][model] = dict(count=len(ids), source_ids=ids)
        self.report['quarantine'] = report
        self.copy_quarantined_files()
        save_json(self.stage / 'quarantine-report.json', report)

    def copy_quarantined_files(self):
        if 'ir.attachment' not in self.quarantine_models:
            return
        source_root = Path(loads((self.stage / 'bulk-settings.json').read_text())['source_filestore'])
        root = self.stage / 'quarantine-filestore'
        root.mkdir(mode=0o700, exist_ok=True)
        self.execute("SELECT source_id,payload->>'store_fname',payload->>'checksum',payload->>'file_size' "
                     "FROM accounting_migration_quarantine.records WHERE model='ir.attachment' ORDER BY source_id")
        for source_id, name, checksum, size in self.cr.fetchall():
            if not name:
                continue  # Inline db_datas is retained in the complete payload.
            src, target = safe_attachment_path(source_root, name), safe_attachment_path(root, name)
            status = dict(source_id=source_id, path=name, checksum=checksum, size=size)
            if not src.is_file():
                status['status'] = 'missing_in_source'
            else:
                if (size is not None and src.stat().st_size != int(size)) or (checksum and digest(src, 'sha1') != checksum):
                    raise MigrationError(f'Quarantined attachment checksum/size mismatch: {source_id}')
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                if target.exists() and digest(target, 'sha1') != digest(src, 'sha1'):
                    raise MigrationError(f'Quarantine file collision: {source_id}')
                shutil.copyfile(src, target)
                target.chmod(0o600)
                if digest(target, 'sha1') != digest(src, 'sha1'):
                    raise MigrationError(f'Quarantine file copy verification failed: {source_id}')
                status['status'] = 'preserved'
            self.report['quarantine']['files'].append(status)

    def verify_quarantine(self):
        for model in getattr(self, 'quarantine_models', set()):
            table = self.models[model]['table']
            raw = sql.Identifier('accounting_migration_source', table)
            expected = len(self.quarantine_policy['records'][model])
            self.fail_if(sql.SQL('SELECT count(*) FROM accounting_migration_quarantine.records q '
                'LEFT JOIN {} s ON s.id=q.source_id WHERE q.model=%s AND '
                '(s.id IS NULL OR q.payload IS DISTINCT FROM to_jsonb(s))').format(raw), [model], 'Quarantine payload changed')
            actual = self.count('SELECT count(*) FROM accounting_migration_quarantine.records WHERE model=%s', [model])
            active = self.count(sql.SQL('SELECT count(*) FROM {}').format(self.src(model)))
            if actual != expected or active + actual != self.manifest['tables'][table]['rows']:
                raise MigrationError(f'Active plus quarantined row reconciliation failed: {model}')
            self.fail_if(sql.SQL('SELECT count(*) FROM {} t JOIN accounting_migration_quarantine.records q '
                'ON q.source_id=t.id WHERE q.model=%s').format(self.dst(model)), [model],
                f'Quarantined record leaked into active business data: {model}')
            self.report['tables'][table].update(quarantined_rows=actual, active_source_rows=active)
