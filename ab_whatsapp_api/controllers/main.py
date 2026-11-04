from odoo import http
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools import config


class AbWhatsAppWebhookController(http.Controller):
    @http.route(
        "/ab_whatsapp_api/webhook",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def webhook_verify(self, **kwargs):
        mode = request.params.get("hub.mode")
        challenge = request.params.get("hub.challenge")
        verify_token = request.params.get("hub.verify_token")
        expected_verify_token = (
            config.get("whatsapp_verify_token", "local-dev-verify-token")
            or "local-dev-verify-token"
        ).strip()

        if mode == "subscribe" and challenge and verify_token == expected_verify_token:
            return request.make_response(
                challenge,
                headers=[("Content-Type", "text/plain; charset=utf-8")],
            )
        return request.make_response("Webhook verification failed.", status=403)

    @http.route(
        "/ab_whatsapp_api/webhook",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def webhook_receive(self, **kwargs):
        payload = request.httprequest.get_json(silent=True) or {}
        result = request.env["ab.whatsapp.service"].sudo().process_webhook_payload(payload)
        return request.make_json_response(
            {
                "ok": True,
                "created": len(result.get("created", [])),
                "updated": len(result.get("updated", [])),
            }
        )

    @http.route(
        "/ab_whatsapp_api/media/<int:message_id>",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def media_proxy(self, message_id: int, **kwargs):
        if not request.env.user.has_group("base.group_system"):
            return request.make_response("Forbidden", status=403)
        try:
            data, mime_type, filename = (
                request.env["ab.whatsapp.service"].sudo().get_message_media_content(message_id)
            )
        except UserError as exc:
            return request.make_response(str(exc), status=404)

        force_download = str(request.params.get("download", "")).lower() in {"1", "true", "yes"}
        is_inline_type = (
            (mime_type or "").startswith("image/")
            or (mime_type or "").startswith("audio/")
            or (mime_type or "").startswith("video/")
        )
        disposition = "attachment" if force_download or not is_inline_type else "inline"
        safe_filename = (filename or "media").replace('"', "")

        return request.make_response(
            data,
            headers=[
                ("Content-Type", mime_type or "application/octet-stream"),
                ("Content-Length", str(len(data))),
                ("Content-Disposition", f'{disposition}; filename="{safe_filename}"'),
            ],
        )
