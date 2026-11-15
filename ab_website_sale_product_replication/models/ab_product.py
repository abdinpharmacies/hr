from odoo import models


class AbProduct(models.Model):
    _inherit = "ab_product"

    def _after_force_id_replication(self, operation, replicated_values):
        result = super()._after_force_id_replication(operation, replicated_values)
        changed = self.filtered(
            lambda product: "default_price" in replicated_values.get(product.id, {})
        )
        if changed:
            changed._sync_linked_website_base_prices()
        return result
