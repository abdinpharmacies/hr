from odoo import api, models


class SupplierClaimManagerService(models.AbstractModel):
    _inherit = 'ab_supplier_claim_manager_service'

    @api.model
    def _get_claim_group_xmlid_prefix(self):
        return 'ab_supplier_claim_workflow'
