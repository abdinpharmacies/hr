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


class DeployCommandParameter(models.Model):
    _name = 'ab_deploy_command_parameter'
    _inherit = 'ab_deploy_guard'
    _description = 'Deployment Command Parameter'
    _order = 'server_id, bash_placeholder, id'
    _rec_name = 'bash_placeholder'

    command_id = fields.Many2one('ab_deploy_command', required=True, ondelete='cascade', index=True)
    server_id = fields.Many2one('ab_deploy_server', required=True, ondelete='restrict', string='Server')
    bash_placeholder = fields.Char(string='Variable Name', required=True,
        help='Use DEPLOY_ followed by uppercase letters, digits or underscores, for example DEPLOY_MODULES.')
    value = fields.Text(required=True, help='Ordinary values only. Values are visible in approved scripts and audit history; do not store secrets.')
    _unique_parameter = models.Constraint('UNIQUE(command_id, server_id, bash_placeholder)',
        'A command can define a variable only once per server.')

    @api.constrains('bash_placeholder', 'value')
    def _validate_parameter(self):
        for record in self:
            if not VARIABLE.fullmatch(record.bash_placeholder or '') or record.bash_placeholder in RESERVED:
                raise ValidationError(_('Use a valid DEPLOY_ variable name that is not reserved for server fields.'))
            if '\x00' in (record.value or '') or len(record.value or '') > 65536:
                raise ValidationError(_('Parameter values cannot contain null bytes or exceed 65536 characters.'))

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


class DeployCommandParameters(models.Model):
    _inherit = 'ab_deploy_command'

    parameter_ids = fields.One2many('ab_deploy_command_parameter', 'command_id',
        string='Server Parameters', groups='ab_deploy.group_administrator', copy=True)

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
        values = {parameter.bash_placeholder: parameter.value for parameter in parameters}
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
