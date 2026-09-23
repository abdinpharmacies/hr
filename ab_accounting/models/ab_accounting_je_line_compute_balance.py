# -*- coding: utf-8 -*-

from odoo import models, fields, tools, _
from time import perf_counter

from odoo.exceptions import UserError


class JEComputation(models.AbstractModel):
    _name = 'ab_accounting_je_line_compute_balance'
    _description = 'ab_accounting_je_line_compute_balance'
    pre_balance = fields.Float(compute='_compute_balance', groups="ab_accounting.group_ab_accounting_manager",
                               digits=(16, 2))
    balance_with_type = fields.Char(compute='_compute_balance', string='Balance(Type)', )
    balance_confirmed = fields.Float(compute='_compute_balance', )
    balance = fields.Float(compute='_compute_balance', )
    available_balance = fields.Float(compute='_compute_balance', )

    negative_balance = fields.Boolean(compute='_compute_balance', )

    def _compute_balance(self):
        """Override this method to compute balance in je header and line."""
        pass

    def compute_balance(self, rec):
        # start = perf_counter()
        if not rec.account_id.calc_balance:
            balance_confirmed = 0
            balance = 0
            pre_balance = 0
            available_balance = 0
            # Forth type is balance with type
        else:
            domain = [
                '|', '|', '|',
                ('account_id.prevent_enquiry', '=', False),
                ('create_uid', '=', self.env.user.id),
                ('create_uid', 'in', self.env.user.responsible_for_ids.ids),
                ('costcenter_id', 'in', self.env.user.costcenter_ids.ids),
                # and account_id
                ('account_id', '=', rec.account_id.id),
            ]
            domain_pre_balance = [('account_id', '=', rec.account_id.id), ]

            if rec.account_id.has_costcenter and rec.costcenter_id:
                domain.append(('costcenter_id', '=', rec.costcenter_id.id))
                domain_pre_balance.append(('costcenter_id', '=', rec.costcenter_id.id))

            if rec.account_id.has_store and rec.store_id:
                domain.append(('store_id', '=', rec.store_id.id))
                domain_pre_balance.append(('store_id', '=', rec.store_id.id))

            balance_list = self._get_balance_list(domain=tuple(domain))
            balance_confirmed = 0
            balance = 0
            if balance_list:
                for balance_item in balance_list:
                    is_confirmed = balance_item.get('is_confirmed')
                    is_posted = balance_item.get('is_posted')
                    if is_confirmed:
                        balance_confirmed += balance_item['net_val']
                    if is_posted:
                        balance += balance_item['net_val']

            available_balance_domain = domain + [('header_id.is_posted', '=', False)]

            pre_balance = sum(je.net_val for je in self.env['ab_accounting_je_line'].sudo().search(domain_pre_balance))

            available_balance = balance + sum(
                je.net_val for je in self.env['ab_accounting_je_line'].sudo().search(available_balance_domain))

        rec.balance_confirmed = balance_confirmed
        rec.pre_balance = pre_balance
        rec.balance = balance
        bal_type = self._get_balance_type(rec)
        rec.balance_with_type = "{0:,.2f} {1}".format(abs(rec.balance), bal_type)
        rec.negative_balance = self._is_negative_balance(rec, available_balance)
        rec.available_balance = rec.negative_balance and abs(available_balance) * -1 or abs(available_balance)

        # end = perf_counter()

    # @tools.ormcache('domain', 'self._uid')
    def _get_balance_list(self, domain):
        domain = list(domain)
        jes = self.env['ab_accounting_je_line_qry'].sudo()
        return jes.read_group(domain=domain,
                              fields=['is_confirmed', 'is_posted', 'net_val:sum'],
                              groupby=['is_confirmed', 'is_posted'],
                              lazy=False)

    @staticmethod
    def _get_balance_type(rec):
        if rec.balance > 0:
            return _("Debit")
        elif rec.balance < 0:
            return _("Credit")
        else:
            return rec.account_id.nature

    @staticmethod
    def _is_negative_balance(rec, balance):
        if rec.account_id.internal_group in {'asset', 'expense'}:
            return balance < 0
        elif rec.account_id.internal_group in {'equity', 'liability', 'income'}:
            return balance > 0
