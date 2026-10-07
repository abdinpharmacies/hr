import re
import shlex

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from .deployment import DeployGuard

VARIABLE = re.compile(r'DEPLOY_[A-Z][A-Z0-9_]*\Z')
REFERENCE = re.compile(r'\$(?:\{)?(DEPLOY_[A-Za-z0-9_]+)')
SERVER_FIELDS = {
    'DEPLOY_DATABASE': 'database_name',
    'DEPLOY_PYTHON': 'odoo_python_path',
    'DEPLOY_CONFIG': 'odoo_config_path',
    'DEPLOY_SERVER_PATH': 'odoo_server_path',
    'DEPLOY_LOG_PATH': 'odoo_log_path',
}
RESERVED = set(SERVER_FIELDS) | {'DEPLOY_ODOO_BIN'}


class DeployParameterGuard(models.AbstractModel):
    _name = 'ab_deploy_parameter_guard'
    _inherit = 'ab_deploy_guard'
    _description = 'Deployment Parameter Guard'
    _rec_name = 'bash_placeholder'

    command_id = fields.Many2one('ab_deploy_command', required=True, ondelete='cascade', index=True)
    bash_placeholder = fields.Char(string='Variable Name', required=True,
        help='Use DEPLOY_ followed by uppercase letters, digits or underscores, for example DEPLOY_MODULES.')
    value = fields.Text(required=True, help='Ordinary values only. Values are visible in approved scripts and audit history; do not store secrets.')

    @api.model
    def _validate_values(self, key, value):
        if not VARIABLE.fullmatch(key or '') or key in RESERVED:
            raise ValidationError(_('Use a valid DEPLOY_ variable name that is not reserved for server fields.'))
        if not value:
            raise ValidationError(_('Enter a parameter value.'))
        if '\x00' in value or len(value) > 65536:
            raise ValidationError(_('Parameter values cannot contain null bytes or exceed 65536 characters.'))

    @api.constrains('bash_placeholder', 'value')
    def _validate_parameter(self):
        for record in self:
            self._validate_values(record.bash_placeholder, record.value)

    @api.model_create_multi
    def create(self, vals_list):
        self._require_role('administrator')
        command_ids = [vals.get('command_id') or self.env.context.get('default_command_id') for vals in vals_list]
        self.env['ab_deploy_command'].browse([cid for cid in command_ids if cid]).sorted('id')._lock()
        return super().create(vals_list)

    def write(self, vals):
        self._require_role('administrator')
        commands = self.command_id | self.env['ab_deploy_command'].browse(vals.get('command_id') or [])
        commands.sorted('id')._lock()
        return super().write(vals)

    def unlink(self):
        self._require_role('administrator')
        self.command_id.sorted('id')._lock()
        self._audit('unlink')
        return super(DeployGuard, self).unlink()


class DeployCommandParameter(models.Model):
    _name = 'ab_deploy_command_parameter'
    _inherit = 'ab_deploy_parameter_guard'
    _description = 'Deployment Command Parameter'
    _order = 'server_id, bash_placeholder, id'

    server_id = fields.Many2one('ab_deploy_server', required=True, ondelete='restrict', string='Server')
    _unique_parameter = models.Constraint('UNIQUE(command_id, server_id, bash_placeholder)',
        'A command can define a variable only once per server.')


class DeployCommandParameterDefault(models.Model):
    _name = 'ab_deploy_command_parameter_default'
    _inherit = 'ab_deploy_parameter_guard'
    _description = 'Deployment Command Default Parameter'
    _order = 'bash_placeholder, id'

    _unique_parameter = models.Constraint('UNIQUE(command_id, bash_placeholder)',
        'A command can define a default only once per variable.')


