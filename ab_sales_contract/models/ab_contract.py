# -*- coding: utf-8 -*-


from odoo import models, fields, api


class CustomerContracts(models.Model):
    _name = 'ab_contract'
    _description = 'ab_contract'

    name = fields.Char()
    max_bill_value = fields.Float()
    paid_percentage = fields.Float()
    paid_amount = fields.Float()
    discount_percentage_rule = fields.Selection(
        [('person', 'Person'), ('company', 'Company'), ('all', 'All')], default='company')
    # extra_discount = fields.Integer()
    # contract_pay=fields.Float()
    active = fields.Boolean(default=True)
    local_product_discount = fields.Float()
    imported_product_discount = fields.Float()
    local_made_product_discount = fields.Float()
    special_import_product_discount = fields.Float()
    investment_product_discount = fields.Float()
    other_product_discount = fields.Float()
    eplus_serial = fields.Integer(index=True)
    last_update_date = fields.Datetime(index=True)
    eplus_create_date = fields.Datetime(index=True)
    eplus_cust_code = fields.Char(readonly=True)
    eplus_cust_id = fields.Char(readonly=True)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if name:
            args = [('name', operator, name),
                    ] + args
        return self._search(args, limit=limit, access_rights_uid=name_get_uid)

