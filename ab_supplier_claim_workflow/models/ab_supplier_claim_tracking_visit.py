from odoo import fields, models


class SupplierClaimTrackingVisit(models.Model):
    _name = 'ab.supplier.claim.tracking.visit'
    _description = 'Supplier Claim Tracking Visit'
    _order = 'visit_date desc, id desc'

    claim_id = fields.Many2one(
        'ab_supplier_claim_cycle',
        string='Claim',
        required=True,
        ondelete='cascade',
        index=True,
    )
    visit_date = fields.Datetime(string='Visit Date', default=fields.Datetime.now, required=True, index=True)
    ip_address = fields.Char(string='IP Address', readonly=True)
    user_agent = fields.Char(string='Browser', readonly=True)
