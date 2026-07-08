from datetime import timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

STAGE_SEQUENCE = ('secretarial', 'inventory', 'purchase', 'suppliers', 'tax_accounts', 'bank_acc', 'sign_check', 'supplier_notification', 'closed')
STAGE_LABELS = {
    'secretarial': 'Secretarial',
    'inventory': 'Inventory',
    'purchase': 'Purchase',
    'suppliers': 'Suppliers',
    'tax_accounts': 'Tax Accounts',
    'bank_acc': 'Bank Account',
    'sign_check': 'Sign Check',
    'supplier_notification': 'Supplier Notification',
    'closed': 'Check delivery',
}
STAGE_ORDER = {s: i for i, s in enumerate(STAGE_SEQUENCE)}
PARALLEL_DECISION_FIELDS = [
    ('inventory', 'inv_decision'),
    ('purchase', 'pur_decision'),
    ('suppliers', 'sup_decision'),
    ('tax_accounts', 'tax_decision'),
    ('bank_acc', 'bank_decision'),
]
DEPARTMENT_STAGES = ('inventory', 'purchase', 'suppliers', 'tax_accounts', 'bank_acc')
FINISHED_FIELD_MAP = {
    'inventory': 'inv_finished',
    'purchase': 'pur_finished',
    'suppliers': 'sup_finished',
    'tax_accounts': 'tax_finished',
    'bank_acc': 'bank_finished',
}
REASON_FIELD_MAP = {
    'inventory': 'inv_reason',
    'purchase': 'pur_reason',
    'suppliers': 'sup_reason',
    'tax_accounts': 'tax_reason',
    'bank_acc': 'bank_reason',
}
WITHHOLDING_TAX_SUPPLIER_TYPE = 'withholding_tax'


