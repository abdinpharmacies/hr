from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class TrainingWalletReset(models.Model):
    _name = 'ab.training.wallet.reset'
    _description = 'Training Wallet Payout'
    _inherit = ['mail.thread']
    _order = 'reset_at desc, id desc'
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True, copy=False, default=lambda self: _('New'))
    scope = fields.Selection(
        [('all', 'All Members'), ('single', 'Single Member')],
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one('res.company', required=True, readonly=True, ondelete='restrict')
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    reset_by = fields.Many2one('res.users', required=True, readonly=True, ondelete='restrict')
    reset_at = fields.Datetime(required=True, readonly=True)
    note = fields.Text(readonly=True)
    line_ids = fields.One2many('ab.training.wallet.reset.line', 'reset_id', string='Members')
    total_amount = fields.Monetary(
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    task_count = fields.Integer(compute='_compute_totals', store=True)
    pending_amount_at_reset = fields.Monetary(
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    pending_task_count_at_reset = fields.Integer(compute='_compute_totals', store=True)

    @api.depends(
        'line_ids.approved_amount',
        'line_ids.approved_task_count',
        'line_ids.pending_amount_at_reset',
        'line_ids.pending_task_count_at_reset',
    )
    def _compute_totals(self):
        for reset in self:
            reset.total_amount = sum(reset.line_ids.mapped('approved_amount'))
            reset.task_count = sum(reset.line_ids.mapped('approved_task_count'))
            reset.pending_amount_at_reset = sum(reset.line_ids.mapped('pending_amount_at_reset'))
            reset.pending_task_count_at_reset = sum(reset.line_ids.mapped('pending_task_count_at_reset'))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('training_wallet_reset_operation'):
            raise AccessError(_('Wallet payout logs can only be created through the reset workflow.'))
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ab.training.wallet.reset') or _('New')
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('training_wallet_reset_operation'):
            raise AccessError(_('Wallet payout logs are immutable.'))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_('Wallet payout logs cannot be deleted.'))


class TrainingWalletResetLine(models.Model):
    _name = 'ab.training.wallet.reset.line'
    _description = 'Training Wallet Payout Line'
    _order = 'reset_at desc, id desc'
    _check_company_auto = True

    reset_id = fields.Many2one(
        'ab.training.wallet.reset',
        required=True,
        ondelete='cascade',
        index=True,
    )
    wallet_id = fields.Many2one(
        'ab.training.wallet',
        required=True,
        ondelete='restrict',
        check_company=True,
        index=True,
    )
    member_id = fields.Many2one(related='wallet_id.user_id', store=True, readonly=True)
    company_id = fields.Many2one(related='reset_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(related='reset_id.currency_id', readonly=True)
    reset_at = fields.Datetime(related='reset_id.reset_at', store=True, readonly=True)
    reset_by = fields.Many2one(related='reset_id.reset_by', store=True, readonly=True)
    approved_amount = fields.Monetary(required=True, readonly=True, currency_field='currency_id')
    approved_task_count = fields.Integer(required=True, readonly=True)
    pending_amount_at_reset = fields.Monetary(required=True, readonly=True, currency_field='currency_id')
    pending_task_count_at_reset = fields.Integer(required=True, readonly=True)
    task_ids = fields.One2many('ab.training.task', 'wallet_reset_line_id', string='Paid Tasks')

    _non_negative_amounts = models.Constraint(
        'CHECK(approved_amount >= 0 AND pending_amount_at_reset >= 0)',
        'Wallet payout amounts cannot be negative.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('training_wallet_reset_operation'):
            raise AccessError(_('Wallet payout lines can only be created through the reset workflow.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('training_wallet_reset_operation'):
            raise AccessError(_('Wallet payout lines are immutable.'))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_('Wallet payout lines cannot be deleted.'))
