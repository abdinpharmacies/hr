# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import UserError
from lxml import etree
from .extra_funcs import Many2oneUnconstraint


# from math import ceil
# from dateutil import parser

class Customer(models.Model):
    _name = 'abdin_eplus.customer'
    _description = 'abdin_eplus Customer'
    _rec_name = 'cust_name_ar'
    _order = 'tup desc'
    cust_id = fields.Integer(readonly=True, index=True)
    cust_code = fields.Char(readonly=True, )
    cust_name_ar = fields.Char(readonly=True, )
    cust_parent = Many2oneUnconstraint('abdin_eplus.customer', readonly=True)
    cust_type = fields.Integer(readonly=True, index=True)
    tup = fields.Datetime(readonly=True, index=True)

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        args += ['|',
                 ('cust_name_ar', operator, name),
                 ('cust_code', '=ilike', name),
                 ]

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


class CustomerContract(models.Model):
    _name = 'abdin_eplus.customer_contracts'
    _description = 'abdin_eplus Customer Contract'
    _rec_name = 'cc_name'
    _order = 'tup desc'
    cc_id = fields.Integer(readonly=True, index=True)
    cc_cust_id = fields.Char(readonly=True, )
    cc_name = fields.Char(readonly=True, )
    cc_pay_perc = fields.Float(readonly=True, )
    cc_dis_per_for_cust = fields.Float(readonly=True, )
    tup = fields.Datetime(readonly=True, index=True)


class StoreTransH(models.Model):
    _name = 'abdin_eplus.store_trans_h'
    _description = 'abdin_eplus Employees'

    stnh_id = fields.Integer(readonly=True, index=True)
    stnh_f_sto_id = fields.Integer(readonly=True, index=True)
    stnh_t_sto_id = fields.Integer(readonly=True, )
    stnh_tot_sell_value = fields.Float(readonly=True, )
    stnh_tot_cost_value = fields.Float(readonly=True, )
    stnh_no_items = fields.Integer(readonly=True, )
    stnh_notes = fields.Char(readonly=True, )
    stnh_flag = fields.Char(readonly=True, )
    sec_insert_uid = fields.Integer(readonly=True, )
    sec_insert_date = fields.Datetime(readonly=True, )
    sec_update_uid = fields.Integer(readonly=True, )
    sec_update_date = fields.Datetime(readonly=True, )
    delivery_emp = Many2oneUnconstraint('abdin_eplus.employee', readonly=True, )
    paid_points = fields.Float(readonly=True, index=True)

    _store_trans_h__from_store_trans_id_unique = models.Constraint('unique(stnh_id,stnh_f_sto_id)', 'Trans is Duplicated.')


class Employee(models.Model):
    _name = 'abdin_eplus.employee'
    _description = 'abdin_eplus Employees'
    _rec_name = 'e_name'
    _order = 'tup desc'

    e_id = fields.Integer(readonly=True, index=True)
    e_code = fields.Char(readonly=True, )
    e_name = fields.Char(readonly=True, )
    e_active = fields.Integer(readonly=True)
    e_delivery = fields.Integer(readonly=True)
    user_id = fields.Many2one('res.users')
    tup = fields.Datetime(readonly=True, index=True)


"""
select pth_id,itm_id,qnty,bonus,itm_back_qty,itm_back_bonus,itm_cost,sec_insert_date,sec_update_date from pur_trans_d
"""


class PurchaseBillDetail(models.Model):
    _name = 'abdin_eplus.pur_trans_d'
    _description = 'abdin_eplus pur_trans_d'
    _rec_name = 'pth_id'
    _order = 'tup desc'
    serial = fields.Integer()
    pth_id = Many2oneUnconstraint('abdin_eplus.pur_trans_h', index=True)
    itm_id = Many2oneUnconstraint('abdin_eplus.item_catalog')
    qnty = fields.Float()
    bonus = fields.Float()
    itm_back_qty = fields.Float()
    itm_back_bonus = fields.Float()
    itm_cost = fields.Float()
    sec_insert_date = fields.Datetime()
    sec_update_date = fields.Datetime()
    tup = fields.Datetime(readonly=True, index=True)


class PurchaseBill(models.Model):
    _name = 'abdin_eplus.pur_trans_h'
    _description = 'abdin_eplus pur_trans_h'
    _rec_name = 'pth_id'
    _order = 'tup desc'

    pth_id = fields.Integer(readonly=True, index=True)
    sto_id = Many2oneUnconstraint('abdin_eplus.store', readonly=True)
    ven_id = Many2oneUnconstraint('abdin_eplus.vendor', readonly=True)
    ven_tel = fields.Char(related='ven_id.ven_tel', string='Tax Reg No')
    total_bill = fields.Float(readonly=True)
    total_after_back = fields.Float(readonly=True)
    ven_bill_no = fields.Char(index=True, readonly=True)
    pth_notice = fields.Char(readonly=True)
    purchase_line_ids = fields.One2many('abdin_eplus.pur_trans_d', 'pth_id', readonly=True)
    sec_insert_date = fields.Datetime(index=True, readonly=True)
    tup = fields.Datetime(readonly=True, index=True)


