import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AbRequestTelegramController(http.Controller):
    @http.route(
        "/ab_request_telegram/webhook",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def telegram_webhook(self, **kwargs):
        payload = request.httprequest.get_json(silent=True) or {}
        try:
            result = request.env["ab_hr_bot"].sudo().process_telegram_update(payload)
        except Exception:
            _logger.exception("ab_request_telegram: unexpected webhook failure.")
            return request.make_json_response({"ok": False, "message": "internal_error"}, status=500)
        return request.make_json_response(result)
