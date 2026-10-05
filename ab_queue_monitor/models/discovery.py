import ast
import time

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path

from ..services import runtime, static_discovery


class DiscoverySession(models.Model):
    _name = 'ab_queue_monitor_session'
    _description = 'Job Discovery'
    _order = 'id desc'
    _rec_name = 'started_at'
    _one_scan = models.UniqueIndex("(state) WHERE state = 'scanning'", 'A discovery is already in progress.')

    state = fields.Selection([('scanning', 'Scanning'), ('done', 'Completed'), ('cancelled', 'Cancelled')], default='scanning', required=True)
    started_at = fields.Datetime(default=fields.Datetime.now, required=True)
    finished_at = fields.Datetime()
    duration = fields.Float(string='Duration (seconds)')
    modules_total = fields.Integer()
    modules_scanned = fields.Integer()
    files_total = fields.Integer()
    files_scanned = fields.Integer()
    definitions_count = fields.Integer(string='Job Definitions')
    modules_count = fields.Integer(string='Modules with Jobs')
    runtime_count = fields.Integer(string='Runtime Executions')
    new_count = fields.Integer(string='New')
    removed_count = fields.Integer(string='Removed')
    unchanged_count = fields.Integer(string='Unchanged')
    changes = fields.Text(string='Changes')
    warnings = fields.Text(string='Scan Warnings')
    work = fields.Json(groups=runtime.ADMIN)
    candidates = fields.Json(groups=runtime.ADMIN)
    incomplete_modules = fields.Json(groups=runtime.ADMIN)

    @api.model
    def _admin(self):
        if not self.env.user.has_group(runtime.ADMIN):
            raise AccessError(self.env._('Only Queue Monitor administrators can discover jobs.'))

    @api.model
    def start_scan(self):
        self._admin()
        Session = self.sudo()
        existing = Session.search(fields.Domain('state', '=', 'scanning'), limit=1)
        if existing:
            return existing._progress()
        modules = self.env['ir.module.module'].sudo().search(fields.Domain('state', '=', 'installed'), order='name')
        session = Session.create({'modules_total': len(modules), 'work': {
            'modules': modules.mapped('name'), 'module_index': 0, 'files': [], 'file_index': 0,
        }, 'candidates': {}, 'incomplete_modules': []})
        return session._progress()

    def scan_step(self):
        self._admin()
        self.ensure_one()
        session = self.sudo()
        if not session.exists():
            raise UserError(self.env._('Discovery session no longer exists.'))
        if not session.try_lock_for_update():
            raise UserError(self.env._('This discovery is being advanced by another request.'))
        session.invalidate_recordset()
        if session.state != 'scanning':
            return session._progress()
        work, candidates = dict(session.work), dict(session.candidates or {})
        incomplete = set(session.incomplete_modules or [])
        warnings = (session.warnings or '').splitlines()
        modules_scanned, files_scanned, files_total = session.modules_scanned, session.files_scanned, session.files_total
        deadline = time.monotonic() + 1.5
        processed = 0
        while work['module_index'] < len(work['modules']) and processed < 30 and time.monotonic() < deadline:
            module = work['modules'][work['module_index']]
            root = get_module_path(module)
            if not work.get('inventoried'):
                try:
                    if not root:
                        raise ValueError('missing_source')
                    work['files'] = static_discovery.inventory(root)
                    files_total += len(work['files'])
                except (OSError, ValueError):
                    work['files'] = []
                    incomplete.add(module)
                    warnings.append(module + ': ' + self.env._('Source inventory unavailable or limit exceeded.'))
                work['inventoried'] = True
            while work['file_index'] < len(work['files']) and processed < 30 and time.monotonic() < deadline:
                filename = work['files'][work['file_index']]
                try:
                    for item in static_discovery.scan_file(root, filename, module):
                        if item['backend'] == 'queue' and item['model_name']:
                            owning_module = runtime.owner(self.env, item['model_name'], item['method_name'])
                            if owning_module and owning_module != module:
                                item.update(module=owning_module, source_file='', source_class='', source_line=0)
                        candidates[self.env['ab_queue_monitor_definition']._key(item)] = item
                except (OSError, SyntaxError, ValueError, UnicodeError, RecursionError):
                    incomplete.add(module)
                    warnings.append(module + '/' + filename + ': ' + self.env._('Source could not be inspected.'))
                work['file_index'] += 1
                files_scanned += 1
                processed += 1
            if work['file_index'] == len(work['files']):
                modules_scanned += 1
                work.update(module_index=work['module_index'] + 1, files=[], file_index=0, inventoried=False)
        session.write({'work': work, 'candidates': candidates, 'incomplete_modules': sorted(incomplete),
                       'modules_scanned': modules_scanned, 'files_scanned': files_scanned, 'files_total': files_total,
                       'definitions_count': len(candidates), 'warnings': '\n'.join(warnings[-500:])})
        if work['module_index'] >= len(work['modules']):
            session._finish()
        return session._progress()

    def cancel_scan(self):
        self._admin()
        self.ensure_one()
        session = self.sudo()
        if not session.try_lock_for_update():
            raise UserError(self.env._('This discovery is being advanced by another request.'))
        session.invalidate_recordset()
        if session.state == 'scanning':
            session.write({'state': 'cancelled', 'finished_at': fields.Datetime.now(), 'work': False, 'candidates': False})
        return session._progress()

    def _finish(self):
        Definition = self.env['ab_queue_monitor_definition'].sudo().with_context(active_test=False)
        candidates = dict(self.candidates or {})
        installed = set(self.work['modules'])

        def merge(model, method, backend, pattern, static=False):
            module = runtime.owner(self.env, model, method)
            if not module or module not in installed:
                return
            item = {'module': module, 'model_name': model, 'method_name': method, 'backend': backend}
            key = Definition._key(item)
            current = candidates.setdefault(key, dict(item, signature=pattern))
            current['static_found' if static else 'runtime_found'] = True
            if not current.get('source_file'):
                current.update(runtime.source_metadata(self.env, model, method, module))

        for function in self.env['queue.job.function'].sudo().search([]):
            merge(function.model_id.model, function.method, 'queue', 'queue.job.function declaration', True)
        adapters = runtime.adapters(self.env)
        runtime_count = 0
        for backend, adapter in adapters.items():
            runtime_count += adapter.jobs.search_count(adapter.domain())
            for model, method in adapter.pairs():
                merge(model, method, backend, 'runtime execution')
        if 'website' in adapters:
            merge(runtime.SYNC_MODEL, '_process_background_checkpoint', 'website', 'inspected dedicated worker', True)
        # Existing schedules are evidence only. Never create, trigger or change one.
        for cron in self.env['ir.cron'].sudo().with_context(active_test=False).search([]):
            try:
                tree = ast.parse(cron.code or '')
            except (SyntaxError, ValueError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id in ('model', 'records'):
                    merge(cron.model_id.model, node.func.attr, 'cron', 'existing scheduled action', True)
        old = Definition.search([])
        by_key = {d.key: d for d in old}
        previous = set(old.filtered('active').mapped('key'))
        now = fields.Datetime.now()
        labels = dict(self.env['ir.module.module'].sudo().search(fields.Domain('name', 'in', list(installed))).mapped(lambda m: (m.name, m.shortdesc)))
        for key, item in candidates.items():
            static, live = bool(item.get('static_found')), bool(item.get('runtime_found'))
            values = {name: item[name] for name in ('model_name', 'method_name', 'backend', 'source_file', 'source_class', 'source_line', 'signature', 'documentation') if name in item}
            values.update(key=key, name=item['model_name'] + '.' + item['method_name'], module_name=item['module'],
                          module_label=labels.get(item['module'], item['module']), static_found=static, runtime_found=live,
                          discovery_type='both' if static and live else ('static' if static else 'runtime'),
                          runtime_support=item['backend'] in adapters, active=True, last_seen_at=now, session_id=self.id)
            if key in by_key:
                by_key[key].write(values)
            else:
                Definition.create(values)
        removed = old.filtered(lambda d: d.active and d.key not in candidates and d.module_name not in (self.incomplete_modules or []))
        removed.write({'active': False})
        current = set(candidates) | set(old.filtered(lambda d: d.active and d.module_name in (self.incomplete_modules or [])).mapped('key'))
        new, missing, unchanged = static_discovery.difference(previous, current)
        self.write({'state': 'done', 'finished_at': now, 'duration': (now - self.started_at).total_seconds(),
                    'definitions_count': len(candidates), 'modules_count': len({v['module'] for v in candidates.values()}),
                    'runtime_count': runtime_count, 'new_count': len(new), 'removed_count': len(missing),
                    'unchanged_count': len(unchanged), 'changes': '\n'.join(['+ ' + k for k in new] + ['- ' + k for k in missing]),
                    'work': False, 'candidates': False})

    def _progress(self):
        result = {name: self[name] for name in ('id', 'state', 'modules_total', 'modules_scanned', 'files_total', 'files_scanned',
                'definitions_count', 'modules_count', 'runtime_count', 'new_count', 'removed_count', 'unchanged_count', 'warnings', 'duration')}
        result['elapsed'] = ((self.finished_at or fields.Datetime.now()) - self.started_at).total_seconds()
        return result
