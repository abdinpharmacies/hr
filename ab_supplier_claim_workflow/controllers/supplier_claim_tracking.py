from odoo import http
from odoo.http import request


class SupplierClaimTrackingController(http.Controller):

    def _get_request_lang(self, kwargs):
        lang = kwargs.get('lang') or request.httprequest.cookies.get('frontend_lang')
        if not lang:
            return False
        if request.env['res.lang'].sudo().search_count([('code', '=', lang), ('active', '=', True)], limit=1):
            return lang
        return False

    @http.route(
        [
            '/supplier-claim/<string:tracking_token>',
            '/supplier-claim/<string:claim_number>/<string:tracking_token>',
        ],
        type='http',
        auth='public',
        website=False,
        sitemap=False,
        csrf=False,
    )
    def supplier_claim_tracking(self, tracking_token=None, claim_number=None, **kwargs):
        lang = self._get_request_lang(kwargs)
        if lang:
            request.update_env(context=dict(request.env.context, lang=lang))
        claim = request.env['ab_supplier_claim_cycle'].sudo()._find_by_tracking_token(
            tracking_token,
            claim_number=claim_number,
        )
        if not claim:
            return request.not_found()
        claim._record_tracking_visit(
            ip_address=request.httprequest.remote_addr,
            user_agent=request.httprequest.user_agent.string,
        )
        return request.render(
            'ab_supplier_claim_workflow.supplier_claim_tracking_page',
            {'tracking': claim._get_public_tracking_data()},
        )

    @http.route(
        [
            '/supplier-claim-presence/<string:tracking_token>',
            '/supplier-claim-presence/<string:claim_number>/<string:tracking_token>',
        ],
        type='http',
        auth='public',
        website=False,
        sitemap=False,
        csrf=False,
        methods=['POST'],
    )
    def supplier_claim_tracking_presence(self, tracking_token=None, claim_number=None, **kwargs):
        claim = request.env['ab_supplier_claim_cycle'].sudo()._find_by_tracking_token(
            tracking_token,
            claim_number=claim_number,
        )
        if not claim:
            return request.make_json_response({'ok': False}, status=404)
        online = kwargs.get('online', '1') not in ('0', 'false', 'False', 'off')
        claim._set_tracking_presence(online=online)
        return request.make_json_response({'ok': True, 'online': online})
