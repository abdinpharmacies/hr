from datetime import timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

STAGE_SEQUENCE = ('secretarial', 'inventory', 'purchase', 'suppliers', 'bank_acc', 'sign_check', 'supplier_notification', 'closed')
STAGE_LABELS = {
    'secretarial': 'Secretarial',
    'inventory': 'Inventory',
    'purchase': 'Purchase',
    'suppliers': 'Suppliers',
    'bank_acc': 'Bank Account',
    'sign_check': 'Sign Check',
    'supplier_notification': 'Supplier Notification',
    'closed': 'Check delivery',
}
STAGE_ORDER = {s: i for i, s in enumerate(STAGE_SEQUENCE)}


class SupplierClaimCycle(models.Model):
    _name = 'ab_supplier_claim_cycle'
    _description = 'Supplier Claim Cycle'
    _rec_name = 'supplier_id'
    _inherit = ['mail.thread']

    stage_history_ids = fields.One2many('ab_supplier_claim_stage_history', 'claim_id', string='Stage History', copy=False)

    supplier_id = fields.Many2one("ab_costcenter", required=True, tracking=True, domain=[("code", "=like", "1-%")])
    num_of_invoice = fields.Integer(required=True, tracking=True)
    status = fields.Selection(
        selection=[(s, STAGE_LABELS[s]) for s in STAGE_SEQUENCE],
        default='secretarial',
        required=True,
        tracking=True,
    )
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
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
    amount_of_check = fields.Char(required=True)
    type_of_invoice = fields.Selection(
        selection=[('original', 'Original'), ('copy', 'Copy')],
        required=True,
    )
    delay_reason = fields.Text(string="Delay / Rejection Reason", tracking=True)
    check_delivery_status = fields.Selection(
        selection=[('ready', 'Ready'), ('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'), ('check_delivered', 'Check Delivered'), ('shipped', 'Shipped')],
        string="Cheque Delivery Status",
        tracking=True,
    )
    supplier_notified = fields.Boolean(string="Supplier Notified", readonly=True, copy=False)
    supplier_notified_by = fields.Many2one('res.users', string="Notified By", readonly=True, copy=False)
    supplier_notification_date = fields.Datetime(string="Notification Date", readonly=True, copy=False)
    contact_name = fields.Char(string='Contact Name', readonly=True, copy=False)
    contact_phone = fields.Char(string='Contact Phone', readonly=True, copy=False)
    contact_result = fields.Selection(
        selection=[('contacted', 'Contacted'), ('already_delivered', 'Already Delivered')],
        string='Contact Result',
        tracking=True,
    )
    notification_notes = fields.Text(string="Notification Notes", tracking=True)
    can_current_user_edit = fields.Boolean(compute='_compute_workflow_access')
    can_current_user_act = fields.Boolean(compute='_compute_workflow_access')
    can_secretarial_override = fields.Boolean(compute='_compute_workflow_access')
    timeline_display = fields.Html(
        compute='_compute_timeline_display',
        sanitize=False,
        readonly=True,
    )

    def _get_stage_group_xmlids(self):
        return {
            'inventory': 'ab_supplier_claim_cycle.supplier_claim_group_inventory',
            'purchase': 'ab_supplier_claim_cycle.supplier_claim_group_purchase',
            'suppliers': 'ab_supplier_claim_cycle.supplier_claim_group_suppliers',
            'bank_acc': 'ab_supplier_claim_cycle.supplier_claim_group_bank_acc',
            'sign_check': 'ab_supplier_claim_cycle.supplier_claim_group_user',
            'supplier_notification': 'ab_supplier_claim_cycle.supplier_claim_group_user',
        }

    @api.depends_context('uid')
    @api.depends('status')
    def _compute_workflow_access(self):
        is_admin = self._is_supplier_claim_admin()
        is_secretarial = self._is_supplier_claim_secretarial()
        stage_groups = self._get_stage_group_xmlids()
        for rec in self:
            can_handle = rec.status != 'closed' and rec._user_can_handle_stage(rec.status, stage_groups)
            rec.can_current_user_act = can_handle
            rec.can_secretarial_override = rec.status != 'closed' and (is_admin or is_secretarial)
            rec.can_current_user_edit = is_admin or (rec.status != 'closed' and (is_secretarial or can_handle))

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
                if rec.status == 'closed' or not rec._user_can_handle_stage(rec.status):
                    raise AccessError(_("Only the current department can edit this supplier claim."))
        return super().write(vals)

    def action_accept(self):
        for rec in self:
            rec._check_can_act_current_stage()
            rec.with_context(supplier_claim_internal_write=True).write({
                'department_decision': 'accepted',
                'delay_reason': False,
            })
            rec._create_stage_history(rec.status, 'accepted')
            rec._notify_secretarial_department_accepted()

    def action_reject(self):
        for rec in self:
            rec._check_can_act_current_stage()
            if not rec.delay_reason:
                raise ValidationError(_("Rejection reason is required."))
            rec.with_context(supplier_claim_internal_write=True).write({'department_decision': 'rejected'})
            rec._create_stage_history(rec.status, 'rejected', rec.delay_reason)
            rec.message_post(
                body=_("%(stage)s rejected this supplier claim. Reason: %(reason)s") % {
                    'stage': rec._get_stage_label(rec.status),
                    'reason': rec.delay_reason,
                }
            )

    def action_done(self):
        for rec in self:
            rec._check_can_act_current_stage()
            if rec.department_decision != 'accepted':
                raise UserError(_("The current department must accept before confirming."))
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
            rec._move_to_next_stage()

    def action_admin_force_next(self):
        if not self._is_supplier_claim_secretarial() and not self._is_supplier_claim_admin():
            raise AccessError(_("Only Secretarial or Admin users can override the workflow."))
        for rec in self:
            rec._check_can_act_current_stage()
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
                raise UserError(_("Please select a Contact Result before confirming supplier notification."))
            if not rec.contact_name:
                raise UserError(_("Please enter your contact name."))
            if not rec.contact_phone:
                raise UserError(_("Please enter your contact phone."))
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
            rec._move_to_next_stage()

    def _move_to_next_stage(self):
        self.ensure_one()
        next_stage = self._get_next_stage()
        if not next_stage:
            raise UserError(_("This supplier claim is already closed."))
        if next_stage == 'closed' and not self.check_delivery_status:
            raise ValidationError(_("Cheque Delivery Status must be set before closing the claim."))
        old_status = self.status
        self.with_context(supplier_claim_internal_write=True).write({
            'status': next_stage,
            'department_decision': 'accepted' if next_stage == 'closed' else 'pending',
            'delay_reason': False,
        })
        self._create_stage_history(next_stage, 'pending')

    def _get_next_stage(self):
        self.ensure_one()
        if self.status not in STAGE_ORDER:
            raise UserError(_("Unknown stage: %s") % self.status)
        index = STAGE_ORDER[self.status]
        if index >= len(STAGE_SEQUENCE) - 1:
            return False
        return STAGE_SEQUENCE[index + 1]

    def _check_can_act_current_stage(self):
        self.ensure_one()
        if self.status == 'closed':
            raise UserError(_("Closed supplier claims cannot be changed."))
        if not self._user_can_handle_stage(self.status):
            raise AccessError(_("Only the current department, Secretarial, or Admin can perform this action."))

    @api.model
    def _user_can_handle_stage(self, stage, stage_groups=None):
        if self._is_supplier_claim_admin() or self._is_supplier_claim_secretarial():
            return True
        if stage_groups is None:
            stage_groups = self._get_stage_group_xmlids()
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

    def _notify_secretarial_department_accepted(self):
        self.ensure_one()
        secretarial_group = self.env.ref(
            'ab_supplier_claim_cycle.supplier_claim_group_user', raise_if_not_found=False
        )
        partner_ids = secretarial_group.sudo().user_ids.mapped('partner_id').ids if secretarial_group else []
        self.message_post(
            body=_(
                "%(stage)s accepted this supplier claim. "
                "Secretarial should notify the supplier for cheque collection."
            ) % {'stage': self._get_stage_label(self.status)},
            partner_ids=partner_ids,
        )

    def _get_stage_label(self, stage):
        return _(STAGE_LABELS.get(stage, stage))

    def _get_visible_event_stages(self):
        if self._is_supplier_claim_admin() or self._is_supplier_claim_secretarial():
            return list(STAGE_ORDER.keys())
        visible = []
        stage_groups = self._get_stage_group_xmlids()
        for stage, xmlid in stage_groups.items():
            if self.env.user.has_group(xmlid):
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
        for stage in STAGE_SEQUENCE:
            stage_histories = histories.filtered(lambda h: h.stage == stage)
            last = stage_histories[-1] if stage_histories else self.env['ab_supplier_claim_stage_history']
            is_current = stage == self.status
            is_completed = self.status == 'closed' or (
                some_history_exists
                and STAGE_ORDER.get(stage, 0) < STAGE_ORDER.get(self.status, 0)
            )

            stage_notes = last.notes or ''

            is_overdue = False
            if is_current and last and last.action_date:
                can_see_overdue = self._is_supplier_claim_admin() or self._is_supplier_claim_secretarial()
                is_overdue = can_see_overdue and fields.Datetime.now() - last.action_date > timedelta(seconds=9)

            timeline.append({
                'type': 'stage',
                'stage': stage,
                'label': STAGE_LABELS.get(stage, stage),
                'is_current': is_current,
                'is_completed': is_completed,
                'is_overdue': is_overdue,
                'user_name': last.user_id.display_name if last and last.user_id else '',
                'action_date': last.action_date.isoformat() if last and last.action_date else '',
                'notes': stage_notes,
            })

            for event in events_by_stage.get(stage, []):
                timeline.append(event)

        return {
            'timeline': timeline,
            'can_act': self.can_current_user_act,
            'can_secretarial_override': self.can_secretarial_override,
            'is_admin': self._is_supplier_claim_admin(),
        }

    @api.depends('status', 'stage_history_ids', 'stage_history_ids.decision', 'stage_history_ids.user_id', 'stage_history_ids.action_date', 'stage_history_ids.notes')
    def _compute_timeline_display(self):
        for rec in self:
            rec.timeline_display = rec._render_timeline_html()

    def _render_timeline_html(self):
        self.ensure_one()
        data = self.action_get_timeline_data()
        timeline = data['timeline']
        current_stage = next((s for s in timeline if s.get('type') == 'stage' and s.get('is_current')), None)

        L = ['<div style="display:flex;gap:32px;min-height:420px;">']

        L.append('<div style="flex:0 0 280px;position:relative;padding:8px 0 8px 0;">')

        for i, entry in enumerate(timeline):
            is_last = i == len(timeline) - 1

            if entry['type'] == 'stage':
                is_comp = entry['is_completed']
                is_curr = entry['is_current']
                is_overdue = entry.get('is_overdue', False)
                accent = '#dc3545' if is_overdue else '#e67e22'
                dot_color = '#28a745' if is_comp else (accent if is_curr else '#d0d0d0')
                bg_color = '#28a745' if is_comp else (accent if is_curr else '#fff')
                border = '2px solid #28a745' if is_comp else ('2px solid %s' % accent if is_curr else '2px solid #d0d0d0')
                txt_color = '#28a745' if is_comp and not is_curr else (accent if is_curr else '#999')
                icon = '✈' if (is_comp and entry['stage'] == 'closed') else ('✓' if is_comp else ('●' if is_curr else '○'))
                icon_text_color = '#fff' if is_comp else txt_color

                L.append('<div style="display:flex;align-items:stretch;min-height:%s;position:relative;">'
                         % ('52px' if not entry['notes'] else '66px'))
                L.append('<div style="display:flex;flex-direction:column;align-items:center;width:28px;flex-shrink:0;">')
                L.append(
                    '<div style="width:28px;height:28px;border-radius:50%%;display:flex;align-items:center;'
                    'justify-content:center;background:%s;border:%s;color:%s;font-size:13px;font-weight:700;'
                    'flex-shrink:0;z-index:1;">%s</div>'
                    % (bg_color, border, icon_text_color, icon)
                )
                if not is_last:
                    L.append('<div style="width:2px;flex:1;background:%s;margin:2px 0 0 0;"></div>' % dot_color)
                L.append('</div>')
                L.append('<div style="padding:2px 0 0 12px;flex:1;min-width:0;">')
                label_color = '#333' if is_comp or is_curr else '#bbb'
                L.append(
                    '<div style="font-weight:600;font-size:14px;color:%s;line-height:1.3;">%s</div>'
                    % (label_color, entry['label'])
                )
                if entry['notes']:
                    L.append(
                        '<div style="font-size:11px;color:#555;margin-top:1px;">%s</div>'
                        % entry['notes']
                    )
                if entry['stage'] == 'supplier_notification' and self.supplier_notified:
                    L.append(
                        '<div style="font-size:12px;color:#333;margin-top:4px;padding-top:4px;border-top:1px dashed #ddd;">'
                        '<div>%s</div><div>%s</div></div>'
                        % (self.contact_name or '', self.contact_phone or '')
                    )
                L.append('</div>')
                L.append('</div>')

            else:
                L.append('<div style="display:flex;align-items:stretch;min-height:60px;position:relative;">')
                L.append('<div style="display:flex;flex-direction:column;align-items:center;width:28px;flex-shrink:0;">')

                if entry['event_type'] == 'rejection':
                    ev_bg = '#dc3545'
                    ev_border = '2px solid #dc3545'
                    ev_icon = '✗'
                    ev_color = '#fff'
                elif entry['event_type'] == 'delay':
                    ev_bg = '#ffc107'
                    ev_border = '2px solid #ffc107'
                    ev_icon = '⚠'
                    ev_color = '#fff'
                else:
                    ev_bg = '#6c757d'
                    ev_border = '2px solid #6c757d'
                    ev_icon = '💬'
                    ev_color = '#fff'

                L.append(
                    '<div style="width:28px;height:28px;border-radius:50%%;display:flex;align-items:center;'
                    'justify-content:center;background:%s;border:%s;color:%s;font-size:13px;font-weight:700;'
                    'flex-shrink:0;z-index:1;">%s</div>'
                    % (ev_bg, ev_border, ev_color, ev_icon)
                )
                if not is_last:
                    L.append('<div style="width:2px;flex:1;background:#d0d0d0;margin:2px 0 0 0;"></div>')
                L.append('</div>')
                L.append('<div style="padding:2px 0 0 12px;flex:1;min-width:0;">')
                event_title = entry.get('event_type', 'Event').title()
                L.append(
                    '<div style="font-weight:600;font-size:13px;color:#dc3545;line-height:1.3;">%s</div>'
                    % event_title
                )
                if entry.get('user_name'):
                    L.append(
                        '<div style="font-size:11px;color:#666;margin-top:1px;">User: %s</div>'
                        % entry['user_name']
                    )
                if entry.get('notes'):
                    L.append(
                        '<div style="font-size:11px;color:#666;margin-top:1px;word-break:break-word;">'
                        'Reason: %s</div>'
                        % entry['notes']
                    )
                L.append('</div>')
                L.append('</div>')

        L.append('</div>')

        if current_stage:
            is_overdue = current_stage.get('is_overdue', False)
            overdue_badge = ''
            if is_overdue:
                overdue_badge = (
                    '<span style="display:inline-block;margin-left:8px;padding:2px 8px;'
                    'background:#dc3545;color:#fff;border-radius:4px;font-size:11px;font-weight:600;'
                    'vertical-align:middle;">⚠ Overdue</span>'
                )
            L.append(
                '<div style="flex:1;padding:16px 20px;background:%s;border-radius:8px;border:1px solid %s;">'
                % ('#fff5f5' if is_overdue else '#f8f9fa', '#f5c6cb' if is_overdue else '#e9ecef')
            )
            L.append(
                '<h3 style="margin:0 0 16px 0;font-size:16px;color:%s;font-weight:600;border-bottom:2px solid %s;'
                'padding-bottom:8px;">%s %s</h3>'
                % ('#dc3545' if is_overdue else '#333', '#dc3545' if is_overdue else '#dee2e6',
                   current_stage['label'], overdue_badge)
            )
            if current_stage.get('user_name'):
                L.append(
                    '<div style="margin-bottom:8px;"><span style="font-weight:600;color:#555;font-size:12px;">User: </span>'
                    '<span style="color:#333;font-size:13px;">%s</span></div>'
                    % current_stage['user_name']
                )
            if current_stage.get('action_date'):
                L.append(
                    '<div style="margin-bottom:8px;"><span style="font-weight:600;color:#555;font-size:12px;">Date: </span>'
                    '<span style="color:#333;font-size:13px;">%s</span></div>'
                    % current_stage['action_date']
                )
            if current_stage.get('notes'):
                L.append(
                    '<div style="margin-bottom:8px;"><span style="font-weight:600;color:#555;font-size:12px;">Notes: </span>'
                    '<span style="color:#333;font-size:13px;">%s</span></div>'
                    % current_stage['notes']
                )
            if current_stage['stage'] == 'sign_check' and (self._is_supplier_claim_admin() or self._is_supplier_claim_secretarial()):
                L.append(
                    '<div style="margin-top:12px;padding:8px 12px;background:#fff3cd;border-radius:6px;'
                    'border:1px solid #ffc107;font-size:13px;color:#856404;">'
                    '⚠ Please confirm that the supplier has been notified to visit the office and collect the cheque before closing the claim.</div>'
                )
            if current_stage['stage'] == 'supplier_notification' and self.supplier_notified:
                L.append(
                    '<div style="margin-bottom:8px;"><span style="font-weight:600;color:#555;font-size:12px;">Contact: </span>'
                    '<span style="color:#333;font-size:13px;">%s</span></div>'
                    % self.contact_name or ''
                )
                L.append(
                    '<div style="margin-bottom:8px;"><span style="font-weight:600;color:#555;font-size:12px;">Phone: </span>'
                    '<span style="color:#333;font-size:13px;">%s</span></div>'
                    % self.contact_phone or ''
                )
            L.append('</div>')
        else:
            L.append(
                '<div style="flex:1;padding:16px 20px;background:#f8f9fa;border-radius:8px;border:1px solid #e9ecef;'
                'display:flex;align-items:center;justify-content:center;color:#999;">'
                'No active stage</div>'
            )

        L.append('</div>')
        return '\n'.join(L)
