from odoo import models


class AbSalesReturnHeaderContract(models.Model):
    _inherit = "ab_sales_return_header"

    def _contract_return_is_contract_source(self, source_header):
        self.ensure_one()
        if not source_header:
            return False
        fields_map = getattr(source_header, "_fields", {}) or {}
        if "contract_id" not in fields_map:
            return False
        return bool(source_header.contract_id)

    def _contract_return_get_source_header(self):
        self.ensure_one()
        if not self.origin_header_id or not self.store_id:
            return self.env["ab_sales_header"]
        return self.env["ab_sales_header"].sudo().search(
            [
                ("eplus_serial", "=", int(self.origin_header_id)),
                ("store_id", "=", self.store_id.id),
            ],
            order="id desc",
            limit=1,
        )

    @staticmethod
    def _contract_return_qty_text(value):
        value = float(value or 0.0)
        return f"{value:.4f}".rstrip("0").rstrip(".") or "0"

    @staticmethod
    def _contract_return_default_factor(product):
        factor = float(product.uom_id.factor or 0.0) if product and product.uom_id else 0.0
        if factor <= 0.0:
            factor = 1.0
        return factor

    def _contract_return_qty_in_default_uom(self, line, qty_source):
        self.ensure_one()
        qty_source = float(qty_source or 0.0)
        if qty_source <= 0.0 or not line.product_id:
            return 0.0
        source_factor = float(line.source_uom_factor or 0.0) or 1.0
        default_factor = self._contract_return_default_factor(line.product_id)
        return qty_source * source_factor / default_factor

    def _contract_return_price_ref(self, source_header, line):
        self.ensure_one()
        if not source_header or not line.product_id:
            return 0.0
        default_factor = self._contract_return_default_factor(line.product_id)
        selected_factor = float(line.uom_id.factor or 0.0) if line.uom_id else 0.0
        if selected_factor <= 0.0:
            selected_factor = float(line.source_uom_factor or 0.0) or default_factor
        ratio = selected_factor / default_factor if default_factor > 0.0 else 1.0
        if ratio <= 0.0:
            ratio = 1.0
        return float(source_header._price_ref_from_line(line, ratio) or 0.0)

    def _contract_return_line_qty_source(self, line, mode="remaining"):
        self.ensure_one()
        sold_qty = float(line.qty_sold_source or 0.0)
        current_qty = float(line.max_returnable_source or 0.0)
        returned_qty = float(line._qty_to_source_unit() or 0.0)
        if mode == "current":
            return max(0.0, current_qty)
        if mode == "sold":
            return sold_qty
        if mode == "returned":
            return returned_qty
        return max(0.0, current_qty - returned_qty)

    def _contract_return_build_virtual_header(self, source_header, mode="remaining"):
        self.ensure_one()
        if not source_header:
            return self.env["ab_sales_header"].new({})

        line_commands = []
        for line in self.line_ids.filtered(lambda l: l.product_id and float(l.qty_sold_source or 0.0) > 0.0):
            qty_source = self._contract_return_line_qty_source(line, mode=mode)
            qty_default = self._contract_return_qty_in_default_uom(line, qty_source)
            if qty_default <= 1e-8:
                continue
            price_ref = self._contract_return_price_ref(source_header, line)
            default_uom = line.product_id.uom_id or line.uom_id
            line_commands.append(
                (0, 0, {
                    "product_id": line.product_id.id,
                    "uom_id": default_uom.id if default_uom else False,
                    "qty_str": self._contract_return_qty_text(qty_default),
                    "sell_price": price_ref,
                })
            )

        source_contract_id = source_header.contract_id.id if self._contract_return_is_contract_source(source_header) else False
        header = self.env["ab_sales_header"].new(
            {
                "store_id": source_header.store_id.id,
                "company_id": source_header.company_id.id,
                "customer_id": source_header.customer_id.id if source_header.customer_id else False,
                "contract_id": source_contract_id,
                "line_ids": line_commands,
            }
        )
        if header.line_ids:
            header.line_ids._compute_qty()
            header.line_ids._compute_amount()
            if header.contract_id:
                header._ab_contract_recompute_lines()
                header._compute_contract_totals()
        return header

    def _contract_return_virtual_totals(self, source_header, mode="remaining"):
        self.ensure_one()
        if not source_header:
            return {
                "after_disc": 0.0,
                "net": 0.0,
            }

        virtual_header = self._contract_return_build_virtual_header(source_header, mode=mode)
        amount_total = 0.0
        if virtual_header.line_ids:
            amount_total = float(
                sum(
                    float(line.price_subtotal or (line.qty or 0.0) * (line.sell_price or 0.0))
                    for line in virtual_header.line_ids
                )
            )
        if not self._contract_return_is_contract_source(virtual_header):
            return {
                "after_disc": amount_total,
                "net": amount_total,
            }

        return {
            "after_disc": float(virtual_header.total_after_discount or amount_total or 0.0),
            "net": float(virtual_header.cust_pay or virtual_header.total_after_discount or amount_total or 0.0),
        }

    def _contract_return_reprice_values(self, before_after_disc=False, before_net=False):
        self.ensure_one()
        source_header = self._contract_return_get_source_header()
        if not self._contract_return_is_contract_source(source_header):
            return {
                "source_header": source_header,
                "is_contract": False,
                "original_after_disc": 0.0,
                "remaining_after_disc": 0.0,
                "refund_after_disc": 0.0,
                "original_net": 0.0,
                "remaining_net": 0.0,
                "refund_net": 0.0,
            }

        remaining = self._contract_return_virtual_totals(source_header, mode="remaining")
        original = self._contract_return_virtual_totals(source_header, mode="current")

        original_after_disc = float(original.get("after_disc") or 0.0)
        remaining_after_disc = float(remaining.get("after_disc") or 0.0)
        original_net = float(original.get("net") or 0.0)
        remaining_net = float(remaining.get("net") or 0.0)

        if before_after_disc is not False:
            before_after_disc_val = float(before_after_disc)
        else:
            before_after_disc_val = float(
                source_header.total_after_discount
                if source_header.total_after_discount is not None
                else (original_after_disc or 0.0)
            )

        if before_net is not False:
            before_net_val = float(before_net)
        else:
            before_net_val = float(
                self.total_sales_net
                if self.total_sales_net is not None
                else (original_net or 0.0)
            )

        return {
            "source_header": source_header,
            "is_contract": True,
            "original_after_disc": before_after_disc_val,
            "remaining_after_disc": remaining_after_disc,
            "refund_after_disc": max(0.0, before_after_disc_val - remaining_after_disc),
            "original_net": before_net_val,
            "remaining_net": remaining_net,
            "refund_net": max(0.0, before_net_val - remaining_net),
        }

