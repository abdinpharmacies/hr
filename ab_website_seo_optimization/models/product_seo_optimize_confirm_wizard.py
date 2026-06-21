from odoo import _, fields, models


class AbProductSeoOptimizeConfirmWizard(models.TransientModel):
    _name = "ab.product.seo.optimize.confirm.wizard"
    _description = "Confirm SEO Product Update"

    seo_id = fields.Many2one("ab.product.seo", required=True, readonly=True, ondelete="cascade")
    product_template_id = fields.Many2one("product.template", readonly=True)
    message = fields.Text(
        default=lambda self: _(
            "The selected published product already has complete native SEO fields. "
            "Do you want to generate new SEO suggestions and update the product?"
        ),
        readonly=True,
    )

    def action_optimize_and_update(self):
        self.ensure_one()
        self.seo_id.with_context(force_seo_optimization=True)._optimize_single_published_product()
        return {"type": "ir.actions.act_window_close"}

    def action_discard(self):
        return {"type": "ir.actions.act_window_close"}
