from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from decimal import Decimal

_WORKFLOW = object()
_HEADER_EDIT = object()


class AbAccountingJeHeader(models.Model):
    _name = 'ab_accounting_je_header'
    _inherit = ['ab_accounting_je_line_compute_balance', 'abdin_et.extra_tools', 'mail.thread']
    _description = 'ab_accounting_je_header'
    _rec_name = 'id'
    _order = 'id desc'

    account_id = fields.Many2one('ab_accounting_account_guide', required=True,
                                 domain=[('own_account', '=', True)],

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
                    rec.create_uid.id == self.env.uid
                    or rec.create_uid.id in self.env.user.responsible_for_ids.ids
                    or rec.account_id.always_show_account
            )

    def _search_always_show_account(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))
        if operator == '=' and val == True:
            return [
                '|', '|',
                ('create_uid', '=', self.env.uid),
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

    @api.depends('line_ids.debit_val', 'line_ids.credit_val', 'line_ids.active')
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
        return self.btn_confirm_all_je()

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
        with self.env.cr.savepoint():
            for rec in self:
                rec._check_validation()
                if not self.env.su and rec.create_uid != self.env.user:
                    raise UserError(_('Only the creator can post this journal.'))
            self.with_context(accounting_workflow=_WORKFLOW).write({
                'posted_date': fields.Date.context_today(self), 'is_posted': True,
            })

    def _check_reviewer(self):
        if not self.env.su and not self.env.user.has_group('ab_accounting.group_ab_accounting_reviewer'):
            raise UserError(_('Reviewer access is required.'))
        for rec in self:
            if not self.env.su and (rec.create_uid == self.env.user or rec.create_uid not in self.env.user.responsible_for_ids):
                raise UserError(_('Only the responsible reviewer can freeze or unfreeze this journal.'))
            if not rec.is_posted:
                raise UserError(_('JE must posted first.'))

    def btn_freeze(self):
        self._check_reviewer()
        self.with_context(accounting_workflow=_WORKFLOW).write({'is_frozen': True})

    def btn_unfreeze(self):
        self._check_reviewer()
        self.with_context(accounting_workflow=_WORKFLOW).write({'is_frozen': False})

    def _check_validation(self):
        msg = ""
        msg += self._msg_is_posted_before()
        msg += self._msg_is_je_balanced(self.line_ids)
        self._validate_posting()
        msg += self._msg_no_lines_to_add()
        if msg:
            raise ValidationError(msg)

    def _set_posted(self):
        return self.btn_post_je()

    def unlink(self):
        if any(self.mapped('is_posted')):
            raise UserError(_('Posted journals must be reversed, not deleted.'))
        return super().unlink()

    @api.constrains('line_ids', 'account_id', 'doctype_id', 'store_id', 'costcenter_id')
    def account_header_constrains(self):
        for rec in self.filtered('is_posted'):
            rec._validate_posting()

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
        return '' if is_balanced else _('Journal %(journal)s is not balanced: debit %(debit)s, credit %(credit)s.') % {'journal': self.id, 'debit': total_deb, 'credit': total_cred}

    def _msg_is_lines_ok(self, lines):
        for line in lines:
            line._validate_posting_line()
        return ''

    @staticmethod
    def _get_je_balance_status(lines):
        debit = sum((Decimal(str(line.debit_val)) for line in lines), Decimal(0)).quantize(Decimal('0.01'))
        credit = sum((Decimal(str(line.credit_val)) for line in lines), Decimal(0)).quantize(Decimal('0.01'))
        return debit == credit, float(debit), float(credit)

    def _validate_posting(self):
        for rec in self:
            if not rec.active or not getattr(rec.doctype_id, 'active', True):
                raise ValidationError(_('Journal and document type must be active.'))
            if not self.env.su and rec.doctype_id not in self.env.user.doctype_ids:
                raise ValidationError(_('You are not authorized for this document type.'))
            rec.account_id._validate_posting_account(own=True)
            if rec.store_id and not rec.store_id.active:
                raise ValidationError(_('Store must be active.'))
            if rec.costcenter_id and not rec.costcenter_id.active:
                raise ValidationError(_('Cost center must be active.'))
            lines = rec.with_context(active_test=False).line_ids.filtered('active')
            if len(lines) < 2:
                raise ValidationError(_('A journal requires at least two active lines.'))
            if not any(line.account_id == rec.account_id and line.costcenter_id == rec.costcenter_id for line in lines):
                raise ValidationError(_('The journal must contain its header account and cost center.'))
            rec._msg_is_lines_ok(lines)
            message = rec._msg_is_je_balanced(lines)
            if message:
                raise ValidationError(message)
            for line in lines:
                line.check_valid_deduction()
                if rec._clac_balance_for_je(line):
                    domain = [('account_id', '=', line.account_id.id), ('header_id.is_posted', '=', True)]
                    if line.account_id.has_store:
                        domain.append(('store_id', '=', line.store_id.id))
                    if line.account_id.has_costcenter:
                        domain.append(('costcenter_id', '=', line.costcenter_id.id))
                    balance = sum(self.env['ab_accounting_je_line'].sudo().search(domain).mapped('net_val'))
                    # Include the whole draft journal once, never other drafts.
                    if not rec.is_posted:
                        balance += sum(l.net_val for l in lines if l.account_id == line.account_id and
                                       (not line.account_id.has_store or l.store_id == line.store_id) and
                                       (not line.account_id.has_costcenter or l.costcenter_id == line.costcenter_id))
                    from odoo.tools.float_utils import float_compare
                    natural = balance if line.account_id.internal_group in {'asset', 'expense'} else -balance
                    if float_compare(natural, -line.account_id.max_negative_value, precision_digits=2) < 0:
                        raise ValidationError(_('Account balance exceeds the permitted negative balance.'))

    def btn_remove_all_je(self):
        if not self.is_posted:
            self.write({'line_ids': [(6, 0, [])]})
        else:
            raise ValidationError(_("JE is posted!"))

    # def btn_archive_je(self):

    def write(self, vals):
        workflow = self.env.context.get('accounting_workflow') is _WORKFLOW
        reverse = self.env.context.get('accounting_reverse') is _WORKFLOW
        if {'is_posted', 'posted_date', 'is_frozen'} & vals.keys() and not workflow:
            raise UserError(_('Use the journal posting and review actions to change its status.'))
        for rec in self:
            if rec.is_frozen and not workflow and not reverse and not self.env.su:
                if rec.create_uid == self.env.user or not self.env.user.has_group('ab_accounting.group_ab_accounting_reviewer') or rec.create_uid not in self.env.user.responsible_for_ids:
                    raise UserError(_('Only the responsible reviewer can edit a frozen journal.'))
            if rec.is_posted and not workflow and not self.env.su:
                if set(vals) - {'line_ids', 'att_file_ids', 'from_excel'}:
                    raise UserError(_('Posted journal header fields cannot be changed.'))
        with self.env.cr.savepoint():
            result = super(AbAccountingJeHeader, self.with_context(accounting_header_edit=_HEADER_EDIT, from_header=True)).write(vals)
            self.filtered('is_posted')._validate_posting()
            return result

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

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get('is_posted') or v.get('is_frozen') for v in vals_list):
            raise UserError(_('Create a draft journal before posting.'))
        records = super().create(vals_list)
        for rec in records:
            for attachment in rec.att_file_ids.filtered(lambda a: not a.res_id):
                attachment.sudo().write({'res_id': rec.id, 'res_model': self._name})
        return records

    @api.model
    def post_journal(self, values):
        """Post a balanced journal using only original header and line fields."""
        allowed = {'account_id', 'costcenter_id', 'store_id', 'doctype_id', 'posted_date', 'res_header_ref', 'res_header_id', 'lines'}
        if set(values) - allowed:
            raise ValidationError(_('Unsupported automated journal fields.'))
        line_fields = {'account_id', 'store_id', 'costcenter_id', 'due_date', 'settlement_date', 'doc_no', 'explain', 'debit_val', 'credit_val'}
        lines = values.get('lines', [])
        if any(set(line) - line_fields for line in lines):
            raise ValidationError(_('Unsupported automated journal line fields.'))
        with self.env.cr.savepoint():
            vals = {key: val for key, val in values.items() if key not in {'lines', 'posted_date'}}
            vals['line_ids'] = [fields.Command.create(line) for line in lines]
            journal = self.create(vals)
            journal.btn_post_je()
            if values.get('posted_date'):
                journal.with_context(accounting_workflow=_WORKFLOW).write({'posted_date': values['posted_date']})
            return journal

    def data_from_excel(self, model_name, x2many_field, excel_data, update_only=False):
        """Retain the original tab-separated import without the legacy addon."""
        import csv
        import io
        self.ensure_one()
        if model_name != 'ab_accounting_je_line' or x2many_field != 'line_ids':
            raise ValidationError(_('Unsupported automated journal fields.'))
        rows = list(csv.DictReader(io.StringIO(excel_data), delimiter='\t'))
        if update_only and len(rows) != len(self.line_ids):
            raise ValidationError(_('Number of rows is not equal number of lines'))
        allowed = {'account_id', 'store_id', 'costcenter_id', 'due_date', 'settlement_date', 'doc_no', 'explain', 'debit_val', 'credit_val'}
        commands = []
        for index, row in enumerate(rows):
            if set(row) - allowed:
                raise ValidationError(_('Unsupported automated journal line fields.'))
            values = {}
            for key, value in row.items():
                if key.endswith('_id'):
                    field = self.env[model_name]._fields[key]
                    records = self.env[field.comodel_name].name_search(value, operator='=', limit=2)
                    if len(records) != 1:
                        raise ValidationError(_('Imported relation must identify exactly one record.'))
                    value = records[0][0]
                elif key in {'debit_val', 'credit_val'}:
                    value = float(value or 0)
                values[key] = value or False
            commands.append(fields.Command.update(self.line_ids[index].id, values) if update_only else fields.Command.create(values))
        self.write({x2many_field: commands})
