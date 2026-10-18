from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class OpeningRun(models.Model):
    _name = 'ab_purchase_ob_run'
    _description = 'Inventory Opening Run'

    _store_unique = models.Constraint('UNIQUE(store_id)', 'A store can have only one inventory opening run.')

    name = fields.Char(required=True)
    store_id = fields.Many2one('ab_store', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='store_id.company_id', store=True, index=True)
    cutoff_date = fields.Date(required=True)
    state = fields.Selection([('open', 'Open'), ('closed', 'Closed')], default='open', required=True, readonly=True)
    closed_by = fields.Many2one('res.users', readonly=True)
    closed_at = fields.Datetime(readonly=True)
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('state', 'open') != 'open' or vals.get('closed_by') or vals.get('closed_at') for vals in vals_list):
            raise ValidationError(_('Create opening runs in the open state.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'state', 'closed_by', 'closed_at'} & vals.keys():
            raise ValidationError(_('Use Close Opening Run to close a run.'))
        if set(vals) - {'active'} and (any(run.state == 'closed' for run in self) or self.env['ab_purchase_ob_header'].search_count([('opening_run_id', 'in', self.ids)])):
            raise ValidationError(_('Opening runs with documents cannot be changed.'))
        return super().write(vals)

    def action_close(self):
        self.check_access('write')
        if not (self.env.user.has_group('base.group_system') or self.env.user.has_group('ab_inventory.group_inventory_manager')):
            raise AccessError(_('Only inventory managers can close opening runs.'))
        self.lock_for_update()
        self.invalidate_recordset()
        if self.env['ab_purchase_ob_header'].search_count([('opening_run_id', 'in', self.ids), ('status', '=', 'pending')]):
            raise ValidationError(_('Approve every opening document before closing its run.'))
        return super().write({'state': 'closed', 'closed_by': self.env.uid, 'closed_at': fields.Datetime.now()})

    def unlink(self):
        raise ValidationError(_('Archive opening runs instead of deleting them.'))
