import re

from odoo import api, fields, models, _


class AbProductSourcePending(models.Model):
    _name = 'ab_product_source_pending'
    _description = 'ab_product_source_pending'
    _auto = False

    source_id = fields.Many2one('ab_product_source', bypass_search_access=True)
    qty = fields.Float()
    product_id = fields.Many2one('ab_product')
    bonus = fields.Integer()
    purchase_price = fields.Float()
    price = fields.Float()
    uom_id = fields.Many2one('ab_uom')
    unit_cost = fields.Float(related='source_id.unit_cost')
    unit_taxes_value = fields.Float(related='source_id.unit_taxes_value')

    def name_get(self):
        return [(rec.id, f"{rec.product_id.name} [{rec.id}]") for rec in self]

    @api.depends('product_id')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        # products = self.env['ab_product']
        pattern = r"\*|  "
        new_name = re.sub(pattern, "%", name) + '%'
        domain = [('product_id.name', '=ilike', new_name)] + args
        if name:
            product_ids = self.search(
                ['|', ('product_id.barcode_ids', '=ilike', name), ('product_id.code', '=ilike', name)])
            if product_ids:
                domain = [('product_id.id', 'in', product_ids.ids)] + args
        return (self.with_user(name_get_uid) if name_get_uid else self).search(domain, limit=limit).ids

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