class SupplierClaimCycle(models.Model):
    _name = 'ab_supplier_claim_cycle'
    _description = 'Supplier Claim Cycle'
    _rec_name = 'name'
    _inherit = ['mail.thread']

    name = fields.Char(string='Claim Number', default=lambda self: self.env['ir.sequence'].next_by_code('ab.supplier.claim.cycle') or _('New'), required=True, readonly=True, copy=False, unique=True)
    stage_history_ids = fields.One2many('ab_supplier_claim_stage_history', 'claim_id', string='Stage History', copy=False)

    supplier_id = fields.Many2one("ab_costcenter", required=True, tracking=True, domain=[("code", "=like", "1-%")])
    supplier_type = fields.Selection(
        related='supplier_id.supplier_type', string='Supplier Type', readonly=True,
        selection=[
            ('advance_payment', 'دفعات مقدمة'),
            ('withholding_tax', 'خصم من المنبع'),
            ('non_taxable', 'غير ضريبي'),
        ],
    )
    supplier_email = fields.Char(related='supplier_id.work_email', string='Supplier Email', readonly=True)
    representative_phone = fields.Char(related='supplier_id.representative_phone', string='Representative Phone', readonly=True)
    num_of_invoice = fields.Integer(required=True, tracking=True)
    status = fields.Selection(
        selection=[(s, STAGE_LABELS[s]) for s in STAGE_SEQUENCE],
        default='secretarial',
        required=True,
        tracking=True,
    )
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)

    inv_decision = fields.Selection(
        selection=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')],
        default='pending', string='Inventory Decision')
    pur_decision = fields.Selection(
        selection=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')],
        default='pending', string='Purchase Decision')
    sup_decision = fields.Selection(
        selection=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')],
        default='pending', string='Suppliers Decision')
    tax_decision = fields.Selection(
        selection=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')],
        default='pending', string='Tax Accounts Decision')
    bank_decision = fields.Selection(
        selection=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')],
        default='pending', string='Bank Account Decision')
    inv_finished = fields.Boolean(default=False, string='Inventory Finished')
    pur_finished = fields.Boolean(default=False, string='Purchase Finished')
    sup_finished = fields.Boolean(default=False, string='Suppliers Finished')
    tax_finished = fields.Boolean(default=False, string='Tax Accounts Finished')
    bank_finished = fields.Boolean(default=False, string='Bank Account Finished')

    department_decision = fields.Selection(
        selection=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')],
        default='pending',
        required=True,
        tracking=True,
    )
    area = fields.Selection(
        selection=[('south', 'South'), ('north', 'North')],
        required=True,
    )
    amount_of_check = fields.Monetary(string='Check Amount', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    type_of_invoice = fields.Selection(
        selection=[('original', 'Original'), ('copy', 'Copy')],
        required=True,
    )
    delay_reason = fields.Text(string="Delay / Rejection Reason", tracking=True)
    inv_reason = fields.Text(string="Inventory Reason", copy=False)
    pur_reason = fields.Text(string="Purchase Reason", copy=False)
    sup_reason = fields.Text(string="Suppliers Reason", copy=False)
    tax_reason = fields.Text(string="Tax Accounts Reason", copy=False)
    bank_reason = fields.Text(string="Bank Account Reason", copy=False)
    check_delivery_status = fields.Selection(
        selection=[('ready', 'Ready'), ('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'),
                   ('check_delivered', 'Issue Check'),
                   ('mixed', 'Mixed (Bank Transfer + Cheque)'),
                   ('shipped', 'Shipped')],
        string="Cheque Delivery Status",
        tracking=True,
    )
    sub_delivery_status = fields.Selection(
        selection=[('ready', 'Ready'), ('shipped', 'Shipped')],
        string="Delivery Sub Status",
    )
    supplier_notified = fields.Boolean(string="Supplier Notified", readonly=True, copy=False)
    supplier_notified_by = fields.Many2one('res.users', string="Notified By", readonly=True, copy=False)
    supplier_notification_date = fields.Datetime(string="Notification Date", readonly=True, copy=False)
    contact_name = fields.Char(string='Contact Name', readonly=True, copy=False)
    contact_phone = fields.Char(string='Contact Phone', readonly=True, copy=False, sanitize=True)
    contact_result = fields.Selection(
        selection=[('contacted', 'Contacted'), ('already_delivered', 'Already Delivered')],
        string='Contact Result',
        tracking=True,
    )
    notification_notes = fields.Text(string="Notification Notes", tracking=True)
    supplier_claim_number = fields.Char(string="Supplier Reference Number", tracking=True)
    claim_document = fields.Binary(string="Claim Document", attachment=True, copy=False)
    claim_document_filename = fields.Char(string="Claim Document Filename")
    cheque_image = fields.Binary(string="Cheque Image", attachment=True, copy=False)
    cheque_image_filename = fields.Char(string="Cheque Image Filename")
    supplier_id_image = fields.Binary(string="Supplier ID Image", attachment=True, copy=False)
    supplier_id_image_filename = fields.Char(string="Supplier ID Image Filename")
    can_current_user_edit = fields.Boolean(compute='_compute_workflow_access')
    can_current_user_act = fields.Boolean(compute='_compute_workflow_access')
    can_secretarial_override = fields.Boolean(compute='_compute_workflow_access')
    can_edit_documents = fields.Boolean(compute='_compute_workflow_access')
    can_finish = fields.Boolean(compute='_compute_workflow_access')
    parallel_status_summary = fields.Html(
        compute='_compute_parallel_status_summary',
        sanitize=False,
        readonly=True,
    )
    department_decision_display = fields.Selection(
        selection=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('in_progress', 'In Progress')],
        compute='_compute_department_decision_display',
        readonly=True,
    )
    timeline_display = fields.Html(
        compute='_compute_timeline_display',
        sanitize=False,
        readonly=True,
    )
    claim_month = fields.Date(string='Claim Month', default=lambda self: fields.Date.context_today(self).replace(day=1))
    payment_method = fields.Selection(
        selection=[('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'),
                   ('cheque', 'Cheque'), ('mixed', 'Mixed (Bank Transfer + Cheque)')],
        string='Payment Method',
        tracking=True,
    )
    issue_ids = fields.One2many('ab.supplier.claim.issue', 'claim_id', string='Issues')
    has_blocking_issue = fields.Boolean(compute='_compute_has_blocking_issue')
    def _get_stage_group_xmlids(self):
        return {
            'inventory': 'ab_supplier_claim_cycle.supplier_claim_group_inventory',
            'purchase': 'ab_supplier_claim_cycle.supplier_claim_group_purchase',
            'suppliers': 'ab_supplier_claim_cycle.supplier_claim_group_suppliers',
            'tax_accounts': 'ab_supplier_claim_cycle.supplier_claim_group_tax_accounts',
            'bank_acc': 'ab_supplier_claim_cycle.supplier_claim_group_bank_acc',
            'sign_check': 'ab_supplier_claim_cycle.supplier_claim_group_user',
            'supplier_notification': 'ab_supplier_claim_cycle.supplier_claim_group_user',
        }

    def _requires_tax_accounts_stage(self):
        self.ensure_one()
        return self.supplier_type == WITHHOLDING_TAX_SUPPLIER_TYPE

    def _get_workflow_sequence(self):
        self.ensure_one()
        if self._requires_tax_accounts_stage():
            return STAGE_SEQUENCE
        return tuple(stage for stage in STAGE_SEQUENCE if stage != 'tax_accounts')

    def _get_parallel_decision_fields(self):
        self.ensure_one()
        if self.status in ('inventory', 'purchase'):
            return [('inventory', 'inv_decision'), ('purchase', 'pur_decision')]
        if self.status == 'suppliers':
            return [('suppliers', 'sup_decision')]
        if self.status == 'tax_accounts':
            return [('tax_accounts', 'tax_decision')]
        if self.status == 'bank_acc':
            return [('bank_acc', 'bank_decision')]
        return []

    @api.depends('issue_ids', 'issue_ids.resolved')
    def _compute_has_blocking_issue(self):
        for rec in self:
            rec.has_blocking_issue = any(not issue.resolved for issue in rec.issue_ids)

    @api.depends_context('uid')
    @api.depends(
        'status',
        'supplier_type',
        'inv_decision',
        'pur_decision',
        'sup_decision',
        'tax_decision',
        'bank_decision',
        'inv_finished',
        'pur_finished',
        'sup_finished',
        'tax_finished',
        'bank_finished',
        'has_blocking_issue',
    )
    def _compute_workflow_access(self):
        is_admin = self._is_supplier_claim_admin()
        is_secretarial = self._is_supplier_claim_secretarial()
        stage_groups = self._get_stage_group_xmlids()
        for rec in self:
            can_handle = False
            can_finish = False
            if rec.status != 'closed':
                if rec.status in DEPARTMENT_STAGES:
                    for stage_key, decision_field in rec._get_parallel_decision_fields():
                        group_xmlid = stage_groups.get(stage_key)
                        if group_xmlid and self.env.user.has_group(group_xmlid):
                            if rec[decision_field] != 'accepted':
                                can_handle = True
                                break
                    for stage_key, decision_field in rec._get_parallel_decision_fields():
                        group_xmlid = stage_groups.get(stage_key)
                        if group_xmlid and self.env.user.has_group(group_xmlid):
                            if rec[decision_field] == 'accepted' and not rec[FINISHED_FIELD_MAP[stage_key]]:
                                can_finish = True
                                break
                    if rec.has_blocking_issue and not is_admin and not is_secretarial:
                        can_handle = False
                        can_finish = False
                else:
                    can_handle = rec._user_can_handle_stage(rec.status, stage_groups)
            rec.can_current_user_act = can_handle
            rec.can_finish = can_finish
            rec.can_secretarial_override = rec.status != 'closed' and (is_admin or is_secretarial)
            rec.can_current_user_edit = is_admin or (rec.status != 'closed' and (is_secretarial or can_handle))
            rec.can_edit_documents = is_admin or (is_secretarial and rec.status != 'closed')

    @api.depends('supplier_type', 'status', 'inv_decision', 'pur_decision', 'sup_decision', 'tax_decision', 'bank_decision')
    def _compute_department_decision_display(self):
        for rec in self:
            decisions = [rec[df] for _, df in rec._get_parallel_decision_fields()]
            if all(d == 'pending' for d in decisions):
                rec.department_decision_display = 'pending'
            elif all(d == 'accepted' for d in decisions):
                rec.department_decision_display = 'accepted'
            elif any(d == 'rejected' for d in decisions):
                rec.department_decision_display = 'rejected'
            else:
                rec.department_decision_display = 'in_progress'

    @api.depends(
        'supplier_type',
        'inv_decision',
        'pur_decision',
        'sup_decision',
        'tax_decision',
        'bank_decision',
        'inv_finished',
        'pur_finished',
        'sup_finished',
        'tax_finished',
        'bank_finished',
        'status',
    )
    def _compute_parallel_status_summary(self):
        for rec in self:
            if rec.status not in DEPARTMENT_STAGES:
                rec.parallel_status_summary = False
                continue
            any_decided = any(
                rec[decision_field] != 'pending'
                for stage_key, decision_field in rec._get_parallel_decision_fields()
            )
            if not any_decided:
                rec.parallel_status_summary = '<div class="scc-parallel-pending"><span class="scc-parallel-icon">⏳</span><span class="o_translate_inline">Pending</span></div>'
                continue
            L = ['<div class="scc-parallel-grid">']
            has_pending = False
            for stage_key, decision_field in rec._get_parallel_decision_fields():
                decision = rec[decision_field]
                finished = rec[FINISHED_FIELD_MAP[stage_key]]
                label = STAGE_LABELS.get(stage_key, stage_key)
                if decision == 'accepted' and finished:
                    icon = '✔'
                    status_text = 'Finished'
                    css_class = 'scc-parallel-card is-accepted'
                elif decision == 'accepted' and not finished:
                    icon = '✔'
                    status_text = 'Accepted'
                    css_class = 'scc-parallel-card is-accepted'
                elif decision == 'rejected' and finished:
                    icon = '✗'
                    status_text = 'Finished'
                    css_class = 'scc-parallel-card is-rejected'
                elif decision == 'rejected' and not finished:
                    icon = '✗'
                    status_text = 'Rejected'
                    css_class = 'scc-parallel-card is-rejected'
                else:
                    has_pending = True
                    continue
                L.append('<div class="%s">' % css_class)
                L.append('<div class="scc-parallel-icon">%s</div>' % icon)
                L.append('<div class="scc-parallel-label">%s</div>' % label)
                L.append('<div class="scc-parallel-status">%s</div>' % status_text)
                L.append('</div>')
            if has_pending:
                L.append('<div class="scc-parallel-card is-pending"><div class="scc-parallel-icon">⏳</div><div class="scc-parallel-label o_translate_inline">Pending</div></div>')
            L.append('</div>')
            rec.parallel_status_summary = '\n'.join(L)

    def _create_stage_history(self, stage, decision, notes=None):
        self.ensure_one()
        return self.env['ab_supplier_claim_stage_history'].create({
            'claim_id': self.id,
            'stage': stage,
            'sequence': STAGE_ORDER.get(stage, 0),
            'decision': decision,
            'user_id': self.env.user.id,
            'action_date': fields.Datetime.now(),
            'notes': notes,
        })

    def name_get(self):
        result = []
        for rec in self:
            name = rec.name or _('New')
            supplier = rec.supplier_id.display_name or ''
            if supplier:
                display = '%s - %s' % (name, supplier)
            else:
                display = name
            result.append((rec.id, display))
        return result

    @api.model_create_multi
    def create(self, vals_list):
        if not self._is_supplier_claim_secretarial() and not self._is_supplier_claim_admin():
            raise AccessError(_("Only Secretarial or Admin users can create supplier claims."))
        for vals in vals_list:
            vals.setdefault('status', 'secretarial')
            vals['department_decision'] = 'accepted'
            if vals.get('status') != 'secretarial' and not self._is_supplier_claim_admin():
                raise AccessError(_("New supplier claims must start at Secretarial."))
        records = super().create(vals_list)
        for rec in records:
            rec._create_stage_history('secretarial', 'accepted', _('Created Request'))
        return records

    def write(self, vals):
        if self.env.context.get('supplier_claim_internal_write'):
            return super().write(vals)
        if 'status' in vals:
            raise AccessError(_("Use workflow actions to move supplier claims between stages."))
        if not self._is_supplier_claim_admin() and not self._is_supplier_claim_secretarial():
            for rec in self:
                if rec.status == 'closed':
                    raise AccessError(_("Only the current department can edit this supplier claim."))
                if rec.status in DEPARTMENT_STAGES:
                    can_write = any(
                        self.env.user.has_group(self._get_stage_group_xmlids()[sk])
                        for sk, _ in rec._get_parallel_decision_fields()
                    )
                    if not can_write:
                        raise AccessError(_("Only the current department can edit this supplier claim."))
                elif not rec._user_can_handle_stage(rec.status):
                    raise AccessError(_("Only the current department can edit this supplier claim."))
        return super().write(vals)

    def action_accept(self):
        for rec in self:
            rec._check_can_act_current_stage()
            if rec.status in DEPARTMENT_STAGES:
                rec._set_parallel_department_decision('accepted')
                rec._try_advance_from_parallel()
            else:
                rec.with_context(supplier_claim_internal_write=True).write({
                    'department_decision': 'accepted',
                    'delay_reason': False,
                })
                rec._create_stage_history(rec.status, 'accepted')
                rec._notify_secretarial_department_accepted()

    def action_reject(self):
        for rec in self:
            rec._check_can_act_current_stage()
            if rec.status in DEPARTMENT_STAGES:
                stage_groups = rec._get_stage_group_xmlids()
                user_stage = None
                user_reason = None
                for stage_key, decision_field in rec._get_parallel_decision_fields():
                    group_xmlid = stage_groups.get(stage_key)
                    if group_xmlid and self.env.user.has_group(group_xmlid):
                        user_stage = stage_key
                        user_reason = rec[REASON_FIELD_MAP[stage_key]]
                        break
                if not user_reason:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Missing Required Information'),
                        'res_model': 'ab.claim.error.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_error_message': _(
                                'The Delay / Rejection Reason field is required when rejecting a department request.'
                            ),
                        },
                    }
                rec._set_parallel_department_decision('rejected')
                reason_field = REASON_FIELD_MAP[user_stage]
                rec.with_context(supplier_claim_internal_write=True).write({reason_field: False})
            else:
                if not rec.delay_reason:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Missing Required Information'),
                        'res_model': 'ab.claim.error.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_error_message': _(
                                'The Delay / Rejection Reason field is required when rejecting.'
                            ),
                        },
                    }
                rec.with_context(supplier_claim_internal_write=True).write({'department_decision': 'rejected'})
                rec._create_stage_history(rec.status, 'rejected', rec.delay_reason)
                rec.message_post(
                    body=_("%(stage)s rejected this supplier claim. Reason: %(reason)s") % {
                        'stage': rec._get_stage_label(rec.status),
                        'reason': rec.delay_reason,
                    }
                )

    def action_finish(self):
        for rec in self:
            rec._check_can_act_current_stage()
            if rec.status not in DEPARTMENT_STAGES:
                raise UserError(_("Finish is only available during department review stages."))
            stage_groups = rec._get_stage_group_xmlids()
            finished = False
            for stage_key, decision_field in rec._get_parallel_decision_fields():
                group_xmlid = stage_groups.get(stage_key)
                if group_xmlid and self.env.user.has_group(group_xmlid):
                    if rec[decision_field] == 'pending':
                        raise UserError(_("You must Accept or Reject before finishing."))
                    rec.with_context(supplier_claim_internal_write=True).write({
                        FINISHED_FIELD_MAP[stage_key]: True,
                    })
                    finished = True
                    break
            if not finished:
                raise AccessError(_("You are not authorized to finish this stage."))
            rec._try_advance_from_parallel()

    def _set_parallel_department_decision(self, decision):
        self.ensure_one()
        stage_groups = self._get_stage_group_xmlids()
        for stage_key, decision_field in self._get_parallel_decision_fields():
            group_xmlid = stage_groups.get(stage_key)
            if group_xmlid and self.env.user.has_group(group_xmlid):
                vals = {decision_field: decision}
                dept_reason = self[REASON_FIELD_MAP[stage_key]] or ''
                if decision == 'rejected':
                    vals[REASON_FIELD_MAP[stage_key]] = dept_reason
                self.with_context(supplier_claim_internal_write=True).write(vals)
                self._create_stage_history(stage_key, decision, dept_reason if decision == 'rejected' else None)
                if decision == 'accepted':
                    self._notify_secretarial_department_accepted(stage_key)
                elif decision == 'rejected':
                    self.message_post(
                        body=_("%(stage)s rejected this supplier claim. Reason: %(reason)s") % {
                            'stage': self._get_stage_label(stage_key),
                            'reason': dept_reason,
                        }
                    )
                return
        raise AccessError(_("You are not authorized to act on this claim."))

    def _try_advance_from_parallel(self):
        self.ensure_one()
        if self.status not in DEPARTMENT_STAGES:
            return
        all_finished = all(
            self[decision_field] == 'accepted' and self[FINISHED_FIELD_MAP[sk]]
            for sk, decision_field in self._get_parallel_decision_fields()
        )
        if not all_finished:
            return
        if self.status in ('inventory', 'purchase'):
            next_stage = 'suppliers'
        elif self.status == 'suppliers':
            next_stage = 'tax_accounts' if self._requires_tax_accounts_stage() else 'bank_acc'
        elif self.status == 'tax_accounts':
            next_stage = 'bank_acc'
        elif self.status == 'bank_acc':
            next_stage = 'sign_check'
        else:
            next_stage = 'sign_check'
        self.with_context(supplier_claim_internal_write=True).write({
            'status': next_stage,
            'department_decision': 'pending',
            'delay_reason': False,
        })
        self._create_stage_history(next_stage, 'pending')

    def action_open_supplier_type_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Supplier Type Setup'),
            'res_model': 'ab.supplier.type.setup.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_supplier_id': self.supplier_id.id,
            },
        }

    def action_done(self):
        for rec in self:
            rec._check_can_act_current_stage()
            if rec.status == 'secretarial':
                if not rec.supplier_id.supplier_type:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Supplier Type Required'),
                        'res_model': 'ab.supplier.type.setup.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_supplier_id': rec.supplier_id.id,
                            'default_supplier_type': False,
                        },
                    }
                if not rec.num_of_invoice:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Missing Required Information'),
                        'res_model': 'ab.claim.error.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_error_message': _(
                                'Please enter the number of invoices.'
                            ),
                        },
                    }
                if not rec.amount_of_check:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Missing Required Information'),
                        'res_model': 'ab.claim.error.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_error_message': _(
                                'Please enter the cheque amount.'
                            ),
                        },
                    }
                if not rec.claim_document and not self.env['ir.attachment'].search_count([
                    ('res_model', '=', self._name),
                    ('res_id', '=', rec.id),
                ], limit=1):
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Missing Required Information'),
                        'res_model': 'ab.claim.error.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_error_message': _(
                                'Please upload the supplier claim document in the Claim Documents section before starting the cycle.'
                            ),
                        },
                    }
                rec.with_context(supplier_claim_internal_write=True).write({
                    'status': 'inventory',
                    'department_decision': 'pending',
                    'delay_reason': False,
                })
                rec._create_stage_history('inventory', 'pending')
                rec._create_stage_history('purchase', 'pending')
                return
            if rec.status == 'sign_check':
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Confirmation'),
                    'res_model': 'ab.check.delivery.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {'default_claim_id': rec.id},
                }
            rec._move_to_next_stage()

    def action_secretarial_force_next(self):
        if not self._is_supplier_claim_secretarial() and not self._is_supplier_claim_admin():
            raise AccessError(_("Only Secretarial or Admin users can override the workflow."))
        for rec in self:
            if rec.status in DEPARTMENT_STAGES:
                rec._reset_parallel_decisions()
                rec.with_context(supplier_claim_internal_write=True).write({
                    'status': 'sign_check',
                    'department_decision': 'pending',
                    'delay_reason': False,
                })
                rec._create_stage_history('sign_check', 'pending')
            else:
                rec._move_to_next_stage()

    def _reset_parallel_decisions(self):
        self.ensure_one()
        self.with_context(supplier_claim_internal_write=True).write({
            'inv_decision': 'pending',
            'pur_decision': 'pending',
            'sup_decision': 'pending',
            'tax_decision': 'pending',
            'bank_decision': 'pending',
            'inv_finished': False,
            'pur_finished': False,
            'sup_finished': False,
            'tax_finished': False,
            'bank_finished': False,
            'inv_reason': False,
            'pur_reason': False,
            'sup_reason': False,
            'tax_reason': False,
            'bank_reason': False,
        })

    def action_admin_force_next(self):
        if not self._is_supplier_claim_secretarial() and not self._is_supplier_claim_admin():
            raise AccessError(_("Only Secretarial or Admin users can override the workflow."))
        for rec in self:
            rec._check_can_act_current_stage()
            if rec.status in DEPARTMENT_STAGES:
                rec._reset_parallel_decisions()
                rec.with_context(supplier_claim_internal_write=True).write({
                    'status': 'sign_check',
                    'department_decision': 'pending',
                    'delay_reason': False,
                })
                rec._create_stage_history('sign_check', 'pending')
                return
            if rec.status == 'sign_check':
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Confirmation'),
                    'res_model': 'ab.check.delivery.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {'default_claim_id': rec.id},
                }
            rec._move_to_next_stage()

    def action_supplier_notified(self):
        for rec in self:
            rec._check_can_act_current_stage()
            if rec.status != 'supplier_notification':
                raise UserError(_("Supplier notification is only available at the Supplier Notification stage."))
            if not rec.contact_result:
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Missing Required Information'),
                    'res_model': 'ab.claim.error.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_error_message': _(
                            'Please select a Contact Result before confirming supplier notification.'
                        ),
                    },
                }
            if not rec.contact_name:
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Missing Required Information'),
                    'res_model': 'ab.claim.error.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_error_message': _(
                            'Please enter the contact name.'
                        ),
                    },
                }
            if not rec.contact_phone:
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Missing Required Information'),
                    'res_model': 'ab.claim.error.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_error_message': _(
                            'Please enter the contact phone.'
                        ),
                    },
                }
            if rec.check_delivery_status not in ('cash', 'bank_transfer'):
                if rec.check_delivery_status in ('check_delivered', 'mixed') and not rec.sub_delivery_status:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Missing Required Information'),
                        'res_model': 'ab.claim.error.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_error_message': _(
                                'Please select a sub status (Ready or Shipped) for cheque delivery.'
                            ),
                        },
                    }
                if not rec.cheque_image or not rec.supplier_id_image:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Missing Required Documents'),
                        'res_model': 'ab.claim.error.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_error_message': _(
                                'Please attach both the cheque image and supplier ID image before confirming supplier notification.'
                            ),
                        },
                    }
            rec.with_context(supplier_claim_internal_write=True).write({
                'supplier_notified': True,
                'supplier_notified_by': self.env.user.id,
                'supplier_notification_date': fields.Datetime.now(),
            })
            rec._create_stage_history('supplier_notification', 'accepted', rec.notification_notes or '')
            rec.message_post(
                body=_("Supplier notified by %(name)s (%(phone)s). Result: %(result)s. Notes: %(notes)s") % {
                    'name': rec.contact_name,
                    'phone': rec.contact_phone,
                    'result': dict(rec._fields['contact_result'].selection).get(rec.contact_result, ''),
                    'notes': rec.notification_notes or _("No notes"),
                }
            )

    def action_close_claim(self):
        for rec in self:
            rec._check_can_act_current_stage()
            if not rec.supplier_notified:
                raise UserError(_("Supplier must be marked as notified before closing the claim."))
            if not rec.check_delivery_status:
                raise UserError(_("Cheque Delivery Status must be set before closing the claim."))
            error = rec._validate_cheque_delivery_documents()
            if error:
                return error
            rec._move_to_next_stage()

    def _move_to_next_stage(self):
        self.ensure_one()
        next_stage = self._get_next_stage()
        if not next_stage:
            raise UserError(_("This supplier claim is already closed."))
        if next_stage == 'closed' and not self.check_delivery_status:
            raise ValidationError(_("Cheque Delivery Status must be set before closing the claim."))
        self.with_context(supplier_claim_internal_write=True).write({
            'status': next_stage,
            'department_decision': 'accepted' if next_stage == 'closed' else 'pending',
            'delay_reason': False,
        })
        self._create_stage_history(next_stage, 'pending')

    def _get_next_stage(self):
        self.ensure_one()
        workflow_sequence = self._get_workflow_sequence()
        if self.status not in workflow_sequence:
            raise UserError(_("Unknown stage: %s") % self.status)
        index = workflow_sequence.index(self.status)
        if index >= len(workflow_sequence) - 1:
            return False
        return workflow_sequence[index + 1]

    def _check_can_act_current_stage(self):
        self.ensure_one()
        if self.status == 'closed':
            raise UserError(_("Closed supplier claims cannot be changed."))
        if not self._user_can_handle_stage(self.status):
            raise AccessError(_("Only the current department, Secretarial, or Admin can perform this action."))

    def _user_can_handle_stage(self, stage, stage_groups=None):
        if self._is_supplier_claim_admin() or self._is_supplier_claim_secretarial():
            return True
        if stage_groups is None:
            stage_groups = self._get_stage_group_xmlids()

        if stage in DEPARTMENT_STAGES:
            return any(
                self.env.user.has_group(stage_groups[sk])
                for sk, _ in self._get_parallel_decision_fields()
                if sk in stage_groups
            )

        group_xmlid = stage_groups.get(stage)
        return bool(group_xmlid and self.env.user.has_group(group_xmlid))

    @api.model
    def _is_supplier_claim_admin(self):
        return self.env.uid == SUPERUSER_ID or self.env.user.has_group(
            'ab_supplier_claim_cycle.supplier_claim_group_admin'
        )

    @api.model
    def _is_supplier_claim_secretarial(self):
        return self.env.user.has_group('ab_supplier_claim_cycle.supplier_claim_group_user')

    def _notify_secretarial_department_accepted(self, stage=None):
        self.ensure_one()
        stage_label = self._get_stage_label(stage) if stage else self._get_stage_label(self.status)
        secretarial_group = self.env.ref(
            'ab_supplier_claim_cycle.supplier_claim_group_user', raise_if_not_found=False
        )
        partner_ids = secretarial_group.sudo().user_ids.mapped('partner_id').ids if secretarial_group else []
        self.message_post(
            body=_(
                "%(stage)s accepted this supplier claim. "
                "Secretarial should notify the supplier for cheque collection."
            ) % {'stage': stage_label},
            partner_ids=partner_ids,
        )

    def _get_stage_label(self, stage):
        return self._get_translated_stage_label(stage)

    def _get_translated_stage_label(self, stage):
        labels = {
            'secretarial': _('Secretarial'),
            'inventory': _('Inventory'),
            'purchase': _('Purchase'),
            'suppliers': _('Suppliers'),
            'tax_accounts': _('Tax Accounts'),
            'bank_acc': _('Bank Account'),
            'sign_check': _('Sign Check'),
            'supplier_notification': _('Supplier Notification'),
            'closed': _('Check delivery'),
        }
        return labels.get(stage, stage)

    def _get_visible_event_stages(self):
        if self._is_supplier_claim_admin() or self._is_supplier_claim_secretarial():
            return list(self._get_workflow_sequence())
        visible = []
        stage_groups = self._get_stage_group_xmlids()
        for stage, xmlid in stage_groups.items():
            if stage in self._get_workflow_sequence() and self.env.user.has_group(xmlid):
                visible.append(stage)
        return visible

    def action_get_timeline_data(self):
        self.ensure_one()
        histories = self.stage_history_ids.sorted(lambda h: (h.sequence, h.action_date or h.create_date))
        some_history_exists = bool(histories)

        visible_event_stages = self._get_visible_event_stages()
        events_by_stage = {}
        for h in histories:
            sk = h.stage
            if sk not in events_by_stage:
                events_by_stage[sk] = []
            if h.decision == 'rejected' and sk in visible_event_stages:
                events_by_stage[sk].append({
                    'type': 'event',
                    'event_type': 'rejection',
                    'user_name': h.user_id.display_name or '',
                    'action_date': h.action_date.isoformat() if h.action_date else '',
                    'notes': h.notes or '',
                })

        timeline = []
        workflow_sequence = self._get_workflow_sequence()
        workflow_order = {stage: index for index, stage in enumerate(workflow_sequence)}

        current_dept_decisions = dict(self._get_parallel_decision_fields()) if self.status in DEPARTMENT_STAGES else {}

        for stage in workflow_sequence:
            for event in events_by_stage.get(stage, []):
                timeline.append(event)

            stage_histories_all = histories.filtered(lambda h: h.stage == stage)

            last = stage_histories_all[-1] if stage_histories_all else self.env['ab_supplier_claim_stage_history']

            if stage in DEPARTMENT_STAGES:
                dept_df = current_dept_decisions.get(stage)
                if dept_df:
                    dept_decision = self[dept_df]
                    is_current = dept_decision == 'pending' and self.status in DEPARTMENT_STAGES and not self.has_blocking_issue
                    is_completed = dept_decision == 'accepted'
                else:
                    is_current = False
                    is_completed = (
                        some_history_exists
                        and workflow_order.get(stage, 0) < workflow_order.get(self.status, 0)
                    )
            else:
                is_current = stage == self.status
                is_completed = (
                    some_history_exists
                    and (
                        workflow_order.get(stage, 0) < workflow_order.get(self.status, 0)
                        or (self.status == 'closed' and stage == 'closed')
                    )
                )

            stage_notes = last.notes or ''

            is_overdue = False
            if is_current and last and last.action_date:
                can_see_overdue = self._is_supplier_claim_admin() or self._is_supplier_claim_secretarial()
                is_overdue = can_see_overdue and fields.Datetime.now() - last.action_date > timedelta(hours=24)

            parallel_decisions = {
                sk: {
                    'decision': self[df],
                    'finished': self[FINISHED_FIELD_MAP[sk]],
                }
                for sk, df in self._get_parallel_decision_fields()
            } if stage in DEPARTMENT_STAGES else None

            timeline.append({
                'type': 'stage',
                'stage': stage,
                'label': self._get_translated_stage_label(stage),
                'is_current': is_current,
                'is_completed': is_completed,
                'is_overdue': is_overdue,
                'user_name': last.user_id.display_name if last and last.user_id else '',
                'action_date': last.action_date.isoformat() if last and last.action_date else '',
                'notes': stage_notes,
                'parallel_decisions': parallel_decisions,
            })

        for issue in self.issue_ids:
            stage_index = workflow_order.get(issue.stage, 0)
            issue_entry = {
                'type': 'event',
                'event_type': 'blocking_issue' if not issue.resolved else 'resolved_issue',
                'issue_title': issue.title,
                'issue_description': issue.description or '',
                'user_name': issue.user_id.display_name or '',
                'action_date': issue.date.isoformat() if issue.date else '',
                'stage': issue.stage,
                'issue_id': issue.id,
                'resolved': issue.resolved,
                'resolved_by': issue.resolved_by.display_name if issue.resolved_by else '',
                'resolved_date': issue.resolved_date.isoformat() if issue.resolved_date else '',
            }
            insert_at = 0
            for j, entry in enumerate(timeline):
                if entry.get('type') == 'stage' and workflow_order.get(entry.get('stage', ''), 0) > stage_index:
                    insert_at = j
                    break
                insert_at = j + 1
            timeline.insert(insert_at, issue_entry)

        return {
            'timeline': timeline,
            'can_act': self.can_current_user_act,
            'can_secretarial_override': self.can_secretarial_override,
            'is_admin': self._is_supplier_claim_admin(),
            'has_blocking_issue': self.has_blocking_issue,
        }

    @api.depends(
        'status',
        'supplier_type',
        'stage_history_ids',
        'stage_history_ids.decision',
        'stage_history_ids.user_id',
        'stage_history_ids.action_date',
        'stage_history_ids.notes',
        'inv_decision',
        'pur_decision',
        'sup_decision',
        'tax_decision',
        'bank_decision',
        'has_blocking_issue',
        'issue_ids',
        'issue_ids.resolved',
    )
    def _compute_timeline_display(self):
        for rec in self:
            rec.timeline_display = rec._render_timeline_html()

    def _render_timeline_html(self):
        self.ensure_one()
        data = self.action_get_timeline_data()
        timeline = data['timeline']
        current_stage = next((s for s in timeline if s.get('type') == 'stage' and s.get('is_current')), None)

        L = ['<div class="scc-timeline">']
        L.append('<div class="scc-timeline-column">')

        for i, entry in enumerate(timeline):
            is_last = i == len(timeline) - 1

            if entry['type'] == 'stage':
                is_comp = entry['is_completed']
                is_curr = entry['is_current']
                is_overdue = entry.get('is_overdue', False)

                dot_class = 'scc-timeline-dot'
                if is_overdue:
                    dot_class += ' is-overdue'
                elif is_comp:
                    dot_class += ' is-completed'
                elif is_curr:
                    dot_class += ' is-current'
                else:
                    dot_class += ' is-pending'

                line_class = 'scc-timeline-line'
                if is_comp:
                    line_class += ' completed'
                elif is_curr:
                    line_class += ' current'
                else:
                    line_class += ' pending'

                label_class = 'scc-timeline-stage-label'
                if is_overdue:
                    label_class += ' overdue'
                elif is_comp:
                    label_class += ' completed'
                elif is_curr:
                    label_class += ' current'
                else:
                    label_class += ' pending'

                icon = '✈' if (is_comp and entry['stage'] == 'closed') else ('✓' if is_comp else ('●' if is_curr else '○'))

                stage_class = 'scc-timeline-stage'
                if entry['notes']:
                    stage_class += ' has-notes'

                L.append('<div class="%s">' % stage_class)
                L.append('<div class="scc-timeline-dot-col">')
                L.append('<div class="%s">%s</div>' % (dot_class, icon))
                if not is_last:
                    L.append('<div class="%s"></div>' % line_class)
                L.append('</div>')
                L.append('<div class="scc-timeline-label-col">')
                L.append('<div class="%s">%s</div>' % (label_class, entry['label']))
                if entry['notes']:
                    L.append('<div class="scc-timeline-notes">%s</div>' % entry['notes'])

                if entry['stage'] == 'supplier_notification' and self.supplier_notified:
                    L.append('<div class="scc-timeline-divider">%s<br/>%s</div>' % (self.contact_name or '', self.contact_phone or ''))
                L.append('</div>')
                L.append('</div>')

            else:
                dot_class = 'scc-timeline-dot'
                if entry['event_type'] == 'rejection':
                    dot_class += ' is-event-rejection'
                    ev_icon = '✗'
                elif entry['event_type'] == 'delay':
                    dot_class += ' is-event-delay'
                    ev_icon = '⚠'
                elif entry['event_type'] == 'blocking_issue':
                    dot_class += ' is-event-blocking'
                    ev_icon = '🔒'
                elif entry['event_type'] == 'resolved_issue':
                    dot_class += ' is-event-resolved'
                    ev_icon = '🔓'
                else:
                    dot_class += ' is-event-other'
                    ev_icon = '💬'

                L.append('<div class="scc-timeline-stage">')
                L.append('<div class="scc-timeline-dot-col">')
                L.append('<div class="%s">%s</div>' % (dot_class, ev_icon))
                if not is_last:
                    L.append('<div class="scc-timeline-line pending"></div>')
                L.append('</div>')
                L.append('<div class="scc-timeline-label-col">')
                event_title = {
                    'rejection': _('Rejection'),
                    'delay': _('Delay'),
                    'blocking_issue': _('Blocking Issue'),
                    'resolved_issue': _('Issue Resolved'),
                }.get(entry.get('event_type'), _('Event'))
                L.append('<div class="scc-timeline-event-label">%s</div>' % event_title)
                if entry.get('user_name'):
                    L.append('<div class="scc-timeline-meta">%s %s</div>' % (_('User:'), entry['user_name']))
                if entry.get('issue_title'):
                    L.append('<div class="scc-timeline-notes"><strong>%s:</strong> %s</div>' % (_('Issue'), entry['issue_title']))
                if entry.get('issue_description'):
                    L.append('<div class="scc-timeline-notes">%s</div>' % entry['issue_description'])
                if entry.get('resolved') and entry.get('resolved_by'):
                    L.append('<div class="scc-timeline-meta">%s %s</div>' % (_('Resolved by:'), entry['resolved_by']))
                L.append('</div>')
                L.append('</div>')

        L.append('</div>')

        if current_stage:
            is_overdue = current_stage.get('is_overdue', False)
            overdue_badge = ''
            if is_overdue:
                overdue_badge = '<span class="scc-overdue-badge">⚠ %s</span>' % _('Overdue')

            detail_class = 'scc-detail-card'
            if is_overdue:
                detail_class += ' is-overdue'

            title_class = 'scc-detail-title'
            if is_overdue:
                title_class += ' is-overdue'

            L.append('<div class="%s">' % detail_class)
            L.append('<h3 class="%s">%s %s</h3>' % (title_class, current_stage['label'], overdue_badge))

            user_html = current_stage['user_name']
            date_str = current_stage['action_date']

            if user_html or date_str:
                L.append('<div class="scc-stage-grid">')
            if user_html:
                L.append('<div class="scc-stage-field"><span class="scc-stage-field-label">%s</span><span class="scc-stage-field-value">%s</span></div>' % (_('User'), user_html))
            if date_str:
                L.append('<div class="scc-stage-field"><span class="scc-stage-field-label">%s</span><span class="scc-stage-field-value">%s</span></div>' % (_('Date'), date_str))
            if user_html or date_str:
                L.append('</div>')

            if current_stage.get('notes'):
                L.append('<div class="scc-detail-field"><span class="scc-detail-field-label">%s</span><span class="scc-detail-field-value">%s</span></div>' % (_('Notes'), current_stage['notes']))

            if self.has_blocking_issue:
                L.append('<div class="scc-detail-alert is-blocking"><span class="scc-detail-alert-icon">🔒</span><span><strong>%s</strong><br/>%s</span></div>' % (
                    _('Workflow Blocked'),
                    _('There is an unresolved blocking issue. Resolve it before proceeding.')
                ))

            if current_stage['stage'] == 'sign_check' and (self._is_supplier_claim_admin() or self._is_supplier_claim_secretarial()):
                L.append('<div class="scc-detail-alert"><span class="scc-detail-alert-icon">⚠</span><span>%s</span></div>' % _(
                    'Please confirm that the supplier has been notified to visit the office and collect the cheque before closing the claim.'
                ))

            if current_stage['stage'] == 'supplier_notification' and self.supplier_notified:
                L.append('<div class="scc-notification-card">')
                L.append('<div class="scc-notification-card-title">📞 %s</div>' % _('Supplier Contacted'))
                L.append('<div class="scc-notification-card-row"><strong>%s:</strong> %s</div>' % (_('Contact'), self.contact_name or ''))
                L.append('<div class="scc-notification-card-row"><strong>%s:</strong> %s</div>' % (_('Phone'), self.contact_phone or ''))
                L.append('</div>')

            L.append('</div>')
        else:
            L.append('<div class="scc-detail-card is-empty">%s</div>' % _('No active stage'))

        L.append('</div>')
        return '\n'.join(L)

    def _validate_cheque_delivery_documents(self):
        self.ensure_one()
        if self.check_delivery_status not in ('check_delivered', 'mixed'):
            return
        if not self.sub_delivery_status:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Missing Required Information'),
                'res_model': 'ab.claim.error.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_error_message': _(
                        'Please select a sub status (Ready or Shipped) for cheque delivery.'
                    ),
                },
            }
        if not self.cheque_image:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Missing Required Documents'),
                'res_model': 'ab.claim.error.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_error_message': _(
                        'Please attach the cheque image before confirming cheque delivery.'
                    ),
                },
            }
        if not self.supplier_id_image:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Missing Required Documents'),
                'res_model': 'ab.claim.error.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_error_message': _(
                        'Please attach the supplier ID image before confirming cheque delivery.'
                    ),
                },
            }
