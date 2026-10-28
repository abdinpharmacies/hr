from datetime import timedelta
from decimal import Decimal, InvalidOperation

from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


def money(value, currency, nonnegative=True):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(_('Enter a valid monetary amount.')) from None
    if not number.is_finite() or (nonnegative and number < 0):
        raise ValidationError(_('Enter a finite, nonnegative monetary amount.'))
    rounded = currency.round(float(number))
    if abs(number - Decimal(str(rounded))) > Decimal('0.00000001'):
        raise ValidationError(_('Amounts must use the company currency precision.'))
    return rounded


class CashRecord(models.AbstractModel):
    _name = 'ab_sales_cash_record'
    _description = 'Controlled Cash Record'

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Use the authorized cash operation to create records.'))

    def write(self, vals):
        raise AccessError(_('Cash records can only change through their authorized operations.'))

    def unlink(self):
        raise AccessError(_('Cash records cannot be deleted.'))

    @api.model
    def _insert(self, vals):
        return super(CashRecord, self.sudo()).create(vals).with_env(self.env)

    def _update(self, vals):
        return super(CashRecord, self.sudo()).write(vals)


class CashConfiguration(models.AbstractModel):
    _name = 'ab_sales_cash_configuration'
    _description = 'Cash Configuration Permissions'

    def _check_manager(self):
        if not (self.env.is_system() or self.env.user.has_group('ab_sales_cash_shift.group_cash_manager')):
            raise AccessError(_('Cash configuration manager access is required.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager()
        records = super().create(vals_list)
        records._check_scope()
        return records

    def write(self, vals):
        self._check_manager()
        self.check_access('write')
        if {'store_id', 'company_id'} & vals.keys():
            raise AccessError(_('Cash configuration cannot be moved to another branch or company.'))
        result = super().write(vals)
        self._check_scope()
        return result

    def _check_scope(self):
        for record in self:
            if record.company_id not in self.env.companies:
                raise AccessError(_('The cash configuration must belong to an allowed company.'))

    def unlink(self):
        raise AccessError(_('Archive cash configuration instead of deleting it.'))


class CashTreasury(models.Model):
    _name = 'ab_sales_cash_treasury'
    _inherit = 'ab_sales_cash_configuration'
    _description = 'Branch Treasury'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    store_id = fields.Many2one('ab_store', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='store_id.company_id', store=True)
    receiver_id = fields.Many2one('ab_hr_employee', string='Receiving Employee', required=True, ondelete='restrict')
    _code_unique = models.Constraint('UNIQUE(store_id, code)', 'Treasury codes must be unique within a branch.')


class CashMethod(models.Model):
    _name = 'ab_sales_cash_method'
    _inherit = 'ab_sales_cash_configuration'
    _description = 'Cashier Payment Method'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    kind = fields.Selection([('cash', 'Cash'), ('card', 'Card'), ('wallet', 'Electronic Wallet'),
                             ('other', 'Other')], required=True)
    require_reference = fields.Boolean(string='Require Transaction Reference', default=True)

    def write(self, vals):
        self._check_manager()
        self.check_access('write')
        self.lock_for_update(allow_referencing=True)
        if {'kind', 'require_reference'} & vals.keys():
            if self.env['ab_sales_cash_tender'].sudo().search_count([('method_id', 'in', self.ids)], limit=1):
                raise ValidationError(_('Used payment methods cannot change their accounting meaning.'))
        return super().write(vals)


class CashDrawer(models.Model):
    _name = 'ab_sales_cash_drawer'
    _inherit = 'ab_sales_cash_configuration'
    _description = 'Branch Cashier Wallet Control'
    _rec_name = 'store_id'

    store_id = fields.Many2one('ab_store', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='store_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    active = fields.Boolean(default=True)
    enabled = fields.Boolean(default=False)
    treasury_id = fields.Many2one('ab_sales_cash_treasury', required=True, ondelete='restrict')
    method_ids = fields.Many2many('ab_sales_cash_method', string='Accepted Payment Methods', required=True)
    _store_unique = models.Constraint('UNIQUE(store_id)', 'Each branch has one shared cash drawer.')

    @api.constrains('store_id', 'treasury_id', 'method_ids', 'enabled')
    def _validate_configuration(self):
        for drawer in self:
            if drawer.treasury_id.store_id != drawer.store_id or not drawer.treasury_id.active:
                raise ValidationError(_('Choose an active treasury in the drawer branch.'))
            if not drawer.method_ids or any(method.company_id != drawer.company_id or not method.active for method in drawer.method_ids):
                raise ValidationError(_('Choose active payment methods in the drawer company.'))
            if drawer.enabled and not self.env['ab_sales_backend']._is_native(drawer.store_id.id):
                raise ValidationError(_('Cash shifts require the native Odoo sales backend.'))

    def write(self, vals):
        self._check_manager()
        self.mapped('store_id')._lock_stock_scope()
        if any(key in vals for key in ('enabled', 'active', 'treasury_id')):
            if self.env['ab_sales_cash_shift'].sudo().search_count([('drawer_id', 'in', self.ids)], limit=1):
                raise ValidationError(_('A drawer with cash history must keep its configuration active.'))
        return super().write(vals)

    @api.model
    def _for_store(self, store):
        drawer = self.sudo().with_context(active_test=False).search([
            ('store_id', '=', store.id), ('enabled', '=', True)], limit=1)
        if drawer:
            self.env['ab_sales_backend']._check_store(store.id, cashier=True)
        return self.browse(drawer.id)

    def _lock(self):
        self.ensure_one()
        self.env['ab_sales_backend']._check_store(self.store_id.id, cashier=True)
        self.store_id.with_user(SUPERUSER_ID)._lock_stock_scope()
        self.invalidate_recordset()

    def _current(self):
        self.ensure_one()
        shift = self.env['ab_sales_cash_shift'].sudo().search([
            ('drawer_id', '=', self.id), ('state', 'in', ['waiting', 'open'])], order='id desc', limit=1)
        return self.env['ab_sales_cash_shift'].browse(shift.id)

    def _next_opening_time(self):
        self.ensure_one()
        now = fields.Datetime.now()
        latest = self.env['ab_sales_cash_shift'].sudo().search(
            [('drawer_id', '=', self.id)], order='start_at desc, id desc', limit=1)
        if latest and latest.start_at and latest.start_at >= now:
            return latest.start_at + timedelta(seconds=1)
        return now

    def _check_cashier(self, employee):
        self.ensure_one()
        profile = self.env['ab_employee_access'].sudo().search([
            ('employee_id', '=', employee.id), ('pos_allow_login', '=', True)], limit=1)
        if not profile or not profile._is_store_allowed_for_pos(self.store_id) or not profile._effective_pos_permissions().get('allow_cashier_screen'):
            raise ValidationError(_('Choose a cashier authorized for this branch.'))

    def _session(self, token):
        self.ensure_one()
        session = self.env['ab_sales_backend']._check_employee_session(
            self.store_id, 'allow_cashier_screen', token=token)
        if session.store_id != self.store_id:
            raise AccessError(_('The employee session must belong to this drawer branch.'))
        return session

    def _require_open(self, token=False, responsible=True, create=False):
        self.ensure_one()
        self._lock()
        shift = self._current()
        session = self._session(token) if responsible or create else False
        if not shift and create:
            shift = self.env['ab_sales_cash_shift']._insert({
                'drawer_id': self.id,
                'employee_id': session.employee_id.id,
                'start_at': self._next_opening_time(),
                'state': 'open',
                'opening_amount': 0,
                'cash_amount': 0,
                'accepted_at': fields.Datetime.now(),
                'accepted_user_id': self.env.uid,
            })
        if not shift:
            raise ValidationError(_('No active cashier wallet exists for this branch.'))
        if responsible:
            if session.employee_id != shift.employee_id:
                raise AccessError(_('This branch wallet belongs to another cashier. Complete the formal handover first.'))
        return shift

    def action_prepare_opening(self):
        self.ensure_one()
        self._check_manager()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'res_model': 'ab_sales_cash_operation',
                'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new',
                'context': {'default_drawer_id': self.id, 'default_operation': 'prepare'}}


class CashShift(models.Model):
    _name = 'ab_sales_cash_shift'
    _inherit = 'ab_sales_cash_record'
    _description = 'Cashier Wallet Ledger'
    _order = 'start_at desc, id desc'
    _rec_name = 'start_at'

    drawer_id = fields.Many2one('ab_sales_cash_drawer', required=True, ondelete='restrict')
    store_id = fields.Many2one(related='drawer_id.store_id', store=True)
    company_id = fields.Many2one(related='drawer_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    employee_id = fields.Many2one('ab_hr_employee', string='Responsible Cashier', required=True, ondelete='restrict')
    start_at = fields.Datetime(string='Opened At', required=True, default=fields.Datetime.now)
    end_at = fields.Datetime(string='Legacy Scheduled End')
    slot = fields.Integer(string='Legacy Scheduled Shift')
    state = fields.Selection([('waiting', 'Awaiting Receipt'), ('open', 'Open'), ('closed', 'Closed')], required=True, default='waiting')
    active_drawer_id = fields.Many2one(
        'ab_sales_cash_drawer', compute='_compute_active_drawer_id', store=True, precompute=True,
        readonly=True, index=True, ondelete='restrict')
    opening_amount = fields.Monetary(string='Opening Float')
    cash_amount = fields.Monetary(string='Expected Cash')
    accepted_at = fields.Datetime()
    accepted_user_id = fields.Many2one('res.users')
    closed_at = fields.Datetime()
    closed_user_id = fields.Many2one('res.users')
    counted_amount = fields.Monetary(string='Counted Cash')
    carry_amount = fields.Monetary(string='Next Opening Float')
    variance = fields.Monetary(string='Cash Difference')
    variance_note = fields.Text(string='Cash Difference Explanation')
    review_state = fields.Selection([('none', 'No Difference'), ('pending', 'Awaiting Finance'), ('approved', 'Reviewed by Finance')], default='none')
    review_note = fields.Text(string='Finance Review Note')
    reviewed_by = fields.Many2one('res.users')
    reviewed_at = fields.Datetime()
    assignment_history = fields.Text(string='Opening Assignment History')
    previous_id = fields.Many2one('ab_sales_cash_shift', ondelete='restrict')
    next_ids = fields.One2many('ab_sales_cash_shift', 'previous_id', string='Following Wallets')
    event_ids = fields.One2many('ab_sales_cash_event', 'shift_id')
    transfer_ids = fields.One2many('ab_sales_cash_transfer', 'shift_id')
    _slot_unique = models.Constraint('UNIQUE(drawer_id, start_at)', 'A drawer has only one wallet opening at the same instant.')
    _active_drawer_unique = models.Constraint('UNIQUE(active_drawer_id)', 'A branch can have only one active cashier wallet.')

    @api.depends('drawer_id', 'state')
    def _compute_active_drawer_id(self):
        for shift in self:
            shift.active_drawer_id = shift.drawer_id if shift.state in ('waiting', 'open') else False

    def action_print_wallet_report(self):
        self.ensure_one()
        self.check_access('read')
        if self.state != 'closed':
            raise ValidationError(_('Close the cashier wallet before printing its report.'))
        return self.env.ref('ab_sales_cash_shift.cash_wallet_report_action').report_action(self)

    def action_reschedule(self):
        self.ensure_one()
        self.check_access('read')
        self.drawer_id._check_manager()
        return {'type': 'ir.actions.act_window', 'res_model': 'ab_sales_cash_operation',
                'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new',
                'context': {'default_drawer_id': self.drawer_id.id, 'default_shift_id': self.id,
                            'default_operation': 'reschedule', 'default_next_employee_id': self.employee_id.id}}

    def action_review(self):
        self.ensure_one()
        self.check_access('read')
        if not (self.env.is_system() or self.env.user.has_group('ab_sales_cash_shift.group_cash_finance')):
            raise AccessError(_('Only Finance can review cash differences.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'ab_sales_cash_operation',
                'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new',
                'context': {'default_drawer_id': self.drawer_id.id, 'default_shift_id': self.id,
                            'default_operation': 'review'}}


class CashEvent(models.Model):
    _name = 'ab_sales_cash_event'
    _inherit = 'ab_sales_cash_record'
    _description = 'Cash Shift Settlement'
    _order = 'id desc'

    shift_id = fields.Many2one('ab_sales_cash_shift', required=True, ondelete='restrict')
    store_id = fields.Many2one(related='shift_id.store_id', store=True)
    company_id = fields.Many2one(related='shift_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    payment_id = fields.Many2one('ab_sales_native_payment', required=True, ondelete='restrict')
    employee_id = fields.Many2one('ab_hr_employee', required=True, ondelete='restrict')
    session_id = fields.Many2one('ab_employee_access_sales_pos_session', required=True, ondelete='restrict')
    total_amount = fields.Monetary()
    cash_amount = fields.Monetary()
    tender_ids = fields.One2many('ab_sales_cash_tender', 'event_id')
    _payment_unique = models.Constraint('UNIQUE(payment_id)', 'Each payment belongs to one cash shift.')


class CashTender(models.Model):
    _name = 'ab_sales_cash_tender'
    _inherit = 'ab_sales_cash_record'
    _description = 'Cash Shift Payment Detail'

    event_id = fields.Many2one('ab_sales_cash_event', required=True, ondelete='restrict')
    store_id = fields.Many2one(related='event_id.store_id', store=True)
    company_id = fields.Many2one(related='event_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    method_id = fields.Many2one('ab_sales_cash_method', required=True, ondelete='restrict')
    amount = fields.Monetary(required=True)
    reference = fields.Char(string='Transaction Reference')


class CashTransfer(models.Model):
    _name = 'ab_sales_cash_transfer'
    _inherit = 'ab_sales_cash_record'
    _description = 'Drawer Treasury Transfer'
    _order = 'id desc'

    shift_id = fields.Many2one('ab_sales_cash_shift', required=True, ondelete='restrict')
    store_id = fields.Many2one(related='shift_id.store_id', store=True)
    company_id = fields.Many2one(related='shift_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    treasury_id = fields.Many2one('ab_sales_cash_treasury', required=True, ondelete='restrict')
    direction = fields.Selection([('opening', 'Treasury to Drawer'), ('closing', 'Drawer to Treasury')], required=True)
    amount = fields.Monetary(required=True)
    receiver_id = fields.Many2one('ab_hr_employee', required=True, ondelete='restrict')
    state = fields.Selection([('pending', 'Awaiting Receipt'), ('received', 'Received')], default='pending', required=True)
    received_at = fields.Datetime()
    received_user_id = fields.Many2one('res.users')
    _shift_direction_unique = models.Constraint('UNIQUE(shift_id, direction)', 'A cash shift has one transfer per direction.')

    def action_receive(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'res_model': 'ab_sales_cash_operation',
                'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new',
                'context': {'default_drawer_id': self.shift_id.drawer_id.id, 'default_transfer_id': self.id,
                            'default_operation': 'receive'}}
