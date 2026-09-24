from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from .ab_supplier import PAYMENT_NATURE, BUSINESS_CATEGORY, TAX_CLASSIFICATION

STATES = [('draft', 'Draft'), ('inventory_purchase', 'Inventory and Purchasing'),
          ('supplier_accounts', 'Supplier Accounts'), ('bank_accounts', 'Bank Accounts'),
          ('returned_secretarial', 'Returned to Secretarial'), ('ready_to_close', 'Ready to Close'), ('closed', 'Closed')]
DECISIONS = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'),
             ('deferred', 'Deferred'), ('cancelled', 'Cancelled'), ('not_required', 'Not Required')]
DEPARTMENTS = ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts')
STAGES = dict(inventory='inventory_purchase', purchasing='inventory_purchase',
              supplier_accounts='supplier_accounts', bank_accounts='bank_accounts')
GROUP_PREFIX = 'ab_supplier_claim_cycle.supplier_claim_group_'


class SupplierClaimCycle(models.Model):
    _name = 'ab_supplier_claim_cycle'
    _description = 'Supplier Claim'
    _inherit = ['mail.thread']
    _rec_name = 'supplier_id'
    _order = 'id desc'

    supplier_id = fields.Many2one('ab_supplier', required=True, ondelete='restrict', tracking=True)
    num_of_invoice = fields.Integer(required=True, tracking=True)
    state = fields.Selection(STATES, default='draft', required=True, readonly=True, copy=False, index=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True, ondelete='restrict')
    area = fields.Selection([('south', 'South'), ('north', 'North')], required=True)
    amount_of_check = fields.Char(required=True)
    type_of_invoice = fields.Selection([('original', 'Original'), ('copy', 'Copy')], required=True)
    active = fields.Boolean(default=True)
    payment_nature = fields.Selection(PAYMENT_NATURE, readonly=True, copy=False)
    business_category = fields.Selection(BUSINESS_CATEGORY, readonly=True, copy=False)
    tax_classification = fields.Selection(TAX_CLASSIFICATION, readonly=True, copy=False)
    review_round = fields.Integer(default=0, readonly=True, copy=False)
    resume_stage = fields.Selection(STATES, readonly=True, copy=False)
    rejection_department = fields.Selection([(d, d.replace('_', ' ').title()) for d in DEPARTMENTS], readonly=True, copy=False)
    rejection_reason = fields.Text(readonly=True, copy=False)
    secretarial_notes = fields.Text()
    # Inline binary storage protects evidence from direct ir.attachment mutations.
    cheque_attachment = fields.Binary(attachment=False, copy=False)
    cheque_filename = fields.Char(copy=False)
    history_ids = fields.One2many('ab_supplier_claim_cycle.history', 'claim_id', readonly=True, copy=False)
    inventory_decision = fields.Selection(DECISIONS, default='not_required', readonly=True, copy=False)
    purchasing_decision = fields.Selection(DECISIONS, default='not_required', readonly=True, copy=False)
    supplier_accounts_decision = fields.Selection(DECISIONS, default='not_required', readonly=True, copy=False)
    bank_accounts_decision = fields.Selection(DECISIONS, default='not_required', readonly=True, copy=False)
    inventory_notes = fields.Text(copy=False)
    purchasing_notes = fields.Text(copy=False)
    supplier_accounts_notes = fields.Text(copy=False)
    bank_accounts_notes = fields.Text(copy=False)
    inventory_followup_date = fields.Date(copy=False)
    purchasing_followup_date = fields.Date(copy=False)
    supplier_accounts_followup_date = fields.Date(copy=False)
    bank_accounts_followup_date = fields.Date(copy=False)

    @api.constrains(*(f'{department}_{suffix}' for department in DEPARTMENTS
                      for suffix in ('decision', 'notes', 'followup_date')))
    def _check_deferred_details(self):
        for claim in self:
            for department in DEPARTMENTS:
                if claim[f'{department}_decision'] == 'deferred':
                    if not (claim[f'{department}_notes'] or '').strip():
                        raise ValidationError(_('A reason is required for rejection or deferral.'))
                    if not claim[f'{department}_followup_date']:
                        raise ValidationError(_('A deferred review must retain its follow-up date.'))

    def _is_admin(self):
        return self.env.su or self.env.user.has_group(GROUP_PREFIX + 'admin') or self.env.user.has_group('base.group_system')

    def _require_role(self, role):
        if not self._is_admin() and not self.env.user.has_group(GROUP_PREFIX + role):
            raise AccessError(_('You are not authorized for this workflow action.'))

    def _prepare_action(self):
        self.check_access('write')
        self.lock_for_update()
        self.invalidate_recordset()
        self.check_access('write')
        if any(not c.active or c.state == 'closed' for c in self):
            raise UserError(_('Closed or archived claims cannot be changed.'))

    @api.model
    def _protected_fields(self):
        return {'state', 'user_id', 'payment_nature', 'business_category', 'tax_classification',
                'review_round', 'resume_stage', 'rejection_department', 'rejection_reason', 'history_ids'} | {
                    f'{d}_decision' for d in DEPARTMENTS}

    @api.model_create_multi
    def create(self, vals_list):
        self._require_role('user')
        allowed = {'supplier_id', 'num_of_invoice', 'area', 'amount_of_check', 'type_of_invoice', 'secretarial_notes'}
        defaults = dict(state='draft', user_id=self.env.uid, review_round=0, payment_nature=False,
                        business_category=False, tax_classification=False, resume_stage=False,
                        rejection_department=False, rejection_reason=False, active=True,
                        cheque_attachment=False, cheque_filename=False)
        for d in DEPARTMENTS:
            defaults.update({f'{d}_decision': 'not_required', f'{d}_notes': False, f'{d}_followup_date': False})
        clean = []
        for vals in vals_list:
            # Forms submit harmless defaults (including the invisible active flag).
            if any(name not in defaults or value != defaults[name]
                   for name, value in vals.items() if name not in allowed):
                raise AccessError(_('Create a draft claim without workflow values.'))
            clean.append({**vals, **defaults})
        # Explicit defaults neutralize forged default_* context values.
        claims = super().create(clean)
        claims._log('created')
        return claims

    def write(self, vals):
        if set(vals) & self._protected_fields():
            raise AccessError(_('Use the validated workflow actions to change decisions or stages.'))
        self.check_access('write')
        self.lock_for_update()
        self.invalidate_recordset()
        self.check_access('write')
        if set(vals) == {'active'}:
            self._require_role('user')
            result = super().write(vals)
            self._log('archived' if not vals['active'] else 'restored')
            return result
        if any(c.state == 'closed' or not c.active for c in self):
            raise UserError(_('Closed or archived claims cannot be changed.'))
        correction_fields = {'num_of_invoice', 'area', 'amount_of_check', 'type_of_invoice', 'secretarial_notes'}
        for claim in self:
            if claim.state in ('draft', 'returned_secretarial'):
                claim._require_role('user')
                allowed = correction_fields | ({'supplier_id'} if claim.state == 'draft' else set())
            else:
                allowed = set()
                for d in DEPARTMENTS:
                    if claim.state == STAGES[d] and claim[f'{d}_decision'] in ('pending', 'deferred'):
                        if claim._is_admin() or self.env.user.has_group(GROUP_PREFIX + d):
                            allowed |= {f'{d}_notes', f'{d}_followup_date'}
                            if d == 'supplier_accounts':
                                allowed |= {'cheque_attachment', 'cheque_filename'}
            if set(vals) - allowed:
                raise AccessError(_('You may only edit the fields assigned to your current stage.'))
        return super().write(vals)

    @api.ondelete(at_uninstall=True)
    def _prevent_claim_deletion(self):
        raise UserError(_('Archive claims instead of deleting them.'))

    def _workflow_write(self, vals):
        # Private RPC-inaccessible bypass, never controlled by a context flag.
        return super(SupplierClaimCycle, self.sudo()).write(vals)

    def _log(self, event, from_state=None, department=False, decision=False, reason=False, followup_date=False):
        self.env['ab_supplier_claim_cycle.history']._append([{
            'claim_id': c.id, 'event': event, 'from_state': from_state or c.state, 'to_state': c.state,
            'department': department, 'decision': decision, 'reason': reason, 'followup_date': followup_date,
            'review_round': c.review_round, 'user_id': self.env.uid, 'occurred_at': fields.Datetime.now(),
            **{f'{d}_decision': c[f'{d}_decision'] for d in DEPARTMENTS},
        } for c in self])

    def action_submit(self):
        self._require_role('user')
        self._prepare_action()
        if any(c.state not in ('draft', 'returned_secretarial') for c in self):
            raise UserError(_('Only draft or returned claims can be submitted.'))
        for claim in self:
            old_state = claim.state
            vals = dict(review_round=claim.review_round + 1, rejection_department=False,
                        rejection_reason=False, resume_stage=False)
            if old_state == 'draft':
                supplier = claim.supplier_id
                if not supplier.active:
                    raise ValidationError(_('Select an active supplier.'))
                vals.update(payment_nature=supplier.payment_nature,
                            business_category=supplier.business_category, tax_classification=supplier.tax_type)
                stage = 'supplier_accounts' if supplier.payment_nature == 'cash' else 'inventory_purchase'
                for d in DEPARTMENTS:
                    vals[f'{d}_decision'] = (
                        'pending' if supplier.payment_nature == 'non_cash' or d == 'supplier_accounts'
                        else 'not_required'
                    )
            else:
                stage = claim.resume_stage
            vals['state'] = stage
            for d in DEPARTMENTS:
                if STAGES[d] == stage:
                    vals.update({f'{d}_decision': 'pending', f'{d}_notes': False, f'{d}_followup_date': False})
            if stage == 'supplier_accounts':
                vals.update(cheque_attachment=False, cheque_filename=False)
            claim._workflow_write(vals)
            claim._log('submitted' if old_state == 'draft' else 'resubmitted', old_state)
        return True

    def action_decide(self, department, decision):
        if department not in DEPARTMENTS or decision not in ('approved', 'rejected', 'deferred'):
            raise ValidationError(_('Invalid department decision.'))
        self._require_role(department)
        self._prepare_action()
        for claim in self:
            if claim.state != STAGES[department] or claim[f'{department}_decision'] not in ('pending', 'deferred'):
                raise UserError(_('This department has no pending decision in the current stage.'))
            reason = (claim[f'{department}_notes'] or '').strip()
            followup = claim[f'{department}_followup_date']
            if decision in ('rejected', 'deferred') and not reason:
                raise ValidationError(_('A reason is required for rejection or deferral.'))
            if decision == 'deferred' and (not followup or followup < fields.Date.context_today(claim)):
                raise ValidationError(_('Deferral requires a follow-up date today or later.'))
            old_state = claim.state
            vals = {f'{department}_decision': decision}
            if decision != 'deferred':
                vals[f'{department}_followup_date'] = False
            cancelled = False
            if decision == 'rejected':
                vals.update(state='returned_secretarial', resume_stage=old_state,
                            rejection_department=department, rejection_reason=reason)
                if department in ('inventory', 'purchasing'):
                    other = 'purchasing' if department == 'inventory' else 'inventory'
                    if claim[f'{other}_decision'] in ('pending', 'deferred'):
                        vals.update({f'{other}_decision': 'cancelled', f'{other}_followup_date': False})
                        cancelled = other
            elif decision == 'approved':
                if department in ('inventory', 'purchasing'):
                    other = 'purchasing' if department == 'inventory' else 'inventory'
                    if claim[f'{other}_decision'] == 'approved':
                        vals.update(state='supplier_accounts', supplier_accounts_decision='pending')
                elif department == 'supplier_accounts':
                    if claim.payment_nature == 'cash':
                        vals['state'] = 'ready_to_close'
                    else:
                        if not claim.cheque_attachment:
                            raise ValidationError(_('A cheque attachment is required before Bank Accounts.'))
                        vals.update(state='bank_accounts', bank_accounts_decision='pending')
                else:
                    vals['state'] = 'ready_to_close'
            claim._workflow_write(vals)
            claim._log('decision', old_state, department, decision, reason, followup if decision == 'deferred' else False)
            if cancelled:
                claim._log('decision', old_state, cancelled, 'cancelled',
                           _('Cancelled because the parallel department rejected the claim.'))
        return True

    def action_close(self):
        self._require_role('user')
        self._prepare_action()
        if any(c.state != 'ready_to_close' for c in self):
            raise UserError(_('Only claims ready to close can be closed.'))
        self._workflow_write({'state': 'closed'})
        self._log('closed', 'ready_to_close')
        return True

    def action_department_decision(self):
        return self.action_decide(self.env.context.get('claim_department'), self.env.context.get('claim_decision'))
