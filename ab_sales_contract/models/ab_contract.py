# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CustomerContracts(models.Model):
    _name = 'ab_contract'
    _inherit = 'ab_contract'

    allow_promotions = fields.Boolean(string="Allow Promotions", default=False)

    @api.constrains(
        'allow_promotions', 'local_product_discount', 'imported_product_discount',
        'local_made_product_discount', 'special_import_product_discount',
        'investment_product_discount', 'other_product_discount',
        'paid_percentage', 'paid_amount',
    )
    def _check_allow_promotions(self):
        enabled = self.filtered('allow_promotions')
        discount_fields = (
            'local_product_discount', 'imported_product_discount',
            'local_made_product_discount', 'special_import_product_discount',
            'investment_product_discount', 'other_product_discount',
        )
        for contract in enabled:
            if (any(contract[name] != 0.0 for name in discount_fields)
                    or contract.paid_percentage not in (0.0, 100.0)
                    or contract.paid_amount != 0.0):
                raise ValidationError(_(
                    "Allow Promotions requires zero default discounts, zero fixed copay, "
                    "and a customer copay of 0% or 100%. "
                    "Disable Allow Promotions before changing these terms."
                ))
        if enabled and self.env['ab_contract_product_origin'].sudo().search_count(
            fields.Domain('contract_id', 'in', enabled.ids)
            & fields.Domain('discount', '!=', 0.0), limit=1,
        ):
            raise ValidationError(_(
                "Allow Promotions requires all product-specific contract discounts to be zero. "
                "Disable Allow Promotions before changing product rules."
            ))

    allow_total_invoice_discount = fields.Boolean(default=False)
    total_invoice_discount_source = fields.Selection(
        [
            ("our_company", "Our Company"),
            ("contract_company", "Contract Company"),
        ],
        default="our_company",
        required=True,
    )
