from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class TrainingWalletResetWizard(models.TransientModel):
    _name = 'ab.training.wallet.reset.wizard'
    _description = 'Reset Training Wallets'

    scope = fields.Selection(
        [('all', 'All Members'), ('single', 'Single Member')],
        required=True,
        default='all',
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        readonly=True,
    )
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    wallet_id = fields.Many2one(
        'ab.training.wallet',
        string='Member Wallet',
        domain="[('company_id', '=', company_id)]",
    )
    approved_task_count = fields.Integer(compute='_compute_preview')
    approved_amount = fields.Monetary(compute='_compute_preview', currency_field='currency_id')
    pending_task_count = fields.Integer(compute='_compute_preview')
    pending_amount = fields.Monetary(compute='_compute_preview', currency_field='currency_id')
    acknowledge_pending = fields.Boolean(
        string='I acknowledge that pending tasks will remain in the wallet and are not included in this payout.',
    )
    note = fields.Text(string='Payout Note')

    @api.depends('scope', 'company_id', 'wallet_id')
    def _compute_preview(self):
        for wizard in self:
            tasks = wizard._get_scope_tasks()
            approved = tasks.filtered(
                lambda task: task.state == 'approved' and not task.wallet_reset_line_id
            )
            pending = tasks.filtered(lambda task: task.state == 'pending')
            wizard.approved_task_count = len(approved)
            wizard.approved_amount = sum(approved.mapped('incentive_value'))
            wizard.pending_task_count = len(pending)
            wizard.pending_amount = sum(pending.mapped('incentive_value'))

    @api.onchange('scope', 'wallet_id')
    def _onchange_scope_wallet(self):
        self.acknowledge_pending = False

    def _get_scope_tasks(self):
        self.ensure_one()
        if not self.company_id:
            return self.env['ab.training.task']
        domain = [('company_id', '=', self.company_id.id)]
        if self.scope == 'single':
            if not self.wallet_id:
                return self.env['ab.training.task']
            domain.append(('wallet_id', '=', self.wallet_id.id))
        return self.env['ab.training.task'].search(domain)

    def action_reset(self):
        self.ensure_one()
        if not self.env.user.has_group('ab_training_tasks.group_training_tasks_manager'):
            raise AccessError(_('Only training managers can reset wallets.'))
        if self.scope == 'single' and not self.wallet_id:
            raise ValidationError(_('Select a member wallet to reset.'))

        tasks = self._get_scope_tasks()
        approved_tasks = tasks.filtered(
            lambda task: task.state == 'approved' and not task.wallet_reset_line_id
        )
        pending_tasks = tasks.filtered(lambda task: task.state == 'pending')
        if pending_tasks and not self.acknowledge_pending:
            raise ValidationError(_(
                'Pending tasks are not included in the payout. Acknowledge the warning before continuing.'
            ))
        if not approved_tasks:
            raise UserError(_('There are no approved wallet incentives available to reset.'))

        approved_by_wallet = defaultdict(lambda: self.env['ab.training.task'])
        pending_by_wallet = defaultdict(lambda: self.env['ab.training.task'])
        for task in approved_tasks:
            approved_by_wallet[task.wallet_id.id] |= task
        for task in pending_tasks:
            pending_by_wallet[task.wallet_id.id] |= task

        operation_context = dict(self.env.context, training_wallet_reset_operation=True)
        reset = self.env['ab.training.wallet.reset'].sudo().with_context(operation_context).create({
            'scope': self.scope,
            'company_id': self.company_id.id,
            'reset_by': self.env.user.id,
            'reset_at': fields.Datetime.now(),
            'note': self.note,
        })
        line_vals = []
        wallet_ids = sorted(set(approved_by_wallet) | set(pending_by_wallet))
        for wallet_id in wallet_ids:
            wallet_tasks = approved_by_wallet[wallet_id]
            wallet_pending = pending_by_wallet[wallet_id]
            line_vals.append({
                'reset_id': reset.id,
                'wallet_id': wallet_id,
                'approved_amount': sum(wallet_tasks.mapped('incentive_value')),
                'approved_task_count': len(wallet_tasks),
                'pending_amount_at_reset': sum(wallet_pending.mapped('incentive_value')),
                'pending_task_count_at_reset': len(wallet_pending),
            })
        lines = self.env['ab.training.wallet.reset.line'].sudo().with_context(operation_context).create(line_vals)
        lines_by_wallet = {line.wallet_id.id: line for line in lines}
        for wallet_id, wallet_tasks in approved_by_wallet.items():
            wallet_tasks.with_context(operation_context).write({
                'wallet_reset_line_id': lines_by_wallet[wallet_id].id,
            })
        reset.with_user(self.env.user).message_post(
            body=_('Approved incentives were paid without changing pending tasks.')
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Wallet Payout'),
            'res_model': 'ab.training.wallet.reset',
            'res_id': reset.id,
            'view_mode': 'form',
            'target': 'current',
        }
