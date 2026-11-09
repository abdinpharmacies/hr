from odoo import Command, api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("order_id") and self.env["sale.order"].browse(values["order_id"]).website_id:
                values["tax_ids"] = [Command.clear()]
        return super().create(vals_list)

    def write(self, values):
        if "tax_ids" not in values:
            return super().write(values)
        website_lines = self.filtered("order_id.website_id")
        backend_lines = self - website_lines
        if website_lines:
            super(SaleOrderLine, website_lines).write({**values, "tax_ids": [Command.clear()]})
        if backend_lines:
            super(SaleOrderLine, backend_lines).write(values)
        return True

    @api.depends("product_id", "company_id")
    def _compute_tax_ids(self):
        super()._compute_tax_ids()
        for line in self.filtered("order_id.website_id"):
            line.tax_ids = False

    def _reset_price_unit(self):
        self.ensure_one()
        if not self.order_id.website_id:
            return super()._reset_price_unit()
        price = self._get_display_price()
        self.update({"price_unit": price, "technical_price_unit": price})
