import datetime
import itertools

from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, ValidationError
from .ab_accounting_je_header import _HEADER_EDIT, _WORKFLOW
import math


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
        self.env.flush_all()
        sql = """
        select je.id from ab_accounting_je_header he
        join ab_accounting_je_line je on he.id = je.header_id
        where
            je.active=True
            and he.costcenter_id IS NOT DISTINCT FROM je.costcenter_id
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

    @api.depends('is_posted', 'is_confirmed', 'create_uid')
    @api.depends_context('uid')
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
            if not self.env.su and self.env.context.get('accounting_reverse') is not _WORKFLOW:
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

    def _validate_posting_line(self):
        for rec in self:
            rec.account_id._validate_posting_account()
            if not rec.account_id or not rec.explain:
                raise ValidationError(_('Account and explanation are required.'))
            if rec.account_id.has_store and not rec.store_id:
                raise ValidationError(_('This account requires a store.'))
            if rec.store_id and (not rec.store_id.active or (not self.env.su and rec.store_id in self.env.user.store_ids)):
                raise ValidationError(_('Store is inactive or forbidden for this user.'))
            if rec.account_id.has_due_date and not rec.due_date:
                raise ValidationError(_('This account requires a due date.'))
            if rec.account_id.has_costcenter and not rec.costcenter_id:
                raise ValidationError(_('This account requires a cost center.'))
            if (rec.costcenter_id and not rec.costcenter_id.active) or (rec.account_id.costcenter_ids and rec.costcenter_id not in rec.account_id.costcenter_ids):
                raise ValidationError(_('Cost center is inactive or not allowed for this account.'))
            if not rec.debit_val and not rec.credit_val:
                raise ValidationError(_('A posted line requires a nonzero debit or credit.'))

    @staticmethod
    def _validate_amount_values(values):
        from decimal import Decimal, InvalidOperation
        for key in ('debit_val', 'credit_val'):
            if key not in values:
                continue
            try:
                amount = Decimal(str(values[key] or 0))
                valid = amount.is_finite() and amount >= 0 and amount == amount.quantize(Decimal('0.01'))
            except (InvalidOperation, ValueError, TypeError):
                valid = False
            if not valid:
                raise ValidationError(_('Debit and credit must be finite non-negative amounts with at most two decimals.'))

    @api.constrains('debit_val', 'credit_val')
    def _check_amounts(self):
        for rec in self:
            for value in (rec.debit_val, rec.credit_val):
                if not math.isfinite(value) or value < 0 or abs(value - round(value, 2)) > 1e-9:
                    raise ValidationError(_('Debit and credit must be finite non-negative amounts with at most two decimals.'))
            if rec.debit_val and rec.credit_val:
                raise ValidationError(_('A line may contain either debit or credit, never both.'))

    def unlink(self):
        if any(self.mapped('is_posted')):
            raise UserError(_('Posted journals must be reversed, not deleted.'))
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self._validate_amount_values(values)
        headers = self.env['ab_accounting_je_header'].browse([v.get('header_id') for v in vals_list if v.get('header_id')])
        if headers.filtered('is_posted') and self.env.context.get('accounting_reverse') is not _WORKFLOW:
            raise UserError(_('Lines cannot be added to a posted journal.'))
        if any(v.get('is_confirmed') for v in vals_list) and self.env.context.get('accounting_reverse') is not _WORKFLOW:
            raise UserError(_('Use the confirmation action.'))
        return super().create(vals_list)

    def write(self, vals):
        self._validate_amount_values(vals)
        workflow = self.env.context.get('accounting_workflow') is _WORKFLOW
        reverse = self.env.context.get('accounting_reverse') is _WORKFLOW
        from_header = self.env.context.get('accounting_header_edit') is _HEADER_EDIT
        for rec in self:
            if 'header_id' in vals and vals['header_id'] != rec.header_id.id:
                raise UserError(_('Journal lines cannot be moved to another header.'))
            if 'is_confirmed' in vals and not workflow and not reverse:
                raise UserError(_('Use the confirmation action.'))
            if rec.is_posted and not workflow and not reverse:
                if rec.is_frozen and not self.env.su and (rec.create_uid == self.env.user or not self.env.user.has_group('ab_accounting.group_ab_accounting_reviewer') or rec.create_uid not in self.env.user.responsible_for_ids):
                    raise UserError(_('Only the responsible reviewer can edit a frozen journal.'))
                role = 'allow_review' if rec.is_confirmed or rec.create_uid != self.env.user else 'allow_entry'
                allowed = set(self.env.user.allowed_field_ids.filtered(role).mapped('allowed_field_id.name'))
                if not self.env.su and set(vals) - allowed:
                    raise UserError(_('This edit is not permitted by your allowed-field authorizations.'))
                if 'active' in vals:
                    raise UserError(_('Use the reversal action to deactivate a posted line.'))
        with self.env.cr.savepoint():
            result = super().write(vals)
            if not from_header and not reverse:
                self.mapped('header_id').filtered('is_posted')._validate_posting()
            return result

    def _get_fields_string(self, flds):
        flds_list = [self._get_fld_string(fld) for fld in flds]
        return ', '.join(flds_list)

    def _get_fld_string(self, fld):
        model_name = 'ab_accounting_je_line'
        fld_string = self.fields_get([fld])[fld]['string']
        fld_string = fld_string or fld
        return fld_string

    @api.depends('account_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s//%s' % (rec.account_id.name or '', rec.id)

    @api.model
    def _search_display_name(self, operator, value):
        domain = [('account_id.name', operator, value)]
        if isinstance(value, str) and value.isdigit():
            return list(fields.Domain.OR([domain, [('id', '=', int(value))]]))
        return domain

    def btn_confirm_je(self):
        for rec in self:
            if not rec.allow_confirm or not self.env.user.has_group('ab_accounting.group_ab_accounting_reviewer'):
                raise UserError(_('Only the responsible reviewer can confirm a posted line.'))
        with self.env.cr.savepoint():
            self.with_context(accounting_workflow=_WORKFLOW).write({'is_confirmed': True})
            self.mapped('header_id').btn_freeze()

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
        self.header_id.with_context(accounting_reverse=_WORKFLOW).write({
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
