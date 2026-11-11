"""Transactional ORM importer with explicit identity mapping and fail-closed verification."""
from adapters import transform, historical_validation_issues
from collections import defaultdict
from decimal import Decimal
import hashlib
from pathlib import Path
import sqlite3
from xml.etree import ElementTree as ET

from psycopg2 import sql
from common import (AUDIT, EXCLUDED, LOOKUPS, TECHNICAL, MigrationError, digest,
                    dumps, loads, save_json, schema_digest)

ATTACHMENT_INTERNAL = {'store_fname', 'db_datas', 'checksum', 'file_size', 'index_content',
                       'access_token', 'public', 'res_name'}
BRANCH_PATHS = {
    'ab_fixed_asset_assets_inventory': 'current_store_id',
    'ab_fixed_asset_inventory_line': 'fixed_asset_header_id.current_store_id',
    'ab_custody_request_header': 'employee_id.department_id.store_id',
    'ab_custody_request_line': 'header_id.employee_id.department_id.store_id',
    'ab_custody_reconciliation_header': 'department_id.store_id',
    'ab_custody_reconciliation_line': 'header_id.department_id.store_id',
    'ab_custody_employee_data': 'employee_id.department_id.store_id',
    'ab_hr_employee': 'department_id.store_id',
    'ab_hr_job_occupied': 'workplace.store_id',
}
RUNTIME_MODELS = {'mail.message', 'mail.mail', 'mail.activity', 'queue.job'}
USER_INTERNAL = {'password', 'groups_id', 'group_ids', 'totp_secret', 'share'}
# Standard framework internals rebuilt by Odoo 19. Custom fields never match this list.
FRAMEWORK_FIELDS = {'message_main_attachment_id', 'message_follower_ids', 'message_ids',
                    'message_partner_ids', 'activity_ids', 'message_channel_ids',
                    'channel_ids', 'notification_type', 'odoobot_state', 'tour_enabled',
                    'partner_share', 'karma', 'karma_tracking_ids', 'res_users_settings_ids', 'signature',
                    'signup_token', 'signup_type', 'signup_expiration'}


class DependencyPending(Exception):
    pass


