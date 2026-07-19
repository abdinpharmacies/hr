from odoo import http
from odoo.http import request


class TelegramManagersController(http.Controller):

    @http.route('/scc/telegram-managers', type='jsonrpc', auth='user')
    def get_telegram_managers(self):
        Groups = request.env['res.groups']
        return Groups.get_telegram_connected_employees()
