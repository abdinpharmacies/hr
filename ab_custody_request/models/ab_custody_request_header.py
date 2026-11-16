import datetime

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class AbCustodyRequestHeader(models.Model):
    _name = 'ab_custody_request_header'
    _description = 'ab_custody_request_header'
    _order = 'id desc'
    _inherit = ['abdin_et.extra_tools', 'mail.thread', 'mail.activity.mixin', 'abdin_telegram']

    custody_type = fields.Selection([('visa', 'Visa'), ('cash', 'Cash')],
                                    readonly=lambda env: not env.user.has_group(
                                        'ab_custody_request.group_ab_custody_request_accounting'))
    employee_id = fields.Many2one('ab_hr_employee',
                                  readonly=True,
                                  store=True,
                                  compute='_compute_employee_id',
                                  required=True, precompute=True)

    employee_code = fields.Char(related='employee_id.costcenter_id.code', string='Code')
    branch_id = fields.Many2one(related='employee_id.department_id', string='Branch')
    custody_balance = fields.Float(compute='_compute_custody_balance', compute_sudo=True)  # compute previous custody
    manager_id = fields.Many2one('ab_hr_employee', related='employee_id.parent_id')
    emails_to = fields.Char(string='Email Recipients', compute='_compute_emails_to', compute_sudo=True)
    custody_link = fields.Char(compute='_compute_custody_link', compute_sudo=True)

    is_sent = fields.Boolean(default=False)
    custody_date = fields.Date(default=lambda self: datetime.date.today(), readonly=True)
    status = fields.Selection(
        selection=[('for_entry', 'For Entry'),
                   ('for_manager', 'For Manager'),
                   ('for_accounting', 'For Accounting'),
                   ('for_payment', 'For Payment'),
                   ('paid', 'Paid')
                   ], default='for_entry', readonly=True)
    description = fields.Text(string='Description', compute='_compute_description_lines', compute_sudo=True, store=True)

    current_user_type = fields.Selection(
        selection=[('claimer', 'Claimer'),
                   ('claimer_manager', 'Claimer Manager'),
                   ('accounting_manager', 'Accounting Manager'),
                   ('payer', 'Payer'),
                   ], compute='_compute_current_user_type', compute_sudo=True)

    line_ids = fields.One2many(comodel_name='ab_custody_request_line',
                               inverse_name='header_id',
                               string='Custody Details')
    user_id = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user.id)

    total_requested_custody = fields.Float(compute='_compute_totals', compute_sudo=True,
                                           groups='ab_custody_request.group_ab_custody_request_accounting,'
                                                  'ab_custody_request.group_ab_custody_request_report',
                                           store=True)
    total_approved_custody = fields.Float(compute='_compute_totals', compute_sudo=True)

    approved_value = fields.Float(string="Approved Value",
                                  compute='_compute_accounting_data',
                                  store=True,
                                  readonly=False,
                                  groups='ab_custody_request.group_ab_custody_request_accounting')
    payment_date = fields.Date(groups='ab_custody_request.group_ab_custody_request_payment')
    employee_account_id = fields.Many2one(
        'ab_custody_employee_data',
        compute='_compute_accounting_data',
        store=True,
        readonly=False,
        groups='ab_custody_request.group_ab_custody_request_accounting,'
               'ab_custody_request.group_ab_custody_request_payment_visa')
    account_number = fields.Char(related='employee_account_id.account_number',
                                 groups='ab_custody_request.group_ab_custody_request_accounting,'
                                        'ab_custody_request.group_ab_custody_request_payment_visa')
    employee_bank = fields.Char(related='employee_account_id.employee_bank',
                                groups='ab_custody_request.group_ab_custody_request_accounting,'
                                       'ab_custody_request.group_ab_custody_request_payment_visa')

    bank = fields.Char(related='employee_account_id.bank',
                       groups='ab_custody_request.group_ab_custody_request_accounting,'
                              'ab_custody_request.group_ab_custody_request_payment_visa')

    att_file_ids = fields.Many2many(comodel_name='ir.attachment',
                                    relation='ab_custody_ir_attachments_rel',
                                    column1='custody_id',
                                    column2='attachment_id',
                                    string='Attachments',
                                    groups='ab_custody_request.group_ab_custody_request_user')

    @api.depends('custody_type')
    def _compute_accounting_data(self):
        for rec in self:
            employee_accounts = rec.employee_account_id.search([('employee_id', '=', rec.employee_id.id)])
            if rec.custody_type:
                if not rec.approved_value:
                    rec.approved_value = rec.total_requested_custody
            if rec.custody_type == 'visa':
                if employee_accounts:
                    rec.employee_account_id = employee_accounts[0].id

    @api.depends('line_ids.description')
    def _compute_description_lines(self):
        for rec in self:
            descriptions = rec.line_ids.mapped('description')
            rec.description = ' / '.join(filter(None, descriptions)) if descriptions else ''

    def btn_post_telegram(self):
        # if not self.env.user.has_group('ab_hr.group_ab_hr_co'):
        #     raise ValidationError(_("Only Coordinator group can post."))

        # subject_lines = self.subject.split('\n')
        fields_str = {name: field._description_string(self.env) for name, field in self._fields.items()}

        status = dict(self._fields['status']._description_selection(self.env)).get(self.status)
        title = f" متابعة طلب العهدة رقم {self.id}"

        # before = f"""<b>Noted by:</b> {self.env.user.name}\n\n"""
        before = f"""<b>##### {title} #####</b>\n\n"""

        subject = f"""<div>{fields_str['employee_id']}: {self.employee_id.name} - {self.employee_id.accid}</div>
        <div>{fields_str['manager_id']}: {self.manager_id.name} - {self.manager_id.accid}</div>
        <div>{fields_str['status']}: {status}</div>
        للمتابعة، برجاء الدخول علي رابط العهدة التالي:
        
        """

        # after = f"\n\n<a href='{self.announcement_link}'>Goto Announcement ⏩</a>"
        after = f"\n\nBy {self.env.user.name}\n<a href='{self.custody_link}'>Goto Link ⏩</a>"

        # attachment = self.attachment if self.send_attachment else None
        attachment = None
        try:
            self.send_by_bot(self.get_chat_id("telegram_custody_group_chat_id"),
                             msg=subject,
                             before=before,
                             after=after,
                             attachment=attachment)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_(
                "Telegram notifications are not configured correctly. Ask an administrator to check "
                "the bot token and destination. This action was not completed."
            )) from exc

        title = _("Message is posted successfully on telegram.")
        status = 'success'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'type': status,
                'sticky': False,  # True/False will display for few seconds if false
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    @api.depends('user_id', 'manager_id.user_id', 'status', 'custody_type')
    @api.depends_context('uid')
    def _compute_current_user_type(self):
        for rec in self:
            rec.current_user_type = rec._get_status_actor()

    def _get_status_actor(self):
        self.ensure_one()
        user = self.env.user
        if self.status == 'for_entry' and self.user_id == user:
            return 'claimer'
        if self.status == 'for_manager' and self.manager_id.sudo().user_id == user:
            return 'claimer_manager'
        if self.status == 'for_accounting' and user.has_group(
                'ab_custody_request.group_ab_custody_request_accounting'):
            return 'accounting_manager'
        if self.status == 'for_payment' and self.custody_type in ('cash', 'visa'):
            payment_group = 'ab_custody_request.group_ab_custody_request_payment_%s' % self.custody_type
            if user.has_group('base.group_system') or user.has_group(payment_group):
                return 'payer'
        return False

    def _get_current_user_type_selection(self):
        selection = self.fields_get(allfields=['status'])['status']['selection']
        return selection

    @api.constrains('line_ids', 'approved_value')
    def _approved_value(self):
        for rec in self:
            if rec.sudo().approved_value > rec.total_requested_custody:
                raise ValidationError(_("Approved value must be <= custody balance!"))
            if not rec.sudo().line_ids:
                raise ValidationError(_("No Lines to Forward"))

    @api.depends('line_ids', 'line_ids.value')
    def _compute_totals(self):
        for rec in self:
            rec.total_requested_custody = sum(line.value for line in rec.line_ids)
            rec.total_approved_custody = rec.approved_value

    @api.depends('user_id', 'user_id.ab_employee_ids')
    def _compute_employee_id(self):
        for rec in self:
            employees = rec.user_id.ab_employee_ids
            employee_id = employees and employees[0].id
            rec.employee_id = employee_id

    @api.depends('employee_id', 'employee_id.accid')
    def _compute_custody_balance(self):
        je_mo = self.env['ab_accounting_je_line']
        for rec in self:
            je_lines = je_mo.search(
                [
                    ('costcenter_id.code', '=', rec.employee_id.accid),
                    ('header_id.is_posted', '=', True),
                    ('account_id', '=', 251),
                ]
            )

            rec.custody_balance = sum(line.debit_val - line.credit_val for line in je_lines)

    def _check_status_transition(self, action):
        self.ensure_one()
        self.check_access('read')
        actor = self._get_status_actor()
        transitions = {
            'claimer': ('for_manager',),
            'claimer_manager': ('for_entry', 'for_accounting'),
            'accounting_manager': ('for_manager', 'for_payment'),
            'payer': ('for_accounting', 'paid'),
        }
        if not actor or action not in transitions[actor]:
            raise AccessError(_("You are not authorized to make this custody transition."))
        if actor == 'claimer_manager' and action == 'for_accounting':
            now = datetime.datetime.now()
            allowed_time = self.env['ab_custody_request_config'].search([
                ('date1', '<=', now), ('date2', '>=', now)], order='date1 desc', limit=1)
            if not allowed_time:
                raise ValidationError(_("Not In Time!"))
            if allowed_time.employee_ids and self.manager_id not in allowed_time.employee_ids:
                raise ValidationError(_("Not In Time For This Employee!"))

    def write(self, values):
        if 'status' in values and not self.env.su:
            for rec in self:
                rec._check_status_transition(values['status'])
        return super().write(values)

    def btn_set_status(self):
        self.ensure_one()
        action = self.env.context.get('action')
        self._check_status_transition(action)
        self.sudo().write({'status': action})
        self.btn_post_telegram()
        status_name = dict(self._fields['status']._description_selection(self.env)).get(action)
        msg = _("""Status is changed to <span class="h6 text-success">%s</span> successfully.""") % status_name
        return self.ab_msg(title='Done', message=msg)

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, f"{rec.employee_id.name}"))
        return res

    @api.depends('employee_id')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)

    @api.depends('employee_id.work_email', 'manager_id.work_email')
    def _compute_emails_to(self):
        for rec in self:
            recipients = dict.fromkeys(
                email.strip() for email in (rec.employee_id.work_email, rec.manager_id.work_email)
                if email and email.strip()
            )
            rec.emails_to = ','.join(recipients) or False

    def _compute_custody_link(self):
        conf_mo = self.env['ir.config_parameter'].sudo()
        for rec in self:
            # CALL ME
            base_url = conf_mo.get_param('web.base.url')
            rec.custody_link = f"{base_url}/web#id={rec.id}&model={rec._name}&view_type=form"

    def btn_show_total_details(self):
        self.ensure_one()
        total_approved = self.sudo().approved_value

        total_request = sum(line.value for line in self.line_ids)

        msg = ('<table class="table table-bordered">'
               '<tbody>'
               '<tr>'
               '<td>Total Approved</td>'
               f'<td>{total_approved}</td>'
               '</tr>'
               '<tr>'
               '<td>Total Request</td>'
               f'<td>{total_request}</td>'
               '</tr>'
               '<tr></tr>'
               '</tbody>'
               '</table>')
        return self.ab_msg(title="Request Totals", message=msg)