class Importer:
    def __init__(self, env, stage, args, schema):
        self.env, self.cr, self.stage, self.args = env, env.cr, stage, args
        self.schema = schema
        if not (stage / 'manifest.json').exists():
            raise MigrationError('No exported snapshot; run export with the same --stage first')
        self.manifest = loads((stage / 'manifest.json').read_text())
        self.rules = loads(Path(__file__).with_name('mappings.json').read_text())
        self.cr.execute("SELECT value FROM accounting_migration.checkpoint WHERE name='allow_missing_files'")
        policy = self.cr.fetchone()
        self.cr.execute("SELECT value FROM accounting_migration.checkpoint WHERE name='allow_source_defects'")
        defects_policy = self.cr.fetchone()
        self.allow_source_defects = bool(getattr(args, 'allow_source_defects', False) or (defects_policy and defects_policy[0] == 'true'))
        self.allow_missing_files = bool(getattr(args, 'allow_missing_files', False) or (policy and policy[0] == 'true'))
        if (self.allow_missing_files or self.allow_source_defects) and args.command == 'import' and not args.rehearsal:
            raise MigrationError('--allow-missing-files requires --rehearsal')
        self.missing_files = {int(b.rsplit(':', 1)[1]) for b in self.manifest.get('blockers', [])
                              if b.startswith('Missing attachment file: ir.attachment:')}
        if not self.manifest.get('complete') and not (self.allow_missing_files or self.allow_source_defects) and args.command != 'validate-export':
            raise MigrationError('Export is incomplete; inspect manifest blockers')
        if digest(stage / 'records.sqlite') != self.manifest.get('records_sha256'):
            raise MigrationError('Export checksum changed')
        self.db = sqlite3.connect(f'file:{stage / "records.sqlite"}?mode=ro', uri=True)
        self.cr.execute('SELECT source_db,target_db,snapshot_id,status FROM accounting_migration.run WHERE id')
        run = self.cr.fetchone()
        if not run or run[:2] != (self.manifest['source_db'], args.database):
            raise MigrationError('Destination is not owned by this migration')
        if run[2] and run[2] != self.manifest['snapshot_id']:
            raise MigrationError('Cannot resume with another source snapshot')
        self.bootstrap_admin_id = env['ir.model.data']._xmlid_to_res_id('base.user_admin')
        bootstrap = self.db.execute("SELECT source_id FROM xmlids WHERE model='res.users' AND xmlid='base.user_admin'").fetchone()
        self.bootstrap_admin_source_id = bootstrap[0] if bootstrap else None
        self.excluded_groups = {}
        scope = set(self.manifest.get('required_modules', []))
        if scope:
            for gid, in self.db.execute("SELECT source_id FROM records WHERE model='res.groups'"):
                identities = [x for x, in self.db.execute("SELECT xmlid FROM xmlids WHERE model='res.groups' AND source_id=?", (gid,))]
                if identities and not any(x.split('.', 1)[0] in scope for x in identities):
                    self.excluded_groups[gid] = identities
        save_json(stage / 'excluded-roles.json', {'reason': 'Roles owned exclusively by modules outside the migrated dependency scope',
                  'groups': self.excluded_groups})
        self.retired_fields = {}
        for rid, payload in self.db.execute("SELECT source_id,payload FROM records WHERE model='ir.model.fields'"):
            identities = [x for x, in self.db.execute("SELECT xmlid FROM xmlids WHERE model='ir.model.fields' AND source_id=?", (rid,))]
            if identities and all(x in self.rules.get('retired_report_fields', {}) for x in identities) and not self.xml_matches('ir.model.fields', rid):
                self.retired_fields[rid] = loads(payload)
        save_json(stage / 'retired-report-fields.json', {'reason': 'Unavailable legacy report column metadata; original field and report selections remain in records.sqlite', 'fields': self.retired_fields})
        self.fingerprint = dumps({'mapping': digest(Path(__file__).with_name('mappings.json')),
                             'adapters': digest(Path(__file__).with_name('adapters.py')),
                             'importer': digest(Path(__file__)),
                             'common': digest(Path(__file__).with_name('common.py')),
                             'worker': digest(Path(__file__).with_name('worker.py')),
                             'records': self.manifest['records_sha256'],
                             'schema': schema_digest(self.schema), 'allow_missing_files': self.allow_missing_files, 'allow_source_defects': self.allow_source_defects})
        self.cr.execute("SELECT value FROM accounting_migration.checkpoint WHERE name='fingerprint'")
        prior_fingerprint = self.cr.fetchone()
        self.refresh_engine = False
        if prior_fingerprint and prior_fingerprint[0] != self.fingerprint:
            previous, current = loads(prior_fingerprint[0]), loads(self.fingerprint)
            self.cr.execute('SELECT count(*) FROM accounting_migration.record_map')
            empty = self.cr.fetchone()[0] == 0
            unchanged = all(previous.get(k) == v for k, v in current.items() if k != 'importer')
            if not (getattr(args, 'refresh_engine_before_records', False) and args.command == 'import'
                    and empty and unchanged and run[3] == 'importing'):
                raise MigrationError('Mappings, importer, schema or export changed since import started; use a new target')
            # Each business batch and its record map commit together. An empty map
            # proves no create/link batch committed; never relax this after import.
            self.refresh_engine = True
            self.previous_fingerprint = prior_fingerprint[0]
        self.status = run[3]
        if run[2] is None and args.command == 'verify':
            raise MigrationError('No snapshot has been imported')
        self.cr.execute('SELECT pg_try_advisory_lock(hashtext(%s))', ['accounting_migration'])
        if not self.cr.fetchone()[0]:
            raise MigrationError('Another migration worker owns this target')
        self.blockers = {b for b in self.manifest.get('blockers', []) if not (
            self.allow_missing_files and b.startswith('Missing attachment file: ir.attachment:'))}
        for alias, canonical in self.rules.get('source_aliases', {}).items():
            if canonical not in self.manifest['models']: continue
            missing = self.db.execute(
                "SELECT count(*) FROM records a LEFT JOIN records o ON o.model=? AND o.source_id=json_extract(a.payload,'$.res_id') "
                "WHERE a.model='ir.attachment' AND json_extract(a.payload,'$.res_model')=? AND o.source_id IS NULL", (canonical, alias)).fetchone()[0]
            if not missing:
                self.blockers.discard(f'Unknown related model: {alias}')
        self.orphan_refs = {}
        for model, field, model_field, constant in [
            ('ab_inventory', 'res_id', 'model_ref', None),
            ('ab_inventory_header', 'res_id', 'model_ref', None),
            ('ab_accounting_tracking', 'je_line', None, 'ab_accounting_je_line'),
        ]:
            model_expr = "json_extract(a.payload,'$." + model_field + "')" if model_field else "'" + constant + "'"
            id_expr = "json_extract(a.payload,'$." + field + "')"
            query = ("SELECT a.source_id," + model_expr + "," + id_expr + " FROM records a LEFT JOIN records b ON b.model=" + model_expr +
                     " AND b.source_id=" + id_expr + " WHERE a.model=? AND " + id_expr + ">0 AND b.source_id IS NULL")
            for source_id, related_model, related_id in self.db.execute(query, (model,)):
                self.orphan_refs[(model, source_id, field)] = (related_model, related_id)
        self.orphan_targets = set(self.orphan_refs.values())
        if self.allow_source_defects:
            for related_model, related_id in self.orphan_targets:
                self.blockers.discard(f'Missing/unsupported related record: {related_model}:{related_id}')
        else:
            for model, rid, field in self.orphan_refs:
                self.blockers.add(f'Unresolved source reference: {model}:{rid}.{field}')
        save_json(stage / 'source-defects.json', {'allowed_for_development': self.allow_source_defects,
                  'count': len(self.orphan_refs), 'references': [
                      {'model': m, 'source_id': i, 'field': f, 'missing_model': target[0], 'missing_source_id': target[1]}
                      for (m, i, f), target in self.orphan_refs.items()]})
        missing_report = []
        for rid in sorted(self.missing_files):
            result = self.db.execute("SELECT payload FROM records WHERE model='ir.attachment' AND source_id=?", (rid,)).fetchone()
            if not result: raise MigrationError('Missing-file report references an absent attachment record')
            row = loads(result[0])
            missing_report.append({k: row.get(k) for k in ('id', 'name', 'res_model', 'res_id', 'res_field', 'store_fname', 'checksum', 'file_size')})
        save_json(stage / 'missing-files.json', {'development_only': True, 'allowed': self.allow_missing_files,
                  'count': len(missing_report), 'attachments': missing_report})
        report = stage / 'historical-validation.json'
        prior_validation = loads(report.read_text()) if report.exists() else {}
        self.historical_issues = prior_validation.get('records', []) if prior_validation.get('fingerprint') == self.fingerprint else []
        if run[2] and args.command in ('verify', 'activate-dev') and prior_validation.get('fingerprint') != self.fingerprint:
            raise MigrationError('Historical validation report is missing or changed; rerun import validation')
        self.cache = {}
        self.skipped_notifications = 0
        self.install_suppression()

    def install_suppression(self):
        # Suppress precisely the known notification gateway; all other networking fails closed.
        def no_telegram(records, *args, **kwargs):
            self.skipped_notifications += 1
            return False
        if hasattr(self.env['res.users'], '_notify_security_setting_update'):
            setattr(type(self.env['res.users']), '_notify_security_setting_update', no_telegram)
        for name in self.env.registry:
            model = self.env[name]
            if hasattr(model, 'send_by_bot'):
                setattr(type(model), 'send_by_bot', no_telegram)

    def target_model(self, model):
        model = self.rules.get('source_aliases', {}).get(model, model)
        return self.rules['models'].get(model, model)

    def mapped(self, model, source_id, pending=False):
        model = self.rules.get('source_aliases', {}).get(model, model)
        if not source_id: return False
        key = (model, int(source_id))
        if key not in self.cache:
            self.cr.execute('SELECT target_id FROM accounting_migration.record_map WHERE model=%s AND source_id=%s', key)
            r = self.cr.fetchone()
            if not r:
                if pending: raise DependencyPending(f'{model}:{source_id}')
                raise MigrationError(f'Unresolved record: {model}:{source_id}')
            if len(self.cache) > 50000: self.cache.clear()
            self.cache[key] = r[0]
        return self.cache[key]

    def reference_id(self, model, row, field, related_model, pending=False):
        if (model, row['id'], field) in getattr(self, 'orphan_refs', {}):
            if not self.allow_source_defects:
                raise MigrationError(f'Unresolved source reference: {model}:{row["id"]}.{field}')
            return 0
        return self.mapped(related_model, row.get(field), pending=pending)

    def register(self, model, source_id, target_id, phase):
        self.cr.execute('INSERT INTO accounting_migration.record_map VALUES (%s,%s,%s,%s,%s) '
                        'ON CONFLICT (model,source_id) DO UPDATE SET phase=EXCLUDED.phase',
                        (model, source_id, self.target_model(model), target_id, phase))
        self.cache[(model, source_id)] = target_id

    def xml_matches(self, model, rid):
        if model in ('resource.calendar.attendance', 'resource.calendar.leaves'):
            return None  # Calendar initializer schedules are replaced, never reused as source rows.
        result = set()
        identities = [x for x, in self.db.execute('SELECT xmlid FROM xmlids WHERE model=? AND source_id=?', (model, rid))]
        if model == 'res.groups' and not identities:
            payload = self.db.execute('SELECT payload FROM records WHERE model=? AND source_id=?', (model, rid)).fetchone()
            name = loads(payload[0]).get('name') if payload else None
            explicit = self.rules.get('unidentified_groups', {}).get(name)
            if explicit:
                matches = self.db.execute("SELECT count(*) FROM records WHERE model='res.groups' AND json_extract(payload,'$.name')=?", (name,)).fetchone()[0]
                if matches != 1: raise MigrationError('Ambiguous manually created source security group')
                identities = [explicit]
        for xmlid in identities:
            xmlid = self.rules['xmlids'].get(xmlid, xmlid)
            module, name = xmlid.split('.', 1)
            r = self.env['ir.model.data'].search([('module', '=', module), ('name', '=', name)], limit=1)
            if r and r.model == self.target_model(model) and self.env[r.model].browse(r.res_id).exists():
                result.add(r.res_id)
        if len(result) > 1:
            raise MigrationError(f'Conflicting XML identities: {model}:{rid}')
        return next(iter(result), None)

    def ignored(self, model, fn, sf=None):
        if fn in TECHNICAL or fn in AUDIT or fn == '_m2m': return True
        if fn in FRAMEWORK_FIELDS: return True
        if sf and sf.get('relation') in EXCLUDED: return True
        if model == 'res.users' and fn in USER_INTERNAL: return True
        if model == 'ir.attachment' and fn in ATTACHMENT_INTERNAL: return True
        return bool(self.rules['ignore_fields'].get(model, {}).get(fn))

    def check_schema(self):
        """Inspect all data before the first business write; include field-level reasons."""
        units = {rid: loads(payload) for rid, payload in self.db.execute("SELECT source_id,payload FROM records WHERE model='ab_uom'")}
        taxes = {rid: loads(payload) for rid, payload in self.db.execute("SELECT source_id,payload FROM records WHERE model='ab_taxes'")}
        self.historical_issues = []
        if self.bootstrap_admin_source_id:
            admin = loads(self.db.execute("SELECT payload FROM records WHERE model='res.users' AND source_id=?", (self.bootstrap_admin_source_id,)).fetchone()[0])
            system_role = self.db.execute("SELECT source_id FROM xmlids WHERE model='res.groups' AND xmlid='base.group_system'").fetchone()
            membership = system_role and self.db.execute('SELECT 1 FROM groups WHERE user_id=? AND group_id=?', (self.bootstrap_admin_source_id, system_role[0])).fetchone()
            if not admin.get('active') or not membership:
                self.blockers.add('Source bootstrap administrator must be active and retain the Settings role for this migration policy')
        for model, in self.db.execute('SELECT DISTINCT model FROM records'):
            print(f'Validating exported model: {model}', flush=True)
            target = self.schema.get(self.target_model(model))
            if model in LOOKUPS:
                for rid, in self.db.execute('SELECT source_id FROM records WHERE model=?', (model,)):
                    if model == 'res.groups' and rid in self.excluded_groups: continue
                    if model == 'ir.model.fields' and rid in self.retired_fields: continue
                    if not self.xml_matches(model, rid): self.blockers.add(f'Unmapped metadata/role: {model}:{rid}')
                continue
            if not target:
                self.blockers.add(f'Missing destination model: {model}'); continue
            src = self.manifest['models'][model]
            for rid, payload in self.db.execute('SELECT source_id,payload FROM records WHERE model=?', (model,)):
                row = transform(model, loads(payload))
                if model in ('ab_product', 'ab_product_source', 'ab_purchase_header'):
                    issues = historical_validation_issues(model, row, units, taxes)
                    if issues:
                        self.historical_issues.append({'model': model, 'source_id': rid, 'issues': issues})
                        if not self.allow_source_defects:
                            self.blockers.add(f'Historical values require development preservation: {model}:{rid}')
                for fn, value in {**row, **row.get('_m2m', {})}.items():
                    sf = src['fields'].get(fn, {})
                    if self.ignored(model, fn, sf): continue
                    if sf.get('relation') == 'res.groups' and any(g in self.excluded_groups for g in (value if isinstance(value, list) else [value])):
                        self.blockers.add(f'Business field references out-of-scope security group: {model}.{fn}')
                    if sf.get('ttype') == 'many2one_reference' and value and fn not in self.rules['polymorphic'].get(model, {}):
                        self.blockers.add(f'Missing polymorphic mapping: {model}.{fn}')
                    tn = self.rules['fields'].get(model, {}).get(fn, fn)
                    tf = target['fields'].get(tn)
                    if not tf:
                        if value not in (None, False, '', [], {}): self.blockers.add(f'Unmapped populated field: {model}.{fn}')
                        continue
                    if sf.get('ttype') != tf['type'] and {sf.get('ttype'), tf['type']} != {'char', 'text'}:
                        if value not in (None, False, '', []): self.blockers.add(f'Incompatible field type: {model}.{fn}')
                    if tf['type'] == 'selection' and value and tf.get('selection') is not None:
                        mapped = self.rules['selections'].get(model, {}).get(fn, {}).get(str(value), value)
                        if model in ('res.users', 'res.partner') and fn == 'lang':
                            if not self.env['res.lang'].with_context(active_test=False).search([('code', '=', mapped)], limit=1):
                                self.blockers.add(f'Unsupported language: {mapped}')
                        elif mapped not in tf['selection']: self.blockers.add(f'Unmapped selection: {model}.{fn}={value}')
                if model == 'res.users' and row.get('password'):
                    scheme = self.env['res.users']._crypt_context().identify(row['password'])
                    if not scheme or scheme == 'plaintext': self.blockers.add(f'Unsupported password hash: res.users:{rid}')
            for fn, f in target['fields'].items():
                oldnames = {self.rules['fields'].get(model, {}).get(k, k) for k in src['fields']}
                if f['required'] and not f['compute'] and fn not in oldnames:
                    default = self.env[self.target_model(model)].default_get([fn]).get(fn)
                    if default is None or default is False: self.blockers.add(f'New required field without default: {model}.{fn}')
        for rid, payload in self.db.execute("SELECT source_id,payload FROM records WHERE model='ab_store'"):
            row = loads(payload)
            if row.get('user_id') and not self.db.execute(
                "SELECT 1 FROM records WHERE model='ab_hr_department' AND json_extract(payload,'$.store_id')=? AND json_extract(payload,'$.user_id')=? LIMIT 1",
                (rid, row['user_id'])).fetchone():
                self.blockers.add(f'Store user is not preserved by exported HR department: ab_store:{rid}')
        for rid, sha, size in self.db.execute('SELECT source_id,sha256,size FROM attachments'):
            path = self.stage / 'blobs' / str(rid)
            if not path.is_file() or path.stat().st_size != size or digest(path) != sha:
                self.blockers.add(f'Attachment checksum failure: ir.attachment:{rid}')
        save_json(self.stage / 'historical-validation.json', {'fingerprint': self.fingerprint, 'allowed_for_development': self.allow_source_defects, 'count': len(self.historical_issues), 'records': self.historical_issues})
        save_json(self.stage / 'preflight.json', {'blockers': sorted(self.blockers)})
        if self.blockers: raise MigrationError(f'Preflight has {len(self.blockers)} blockers; see preflight.json')

    def relation_ids(self, model, field, related, ids):
        retired = getattr(self, 'retired_fields', {})
        if related != 'ir.model.fields' or not retired: return ids
        if (model, field) in {('ab_accounting_account_statement', 'report_field_ids'), ('ab_accounting_recon_header', 'report_field_ids')}:
            return [rid for rid in ids if rid not in retired]
        if set(ids) & retired.keys():
            raise MigrationError(f'Retired metadata used outside report columns: {model}.{field}')
        return ids

    def seed(self):
        # Fresh target identities are a small set; use the SQLite unique XML-ID
        # index instead of making millions of ORM searches for __export__ IDs.
        self.cr.execute('SELECT module,name FROM ir_model_data')
        candidates = {module + '.' + name for module, name in self.cr.fetchall()}
        candidates.update(self.rules['xmlids'])
        pairs = set()
        candidates = sorted(candidates)
        for offset in range(0, len(candidates), 500):
            chunk = candidates[offset:offset + 500]
            placeholders = ','.join('?' for _ in chunk)
            pairs.update(self.db.execute('SELECT model,source_id FROM xmlids WHERE xmlid IN (' + placeholders + ')', chunk))
        placeholders = ','.join('?' for _ in LOOKUPS)
        pairs.update(self.db.execute('SELECT model,source_id FROM records WHERE model IN (' + placeholders + ')', sorted(LOOKUPS)))
        for model, rid in sorted(pairs):
            if model == 'res.groups' and rid in self.excluded_groups: continue
            if model == 'ir.model.fields' and rid in self.retired_fields: continue
            target = self.xml_matches(model, rid)
            if target:
                self.cr.execute('SELECT 1 FROM accounting_migration.record_map WHERE model=%s AND source_id=%s', (model, rid))
                if self.cr.fetchone(): continue
                self.register(model, rid, target, 'done' if model in LOOKUPS else 'seeded')
            elif model in LOOKUPS:
                raise MigrationError(f'Unmapped lookup: {model}:{rid}')
        self.cr.commit()

    def values(self, model, row, final=False):
        row = transform(model, row)
        target = self.schema[self.target_model(model)]
        source = self.manifest['models'][model]
        vals = {}
        polymorphic = self.rules['polymorphic'].get(model, {})
        integer_links = self.rules.get('integer_links', {}).get(model, {})
        for fn, value in row.items():
            sf = source['fields'].get(fn, {})
            if self.ignored(model, fn, sf): continue
            tn = self.rules['fields'].get(model, {}).get(fn, fn)
            tf = target['fields'].get(tn)
            if not tf or (tf['compute'] and tf['readonly']) or tf['related']: continue
            if fn in polymorphic:
                if value and (final or model in ('ab_inventory', 'ab_inventory_header')):
                    vals[tn] = self.reference_id(model, row, fn, row[polymorphic[fn]], pending=not final)
                continue
            if fn in polymorphic.values() and value:
                vals[tn] = self.target_model(value)
                continue
            if fn in integer_links:
                if value and (final or model == 'ab_inventory'):
                    vals[tn] = self.reference_id(model, row, fn, integer_links[fn], pending=not final)
                continue
            if tf['type'] == 'many2one':
                if not value: vals[tn] = False
                elif tf['required'] or final:
                    vals[tn] = self.mapped(sf['relation'], value, pending=not final)
                # Optional links are deferred, preventing defaults from referring to unrelated seeded records.
                else:
                    try: vals[tn] = self.mapped(sf['relation'], value, pending=True)
                    except DependencyPending: vals[tn] = False
            elif tf['type'] == 'reference':
                if final and value:
                    rm, ri = value.rsplit(',', 1)
                    vals[tn] = f'{self.target_model(rm)},{self.mapped(rm, int(ri))}'
            elif tf['type'] in ('one2many', 'many2many'): continue
            elif tf['type'] == 'binary':
                vals[tn] = value or False  # Odoo 15 Binary columns already contain base64
            elif tf['type'] == 'selection':
                vals[tn] = self.rules['selections'].get(model, {}).get(fn, {}).get(str(value), value) or False
            else:
                vals[tn] = False if value is None else float(value) if isinstance(value, Decimal) else value
        for fn, values in row.get('_m2m', {}).items():
            sf = source['fields'][fn]
            if self.ignored(model, fn, sf): continue
            tn = self.rules['fields'].get(model, {}).get(fn, fn)
            tf = target['fields'].get(tn)
            if tf and not tf['related'] and not (tf['compute'] and tf['readonly']):
                try:
                    vals[tn] = [(6, 0, [self.mapped(sf['relation'], rid, pending=not final) for rid in self.relation_ids(model, fn, sf['relation'], values)])]
                except DependencyPending:
                    if tf['required']: raise
        if final and model == 'ab_accounting_tracking' and vals.get('field_diff_json'):
            diff = loads(vals['field_diff_json'])
            for changes in diff.values():
                if isinstance(changes, list):
                    for item in changes:
                        if isinstance(item, dict) and item.get('user_id'):
                            item['user_id'] = self.mapped('res.users', item['user_id'])
            vals['field_diff_json'] = dumps(diff)
        if model in ('ab_inventory', 'ab_inventory_header') and row.get('header_ref'):
            import re
            prefix = re.fullmatch(r'(P|N|O)([0-9]+)', row['header_ref'])
            if not prefix:
                raise MigrationError(f'Unsupported inventory header reference: {model}:{row["id"]}')
            header_model = {'P': 'ab_purchase_header', 'N': 'ab_purchase_notice_header', 'O': 'ab_purchase_ob_header'}[prefix[1]]
            if (header_model, int(prefix[2])) in getattr(self, 'orphan_targets', set()):
                if not self.allow_source_defects: raise MigrationError('Unresolved inventory header reference')
                vals['header_ref'] = 'LEGACY:' + row['header_ref']
                vals['migration_reference_missing'] = True
            else:
                vals['header_ref'] = prefix[1] + str(self.mapped(header_model, int(prefix[2]), pending=not final))
        if model in ('ab_inventory', 'ab_inventory_header', 'ab_accounting_tracking'):
            if vals.get('migration_reference_missing') or any((model, row['id'], f) in getattr(self, 'orphan_refs', {}) for f in ('res_id', 'je_line')):
                vals['migration_reference_missing'] = True
                vals['migration_source_references'] = dumps({f: row.get(f) for f in ('model_ref', 'res_id', 'header_id', 'header_ref', 'je_line') if f in row})
        if model == 'resource.calendar' and not final:
            if row.get('company_id'):
                vals['company_id'] = self.mapped('res.company', row['company_id'], pending=True)
            vals['attendance_ids'] = [(5, 0, 0)]
            vals['leave_ids'] = [(5, 0, 0)]
        if model == 'res.users':
            # Odoo requires one active Settings administrator while importing roles.
            # Database connections remain restricted throughout the import.
            vals['active'] = row['id'] == getattr(self, 'bootstrap_admin_source_id', None)
            if row.get('company_id'):
                company = self.mapped('res.company', row['company_id'], pending=not final)
                vals['company_id'] = company
                if not final: vals['company_ids'] = [(6, 0, [company])]
        if model == 'ir.attachment':
            if row.get('res_model') and row.get('res_id'):
                vals['res_id'] = self.mapped(row['res_model'], row['res_id'], pending=not final)
            if row.get('type') != 'url':
                if row['id'] in getattr(self, 'missing_files', set()):
                    if not self.allow_missing_files: raise MigrationError('Missing file was not authorized for development')
                    vals.update(raw=False, migration_file_missing=True,
                                migration_source_path=row.get('store_fname'),
                                migration_source_checksum=row.get('checksum'),
                                migration_source_size=row.get('file_size') or 0)
                else:
                    vals['raw'] = (self.stage / 'blobs' / str(row['id'])).read_bytes()
            vals['public'] = False
            if row.get('res_field') and row.get('res_model'):
                vals['res_field'] = self.rules['fields'].get(row['res_model'], {}).get(row['res_field'], row['res_field'])
            vals['res_model'] = self.target_model(row['res_model']) if row.get('res_model') else False
        return vals

    def changed_values(self, record, values):
        result = {}
        for name, value in values.items():
            field = record._fields[name]
            actual = record[name]
            if field.type == 'many2one': actual = actual.id
            elif field.type == 'many2many' and value and value[0][0] == 6:
                if set(actual.ids) != set(value[0][2]): result[name] = value
                continue
            elif field.type == 'one2many':
                result[name] = value
                continue
            elif field.type in ('date', 'datetime'):
                actual, value = str(actual or ''), str(value or '')
            elif field.type == 'binary':
                actual = actual.encode() if isinstance(actual, str) else bytes(actual or b'')
                value = value.encode() if isinstance(value, str) else bytes(value or b'')
            if actual != value: result[name] = values[name]
        return result

    def model_order(self):
        available = set(self.manifest['counts']) - LOOKUPS
        result, visiting = [], set()
        def visit(model):
            if model in result or model in visiting or model not in available: return
            visiting.add(model)
            fields = self.manifest['models'][model]['fields']
            for fn, tf in self.schema[self.target_model(model)]['fields'].items():
                if tf['required'] and not tf['related'] and tf['type'] in ('many2one', 'many2many'):
                    visit(fields.get(fn, {}).get('relation'))
            extra = {
                'ab_product': ['ab_product_tag'],
                'ab_inventory': ['ab_product_source', 'ab_inventory_header', 'ab_purchase_line', 'ab_purchase_notice_line', 'ab_purchase_ob_line'],
                'ab_inventory_header': ['ab_purchase_header', 'ab_purchase_notice_header', 'ab_purchase_ob_header'],
                'resource.calendar': ['res.company'],
            }
            for related in extra.get(model, []): visit(related)
            visiting.remove(model)
            result.append(model)
        for model in ['res.currency', 'res.country', 'res.partner', 'res.company', 'res.users'] + sorted(available): visit(model)
        return result

    def prime_mappings(self, model, rows):
        if len(self.cache) > 50000: self.cache.clear()
        refs = defaultdict(set)
        refs[model].update(row['id'] for row in rows)
        fields = self.manifest['models'][model]['fields']
        links = {f: sf['relation'] for f, sf in fields.items() if sf.get('ttype') == 'many2one' and sf.get('relation') not in EXCLUDED}
        for row in rows:
            for field, related in links.items():
                if row.get(field): refs[related].add(row[field])
            for field in ('create_uid', 'write_uid'):
                if row.get(field): refs['res.users'].add(row[field])
            for field, ids in row.get('_m2m', {}).items():
                if not self.ignored(model, field, fields.get(field)):
                    refs[fields[field]['relation']].update(ids)
            for field, related in self.rules.get('integer_links', {}).get(model, {}).items():
                if row.get(field): refs[related].add(row[field])
            for field, model_field in self.rules['polymorphic'].get(model, {}).items():
                if row.get(field) and row.get(model_field): refs[row[model_field]].add(row[field])
        for related, ids in refs.items():
            related = self.rules.get('source_aliases', {}).get(related, related)
            missing = [rid for rid in ids if (related, rid) not in self.cache]
            if missing:
                self.cr.execute('SELECT source_id,target_id FROM accounting_migration.record_map WHERE model=%s AND source_id=ANY(%s)', [related, missing])
                self.cache.update(((related, rid), tid) for rid, tid in self.cr.fetchall())

    def verification_records(self):
        for model in self.model_order():
            cursor = self.db.execute('SELECT source_id,payload FROM records WHERE model=? ORDER BY source_id', (model,))
            while batch := cursor.fetchmany(max(self.args.batch_size, 500)):
                rows = [transform(model, loads(payload)) for _, payload in batch]
                self.env.invalidate_all()
                self.prime_mappings(model, rows)
                ids = [self.cache[(model, row['id'])] for row in rows if (model, row['id']) in self.cache]
                records = self.env[self.target_model(model)].browse(ids).exists()
                by_id = {record.id: record for record in records}
                for row in rows:
                    tid = self.cache.get((model, row['id']))
                    yield model, row['id'], row, by_id.get(tid)

    def phase(self, final=False):
        from psycopg2.extras import execute_values
        count, unresolved = 0, []
        self.pending_total = 0
        for model in self.model_order():
            cursor = self.db.execute('SELECT source_id,payload FROM records WHERE model=? ORDER BY source_id', (model,))
            model_count = 0
            while batch := cursor.fetchmany(self.args.batch_size):
                self.cr.execute('SELECT source_id,target_id,phase FROM accounting_migration.record_map WHERE model=%s AND source_id=ANY(%s)',
                                [model, [r[0] for r in batch]])
                states = {sid: (tid, phase) for sid, tid, phase in self.cr.fetchall()}
                target = self.env[self.target_model(model)]
                if self.allow_source_defects and model in ('ab_product', 'ab_product_source', 'ab_purchase_header'):
                    # Preserve audited legacy imports through the addon's existing
                    # external-import validation context, never by changing quantities/prices.
                    target = target.with_context(eplus_replication=True)
                if model in ('res.users', 'res.partner'): target = target.with_context(active_test=True)
                records = target.browse([state[0] for state in states.values()])
                record_by_id = {rec.id: rec for rec in records}
                creates, prepared = [], []
                pending_rows = {rid: transform(model, loads(payload)) for rid, payload in batch if not (states.get(rid) and (states[rid][1] == 'done' or (not final and states[rid][1] == 'created')))}
                self.prime_mappings(model, list(pending_rows.values()))
                for rid, payload in batch:
                    state = states.get(rid)
                    if state and (state[1] == 'done' or (not final and state[1] == 'created')): continue
                    if final and not state: raise MigrationError(f'Missing creation checkpoint: {model}:{rid}')
                    row = pending_rows[rid]
                    try: vals = self.values(model, row, final)
                    except DependencyPending:
                        self.pending_total += 1
                        if len(unresolved) < 1000: unresolved.append((model, rid))
                        continue
                    prepared.append((rid, row, vals, state))
                try:
                    mappings = []
                    for rid, row, vals, state in prepared:
                        if model == 'res.users' and state and state[0] == self.env.uid: vals.pop('active', None)
                        if state:
                            record = record_by_id[state[0]]
                            changed = self.changed_values(record, vals)
                            if changed: record.write(changed)
                        elif model == 'ir.attachment' and vals.get('res_field') and vals.get('res_id'):
                            generated = target.search([('res_model', '=', vals['res_model']), ('res_id', '=', vals['res_id']), ('res_field', '=', vals['res_field'])])
                            if len(generated) > 1: raise MigrationError('Ambiguous binary field attachment')
                            if generated:
                                self.cr.execute('SELECT 1 FROM accounting_migration.record_map WHERE target_model=%s AND target_id=%s', [model, generated.id])
                                if self.cr.fetchone(): raise MigrationError('Duplicate source binary field attachment')
                                record = generated
                                record.write(vals)
                            else: record = target.create(vals)
                        elif model not in ('res.users', 'ir.attachment'):
                            creates.append((rid, vals))
                            continue
                        else: record = target.create(vals)
                        if model == 'res.users' and row.get('password'): record._set_encrypted_password(record.id, row['password'])
                        mappings.append((model, rid, self.target_model(model), record.id, 'done' if final else 'created'))
                    if creates:
                        created = target.create([vals for _, vals in creates])
                        if len(created) != len(creates): raise MigrationError('ORM create returned an unexpected record count')
                        mappings.extend((model, rid, self.target_model(model), record.id, 'created') for (rid, _), record in zip(creates, created))
                    if mappings:
                        execute_values(self.cr, 'INSERT INTO accounting_migration.record_map VALUES %s ON CONFLICT (model,source_id) DO UPDATE SET phase=EXCLUDED.phase', mappings)
                        for m, rid, _, tid, _ in mappings: self.cache[(m, rid)] = tid
                        if len(self.cache) > 50000: self.cache.clear()
                        self.env.flush_all(); self.cr.commit(); self.env.invalidate_all()
                        count += len(mappings); model_count += len(mappings)
                        if model_count % 10000 < len(mappings):
                            print(f'{"Linked" if final else "Created"} {model}: {model_count}', flush=True)
                except Exception as exc:
                    self.cr.rollback(); self.cache.clear()
                    from odoo.exceptions import UserError
                    import traceback
                    diag = getattr(exc, 'diag', None)
                    save_json(self.stage / 'failure.json', {'model': model, 'source_id': rid if prepared and not creates else None,
                        'batch_source_ids': [r[0] for r in prepared], 'phase': 'links' if final else 'create', 'exception': type(exc).__name__,
                        'message': str(exc) if isinstance(exc, UserError) else None,
                        'constraint': getattr(diag, 'constraint_name', None), 'column': getattr(diag, 'column_name', None),
                        'frames': [{'file': frame.filename, 'function': frame.name, 'line': frame.lineno} for frame in traceback.extract_tb(exc.__traceback__)]})
                    raise MigrationError(f'Import batch failed for {model} ({type(exc).__name__}); batch rolled back') from None
            print(f'{"Linked" if final else "Created"} {model}: {model_count}; pending total {self.pending_total}', flush=True)
        self.env.flush_all(); self.cr.commit(); self.env.invalidate_all()
        return count, unresolved

    def apply_security(self):
        root = ET.Element('odoo')
        data = ET.SubElement(root, 'data')
        # XML imports own security changes; no Python group membership writes.
        grouped = defaultdict(list)
        for uid, gid in self.db.execute('SELECT user_id,group_id FROM groups'):
            if gid not in self.excluded_groups:
                grouped[uid].append(self.mapped('res.groups', gid))
            else:
                grouped.setdefault(uid, [])
        for uid, gids in grouped.items():
            target_id = self.mapped('res.users', uid)
            xid = f'user_{uid}'
            md = self.env['ir.model.data'].search([('module', '=', 'accounting_migration'), ('name', '=', xid)], limit=1)
            if not md:
                self.env['ir.model.data'].create({'module': 'accounting_migration', 'name': xid,
                                               'model': 'res.users', 'res_id': target_id, 'noupdate': True})
            rec = ET.SubElement(data, 'record', {'id': xid, 'model': 'res.users'})
            ET.SubElement(rec, 'field', {'name': 'group_ids', 'eval': repr([(6, 0, sorted(set(gids)))])})
        path = self.stage / 'security'
        path.mkdir(mode=0o700, exist_ok=True)
        content = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        (path / 'users.xml').write_bytes(content)
        from odoo.tools.convert import convert_xml_import
        with open(path / 'users.xml', 'rb') as xmlfile:
            convert_xml_import(self.env, 'accounting_migration', xmlfile, mode='init', noupdate=True)
        self.cr.commit()

    def activate_languages(self):
        languages = {r[0] for r in self.db.execute('SELECT DISTINCT lang FROM translations')}
        for model, payload in self.db.execute("SELECT model,payload FROM records WHERE model IN ('res.users','res.partner')"):
            lang = loads(payload).get('lang')
            if lang:
                languages.add(self.rules['selections'].get(model, {}).get('lang', {}).get(lang, lang))
        for lang in sorted(languages):
            self.env['res.lang']._activate_lang(lang)
        self.cr.commit()

    def apply_translations(self):
        for model, rid, field, lang, value in self.db.execute('SELECT model,source_id,field,lang,value FROM translations'):
            tm = self.target_model(model)
            tf = self.rules['fields'].get(model, {}).get(field, field)
            if self.ignored(model, field): continue
            if tf not in self.env[tm]._fields or not self.env[tm]._fields[tf].translate:
                raise MigrationError(f'Unsupported translated field: {model}.{field}')
            if not self.env['res.lang'].search([('code', '=', lang), ('active', '=', True)], limit=1):
                self.env['res.lang']._activate_lang(lang)
            self.env[tm].browse(self.mapped(model, rid)).with_context(lang=lang).write({tf: value})
        self.cr.commit()

    def restore_audit(self):
        # Only log-access metadata is updated with SQL; business rows use the ORM.
        from psycopg2.extras import execute_values
        self.env.flush_all()
        for model in self.model_order():
            fields = sorted(AUDIT & set(self.schema[self.target_model(model)]['fields']))
            if not fields: continue
            cursor = self.db.execute('SELECT source_id,payload FROM records WHERE model=? ORDER BY source_id', (model,))
            while batch := cursor.fetchmany(max(self.args.batch_size, 1000)):
                self.cr.execute('SELECT source_id,target_id FROM accounting_migration.record_map WHERE model=%s AND source_id=ANY(%s)',
                                [model, [r[0] for r in batch]])
                identities = dict(self.cr.fetchall())
                updates = []
                for rid, payload in batch:
                    row = loads(payload)
                    if not all(f in row for f in fields): continue
                    values = [identities[rid]]
                    for field in fields:
                        value = row[field]
                        values.append(self.mapped('res.users', value) if field.endswith('_uid') and value else value)
                    updates.append(tuple(values))
                if updates:
                    statement = sql.SQL('UPDATE {} t SET {} FROM (VALUES %s) AS v({}) WHERE t.id=v.id').format(
                        sql.Identifier(self.schema[self.target_model(model)]['table']),
                        sql.SQL(',').join(sql.SQL('{}=v.{}::{}').format(sql.Identifier(f), sql.Identifier(f),
                            sql.SQL('integer' if f.endswith('_uid') else 'timestamp')) for f in fields),
                        sql.SQL(',').join(map(sql.Identifier, ['id'] + fields))).as_string(self.cr.connection)
                    execute_values(self.cr, statement, updates, page_size=1000)
                    self.cr.commit()
            print(f'Restored audit metadata: {model}', flush=True)
        self.env.invalidate_all()

    def backup(self):
        from common import ensure_backup
        ensure_backup(self.args.config, self.args.database, self.stage)

    def run(self):
        if self.status == 'development_active':
            raise MigrationError('Migration is already activated; use verify or a new target/stage')
        if not self.manifest['frozen'] and not self.args.rehearsal:
            raise MigrationError('Cutover import requires --source-frozen at export, or explicit --rehearsal')
        self.check_schema()
        self.backup()
        fingerprint = self.fingerprint
        self.cr.execute("SELECT value FROM accounting_migration.checkpoint WHERE name='fingerprint'")
        prior = self.cr.fetchone()
        if prior and prior[0] != fingerprint:
            if not self.refresh_engine:
                raise MigrationError('Mappings, schema or export changed since import started; use a new target')
            self.cr.execute('SELECT count(*) FROM accounting_migration.record_map')
            if self.cr.fetchone()[0]: raise MigrationError('Cannot refresh importer after records have committed')
            save_json(self.stage / 'engine-refresh.json', {'reason': 'Importer optimization before any committed business batch',
                      'previous': loads(prior[0]), 'current': loads(fingerprint), 'committed_mappings': 0})
            self.cr.execute("UPDATE accounting_migration.checkpoint SET value=%s WHERE name='fingerprint'", [fingerprint])
        self.cr.execute("INSERT INTO accounting_migration.checkpoint VALUES ('fingerprint',%s) ON CONFLICT DO NOTHING", [fingerprint])
        self.cr.execute("INSERT INTO accounting_migration.checkpoint VALUES ('allow_missing_files',%s) ON CONFLICT DO NOTHING",
                        ['true' if self.allow_missing_files else 'false'])
        self.cr.execute("INSERT INTO accounting_migration.checkpoint VALUES ('allow_source_defects',%s) ON CONFLICT DO NOTHING",
                        ['true' if self.allow_source_defects else 'false'])
        self.cr.execute('CREATE TABLE IF NOT EXISTS accounting_migration.baseline(model text, id bigint, PRIMARY KEY(model,id))')
        if not prior:
            for model in set(self.manifest['counts']) | (RUNTIME_MODELS & set(self.schema)):
                if model in LOOKUPS: continue
                tm = self.target_model(model)
                self.cr.execute(sql.SQL('INSERT INTO accounting_migration.baseline SELECT %s,id FROM {}').format(
                    sql.Identifier(self.schema[tm]['table'])), [tm])
        self.cr.execute("UPDATE accounting_migration.run SET snapshot_id=%s,status='importing' WHERE id", [self.manifest['snapshot_id']])
        self.cr.commit()
        self.activate_languages()
        self.seed()
        while True:
            done, pending = self.phase()
            if not pending: break
            if not done:
                save_json(self.stage / 'dependency-blockers.json', {'records': pending[:1000], 'total': self.pending_total})
                raise MigrationError('Unresolved required dependency cycle; see dependency-blockers.json')
        self.phase(final=True)
        (self.stage / 'failure.json').unlink(missing_ok=True)
        (self.stage / 'dependency-blockers.json').unlink(missing_ok=True)
        self.apply_security()
        self.apply_translations()
        self.restore_audit()
        self.cr.execute("UPDATE accounting_migration.run SET status='imported' WHERE id")
        self.cr.commit()
        self.verify()

    def verify(self):
        problems = []
        counts = {}
        for model, expected in self.manifest['counts'].items():
            self.cr.execute("SELECT count(*) FROM accounting_migration.record_map WHERE model=%s AND phase='done'", [model])
            actual = self.cr.fetchone()[0]
            excluded = len(self.excluded_groups) if model == 'res.groups' else len(self.retired_fields) if model == 'ir.model.fields' else 0
            counts[model] = {'source': expected, 'mapped': actual, 'excluded_out_of_scope': excluded}
            if actual != expected - excluded: problems.append(f'Incomplete mapping: {model}')
        for model in set(self.manifest['roots']) | (RUNTIME_MODELS & set(self.schema)):
            if model in LOOKUPS: continue
            tm = self.target_model(model)
            self.cr.execute(sql.SQL('SELECT count(*) FROM {} t LEFT JOIN accounting_migration.record_map m ON m.target_model=%s AND m.target_id=t.id '
                                    'LEFT JOIN accounting_migration.baseline b ON b.model=%s AND b.id=t.id WHERE m.target_id IS NULL AND b.id IS NULL').format(
                                    sql.Identifier(self.schema[tm]['table'])), [tm, tm])
            if self.cr.fetchone()[0]: problems.append(f'Unmapped records created by import side effects: {model}')
        for model, rid, field, lang, value in self.db.execute('SELECT model,source_id,field,lang,value FROM translations'):
            if self.ignored(model, field): continue
            tf = self.rules['fields'].get(model, {}).get(field, field)
            try:
                record = self.env[self.target_model(model)].browse(self.mapped(model, rid))
                if record.with_context(lang=lang)[tf] != value:
                    problems.append(f'Translation mismatch: {model}:{rid}.{field} ({lang})')
            except (MigrationError, KeyError): problems.append(f'Unresolved translation: {model}:{rid}.{field}')
        # Compare source values and links against their destination records, including computed financial values.
        totals = defaultdict(lambda: [Decimal(0), Decimal(0)])
        for model, rid, row, rec in self.verification_records():
            if rec is None:
                problems.append(f'Missing destination record or mapping: {model}:{rid}')
                continue
            tid = rec.id
            for fn, value in row.items():
                sf = self.manifest['models'][model]['fields'].get(fn, {})
                if self.ignored(model, fn, sf) or fn in self.rules['polymorphic'].get(model, {}) or fn in self.rules.get('integer_links', {}).get(model, {}): continue
                tn = self.rules['fields'].get(model, {}).get(fn, fn)
                tf = self.schema[self.target_model(model)]['fields'].get(tn)
                if not tf or tf['type'] in ('one2many','many2many') or tf['related']: continue
                if model == 'res.users' and fn == 'active' and self.status != 'development_active': continue  # users deliberately remain inactive pending release
                actual = rec.number_next_actual if model in ('ir.sequence', 'ir.sequence.date_range') and tn == 'number_next' else rec[tn]
                if tf['type'] == 'many2one': expected, actual = self.mapped(sf['relation'], value), actual.id
                elif tf['type'] == 'binary':
                    expected = bytes(value or b'') if not isinstance(value, str) else value.encode()
                    actual = actual.encode() if isinstance(actual, str) else bytes(actual or b'')
                elif tf['type'] == 'reference':
                    if value:
                        rm, ri = value.rsplit(',', 1)
                        expected = f'{self.target_model(rm)},{self.mapped(rm, int(ri))}'
                        actual = f'{actual._name},{actual.id}' if actual else False
                    else: expected, actual = False, bool(actual)
                elif tf['type'] in ('float', 'monetary'):
                    expected = Decimal(str(value or 0)); actual = Decimal(str(actual or 0))
                    if abs(actual - expected) <= Decimal('0.000001'): continue
                elif tf['type'] in ('date','datetime'):
                    expected, actual = str(value or ''), str(actual or '')
                elif model in ('ab_inventory', 'ab_inventory_header') and fn == 'header_ref':
                    expected = self.values(model, row, final=True)['header_ref']
                elif model == 'ab_accounting_tracking' and fn == 'field_diff_json':
                    expected = self.values(model, row, final=True).get(fn)
                elif fn in self.rules['polymorphic'].get(model, {}).values() and value:
                    expected = self.target_model(value)
                elif tf['type'] == 'selection': expected = self.rules['selections'].get(model, {}).get(fn, {}).get(str(value), value) or False
                else: expected = False if value is None else value
                if actual != expected: problems.append(f'Value mismatch: {model}:{rid}.{fn}')
            if model in ('ab_inventory', 'ab_inventory_header', 'ab_accounting_tracking'):
                adapted = self.values(model, row, final=True)
                if adapted.get('migration_reference_missing'):
                    if not rec.migration_reference_missing or rec.migration_source_references != adapted['migration_source_references']:
                        problems.append(f'Legacy source reference metadata mismatch: {model}:{rid}')
            for fn in AUDIT:
                if fn not in row or fn not in rec._fields: continue
                actual = rec[fn]
                expected = row[fn]
                if fn.endswith('_uid'):
                    expected, actual = self.mapped('res.users', expected), actual.id
                else: expected, actual = str(expected or ''), str(actual or '')
                if actual != expected: problems.append(f'Audit mismatch: {model}:{rid}.{fn}')
            for fn, mf in self.rules['polymorphic'].get(model, {}).items():
                if row.get(fn) and rec[fn] != self.reference_id(model, row, fn, row[mf]):
                    problems.append(f'Polymorphic relation mismatch: {model}:{rid}.{fn}')
            for fn, rm in self.rules.get('integer_links', {}).get(model, {}).items():
                if row.get(fn) and rec[fn] != self.reference_id(model, row, fn, rm):
                    problems.append(f'Integer relation mismatch: {model}:{rid}.{fn}')
            if model == 'ab_accounting_je_line':
                # Use source identifiers for grouping; destination relations are separately checked.
                key = dumps([row.get('account_id'), row.get('store_id'), str(row.get('final_date') or row.get('create_date') or '')[:7], row.get('is_posted')])
                for fn in ('debit_val','credit_val'):
                    totals[key + ':' + fn][0] += Decimal(str(row.get(fn) or 0))
                    totals[key + ':' + fn][1] += Decimal(str(rec[fn] or 0))
            if model == 'res.users':
                self.cr.execute('SELECT password FROM res_users WHERE id=%s', [tid])
                if (self.cr.fetchone()[0] or '') != (row.get('password') or ''):
                    problems.append(f'Password hash mismatch: res.users:{rid}')
            if model == 'ir.attachment' and row.get('type') != 'url' and rid in self.missing_files:
                if (not rec.migration_file_missing or rec.raw or
                    rec.migration_source_path != (row.get('store_fname') or False) or
                    rec.migration_source_checksum != (row.get('checksum') or False) or
                    rec.migration_source_size != (row.get('file_size') or 0)):
                    problems.append(f'Missing attachment metadata mismatch: ir.attachment:{rid}')
            if model == 'ir.attachment' and row.get('type') != 'url' and rid not in self.missing_files:
                expected = self.db.execute('SELECT sha256 FROM attachments WHERE source_id=?', (rid,)).fetchone()
                if not expected or hashlib.sha256(rec.raw or b'').hexdigest() != expected[0]:
                    problems.append(f'Attachment mismatch: ir.attachment:{rid}')
                if rec.res_field and rec.res_model and rec.res_id:
                    import base64
                    owner = self.env[rec.res_model].browse(rec.res_id)
                    encoded = owner[rec.res_field]
                    if not expected or hashlib.sha256(base64.b64decode(encoded or b'')).hexdigest() != expected[0]:
                        problems.append(f'Binary field resolves to wrong attachment: ir.attachment:{rid}')
            for fn, ids in row.get('_m2m', {}).items():
                sf = self.manifest['models'][model]['fields'][fn]
                if self.ignored(model, fn, sf): continue
                tn = self.rules['fields'].get(model, {}).get(fn, fn)
                if tn in rec._fields and set(rec[tn].ids) != {self.mapped(sf['relation'], i) for i in self.relation_ids(model, fn, sf['relation'], ids)}:
                    problems.append(f'Relation mismatch: {model}:{rid}.{fn}')
            if len(problems) > 10000:
                problems.append('Mismatch report truncated at 10000; verification failed'); break
        for key, (expected, actual) in totals.items():
            if abs(expected - actual) > Decimal('0.000001'): problems.append(f'Accounting aggregate mismatch: {key}')
        if self.env['ir.cron'].search_count([('active', '=', True)]):
            problems.append('Scheduled jobs were enabled during import')
        for rid, payload in self.db.execute("SELECT source_id,payload FROM records WHERE model='resource.calendar'"):
            calendar = self.env['resource.calendar'].browse(self.mapped('resource.calendar', rid))
            for child, field in [('resource.calendar.attendance', 'attendance_ids'), ('resource.calendar.leaves', 'leave_ids')]:
                expected = {self.mapped(child, child_id) for child_id, in self.db.execute(
                    "SELECT source_id FROM records WHERE model=? AND json_extract(payload,'$.calendar_id')=?", (child, rid))}
                if set(calendar[field].ids) != expected:
                    problems.append(f'Calendar schedule mismatch: resource.calendar:{rid}.{field}')
        for rid, payload in self.db.execute("SELECT source_id,payload FROM records WHERE model='ab_store'"):
            row = loads(payload)
            if row.get('user_id') and not self.env['ab_hr_department'].search_count([
                ('store_id', '=', self.mapped('ab_store', rid)),
                ('user_id', '=', self.mapped('res.users', row['user_id']))]):
                problems.append(f'Store user relationship mismatch: ab_store:{rid}')
        checks = self.check_access()
        if not checks['passed']:
            problems.append('Branch/role access acceptance tests failed; see access-checks.json')
        self.cr.execute("SELECT count(*),count(*) FILTER (WHERE u.id<>%s) FROM res_users u JOIN accounting_migration.record_map m ON m.model='res.users' AND m.target_id=u.id WHERE u.active", [self.bootstrap_admin_id])
        active_imported, active_non_admin = self.cr.fetchone()
        if self.status != 'development_active' and active_non_admin:
            problems.append('Imported users other than the bootstrap administrator were enabled before acceptance')
        report = {'passed': not problems, 'historical_validation_exceptions': len(self.historical_issues), 'source_references_complete': not self.orphan_refs, 'unresolved_source_references': len(self.orphan_refs), 'files_complete': not self.missing_files, 'missing_files': len(self.missing_files),
                  'cutover_ready': not problems and not self.missing_files and not self.orphan_refs and not self.historical_issues and self.manifest['frozen'] and not self.manifest.get('sample_per_model'),
                  'counts': counts, 'problems': problems, 'accounting_totals': dict(totals),
                  'users_inactive': active_imported == 0, 'imported_non_admin_users_inactive': active_non_admin == 0,
                  'bootstrap_administrator_active': bool(self.env['res.users'].browse(self.bootstrap_admin_id).active), 'scheduled_jobs_disabled': True}
        save_json(self.stage / 'verification.json', report)
        self.cr.execute('UPDATE accounting_migration.run SET status=%s WHERE id', [('development_active' if self.status == 'development_active' else 'verified') if not problems else 'verification_failed'])
        self.cr.commit()
        if problems: raise MigrationError(f'Verification failed ({len(problems)} findings); see verification.json')

    def activate_dev(self):
        if self.manifest.get('sample_per_model'):
            raise MigrationError('Cannot activate a sampled migration')
        self.verify()
        users = [(rid, bool(loads(payload).get('active'))) for rid, payload in self.db.execute("SELECT source_id,payload FROM records WHERE model='res.users'")]
        # Enable source-active users first; never remove the last active administrator midway.
        for rid, active in sorted(users, key=lambda item: (not item[1], item[0])):
            user = self.env['res.users'].browse(self.mapped('res.users', rid))
            if user.id != self.env.uid and user.active != active:
                user.with_context(active_test=True).write({'active': active})
        self.env['ir.cron'].search([]).write({'active': False})
        self.restore_audit()
        self.cr.execute("UPDATE accounting_migration.run SET status='development_active' WHERE id")
        self.cr.commit()
        save_json(self.stage / 'activation.json', {'development': True, 'target': self.args.database,
                  'source_active_users_restored': True, 'scheduled_jobs_disabled': True,
                  'production_cutover': False, 'historical_validation_exceptions': len(self.historical_issues), 'missing_files': len(self.missing_files), 'unresolved_source_references': len(self.orphan_refs)})

    def check_access(self):
        """Execute record-rule checks as imported users, never as sudo."""
        from odoo.exceptions import AccessError
        issues, tested, managers = [], 0, 0
        source_groups = defaultdict(set)
        for uid, gid in self.db.execute('SELECT user_id,group_id FROM groups'):
            if gid not in self.excluded_groups:
                source_groups[uid].add(self.mapped('res.groups', gid))
        for uid, payload in self.db.execute("SELECT source_id,payload FROM records WHERE model='res.users'"):
            try: tid = self.mapped('res.users', uid)
            except MigrationError: continue
            user = self.env['res.users'].browse(tid)
            expected = source_groups[uid]
            if not expected.issubset(set(user.all_group_ids.ids)):
                issues.append(f'Missing mapped roles: res.users:{uid}')
            if user.has_group('base.group_system'):
                system = self.env['ir.model.data']._xmlid_to_res_id('base.group_system')
                if system not in expected: issues.append(f'Unexpected administrator privilege: res.users:{uid}')
                managers += 1
                continue
            # In this addon store_ids means FORBIDDEN Store Auth, not assigned branches.
            # Assignment comes from HR department/employee links. Never invert this policy.
            assigned = self.env['ab_store'].browse()
            if 'ab_department_ids' in user._fields:
                assigned |= user.ab_department_ids.mapped('store_id')
            if 'ab_employee_ids' in user._fields:
                assigned |= user.ab_employee_ids.mapped('department_id.store_id')
            allowed = assigned.ids
            if not allowed: continue
            for model in self.manifest['roots']:
                tm = self.target_model(model)
                if tm not in self.env: continue
                branch_path = BRANCH_PATHS.get(model, 'store_id')
                if branch_path == 'store_id' and 'store_id' not in self.env[tm]._fields: continue
                # Manager exception is module-specific and checked before branch restrictions.
                owners = set(self.manifest['models'][model]['modules'])
                manager_groups = self.env['ir.model.data'].search([
                    ('module', 'in', list(owners)), ('model', '=', 'res.groups'), ('name', 'ilike', 'manager')])
                if set(manager_groups.mapped('res_id')) & expected: continue
                own = self.env[tm].search([(branch_path, 'in', allowed)], limit=1)
                other = self.env[tm].search([(branch_path, 'not in', allowed), (branch_path, '!=', False)], limit=1)
                if not other: continue
                scoped = self.env[tm].with_user(user).with_context(allowed_company_ids=user.company_ids.ids)
                try:
                    leaked = scoped.search([('id', '=', other.id)])
                    if leaked: issues.append(f'Cross-branch visibility: user {uid}, model {model}')
                    if own: scoped.search([('id', '=', own.id)])
                    tested += 1
                except AccessError:
                    # No model ACL means neither branch is visible, which is safe.
                    tested += 1
        if not tested: issues.append('No eligible cross-branch record-rule scenario was exercised')
        result = {'snapshot_id': self.manifest['snapshot_id'], 'passed': not issues,
                  'scenarios': tested, 'administrators': managers, 'issues': issues}
        save_json(self.stage / 'access-checks.json', result)
        return result