class DeployCommandParameters(models.Model):
    _inherit = 'ab_deploy_command'

    parameter_ids = fields.One2many('ab_deploy_command_parameter', 'command_id',
        string='Server Parameters', groups='ab_deploy.group_administrator', copy=True)
    parameter_default_ids = fields.One2many('ab_deploy_command_parameter_default', 'command_id',
        string='Default Parameters', groups='ab_deploy.group_administrator', copy=True)
    parameter_server_ids = fields.Many2many('ab_deploy_server', string='Parameter Servers',
        groups='ab_deploy.group_administrator', copy=False)
    parameter_key = fields.Char(string='Key', groups='ab_deploy.group_administrator', copy=False)
    parameter_value = fields.Text(string='Value', groups='ab_deploy.group_administrator', copy=False)

    def action_add_all_parameter_servers(self):
        self.ensure_one()
        self._require_role('administrator')
        self._lock()
        servers = self.env['ab_deploy_server'].search(fields.Domain('active', '=', True))
        self.write({'parameter_server_ids': [fields.Command.link(server.id)
                                            for server in servers - self.parameter_server_ids]})
        return True

    def action_set_parameter(self):
        self.ensure_one()
        self._require_role('administrator')
        self._lock()
        Parameter = self.env['ab_deploy_command_parameter']
        Parameter._validate_values(self.parameter_key, self.parameter_value)
        servers = self.parameter_server_ids
        servers.check_access('read')
        domain = fields.Domain('command_id', '=', self.id) & fields.Domain('bash_placeholder', '=', self.parameter_key)
        if servers:
            existing = Parameter.search(domain & fields.Domain('server_id', 'in', servers.ids))
            existing.filtered(lambda row: row.value != self.parameter_value).write({'value': self.parameter_value})
            missing = servers - existing.server_id
            if missing:
                Parameter.create([{'command_id': self.id, 'server_id': server.id,
                                   'bash_placeholder': self.parameter_key, 'value': self.parameter_value}
                                  for server in missing])
            message = _('Parameter %(key)s set for %(count)s servers.', key=self.parameter_key, count=len(servers))
        else:
            Default = self.env['ab_deploy_command_parameter_default']
            existing = Default.search(domain)
            if existing:
                existing.filtered(lambda row: row.value != self.parameter_value).write({'value': self.parameter_value})
            else:
                Default.create({'command_id': self.id, 'bash_placeholder': self.parameter_key,
                                'value': self.parameter_value})
            message = _('Shared default set for parameter %s.', self.parameter_key)
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Set Parameter'), 'message': message, 'type': 'success',
                           'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}}}

    def _resolve_server_script(self, server):
        self.ensure_one()
        server.ensure_one()
        self.check_access('read')
        server.check_access('read')
        names = sorted(set(REFERENCE.findall(self.template or '')))
        if not names:
            return self.template
        parameters = self.env['ab_deploy_command_parameter'].sudo().search(
            fields.Domain('command_id', '=', self.id) & fields.Domain('server_id', '=', server.id))
        defaults = self.env['ab_deploy_command_parameter_default'].sudo().search(
            fields.Domain('command_id', '=', self.id))
        values = {parameter.bash_placeholder: parameter.value for parameter in defaults}
        values.update({parameter.bash_placeholder: parameter.value for parameter in parameters})
        values.update({name: server[field] for name, field in SERVER_FIELDS.items()})
        values['DEPLOY_ODOO_BIN'] = (server.odoo_server_path.rstrip('/') + '/server/odoo-bin') if server.odoo_server_path else False
        missing = [name for name in names if not values.get(name)]
        if missing:
            raise ValidationError(_('Command %(command)s on server %(server)s is missing values for: %(variables)s',
                                    command=self.name, server=server.name, variables=', '.join(missing)))
        if any('\x00' in values[name] for name in names):
            raise ValidationError(_('Parameter values cannot contain null bytes or exceed 65536 characters.'))
        assignments = ['%s=%s' % (name, shlex.quote(values[name])) for name in names]
        return '\n'.join(assignments) + '\n' + self.template
