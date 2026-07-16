import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AbTelegramWebhookController(http.Controller):
    @http.route(
        "/ab_telegram_webhook/webhook",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def webhook_ping(self, **kwargs):
        return request.make_response(
            "ok",
            headers=[("Content-Type", "text/plain; charset=utf-8")],
        )

    @http.route(
        "/ab_telegram_webhook/webhook",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def webhook_receive(self, **kwargs):
        payload = request.httprequest.get_json(silent=True) or {}
        try:
            result = request.env["ab_telegram_service"].sudo().dispatch_webhook_payload(payload)
        except Exception:
            _logger.exception("ab_telegram_webhook: unexpected webhook failure.")
            return request.make_json_response({"ok": False, "echoed": False, "reason": "internal_error"}, status=500)
        return request.make_json_response(result)
