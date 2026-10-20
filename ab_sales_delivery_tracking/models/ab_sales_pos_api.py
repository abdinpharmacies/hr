from odoo import api, models, _
from odoo.exceptions import UserError

# Keep aligned with DELIVERY_UI_VERSION in the module-owned POS action.
_DELIVERY_UI_VERSION = "1"


class AbSalesPosApi(models.TransientModel):
    _inherit = "ab_sales_pos_api"

    @api.model
    def pos_submit(self, payload=None, **kwargs):
        incoming = payload if payload is not None else kwargs
        if not isinstance(incoming, dict):
            return super().pos_submit(payload=payload, **kwargs)
        incoming = dict(incoming)
        header = dict(incoming.get("header") or {})
        if header.pop("delivery_ui_version", None) != _DELIVERY_UI_VERSION:
            raise UserError(_(
                "Your POS interface is outdated. Save your draft and reload the page before submitting."
            ))
        # Only a JSON boolean true grants consent; absent or malformed choices do not.
        header["delivery_notify"] = bool(header.get("is_delivery")) and header.get("delivery_notify") is True
        instructions = header.get("delivery_instructions") or ""
        if not isinstance(instructions, str):
            raise UserError(_("Delivery instructions must be text."))
        header["delivery_instructions"] = instructions.strip()
        if header.get("is_delivery") and header["delivery_notify"] and not header["delivery_instructions"]:
            raise UserError(_("Delivery instructions are required when notifying the delivery bot."))
        incoming["header"] = header
        return super().pos_submit(payload=incoming)
