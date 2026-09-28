from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from .ab_supplier import PAYMENT_NATURE, BUSINESS_CATEGORY, TAX_CLASSIFICATION, SUPPLIER_SECTION

STATES = [('legacy_review', 'Legacy — Review Required'), ('draft', 'Draft'), ('inventory', 'Inventory'), ('purchasing', 'Purchasing'),
          ('inventory_purchase', 'Inventory and Purchasing'),
          ('supplier_accounts', 'Supplier Accounts'), ('bank_accounts', 'Bank Accounts'),
          ('returned_secretarial', 'Returned to Secretarial'), ('ready_to_close', 'Ready to Close'), ('closed', 'Closed')]
DECISIONS = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'),
             ('deferred', 'Deferred'), ('cancelled', 'Cancelled'), ('not_required', 'Not Required')]
DEPARTMENTS = ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts')
STAGES = dict(inventory='inventory', purchasing='purchasing',
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
    legacy_status = fields.Char(readonly=True, copy=False)
    payment_nature = fields.Selection(PAYMENT_NATURE, copy=False, tracking=True)
    business_category = fields.Selection(BUSINESS_CATEGORY, readonly=True, copy=False)
    tax_classification = fields.Selection(
        TAX_CLASSIFICATION, string='Tax Type', copy=False, tracking=True,
        help='Optional. Uses the supplier value or its first submitted choice. Fixed after submission.')
    section = fields.Selection(
        SUPPLIER_SECTION, copy=False, tracking=True,
        help='Optional. Uses the supplier value or its first submitted choice. Fixed after submission.')
    bracket_id = fields.Many2one('ab_supplier_bracket', string='Supplier Bracket', ondelete='restrict',
                                 copy=False, tracking=True,
                                 help='Optional. Terms are copied on submission and do not calculate the claim amount.')
    bracket_snapshot = fields.Json(readonly=True, copy=False)
    bracket_payment_type = fields.Selection([
        ('credit', 'Credit'), ('claim_cash', 'Claim Cash'), ('instant_cash', 'Instant Cash')],
        compute='_compute_bracket_terms', string='Payment Type')
    bracket_start_day = fields.Integer(compute='_compute_bracket_terms', string='Start Day')
    bracket_termination_day = fields.Integer(compute='_compute_bracket_terms', string='Termination Day')
    bracket_credit_days = fields.Integer(compute='_compute_bracket_terms', string='Credit Days')
    bracket_discount = fields.Float(compute='_compute_bracket_terms', string='Discount (%)', digits=(5, 2))
    bracket_withdrawal_bracket = fields.Float(compute='_compute_bracket_terms', string='Withdrawal Bracket')
    review_round = fields.Integer(default=0, readonly=True, copy=False)
    resume_stage = fields.Selection(STATES, readonly=True, copy=False)
    rejection_department = fields.Selection([(d, d.replace('_', ' ').title()) for d in DEPARTMENTS], readonly=True, copy=False)
    rejection_reason = fields.Text(readonly=True, copy=False)
    secretarial_notes = fields.Text()
    # Inline binary storage protects evidence from direct ir.attachment mutations.
    cheque_attachment = fields.Binary(attachment=False, copy=False)
    cheque_filename = fields.Char(copy=False)
    history_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', 'claim_id', readonly=True, copy=False,
        domain=fields.Domain('event', 'not in', ['created', 'submitted']))
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

    @api.model
    def _supplier_classifications_by_id(self, supplier_ids):
        suppliers = self.env['ab_supplier'].browse(supplier_ids).exists()
        suppliers.check_access('read')
        defaults = self.env['ab_supplier_claim_cycle.defaults'].sudo().search(
            fields.Domain('supplier_id', 'in', suppliers.ids))
        remembered = {record.supplier_id.id: record for record in defaults}
        result = {}
        for supplier in suppliers:
            previous = remembered.get(supplier.id)
            result[supplier.id] = {
                'tax_classification': supplier.tax_type or (previous.tax_classification if previous else False),
                'section': supplier.section or (previous.section if previous else False),
                'payment_nature': supplier.payment_nature,
            }
        return result

    @api.model
    def _supplier_classifications(self, supplier_id):
        return self._supplier_classifications_by_id([supplier_id] if supplier_id else []).get(
            supplier_id, {'tax_classification': False, 'section': False, 'payment_nature': False})

    @api.onchange('supplier_id')
    def _onchange_supplier_terms(self):
        for claim in self:
            if claim.state == 'draft':
                claim.update(claim._supplier_classifications(claim.supplier_id.id))
                claim.bracket_id = False

    def _bracket_values(self):
        self.ensure_one()
        if not self.bracket_id:
            return {}
        self.bracket_id.check_access('read')
        return {name: self.bracket_id[name] for name in (
            'payment_type', 'start_day', 'termination_day', 'credit_days', 'discount', 'withdrawal_bracket')}

    @api.depends('bracket_snapshot', 'state', 'bracket_id.payment_type', 'bracket_id.start_day',
                 'bracket_id.termination_day', 'bracket_id.credit_days', 'bracket_id.discount',
                 'bracket_id.withdrawal_bracket')
    def _compute_bracket_terms(self):
        for claim in self:
            terms = claim._bracket_values() if claim.state == 'draft' else (claim.bracket_snapshot or {})
            for name in ('payment_type', 'start_day', 'termination_day', 'credit_days', 'discount', 'withdrawal_bracket'):
                claim['bracket_' + name] = terms.get(name, False)

    @api.constrains('supplier_id', 'bracket_id')
    def _check_supplier_bracket(self):
        for claim in self:
            if claim.bracket_id:
                if not claim.supplier_id._has_bracket(claim.bracket_id):
                    raise ValidationError(_('Select a bracket belonging to this supplier’s cost center.'))

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
        return {'legacy_status', 'state', 'user_id', 'business_category', 'bracket_snapshot',
                'review_round', 'resume_stage', 'rejection_department', 'rejection_reason', 'history_ids'} | {
                    f'{d}_decision' for d in DEPARTMENTS}

    @api.model_create_multi
    def create(self, vals_list):
        self._require_role('user')
        allowed = {'supplier_id', 'tax_classification', 'section', 'payment_nature', 'bracket_id', 'num_of_invoice', 'area', 'amount_of_check', 'type_of_invoice', 'secretarial_notes'}
        defaults = dict(state='draft', legacy_status=False, user_id=self.env.uid, review_round=0,
                        business_category=False, bracket_snapshot=False, resume_stage=False,
                        rejection_department=False, rejection_reason=False, active=True,
                        cheque_attachment=False, cheque_filename=False)
        for d in DEPARTMENTS:
            defaults.update({f'{d}_decision': 'not_required', f'{d}_notes': False, f'{d}_followup_date': False})
        supplier_ids = {vals.get('supplier_id') or self.env.context.get('default_supplier_id') for vals in vals_list}
        classifications_by_id = self._supplier_classifications_by_id([sid for sid in supplier_ids if sid])
        clean = []
        for vals in vals_list:
            # Forms submit harmless defaults (including the invisible active flag).
            if any(name not in defaults or value != defaults[name]
                   for name, value in vals.items() if name not in allowed):
                raise AccessError(_('Create a draft claim without workflow values.'))
            supplier_id = vals.get('supplier_id') or self.env.context.get('default_supplier_id')
            classifications = classifications_by_id.get(supplier_id, {
                'tax_classification': False, 'section': False, 'payment_nature': False})
            clean.append({**classifications, 'bracket_id': False, **vals, **defaults})
        # Explicit defaults neutralize forged default_* context values.
        claims = super().create(clean)
        claims._record_secretarial_notes()
        explicit_ids = {claim.id for claim, vals in zip(claims, vals_list) if vals.get('payment_nature')}
        claims.filtered(lambda claim: claim.id in explicit_ids)._save_supplier_payment_nature()
        return claims

    def _save_supplier_payment_nature(self):
        # Called only after validated draft create/write. Claim users have read-only
        # supplier access; elevate only this explicitly selected preference.
        choices = {claim.supplier_id.id: claim.payment_nature for claim in self}
        for nature in ('cash', 'non_cash'):
            suppliers = self.mapped('supplier_id').filtered(lambda supplier: choices[supplier.id] == nature)
            suppliers.filtered(lambda supplier: supplier.payment_nature != nature).sudo().write(
                {'payment_nature': nature})

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
                allowed = correction_fields | ({'supplier_id', 'tax_classification', 'section', 'payment_nature', 'bracket_id'} if claim.state == 'draft' else set())
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
        if 'supplier_id' in vals:
            vals = {**self._supplier_classifications(vals['supplier_id']), 'bracket_id': False, **vals}
        previous_notes = ({claim.id: (claim.secretarial_notes or '').strip() for claim in self}
                          if 'secretarial_notes' in vals else {})
        result = super().write(vals)
        if vals.get('payment_nature'):
            self._save_supplier_payment_nature()
        if 'secretarial_notes' in vals:
            self.filtered(lambda claim: (claim.secretarial_notes or '').strip() != previous_notes[claim.id])._record_secretarial_notes()
        return result

    @api.ondelete(at_uninstall=True)
    def _prevent_claim_deletion(self):
        raise UserError(_('Archive claims instead of deleting them.'))

    def _workflow_write(self, vals):
        # Private RPC-inaccessible bypass, never controlled by a context flag.
        return super(SupplierClaimCycle, self.sudo()).write(vals)

    def _history_values(self, event, from_state=None, department=False, decision=False, reason=False, followup_date=False):
        self.ensure_one()
        return {
            'claim_id': self.id, 'event': event, 'from_state': from_state or self.state, 'to_state': self.state,
            'department': department, 'decision': decision, 'reason': reason, 'followup_date': followup_date,
            'review_round': self.review_round, 'user_id': self.env.uid, 'occurred_at': fields.Datetime.now(),
            **{f'{d}_decision': self[f'{d}_decision'] for d in DEPARTMENTS},
            'tax_classification': self.tax_classification, 'section': self.section,
            'bracket_snapshot': self.bracket_snapshot,
        }

    def _log(self, event, from_state=None, department=False, decision=False, reason=False, followup_date=False):
        self.env['ab_supplier_claim_cycle.history']._append([
            claim._history_values(event, from_state, department, decision, reason, followup_date) for claim in self])

    def _record_secretarial_notes(self):
        self.env['ab_supplier_claim_cycle.history']._append([
            claim._history_values('secretarial_note', department='secretarial', reason=claim.secretarial_notes.strip())
            for claim in self if (claim.secretarial_notes or '').strip()])

    def _check_secretarial_note_access(self):
        self._require_role('user')
        self._prepare_action()
        if any(claim.state not in ('draft', 'returned_secretarial') for claim in self):
            raise UserError(_('Secretarial notes can only be added in Draft or when returned to Secretarial.'))

    def action_open_secretarial_note(self):
        self.ensure_one()
        self._check_secretarial_note_access()
        return {
            'type': 'ir.actions.act_window', 'name': _('Add Secretarial Note'),
            'res_model': 'ab_supplier_claim_cycle.note.wizard', 'view_mode': 'form', 'target': 'new',
            'context': {'default_claim_id': self.id},
        }

    def action_add_secretarial_note(self, note):
        self._check_secretarial_note_access()
        if not isinstance(note, str) or not note.strip():
            raise ValidationError(_('Enter a note before saving.'))
        self._log('secretarial_note', department='secretarial', reason=note.strip())
        return True

    def action_restart_legacy_review(self):
        self._require_role('admin')
        self._prepare_action()
        if any(claim.state != 'legacy_review' for claim in self):
            raise UserError(_('Only recovered legacy claims can restart review.'))
        self._workflow_write({'state': 'draft'})
        self._log('migrated', 'legacy_review', reason='Administrator explicitly restarted the legacy claim for fresh review.')
        return True

    def action_submit(self):
        self._require_role('user')
        self._prepare_action()
        if any(c.state not in ('draft', 'returned_secretarial') for c in self):
            raise UserError(_('Only draft or returned claims can be submitted.'))
        drafts = self.filtered(lambda c: c.state == 'draft')
        drafts._check_supplier_bracket()
        drafts.mapped('bracket_id').lock_for_update(allow_referencing=True)
        drafts.mapped('bracket_id').invalidate_recordset()
        drafts._check_supplier_bracket()
        self.env['ab_supplier_claim_cycle.defaults']._remember(drafts)
        for claim in self:
            old_state = claim.state
            vals = dict(review_round=claim.review_round + 1, rejection_department=False,
                        rejection_reason=False, resume_stage=False)
            if old_state == 'draft':
                supplier = claim.supplier_id
                if not supplier.active:
                    raise ValidationError(_('Select an active supplier.'))
                if not claim.payment_nature:
                    raise ValidationError(_('Select a payment nature before submitting the claim.'))
                vals.update(payment_nature=claim.payment_nature,
                            business_category=supplier.business_category, bracket_snapshot=claim._bracket_values())
                stage = 'supplier_accounts' if claim.payment_nature == 'cash' else 'inventory'
                for d in DEPARTMENTS:
                    vals[f'{d}_decision'] = (
                        'pending' if claim.payment_nature == 'non_cash' or d == 'supplier_accounts'
                        else 'not_required'
                    )
            else:
                stage = claim.resume_stage
            if stage not in STAGES.values():
                raise ValidationError(_('The claim has no valid review stage to resume.'))
            vals['state'] = stage
            for d in DEPARTMENTS:
                if STAGES[d] == stage:
                    vals.update({f'{d}_decision': 'pending', f'{d}_notes': False, f'{d}_followup_date': False})
            if stage == 'supplier_accounts':
                vals.update(cheque_attachment=False, cheque_filename=False)
            claim._workflow_write(vals)
            if old_state != 'draft':
                claim._log('resubmitted', old_state)
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
            if decision == 'rejected':
                vals.update(state='returned_secretarial', resume_stage=old_state,
                            rejection_department=department, rejection_reason=reason)
            elif decision == 'approved':
                if department == 'inventory':
                    # Preserve Purchasing approvals recorded before sequential routing.
                    if claim.purchasing_decision == 'approved':
                        vals.update(state='supplier_accounts', supplier_accounts_decision='pending')
                    else:
                        vals['state'] = 'purchasing'
                        if claim.purchasing_decision != 'deferred':
                            vals['purchasing_decision'] = 'pending'
                elif department == 'purchasing':
                    if claim.inventory_decision != 'approved':
                        raise ValidationError(_('Inventory approval is required before Purchasing approval.'))
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
