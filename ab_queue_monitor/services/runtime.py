"""Adapters for inspected queue implementations; never invoke job methods."""
import inspect
import re
from datetime import timedelta
from pathlib import Path

from odoo import fields
from odoo.modules.module import get_module_path

ADMIN = 'ab_queue_monitor.group_admin'
USER = 'ab_queue_monitor.group_user'
SYNC_MODEL = 'ab_website_product_sync_job'
CLASSIFICATION_MODEL = 'ab_product_classification_run'


def owner(env, model, method):
    if model not in env:
        return ''
    function = getattr(type(env[model]), method, None)
    if function is None:
        return ''
    function = inspect.unwrap(function)
    module = getattr(function, '__module__', '')
    parts = module.split('.')
    return parts[2] if parts[:2] == ['odoo', 'addons'] and len(parts) > 2 else ''


def source_metadata(env, model, method, module):
    if model not in env:
        return {}
    function = inspect.unwrap(getattr(type(env[model]), method, None))
    code = getattr(function, '__code__', None)
    root = get_module_path(module)
    if not code or not root:
        return {}
    filename = Path(code.co_filename).resolve()
    if not filename.is_relative_to(Path(root).resolve()):
        return {}
    return {'source_file': str(filename.relative_to(Path(root).resolve())),
            'source_line': code.co_firstlineno, 'source_class': function.__qualname__.split('.')[0]}


def state_category(state, retry=0):
    if state in ('pending', 'enqueued', 'queued', 'wait_dependencies', 'draft'):
        return 'retrying' if retry > 0 and state != 'wait_dependencies' else 'pending'
    return {'started': 'running', 'running': 'running', 'done': 'completed',
            'completed': 'completed', 'failed': 'failed', 'cancelled': 'cancelled',
            'retry': 'retrying'}.get(state, 'unknown')


def safe_traceback(value):
    # Messages and source lines can contain arbitrary secrets. Only safe frame
    # locations and exception class identifiers leave the adapter.
    frames = []
    for line in (value or '').splitlines()[-300:]:
        match = re.match(r'\s*File "([^"]+\.py)", line (\d+), in ([\w<>]+)', line)
        if match:
            filename = match[1].replace('\\', '/').split('/')[-1]
            frames.append(f'{filename}:{match[2]} in {match[3]}')
    return '\n'.join(frames[-30:])


class QueueAdapter:
    backend = 'queue'
    model = 'queue.job'
    created = 'date_created'
    started = 'date_started'
    finished = 'date_done'

    def __init__(self, env, now=None, delay_minutes=30):
        self.env = env
        self.jobs = env[self.model].sudo()
        self.now = now or fields.Datetime.now()
        self.delay_minutes = delay_minutes

    def states(self):
        return self.jobs._fields['state']._description_selection(self.env)

    def domain(self):
        # Monitoring roles are global technical roles; payloads remain hidden.
        return fields.Domain.TRUE

    def pairs(self):
        return [(model, method) for model, method in self.jobs._read_group(
            self.domain(), ['model_name', 'method_name'], []) if model and method]

    def pair_domain(self, definition):
        return fields.Domain('model_name', '=', definition.model_name) & fields.Domain('method_name', '=', definition.method_name)

    def status_domain(self, status):
        states = [state for state, _ in self.states() if state_category(state) == status]
        domain = fields.Domain('state', 'in', states)
        if 'retry' in self.jobs._fields:
            if status == 'retrying':
                states = [state for state, _ in self.states() if state_category(state, 1) == status]
                domain = fields.Domain('state', 'in', states) & fields.Domain('retry', '>', 0)
            elif status == 'pending':
                domain &= fields.Domain('retry', '=', 0) | fields.Domain('state', '=', 'wait_dependencies')
        return domain

    def delayed_domain(self):
        cutoff = self.now - timedelta(minutes=self.delay_minutes)
        running_date = fields.Domain(self.started, '<=', cutoff) | (
            fields.Domain(self.started, '=', False) & fields.Domain(self.created, '<=', cutoff))
        waiting_fields = [name for name in (self.created, 'date_enqueued', 'eta') if name in self.jobs._fields]
        waiting_date = fields.Domain.AND([
            fields.Domain(name, '=', False) | fields.Domain(name, '<=', cutoff) for name in waiting_fields
        ]) & fields.Domain.OR([fields.Domain(name, '!=', False) for name in waiting_fields])
        return (self.status_domain('running') & running_date) | (
            (self.status_domain('pending') | self.status_domain('retrying')) & waiting_date)

    def grouped_states(self, domain):
        names = ['model_name', 'method_name'] if self.backend == 'queue' else []
        names += ['state']
        has_retry = 'retry' in self.jobs._fields
        if has_retry:
            names.append('retry')
        for values in self.jobs._read_group(domain, names, ['__count', 'id:max']):
            model, method, *values = values if self.backend == 'queue' else (self.model, '_process_background_checkpoint', *values)
            state, *values = values
            retry = values.pop(0) if has_retry else 0
            yield model, method, state_category(state, retry), *values

    def summary(self, job):
        def get(name, default=False):
            return job[name] if name in job._fields else default
        started, finished = get(self.started), get(self.finished) or get('date_cancelled')
        status = state_category(get('state'), get('retry', 0))
        end = finished or (self.now if status == 'running' else False)
        duration = max(0, (end - started).total_seconds()) if started and end else None
        if not started and status in ('pending', 'retrying'):
            duration = 0
        waiting_dates = [get(name) for name in (self.created, 'date_enqueued', 'eta') if get(name)]
        reference = (started or get(self.created)) if status == 'running' else max(waiting_dates, default=False)
        delayed = bool(status in ('running', 'pending', 'retrying') and reference
                       and reference <= self.now - timedelta(minutes=self.delay_minutes))
        return {
            'id': job.id, 'backend': self.backend, 'uuid': get('uuid') or '',
            'model': get('model_name'), 'method': get('method_name'),
            'state': get('state'), 'status': status, 'delayed': delayed,
            'channel': get('channel') or '', 'priority': get('priority', 0),
            'retry': get('retry', 0), 'created': fields.Datetime.to_string(get(self.created)),
            'started': fields.Datetime.to_string(started), 'finished': fields.Datetime.to_string(finished),
            'duration': round(duration, 1) if duration is not None else None, 'worker': get('worker_pid') or '',
            'database': self.env.cr.dbname,
        }

    def details(self, job):
        data = self.summary(job)
        data.update(error='', result=self.env._('Payload values are withheld.'),
                    arguments=self.env._('Payload values are withheld.'), dependencies={}, context=False)
        if self.env.user.has_group(ADMIN):
            name = (job.exc_name or '') if 'exc_name' in job._fields else ''
            info = job.exc_info if 'exc_info' in job._fields else ''
            data['error'] = (name if re.fullmatch(r'[\w.]+', name) else '') + '\n' + safe_traceback(info)
        if 'dependencies' in job._fields:
            dependencies = job.dependencies or {}
            for key in ('depends_on', 'reverse_depends_on'):
                values = dependencies.get(key, []) if isinstance(dependencies, dict) else []
                values = values if isinstance(values, (list, tuple)) else []
                data['dependencies'][key] = [v for v in values[:100] if isinstance(v, str) and re.fullmatch(r'[a-fA-F0-9-]{36}', v)]
        data['context'] = self.context(job)
        return data

    def context(self, job):
        if 'records' not in job._fields or job.model_name != CLASSIFICATION_MODEL or CLASSIFICATION_MODEL not in self.env:
            return False
        # Deserialize the framework's recordset reference, never invoke it or
        # deserialize arbitrary pickle. Preserve caller ACLs on the target.
        records = job.records
        if records._name != CLASSIFICATION_MODEL or len(records) != 1:
            return False
        run = self.env[CLASSIFICATION_MODEL].with_context(prefetch_fields=False).browse(records.ids).exists()
        if not run or not run.has_access('read'):
            return False
        names = ['total_products', 'processed_products', 'classified_products', 'needs_review_count', 'failed_count']
        return {'model': CLASSIFICATION_MODEL, 'id': run.id, 'name': self.env._('Classification Run'),
                'metrics': {name: value for name, value in run.read([name for name in names if name in run._fields])[0].items() if name != 'id'}}


