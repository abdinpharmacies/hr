from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AbdinProductTag(models.Model):
    _name = 'ab_product_tag'
    _description = 'Abdin Product Tag'

    name = fields.Char(required=True)
    tag_type = fields.Selection(selection=[('type', 'Similar classification'),('offer', 'Offer'),('unit', 'Unit')],required=True)
    priority = fields.Integer(default=1)
    product_ids = fields.Many2many(comodel_name='ab_product',relation='ab_product_product_tag',column2='product_id',column1='tag_id')
    _ab_product_tag_name_unique = models.Constraint('UNIQUE(name)', 'The tag name must be unique. Another record with the same name already exists.')

    @api.onchange('tag_type')
    def _onchange_product_tag(self):
        for rec in self:
            if rec.tag_type == 'unit':
                rec.priority = 1
            elif rec.tag_type == 'type':
                rec.priority = 2
            elif rec.tag_type == 'offer':
                rec.priority = 3

    @api.constrains('name','tag_type')
    def _constrains_product_tag(self):
        for rec in self:
            tags = self.search([('name', '=ilike', rec.name)])
            if len(tags) > 1:
               raise UserError(_(f"The tag name '{rec.name}' must be unique. Another record with the same name already exists."))

