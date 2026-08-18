import logging
import base64
import io
import re
import secrets
import urllib.parse

from datetime import timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import config
from odoo.tools.misc import format_datetime

_logger = logging.getLogger(__name__)

PHONE_DIGIT_TRANSLATION = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
STAGE_SEQUENCE = ('secretarial', 'inventory', 'purchase', 'suppliers', 'tax_accounts', 'bank_acc', 'sign_check', 'supplier_notification', 'delivery', 'closed')
STAGE_LABELS = {
    'secretarial': 'Secretarial',
    'inventory': 'Inventory',
    'purchase': 'Purchase',
    'suppliers': 'Suppliers',
    'tax_accounts': 'Tax Accounts',
    'bank_acc': 'Bank Account',
    'sign_check': 'Sign Check',
    'supplier_notification': 'Supplier Notification',
    'delivery': 'Delivery',
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
DEFER_REASON_FIELD_MAP = {
    'inventory': 'inv_deferred_reason',
    'purchase': 'pur_deferred_reason',
    'suppliers': 'sup_deferred_reason',
    'tax_accounts': 'tax_deferred_reason',
    'bank_acc': 'bank_deferred_reason',
}
DEFER_EXPECTED_DATE_FIELD_MAP = {
    'inventory': 'inv_deferred_expected_date',
    'purchase': 'pur_deferred_expected_date',
    'suppliers': 'sup_deferred_expected_date',
    'tax_accounts': 'tax_deferred_expected_date',
    'bank_acc': 'bank_deferred_expected_date',
}
DEFER_OVERDUE_DAYS_FIELD_MAP = {
    'inventory': 'inv_deferred_overdue_days',
    'purchase': 'pur_deferred_overdue_days',
    'suppliers': 'sup_deferred_overdue_days',
    'tax_accounts': 'tax_deferred_overdue_days',
    'bank_acc': 'bank_deferred_overdue_days',
}
WITHHOLDING_TAX_SUPPLIER_TYPE = 'withholding_tax'


class SupplierClaimCycle(models.Model):
    _name = 'ab_supplier_claim_cycle'
    _inherit = ['ab_supplier_claim_cycle', 'mail.activity.mixin']
    _description = 'Supplier Claim Cycle'
    _rec_name = 'name'

    name = fields.Char(string='Claim Number', default='New', required=True, readonly=True, copy=False)
    _uniq_name = models.Constraint('UNIQUE(name)', 'Claim number must be unique.')
    tracking_token = fields.Char(
        string='Tracking Token',
        default=lambda self: self._generate_tracking_token(),
        readonly=True,
        copy=False,
        index=True,
    )
    tracking_url = fields.Char(
        string='Tracking URL',
        compute='_compute_tracking_url',
        readonly=True,
    )
    tracking_qr_url = fields.Char(
        string='Tracking QR Code',
        compute='_compute_tracking_url',
        readonly=True,
    )
    tracking_first_accessed = fields.Datetime(readonly=True, copy=False)
    tracking_last_seen = fields.Datetime(string='Last Seen', readonly=True, copy=False)
    tracking_is_online = fields.Boolean(string='Online', readonly=True, copy=False)
    tracking_visit_ids = fields.One2many(
        'ab_supplier_claim_tracking_visit',
        'claim_id',
        string='Last Visits',
        readonly=True,
        copy=False,
    )
    tracking_visit_count = fields.Integer(
        string='Visits',
        compute='_compute_tracking_visit_stats',
        store=True,
    )
    tracking_last_visit = fields.Datetime(
        string='Last Visit',
        compute='_compute_tracking_visit_stats',
        store=True,
    )
    _uniq_tracking_token = models.Constraint('UNIQUE(tracking_token)', 'Tracking token must be unique.')
    stage_history_ids = fields.One2many('ab_supplier_claim_stage_history', 'claim_id', string='Stage History', copy=False)

    supplier_section = fields.Selection(
        related='supplier_id.section',
        string='Supplier Section',
        readonly=True,
    )
    supplier_type = fields.Selection(
        string='Supplier Type',
        selection=[
            ('advance_payment', 'Advance Payment'),
            ('withholding_tax', 'Withholding Tax'),
            ('non_taxable', 'Non-Taxable'),
        ],
        copy=False,
    )
    supplier_email = fields.Char(string='Supplier Email', copy=False)
    representative_phone = fields.Char(string='Representative Phone', copy=False)
    delegate_phone_ids = fields.Many2many('ab_delegate_phone', string='Delegate Phones',
        domain="[('partner_id', '=', supplier_id)]", copy=False, relation='claim_delegate_phone_rel')

    status = fields.Selection(
        selection=[(s, STAGE_LABELS[s]) for s in STAGE_SEQUENCE],
        default='secretarial',
        required=True,
        tracking=True,
    )

    inv_decision = fields.Selection(
        selection=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('deferred', 'Deferred')],
        default='pending', string='Inventory Decision')
    pur_decision = fields.Selection(
        selection=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('deferred', 'Deferred')],
        default='pending', string='Purchase Decision')
    sup_decision = fields.Selection(
        selection=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('deferred', 'Deferred')],
        default='pending', string='Suppliers Decision')
    tax_decision = fields.Selection(
        selection=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('deferred', 'Deferred')],
        default='pending', string='Tax Accounts Decision')
    bank_decision = fields.Selection(
        selection=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('deferred', 'Deferred')],
        default='pending', string='Bank Account Decision')
    inv_finished = fields.Boolean(default=False, string='Inventory Finished')
    pur_finished = fields.Boolean(default=False, string='Purchase Finished')
    sup_finished = fields.Boolean(default=False, string='Suppliers Finished')
    tax_finished = fields.Boolean(default=False, string='Tax Accounts Finished')
    bank_finished = fields.Boolean(default=False, string='Bank Account Finished')

    department_decision = fields.Selection(
        selection=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('deferred', 'Deferred')],
        default='pending',
        required=True,
        tracking=True,
    )
    inv_reason = fields.Text(string="Inventory Reason", copy=False)
    pur_reason = fields.Text(string="Purchase Reason", copy=False)
    sup_reason = fields.Text(string="Suppliers Reason", copy=False)
    tax_reason = fields.Text(string="Tax Accounts Reason", copy=False)
    bank_reason = fields.Text(string="Bank Account Reason", copy=False)
    inv_deferred_expected_date = fields.Date(string='Inventory Expected Completion Date', copy=False, tracking=True)
    pur_deferred_expected_date = fields.Date(string='Purchase Expected Completion Date', copy=False, tracking=True)
    sup_deferred_expected_date = fields.Date(string='Suppliers Expected Completion Date', copy=False, tracking=True)
    tax_deferred_expected_date = fields.Date(string='Tax Accounts Expected Completion Date', copy=False, tracking=True)
    bank_deferred_expected_date = fields.Date(string='Bank Account Expected Completion Date', copy=False, tracking=True)
    inv_deferred_reason = fields.Text(string='Inventory Deferral Reason', copy=False, tracking=True)
    pur_deferred_reason = fields.Text(string='Purchase Deferral Reason', copy=False, tracking=True)
    sup_deferred_reason = fields.Text(string='Suppliers Deferral Reason', copy=False, tracking=True)
    tax_deferred_reason = fields.Text(string='Tax Accounts Deferral Reason', copy=False, tracking=True)
    bank_deferred_reason = fields.Text(string='Bank Account Deferral Reason', copy=False, tracking=True)
    inv_deferred_overdue_days = fields.Integer(
        string='Inventory Actual Overdue Days', compute='_compute_deferred_overdue_days')
    pur_deferred_overdue_days = fields.Integer(
        string='Purchase Actual Overdue Days', compute='_compute_deferred_overdue_days')
    sup_deferred_overdue_days = fields.Integer(
        string='Suppliers Actual Overdue Days', compute='_compute_deferred_overdue_days')
    tax_deferred_overdue_days = fields.Integer(
        string='Tax Accounts Actual Overdue Days', compute='_compute_deferred_overdue_days')
    bank_deferred_overdue_days = fields.Integer(
        string='Bank Account Actual Overdue Days', compute='_compute_deferred_overdue_days')
    delay_reason = fields.Text(string="Rejection Reason", tracking=True)
    sub_delivery_status = fields.Selection(
        selection=[('ready', 'Delivered'), ('shipped', 'Shipped')],
        string="Delivery Sub Status",
    )
    supplier_notified = fields.Boolean(string="Supplier Notified", readonly=True, copy=False)
    supplier_notified_by = fields.Many2one('res.users', string="Notified By", readonly=True, copy=False)
    supplier_notification_date = fields.Datetime(string="Notification Date", readonly=True, copy=False)
    whatsapp_message_sent = fields.Boolean(string="WhatsApp Message Sent", readonly=True, copy=False)
    whatsapp_message_sent_by = fields.Many2one('res.users', string="WhatsApp Sent By", readonly=True, copy=False)
    whatsapp_message_sent_date = fields.Datetime(string="WhatsApp Sent Date", readonly=True, copy=False)
    contact_name = fields.Char(string='Contact Name', readonly=True, copy=False)
    contact_phone = fields.Char(string='Contact Phone', copy=False)
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
    is_dev_override = fields.Boolean(compute='_compute_dev_override')
    show_dev_override_badge = fields.Boolean(compute='_compute_dev_override')
    is_escalation_viewer = fields.Boolean(compute='_compute_escalation_viewer')
    parallel_status_summary = fields.Html(
        compute='_compute_parallel_status_summary',
        sanitize=False,
        readonly=True,
    )
    department_decision_display = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
            ('deferred', 'Deferred'),
            ('in_progress', 'In Progress'),
        ],
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
    issue_ids = fields.One2many('ab_supplier_claim_issue', 'claim_id', string='Issues')
    has_blocking_issue = fields.Boolean(compute='_compute_has_blocking_issue')
    show_chatter = fields.Boolean(string='Show Chatter', default=True)
    stage_escalated = fields.Boolean(default=False, string='Stage Escalated')
    escalation_missing_manager = fields.Boolean(default=False, string='Escalation Manager Not Found')
    assigned_escalation_user = fields.Many2one('res.users', string='Assigned Escalation User')
    escalation_ids = fields.One2many('ab_supplier_claim_escalation', 'claim_id', string='Escalations', copy=False)
    escalation_count = fields.Integer(compute='_compute_escalation_count', string='Escalation Count')
    has_pending_escalation = fields.Boolean(compute='_compute_has_pending_escalation', string='Has Pending Escalation',
                                            search='_search_has_pending_escalation')

    tax_percentage = fields.Float(string='Tax Percentage (%)', default=1.0, readonly=True)
    tax_amount = fields.Monetary(string='Withholding Tax', currency_field='currency_id',
                                  compute='_compute_tax', store=True, readonly=True)
    net_payable = fields.Monetary(string='Net Payable', currency_field='currency_id',
                                   compute='_compute_tax', store=True, readonly=True)
    tax_frozen = fields.Boolean(string='Tax Frozen', default=False, copy=False)
    tax_calculated_at = fields.Datetime(string='Tax Calculated At', readonly=True, copy=False)
    has_tax_accounts = fields.Boolean(compute='_compute_has_tax_accounts', string='Has Tax Accounts Stage')

    @api.depends('escalation_ids')
    def _compute_escalation_count(self):
        for rec in self:
            rec.escalation_count = len(rec.escalation_ids)

    @api.depends('escalation_ids.status', 'escalation_ids.current_stage')
    def _compute_has_pending_escalation(self):
        for rec in self:
            try:
                rec.has_pending_escalation = any(
                    e.status == 'pending' and e.current_stage == rec.status
                    for e in rec.escalation_ids
                )
            except Exception:
                rec.has_pending_escalation = False

    def _search_has_pending_escalation(self, operator, value):
        if operator not in ('=', '!='):
            raise NotImplementedError
        target = bool(value)
        esc = self.env['ab_supplier_claim_escalation']
        try:
            pending_claims = esc.search([('status', '=', 'pending')]).mapped('claim_id')
        except Exception:
            return [('id', '=', False)] if target else []
        if target:
            return [('id', 'in', pending_claims.ids)]
        return [('id', 'not in', pending_claims.ids)]

    @api.depends('amount_of_check', 'tax_percentage', 'tax_frozen')
    def _compute_tax(self):
        for rec in self:
            rec.tax_amount = rec.amount_of_check * (rec.tax_percentage / 100)
            rec.net_payable = rec.amount_of_check - rec.tax_amount

    @api.depends('supplier_type')
    def _compute_has_tax_accounts(self):
        for rec in self:
            rec.has_tax_accounts = rec.supplier_type == WITHHOLDING_TAX_SUPPLIER_TYPE

    @api.depends(
        'inv_decision', 'pur_decision', 'sup_decision', 'tax_decision', 'bank_decision',
        'inv_deferred_expected_date', 'pur_deferred_expected_date',
        'sup_deferred_expected_date', 'tax_deferred_expected_date',
        'bank_deferred_expected_date',
    )
    def _compute_deferred_overdue_days(self):
        today = fields.Date.context_today(self)
        decision_fields = dict(PARALLEL_DECISION_FIELDS)
        for rec in self:
            for stage_key, date_field in DEFER_EXPECTED_DATE_FIELD_MAP.items():
                overdue_field = DEFER_OVERDUE_DAYS_FIELD_MAP[stage_key]
                decision_field = decision_fields[stage_key]
                expected_date = rec[date_field]
                if rec[decision_field] == 'deferred' and expected_date and today > expected_date:
                    rec[overdue_field] = (today - expected_date).days
                else:
                    rec[overdue_field] = 0

    @api.model
    def _generate_tracking_token(self):
        token = secrets.token_urlsafe(32)
        while self.sudo().search_count([('tracking_token', '=', token)], limit=1):
            token = secrets.token_urlsafe(32)
        return token

    @api.depends('tracking_token', 'name')
    def _compute_tracking_url(self):
        base_url = self._get_tracking_base_url()
        for rec in self:
            if not rec.tracking_token or not base_url:
                rec.tracking_url = False
                rec.tracking_qr_url = False
                continue
            tracking_url = '%s/supplier-claim/%s/%s' % (
                base_url,
                urllib.parse.quote(rec.name or 'claim', safe=''),
                urllib.parse.quote(rec.tracking_token, safe=''),
            )
            rec.tracking_url = tracking_url
            rec.tracking_qr_url = rec._make_tracking_qr_data_uri(tracking_url, base_url)

    def _get_tracking_base_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        if not base_url:
            return ''
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.hostname not in ('127.0.0.1', 'localhost', '0.0.0.0') or parsed.port:
            return base_url
        http_port = config.get('http_port') or config.get('xmlrpc_port')
        try:
            http_port = int(http_port)
        except (TypeError, ValueError):
            return base_url
        if (parsed.scheme == 'http' and http_port == 80) or (parsed.scheme == 'https' and http_port == 443):
            return base_url
        netloc = parsed.hostname
        if parsed.username:
            userinfo = parsed.username
            if parsed.password:
                userinfo = '%s:%s' % (userinfo, parsed.password)
            netloc = '%s@%s' % (userinfo, netloc)
        return urllib.parse.urlunsplit((parsed.scheme, '%s:%s' % (netloc, http_port), parsed.path, '', ''))

    def _make_tracking_qr_data_uri(self, tracking_url, base_url):
        try:
            import qrcode
            from qrcode.image.svg import SvgImage
        except ImportError:
            return '%s/report/barcode/QR/%s?width=180&height=180' % (
                base_url,
                urllib.parse.quote(tracking_url, safe=''),
            )
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=3,
        )
        qr.add_data(tracking_url)
        qr.make(fit=True)
        image = qr.make_image(image_factory=SvgImage)
        output = io.BytesIO()
        image.save(output)
        encoded = base64.b64encode(output.getvalue()).decode('ascii')
        return 'data:image/svg+xml;base64,%s' % encoded

    def _ensure_tracking_token(self):
        for rec in self.sudo():
            if not rec.tracking_token:
                rec.with_context(supplier_claim_internal_write=True).write({
                    'tracking_token': rec._generate_tracking_token(),
                })
        return True

    @api.depends('tracking_visit_ids.visit_date')
    def _compute_tracking_visit_stats(self):
        for rec in self:
            visits = rec.tracking_visit_ids
            rec.tracking_visit_count = len(visits)
            rec.tracking_last_visit = visits[:1].visit_date if visits else False

    def _record_tracking_visit(self, ip_address='', user_agent=''):
        self.ensure_one()
        now = fields.Datetime.now()
        vals = {
            'tracking_last_seen': now,
            'tracking_is_online': True,
        }
        if not self.tracking_first_accessed:
            vals['tracking_first_accessed'] = now
        self.with_context(supplier_claim_internal_write=True).write(vals)
        self.env['ab_supplier_claim_tracking_visit'].sudo().create({
            'claim_id': self.id,
            'visit_date': now,
            'ip_address': ip_address or '',
            'user_agent': (user_agent or '')[:255],
        })
        return True

    def _set_tracking_presence(self, online=True):
        self.ensure_one()
        vals = {
            'tracking_last_seen': fields.Datetime.now(),
            'tracking_is_online': bool(online),
        }
        self.with_context(supplier_claim_internal_write=True).write(vals)
        return True

    @api.model
    def _backfill_tracking_tokens(self):
        seen_tokens = set()
        for claim in self.sudo().search([], order='id'):
            if claim.tracking_token and claim.tracking_token not in seen_tokens:
                seen_tokens.add(claim.tracking_token)
                continue
            token = self._generate_tracking_token()
            while token in seen_tokens:
                token = self._generate_tracking_token()
            claim.with_context(supplier_claim_internal_write=True).write({
                'tracking_token': token,
            })
            seen_tokens.add(token)
        return True

    @api.model
    def _find_by_tracking_token(self, tracking_token, claim_number=None):
        token = (tracking_token or '').strip()
        if not token:
            return self
        domain = [('tracking_token', '=', token)]
        if claim_number:
            domain.append(('name', '=', (claim_number or '').strip()))
        return self.sudo().search(domain, limit=1)

    def action_open_tracking_page(self):
        self.ensure_one()
        self._ensure_tracking_token()
        return {
            'type': 'ir.actions.act_url',
            'url': self.tracking_url,
            'target': 'new',
        }

    def action_open_tracking_dialog(self):
        self.ensure_one()
        self._ensure_tracking_token()
        action = self.env.ref('ab_supplier_claim_workflow.action_ab_supplier_claim_tracking').read()[0]
        action.update({
            'res_id': self.id,
            'target': 'new',
        })
        return action

    def action_copy_tracking_link(self):
        self.ensure_one()
        self._ensure_tracking_token()
        return {
            'type': 'ir.actions.client',
            'tag': 'supplier_claim_copy_tracking_link',
            'params': {
                'url': self.tracking_url,
            },
        }

    def _get_public_stage_history(self, stage, decisions=None):
        histories = self.stage_history_ids.filtered(lambda h: h.stage == stage)
        if decisions:
            histories = histories.filtered(lambda h: h.decision in decisions)
        return histories.sorted(lambda h: h.action_date or h.create_date)

    def _get_public_stage_event(self, stage, decision):
        histories = self._get_public_stage_history(stage, [decision])
        return histories[-1] if histories else self.env['ab_supplier_claim_stage_history']

    def _get_public_delay_info(self, timeline):
        sla_seconds = self._get_escalation_sla_seconds()
        now = fields.Datetime.now()
        for entry in timeline:
            if not entry.get('is_current'):
                continue
            pending_history = self._get_public_stage_event(entry['stage'], 'pending')
            if not pending_history or not pending_history.action_date:
                continue
            delay_date = pending_history.action_date + timedelta(seconds=sla_seconds)
            if now <= delay_date:
                continue
            return {
                'title': _('Delayed'),
                'stage': entry['stage'],
                'department': entry['label'],
                'reason': self.delay_reason or _('No delay reason was provided.'),
                'date': format_datetime(self.env, delay_date, dt_format='medium'),
            }
        return {}

    def _get_public_rejection_info(self):
        latest = self.env['ab_supplier_claim_stage_history']
        latest_accepted = {}
        for history in self.stage_history_ids.sorted(lambda h: h.action_date or h.create_date):
            if history.decision == 'accepted':
                latest_accepted[history.stage] = history.action_date or history.create_date
            if history.decision == 'rejected':
                accepted_date = latest_accepted.get(history.stage)
                history_date = history.action_date or history.create_date
                if not accepted_date or history_date > accepted_date:
                    latest = history
        if not latest:
            return {}
        return {
            'title': _('Rejected'),
            'stage': latest.stage,
            'department': self._get_translated_stage_label(latest.stage),
            'reason': latest.notes or _('No reason was provided.'),
            'date': format_datetime(self.env, latest.action_date, dt_format='medium') if latest.action_date else '',
        }

    def _get_public_escalation_info(self):
        latest = self.stage_history_ids.filtered(lambda h: h.decision == 'escalated').sorted(
            lambda h: h.action_date or h.create_date
        )
        if not latest:
            return {}
        history = latest[-1]
        return {
            'title': _('Escalated'),
            'message': _('This claim has been escalated.'),
            'department': self._get_translated_stage_label(history.stage),
            'date': format_datetime(self.env, history.action_date, dt_format='medium') if history.action_date else '',
        }

    def _get_public_current_status_text(self):
        self.ensure_one()
        if self.status == 'closed':
            return _('Completed')
        if self.supplier_notified:
            return _('Cheque Ready')
        if self.status == 'supplier_notification':
            return _('Waiting for Supplier Notification')
        return _('Waiting for %(department)s Department') % {
            'department': self._get_translated_stage_label(self.status),
        }

    def _get_public_activity_events(self):
        self.ensure_one()
        events = []
        histories = self.stage_history_ids.sorted(
            lambda h: h.action_date or h.create_date, reverse=True
        )[:5]
        for h in histories:
            stage_label = self._get_translated_stage_label(h.stage)
            action_label = dict(h._fields['decision'].selection).get(h.decision, h.decision)
            events.append({
                'type': 'stage_change',
                'stage': h.stage,
                'action': action_label,
                'label': stage_label,
                'user': h.user_id.display_name or '',
                'date': format_datetime(self.env, h.action_date or h.create_date, dt_format='medium'),
                'timestamp': str(h.action_date or h.create_date),
            })
        if not events:
            events.append({
                'type': 'created',
                'label': _('Claim Created'),
                'date': format_datetime(self.env, self.create_date, dt_format='medium'),
                'timestamp': str(self.create_date),
            })
        return events

    def _get_public_tracking_data(self):
        self.ensure_one()
        self._ensure_tracking_token()
        timeline_data = self.action_get_timeline_data()
        stage_entries = [
            entry for entry in timeline_data.get('timeline', [])
            if entry.get('type') == 'stage'
        ]
        rejection_info = self._get_public_rejection_info()
        delay_info = self._get_public_delay_info(stage_entries)
        escalation_info = self._get_public_escalation_info()

        timeline = []
        completed_count = 0
        for entry in stage_entries:
            stage = entry['stage']
            rejected = rejection_info and rejection_info.get('stage') == stage
            delayed = delay_info and delay_info.get('stage') == stage
            completed = bool(entry.get('is_completed')) and not rejected
            if completed:
                completed_count += 1
            state = 'completed' if completed else 'pending'
            icon = '✓' if completed else '○'
            if entry.get('is_current') and not completed:
                state = 'current'
                icon = '●'
            if rejected:
                state = 'rejected'
                icon = '✗'
            elif delayed:
                state = 'delayed'
                icon = '!'
            timeline.append({
                'stage': stage,
                'label': entry['label'],
                'state': state,
                'icon': icon,
                'is_current': bool(entry.get('is_current')),
            })

        total_stages = max(len(stage_entries), 1)
        progress = int(round((completed_count / total_stages) * 100))
        if self.status == 'closed':
            progress = 100

        now = fields.Datetime.now()
        created = self.create_date or now
        token_age = (now - created).days
        base_url = self._get_tracking_base_url()
        tracking_presence_url = ''
        if base_url and self.tracking_token:
            tracking_presence_url = '%s/supplier-claim-presence/%s/%s' % (
                base_url,
                urllib.parse.quote(self.name or 'claim', safe=''),
                urllib.parse.quote(self.tracking_token, safe=''),
            )

        return {
            'claim_number': self.name,
            'supplier_name': self.supplier_id.display_name or '',
            'current_status': self._get_public_current_status_text(),
            'current_department': self._get_translated_stage_label(self.status),
            'progress': progress,
            'timeline': timeline,
            'delay': delay_info,
            'rejection': rejection_info,
            'escalation': escalation_info,
            'supplier_notified': bool(self.supplier_notified),
            'notification_date': format_datetime(self.env, self.supplier_notification_date, dt_format='medium') if self.supplier_notification_date else '',
            'cheque_delivered': self.status == 'closed',
            'collection_date': format_datetime(self.env, self.write_date, dt_format='medium') if self.status == 'closed' and self.write_date else '',
            'tracking_url': self.tracking_url,
            'tracking_presence_url': tracking_presence_url,
            'tracking_qr_url': self.tracking_qr_url,
            'created_date': format_datetime(self.env, created, dt_format='medium'),
            'visit_count': self.tracking_visit_count,
            'last_visit': format_datetime(self.env, self.tracking_last_visit, dt_format='medium') if self.tracking_last_visit else '',
            'token_age_days': token_age,
            'is_online': self.tracking_is_online,
            'activity_events': self._get_public_activity_events(),
        }

    @api.onchange('supplier_id')
    def _onchange_supplier_id(self):
        if self.supplier_id:
            self.supplier_email = self.supplier_id.work_email or ''
            self.contact_phone = self._get_valid_supplier_master_contact_phone(self.supplier_id) or ''
            delegate_phones = self._get_supplier_delegate_phone_candidates(create_missing=False)
            if delegate_phones:
                self.delegate_phone_ids = [(6, 0, delegate_phones.ids)]
            if self.supplier_id.supplier_type:
                self.supplier_type = self.supplier_id.supplier_type
            if self.supplier_id.region:
                self.area = self.supplier_id.region

    def _split_delegate_phone_values(self, value):
        phones = []
        for phone in re.split(r'[,،;\n]+', value or ''):
            phone = phone.strip()
            if phone and phone not in phones:
                phones.append(phone)
        return phones

    def _get_supplier_delegate_phone_candidates(self, create_missing=False):
        self.ensure_one()
        if not self.supplier_id:
            return self.env['ab_delegate_phone']

        DelegatePhone = self.env['ab_delegate_phone'].sudo()
        existing = DelegatePhone.search([('partner_id', '=', self.supplier_id.id)], order='is_default desc, id')
        if existing:
            default_existing = existing.filtered('is_default')
            return default_existing or existing

        if not create_missing:
            return self.env['ab_delegate_phone']

        source_phone_text = self.supplier_id.mobile_phone or self.contact_phone or ''
        phones = self._split_delegate_phone_values(source_phone_text)
        delegates = DelegatePhone
        for index, phone in enumerate(phones):
            delegates |= DelegatePhone.create({
                'name': phone,
                'partner_id': self.supplier_id.id,
                'is_default': index == 0,
            })
        return delegates

    def _ensure_delegate_phone_selection(self):
        for rec in self:
            if rec.delegate_phone_ids or not rec.supplier_id:
                continue
            delegates = rec._get_supplier_delegate_phone_candidates(create_missing=True)
            if delegates:
                rec.with_context(supplier_claim_internal_write=True).write({
                    'delegate_phone_ids': [(6, 0, delegates.ids)],
                })
        return True

    def _get_delegate_phone_text(self):
        self.ensure_one()
        if self.delegate_phone_ids:
            return ', '.join(self.delegate_phone_ids.mapped('name'))
        return self.contact_phone or self.supplier_id.mobile_phone or ''

    def _get_supplier_mapping_phone_text(self):
        self.ensure_one()
        return self._normalize_contact_phone(self.contact_phone) or self._get_delegate_phone_text()

    def _sync_supplier_mapping_contact_phone(self):
        for rec in self:
            phone = rec._normalize_contact_phone(rec.contact_phone)
            if rec.supplier_id and phone:
                rec.supplier_id.sudo().write({'mobile_phone': phone})
        return True

    @api.model
    def _normalize_contact_phone(self, phone):
        return (phone or '').strip().translate(PHONE_DIGIT_TRANSLATION)

    @api.model
    def _is_valid_contact_phone(self, phone):
        normalized_phone = self._normalize_contact_phone(phone)
        return bool(re.fullmatch(r'\+?[0-9]{8,15}', normalized_phone))

    @api.model
    def _get_valid_supplier_master_contact_phone(self, supplier):
        phone = self._normalize_contact_phone(supplier.mobile_phone) if supplier else ''
        return phone if self._is_valid_contact_phone(phone) else False

    @api.constrains('contact_phone')
    def _check_contact_phone_format(self):
        for rec in self:
            if rec.contact_phone and not rec._is_valid_contact_phone(rec.contact_phone):
                raise ValidationError(_("Please enter a valid phone number using digits only."))

    def _calculate_and_freeze_tax(self):
        self.ensure_one()
        if self.tax_frozen:
            return
        self.tax_amount = self.amount_of_check * (self.tax_percentage / 100)
        self.net_payable = self.amount_of_check - self.tax_amount
        self.with_context(supplier_claim_internal_write=True).write({
            'tax_frozen': True,
            'tax_calculated_at': fields.Datetime.now(),
        })

    def _mail_activity_available(self):
        return bool(self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False))

    def _is_dev_override_enabled(self):
        return False

    def _get_dev_override_user(self):
        return self.env['res.users']

    def _get_effective_department_managers(self, stage_key=None):
        self.ensure_one()
        return self._resolve_escalation_details(stage_key=stage_key)['manager_users']

    def _format_stage_overdue_summary(self, stage_label):
        return _('Stage Overdue: %s') % stage_label

    def _format_stage_overdue_activity_note(self, manager, stage_label):
        return _(
            'Dear %(manager)s,\n'
            'The %(stage)s stage for claim %(name)s is overdue. '
            'Please review and take action.'
        ) % {
            'manager': manager.display_name,
            'stage': stage_label,
            'name': self.display_name,
        }

    def _send_external_escalation_notification(self, manager, stage_key=None):
        self.ensure_one()
        return False

    def _send_escalation_notification(self, manager, stage_key=None):
        self.ensure_one()
        manager_lang = manager.lang or self.env.lang
        localized_claim = self.with_context(lang=manager_lang)
        stage_label = localized_claim._get_stage_label(stage_key or self.status)
        if not self._mail_activity_available():
            self._create_internal_escalation(manager, stage_key=stage_key)
            method = 'internal_fallback'
        else:
            try:
                localized_claim.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=localized_claim._format_stage_overdue_summary(stage_label),
                    note=localized_claim._format_stage_overdue_activity_note(manager, stage_label),
                    user_id=manager.id,
                    date_deadline=fields.Date.today(),
                )
                method = 'odoo_activity'
            except Exception:
                self._create_internal_escalation(manager, stage_key=stage_key)
                method = 'internal_fallback'
        localized_claim._send_external_escalation_notification(manager, stage_key=stage_key)
        return method

    def _create_internal_escalation(self, manager, stage_key=None):
        self.ensure_one()
        current_stage = stage_key or self.status
        self.env['ab_supplier_claim_escalation'].create({
            'claim_id': self.id,
            'manager_id': manager.id,
            'department_name': self._get_stage_label(current_stage),
            'current_stage': current_stage,
            'method': 'internal_fallback',
            'notes': _('Automatic escalation triggered via internal fallback.'),
        })
        self.write({
            'assigned_escalation_user': manager.id,
        })

    def _get_stage_group_xmlids(self):
        return {
            'inventory': 'ab_supplier_claim_workflow.supplier_claim_group_inventory',
            'purchase': 'ab_supplier_claim_workflow.supplier_claim_group_purchase',
            'suppliers': 'ab_supplier_claim_workflow.supplier_claim_group_suppliers',
            'tax_accounts': 'ab_supplier_claim_workflow.supplier_claim_group_tax_accounts',
            'bank_acc': 'ab_supplier_claim_workflow.supplier_claim_group_bank_acc',
            'sign_check': 'ab_supplier_claim_cycle.supplier_claim_group_user',
            'supplier_notification': 'ab_supplier_claim_cycle.supplier_claim_group_user',
            'delivery': 'ab_supplier_claim_cycle.supplier_claim_group_user',
        }

    def _requires_tax_accounts_stage(self):
        self.ensure_one()
        return self.supplier_type == WITHHOLDING_TAX_SUPPLIER_TYPE

    def _requires_delivery_stage(self):
        self.ensure_one()
        return (
            self.status == 'delivery'
            or self.check_delivery_status == 'shipped'
            or self.sub_delivery_status == 'shipped'
            or bool(self.stage_history_ids.filtered(lambda h: h.stage == 'delivery'))
        )

    def _get_workflow_sequence(self):
        self.ensure_one()
        return tuple(
            stage for stage in STAGE_SEQUENCE
            if (
                (stage != 'tax_accounts' or self._requires_tax_accounts_stage())
                and (stage != 'delivery' or self._requires_delivery_stage())
            )
        )

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

    def _compute_dev_override(self):
        enabled = self._is_dev_override_enabled()
        is_match = False
        if enabled:
            dev_user = self._get_dev_override_user()
            is_match = bool(dev_user) and self.env.user == dev_user
        for rec in self:
            rec.is_dev_override = is_match
            rec.show_dev_override_badge = is_match

    def _compute_escalation_viewer(self):
        is_user = self.env.user.has_group('ab_supplier_claim_cycle.supplier_claim_group_user')
        is_admin = self._is_supplier_claim_admin()
        is_dev = False
        if self._is_dev_override_enabled():
            dev_user = self._get_dev_override_user()
            is_dev = bool(dev_user) and self.env.user == dev_user
        for rec in self:
            is_manager = self.env.user in rec._resolve_escalation_managers()
            rec.is_escalation_viewer = is_user or is_admin or is_manager or is_dev

    @api.depends('supplier_type', 'status', 'inv_decision', 'pur_decision', 'sup_decision', 'tax_decision', 'bank_decision')
    def _compute_department_decision_display(self):
        for rec in self:
            decisions = [rec[df] for _, df in rec._get_parallel_decision_fields()]
            if not decisions:
                rec.department_decision_display = rec.department_decision or 'pending'
            elif any(d == 'deferred' for d in decisions):
                rec.department_decision_display = 'deferred'
            elif all(d == 'pending' for d in decisions):
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
                rec.parallel_status_summary = '<div class="scc-parallel-pending"><span class="scc-parallel-icon">⏳</span><span class="o_translate_inline">%s</span></div>' % _('Pending')
                continue
            L = ['<div class="scc-parallel-grid">']
            has_pending = False
            for stage_key, decision_field in rec._get_parallel_decision_fields():
                decision = rec[decision_field]
                finished = rec[FINISHED_FIELD_MAP[stage_key]]
                label = self._get_translated_stage_label(stage_key)
                if decision == 'accepted' and finished:
                    icon = '✔'
                    status_text = _('Finished')
                    css_class = 'scc-parallel-card is-accepted'
                elif decision == 'accepted' and not finished:
                    icon = '✔'
                    status_text = _('Accepted')
                    css_class = 'scc-parallel-card is-accepted'
                elif decision == 'rejected' and finished:
                    icon = '✗'
                    status_text = _('Finished')
                    css_class = 'scc-parallel-card is-rejected'
                elif decision == 'rejected' and not finished:
                    icon = '✗'
                    status_text = _('Rejected')
                    css_class = 'scc-parallel-card is-rejected'
                elif decision == 'deferred':
                    icon = '⏸'
                    overdue_days = rec[DEFER_OVERDUE_DAYS_FIELD_MAP[stage_key]]
                    expected_date = rec[DEFER_EXPECTED_DATE_FIELD_MAP[stage_key]]
                    if overdue_days:
                        status_text = _('%(days)s days overdue') % {'days': overdue_days}
                    elif expected_date:
                        status_text = _('Deferred until %s') % expected_date
                    else:
                        status_text = _('Deferred')
                    css_class = 'scc-parallel-card is-pending'
                else:
                    has_pending = True
                    continue
                L.append('<div class="%s">' % css_class)
                L.append('<div class="scc-parallel-icon">%s</div>' % icon)
                L.append('<div class="scc-parallel-label">%s</div>' % label)
                L.append('<div class="scc-parallel-status">%s</div>' % status_text)
                L.append('</div>')
            if has_pending:
                L.append('<div class="scc-parallel-card is-pending"><div class="scc-parallel-icon">⏳</div><div class="scc-parallel-label o_translate_inline">%s</div></div>' % _('Pending'))
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
            self._normalize_check_delivery_status_vals(vals)
            amount = vals.get('amount_of_check')
            if not amount or float(amount) <= 0:
                raise ValidationError(_("Please enter the cheque amount."))
            if vals.get('supplier_id') and not vals.get('contact_phone'):
                supplier = self.env['ab_costcenter'].browse(vals['supplier_id'])
                vals['contact_phone'] = self._get_valid_supplier_master_contact_phone(supplier)
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('ab.supplier.claim.cycle') or _('New')
            vals.setdefault('tracking_token', self._generate_tracking_token())
            vals.setdefault('status', 'secretarial')
            vals['department_decision'] = 'accepted'
            if vals.get('status') != 'secretarial' and not self._is_supplier_claim_admin():
                raise AccessError(_("New supplier claims must start at Secretarial."))
        records = super().create(vals_list)
        for rec in records:
            rec._create_stage_history('secretarial', 'accepted', _('Created Request'))
            rec._notify_claim_created_to_module_users()
        records._sync_supplier_mapping_contact_phone()
        return records

    def _notify_claim_created_to_module_users(self):
        self.ensure_one()
        group_xmlids = [
            'ab_supplier_claim_cycle.supplier_claim_group_user',
            'ab_supplier_claim_cycle.supplier_claim_group_reviewer',
            'ab_supplier_claim_workflow.supplier_claim_group_inventory',
            'ab_supplier_claim_workflow.supplier_claim_group_purchase',
            'ab_supplier_claim_workflow.supplier_claim_group_suppliers',
            'ab_supplier_claim_workflow.supplier_claim_group_tax_accounts',
            'ab_supplier_claim_workflow.supplier_claim_group_bank_acc',
        ]
        excluded_group_xmlids = [
            'ab_supplier_claim_cycle.supplier_claim_group_admin',
            'base.group_system',
        ]
        users = self.env['res.users']
        for xmlid in group_xmlids:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                users |= group.sudo().user_ids

        excluded_users = self.env['res.users']
        for xmlid in excluded_group_xmlids:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                excluded_users |= group.sudo().user_ids

        partner_ids = (users - excluded_users).mapped('partner_id').ids
        if not partner_ids:
            return False
        self.message_post(
            body=_("New supplier claim %(claim)s was registered for %(supplier)s.") % {
                'claim': self.display_name,
                'supplier': self.supplier_id.display_name or '',
            },
            partner_ids=partner_ids,
        )
        return True

    def _notify_department_turn_started(self, stage_key):
        return False

    @api.model
    def _normalize_check_delivery_status_vals(self, vals):
        if 'check_delivery_status' not in vals or 'sub_delivery_status' in vals:
            return vals
        if vals['check_delivery_status'] in ('check_delivered', 'mixed'):
            vals['sub_delivery_status'] = 'shipped'
        elif vals['check_delivery_status'] in ('cash', 'bank_transfer', 'ready', False):
            vals['sub_delivery_status'] = False
        return vals

    def write(self, vals):
        vals = dict(vals)
        self._normalize_check_delivery_status_vals(vals)
        if 'supplier_id' in vals and 'contact_phone' not in vals:
            supplier = self.env['ab_costcenter'].browse(vals['supplier_id']) if vals['supplier_id'] else False
            vals['contact_phone'] = self._get_valid_supplier_master_contact_phone(supplier)
        if self.env.context.get('supplier_claim_internal_write'):
            result = super().write(vals)
            if 'contact_phone' in vals or 'supplier_id' in vals:
                self._sync_supplier_mapping_contact_phone()
            return result
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
        result = super().write(vals)
        if 'contact_phone' in vals or 'supplier_id' in vals:
            self._sync_supplier_mapping_contact_phone()
        return result

    def action_accept(self):
        for rec in self:
            rec._check_can_act_current_stage()
            if rec.status in DEPARTMENT_STAGES:
                rec._set_parallel_department_decision('accepted')
                if rec.status == 'tax_accounts' and rec._requires_tax_accounts_stage():
                    rec._calculate_and_freeze_tax()
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
                        'res_model': 'ab_claim_error_wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_error_message': _(
                                'The Rejection Reason field is required when rejecting a department request.'
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
                        'res_model': 'ab_claim_error_wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_error_message': _(
                                'The Rejection Reason field is required when rejecting.'
                            ),
                        },
                    }
                rec.with_context(supplier_claim_internal_write=True).write({'department_decision': 'rejected'})
                rec._create_stage_history(rec.status, 'rejected', rec.delay_reason)
                rec._create_stage_history(rec.status, 'pending')
                rec.message_post(
                    body=_("%(stage)s rejected this supplier claim. Reason: %(reason)s") % {
                        'stage': rec._get_stage_label(rec.status),
                        'reason': rec.delay_reason,
                    }
                )

    def action_defer(self):
        for rec in self:
            rec._check_can_act_current_stage()
            if rec.status not in DEPARTMENT_STAGES:
                raise UserError(_("Deferral is only available during department review stages."))
            stage_key = rec._get_user_parallel_stage()
            if not stage_key:
                raise AccessError(_("You are not authorized to defer this claim."))
            date_field = DEFER_EXPECTED_DATE_FIELD_MAP[stage_key]
            reason_field = DEFER_REASON_FIELD_MAP[stage_key]
            if not rec[date_field] or not rec[reason_field]:
                return rec._defer_wizard_action(stage_key, date_field, reason_field)
            rec._set_parallel_department_decision('deferred')

    def _defer_wizard_action(self, stage_key, date_field, reason_field):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Defer Supplier Claim'),
            'res_model': 'ab_supplier_claim_defer_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_claim_id': self.id,
                'default_stage_key': stage_key,
                'default_expected_completion_date': self[date_field],
                'default_deferral_reason': self[reason_field],
            },
        }

    @api.model
    def _get_defer_expected_date_field(self, stage_key):
        return DEFER_EXPECTED_DATE_FIELD_MAP.get(stage_key)

    @api.model
    def _get_defer_reason_field(self, stage_key):
        return DEFER_REASON_FIELD_MAP.get(stage_key)

    def _get_deferred_actual_overdue_days(self, stage_key):
        self.ensure_one()
        date_field = self._get_defer_expected_date_field(stage_key)
        expected_date = self[date_field] if date_field else False
        if not expected_date:
            return 0
        return max((fields.Date.context_today(self) - expected_date).days, 0)

    def _format_deferred_stage_history_note(self, stage_key):
        self.ensure_one()
        date_field = self._get_defer_expected_date_field(stage_key)
        reason_field = self._get_defer_reason_field(stage_key)
        return _(
            'Expected completion date: %(date)s\n'
            'Reason: %(reason)s\n'
            'Actual overdue days: %(days)s'
        ) % {
            'date': self[date_field] if date_field else '',
            'reason': self[reason_field] if reason_field else '',
            'days': self._get_deferred_actual_overdue_days(stage_key),
        }

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
                    if rec[decision_field] == 'deferred':
                        raise UserError(_("Deferred requests cannot be finished until they are accepted or rejected."))
                    rec.with_context(supplier_claim_internal_write=True).write({
                        FINISHED_FIELD_MAP[stage_key]: True,
                    })
                    finished = True
                    break
            if not finished:
                raise AccessError(_("You are not authorized to finish this stage."))
            rec._try_advance_from_parallel()

    def _missing_info_action(self, message):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Missing Required Information'),
            'res_model': 'ab_claim_error_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_error_message': message,
            },
        }

    def _get_user_parallel_stage(self):
        self.ensure_one()
        stage_groups = self._get_stage_group_xmlids()
        for stage_key, _decision_field in self._get_parallel_decision_fields():
            group_xmlid = stage_groups.get(stage_key)
            if group_xmlid and self.env.user.has_group(group_xmlid):
                return stage_key
        return False

    def _get_parallel_overall_decision(self):
        self.ensure_one()
        decisions = [self[decision_field] for _stage_key, decision_field in self._get_parallel_decision_fields()]
        if not decisions:
            return self.department_decision or 'pending'
        if any(decision == 'deferred' for decision in decisions):
            return 'deferred'
        if any(decision == 'rejected' for decision in decisions):
            return 'rejected'
        if all(decision == 'accepted' for decision in decisions):
            return 'accepted'
        return 'pending'

    def _set_parallel_department_decision(self, decision):
        self.ensure_one()
        stage_groups = self._get_stage_group_xmlids()
        for stage_key, decision_field in self._get_parallel_decision_fields():
            group_xmlid = stage_groups.get(stage_key)
            if group_xmlid and self.env.user.has_group(group_xmlid):
                vals = {decision_field: decision}
                dept_reason = self[REASON_FIELD_MAP[stage_key]] or ''
                if decision == 'deferred':
                    dept_reason = self[DEFER_REASON_FIELD_MAP[stage_key]] or ''
                if decision == 'rejected':
                    vals[REASON_FIELD_MAP[stage_key]] = dept_reason
                self.with_context(supplier_claim_internal_write=True).write(vals)
                if decision == 'accepted':
                    self._create_stage_history(stage_key, decision)
                    self.with_context(supplier_claim_internal_write=True).write({
                        'department_decision': self._get_parallel_overall_decision(),
                    })
                    self._notify_secretarial_department_accepted(stage_key)
                elif decision == 'rejected':
                    self._create_stage_history(stage_key, decision, dept_reason)
                    self.with_context(supplier_claim_internal_write=True).write({
                        'department_decision': self._get_parallel_overall_decision(),
                    })
                    self._create_stage_history(stage_key, 'pending')
                    self.message_post(
                        body=_("%(stage)s rejected this supplier claim. Reason: %(reason)s") % {
                            'stage': self._get_stage_label(stage_key),
                            'reason': dept_reason,
                        }
                    )
                elif decision == 'deferred':
                    expected_date = self[DEFER_EXPECTED_DATE_FIELD_MAP[stage_key]]
                    self.with_context(supplier_claim_internal_write=True).write({
                        'department_decision': self._get_parallel_overall_decision(),
                    })
                    self._create_stage_history(
                        stage_key,
                        decision,
                        self._format_deferred_stage_history_note(stage_key),
                    )
                    self.message_post(
                        body=_("%(stage)s deferred this supplier claim until %(date)s. Reason: %(reason)s") % {
                            'stage': self._get_stage_label(stage_key),
                            'date': expected_date,
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
            'stage_escalated': False,
            'escalation_missing_manager': False,
            'assigned_escalation_user': False,
        })
        self._create_stage_history(next_stage, 'pending')
        self._notify_department_turn_started(next_stage)

    def action_toggle_chatter(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'toggle_claim_chatter',
        }

    def action_done(self):
        for rec in self:
            rec._check_can_act_current_stage()
            if rec.status == 'secretarial':
                if not rec.supplier_type:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Supplier Type Required'),
                        'res_model': 'ab_supplier_type_setup_wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_supplier_id': rec.supplier_id.id,
                            'default_claim_id': rec.id,
                            'default_supplier_type': False,
                        },
                    }
                if not rec.num_of_invoice:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Missing Required Information'),
                        'res_model': 'ab_claim_error_wizard',
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
                        'res_model': 'ab_claim_error_wizard',
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
                        'res_model': 'ab_claim_error_wizard',
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
                    'stage_escalated': False,
                    'escalation_missing_manager': False,
                    'assigned_escalation_user': False,
                })
                rec._create_stage_history('inventory', 'pending')
                rec._create_stage_history('purchase', 'pending')
                rec._notify_department_turn_started('inventory')
                rec._notify_department_turn_started('purchase')
                return
            if rec.status == 'sign_check':
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Confirmation'),
                    'res_model': 'ab_check_delivery_wizard',
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
                    'stage_escalated': False,
                    'escalation_missing_manager': False,
                    'assigned_escalation_user': False,
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
            'inv_deferred_expected_date': False,
            'pur_deferred_expected_date': False,
            'sup_deferred_expected_date': False,
            'tax_deferred_expected_date': False,
            'bank_deferred_expected_date': False,
            'inv_deferred_reason': False,
            'pur_deferred_reason': False,
            'sup_deferred_reason': False,
            'tax_deferred_reason': False,
            'bank_deferred_reason': False,
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
                    'stage_escalated': False,
                    'escalation_missing_manager': False,
                    'assigned_escalation_user': False,
                })
                rec._create_stage_history('sign_check', 'pending')
                return
            if rec.status == 'sign_check':
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Confirmation'),
                    'res_model': 'ab_check_delivery_wizard',
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
                    'res_model': 'ab_claim_error_wizard',
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
                    'res_model': 'ab_claim_error_wizard',
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
                    'res_model': 'ab_claim_error_wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_error_message': _(
                            'Please enter the contact phone.'
                        ),
                    },
                }
            if not rec._is_valid_contact_phone(rec.contact_phone):
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Missing Required Information'),
                    'res_model': 'ab_claim_error_wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_error_message': _(
                            'Please enter a valid phone number using digits only.'
                        ),
                    },
                }
            if rec.check_delivery_status in ('check_delivered', 'mixed') and not rec.sub_delivery_status:
                rec.with_context(supplier_claim_internal_write=True).write({
                    'sub_delivery_status': 'shipped',
                })
            if rec.check_delivery_status not in ('cash', 'bank_transfer'):
                if not rec.cheque_image or not rec.supplier_id_image:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Missing Required Documents'),
                        'res_model': 'ab_claim_error_wizard',
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
            rec._ensure_delegate_phone_selection()
            rec.supplier_id.sudo().write({
                'work_email': rec.supplier_email or '',
                'mobile_phone': rec._get_supplier_mapping_phone_text(),
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
            if rec.check_delivery_status in ('check_delivered', 'mixed'):
                rec.with_context(supplier_claim_internal_write=True).write({
                    'status': 'delivery',
                    'sub_delivery_status': 'shipped',
                    'department_decision': 'pending',
                    'delay_reason': False,
                    'stage_escalated': False,
                    'escalation_missing_manager': False,
                    'assigned_escalation_user': False,
                })
                rec._create_stage_history('delivery', 'pending')

    def _get_supplier_whatsapp_phone(self):
        self.ensure_one()
        phone = re.sub(r'\D+', '', self._normalize_contact_phone(self.contact_phone))
        if phone.startswith('00'):
            phone = phone[2:]
        elif phone.startswith('0'):
            phone = '20%s' % phone[1:]
        return phone if 8 <= len(phone) <= 15 else ''

    def _requires_whatsapp_notification(self):
        self.ensure_one()
        return self.check_delivery_status in ('check_delivered', 'mixed')

    def action_open_supplier_whatsapp(self):
        for rec in self:
            if not rec._is_supplier_claim_admin() and not rec._is_supplier_claim_secretarial():
                raise AccessError(_("Only Secretarial or Admin users can contact the supplier."))
            if not rec._requires_whatsapp_notification():
                raise UserError(_("WhatsApp notification is only required for cheque delivery claims."))
            if rec.status not in ('supplier_notification', 'delivery') or not rec.supplier_notified:
                raise UserError(_("WhatsApp notification is only available after the supplier is marked as notified."))
            phone = rec._get_supplier_whatsapp_phone()
            if not phone:
                raise UserError(_("Please enter a valid contact phone before sending a WhatsApp message."))
            message = _(
                "Hello, please visit the office to collect your cheque for supplier claim %(claim)s."
            ) % {'claim': rec.name}
            rec.with_context(supplier_claim_internal_write=True).write({
                'whatsapp_message_sent': True,
                'whatsapp_message_sent_by': self.env.user.id,
                'whatsapp_message_sent_date': fields.Datetime.now(),
            })
            rec.message_post(body=_("WhatsApp message opened for supplier contact: %(phone)s") % {'phone': phone})
            return {
                'type': 'ir.actions.act_url',
                'url': 'https://wa.me/%s?text=%s' % (phone, urllib.parse.quote(message)),
                'target': 'new',
            }
        return False

    def action_validate_close(self):
        """Return close-blockers as a list of error message strings (no exceptions)."""
        self.ensure_one()
        errors = []
        if not self.supplier_notified:
            errors.append(_("Supplier must be marked as notified before closing the claim."))
        if self._requires_whatsapp_notification() and not self.whatsapp_message_sent:
            errors.append(_("Please send the WhatsApp message to the supplier before closing the claim."))
        if not self.check_delivery_status:
            errors.append(_("Cheque Delivery Status must be set before closing the claim."))
        if self.check_delivery_status in ('check_delivered', 'mixed'):
            if not self.sub_delivery_status:
                errors.append(_("Please select a sub status (Delivered or Shipped) for cheque delivery."))
            elif self.status != 'delivery':
                errors.append(_("Please complete the Delivery stage before closing the claim."))
            elif self.sub_delivery_status != 'ready':
                errors.append(_("Please set the delivery status to Delivered before closing the claim."))
            if not self.cheque_image:
                errors.append(_("Please attach the cheque image before confirming cheque delivery."))
            if not self.supplier_id_image:
                errors.append(_("Please attach the supplier ID image before confirming cheque delivery."))
        return errors

    def _normalize_delivery_values_for_close(self):
        for rec in self:
            vals = {}
            if rec.check_delivery_status == 'shipped':
                vals['check_delivery_status'] = 'ready'
            if vals:
                rec.with_context(supplier_claim_internal_write=True).write(vals)
        return True

    def action_close_claim(self):
        for rec in self:
            rec._check_can_act_current_stage()
            errors = rec.action_validate_close()
            if errors:
                raise UserError(errors[0])
            error = rec._validate_cheque_delivery_documents()
            if error:
                return error
            rec._normalize_delivery_values_for_close()
            rec._ensure_delegate_phone_selection()
            rec.supplier_id.sudo().write({
                'work_email': rec.supplier_email or '',
                'mobile_phone': rec._get_supplier_mapping_phone_text(),
            })
            rec._move_to_next_stage()

    @api.model
    def _get_escalation_sla_seconds(self):
        return int(self.env['ir.config_parameter'].sudo().get_param(
            'supplier_claim.escalation_sla_seconds', '86400'))

    def _get_department_escalation_start_datetime(self, dept_key, pending_datetime=False):
        self.ensure_one()
        decision_field = dict(PARALLEL_DECISION_FIELDS).get(dept_key)
        date_field = DEFER_EXPECTED_DATE_FIELD_MAP.get(dept_key)
        if decision_field and date_field and self[decision_field] == 'deferred' and self[date_field]:
            return fields.Datetime.to_datetime(self[date_field]) + timedelta(days=1)
        return pending_datetime

    @api.model
    def _cron_escalate_overdue_stages(self):
        claims = self.search([('status', 'in', DEPARTMENT_STAGES)])
        sla_seconds = self._get_escalation_sla_seconds()
        now = fields.Datetime.now()
        now_str = format_datetime(self.env, now, dt_format='medium')

        for claim in claims:
            if claim.status in ('inventory', 'purchase'):
                departments = ['inventory', 'purchase']
            else:
                departments = [claim.status]

            for dept_key in departments:
                dept_history = self.env['ab_supplier_claim_stage_history'].search([
                    ('claim_id', '=', claim.id),
                    ('stage', '=', dept_key),
                    ('decision', '=', 'pending'),
                ], order='action_date desc', limit=1)
                if not dept_history or not dept_history.action_date:
                    continue
                escalation_start = claim._get_department_escalation_start_datetime(dept_key, dept_history.action_date)
                if not escalation_start or now - escalation_start <= timedelta(seconds=sla_seconds):
                    continue

                details = claim._resolve_escalation_details(stage_key=dept_key)
                manager_users = details['manager_users']
                dept_label = claim._get_stage_label(dept_key)

                last_escalated = self.env['ab_supplier_claim_stage_history'].search([
                    ('claim_id', '=', claim.id),
                    ('stage', '=', dept_key),
                    ('decision', '=', 'escalated'),
                ], order='action_date desc', limit=1)
                if last_escalated:
                    last_rejected = self.env['ab_supplier_claim_stage_history'].search([
                        ('claim_id', '=', claim.id),
                        ('stage', '=', dept_key),
                        ('decision', '=', 'rejected'),
                    ], order='action_date desc', limit=1)
                    if (
                        last_escalated.action_date >= escalation_start
                        and (not last_rejected or last_escalated.action_date > last_rejected.action_date)
                    ):
                        current_manager_lines = [
                            '\u2022 %s' % user.display_name
                            for user in manager_users
                        ]
                        if not current_manager_lines or all(
                            line in (last_escalated.notes or '')
                            for line in current_manager_lines
                        ):
                            continue

                _logger.info(
                    'Escalation audit for claim %s (department: %s):\n'
                    '  Manager Users: %s\n'
                    '  Elapsed seconds: %s',
                    claim.display_name, dept_key,
                    ', '.join(u.display_name for u in manager_users) if manager_users else 'NONE',
                    round((now - escalation_start).total_seconds(), 1),
                )

                if manager_users:
                    for manager in manager_users:
                        claim._send_escalation_notification(manager, stage_key=dept_key)
                    manager_lines = '\n'.join(
                        '\u2022 %s' % u.display_name
                        for u in manager_users
                    )
                    notes = _(
                        'Escalation notification was sent to:\n%(managers)s\n'
                        'Department: %(dept)s\n'
                        'Time: %(time)s'
                    ) % {
                        'managers': manager_lines,
                        'dept': dept_label,
                        'time': now_str,
                    }
                    claim._create_stage_history(dept_key, 'escalated', notes)
                else:
                    notes = claim._format_no_escalation_managers_note(dept_label, now_str)
                    already_no_mgr = self.env['ab_supplier_claim_stage_history'].search([
                        ('claim_id', '=', claim.id),
                        ('stage', '=', dept_key),
                        ('decision', '=', 'escalated'),
                        ('action_date', '>=', escalation_start),
                        ('notes', 'not like', 'Escalation notification%'),
                    ], limit=1)
                    if not already_no_mgr:
                        claim._create_stage_history(dept_key, 'escalated', notes)
                    claim.write({
                        'escalation_missing_manager': True,
                    })

    def _resolve_escalation_details(self, stage_key=None):
        self.ensure_one()
        result = {
            'group_xmlid': None,
            'users': [],
            'employees': [],
            'departments': [],
            'managers': [],
            'manager_users': [],
        }
        STATUS_TO_DEPT_CODE = {
            'inventory': 'inventory',
            'purchase': 'purchase',
            'suppliers': 'suppliers',
            'tax_accounts': 'tax_accounts',
            'bank_acc': 'bank_accounts',
        }
        dept_code = STATUS_TO_DEPT_CODE.get(stage_key or self.status)
        if not dept_code:
            return result
        try:
            Employee = self.env['ab_hr_employee'].sudo()
        except KeyError:
            return result
        manager_employee = self.env['ab_supplier_claim_manager_service'].sudo()._get_stored_manager(dept_code)

        if manager_employee and manager_employee.user_id:
            result['managers'].append(manager_employee)
            result['manager_users'].append(manager_employee.user_id)
        if not result['manager_users']:
            return result
        stage_groups = self._get_stage_group_xmlids()
        group_xmlid = stage_groups.get(stage_key or self.status)
        if group_xmlid:
            result['group_xmlid'] = group_xmlid
            group = self.env.ref(group_xmlid, raise_if_not_found=False)
            if group:
                result['users'] = list(group.sudo().user_ids)
        return result

    def _format_no_escalation_managers_note(self, department, time):
        self.ensure_one()
        return _(
            'No escalation manager is configured for the %(dept)s department.\n'
            'Time: %(time)s'
        ) % {
            'dept': self._get_display_stage_label(department),
            'time': time,
        }

    def _resolve_escalation_managers(self):
        return self._resolve_escalation_details()['manager_users']

    def action_assign_escalation_user(self):
        self.ensure_one()
        if not self.assigned_escalation_user:
            return
        method = self._send_escalation_notification(self.assigned_escalation_user)
        now_str = fields.Datetime.now().strftime('%Y-%m-%d %H:%M')
        self._create_stage_history(
            self.status, 'escalated',
            _(
                'Manual escalation.\n'
                'Assigned to: %(name)s (%(login)s)\n'
                'Department: %(dept)s\n'
                'Notification type: %(method)s\n'
                'Escalated at: %(time)s'
            ) % {
                'name': self.assigned_escalation_user.display_name,
                'login': self.assigned_escalation_user.login or self.assigned_escalation_user.email or '',
                'dept': self._get_stage_label(self.status),
                'method': _('Odoo Activity') if method == 'odoo_activity' else _('Internal Fallback'),
                'time': now_str,
            },
        )
        self.write({
            'escalation_missing_manager': False,
            'assigned_escalation_user': False,
        })

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
            'stage_escalated': False,
            'escalation_missing_manager': False,
            'assigned_escalation_user': False,
        })
        self._create_stage_history(next_stage, 'pending')
        self._notify_department_turn_started(next_stage)

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
        return dict(self._fields['status']._description_selection(self.env)).get(stage, stage)

    def _get_display_stage_label(self, label):
        normalized_label = (label or '').strip()
        for stage, source_label in STAGE_LABELS.items():
            if normalized_label == source_label:
                return self._get_translated_stage_label(stage)
        return label

    def _format_escalation_sent_note(self, managers, department, time):
        return _(
            'Escalation notification was sent to:\n%(managers)s\n'
            'Department: %(dept)s\n'
            'Time: %(time)s'
        ) % {
            'managers': managers,
            'dept': self._get_display_stage_label(department),
            'time': time,
        }

    def _get_note_time_value(self, lines):
        time_line = next(
            (
                line for line in lines
                if line.startswith('Time: ')
            ),
            ''
        )
        return time_line.split(':', 1)[1].strip() if ':' in time_line else ''

    def _get_display_history_notes(self, notes):
        notes = notes or ''
        lines = notes.splitlines()
        if not lines:
            return notes

        title = lines[0].strip()
        translated_title = _('Escalation notification was sent to:')
        if title not in (
            'Escalation notification sent to:',
            'Escalation notification was sent to:',
            translated_title,
        ):
            return notes

        department_prefixes = ('Department: ', '%s ' % _('Department:'))
        time_prefixes = ('Time: ', '%s ' % _('Time:'))
        department_index = next(
            (
                index for index, line in enumerate(lines)
                if line.startswith(department_prefixes)
            ),
            None,
        )
        time_index = next(
            (
                index for index, line in enumerate(lines)
                if line.startswith(time_prefixes)
            ),
            None,
        )
        if department_index is None or time_index is None:
            return notes

        managers = '\n'.join(lines[1:department_index]).strip()
        department = lines[department_index].split(':', 1)[1].strip()
        time = lines[time_index].split(':', 1)[1].strip()
        return self._format_escalation_sent_note(managers, department, time)

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

        def display_datetime(value):
            return format_datetime(self.env, value, dt_format='medium') if value else ''

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
                    'display_date': display_datetime(h.action_date),
                    'notes': self._get_display_history_notes(h.notes),
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
                    is_current = dept_decision in ('pending', 'deferred') and self.status in DEPARTMENT_STAGES and not self.has_blocking_issue
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

            if last and last.decision == 'deferred' and stage in DEPARTMENT_STAGES:
                stage_notes = self._format_deferred_stage_history_note(stage)
            else:
                stage_notes = self._get_display_history_notes(last.notes) if last else ''

            is_overdue = False
            if is_current and stage != 'closed' and last and last.action_date:
                can_see_overdue = self._is_supplier_claim_admin() or self._is_supplier_claim_secretarial()
                overdue_start = self._get_department_escalation_start_datetime(stage, last.action_date)
                is_overdue = (
                    can_see_overdue
                    and overdue_start
                    and fields.Datetime.now() - overdue_start > timedelta(seconds=self._get_escalation_sla_seconds())
                )

            parallel_decisions = {
                sk: {
                    'decision': self[df],
                    'finished': self[FINISHED_FIELD_MAP[sk]],
                }
                for sk, df in self._get_parallel_decision_fields()
            } if stage in DEPARTMENT_STAGES else None

            show_defer_overdue_days = False
            defer_overdue_days = 0
            defer_remaining_days = 0
            if stage in DEPARTMENT_STAGES:
                decision_field = current_dept_decisions.get(stage)
                expected_date_field = self._get_defer_expected_date_field(stage)
                if (
                    decision_field
                    and expected_date_field
                    and self[decision_field] == 'deferred'
                    and self[expected_date_field]
                ):
                    show_defer_overdue_days = True
                    expected_date = self[expected_date_field]
                    today = fields.Date.context_today(self)
                    if today > expected_date:
                        defer_overdue_days = (today - expected_date).days
                    else:
                        defer_remaining_days = (expected_date - today).days

            timeline.append({
                'type': 'stage',
                'stage': stage,
                'label': self._get_translated_stage_label(stage),
                'is_current': is_current,
                'is_completed': is_completed,
                'is_overdue': is_overdue,
                'user_name': last.user_id.display_name if last and last.user_id else '',
                'action_date': last.action_date.isoformat() if last and last.action_date else '',
                'display_date': display_datetime(last.action_date if last else False),
                'notes': stage_notes,
                'parallel_decisions': parallel_decisions,
                'show_defer_overdue_days': show_defer_overdue_days,
                'defer_overdue_days': defer_overdue_days,
                'defer_remaining_days': defer_remaining_days,
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
                'display_date': display_datetime(issue.date),
                'stage': issue.stage,
                'issue_id': issue.id,
                'resolved': issue.resolved,
                'resolved_by': issue.resolved_by.display_name if issue.resolved_by else '',
                'resolved_date': issue.resolved_date.isoformat() if issue.resolved_date else '',
                'display_resolved_date': display_datetime(issue.resolved_date),
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

    @api.depends_context('lang')
    @api.depends(
        'status',
        'supplier_type',
        'check_delivery_status',
        'sub_delivery_status',
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
        'inv_deferred_expected_date',
        'pur_deferred_expected_date',
        'sup_deferred_expected_date',
        'tax_deferred_expected_date',
        'bank_deferred_expected_date',
        'inv_deferred_reason',
        'pur_deferred_reason',
        'sup_deferred_reason',
        'tax_deferred_reason',
        'bank_deferred_reason',
        'has_blocking_issue',
        'issue_ids',
        'issue_ids.resolved',
        'tax_frozen',
        'tax_amount',
        'tax_percentage',
        'net_payable',
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

                icon = '🏛' if entry['stage'] == 'tax_accounts' and self._requires_tax_accounts_stage() else (
                    '✈' if (is_comp and entry['stage'] == 'closed') else (
                    '✓' if is_comp else ('●' if is_curr else '○')))

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
                if entry.get('show_defer_overdue_days'):
                    if entry.get('defer_overdue_days', 0) > 0:
                        defer_overdue_label = _('Delay days after expected deferral date: %(days)s days') % {
                            'days': entry.get('defer_overdue_days', 0),
                        }
                        defer_overdue_class = 'scc-timeline-defer-overdue is-overdue'
                    else:
                        remaining_days = entry.get('defer_remaining_days', 0)
                        defer_overdue_label = _('Remaining days until expected deferral date: %(days)s days') % {
                            'days': remaining_days,
                        }
                        if remaining_days == 0:
                            defer_overdue_class = 'scc-timeline-defer-overdue is-due-today'
                        elif remaining_days <= 2:
                            defer_overdue_class = 'scc-timeline-defer-overdue is-due-soon'
                        else:
                            defer_overdue_class = 'scc-timeline-defer-overdue is-on-track'
                    L.append('<div class="%s">%s</div>' % (defer_overdue_class, defer_overdue_label))

                if entry['stage'] == 'tax_accounts' and is_comp and self._requires_tax_accounts_stage():
                    L.append('<div class="scc-timeline-tax-summary">')
                    L.append('<div class="scc-timeline-tax-line">%s <strong>%s%%</strong></div>' % (_('Tax Applied:'), int(self.tax_percentage)))
                    tax_amount_display = _('%(amount)s %(currency)s') % {
                        'amount': '{:,.2f}'.format(self.tax_amount or 0.0),
                        'currency': self.currency_id.symbol or '',
                    } if self.tax_amount else _('0.00')
                    L.append('<div class="scc-timeline-tax-amount">- %s</div>' % tax_amount_display)
                    L.append('</div>')

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
                if entry.get('notes'):
                    L.append('<div class="scc-timeline-notes">%s</div>' % entry['notes'])
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
            date_str = current_stage.get('display_date') or current_stage['action_date']

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

            if current_stage['stage'] == 'tax_accounts' and self._requires_tax_accounts_stage():
                tax_amt = self.tax_amount or 0.0
                net_amt = self.net_payable or 0.0
                claim_amt = self.amount_of_check or 0.0
                currency = self.currency_id.symbol or ''
                fmt = lambda v: '{:,.2f}'.format(v)
                L.append('<div class="scc-tax-financial-card">')
                L.append('<div class="scc-tax-financial-header">🏛 %s</div>' % _('Withholding Tax Summary'))
                L.append('<div class="scc-tax-financial-body">')
                L.append('<div class="scc-tax-financial-row">')
                L.append('<span class="scc-tax-financial-label">%s</span>' % _('Claim Amount'))
                L.append('<span class="scc-tax-financial-value">%s %s</span>' % (fmt(claim_amt), currency))
                L.append('</div>')
                L.append('<div class="scc-tax-financial-row">')
                L.append('<span class="scc-tax-financial-label">🏛 %s</span>' % _('Withholding Tax'))
                L.append('<span class="scc-tax-financial-value scc-tax-amount">%s%% (-%s %s)</span>' % (
                    int(self.tax_percentage or 1.0), fmt(tax_amt), currency))
                L.append('</div>')
                L.append('<div class="scc-tax-financial-divider"></div>')
                L.append('<div class="scc-tax-financial-row scc-tax-net-row">')
                L.append('<span class="scc-tax-financial-label scc-tax-net-label">%s</span>' % _('Net Payable'))
                L.append('<span class="scc-tax-financial-value scc-tax-net-value">%s %s</span>' % (fmt(net_amt), currency))
                L.append('</div>')
                L.append('</div>')
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
                'res_model': 'ab_claim_error_wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_error_message': _(
                        'Please select a sub status (Delivered or Shipped) for cheque delivery.'
                    ),
                },
            }
        if not self.cheque_image:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Missing Required Documents'),
                'res_model': 'ab_claim_error_wizard',
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
                'res_model': 'ab_claim_error_wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_error_message': _(
                        'Please attach the supplier ID image before confirming cheque delivery.'
                    ),
                },
            }
