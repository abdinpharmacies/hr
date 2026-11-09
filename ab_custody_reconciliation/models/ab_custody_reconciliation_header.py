# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import date
from odoo.exceptions import ValidationError, UserError


class AbCustodyReconciliationHeader(models.Model):
    _name = 'ab_custody_reconciliation_header'
    _description = 'ab_custody_reconciliation_header'
    _inherit = ['abdin_et.extra_tools', 'mail.thread', 'mail.activity.mixin', 'abdin_telegram']
    _order = 'id DESC'

    employee_id = fields.Many2one('ab_hr_employee',
                                  readonly=True,
                                  store=True,
                                  compute='_compute_employee_id',
                                  required=True, precompute=True)
    je_header_id = fields.Many2one('ab_accounting_je_header')
    employee_code = fields.Char(related='employee_id.costcenter_id.code', string='Code')
    department_id = fields.Many2one(related='employee_id.department_id', string='Department')
    submit_date = fields.Date(readonly=True)
    custody_balance = fields.Float(compute='_compute_custody_balance', compute_sudo=True)
    manager_id = fields.Many2one('ab_hr_employee', related='employee_id.parent_id')
    is_sent = fields.Boolean(default=False)
    att_file_ids = fields.Many2many(comodel_name='ir.attachment',
                                    relation='ab_custody_reconciliation_ir_attachments_rel',
                                    column1='custody_reconciliation_id',
                                    column2='attachment_id',
                                    string='Attachments', )
    feedback = fields.Html(compute='_compute_feedback', compute_sudo=True)

    user_id = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user.id)
    line_ids = fields.One2many(comodel_name='ab_custody_reconciliation_line',
                               inverse_name='header_id',
                               string='Reconciliation Details',
                               context={'active_test': False})
    # is_closed = fields.Boolean(default=False)
    total_value = fields.Float(compute='_compute_total_value', store=False, compute_sudo=True)
    total_approved_value = fields.Float(compute='_compute_total_approved', compute_sudo=True)
    recon_status = fields.Selection([
        ('entry', 'Entry'),  # requester can crud
        ('submitted', 'Submitted'),  # prevent requester from editing
        ('frozen', 'Frozen'),  # prevent concerned department from approval
        ('posted', 'Posted'),  # after accounting posting
        ('confirmed', 'Confirmed'),  # after accounting confirming
    ], default='entry')

    lines_notes = fields.Char(compute='_compute_lines_notes', search='_search_lines_notes')

    print_all = fields.Boolean(default=False)

    def _compute_lines_notes(self):
        for rec in self:
            rec.lines_notes = '\n'.join(rec.line_ids.mapped('notes'))

    def _search_lines_notes(self, operator, val):
        if operator != 'ilike':
            raise UserError(_("Normal filtering does not work for this field"))

        line_ids = self.env['ab_custody_reconciliation_line'].search([
            '|',
            ('notes', operator, val),
            ('rejection_reason', operator, val)
        ])
        ids = line_ids.header_id.ids

        return [('id', 'in', ids)]

    def btn_filter(self):
        self.ensure_one()
        domain = [('header_id', '=', self.id)]
        return {
            "name": '.',
            "type": "ir.actions.act_window",
            "res_model": "ab_custody_reconciliation_line",
            "views": [[False, "list"], [False, "form"], [False, "pivot"]],
            "target": "current",
            "domain": domain,
        }

    @api.depends('line_ids', 'line_ids.status')
    def _compute_total_approved(self):
        for rec in self:
            # approved_lines = rec.line_ids.filtered(lambda line: line.status == 'approved')
            # approved_values = approved_lines.mapped('value')
            # rec.total_approved_value = sum(approved_values)
            rec.total_approved_value = sum(line.value for line in rec.line_ids if line.status == 'approved')

    @api.depends('line_ids.value')
    def _compute_total_value(self):
        for rec in self:
            rec.total_value = sum(line.value for line in rec.line_ids)

    def _compute_feedback(self):
        for rec in self:
            entry_count = len(rec.line_ids.filtered(lambda line: line.status == 'entry'))
            rejected_count = len(rec.line_ids.filtered(lambda line: line.status == 'rejected'))
            approved_count = len(rec.line_ids.filtered(lambda line: line.status == 'approved'))
            pending_count = len(rec.line_ids.filtered(lambda line: line.status == 'pending'))
            neglected_count = len(rec.line_ids.filtered(lambda line: line.status == 'neglected'))
            feedback_dict = {
                '<span class="text-info">Entry</span>': entry_count,
                '<span class="text-warning">Pending</span>': pending_count,
                '<span class="text-success">Approved</span>': approved_count,
                '<span class="text-danger">Rejected</span>': rejected_count,
                '<span class="text-primary">Neglected</span>': neglected_count,
            }
            feedback_list = []
            for k, v in feedback_dict.items():
                if v:
                    feedback_list.append(f"<div>{k}: {v}</div>")
            rec.feedback = '\n'.join(feedback_list)

    def btn_post_telegram(self):
        # if not self.env.user.has_group('ab_hr.group_ab_hr_co'):
        #     raise ValidationError(_("Only Coordinator group can post."))

        # subject_lines = self.subject.split('\n')
        fields_str = {name: field._description_string(self.env) for name, field in self._fields.items()}

        title = f" تسوية العهدة رقم  {self.id}"

        # before = f"""<b>Noted by:</b> {self.env.user.name}\n\n"""
        before = f"""<b>##### {title} #####</b>\n\n"""
        conf_mo = self.env['ir.config_parameter'].sudo()
        base_url = conf_mo.get_param('web.base.url')
        recon_action_id = self.env.ref('ab_custody_reconciliation.ab_custody_reconciliation_line_action').id

        recon_link = f"{base_url}/web#action={recon_action_id}"
        subject = f"""<div>{fields_str['employee_id']}: {self.employee_id.name} - {self.employee_id.accid}</div>
        <div>{fields_str['manager_id']}: {self.manager_id.name} - {self.manager_id.accid}</div>
        <div>
        للمتابعة، برجاء الدخول علي رابط تسوية العهدة التالي:
        </div>
        """

        # after = f"\n\n<a href='{self.announcement_link}'>Goto Announcement ⏩</a>"
        after = f"\n\nBy {self.env.user.name}\n<a href='{recon_link}'>Goto Link ⏩</a>"

        # attachment = self.attachment if self.send_attachment else None
        attachment = None
        chat_ids_set = set(self.line_ids.mapped('custody_account_id.telegram_group_id'))
        for chat_id in chat_ids_set:
            self.send_by_bot(int(chat_id),
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

    def btn_submit(self):
        self.ensure_one()
        pending_count = len(self.line_ids)

        if not pending_count:
            raise ValidationError(_("No records to submit!"))
        if not self.recon_status == 'entry':
            raise ValidationError(_("Custody must be entry to submit"))
        for line in self.line_ids:
            if not line.attachment:
                raise ValidationError(_(f"Line {line.id} has no attachment"))
        self.submit_date = date.today()
        self.line_ids.status = 'pending'

        # last thing to do is change recon_status
        self.recon_status = 'submitted'

        self.btn_post_telegram()
        msg = _(
            f""" <span class="h6 text-success">{pending_count}</span> 
            Record(s) is 
            <span class="h6 text-success">pending</span>.""")
        return self.ab_msg(title='Done', message=msg)

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

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        if name:
            args += [('id', '=ilike', name), ]
        ids = (self.with_user(name_get_uid) if name_get_uid else self).search(args, limit=limit).ids
        return ids

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """Expose the existing search order through the Odoo 19 public API."""
        ids = self._name_search(name, args=domain, operator=operator, limit=limit)
        return [(record.id, record.display_name) for record in self.browse(ids)]

    @api.model
    def _search_display_name(self, operator, value):
        """Keep code/barcode/name matching in relational search domains too."""
        if operator in ('in', 'not in') and isinstance(value, (list, tuple)):
            domain = fields.Domain.OR(self._search_display_name('=', item) for item in value)
            return list(~domain if operator == 'not in' else domain)
        ids = self._name_search(value or '', operator=operator, limit=None)
        return [('id', 'in', ids)]

    def _compute_reconciliation_link(self):
        conf_mo = self.env['ir.config_parameter'].sudo()
        for rec in self:
            base_url = conf_mo.get_param('web.base.url')
            rec.reconciliation_link = f"{base_url}/web#id={rec.id}&model={rec._name}&view_type=form"

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, f"({rec.id}) --- {rec.employee_id.name}"))
        return res

    @api.depends('employee_id')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)

    def btn_freeze_recon(self):
        if self.recon_status == 'frozen':
            raise ValidationError(_("Record is already frozen!"))
        if self.recon_status == 'entry':
            raise ValidationError(_("You can not freeze while status is entry"))

        pending_count = len(self.line_ids.filtered(lambda line: line.status == 'pending'))
        if pending_count:
            msg = f'<span class="text-warning h6">You will mark {pending_count} record(s) as neglected!, are you sure?</span>'
            return self.ab_msg(title="Confirm", message=msg, mode='ok-cancel',
                               model_name=self._name, rec_id=self.id, fn_method='_freeze_recon')
        else:
            self.sudo().recon_status = 'frozen'
            return self.ab_msg(message="<span class='text-success'>Reconciliation set to closed</span>")

    def btn_unfreeze_recon(self):
        if not self.recon_status == 'frozen':
            raise ValidationError(_("Record is already unfrozen!"))
        self.sudo().recon_status = 'submitted'
        for line in self.line_ids:
            if line.status == 'neglected':
                line.sudo().status = 'pending'
        msg = f'<span class="text-info h6">Record is unfrozen successfully!</span>'
        return self.ab_msg(message=msg)

    @api.model
    def _freeze_recon(self, rec_id, *args, **kwargs):
        rec = self.browse(rec_id)
        rec.sudo().recon_status = 'frozen'
        i = 0
        for line in rec.line_ids:
            if line.status == 'pending':
                i += 1
                line.sudo().status = 'neglected'
        msg = f'<span class="text-info h6">You marked {i} records as neglected!</span>'
        return self.ab_msg(message=msg)

    def btn_recreate_lines(self):
        pass

    # def btn_print_pdf_reconciliation(self):
    #     user_lang = self.env.user.lang
    #     print('user_lang', user_lang)
    #     ar_lang = self.env['res.lang'].sudo().search([('active', '=', True), ('code', '=ilike', 'ar_%')])
    #     if ar_lang:
    #         self.env.user.with_context(lang=ar_lang.code)
    #     action = self.env.ref('ab_custody_reconciliation.action_print_account_statement_pdf')
    #     return action.report_action(self)

    def btn_print_pdf_reconciliation(self):
        print_all = self.env.context.get('print_all')
        self.sudo().print_all = print_all
        action = self.env.ref('ab_custody_reconciliation.ab_custody_reconciliation_header_pdf_report').sudo()
        self.message_post(body=f"Report is printed.")
        return action.report_action(self)

    @api.model
    def _get_ar_lang(self):
        ar_lang = self.env['res.lang'].sudo().search([('active', '=', True), ('code', '=ilike', 'ar_%')], limit=1)
        return ar_lang.code or self.env.user.lang

    def write(self, values):
        if self.env.su:
            return super().write(values)
        allowed = {'att_file_ids', 'message_ids', 'message_follower_ids', 'message_main_attachment_id', 'activity_ids'}
        not_accountant = not self.env.user.has_group(
            'ab_custody_reconciliation.group_ab_custody_reconciliation_accounting')
        not_allowed_fields = set(values) - allowed
        for rec in self:
            for att in rec.att_file_ids:
                if not att.res_id:
                    att.sudo().res_id = rec.id

            if not_accountant:
                if rec.recon_status != 'entry':
                    if not_allowed_fields:
                        raise ValidationError(_("Only 'Attachments' field allowed for this user"))

            je_header_id = values.get('je_header_id')
            if je_header_id and rec.je_header_id.id and rec.je_header_id.id != je_header_id:
                raise ValidationError(
                    _("Custody %s already linked to JE Header with ID: %s")
                    % (rec.id, rec.je_header_id.id))
        res = super().write(values)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for values in vals_list:
            records |= self._create_one_ab_custody_reconciliation_abcustodyreconciliationheader(values)
        return records

    def _create_one_ab_custody_reconciliation_abcustodyreconciliationheader(self, values):
        res = super().create(values)
        # This is a FIX for bug res_id=0 in ir.attachment model
        for att in res.att_file_ids:
            if not att.res_id:
                att.sudo().res_id = res.id
        return res
