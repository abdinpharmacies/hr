from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError
import re


class AbdinProductCard(models.Model):
    _name = 'ab_product_card'
    _description = 'Abdin Product Card'

    name = fields.Char(required=False)
    company_id = fields.Many2one('ab_product_company')
    has_exp_date = fields.Boolean(default=True)
    is_medicine = fields.Boolean(default=True)
    is_service = fields.Boolean()
    is_freeze = fields.Boolean()
    is_narcotic = fields.Boolean()
    groups_ids = fields.Many2many(comodel_name='ab_product_group',
                                  relation='ab_product_card_group_rel', column1='product_card_id', column2='group_id')
    scientific_groups_ids = fields.Many2many(comodel_name='ab_scientific_group',
                                             relation='ab_product_card_sci_group_rel', column1='product_card_id',
                                             column2='sci_group_id')
    usage_causes_id = fields.Many2one('ab_usage_causes')
    usage_manner_id = fields.Many2one('ab_usage_manner')
    origin_id = fields.Many2one('ab_product_origin')
    origin = fields.Selection(
        selection=[('local', 'Local'),
                   ('imported', 'Imported'),
                   ('special_imported', 'Special Imported'),
                   ('chemical', 'Chemical'),
                   ('other', 'Other'),
                   ], )

    effective_material = fields.Char()
    effective_material_conc = fields.Integer()
    allow_sale = fields.Boolean(default=True)
    allow_purchase = fields.Boolean(default=True)
    allow_transfer = fields.Boolean(default=True)
    allow_discount = fields.Boolean()
    allow_print_name = fields.Boolean(default=True)
    max_discount_percentage = fields.Float()
    is_favorite = fields.Selection(
        [('0', 'Normal'), ('1', 'Favorite'), ], default='0', string="Favorite")
    description = fields.Text()
    product_ids = fields.One2many(comodel_name='ab_product', inverse_name='product_card_id')
    active = fields.Boolean(default=True)

    @api.model
    def _check_same_unit_type(self, product_ids):
        if len(product_ids.mapped('uom_category_id')) > 1:
            raise ValidationError(_("All products on a card must have the same unit category."))

    @api.model
    def _search_display_name(self, operator, value):
        name = value or ''
        pattern = r"\*|  "
        new_name = re.sub(pattern, "%", name) + '%'
        domain = [('name', '=ilike', new_name)]
        if name:
            product_ids = self.env['ab_product'].search(
                ['|', ('barcode_ids', '=ilike', name), ('code', '=ilike', name)]
            )
            product_card_ids = [product.product_card_id.id for product in product_ids]
            if product_card_ids:
                domain = [('id', 'in', product_card_ids)]
        return domain
