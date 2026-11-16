import logging

from odoo import fields, models


_logger = logging.getLogger(__name__)


class OdooReplication(models.AbstractModel):
    _inherit = "ab_odoo_replication"

    def _replicate_model(self, model_name, limit, commit, extra_fields,
                         replicate_all, extra_domain):
        result = super()._replicate_model(
            model_name, limit, commit, extra_fields, replicate_all, extra_domain,
        )
        if model_name == "ab_product" and not extra_domain:
            self._reconcile_website_base_prices(commit=commit)
        return result

    def _reconcile_website_base_prices(self, commit=False):
        Template = self.env["product.template"].with_context(active_test=False)
        last_id = 0
        updated = 0
        while True:
            templates = Template.search(
                fields.Domain("ab_product_id", "!=", False)
                & fields.Domain("id", ">", last_id),
                order="id", limit=500,
            )
            if not templates:
                break
            last_id = templates[-1].id
            changed = templates.filtered(
                lambda template: template.list_price != template.ab_product_id.default_price
            )
            for template in changed:
                template.write({"list_price": template.ab_product_id.default_price})
            updated += len(changed)
            if changed and commit:
                self.env.cr.commit()
        _logger.info("Replicated website base prices reconciled: updated=%s", updated)
        return updated