class RSalesTransH(models.Model):
    _name = 'abdin_eplus.r_sales_trans_h'
    _description = 'abdin_eplus sales header branches'
    _rec_name = 'sth_id'
    _order = 'sec_insert_date_h desc'

    bill_day = fields.Date(readonly=True, string="Bill Day", index=True)
    sto_id = Many2oneUnconstraint('abdin_eplus.store', index=True, required=True, readonly=True, string='Store')
    sth_id = fields.Integer(readonly=True, index=True, required=True, string='Bill ID')
    bill_type = fields.Selection(readonly=True,
                                 selection=[('1', 'Cash'), ('2', 'Vendor Offers'), ('3', 'Contract')])
    cust_id = Many2oneUnconstraint('abdin_eplus.customer', index=True, readonly=True, string='Customer')
    cust_parent = Many2oneUnconstraint('abdin_eplus.customer', readonly=True, string='Customer Parent')
    items_count = fields.Float(readonly=True, )
    total_sales_d = fields.Float(readonly=True, )
    total_sales_h = fields.Float(readonly=True, )
    total_exchange_h = fields.Float(readonly=True, )
    total_bill_after_disc_h = fields.Float(readonly=True, )
    total_disc_percent_h = fields.Float(readonly=True, )
    total_disc_money_h = fields.Float(readonly=True, )
    extra_expenses_h = fields.Float(readonly=True, )
    total_bill_after_disc_d = fields.Float(readonly=True, )
    cash_h = fields.Float(readonly=True, )
    loaded_value_contract = fields.Float(readonly=True, )
    credit_value_contract = fields.Float(readonly=True, )
    cost_d = fields.Float(readonly=True, )
    total_local_d = fields.Float(readonly=True, )
    total_imported_d = fields.Float(readonly=True, )
    sec_insert_date_h = fields.Datetime(readonly=True, string="Bill Time", index=True)
    employee = Many2oneUnconstraint('abdin_eplus.employee', readonly=True, )
    is_delivery = fields.Boolean(readonly=True, )
    deliv_emp_id = Many2oneUnconstraint('abdin_eplus.employee', readonly=True, )
    deliv_points = fields.Float(readonly=True, )
    paid_points = fields.Float(readonly=True, index=True)
    is_visa = fields.Boolean(readonly=True, )
    tup = fields.Integer(index=True, default=0, readonly=True)

    _r_sales_trans_h__sto_id__sth_id_unique = models.Constraint('unique(sto_id,sth_id)', 'Bill is Duplicated For the Same Branch.')


class Store(models.Model):
    _name = 'abdin_eplus.store'
    _description = 'abdin_eplus Store'
    _rec_name = 'sto_name_ar'
    _order = 'sto_id asc'
    sto_id = fields.Integer(index=True, readonly=True, )
    sto_code = fields.Char(index=True, readonly=True)
    sto_name_ar = fields.Char(readonly=True)
    sto_ip1 = fields.Char(readonly=True)

    activated = fields.Integer(readonly=True)
    geo_distance_weight = fields.Integer(default=1000000000)
    region = fields.Many2one('abdin_eplus_ab_region')
    tup = fields.Datetime(index=True, readonly=True)
    is_store = fields.Boolean()

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        code_args = args + [('sto_code', '=', name), ]

        ids = (self.with_user(name_get_uid) if name_get_uid else self).search(code_args, limit=limit).ids
        if not ids:
            args += [('sto_name_ar', operator, name), ]
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


class ItemCatalog(models.Model):
    _name = 'abdin_eplus.item_catalog'
    _description = 'abdin_eplus Item_Catalog'
    _rec_name = 'itm_name_ar'
    _order = 'tup desc'

    _parent_store = True
    _parent_name = "parent_id"  # optional if field is 'parent_id'
    parent_path = fields.Char(index=True)

    itm_id = fields.Integer(readonly=True, index=True)
    itm_code = fields.Char(readonly=True, )
    itm_name_ar = fields.Char()
    itm_name_en = fields.Char()
    bname_en = fields.Char(readonly=True, )
    itm_ismedicine = fields.Integer()
    itm_def_pharm_price = fields.Float(readonly=True)
    parent_id = fields.Many2one('abdin_eplus.item_catalog',
                                string='Parent Product',
                                ondelete='restrict',
                                index=True)

    child_ids = fields.One2many(
        'abdin_eplus.item_catalog', 'parent_id',
        string='Child Products')

    supplier_id = fields.Many2one('abdin_eplus_ab_supplier')

    itm_def_sell_price = fields.Float(readonly=True, )
    tup = fields.Datetime(readonly=True, index=True)

    # itm_active = fields.Integer()
    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        args += [('itm_code', '=ilike', name), ]
        ids = (self.with_user(name_get_uid) if name_get_uid else self).search(args, limit=limit).ids
        if not ids:
            args = ['|',
                    ('itm_name_ar', operator, name),
                    ('itm_name_en', operator, name),
                    ]
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


class Vendor(models.Model):
    _name = 'abdin_eplus.vendor'
    _description = 'abdin_eplus Vendor'

    _rec_name = 'ven_name_ar'
    _order = 'tup desc'
    ven_id = fields.Integer(readonly=True, index=True)
    ven_code = fields.Char(readonly=True, )
    ven_name_ar = fields.Char(readonly=True, )
    ven_tel = fields.Char(readonly=True, index=True)
    ven_parent_ven_id = fields.Integer(readonly=True, string="Parent Vendor")
    ven_active = fields.Integer(readonly=True)
    tup = fields.Datetime(readonly=True, index=True)
    # itm_active = fields.Integer()

###############################################################################################################
###############################################################################################################
