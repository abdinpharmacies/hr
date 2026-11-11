# Copyright (C) 2023-TODAY Cybrosys Technologies (https://www.cybrosys.com).
# Original author: Yadhukrishnan K. Odoo 19 adaptation: emadco88.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).
from odoo import http
from odoo.http import request


class IdleTimer(http.Controller):
    @http.route('/get_idle_time/timer', auth='user', type='jsonrpc', readonly=True)
    def get_idle_time(self):
        user = request.env.user
        return user.idle_time if user.enable_idle else False
