from odoo import fields, models


class AbSalesLine(models.Model):
    _inherit = "ab_sales_line"

    is_doctor_prescription_product = fields.Boolean(
        string="Prescription Product",
        default=False,
        index=True,
        help="Enable when this line is part of the selected doctor's prescription.",
    )

    def _prepare_doctor_prescription_values(self):
        self.ensure_one()
        return {
            "doctor_id": self.header_id.doctor_id.id,
            "product_id": self.product_id.id,
            "uom_id": self.uom_id.id if self.uom_id else False,
            "qty": self.qty or 0.0,
            "sell_price": self.sell_price or 0.0,
            "last_sales_header_id": self.header_id.id,
            "last_sales_line_id": self.id,
            "active": True,
        }

