from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

from ..models.cash_shift import money


class CashOperation(models.TransientModel):
    _name = 'ab_sales_cash_operation'
    _description = 'Cash Shift Operation'

    operation = fields.Selection([('prepare', 'Prepare First Opening'), ('accept', 'Confirm Wallet Receipt'),
        ('close', 'Hand Over and Close Wallet'), ('settle', 'Record Payment'), ('receive', 'Receive Treasury Transfer'),
        ('review', 'Finance Review'), ('reschedule', 'Reassign Unconfirmed Opening')], required=True, readonly=True)
    drawer_id = fields.Many2one('ab_sales_cash_drawer', required=True, readonly=True)
    store_id = fields.Many2one(related='drawer_id.store_id')
    currency_id = fields.Many2one(related='drawer_id.currency_id')
    shift_id = fields.Many2one('ab_sales_cash_shift', readonly=True)
    transfer_id = fields.Many2one('ab_sales_cash_transfer', readonly=True)
    sale_id = fields.Many2one('ab_sales_header', readonly=True)
    return_id = fields.Many2one('ab_sales_return_header', readonly=True)
    session_token = fields.Char(copy=False)
    employee_id = fields.Many2one('ab_hr_employee', string='Employee')
    pin = fields.Char(string='Employee PIN', copy=False)
    counted_amount = fields.Monetary(string='Physically Counted Cash')
    count_confirmed = fields.Boolean(string='I physically counted this cash')
    opening_amount = fields.Monetary(string='First Opening Float')
    carry_amount = fields.Monetary(string='Next Employee Opening Balance')
    next_employee_id = fields.Many2one('ab_hr_employee', string='Next Cashier')
    treasury_id = fields.Many2one('ab_sales_cash_treasury', string='Destination Treasury')
    note = fields.Text(string='Explanation / Review Note')
    expected_amount = fields.Monetary(related='shift_id.cash_amount', string='Expected Cash')
    handover_amount = fields.Monetary(related='shift_id.opening_amount', string='Opening to Receive')
    due_amount = fields.Monetary(compute='_compute_due')
    method_ids = fields.Many2many(related='drawer_id.method_ids')
    line_ids = fields.One2many('ab_sales_cash_operation_line', 'wizard_id', string='Payment Breakdown')

    @api.depends('sale_id', 'return_id')
    def _compute_due(self):
        for wizard in self:
            amount = wizard.return_id._native_refund_amount() if wizard.return_id else (wizard.sale_id.native_totals or {}).get('total_bill_net', 0)
            wizard.due_amount = wizard.currency_id.round(amount) if wizard.currency_id else amount

    @api.model
    def default_get(self, names):
        result = super().default_get(names)
        drawer = self.env['ab_sales_cash_drawer'].browse(result.get('drawer_id')).exists()
        if drawer:
            drawer.check_access('read')
            result['treasury_id'] = drawer.treasury_id.id
        return result

    def _session(self):
        self.ensure_one()
        if not self.session_token:
            session = self.env['ab_employee_access_sales_pos_session'].sudo().search([
                ('service_user_id', '=', self.env.uid), ('employee_id', '=', self.employee_id.id),
                ('store_id', '=', self.drawer_id.store_id.id), ('state', '=', 'active')], limit=1)
            if not session or not self.pin or not session._get_pos_profile().check_pos_pin(self.pin):
                raise AccessError(_('Enter the active employee and PIN for this branch.'))
            token = session.session_token
        else:
            token = self.session_token
        return self.drawer_id._session(token)

    def _count(self):
        if not self.count_confirmed:
            raise ValidationError(_('Confirm that the cash was physically counted.'))
        return money(self.counted_amount, self.currency_id)

    def action_confirm(self):
        self.ensure_one()
        self.check_access('write')
        self.drawer_id.check_access('read')
        if self.drawer_id.company_id not in self.env.companies:
            raise AccessError(_('The drawer must belong to an allowed company.'))
        with self.env.cr.savepoint():
            if self.operation == 'review':
                self._review()
            else:
                self.drawer_id._lock()
                if not self.drawer_id.enabled or not self.drawer_id.active:
                    raise ValidationError(_('Enable the drawer before performing cash operations.'))
                if self.operation == 'prepare':
                    self._prepare()
                elif self.operation == 'reschedule':
                    self._reschedule()
                else:
                    session = self._session()
                    if self.operation == 'settle':
                        self._settle(session)
                    elif self.operation == 'accept':
                        self._accept(session)
                    elif self.operation == 'close':
                        self._close(session)
                    elif self.operation == 'receive':
                        self._receive(session)
            self.write({'session_token': False, 'pin': False})
        return {'type': 'ir.actions.act_window_close'}

    def _prepare(self):
        drawer = self.drawer_id
        drawer._check_manager()
        if drawer._current():
            raise ValidationError(_('This branch already has an active cashier wallet.'))
        if not self.next_employee_id:
            raise ValidationError(_('Select the responsible cashier for the opening.'))
        drawer._check_cashier(self.next_employee_id)
        amount = money(self.opening_amount, self.currency_id)
        shift = self.env['ab_sales_cash_shift']._insert({
            'drawer_id': drawer.id, 'employee_id': self.next_employee_id.id,
            'start_at': drawer._next_opening_time(), 'state': 'open',
            'opening_amount': amount, 'cash_amount': amount})
        if amount:
            self.env['ab_sales_cash_transfer']._insert({'shift_id': shift.id, 'treasury_id': drawer.treasury_id.id,
                'direction': 'opening', 'amount': amount, 'receiver_id': self.next_employee_id.id})

    def _checked_shift(self, state):
        shift = self.shift_id
        shift.check_access('read')
        states = [state] if isinstance(state, str) else state
        if not shift or shift.drawer_id != self.drawer_id or shift.state not in states or self.drawer_id._current() != shift:
            raise ValidationError(_('This is not the active cashier wallet. Refresh the screen.'))
        return shift

    def _accept(self, session):
        shift = self._checked_shift(['waiting', 'open'])
        if session.employee_id != shift.employee_id:
            raise AccessError(_('Only the incoming cashier can confirm receipt of this wallet.'))
        if shift.accepted_at:
            return
        amount = self._count()
        if not self.currency_id.is_zero(amount - shift.opening_amount):
            raise ValidationError(_('The received amount must match the recorded opening float.'))
        shift._update({'state': 'open', 'accepted_at': fields.Datetime.now(), 'accepted_user_id': self.env.uid})
        transfers = shift.transfer_ids.filtered(lambda record: record.direction == 'opening' and record.state == 'pending')
        transfers._update({'state': 'received', 'received_at': fields.Datetime.now(), 'received_user_id': self.env.uid})

    def _close(self, session):
        shift = self._checked_shift('open')
        if session.employee_id != shift.employee_id:
            raise AccessError(_('Only the responsible cashier can close this drawer shift.'))
        amount = self._count()
        carry = money(self.carry_amount, self.currency_id)
        if carry > amount:
            raise ValidationError(_('The next opening balance cannot exceed the counted cash.'))
        if carry and not self.next_employee_id:
            raise ValidationError(_('Choose the next cashier when retaining an opening balance.'))
        if carry:
            self.drawer_id._check_cashier(self.next_employee_id)
        treasury = self.treasury_id
        treasury_amount = self.currency_id.round(amount - carry)
        if treasury_amount:
            treasury.check_access('read')
        if treasury_amount and (not treasury or not treasury.active or treasury.store_id != shift.store_id):
            raise ValidationError(_('Choose an active treasury in the drawer branch.'))
        variance = self.currency_id.round(amount - shift.cash_amount)
        shift._update({'state': 'closed', 'closed_at': fields.Datetime.now(), 'closed_user_id': self.env.uid,
            'counted_amount': amount, 'carry_amount': carry, 'variance': variance,
            'variance_note': self.note, 'review_state': 'pending' if variance else 'none'})
        shift.flush_recordset(['state', 'active_drawer_id'])
        if carry:
            self.env['ab_sales_cash_shift']._insert({'drawer_id': self.drawer_id.id,
                'employee_id': self.next_employee_id.id, 'start_at': self.drawer_id._next_opening_time(), 'state': 'open',
                'opening_amount': carry, 'cash_amount': carry, 'previous_id': shift.id})
        if treasury_amount:
            self.env['ab_sales_cash_transfer']._insert({'shift_id': shift.id, 'treasury_id': treasury.id,
                'direction': 'closing', 'amount': treasury_amount, 'receiver_id': treasury.receiver_id.id})

    def _reschedule(self):
        self.drawer_id._check_manager()
        shift = self._checked_shift(['waiting', 'open'])
        if shift.accepted_at:
            raise ValidationError(_('A confirmed wallet assignment cannot be changed.'))
        self.drawer_id._check_cashier(self.next_employee_id)
        if not (self.note or '').strip():
            raise ValidationError(_('Explain why the unaccepted opening is being reassigned.'))
        audit = _('%(time)s — %(user)s: %(old)s → %(new)s; %(reason)s',
            time=fields.Datetime.now(), user=self.env.user.display_name,
            old=shift.employee_id.display_name, new=self.next_employee_id.display_name,
            reason=self.note)
        shift._update({'employee_id': self.next_employee_id.id,
            'assignment_history': '\n'.join(filter(None, [shift.assignment_history, audit]))})
        shift.transfer_ids.filtered(lambda item: item.direction == 'opening' and item.state == 'pending')._update({
            'receiver_id': self.next_employee_id.id})

    def _settle(self, session):
        if bool(self.sale_id) == bool(self.return_id):
            raise ValidationError(_('Choose exactly one sale or refund.'))
        document = self.return_id or self.sale_id
        document.check_access('read')
        if document.store_id != self.drawer_id.store_id:
            raise AccessError(_('The document must belong to this branch.'))
        rows = [{'method_id': line.method_id.id, 'amount': line.amount, 'reference': line.reference} for line in self.line_ids]
        self.env['ab_sales_cashier_api'].with_context(cash_shift_tenders=rows).save_pending_invoice(
            document.id, store_id=self.drawer_id.store_id.id, wallet_id=self.drawer_id.store_id.id,
            document_type='return' if self.return_id else 'sale', session_token=session.session_token)

    def _receive(self, session):
        transfer = self.transfer_id
        transfer.check_access('read')
        if not transfer or transfer.shift_id.drawer_id != self.drawer_id or transfer.direction != 'closing':
            raise AccessError(_('Choose a closing transfer from this drawer.'))
        if session.employee_id != transfer.receiver_id:
            raise AccessError(_('Only the designated treasury employee can confirm receipt.'))
        if not self.currency_id.is_zero(self._count() - transfer.amount):
            raise ValidationError(_('The received amount must match the treasury transfer.'))
        if transfer.state != 'received':
            transfer._update({'state': 'received', 'received_at': fields.Datetime.now(), 'received_user_id': self.env.uid})

    def _review(self):
        if not (self.env.is_system() or self.env.user.has_group('ab_sales_cash_shift.group_cash_finance')):
            raise AccessError(_('Only Finance can review cash differences.'))
        shift = self.shift_id
        shift.check_access('read')
        if not shift or shift.drawer_id != self.drawer_id or shift.state != 'closed':
            raise ValidationError(_('Choose a closed shift for Finance review.'))
        shift.lock_for_update(allow_referencing=True)
        shift.invalidate_recordset()
        if shift.review_state != 'pending' or not (self.note or '').strip():
            raise ValidationError(_('A pending cash difference requires a Finance review note.'))
        shift._update({'review_state': 'approved', 'review_note': self.note,
                       'reviewed_by': self.env.uid, 'reviewed_at': fields.Datetime.now()})


class CashOperationLine(models.TransientModel):
    _name = 'ab_sales_cash_operation_line'
    _description = 'Payment Breakdown Entry'

    wizard_id = fields.Many2one('ab_sales_cash_operation', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='wizard_id.currency_id')
    method_id = fields.Many2one('ab_sales_cash_method', required=True)
    amount = fields.Monetary(required=True)
    reference = fields.Char(string='Transaction Reference')
