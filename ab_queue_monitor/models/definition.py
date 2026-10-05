from odoo import api, fields, models

from ..services import runtime


class JobDefinition(models.Model):
    _name = 'ab_queue_monitor_definition'
    _description = 'Job Definition'
    _order = 'module_name, method_name, id'
    _rec_name = 'name'
    _unique_key = models.Constraint('UNIQUE(key)', 'A job definition must be unique.')

    name = fields.Char(required=True)
    key = fields.Char(required=True, index=True)
    module_name = fields.Char(required=True, index=True, string='Module')
    module_label = fields.Char(string='Module Display Name')
    model_name = fields.Char(index=True, string='Model')
    method_name = fields.Char(required=True, index=True, string='Method')
    backend = fields.Selection([('queue', 'Integration Queue'), ('website', 'Website Worker'), ('thread', 'Thread'), ('cron', 'Scheduled Action')], required=True)
    source_file = fields.Char()
    source_class = fields.Char()
    source_line = fields.Integer()
    signature = fields.Char(string='Detection Evidence')
    documentation = fields.Text(groups='ab_queue_monitor.group_admin')
    discovery_type = fields.Selection([('static', 'Static'), ('runtime', 'Runtime'), ('both', 'Both')], index=True)
    static_found = fields.Boolean()
    runtime_found = fields.Boolean()
    runtime_support = fields.Boolean()
    discovered_at = fields.Datetime(default=fields.Datetime.now)
    last_seen_at = fields.Datetime()
    active = fields.Boolean(default=True, index=True)
    session_id = fields.Many2one('ab_queue_monitor_session', string='Last Discovery', ondelete='restrict')
    latest_state = fields.Char(compute='_compute_runtime', string='Latest State')
    latest_uuid = fields.Char(compute='_compute_runtime', string='Latest UUID')
    latest_at = fields.Datetime(compute='_compute_runtime', string='Latest Execution')
    execution_count = fields.Integer(compute='_compute_runtime', string='Executions')
    failure_count = fields.Integer(compute='_compute_runtime', string='Failures')
    channel = fields.Char(compute='_compute_runtime')

    def _compute_runtime(self):
        adapters = runtime.adapters(self.env)
        for definition in self:
            definition.latest_state = self.env._('Declared / Idle') if definition.runtime_support else self.env._('Unknown')
            definition.latest_uuid = False
            definition.latest_at = False
            definition.execution_count = 0
            definition.failure_count = 0
            definition.channel = False
            adapter = adapters.get(definition.backend)
            if adapter:
                domain = adapter.domain() & adapter.pair_domain(definition)
                groups = adapter.jobs._read_group(domain, ['state'], ['__count'])
                definition.execution_count = sum(n for _, n in groups)
                definition.failure_count = sum(n for state, n in groups if state == 'failed')
                job = adapter.jobs.search(domain, order=adapter.created + ' desc, id desc', limit=1)
                if job:
                    values = adapter.summary(job)
                    definition.latest_state = dict(adapter.states()).get(values['state'], values['state'])
                    definition.latest_uuid = values['uuid']
                    definition.latest_at = values['created']
                    definition.channel = values['channel']

    def action_executions(self):
        self.check_access('read')
        self.ensure_one()
        return {'type': 'ir.actions.client', 'tag': 'ab_queue_monitor.dashboard',
                'params': {'definition_id': self.id, 'module': self.module_name, 'tab': 'executions'}}

    @api.model
    def _key(self, values):
        return '|'.join(values.get(name, '') or '' for name in ('module', 'backend', 'model_name', 'method_name'))
