from odoo import api, fields, models, _


class AbProductSupplierOrigin(models.Model):
    _name = 'ab_product_supplier_origin'
    _description = 'ab_product_supplier_origin'
    _rec_name = 'product_id'

    supplier_code = fields.Char()
    product_id = fields.Many2one('ab_product', required=True, index=True)
    costcenter_id = fields.Many2one('ab_costcenter', required=True, index=True)
    origin = fields.Selection(
        selection=[
            ('local', 'Local'),
            ('local_45', 'Local 45'),
            ('imported', 'Imported'),
            ('cash', 'Cash'),
        ],
        default='local',
        index=True)

    def update_product_supplier_from_purchase_lines(self):
        cr = self.env.cr
        cr.execute("""
        SELECT distinct on (ps.product_id, sup.costcenter_id)
        ps.product_id, sup.costcenter_id
        from ab_purchase_line pl 
        join ab_product_source ps on ps.id = pl.source_id
        join ab_purchase_header ph on ph.id = pl.header_id
        join ab_supplier sup on sup.id = ph.supplier_id
        left join ab_product_supplier_origin org 
            on org.costcenter_id = sup.costcenter_id and org.product_id=ps.product_id
        where org.product_id is null
        """)
        products_costcenters = cr.fetchall()
        for prod_id, cc_id in self.web_progress_iter(products_costcenters):
            self.create({
                'product_id': prod_id,
                'costcenter_id': cc_id,
                'origin': 'local',
            })
