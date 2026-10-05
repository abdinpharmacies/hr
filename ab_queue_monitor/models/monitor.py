from odoo import _lt, api, fields, models
from odoo.exceptions import AccessError, UserError
from datetime import datetime, time
from pytz import UTC, timezone

from ..services import runtime

STATUS = [('idle', _lt('Declared / Idle')), ('pending', _lt('Pending')), ('running', _lt('Running')),
          ('completed', _lt('Completed')), ('failed', _lt('Failed')), ('retrying', _lt('Retrying')),
          ('cancelled', _lt('Cancelled')), ('unknown', _lt('Unknown'))]


class QueueMonitor(models.AbstractModel):
    _name = 'ab_queue_monitor'
    _description = 'Queue Monitor'

    def _authorize(self):
        if not self.env.user.has_group(runtime.USER):
            raise AccessError(self.env._('Queue Monitor access is required.'))

    @api.model
    def dashboard(self, filters=None, offset=0, tab='definitions'):
        self._authorize()
        filters = filters if isinstance(filters, dict) else {}
        offset = max(0, min(int(offset), 100000))
        Definition = self.env['ab_queue_monitor_definition'].with_context(active_test=False)
        domain = fields.Domain.TRUE
        if filters.get('active', True):
            domain &= fields.Domain('active', '=', True)
        if filters.get('module'):
            domain &= fields.Domain('module_name', '=', str(filters['module'])[:200])
        if filters.get('search'):
            domain &= fields.Domain('name', 'ilike', str(filters['search'])[:200])
        if filters.get('discovery') in ('static', 'runtime', 'both'):
            domain &= fields.Domain('discovery_type', '=', filters['discovery'])
        if filters.get('definition_id'):
            domain &= fields.Domain('id', '=', int(filters['definition_id']))
        definitions = Definition.search(domain)
        adapters = runtime.adapters(self.env)
        summaries = {}
        for backend, adapter in adapters.items():
            base_domain = self._execution_filter(adapter, adapter.domain(), filters)
            group_fields = ['model_name', 'method_name', 'state'] if backend == 'queue' else ['state']
            grouped = adapter.jobs._read_group(base_domain, group_fields, ['__count', 'id:max'])
            bucket = {}
            for values in grouped:
                model, method, state, count, latest_id = values if backend == 'queue' else (adapter.model, '_process_background_checkpoint', *values)
                entry = bucket.setdefault((model, method), {'count': 0, 'failures': 0, 'latest_id': 0})
                entry['count'] += count
                entry['failures'] += count if runtime.state_category(state) == 'failed' else 0
                entry['latest_id'] = max(entry['latest_id'], latest_id)
            latest_jobs = adapter.jobs.browse([v['latest_id'] for v in bucket.values()])
            # Prefetch only the small, non-payload fields used by summary().
            latest_jobs.fetch([f for f in ('state', 'uuid', 'model_name', 'method_name', 'channel', 'priority',
                'retry', adapter.created, adapter.started, adapter.finished, 'date_cancelled', 'worker_pid') if f in adapter.jobs._fields])
            latest_by_id = {job.id: adapter.summary(job) for job in latest_jobs}
            for pair, entry in bucket.items():
                entry['latest'] = latest_by_id[entry['latest_id']]
                summaries[(backend, *pair)] = entry
        rows, execution_domains = [], {}
        for definition in definitions:
            adapter = adapters.get(definition.backend)
            row = {name: definition[name] for name in ('id', 'name', 'module_name', 'module_label', 'model_name', 'method_name', 'backend', 'discovery_type', 'source_file', 'source_line', 'active')}
            row.update(status='idle' if definition.runtime_support else 'unknown', count=0, failures=0, latest=False, channel='')
            if adapter:
                job_domain = adapter.domain() & adapter.pair_domain(definition)
                job_domain = self._execution_filter(adapter, job_domain, filters)
                execution_domains[definition.id] = job_domain
                summary = summaries.get((definition.backend, definition.model_name, definition.method_name))
                if summary:
                    row.update(count=summary['count'], failures=summary['failures'], latest=summary['latest'])
                    row['status'], row['channel'] = row['latest']['status'], row['latest']['channel']
            if (filters.get('channel') or filters.get('date')) and not row['count']:
                continue
            if filters.get('status') and row['status'] != filters['status'] and tab == 'definitions':
                continue
            if filters.get('error') and not row['failures']:
                continue
            rows.append(row)
        result_rows = rows[offset:offset + 40]
        total = len(rows)
        if tab == 'executions':
            # Paginate each backend in SQL, then merge its first offset+limit
            # records. The adapter set is small and does not duplicate payloads.
            merged, total = [], 0
            for backend, adapter in adapters.items():
                selected = [d for d in definitions if d.backend == backend and d.id in execution_domains]
                if any(filters.get(key) for key in ('module', 'definition_id', 'discovery')):
                    if not selected:
                        continue
                    job_domain = fields.Domain.OR([execution_domains[d.id] for d in selected])
                else:
                    job_domain = self._execution_filter(adapter, adapter.domain(), filters)
                    if filters.get('search'):
                        if backend == 'queue':
                            job_domain &= fields.Domain('method_name', 'ilike', str(filters['search'])[:200]) | fields.Domain('model_name', 'ilike', str(filters['search'])[:200])
                        elif str(filters['search']).lower() not in (adapter.model + '._process_background_checkpoint').lower():
                            job_domain &= fields.Domain.FALSE
                if filters.get('status'):
                    matching = [s for s, _ in adapter.states() if runtime.state_category(s) == filters['status']]
                    if filters['status'] == 'retrying' and 'retry' in adapter.jobs._fields:
                        retry_states = [s for s, _ in adapter.states() if runtime.state_category(s, 1) == 'retrying']
                        job_domain &= fields.Domain('state', 'in', retry_states) & fields.Domain('retry', '>', 0)
                    else:
                        job_domain &= fields.Domain('state', 'in', matching)
                        if filters['status'] == 'pending' and 'retry' in adapter.jobs._fields:
                            job_domain &= fields.Domain('retry', '=', 0) | fields.Domain('state', '=', 'wait_dependencies')
                total += adapter.jobs.search_count(job_domain)
                for job in adapter.jobs.search(job_domain, order=adapter.created + ' desc, id desc', limit=offset + 40):
                    row = adapter.summary(job)
                    row['module_name'] = runtime.owner(self.env, row['model'], row['method'])
                    merged.append(row)
            result_rows = sorted(merged, key=lambda r: (r['created'] or '', r['id']), reverse=True)[offset:offset + 40]
        modules = Definition._read_group(fields.Domain('active', '=', True), ['module_name', 'module_label'], ['__count'])
        kpis = {'modules': len(modules), 'definitions': Definition.search_count(fields.Domain('active', '=', True)), 'running': 0, 'pending': 0, 'failed': 0, 'completed': 0}
        channels = set()
        module_counts = {}
        day_start = self._utc_day_start(fields.Date.context_today(self))
        for adapter in adapters.values():
            group_fields = ['model_name', 'method_name', 'state'] if adapter.backend == 'queue' else ['state']
            for values in adapter.jobs._read_group(adapter.domain(), group_fields, ['__count']):
                model, method, state, count = values if adapter.backend == 'queue' else (adapter.model, '_process_background_checkpoint', *values)
                category = runtime.state_category(state)
                if category in ('running', 'pending', 'failed'):
                    kpis[category] += count
                    module = runtime.owner(self.env, model, method)
                    counts = module_counts.setdefault(module, {'running': 0, 'pending': 0, 'failed': 0})
                    counts[category] += count
            done_states = [state for state, _ in adapter.states() if runtime.state_category(state) == 'completed']
            if adapter.finished in adapter.jobs._fields:
                kpis['completed'] += adapter.jobs.search_count(adapter.domain() & fields.Domain('state', 'in', done_states) & fields.Domain(adapter.finished, '>=', day_start))
            if 'channel' in adapter.jobs._fields:
                channels.update(c for c, in adapter.jobs._read_group(adapter.domain(), ['channel'], []) if c)
        session = self.env['ab_queue_monitor_session'].search([], limit=1)
        return {'rows': result_rows, 'total': total, 'kpis': kpis,
                'modules': [{'name': m, 'label': label, 'count': n, **module_counts.get(m, {'running': 0, 'pending': 0, 'failed': 0})} for m, label, n in modules],
                'channels': sorted(channels), 'statuses': [{'value': s, 'label': self.env._(label)} for s, label in STATUS],
                'runtime_states': {key: adapter.states() for key, adapter in adapters.items()},
                'runner': runtime.runner_health(self.env), 'can_discover': self.env.user.has_group(runtime.ADMIN),
                'session': dict(session._progress(), started_at=fields.Datetime.to_string(session.started_at)) if session else False}

    def _execution_filter(self, adapter, domain, filters):
        if filters.get('runtime_state'):
            domain &= fields.Domain('state', '=', str(filters['runtime_state'])[:80])
        if filters.get('channel'):
            domain &= fields.Domain('channel', '=', str(filters['channel'])[:200]) if 'channel' in adapter.jobs._fields else fields.Domain.FALSE
        if filters.get('date'):
            try:
                date = fields.Date.to_date(filters['date'])
            except (TypeError, ValueError):
                raise UserError(self.env._('Choose a valid date.'))
            domain &= fields.Domain(adapter.created, '>=', self._utc_day_start(date))
        if filters.get('error'):
            domain &= fields.Domain('state', '=', 'failed')
        return domain

    def _utc_day_start(self, day):
        return timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC').localize(
            datetime.combine(day, time.min)).astimezone(UTC).replace(tzinfo=None)

    @api.model
    def execution_details(self, backend, execution_id):
        self._authorize()
        adapter = runtime.adapters(self.env).get(backend)
        if not adapter:
            raise UserError(self.env._('Runtime details are unavailable for this job.'))
        job = adapter.jobs.search(adapter.domain() & fields.Domain('id', '=', int(execution_id)), limit=1)
        if not job:
            raise UserError(self.env._('This execution is no longer retained by its queue.'))
        data = adapter.details(job)
        definition = self.env['ab_queue_monitor_definition'].search(fields.Domain('backend', '=', backend)
            & fields.Domain('model_name', '=', data['model']) & fields.Domain('method_name', '=', data['method']), limit=1)
        data['definition'] = {name: definition[name] for name in ('id', 'source_file', 'source_class', 'source_line', 'module_name')} if definition else False
        return data
