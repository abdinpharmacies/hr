from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class TrainingWallet(models.Model):
    _name = 'ab.training.wallet'
    _description = 'Training Member Wallet'
    _order = 'user_id'
    _check_company_auto = True

    user_id = fields.Many2one(
        'res.users',
        string='Member',
        required=True,
        ondelete='restrict',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        index=True,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        readonly=True,
    )
    active = fields.Boolean(default=True)
    task_ids = fields.One2many('ab.training.task', 'wallet_id', string='Tasks')
    activity_task_ids = fields.One2many(
        'ab.training.task',
        'wallet_id',
        string='Incentive Activity',
        domain=[('state', 'in', ('pending', 'approved'))],
    )
    reset_line_ids = fields.One2many(
        'ab.training.wallet.reset.line',
        'wallet_id',
        string='Payout History',
    )
    approved_amount = fields.Monetary(
        compute='_compute_balances',
        currency_field='currency_id',
        string='Approved Balance',
    )
    pending_amount = fields.Monetary(
        compute='_compute_balances',
        currency_field='currency_id',
        string='Pending Balance',
    )
    approved_task_count = fields.Integer(compute='_compute_balances')
    pending_task_count = fields.Integer(compute='_compute_balances')
    total_paid_amount = fields.Monetary(
        compute='_compute_paid_totals',
        currency_field='currency_id',
        string='Total Paid',
    )
    last_reset_at = fields.Datetime(
        compute='_compute_paid_totals',
        string='Last Payout At',
    )

    _unique_member_company = models.Constraint(
        'UNIQUE(user_id, company_id)',
        'A member can only have one training wallet per company.',
    )

    @api.depends(
        'task_ids.state',
        'task_ids.incentive_value',
        'task_ids.wallet_reset_line_id',
    )
    def _compute_balances(self):
        balances = defaultdict(lambda: {
            'approved_amount': 0.0,
            'pending_amount': 0.0,
            'approved_task_count': 0,
            'pending_task_count': 0,
        })
        if self.ids:
            tasks = self.env['ab.training.task'].search([
                ('wallet_id', 'in', self.ids),
                ('state', 'in', ('pending', 'approved')),
            ])
            for task in tasks:
                values = balances[task.wallet_id.id]
                if task.state == 'pending':
                    values['pending_amount'] += task.incentive_value
                    values['pending_task_count'] += 1
                elif not task.wallet_reset_line_id:
                    values['approved_amount'] += task.incentive_value
                    values['approved_task_count'] += 1
        for wallet in self:
            values = balances[wallet.id]
            wallet.approved_amount = values['approved_amount']
            wallet.pending_amount = values['pending_amount']
            wallet.approved_task_count = values['approved_task_count']
            wallet.pending_task_count = values['pending_task_count']

    @api.depends('reset_line_ids.approved_amount', 'reset_line_ids.reset_at')
    def _compute_paid_totals(self):
        for wallet in self:
            wallet.total_paid_amount = sum(wallet.reset_line_ids.mapped('approved_amount'))
            wallet.last_reset_at = max(wallet.reset_line_ids.mapped('reset_at'), default=False)

    @api.model
    def _get_or_create(self, user, company):
        wallet = self.search([
            ('user_id', '=', user.id),
            ('company_id', '=', company.id),
        ], limit=1)
        if not wallet:
            wallet = self.create({
                'user_id': user.id,
                'company_id': company.id,
            })
        return wallet

    @api.model
    def action_open_my_wallet(self):
        if not self.env.user.has_group('ab_training_tasks.group_training_tasks_member'):
            raise AccessError(_('You do not have access to training wallets.'))
        wallet = self.sudo()._get_or_create(self.env.user, self.env.company)
        form_view_id = self.env['ir.model.data']._xmlid_to_res_id(
            'ab_training_tasks.view_training_wallet_form'
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('My Wallet'),
            'res_model': 'ab.training.wallet',
            'res_id': wallet.id,
            'view_mode': 'form',
            'views': [(form_view_id, 'form')],
            'target': 'current',
            'context': {'create': False, 'edit': False, 'delete': False},
        }

    def action_open_reset_wizard(self):
        self.ensure_one()
        if not self.env.user.has_group('ab_training_tasks.group_training_tasks_manager'):
            raise AccessError(_('Only training managers can reset wallets.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reset Member Wallet'),
            'res_model': 'ab.training.wallet.reset.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_scope': 'single',
                'default_wallet_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }
