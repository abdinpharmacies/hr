from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# class IrAttachment(models.Model):
#     _inherit = 'ir.attachment'
#
#     @api.model
#     def check(self, mode, values=None):
#         if self.env.user.has_group('ab_accounting.group_ab_accounting_accountant'):
#             return True
#         else:
#             return super(IrAttachment, self).check(mode, values)


class AbAccountingJeHeader(models.Model):
    _name = 'ab_accounting_je_header'
    _inherit = ['ab_data_from_excel', 'ab_accounting_je_line_compute_balance', 'abdin_et.extra_tools', 'mail.thread']
    _description = 'ab_accounting_je_header'
    _rec_name = 'id'
    _order = 'id desc'

    account_id = fields.Many2one('ab_accounting_account_guide', required=True,
                                 domain=[('own_account', '=', True)],
                                 auto_join=True,
                                 )

    contains_account = fields.Char(compute='_compute_contains_account', search='_search_contains_account')
    je_headers_search = fields.Char(compute='_compute_je_headers_search', search='_search_je_headers_search')
    doctype_id = fields.Many2one('ab_accounting_doctype', 'Document Type',
                                 domain=lambda self: [('id', 'in', self.env.user.doctype_ids.ids)],
                                 required=True,
                                 )

    from_excel = fields.Text()
    is_posted = fields.Boolean(default=False, index=True)
    is_frozen = fields.Boolean(default=False)
    line_ids = fields.One2many(
        comodel_name='ab_accounting_je_line',
        inverse_name='header_id',
        string='Moves')
    costcenter_id = fields.Many2one('ab_costcenter')
    has_due_date = fields.Boolean(related='account_id.has_due_date')
    has_costcenter = fields.Boolean(related='account_id.has_costcenter')
    has_store = fields.Boolean(related='account_id.has_store')

    posted_date = fields.Date(readonly=True)
    responsibility = fields.Boolean(compute='_compute_responsibility',
                                    search='_search_responsibility', )

    att_file_ids = fields.Many2many(comodel_name='ir.attachment',
                                    relation='class_ir_attachments_rel',
                                    column1='class_id',
                                    column2='attachment_id',
                                    string='Attachments',
                                    groups='ab_accounting.group_ab_accounting_accountant')

    total_net_val = fields.Float(compute='_compute_lines_totals', compute_sudo=True)
    total_debit_val = fields.Float(compute='_compute_lines_totals', compute_sudo=True)
    total_credit_val = fields.Float(compute='_compute_lines_totals', compute_sudo=True)
    active = fields.Boolean(default=True)
    all_confirmed = fields.Boolean(compute='_compute_all_confirmed', search='_search_all_confirmed')
    header_store_id = fields.Many2one('ab_store', compute='_compute_header_vars')
    store_id = fields.Many2one('ab_store')
    header_debit_val = fields.Float(compute='_compute_header_vars')
    header_credit_val = fields.Float(compute='_compute_header_vars')
    always_show_account = fields.Boolean(compute='_compute_always_show_account', search='_search_always_show_account')

    @api.depends('account_id')
    def _compute_always_show_account(self):
        for rec in self:
            # Set visibility based on custom logic
            rec.always_show_account = (
                    rec.create_uid.id == self._uid
                    or rec.create_uid.id in self.env.user.responsible_for_ids.ids
                    or rec.account_id.always_show_account
            )

    def _search_always_show_account(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))
        if operator == '=' and val == True:
            return [
                '|', '|',
                ('create_uid', '=', self._uid),
                ('create_uid', 'in', self.env.user.responsible_for_ids.ids),
                ('account_id.always_show_account', '=', True),
            ]
        else:
            return [(0, '=', 1)]

    def _search_contains_account(self, op, val):
        return [('line_ids.account_id.name', 'ilike', val)]

    def _compute_contains_account(self):
        for rec in self:
            rec.contains_account = '...'

    def _search_je_headers_search(self, op, val):
        je_h_ids = [int(je_h) for je_h in val.split() if je_h.isdigit()]
        return [('id', 'in', je_h_ids)]

    def _compute_je_headers_search(self):
        for rec in self:
            rec.je_headers_search = '...'

    def _search_all_confirmed(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))
        if operator != '=':  # that means it is '!='
            val = not val
        not_confirmed_je_ids = self.search([('line_ids.is_confirmed', '=', False)]).ids
        return [('id', 'not in' if val else 'in', not_confirmed_je_ids)]

    def _compute_all_confirmed(self):
        for rec in self:
            if not rec.line_ids:
                rec.all_confirmed = False
            else:
                rec.all_confirmed = all(line.is_confirmed for line in rec.line_ids)

    def _compute_header_vars(self):
        for rec in self:
            header = rec.line_ids.filtered('is_header')
            rec.header_store_id = header and header[0].store_id.id or False
            rec.header_debit_val = header and header[0].debit_val or 0
            rec.header_credit_val = header and header[0].credit_val or 0

    @api.depends('line_ids')
    def _compute_lines_totals(self):
        je_line_mo = self.env['ab_accounting_je_line'].sudo()
        for rec in self:
            je_lines = je_line_mo.search([('header_id', '=', rec.id)])
            total_debit_val = sum(je_lines.mapped('debit_val'))
            total_credit_val = sum(je_lines.mapped('credit_val'))
            rec.total_debit_val = total_debit_val
            rec.total_credit_val = total_credit_val
            rec.total_net_val = total_debit_val - total_credit_val

    @api.onchange('account_id', 'costcenter_id')
    def _onchange_account_header(self):
        header_je = self.line_ids.filtered('is_header')
        if not self.line_ids:
            # create header_je
            self.write({'line_ids': [(0, 0, {'costcenter_id': self.costcenter_id.id,
                                             'account_id': self.account_id.id, })]})
        if header_je:
            # update header_je
            first_header_je_id = header_je[0].id

            self.write({'line_ids': [(1, first_header_je_id, {'costcenter_id': self.costcenter_id.id,
                                                              'account_id': self.account_id.id, })]})
            self.update({})

    @api.depends('account_id', 'costcenter_id')
    def _compute_balance(self):
        for rec in self:
            self.compute_balance(rec)

    def btn_confirm_all_je(self):
        self = self.with_context(no_calc_balance=True)
        for line in self.line_ids:
            if line.allow_confirm:
                line.btn_confirm_je()

    def sudo_confirm_all_je(self):
        sudo_confirm = self.with_context(sudo_confirm=True)
        sudo_confirm.line_ids.write({'is_confirmed': True})

    def _search_responsibility(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        ids = self.sudo().search([
            ('create_uid', 'in', self.env.user.responsible_for_ids.ids),
        ], ).ids

        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', ids)]

    @api.depends('create_uid')
    def _compute_responsibility(self):
        for rec in self:
            if rec.create_uid.id in self.env.user.responsible_for_ids.ids:
                rec.responsibility = True
            else:
                rec.responsibility = False

    def btn_post_je(self):
        self.posted_date = fields.Date.today()
        self._check_validation()
        self._set_posted()
        # self._set_header_line_confirmed()

    def btn_freeze(self):
        if self.create_uid.id == self.env.user.id:
            raise ValidationError(_("You can not freeze JE (as you created it).\n "
                                    "Only 'Reviewer' can freeze ..."))
        if self.is_posted:
            self.is_frozen = True
        else:
            raise UserError(_("JE must posted first."))

    def btn_unfreeze(self):
        if self.create_uid.id == self.env.user.id:
            raise ValidationError(_("You can not unfreeze JE (as you created it).\n "
                                    "Only 'Reviewer' can unfreeze ..."))

        self.is_frozen = False

    def _check_validation(self):
        msg = ""
        msg += self._msg_is_posted_before()
        msg += self._msg_is_je_balanced(self.line_ids)
        msg += self._msg_is_lines_ok(self.line_ids)
        msg += self._msg_no_lines_to_add()
        if msg:
            raise ValidationError(msg)

    def _set_posted(self):
        self.is_posted = True

    def unlink(self):
        for rec in self:
            if rec.is_posted:
                if not self.env.user.has_group('base.group_system'):
                    raise UserError("YOU CAN NOT DELETE JOURNAL ENTRIES, PLEASE REVERSE IT.")
        res = super().unlink()
        return res

    def _set_header_line_confirmed(self):
        self.is_confirmed = True

    @api.constrains('line_ids')
    def account_header_constrains(self):
        for rec in self:
            if rec.is_frozen and rec.create_uid.id == self.env.uid:
                raise ValidationError(_("This action is not allowed for you (as you created JE).\n "
                                        "Only 'Reviewer' can edit this JE  ....."))
            if rec.sudo().is_posted:
                msg = ""
                msg += self._msg_is_je_balanced(self.line_ids)
                msg += self._msg_is_lines_ok(self.line_ids)
                msg += self._msg_no_lines_to_add()
                if msg:
                    raise ValidationError(msg)

    def _clear_header(self):
        self.account_id = self.debit_val = self.credit_val \
            = self.due_date = self.costcenter_id = self.doctype_id = None

    def btn_add_data_from_excel(self):
        number_of_lines = len(self.from_excel.strip().split('\n')) - 1
        self.data_from_excel(model_name='ab_accounting_je_line',
                             x2many_field='line_ids',
                             excel_data=self.from_excel.strip('\n'), update_only=False)

        message = _("""<span class='h4 text-success'>%s</span> lines added  
        <span class='h4 text-success'>successfully</span>  
        by user <span class='h4 font-italic text-muted'>%s</span>""") % (number_of_lines, self.env.user.name)
        return self.ab_msg(message=message)

    def btn_update_data_from_excel(self):
        rows_count = len(self.from_excel.strip('\n').split('\n')) - 1
        if rows_count == len(self.line_ids):
            self.data_from_excel(model_name='ab_accounting_je_line',
                                 x2many_field='line_ids',
                                 excel_data=self.from_excel.strip('\n'), update_only=True)
        else:
            raise UserError(_("Number of rows is not equal number of lines"))
        message = _("""<span class='h4 text-success'>%s</span> lines updated  
        <span class='h4 text-success'>successfully</span>  
        by user <span class='h4 font-italic text-muted'>%s</span>""") % (len(self.line_ids), self.env.user.name)
        return self.ab_msg(message=message)

    @staticmethod
    def notify_user(msg, title="Done", msg_type="success"):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': msg,
                'type': msg_type,  # types: success,warning,danger,info
                'sticky': True,  # True/False will display for few seconds if false
            },
        }

    ##########################################
    # Validation msg Methods #################
    ##########################################
    def _msg_is_posted_before(self):
        return "" if not self.is_posted else _('\n- Moves have been Posted before.')

    def _msg_no_lines_to_add(self):
        return "" if self.line_ids else _('\n- No moves to add.')

    def _msg_is_je_balanced(self, lines):
        is_balanced, total_deb, total_cred = self._get_je_balance_status(lines)
        return "" if is_balanced else f"\n- JE {self.id} is not balanced. {total_deb} not equal {total_cred}"

    def _msg_is_lines_ok(self, lines):
        msg = ""
        for line in lines:
            allowed_costcenter_ids = set(line.account_id.costcenter_ids.ids)

            if not (line.account_id.allow_account or line.account_id.own_account):
                msg += _(f"\n- You are not allowed to post account {line.account_id.name}.")
            if line.account_id.has_costcenter and not line.costcenter_id:
                msg += _(f"\n- Costcenter is required for {line.account_id.name}.")
            if allowed_costcenter_ids and line.costcenter_id.id not in allowed_costcenter_ids:
                msg += _(f"\n- Costcenter:\n\t "
                         f"{line.costcenter_id.name}\n\t "
                         f"is not allowed for account:\n\t "
                         f"{line.account_id.name}.")

            if not line.account_id:
                msg += _(f"\n- Account is required for {line.id}.")
            if not line.explain:
                msg += _(f"\n- Explain is required for \n\t{line.account_id.name}.")
            if not line.store_id:
                msg += _(f"\n- Store is required for \n\t{line.account_id.name}.")
            if line.account_id.has_due_date and not line.due_date:
                msg += _(f"\n- Due Date is required for \n\t{line.account_id.name}.")
            if line.debit_val > 0 and line.credit_val > 0:
                msg += _(f"\n- Only debit or credit could be greater than zero for {line.account_id.name}.")

        return msg

    @staticmethod
    def _get_je_balance_status(lines):
        total_debit = 0
        total_credit = 0
        for line in lines:
            total_debit += line.debit_val
            total_credit += line.credit_val
        return abs(total_debit - total_credit) < 0.99, total_debit, total_credit

    def btn_remove_all_je(self):
        if not self.is_posted:
            self.write({'line_ids': [(6, 0, [])]})
        else:
            raise ValidationError(_("JE is posted!"))

    # def btn_archive_je(self):

    def write(self, vals):
        if self.env.user.has_group("base.group_system") or self.env.context.get('sudo_confirm'):
            return super().write(vals)
        for rec in self:
            self = self.with_context(from_header=True)
            res = super().write(vals)
            if rec.create_uid.id == self._uid and 'is_frozen' in vals and vals['is_frozen']:
                raise UserError(_("You can not freeze JE you did create"))
            elif rec.create_uid.id != self._uid and 'is_posted' in vals and vals['is_posted']:
                raise UserError(_("You can not post JE you did not create"))
            if rec.is_posted and not self.env.context.get('no_calc_balance'):
                for je in self.web_progress_iter(rec.line_ids, msg=_('Rechecking Balances ...')):
                    # ONLY FOR EMPLOYEE ACCOUNT سلف وعهد وخصومات
                    je.check_valid_deduction()

                    # IF ACCOUNT NEED BALANCE CALC
                    if self._clac_balance_for_je(je):
                        pre_balance = je.sudo().pre_balance
                        balance_err = UserError(
                            _(f"Balance can not be negative for account: {je.account_id.name}, \n"
                              f"Costcenter: {je.costcenter_id.code}-{je.costcenter_id.name}\n"
                              f"JE ID: {je.id}"
                              ))

                        if je.account_id.internal_group in {'asset', 'expense'}:
                            if pre_balance + je.account_id.max_negative_value < 0:
                                raise balance_err
                        elif je.account_id.internal_group in {'equity', 'liability', 'income'}:
                            if pre_balance - je.account_id.max_negative_value > 0:
                                raise balance_err

            return res

    def _clac_balance_for_je(self, je):
        """
        Do not calc balance if:
        1. clac_balance is False in account_guide
        2. val is debit for debit_account_type
        3. val is credit for credit_account_type
        """
        net_val = je.debit_val - je.credit_val
        debit_type = je.account_id.internal_group in {'asset', 'expense'}
        credit_type = je.account_id.internal_group in {'equity', 'liability', 'income'}
        # clac_balance is False in account_guide
        if not je.account_id.calc_balance:
            return False
        # val is debit for debit_account_type
        elif net_val > 0 and debit_type:
            return False
        # val is credit for credit_account_type
        elif net_val < 0 and credit_type:
            return False
        else:
            return True

    @api.model
    def create(self, values):
        res = super().create(values)
        # This is a FIX for bug res_id=0 in ir.attachment model
        for att in res.att_file_ids:
            if not att.res_id:
                att.sudo().res_id = res.id
        return res
