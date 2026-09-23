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
    command_type = fields.Selection([('action', 'Deployment Action'), ('check', 'Post-deployment Check')],
                                    string='Command Type', required=True, default='action')
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
    _order = 'command_type, sequence, id'

    request_id = fields.Many2one('ab_deploy_request', required=True, ondelete='restrict', index=True)
    sequence = fields.Integer(default=10)
    command_id = fields.Many2one('ab_deploy_command', required=True, ondelete='restrict')
    description = fields.Text(related='command_id.description')
    approved_command_type = fields.Selection([('action', 'Deployment Action'), ('check', 'Post-deployment Check')],
                                            readonly=True, copy=False)
    command_type = fields.Selection([('action', 'Deployment Action'), ('check', 'Post-deployment Check')],
                                   string='Command Type', compute='_compute_command_type', store=True)

    @api.depends('request_id.state', 'command_id.command_type', 'approved_command_type')
    def _compute_command_type(self):
        for line in self:
            line.command_type = line.command_id.command_type if line.request_id.state == 'draft' else (line.approved_command_type or 'action')

    def _freeze_type(self):
        for kind in ('action', 'check'):
            lines = self.filtered(lambda line: line.command_id.command_type == kind and line.approved_command_type != kind)
            if lines:
                super(DeployRequestCommand, lines).write({'approved_command_type': kind})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'approved_command_type' in vals:
                raise AccessError(_('Approved command types cannot be edited manually.'))
            vals.setdefault('request_id', self.env.context.get('default_request_id'))
        self.env['ab_deploy_request'].browse([v['request_id'] for v in vals_list])._draft()
        return super().create(vals_list)

    def write(self, vals):
        if 'approved_command_type' in vals:
            raise AccessError(_('Approved command types cannot be edited manually.'))
        if 'request_id' in vals:
            raise AccessError(_('Commands cannot be moved to another request.'))
        self.mapped('request_id')._draft()
        return super().write(vals)

    def unlink(self):
        self.mapped('request_id')._draft()
        self._audit('unlink')
        return super(DeployGuard, self).unlink()
