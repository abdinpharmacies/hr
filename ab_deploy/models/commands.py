from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from .deployment import DeployGuard


class DeployCommand(models.Model):
    _name = 'ab_deploy_command'
    _inherit = 'ab_deploy_guard'
    _description = 'Deployment Command'
    _order = 'name, id'

    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
    template = fields.Text(string='Bash Script', required=True)

    @api.constrains('template')
    def _check_template(self):
        for record in self:
            if not (record.template or '').strip() or len(record.template) > 65536 or '\x00' in record.template:
                raise ValidationError(_('Enter a Bash script of 1 to 65536 characters without null bytes.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._require_role('administrator')
        return super().create(vals_list)

    def write(self, vals):
        self._require_role('administrator')
        self._lock()
        return super().write(vals)


class DeployRequestCommand(models.Model):
    _name = 'ab_deploy_request_command'
    _inherit = 'ab_deploy_guard'
    _description = 'Request Command'
    _order = 'sequence, id'

    request_id = fields.Many2one('ab_deploy_request', required=True, ondelete='restrict', index=True)
    sequence = fields.Integer(default=10)
    command_id = fields.Many2one('ab_deploy_command', required=True, ondelete='restrict')
    description = fields.Text(related='command_id.description')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('request_id', self.env.context.get('default_request_id'))
        self.env['ab_deploy_request'].browse([v['request_id'] for v in vals_list])._draft()
        return super().create(vals_list)

    def write(self, vals):
        if 'request_id' in vals:
            raise AccessError(_('Commands cannot be moved to another request.'))
        self.mapped('request_id')._draft()
        return super().write(vals)

    def unlink(self):
        self.mapped('request_id')._draft()
        self._audit('unlink')
        return super(DeployGuard, self).unlink()
