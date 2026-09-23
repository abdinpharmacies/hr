import datetime
import itertools

from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, ValidationError


class JournalEntries(models.Model):
    _name = 'ab_accounting_je_line'
    _description = 'ab_accounting_je_line'
    _inherit = ['ab_accounting_je_line_common', 'ab_accounting_je_line_compute_balance']
    _rec_name = 'explain'
    _order = 'id desc'

    message = fields.Char()
    image = fields.Image()
    old_je_serial = fields.Integer(index=True)
    user_line_owner = fields.Many2one('res.users', readonly=True)

    header_id = fields.Many2one('ab_accounting_je_header',
                                index=True,
                                required=True,
                                ondelete='cascade', readonly=True)

    with_account_id = fields.Many2one(related='header_id.account_id', string='With Account')
    internal_type = fields.Selection(related='account_id.internal_type')
    parent_path = fields.Char(related='account_id.parent_path')
    reconcile = fields.Boolean(related='account_id.reconcile')
    linked_account_id = fields.Many2one(related='account_id.linked_account_id')

    has_due_date = fields.Boolean(related='account_id.has_due_date')
    has_costcenter = fields.Boolean(related='account_id.has_costcenter')
    has_store = fields.Boolean(related='account_id.has_store')
    posted_date = fields.Date(related='header_id.posted_date', readonly=True)
    is_frozen = fields.Boolean(related='header_id.is_frozen')
    is_posted = fields.Boolean(related='header_id.is_posted')
    doctype_id = fields.Many2one(related='header_id.doctype_id')

    net_val = fields.Float(compute='_compute_net_val', store=True, readonly=True, digits=(16, 2))

    allow_confirm = fields.Boolean(compute='_compute_allow_confirm',
                                   search='_search_allow_confirm')
    allow_reverse = fields.Boolean(compute='_compute_allow_reverse',
                                   search='_search_allow_reverse')

    is_header = fields.Boolean(compute='_compute_is_header',
                               search='_search_is_header',
                               compute_sudo=True, )
    responsibility = fields.Boolean(compute='_compute_responsibility',
                                    search='_search_responsibility',
                                    )

    # firing_action = fields.Boolean(compute='_compute_firing_action')
    # last_deduction = fields.Date(compute='_compute_last_deduction')
    #
    # def _compute_firing_action(self):
    #     for rec in self:
    #         self.sudo().search([('costcenter_id', '=', rec.costcenter_id.id),])

    @api.depends('header_id', 'account_id', 'costcenter_id')
    def _compute_is_header(self):
        for rec in self:
            rec.is_header = (rec.header_id.account_id.id == rec.account_id.id
                             and rec.header_id.costcenter_id.id == rec.costcenter_id.id)

    def _search_is_header(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))
        self.flush()
        sql = """
        select je.id from ab_accounting_je_header he 
        join ab_accounting_je_line je on he.id = je.header_id
        where
            je.active=True
            and he.costcenter_id=je.costcenter_id
            and he.account_id=je.account_id
        """
        self.env.cr.execute(sql)
        je = self.env.cr.fetchall()
        je_ids = list(itertools.chain.from_iterable(je))
        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', je_ids)]

    @api.depends('account_id', 'due_date', 'settlement_date')
    def _compute_final_date(self):
        for rec in self:
            if not rec.account_id.reconcile:
                rec.final_date = rec.due_date
            else:
                rec.final_date = rec.settlement_date

    def _search_responsibility(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        je_ids = self.sudo().search([
            '|',
            ('create_uid', '=', self.env.user.id),
            ('create_uid', 'in', self.env.user.responsible_for_ids.ids),
        ], ).ids

        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', je_ids)]

    @api.depends('create_uid')
    def _compute_responsibility(self):
        for rec in self:
            if rec.create_uid.id in self.env.user.responsible_for_ids.ids:
                rec.responsibility = True
            else:
                rec.responsibility = False

    @api.depends('account_id', 'costcenter_id', 'credit_val', 'debit_val')
    def _compute_balance(self):
        for rec in self:
            self.compute_balance(rec)

    @api.depends('account_id')
    def _compute_allow_confirm(self):
        for rec in self:
            if rec.is_posted and not rec.is_confirmed:
                rec.allow_confirm = rec.create_uid.id in self.env.user.responsible_for_ids.ids
            else:
                rec.allow_confirm = False

    def _search_allow_confirm(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        je_ids = self.sudo().search([
            ('is_posted', '=', True),
            ('is_confirmed', '=', False),
            ('create_uid', 'in', self.env.user.responsible_for_ids.ids),
        ], ).ids

        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', je_ids)]

    @api.depends('is_header', 'costcenter_id', 'account_id')
    def _compute_allow_reverse(self):
        for rec in self:
            if rec.is_posted and rec.is_confirmed and not rec.is_header:
                rec.allow_reverse = True
            else:
                rec.allow_reverse = False

    def _search_allow_reverse(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        je_ids = self.sudo().search([
            ('is_posted', '=', True),
            ('is_confirmed', '=', True),
            ('is_header', '=', False),
        ], ).ids

        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', je_ids)]

    @api.constrains('debit_val', 'credit_val', 'account_id',
                    'costcenter_id', 'header_id', 'settlement_date', 'due_date',
                    'explain', 'store_id', 'is_confirmed', 'create_uid')
    def _constraint_journal_entries(self):
        for rec in self:
            if not self.env.user.has_group('base.group_system'):
                if rec.create_uid != rec.header_id.create_uid:
                    raise ValidationError(_("Header Creator must be same as line Creator"))
                if rec.is_frozen and rec.create_uid.id == self.env.uid:
                    raise ValidationError(
                        _("Creator – %s – cannot edit their records because the reviewer has frozen them." % (
                        self.env.user.name,)))
            if not rec.is_posted and rec.is_confirmed:
                raise ValidationError(_("JE Must Posted First"))
            if rec.settlement_date and rec.settlement_date > fields.Date.today():
                raise ValidationError(_("Settlement Date Can not be in future"))
            if rec.debit_val < 0 or rec.credit_val < 0:
                raise ValidationError(_("Debit and Credit Should NOT be less than 0\nJE ID: %s\nDebit: %s\nCredit: %s" % (
                        rec.id, rec.debit_val, rec.credit_val,)))

    @api.depends('debit_val', 'credit_val')
    def _compute_net_val(self):
        for rec in self:
            rec.net_val = rec.debit_val - rec.credit_val

    def unlink(self):
        for rec in self:
            if rec.is_posted:
                if not self.env.user.has_group('base.group_system'):
                    raise UserError("YOU CAN NOT DELETE JOURNAL ENTRIES, PLEASE REVERSE IT.")
        res = super().unlink()
        return res

    def _fields_from_header(self, vals):
        flds = {'account_id', 'costcenter_id', 'debit_val', 'credit_val', 'active'}
        from_header = self.env.context.get('from_header')
        return from_header or not set(vals).intersection(flds)

    def write(self, vals):
        if self.env.user.has_group("base.group_system"):
            return super().write(vals)

        if not self._fields_from_header(vals):
            raise UserError(_("Can not edit these fields from here,"
                              "\nplease edit them from there."
                              "\n You can double click 'HEADER ID' to goto that header"))
        if self.env.context.get('sudo_confirm'):
            return super().write(vals)

        for rec in self:
            is_posted_old_status = rec.header_id.is_posted
            is_confirmed_old_status = rec.is_confirmed

            # @todo Prevent these fields with write access
            always_allowed = ['active', 'is_confirmed', 'msg', 'claim_id', 'header_id',
                              'vendor_id', 'is_paid', 'user_line_owner', 'fixed_asset_id']

            res = super().write(vals)
            if rec.create_uid.id == self._uid:
                allowed_fields_for_user = self.env.user.allowed_field_ids.filtered("allow_entry").mapped(
                    "allowed_field_id.name")
            else:
                allowed_fields_for_user = self.env.user.allowed_field_ids.filtered("allow_review").mapped(
                    "allowed_field_id.name")

            if is_confirmed_old_status:
                allowed_fields_for_user = self.env.user.allowed_field_ids.filtered("allow_review").mapped(
                    "allowed_field_id.name")

            allowed_fields_for_user.extend(always_allowed)

            if is_posted_old_status:
                if not set(vals).issubset(allowed_fields_for_user):
                    show_allowed_fields_for_user = set(allowed_fields_for_user) - set(always_allowed)
                    raise UserError(
                        _("YOU CAN EDIT ONLY THESE FIELDS "
                          f"({self._get_fields_string(list(show_allowed_fields_for_user))})."
                          "\nASK CREATOR TO EDIT THEM"))

            return res

    def _get_fields_string(self, flds):
        flds_list = [self._get_fld_string(fld) for fld in flds]
        return ', '.join(flds_list)

    def _get_fld_string(self, fld):
        model_name = 'ab_accounting_je_line'
        fld_string = self.env['ir.translation'].get_field_string(model_name)[fld]
        fld_string = fld_string or fld
        return fld_string

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        args += ['|',
                 ('account_id.name', operator, name),
                 ('id', '=ilike', name),
                 ]

        ids = self._search(args, limit=limit, access_rights_uid=name_get_uid)
        return ids

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, '%s//%s' % (rec.account_id.name, rec.id,)))
        return res

    def btn_confirm_je(self):
        if self.allow_confirm:
            self.is_confirmed = True
            self.header_id.is_frozen = True

    def btn_reverse_je(self):
        self = self.with_context(from_header=True)
        self.ensure_one()
        self._check_is_creator()
        self._check_is_allow_reverse()
        reversed_je = self._get_reverse_header_dict()
        if reversed_je:
            self._write_to_header(reversed_je)
        else:
            raise UserError(_("Can not find Header in current journal entries."
                              "\n\tPlease reverse JE manually."))

    def _write_to_header(self, reversed_je):
        self.header_id.sudo().write({
            'line_ids': [(1, self.id, {'active': False, 'is_confirmed': True}),
                         (0, 0, reversed_je)],
        })

    def _check_is_creator(self):
        if self.create_uid.id != self.env.uid:
            raise UserError(_("Only creator can reverse JE."))

    def _check_is_allow_reverse(self):
        if not self.allow_reverse:
            raise UserError(_("Reverse is not allowed."))

    def _get_reverse_header_dict(self):
        reversed_je = {}
        flds = ['store_id', 'due_date', 'costcenter_id', 'doc_no', 'explain', 'account_id']
        header_je = self.header_id.line_ids.filtered('is_header')
        if header_je:
            reversed_je = {fld: self._get_field_value(header_je[0], fld)
                           for fld in flds}

            reversed_je.update({'credit_val': self.credit_val,
                                'debit_val': self.debit_val,
                                'is_confirmed': True, })
        return reversed_je

    @staticmethod
    def _get_field_value(move, fld):
        line_fields = move._fields
        field = line_fields[fld]
        field_type = field.__class__.__name__
        if field_type == 'Many2one':
            return getattr(move, fld).id
        else:
            return getattr(move, fld)

    @staticmethod
    def _get_je_balance_status(lines):
        total_debit = 0
        total_credit = 0
        for line in lines:
            total_debit += line.debit_val
            total_credit += line.credit_val
        return total_debit == total_credit, total_debit, total_credit

    def check_valid_deduction(self):
        firing_parent_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_firing_parent').id

        if self.account_id.parent_id.id == firing_parent_account_id:  # سلف وعهد وخصومات
            is_costcenter_forbidden = self.env['ab_costcenter_deduction_forbidden'].sudo().search_count(
                [('costcenter_id', '=', self.costcenter_id.id)])
            if is_costcenter_forbidden:
                raise ValidationError(_(f"""You can not add any deductions on this costcenter (not working employee):
                 {self.costcenter_id.code}-{self.costcenter_id.name}"""))

        if self.account_id.salary_deduction:  # سلف وخصومات
            is_costcenter_month_prevented = self.env[
                'ab_costcenter_deduction_month_prevented'].sudo().search_count(
                [('costcenter_id', '=', self.costcenter_id.id),
                 ('till_month', '>=', self.due_date), ])
            if is_costcenter_month_prevented:
                raise ValidationError(_(f"""You can not add any deduction on this costcenter in this due date:
                 {self.due_date}
                 {self.costcenter_id.code}-{self.costcenter_id.name}
---------------Please change due date -----------------"""))
