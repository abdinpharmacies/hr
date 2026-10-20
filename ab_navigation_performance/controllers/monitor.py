from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request


class NavigationPerformance(http.Controller):
    @http.route("/ab/performance", type="http", auth="user", website=True, sitemap=False, methods=["GET"])
    def monitor(self, **kwargs):
        if not request.env.user.has_group("base.group_system"):
            raise Forbidden()
        response = request.render("ab_navigation_performance.monitor", {})
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response
