# -*- coding: utf-8 -*-
import re
import difflib
import logging

from odoo import models, fields, api, _  # noqa
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)
ALLOWED_VALUE = 10


class AccountGuide(models.Model):
    _inherit = 'ab_accounting_account_guide'

    internal_type = fields.Selection(
        selection_add=[('supplier_je', 'Supplier Deduction')],
        ondelete={'supplier_je': 'set default'}
    )


class SupplierClaim(models.Model):
    _name = 'ab_purchase_claim'
    _description = 'ab_purchase_claim'
    _inherit = ['ab_purchase_je_header_delegate_common', 'mail.thread', 'mail.activity.mixin', 'abdin_et.extra_tools']
    _rec_name = 'description'
    _order = 'id desc'

    # Collection Headers
    description = fields.Char(required=True, store=True, readonly=False)
    claim_deliver_day = fields.Date()
    active = fields.Boolean(default=True)

    costcenter_id = fields.Many2one('ab_costcenter', string='Supplier', index=True)
    je_header_ro_id = fields.Many2one(related='je_header_id', string='J.E. Header')
    costcenter_id_domain = fields.Binary(compute='_compute_costcenter_id_domain', compute_sudo=True)

    supplier_balance = fields.Float(compute='_compute_supplier_balance')
    is_closed = fields.Boolean(default=False)
    # Collection Info Readonly
    claim_value = fields.Float(readonly=True)

    instant_cash = fields.Boolean(default=False)

    je_lines_search_ids = fields.Many2many(
        comodel_name='ab_accounting_je_line',
        relation='ab_purchase_claim_je_line_rel',
        column1='claim_id',
        column2='je_line_id',
        string='JE Search',
        domain=lambda self: self._get_je_lines_search_ids_domain(),
    )

    find_what = fields.Selection(
        selection=[
            ('pur_and_notice', 'Purchases and Notices'),
            ('gen_notice', 'General Notices'),
        ], )
    find_by = fields.Selection(
        selection=[
            ('doc_code_and_value', 'Document Code And Value'),
            ('eplus_serial', 'e-Plus Serial'),
        ], default='doc_code_and_value')

    excel_text = fields.Text()
    excel_notes = fields.Text()

    name = fields.Char()
    claim_month = fields.Date()
    claim_deliver_date = fields.Date()

    je_line_ids = fields.One2many('ab_accounting_je_line', 'claim_id', readonly=True)

    distribution_line_ids = fields.One2many('ab_purchase_claim_dist_line', 'claim_id')

    total_supplier_inv_debit = fields.Float(compute='_compute_totals')
    total_supplier_je_debit = fields.Float(compute='_compute_totals')
    total_supplier_credit = fields.Float(compute='_compute_totals')
    total_claim = fields.Float(compute='_compute_totals')

    total_taxes = fields.Float(compute='_compute_totals')

    doc_date_start = fields.Date()
    doc_date_end = fields.Date()

    user_id = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user.id)
    invoice_number_search = fields.Char(compute='_compute_invoice_number_search',
                                        search='_search_invoice_number_search')
    eplus_serial_search = fields.Char(compute='_compute_eplus_serial_search',
                                      search='_search_eplus_serial_search')

    def _compute_invoice_number_search(self):
        for rec in self:
            rec.invoice_number_search = '---'

    def _search_invoice_number_search(self, operator, val):
        if operator != 'ilike':
            raise UserError(_('Operation not supported'))

        invoice_numbers = val.split()
        je_line_ids = self.env['ab_accounting_je_line'].search([('doc_no', 'in', invoice_numbers)])

        ids = je_line_ids.mapped('claim_id').ids
        return [('id', 'in', ids)]

    def _compute_eplus_serial_search(self):
        for rec in self:
            # rec.eplus_serial_search = ','.join(map(str, rec.je_line_ids.mapped('je_eplus_serial')))
            rec.eplus_serial_search = '---'

    def _search_eplus_serial_search(self, operator, val):
        if operator != 'ilike':
            raise UserError(_('Operation not supported'))

        eplus_serials = val.split()
        je_line_ids = self.env['ab_accounting_je_line'].search([('je_eplus_serial', 'in', eplus_serials)])

        ids = je_line_ids.mapped('claim_id').ids
        return [('id', 'in', ids)]

    @api.constrains('costcenter_id', 'line_ids', 'account_id', 'je_line_ids')
    def _constrains_ab_purchase_claim(self):
        supplier_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_suppliers').id
        for rec in self:
            if rec.account_id.id != supplier_account_id:
                raise ValidationError(_("Account Must Be 'Supplier Account'"))

            if any(line.costcenter_id != rec.costcenter_id for line in rec.line_ids):
                raise ValidationError(_("Costcenter in JE lines must be same as Claim Costcenter"))

    @api.depends('costcenter_id')
    def _compute_supplier_balance(self):
        for rec in self:
            je_lines = self.env['ab_accounting_je_line'].search(
                [
                    ('costcenter_id', '=', rec.costcenter_id.id),
                    ('header_id.is_posted', '=', True),
                    ('account_id', '=', rec.account_id.id),
                ]
            )

            rec.supplier_balance = sum(line.net_val for line in je_lines) * -1

    @api.depends('instant_cash')
    def _compute_costcenter_id_domain(self):
        for rec in self:
            if rec.instant_cash:
                costcenter_ids = self.env['ab_supplier_bracket'].sudo().search([]).filtered(
                    lambda s: s.payment_type == 'instant_cash').mapped('supplier_id.id')
                domain = fields.Domain('id', 'in', costcenter_ids)
            else:
                supplier_mo = self.env['ab_supplier'].with_context(active_test=False)
                costcenter_ids = supplier_mo.search([]).mapped('costcenter_id.id')
                domain = fields.Domain('id', 'in', costcenter_ids)

            rec.costcenter_id_domain = list(domain)

    def _get_je_lines_search_ids_domain(self):
        supplier_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_suppliers').id
        return [('account_id', '=', supplier_account_id)]

    def btn_search_available_invoices(self):
        pass

    @api.depends('je_line_ids', 'je_line_ids.debit_val', 'je_line_ids.credit_val')
    def _compute_totals(self):
        vat_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_vat').id
        inventory_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_inventory').id

        for rec in self:
            rec.total_supplier_je_debit = sum(line.debit_val for line in rec.je_line_ids
                                              if
                                              line.header_id.res_header_ref and 'purchase_claim' in line.header_id.res_header_ref)

            total_supplier_debit = sum(line.debit_val for line in rec.je_line_ids)
            rec.total_supplier_inv_debit = total_supplier_debit - rec.total_supplier_je_debit

            rec.total_supplier_credit = sum(line.credit_val for line in rec.je_line_ids)
            rec.total_claim = rec.total_supplier_credit - (rec.total_supplier_je_debit + rec.total_supplier_inv_debit)
            je_headers = rec.je_line_ids.mapped('header_id')

            rec.total_taxes = sum(
                je_headers.line_ids.filtered(lambda l: l.account_id.id == vat_account_id).mapped('net_val')
            )

            # rec.total_inventory = sum(
            #     je_headers.line_ids.filtered(lambda l: l.account_id.id == inventory_account_id).mapped('net_val')
            # )

    @api.depends('distribution_line_ids', 'total_claim')
    def _compute_distribution_calc(self):
        for rec in self:
            rec.total_discount = sum(line.value * (line.discount / 100) for line in rec.distribution_line_ids)

            rec.distribution_rest = rec.total_claim - sum(line.value for line in rec.distribution_line_ids)

    ##############################################################################################################
    # Buttons Methods #######################################################################################
    def btn_freeze(self):
        self.je_header_id.btn_freeze()

    def btn_unfreeze(self):
        self.je_header_id.btn_unfreeze()

    def btn_generate_auto_jes(self):
        if not self.je_line_ids:
            return

        source_tax_account_id = 543
        for line in self.je_line_ids:
            if line.net_val * -1 >= 300:
                pass
        total_source_taxes = sum(je.net_val * -0.01
                                 for je in self.je_line_ids if je.net_val * -1 >= 300)

        suspend_supplier_account_id = 486

        store_id = self.je_line_ids[0].store_id.id

        self.write({'line_ids': [
            (0, 0, {
                'account_id': self.account_id.id,
                'store_id': store_id,
                'debit_val': self.total_claim,
                'costcenter_id': self.costcenter_id.id,
            }),
        ]})

    def btn_link_je_to_claim(self):
        domain = self._get_je_line_domain()
        je_lines = self.env['ab_accounting_je_line'].sudo().search(domain)
        self._validate_je_lines(je_lines)
        self.write({
            'je_lines_search_ids': [(6, 0, [])],
            'from_excel': ''
        })
        je_lines.write({'claim_id': self.id})

    def _validate_je_lines(self, je_lines):
        # Invoices in other Claims
        # Invoices for other Suppliers
        err_list = []
        for line in je_lines:
            if line.claim_id and line.claim_id.id != self.id:
                err = f"e-Plus Serial: {line.je_eplus_serial} - In other Claims {line.claim_id.description}"
                err_list.append(err)
            if line.costcenter_id.id != self.costcenter_id.id:
                err = f"e-Plus Serial: {line.je_eplus_serial} - Not for this Supplier {line.costcenter_id.name}"
                err_list.append(err)
        if err_list:
            raise ValidationError(_("INVOICES HAVE ERRORS.\n" + "\n".join(err_list)))

    def btn_remove_invoices_from_claim(self):
        # self.excel_text = ""
        self.excel_notes = ""
        self.je_line_ids.claim_id = False
        # self.write({'je_lines_search_ids': [(6, 0, [])]})

    ##############################################################################################################
    def _get_je_line_domain(self):
        try:
            code_value_found = set()
            code_value_set = set()
            supplier_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_suppliers').id
            domain = [('account_id', '=', supplier_account_id), ]
            pur_mo = self.env['ab_purchase_header'].sudo()
            je_mo = self.env['ab_accounting_je_line'].sudo()
            je_ids = []
            if self.je_lines_search_ids:
                je_ids += self.je_lines_search_ids.ids

            if self.doc_date_start and self.doc_date_end:
                domain += [('due_date', '>=', self.doc_date_start), ('due_date', '<=', self.doc_date_end)]

            if not self.excel_text:
                domain += [('costcenter_id', '=', self.costcenter_id.id), ]

            if self.excel_text and self.excel_text.strip():
                # invoices = self.excel_text.split('\n')
                invoices = re.split(r'\n', self.excel_text)
                if self.find_by == 'doc_code_and_value':
                    code_value_list = [inv.split() for inv in invoices if inv]
                    code_value_set = set((t[0], int(float(t[1])) if len(t) > 1 else 0) for t in code_value_list)
                    je_mo = self.env['ab_accounting_je_line']

                    je_header_ids = []
                    code_value_found = []
                    je_lines = je_mo.search(
                        [('costcenter_id', '=', self.costcenter_id.id),
                         ('account_id', '=', self.account_id.id),
                         ('claim_id', '=', False),
                         ])
                    for je in je_lines:
                        code = je.doc_no
                        code = re.sub(r'[a-zA-Z]', '', code)
                        t = (code, int(je.net_val * -1))
                        if t in code_value_set:
                            je_header_ids.append(je.header_id.id)
                            code_value_found.append(t)
                        t_code_only = (code, 0)
                        if t_code_only in code_value_set:
                            je_header_ids.append(je.header_id.id)
                            code_value_found.append(t_code_only)

                    pur_headers = pur_mo.search([('je_header_id', 'in', je_header_ids)])

                    je_ids += self._get_je_ids_from_pur_headers(pur_headers)

                    domain += [('id', 'in', je_ids)]

                if self.find_by == 'eplus_serial':
                    if not all(s.isdigit() for s in invoices if s):
                        raise ValidationError(_("INVOICES SERIAL MUST BE DIGITS."))

                    je_mo = self.env['ab_accounting_je_line'].sudo()
                    je_ids += je_mo.search([('je_eplus_serial', 'in', [int(s) for s in invoices if s])]).ids

                    domain += [('id', 'in', je_ids)]

            current_code_value_set = {(str(j.doc_no), int(j.net_val * -1)) for j in self.je_line_ids}
            diff_set = code_value_set - set(code_value_found) - current_code_value_set
            je_lines = je_mo.search(
                [
                    # ('costcenter_id', '=', self.costcenter_id.id),
                    ('account_id', '=', self.account_id.id),
                    ('claim_id', '=', False)
                ])

            possible_match_list = self._get_possible_matches(diff_set, je_lines, self.costcenter_id)

            self.excel_notes = '\n'.join(po for po in possible_match_list)
            domain += [('id', 'in', je_ids)] if je_ids else []
            return domain

        except Exception as e:
            _logger.warning(repr(e))
            raise ValidationError(str(e))

    @staticmethod
    def _get_possible_matches(diff_set, je_lines, claim_cc):
        possible_matches = ['------------------------------']
        if len(diff_set) > 5:
            raise ValidationError(_("It will take too long time for get possibilities for next invoices\n" +
                                    '\n'.join(str(s) for s in diff_set)))
        for code, val in diff_set:
            possible_match = []
            for je in je_lines:
                doc_no = je.doc_no or ""
                code_ratio = (difflib.SequenceMatcher(None, code, str(doc_no)).ratio()) * 100
                val_min = min([val, je.net_val * -1])
                val_max = max([val, je.net_val * -1])
                val_diff = val_max - val_min

                val_ratio = (val_min - val_diff) / val_max * 100 if val_max else 0
                total_ratio = round((code_ratio + val_ratio) / 2)  # round(number) -> int

                if total_ratio > 90:
                    # "[CC Code: 1-1470]"
                    another_supplier = f"\t[CC Code: {je.costcenter_id.code}]" if je.costcenter_id != claim_cc else ""
                    # "13331914     5559    100%
                    # "13331914     5559    [CC Code: 1-1470]    100%
                    possible_match.append(f"{doc_no}\t{int(je.net_val * -1)}{another_supplier}\t{total_ratio}")

            if possible_match and len(possible_match) > 0:
                possible_match.sort(key=lambda x: int(x.split()[-1]), reverse=True)
                possible_match = [f"{match}%" for match in possible_match]
            else:
                possible_match.append("X NO MATCH X")

            possible_match_lines = '\n'.join(possible_match)
            possible_match = f"{code}\t{val}\n{possible_match_lines}"

            possible_matches.append(possible_match)
            possible_matches.append('------------------------------')

        return possible_matches

    def _get_je_ids_from_pur_headers(self, pur_headers):
        # pur_mo = self.env['ab_purchase_header'].sudo()
        pur_notice_mo = self.env['ab_purchase_notice_header'].sudo()
        pur_notice_headers = pur_notice_mo.search([('purchase_header_id', 'in', pur_headers.ids)])

        je_line_mo = self.env['ab_accounting_je_line'].sudo()

        je_headers = pur_headers.mapped('je_header_id') | pur_notice_headers.mapped('je_header_id')

        je_lines = je_line_mo.search([('header_id', 'in', je_headers.ids)])

        return je_lines.ids

    ##############################################################################################################
    def btn_set_claim_deliver_date(self):
        self.ensure_one()

    ##############################################################################################################
    def btn_delay_rest_claim(self):
        store_id = 78
        claim_rest_credit = self.total_claim if self.total_claim > 0 else 0
        claim_rest_debit = self.total_claim * -1 if self.total_claim <= 0 else 0

        self.write({'line_ids': [
            (0, 0, {
                'account_id': self.account_id.id,
                'store_id': store_id,
                'credit_val': claim_rest_credit,
                'debit_val': claim_rest_debit,
                'costcenter_id': self.costcenter_id.id,
                'explain': self.description,
                'auto_link_claim': False
            }),
            (0, 0, {
                'account_id': self.account_id.id,
                'store_id': store_id,
                'debit_val': claim_rest_credit,
                'credit_val': claim_rest_debit,
                'explain': self.description,
                'costcenter_id': self.costcenter_id.id,
                'auto_link_claim': True
            }),
        ]})

    def btn_post_je(self):
        self._check_claim_is_balanced()
        self.je_header_id.btn_post_je()

    def btn_confirm_all_je(self):
        if abs(self.total_claim) > ALLOWED_VALUE:
            raise ValidationError(_("Claim is not balanced!"))

        self.je_header_id.btn_confirm_all_je()

    def _check_claim_is_balanced(self):
        claim_is_not_balanced = abs(self.total_claim) > ALLOWED_VALUE
        has_invoice_or_notice = abs(self.total_supplier_credit) > 0 or abs(self.total_supplier_inv_debit) > 0
        if claim_is_not_balanced and has_invoice_or_notice:
            raise ValidationError(_("Claim is not balanced, you can delay claim for future closing."))

    def btn_filter_claim_lines(self):
        return {
            'name': _('.'),
            "type": "ir.actions.act_window",
            "res_model": "ab_accounting_je_line",
            "views": [[False, "tree"]],
            "domain": [('claim_id', '=', self.id)],
            "target": "current",
        }

    def write(self, vals):
        # if 'claim_month' in vals and vals['claim_month']:
        #     claim_month_list = vals['claim_month'].split('-')
        #     claim_month_list[2] = '1'
        #     vals['claim_month'] = '-'.join(claim_month_list)

        res = super().write(vals)
        for rec in self:
            if rec.is_frozen and rec.create_uid == self.env.user in vals:
                raise ValidationError(_("Claim is Frozen!\nAsk 'Reviewer' to unfreeze it."))
        return res

    # def unlink(self):
    #     for rec in self:
    #         rec.je_header_id.unlink()
    #
    #     res = super(SupplierClaim, self).unlink()
    #     return res
