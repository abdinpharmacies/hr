from odoo import http
from odoo.http import request
from odoo.addons.ab_whatsapp_api.controllers.main import AbWhatsAppWebhookController


class GatewayOnlyWebhook(AbWhatsAppWebhookController):
    @http.route()
    def webhook_verify(self, **kwargs):
        return request.make_response('Gone', status=410)

    @http.route()
    def webhook_receive(self, **kwargs):
        return request.make_response('Gone', status=410)
