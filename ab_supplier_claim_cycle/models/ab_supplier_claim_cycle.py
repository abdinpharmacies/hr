from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

PAYMENT_NATURE = [('cash', 'Cash'),
                  ('bank_transfer', 'Bank Transfer'), ('check', 'Check')]
TAX_CLASSIFICATION = [
    ('through_supplier', 'Advance Payments'),
    ('tax_payment', 'Tax Payment'),
    ('non_tax_payment', 'Non-tax Payment'),
]

SUPPLIER_SECTION = [('medical', 'Medicine'), ('cosmo', 'Cosmetics'), ('other', 'Other')]
CLAIM_DEFAULT_FIELDS = ('type_of_invoice', 'payment_nature', 'tax_classification', 'section', 'area')

STATES = [('draft', 'Draft'), ('inventory', 'Inventory'),
          ('purchasing', 'Purchasing'),
          ('supplier_accounts', 'Supplier Accounts'), ('bank_accounts', 'Bank Accounts'),
          ('returned_secretarial', 'Returned to Secretarial'), ('ready_to_close', 'Ready to Close'),
          ('closed', 'Closed')]
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

    supplier_id = fields.Many2one(
        'ab_costcenter', required=True, ondelete='restrict', tracking=True,
        domain=fields.Domain('code', '=like', '1-%'),
    )
    num_of_invoice = fields.Integer(required=True, tracking=True)
    state = fields.Selection(STATES, default='draft', required=True, readonly=True, copy=False, index=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True, ondelete='set null')
    area = fields.Selection([('south', 'South'), ('north', 'North')], required=True)
    amount_of_check = fields.Char(required=True)
    type_of_invoice = fields.Selection([('original', 'Original'), ('copy', 'Copy'),
                                        ('bank_statement', 'Bank Statement')], required=True)
    active = fields.Boolean(default=True)
    payment_nature = fields.Selection(PAYMENT_NATURE, copy=False, tracking=True)
    tax_classification = fields.Selection(
        TAX_CLASSIFICATION, string='Tax Type', copy=False, tracking=True,
        help='Defaults from the latest claim for this cost center and remains editable in Draft.')
    section = fields.Selection(
        SUPPLIER_SECTION, copy=False, tracking=True,
        help='Defaults from the latest claim for this cost center and remains editable in Draft.')
    review_round = fields.Integer(default=0, readonly=True, copy=False)
    resume_stage = fields.Selection(STATES, readonly=True, copy=False)
    rejection_department = fields.Selection([(d, d.replace('_', ' ').title()) for d in DEPARTMENTS], readonly=True,
                                            copy=False)
    rejection_reason = fields.Text(readonly=True, copy=False)
    secretarial_notes = fields.Text()
    # Inline binary storage protects evidence from direct ir.attachment mutations.
    attachment = fields.Binary(string='Attachment', attachment=False, copy=False)
    cheque_attachment = fields.Binary(attachment=False, copy=False)
    cheque_filename = fields.Char(copy=False)
    bank_cheque_attachment = fields.Binary(string='Cheque Attachment', attachment=False, copy=False)
    bank_cheque_filename = fields.Char(copy=False)
    history_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', 'claim_id', readonly=True, copy=False)
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

    can_edit_current_review = fields.Boolean(compute='_compute_can_edit_current_review')

    @api.depends('state', 'active', *(f'{department}_decision' for department in DEPARTMENTS))
    @api.depends_context('uid')
    def _compute_can_edit_current_review(self):
        is_admin = self._is_admin()
        allowed = {department for department in DEPARTMENTS
                   if is_admin or self.env.user.has_group(GROUP_PREFIX + department)}
        for claim in self:
            claim.can_edit_current_review = bool(
                claim.active and claim.state in allowed
                and claim[f'{claim.state}_decision'] in ('pending', 'deferred'))

    note_history_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', compute='_compute_note_history', readonly=True)

    @api.depends('history_ids', 'history_ids.reason', 'history_ids.cheque_attachment')
    def _compute_note_history(self):
        for claim in self:
            claim.note_history_ids = claim.history_ids.filtered(
                lambda entry: (entry.reason or '').strip() or entry.cheque_attachment)

    timeline_inventory_exception_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', compute='_compute_timeline_exceptions')
    timeline_purchasing_exception_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', compute='_compute_timeline_exceptions')
    timeline_supplier_accounts_exception_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', compute='_compute_timeline_exceptions')
    timeline_bank_accounts_exception_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', compute='_compute_timeline_exceptions')

    @api.depends('history_ids.event', 'history_ids.department', 'history_ids.decision')
    def _compute_timeline_exceptions(self):
        for claim in self:
            exceptions = claim.history_ids.filtered(
                lambda entry: entry.event == 'decision' and entry.decision in ('deferred', 'rejected'))
            for department in DEPARTMENTS:
                claim[f'timeline_{department}_exception_ids'] = exceptions.filtered(
                    lambda entry: entry.department == department).sorted('id')

    timeline_draft = fields.Text(compute='_compute_timeline_details')
    timeline_draft_date = fields.Datetime(compute='_compute_timeline_details')
    timeline_inventory = fields.Text(compute='_compute_timeline_details')
    timeline_inventory_date = fields.Datetime(compute='_compute_timeline_details')
    timeline_purchasing = fields.Text(compute='_compute_timeline_details')
    timeline_purchasing_date = fields.Datetime(compute='_compute_timeline_details')
    timeline_supplier_accounts = fields.Text(compute='_compute_timeline_details')
    timeline_supplier_accounts_date = fields.Datetime(compute='_compute_timeline_details')
    timeline_bank_accounts = fields.Text(compute='_compute_timeline_details')
    timeline_bank_accounts_date = fields.Datetime(compute='_compute_timeline_details')
    timeline_closure = fields.Text(compute='_compute_timeline_details')
    timeline_closure_date = fields.Datetime(compute='_compute_timeline_details')

    @api.depends('history_ids', 'history_ids.user_id.name', 'history_ids.occurred_at',
                 'history_ids.event', 'history_ids.department', 'create_uid.name', 'create_date')
    @api.depends_context('lang', 'tz')
    def _compute_timeline_details(self):
        for claim in self:
            latest = {}
            for event in claim.history_ids.sorted('id', reverse=True):
                stage = False
                if event.event == 'decision' and event.department in DEPARTMENTS:
                    stage = event.department
                elif event.event == 'closed':
                    stage = 'closure'
                elif event.event in ('resubmitted', 'secretarial_note'):
                    stage = 'draft'
                if stage and stage not in latest:
                    latest[stage] = event
            for stage in ('draft', *DEPARTMENTS, 'closure'):
                event = latest.get(stage)
                lines = []
                date = False
                if event:
                    lines = [event.user_id.display_name]
                    date = event.occurred_at
                elif stage == 'draft' and claim.create_date:
                    lines = [claim.create_uid.display_name]
                    date = claim.create_date
                claim['timeline_' + stage + '_date'] = date
                claim['timeline_' + stage] = '\n'.join(lines) or False

    def _last_claim_values_by_supplier(self, supplier_ids, exclude_ids=None):
        supplier_ids = {supplier_id for supplier_id in supplier_ids if supplier_id}
        exclude_ids = [record_id for record_id in (exclude_ids or []) if isinstance(record_id, int)]
        empty_values = {name: False for name in CLAIM_DEFAULT_FIELDS}
        result = {supplier_id: dict(empty_values) for supplier_id in supplier_ids}
        if not supplier_ids:
            return result

        domain = fields.Domain('supplier_id', 'in', supplier_ids)
        if exclude_ids:
            domain &= fields.Domain('id', 'not in', exclude_ids)
        previous_claims = self.with_context(active_test=False).search(
            domain,
            order='supplier_id, id desc',
        )
        found = set()
        for previous_claim in previous_claims:
            supplier_id = previous_claim.supplier_id.id
            if supplier_id not in found:
                result[supplier_id] = {
                    name: previous_claim[name]
                    for name in CLAIM_DEFAULT_FIELDS
                }
                found.add(supplier_id)
        return result

    @api.onchange('supplier_id')
    def _onchange_supplier_terms(self):
        draft_claims = self.filtered(lambda claim: claim.state == 'draft')
        values_by_supplier = self._last_claim_values_by_supplier(
            draft_claims.mapped('supplier_id').ids,
            exclude_ids=draft_claims._origin.ids,
        )
        empty_values = {name: False for name in CLAIM_DEFAULT_FIELDS}
        for claim in draft_claims:
            claim.update(values_by_supplier.get(claim.supplier_id.id, empty_values))

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
        return self.env.su or self.env.user.has_group(GROUP_PREFIX + 'admin') or self.env.user.has_group(
            'base.group_system')

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
        return {'state', 'user_id',
                'review_round', 'resume_stage', 'rejection_department', 'rejection_reason', 'history_ids'} | {
            f'{d}_decision' for d in DEPARTMENTS}

    @api.model_create_multi
    def create(self, vals_list):
        self._require_role('user')
        allowed = {'supplier_id', 'tax_classification', 'section', 'payment_nature', 'num_of_invoice',
                   'area', 'amount_of_check', 'type_of_invoice', 'secretarial_notes', 'attachment'}
        defaults = dict(state='draft', user_id=self.env.uid, review_round=0,
                        resume_stage=False,
                        rejection_department=False, rejection_reason=False, active=True, attachment=False,
                        cheque_attachment=False, cheque_filename=False,
                        bank_cheque_attachment=False, bank_cheque_filename=False)
        for d in DEPARTMENTS:
            defaults.update({f'{d}_decision': 'not_required', f'{d}_notes': False, f'{d}_followup_date': False})
        supplier_ids = {vals.get('supplier_id') or self.env.context.get('default_supplier_id') for vals in vals_list}
        values_by_supplier = self._last_claim_values_by_supplier(supplier_ids)
        clean = []
        for vals in vals_list:
            # Forms submit harmless defaults (including the invisible active flag).
            if any(name not in defaults or value != defaults[name]
                   for name, value in vals.items() if name not in allowed):
                raise AccessError(_('Create a draft claim without workflow values.'))
            supplier_id = vals.get('supplier_id') or self.env.context.get('default_supplier_id')
            previous_values = values_by_supplier.get(
                supplier_id,
                {name: False for name in CLAIM_DEFAULT_FIELDS},
            )
            clean.append({**previous_values, **vals, **defaults})
        # Explicit defaults neutralize forged default_* context values.
        claims = super().create(clean)
        claims._record_secretarial_notes()
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
        correction_fields = {
            'num_of_invoice', 'area', 'amount_of_check', 'type_of_invoice', 'secretarial_notes', 'attachment',
        }
        for claim in self:
            if claim.state in ('draft', 'returned_secretarial'):
                claim._require_role('user')
                allowed = correction_fields | ({'supplier_id', 'tax_classification', 'section', 'payment_nature'}
                                               if claim.state == 'draft' else set())
            else:
                allowed = set()
                for d in DEPARTMENTS:
                    if claim.state == STAGES[d] and claim[f'{d}_decision'] in ('pending', 'deferred'):
                        if claim._is_admin() or self.env.user.has_group(GROUP_PREFIX + d):
                            allowed |= {f'{d}_notes', f'{d}_followup_date'}
                            if d == 'supplier_accounts':
                                allowed |= {'cheque_attachment', 'cheque_filename'}
                            elif d == 'bank_accounts':
                                allowed |= {'bank_cheque_attachment', 'bank_cheque_filename'}
            if set(vals) - allowed:
                raise AccessError(_('You may only edit the fields assigned to your current stage.'))
        if 'supplier_id' in vals:
            values_by_supplier = self._last_claim_values_by_supplier(
                [vals['supplier_id']],
                exclude_ids=self.ids,
            )
            previous_values = values_by_supplier.get(
                vals['supplier_id'],
                {name: False for name in CLAIM_DEFAULT_FIELDS},
            )
            vals = {**previous_values, **vals}
        previous_notes = ({claim.id: (claim.secretarial_notes or '').strip() for claim in self}
                          if 'secretarial_notes' in vals else {})
        result = super().write(vals)
        if 'secretarial_notes' in vals:
            self.filtered(lambda claim: (claim.secretarial_notes or '').strip() != previous_notes[
                claim.id])._record_secretarial_notes()
        return result

    @api.ondelete(at_uninstall=True)
    def _prevent_claim_deletion(self):
        raise UserError(_('Archive claims instead of deleting them.'))

    def _workflow_write(self, vals):
        # Private RPC-inaccessible bypass, never controlled by a context flag.
        return super(SupplierClaimCycle, self.sudo()).write(vals)

    def _history_values(self, event, from_state=None, department=False, decision=False, reason=False,
                        followup_date=False):
        self.ensure_one()
        return {
            'claim_id': self.id, 'event': event, 'from_state': from_state or self.state, 'to_state': self.state,
            'department': department, 'decision': decision, 'reason': reason, 'followup_date': followup_date,
            'review_round': self.review_round, 'user_id': self.env.uid, 'occurred_at': fields.Datetime.now(),
            **{f'{d}_decision': self[f'{d}_decision'] for d in DEPARTMENTS},
            'tax_classification': self.tax_classification, 'section': self.section,
        }

    def _log(self, event, from_state=None, department=False, decision=False, reason=False, followup_date=False):
        self.env['ab_supplier_claim_cycle.history']._append([
            claim._history_values(event, from_state, department, decision, reason, followup_date) for claim in self])

    def _record_secretarial_notes(self):
        self.env['ab_supplier_claim_cycle.history']._append([
            claim._history_values('secretarial_note', department='secretarial', reason=claim.secretarial_notes.strip())
            for claim in self if (claim.secretarial_notes or '').strip()])

    def action_submit(self):
        self._require_role('user')
        self._prepare_action()
        if any(c.state not in ('draft', 'returned_secretarial') for c in self):
            raise UserError(_('Only draft or returned claims can be submitted.'))
        drafts = self.filtered(lambda c: c.state == 'draft')
        suppliers = drafts.mapped('supplier_id')
        suppliers.check_access('read')
        suppliers.lock_for_update(allow_referencing=True)
        suppliers.invalidate_recordset()
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
                stage = 'supplier_accounts' if claim.payment_nature == 'cash' else 'inventory'
                for d in DEPARTMENTS:
                    vals[f'{d}_decision'] = (
                        'pending' if claim.payment_nature != 'cash' or d == 'supplier_accounts'
                        else 'not_required'
                    )
            else:
                stage = claim.resume_stage
            if stage not in STAGES.values():
                raise ValidationError(_('The claim has no valid review stage to resume.'))
            vals['state'] = stage
            for d in DEPARTMENTS:
                if STAGES[d] == stage:
                    vals.update({f'{d}_decision': 'pending', f'{d}_notes': False,
                                 f'{d}_followup_date': fields.Date.context_today(claim)})
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
                        vals.update(state='bank_accounts', bank_accounts_decision='pending')
                else:
                    vals['state'] = 'ready_to_close'
            next_stage = vals.get('state')
            if next_stage in DEPARTMENTS:
                vals[f'{next_stage}_followup_date'] = fields.Date.context_today(claim)
            claim._workflow_write(vals)
            claim._log('decision', old_state, department, decision, reason,
                       followup if decision == 'deferred' else False)
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
