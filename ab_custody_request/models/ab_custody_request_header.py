import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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
        self.send_by_bot(self.get_chat_id("telegram_custody_group_chat_id"),
                         msg=subject,
                         before=before,
                         after=after,
                         attachment=attachment)

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

    def _compute_current_user_type(self):
        for rec in self:
            if rec.user_id.id == self.env.user.id and rec.status == 'for_entry':
                rec.current_user_type = 'claimer'

            elif rec.manager_id.sudo().user_id.id == self.env.user.id and rec.status == 'for_manager':
                rec.current_user_type = 'claimer_manager'

            elif self.env.user.has_group(
                    'ab_custody_request.group_ab_custody_request_accounting') and rec.status == 'for_accounting':
                rec.current_user_type = 'accounting_manager'

            elif self.env.user.has_group(
                    'ab_custody_request.group_ab_custody_request_payment') and rec.status == 'for_payment':
                rec.current_user_type = 'payer'
            else:
                rec.current_user_type = False

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

    def btn_set_status(self):
        self.ensure_one()
        action = self.env.context.get('action')
        now = datetime.datetime.now()

        allowed_time_recs = self.env['ab_custody_request_config'].search([
            ('date1', '<=', now),
            ('date2', '>=', now)], order='date1 desc')

        if not allowed_time_recs:  # not in time
            # from claimer_manager to accounting
            if self.current_user_type == 'claimer_manager' and action == 'for_accounting':
                raise ValidationError(_("Not In Time!"))

        if allowed_time_recs:
            allowed_employees = allowed_time_recs[0].employee_ids

            current_employee = self.env['ab_hr_employee'].search([('user_id', '=', self.env.user.id)], limit=1)

            if allowed_employees:
                # from claimer_manager to accounting
                if self.current_user_type == 'claimer_manager' and action == 'for_accounting':
                    if current_employee.id not in allowed_employees.ids:
                        raise ValidationError(_("Not In Time For This Employee!"))

        if self.current_user_type == 'claimer':
            if self.status != 'for_entry':
                raise ValidationError(_('Status must be "For Entry"'))
            if action != 'for_manager':
                raise ValidationError(_('You can set status "For Manager" only'))
        elif self.current_user_type == 'claimer_manager':
            if self.status != 'for_manager':
                raise ValidationError(_('Status must be "For Manager"'))
            if action not in ('for_entry', 'for_accounting'):
                raise ValidationError(_('You can set status "For Entry" or "For Accounting" only'))

        elif self.current_user_type == 'accounting_manager':
            if self.status != 'for_accounting':
                raise ValidationError(_('Status must be "For Accounting"'))
            if action not in ('for_manager', 'for_payment'):
                raise ValidationError(_('You can set status "For Manager" or "For Payment" only'))

        elif self.current_user_type == 'payer':
            if self.status != 'for_payment':
                raise ValidationError(_('Status must be "For Payment"'))
            if action not in ('for_accounting', 'paid'):
                raise ValidationError(_('You can set status "For Accounting" or "Paid" only'))

        self.sudo().status = action
        self.btn_post_telegram()

        status_name = dict(self._fields['status']._description_selection(self.env)).get(action)

        msg = _(f"""Status is changed to <span class="h6 text-success">{status_name}</span> successfully.""")
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
