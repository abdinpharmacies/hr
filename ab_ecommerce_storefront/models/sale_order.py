from odoo import api, fields, models
from odoo.tools.urls import urljoin


class SaleOrder(models.Model):
    _inherit = "sale.order"

    ab_prescription_order_ids = fields.One2many(
        "ab.prescription.order", "sale_order_id", string="Prescription Requests",
    )

    def _cart_add(self, product_id, quantity=1.0, *, uom_id=None, **kwargs):
        result = super()._cart_add(product_id, quantity=quantity, uom_id=uom_id, **kwargs)
        if quantity > 0 and self.partner_id and not self.env.user._is_public():
            self.partner_id.sudo().write({"ab_storefront_has_cart_history": True})
        return result

    def _ab_storefront_latest_prescription(self):
        self.ensure_one()
        return self.ab_prescription_order_ids.filtered(
            lambda prescription: prescription.partner_id.commercial_partner_id
            == self.partner_id.commercial_partner_id
            and prescription.company_id == self.company_id
        ).sorted("id", reverse=True)[:1]

    @api.constrains("partner_id", "company_id", "website_id")
    def _check_prescription_customer(self):
        self.ab_prescription_order_ids._check_sale_order_customer()

    def _ab_storefront_payment_label(self):
        self.ensure_one()
        tx = self.get_portal_last_transaction()
        if tx:
            if tx.state in ("draft", "pending") and tx.provider_id.custom_mode == "cash_on_delivery":
                return self.env._("Cash on delivery")
            labels = {
                "draft": self.env._("Payment initiated"),
                "pending": self.env._("Payment processing"),
                "authorized": self.env._("Payment authorized"),
                "done": self.env._("Payment successful"),
                "cancel": self.env._("Payment cancelled"),
                "error": self.env._("Payment failed"),
            }
            return labels.get(tx.state, self.env._("Payment pending"))
        if self.currency_id.is_zero(self.amount_total):
            return self.env._("No payment required")
        return self.env._("Payment pending")

    def _ab_storefront_delivery_stage(self):
        self.ensure_one()
        if self.state == "cancel":
            return "cancelled"
        stage = "confirmed" if self.state == "sale" else "created"
        if "picking_ids" not in self._fields:
            return stage
        # Warehouse completion proves dispatch, not receipt by the customer.
        outgoing = self.picking_ids.filtered(
            lambda picking: picking.picking_type_code == "outgoing"
            and picking.location_dest_id.usage == "customer" and picking.state != "cancel"
        )
        returns = self.picking_ids.move_ids.filtered(
            lambda move: move.state == "done" and move.origin_returned_move_id
            and move.location_id.usage == "customer"
            and move.location_dest_id.usage == "internal"
        )
        if returns:
            return "return_received"
        if outgoing and all(picking.state == "done" for picking in outgoing):
            return "shipped"
        if any(picking.state == "done" for picking in outgoing):
            return "partially_shipped"
        if any(picking.state == "assigned" for picking in outgoing):
            return "preparing"
        return stage

    def _ab_storefront_tracking_steps(self, include_prescription=True):
        self.ensure_one()
        prescription = self._ab_storefront_latest_prescription() if include_prescription else False
        steps = prescription._ab_storefront_tracking_steps(include_order=False) if prescription else []
        stage = self._ab_storefront_delivery_stage()
        definitions = [
            ("created", self.env._("Order created"), self.env._("We received your order details.")),
            ("confirmed", self.env._("Order confirmed"), self.env._("The order is confirmed by Abdin Pharmacies.")),
            ("preparing", self.env._("Preparing order"), self.env._("Your items are reserved for preparation.")),
            ("shipped", self.env._("Out for delivery"), self.env._("Your order has left the pharmacy and is on the way.")),
            ("delivered", self.env._("Delivered"), self.env._("Your order has been delivered.")),
        ]
        keys = [key for key, label, description in definitions]
        current = keys.index(stage) if stage in keys else (2 if stage == "partially_shipped" else 0)
        for index, (key, label, description) in enumerate(definitions):
            if prescription and key == "created":
                continue
            if stage in ("cancelled", "return_received") and index > 0:
                continue
            steps.append({
                "key": key, "label": label, "description": description,
                "state": "complete" if index < current or stage in ("cancelled", "return_received")
                else ("current" if index == current else "pending"),
            })
        if prescription and self.state in ("draft", "sent"):
            for step in steps:
                if step["key"] in keys:
                    step["state"] = "pending"
            if prescription.state in ("cancelled", "rejected"):
                steps = [step for step in steps if step["state"] != "pending"]
        if stage == "partially_shipped":
            for shipped_index, step in enumerate(steps):
                if step["key"] == "shipped":
                    break
            else:
                shipped_index = len(steps)
            steps.insert(shipped_index, {
                "key": stage, "label": self.env._("Partially shipped"),
                "description": self.env._("Some items have been dispatched; others are still being prepared."),
                "state": "current",
            })
            for step in steps:
                if step["key"] == "preparing":
                    step["state"] = "complete"
        exceptions = {
            "cancelled": (self.env._("Order cancelled"), self.env._("This order was cancelled.")),
            "return_received": (self.env._("Return received"), self.env._("Returned items were received by the warehouse.")),
        }
        if stage in exceptions:
            steps = [dict(step, state="complete") for step in steps if step["state"] != "pending"]
            label, description = exceptions[stage]
            steps.append({"key": stage, "label": label, "description": description, "state": "exception"})
        elif self.get_portal_last_transaction().state in ("error", "cancel"):
            steps = [step for step in steps if step["state"] != "pending"]
            steps.append({
                "key": "payment_failed", "label": self.env._("Payment failed"),
                "description": self.env._("The payment could not be completed."),
                "state": "exception",
            })
        return steps

    def _ab_storefront_customer_invoices(self):
        self.ensure_one()
        return self.invoice_ids.filtered(
            lambda invoice: invoice.state == "posted"
            and invoice.move_type in ("out_invoice", "out_refund")
            and invoice.company_id == self.company_id
            and invoice.commercial_partner_id == self.partner_invoice_id.commercial_partner_id
        ).sorted("invoice_date", reverse=True)

    def _ab_storefront_report_terms_url(self):
        self.ensure_one()
        use_invoice_terms = self.env["ir.config_parameter"].sudo().get_param(
            "account.use_invoice_terms",
        )
        if not use_invoice_terms or self.company_id.terms_type != "html":
            return False
        return urljoin(self.get_base_url(), "/terms")

    def _ab_storefront_report_discount_amount(self):
        self.ensure_one()
        discount = 0.0
        for line in self.order_line:
            if line.display_type or not line.discount:
                continue
            if "is_delivery" in line._fields and line.is_delivery:
                continue
            discount += line.price_unit * line.product_uom_qty * line.discount / 100.0
        return self.currency_id.round(discount)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _ab_storefront_report_line_parts(self):
        self.ensure_one()
        raw_lines = [
            value.strip()
            for value in (self.name or "").splitlines()
            if value and value.strip()
        ]
        product = self.product_id
        sku = product.default_code or ""
        if "is_delivery" in self._fields and self.is_delivery:
            return {
                "sku": "",
                "name": raw_lines[0] if raw_lines else product.display_name,
                "description": "\n".join(raw_lines[1:]),
            }

        fallback_name = product.with_context(display_default_code=False).display_name
        product_name = raw_lines[0] if raw_lines else fallback_name
        if sku and product_name.startswith(f"[{sku}]"):
            product_name = product_name[len(sku) + 2:].strip()
        description_lines = raw_lines[1:]

        comparable_names = {
            value.strip()
            for value in (
                fallback_name,
                product.name,
                product.product_tmpl_id.name,
            )
            if value and value.strip()
        }
        if product_name in comparable_names:
            description = "\n".join(description_lines)
        else:
            description = "\n".join(description_lines)
        return {
            "sku": sku,
            "name": product_name or fallback_name,
            "description": description,
        }

    def _ab_storefront_report_tax_label(self):
        self.ensure_one()
        labels = [
            tax.tax_label or tax.name
            for tax in self.tax_ids
            if tax.tax_label or tax.name
        ]
        return ", ".join(labels)
