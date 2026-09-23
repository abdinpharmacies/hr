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
    required_check_ids = fields.Many2many(
        'ab_deploy_command', 'ab_deploy_command_required_check_rel', 'action_id', 'check_id',
        string='Required Checks', domain="[('command_type', '=', 'check'), ('active', '=', True)]")
    check_sequence = fields.Integer(string='Check Sequence', default=10)
    template = fields.Text(string='Bash Script', required=True)

    def _validate_required_checks(self):
        for command in self:
            checks = command.with_context(active_test=False).required_check_ids
            checks.sorted('id')._lock()
            if command.command_type == 'check':
                if checks:
                    raise ValidationError(_('Post-deployment checks cannot require other checks.'))
            elif command.active and (not checks or any(
                    not check.active or check.command_type != 'check' or check == command for check in checks)):
                raise ValidationError(_('Action %s requires at least one active Post-deployment Check.', command.name))

    @api.constrains('template')
    def _check_template(self):
        for record in self:
            if not (record.template or '').strip() or len(record.template) > 65536 or '\x00' in record.template:
                raise ValidationError(_('Enter a Bash script of 1 to 65536 characters without null bytes.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._require_role('administrator')
        records = super().create(vals_list)
        records._validate_required_checks()
        return records

    def write(self, vals):
        self._require_role('administrator')
        self._lock()
        if vals.get('active') is False or vals.get('command_type') == 'action':
            actions = self.search(fields.Domain('active', '=', True)
                                  & fields.Domain('command_type', '=', 'action')
                                  & fields.Domain('required_check_ids', 'in', self.ids))
            if actions:
                raise ValidationError(_('These checks are required by active actions: %s', ', '.join(actions.mapped('name'))))
        result = super().write(vals)
        self._validate_required_checks()
        return result


class DeployRequestCommand(models.Model):
    _name = 'ab_deploy_request_command'
    _inherit = 'ab_deploy_guard'
    _description = 'Request Command'
    _order = 'execution_sequence, command_type, sequence, id'

    request_id = fields.Many2one('ab_deploy_request', required=True, ondelete='restrict', index=True)
    sequence = fields.Integer(default=10)
    command_id = fields.Many2one('ab_deploy_command', required=True, ondelete='restrict')
    parent_line_id = fields.Many2one('ab_deploy_request_command', string='Related Action',
                                     ondelete='cascade', readonly=True, copy=False, index=True)
    execution_sequence = fields.Integer(string='Execution Order', readonly=True, copy=False)
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
            if any(key in vals for key in ('parent_line_id', 'execution_sequence')):
                raise AccessError(_('Linked check rows are managed automatically. Edit the related action instead.'))
            if 'approved_command_type' in vals:
                raise AccessError(_('Approved command types cannot be edited manually.'))
            vals.setdefault('request_id', self.env.context.get('default_request_id'))
        self.env['ab_deploy_request'].browse([v['request_id'] for v in vals_list])._draft()
        records = super().create(vals_list)
        records.request_id._sync_linked_checks()
        return records

    def write(self, vals):
        if self.parent_line_id or any(key in vals for key in ('parent_line_id', 'execution_sequence')):
            raise AccessError(_('Linked check rows are managed automatically. Edit the related action instead.'))
        if 'approved_command_type' in vals:
            raise AccessError(_('Approved command types cannot be edited manually.'))
        if 'request_id' in vals:
            raise AccessError(_('Commands cannot be moved to another request.'))
        self.mapped('request_id')._draft()
        result = super().write(vals)
        self.request_id._sync_linked_checks()
        return result

    def unlink(self):
        requests = self.request_id
        requests._draft()
        if self.parent_line_id:
            raise AccessError(_('Linked check rows are managed automatically. Edit the related action instead.'))
        children = requests.command_ids.filtered(lambda line: line.parent_line_id in self)
        children._remove_generated()
        self._audit('unlink')
        result = super(DeployGuard, self).unlink()
        requests._sync_linked_checks()
        return result

    def _remove_generated(self):
        if any(not line.parent_line_id for line in self):
            raise ValidationError(_('Only generated checks can be removed automatically.'))
        self._audit('unlink')
        return super(DeployGuard, self).unlink()


class DeployRequestLinkedChecks(models.Model):
    _inherit = 'ab_deploy_request'

    command_ids = fields.One2many(copy=False)

    def copy_data(self, default=None):
        values = super().copy_data(default=default)
        if 'command_ids' not in (default or {}):
            for request, vals in zip(self, values):
                vals['command_ids'] = [fields.Command.create({
                    'command_id': line.command_id.id, 'sequence': line.sequence,
                }) for line in request.command_ids if not line.parent_line_id]
        return values

    def action_refresh_linked_checks(self):
        self._draft()
        self._sync_linked_checks()
        return True

    def _sync_linked_checks(self):
        Line = self.env['ab_deploy_request_command']
        for request in self:
            request._draft()
            roots = request.command_ids.filtered(lambda line: not line.parent_line_id)
            actions = roots.filtered(lambda line: line.command_id.command_type == 'action').sorted(
                lambda line: (line.sequence, line.id))
            standalone = (roots - actions).sorted(lambda line: (line.sequence, line.id))
            ordered = Line
            kept = Line
            for action in actions:
                ordered |= action
                checks = action.command_id.required_check_ids.sorted(lambda check: (check.check_sequence, check.id))
                children = request.command_ids.filtered(lambda line: line.parent_line_id == action)
                for check in checks:
                    child = children.filtered(lambda line: line.command_id == check)[:1]
                    if not child:
                        child = super(DeployRequestCommand, Line).create({
                            'request_id': request.id, 'command_id': check.id, 'parent_line_id': action.id,
                            'sequence': check.check_sequence,
                        })
                    if child.sequence != check.check_sequence:
                        super(DeployRequestCommand, child).write({'sequence': check.check_sequence})
                    ordered |= child
                    kept |= child
            stale = request.command_ids.filtered('parent_line_id') - kept
            stale._remove_generated()
            ordered |= standalone
            for position, line in enumerate(ordered, 1):
                if line.execution_sequence != position:
                    super(DeployRequestCommand, line).write({'execution_sequence': position})
