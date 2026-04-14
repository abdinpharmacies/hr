# -*- coding: utf-8 -*-

import re
from math import floor

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AbSalesPosApi(models.TransientModel):
    _inherit = "ab_sales_pos_api"

    @api.model
    def pos_promotions(self, store_id=None, lines=None, applied_program_id=None, manual_clear=False):
        self._require_models("ab_sales_header", "ab_sales_line", "ab_promo_program", "ab_product_uom")
        replica_db = self.env["ab_replica_db"].sudo().get_current_from_config()
        if isinstance(manual_clear, str):
            manual_clear = (manual_clear or "").strip().lower() in ("1", "true", "yes", "on")
        else:
            manual_clear = bool(manual_clear)

        def _safe_program_id(program):
            program_id = getattr(program, "id", None)
            origin = getattr(program_id, "origin", None)
            if origin:
                program_id = origin
            try:
                return int(program_id)
            except Exception:
                return 0

        def _available_programs_for_header(header):
            products_in_order = header.line_ids.mapped("product_id")
            Promo = self.env["ab_promo_program"].sudo()
            if not products_in_order:
                return Promo.browse()

            now = fields.Datetime.now()
            domain = [
                ("active", "=", True),
                "|", ("company_id", "=", header.company_id.id), ("company_id", "=", False),
                "|", ("rule_date_from", "=", False), ("rule_date_from", "<=", now),
                "|", ("rule_date_to", "=", False), ("rule_date_to", ">=", now),
            ]
            if header.store_id:
                domain += ["|", ("store_ids", "=", False), ("store_ids", "in", header.store_id.id)]
            else:
                domain += [("store_ids", "=", False)]
            if "replica_db_ids" in Promo._fields:
                if replica_db:
                    domain += ["|", ("replica_db_ids", "=", False), ("replica_db_ids", "in", replica_db.id)]
                else:
                    domain += [("replica_db_ids", "=", False)]

            promos = Promo.search(domain, order="sequence,id")
            applicable = Promo.browse()
            for program in promos:
                vis_scope = header._program_visibility_products(program)
                if vis_scope & products_in_order and header._program_is_effective(program):
                    applicable |= program
            return applicable

        def _auto_apply_single_program(header, programs):
            progs = programs.filtered(lambda p: header._program_is_effective(p))
            if len(progs) != 1:
                return self.env["ab_promo_program"].browse()
            program = progs[0]
            if not _program_meets_min_qty(header, program):
                header.applied_program_ids = [(6, 0, [])]
                return self.env["ab_promo_program"].browse()
            scope = header._program_discount_products(program)
            need_qty = float(program.rule_min_qty or 0.0)
            total_scope_qty = 0.0
            if scope:
                for line in header.line_ids:
                    if line.product_id in scope and (line.qty or 0.0) > 0:
                        total_scope_qty += header._line_qty_in_program_uom(line, program)
            if not scope or need_qty <= 0.0 or (total_scope_qty + 1e-8 >= need_qty):
                header.applied_program_ids = [(6, 0, [program.id])]
                return program
            else:
                header.applied_program_ids = [(6, 0, [])]
                return self.env["ab_promo_program"].browse()

        def _program_meets_min_qty(header, program):
            scope = header._program_discount_products(program)
            need_qty = float(program.rule_min_qty or 0.0)
            if not scope or need_qty <= 0.0:
                return True
            total_scope_qty = 0.0
            for line in header.line_ids:
                if line.product_id in scope and (line.qty or 0.0) > 0:
                    total_scope_qty += header._line_qty_in_program_uom(line, program)
            return bool(total_scope_qty + 1e-8 >= need_qty)

        def _format_qty(value):
            try:
                num = float(value)
            except Exception:
                return str(value)
            if num.is_integer():
                return str(int(num))
            return f"{num:.3f}".rstrip("0").rstrip(".")

        def _missing_qty_to_next(header, program):
            scope = header._program_discount_products(program)
            need_qty = float(program.rule_min_qty or 0.0)
            if not scope or need_qty <= 0.0:
                return 0.0
            total_scope_qty = 0.0
            for line in header.line_ids:
                if line.product_id in scope and (line.qty or 0.0) > 0:
                    total_scope_qty += float(floor(header._line_qty_in_program_uom(line, program)))
            remainder = total_scope_qty % need_qty
            if remainder <= 1e-8:
                return 0.0
            return need_qty - remainder

        try:
            store_id = int(store_id or 0)
        except Exception:
            store_id = 0

        if not store_id:
            return self._empty_promo_payload()

        lines = lines or []
        if not isinstance(lines, list):
            raise UserError(_("Invalid lines payload."))

        line_commands = []
        for line in lines:
            try:
                product_id = int(line.get("product_id") or 0)
            except Exception:
                product_id = 0
            if not product_id:
                continue
            qty_str = line.get("qty_str") or "1"
            try:
                sell_price = float(line.get("sell_price") or 0.0)
            except Exception:
                sell_price = 0.0
            uom_id = line.get("uom_id") or False
            if isinstance(uom_id, (list, tuple)):
                uom_id = uom_id[0] if uom_id else False
            try:
                uom_id = int(uom_id) if uom_id else False
            except Exception:
                uom_id = False
            line_commands.append((0, 0, {
                "product_id": product_id,
                "qty_str": qty_str,
                "sell_price": sell_price,
                "uom_id": uom_id,
            }))

        if not line_commands:
            return self._empty_promo_payload()

        header = self.env["ab_sales_header"].new({
            "store_id": store_id,
            "line_ids": line_commands,
        })

        header.line_ids._compute_qty()
        header.line_ids._compute_amount()

        promo_id = None
        if applied_program_id:
            if isinstance(applied_program_id, (list, tuple)) and applied_program_id:
                applied_program_id = applied_program_id[0]
            try:
                promo_id = int(applied_program_id)
            except Exception:
                promo_id = None

        available_programs = _available_programs_for_header(header)
        available_ids = [_safe_program_id(program) for program in available_programs]
        header.applied_program_ids = [(6, 0, [])]
        applied_program = self.env["ab_promo_program"].browse()
        selected_program = self.env["ab_promo_program"].browse()
        if promo_id and promo_id in available_ids:
            selected_program = available_programs.filtered(
                lambda program: _safe_program_id(program) == promo_id
            )[:1]
            if selected_program and _program_meets_min_qty(header, selected_program):
                header.applied_program_ids = [(6, 0, [promo_id])]
                header.promo_manual_override = True
                applied_program = selected_program

        if not applied_program and not manual_clear:
            applied_program = _auto_apply_single_program(header, available_programs)

        header._compute_amounts()
        amount_total = float(header.amount_total or 0.0)
        promo_discount = 0.0
        if applied_program:
            for product in header.line_ids.mapped("product_id"):
                promo_discount += float(header._discount_for_program_on_product(applied_program, product) or 0.0)
        promo_discount = min(promo_discount, amount_total)
        amount_total_after_promo = amount_total - promo_discount
        header.promo_discount_amount = promo_discount
        header.amount_total_after_promo = amount_total_after_promo

        if not selected_program and len(available_programs) == 1:
            selected_program = available_programs[:1]

        promo_message = ""
        if len(available_programs) > 1 and not selected_program:
            promo_message = _("Choose manually from available promotions.")
        elif selected_program:
            missing = _missing_qty_to_next(header, selected_program)
            if missing > 1e-8:
                promo_message = _(
                    "Add %(missing)s unit(s) to unlock promotion %(promo)s.",
                    missing=_format_qty(missing),
                    promo=selected_program.display_name or selected_program.name,
                )

        available_programs_payload = []
        for program in available_programs:
            available_programs_payload.append({
                "id": _safe_program_id(program),
                "name": program.name,
                "display_name": program.display_name or program.name,
                "rule_text": program.rule_text or "",
                "apply_disc_on": program.apply_disc_on,
                "disc_percent": float(program.disc_percent or 0.0),
                "fixed_price": float(program.fixed_price or 0.0),
            })

        applied = applied_program or header.applied_program_ids[:1]
        total_net_amount = amount_total_after_promo if applied else amount_total
        return {
            "available_programs": available_programs_payload,
            "applied_program_id": _safe_program_id(applied) if applied else False,
            "applied_program_name": applied.display_name if applied else "",
            "selected_program_id": _safe_program_id(selected_program) if selected_program else False,
            "selected_program_name": selected_program.display_name if selected_program else "",
            "promo_message": promo_message or "",
            "promo_discount_amount": float(promo_discount or 0.0),
            "amount_total_after_promo": float(amount_total_after_promo or 0.0),
            "total_net_amount": total_net_amount,
        }

    @api.model
    def _empty_promo_payload(self):
        return {
            "available_programs": [],
            "applied_program_id": False,
            "applied_program_name": "",
            "promo_message": "",
            "promo_discount_amount": 0.0,
            "amount_total_after_promo": 0.0,
            "total_net_amount": 0.0,
        }
