# -*- coding: utf-8 -*-

from odoo import models


class AbSalesReturnHeaderPromo(models.Model):
    _inherit = "ab_sales_return_header"

    def _promo_return_is_promo_source(self, source_header):
        self.ensure_one()
        if not source_header:
            return False
        fields_map = getattr(source_header, "_fields", {}) or {}
        if "contract_id" in fields_map and source_header.contract_id:
            return False
        if "applied_program_ids" not in fields_map:
            return False
        return bool(source_header.applied_program_ids)

    def _promo_return_get_source_header(self):
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

    def _promo_return_get_program(self, source_header=False):
        self.ensure_one()
        source_header = source_header or self._promo_return_get_source_header()
        if not self._promo_return_is_promo_source(source_header):
            return self.env["ab_promo_program"]
        program = source_header.applied_program_ids[:1]
        program_id = getattr(program, "id", None)
        origin = getattr(program_id, "origin", None)
        if origin:
            program = self.env["ab_promo_program"].browse(int(origin))
        return program

    @staticmethod
    def _promo_return_qty_text(value):
        value = float(value or 0.0)
        return f"{value:.4f}".rstrip("0").rstrip(".") or "0"

    @staticmethod
    def _promo_return_default_factor(product):
        factor = float(product.uom_id.factor or 0.0) if product and product.uom_id else 0.0
        if factor <= 0.0:
            factor = 1.0
        return factor

    def _promo_return_qty_in_default_uom(self, line, qty_source):
        self.ensure_one()
        qty_source = float(qty_source or 0.0)
        if qty_source <= 0.0 or not line.product_id:
            return 0.0
        source_factor = float(line.source_uom_factor or 0.0) or 1.0
        default_factor = self._promo_return_default_factor(line.product_id)
        return qty_source * source_factor / default_factor

    def _promo_return_price_ref(self, source_header, line):
        self.ensure_one()
        if not source_header or not line.product_id:
            return 0.0
        default_factor = self._promo_return_default_factor(line.product_id)
        selected_factor = float(line.uom_id.factor or 0.0) if line.uom_id else 0.0
        if selected_factor <= 0.0:
            selected_factor = float(line.source_uom_factor or 0.0) or default_factor
        ratio = selected_factor / default_factor if default_factor > 0.0 else 1.0
        if ratio <= 0.0:
            ratio = 1.0
        return float(source_header._price_ref_from_line(line, ratio) or 0.0)

    def _promo_return_line_qty_source(self, line, mode="remaining"):
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

    def _promo_return_build_virtual_header(self, source_header, mode="remaining"):
        self.ensure_one()
        if not source_header:
            return self.env["ab_sales_header"].new({})

        line_commands = []
        for line in self.line_ids.filtered(lambda l: l.product_id and float(l.qty_sold_source or 0.0) > 0.0):
            qty_source = self._promo_return_line_qty_source(line, mode=mode)
            qty_default = self._promo_return_qty_in_default_uom(line, qty_source)
            if qty_default <= 1e-8:
                continue
            price_ref = self._promo_return_price_ref(source_header, line)
            default_uom = line.product_id.uom_id or line.uom_id
            line_commands.append(
                (0, 0, {
                    "product_id": line.product_id.id,
                    "uom_id": default_uom.id if default_uom else False,
                    "qty_str": self._promo_return_qty_text(qty_default),
                    "sell_price": price_ref,
                })
            )

        header = self.env["ab_sales_header"].new(
            {
                "store_id": source_header.store_id.id,
                "company_id": source_header.company_id.id,
                "customer_id": source_header.customer_id.id if source_header.customer_id else False,
                "line_ids": line_commands,
            }
        )
        if header.line_ids:
            header.line_ids._compute_qty()
            header.line_ids._compute_amount()
        return header

    def _promo_return_virtual_total(self, source_header, mode="remaining"):
        self.ensure_one()
        if not source_header:
            return 0.0

        virtual_header = self._promo_return_build_virtual_header(source_header, mode=mode)
        if virtual_header.line_ids:
            virtual_header._compute_amounts()

        amount_total = float(virtual_header.amount_total or 0.0)
        program = self._promo_return_get_program(source_header=source_header)
        if not program or not virtual_header.line_ids:
            return amount_total

        virtual_header.applied_program_ids = program
        virtual_header.with_context(force_program_effective=True)._compute_promo_totals()
        return float(virtual_header.amount_total_after_promo or amount_total or 0.0)

    def _promo_return_reprice_values(self):
        self.ensure_one()
        source_header = self._promo_return_get_source_header()
        if not source_header:
            raw_total = sum(float(line.qty or 0.0) * float(line.sell_price or 0.0) for line in self.line_ids)
            return {
                "source_header": source_header,
                "original_total": 0.0,
                "remaining_total": 0.0,
                "refund_total": raw_total,
            }

        original_total = self._promo_return_virtual_total(source_header, mode="current")
        remaining_total = self._promo_return_virtual_total(source_header, mode="remaining")
        refund_total = max(0.0, float(original_total or 0.0) - float(remaining_total or 0.0))
        return {
            "source_header": source_header,
            "original_total": float(original_total or 0.0),
            "remaining_total": float(remaining_total or 0.0),
            "refund_total": refund_total,
        }

