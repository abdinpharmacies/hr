import re

from odoo import api, fields, models
from odoo.tools.translate import _


class AbProductSourcePending(models.Model):
    _name = 'ab_product_source_pending'
    _description = 'ab_product_source_pending'
    _auto = False

    source_id = fields.Many2one('ab_product_source', auto_join=True)
    qty = fields.Float()
    product_id = fields.Many2one('ab_product')
    bonus = fields.Integer()
    purchase_price = fields.Float()
    price = fields.Float()
    uom_id = fields.Many2one('ab_uom')
    unit_cost = fields.Float(related='source_id.unit_cost')
    unit_taxes_value = fields.Float(related='source_id.unit_taxes_value')

    @api.depends('product_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.product_id.name} [{rec.id}]"

    @api.model
    def _search_display_name(self, operator, value):
        name = value or ''
        pattern = r"\*|  "
        new_name = re.sub(pattern, "%", name) + '%'
        domain = [('product_id.name', '=ilike', new_name)]
        if name:
            product_ids = self.search(
                ['|', ('product_id.barcode_ids', '=ilike', name), ('product_id.code', '=ilike', name)]
            )
            if product_ids:
                domain = [('product_id.id', 'in', product_ids.ids)]
        return domain

    def init(self):
        self._cr.execute(f"""
            DROP VIEW IF EXISTS {self._table} CASCADE ;
            ----------------------------------------------------
            CREATE OR REPLACE VIEW {self._table} AS
            SELECT distinct on (inv.source_id)
                inv.source_id as id, 
                inv.source_id as source_id,
                inv.status as status,
                ps.product_id,
                ps.bonus,
                ps.price,
                ps.purchase_price,
                ps.uom_id,
                sum(inv.qty) as qty
            FROM ab_inventory inv join ab_product_source ps on inv.source_id = ps.id 
                            WHERE status='pending_main' 
                            GROUP BY 
                                inv.source_id,            
                                ps.product_id,
                                ps.bonus,
                                ps.price,
                                ps.purchase_price,
                                ps.uom_id,
                                inv.status
                            HAVING sum(inv.qty)>0
                            order by inv.source_id
           """)
