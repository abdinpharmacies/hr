from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_round
from odoo.tools.safe_eval import safe_eval


class AbSalesReturnUiApi(models.TransientModel):
    _name = "ab_sales_return_ui_api"
    _description = "Sales Return UI API"

    create_date = fields.Datetime(readonly=True)

    @api.model
    def _get_return_header(self, return_header_id):
        header = self.env["ab_sales_return_header"].browse(int(return_header_id or 0)).exists()
        if not header:
            raise UserError(_("Sales return was not found."))
        return header

    @api.model
    def _get_sale_header(self, sale_header_id):
        header = self.env["ab_sales_header"].browse(int(sale_header_id or 0)).exists()
        if not header:
            raise UserError(_("Sales bill was not found."))
        return header

    @api.model
    def _status_label(self, status):
        selection = dict(self.env["ab_sales_return_header"]._fields["status"].selection)
        return selection.get(status, status or "")

    @api.model
    def _status_class(self, status):
        if status == "saved":
            return "text-bg-success"
        if status == "pending":
            return "text-bg-warning"
        return "text-bg-info"

    @api.model
    def _line_uom_options(self, line):
        options = []
        seen = set()
        candidates = line.uom_id
        category = line.product_uom_category_id
        if category:
            candidates |= self.env["ab_product_uom"].search([("category_id", "=", category.id)])
        for uom in candidates.sorted(lambda rec: (rec.factor or 0.0, rec.display_name or "")):
            if uom.id in seen:
                continue
            seen.add(uom.id)
            options.append(
                {
                    "id": uom.id,
                    "name": uom.display_name or uom.name or "",
                    "factor": float(uom.factor or 0.0),
                }
            )
        return options

    @api.model
    def _serialize_line(self, line):
        return {
            "id": line.id,
            "product_name": line.product_id.display_name or "",
            "item_id": int(line.itm_eplus_id or 0),
            "qty_str": line.qty_str or "0",
            "qty": float(line.qty or 0.0),
            "qty_sold": float(line.qty_sold or 0.0),
            "max_returnable_qty": float(line.max_returnable_qty or 0.0),
            "sell_price": float(line.sell_price or 0.0),
            "line_value": float(line.line_value or 0.0),
            "uom_id": line.uom_id.id if line.uom_id else False,
            "uom_name": line.uom_id.display_name or "",
            "uom_options": self._line_uom_options(line),
            "sold_without_balance": bool(line.itm_nexist),
        }

    @api.model
    def _serialize_header(self, header):
        header.ensure_one()
        return {
            "id": header.id,
            "store_id": header.store_id.id if header.store_id else False,
            "store_name": header.store_id.display_name or "",
            "origin_header_id": int(header.origin_header_id or 0),
            "status": header.status or "",
            "status_label": self._status_label(header.status),
            "status_class": self._status_class(header.status),
            "notes": header.notes or "",
            "total_return_qty": float(header.total_return_qty or 0.0),
            "total_return_value": float(header.total_return_value or 0.0),
            "total_sales_net": float(header.total_sales_net or 0.0),
            "sales_return_id": int(header.sales_return_id or 0),
            "f_transaction_id": int(header.f_transaction_id or 0),
            "can_reload": header.status != "saved",
            "can_clear": header.status != "saved",
            "can_total_return": header.status != "saved",
            "can_set_pending": header.status == "prepending",
            "can_push": header.status != "saved",
            "lines": [self._serialize_line(line) for line in header.line_ids],
        }

    @api.model
    def _action_payload(self, return_header_id):
        return {
            "type": "ir.actions.client",
            "tag": "ab_sales.return_ui",
            "name": _("Sales Return"),
            "target": "new",
            "context": {
                **self.env.context,
                "active_id": int(return_header_id),
                "active_ids": [int(return_header_id)],
                "dialog_size": "large",
            },
            "params": {
                "return_header_id": int(return_header_id),
            },
        }

    @api.model
    def open_from_sale_header(self, sale_header_id, **kwargs):
        sale_header = self._get_sale_header(sale_header_id)
        if not sale_header.store_id:
            raise UserError(_("Please select a Store first."))
        if not sale_header.eplus_serial:
            raise UserError(_("This bill has no ePlus serial."))
        try:
            action = sale_header.action_open_sales_return()
        except AccessError:
            raise UserError(_("You do not have access to sales return yet."))
        return_header_id = int(action.get("res_id") or 0)
        if not return_header_id:
            raise UserError(_("Sales return could not be opened."))
        return self._action_payload(return_header_id)

    @api.model
    def get_state(self, return_header_id, **kwargs):
        header = self._get_return_header(return_header_id)
        return self._serialize_header(header)

    @api.model
    def save_notes(self, return_header_id, notes="", **kwargs):
        header = self._get_return_header(return_header_id)
        header.write({"notes": (notes or "").strip()})
        return self.get_state(header.id)

    @api.model
    def _evaluate_qty(self, qty_str):
        text = (qty_str or "").strip()
        if not text:
            return 0.0
        try:
            return float_round(float(safe_eval(text)), precision_digits=4)
        except Exception:
            return 0.0

    @api.model
    def _uom_change_vals(self, line, target_uom, qty_str=None):
        source_factor = float(line.source_uom_factor or 0.0) or 1.0
        old_factor = float(line.uom_id.factor or 0.0) if line.uom_id else 0.0
        if old_factor <= 0:
            old_factor = source_factor
        new_factor = float(target_uom.factor or 0.0) if target_uom else 0.0
        if new_factor <= 0:
            new_factor = source_factor

        current_qty = self._evaluate_qty(qty_str) if qty_str is not None else float(line.qty or 0.0)
        qty_in_small = current_qty * old_factor
        next_qty = qty_in_small / (new_factor or 1.0)

        sold_source = float(line.qty_sold_source or 0.0)
        rem_source = float(line.max_returnable_source or 0.0)
        sell_source = float(line.sell_price or 0.0) * (source_factor or 1.0) / (old_factor or 1.0)
        cost_source = float(line.cost or 0.0) * (source_factor or 1.0) / (old_factor or 1.0)

        return {
            "uom_id": target_uom.id if target_uom else False,
            "qty_str": line._fmt_qty(next_qty),
            "qty_sold": sold_source * source_factor / (new_factor or 1.0),
            "max_returnable_qty": rem_source * source_factor / (new_factor or 1.0),
            "sell_price": sell_source * (new_factor or 1.0) / (source_factor or 1.0),
            "cost": cost_source * (new_factor or 1.0) / (source_factor or 1.0),
        }

    @api.model
    def update_line(self, return_header_id, line_id, qty_str=None, uom_id=False, **kwargs):
        header = self._get_return_header(return_header_id)
        line = header.line_ids.filtered(lambda rec: rec.id == int(line_id or 0))[:1]
        if not line:
            raise UserError(_("Sales return line was not found."))

        write_vals = {}
        if qty_str is not None:
            write_vals["qty_str"] = qty_str or "0"

        if uom_id:
            target_uom = self.env["ab_product_uom"].browse(int(uom_id)).exists()
            if not target_uom:
                raise UserError(_("Selected unit of measure was not found."))
            write_vals.update(self._uom_change_vals(line, target_uom, qty_str=qty_str))

        if write_vals:
            line.write(write_vals)

        return self.get_state(header.id)

    @api.model
    def reload_lines(self, return_header_id, **kwargs):
        header = self._get_return_header(return_header_id)
        header.action_load_lines()
        return self.get_state(header.id)

    @api.model
    def clear_lines(self, return_header_id, **kwargs):
        header = self._get_return_header(return_header_id)
        header.action_clear_lines()
        return self.get_state(header.id)

    @api.model
    def total_return_invoice(self, return_header_id, **kwargs):
        header = self._get_return_header(return_header_id)
        header.action_total_return_invoice()
        return self.get_state(header.id)

    @api.model
    def set_pending(self, return_header_id, **kwargs):
        header = self._get_return_header(return_header_id)
        header.action_set_pending()
        return self.get_state(header.id)

    @api.model
    def push_to_eplus(self, return_header_id, **kwargs):
        header = self._get_return_header(return_header_id)
        header.action_push_to_eplus_return()
        return self.get_state(header.id)

    @api.model
    def abandon_return(self, return_header_id, **kwargs):
        header = self.env["ab_sales_return_header"].browse(int(return_header_id or 0)).exists()
        if not header:
            return {"deleted": False}
        if header.status != "prepending":
            return {"deleted": False, "status": header.status}
        header.unlink()
        return {"deleted": True}