class WebsiteSyncAdapter(QueueAdapter):
    backend = 'website'
    model = SYNC_MODEL
    created = 'create_date'
    started = 'date_start'

    def domain(self):
        return fields.Domain('background_requested', '=', True) | fields.Domain('state', '!=', 'draft')

    def pairs(self):
        return [(self.model, '_process_background_checkpoint')] if self.jobs.search_count(self.domain(), limit=1) else []

    def pair_domain(self, definition):
        return self.domain()

    def summary(self, job):
        data = super().summary(job)
        data.update(model=self.model, method='_process_background_checkpoint', channel='website_sync')
        return data

    def details(self, job):
        data = self.summary(job)
        data.update(error='', arguments=self.env._('Payload values are withheld.'),
                    result=self.env._('Payload values are withheld.'), dependencies={}, context=False)
        record = self.env[self.model].with_context(prefetch_fields=False).browse(job.id)
        if record.has_access('read'):
            data['context'] = {'model': self.model, 'id': record.id, 'name': self.env._('Website Product Sync'),
                               'metrics': {name: record[name] for name in ('total_count', 'processed_count', 'failed_count')}}
        return data


def adapters(env, now=None, delay_minutes=30):
    result = {'queue': QueueAdapter(env, now, delay_minutes)}
    if SYNC_MODEL in env and 'background_requested' in env[SYNC_MODEL]._fields:
        result['website'] = WebsiteSyncAdapter(env, now, delay_minutes)
    return result


def runner_health(env):
    from odoo.addons.integration_queue_job.jobrunner.runner import PG_ADVISORY_LOCK_ID
    # Read the existing lease. Never acquire/release the runner's lock or call
    # /queue_job/runjob, which is an execution endpoint, not a health endpoint.
    env.cr.execute('''SELECT pid FROM pg_locks WHERE locktype = 'advisory'
        AND database = (SELECT oid FROM pg_database WHERE datname = current_database())
        AND classid = %s AND objid = %s AND objsubid = 1 AND granted''',
        (PG_ADVISORY_LOCK_ID >> 32, PG_ADVISORY_LOCK_ID & 0xffffffff))
    lease = env.cr.fetchone()
    jobs = env['queue.job'].sudo()
    last = jobs.search(fields.Domain('date_done', '!=', False), order='date_done desc', limit=1) if 'date_done' in jobs._fields else jobs.browse()
    return {'status': 'lease_held' if lease else 'unknown', 'progress': 'unverified', 'database': env.cr.dbname,
            'pid': lease[0] if lease else False, 'last_activity': fields.Datetime.to_string(last.date_done) if last else False,
            'evidence': env._('Runner database lease is held; dispatch responsiveness is not measured.') if lease else env._('No runner lease observed. Configuration alone does not establish health.')}
